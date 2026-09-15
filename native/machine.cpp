// The inspected PortForge board remains the single time/memory authority.
// This adapter batches it, exports explicit state, and never calls Python in a step.
#include <algorithm>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "build_identity.hpp"
#include "src/host/genesis_engine.hpp"
#include "src/platform/genesis/snapshot.hpp"
#include "src/platform/genesis/render.hpp"

#ifdef _WIN32
#define AL_API extern "C" __declspec(dllexport)
#else
#define AL_API extern "C" __attribute__((visibility("default")))
#endif

namespace {
thread_local std::string error;
struct GateYield : std::exception {};
class Executor final : public pf::host::GenesisInterpreterExecutor {
public:
    using GenesisInterpreterExecutor::GenesisInterpreterExecutor;
    std::uint32_t gate = 0xffffffffu;
    bool bypass = false, yielded = false;
    std::vector<std::uint32_t> gates;
    pf::host::GenesisNativeOperation staged;
    bool completed = false, declined = false;
    pf::host::GenesisNativeOperation prepare_native_operation() override { return staged; }
    void run_region(const pf::host::GenesisRegionBoundary& boundary) override {
        // After IRQ admission, before the engine's instruction-boundary mutation.
        // The existing engine catches this C++ yield locally; it never crosses FFI.
        if (staged.execute) { declined = true; throw GateYield{}; }
        if (pc() == gate || std::find(gates.begin(), gates.end(), pc()) != gates.end()) {
            if (!bypass) { yielded = true; throw GateYield{}; }
            bypass = false;
        }
        GenesisInterpreterExecutor::run_region(boundary);
    }
};
struct Handle {
    pf::genesis::Machine machine;
    Executor executor;
    pf::host::GenesisEngine engine;
    pf::genesis::SnapshotIdentity identity;
    pf::genesis::Renderer renderer;
    std::vector<std::int16_t> pcm;
    bool failed = false;
    bool pcm_overflow = false, discard_pcm = false;
    // The adapter holds no game facts: the snapshot identity is the cartridge's
    // hash plus the profile id/hash the caller declares (genesis_re.machine).
    Handle(std::vector<std::uint8_t> rom, const char* profile_id, const char* profile_sha256)
        : machine(rom, pf::genesis::ntsc_profile()), executor(machine), engine(machine, executor),
          identity{pf::Sha256::of(rom.data(), rom.size()), profile_id, profile_sha256} {
        identity.validate();
        machine.pcm_trace = {this, [](void* p, std::int32_t left, std::int32_t right, std::uint64_t) {
            auto& h = *static_cast<Handle*>(p);
            if (h.discard_pcm) return; // Explicit presentation-only discard, not verification.
            auto& out = h.pcm;
            if (out.size() < 2 * 106536) {
                out.push_back(static_cast<std::int16_t>(std::clamp(left, -32768, 32767)));
                out.push_back(static_cast<std::int16_t>(std::clamp(right, -32768, 32767)));
            } else h.pcm_overflow = true;
        }};
    }
};
Handle* active = nullptr;
Handle& get(void* value) {
    if (!value || value != active) throw std::runtime_error("Invalid or closed machine handle");
    return *active;
}
template<class F> int protect(F&& f) noexcept {
    try { error.clear(); f(); return 0; }
    catch (const std::exception& e) { error = e.what(); return -1; }
    catch (...) { error = "Unknown native exception"; return -1; }
}
void require(bool yes, const char* message) { if (!yes) throw std::runtime_error(message); }
std::vector<std::uint8_t> snapshot(Handle& h) {
    require(!h.failed, "Execution failed; reset in a new machine before capturing");
    require(!h.executor.bypass, "Cannot snapshot an armed bypass");
    auto body = pf::genesis::encode_snapshot(h.machine, h.identity);
    pf::genesis::snapshot_detail::Writer w;
    const std::uint8_t magic[] = {'A','L','N','A','T','0','0','1'};
    w.bytes(magic, 8);
    auto scheduler = h.engine.capture_scheduler_state();
    w.field(scheduler.delivered); w.put<std::uint8_t>(scheduler.level_recognised ? 1 : 0);
    w.bytes(body.data(), body.size());
    auto result = w.take();
    auto digest = pf::Sha256::of(result.data(), result.size());
    result.insert(result.end(), digest.begin(), digest.end());
    return result;
}
// ALNAT001 wraps exactly the pinned PFGENS02 field codec. Inspect before any
// mutation; the PF decoder performs the remaining per-device validation on import.
std::uint64_t snapshot_tick(Handle& h, const std::uint8_t* data, std::uint64_t size) {
    require(data && size >= 17 + 10 + 44 + 128 && size <= 4 * 1024 * 1024, "Invalid snapshot size");
    require(std::memcmp(data, "ALNAT001", 8) == 0, "Unsupported native snapshot schema");
    require(std::string(reinterpret_cast<const char*>(data + size - 64), 64) == pf::Sha256::of(data, size - 64), "Snapshot integrity mismatch");
    require(data[16] <= 1, "Invalid scheduler latch");
    const auto* inner = data + 17;
    const auto inner_size = size - 17 - 64;
    require(std::string(reinterpret_cast<const char*>(inner + inner_size - 64), 64) == pf::Sha256::of(inner, inner_size - 64), "Inner snapshot integrity mismatch");
    std::vector<std::uint8_t> body(inner, inner + inner_size - 64);
    pf::genesis::snapshot_detail::Reader reader(body);
    std::array<std::uint8_t,8> magic{}; reader.bytes(magic.data(), magic.size());
    require(magic == pf::genesis::kGenesisSnapshotMagic && reader.get<std::uint16_t>() == 2, "Unsupported inner snapshot schema");
    require(pf::genesis::snapshot_detail::text(reader) == h.identity.program_sha256 &&
            pf::genesis::snapshot_detail::text(reader) == h.identity.profile_id &&
            pf::genesis::snapshot_detail::text(reader) == h.identity.work_profile_sha256, "Snapshot identity mismatch");
    // Codec v2 ends in five uint64 fields (starting with master tick), one
    // uint32 standing PC and the integrity hash. This coupling lives here only.
    std::uint64_t tick = 0;
    for (unsigned i=0; i<8; ++i) tick |= std::uint64_t(body[body.size()-44+i]) << (8*i);
    return tick;
}
}

