# Architecture

This repository hosts more than one Genesis recovery project on one shared
machine, history, replay and verification foundation.  This document is the
ownership boundary: what is common, what belongs to a game, and what a third
game would have to add.  The methodology that runs on top of it is
`recovery-process.md`; the input-history model is `history-and-replay.md`;
the machine and donor policy is `machine-ownership.md`.

## The audit that produced the split (15 September 2026)

Before the split the whole tree was one package, `aladdin_sega`.  Its modules
fell into three classes:

**Platform/recovery-generic** — nothing in them is a fact about Aladdin:
`machine.py` (the typed C ABI over the one native Genesis adapter,
`native/machine.cpp`), `history.py` (immutable cold-start input histories),
`history_runtime.py` (frame stepping, observation, caches, sessions),
`verification.py` (fresh-worker strict comparison), `frontend.py` (the pygame
timeline and player), `audio.py`, `artifacts.py`, `diagnostics.py`,
`receipt.py`, `cli.py`.

**Aladdin-specific** — ROM identity, addresses, recovered routines:
`profile.py` (the ROM hash and the measured observation instant),
`boundary.py`, `recovery.py`, `recovered.py`, `game/` (the recovered game),
`native/` in the Python package (the recovered native runtime: boot, frame,
sequences, title, VDP model, sound service), most scripts and most tests.
Note the distinction between `native/machine.cpp` at the repository root (the
shared Genesis machine adapter) and `src/aladdin_sega/native/` (recovered
Aladdin execution); both keep their names.

**Mixed** — generic mechanisms whose defaults embedded Aladdin: the native
adapter wrote the literal `aladdin-usa-ntsc-v1` into every snapshot identity;
`history.py` defaulted every store to the Aladdin root; `history_runtime`
imported Aladdin's candidate dispatcher and observation instant;
`machine.py` and `receipt.py` imported Aladdin's profile hash; the CLI and the
frontend defaulted to Aladdin's ROM and `history/`; the library, environment
variable, CLI and CMake names said Aladdin.

The recovered Aladdin code depended on the shared layer only through
`Machine` and the board's frame length (`native/sound_service.py`), so the
dependency direction was already the right one: game code imports shared
code, never the reverse, except for the registry.

## The boundary

```text
src/genesis_re/            shared Genesis + recovery infrastructure
    machine.py             the one native Genesis machine (ctypes over native/machine.cpp)
    profile.py             Board (NTSC facts) and GameProfile (what varies per cartridge)
    games.py               the registry: GAMES = {"aladdin": ALADDIN, "gods": GODS}
    history.py             immutable input histories (root record supplied by the game)
    history_runtime.py     GenesisRun / Session over a game profile
    verification.py        cold, tree and fresh-worker comparison
    frontend.py            game chooser, per-game timeline, player
    audio.py, artifacts.py, diagnostics.py, receipt.py, cli.py

src/aladdin_sega/          the Aladdin recovery project
    profile.py             ALADDIN: ROM identity, history roots, candidate provider
    boundary.py, recovery.py, recovered.py, game/, native/

src/gods_sega/             the Gods recovery project
    profile.py             GODS: ROM identity, history roots, candidate provider
    game/, boundary.py, recovery.py   (the camera follow step so far; see ../gods/STATUS.md)

native/machine.cpp         the shared adapter (libgenesis_native); no game facts
scripts/                   shared tooling (dev.py, tracer, census, verifiers)
scripts/aladdin/           Aladdin witnesses, native runtime tools, cartography
scripts/gods/              Gods tooling
tests/common/              shared machine, history, replay, verification tests
tests/games/aladdin/       Aladdin recovery tests
tests/games/gods/          Gods tests
history/<game>/            original-machine input histories, one store per game
history_native/<game>/     native-runtime histories (Aladdin only so far)
```

A `GameProfile` owns exactly the facts that vary per cartridge: the stable
game id and title, the Python package holding its recovered code, the ROM
filename, size and SHA-256, the board (NTSC for both games), the observation
instant inside a frame, the history root records, the candidate provider
(how a candidate name becomes an armed recovered-code dispatcher; both games
have one) and the native entries the tracer collapses (Aladdin's sound
driver and tile upload; none for Gods yet).
Everything that is a fact about the console — master clock, dividers, frame
length, the controller, power-on RAM, scheduling and audio contracts — is the
`Board`, shared.

The native adapter holds no game facts.  The snapshot identity it embeds is
the ROM's SHA-256 plus a profile id and hash that Python declares: the
registered game's for a supported cartridge (so every Aladdin snapshot
fixture kept its identity `aladdin-usa-ntsc-v1` across the split), the
board's for any other cartridge.  A snapshot from one cartridge cannot be
restored into another.  Above it, `GenesisRun` binds a game: the cache key
includes the game id, the profile hash, the ROM hash, the native binary and
(for candidates) the recovered source.

