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
  (`tests/games/gods/test_recording.py`, skipped where the local
  evidence is absent).
- A deliberately shifted input diverges detectably; Aladdin caches and
  snapshots are refused for Gods and vice versa (constructed tests in
  `tests/games/gods/test_boot.py` and `tests/common/test_games.py`).

The oracle/replay path is trustworthy on the recorded route: level 1 of
the original game, from power-on.  A PASS covers these histories and the
original execution only.

## Phase 4: the recovery grinding loop (one iteration done)

The loop the Aladdin process settled on, instantiated for Gods with the
shared tools and no new machinery:

1. **Observe executed regions.** `scripts/hot_calls.py --game gods --from
   6000 --to 6600` single-steps 600 frames of the recorded level-1 play
   (5.0M instructions, 17 s) and lists 118 callees with counts and
   activation lengths (`artifacts/gods/census/hot-calls-6000-6600.json`).
   The game logic runs every other frame (300 main-loop calls in 600
   frames).  Screening the small, constant-length, RAM-only callees with the
   tracer left the camera follow step **002806** (17-21 instructions, two to
   four words written, no calls, no device access, once per game tick).
2. **Bounded candidate.** `recovery_census.py --game gods --classifier entry
   --entry 002806` over the whole `main` recording: 6,678 occurrences, six
   distinct executed paths, none deadline-cut, twelve retained entry
   states (`artifacts/gods/evidence/census-002806`).  Three arms of the
   routine (the x-negative, x-limit and y-negative clamps at 002822, 00282C,
   00283A) were never entered by either recording.
3. **Recovered source.** `src/gods_sega/game/camera.py` (`camera_follow`:
   the camera x eases by 4 toward the follow point, y snaps, the halved
   clamped values feed the scroll pipeline), `src/gods_sega/boundary.py`
   (`camera_follow_plan`: the exact writes, D0.W, A7, PC, CCR incl. X from
   the asr, per-path instruction and cycle cost), `src/gods_sega/recovery.py`
   (`Candidate('camera')`, gate 002806, admission through `Machine.atomic`).
   The three unwitnessed clamps are declined (`UnsupportedCandidate`) and
   the original runs them; they are readable in the ROM but not recovered.
4. **Strict witness.** `factcheck.py check FIXTURE gods_sega.boundary:
   camera_follow_plan --game gods`: MATCH on all ten retained fixtures (six
   paths, four CCR variants): cycles, instructions, last PC, every written
   byte, every changed register.
5. **Future continuation.** `segment_verify.py --game gods --candidate
   camera` from the retained frame-6000 and frame-12000 states: PASS over
   300 frames each against the reference, 150 hits, 0 fallbacks.
6. **Fresh-process replay.** `history-verify main --game gods --candidate
   camera`: two fresh workers, every canonical frame of the 15,148-frame
   recording equal in state, video and PCM — **PASS, 6,678 candidate hits, 0
   fallbacks, 119,994 instructions replaced** (`artifacts/gods/verify-camera-main`,
   60 s).  The tree over both recordings: PASS, 29,731 frames, 11,448 hits,
   0 fallbacks (`artifacts/gods/verify-camera-tree`).
7. **Negative control.** `--candidate camera-mutant-result` (one stored byte
   off by one) diverges at frame 329, the first game tick that enters the
   routine (`artifacts/gods/verify-camera-mutant`); on the frame-6000
   segment it diverges at frame 6001.

Tests: `tests/games/gods/test_camera.py` (semantics always; the fixture and
reference tiers when the local evidence exists).  What this proves: the
recovered camera step reproduces the original's effects on every state the
recordings reach.  What it does not prove: the three clamp arms, or anything
about Gods beyond this routine.

What the second game needed that the first had to invent: nothing in the
machine, the histories, the replay runner, the verifier or the tracer.  New
for Gods: `hot_calls.py` (a callee census, shared), a Gods `AtomicPlan` /
`Candidate` of about ninety lines mirroring Aladdin's contract (the one
piece worth lifting into `genesis_re` once a third game repeats it), and
the census's `--classifier entry`.

## Next bites

From the same census, RAM-only and every game tick: 0049DA (19 instructions,
a scan of four 6-byte slots at FFF39A for a negative word, returns the index
in D7), 004150 (38 instructions, the table clear below FFC1BA — up to 0x200
bytes written, the atomic limit allows 2,048), 00FDB8 (27 instructions from
00FC08, a 6-byte record appended at A5 from the ROM table at 00885E),
001164 (38 instructions, 1,015 calls, the screen-bounds test before a sprite
record is emitted).  Regions that touch the VDP (003BEC writes C00000) or
the Z80 window (0F4472, the sound command transfer) are platform seams, not
first candidates.

## What Gods has not got

One recovered routine of about twenty instructions; no address map beyond
the six words it touches, no semantic map, no native runtime, no
sound-driver knowledge.  `src/gods_sega` is the profile, the camera step,
its boundary and the dispatcher.
