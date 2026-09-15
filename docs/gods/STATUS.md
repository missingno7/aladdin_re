# Gods (USA): status

Current state only.  The per-region record is `ledger.md`; the iteration
recipe is `grinder-protocol.md`; the worker prompt is `grinder-goal.md`.
Last updated 16 September 2026.

## The cartridge

`assets/Gods (USA).md`: 1,048,576 bytes, SHA-256
`f7e577a66ed4d9901cb44ed0620e61439527cfbd854bc4626173b17e30fa6be0`, header
"SEGA GENESIS", "(C)SEGA 1992.JUN", name "GODS", serial "GM T87016  -00",
region "U", ROM `000000`–`0FFFFF`, work RAM `FF0000`–`FFFFFF`, header
checksum `E80A` (equal to the computed sum), entry `000200`.  Profile
`gods-usa-ntsc-v1` (`src/gods_sega/profile.py`); any other file is refused.
It runs on the shared machine with no game-specific change; the three
platform fixes its boot path needed were made in PortForge and pinned
(`695bc65`).  The game runs its logic every other frame (30 Hz).

## What runs today

- **The original**, cold from power-on, on every recorded history.
- **The candidate `camera`** (`src/gods_sega/recovery.py`): the original with
  one gate armed, the camera follow step `002806`.

## Recorded histories (`history/gods/`, root `gods-usa-new`)

Eight player recordings, all from power-on, three of them branched from
checkpoints of an earlier one; 14,583 to 34,904 frames each, 107,519 frames
of tree edges in total (about thirty minutes of play).  The longest,
`fb408bc75597…` (the current `main`, score 261,208 at its end), goes well
beyond level 1; `f40d7bcc9dda…` reaches the right end of a wide level (the
camera's x limit).  Screenshots and labels are in the timeline
(`play.cmd --game gods`).  Retained evidence for the loop is pinned to node
ids, never to `main`:

| node | frames | what it holds |
|---|---|---|
| `f0ac19738f19…` | 15,148 | the reference for `segment_verify` (`artifacts/gods/evidence/main/reference.json`) and the retained boundary states at frames 6,000 and 12,000; the census `artifacts/gods/evidence/census-002806` |
| `fb408bc75597…` | 34,904 | census `census-002806-fb408bc75597` |
| `7251bbd0ecf7…` | 25,264 | census `census-002806-7251bbd0ecf7` |
| `f40d7bcc9dda…` | 17,620 | census `census-002806-f40d7bcc9dda` (the three x-limit path classes) |

## Evidence that passes

| claim | evidence | artifact |
|---|---|---|
| the original is reproducible: two fresh workers agree on every frame of every branch (state, video, PCM, counters) | `history-verify main --game gods --candidate original --tree` | `artifacts/gods/verify-tree-2026-09-15` (29,731 frames, the first two recordings); the eight-recording tree with the candidate below |
| the player's exit cache ends where a cold run ends; two retained real states continue identically for 300 frames | `history-run --cache` vs cold; `segment_verify --candidate original` | `tests/games/gods/test_recording.py` |
| **`002806` camera follow step**: the plan reproduces every fact of the original on all 61 retained fixtures (nine path classes over three recordings: hold/right/left × the x limit, and the y limit) | `factcheck check` on every fixture | `tests/games/gods/test_camera.py` |
| `camera` reproduces the original on the tree of all eight recordings: **PASS, 107,519 frames, 41,109 hits, 0 fallbacks, 734,968 instructions replaced**; on `f40d7bcc…` (the x-limit recording) PASS, 0 fallbacks | `history-verify main --candidate camera --tree`; `history-verify f40d7bcc9dda --candidate camera` | `artifacts/gods/verify-camera-tree-2026-09-16b`, `artifacts/gods/verify-camera-f40d7bcc` |
| the negative control diverges at the first tick that enters the routine | `--candidate camera-mutant-result` | `artifacts/gods/verify-camera-mutant` (frame 329 on `f0ac1973…`), `verify-camera-mutant-f40d7bcc` (frame 1,540) |
| the suite: `scripts/run_tests.py gods` (common + Gods), about 25 s | 189 tests | — |

Declined on purpose (the original runs them): the two negative clamps of
the camera step (`002822`, `00283A`), which no recording has entered.

## What is not recovered

Everything else.  One routine of about twenty instructions is recovered; the
address map is the six words it touches (`src/gods_sega/game/camera.py`).
There is no object-table convention, no semantic map, no seam for a
platform call inside a region, no native runtime, no sound-driver
knowledge.  `src/gods_sega` is the profile, one semantic module, one planner
and the dispatcher.

## Next bites

From the callee census of 600 gameplay frames
(`artifacts/gods/census/hot-calls-6000-6600.json`, `f0ac1973…` frames
6,000–6,600), RAM-only and executed every game tick — census each over the
longest recordings before choosing:

| entry | calls / 600 frames | length | what the trace shows |
|---|---|---|---|
| `0049DA` | 300 | 19 | a scan of four 6-byte slots at `FFF39A` for a negative word; leaves the index in D7; no writes |
| `004150` | 301 | 38 (3,806 cycles) | the table clear below `FFC1BA` by `movem` bursts: up to 0x200 bytes written (the atomic limit is 2,048) |
| `00FDB8` | 600 | 27 | from `00FC08`: a 6-byte record appended at A5 from the ROM table at `00885E` |
| `002806` | 300 | 17–21 | recovered (`camera`) |
| `001164` | 1,015 | 13–40 | the screen-bounds test before a sprite record is emitted (six callers) |

Deferred, not first candidates: `003BEC` (writes the VDP at `C00000`),
`0F4472`/`0F44AA` (the sound-command transfer into the Z80 window
`A01F80`), anything under the VBlank handler (`0003DC`).

## Open questions

- An address error during play on 15 September (PC `012E46`: the second
  tracked object record's index at `FFF01E` was −1 while `FFF378` still held
  its pointer) could not be reproduced; the session's inputs were lost.  A
  session that faults now preserves its inputs as a node
  (`reason: execution_failure`); if it recurs, resume that node and step
  once.  The precondition is ordinary play: the recordings `f40d7bcc…`,
  `7251bbd0…` and `fb408bc7…` set `FFF378` (92, 67 and 1 times) and two of
  them retire the record once (`004AE2` writes −1 to `FFF01E`) without
  faulting; the fault needs the retire to fall between the pointer's
  computation (`008306`) and its use (`012DD6`).  Whether that ordering is
  the game's own or a machine timing effect is open until it is recorded.
