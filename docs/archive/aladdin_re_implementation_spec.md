# Frozen historical evidence

This report preserves ROM mapping, qualification, and recovery decisions at its source freeze. It is not current operating guidance: use the immutable cold-start input-history workflow in [../history.md](../history.md). Current commands do not promise to load legacy replay or snapshot artifacts referenced below.

# Aladdin RE — implementation specification

**Version:** 3 · **Architecture reviewed:** 13 September 2026  
**Audience:** the coding agent and its supervising agent  
**Project:** `aladdin_re` · **Python package:** `aladdin_sega`  
**Target:** one user-supplied Disney’s Aladdin Mega Drive / Genesis ROM revision and one console profile

**Platform scope amendment (user decision, 12 September 2026):** Capture,
development and verification run on the user's Windows x64 machine. Linux builds
and Windows/Linux artifact interchange are outside the current scope and do not
block any milestone. Explicit serialization and fresh-process Windows restore
remain required.

> Build a playable, recordable Aladdin first. The user will supply gameplay recordings and snapshots. The AI then owns the recovery, verification, diagnosis, and incremental conversion into source. Reuse controllable chip libraries instead of implementing their internals again.

The capture and first recovery milestones below are already implemented. Inspect current code and STATUS before using this specification; old milestone checklists and conceptual APIs are not automatic TODOs. The current task and concrete Aladdin recovery requirements take precedence over earlier proposals.

## Current implementation decisions

The [necessity review](architecture-review.md) distinguishes implementation ownership
from recovery control, measures the current loop, and identifies the smallest
next capability. Use only what this Aladdin recovery actually needs.

The bounded architecture audit is implemented; see
[component-migration.md](component-migration.md) for compiler-derived dependencies
and [STATUS.md](../STATUS.md) for executed evidence. The
[ownership policy](../External%20Components%20and%20Machine%20Ownership%20Policy.md)
is authoritative for component ownership. These decisions supersede early
proposals below where a proposed layout or example differs from current code.

- PortForge is a donor. Retain the working M68000/Z80, VDP and GenesisEngine
  behind the project ABI; do not rewrite them for nominal ownership.
- Independent Nuked cores are direct pinned dependencies. Borrowed sound timing
  and state adapters remain until an actual integration change warrants absorption.
- Runtime and native-test donor closures are separate. Session/census/input-script
  and verdict code are test-only; they are not project replay dependencies.
- Project Python owns recovery, artifacts, comparison and presentation. Keep
  snapshot payloads opaque outside the native codec; enforce this boundary with
  the lightweight architecture guard.
- Current archives use version 2 and explicit machine-state contract 1. Reject
  early formats clearly and regenerate at new paths. Do not retain compatibility
  tables or source-transition chains. Source hashes identify builds; the profile
  contains behavioral configuration, not donor commits or private codec names.
- `recovered.py` contains editable game behavior; `recovery.py` contains small
  gate/qualification policy. The buffer clear and open detach region are already
  implemented. Expand connected recovery next, without a prolonged cleanup phase.

## 1. Product, workflow, and non-goals

Build a small Python-hosted development environment in which the original Aladdin runs, can be inspected and replayed, and progressively becomes editable game source. This is neither a remake nor an emulator research project for its own sake.

There are two concurrent recovery workstreams:

- **Carrier expansion:** expose increasingly connected regions as editable Python, with local control flow, known calls, live memory views, and explicit remaining legacy transfers.
- **Mechanism replacement:** establish bounded contracts inside those regions, replace their implementations with ordinary game code, and remove obsolete runtime adapters.

Editable source is not the same as independently replaceable source. A routine may be useful editable carrier while it still uses guest registers, guest-backed memory, or a legacy callback. Independent replacement additionally needs a supported input domain, outputs, effects, continuation, aliasing, and timing contract.

**The first delivery is capture-ready gameplay, not the first completed decompilation.** It must let the user launch Aladdin, play, start/stop recording, and capture a snapshot without learning internal addresses or running probes. The first human gameplay replay comes from the user after this milestone. Do not block recorder development on a recording that cannot exist yet.

The AI handles everything downstream: artifact validation, reference replay, witness extraction, execution maps, candidate selection, source recovery, comparison, regression tests, and concise progress reports. Additional user recordings extend scenario coverage; they are not an excuse to ask the user to debug the implementation.

### Scope

Use Python 3.12 as the initial development baseline. Support interactive and headless Windows x64 on the user's machine. Other Python versions/platforms, including Linux, are outside the current scope unless subsequently requested. Use `pygame` for window/input/audio output only; headless commands must work without initializing a display or sound device.

Initially exclude other games, PAL/NTSC variants beyond the selected profile, Sega CD, 32X, a general plugin system, universal IR, a new language, cloud orchestration, a web dashboard, automatic C++ export, and a wholesale native-object migration.

A final port may still use emulated graphics/sound chips and original ROM data. Removing M68000 execution, removing Z80 sound-driver execution, removing historical memory layout, and removing the ROM as an asset container are **independent properties**. Do not claim “CPU-free” merely because M68000 gameplay is recovered while the Z80 still executes its original driver.

## 2. Architecture decisions to implement

| Area | Decision |
|---|---|
| Main language | Python for editable carrier, recovered game code, tools, and high-level orchestration. No pure-Python-chip ideology. |
| Chip implementation | Reuse suitable isolated cores, including CPU cores. Wrap C/C++ rather than porting proven chip internals into Python. |
| Existing Sega work | Prefer the already working PortForge Sega model and validated integrations. Audit actual local source before importing it. |
| Selected cores | Retained donor M68000/Z80 and direct upstream Nuked OPN2/PSG. Musashi or floooh/chips are possible future references/replacements only when evidence warrants a change. |
| VDP / board integration | Reuse the existing Sega implementation/model. Write only the missing integration or evidence-backed behavior; do not copy a whole console engine behind an opaque `run_frame()`. |
| Native interface | One small, versioned C ABI with opaque handles, explicit errors and state export. Default Python binding: `ctypes`; reuse an existing sound wrapper if it already meets the contract. |
| Packaging | Standard CMake plus a supported Python build backend such as scikit-build-core. No compiler invocation or dependency download on first gameplay frame. |
| State | One authoritative set of guest RAM and chip state per machine. Named fields are live views until a separate storage migration is qualified. |
| Time | Integer console master ticks with explicit conversion remainders and deterministic event ordering. Host wall time only paces presentation. |
| Recording | User-generated external input events, timestamped when applied to the simulated machine. Immutable source recording, separate derived reference results. |
| Snapshot | Versioned, portable, explicit state serialization; safe scheduler boundaries; no Python stack serialization and no raw C-struct files. |
| Original vs candidate | Same frozen input stream, independent mutable states. Default isolation: one active machine per worker process, reference and candidate in separate processes. |
| Recovery | Open carrier regions are allowed. Unknown executable behavior remains an explicit legacy route, never a fabricated result. |
| First milestone | Original-code Aladdin with reliable capture, replay, snapshot restore, and basic diagnostics. User recording follows. |

