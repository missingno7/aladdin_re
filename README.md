# Aladdin RE

Aladdin RE is a Windows development environment for the USA Genesis release of
*Aladdin*.  It runs one verified ROM revision through a focused native Genesis
binding and keeps player input as an immutable cold-start history.  Python game
recovery remains selective and under active investigation.  This repository is
not a distributable ROM package or a hardware-accuracy claim.

See [the current status](docs/STATUS.md), [input-history model](docs/history.md),
and [third-party license and source notes](third_party/README.md).

## Play

Put the verified cartridge at `assets/Aladdin (USA).md`; the filename extension
does not change that it is a binary ROM.  The launcher validates its exact hash
before execution.

```powershell
.\play.cmd
.\play.cmd --new
.\play.cmd --node main
.\play.ps1 -Mute
```

The initial panel visualizes immutable input checkpoints.  Click **New** for a
cold root, **Main** for the current branch, or any checkpoint point to branch
from it.  F5 and F6 create manual checkpoints; a clean exit creates one too.
F7 pauses and F8 advances one frame while paused.  `--mute` silences only host
playback: Genesis audio still runs and is still part of verification.

The recovered game itself (no original CPU; the ROM's Z80 sound driver runs as
a platform service on a dedicated machine):

```powershell
.\play_native.cmd
.\play_native.cmd --resume NODE
.\play_native.cmd --mute
.\play_native.cmd --help
```

Arrows, Z = A, X = B, C = C, Return = Start, Escape exits, F5 journals a
checkpoint.  Inputs are journaled as an immutable history in `history_native/`;
a NativeGap ends the session with its record in `history_native/gaps/`, and
`--resume NODE` replays that history and hands the controller back.

Input histories live under `history/` by default and are ignored by Git.  They
contain canonical frame input segments, optional screenshots, and disposable
Genesis caches.  See [docs/history.md](docs/history.md) for identity, branching,
cache, and command details.

## Develop from the checkout

`play.cmd`, `play.ps1`, and `scripts/dev.py` run this checkout directly.  They
prepend its absolute `src` directory to `PYTHONPATH` and set
`ALADDIN_NATIVE_LIBRARY` to `build/libaladdin_native.dll`.  They do not install,
reinstall, build, or download anything.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py doctor
.\.venv\Scripts\python.exe scripts\dev.py history-validate --history history
.\.venv\Scripts\python.exe scripts\dev.py history-run main --history history --candidate lifecycle
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --history history --candidate lifecycle --tree --output artifacts\history-verify
```

`history-run` reconstructs a path cold by default; `--cache` explicitly permits
a compatible disposable player cache.  `history-verify` uses fresh workers and
compares strict per-frame state, video, PCM, and terminal observations.  A tree
verification creates only temporary prefix states for that invocation.  A PASS
only covers the selected history and candidate execution.

Use `history-export` to write a portable normalized input path, and
`history-capture` for a constructed API smoke path.  Neither turns a constructed
path into user-gameplay evidence.

## Build on Windows

Requirements are Python 3.12 x64, CMake/Ninja, a C++17 compiler, and the pinned
PortForge checkout described in [third_party/README.md](third_party/README.md).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install cmake==4.4.3 ninja==1.13.2 scikit-build-core==1.0.3 pygame==2.6.1 pytest==9.1.1 pytest-xdist==3.6.1 capstone==5.0.7
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

Install the package only when you deliberately need a packaged player after a
native or packaged-Python change.  The source launchers above deliberately do
not do this:

```powershell
$env:CMAKE_GENERATOR = 'Ninja'
$env:CMAKE_ARGS = "-DPORTFORGE_ROOT=D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge -DCMAKE_C_COMPILER=C:/msys64/mingw64/bin/gcc.exe -DCMAKE_CXX_COMPILER=C:/msys64/mingw64/bin/g++.exe -DCMAKE_MAKE_PROGRAM=$PWD/.venv/Scripts/ninja.exe -DBUILD_TESTING=OFF".Replace('\', '/')
.\.venv\Scripts\python.exe -m pip install . --no-build-isolation --no-deps
```

The build validates locked donor-source bytes before native compilation.  It
refuses changed locked files instead of producing a DLL with stale provenance.
Windows x64 is the supported platform.

## Tests and limits

```powershell
$env:ALADDIN_NATIVE_LIBRARY = "$PWD/build/libaladdin_native.dll"
.\.venv\Scripts\python.exe -m pytest -q -n 8
.\.venv\Scripts\python.exe scripts\check_architecture.py
```

The history smoke suite validates canonical input identity, branching, cache
rejection, presentation separation, and cold/cache reconstruction.  It does
not yet provide a new user history or full-game recovery qualification.

Historical replay and snapshot documents remain under [docs/archive](docs/archive/)
as frozen evidence.  Current commands intentionally do not promise to load
their obsolete artifact formats.
