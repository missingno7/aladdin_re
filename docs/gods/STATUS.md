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

## Phase

Recover and compose upward inside the original execution.  The goal of
this phase is not a native Gods runtime: it is to push recovered
ownership up the original call graph until the bounded frontier is
substantially exhausted (`../common/recovery-process.md`, "The three
things a game is").  Native readiness is a design property of the
semantics (`game/` functions take readers and arguments, never the
machine), not the frontier.  Progress is reported as: behaviour
recovered and proven, boundaries newly owned, leaf-to-parent
compositions, dispatcher families closed, subsystem structure found,
original execution removed by upward composition, hard blockers, any
temporary adapter and why, whether the bounded frontier is still
productive, and what evidence would justify the native phase.

## The observation instant and the adapter's refusals

The replay observes the machine, and deadlines recovered operations, at
0.845 of the frame (raster line ~221, `OBSERVATION_OFFSET_TICKS` in
`profile.py`): the idle instant of the parity wait just before the
vertical interrupt, measured over every recording in the timing research
of 16 September (`research/timing-and-verification-2026-09-16.md`,
`research/timing-verification-pass-2026-09-16.md`).  The default
(mid-frame) instant sat inside Gods' busy window in nine ticks of ten,
so a plan or a seam suffix at the frame's end was refused for no reason of
the game's.  The input instant is the frame wrap and did not move; the
original's trajectory is the same at either instant (its observations are
not: the cache key carries the instant, `cache_contract` 4).

