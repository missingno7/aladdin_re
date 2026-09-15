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

## Aladdin through the same boundary

After the split, `history-verify 44223150b7d6… --game aladdin --candidate
lifecycle` (the 82,161-frame recording, two fresh workers) passed with 0
restores and 137 fallbacks, the count recorded before the split
(`artifacts/multi-game-aladdin-main`, 414 s).

## Phase 2: recording and replay (done, player recordings)

On 15 September 2026 the user recorded two cold histories with
`play.cmd --game gods` (root `gods-usa-new`, store `history/gods/`):

| node | frames | input changes | content |
|---|---|---|---|
| `ca2b703b6fd5…` | 14,583 | 1,382 | title, Begin Quest, level 1 play, back to the title menu |
| `f0ac19738f19…` (`main`) | 15,148 | 1,594 | the same route, longer (score 28,703 by frame 12,000) |

Both appear in the Gods timeline only; the exit checkpoint's cache resumes
either.  These are real player input, about four minutes of level-1 play
each, not constructed fixtures.

## Phase 3: replay confidence (done on the recordings)

- `history-verify main --game gods --candidate original --tree`: two fresh
  workers agree on every canonical frame of both recordings (29,731 frames:
  state, video, PCM chain and byte count, CPU/Z80 counters, PC/SR,
  terminal) — PASS, `artifacts/gods/verify-tree-2026-09-15`, 121 s.
- `history-verify main` alone: PASS (`artifacts/gods/verify-main-2026-09-15`,
  61 s); its `reference.json` is retained under
  `artifacts/gods/evidence/main/`.
- `history-run main --game gods --cache` (the player's own exit cache) ends in
  the same terminal observation as the cold run (state
  `52187597…`, PCM `569fb39e…`, 53,860,180 PCM bytes, frame 15,148).
- Two frame-boundary states of `main` (frames 6,000 and 12,000, captured on
  a cold run) verify against the reference for 300 frames each with
  `segment_verify.py --game gods --candidate original`
  (`tests/games/gods/test_recorded_evidence.py`, skipped where the local
  evidence is absent).
- A deliberately shifted input diverges detectably; Aladdin caches and
  snapshots are refused for Gods and vice versa (constructed tests in
  `tests/games/gods/test_boot.py` and `tests/common/test_games.py`).

The oracle/replay path is trustworthy on the recorded route: level 1 of
the original game, from power-on.  A PASS covers these histories and the
original execution only.

## Phase 4: the recovery grinding loop (not started)

Gods has no candidate provider, no boundary, no recovered module, no
census, no witnesses.  The first bounded region will be chosen from the
recorded path's execution evidence (`recovery_census.py --game gods` with a
Gods classifier, then the tracer), not from reading the ROM.  Note for that
step: the census's `--classifier kind` reads the record kind byte at (A1),
an Aladdin object-table convention; use `--classifier entry` (no game
knowledge) until Gods has its own.

## What Gods has not got

No recovered routines, no address map, no semantic map, no native runtime,
no sound-driver knowledge, no witnesses.  `src/gods_sega` is the profile
alone.
