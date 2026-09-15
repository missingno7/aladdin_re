# Multi-game architecture

This repository hosts more than one Genesis recovery project on one shared
machine, history, replay and verification foundation.  This document is the
ownership boundary: what is common, what belongs to a game, and what a third
game would have to add.

## The audit (15 September 2026)

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
    profile.py             GODS: ROM identity, history roots (no recovered code yet)

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
instant inside a frame, the history root records, and the optional candidate
provider (how a candidate name becomes an armed recovered-code dispatcher).
Everything that is a fact about the console — master clock, dividers, frame
length, the controller, power-on RAM, scheduling and audio contracts — is the
`Board`, shared.

The native machine is game-agnostic.  Its snapshot identity is the ROM's
SHA-256 plus the board's id and hash; a snapshot or cache from one cartridge
cannot be restored into another.  Above it, `GenesisRun` binds a game: the
cache key includes the game id, the profile hash, the ROM hash, the native
binary and (for candidates) the recovered source.

History identity is unchanged: a node id is the root record, the ordered
input stream and the end frame.  The root record names the game
(`aladdin-usa-new`, `gods-usa-new`), so no Gods node id can equal an Aladdin
one, and a store's manifest is checked against the selected game's root before
anything is read.  A store below `history/aladdin` holds only Aladdin nodes;
the timeline reads one store.

## What a third game adds

1. `src/<game>_sega/profile.py` with its `GameProfile` (exact ROM hash, size,
   filename, roots) — and nothing else until recovery starts.
2. One line in `genesis_re/games.py`.
3. `tests/games/<game>/`, `scripts/<game>/` as they become necessary.

The machine, the histories, the frontend, the replay mechanics and the
verification foundation are not touched.

## What stays deliberately un-generalized

The common layer provides mechanisms, not knowledge.  Aladdin's PCs, object
table, RAM map, sound commands, title state and native sequences stay under
`aladdin_sega`; Gods' will stay under `gods_sega`.  Only when both games
independently reveal the same recovery mechanism is it worth lifting.