History identity is unchanged: a node id is the root record, the ordered
input stream and the end frame.  The root record names the game
(`aladdin-usa-new`, `gods-usa-new`), so no Gods node id can equal an Aladdin
one, and a store's manifest is checked against the selected game's root before
anything is read.  A store below `history/aladdin` holds only Aladdin nodes;
the timeline reads one store.

## How game selection works

`genesis_re.games.GAMES` maps the stable id (`aladdin`, `gods`) to its
`GameProfile`.  Every developer command takes `--game ID`
(`python -m genesis_re history-verify main --game gods --candidate original`,
`scripts/dev.py` forwards it); `--history` defaults to `history/<id>` and
`--rom` to `assets/<the profile's filename>`.  `play` without `--game` opens
the chooser window first; with `--game` it opens that game's timeline
directly.  Automated play (`--frames`, `--new`, `--node`) needs an explicit
game.  Shared scripts (`recovery_census.py`, `segment_verify.py`,
`factcheck.py`, `pathfacts`) take `--game` too; game scripts under
`scripts/<game>/` are bound to their game.

The registry is the only shared module that imports a game package
(`scripts/check_architecture.py` enforces it); `Machine(rom)` looks the
cartridge up there to embed the registered game's identity in its snapshots,
and a registered cartridge run as another game is refused
(`GenesisRun(GODS, aladdin_rom)`).

## Histories, caches and evidence per game

```text
history/aladdin/      original-machine Aladdin histories (root aladdin-usa-new)
history/gods/         original-machine Gods histories   (root gods-usa-new)
history_native/aladdin/   Aladdin native-runtime histories (root aladdin-usa-native)
artifacts/            evidence; Gods artifacts are written under artifacts/gods/
```

The Aladdin stores that used to live directly under `history/` and
`history_native/` were moved into the `aladdin/` subdirectories on 15
September 2026; node ids, caches and screenshots are unchanged, and the
store manifest refuses any other game's root.  A cache is keyed by
`{game, rom, profile, native, state_version, candidate[, source]}`, so a
cache produced for one game or one build is never restored into another.

## Tests

```text
tests/common/          shared machine, history, replay, verification, tooling
tests/games/aladdin/   the Aladdin recovery corpus
tests/games/gods/      the Gods project
```

`scripts/run_tests.py common|aladdin|gods|all`; the same by path
(`pytest tests/common tests/games/gods`) or by marker (`-m "common or gods"`).
The common suite runs its real-cartridge checks on one registered game
(`GAME = GAMES["aladdin"]` at the top of those modules) and
`tests/common/test_games.py` runs the isolation checks over every game whose
ROM is present.

## What a third game adds

1. `src/<game>_sega/profile.py` with its `GameProfile` (exact ROM hash, size,
   filename, roots) — and nothing else until recovery starts; inspect the
   cartridge and record the revision, never invent it.
2. One line in `genesis_re/games.py`, and the package name in
   `scripts/check_architecture.py` and `pyproject.toml`'s wheel list.
3. `tests/games/<game>/` (start from `tests/games/gods/test_boot.py`) and
   `scripts/<game>/` as they become necessary; a `docs/<game>/STATUS.md`.

When recovery starts, the game gains a candidate provider
(`GameProfile.candidate`: a name to an object with `arm(machine)`,
`on_gate(machine, deadline)` and `stats`), its own boundary/recovery
modules and, for the tracer, `tracer_native_entries`.

The machine, the histories, the frontend, the replay mechanics and the
verification foundation are not touched.

## What stays deliberately un-generalized

The common layer provides mechanisms, not knowledge.  Aladdin's PCs, object
table, RAM map, sound commands, title state and native sequences stay under
`aladdin_sega`; Gods' camera addresses stay under `gods_sega`.  Only when both
games independently reveal the same recovery mechanism is it worth lifting.
The first such case happened on 16 September 2026: when Gods reached a
region with a platform operation inside it and reproduced the seam shape
Aladdin's sound requests had proven, the admission contract (`AtomicPlan`,
`UnsupportedCandidate`), the `Seam` and its runner (`run_seam`: pause
recovered execution, let the machine run the operation, resume) moved into
`src/genesis_re/seam.py`; both games' boundaries import them, both
dispatchers call the runner and keep their own counters.  What did not
move: the seam *plans* (where each game's regions resume, their frames,
their suffixes), the 68000 flag helpers and alias guards (small, copied),
the gate dispatcher (`Candidate.arm/on_gate/stats` — the same contract in
both games, left duplicated until a third game repeats it).
`recovery-process.md` §8 describes the contract the replay runner expects.