These are defaults, not permission to build several competing implementations. When the existing workspace provides a simpler proven equivalent, use it and record the reason. A default may be rejected for a demonstrated control, correctness, performance, or licensing problem—not speculative preference.

## 3. Mandatory reuse policy

**Reuse a small chip library when we can control its execution and observe/save the state needed for this project.** This applies equally to sound chips and CPUs. A missing Python package is not a reason to reinvent the chip: implement a wrapper.

A reusable core must permit, directly or through a small reviewable adapter:

1. Caller-controlled advancement; no hidden host clock or autonomous thread.
2. Correctly ordered bus/register operations, interrupt handling, and explicit timing units.
3. Complete save/restore of relevant internal execution state.
4. Controlled memory ownership and acceptable instance/global-state behavior.
5. A pinned source revision, preserved notices, and a compatible distribution plan.

The core owns chip internals. This project owns the console profile, integration, input timeline, execution selection, and recovery boundaries. A batching helper may advance tightly coupled components under that model; it must not introduce a second, contradictory machine model.

Do not copy a console-wide renderer/audio scheduler into a chip wrapper merely because it is nearby upstream. Conversely, do not reject an already working small Sega subsystem because some of its glue is C++ rather than Python.

### Concrete candidates and constraints

- **M68000 — Musashi:** a standalone C processor core with configurable memory and interrupt integration. It is the fresh-integration default, not a requirement to discard a suitable existing core. Its instruction callback requires special care for interception; see §7. [R4]
- **Z80 — `floooh/chips/z80.h`:** a standalone cycle-stepped core with explicit pins. The wrapper must provide Sega reset/bus-ownership behavior and batch ticking in C. Do not write a second Python Z80. [R5]
- **FM — Nuked OPN2:** use the appropriate pinned YM2612/YM3438 mode for the selected console profile and retain exact control over clocking and register access. [R6]
- **PSG — Nuked-PSG:** an actual YM7101 PSG implementation exists; do not start by implementing a generic SN76489 approximation and discovering variant differences later. [R7]
- **VDP:** first inspect the PortForge VDP and any existing isolated dependency. Use the least disruptive controllable implementation. A missing reusable standalone core permits targeted implementation work; it does not authorize a new gate-level console simulator.

Licenses differ: the inspected OPN2 header carries LGPL-2.1-or-later, whereas Nuked-PSG source carries GPLv2-or-later. Record exact licenses and local modifications; do not label the combined distribution permissive by assumption. Keep third-party source and notices available. This specification does not settle project-wide licensing for the implementer. [R6, R7]

Do not choose a whole-console circuit-level simulation as the default just because it offers maximum detail. Nuked-MD is useful as a potential reference, but its author's 2023 report described a very large realtime deficit. That historical report is not a current benchmark; the relevant decision here is to reuse suitable *small* cores and measure the actual integrated workload. [R10]

## 4. Inspect existing work before writing replacements for it

Locate these projects in the actual workspace:

- `pre2_port`: recovered function composition, original-memory views, detached verification adapters, and the progression toward a standalone game.
- `dos_re`: deterministic capture/replay, state/continuation handling, diagnostics, and the lessons about instruction-budget clocks.
- `port_forge` / `PortForge`: Sega board model, devices, timing, integration tests, and working native dependencies.
- `aladdin_sega_forged`: exact ROM identity, known region entries, existing live views, placement/sprite-builder work, and actual callback/stack behavior.

Paths and names above are discovery hints. Never fabricate file paths or claim an unavailable checkout was inspected. Public GitHub access during preparation did not expose the current PortForge/Aladdin implementation. The implementing agent must inspect the local copies and pin the source commits it actually uses.

Do not confuse current `dos_re` with the historical revision embedded in early Pre2. The inspected public README describes `dos_re 3.0`, a broader evidence/IR/planning system. Borrow applicable mechanisms and tests, not that entire architecture. [R1, R2, R3]

Create a compact table in `docs/STATUS.md`:

```text
component | source commit/path | retained behavior | test/evidence | remaining gap
```

Keep the old projects unchanged. Copy or depend on a minimal coherent component with its provenance; do not bulk-import old reports, compatibility trees, or unused registries.

## 5. Minimal project structure and dependency rules

The current structure reflects working ownership; create subpackages only when
there is enough code to justify them:

```text
src/aladdin_sega/
  recovered.py        # editable leaf and open composed game region
  recovery.py         # project gate selection, admission dispatch and mutants
  machine.py          # small typed native ABI; no Aladdin routine addresses
  profile.py          # selected ROM and behavioral configuration
  artifacts.py        # containers, inputs; machine payload stays opaque
  verification.py     # fresh-process observations and comparison
  receipt.py          # exact execution provenance
  frontend.py         # input, window and host audio presentation
native/machine.cpp    # retained Genesis integration behind project C ABI
third_party/          # direct sound cores; separate donor locks and actual graph
scripts/             # short witnesses, build checks, focused source export
recordings/          # ignored immutable user originals and separately derived v2 files
artifacts/           # ignored derived evidence and preserved reference builds
```

Recovered behavior must not import the CPU binding, dispatcher, verifier or donor
framework. Pass narrow live storage services and explicit input registers.
Snapshot/replay infrastructure works without importing an oracle; verification
depends on running code, never vice versa. Frontend callbacks do not own time.
No universal manifest engine, island registry, plugin discovery or abstract
backend hierarchy is required for this implementation.

## 6. State, bus, and virtual time

### One authority, including across Python/native code

Keep one owned instance of each RAM bank and chip state. Python views and native fast paths must access that same storage. No per-tick “read RAM into Player; update Player; copy all fields back” while other code can write RAM independently. Pre2's object-runtime documentation explicitly records the danger of competing mutable authorities. [R1]

Choose a fixed allocation and document ownership. Pin Python buffers exported to C for the machine lifetime, or expose C-owned storage through safe live views. Do not resize pinned buffers. On restore, either preserve storage identities or invalidate/rebind every view and native pointer; test this rather than relying on incidental addresses.

Use separate APIs for side-effecting bus reads and diagnostic `peek`. MMIO and DMA go through the modeled bus. A debugger must not clear status or advance hardware merely by displaying it. Guest addresses, address-register values, and RAM offsets are different concepts; preserve the original operand widths and bus mapping.

Identify executable writable memory. Any decode/region cache must invalidate when those bytes change. A binding derived from ROM bytes must not quietly apply to unrelated RAM code at the same apparent address.

### Clock and scheduler

Use a monotonically increasing integer master-tick timeline. Region, chip mode, power-on RAM policy, core options, and time conversion ratios belong in the pinned machine profile. Represent fractional device phases/remainders explicitly and include them in snapshots.

Reuse the existing Sega scheduling rules where validated. Coordinate M68000, Z80, VDP/DMA, interrupts, controller protocol, and audio deadlines. Stable same-timestamp ordering must follow the modeled hardware, not an arbitrary sort by component name. Version that policy.

