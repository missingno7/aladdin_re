# Genesis RE

A Windows development environment for recovering Genesis games from their
exact ROM revisions into readable, proven source.  One shared native Genesis
machine, immutable cold-start input histories, a timeline and player, strict
replay verification, and one recovery project per game.

| game | package | supported revision | state |
|---|---|---|---|
| Aladdin (USA) | `src/aladdin_sega` | `aladdin-usa-ntsc-v1` | a large recovered frontier under gates, and a native runtime that runs the whole recorded route from power-on — [docs/aladdin/STATUS.md](docs/aladdin/STATUS.md) |
| Gods (USA) | `src/gods_sega` | `gods-usa-ntsc-v1` | eight player recordings verified cold; the first recovered region (the camera follow step) passes the whole tree — [docs/gods/STATUS.md](docs/gods/STATUS.md) |

The shared infrastructure is `src/genesis_re` (machine, histories, replay,
frontend, verification, registry).  Documentation starts at
[docs/README.md](docs/README.md): the architecture and ownership boundary,
the history model, the recovery process, how Aladdin converged, how to grind
Gods.  Third-party license and source notes are in
[third_party/README.md](third_party/README.md).  This repository is not a
distributable ROM package or a hardware-accuracy claim.  (The checkout
directory is still called `aladdin_re`; the name predates the second game.)

## Play

Put the verified cartridges under `assets/` (`Aladdin (USA).md`,
`Gods (USA).md`; the `.md` extension does not change that they are binary
ROMs).  Each game's exact SHA-256 is validated before execution.

```powershell
.\play.cmd                      # choose the game, then its history timeline
.\play.cmd --game gods          # straight to the Gods timeline
.\play.cmd --game gods --new    # a cold Gods root
.\play.cmd --game aladdin --node main
.\play.ps1 -Mute
```

Click **New** for a cold root, **Main** for the current branch, or any
checkpoint to branch from it.  F5/F6 create checkpoints, a clean exit creates
one, F7 pauses, F8 steps.  `--mute` silences host playback only.  Histories
live under `history/<game>/`, each store bound to its game; a session that
dies on a machine fault keeps its inputs as a replayable node.  The Aladdin
native runtime (the recovered game without the original CPU) is
`.\play_native.cmd`, with histories under `history_native/aladdin/`.

## Develop from the checkout

`play.cmd`, `play.ps1` and `scripts/dev.py` run this checkout directly against
`build/libgenesis_native.dll` (`GENESIS_NATIVE_LIBRARY`); they never install
or build.  Every developer command names its game with `--game`; `--history`
defaults to `history/<game>` and `--rom` to the game's file under `assets/`.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py doctor --game gods
.\.venv\Scripts\python.exe scripts\dev.py history-validate --game gods
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --game gods --candidate original --tree --output artifacts\gods\verify
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --game aladdin --candidate lifecycle --output artifacts\verify
```

`history-verify` starts two fresh workers and compares every canonical frame
(state, video, PCM, counters); `--candidate original` is the determinism check,
a candidate name compares recovered code against the original.  Shared
tooling in `scripts/` (`dev.py`, `run_tests.py`, `hot_calls.py`,
`recovery_census.py`, `factcheck.py`, `segment_verify.py`, `verify_status.py`,
`frontier_ledger.py`) takes `--game`; game tooling is under `scripts/aladdin/`
and `scripts/gods/`.  What each does and when: [docs/common/recovery-process.md](docs/common/recovery-process.md).

## Tests

```text
tests/common/          shared machine, history, replay, verification, tooling
tests/games/aladdin/   the Aladdin recovery corpus
tests/games/gods/      the Gods project
```

```powershell
.\.venv\Scripts\python.exe scripts\run_tests.py common     # shared only (about 15 s)
.\.venv\Scripts\python.exe scripts\run_tests.py gods       # shared + Gods (about 25 s)
.\.venv\Scripts\python.exe scripts\run_tests.py aladdin    # shared + Aladdin (about 90 s)
.\.venv\Scripts\python.exe scripts\run_tests.py all        # everything (about 100 s)
.\.venv\Scripts\python.exe scripts\check_architecture.py
```

`tests/conftest.py` sets the import paths and the native library for the
test process and the workers it spawns; no environment variables are needed.
A grinding iteration on one game runs that game's scope; `all` at larger
checkpoints.

## Build on Windows

Requirements: Python 3.12 x64, CMake/Ninja, a C++17 compiler, and the pinned
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

Install the package (`pip install . --no-build-isolation --no-deps` with
`CMAKE_ARGS` set as above) only when you deliberately need a packaged
player; the source launchers never do.  The build validates locked
donor-source bytes before compiling and refuses changed locked files.
Windows x64 is the supported platform.  The native adapter
(`native/machine.cpp`) holds no game facts.
