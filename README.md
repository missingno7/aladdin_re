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
.\play.cmd --snapshot "recordings\20260912T210633.203951Z.alsnap" --compatibility review-baseline-v1
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

## Development from the source tree

Use the source runner after editing Python. It starts a fresh child process,
prepends this checkout's absolute `src` path to `PYTHONPATH`, and points it at
the already-built native DLL. It does **not** build, download, install, or
reinstall anything.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py doctor
.\.venv\Scripts\python.exe scripts\dev.py replay recordings\your.alreplay --headless
.\.venv\Scripts\python.exe scripts\dev.py --native D:\work\libaladdin_native.dll doctor
```

`doctor` reports the loaded Python module path, native source identity, native
binary hash, and execution/build receipts. Use it before interpreting a replay
result so a stale installed package is not mistaken for source-tree code.

Original play remains the default. Recovery candidates are explicit replay
choices; they are not enabled by `play.cmd`.

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
.\.venv\Scripts\python.exe scripts\dev.py replay recordings\your.alreplay --headless
.\.venv\Scripts\python.exe scripts\dev.py snapshot-check recordings\your.alreplay --timeout-seconds 120
.\.venv\Scripts\python.exe scripts\dev.py compare recordings\your.alreplay `
  --candidate leaf --timeout-seconds 120 --output artifacts\comparison
```

`compare` runs original and candidate workers in separate fresh processes. It
writes their ordered 60-frame state/frame/PCM observations and a compact report
with the last matching checkpoint and first failing interval. `leaf` and
`composed` are the recovery candidates; mutation modes are reserved for tests.
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

The comparison contract is `full-machine-frame-pcm-60frames-v1`: complete
machine snapshots, frame hashes, PCM chunks, and terminal state/frame/full-PCM
hashes are compared on the available scenario. This is integrated same-model
evidence. It does not establish independent console or hardware accuracy.

The default loader requires exact capture identity. The supplied older user
recording and snapshots were made by baseline `b3c78ac`; use the named,
directional qualification only where it is supported:

```powershell
.\.venv\Scripts\python.exe scripts\dev.py replay recordings\your.alreplay `
  --compatibility review-baseline-v1 --headless
.\.venv\Scripts\python.exe scripts\dev.py snapshot-check recordings\your.alreplay `
  --compatibility review-baseline-v1 --timeout-seconds 120
.\.venv\Scripts\python.exe scripts\qualify_baseline.py `
  --recording recordings\your.alreplay --rom "assets\Aladdin (USA).md" `
  --output artifacts\baseline-qualification --timeout-seconds 120
```

`artifacts/baseline-b3c78ac` preserves the qualified baseline package, DLL, and
hash receipt. `qualify_baseline.py` verifies that receipt, keeps the baseline
worker isolated from current source code, and writes a derived comparison. It
never rewrites a user capture. An unsupported source or machine-model transition
is rejected rather than silently accepted.

## Source bundle for an authorized fresh Windows worker

An authorized local worker can create the exact focused dependency bundle from
the inspected checkout:

```powershell
.\.venv\Scripts\python.exe scripts\export_sources.py `
  --source D:\Games\DOS\dos_recosystem\aladdin_sega_forged\port_forge `
  --output D:\work\aladdin-portforge-sources
```

The script validates all 52 locked source hashes before writing a new output
directory. It copies only those original relative paths, plus the lock,
provenance metadata, and selected notices. It refuses existing output paths and
does not copy a ROM or the whole PortForge framework. This is an authorized
local engineering handoff, not a public publication path; see the license and
distribution limits in [third_party/README.md](third_party/README.md).

## Tests

```powershell
$env:ALADDIN_NATIVE_LIBRARY = "$PWD/build/libaladdin_native.dll"
.\.venv\Scripts\python.exe -m pytest -q
```

Windows x64 is the supported platform for this project. Linux builds and
cross-platform artifact interchange are outside the current acceptance scope.