Do not assume one display frame equals one gameplay update. User input may be sampled at a defined frame boundary for convenience, but the recorder writes its *actual applied master tick*. Headless execution, pause, turbo, host frame dropping, or carrier speedups must not change the simulated input timeline.

Batch execution between relevant synchronization points. A core's cycle budget may finish on an instruction boundary beyond the requested count; return actual consumed time and preserve overshoot/debt. Never silently truncate executed cycles or run devices backwards to hide overshoot. Core execution granularity limits the accuracy claim: instruction/scanline synchronization is not automatically exact bus-cycle emulation.

A clocked chip can have sub-instruction behavior while the board model is coarser. Record both. Target demonstrated correctness for this profile and the exercised scenarios, not an unsupported claim of cycle-perfect hardware.

### Time across recovered code

A replacement must not perform all writes immediately and then add an arbitrary constant cycle count at the end. A second CPU, DMA, interrupt, or timed device read may observe the intermediate order.

For initial live replacements choose one supported route:

- Retain the needed timing/event boundaries in generated carrier bookkeeping.
- Run a bounded atomic segment only after checking that no relevant observer/event can intervene, and account for its modeled elapsed time correctly.
- Use a separately qualified semantic contract that explicitly permits a different internal schedule while preserving the relevant observations.

If a guard requires legacy execution, choose it **before the candidate's first mutation**. Do not execute half the candidate and then repeat the original. Use local admission checks rather than introducing a generic rollback engine.

A timing recipe may be derived from original control flow and runtime inputs. It may not be an array of durations indexed by replay tick, nor may the shipped path execute the original in parallel just to discover the answer/time to copy.

Strict carrier equivalence is the initial default. A later semantic-tick comparison is a separate named contract, not an excuse to silently weaken the existing replay test.

## 7. Native integration: concrete pitfalls and required control tests

### Wrapper contract

Use opaque handles and fixed-width types. The following describes the wrapper to build, not an API all upstream libraries already expose:

```text
create(profile) / destroy(handle)
reset(handle)
advance(handle, budget_or_deadline) -> actual_time, stop_reason
read_at / write_at                  # where appropriate for the device
export_state / import_state        # versioned explicit fields
inspect_state                      # read-only diagnostic representation
```

CPU execution additionally needs: run to an instruction/region boundary, inspect/set architectural state, deliver interrupts, intercept a selected PC **before** its opcode executes, and resume original execution once without re-triggering the same interception.

Prefer a C-side membership check for active interception addresses. Do not cross into Python for every instruction or every ordinary ROM/RAM access just to discover that nothing needs attention. A small native memory map can directly address the same pinned buffers, routing only MMIO/special events through the controlled integration. Test that instrumented and fast paths have identical effects.

For a fresh wrapper, use `ctypes` with explicit `argtypes`/`restype`, strong ownership of callbacks and buffers, and structured native error returns. Load the packaged library from its known path. Never depend on accidental C integer sizes, callback lifetime, or current-directory DLL lookup. The Python documentation specifically warns that callback objects can be garbage-collected unless references are retained. [R8]

C must return normally across the FFI boundary. No `longjmp` through Python, C++ exception through a C ABI, or ignored Python callback exception that supplies a guessed bus value. Where a callback cannot abort immediately, record an error, stop safely, and invalidate that run rather than comparing a corrupted continuation.

**Instance policy:** one active machine per process in v1. Run reference/candidate in separate workers launched on Windows. Do not assume the GIL makes a global-state CPU core safe, or rely on Unix-only fork inheritance. Freeze process-global chip configuration at worker initialization. This avoids building a reentrant-core refactor merely for verification.

### Musashi: intercept before execution, not after

The inspected `m68k_execute` loop calls `m68ki_instr_hook(REG_PC)` and then proceeds to fetch and execute the instruction before checking the remaining cycle budget. `m68k_end_timeslice()` changes cycle accounting; calling it inside that hook is **not itself a stop-before-opcode guarantee**. [R4]

Implement or reuse a real pre-instruction yield gate. If Musashi is selected, a tiny documented local patch that checks the gate and exits before opcode fetch is preferable to a new CPU. Preserve prior-instruction completion, pending interrupt/trace ordering, return accounting, and restart state.

Required tests before relying on this facility:

- An intercepted store has not executed; PC and memory still describe the entry boundary.
- Bypass-once executes the original opcode exactly once and makes progress.
- Candidate execution does not also execute the replaced first opcode.
- A pending IRQ and a trap at the same boundary have the declared ordering.
- Exceptions, STOP, nonzero cycle debt, and trace configuration cannot turn a “yield” into a false successful instruction.
- Capturing at a supported gate, restoring, and resuming gives the same continuation.

Do not patch a fake RTS into the ROM, intercept by mutating opcodes, or let a callback recursively re-enter the core. Existing tested PortForge facilities can satisfy these requirements without adopting Musashi.

### Z80

The inspected `chips/z80.h` exposes explicit `z80_tick` pins and an instruction-completion helper; its documentation says the reset pin is not currently emulated and directs callers to `z80_reset()`. Implement Sega reset and bus request/grant behavior in the adapter instead of assuming all board signals are handled by the core. [R5]

Keep the returned pin mask and internal execution state in snapshots. Batch ticks in C while respecting mapped memory, FM/PSG access, interrupts, reset, and the bank window. A YM2612 wrapper does not replace the Z80 sound driver.

### Nuked OPN2 and PSG

For OPN2 bind to the pinned header, not a copied README prototype: the inspected header uses a `Bit16s` output buffer for `OPN2_Clock`, while the README displays `Bit32s`. Also inspect process-global configuration: `OPN2_SetChipType` is not per-instance configuration in the inspected implementation. Choose one mode per worker and include it in the profile. [R6]

For Nuked-PSG prefer the low-level `YMPSG_Clock` and `YMPSG_Write` under our timeline. Its inspected `YMPSG_WriteBuffered` / `YMPSG_Generate` already impose buffering, delay, and clock advancement. Wrapping them in a second timestamp queue without mapping those semantics can double-delay writes or advance time unexpectedly. [R7]

Clock conversion must use each core's actual unit, not assume “one core clock” equals one console master tick. Batch internal clocks in C, stopping at relevant writes, reads, deadlines, or IRQ/status observations.

Sound-disabled/headless mode must still evolve sound-chip and Z80 state. It may discard host PCM output, not freeze the sound system. The host audio callback consumes already-produced samples and never drives the simulation. On restore, flush the host playback queue; preserve simulated mixer/resampler/filter phase so future samples match. Treat raw chip-output equality and final host playback behavior as separate checks.

If PCM generation uses floating-point arithmetic, specify its rounding/conversion and test reproducibility across fresh Windows processes. Do not weaken digital chip-state comparison to hide a host floating-point difference.

## 8. Snapshot format and continuation guarantees