// Project state contract, independent of source/build provenance. Bump when
// persisted state or continuation semantics change; early artifacts regenerate.
AL_API std::uint32_t al_state_version() noexcept { return 1; }
AL_API std::uint32_t al_abi() noexcept { return 2; }
AL_API const char* al_source_id() noexcept { return AL_SOURCE_ID; }
AL_API const char* al_build_info() noexcept { return AL_BUILD_INFO; }
AL_API const char* al_error() noexcept { return error.c_str(); }
AL_API int al_create(const std::uint8_t* rom, std::uint64_t size, const char* profile_id, const char* profile_sha256, void** out) noexcept {
    return protect([&] {
        require(out, "Missing handle output"); *out = nullptr;
        require(!active, "Only one active machine per process is supported");
        require(rom && size >= 256 && size <= 0x400000 && profile_id && profile_sha256, "Invalid ROM or profile identity");
        auto h = std::make_unique<Handle>(std::vector<std::uint8_t>(rom, rom + size), profile_id, profile_sha256);
        active = h.release(); *out = active;
    });
}
AL_API int al_destroy(void* ptr) noexcept {
    return protect([&] { auto* h = &get(ptr); active = nullptr; delete h; });
}
AL_API int al_run(void* ptr, std::uint64_t target, std::uint64_t instructions, std::uint32_t* reason) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(!h.failed, "Machine invalidated by earlier execution error");
        require(reason && ((target != 0) != (instructions != 0)), "Specify one finite run limit");
        require(!target || target >= h.machine.master_cycles, "Cannot run backwards");
        h.executor.yielded = false;
        auto r = target ? h.engine.run_until_master(target) : h.engine.run(instructions);
        if (h.pcm_overflow) {
            h.failed = true;
            throw std::runtime_error("PCM output capacity exceeded; execution invalidated. Drain audio between smaller batches or select explicit discard policy.");
        }
        if (h.executor.yielded) { *reason = 1; return; }
        if (r.end.classification != pf::RunEndClass::ExecutionSuspension) {
            h.failed = true;
            throw std::runtime_error(r.ending + ": " + r.detail);
        }
        *reason = 0;
    });
}
AL_API int al_gate(void* ptr, std::uint32_t pc, std::uint32_t bypass) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(bypass <= 1, "Invalid bypass flag");
        require(pc == 0xffffffffu || pc <= 0xffffffu, "Gate address out of range");
        require(!bypass || (pc != 0xffffffffu && h.executor.pc() == pc), "Bypass must start at its gate");
        h.executor.gate = pc; h.executor.bypass = bypass != 0;
    });
}
AL_API int al_gates(void* ptr, const std::uint32_t* pcs, std::uint64_t count) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(count <= 64 && (pcs || !count), "Invalid gate set");
        for (std::uint64_t i=0; i<count; ++i) require(pcs[i] <= 0xffffffu, "Gate address out of range");
        h.executor.gates.clear();
        if (count) h.executor.gates.assign(pcs, pcs+count);
        h.executor.gate = 0xffffffffu; h.executor.bypass = false;
    });
}
AL_API int al_registers(void* ptr, std::uint32_t* values, std::uint64_t count) noexcept {
    return protect([&] {
        auto& c = get(ptr).machine.mem.cpu;
        require(values && count == 18, "Expected 18 register fields");
        std::copy(c.d, c.d+8, values); std::copy(c.a, c.a+8, values+8);
        values[16] = c.pc; values[17] = c.status;
    });
}
// Plans are bounded sparse effects calculated from live RAM while stopped.
// No effect is applied until the EXISTING engine admits the entire operation.
// This ABI deliberately supports work RAM only, not unqualified MMIO batching.
AL_API int al_atomic(void* ptr, std::uint64_t target, std::uint64_t cycles,
                    std::uint64_t instructions, std::uint32_t last_pc,
                    const std::uint32_t* addresses, const std::uint8_t* bytes, std::uint64_t count,
                    const std::uint32_t* fields, const std::uint32_t* values, std::uint64_t nfields,
                    std::uint32_t* accepted) noexcept {
    return protect([&] {
        auto& h = get(ptr); auto& m = h.machine; auto& e = h.executor;
        require(!h.failed && e.yielded && !e.bypass && !e.staged.execute, "Atomic replacement requires a parked gate");
        require(accepted && cycles && cycles <= 100000 && instructions && instructions <= 10000,
                "Invalid atomic cost");
        require(last_pc <= 0xffffffu && !(last_pc & 1), "Invalid last instruction PC");
        require(count <= 2048 && (!count || (addresses && bytes)) && nfields <= 18 && (!nfields || (fields && values)), "Invalid effect buffers");
        for (std::uint64_t i=0; i<count; ++i)
            require(addresses[i] >= 0xff0000u && addresses[i] <= 0xffffffu, "Atomic writes require work RAM");
        for (std::uint64_t i=0; i<nfields; ++i) {
            require(fields[i] < 18, "Invalid register field");
            if (fields[i] == 16) require(values[i] <= 0xffffffu && !(values[i]&1), "Invalid continuation PC");
            if (fields[i] == 17) require(values[i] <= 65535 && ((values[i] ^ m.mem.cpu.status) & ~31u) == 0,
                                      "Atomic status updates may change CCR only");
        }
        *accepted = 0;
        require(target >= m.master_cycles, "Atomic deadline precedes gate");
        // Preserve the caller's input/checkpoint limit as well as the engine's
        // native-operation raster/IRQ/DMA/trace/instruction guards.
        if (cycles >= (target - m.master_cycles) / m.profile.m68k_divider) return;
        // A currently shared bank is outside this atomic domain. A bank change
        // during the span is also watched before its first RAM access below.
        if (m.z80.running() && (std::uint32_t(m.z80.bank) << 15) >= 0xe00000u) return;
        const auto entry = e.pc();
        auto& host = m.z80.host;
        require(!host.observe_window, "Atomic operation cannot replace a sound observer");
        e.completed = e.declined = false;
        e.staged = {cycles, instructions, last_pc, [&] {
            require(e.pc() == entry, "Atomic entry changed before admission");
            for (std::uint64_t i=0; i<count; ++i) m.mem.write8(addresses[i], bytes[i]);
            for (std::uint64_t i=0; i<nfields; ++i) {
                auto f = fields[i], v = values[i];
                if (f < 8) m.mem.cpu.d[f] = v;
                else if (f < 16) m.mem.cpu.a[f-8] = v;
                else if (f == 16) m.mem.cpu.pc = v;
                else m.mem.cpu.status = static_cast<std::uint16_t>(v);
            }
            e.completed = true;
        }};
        host.observe_window = [](void*, std::uint32_t at, bool) {
            if (at >= 0xe00000u) throw std::runtime_error("Atomic shared-RAM guard: Z80 window observed work RAM");
        };
        struct Clear {
            Executor& e; pf::genesis::Z80Box::Host& host;
            ~Clear() { e.staged = {}; host.observe_window = nullptr; }
        } clear{e, host};
        auto result = h.engine.run(instructions);
        if (e.declined && !e.completed) return;
        if (!e.completed || result.end.classification != pf::RunEndClass::ExecutionSuspension || h.pcm_overflow) {
            h.failed = true;
            throw std::runtime_error("Atomic execution failed; machine invalidated: " + result.detail);
        }
        e.yielded = false; *accepted = 1;
    });
}
AL_API int al_info(void* ptr, std::uint64_t* out, std::uint64_t count) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(out && count == 8, "Info buffer must contain eight uint64 values");
        const auto& m = h.machine;
        const std::uint64_t values[] = {m.master_cycles, m.mem.instructions, m.mem.cpu_cycles,
            m.z80.instructions(), m.mem.cpu.pc, m.mem.cpu.status, m.io.pad1, h.engine.vertical_delivered()};
        std::copy(std::begin(values), std::end(values), out);
    });
}
AL_API int al_pad(void* ptr, std::uint32_t mask) noexcept {
    return protect([&] { require(mask <= 255, "Pad mask out of range"); get(ptr).machine.io.pad1 = mask; });
}
AL_API int al_ram(void* ptr, std::uint8_t** out, std::uint64_t* size) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(out && size, "Missing RAM output");
        *out = h.machine.mem.memory.data() + pf::genesis::kWorkRamBase; *size = pf::genesis::kWorkRamSize;
    });
}
AL_API int al_export(void* ptr, std::uint8_t* out, std::uint64_t capacity, std::uint64_t* size) noexcept {
    return protect([&] {
        auto bytes = snapshot(get(ptr)); require(size, "Missing snapshot size"); *size = bytes.size();
        if (out) { require(capacity >= bytes.size(), "Snapshot output too small"); std::memcpy(out, bytes.data(), bytes.size()); }
    });
}
AL_API int al_import(void* ptr, const std::uint8_t* data, std::uint64_t size) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(!h.failed, "Restore requires a valid machine");
        snapshot_tick(h, data, size);
        std::uint64_t delivered = 0;
        for (unsigned i = 0; i < 8; ++i) delivered |= std::uint64_t(data[8 + i]) << (8 * i);
        // Upstream decoder validates into temporary value state before mutation.
        pf::genesis::restore_snapshot(h.machine, {data + 17, data + size - 64}, h.identity);
        h.engine.restore_scheduler_state({delivered, data[16] != 0});
        h.pcm.clear(); h.executor.bypass = false; h.executor.yielded = false;
    });
}
AL_API int al_snapshot_tick(void* ptr, const std::uint8_t* data, std::uint64_t size, std::uint64_t* tick) noexcept {
    return protect([&] { require(tick, "Missing tick output"); *tick = snapshot_tick(get(ptr), data, size); });
}
AL_API int al_audio_policy(void* ptr, std::uint32_t discard) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(discard <= 1 && !h.failed, "Invalid audio policy or machine");
        require(h.pcm.empty(), "Drain existing PCM before changing audio policy");
        h.discard_pcm = discard != 0;
    });
}
AL_API int al_frame(void* ptr, std::uint8_t* rgb, std::uint64_t capacity, std::uint32_t* width, std::uint32_t* height) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(rgb && width && height, "Missing frame output");
        auto f = h.renderer.render(h.machine.vdp);
        require(capacity >= f.pixels.size() * 3, "Frame buffer too small");
        *width = f.width; *height = f.height;
        for (std::size_t i = 0; i < f.pixels.size(); ++i) {
            rgb[3*i] = f.pixels[i] >> 16; rgb[3*i+1] = f.pixels[i] >> 8; rgb[3*i+2] = f.pixels[i];
        }
    });
}
AL_API int al_audio(void* ptr, std::int16_t* out, std::uint64_t capacity, std::uint64_t* count) noexcept {
    return protect([&] {
        auto& h = get(ptr); require(!h.pcm_overflow, "PCM was lost in an invalidated run");
        require(count, "Missing PCM count"); *count = h.pcm.size();
        if (out) { require(capacity >= h.pcm.size(), "PCM output too small"); std::copy(h.pcm.begin(), h.pcm.end(), out); h.pcm.clear(); }
    });
}
