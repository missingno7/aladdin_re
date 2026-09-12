# Status — 12 September 2026

The repository began with two specification documents and the local ROM. A
Python 3.12 package, CMake native binding, original player, recorder and snapshot /
replay checks now run on this Windows x64 host. **The first Agrabah level was
reached and visually inspected.** No recovered game replacements are enabled.

This is a working Windows capture slice. Full A1 acceptance remains open for
Linux execution / cross-platform restoration and broader interactive coverage.
The first human recording has now been validated, including two independently
saved live snapshots. Windows capture, replay and continuation are working for
this scenario. Cross-platform verification remains open.

## First human recording and audio correction

`recordings/20260912T210640.729016Z.alreplay` is a cold-boot, original-mode user
recording: 225.0231 seconds, 1,008 applied input changes, ending at master tick
12,082,203,375. User-described coverage is level 1, a bonus level, and arrival in
level 2. The later live snapshot's desert scene was visually inspected here.
Two fresh original replay processes produced identical complete serialized state,
final frame and all generated PCM:

```text
recording cd63a64fd08a25887e99fbc9150f3b42c6ccc6a837a6b7dbd110ba980d6e21a3
state     8f15dafc6d6a4429e1e88c52421f6a13e27b74255d9d3bdda4ffc3aa2c521b18
frame     d51bd1fb5a77cb7a6f41cef752a820c9e7e1a5484e1984c87083f2204ac047fa
PCM       878623149f19c75892fa5ef52833419e53df5096f4248ab12e27688de9200f16
```

The two original live snapshots match replay's full serialized state exactly,
including resolving input events at the same timestamp. Their original state
is then restored and continued using the unconsumed input suffix; separate
processes must reproduce the full final state, final frame and every suffix
PCM sample. The suffix audio is also compared to uninterrupted original replay.

| Live snapshot | Simulated time | Next input index | Remaining events |
|---|---:|---:|---:|
| `20260912T210626.701921Z.alsnap` | 211.2387 s | 964 | 44 |
| `20260912T210633.203951Z.alsnap` | 217.6302 s | 982 | 26 |

Original recordings/snapshots are unchanged. Derived results are in
`artifacts/intake-20260912/`: `replay-1.json`, `replay-2.json`,
`live-snapshot-check.json`, and before/after audio diagnostics.

**Audio defect found in host presentation:** the old frontend supplied one
~16.7 ms `Sound` per video frame to a channel with only one pending slot. A full
slot silently discarded newly generated PCM, while short sounds and host sleep
jitter also caused gaps. A three-second constant nonzero PCM test reproduced
12 discarded chunks out of 180 and 14,837 silent sample frames out of 163,840
output frames (~9.1%). The actual mixer was 53,267 Hz / signed-16 stereo,
SDL_mixer 2.6.2; a sample-rate mismatch was not observed in that test.

The replacement uses pygame's installed post-mix callback to consume a bounded
continuous PCM FIFO, without per-frame `Sound` objects. It primes 4,096 stereo
frames (~77 ms), reports underruns/overflow, and clears host output on pause.
Absolute frame deadlines compensate sleep overshoot. Neither the callback nor
host pacing executes the machine or changes recorded simulation timestamps.
The same three-second test delivered all samples without underruns or discarded
chunks; samples still queued at shutdown were accounted for. A 600-frame player
run resumed from the user's later snapshot with sound enabled also had zero
underruns: 533,357 submitted frames = 529,408 played + 3,949 queued at exit.
This establishes a corrected delivery path; subjective listening is not claimed.

`play.cmd --snapshot recordings/20260912T210633.203951Z.alsnap` now resumes
interactive play. Combining it with `--record-from-start` creates a new recording
anchored to that snapshot, labeled `snapshot-resume`, including the release of
any held controller buttons when live control takes over. No save is rewritten.
The installed package is updated. The expanded Python suite passes 22 tests,
including callback chunk continuity, underrun/reprime, no silent overflow,
deadline drift compensation and resumed recording provenance.

## Decisions and provenance