Implement `.alsnap` using a standard container, such as ZIP with a JSON manifest and binary sections. Use stdlib codecs initially. Explicit little-endian fixed-width section encoding is fine even though guest word accesses are big-endian; those are separate conventions.

The current manifest contains artifact version 2, machine-state contract 1, ROM SHA-256, behavioral profile digest, source/project provenance, snapshot boundary kind, virtual tick, and checksums/lengths for sections. Python handles the container and treats machine.bin as opaque; the native codec owns field serialization and validation. An implementation-specific snapshot additionally identifies the carrier build and continuation schema it requires.

Serialize at least:

| State domain | Include |
|---|---|
| M68000 | Architectural registers plus execution-relevant hidden state: pending exceptions/IRQs, STOP/trace state, active stack modes, prefetch/configuration when used, cycle debt. |
| Z80 | Main/alternate registers, interrupt modes/latches, halted/internal execution state, pins, banking and reset/bus ownership. |
| Memory | Work RAM, Z80 RAM, VRAM, CRAM, VSRAM, and any profile-supported mutable cartridge state. ROM bytes are identified, not embedded. |
| VDP / board | Registers, command/address latch, FIFO/DMA state, counters/beam position, pending interrupts, sprite/status/cache state if not safely reconstructible, relevant partially built output. |
| Audio | Full internal FM/PSG state, pending timed operations, dividers, mixer/resampler/filter state. Not just visible chip registers. |
| Input | Latched pad button state, port direction/output state, handshake counters and timeouts. |
| Scheduler | Current time, per-component phases/debt, relevant queued internal events and deterministic tie ordering. |
| Carrier | Explicit pending continuation records, or proof that the chosen boundary has no live carrier continuation. |

Audit each selected core's actual state. The OPN2 and PSG headers illustrate why visible registers alone are insufficient: they also contain internal counters, latches, noise/envelope state and other execution history. [R6, R7]

### Portability and safe loading

Do not persist `pickle`, native pointers, callbacks, Python objects, a live generator, or a `memcpy` of an entire C struct as the user snapshot format. Raw context blobs may contain padding, addresses, or ABI-specific layout. Use a small explicit serializer at the pinned core boundary, retaining all relevant fields; pointers/callbacks must be re-established, not deserialized.

A process-local fast checkpoint may have a different representation, but it is a cache, not a portable user artifact or a canonical digest. Do not build two snapshot systems before performance makes the cache necessary.

Validate the one supported artifact version, ROM/profile identity, machine-state contract, sizes, section bounds, hashes, and continuation contract before applying state. Regenerate early captures when this contract changes; do not accumulate migration registries. Reject truncation, unsupported versions, path traversal, excessive decompression, and attempts to load code through metadata. Failed restore must not leave the active machine half-mutated. Restoring a native-backed machine may require closing/recreating its worker rather than constructing two active global cores together.

Fresh-process restore on Windows is mandatory. Capture and AI analysis use the user's Windows machine, so Windows-to-Linux transfer is outside current acceptance gates. Do not claim cross-platform portability without testing it or silently decode platform-specific blobs as portable.

### Snapshot boundaries

Initially capture at a documented top-level scheduler boundary where native calls have returned and state is coherent. A user pressing the snapshot key requests the next such boundary; save its *actual* timestamp. Do not pretend it captured an arbitrary Python expression halfway through execution.

For open regions, live locals must either be materialized into guest state at a valid resume PC or stored in a small explicit continuation record. Avoid making every local variable or every basic block into a new VM frame. Only state crossing an actual suspension boundary needs representation.

Required restore property:

```text
snapshot S + input suffix -> state/output A
fresh process + restore S + same suffix -> state/output B
A == B under the declared comparison schema
```

Test several nontrivial states, not just reset. Include active sound, pending interrupts, a VDP transfer/latch, held input, and a legacy callback once available. Diagnostic requests and taking a snapshot must not alter subsequent simulated results.

## 9. Recording workflow: user captures, AI processes

### User interface

Provide one documented launch command, for example:

```bash
python -m aladdin_sega play --rom assets/Aladdin.bin
```

Show clear controls and status in the window or overlay:

| Key | Action |
|---|---|
| F5 | Start/stop recording; starting mid-session automatically saves the initial machine state. |
| F6 | Capture a standalone snapshot at the next supported boundary. |
| F7 | Pause/resume presentation and simulation. |
| F8 | Advance to the next video frame boundary while paused. |
| F9 | Add a bookmark to an active recording; annotations do not affect simulation. |

These bindings are defaults and must not be confused with guest controller buttons. Expose game-button mappings and support normal release events. On focus loss, release held inputs through the same timestamped input path so a hidden host key state cannot stick forever.

A completed capture reports its path, duration in virtual time, profile/ROM identity, and whether it was recorded in `original` or `hybrid` mode. It must not require the user to collect a memory dump separately or find a PC.

**Record in original mode by default.** That means no recovered game replacements. A hybrid recording is allowed only with its exact implementation identity and an explicit trust label; a recording made by a candidate is not automatically original-behavior evidence.

The user supplies the ROM and human gameplay scenarios. The AI may create synthetic inputs, tiny test ROMs, deterministic fuzz, derived snapshots, and replay slices for engineering tests. Mark these as synthetic/derived; never claim the user played them. Do not force the user to record internal edge cases before writing chip, codec, or recorder tests.

When genuinely missing a gameplay witness, report the uncovered behavior and a gameplay-level request such as “record entering this room.” Do not ask the user to produce registers, traces, byte ranges, or manually identify hook addresses. Continue independent work while that coverage is absent.

### Immutable replay format

Implement `.alreplay` as a self-contained standard archive:

```text
manifest.json
initial.alsnap
events.jsonl
bookmarks.json              # optional
```

The manifest includes ROM/profile identity, capture implementation/build, format version, origin (`user` or `synthetic`), initial-state hash, and terminal virtual time. Store reset provenance when known; a mid-session recording is not evidence for cold boot.

An input event has the following meaning:

```json
{"tick": 123456, "seq": 17, "kind": "pad_state", "port": 0, "buttons": 33}
```

`buttons` is the stable guest-button bitmask defined by this format, not a host keyboard code. `tick` is when the device-facing button state actually changed. `seq` resolves ordering among equally timed external events. Values above are schema examples, not an Aladdin recording.

Record external input changes, not writes to Aladdin's RAM, player position, RNG, or measured CPU results. Controller reads still run through the emulated port/handshake logic. The recorder may log reads as diagnostics, but replay must not inject recorded read results to bypass a broken controller model.

A replay runs to its explicit terminal time even when no button changes occur. Validate event ordering, allowed kinds, port/mask ranges, and events outside the recording interval.

Pause/turbo/window focus/audio pacing are not alternate simulation clocks. Host events are queued and timestamped at their actual application boundary; do not backdate them from wall-clock timestamps. During replay, ignore live game input unless the user explicitly takes over and starts a new recording segment.

