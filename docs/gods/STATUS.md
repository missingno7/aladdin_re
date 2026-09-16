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
- **The candidate `camera-sprites`** (`src/gods_sega/recovery.py`): the
  original with eighteen gates armed, the camera follow step `002806`, the
  sprite emitter `0018C8`, its RAM-only sibling `001164`, the work-table
  reset `004150`, the spawn queue `0049DA`, the grid cell lookup `0063FA`,
  the footprint stamp `00FDB8`, the solid drawer `00FC8E`, the animation
  step `00FE08`, the countdown check `010332`, the collision gate `010A14`,
  the zone check `00BCCE`, the particle drawer's own emitter `00126A`, the
  hazard tick `014084`, the trigger conditions `00470C`, the score
  conversion `00364C`, the trigger evaluator's non-firing arm `00462C` and
  the proximity table search-and-add `00F828`/`00F86A`; `camera`,
  `sprites`, `sprites-static`, `conditions`,
  `table-reset`, `spawn-queue`, `grid-cell`, `footprint`, `solid-draw`,
  `animation-step`, `countdown-check`, `collision-gate`, `zone-check`,
  `particle-emit`, `hazard-tick`, `score-convert`, `evaluator` and
  `proximity` arm each alone.

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
| `f40d7bcc9dda…` | 17,620 | census `census-002806-f40d7bcc9dda` (the three x-limit path classes); `census-0018C8-f40d7bcc9dda` |
| `fb408bc75597…`, `7251bbd0ecf7…`, `f40d7bcc9dda…` | — | the sprite emitter's census `census-0018C8-<node>` (27, 32 and 30 path classes; 134 fixtures) |
| `f0ac19738f19…`, `fb408bc75597…`, `7251bbd0ecf7…`, `f40d7bcc9dda…` | — | `001164`'s census `census-001164[-<node>]` (4, 20, 20 and 24 path classes; 23 fixtures free of an interposed VBlank, 82 total) |
| `f0ac19738f19…`, `fb408bc75597…`, `7251bbd0ecf7…`, `f40d7bcc9dda…` | — | `004150`'s census `census-004150[-<node>]` (1, 2, 1 and 1 path classes; 9 fixtures; the poison-fill arm is witnessed only on `fb408bc75597…`) |
| `f0ac19738f19…`, `fb408bc75597…`, `7251bbd0ecf7…`, `f40d7bcc9dda…` | — | `0049DA`'s census `census-0049DA[-<node>]` (5, 5, 3 and 1 path classes; 18 fixtures: 0-2 active slots, continuing or retiring; the only witnessed active occurrences fall at frames 428-2800 of the main history) |
| `f0ac19738f19…`, `fb408bc75597…`, `7251bbd0ecf7…`, `f40d7bcc9dda…` | — | `0063FA`'s census `census-0063FA[-<node>]` (a single path class on every recording; 6 fixtures) |

## Evidence that passes

