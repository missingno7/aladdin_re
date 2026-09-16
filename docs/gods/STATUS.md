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
  original with eight gates armed, the camera follow step `002806`, the
  sprite emitter `0018C8`, its RAM-only sibling `001164`, the work-table
  reset `004150`, the spawn queue `0049DA`, the grid cell lookup `0063FA`,
  the footprint stamp `00FDB8` and the solid drawer `00FC8E`; `camera`,
  `sprites`, `sprites-static`, `table-reset`, `spawn-queue`, `grid-cell`,
  `footprint` and `solid-draw` arm each alone.

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
| the suite: `scripts/run_tests.py gods` (common + Gods), about 30 s | 566 tests, none skipped | — |

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

Everything else.  Eight routines are recovered: the camera follow step
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
no recording enters).  The
emitter's remaining siblings (`001256`/`001260`/`00126A`, `001312`) share
its descriptor layout and list conventions but are not recovered.  There
is no object-table convention, no semantic map, no native runtime, no
sound-driver knowledge.  The seam for a platform operation inside a
region exists and is shared (`src/genesis_re/seam.py`); Gods has one seam
plan.

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
| `00126A` (`001256`, `001260`) | 412 | 305–307 | from `010248` (the particle drawer's jump table at `0100F2`): the emitter's sibling without the cache — the same seam shape (record composition, inline upload `0012F4`–`001308`, restore); `factcheck facts --park 00126A` does not reach the routine from `boundary-6000.state` within the default step budget.  A full census of `f0ac1973…` alone (15,148 frames) finds **32 retained path classes plus 17 more that overflowed retention** -- far more arms than a bounded leaf; likely the same per-object-type diversity as `00FDB8` below.  Census every recording and look for a bound (a fixed small set of object types, or a size the ROM tables themselves cap) before spending more on this one |
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
| `00FE08` | 19 | calls unrecovered `00FFF0`; arms range 10-165 instructions |
| `010A14` | 10, but several branch points (`(a5+4)>7`, two `(a5+0xA)==0` arms, `(a3+0x12)!=0`) show only one side -- unwitnessed arms dominate | calls `010CBC`, a parameterised twin of `0063FA`'s own grid computation (recoverable once a leaf needs it on its own), then dereferences the computed grid cell (3 checks, 0x80-byte stride) and a second object pointer `a3` |
| `00BCCE` | 28 | — |
| `00470C` | 30 | — |
| `010332` | 7, but every arm with any work calls unrecovered `01158C`/`0115D4` | — |
| `014084` | 32 retained + 25 more overflowed | — |
| `00126A` (`001256`, `001260`) | 32 retained + 17 more overflowed (on `f0ac1973…` alone) | the sprite-emitter-sibling seam shape, but per-object-type like `00FDB8` |
| `00FDB8` | 16 (4 real: 13 were VBlank variants) | recovered — see the solids below |

`010CBC` is worth flagging on its own: it is exactly `0063FA`'s grid
computation with X/Y taken from D0/D1 instead of the fixed words
`FFF18C`/`FFF18E` -- a trivial leaf once some future candidate needs it
as a callee (the `0049DA`-calls-`001164` shape), but not a candidate by
itself (no direct caller was found in the census; it is only reached
through `010A14`).

Screened and set aside earlier, not first candidates: `013362` (600
calls, 3–1,047 instructions -- an interpreter or unbounded loop, not a
leaf), `00052E` (600 calls, 434–9,152 instructions -- likewise), `00BA8E`/
`010CD2` (412 calls each, 116–268 / 125–277 -- wide range, seam-shaped
candidates for later, once the object-record convention exists).
`00FC8E` was screened aside on the same "inherits `00FDB8`'s per-object-type
diversity" worry; it did not hold (see the third correction below) and the
routine is now recovered (`solid-draw`).

Two corrections to that screening, from the supervisor's iteration on
`00FDB8`: (1) a caller-supplied record is not by itself a reason to defer
— the footprint stamp reads its definition through `A2` and its loop
counts are the definition's bytes, and it went through the whole ladder as
a plain leaf (`grinder-protocol.md` §"Candidate selection rules"); what
needs a convention is a dispatch through a type byte into unrecovered
handlers.  (2) Most of the "path classes" above were VBlank landing
positions, which the tracer now sets aside (`00FDB8`: 16 → 4).  Re-screen
`00FE08`, `010A14`, `00BCCE`, `00470C`, `010332`, `014084`, `00126A` with
the current tracer before taking their class counts at face value.  (3)
`00FC8E`'s own worry ("per-object-type diversity" like `00FDB8`'s pre-fix
screening) also did not hold once censused with the current tracer: over
107,519 tree frames the routine only ever takes the positive (tile-table)
arm, in a small number of rows x cells shapes (1-3 rows, 1-3 cells) bounded
by the same definition bytes `00FDB8` reads; the negative (inline VDP
upload) arm is real ROM code but no recording enters it, so it is declined
like any other unwitnessed arm -- not a platform-tail seam that had to be
built.  A routine flagged as "per-object-type diversity" from a raw path-class
count is worth a real census before being set aside a second time.

**The solids** (the subsystem `00FDB8` and `00FC8E` belong to): 25 solid
objects, each a live record at `FF4AAE` (0x18 bytes: world x, y at
`+0`/`+2`, an active flag at `+4` — negative is empty — a frame index at
`+5`, four longs from `+6`) with a definition at `FF65A2` (0x1C bytes: a
type id at `+4`, an index at `+5`, four longs at `+6`, the footprint width
and height at `+0x1A`/`+0x1B`).  Every game tick `00FBB6` replays the undo
list (`00FAF4`, 50 entries at `FF4982`), then for each active solid: steps
its animation (`00FE08`, which calls `00FFF0`), stamps its footprint
(`00FDB8`), and draws it (`00FC8E`, recovered as `solid-draw`: the sprite
records for a width×height grid of 32×16 cells, tile index from the table
at `FFF2D6` by type id; a negative entry means the tiles are uploaded by an
inline VDP block from `FFEA2C`-relative data, unwitnessed and declined).
The grid `FF885E` is what `0063FA` (the player) and `010CBC` (the movers)
consult.  Next bites in this subsystem: `00FE08`/`00FFF0` (the animation
step, census both), then the whole per-tick pass `00FBB6` as a composition
of recovered leaves.

A general note for the next long leaf: a routine whose own activation runs
long enough to span a VBlank shows up as a `scheduler admission` fallback
at that gate on the tree (exact by construction, not a declined arm) --
`001164` and `0049DA` both do this; do not mistake it for a missed arm.

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
