# Genesis RE

A Windows development environment for recovering Genesis games from their
exact ROM revisions: one shared native Genesis machine, immutable cold-start
input histories, a history timeline and player, strict replay verification,
and one recovery project per game.  Two games are registered:

| game | package | supported revision | state |
|---|---|---|---|
| Aladdin (USA) | `src/aladdin_sega` | `aladdin-usa-ntsc-v1` | a large recovered frontier, a native runtime from power-on; see [docs/STATUS.md](docs/STATUS.md) |
| Gods (USA) | `src/gods_sega` | `gods-usa-ntsc-v1` | runs as the original through the shared machine; no recovered code yet; see [docs/gods/STATUS.md](docs/gods/STATUS.md) |

The shared infrastructure is `src/genesis_re`.  The ownership boundary, how
game selection works and what a third game would add are in
[docs/multi-game-architecture.md](docs/multi-game-architecture.md); the
input-history model is in [docs/history.md](docs/history.md); third-party
license and source notes are in [third_party/README.md](third_party/README.md).
This repository is not a distributable ROM package or a hardware-accuracy
claim.  (The checkout directory is still called `aladdin_re`; the name predates
the second game.)

## Play

Put the verified cartridges under `assets/` (`Aladdin (USA).md`,
`Gods (USA).md`; the `.md` extension does not change that they are binary
ROMs).  Each game's exact SHA-256 is validated before execution; any other
revision is refused.

```powershell
.\play.cmd                      # choose the game, then its history timeline
.\play.cmd --game gods          # straight to the Gods timeline
.\play.cmd --game gods --new    # a cold Gods root
.\play.cmd --game aladdin --node main
.\play.ps1 -Mute
```

Without `--game` the window first asks which game to play; the timeline shown
afterwards is that game's own.  Click **New** for a cold root, **Main** for the
current branch, or any checkpoint to branch from it.  F5 and F6 create manual
checkpoints; a clean exit creates one too.  F7 pauses and F8 advances one frame
while paused.  `--mute` silences only host playback: Genesis audio still runs
and is still part of verification.

Input histories live under `history/<game>/` (`history/aladdin`,
`history/gods`) and are ignored by Git.  A store's manifest names its game's
root record, so an Aladdin store cannot be opened as a Gods one and no node
id of one game can equal a node id of the other.  Each store contains
canonical frame input segments, optional screenshots, and disposable Genesis
caches keyed by game, ROM, profile, native binary and state contract.  See
[docs/history.md](docs/history.md).

The recovered Aladdin game itself (no original CPU; the ROM's Z80 sound driver
runs as a platform service on a dedicated machine) is Aladdin's native runtime:

```powershell
.\play_native.cmd
.\play_native.cmd --resume NODE
.\play_native.cmd --help
```

Its histories are journaled under `history_native/aladdin/`.

## Develop from the checkout

`play.cmd`, `play.ps1`, and `scripts/dev.py` run this checkout directly.  They
prepend its absolute `src` directory to `PYTHONPATH` and set
`GENESIS_NATIVE_LIBRARY` to `build/libgenesis_native.dll`.  They do not
install, reinstall, build, or download anything.  Every developer command names
its game with `--game`; `--history` defaults to `history/<game>` and `--rom` to
the game's file under `assets/`.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py doctor --game gods
.\.venv\Scripts\python.exe scripts\dev.py history-validate --game gods
.\.venv\Scripts\python.exe scripts\dev.py history-run main --game aladdin --candidate lifecycle
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --game gods --candidate original --output artifacts\gods-verify
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --game aladdin --candidate lifecycle --tree --output artifacts\history-verify
```

`history-run` reconstructs a path cold by default; `--cache` explicitly permits
a compatible disposable player cache.  `history-verify` uses fresh workers and
compares strict per-frame state, video, PCM, and terminal observations;
`--candidate original` compares two fresh original runs (the fresh-process
determinism check), a recovery candidate name compares the game's recovered
code against the original.  A tree verification creates only temporary prefix
states for that invocation.  A PASS only covers the selected history and
candidate execution.

Use `history-export` to write a portable normalized input path, and
`history-capture` for a constructed API smoke path.  Neither turns a constructed
path into user-gameplay evidence.

Shared tooling is in `scripts/` (`dev.py`, the tracer `pathfacts.py` and
`factcheck.py`, `recovery_census.py`, `segment_verify.py`, `verify_status.py`,
`frontier_ledger.py`); it takes `--game`.  Game-specific tooling is under
`scripts/aladdin/` (witnesses, the native runtime and its verifiers,
cartography) and `scripts/gods/`.

## Tests

Tests are structured by scope, not skipped at runtime:

```text
tests/common/          shared machine, history, replay, verification, tooling
tests/games/aladdin/   the Aladdin recovery corpus
tests/games/gods/      the Gods project
```

```powershell
.\.venv\Scripts\python.exe scripts\run_tests.py common     # shared only (about 15 s)
.\.venv\Scripts\python.exe scripts\run_tests.py gods       # shared + Gods (about 20 s)
.\.venv\Scripts\python.exe scripts\run_tests.py aladdin    # shared + Aladdin (about 90 s)
.\.venv\Scripts\python.exe scripts\run_tests.py all        # everything (about 100 s)
.\.venv\Scripts\python.exe scripts\check_architecture.py
```

`tests/conftest.py` sets the checkout's import paths and the built native
library for the test process and for the fresh workers it spawns, so no
environment variables are needed; plain `pytest tests/common tests/games/gods`
works too, as do the `common`, `aladdin` and `gods` markers.  A grinding
iteration on one game runs that game's scope; run `all` at larger checkpoints.

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
Windows x64 is the supported platform.  The native adapter
(`native/machine.cpp`) holds no game facts: the snapshot identity it embeds is
the cartridge's hash plus the profile id and hash Python declares.

## Limits

The history smoke suite validates canonical input identity, branching, cache
rejection, presentation separation, and cold/cache reconstruction.  It does
not by itself provide a new user history or full-game recovery qualification.
Historical Aladdin replay and snapshot documents remain under
[docs/archive](docs/archive/) as frozen evidence; the Aladdin status log is
[docs/STATUS.md](docs/STATUS.md).  Current commands intentionally do not
promise to load obsolete artifact formats.