| claim | evidence | artifact |
|---|---|---|
| the original is reproducible: two fresh workers agree on every frame of every branch (state, video, PCM, counters) | `history-verify main --game gods --candidate original --tree` | `artifacts/gods/verify-tree-2026-09-15` (29,731 frames, the first two recordings); the eight-recording tree with the candidate below |
| the player's exit cache ends where a cold run ends; two retained real states continue identically for 300 frames | `history-run --cache` vs cold; `segment_verify --candidate original` | `tests/games/gods/test_recording.py` |
| **`002806` camera follow step**: the plan reproduces every fact of the original on all 61 retained fixtures (nine path classes over three recordings: hold/right/left × the x limit, and the y limit) | `factcheck check` on every fixture | `tests/games/gods/test_camera.py` |
| `camera` reproduces the original on the tree of all eight recordings: **PASS, 107,519 frames, 41,109 hits, 0 fallbacks, 734,968 instructions replaced**; on `f40d7bcc…` (the x-limit recording) PASS, 0 fallbacks | `history-verify main --candidate camera --tree`; `history-verify f40d7bcc9dda --candidate camera` | `artifacts/gods/verify-camera-tree-2026-09-16b`, `artifacts/gods/verify-camera-f40d7bcc` |
| the negative control diverges at the first tick that enters the routine | `--candidate camera-mutant-result` | `artifacts/gods/verify-camera-mutant` (frame 329 on `f0ac1973…`), `verify-camera-mutant-f40d7bcc` (frame 1,540) |
| **`0018C8` sprite emitter**: the plan reproduces every fact of the original on all 134 retained fixtures over three recordings (off-screen x/y, cache hit after 1–8 slots, cache miss into an empty slot or the ninth; a miss is a seam: the prefix is checked to the VDP control write, the suffix from the resume) | `factcheck check` on every fixture (`MATCH (seam ...)` for the miss arm) | `tests/games/gods/test_sprites.py` |
| `sprites` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 40,935 hits (13,218 seams entered, 13,108 completed), 306 scheduler refusals, 0 foreign returns**; `camera-sprites` on the tree of all eight recordings: **PASS, 107,519 frames, 306,295 hits, 82,757 seams entered, 81,822 completed, 344 seam deadlines, 1,733 scheduler refusals, 9,443,248 instructions replaced** | `history-verify f0ac19738f19 --candidate sprites`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-sprites-f0ac1973b`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16b` |
| both sprite negative controls diverge at the first gameplay frame (a stored byte off; `d0` off in every admitted plan, which breaks the VDP command the machine reads at the seam) | `--candidate sprites-mutant-result`, `sprites-mutant-register` | `artifacts/gods/verify-sprites-mutant-result`, `verify-sprites-mutant-register` (frame 429) |
| **`001164` sprite emitter sibling**: the plan reproduces every fact of the original on all 23 retained fixtures free of an interposed VBlank, over four recordings (off-screen x, off-screen y, a placed record with and without the flip attribute); the list-full guard (`0011B8`) is unwitnessed | `factcheck check` on every fixture | `tests/games/gods/test_static_sprites.py` |
| `sprites-static` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 15,551 hits, 134 fallbacks (all scheduler admission: an interrupt due mid-activation)**; `camera-sprites` (all three gates) on the tree of all eight recordings: **PASS, 107,519 frames, 454,447 hits, 3,571 fallbacks (3,227 scheduler admission incl. 1,494 at `001164`, 344 seam deadline), 15,024,355 instructions replaced** | `history-verify f0ac19738f19 --candidate sprites-static`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-sprites-static-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16c` |
| the negative control diverges at the first frame that enters the region | `--candidate sprites-static-mutant-result` | `artifacts/gods/verify-sprites-static-mutant` (frame 457) |
| **`004150` work-table reset**: the plan reproduces every fact of the original on all 9 retained fixtures over four recordings (the common zero-fill arm; the rarer poison-fill arm witnessed once on `fb408bc75597…`) | `factcheck check` on every fixture | `tests/games/gods/test_tables.py` |
| `table-reset` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 6,669 hits, 0 fallbacks**; `camera-sprites` (all four gates) on the tree of all eight recordings: **PASS, 107,519 frames, 495,476 hits, 3,571 fallbacks (same reasons as before: 3,227 scheduler admission, 344 seam deadline), 16,583,517 instructions replaced** | `history-verify f0ac19738f19 --candidate table-reset`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-table-reset-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16d` |
| the negative control diverges at the first frame that enters the region | `--candidate table-reset-mutant-result` | `artifacts/gods/verify-table-reset-mutant` (frame 429) |
| **`0049DA` spawn queue**: the plan reproduces every fact of the original on all 18 retained fixtures over four recordings (0-2 active slots per tick, continuing or retiring); a RAM-only leaf that calls the already-recovered `001164` once per active slot | `factcheck check` on every fixture | `tests/games/gods/test_spawn_queue.py` |
| `spawn-queue` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 6,597 hits, 72 fallbacks (all scheduler admission)**; `camera-sprites` (all five gates) on the tree of all eight recordings: **PASS, 107,519 frames, 536,020 hits, 3,939 fallbacks (3,595 scheduler admission incl. 368 at `0049DA`, 344 seam deadline), 17,357,029 instructions replaced** | `history-verify f0ac19738f19 --candidate spawn-queue`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-spawn-queue-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16e` |
| the negative control diverges at the first frame that enters the region (an active slot; frame 1,021 is the first witnessed occurrence) | `--candidate spawn-queue-mutant-result` | `artifacts/gods/verify-spawn-queue-mutant` |
| **`0063FA` grid cell lookup**: the plan reproduces every fact of the original on all 6 retained fixtures over four recordings (a single path class: no branch, no store) | `factcheck check` on every fixture | `tests/games/gods/test_grid.py` |
| `grid-cell` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 6,709 hits, 86 fallbacks (all scheduler admission)**; `camera-sprites` (six gates) on the tree of all eight recordings: PASS, 107,519 frames, 577,899 hits, 4,366 fallbacks (4,022 scheduler admission incl. 427 at `0063FA`, 344 seam deadline), 17,733,940 instructions replaced | `history-verify f0ac19738f19 --candidate grid-cell`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-grid-cell-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16f` |
| **`00FDB8` footprint stamp**: the plan reproduces every fact of the original on all 27 retained fixtures over four recordings (four rows × cells combinations; the VBlank-pre-empted fixtures through `pathfacts.region_only`) | `factcheck check` on every fixture | `tests/games/gods/test_footprint.py` |
| `footprint` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 11,517 hits, 65 fallbacks (all scheduler admission)**; `camera-sprites` (all seven gates) on the tree of all eight recordings: **PASS, 107,519 frames, 648,130 hits, 4,882 fallbacks (4,538 scheduler admission, 344 seam deadline)** | `history-verify f0ac19738f19 --candidate footprint`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-footprint-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16g` |
| the footprint negative control diverges at frame 429 | `--candidate footprint-mutant-result` | `artifacts/gods/verify-footprint-mutant` |
| the negative control (a register, since the routine stores nothing) diverges at frame 6,185 | `--candidate grid-cell-mutant-result` | `artifacts/gods/verify-grid-cell-mutant` |
| **`00FC8E` solid drawer**: the plan reproduces every fact of the original on all 51 retained fixtures over four recordings (0-9 cells, off-screen cells skipped on the x or the y test, the table scan matching within 1-2 mismatches); the inline VDP upload arm (a table entry with the tile index's sign bit set) and an unterminated or unmatched table scan are declined (unwitnessed) | `factcheck check` on every fixture | `tests/games/gods/test_solids.py` |
| `solid-draw` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 11,472 hits, 110 fallbacks (all scheduler admission)**; `camera-sprites` (all eight gates) on the tree of all eight recordings: **PASS, 107,519 frames, 718,111 hits, 5,648 fallbacks (5,304 scheduler admission incl. 766 at `00FC8E`, 344 seam deadline)** | `history-verify f0ac19738f19 --candidate solid-draw`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-solid-draw-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16h` |
| the solid drawer's negative control (a register: the routine's own last write is the unconditional list-head pointer, corrupting it risks an address error in the unrecovered sprite-list flush) diverges at frame 429 | `--candidate solid-draw-mutant-result` | `artifacts/gods/verify-solid-draw-mutant` |
| **`00FE08` animation step**: the plan reproduces every fact of the original on the 6 retained 'idle'-arm fixtures over four recordings; the 'moving' arm (common, not merely unwitnessed) is declined -- it calls the unrecovered coroutine/dispatch at `00FFF0` | `factcheck check` on every fixture | `tests/games/gods/test_animation.py` |
| `animation-step` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 11,542 hits, 40 fallbacks (38 scheduler admission, 2 unsupported domain)**; `camera-sprites` (nine gates) on the tree of all eight recordings: **PASS, 107,519 frames, 788,232 hits, 6,274 fallbacks (5,609 scheduler admission, 344 seam deadline, 321 unsupported domain at `00FE08`)** | `history-verify f0ac19738f19 --candidate animation-step`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-animation-step-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16i` |
| the animation step's negative control (the last write is the shared frame-budget word, not a pointer) diverges at frame 430 | `--candidate animation-step-mutant-result` | `artifacts/gods/verify-animation-step-mutant` |
| **`010332` countdown check**: the plan reproduces every fact of the original on 38 of the 43 retained fixtures over four recordings ('idle'/'waiting', and the 'trigger' arm's own 'trigger-reject'/'trigger-spawn' sub-arms -- the countdown reload and frequency word, a direction-mirrored screen window test and a bounded pool scan+fill); the 'trigger-deep' sub-arm (a further A3 gate byte, calling unrecovered `0091BC`) and 'trigger-pool-full' (the same bounded pool exhausted, unwitnessed) are declined | `factcheck check` on every fixture | `tests/games/gods/test_timers.py` |
| `countdown-check` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 3,273 hits, 33 fallbacks (all scheduler admission)**; `camera-sprites` (all fourteen gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,019,144 hits, 11,195 fallbacks (7,040 scheduler admission, 3,728 seam deadline, 426 unsupported domain across two declined-call regions, 1 gate-without-planner foreign-return edge, tree still bit-exact)** | `history-verify f0ac19738f19 --candidate countdown-check`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-countdown-check2-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16p` |
| the countdown check's negative control diverges at frame 469 | `--candidate countdown-check-mutant-result` | `artifacts/gods/verify-countdown-check2-mutant` |
| **`010A14` collision gate**: the plan reproduces every fact of the original on all 20 retained fixtures over the two recordings that reach this entry ('held', 'gated', and now the 'collision' arm's own 'collision-clear'/'collision-held' sub-arms: `010CBC`'s arithmetic inline, a near/mid/far grid test); the 'collision-deep' sub-arm (a further A3 gate byte, an unbounded grid search) and the phase>7 arm ('over', real ROM code but unwitnessed on either recording) are declined | `factcheck check` on every fixture | `tests/games/gods/test_movement.py` |
| `collision-gate` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 1,426 hits, 14 fallbacks (all scheduler admission)**; `camera-sprites` (all fourteen gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,019,144 hits, 11,195 fallbacks (7,040 scheduler admission, 3,728 seam deadline, 426 unsupported domain across two declined-call regions, 1 gate-without-planner foreign-return edge, tree still bit-exact)** | `history-verify f0ac19738f19 --candidate collision-gate`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-collision-gate2-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16p` |
| the collision gate's negative control diverges at frame 469 | `--candidate collision-gate-mutant-result` | `artifacts/gods/verify-collision-gate2-mutant` |
| **`00BCCE` zone check**: the plan reproduces every fact of the original on all 69 retained fixtures over four recordings (a box test around the player's own position, widened on two levels; fully witnessed, no declines) | `factcheck check` on every fixture | `tests/games/gods/test_zones.py` |
| `zone-check` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 4,316 hits, 35 fallbacks (all scheduler admission)**; `camera-sprites` (all twelve gates) on the tree of all eight recordings: **PASS, 107,519 frames, 881,371 hits, 7,335 fallbacks (6,100 scheduler admission, 344 seam deadline, 891 unsupported domain)** | `history-verify f0ac19738f19 --candidate zone-check`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-zone-check-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16l` |
| the zone check's negative control (a register: 'held'/'outside', the great majority, store nothing durable at all) diverges at frame 475 | `--candidate zone-check-mutant-result` | `artifacts/gods/verify-zone-check-mutant` |
| **`00126A` particle drawer's own emitter**: `0018C8`'s own seam shape reproduced with this routine's addresses -- no per-frame cache, so every on-screen call uploads; the plan reproduces every fact of the original on all 58 retained fixtures over four recordings (off-screen x/y, flip and no-flip uploads) | `factcheck check` on every fixture | `tests/games/gods/test_particles.py` |
| `particle-emit` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 7,330 hits (3,314 seams entered, 3,026 completed), 335 fallbacks (53 scheduler admission, 282 seam deadline)**; `camera-sprites` (all thirteen gates) on the tree of all eight recordings: **PASS, 107,519 frames, 955,464 hits, 105,964 seams entered, 101,583 completed, 11,118 fallbacks (6,498 scheduler admission, 3,728 seam deadline, 891 unsupported domain, 1 gate-without-planner -- a foreign-return edge the shared seam runner already falls back on safely, tree still bit-exact)** | `history-verify f0ac19738f19 --candidate particle-emit`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-particle-emit-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16m` |
| the particle emitter's negative control diverges at frame 469 | `--candidate particle-emit-mutant-result` | `artifacts/gods/verify-particle-emit-mutant` |
| **`014084` hazard tick**: two disjoint bodies behind one early branch -- 'paint' (inactive, or an active object whose grid cell isn't 1: a tile-array write clamped to bounds) and 'spawn' (grid cell 1: a sound request, then a bounded 20-entry pool scan and fill, whether or not a slot was free); the plan reproduces every fact of the original on all 113 retained fixtures over four recordings; the 'trigger' arm (rare, gated by a parallel table byte and a counter, calling `00F828` -- now recovered on its own, `proximity`, but not yet composed into `hazard_tick_plan`) is declined | `factcheck check` on every fixture | `tests/games/gods/test_hazard.py` |
| `hazard-tick` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 26,075 hits, 218 fallbacks (185 scheduler admission, 33 unsupported domain)**; `camera-sprites` (all fourteen gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,018,584 hits, 11,755 fallbacks (7,038 scheduler admission, 3,728 seam deadline, 988 unsupported domain, 1 gate-without-planner foreign-return edge, tree still bit-exact)** | `history-verify fb408bc75597 --candidate hazard-tick`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-hazard-tick-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16n` |
| the hazard tick's negative control diverges at frame 2,628 (the first frame the region is exercised on `fb408bc75597…`) | `--candidate hazard-tick-mutant-result` | `artifacts/gods/verify-hazard-tick-mutant` |
| **`00470C` trigger conditions** (the first Gods dispatcher): the plan reproduces every fact of the original on all 129 retained fixtures over five census directories (fourteen kinds, every witnessed compare position) | `factcheck check` on every fixture | `tests/games/gods/test_conditions.py` |
| `conditions` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 5,247 hits, 36 fallbacks (all scheduler admission)**; `camera-sprites` (all fifteen gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,055,949 hits, 11,521 fallbacks (7,366 scheduler admission, 3,728 seam deadline, 426 declined arms of other regions), 30.6M instructions replaced** | `history-verify f0ac19738f19 --candidate conditions`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-conditions-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16p` |
| the conditions negative control (a failing condition reported as passing) diverges at frame 993; a register mutant was blind and was dropped | `--candidate conditions-mutant-outcome` | `artifacts/gods/verify-conditions-mutant` |
| **`00364C` score conversion**: 1-3 digit values (0-999), witnessed at both score-update call sites over four recordings; the plan reproduces every fact on all 12 retained fixtures | `factcheck check` on every fixture | `tests/games/gods/test_score.py` |
| `score-convert` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 56 hits, 0 fallbacks**; mutant DIVERGENCE at frame 675 | `history-verify f0ac19738f19 --candidate score-convert` | `artifacts/gods/verify-score-convert-f0ac1973`, `verify-score-convert-mutant` |
| **`00462C` trigger evaluator**: the non-firing arm, a composition of three calls into `00470C` (the boundary owns the call); the plan reproduces every fact on all 21 non-firing retained fixtures over four recordings; firing (11) and disabled (0, unwitnessed) decline | `factcheck check` on every fixture | `tests/games/gods/test_triggers.py` |
| `evaluator` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 1,708 hits, 55 fallbacks (32 firing, 21 scheduler admission, 2 disabled)**; mutant DIVERGENCE at frame 993 | `history-verify f0ac19738f19 --candidate evaluator` | `artifacts/gods/verify-evaluator-f0ac1973`, `verify-evaluator-mutant` |
| **`00F828`/`00F86A` proximity table search-and-add**: `00F828` owns its own call into `00F86A`; the plan reproduces every fact on all 14 'not-found'+'added' retained fixtures over two recordings (not exercised on `f0ac1973…`/`f40d7bcc…`); 'trigger' (19) and 'pool-full' (0, unwitnessed) decline | `factcheck check` on every fixture | `tests/games/gods/test_proximity.py` |
| `proximity` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 8 hits, 25 fallbacks (all the declined trigger arm)**; mutant DIVERGENCE at frame 12,890 | `history-verify fb408bc75597 --candidate proximity` | `artifacts/gods/verify-proximity-fb408bc75597`, `verify-proximity-mutant` |
| `camera-sprites` (all eighteen gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,032,299 hits, 11,608 fallbacks (7,188 scheduler admission, 3,728 seam deadline, 692 declined arms across nine reasons, 1 gate-without-planner foreign-return edge), 30.9M instructions replaced** | `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-camera-sprites-tree-2026-09-16q` |
| the suite: `scripts/run_tests.py gods` (common + Gods), about 50 s | 1,319 tests, 1 skipped | — |

The fallbacks that remain on the tree are all exact by construction: a
`scheduler admission` refusal is the native scheduler declining a plan or a
suffix because an interrupt is due inside its span (about one per cent of
`0018C8`'s activations, and `001164`'s and `0049DA`'s activations are long
enough that an interposed VBlank shows up on a real fraction of their
retained census fixtures; the original runs it), and a `seam deadline` is
the frame's observation instant falling inside the ceded upload loop (the
committed prefix stands; the original finishes the activation).  Neither
is an arm the candidate declined.

Declined on purpose (the original runs them): the two negative clamps of
the camera step (`002822`, `00283A`), the flipped-sprite arm of the emitter
(`001928`/`00199C`, sprite ids with bit 15 set) and `001164`'s list-full
guard (`0011B8`, `LIST_FULL` at `FFEE30`), none of which any recording has
entered.

## What is not recovered

Everything else.  Fourteen routines are recovered: the camera follow step
(`game/camera.py`, six words); the sprite emitter and its RAM-only sibling
(`game/sprites.py`: the sprite list at `FFEBF6`–`FFEBFF`, the per-frame
tile cache at `FFEE98`/`FFEEAA`, the dynamic-tile cursor `FFEE84`, the ROM
descriptor table `066794` indexed through `0019D2` for the dynamic emitter
and its own table at `0011E6` for the sibling, whose tile is a fixed
descriptor field instead of a cache slot); the work-table reset
(`game/tables.py`: an unconditional 1,600-byte fill below `FFC1BA`, zero or
-- rarely -- 0xFE with `FFEF5C` also cleared; the table's own purpose is
not known); the spawn queue (`game/spawn_queue.py`: four fixed 6-byte
slots at `FFF39A`, each an animation counter and a world position, that
call `001164` -- the first recovered example of "calls to routines already
recovered", the shape Aladdin's platform tail generalises to a plain call);
the grid cell lookup (`game/grid.py`: a pure address computation over
`FFF18C`/`FFF18E` into a work-RAM table (register value `FFFF885E`, i.e.
`FF885E`, not a ROM address) that `00FDB8` and `010CBC` also index, by
different transforms -- what the table holds is not known, but it is
live state, likely a per-level tile/collision grid); the footprint stamp
(`game/grid.py: stamp_footprint`: a solid's cells set into that same grid
and queued on the undo list, rows and cells bounded by the definition's own
height and width bytes); and the solid drawer (`game/solids.py`: the same
definition's rows x cells grid appended as sprite records into the sprite
list, the tile index looked up by type id in a work-RAM table pointer
(`SOLID_TILE_TABLE`) -- a found entry with the tile index's sign bit set
means the tiles are uploaded fresh by an inline VDP block instead, an arm
no recording enters); the animation step (`game/animation.py`: the
'idle' arm only -- the shared frame-budget word `FRAME_BUDGET` refreshed
from the definition's own field, on both arms; the common 'moving' arm
calls the unrecovered coroutine and per-type dispatch at `00FFF0` and is
declined); the countdown check (`game/timers.py`: a caller-supplied
control byte and countdown record, 'idle' and 'waiting' recovered; a
residue of zero reloads the countdown and a frequency word
unconditionally, then either the unrecovered `0091BC` pool (`'trigger-deep'`,
declined) or a direction-mirrored screen window test (`01158C`/`0115D4`'s
own shape) and, inside it, a bounded 20-entry pool scan+fill shaped like
`hazard.py`'s own (`'trigger-reject'`/`'trigger-spawn'`, both recovered;
`'trigger-pool-full'` declined as unwitnessed)); the collision gate
(`game/movement.py`: a phase counter and a +-4 residue test over a
caller-supplied state struct; 'held' and 'gated' recovered; a residue of
zero calls `010CBC` (`game/grid.py: grid_cell_at`, `0063FA`'s own
arithmetic parameterised on D0/D1 -- no direct caller of its own, so no
separate gate) and runs a near/mid/far grid test (`'collision-clear'`/
`'collision-held'`, both recovered; a further gate byte in a second
caller-supplied record routes to an unbounded grid search this module
does not model, `'collision-deep'`, declined as unwitnessed) and the
phase>7 arm declined as unwitnessed); and the zone check (`game/zones.py`: a box test around
the player's own position (`0063FA`'s own `GRID_X`/`GRID_Y`), widened on
two levels -- fully recovered, no declines, the routine's own eight-register
save/restore frame makes the whole box arithmetic scratch except a
cooldown word and D2's own final value); and the particle drawer's own
emitter (`game/sprites.py: emit_particle_sprite`, `00126A`: `0018C8`'s own
seam shape with this routine's own descriptor-offset convention -- the
caller passes the descriptor byte offset directly, no id-to-offset table
-- and no per-frame cache, so every on-screen call is a seam upload); and
the hazard tick (`game/hazard.py`: two disjoint bodies behind one early
branch, no save/restore frame at all -- 'paint' clamps a tile-array write
to bounds, 'spawn' requests a sound and fills a bounded 20-entry pool;
'trigger', the pool scan's own rare gate, calls `00F828` (recovered
separately, `proximity`, but not yet composed here) and is declined).  The
emitter's remaining siblings (`001256`/`001260`, `001312`) share
its descriptor layout and list conventions but are not recovered.  Three
more regions recovered 16 Sep: the score conversion (`game/score.py`: BCD
digit packing, threading the caller's own X flag as the first digit's
carry-in); the trigger evaluator's non-firing arm (`game/triggers.py`: a
composition of three calls into `00470C`, `00462C` owning the call; its
firing arm -- message, then a fifteen-handler action table -- declined);
and the proximity table search-and-add (`game/hazard.py:
proximity_search`/`proximity_add`: `00F828` owning its own call into
`00F86A`; the matching-and-still-fresh 'trigger' arm at `00F8A2`, a
caller-record dispatch with its own deliberate double stack return,
declined).  There is no object-table convention, no semantic map, no
native runtime, no sound-driver knowledge.  The seam for a platform
operation inside a region exists and is shared (`src/genesis_re/seam.py`);
Gods has one seam plan.

## Next bites

From the callee census of 600 gameplay frames
(`artifacts/gods/census/hot-calls-6000-6600.json`, `f0ac1973…` frames
6,000–6,600), RAM-only and executed every game tick — census each over the
longest recordings before choosing:

| entry | calls / 600 frames | length | what the trace shows |
|---|---|---|---|
| `0049DA` | 300 | 19-113 | recovered (`spawn-queue`): a scan of four 6-byte slots at `FFF39A` (an animation counter, a world position); an active slot calls the already-recovered `001164` once, then advances or retires the counter -- 0-2 calls witnessed per tick |
| `004150` | 301 | 38 or 40 (3,806 / 3,940 cycles) | recovered (`table-reset`): an unconditional 1,600-byte fill below `FFC1BA` by unrolled `movem` bursts, zero or (rarely) 0xFE per `FFF210`'s sign |
| `00FDB8` | 600 | 27–47 | recovered (`footprint`): a solid's footprint stamped into the level grid `FF885E` (32×16-pixel cells, 128 bytes per row), each cell's old byte queued on the undo list at A5; rows and cells are the definition's height and width bytes (A2 `+0x1B`, `+0x1A`); the no-footprint arm (width bit 7) unwitnessed, declined one path class, but a 34,904-frame census shows **16 distinct path classes** with differing loop trip counts -- looks like a per-object-type dispatch (varying tile sizes, record counts), not a bounded single-shape leaf; census every recording before treating this as a small candidate, or treat it as the first case needing an object-record convention |
| `002806` | 300 | 17–21 | recovered (`camera`) |
| `0018C8` | 742 | 10–145 | recovered (`sprites`): the dynamic sprite emitter with a per-frame tile cache; a miss uploads the tiles inline (`001974`–`001988`), the first Gods seam |
| `00126A` (`001256`, `001260`) | 412 | 305–307 | recovered (`particle-emit`): the emitter's sibling without the cache, called from `010248` (the particle drawer's jump table at `0100F2`) — `0018C8`'s own seam shape, no cache so every on-screen call is a seam; only 5-13 real path classes once censused with the current tracer (the earlier "32 + 17 overflowed" count was the online classifier retaining a fixture per deadline-cut occurrence, not per real path) |
| `001164` | 1,015 | 9–40 | recovered (`sprites-static`): the emitter's RAM-only sibling, its own descriptor-offset table (`0011E6`) and a fixed tile field instead of a cache (six callers) |
| `0063FA` | 309 | 9 (constant) | recovered (`grid-cell`): a pure address computation, one path, no branch, no store; three callers (`006468`, `006FFE`, `007282`) |
| `00FC8E` | 600 | 33–106 | recovered (`solid-draw`): the same definition `00FDB8` reads drawn as sprites, a work-RAM `(type id, tile index)` table scan then a rows x cells grid appended to the sprite list, off-screen cells skipped; the inline VDP upload arm (a negative table entry) declined, unwitnessed on every recording |

Screened over the full `fb408bc75597…` history (`recovery_census.py
--classifier entry`, not a direct park -- the 600-frame window's tight
min/max hid real diversity every time) and set aside, all for the same
reason: many more path classes than a bounded leaf has, always tracing
back to a caller-supplied object pointer (or a call into an unrecovered
routine that itself depends on one) -- the object-record convention, not
a grinder's to invent:

| entry | path classes (full history) | why |
|---|---|---|
| `00FE08` | 19 | recovered as `animation-step` (the 'idle' arm; 'moving' calls unrecovered `00FFF0`) |
| `010A14` | 10 | recovered as `collision-gate` (the 'held'/'gated' arms and, since 16 Sep, the 'collision' arm's own 'collision-clear'/'collision-held' sub-arms via `010CBC`, now also recovered; 'collision-deep' and phase>7 declined as unwitnessed) |
| `00BCCE` | 28 (15 real: 13 were the same VBlank-in-interrupt-handler misattribution `00FDB8`'s screening hit) | recovered as `zone-check`: fully witnessed, no declines |
| `00470C` | 30 (re-censused, current tracer) | a genuine per-type dispatch: `move.w d5,d0; add.w d0,d0; add.w d0,d0; movea.l $4718(pc,d0.w),a5; jmp (a5)` into a ROM jump table at `004718` (disassembles as `ori.b` data -- it is a table of handler addresses, not code) with at least a dozen distinct handler bodies; the census's 30 small (6-15 instruction) classes are those handlers' own bodies, not variants of one shape.  Leave for the supervisor: not a leaf, needs an object/kind convention |
| `010332` | 7 | recovered as `countdown-check` (the 'idle'/'waiting' arms and, since 16 Sep, the 'trigger' arm's own 'trigger-reject'/'trigger-spawn' sub-arms via `01158C`/`0115D4`, now also recovered; 'trigger-deep' (calls unrecovered `0091BC`) and 'trigger-pool-full' declined as unwitnessed) |
| `014084` | 32 retained + 25 more overflowed | recovered as `hazard-tick`: two disjoint bodies behind one early `tst.b $48(a1); beq`, as screened; both turned out to be plain leaves (the pool scan bounded like `0018C8`'s cache scan, the tile-array write clamped to bounds) once the sign-extension of each individual `adda.w` (not a single combined offset) was modelled correctly |
| `00126A` (`001256`, `001260`) | 32 retained + 17 more overflowed (on `f0ac1973…` alone) | recovered as `particle-emit`: **not** a per-type dispatch after all -- disassembly through `0012F4` is exactly `0018C8`'s own shape (camera subtraction, the same two screen-margin tests, a descriptor lookup at `066794`, the four-word sprite record, the inline VDP upload `0012F4`+).  Re-censused with the current tracer: 5-13 real path classes per recording, not 32+17 -- the earlier count was inflated the same way `00FDB8`'s was before its own fix |
| `00FDB8` | 16 (4 real: 13 were VBlank variants) | recovered — see the solids below |

`010CBC` (recovered 16 Sep as `game/grid.py: grid_cell_at`, used inline by
`collision_gate_plan`): exactly `0063FA`'s grid computation with X/Y taken
from D0/D1 instead of the fixed words `FFF18C`/`FFF18E`; still not a
candidate by itself (no direct caller was found in the census; it is only
reached through `010A14`), so it has no gate of its own -- the
`0049DA`-calls-`001164` shape without the separate gate, since that shape
needs one only when the callee has a direct call site elsewhere too.

Screened and set aside earlier, not first candidates: `013362` (600
calls, 3–1,047 instructions -- an interpreter or unbounded loop, not a
leaf), `00052E` (600 calls, 434–9,152 instructions -- likewise), `00BA8E`/
`010CD2` (412 calls each, 116–268 / 125–277 -- wide range, seam-shaped
candidates for later, once the object-record convention exists).
`00FC8E` was screened aside on the same "inherits `00FDB8`'s per-object-type
diversity" worry; it did not hold (see the third correction below) and the
routine is now recovered (`solid-draw`).

Re-screened 16 Sep alongside `010CBC` (which turned out trivial and is now
recovered, folded into `collision-gate`): `00F828`/`00F86A` (the hazard
tick's own `'trigger'` callee, recovered 16 Sep as `proximity` -- its own
'not-found'+'added' arm only, the 'trigger' arm at `00F8A2` declined) is
not the same shape as `010CBC`.  `00F828` unconditionally
calls `00F86A` first, which searches a 40-entry table at `FFFF0C70` for an
existing matching entry (by two coordinate words) and, on a match, decrements
a timer field and returns past *both* stack frames at once (`addq.w #4,a7`
before its own `rts`, discarding `00F828`'s own return address -- a deliberate
double-return, not a bug); only on no match does control fall into `00F828`'s
own pool-add step.  A real shape, not a tracer artifact -- recovered 16 Sep
as `proximity` (the 'not-found'+'added' composition; the 'trigger' arm at
`00F8A2` declined, unwitnessed real code).  `00BA8E`/`010CD2` were
re-screened the same day (`docs/gods/blockers/2026-09-16-00BA8E.md`):
`00BA8E` calls the already-recovered `00BCCE` (zone check) and requests a
sound (`FFFDEA`-style RAM write), then a bounded neighbourhood scan whose
"nothing found" tail (25 of 32 real path classes, `fb408bc75597…`) is
RAM-only and admissible in principle but not carried through -- the arm
that matters calls `013264`, which jumps through a ROM table at `12D04`
indexed by an object-type value (a genuine per-type dispatch); `010CD2`
calls `00BA8E` and, further in, the unrecovered `0091BC` on one path, and
`01158C`/`0115D4` (already reproduced at `010332`'s own addresses, not
called from here) on the others, plus a branch on a literal state value
(`010D7C`: `cmpi.w #$3d,d2`) that smells like a per-state dispatch.
Confirms the earlier assessment: these need the object-record convention
(and, for `010D7C`, possibly a dispatch read) before either is a full
candidate; `00BA8E`'s own clean arm is the next bite once that convention
-- or the time to derive its cost by hand -- exists.

Two corrections to that screening, from the supervisor's iteration on
`00FDB8`: (1) a caller-supplied record is not by itself a reason to defer
— the footprint stamp reads its definition through `A2` and its loop
counts are the definition's bytes, and it went through the whole ladder as
a plain leaf (`grinder-protocol.md` §"Candidate selection rules"); what
needs a convention is a dispatch through a type byte into unrecovered
handlers.  (2) Most of the "path classes" above were VBlank landing
positions, which the tracer now sets aside (`00FDB8`: 16 → 4)
(`00FE08` and `010332` were re-screened and are now recovered, each
as a dominant bounded arm plus a declined call into unrecovered code;
`00470C` was re-screened and confirmed a genuine per-type dispatch, not a
tracer artifact; `00126A` was read from the disassembly, then re-censused
with the current tracer once its shape was confirmed, and recovered as
`particle-emit` -- 5-13 real path classes, not 32+17; `014084` kept a
similar class count once re-censused (32 real classes, not fewer), but the
diversity turned out to be the pool-scan depth and the tile-write bound
outcome, not a dispatch -- recovered as `hazard-tick`).  (3)
`00FC8E`'s own worry ("per-object-type diversity" like `00FDB8`'s pre-fix
screening) also did not hold once censused with the current tracer: over
107,519 tree frames the routine only ever takes the positive (tile-table)
arm, in a small number of rows x cells shapes (1-3 rows, 1-3 cells) bounded
by the same definition bytes `00FDB8` reads; the negative (inline VDP
upload) arm is real ROM code but no recording enters it, so it is declined
like any other unwitnessed arm -- not a platform-tail seam that had to be
built.  A routine flagged as "per-object-type diversity" from a raw path-class
count is worth a real census before being set aside a second time.  (4)
`00BCCE`'s pre-staged census (28 path classes, 13 of them recorded as
"calls `0F4472`") was stale in a different way: a VBlank interrupt landing
mid-activation, whose own handler happens to call the sound Z80 transfer
`0F4472`, was misattributed to the region's own call list by an older
tracer -- re-censused, every one of those 13 classes collapses into the
same 15 real, RAM-only classes the rest of the occurrences already show,
and the region needed no decline at all.  A census directory's own
generation date does not track the tracer that produced it; re-run
`recovery_census.py` fresh rather than trust a pre-staged directory's
`calls`/`natives` fields when a decline looks surprising for a routine
this small.