For v1, loading a snapshot, resetting, rewinding, or taking over during a recording seals the current segment and starts a new one with a new anchor. Do not splice backward time into an ordinary event stream or silently overwrite its earlier history. A branch editor is out of scope.

### Playback cursor and snapshot ownership

Keep the replay stream separate from the machine's internal event queue. A replay-aware checkpoint records the replay hash and next unconsumed event index; the machine snapshot contains current input latches and internal device events. Do not load future external events from both sources and apply them twice.

The snapshot timestamp plus cursor must unambiguously define whether an equal-timestamp input has already been applied. Test holding/releasing a key immediately around snapshot capture.

### AI-generated derivatives

Never rewrite the user's archive to attach updated expected outputs. Put derived material in a separate cache keyed by:

```text
recording content hash
reference build/core profile
comparison schema
relevant implementation/configuration identity
```

Derived products include reference checkpoint digests, frame/audio output hashes, execution coverage, region witnesses, and incident reproductions. They can be regenerated. Preserve user originals even if a newer reference changes its result.

After intake, validate the archive, reproduce it twice in original mode, test at least one fresh-process snapshot suffix, and register its actual coverage. Only then use it as the canonical scenario for recovery. A changed core/profile invalidates derived baselines; it does not justify changing original input or accepting a divergence silently.

## 10. Verification: separate claims and avoid circular evidence

Implement three execution modes:

- `original`: the original ROM and original sound driver execute; game replacements are disabled.
- `hybrid`: selected carrier/recovered bindings execute with explicit supported legacy routes.
- `verify`: orchestrates independent reference/candidate workers over identical starting conditions and input events.

Use one candidate trajectory from the common start for whole-replay verification. Do not restore candidate RAM from the reference every frame; that hides accumulating errors. Entry-seeded local witnesses are useful, but must be reported as local tests rather than whole-run equivalence.

Distinguish the following claims:

| Claim | What the evidence establishes |
|---|---|
| Determinism | This implementation reproduces its own execution under identical state/input. |
| Board/core validation | Selected behavior agrees with independent known evidence/reference tests. |
| Carrier equivalence | The candidate preserves the defined original execution observations for tested inputs. |
| Replacement qualification | A stated domain and contract support independently changing the mechanism's internals. |

Agreement between original/hybrid paths sharing a CPU/device model does not prove that shared model is correct. Use targeted independent CPU tests and existing trusted board traces/results where available. SingleStepTests supplies initial/final processor/memory instruction tests, not a proof of all Genesis hardware behavior. Its documented generator provenance must not be described as hardware measurement. [R9]

For full-console corroboration prefer a reproducible external reference run or existing validated PortForge evidence with defined input/profile conditions. Do not make foreign savestate interoperability a prerequisite or assume two emulators share a binary state layout. Report a missing independent reference honestly while continuing self-determinism and local core testing.

### Comparisons

Start strict for machine/carrier changes: relevant CPU state, RAM banks, device state, virtual time/phase, continuation, and produced output at corresponding supported boundaries. Exclude host pointers, logging, UI state, cache allocation order, and other non-simulated data by construction—not through a growing ad hoc ignore list.

Compare full small memories initially. Add dirty-page optimization only after profiling and prove it detects the same differences, including native writes and DMA. Canonical digests accelerate equality checks; on mismatch produce byte/field differences.

Final RAM equality alone does not establish identical effects. Where relevant, compare ordered MMIO/bus events, consumed input observations, audio output and subsequent device behavior. Preserve overlap/read-after-write order inside live views. Cosmetic appearance alone is insufficient.

A qualified semantic comparison can project state into a narrower contract, but must name excluded domains and why they cannot affect that claim. Do not exclude “stack”, “audio”, “timers” or “rendering” wholesale merely to turn a test green. Never inject oracle RNG/timer/continuation values into the candidate and then call it whole-machine replay equivalence. Pre2's game-tick demo deliberately used narrower domains and timing inputs; learn from the distinction, not just its green verdict. [R2]

Finite replay coverage is not universal correctness. Use statuses such as `tested`, `entry-witness-checked`, `replay-equivalent`, and `qualified-for-domain`. A 32,768-case test is not “exhaustive” unless the entire declared domain truly has that size and was enumerated.

### First-divergence diagnostics

Run coarse checks at stable video/semantic boundaries, then rerun the first divergent interval with finer instrumentation. Use bounded trace buffers and snapshots rather than logging every instruction forever.

Do not blindly binary-search endpoint equality: programs can diverge and later reconverge, so “equal at a later endpoint” does not prove the prefix was equal. Use compared prefix/checkpoint records, then locate the first mismatch within the bracket.

An incident bundle contains:

```text
reference/candidate build and ROM/profile identities
starting snapshot or recording anchor
minimal relevant input segment
first mismatching boundary/time/PC
field/byte differences and relevant recent events
region/call/continuation context
one reproducible CLI command
```

No copyrighted ROM bundled by default. Snapshots and traces can themselves contain original-game data; keep them private/local unless the user decides otherwise.

### Test the tests

Deliberately introduce and detect wrong arithmetic/sign handling, stale aliased reads, a missed memory write, a wrong return target, and a shifted MMIO event in representative tests. Assert nonzero candidate hit counts. An uncalled replacement with a green replay is not a successful experiment.

Test the packaged player path, not only helpers. Ensure the default player implementation selection is actually exercised. A verifier exception, unsupported state, missing input, timeout, or zero-hit candidate must not be reported as PASS.

## 11. Editable carrier and qualified mechanisms

### Source is more than an instruction wrapper

Recover the next concrete Aladdin region directly in Python. The current two entries do not justify an emitter. Add a narrow source-generation tool only when repeated translation work demonstrates its value; do not start a universal decompiler.

The first useful carrier must expose local computation and branches. A function containing only `execute_original_region(address)` is a routing stub, not recovered source. Likewise, moving `execute_opcode(...)` into a larger file does not count as semantic recovery or removal of machine dependence.

Machine-shaped Python is acceptable: registers, exact-width helpers, direct RAM views and explicit legacy transfers may remain. Local `if`/loops and known safe calls should be ordinary source constructs where the control flow supports them. Shared entries and unresolved exits must remain explicit; do not force a false function boundary.

Emission must be byte-provenance-aware: record ROM revision, entry, original covered bytes/ranges and code hash. Reject stale bindings. After a generated body is adopted for manual/AI editing, do not overwrite it during regeneration. Give it one source authority and keep its origin separately.

### Live semantic views

Use a small set of explicit endian/width accessors or descriptors. A named field aliases original storage; reading it twice means two live reads unless the algorithm intentionally captures a value. Dynamic bases, overlapping fields, byte/word aliases, signed values and in-place copies must retain their observed behavior.

A simple conceptual shape is:

```python
obj = ObjectView(state.ram, base)
x = obj.x
obj.x = add_u16(x, delta)
```

The actual field offsets and units must come from the current ROM/evidence. Never copy Sonic field names or example addresses into Aladdin as facts. Use neutral labels such as `field_08` when the meaning is unknown.

