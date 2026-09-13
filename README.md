# Aladdin RE

A Windows development environment for the USA Genesis release of Aladdin. It
runs the original ROM through a focused native Genesis binding, records input,
saves snapshots, replays in fresh processes, and provides an opt-in path for
recovering selected gameplay regions into Python. It is not a distributable ROM
package or a hardware-accuracy claim. See [docs/STATUS.md](docs/STATUS.md) for
the current evidence and limits.

## Play, record, and resume

`play.cmd` is the normal original-mode launcher. It works from Explorer or a
command prompt and does not depend on PowerShell execution policy.

```powershell
.\play.cmd
.\play.cmd --record-from-start
.\play.cmd --snapshot "recordings\current\20260912T210633.203951Z.alsnap"
```

The ROM defaults to `assets/Aladdin (USA).md`; despite the extension, it is a
binary cartridge. Its exact SHA-256 is checked before execution. ROMs,
recordings, and derived artifacts are ignored by Git.

F5 starts or stops a recording, F6 saves a snapshot, F7 pauses, F8 advances one
frame while paused, and F9 adds a bookmark. A resumed recording is anchored to
the selected snapshot; it does not alter that save. `--mute` mutes host output
without stopping the chips or Z80. `--audio-report artifacts/audio.json` writes
host FIFO diagnostics on exit.

Snapshots capture machine/device state at completed native-operation boundaries.
Host PCM queues are presentation state and are deliberately cut at a snapshot:
restoring does not repeat sound already delivered to the host queue.
Snapshots saved during the recovered sound continuation also retain its small
explicit return record. `--snapshot` resumes that carrier automatically.

## Development from the source tree

Use the source runner after editing Python. It starts a fresh child process,
prepends this checkout's absolute `src` path to `PYTHONPATH`, and points it at
the already-built native DLL. It does **not** build, download, install, or
reinstall anything.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py doctor
.\.venv\Scripts\python.exe scripts\dev.py replay recordings\your.alreplay
.\.venv\Scripts\python.exe scripts\dev.py --native D:\work\libaladdin_native.dll doctor
```

`doctor` reports the loaded Python module path, native source identity, native
binary hash, and execution/build receipts. Use it before interpreting a replay
result so a stale installed package is not mistaken for source-tree code.

Original play remains the default. Recovery candidates are explicit replay
choices; a snapshot with a pending carrier return also enables its continuation
when resumed through `play.cmd`.

## Build on Windows

Requirements are Python 3.12 x64, CMake/Ninja, a C++17 compiler, and the pinned
PortForge checkout described in [third_party/README.md](third_party/README.md).

```powershell
# On a fresh checkout, using Python 3.12:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install cmake==4.4.3 ninja==1.13.2 scikit-build-core==1.0.3 pygame==2.6.1 pytest==9.1.1
.\.venv\Scripts\cmake.exe -S . -B build -G Ninja `
  -DPORTFORGE_ROOT=D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge `
  -DCMAKE_C_COMPILER=C:/msys64/mingw64/bin/gcc.exe `
  -DCMAKE_CXX_COMPILER=C:/msys64/mingw64/bin/g++.exe `
  -DCMAKE_MAKE_PROGRAM="$PWD/.venv/Scripts/ninja.exe" `
  -DCMAKE_BUILD_TYPE=Release `
  -DBUILD_TESTING=ON
.\.venv\Scripts\cmake.exe --build build -j 4
.\.venv\Scripts\ctest.exe --test-dir build --output-on-failure
```

Install the player package separately when native or packaged Python changes:

```powershell
$env:CMAKE_GENERATOR = 'Ninja'
$env:CMAKE_ARGS = "-DPORTFORGE_ROOT=D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge -DCMAKE_C_COMPILER=C:/msys64/mingw64/bin/gcc.exe -DCMAKE_CXX_COMPILER=C:/msys64/mingw64/bin/g++.exe -DCMAKE_MAKE_PROGRAM=$PWD/.venv/Scripts/ninja.exe -DBUILD_TESTING=OFF"
.\.venv\Scripts\python.exe -m pip install . --no-build-isolation --no-deps
```

Every incremental build regenerates its source identity and verifies the locked
dependency bytes before native compilation. A changed locked file causes the
build to refuse rather than emitting a DLL with stale provenance. Gameplay never
starts a compiler or downloads a dependency.

The native PCM queue has two explicit policies. Capture/verification is lossless
within its bounded queue: exceeding capacity invalidates execution and requires
smaller batches. Presentation code can select explicit discard; chips and the
Z80 still advance, but discarded samples cannot support a PCM verdict.

## Replay and verification

A single `replay` run means only that one worker executed. It emits
`status: COMPLETED` and `compared: false`; its hashes are observations, not an
equivalence verdict.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py replay recordings\your.alreplay
.\.venv\Scripts\python.exe scripts\dev.py snapshot-check recordings\your.alreplay --timeout-seconds 120
.\.venv\Scripts\python.exe scripts\dev.py compare recordings\your.alreplay `
  --candidate leaf --timeout-seconds 120 --output artifacts\comparison