**The solids** (the subsystem `00FDB8` and `00FC8E` belong to): 25 solid
objects, each a live record at `FF4AAE` (0x18 bytes: world x, y at
`+0`/`+2`, an active flag at `+4` — negative is empty — a frame index at
`+5`, four longs from `+6`) with a definition at `FF65A2` (0x1C bytes: a
type id at `+4`, an index at `+5`, four longs at `+6`, the footprint width
and height at `+0x1A`/`+0x1B`).  Every game tick `00FBB6` replays the undo
list (`00FAF4`, 50 entries at `FF4982`), then for each active solid: steps
its animation (`00FE08`, recovered as `animation-step`: the shared
frame-budget refresh and the 'idle' immediate return; the common 'moving'
arm calls `00FFF0`, a resumable Bresenham-style line walk that stores its
own continuation address back into the live record, then a per-object-type
jump-table dispatch on a state byte -- a coroutine and dispatch engine, not
a leaf, and the next real gap in this subsystem), stamps its footprint
(`00FDB8`), and draws it (`00FC8E`, recovered as `solid-draw`: the sprite
records for a width×height grid of 32×16 cells, tile index from the table
at `FFF2D6` by type id; a negative entry means the tiles are uploaded by an
inline VDP block from `FFEA2C`-relative data, unwitnessed and declined).
The grid `FF885E` is what `0063FA` (the player) and `010CBC` (the movers)
consult.  Next bites in this subsystem: `00FFF0`'s coroutine and its
`00FEC0`/`00FF54` per-type dispatch (a `NEW_GODS_SUBSYSTEM`-shaped gap, not
a leaf -- census the state-byte values it actually dispatches on before
attempting anything), then the whole per-tick pass `00FBB6` as a
composition of recovered leaves.