Do not require a full structure layout before naming a field. Do not create a registry-backed object graph just to write `obj.x`. Pure value records for calculation inputs/results are fine; they are not a second authoritative mutable game state.

### Explicit control transfers

The current implementation admits whole RAM-only plans or falls back from an unchanged entry. It has no suspended Python-to-legacy-to-Python call. Add a continuation mechanism only when a concrete region needs one; the following names describe semantics, not APIs that must be built:

| Operation | Meaning |
|---|---|
| `Transfer(target)` | Tail/control transfer with no invented return. |
| `GuestCall(target, return_pc, continuation)` | Preserve the appropriate guest call effects and arrange an explicit supported return continuation. |
| `GuestReturn()` | Read and honor the actual guest return state. |
| `Yield(continuation)` | Suspend at a documented scheduler boundary with explicit live state. |

These are semantic requirements, not a mandatory generic coroutine framework. A continuation can be a region identity, resume label and a few typed values. Store it only when execution genuinely leaves the Python chain.

Assign one owner for each stack push/pop, PC update, cycle charge, interrupt boundary and resume action. Make that ownership visible in tests. Double-pushing a return slot in both adapter and callee is a correctness bug, not an acceptable abstraction leak.

Known synchronous calls should become direct source calls when safe. They may still preserve guest return slots. Removing a slot is a separate local transformation requiring evidence that its value/write is unobservable under the declared contract.

If an original callee modifies its return address, `GuestReturn()` must take that actual destination rather than force the Python caller's anticipated resume label. Associate suspended continuations with their dynamic call/stack context, not only a matching PC; recursion, shared returns and interrupts can revisit the same address. An incompatible return must remain a supported explicit transfer or a precise unsupported-continuation error—never a guessed resume.

Do not keep an opaque Python host stack alive while recursively interpreting arbitrary guest code and then claim snapshots can restore it. Either materialize a valid machine continuation or return control to the scheduler with an explicit continuation record.

### Binding and admission

Current dispatch is two explicit entry addresses and functions. Keep their evidence in tests and recovery notes. The following are review questions, not fields for a new runtime registry or manifest:

```text
stable local region name
ROM/code hash and entry
implementation body and revision
admissible entry states / guards
control exits and timing policy
memory/register/stack dependencies
verification references and actual hit counts
merge target / adjacent region
```

A declared guard may route unsupported inputs to original execution before effects begin; count and report it. This is transparent hybrid execution, not a failed qualified native implementation pretending to be complete. Unknown opcode behavior, fake device values, and skipped work are never acceptable fallback.

Track source maturity, storage ownership, guest-stack dependence, unresolved exits, timing contract and verification scope independently. Avoid a single “M3 therefore done” flag.

### First experiment and composition

Use prior Aladdin placement or sprite-builder work as candidate discovery hints. Recheck identity and tests; addresses and results from an older report are not permission to activate a replacement blindly.

The first candidate must be exercised by the user's replay, or a clearly labeled relevant derived witness. Require local equality, mutation detection, and a full unreseeded candidate replay. Then select an adjacent **open** region with ordinary branching, a known call and a remaining machine dependency. Do not spend the entire phase replacing unrelated arithmetic leaves.

The next milestone is composition: two recovered regions call directly where safe, and at least one actual runtime transition/adapter disappears. Keep useful offline witnesses and tests even when their live hooks disappear. If no machinery can be removed and the next replacement is not easier, investigate the boundary before expanding the pattern.

## 12. Agent-facing tools and output

Provide a single CLI with consistent configuration and machine-readable results. Proposed surface:

```bash
# Initial user workflow
python -m aladdin_sega doctor
python -m aladdin_sega play --rom assets/Aladdin.bin

# Original replay and round-trip checks
python -m aladdin_sega replay recordings/first.alreplay
python -m aladdin_sega snapshot-check recordings/first.alreplay

# AI analysis after the user supplies a recording
python -m aladdin_sega baseline recordings/first.alreplay
python -m aladdin_sega verify recordings/first.alreplay --candidate placement
python -m aladdin_sega witness recordings/first.alreplay --region placement
python -m aladdin_sega emit --region object_update
python -m aladdin_sega progress --recording recordings/first.alreplay
```

Names such as `placement` and `object_update` are illustrative until assigned to real discovered regions. Commands may use a local config for ROM location; ROM and profile are always validated. `doctor` must explain missing ROM, native library, unsupported ABI/profile, or build dependency without falling through to an unrelated module error.

Implement commands when their milestone needs them, not as empty placeholders. `play`, `replay`, `snapshot-check`, and useful build diagnostics come first. Later commands must reuse the same runtime/artifact codecs rather than becoming independent alternate players.

Results distinguish PASS, FAIL, UNSUPPORTED, MISSING_INPUT and ERROR. Required missing recordings, zero-hit tests and timeouts are not PASS. Include executed coverage, comparison scope, source/build identities, and the precise reproduction command. Treat wall-time watchdogs as diagnostics, never as a simulated-time end condition.

Keep normal logs compact and bounded. Full instruction/memory tracing is an opt-in tool around an incident, not a permanent high-volume capture requirement.

## 13. Tests before the first human recording

The absence of user gameplay recordings does **not** block implementation or basic correctness tests. Use small authored programs, synthetic device operations and controlled input events. Mark their provenance.

Minimum initial test set:

| Test | Required failure it must detect |
|---|---|
| CPU pre-execution interception | First opcode accidentally executes; bypass executes twice; pending IRQ changes precedence unnoticed. |
| Guest calls/returns | Wrong stack update, return-slot overwrite ignored, nested/shared return resumed incorrectly. |
| Width/aliasing | Wrong sign extension, upper-register corruption, stale overlapping field, incorrect copy order. |
| Core export/restore | Missing hidden state, wrong pin/phase, stale native pointer after restore. |
| Whole-machine snapshot | Restore changes future RAM/device/video/audio under a fixed synthetic input suffix. |
| Recorder codec | Truncation, wrong ROM/profile, bad event order, duplicate event at checkpoint, missing terminal time. |
| Recorder round trip | Held/released inputs differ between live synthetic capture and playback. |
| Pacing independence | Headless/turbo/audio-muted changes simulated state or event application. |
| Fresh-process artifact restore | A Windows-produced snapshot/replay cannot resume equivalently in a new Windows process. |
| Default player path | Packaged/default runtime does not select the tested implementation. |
| Verifier mutations | Deliberately wrong value, write, continuation or timed operation receives a false PASS. |

Reuse focused subsets of existing CPU corpora and local tests. Do not make ingesting millions of tests a prerequisite for a first working board integration. Document unsupported or disputed flags/cases instead of broad masking to obtain a clean count. [R9]

Run cold boot as well as snapshot-start tests. A collection of mid-session snapshots cannot establish initialization correctness. The first user replay should preferably include boot/menu/early gameplay, but recorder delivery must work even when the user starts recording mid-session.

