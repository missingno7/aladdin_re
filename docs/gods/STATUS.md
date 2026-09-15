# Gods (USA): status

Started 15 September 2026 as the second game of the repository, the
generalization test of the Aladdin recovery process.  Nothing of Gods is
recovered yet; this file says exactly what the project has.

## Supported revision

Inspected from the cartridge at `assets/Gods (USA).md`: 1,048,576 bytes,
SHA-256 `f7e577a66ed4d9901cb44ed0620e61439527cfbd854bc4626173b17e30fa6be0`,
header "SEGA GENESIS", "(C)SEGA 1992.JUN", name "GODS", serial
"GM T87016  -00", region "U", ROM 000000-0FFFFF, work RAM FF0000-FFFFFF,
header checksum E80A (equal to the computed sum), entry 000200.  Profile id
`gods-usa-ntsc-v1` (`src/gods_sega/profile.py`); any other file is refused.

## Phase 1: the original game path (done, headless evidence)

Through the shared machine (`native/machine.cpp`, the NTSC board), with no
Gods-specific change to the machine:

- cold power-on runs; the VBlank counter advances one per frame from about
  frame 6; the Z80 executes and PCM is emitted from the first frame;
- video: the Mindscape logo by frame 240, the intro by 900, "GET READY"
  after Start, level 1 on screen by frame 1500 (a cold run with Start held
  at frames 900-904);
- controller input is read: Start changes the trajectory (state and video);
- two cold runs from reset agree frame by frame in state, video and PCM for
  1,400 frames with inputs; a snapshot restored mid-history continues
  identically; a Gods session journals into a `gods-usa-new` store and
  resumes from its cache at the same state as a cold reconstruction;
- fresh-worker `history-verify --game gods --candidate original` passes on
  a constructed history (960 frames), and one deliberately shifted input
  is detected from its first differing frame.

Tests: `tests/games/gods/test_boot.py` (`scripts/run_tests.py gods`).
Everything above is constructed or headless evidence, not player gameplay.

## Phase 2: recording and replay (waiting for a recording)

`play.cmd --game gods` opens the Gods timeline; `--new` starts a cold root;
checkpoints and the exit checkpoint land in `history/gods/`.  The
manually recorded gameplay history that phase 3 needs does not exist yet.

## Phase 3: replay confidence (constructed evidence only so far)

Done on constructed input: same history from cold reset gives the same
terminal and per-frame state, video agrees, PCM agrees, cache restore does
not change the continuation, a fresh process reconstructs the history, a
deliberately altered input diverges detectably, and Aladdin caches or
snapshots are refused for Gods and vice versa
(`tests/common/test_games.py`).  To do on the real recording: the same
checks on its full length (`history-verify main --game gods --candidate
original --tree`), then a retained reference for `segment_verify`.

## Phase 4: the recovery grinding loop (not started)

Gods has no candidate provider, no boundary, no recovered module, no
census, no witnesses.  The first bounded region will be chosen from the
recorded path's execution evidence (`recovery_census.py --game gods` with a
Gods classifier, then the tracer), not from reading the ROM.  Note for that
step: `recovery_census.kind_classifier` reads the record kind byte at (A1),
an Aladdin object-table convention; Gods needs its own classifier passed to
`capture_entries`.

## What Gods has not got

No recovered routines, no address map, no semantic map, no native runtime,
no sound-driver knowledge, no witnesses.  `src/gods_sega` is the profile
alone.
