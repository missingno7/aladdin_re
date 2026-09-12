// The inspected PortForge board remains the single time/memory authority.
// This adapter batches it, exports explicit state, and never calls Python in a step.
#include <algorithm>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
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
    void run_region(const pf::host::GenesisRegionBoundary& boundary) override {
        // After IRQ admission, before the engine's instruction-boundary mutation.
        // The existing engine catches this C++ yield locally; it never crosses FFI.
        if (pc() == gate) {
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
    Handle(std::vector<std::uint8_t> rom, const char* profile)
        : machine(rom, pf::genesis::ntsc_profile()), executor(machine), engine(machine, executor),
          identity{pf::Sha256::of(rom.data(), rom.size()), "aladdin-usa-ntsc-v1", profile} {
        identity.validate();
        machine.pcm_trace = {this, [](void* p, std::int32_t left, std::int32_t right, std::uint64_t) {
            auto& out = static_cast<Handle*>(p)->pcm;
            // Bounded output queue. Dropping presentation PCM never stops chip time.
            if (out.size() < 2 * 106536) {
                out.push_back(static_cast<std::int16_t>(std::clamp(left, -32768, 32767)));
                out.push_back(static_cast<std::int16_t>(std::clamp(right, -32768, 32767)));
            }
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
}

AL_API std::uint32_t al_abi() noexcept { return 1; }
AL_API const char* al_source_id() noexcept { return AL_SOURCE_ID; }
AL_API const char* al_error() noexcept { return error.c_str(); }
AL_API int al_create(const std::uint8_t* rom, std::uint64_t size, const char* profile, void** out) noexcept {
    return protect([&] {
        require(out, "Missing handle output"); *out = nullptr;
        require(!active, "Only one active machine per process is supported");
        require(rom && size >= 256 && size <= 0x400000 && profile, "Invalid ROM or profile");
        auto h = std::make_unique<Handle>(std::vector<std::uint8_t>(rom, rom + size), profile);
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
        require(data && size >= 81 && size <= 4 * 1024 * 1024, "Invalid snapshot size");
        require(std::memcmp(data, "ALNAT001", 8) == 0, "Unsupported native snapshot schema");
        require(std::string(reinterpret_cast<const char*>(data + size - 64), 64) == pf::Sha256::of(data, size - 64), "Snapshot integrity mismatch");
        require(data[16] <= 1, "Invalid scheduler latch");
        std::uint64_t delivered = 0;
        for (unsigned i = 0; i < 8; ++i) delivered |= std::uint64_t(data[8 + i]) << (8 * i);
        // Upstream decoder validates into temporary value state before mutation.
        pf::genesis::restore_snapshot(h.machine, {data + 17, data + size - 64}, h.identity);
        h.engine.restore_scheduler_state({delivered, data[16] != 0});
        h.pcm.clear(); h.executor.bypass = false; h.executor.yielded = false;
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
        auto& h = get(ptr); require(count, "Missing PCM count"); *count = h.pcm.size();
        if (out) { require(capacity >= h.pcm.size(), "PCM output too small"); std::copy(h.pcm.begin(), h.pcm.end(), out); h.pcm.clear(); }
    });
}