Public CI runs artifact-independent tests. Local/private jobs run the user's copyrighted ROM and recordings. Public CI missing those assets may report explicit skips; the agent's final gameplay milestone must separately report whether its required local asset tests actually ran.

## 14. Implementation sequence and acceptance gates

### A0 — inventory and a bounded native-control spike

Inspect existing sources and pin one selected ROM/profile and core set. Do not spend the phase comparing every possible emulator. Preserve a working integration unless a concrete requirement rules it out.

Test M68000 interception/resumption, selected core state round trips, and one batched audio operation. Measure a representative actual workload as soon as available. Resolve the C ABI and buffer ownership before spreading it through the project. Reuse pre-existing tests and implementations where they already cover this gate.

**Exit:** a chosen controllable substrate, reproducible build, explicit remaining board gaps, and no need for a new Python implementation of an already suitable chip.

### A1 — capture-ready Aladdin

Bring up the actual original ROM: reset, intro/menu, initial level, controls, image and sound. Implement recording and snapshots at supported boundaries, headless replay, and fresh-process restore. Keep all game replacements disabled by default for the first capture workflow.

Validate determinism and control with synthetic tests and any existing correctly attributed local materials. Do not announce user-corpus equivalence before the user provides that corpus. Inspect the real packaged/launch path on the user's target platform, not only an imported helper.

**Exit:** the user can launch, play, press record, save a snapshot and hand over the resulting files. Provide exact launch/controls and an honest test/performance report. This is a legitimate handoff awaiting the first human recording—not a failed porting milestone.

### A2 — first user artifact intake

Validate, register and reproduce the user recording in original mode. Preserve the original archive. Build derived reference data, verify an intermediate snapshot suffix, and report the scenes/time actually covered. Fix recorder/platform nondeterminism before trusting recovery comparisons.

**Exit:** a reproducible reference scenario with a pinned profile and trustworthy provenance, not merely a file that can be opened.

### B1 — one real live Python replacement

Choose an exercised mechanism with a useful boundary. Recover its live inputs/outputs and supported continuation/time behavior. Implement it once, wire it into the actual hybrid player, and use the same function for local witnesses and whole-replay verification.

**Exit:** nonzero live hits, original/candidate comparisons, a mutation caught, no reference-state injection, and no new general framework.

### B2 — a meaningful open carrier region

Expand into a neighboring region. Implement the minimum source-emission/continuation support needed for local control flow, a known call and explicit unresolved transfer. Demonstrate correct scheduling and safe snapshot continuation at its supported boundary.

**Exit:** more continuous editable source, not just another isolated math helper; strict replay still valid under its stated comparison contract.

### B3 — prove convergence by composition

Connect the neighboring source pieces and remove an unnecessary guest dispatch bounce or manual runtime adapter. Compare the real default hybrid run before/after. Keep original execution available in the oracle worker.

**Exit:** measurable deletion/localization of compatibility work, unchanged supported behavior, and a simpler next recovery step.

### C — continue broad expansion and deep replacement together

Run adjacent carrier expansion and qualification of a worthwhile mechanism in parallel. Prefer one coherent area with leverage over ten unrelated tiny wins. Keep the reference replay stable and broaden the user corpus when new gameplay is supplied.

Do not postpone all semantic work until all carrier source is emitted. Do not demand full native independence before exposing useful source. Do not turn this phase into an endless architectural rewrite.

## 15. Performance and scope guardrails

Measure original-mode playback before assuming Python-hosted Sega will be fast enough. The console being simpler than a DOS environment is not a throughput benchmark. Native chip cores reduce risk; Python call/FFI frequency and VDP processing still need measurement.

Report actual host, profile, build, emulated duration, wall time, realtime ratio, CPU/device/FFI cost and instrumentation mode. Include sound-enabled performance. A meaningful gameplay measurement follows once a user recording exists; boot-only numbers must be labeled boot-only.

Optimize in this order when the profile justifies it: eliminate per-cycle/per-access Python crossings, batch safe native work, avoid unnecessary whole-state allocation/copy, reuse buffer views, and move only a demonstrated hot isolated helper into native code. Keep recovered gameplay editable in Python. Do not respond to a slow run by disabling IRQs, sound emulation or timed work.

Realtime original-mode play is the practical target for user recording on the target desktop, not a claim already established here. Offline verification may run slower. If the original path is unusable, fix measured execution overhead before asking the user to record meaningful gameplay or assuming future decompilation will rescue performance.

Prefer narrow rerunnable witnesses for the edit/test loop plus periodic full replay gates. No full emulator rebuild should be necessary for an ordinary recovered-Python edit. Native core/configuration changes correctly require rebuilding and revalidating affected baselines.

## 16. Agent delegation and repository discipline

The supervisor may use available subagents. Start with no more than three concurrent implementation lanes unless there are truly independent tasks: native/board integration, artifact/recorder tests, and recovery/verification once ready. Assign explicit file ownership. A separate stronger reviewer can challenge timing, continuation and evidence claims without making competing edits.

Reuse installed agent mechanisms; do not build a new agent orchestration platform. Model labels such as Luna/Tera are optional runtime choices, not dependencies of this project. Do not assume unsupported persistent wakeups or claim agents will keep running after the actual execution session ends.

Keep one owner for the bus/clock/state ABI. Workers must not invent separate snapshot codecs, timing conventions, memory wrappers or binding registries. Agree only the minimum interface needed for parallel work and integrate at passing checkpoints.

Progress within the current execution session until the next meaningful milestone or a genuine dependency blocks it. When waiting for the user's first replay after A1, deliver the working capture tools and remaining evidence gap. Before A1, missing human recordings are not a blocker. Do not manufacture coverage or ask for architectural decisions that this specification already makes.

Maintain just enough documentation: a short root README, the current STATUS/decision table, and inline provenance. Do not copy this entire document into several competing status files. Keep experiments reversible; delete obsolete runtime glue and superseded one-off probes, but retain useful regression evidence.

## 17. Convergence ledger and completion criteria

For a fixed replay/profile, report:

```text
connected editable source regions and important gaps between them
actual dynamic legacy boundary crossings
M68000 / Z80 original instruction counts, kept separate
known direct source calls gained
qualified mechanisms and their supported domains
manual runtime adapters added / removed
remaining stack, storage and timing dependencies
edit-to-verdict time and full replay result
```

Count source contiguity and replacement friction, not just emitted LOC. A crossing count without source-body/coverage context can be gamed by wrapping an interpreter in one giant region. Reduced counts caused by skipped work are regressions, not convergence.

Distinguish manual runtime scaffolding, generated mechanical metadata, reusable chip wrappers and permanent tests. Large tables are not necessarily manual levers; removing tests is not reducing legacy execution. A useful library wrapper may remain permanently as the platform boundary while CPU compatibility glue shrinks.

Reassess a pattern when every next function needs a unique adapter, overlapping state authorities appear, equivalent compatibility calculations are repeatedly handwritten, the same code is migrated between several temporary representations, or prettier output requires weaker verification. Prefer fixing one shared mechanism over scaling a bad pattern.