The main implementation specification v2 takes precedence over the subordinate
component policy where they disagree about initial native CPUs and instance
isolation. Existing suitable C++ cores were retained; no new chip interpreter,
Musashi migration, generic framework import or core comparison project was added.

The supplied paths were stale. Actual references were located under
`D:/Games/DOS/dos_recosystem/`; all were treated as read-only.

| Component | Source commit/path | Retained behavior | Test/evidence | Remaining gap |
|---|---|---|---|---|
| ROM | Local `assets/Aladdin (USA).md`; SHA-256 `a3779fc77994780e80d05bb557f800110d0398d34b951baa8c0a14910014ded3` | 2 MiB USA cartridge; reset PC `0x21A` | Exact local bytes match Aladdin reference `game.json` | Other revisions intentionally unsupported |
| Aladdin reference | `aladdin_sega_forged`, `b7413c33158e9e78e6ba602702fcd344d4c29187` | ROM identity, NTSC declarations, recovery hints | README, profile, source inventory inspected | Old HUD/placement replacements and replay claims not imported |
| M68000 / Z80 | Aladdin's `port_forge` submodule, `6c971b08c0698cd5fe56ab0ed855df4cbfc0b511` | Existing C++ interpreters, cycle charges, interrupts | Both upstream CPU executables pass; real-ROM execution | No newly run independent CPU corpus; trace/STOP boundary matrix not yet complete |
| Genesis board / VDP / IO / renderer | Same submodule `src/platform/genesis/` | Shared memory, mirrors, MMIO, DMA, three-button pad, raster/render behavior | Upstream device/render tests, boot and first-level image | Inherited named refusals; no cycle-perfect or independent full-console fidelity claim |
| Scheduler | Same submodule `src/host/genesis_engine.hpp` | Instruction-granular recognition/admission, master deadlines, actual overshoot | Scheduler continuation executable; batching and restore tests | Tighter timing than upstream was not introduced |
| FM / PSG | PortForge Nuked adapters and pinned upstream C sources; see `third_party/README.md` | Native batches, explicit phases, chip state and PCM | Audio integration executable; exact real-ROM PCM replay and suffix equality | Host playback quality not audited by ear; analog gain remains inherited convention |
| Native boundary | New `native/machine.cpp` | ABI v1, owned handle, one machine/process, pre-instruction gate, read-only RAM inspection, explicit snapshot envelope | Store-before-gate, bypass-once, IRQ-before-handler-gate, TRAP and restore tests | General recovered-function control API and trace/STOP cases remain future work |
| Snapshots / recording | New Python package plus pinned explicit native field codec | `.alsnap` / `.alreplay` ZIPs, hashes, safe member/size checks, timestamped input, explicit terminal, immutable saves | Mid-session replay, malformed artifacts, held/released equal-tick inputs, fresh worker | Windows/Linux interchange unverified; no hybrid continuation yet |
| Pre2 lessons | `legacy/pre2_port`, `b5000dcbeb5fb25896fcc15ac185d99c4b7c02ec`, `pre2/native/object_runtime.py` | Consulted authority/migration lessons only | Source inspected | No code copied |
| Historical DOS replay | `legacy/dos_re`, `0f90b3203829a15cd666b8a486021c63f4c50b1d`, `dos_re/replay_input.py` | Consulted separate input cursor/application design | Source inspected | Not confused with current public dos_re 3.0; no code copied |

`third_party/sources.json` pins 52 actual dependency files. The build rejects
changed bytes. Source dependencies remain in the existing local checkout;
the installed player needs only its packaged DLL and the user's ROM.

## Executed evidence

- Seven selected upstream CTest executables pass, with assertions enabled even
  in Release: M68000, Z80, Genesis devices, renderer, Nuked machine integration,
  snapshot codec, scheduler continuation.
- Fifteen Python tests cover the new ABI, gate/bypass, IRQ/TRAP entry, failed
  restore atomicity, stable RAM allocation, output-preserving execution chunks,
  deliberate wrong-store detection, codecs, recording and actual pygame hotkeys.
  Local-ROM tests ran; they were not skipped.