A fallback that is not a declined arm is the adapter refusing an exact
span, and the dispatcher records why (`Machine.refusal`, ABI 3):
`observation deadline` (the instant precedes the span's end), `z80 bank
guard` (the sound driver's bit-serial bank switch leaves the Z80 bank
register pointing at work RAM for a few raster lines; `al_atomic` refuses
any span meanwhile — an adapter conservatism under separate, read-only
investigation, not a game fact), `vblank in span` (a vertical interrupt is
due inside the span), `machine admission` (another condition of the
engine's).  All four are exact: the original runs the span.  The earlier
explanation here — that the refusals were interrupts due inside spans —
described the minority.

Measured on the tree of all eight recordings with the twenty-three-gate
candidate, before and after the instant moved (`artifacts/gods/verify-camera-sprites-tree-2026-09-16x`
→ `verify-camera-sprites-tree-instant`): hits 1,041,708 → **1,047,654**,
fallbacks 13,293 → **6,905**; of the 6,905: `z80 bank guard` 4,214,
declined arms 1,588 (the walker and the firing-arm callees, below),
`seam deadline` 443 (was 3,728), `observation deadline` 335, `vblank in
span` 298, `machine admission` 27.  The original at the new instant is
reproducible on the whole tree (`verify-original-tree-instant`) and the
candidate equals it everywhere; the retained boundary states and the
segment reference (`artifacts/gods/evidence/main`) were retained again at
the new instant (the old ones are beside them in `main-mid-frame-instant`).
The Z80 bank guard, the largest class, is an adapter conservatism with a
read-only study and a candidate narrower rule
(`research/z80-bank-guard-2026-09-16.md`, R1: refuse a *completed* bank
into work RAM only); it is not changed by this baseline.

## What runs today

- **The original**, cold from power-on, on every recorded history.
- **The candidate `camera-sprites`** (`src/gods_sega/recovery.py`): the
  original with twenty-six gates armed, the camera follow step `002806`, the
  sprite emitter `0018C8`, its RAM-only sibling `001164`, the work-table
  reset `004150`, the spawn queue `0049DA`, the grid cell lookup `0063FA`,
  the footprint stamp `00FDB8`, the solid drawer `00FC8E`, the animation
  step `00FE08`, the countdown check `010332`, the collision gate `010A14`,
  the zone check `00BCCE`, the particle drawer's own emitter `00126A`, the
  hazard tick `014084`, the trigger conditions `00470C`, the score
  conversion `00364C`, the trigger evaluator's non-firing arm `00462C`, the
  proximity table search-and-add `00F828`/`00F86A`, the pickup award
  `013264`, the next-random draw `014A3C`, the effect pool add `00932C`, the
  pickup check `00BA8E`, the pickup probe `010CD2`, the line walker's object
  resume `00FFF0`, the projectile launch `0091BC` and the line walker's
  projectile resume `0093D2`; `camera`, `sprites`, `sprites-static`, `conditions`, `pickups`,
  `table-reset`, `spawn-queue`, `grid-cell`, `footprint`, `solid-draw`,
  `animation-step`, `countdown-check`, `collision-gate`, `zone-check`,
  `particle-emit`, `hazard-tick`, `score-convert`, `evaluator`,
  `proximity`, `next-random`, `effect-pool-add`, `pickup-check`,
  `pickup-probe`, `walker`, `projectile-launch` and `projectile-resume`
  arm each alone.

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
| **`00FE08` animation step**: the plan reproduces every fact of the original on all 43 retained fixtures over four recordings -- the 'idle' arm and, since 17 Sep, the 'moving' arm's own call into the already-recovered walker resume `00FFF0` (`moving-continue`: the walk has not finished this call; `moving-complete`: it has, with more than one waypoint left, the next one loaded and the slot reset to -1); `moving-coldstart` (the walk finishes with at most one waypoint left, falling into a per-object-type waypoint dispatch `00FEC0`/`00FF54`) is declined -- censused fresh over all eight recordings, unwitnessed on every one -- along with a zero budget and a record whose continuation is not one of the walker's own bodies | `factcheck check` on every fixture | `tests/games/gods/test_animation.py` |
| `animation-step` reproduces the original on `fb408bc7…`: **PASS, 34,904 frames, 30,043 hits, 39 fallbacks, all exact adapter refusals (0 unsupported domain)**; `camera-sprites` (twenty-four gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,047,974 hits, 6,586 fallbacks (00FE08's own fallbacks-by-gate 321 → 118, all now exact adapter refusals, 0 unsupported domain at this gate)** | `history-verify fb408bc75597 --candidate animation-step`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-animation-step2-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17a` |
| the animation step's negative control diverges at frame 2,260, the tree's first entry into the 'moving' arm | `--candidate animation-step-mutant-result` | `artifacts/gods/verify-animation-step2-mutant` |
| **`010332` countdown check**: the plan reproduces every fact of the original on all 64 retained fixtures over four recordings ('idle'/'waiting', the 'trigger' arm's own 'trigger-reject'/'trigger-spawn' sub-arms, and, since 17 Sep, 'trigger-deep-launch' -- the record's own position and a rate-derived budget straight into the already-recovered projectile launch `0091BC`); 'trigger-deep-pool-full' and 'trigger-pool-full' (both the same shape of bounded pool exhausted, unwitnessed) are declined | `factcheck check` on every fixture | `tests/games/gods/test_timers.py` |
| `countdown-check` reproduces the original on `f40d7bcc9dda…` (the history that witnesses 'trigger-deep-launch'): **PASS, 17,620 frames, 3,277 hits, 33 fallbacks, all exact adapter refusals (0 unsupported domain)**; `camera-sprites` (twenty-six gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,049,180 hits, 6,589 fallbacks, tree bit-exact -- the `countdown check trigger arm calls unrecovered 0091BC` fallback reason is gone** | `history-verify f40d7bcc9dda --candidate countdown-check`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-countdown-check3-f40d7bcc9dda`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17d` |
| the countdown check's negative control diverges at frame 2,696 (on `f40d7bcc9dda…`) | `--candidate countdown-check-mutant-result` | `artifacts/gods/verify-countdown-check3-mutant` |
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
| **`013264` pickup award + `013316` grid inverse/debris burst**: the plan reproduces every fact of the original on the 25 retained item/special fixtures and all 11 code −4 fixtures (the sound-off debris arm) over four recordings; the sound-on, rate-limit and pool-exhausted arms of 013316 decline as unwitnessed | `factcheck check` on every fixture | `tests/games/gods/test_pickups.py`, `tests/games/gods/test_pickup_check.py` |
| `pickups` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 155 hits, 1 fallback (scheduler admission)** -- the one code −4 occurrence on this history is now admitted (was declined); `camera-sprites` (all twenty-two gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,041,676 hits, 13,142 fallbacks, tree bit-exact** | `history-verify f0ac19738f19 --candidate pickups`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-pickups-f0ac1973b`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16w` |
| the pickup negative control diverges at the first award | `--candidate pickups-mutant-result` | `artifacts/gods/verify-pickups-mutant2` |
| **`014A3C` next-random draw**: a single path (no branch); the plan reproduces every fact on both retained fixtures | `factcheck check` on every fixture | `tests/games/gods/test_pickup_check.py` |
| `next-random` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 727 hits, 5 fallbacks (all scheduler admission)**; mutant DIVERGENCE at frame 1,340 (a register: the drawn word, not the stored cursor -- the cursor itself can wrap onto an odd address and fault the 68000 on its own next read) | `history-verify f0ac19738f19 --candidate next-random` | `artifacts/gods/verify-next-random-f0ac1973`, `verify-next-random-mutant2` |
| **`00932C` effect pool add**: the general form `hazard.py`'s own `_spawn` inlines with `d2=d3=0`; the plan reproduces every fact on all 21 retained fixtures (0-19 skips before the found test, and the pool-full arm itself) | `factcheck check` on every fixture | `tests/games/gods/test_pickup_check.py` |
| `effect-pool-add` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 89 hits, 0 fallbacks**; mutant DIVERGENCE at frame 1,340 | `history-verify f0ac19738f19 --candidate effect-pool-add` | `artifacts/gods/verify-effect-pool-add-f0ac1973`, `verify-effect-pool-add-mutant` |
| **`00BA8E` pickup check**: a composition over the already-recovered zone check, pickup award, next-random and effect-pool-add; the plan reproduces every fact on 665 retained fixtures over all eight recordings (the clean arm's own near/far/none/bail sub-arms per axis, the array-append side effect, found-sound, found-bare, found-effect including both jitter axes' own default-mask arm and the second jitter's own negative branch, the effect pool's own full arm, and code -4-and-below's own cascade into 013316 composed inline the way the direct 013264 gate already does); only the special-1 pickup's own further decrement going negative (`jsr 011540`, unrecovered), the digit-split message tail and 013316's own sound-on/pool-exhausted arms decline as unwitnessed by any of the eight recordings (17 Sep: re-censused with `--max-classes 400` on `fb408bc75597…` after the default 32-class cap was found to silently discard rarer real classes -- 400 real path classes, not 32) | `factcheck check` on every fixture | `tests/games/gods/test_pickup_check.py` |
| `pickup-check` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 4,320 hits, 31 fallbacks (all z80 bank guard)** -- up from 4,260 hits/91 fallbacks, every previously-declined arm but the three above now admits; `camera-sprites` (all twenty-three gates, tree still fold `pickup-probe` in) on the tree of all eight recordings: **PASS, 107,519 frames, 1,046,640 hits, 5,845 fallbacks (4,218 z80 bank guard, 443 seam deadline, 345 observation deadline, 304 vblank in span, 189 evaluator firing/disabled, 97 hazard tick trigger, 76 proximity trigger, 27 machine admission, 146 pickup check declines (145 found-message, 1 found-special-timer) -- down from 13,151 fallbacks, tree bit-exact** | `history-verify f0ac19738f19 --candidate pickup-check`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-pickup-check2-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17e` |
| the pickup check's negative control diverges at the first found award | `--candidate pickup-check-mutant-result` | `artifacts/gods/verify-pickup-check2-mutant` |
| **`010CD2` pickup probe**: a caller-supplied record's own camera-relative call into the already-recovered pickup check, composed by calling `pickup_check_plan` itself with a synthetic register file for the point `00BA8E` is entered (one level deeper than the `0049DA`-calls-`001164` shape); the plan reproduces every fact on all 33 retained fixtures, none declined (was 32, one DECLINED) | `factcheck check` on every fixture | `tests/games/gods/test_pickup_check.py` |
| `pickup-probe` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 3,283 hits, 23 fallbacks (all z80 bank guard)** -- up from 3,248 hits/58 fallbacks, the pickup-check found-jitter-y-negative decline is gone; `camera-sprites` (all twenty-three gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,046,640 hits, 5,845 fallbacks, tree bit-exact** (same cold run as the row above) | `history-verify f0ac19738f19 --candidate pickup-probe`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-pickup-probe2-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17e` |
| the pickup probe's negative control (result-byte and register mutants either crash the 68000 on an unrecovered coroutine's own record read, or are blind on a scratch register) diverges at frame 469 by dropping all writes instead | `--candidate pickup-probe-mutant-result` | `artifacts/gods/verify-pickup-probe-mutant3` |
| **`00FFF0` line walker resume**: every fact on 35 retained fixtures over four recordings; consecutive invocations over 300 real frames continue from the re-armed record | `factcheck check`; `segment_verify` from a retained walker state | `tests/games/gods/test_walker.py`, `test_walker_resume.py` |
| `walker` reproduces the original on `fb408bc7…`: **PASS, 34,904 frames, 169 hits of 170 calls (one Z80 bank refusal)**; `camera-sprites` (twenty-four gates) on the tree: **PASS, 107,519 frames, 1,047,974 hits, 6,906 fallbacks** | `history-verify fb408bc75597 --candidate walker`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-walker-fb408bc7-b`, `artifacts/gods/verify-camera-sprites-tree-walker-b` |
| the walker negative control (the re-armed x one off) diverges at frame 2,260 | `--candidate walker-mutant-result` | `artifacts/gods/verify-walker-mutant` |
| **`0091BC` projectile launch**: the plan reproduces every fact of the original on all 40 retained fixtures over four recordings (0-3 pool skips, all four quadrants, both y-sign cases -- the cold start into the walker's own projectile copy, `game/walker.py`); the pool exhausted (`0091DE`) declined, unwitnessed | `factcheck check` on every fixture | `tests/games/gods/test_projectiles.py` |
| `projectile-launch` reproduces the original on `fb408bc7…`: **PASS, 34,904 frames, 50 hits (every witnessed occurrence), 0 fallbacks**; `camera-sprites` (twenty-five gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,048,034 hits, 6,586 fallbacks, tree bit-exact** | `history-verify fb408bc75597 --candidate projectile-launch`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-projectile-launch-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17b` |
| the projectile launch's negative control (the re-armed x one off) diverges at frame 29,278, the tree's first entry | `--candidate projectile-launch-mutant-result` | `artifacts/gods/verify-projectile-launch-mutant` |
| **`0093D2` line walker resume, projectile copy**: a byte-for-byte duplicate of `00FFF0`'s own body at a second ROM address; every fact reproduced on all 147 retained fixtures over four recordings (all four bodies, the yield on the budget, with and without the minor-axis wrap; the projectile copy never completes via a counter) | `factcheck check` on every fixture | `tests/games/gods/test_projectile_resume.py` |
| `projectile-resume` reproduces the original on `fb408bc7…`: **PASS, 34,904 frames, 628 hits of 630 calls (2 exact adapter refusals)**; `camera-sprites` (twenty-six gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,049,180 hits, 6,597 fallbacks, tree bit-exact** | `history-verify fb408bc75597 --candidate projectile-resume`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-projectile-resume-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17c` |
| the projectile resume's negative control (the re-armed x one off) diverges at frame 12,971, the frame after the tree's first entry (12,970) | `--candidate projectile-resume-mutant-result` | `artifacts/gods/verify-projectile-resume-mutant` |
| the walker's own review-gate VBlank-slide check (`scripts/gods/vblank_slide.py --ticks 20`) on a retained gameplay-tick fixture: **DIFFERS** at every placement tried, but only in the global VBlank counter and its own elapsed-field mirror (both off by exactly one, the tool's documented artifact of a large burn shifting which tick boundary the interrupt lands inside) -- every live RAM byte, register and the sound block agree; not a byte the region and the handler share, so `00FFF0`'s own admission (proven through the full ladder) is not reopened | `scripts/gods/vblank_slide.py census-00FFF0/00FFF0-entry-p0.state --ticks 20` | ledger.md 2026-09-17 |
| the suite: `scripts/run_tests.py gods` (common + Gods), about 43 s | 1,798 tests | — |

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
'idle' arm and, since 17 Sep, the 'moving' arm's own call into the
already-recovered walker resume `00FFF0` (`'moving-continue'`/
`'moving-complete'`); `'moving-coldstart'` (a finished walk with at most
one waypoint left, falling into a per-object-type waypoint dispatch
`00FEC0`/`00FF54`) declined, unwitnessed on all eight recordings); the
countdown check (`game/timers.py`: a caller-supplied
control byte and countdown record, 'idle' and 'waiting' recovered; a
residue of zero reloads the countdown and a frequency word
unconditionally, then either the record's own position and a
rate-derived budget straight into the already-recovered projectile
launch `0091BC` (`'trigger-deep-launch'`, recovered 17 Sep;
`'trigger-deep-pool-full'` declined, unwitnessed) or a direction-mirrored
screen window test (`01158C`/`0115D4`'s own shape) and, inside it, a
bounded 20-entry pool scan+fill shaped like
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

Next bites of the walker subsystem, in order, all with `game/walker.py`
as the semantics and `walker_resume_plan` as the boundary model: (1)
DONE, 17 Sep — `00FE08`'s `moving` arm now owns the resume call the way
`0049DA` owns `001164` (`animation.animation_step` extended:
`'moving-continue'`/`'moving-complete'`, the walker's own cost fragments
`_WR_HEAD`/`_WR_STEP`/`_WR_TAIL` reused directly since `00FFF0` *is* this
arm's `bsr` target); the 321 declined `moving` arms on the tree are gone
(00FE08's own fallbacks-by-gate 321 → 118, all exact adapter refusals).
The cold-start path (`00FE5C`–`00FE8C`: the next waypoint from the
solid's table, the budget from the speed byte, `bra 010002` —
`walker.start` then `walker.run`) stays declined as `'moving-coldstart'`:
its own callees `00FEC0`/`00FF54` (a per-object-type waypoint dispatch,
four handlers each, both fully disassembled) were freshly censused this
session over all eight recordings and fired on **none** of them — real
ROM code, unwitnessed, per the grinder-protocol's own rule ("every arm no
recording entered stays declined"), not a mechanism gap.  (2) DONE, 17
Sep — `0091BC` recovered as its own candidate `projectile-launch`: the
pool scan (declined when full, unwitnessed) then the projectile copy's
cold start (`walker.run(walker.start(...), budget, 'projectile')`; the
`move.w #$ffff,d0` versus `moveq` residue difference between the '+x'
and '-x' quadrants modelled directly).  40 fixtures over four recordings
MATCH; `fb408bc75597…`: PASS, 50/50 hits, 0 fallbacks; the tree stays
bit-exact at twenty-five (now twenty-six) gates.  `010332`'s own
`'trigger-deep'` arm is composed too, same day: its own tail
(`0103AA`-`0103C8`, one instruction past `COUNTDOWN_CHECK_LAST_PC`,
identified by a fresh disassembly) -- the record's own position `+0x10`
in x, a budget `(rate>>1)+2`, a full 15-register frame, `D6=1` fixed,
`jsr 0091BC`, full restore -- now calls straight into the already-recovered
launch as `'trigger-deep-launch'`; a fresh full-history census of `010332`
on `f40d7bcc9dda…` (the original census's window had missed it) retained
5 fixtures (8 real occurrences), all MATCH, and the tree's own
`countdown check trigger arm calls unrecovered 0091BC` fallback reason is
gone.  A second caller (`009D16` on
`fb408bc75597…`/`4492103be245…`/`7251bbd0ecf7…`, accounting for the bulk
of the 50+1+1 `0091BC` occurrences on those three) is still not
`010332`'s own code and remains unidentified -- the one open question
left in `docs/gods/blockers/2026-09-16-0091BC.md`.  (3) DONE
(the resume half), 17 Sep — `0093D2` (the projectile copy's own resume,
called by the driver `009210`) recovered as its own candidate
`projectile-resume`: a byte-for-byte duplicate of `00FFF0`'s own body at
a second ROM address, reusing `WALKER_RESUME_ENTRY`'s own cost fragments
directly (`_WR_HEAD`/`_WR_STEP`/`_WR_TAIL`, confirmed identical) with
only the re-arm table and the RTS addresses of its own.  147 fixtures
over four recordings MATCH; `fb408bc75597…`: PASS, 628/630 hits;
the tree stays bit-exact at twenty-six gates.  The driver `009210`
itself was censused fresh over the four recordings that fire projectiles
(32 real path classes on `fb408bc75597…`/`4492103be245…`/
`7251bbd0ecf7…`, `artifacts/gods/evidence/census-009210-<node>`) but not
yet read past its own census; the driver itself only as far as the
walker's contract needs (completion is the driver's: who frees a slot,
who runs the tile test, where `00932C` belongs) remains the next bite.

Screened over the full `fb408bc75597…` history (`recovery_census.py
--classifier entry`, not a direct park -- the 600-frame window's tight
min/max hid real diversity every time) and set aside, all for the same
reason: many more path classes than a bounded leaf has, always tracing
back to a caller-supplied object pointer (or a call into an unrecovered
routine that itself depends on one) -- the object-record convention, not
a grinder's to invent:

| entry | path classes (full history) | why |
|---|---|---|
| `00FE08` | 19 | recovered as `animation-step` (the 'idle' arm and, since 17 Sep, 'moving-continue'/'moving-complete' -- its own call into the already-recovered `00FFF0`; 'moving-coldstart' declined, unwitnessed) |
| `010A14` | 10 | recovered as `collision-gate` (the 'held'/'gated' arms and, since 16 Sep, the 'collision' arm's own 'collision-clear'/'collision-held' sub-arms via `010CBC`, now also recovered; 'collision-deep' and phase>7 declined as unwitnessed) |
| `00BCCE` | 28 (15 real: 13 were the same VBlank-in-interrupt-handler misattribution `00FDB8`'s screening hit) | recovered as `zone-check`: fully witnessed, no declines |
| `00470C` | 30 (re-censused, current tracer) | a genuine per-type dispatch: `move.w d5,d0; add.w d0,d0; add.w d0,d0; movea.l $4718(pc,d0.w),a5; jmp (a5)` into a ROM jump table at `004718` (disassembles as `ori.b` data -- it is a table of handler addresses, not code) with at least a dozen distinct handler bodies; the census's 30 small (6-15 instruction) classes are those handlers' own bodies, not variants of one shape.  Leave for the supervisor: not a leaf, needs an object/kind convention |
| `010332` | 7 | recovered as `countdown-check` (the 'idle'/'waiting' arms, the 'trigger' arm's own 'trigger-reject'/'trigger-spawn' sub-arms via `01158C`/`0115D4`, and, since 17 Sep, 'trigger-deep-launch' via the already-recovered `0091BC`; only 'trigger-deep-pool-full' and 'trigger-pool-full' stay declined, unwitnessed) |
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
leaf), `00052E` (600 calls, 434–9,152 instructions -- likewise).  `00BA8E`
itself, screened the same way (412 calls, 116–268 instructions), is now
recovered (`pickup-check`); a fresh census of `010CD2` (412 calls, 125–277
instructions) proved it is a thin caller-supplied-record composition over
`00BA8E` alone, on every witnessed path -- the original blocker's reading
that it also called the unrecovered `0091BC` was a misattribution (see the
correction below); `010CD2` is now recovered too (`pickup-probe`).
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
was originally read as also calling the unrecovered `0091BC` and a
literal-state branch at `010D7C` (`cmpi.w #$3d,d2`).  `00BA8E` itself is
now recovered (16 Sep, `pickup-check`): the "per-type dispatch" the
earlier note read at `013264`'s own table was resolved the same day
(`docs/gods/blockers/2026-09-16-00BA8E.md` Resolution) -- a record table,
not handlers -- which freed `00BA8E`'s own clean and found arms as an
ordinary composition (the caller-supplied-record rule, not the
object-record convention).  A fresh census of `010CD2` itself (same day)
found that reading was wrong: `010CD2` is a single thin composition --
push the record, add the camera to (d0,d1), call `00BA8E` with the
record's own word, write the result back, and on a negative result store
a sentinel -- on every one of 412 witnessed calls across all recordings;
`0091BC` and `010D7C` belong to a wholly separate adjacent routine
(`010CF8` onward, `010A14`'s own `'trigger-deep'` callee) that `010CD2`
never reaches.  `010CD2` is now recovered too (16 Sep, `pickup-probe`),
composed the way `00BA8E` composes its own callees, one level deeper
(calling `pickup_check_plan` itself with a synthetic register file for
the point `00BA8E` is entered).  `0091BC` remains open, and is a
different, harder shape: a resumable coroutine that stores its own
continuation address back into a live record and dispatches through it,
in two independent ROM copies (`0093D2`/`0093E4`, `0091BC`'s own callee;
`010000`/`010002`, `00FFF0`'s own body -- and `00FFF0`, `00FE08`'s own
declined `'moving'` arm, turned out to be the *same* engine, not a
separate shape) -- escalated together, `NEW_GODS_SUBSYSTEM`
(`docs/gods/blockers/2026-09-16-0091BC.md`).

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
frame-budget refresh, the 'idle' immediate return, and, since 17 Sep, the
'moving' arm's own call into `00FFF0` -- the walker's resume, a resumable
Bresenham-style line walk that stores its own continuation address back
into the live record and dispatches through it, recovered on its own 16
Sep (candidate `walker`) and now owned by this call the way `0049DA` owns
`001164`; the cold-start continuation past a finished walk with at most
one waypoint left, `'moving-coldstart'`, stays declined -- its own
per-object-type waypoint dispatch (`00FEC0`/`00FF54`) is real ROM code no
recording enters), stamps its footprint (`00FDB8`), and draws it
(`00FC8E`, recovered as `solid-draw`: the sprite records for a
width×height grid of 32×16 cells, tile index from the table at `FFF2D6`
by type id; a negative entry means the tiles are uploaded by an inline
VDP block from `FFEA2C`-relative data, unwitnessed and declined).  The
grid `FF885E` is what `0063FA` (the player) and `010CBC` (the movers)
consult.  Next bites in this subsystem: the projectile copy's own launch
(`0091BC`) and driver (`009210`), per the walker subsystem's own next
bites above, then the whole per-tick pass `00FBB6` as a composition of
recovered leaves.

A general note for the next long leaf: a routine whose own activation runs
long enough to span a VBlank shows up as a `scheduler admission` fallback
at that gate on the tree (exact by construction, not a declined arm) --
`001164` and `0049DA` both do this; do not mistake it for a missed arm.

**The line walker** (the first stateful subsystem; `game/walker.py`):
Gods walks straight lines with a Bresenham stepper whose progress lives in
an 18-byte record inside the owner's object — the continuation address
(which of four loop bodies: toward +x or −x, shallow or steep), the
position, the y-step sign, |dx|, |dy|, the error accumulator and the
walk's own step counter.  Each call gets a step budget in `FFF1FE` from
its caller, takes steps until the budget is spent, writes the record back
re-armed and returns; the next call continues from the record.  Two ROM
copies differ in one thing: the **object copy** (`00FFF0` resume /
`010002` cold start; the solids' movement between waypoints, record at
`+6` of the solid's live record, driven by the animation step `00FE08`)
counts the walk down with `dbra` and stops inside the call when the major
axis is exhausted, the counter going negative — the completion `00FE08`
tests to load the next waypoint; the **projectile copy** (`0093D2` /
`0093E4`; the 20-entry pool at `FFE19E`, 22 bytes each, filled by `0091BC`
and driven by `009210`) loops unconditionally, decrements the counter once
per call, and re-arms its "toward −x, steep" body as "toward +x, steep"
(`0094BC` stores `009436`) — a quirk of the ROM, kept.

Semantic-operation card, the object copy's resume (`00FFF0`, candidate
`walker`): *operation* — advance a solid's walk by up to the budget;
*boundary* — entry with A3 at the record and the budget word set by the
caller, exit at the body's RTS with the record re-armed; *persistent
state* — the record (phase, position, sign, spans, error, counter), read
at entry and written at exit, and the budget word (what is left);
*external observations* — none (RAM only); *pending effects* — none;
*permitted interference* — the vertical interrupt anywhere inside (the
handler shares no byte with it; slide check pending on a retained
fixture); *proven movable events* — the interrupt (by the handler's
read/write set, not yet by the slide tool); *ordering boundaries* — the
record must be written before the owner's next resume, which the tick
order guarantees; *timing dependency* — none beyond the budget the caller
computes from the solid's speed; *evidence* — 35 fixtures over four
recordings MATCH (the step arithmetic, the yield on the budget or the
counter, `movem.w`'s sign extension in the residue), consecutive
invocations over 300 real frames continue from the re-armed record, the
mutant (the re-armed x one off) diverges at the next invocation — a
counter one off is not a usable control: it drives the original's own
waypoint code into a write to the cartridge, a fault, which is itself a
fact about the game's tolerance of its records; *remaining
blocker* — none for the resume, and (17 Sep) none for `00FE08`'s own call
into it (`animation-step`, above); the cold start proper (`00FE5C`–`00FE8C`
→ `010002`, reached only when a finished walk has at most one waypoint
left) stays declined -- unwitnessed on all eight recordings, not a missing
mechanism (`walker.start` already models the cold-start arithmetic).

Semantic-operation card, the projectile copy's cold start (`0091BC`,
candidate `projectile-launch`, recovered 17 Sep): *operation* — find a
free pool slot and start a walk toward the tracked position (the player,
biased `+8`/`+6`), taking the caller's own budget of steps immediately;
*boundary* — entry with D0/D1 the walk's own starting position, D4 the
budget, D6 a flag (bit 0 kept), no save/restore frame at all (D0-D7/A3
live scratch, the hazard tick's own shape); exit at `0091F6`'s RTS, the
shared budget word left at what remains; *persistent state* — the found
slot's own 18-byte walker record plus its own two aux words (`+0x12` the
budget again, `+0x14` the flag) and the pool's own free/occupied
convention (the first long negative); *external observations* — none
(RAM only); *pending effects* — none of this call's own (`LAUNCHED_FLAG`
`FFF386` is set unconditionally, read by something later, not traced);
*permitted interference* — the vertical interrupt anywhere inside, not
yet slide-checked; *ordering boundaries* — the slot must be written
before the driver's own next poll; *timing dependency* — none beyond the
budget; *evidence* — 40 fixtures over four recordings MATCH (all four
quadrants, both y-sign cases, 0-3 pool skips; the cold-start setup's own
cost reuses `WALKER_RESUME_ENTRY`'s per-step and re-arm-tail fragments,
confirmed instruction-for-instruction identical), `fb408bc75597…`:
PASS, every one of 50 witnessed calls hits, 0 fallbacks, the mutant
diverges at the tree's first entry (frame 29,278); *remaining blocker* —
none for the launch itself.  Two callers are now identified from the
retained fixtures' own return addresses: on `f40d7bcc9dda…` it is
`010332`'s own `'trigger-deep'` tail, one instruction past the current
`COUNTDOWN_CHECK_LAST_PC` (`0103AA`-`0103C8`: the record's own position
`+0x10` in x, a budget `(rate>>1)+2` from the rate byte, a full
15-register frame, `D6=1` fixed, `jsr 0091BC`, full restore) — composed
into `countdown_check_plan` the same session (`'trigger-deep-launch'`;
every register but D3/D4 is restored afterward, so the composition
needed no register residue threading at all); on
`fb408bc75597…`/`4492103be245…`/`7251bbd0ecf7…` the
return address (`009D16`) is not inside `010332`'s own code at all — a
second, still undisassembled caller remains open.

Semantic-operation card, the projectile copy's resume (`0093D2`,
candidate `projectile-resume`, recovered 17 Sep): identical in every
respect to `00FFF0`'s own card above except the record it steps (a
pooled projectile's, at the slot `0091BC` found rather than a solid's
own `+6`) and the completion signal (the projectile copy never
"completes": `_walk_steps`'s own 'projectile' copy only ever yields
`'continue'` or `'budget'` steps, never `'counter'`, so the caller -- the
driver `009210` -- owns deciding when a walk is done, not this routine).
A byte-for-byte duplicate of `00FFF0`'s own body at a second ROM address
(`0093D2`-`0094D8`), reusing `WALKER_RESUME_ENTRY`'s own cost fragments
directly; *evidence* — 147 fixtures over four recordings MATCH (all four
bodies, the yield on the budget, with and without the minor-axis wrap);
`fb408bc75597…`: PASS, 628 hits of 630 calls (2 exact adapter refusals);
the tree stays bit-exact at twenty-six gates; mutant DIVERGENCE at frame
12,971 (the frame after the tree's first entry, 12,970); *remaining
blocker* — none for the resume itself.  The driver (`009210` →
`0093D2`'s resume) was censused fresh over the four recordings that fire
projectiles (32 real path classes on each of
`fb408bc75597…`/`4492103be245…`/`7251bbd0ecf7…`, `artifacts/gods/evidence/
census-009210-<node>`) but not yet read past its own census; it is the
next bite (who frees a slot, who runs the tile test, where `00932C`
belongs), per grinder-protocol not recovered wholesale without a parent
composition requiring it.

**The pickups** (the subsystem `013264` belongs to): a byte grid at
`FFBBDE` (8×8-pixel cells, 48 per row) holds pickup codes; the pickup
check `00BA8E` scans the player's box (`FFF382`/`FFF384`) against it every
tick after the zone check, and a hit calls the award `013264` with A0 past
the found byte.  Codes 1–27 are item slots in three groups of nine (the
group tables `FFEF8C`/`FFF01E`/`FFF0B0`: an active-id word, then nine
8-byte slots); the active id selects the group's item record through the
ROM table at `012D04` — eleven work-RAM records of 0x50 bytes at `FFF552`,
the table the 16 September blocker misread as handlers — and the record's
word `+8` is the value awarded to `FFF35A` (plus an eighth of
`FFF362 − FFF36C` when positive), with a cue when `FFEF14` is set and the
slot consumed when the record's byte `+0x49` says so.  Codes −1/−2/−3 are
special awards; −4 and below (a third of the witnessed hits) award
`BIG_VALUE` (10,000, unconditionally, the same cascade tail as the
special codes) and continue into `013316` (`grid_inverse_award`: the
grid byte's own address inverted back into a world position, then --
sound off, the only witnessed arm -- a bounded debris burst: up to 8
particles into a shared 80-slot pool at `FF123E`, each a random impact
cue through `014A3C` and a ROM table offset word).  013316 has no
separate call site (013264's own cascade falls straight through), so no
gate of its own: the composition owns it inside `pickup_award_plan`
itself.  `013264`+`013316` are recovered together (`pickups`); the check
`00BA8E` is recovered (`pickup-check`,
`game/pickups.py: pickup_check`): the clean arm (a two-axis box clamp over
`FFF382`/`FFF384` bounding the grid scan, several near/far/bail sub-arms
per axis, an array-append side effect into `FFF1E8`/`FFF1E2` common on
some recordings) and the found arm's own compositions -- found-sound (the
box's own D2 residue negative or zero: an immediate cue), found-bare
(residue positive, the award itself zero: a bare restore-and-return),
found-effect (residue positive, the award nonzero: two draws from the
random table `014A3C` jitter a spawn position on each axis -- including
each axis' own default mask when the halved box size collapses to zero,
and the second draw's own negative branch, both bounded arithmetic once
censused with `--max-classes 400`, not declines -- then `00932C` adds it
to a shared 20-entry effect pool at `FF090E`, the same pool hazard.py's
own `_spawn` fills with `d2=d3=0`, including its own pool-full arm), and
the special-1 pickup's own further step (a shared timer word decremented
by the box's own D2 residue, continuing into the SAME found-sound/bare/
effect tail unless it goes negative).  17 September: a code of -4 or
below (013264's own cascade to `BIG_VALUE`) is composed too, the same way
the direct `013264` gate already owns 013316's debris burst inline.
`014A3C` and `00932C` are recovered on their own (`next-random`,
`effect-pool-add`): both have real callers beyond `00BA8E` (`014A3C`
3,971 times / 34,904 frames from many sites; `00932C` almost entirely
from the hazard tick's own spawn arm, already owned inline there).
Declined within the composition: the special-1 pickup's own further call
when its own timer decrement goes negative (an unrecovered routine at
`011540`), and the message/digit-split tail (`FFEF46` set) -- neither
witnessed by any of the eight recordings, even after the default
32-class-per-node census cap (which had silently discarded rarer real
classes, `--max-classes 400` on `fb408bc75597…` found 400) was raised.
Within 013316's own debris burst (whether reached from `00BA8E` or
`013264` directly): the sound-on arm (a fixed award, no burst), the
rate-limit gate's own abort and its "arm itself" sub-arm, and the
pool-exhausted arm -- none witnessed by any recording.  This subsystem's
own bounded frontier is now exhausted; `00BA8E`'s further callees
(`014A3C`, `00932C`) named in the 15 September blocker are all recovered.

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
then the action dispatch table at `0046D0`, fifteen handlers) is declined
and escalated 16 Sep, `NEW_GODS_SUBSYSTEM`
(`docs/gods/blockers/2026-09-16-00462C-firing.md`): a fresh census showed
it is not one bounded dispatcher family but three nested unrecovered
mechanisms -- a second, independent per-kind message dispatcher inside
`0079DC` (19+ kinds witnessed), a collectible/achievement-slot tracker
(`004790`/`0047DA`, reached from both of the firing tail's two other
unconditional calls `004800`/`00475E`) that on real, witnessed paths
calls `001648`, which writes through what looks like a hardware port or
DMA target rather than plain RAM, and the fifteen-entry action table
itself, whose handlers range from a free `rts` (three of fifteen
entries) to genuinely complex (`00772E`: 10 real path classes in 12
occurrences, not yet disassembled).  The disabled arm (`FFEF38` nonzero,
skipping evaluation entirely) is real ROM code no recording has ever
entered: declined too.

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