The project is progressing when a new source region connects to existing source, remaining dependencies become explicit/local, and replacing the next mechanism becomes simpler. The final game should emerge from the same running implementation, not from discarding the carrier and beginning a second game rewrite.

### Expected first delivery

Deliver the working project and launcher, reproducible native build, original-mode game, recording/snapshot UI, headless replay/restore checks, compact test results, pinned component provenance and licenses, and a precise list of unsupported behavior. Include only features that actually work; no placeholder success messages.

**Start with A0, then A1. Build the recorder and snapshot workflow so the user can provide the first replay. The AI will then execute A2 and the continuing recovery loop.**

---

## Appendix A — researched sources and decision provenance

The observations below come from source/document inspection on 12 September 2026. They are not results of compiling these cores together, benchmarking the proposed project, or executing the user's Aladdin ROM. The architecture and acceptance gates above are design decisions informed by that inspection.

For mutable upstream branches, the implementer must pin an actual source commit. Where listed below, a blob SHA identifies the particular inspected file, not a buildable repository revision.

### R1 — Pre2: authority and memory migration

- [Pre2 object runtime at pinned commit](https://github.com/missingno7/pre2_port/blob/b5000dcbeb5fb25896fcc15ac185d99c4b7c02ec/pre2/native/object_runtime.py)
- [Historical first NativeGameState implementation](https://github.com/missingno7/pre2_port/commit/b593c3a09babc756c286d1012e986b640baddf15)

Lesson used: execution can be detached before the historical memory layout disappears. Concurrent mutable copies and full-sync write-back are a different problem from adding semantic names.

### R2 — Pre2: replay clock and equivalence scope

- [Game-tick replay implementation at pinned commit](https://github.com/missingno7/pre2_port/blob/b5000dcbeb5fb25896fcc15ac185d99c4b7c02ec/pre2/native/game_tick_demo.py)
- Inspected file blob: `7a199e093cc63f231a2e0a8cb72b4a6df4ce6d49`.

Lesson used: instruction-budget presentation clocks changed meaning after replacements. The later game-tick artifact deliberately used selected state domains and sampled timing inputs; it is not a template for claiming whole-machine equality from narrow digests.

### R3 — Current dos_re is not the historical Pre2 workbench

- [Current public dos_re README](https://github.com/missingno7/dos_re/blob/main/README.md)
- Inspected file blob: `a6bc315196fe8c96ce2ed59504a9765691527b7e`.

Lesson used: record the actual source version; keep implementation properties and evidence scope independent. Do not transplant its general IR/Atlas/planner architecture into a new single-game project by default.

### R4 — Musashi: execution and interception

- [Musashi repository and integration documentation](https://github.com/kstenerud/Musashi)
- [Execution loop, timeslice and IRQ implementation](https://github.com/kstenerud/Musashi/blob/master/m68kcpu.c)
- Inspected `m68kcpu.c` blob: `4c9981fd935a3dd25eb2b2dd9faf34e978193875`.

Source finding: the instruction hook precedes opcode execution, but loop termination is checked afterward. The stop-before-instruction requirement therefore needs a real exit facility, not only the timeslice API.

### R5 — Z80: externally controlled cycle stepping

- [Standalone chip library](https://github.com/floooh/chips)
- [Z80 header and pin-level integration documentation](https://github.com/floooh/chips/blob/master/chips/z80.h)
- Inspected header blob: `055d581d6b7042dee217908566a772a4502d8b12`.

Source finding: explicit ticking and pins support a controllable adapter. The documented reset API caveat and board-specific arbitration remain integration responsibilities.

### R6 — Nuked OPN2: state, actual ABI and mode

- [Nuked OPN2 repository](https://github.com/nukeykt/Nuked-OPN2)
- [Header](https://github.com/nukeykt/Nuked-OPN2/blob/master/ym3438.h)
- [Implementation](https://github.com/nukeykt/Nuked-OPN2/blob/master/ym3438.c)
- Inspected header blob: `f948e141eeaafb2f934a6d3830a71082ecc01a76`.

Source findings used: explicit clock/read/write entry points, extensive hidden chip state, a header/README output-buffer type discrepancy, process-global chip-mode configuration, and its own license notice.

### R7 — Nuked-PSG: Sega-specific core and buffering

- [Nuked-PSG / Yamaha YM7101](https://github.com/nukeykt/Nuked-PSG)
- [Header](https://github.com/nukeykt/Nuked-PSG/blob/master/ympsg.h)
- [Buffered-write and clock implementation](https://github.com/nukeykt/Nuked-PSG/blob/master/ympsg.c)
- Inspected header blob: `f1596214f448f01fc0b00b027da26513946e3bd3`.
- Inspected implementation blob: `5f7c4d832b953981452efaf2da5a61f2a651bf35`.

Source findings used: the low-level API is suitable for project-owned timing; higher-level buffered helpers add their own timing behavior. The source license differs from OPN2.

### R8 — Python binding and standard packaging

- [Python 3.12 ctypes documentation](https://docs.python.org/3.12/library/ctypes.html)
- [scikit-build-core getting started](https://scikit-build-core.readthedocs.io/en/stable/guide/getting_started.html)

Decision: use established FFI/build facilities, explicit types and owned callback lifetimes. Packaging choice does not justify a new build framework. Do not depend on ctypes APIs introduced after the selected Python baseline.

### R9 — Independent processor test inputs

- [SingleStepTests / 680x0](https://github.com/SingleStepTests/680x0)
- [SingleStepTests / Z80](https://github.com/SingleStepTests/z80)

Decision: use applicable, attributed initial/final-state tests in addition to same-model replay checks. Inspect corpus provenance and format; do not label generated reference data as hardware recordings or universal proof.

### R10 — Whole-console circuit emulation is a different tradeoff

- [Nuked-MD](https://github.com/nukeykt/Nuked-MD)
- [Author's original discussion, including the May 2023 performance report](https://gendev.spritesmind.net/forum/viewtopic.php?t=3356)

Decision: do not infer that every “Nuked” project has the same integration/performance role. Small reusable chip cores are the default; a complete circuit-level console is a potential reference, not the required runtime.

## Appendix B — facts the implementing agent must establish locally

Resolve these from code and tests rather than guessing:

- The exact available ROM hash, region, controller setup, and original power-on profile.
- Which PortForge Sega components and wrappers already work and can be reused without the general framework.
- The selected core configuration, interception semantics, timing granularity and full serializable state.
- The actual fresh-process Windows snapshot equivalence and original-game performance with sound.
- Which real Aladdin region the user's first replay exercises, and which existing placement/sprite-builder evidence matches its revision.
- The coverage and remaining uncertainty of independent machine validation versus same-model carrier verification.

Missing evidence is a named limitation, not permission to invent a result. Missing user gameplay recordings before capture-ready delivery are expected. Build the tools, hand over the capture workflow, and then use the user's artifacts as the basis for continuing convergence.