- Built and installed the package using scikit-build-core, CMake/Ninja, GCC/G++
  12.2.0 and Python 3.12.14. `doctor` loaded the packaged DLL without a development
  override. The installed `play --frames 60` completed using the Windows display
  and audio initialization paths. Synthetic hotkey tests use SDL dummy devices.
- Cold boot, 1,800 frames: 30.0387 simulated seconds in 4.0229 wall seconds
  (7.47x realtime), with both CPUs and sound chips advancing; 6,400,284 PCM bytes.
  Timing excludes final image rendering and snapshot encoding. Per-component
  CPU/VDP/FFI costs remain unmeasured.
- Synthetic Start/menu/right-input scenario, 4,200 frames: 70.0903 simulated
  seconds in 10.3231 wall seconds (about 6.79x realtime, including capture work).
  43,497,534 M68000 instructions; 24,803,606 Z80 instructions. Visually inspected
  Sega intro, title, story and first Agrabah level. This is synthetic engineering
  coverage, not a human gameplay scenario or game-completion test.
- That scenario's original replay matches the capture's full serialized state,
  final framebuffer and all generated PCM. Its intermediate checkpoint suffix
  also matches in a new Python process: six remaining input events, full state,
  final image and every suffix PCM sample. No reference state is injected.

Local derived evidence is under `artifacts/`, including `boot/result.json`,
`synthetic-gameplay.alreplay`, `synthetic-gameplay-result.json`, and `scene-4200.png`.
Synthetic full-run identities:

```text
state  f006c4b105a4881f544dd2b9ca000db6e766cfcc00dd3e2956b743506839bba2
frame  8d4ade77449115f85366fac251d47c4d8a812ffeef0999eb48dff6fc54cbdd63
PCM    74356c1cad32f5c866345470704fed11a43f7cbc0e24c055f62669311764f34d
```

Regenerate with `.venv/Scripts/python.exe scripts/capture_smoke.py`, then run the
`replay` and `snapshot-check --fresh-process` commands on its output. Capture files
are never overwritten by this script. See the root README for launch/build steps.

## State and timing contract

One native allocation owns work RAM, with Python diagnostic views reading that
storage. Restore preserves its allocation and re-establishes upstream device
wiring. Every native call returns normally before Python records input or saves.
Actual completed instruction timestamps, including budget overshoot, are retained.
The original PortForge machine and scheduler form a focused reused subsystem;
Python owns requests, artifact identity and external input delivery. There is no
second Python scheduler or a separate recovered-game state.

Persistent native state is an explicit field stream, wrapped with the scheduler's
delivered-interrupt count and sampled-level latch plus an integrity digest. It is
not a raw C struct. Debugger gate configuration is external policy; armed bypass
cannot be snapshotted. Replay cursors are separate from internal device state.
No future external events are injected from the machine snapshot.

PCM is signed 16-bit stereo clamped from the inherited mixed output. Pygame uses
the nearest integer host sample rate to `53693175/1008`; this host approximation
does not alter chip timing. A continuous host FIFO now replaces the old dropping
queue; overflow is an explicit error, and underruns are counted. The separate
native output staging buffer is drained every frame. Headless/muted execution
still evolves both sound chips and the Z80. The renderer samples current VDP state
at completed frame boundaries; this is not a newly implemented scanline renderer.

## Next work / open acceptance

1. Run Linux build and Windows-produced replay/snapshot suffix checks on Linux.
   WSL enumeration returned access denied in this execution environment; no Linux
   result is claimed.
2. Extend the boundary matrix to STOP/trace and more exception/debt combinations;
   add a focused independent reference witness where an actual discrepancy matters.
3. Confirm subjective speaker playback quality after the host audio fix and use
   `--audio-report` if a particular device still stutters.
4. Use the now-validated first user recording as recovery evidence; identify an
   exercised mechanism and its boundaries before implementing a replacement.
5. Resolve public distribution licensing before publishing a package. No top-level
   PortForge license was found; existing audio notices are recorded explicitly.

No universal recovery registry, emitter, witness framework, hybrid backend or
placeholder success command has been added. Recovered regions and live candidate
hits remain zero. These are subsequent milestones, not completed work.