```

`compare` runs original and candidate workers in separate fresh processes. It
writes their ordered 60-frame state/frame/PCM observations and a compact report
with the last matching checkpoint and first failing interval. `composed` retains
the prior recovery cluster; `carrier` extends it through the original sound
callees and back into Python. Mutation modes are reserved for tests.
A candidate with zero executed hits is `NOT_EXERCISED`, not a pass.

For a fast, local edit-to-verdict check, first create a real recording witness:

```powershell
$env:PYTHONPATH = "$PWD/src"
$env:ALADDIN_NATIVE_LIBRARY = "$PWD/build/libaladdin_native.dll"
.\.venv\Scripts\python.exe scripts\recovery_witness.py --candidate leaf --output artifacts\leaf-witness
.\.venv\Scripts\python.exe scripts\edit_loop_check.py artifacts\leaf-witness\witness.alreplay
```

The second command edits a disposable Python source copy, verifies that the
production comparison rejects it, and checks that the native DLL stayed intact.

For the connected carrier, `scripts/carrier_witness.py` captures a real entry,
saves inside the original sound callee, qualifies fresh-process resumption and
runs result/return/timing negative controls. Then use `scripts/dev.py compare`
on its `witness.alreplay` with `--candidate carrier` for ordinary Python edits.
The [carrier experiment report](docs/carrier-convergence.md) gives the region
map, exact continuation contract, measured overhead and scope limits. Its
verdict is **NOT CONVERGING**: the continuation works, but this expansion adds
more recovery machinery than it removes.

The comparison contract is `full-machine-frame-pcm-60frames-v1`: complete
machine snapshots, frame hashes, PCM chunks, and terminal state/frame/full-PCM
hashes are compared on the available scenario. This is integrated same-model
evidence. It does not establish independent console or hardware accuracy.

Ordinary archives use version 2 and machine-state contract 1. A snapshot with
a pending carrier return uses version 3 for its additional recovery metadata;
replays remain version 2. ROM and behavioral profile must match; source/build
hashes remain provenance. Unsupported earlier
formats fail clearly instead of entering a compatibility migration chain.
The supplied user replay and two saves were regenerated from their input stream
under `recordings/current/`, with parent hashes in `provenance.json`. The original
files remain untouched. New recordings already use the current format.

## Architecture and recovery

Python owns game source, recovery dispatch, replay, verification and presentation.
The small machine API isolates retained Genesis CPU/VDP/scheduler components.
Nuked OPN2 and PSG compile directly from the pinned sources in `third_party/`.
The [necessity review](docs/architecture-review.md) assesses current scope, control
capabilities, iteration cost and deletion opportunities. The
[component ledger](docs/component-migration.md) records the actual compiler
closure, remaining donor edges, migration classes and removal triggers.

Edit `src/aladdin_sega/recovered.py` for the buffer clear at `0x1AE372`, object-pair
clear at `0x1ABE6E`, detach region at `0x1AD0FC`, object initializer at `0x1AE30A`,
cleanup/template path at `0x1AE954`, and shared replacement tail at `0x1AF4C6`
(with its incrementing entry at `0x1AF4C2`). These paths compose pair clearing
and initialization directly. Gate policy and mutants live separately
in `recovery.py`. See [recovery-first.md](docs/recovery-first.md) for domains,
timing, continuation and reproducible short witnesses.

## Inspect a failing short witness

Add `--diagnostics` to a comparison when hashes alone are insufficient:

```powershell
.\.venv\Scripts\python.exe scripts\dev.py compare artifacts\leaf-witness\witness.alreplay `
  --candidate leaf --diagnostics --output artifacts\leaf-diff
```

The report includes PC/SR and register differences, the first 32 changed work-RAM
bytes (plus the total count), and whether the workers stopped at the same tick.
Each comparison creates a fresh diagnostic directory with the exact input replay,
per-worker inspection metadata/RAM, and a `.alsnap` when that state can be saved.
The reported reproduction commands use the copied input. The ROM stays external.

These are **terminal or failure-state** differences, not a claim about the first
bad instruction. A failed native execution may allow register/RAM inspection but
refuse a restorable snapshot; the original failure and capture error are retained.
No native snapshot fields are decoded in Python. Default comparisons retain their
existing checkpoint/hash behavior and do not write these extra captures.

`candidate_stats.fallback_reasons` distinguishes scheduler admission refusal,
unsupported data domains. Replay is always headless,
snapshot checks always use fresh processes, and play always runs the original
mode; the old no-op `--headless`, `--fresh-process` and `--mode` flags are removed.

## Source bundle for an authorized fresh Windows worker

An authorized local worker can create the exact focused dependency bundle from
the inspected checkout:

```powershell
.\.venv\Scripts\python.exe scripts\export_sources.py `
  --source D:\Games\DOS\dos_recosystem\aladdin_sega_forged\port_forge `
  --output D:\work\aladdin-portforge-sources
```

The script validates the 27 runtime donor files before writing a new output
directory. Add `--tests` for the 19 additional test-only files; configure with
`BUILD_TESTING=OFF` when using a runtime-only bundle. The directly vendored sound
cores already travel with this repository. It copies only those original relative paths, plus the lock,
provenance metadata, and selected notices. It refuses existing output paths and
does not copy a ROM or the whole PortForge framework. This is an authorized
local engineering handoff, not a public publication path; see the license and
distribution limits in [third_party/README.md](third_party/README.md).

## Tests

```powershell
$env:ALADDIN_NATIVE_LIBRARY = "$PWD/build/libaladdin_native.dll"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_architecture.py
```

Windows x64 is the supported platform for this project. Linux builds and
cross-platform artifact interchange are outside the current acceptance scope.