A general note for the next long leaf: a routine whose own activation runs
long enough to span a VBlank shows up as a `scheduler admission` fallback
at that gate on the tree (exact by construction, not a declined arm) --
`001164` and `0049DA` both do this; do not mistake it for a missed arm.

**The triggers** (the subsystem `00470C` belongs to): the level's trigger
records at `FFB01A` (0x18 bytes each) carry three (kind, argument)
condition pairs at `+0`..`+A`, an action index at `+10` and a message
index at `+14`; the evaluator `00462C` presets three result slots
(`FFF38C`/`FFF38E`/`FFF390`) to -1, calls `00470C` for each pair (kind in
D5, argument in D6, slot in A3), ANDs the slots, and on all-true marks the
record fired, shows its message (`0046A4`–`0046B4`, through `007986` /
`0079DC`), and dispatches its action through the ROM table at `0046D0`
(fifteen handlers).  `00470C` is recovered: fourteen of its seventeen
predicate kinds (0–3, 5–12, 15, 16) over the current markers `FFF22E`, the
tracked ids `FFEF8C`/`FFF01E`/`FFF0B0`, the status words `FF502A`, the two
progress words `FFEF3E`/`FFF1CC`, the elapsed seconds `FFF2AA`/`FFEEC0`
and the flagged entries `FF62F6`; kinds 4, 13 and 14 stay declined -- not
because `00364C` is unrecovered (it now is) but because no recording ever
calls `00470C` with kind 13 or 14 at all (checked against every condition
census directory: no kind-13/14 fixture exists anywhere), so the (kind,
arm) pair has no fact to admit.  `00364C` (the score conversion the two
score kinds would call) is recovered on its own merits: a RAM-only leaf
witnessed directly from its other two callers, the score-update sites
`0035B2`/`003604` (`game/score.py`, candidate `score-convert`).  The
evaluator `00462C` is recovered on its non-firing arm: a composition of
three calls into the already-recovered `00470C` (the boundary owns the
whole call, the shape `0049DA` calling `001164` proved), ANDing the three
slots (`game/triggers.py`, candidate `evaluator`); its firing arm (message,
then the action dispatch table at `0046D0`, fifteen handlers) is a second
dispatcher, declined and left for the supervisor.  The disabled arm
(`FFEF38` nonzero, skipping evaluation entirely) is real ROM code no
recording has ever entered: declined too.  Next in this subsystem: the
action dispatch table's fifteen handlers, each its own leaf or seam.

Deferred, not first candidates: `003BEC` (the tile-pair VDP writer inside
the map streaming interpreter `003158`/`003480`, which does not return
within a frame), `0F4472`/`0F44AA` (the sound-command transfer into the Z80
window `A01F80`, called from the VBlank handler), anything under the
VBlank handler (`0003DC`), `001098` (the per-tick sprite-list flush: two VDP
blocks with RAM work between them — a platform tail from its first block
would recover 13 instructions).  Sound requests in Gods are RAM writes
into the command block `FFFDEA` (`0F446C`); the transfer to the Z80 is the
VBlank handler's, so a region that requests a sound is RAM-only here.

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
