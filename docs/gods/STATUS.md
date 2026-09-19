# Gods (USA): status

Current state only.  The per-region record is `ledger.md`; the iteration
recipe is `grinder-protocol.md`; the worker prompt is `grinder-goal.md`.
Last updated 19 September 2026.

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

The tick's phases, with what each costs and what is recovered inside,
are mapped in `tick-map.md`: the mass of a tick is the player state
machine (`005700`, 29 states), the creature update (`00A772`, 8 kinds) and
the world update (`0030CC`), the next three subsystems.

`005700`'s own shared tail (`0075D6`) is recovered as a platform-tail
seam (17 Sep); its own tile-trigger-scan found-tile arm is composed at
last (18 Sep): a raised kind-3 event (`00462C`, the trigger evaluator)
resolves on its non-firing arm through the already-recovered
`evaluator_plan`'s own machinery (`_evaluator_resolve`, shared by both
callers), and the scan continues after each admitted raise, up to six
per activation; every other kind and the evaluator's own firing arm still
decline by name.  Its own state handlers reach a hit-list search (`008222`,
recovered 18 Sep as `contact-search`) or its own per-object-type
consumers (`012DA0`/`012E5A`, recovered the same day as
`contact-consume-primary`/`contact-consume-secondary` -- the
supervisor's Decision on `docs/gods/blockers/2026-09-17-008222.md`
named its own data, `pickups.ITEM_RECORDS`, for both) on a real,
frequently-witnessed fraction of activations.  The first two
movement-cluster states are composed over these recovered pieces the
same day: state 24 (`006AD8`) and state 25 (`006B14`), a 3-tick shape
that calls the consumer once and transitions to state 14 -- fully
witnessed, no declines.  `00722C`, the 200-entry box-overlap scan
states 0 and 1 both call, is recovered too (`game.movement.
box_overlap_scan`) -- but its own result is discarded at both call
sites (no conditional branch reads it), so, like `tile_trigger_scan`
before `0075D6` existed, it is not yet its own gate: it waits to be
composed.  State 1 (`007282`) is recovered (18 Sep): a ~130-instruction
decision tree over the grid cell, the contact search and a shared
movement cascade, ending at `0075D6` (or, on a contact-search-found
result, a deterministic hand-off into state 5's own dispatch read,
`0074A8`-`0074B4`) -- every arm the main history witnesses, including a
STATE_COUNTER already above 7 reaching the cascade's own reset; only the
box-overlap scan (`0072D8`) declines, unrecovered.  State 0 (`006FFE`) is
recovered too (18 Sep): NOT a byte-identical copy of state 1 -- real
differences the tracer found, not assumed by symmetry (arm A compares
EA20 to the literal 1, not its sign; the bit-0 sub-arm's own
EA20-positive case reaches a three-way grid-byte dispatch state 1 has no
analogue of; the cascade decrements POSITION_X against different grid
offsets and a different low-bits threshold; the shared sub-body is its
own physical copy whose negative-EA1E arm sign-extends d7 to the full
register) -- `game/player.py`'s own module note above `state0_step`
transcribes them.  State 14 (`006DA6`) is recovered too (18 Sep): a
vertical-movement dispatcher over the same recovered pieces, its own
settle tail composed with two real forks the original survey missed
(`FFFFF1AE != 0` on entry, and `FFFFEA20 != 0` handing back to the SAME
EA20 dispatch this plan already owns) -- no arm declines by name any
more.  Four real bugs the milestone tree caught outside the single-history
census (never guessed): arm B's own `+0x17F` nibble sub-test, wrongly
declined as unwitnessed, actually mirrors arm A's `+0x181` test exactly;
`FFFFF1A4`'s own unconditional clear was missing from three of arm A's
downstream stores; arm B's own retry counter is never re-cleared past its
budget (unlike arm A's mirror) and three of its stores wrongly hardcoded
zero; and a D0 clobber (`move.w f18e,d0`) was missed on both arms' own
nibble-tested exit.  State 5's own table-dispatch entry (`00746A`, which
falls back into state 1's own body on one arm -- "one region, two gates,
one planner") is the next bite.

**Superseded later the same day**: every witnessed state (including 5)
now has its own gated candidate (the coordinator's own frequency-order
list closed in full, `ledger.md`'s 18 September entries), and the family
itself is composed over them: `player_state_plan` (candidate
`'player-state'`) owns `005700`'s own dispatch head directly, replacing
the 25 individual player-state gates inside `camera-sprites` with one.
Building it surfaced a genuine gap the misnomer above had hidden: real
STATE_TABLE index 26 (ROM `005724`, not `0069AC`, which is index 20) has
never been recovered as its own leaf -- the seventh most frequent state
and now the clear next bite (`005700`'s own semantic-operation card,
below, has the count and the milestone tree numbers).

## What runs today

- **The original**, cold from power-on, on every recorded history.
- **The candidate `camera-sprites`** (`src/gods_sega/recovery.py`): the
  original with sixty-four gates armed -- the native machine's own capacity
  limit (`native/machine.cpp`, PortForge, pinned); state 18 (below) is fully
  recovered but stays a standalone candidate rather than a sixty-fifth gate,
  per Aladdin's own precedent for exhausted native capacity
  (`docs/archive/aladdin/recovery-cost-log.md`) -- the camera follow step `002806`, the
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
  resume `00FFF0`, the projectile launch `0091BC`, the line walker's
  projectile resume `0093D2`, the message display gate `007986`, the
  string copy `0079DC`, the achievement slot reset `0047DA` (a seam over
  the collected-item icon upload `001648`), the achievement slot dispatch
  `004790` (a seam over `0047DA`'s own seam), the slot scan `00475E` (up to
  three calls into `004790`, one of them possibly its own seam), the record
  id scan `004800` (up to three calls into a freshly-disassembled `0048B4`,
  achievement_slot_dispatch's own id-compare tail reached by a tail jump
  straight into `0047DA`), and two of the trigger evaluator's own
  action-table handlers, the elapsed-seconds reset `0048E4` and the pickup
  group clear `004ACA` (both reached by the evaluator's own firing tail
  through a tail jump, `0046CE`, needing no seam of their own), and the
  player state machine's own shared tail `0075D6` (a platform-tail seam
  over a second inline upload, `001312`, with no suffix beyond its own
  `rts`: the tile trigger scan's clean arm, the follow-point step, the
  state-table re-index), the movement-cluster contact search `008222`
  (with its own helper `00837E`), its own two consumers `012DA0`
  (with `012E32`) and `012E5A` (with `012EE6`), the family over the item
  type `pickups.ITEM_RECORDS` names, and the first two movement-cluster
  states composed over that family, `006AD8` (state 24) and `006B14`
  (state 25); `camera`,
  `sprites`, `sprites-static`, `conditions`, `pickups`,
  `table-reset`, `spawn-queue`, `grid-cell`, `footprint`, `solid-draw`,
  `animation-step`, `countdown-check`, `collision-gate`, `zone-check`,
  `particle-emit`, `hazard-tick`, `score-convert`, `evaluator`,
  `proximity`, `next-random`, `effect-pool-add`, `pickup-check`,
  `pickup-probe`, `walker`, `projectile-launch`, `projectile-resume`,
  `message-gate`, `string-copy`, `achievement-slot-reset`,
  `achievement-slot-dispatch`, `slot-scan`, `record-id-scan`,
  `action-reset-elapsed`, `action-clear-group`, `player-tail`,
  `contact-search`, `contact-consume-primary`,
  `contact-consume-secondary`, `trail-check` and `player-state` arm each
  alone.  **18 September, later the same day**: the 25 individual
  player-state gates this candidate used to arm (`state-24`, `state-25`,
  `state-1`, `state-0`, `state-14`, `state-5`, `state-6`, `state-9`,
  `state-26`, `state-8`, `state-13`, `state-12`, `state-16`, `state-11`,
  `state-2`, `state-3`, `state-4`, `state-17`, `state-21`, `state-28`,
  `state-22`, `state-27`, `state-23`, `state-10`, `state-19`) are
  retired from `camera-sprites`' own gate set: `player_state_plan`
  (`player-state`, above) now owns the jump into each of their own
  planners directly, so their own hits are replaced by this one
  dispatcher's.  Their own standalone candidates (same names), gates and
  tests are untouched -- only `camera-sprites`' own composite no longer
  arms them itself.  `camera-sprites` is now forty gates, down from
  sixty-four.  The player state machine's own shared box-overlap-scan copy
  (`0058D2`, consuming what states 0/1's own `00722C` twin discards), the
  achievement highlight cycle (`005CEE`, a seam over a seam like
  `achievement-slot-dispatch`'s own shape over `0047DA`) and the floating
  icon spawn (`010D7C`) are owned by `state-19` and by the standalone
  `state-18` (below), not separate candidates of their own.
- **The candidate `state-18`** (`src/gods_sega/recovery.py`): a single gate
  at `005834`, fully recovered and verified through the whole ladder but
  kept out of `camera-sprites` (above) for native gate capacity.
- **The candidate `creature-attack`** (`src/gods_sega/recovery.py`): a
  single gate at `009D6C`, the creature update's own attack timer (18
  Sep) -- called once per active creature per frame from `00A772`.  A
  full-tree census (273 retained fixtures across all five recordings)
  found no seam at all (every native/device boundary this leaf touches is
  itself already-recovered pure 68000 code) and four real dispatch
  families past the two early 'skip' exits and 'waiting': aim quadrant 1
  jitters the tracked position with two draws from the shared random table
  (`game/effects.py: next_random`) and launches through the projectile
  pool's own body entered directly at `0091C8` (`game/projectiles.py:
  launch_toward`, a new public split of `launch`'s own head so both
  `0091BC` and `0091C8` share one planner); quadrants 2-3 launch at the
  tracked position with no jitter, through `0091BC` (`launch`) itself;
  quadrant 0 never launches -- it hands the already-recovered
  `timers._spawn` BACK/FORWARD hazard-pool fill a locally-derived
  frequency through a tail-JUMP (not a call), so `01158C`/`0115D4`'s own
  inner `rts` returns straight past `009D6C` to `00A772` (the same shape
  `countdown_check_plan` already prices, reused here).  Kept out of
  `camera-sprites` for the same native gate cap `state-18` is.  Every
  register this leaf itself sets is dead on return (`00A772`'s own very
  next instruction clobbers D0 unconditionally, and the kind-handler jsr
  between there and its own next read clobbers D1-D5), so its mutant is
  `_mutate_result` (one write byte off by one), not a register mutant --
  confirmed observationally, not assumed.  Milestone tree PASS (18 Sep,
  `artifacts/gods/verify-creature-attack-2026-09-18`): 20,865 hits, 24
  fallbacks, all `ADAPTER_REFUSALS` (`machine admission` 1, `vblank in
  span` 1, `z80 bank guard` 21, `observation deadline` 1); mutant
  DIVERGENCE confirmed on the longest recording (frame 12,922).  `00A772`
  (the per-creature family calling `009D6C` then a kind table) and `00A578`
  (the 9-slot creature-list walk) are NOT recovered -- see the Resolution
  in `docs/gods/blockers/2026-09-18-00A578.md` for the shape and sub-parts
  found while scoping them (six new unrecovered helpers `00A578`'s own
  spawn-init loop and `00A772`'s own tail call into, past `009D6C` and the
  kind table).
- **The candidate `creature-frame-offset`** (`src/gods_sega/recovery.py`):
  a single gate at `00AA50`, one of `00A772`'s own three unconditional
  callees (18 Sep, `docs/gods/blockers/2026-09-18-00A578.md`'s own
  Progress) -- the creature's own per-kind, per-frame animation offset,
  reached both from `00A772`'s own `$f38a.w` "moving" arm and from inside
  the still-unrecovered ground/fall kind handlers.  Twelve instructions,
  RAM/ROM-read only, no store, ONE unconditional path (no branch at all)
  on every one of 19,798 occurrences across the four recordings that
  reach it.  Milestone tree PASS on those four (18 Sep,
  `artifacts/gods/verify-creature-frame-offset-2026-09-18`, bit-exact);
  the fifth recording never reaches it at all, honestly `NOT_EXERCISED`.
  Mutant `creature-frame-offset-mutant-result` (D2 off by one) faults the
  M68000 with an address error a few calls into the still-unrecovered
  chain its own result feeds -- the same "real consequence of the
  corruption" class states 22/23's own mutants hit, not a control
  failure.  `00A922` and `00B944` (the remaining two of `00A772`'s own
  unconditional callees) are the next bites.
- **The candidate `state-26`** (`src/gods_sega/recovery.py`): a single
  gate at `005724`, real STATE_TABLE index 26 -- the tree's largest single
  decline before its own recovery (1,975 of 8,857 fallbacks), folded into
  `_PLAYER_STATE_PLANNERS` so `player_state_plan` composes it directly
  (its own hits are counted under `camera-sprites`, which dropped from
  8,857 to 6,970 fallbacks); kept as its own standalone candidate too, the
  same shape every other individual player state is.  See `ledger.md`'s
  own 18 September entry for the four top-level arms and their counts.
  The pre-existing candidate named `'state-26'` (`0069AC`, real index 20)
  is renamed `'state-20'`; the gate PC and every fixture/test are
  unchanged.
- **The candidate `creature-pickup-check`** (`src/gods_sega/recovery.py`):
  a single gate at `00B944`, the second of `00A772`'s own three
  unconditional callees (18 Sep, `docs/gods/blockers/2026-09-18-00A578.md`'s
  own ordering) -- a probe into the already-recovered pickup check
  (`00BA8E`), the same shape `pickup_probe_plan` already proves over
  `010CD2` but with no camera add and one extra unconditional seed write
  (`zones.HALF_WIDTH`/`HALF_HEIGHT = 0x20`) before the call, composed via
  a new `_ConstMachine` RAM-overlay helper (boundary.py, Gods-local) since
  this region's own head write feeds a callee's own read two levels down.
  Milestone tree PASS (`artifacts/gods/verify-creature-pickup-check-leaves-2026-09-18`,
  standalone gate): 107,519 frames, 20,811 hits, 78 fallbacks (all
  `ADAPTER_REFUSALS` but one already-known pickup_check decline).
- **The candidate `event-consume`** (`src/gods_sega/recovery.py`): a single
  gate at `00A922`, the last of `00A772`'s own three unconditional callees
  (18 Sep, `docs/gods/blockers/2026-09-18-00A578.md`'s own ordering) -- the
  creature's own world-event consume.  Two bounded loops: the first walks
  the event list (`EVENT_LIST`, stride 6, up to 20 entries) for a slot
  whose own kind passes the type's own `QUADRANT_WORD` mask, isn't
  `EVENT_KIND_EXCLUDED`, and whose own (x, y) falls in the creature's own
  box; the second, on a match, walks `game.movement.BOX_SCAN_TABLE`
  backwards for an active object of the SAME (x, y, kind), and on a match
  stores the event into the instance and marks both slots consumed.  See
  `ledger.md`'s own 18 September entry for the arm breakdown and the four
  real defects this session's own FAST tier and `--perturb-upper-halves`
  caught in turn (two wrong box-margin constants copied from state-26's
  own box scan, a missing shared-`dbra` cost on loop 2's own continuing
  arms, a missing `lsr.w d3,d2` cost, a missing final `rts` cost, and two
  registers' own upper halves not carried from entry).  Milestone tree
  PASS on four of the five leaves (`artifacts/gods/verify-event-consume-leaves-2026-09-18`,
  standalone gate): 107,519 frames total, 19,779 hits, 19 fallbacks (all
  `ADAPTER_REFUSALS`); the fifth recording (`ca2b703b6fd5`) never reaches
  `00A922` at all, honestly `NOT_EXERCISED` (0 retained fixtures in its
  own census, matching).
- **The candidate `creature-grid-cell`** (`src/gods_sega/recovery.py`): a
  single gate at `00AA38`, the first of the six further callees the six
  witnessed kind handlers need (19 Sep,
  `docs/gods/blockers/2026-09-18-00A578.md`'s own Decision).  Byte-for-byte
  `game.grid.grid_cell_at`'s own arithmetic (0063FA/010CBC's shared shape),
  a third call site over the creature instance's own POSITION_X/POSITION_Y
  instead of the fixed words or a caller's D0/D1 -- confirmed identical,
  not merely similar.  One unconditional path, no branch, no store, no
  seam.  Milestone tree PASS on four of the five leaves
  (`artifacts/gods/verify-creature-grid-cell-leaves-2026-09-18`, standalone
  gate): 107,519 frames total, 1,283 hits, 0 fallbacks; `ca2b703b6fd5`
  honestly `NOT_EXERCISED`, matching every other creature-family leaf.
- **The candidate `ground-edge-test`** (`src/gods_sega/recovery.py`): a
  single gate at `00AD68`, the second of the six further callees.  A
  two-cell test over the grid table's own bytes at the address
  `creature-grid-cell` leaves in A1, gated by the creature's own
  POSITION_X low 5 bits; only the two non-matching arms (D1=0) are
  witnessed -- the two arms where the flag actually matches (D1=1) are
  real ROM, declined.  `--perturb-upper-halves` caught a real defect (the
  routine's own `moveq #0,d1` clears the whole 32-bit register, not the
  low word the plan first assumed).  Milestone tree PASS on four of the
  five leaves (`artifacts/gods/verify-ground-edge-test-leaves-2026-09-18`,
  standalone gate): 107,519 frames total, 394 hits, 0 fallbacks;
  `ca2b703b6fd5` honestly `NOT_EXERCISED`.  Since the evening of 18
  September every recovered creature-update piece (`009D6C`, `00AA50`,
  `00AA38`, `00AD68`, `00A922`, `00B944`) is armed in `camera-sprites` as a
  leaf (forty-six gates of the adapter's sixty-four; the `00A772` family
  composition will fold them, as `005700`'s did the states).
- **19 September**: the four remaining kind handlers of the six the
  Decision named are recovered -- the ground-contact pair `00ACA0`/`00AD88`
  (kinds 4/5, `candidate`s `'creature-ground-contact'`/`'creature-ground-
  contact-mirror'`) composed over `creature_grid_cell` and `ground_edge_test`
  (both entry points -- 00AD46's own (d16,An) variant and 00AD68 itself),
  ending at a hand-off to `kind_frame_offset`'s own separately-armed gate;
  and the fall pair `00AE6C`/`00AED4` (kinds 2/3, `candidate`s
  `'creature-fall-kind'`/`'creature-fall-kind-mirror'`) composed over
  `kind_frame_offset` (inline, a real bsr/rts) and `creature_grid_cell`.
  Every recovered piece is armed in `camera-sprites` (fifty gates of the
  adapter's sixty-four).  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19a`, 107,519
  frames): 1,161,016 hits, 7,109 fallbacks, 40.07M instructions replaced.
  `00AF3C` (needed by both `00AA76` and `00AB50`) is recovered too, the
  same session (`'creature-grid-cell-d0d1'`): a FOURTH call site of the
  shared grid arithmetic 0063FA/010CBC/00AA38 all run, X/Y from the
  caller's own D0/D1, pure, no RAM read, extremely hot (22,932
  occurrences); `camera-sprites` extended to fifty-one gates.  `00AF52`
  itself (00AA76's own second call, after 00AF3C) does not close the same
  session: escalated `NEW_GODS_SUBSYSTEM`
  (`docs/gods/blockers/2026-09-18-00A578.md`'s own 19 September
  Progress/Decision) after disassembly alone showed three further
  unexamined calls (`00B02A`, `00B082`, `00B002`) behind what looked like
  a bounded leaf.  The supervisor's own Decision on `00AF52` (same day,
  evening) read the ROM directly and found none of the three is a new
  subsystem: `00B082`'s own "indirect jsr through a computed table" is
  `jsr $14a3c.l` -- a direct call into the already-recovered next-random
  draw -- and its "large record write" is a `movem.w $4102.l` fill of a
  400-byte RAM block from thirteen ROM constants; `00B02A` is a 32-slot
  pool scan (`0091BC`'s own shape); `00B002` is three further calls to
  census.  Every piece named a shape; the order to proceed: `00B082`,
  `00B02A`, `00B724`/`00B7DA`/`00B6AE` then `00B002`, `00AF52` over them,
  `00AC36`, `00AA76`/`00AB50`, `00B8C2` then `00B920`, `00A772` as the
  family, `00A578` as the walk.

- **19 September, grinder session following the Decision on `00AF52`**:
  `00B082` (`'aim-cue-update'`) is recovered first, in the Decision's own
  order.  A full-tree census (`--entry 0x00B082`, all five recordings, 41
  retained fixtures) showed the routine is considerably richer than the
  Decision's own "fill + recovered call" first read: past the fill and an
  unwitnessed `AIM_CUE_SKIP_FLAG` shortcut (real ROM, declined), a random
  draw against the type's own threshold byte picks the LOW or HIGH nibble
  of the type's own index byte to dispatch one of four table entries, of
  which three are witnessed -- index 0 (`00B2EC`, `'window-mark'`):
  unconditional, branch-free, three bytes set in a camera-relative
  sub-table; index 1 (`00B0FE`, `'quadrant-mark'`): a fully deterministic
  32-call sweep over the shared "mark" leaf `00B1AC` (two mirrored 8-step
  passes, each run twice -- immediate values only, no data dependence in
  the trip count); index 2 (`00B15C`, `'event-scan'`): walks the SAME
  `EVENT_LIST`/`EVENT_COUNT` `event_consume` already reads, marking every
  entry, and on `EVENT_COUNT == 0` retries once with the OTHER nibble
  (real ROM: a second `exg`/redispatch, `00B0E0`).  Index 3 (`00B1E8`)
  and the shared mark leaf's own miss arm (out of its table's own
  `[BASE, BASE+0x17C)` window) are real ROM, never witnessed by any of
  the five recordings: declined, as is a retry landing on index 2 (self)
  or 3.  Every cost fragment (the fill, the dispatch head's two nibble
  variants, each arm's own body, the shared mark leaf, the retry
  overhead) was verified against independent fixtures until the
  assembled totals matched the tracer to the cycle before any register
  work began; getting the exit register file and RAM residue exact took
  several real corrections along the way -- the outer `movem.l
  a3-a5,-(a7)` frame's own stack residue is overwritten a second (and,
  for the event-scan and quadrant arms, a third) time by the routine's
  own internal calls (`014A3C`'s own frame, the window arm's own scratch
  `move.l a3,-(a7)`, the event scan's own `movem.l d7/a0,-(a7)` and every
  `bsr $b1ac`'s own return-address push, all landing in the SAME 12 bytes
  in sequence); `MOVEQ`-loaded registers (the quadrant loop's own D0/D1)
  keep a `0xFFFF` upper half no later word op ever clears; the
  event-scan's own saved D7/A0 are restored from the stack at the tail,
  not left at the loop's own scratch values.  `factcheck check` (41
  fixtures: 37 MATCH, 4 correctly DECLINE the mark leaf's own miss arm)
  and `--perturb-upper-halves` both clean.  `camera-sprites` (fifty-two
  gates) milestone tree PASS; `aim-cue-update` reproduces the original on
  `f0ac19738f19…`: PASS, 15,148 frames, 39 hits, 0 fallbacks, bit-exact;
  mutant `aim-cue-update-mutant-result` DIVERGENCE at frame 10,658.
  `00B02A`/`00B05A` (`'aim-pool-reset'`/`'aim-pool-add'`) are recovered
  next, the same session: one 256-byte, 32-slot work-RAM pool at
  `FFFF40B2`-`FFFF41B2`, two entries -- `00B02A` an unconditional,
  branch-free reset from the SAME ROM constants `00B082`'s own fill reads
  (a different tiling, dropping A5); `00B05A` the ADD, the SAME
  "scan a fixed-stride table for a free long-tested slot, write four
  words, bump a counter" shape `hazard.effect_pool_add`/`timers._spawn`
  already prove -- every witnessed occurrence (all five recordings) finds
  a free slot within the first four positions; the counter-gate and a
  fully exhausted scan are real ROM, never witnessed, declined.
  `camera-sprites` (fifty-four gates) milestone tree PASS on all five
  leaves (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19e`,
  107,519 frames); both candidates reproduce the original on
  `f0ac19738f19…`: PASS, 39 hits each, 0 fallbacks, bit-exact; both
  mutants DIVERGENCE.  `00B32E` (`'aim-window-address'`) is recovered
  next, the same session: the SAME camera-relative scaling `00B082`'s own
  window-mark arm uses, called (with `00AF3C`) from every one of
  `00AF52`'s own further creature-targeting callees -- a pure address
  computation, no store, one path, 12,737 occurrences across the tree.
  `camera-sprites` (fifty-five gates) milestone tree PASS; the candidate
  reproduces the original on `f0ac19738f19…`: PASS, bit-exact; mutant (a
  register control, A0 off by one -- the leaf stores nothing of its own)
  DIVERGENCE.  Full-tree census of the three remaining Decision items
  (`00B724`, `00B7DA`, `00B6AE`, 871 occurrences each) found all three
  bounded, calling ONLY `{00AF3C, 00B32E}` (`00B724`/`00B7DA`) or
  `{00AF3C, 00B32E, 00B05A}` (`00B6AE`) on every witnessed occurrence
  (max 223-300 instructions, one exit PC each) -- tractable.  `00B002`
  ITSELF is not: past its own three calls it tail-jumps (`bra.w`) to
  `00B588`, unexamined by the Decision's own reconnaissance, which calls
  `00B354` (a second function sharing `00B32E`'s own ROM range, past
  its own `rts`) and `00B62A` (wholly new) -- a real scope gap, not yet
  censused.  Next: `00B724`, `00B7DA`, `00B6AE` (each its own leaf over
  `{00AF3C, 00B32E}`/`{..., 00B05A}`), then `00B588`'s own reconnaissance
  before `00B002` can be composed.

- **19 September, grinder session following the three-region reconnaissance
  above**: all three are recovered.  `00B724` (`'aim-target-scan'`): a
  horizontal raycast up to the type's own step limit, marking each visited
  column in the SAME window table `aim_cue_update`'s own window-mark arm
  writes into and appending into a second, per-call-restarted 32-slot pool
  (`AIM_SEARCH_POOL_LOW`, immediately below `AIM_POOL`); 127 retained
  fixtures, 120 MATCH, 7 correctly declined (`'blocked-start'`/
  `'pruned-start'`, real ROM never witnessed).  `00B7DA` (`'aim-target-
  scan-backward'`): 00B724's own mirror, stepping left -- but NOT a
  byte-identical copy, two real differences the tracer found: the first
  probe is a bare advance with no store (a call alone can produce zero
  stores), and there is no step-count limit at all; 149 retained fixtures,
  140 MATCH, 9 declined.  `00B6AE` (`'aim-target-resolve'`): a two-slot
  outer loop consuming the 'exhausted' snapshots `00B724`/`00B7DA` leave
  (`AIM_SEARCH_SNAPSHOT`/`AIM_SEARCH_BACKWARD_SNAPSHOT`), each slot an
  independent VERTICAL scan (opposite header polarity from the other two:
  here header==1 STOPS the scan to evaluate, there it continues), reusing
  the already-recovered `aim_pool_add` (00B05A) verbatim for its own store
  arm; the second slot's own reads had to see the first slot's own writes
  (a real cross-slot RAM dependency), composed via the same `_ConstMachine`
  overlay `creature_pickup_check_plan` already established -- 93 retained
  fixtures, all 93 MATCH.  `camera-sprites` extended to fifty-eight gates.
  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19h`, 107,519
  frames, bit-exact).  See `ledger.md`'s own three 19 September entries for
  the full arm breakdowns, cost tables and the real defects each session's
  own FAST tier and `--perturb-upper-halves` caught (a duplicate-named cost
  constant, missing D2/X-flag threading, MOVEM's own sign-extension on
  load, the cross-slot RAM dependency).

- **19 September, later the same session**: `00B588` itself, disassembled
  fresh (`00B588`-`00B724`, `00B354`-`00B588`), is a real subsystem, not a
  thin tail: it walks every entry currently in `AIM_POOL` and for each runs
  FOUR directional ray-march passes (`00B354`/`00B440`, each its own bounded
  loop over an eleven-entry ROM table at `00AE4C`, calling `00B524` and the
  SAME bounding-box-plus-window-mark shape `00B62A`/`00B6AE` already prove),
  each followed by `00B62A` itself (a tractable, loop-free evaluator on its
  own terms -- 70 retained fixtures scoped it -- but semantically entangled
  with `00B354`/`00B440`'s own `F2D4`/`F2D2` context, so not recovered
  ahead of them).  Escalated `NEW_GODS_SUBSYSTEM`
  (`docs/gods/blockers/2026-09-18-00A578.md`'s own 19 September addendum);
  `00B002` itself is otherwise fully scoped (two `bsr`s with a register
  pass-through and three `clr`s resetting both scan slots) and composes
  cleanly once `00B588` is recovered.  `00AF52`, `00AC36`, `00AA76`/
  `00AB50`, `00A772` and `00A578` all remain blocked behind `00B588`.

  Independent of that whole chain, `00A578`'s own spawn-init body's own
  unconditional callees `00B8C2` (`'spawn-table-find-free'`) and `00B920`
  (`'spawn-table-add'`) are recovered: a bounded 10-slot table scan
  (`SPAWN_TABLE_LOW`, `FFFF0EF0`) returning its own result via the CCR alone
  (an `rtr` popping a literal pushed value -- not a new mechanism), composed
  by the ADD into a real internal call.  `camera-sprites` extended to sixty
  gates.  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19i`, 107,519
  frames, bit-exact).  See `ledger.md`'s own entry for the arm breakdown and
  the three real defects this session's own FAST tier and
  `--perturb-upper-halves` caught (RTR's own wholesale CCR load, the
  `clr.w -(a7)` stack write RTR itself pops, MOVEQ's own upper-half clear).

  With every admissible candidate in the Decision's own list now either
  recovered or blocked behind the `00B588` escalation, this session's own
  frontier is exhausted: the next work is the `00B588` reconnaissance's own
  next question (what the eleven `00AE4C` table entries encode) or a fresh
  bite chosen from elsewhere in the tick (the player state machine and the
  world update, `0030CC`, remain the two other tick phases whose own mass
  is still mostly original execution -- `tick-map.md`).

- **19 September, grinder session following the Decision on `00B588`**: the
  first two of the Decision's own piecewise order are recovered.  `00B524`
  (`'aim-probe-mark'`): a found-only probe over one ray-march step
  (`00B354`/`00B440` call it at specific steps, not yet recovered
  themselves) -- the SAME step-limit test, camera-relative box test and
  window-mark tile read as `00B6AE`'s own inner loop (`_resolve_slot`), D7
  derived from a caller-supplied local step accumulator (D4) instead of an
  incrementing counter; every arm real and witnessed (45 fixtures over
  four recordings, the fifth honestly `NOT_EXERCISED`), no declines.
  `00B62A` (`'aim-probe-mark-store'`): the STORE-capable evaluator `00B588`
  calls directly after each ray pass, D7 derived from `AIM_RAY_STEP_INDEX`
  (F2D4, written by the ray march's own tail) instead of D4, a real dedup
  guard against A5 (the creature's own tracked position, per the
  escalation -- this session's own recovery does not confirm which caller
  sets it either) before the store arm, composing the already-recovered
  `aim_pool_add` (00B05A) verbatim; only `'pruned'` (tile > 0, D7 >= tile)
  and the box/step-limit misses decline nothing (real, witnessed misses
  with no update at all) -- 70 fixtures over four recordings, no declines.
  Both share one found-tail (`_aim_found_update`) and one box test
  (`_aim_probe_bound`), factored fresh in `game/creatures.py` without
  touching `_resolve_slot`'s own already-sealed code.  `factcheck check`
  and `--perturb-upper-halves` both clean on all 115 fixtures combined
  after fixing real defects this session found in turn: 00B524's own
  initial `movem.l d2-d3,-(a7)` frame's own stack write (real even though
  the net register change is zero) was missing from the plan entirely; X
  is never retained from the entry SR on either routine -- it is set fresh
  by the initial `add.w 4(a3),d7` (the step-limit exit), by the box test's
  own second `sub.w f3f0,d3` (every bound-\* exit, regardless of which of
  the four sequential compares actually fails, since both subs always run
  first), or by `00B32E`'s own internal `add.w d3,d2` tail (every arm past
  the box test) -- never by the asr before it, always overwritten before
  any exit can read it; and `00B62A`'s own D2/D3 exit values are `00B32E`'s
  own internal scratch RESIDUE (the SAME final offset
  `_res_window_d2`/`aim_target_resolve_plan` already name), not the
  caller's own dx/dy, on every arm that reaches the call -- `00B62A` saves
  neither register around its own `bsr $b32e`, unlike `00B524`'s movem
  frame.  `camera-sprites` extended to sixty-two gates.  Milestone tree
  PASS on all five leaves (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19j`,
  107,519 frames): 1,211,876 hits, 8,192 fallbacks, no decline at either
  new gate.  Both reproduce the original on `f0ac19738f19…`: `aim-probe-mark`
  PASS, 939 hits, 9 fallbacks (all `ADAPTER_REFUSALS`); `aim-probe-mark-store`
  PASS, 489 hits, 3 fallbacks (all `ADAPTER_REFUSALS`); both mutants
  (`_mutate_aim_probe`, shared: `AIM_SEARCH_BEST_INDEX`'s own low byte on a
  `'found'` occurrence, else `AIM_POOL_COUNT`'s own low byte on a `'store'`
  occurrence, else unmutated) DIVERGENCE (frame 13,973 and 12,314).  Next,
  per the Decision's own order: `00B354`/`00B440` as one parameterised
  ray-march implementation if they mirror (a real census first -- neither
  has been censused yet, only disassembled), then `00B588` composing them
  over every `AIM_POOL` entry, then `00B002`, `00AF52`, `00AC36`,
  `00AA76`/`00AB50`, `00A772` as the family, `00A578` as the walk.

- **19 September, grinder session continuing the Decision's own order**:
  `00B354`/`00B440` (candidates `'aim-ray-march-forward'`/
  `'aim-ray-march-backward'`) are recovered -- a real directional ray-march
  loop over the eight-entry `00AE4C` table (the upward arc the Decision
  itself read), `00B588`'s own outer loop running each once (twice
  conditionally) per `AIM_POOL` entry.  A full-tree census (all five
  recordings) showed 200 (forward) / 218 (backward) real path classes, no
  declines: the ROM's own control flow is genuinely an outer loop that
  revisits its own table-lookup block from a SECOND entry point (a
  near-exhaustion tail redirects back into the table lookup whenever
  neither of its own two solid tests finds anything), not a simple bounded
  step count, so the semantics (`game/creatures.py: _aim_ray_march`, one
  shared interpreter parameterised on direction per the Decision's own
  instruction, branching only where the ROM genuinely differs -- the
  near-check's own column offset, and the second probe's own setup, which
  backward skips two real instructions of) is a literal block-by-block
  transcription of the ROM, verified by replaying its own event trace
  against 411 real fixtures before any cost or CCR work began.  Two real
  internal calls per activation into the already-recovered `aim_probe_mark`
  (00B524, itself calling 00B32E on non-bound/non-step-limit arms) -- three
  levels of composition, each level's own CCR and stack residue persisting
  into its caller exactly as the machine leaves it.  `factcheck check` and
  `--perturb-upper-halves` both clean on all 418 fixtures after fixing four
  real defects this session found in turn: A2's own exit value needs the
  full 32-bit work-RAM representation (`0xFFFFxxxx`), not a 24-bit
  truncation that silently drops the top byte on re-widening; D7 (aim_probe_
  mark's own scratch register) persists from the LAST probe call's own exit
  into the ray march's own exit register file; the `'step-limit'` arm's own
  composed exit SR needs aim_probe_mark's own internal `add.w $4(a3),d7`
  recomputed fresh, not the caller's own retained X; and `AIM_RAY_STEP_INDEX`
  (F2D4) itself was missing from the plan's own writes entirely on the first
  pass.  `camera-sprites` reached sixty-four gates -- the adapter's own
  cap, exactly: no further leaf can be armed until a family composition
  (`00B588` composing `00B354`/`00B440`/`00B62A`, or later `00A772`) frees
  gates back, the same shape `005700`'s own composition already proved.
  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19k`, 107,519
  frames): 1,196,792 hits, 8,650 fallbacks, no decline at either new gate.
  Both reproduce the original on `f0ac19738f19…`: `aim-ray-march-forward`
  PASS, 229 hits, 17 fallbacks (all `ADAPTER_REFUSALS`);
  `aim-ray-march-backward` PASS, 230 hits, 16 fallbacks (all
  `ADAPTER_REFUSALS`); both mutants (`_mutate_aim_ray_march`, shared:
  `AIM_RAY_STEP_INDEX`'s own low byte off by 4, not 1 -- 00B62A's own D7
  derives it through `>>2`, so a plain +1 only changes the shifted result on
  one of four occurrences) DIVERGENCE (frame 12,361 and 12,314).  Next, per
  the Decision's own order: `00B588` composing `00B354`/`00B440`/`00B62A`
  over every `AIM_POOL` entry (this is also the family composition that
  frees gates back below the cap), then `00B002`, `00AF52`, `00AC36`,
  `00AA76`/`00AB50`, `00A772` as the family, `00A578` as the walk with its
  own semantic-operation card.

- **19 September, grinder session closing the ray-march family**: `00B588`
  itself recovered -- a DBRA loop over `AIM_SEARCH_COUNT` entries at
  `AIM_SEARCH_POOL_LOW` (a real defect this session's own first
  `factcheck check` caught: the pool this routine walks is
  `aim_target_scan`'s own per-call "visited columns" pool, `AIM_SEARCH_*`,
  not `AIM_POOL_*`).  Per entry: one unconditional `00AF3C` grid-cell
  lookup gating a skip test (`-0x80(a2) == 1`, real ROM, never witnessed
  skipping mid-scan on an empty slot -- that arm still declines by name);
  unless skipped, a forward ray-march-and-store pass (`00B354`/`00B62A`)
  always, a second forward pass only when the creature's own type
  template byte past `$c(a4)` is signed greater than 4 (D5 13 instead of
  7, F2D2 7 instead of 3), then the same shape backward (`00B440`/`00B62A`,
  F2D2 2 then 6) -- none, two or four ray-march+store passes an entry,
  every combination witnessed.  `gods_sega.boundary.aim_pool_scan_plan`
  composes the four already-sealed gate plans as real internal `bsr`'s,
  the same `_ConstMachine` overlay technique the ray marches already use
  for their own internal probe calls, now four levels deep at its busiest
  arm.  Six real defects this session's own `factcheck check` found in
  turn before the fixtures matched: two ray-march-pass call sites had
  D5/D7 positionally swapped; the plan's own final writes used 16-bit
  overlay addresses instead of the 24-bit work-RAM addresses factcheck
  compares against; the per-entry D6 stack push never decremented across
  iterations; the per-entry F2D2 context-flag write used one hardcoded
  literal instead of each pass's own real value (and is the ONLY write to
  survive a skipped entry, so its absence surfaced as a missing write on
  the very first single-entry fixture); one extended pass's own
  `clr.w f2d4.w` cost entry was never charged; and D0/D1's own reload
  every iteration needs the entry's own upper half preserved, explicit
  even on a skipped entry where no later call ever reports the register
  changed.  A seventh, only visible past the fixtures: `native/machine.cpp`'s
  own `al_atomic` requires 0 < instructions <= 10,000 and 0 < cycles <=
  100,000 -- a real cap a busy pool (several entries, several extended
  passes) can exceed, first seen as a `CANDIDATE_ERROR` on
  `f0ac19738f19…`'s own `history-verify`, not by any fixture (census
  fixtures alone never exercise the native adapter's own admission path).
  `aim_pool_scan_plan` now declines by name once its own running total
  would cross either limit, the same "decline rather than guess" rule
  every unwitnessed arm already follows, just triggered by cost instead of
  by a branch.  `candidate 'aim-pool-scan'` replaces
  `'aim-ray-march-forward'`/`'aim-ray-march-backward'`/`'aim-probe-mark-store'`
  in `camera-sprites`: every witnessed call into those three PCs comes
  from `00B588`'s own body, so its own atomic plan already covers the
  whole span once `00B588` itself is armed there -- sixty-four gates to
  **sixty-two**, freeing two ahead of `00A772`'s own family composition
  (their own `PLANNERS` entries and standalone tests are unchanged, the
  same "retired from the combined candidate, kept for its own isolated
  tests" shape the 25 individual player-state gates and `005700` already
  established).  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-b588`, 107,519
  frames, current receipts).  Reproduces the original on
  `f0ac19738f19…`: PASS, 15 hits, 27 fallbacks (23 atomic-plan-cap
  declines, all a busy pool genuinely exceeding the native adapter's own
  limit; 4 observation deadline, both `ADAPTER_REFUSALS`); mutant
  (`_mutate_aim_ray_march`, shared with the ray marches) DIVERGENCE at
  frame 13,905.  Next, per the Decision's own order: `00B002`, `00AF52`,
  `00AC36`, `00AA76`/`00AB50`, then `00A772` as the family (frees the
  creature gates further), then `00A578` as the walk with its own
  semantic-operation card.

- **19 September, later the same session**: `00B002` recovered -- the
  progress note's own scoping confirmed exactly, fresh against the ROM
  (`census-0XB002-*`, five recordings): `clr.w f2b0.w`
  (`AIM_SEARCH_COUNT`), `clr.l f2b2.w` (`AIM_SEARCH_SNAPSHOT`'s own
  leading D0/D1 long), `clr.l f2b6.w` (its own trailing D7 word paired
  with `AIM_SEARCH_SNAPSHOT_FLAG`), `clr.l f2ba.w`
  (`AIM_SEARCH_BACKWARD_SNAPSHOT`'s own leading D0/D1 long -- its own
  trailing D7/flag are NOT cleared here, real ROM, read as whatever the
  prior activation left), then `movem.l d0-d1,-(a7)` / `bsr 00B724` /
  `movem.l (a7)+,d0-d1` (restoring the original x0/y0) / `bsr 00B7DA` (A3
  a genuine pass-through from `00B724`'s own exit) / `bsr 00B6AE`, then
  `bra.w $b588` -- `00B002` never executes its own `rts`.
  `gods_sega.boundary.aim_search_scan_plan` composes the four
  already-sealed gate plans (`00B724`/`00B7DA`/`00B6AE`/`00B588`) as real
  internal calls and a tail jump, the same `_ConstMachine` overlay
  technique `00B588`'s own composition established, one level higher --
  five levels deep at its busiest arm.  Every one of the four's own
  census fixtures returns to (or reaches) a fixed address inside
  `00B002`'s own body, one caller each, confirming the whole span is
  covered: `candidate 'aim-search-scan'` replaces
  `'aim-target-scan'`/`'aim-target-scan-backward'`/`'aim-target-resolve'`/
  `'aim-pool-scan'` in `camera-sprites` -- **sixty-two gates to
  fifty-nine** (their own `PLANNERS` entries and standalone tests
  unchanged, the same retirement shape as `00B588`'s own).
  `aim_search_scan_plan` also carries its own combined-cost decline (the
  SAME `al_atomic` cap `aim_pool_scan_plan`'s own decline already prices,
  checked again here since the inner check only ever sees its own local
  total, never this routine's own three-call prefix ahead of it).  One
  real defect this session's own `factcheck check` found: the backward
  scan and resolve calls run AFTER the `movem.l (a7)+` pop restores this
  routine's own entry stack depth, so their own return-address residue
  lands one stack slot shallower than the forward call's own (the first
  draft used a single shared slot throughout, matching every fixture
  whose own residue never differed from the forward call's, and
  mismatching every fixture where it did).  Milestone tree PASS on all
  five leaves (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-
  b002`, 107,519 frames, current receipts).  Reproduces the original on
  `f0ac19738f19…`: PASS, 15 hits, 27 fallbacks (23 atomic-plan-cap
  declines, 4 observation deadline, both `ADAPTER_REFUSALS`); mutant
  (`_mutate_aim_ray_march`, shared) DIVERGENCE at frame 13,905.  Next, per
  the Decision's own order: `00AF52`, `00AC36`, `00AA76`/`00AB50`, then
  `00A772` as the family (frees the creature gates further), then
  `00A578` as the walk with its own semantic-operation card.

- **19 September, later the same session**: `00AF52` recovered -- the
  reconnaissance's own scoping (`00AA76`'s own second call, box test then
  `00B02A`/`00B082`/`00B002`) confirmed, PLUS a second loop past where the
  original reconnaissance stopped disassembling (at the `cmpi #$10` tail):
  `move.l #$ffffffff,f2ce.w` resets `AIM_SEARCH_BEST_FLAG:AIM_SEARCH_BEST_INDEX`,
  a camera-relative four-way box test on `(a5)`'s own position (the SAME
  `AIM_PROBE_LOW_BIAS`/`AIM_SEARCH_X_LIMIT`/`AIM_PROBE_Y_HIGH` bounds the
  probe box test already uses -- X-low/X-high/Y-high all witnessed, Y-low
  real ROM never witnessed, declined by name) gates everything else.  In
  bounds: `00B02A`/`00B082` run once each (A3-A5 saved around both,
  reloaded -- not popped -- between them), `AIM_SEARCH_START_INDEX`
  cleared, then `00B002` on `(a5)`'s own raw position; if
  `AIM_SEARCH_BEST_INDEX` is (unsigned) `<= 0x10`, done.  Otherwise a
  circular scan of the 32-slot `AIM_POOL` (`FFFF40B2`, distinct from
  `AIM_SEARCH_POOL_LOW`): every occupied slot's own D0/D1 (a found
  target's own position) and D2/D3 (the next search's own
  `AIM_SEARCH_START_INDEX`/`AIM_SEARCH_FLAG_SOURCE` seed) drive ANOTHER
  `00B002` call on the target's own position, repeating until the same
  `<= 0x10` stop or `AIM_POOL_COUNT` reaches 0, wrapping back to the
  pool's own start on a full pass with the count still nonzero (real,
  witnessed) -- the found-slot arm's own 32-slot exhaustion (not the
  wrap) is real ROM, never witnessed, declined.
  `gods_sega.boundary.aim_search_dispatch_plan` composes
  `aim_pool_reset_plan`/`aim_cue_update_plan`/`aim_search_scan_plan` (the
  last one possibly several times) as real internal calls, the same
  `_ConstMachine` overlay technique the rest of the family already
  established -- six levels deep at its busiest arm.  `candidate
  'aim-search-dispatch'` replaces `'aim-cue-update'`/`'aim-pool-reset'`
  in `camera-sprites` (both exit exclusively into this routine's own
  body): **fifty-nine gates to fifty-eight** (`AIM_POOL_ADD_ENTRY` stays
  armed on its own -- a second, independent caller via `00B62A`'s own
  'store' arm).  `aim_search_dispatch_plan` also carries its own
  combined-cost decline, the same `al_atomic` cap every composition in
  this family prices.  Two real defects this session's own `factcheck
  check` found: the pool-drain loop's own A3 register is real, live
  state by the second call onward (`00B002`'s own composition changes it
  as part of its own real semantics, not a fixed pass-through the way
  A4/A5 are) -- the first draft saved/restored this routine's own ENTRY
  A3 instead of whatever the LATEST call actually left it as; and the
  loop's own wrap-around (`bra.b $afb2`) lands on the SAME `lea.l`/
  `moveq` reset the routine's own head uses, two real charged
  instructions the first draft's own bookkeeping applied the EFFECT of
  without charging the COST of (found by parking the original machine at
  the exact loop iteration a fixture's own cycle count came up short,
  confirming `aim_search_scan_plan` itself was already exact for that
  same input).  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-af52`,
  107,519 frames, current receipts).  Reproduces the original on
  `f0ac19738f19…`: PASS, 12 hits, 27 fallbacks (all atomic-plan-cap
  declines); mutant (`_mutate_aim_ray_march`, shared) DIVERGENCE at frame
  13,905.  Next, per the Decision's own order: `00AC36`, `00AA76`/
  `00AB50`, then `00A772` as the family (frees the creature gates
  further), then `00A578` as the walk with its own semantic-operation
  card.

- **19 September, later the same session**: `00AC36` recovered -- exactly
  the small, bounded, callee-free dispatcher the blocker doc's own
  reconnaissance already named, now tractable with `00AF52`'s own
  `AIM_SEARCH_BEST_FLAG` contract understood.  Reads `f2ce.w`
  (`AIM_SEARCH_BEST_FLAG`) once: `f2ce <= 1` (signed) writes it straight
  to `DIRECTION_INDEX` (`$a`, aka KIND); `f2ce > 1` derives `x = f2ce - 2`,
  KIND `:= (x & 1) + 4` (an even/odd split over four/five), then over `x`
  with its own low bit cleared -- `x == 0` sets `FALL_PHASE` (`$12`) to
  7, one more `-2` reaching 0 sets it to 9 (real ROM, never witnessed by
  any of the four recordings, declined by name), anything past that sets
  it to 13 -- and clears `FRAME_STEP` (`$4`) regardless of which
  `FALL_PHASE` arm.  `game.creatures.aim_search_flag_dispatch` (pure
  arithmetic, no RAM read beyond `f2ce.w` itself, no calls);
  `gods_sega.boundary.aim_search_flag_dispatch_plan`; candidate
  `'aim-search-flag-dispatch'`, armed as a NEW leaf in `camera-sprites`
  (fifty-eight gates to fifty-nine).  One real defect this session's own
  `--perturb-upper-halves` found: D1's own last write in the 'extended'
  arm is always a `moveq` (`#7` or `#$d`) -- clears the whole register;
  the first draft preserved the caller's own entry upper half instead.
  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-ac36`,
  107,519 frames, current receipts).  Reproduces the original on
  `fb408bc75597…`: PASS, 23 hits, 0 fallbacks; mutant (`_mutate_result`)
  DIVERGENCE at frame 10,460.  Next, per the Decision's own order:
  `00AA76`/`00AB50`, then `00A772` as the family (frees the creature
  gates further), then `00A578` as the walk with its own
  semantic-operation card.

- **19 September, grinder session opening on the `verify-camera-sprites-
  leaves-2026-09-19-ac36` tree**: two arms this doc and `boundary.py`
  called "real ROM, never witnessed" turned out to already have retained
  census fixtures -- a boundary defect, not a missing census (confirmed by
  re-running `census_all.py --max-classes 400` fresh on both `00B724` and
  `00AF52`: 11-41 distinct path classes per recording, none anywhere near
  the cap, matching the existing evidence exactly).  `00B724`'s own
  `'pruned-start'` (declined 635 times on the `-ac36` tree) and `00B7DA`'s
  own mirror (exposed once `00B724`'s fix let composed calls reach it) are
  now admitted: the same early-exit `rts` (`00B7B8`/`00B862`) their own
  continuing arms already model, one guard sooner, needing a new SR helper
  (`_ats_window_sr`, reproducing `00B32E`'s own final `add.w d3,d2` --
  X threading through the internal `00AF3C`/`00B32E` calls, caught by a
  `-ccr01` fixture whose entry `X=1` exposed a first-draft bug).  `00AF52`'s
  own `'Y-low bound exit'` (declined 192 times) is the SAME shape as the
  already-admitted X-low/X-high/Y-high bounds -- wiring it to the same
  `bound_exit` closure was the whole fix.  `factcheck check` and
  `--perturb-upper-halves` clean on the full fixture sets (`aim-target-scan`
  254/254 MATCH, `aim-target-scan-backward` 147/149 MATCH -- 2 correctly
  declined `'found without a new best'`, `aim-search-dispatch` 253/351
  MATCH -- the rest all cost-cap declines or the same backward sub-arm);
  `run_tests.py gods`: 19,747 passed, 11 skipped.  All three candidates
  reproduce the original on `f0ac19738f19…` and their mutants DIVERGENCE.
  `camera-sprites` milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-aimfix`,
  107,519 frames, current receipts): fallbacks 9,009 -> **8,215** (both
  declined reasons gone; the rest of the drop is hits moving from `00B002`'s
  own gate onto `00AF52`'s own, since a previously-declined `00AF52`
  activation used to fall back to the real CPU, which then re-triggered
  `00B002`'s own separate gate -- the whole span is now one atomic hit).
  Next, per the Decision's own order (unchanged by this fix): `00AA76`/
  `00AB50`, then `00A772` as the family, then `00A578` as the walk.

- **19 September, grinder session opening on `00AA76`**: recovered.  Read
  `$AAE4`, the `$AB1A` not-taken (negative-counter) arm and confirmed
  `$2(a5)`/`$6(a5)` by role (`POSITION_Y` and, for `$6(a5)`, a per-instance
  search-retry counter -- the SAME offset `LIFECYCLE_RESET`/
  `GROUND_HOLD_TIMER` other callers already name, `creatures.
  AIM_RETRY_COUNTER` here) -- five real arms, not the "about twenty
  instructions" the reconnaissance first estimated: the header guard
  (`(a5) & $1c`), the `$100(a2)` footing guard (00AF3C), 00AF52's own
  three-way re-dispatch on `AIM_SEARCH_BEST_FLAG` (negative runs a SECOND
  00AF3C on the original position then a six-probe neighbor cascade;
  zero and the cascade's own third-probe shortcut both reach the shared
  reset; positive runs 00AC36), and the shared reset itself (two entry
  points, `$AB1A`/`$AB06`) reseeding the retry counter via a per-type byte
  and the shared `timers.FREQUENCY_SCALE` multiplier when it goes
  negative -- verified against a real trace including MULU's own
  unsigned treatment of a byte-subtraction underflow.  Of the neighbor
  cascade's six probes, only two routes and two second-group outcomes are
  witnessed by any of the five recordings; the rest (`probe_b` alone, the
  second group's first two probes) are real ROM, declined by name.
  Composed in `boundary.aim_kind_handler_76_plan` over
  `creature_grid_cell_d0d1_plan`/`aim_search_dispatch_plan`/
  `aim_search_flag_dispatch_plan` as real internal `bsr` calls, ending at
  a hand-off to `kind_frame_offset`'s own separately-armed gate -- the
  SAME shape `ground_contact_update_plan`'s own trigger arms already use.
  Two real defects the FAST tier caught before any fixture matched: the
  `movem.l a3-a5,-(a7)` frame around the 00AF52 call needs its own -12
  stack-pointer effect modelled explicitly (every one of 00AF52's own
  internal residues is computed relative to it) and its own SR threading
  after each internal call must read the CALLEE's own real exit SR, never
  this routine's own stale pre-call value; a third (`--perturb-upper-halves`):
  `moveq #1,d0` clears the whole register, not preserved from entry.
  `factcheck check` clean on all 349 retained fixtures (247 MATCH, 0
  MISMATCH, 102 DECLINED -- all inherited cost-cap declines from the
  composed 00AF52/00B7DA, or the two never-witnessed neighbor-cascade
  routes/outcomes).  `camera-sprites` extended to sixty gates.  Milestone
  tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-aa76`, 107,519
  frames, current receipts).  Reproduces the original on
  `f0ac19738f19…`: PASS, 59 hits, 7 fallbacks (all atomic-plan-cap);
  mutant (`_mutate_result`) DIVERGENCE at frame 13,901.  Next, per the
  Decision's own order: `00AB50` (the same shape, NOT byte-identical:
  its own shared-exit test is `f2ce == 1` not `f2ce == 0`, its own arm-2
  sets KIND 3 not 2, and its own two neighbor cascades run in the
  opposite order -- confirmed by direct disassembly, not assumed), then
  `00A772` as the family, then `00A578` as the walk.

- **19 September, grinder session on `00AB50`**: recovered -- 00AA76's own
  mirror, confirmed NOT byte-identical the same way every other mirror
  pair in this game has been (ground-contact/fall-kind before it): its
  own shared-exit test is `f2ce == 1`, reached via a separate `cmpi.w`
  after the `tst.l` that gates the negative arm (00AA76's own is a plain
  `tst.w` against 0, so `f2ce == 0` shortcuts there directly; here it
  falls through to 00AC36 like any other non-negative, non-1 value);
  its own arm-2 sets KIND 3; its own two neighbor cascades run in the
  opposite offset order; and past them its own KIND polarity inverts
  end to end (the shared reset writes KIND 1 where 00AA76's own writes
  KIND 0, the cascade's own immediate exit writes KIND 0 where 00AA76's
  own writes KIND 1) with the header-field adjustment flipped from SUBQ
  to ADDQ to match -- the same "position deltas negate between mirrors"
  pattern `ground_contact_update`'s own pair already established.  Reused
  `game/creatures.py`'s own `aim_retry_counter_step`/
  `aim_kind_handler_search` verbatim, parameterised on offset order.  A
  real, PRE-EXISTING defect in the already-shipped `aim_search_flag_
  dispatch_plan` (00AC36) surfaced only through this new caller: its own
  `'extended'` arm's exit SR assumed `clr.w $4(a5)` was the last X-setter
  and retained the caller's own entry X, but the routine's REAL last
  X-setter is `00AC46`'s own `subq.w #2,d0` (unconditionally X=0 in this
  arm, since every path reaching it has `f2ce` signed `> 1`) -- every
  EXISTING caller of 00AC36 happened to always enter with X already 0, so
  the bug was invisible until 00AB50's own composition produced a real
  X=1 entry; fixed in `aim_search_flag_dispatch_plan` itself, not worked
  around in the caller, and re-verified clean on its own original
  14-fixture set plus both kind-handler callers.  `factcheck check` clean
  on all 346 retained fixtures (257 MATCH, 0 MISMATCH, 89 DECLINED -- all
  inherited cost-cap declines or the two never-witnessed neighbor-cascade
  routes/outcomes).  `camera-sprites` extended to sixty-one gates.
  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-ab50`, 107,519
  frames, current receipts).  Reproduces the original on `f0ac19738f19…`:
  PASS, 153 hits, 20 fallbacks (all atomic-plan-cap/observation
  deadline); mutant (`_mutate_result`) DIVERGENCE at frame 12,265.  Next,
  per the Decision's own order: `00A772` as the family (frees the
  creature gates further), then `00A578` as the walk with its own
  semantic-operation card.

- **19 September, grinder session opening on `00A772` itself**: fresh
  disassembly shows the routine is real ~310 bytes, not the ~0x60 the
  original blocker's own reconnaissance transcribed -- past the
  already-recovered kind-table dispatch and its own three composing
  calls, execution ALWAYS continues (no early `rts`) into a further tail:
  an animation-frame/sprite-position update through the SAME frame table
  `kind_frame_offset` already reads, a call into the already-recovered
  sprite emitter (`0018C8`) and, conditionally, the already-recovered
  next-random draw (`014A3C`) -- but also TWO genuinely new, previously
  unexamined calls: `00004AAA` (a 200-slot creature effect-slot pool,
  now recovered, above) via its own caller `00010E28` (not yet
  recovered), and `00009A9F2` (called only when the creature's own
  `LIFECYCLE` word is negative -- 52 of 1,131 retained fixtures witness
  it) which itself calls `000003F0C`, a BCD digit-increment utility on a
  counter array at `$EF80` that only sets a dirty flag (`$F1CE`) for a
  separate, VBlank-driven display flush this session does not chase.
  Neither new call touches a device directly.  `00A772`'s own "moving"
  arm (`$F38A.w != 0`, hand off to `00AA50` instead of the attack timer)
  is real ROM, never witnessed by any of the five recordings across
  1,131 retained fixtures -- every occurrence takes the attack-timer arm.
  `00004AAA` closes this session (own entry above); `00010E28`,
  `00009A9F2`/`000003F0C`, and the eight kind-handler slots' own
  remaining unwitnessed pair (`00AA80`/`00AB5A`) are the next bites
  before `00A772` itself can be composed as the family; `00A578` as the
  walk remains open behind it.

- **19 September, later the same session**: `00010E28` (`'effect-slot-add'`)
  and `00003F0C` (`'bcd-counter-add'`) both recovered.  `00010E28`
  composes `00004AAA` over a full `movem.l` register frame (every
  register but A7 returns to its own entry value except D6, not in the
  save list, left as the pool scan's own remaining count): on `'found'`
  it stores the caller's own D0/D1 (a world position), an adjusted D2 (a
  frame/type index wrapped modulo `0xB`, both directions witnessed), and
  a literal 1 into the slot, advances a cursor (`F2A6`) past it, and
  marks the slot's own index in a parallel 200-byte flag table
  (`FFFF3FEA`); `'exhausted'` real ROM, never witnessed, declined.
  `00003F0C` is a shared packed-BCD counter add (`FFFFEF80`, three
  digit-pair bytes via `ABCD`, propagating decimal carry) with FAR more
  callers than just `00A772`'s own tail (400+ occurrences across the
  recordings against `00A9F2`'s own 52) -- one path class per recording,
  the carry-propagation formula verified past the witnessed data with
  `factcheck branches --vary` (a forced `0x99+1` overflow neither real
  play nor the retained fixtures happened to reach).  Both new gates
  bring `camera-sprites` to **sixty-four**, the adapter's own cap: no
  further leaf can be armed there until a family composition frees gates
  back (`00A772` itself, next).  Three real defects the FAST tier caught
  in turn: `00010E28`'s own `movem.l` push frame (32 bytes of real,
  permanent stack residue) and the internal `jsr`'s own return-address
  residue were both missing from the first draft entirely, and the
  `F2A6` cursor used the 24-bit masked slot address instead of the full
  32-bit one (losing its own `0xFF` top byte); `00003F0C`'s own first
  draft read the wrong RAM offset for each digit-pair byte (a word's own
  SECOND byte, `+3`/`+5`/`+7` from the base, not `+2`/`+4`/`+6`).
  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-bcd`, 107,519
  frames, current receipts).  Next: `00009A9F2` (composes `00003F0C`,
  called only when `LIFECYCLE` is negative -- kept out of `camera-sprites`
  for the same gate cap until `00A772`'s own family composition frees
  room), the eight kind-handler slots' own remaining unwitnessed pair,
  then `00A772` itself as the family; `00A578` as the walk remains open
  behind it.

- **19 September, later the same session**: `00009A9F2` (`'creature-death-bcd'`)
  recovered -- composes `00003F0C` up to twice over a partial `movem.w`
  register frame (D3 and D5 are NOT in the save list, so both stay as
  whatever the last internal call and this routine's own arithmetic left
  them).  Derives up to two ABCD "amount" bytes from the creature's own
  type-template byte: `((byte & $ff) >> 1) + 1`, divided by 10 (`DIVU`);
  the quotient/remainder pack into a first amount fed to `00003F0C`
  unmodified even when the quotient exceeds 9 (a non-BCD nibble
  `00003F0C`'s own digit-carry arithmetic still resolves correctly, the
  same way real ABCD hardware does on any byte); a quotient above 9 also
  triggers a second, corrective amount and a second `00003F0C` call --
  both branches witnessed.  Kept OUT of `camera-sprites` (the adapter's
  own 64-gate cap, already reached) until `00A772`'s own family
  composition frees room.  Four real defects the FAST tier caught in
  turn: the `movem.w` frame used 4-byte (`movem.L`) spacing instead of
  2-byte; every restored register sign-extends its own saved WORD on the
  pop rather than preserving the caller's own entry upper half; the
  second internal `00003F0C` call was missing its own `jsr` instruction's
  cost entirely; and the shared exit's own SR test read the caller's
  entry D6 instead of this routine's own local value.  `factcheck check`
  and `--perturb-upper-halves` both clean on all 7 retained fixtures.
  Reproduces the original on `f0ac19738f19…`: PASS, 78 hits, 2 fallbacks
  (`z80 bank guard`); mutant DIVERGENCE at frame 601.  With this,
  `00A772`'s own further tail is FULLY recovered piecewise
  (`00004AAA`/`00010E28`/`00003F0C`/`00009A9F2`, all composing back to
  already-recovered leaves and each other); the eight kind-handler
  slots' own remaining unwitnessed pair (`00AA80`/`00AB5A`, real ROM,
  never reached by any of the five recordings) need no further
  reconnaissance -- they decline by name inside `00A772`'s own future
  composition.  Next: `00A772` itself as the family, composing
  `009D6C`/`00AA50`/`00B944`/`00A922`, the eight kind-handler slots, and
  its own further tail (`00004AAA` through `00009A9F2`); then `00A578`
  as the walk.

- **19 September, `00A772` itself composed as the family**:
  `creature_family_plan` (candidate `'creature-family'`) composes, in
  order, `attack_update_plan` (unconditional -- the header's own
  "moving" arm is 0% witnessed and declined up front), the eight-entry
  kind table (kind 0/1 `00AA76`/`00AB50`, 2/3 the fall pair, 4/5 the
  ground pair, 6/7 `00AA80`/`00AB5A` declined by name), `event_consume_
  plan` with D2 saved/restored around it, a fresh D0/D1 reload,
  `creature_pickup_check_plan` inside a `movem.l d7/a3-a5` frame, and,
  only when LIFECYCLE comes back negative, `creature_death_bcd_plan`.  A
  genuinely new finding past the already-recovered dispatch:
  `aim_kind_handler_76_plan`/`aim_kind_handler_50_plan` and both
  `ground_contact_update` variants do not return to their own caller at
  all -- they tail-jump (`bra`, no return-address push) into
  `kind_frame_offset_plan`'s own entry (`00AA50`), which then pops the
  kind dispatch's own return address on ITS OWN `rts`; the fall pair
  already inlines `kind_frame_offset` and returns directly.  From there
  the routine is a platform tail (the "one seam, cede the whole
  remainder" rule `player_tail_plan` already draws on at `0075D6`): the
  prefix ends at the `jsr $126a.l` itself, the entire remainder --
  `particle_emit`'s own body, the closing `movem.l (a7)+`, the
  `DISPLAY_TIMER` test, and the conditional second device call (`jsr
  $18c8`, `sprite_emit`) inside the rare animation block -- is ceded to
  the machine untouched, resuming at `00A772`'s own SOLE witnessed `rts`
  (`00A864`); the other `rts` (`00A8A8`) is 0% witnessed and declined up
  front the same way the moving arm is.  Retires ten individual leaf
  gates from `camera-sprites` (`attack-update`, `event-consume`,
  `creature-pickup-check`, the ground-contact pair, the fall-kind pair,
  `creature-grid-cell`, `ground-edge-test`, `af3c`) -- every witnessed
  call into them now comes from this composition alone; `kind_frame_
  offset` itself stays armed on its own, since the declined moving arm
  reaches it directly.  `camera-sprites` drops from sixty-four to
  **fifty-five** gates.  1,131 retained fixtures: 1,092 MATCH, 39
  DECLINED, 0 MISMATCH.  Four real defects the FAST tier caught: the D2/
  D7 push-pop bookkeeping around `event_consume` never advanced the
  tracked stack pointer (every later internal push landed six bytes too
  high); the kind dispatch's own hand-off to `kind_frame_offset` was
  missing from the first draft entirely; the D0/D1/kind reloads read the
  raw machine instead of this composition's own overlay, missing an
  aim-chain rewrite of the creature's own position on the deepest kind-76
  activations; and the LIFECYCLE-negative branch's own type-record read
  used the entry-time A4 instead of the CURRENT one (the kind handler's
  own internal chain can leave A4 clobbered as scratch).  A fifth defect
  surfaced only on the tree milestone's own longest recording
  (`fb408bc75597`, 34,904 frames): the native adapter's own 100,000-
  cycle/10,000-instruction atomic-plan cap is checked by the aim-search/
  aim-pool leaves against their OWN incremental cost alone, blind to
  this composition's own outer overhead running before them -- fixed
  with the same cap check at this composition's own outer boundary.
  Reproduces the original on `f0ac19738f19…`: PASS, 517 hits, 77
  fallbacks (all adapter refusals or the aim-pool cost-cap decline);
  PASS on `fb408bc75597…` too (34,904 frames, post cost-cap fix); mutant
  (`_mutate_creature_family`, D0 off by one) DIVERGENCE at frame 12,265.
  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-a772b`,
  107,519 frames, current receipts).  Next: `00A578` as the walk over
  the nine slots at `FF1496`, composing `00A772` and `00B920`, with its
  own semantic-operation card.

- **19 September, `00A578` itself composed as the walk**: real
  disassembly shows the loop counter is pushed as 9 and tested AFTER
  each decrement (`subq.w #1,(a7); bpl.w`, not a DBRA), so the body
  actually runs TEN times -- confirmed directly against the tracer and
  against RAM (the tenth slot's own header is 0 on all 1,283 retained
  fixtures across all five recordings) and modelled as a real 10th
  iteration.  `creature_walk_plan` composes `creature_family_plan`
  (00A772) from the per-frame-update body's own `LIFECYCLE > 0` arm,
  `spawn_table_add_plan` (00B920) from both the spawn-init body and the
  icon-spawn sub-machine's own `-2` arm, `creature_grid_cell_plan`
  (00AA38) and `static_emit_plan` (001164) directly, and a new reusable
  `floating_icon_spawn_plan` (0010D7C, composed at all three of its own
  call sites here rather than duplicated).  The SAME platform-tail rule
  as 00A772's own: once any composed family activation reaches the
  device, the entire remainder of the WHOLE TICK's own walk is ceded,
  resuming at 00A578's own sole rts (00A662), never at 00A772's own
  00A864.  Retires two more leaf gates from `camera-sprites`
  (`creature-family`, `spawn-table-add` -- 00A578 is confirmed their own
  sole caller) -- fifty-five to **fifty-four** gates.  1,283 retained
  fixtures: 1,245 MATCH, 38 DECLINED, 0 MISMATCH, `--perturb-upper-halves`
  clean.  A long chain of real defects the FAST tier caught (full list in
  `ledger.md`'s own entry): the loop-counter's own off-by-one; stack/list
  pointers tracked as 24-bit-masked locals then used as the base for the
  NEXT advance, silently dropping the `0xFFFF` page prefix; the outer
  a3/a5 registers only updated at the top of each slot iteration, one
  iteration stale by the time the loop exits; half a dozen real
  MOVE/MOVEQ/ADDQ sites across the three bodies left D0/D1/D2/D4/D6/D7
  untracked; the kind dispatch's own zone-mode test reading 00A578's own
  ENTRY a1 instead of `creature_grid_cell_plan`'s own live exit a1 (its
  own bsr runs first and documents overwriting a1); two bare `bra`
  instructions right after an internal call's own return point missing
  their own charge entirely; and two real 68000 timing quirks new to
  this session -- ADDQ/CLR to an absolute-word or `(d16,An)` destination
  costs 4 more than a plain MOVE of the same shape (the same
  read-modify-write quirk this session's own CLR finding already named,
  now confirmed for ADDQ too), while a plain MOVE.W `(d16,An)` SOURCE
  read does not carry it.  Reproduces the original on `f0ac19738f19…`:
  PASS, 6,756 hits, 70 fallbacks (all adapter refusals or the aim-pool
  cost-cap decline); mutant (`_mutate_creature_walk`) `CANDIDATE_ERROR`
  (an M68000 address error) rather than a clean divergence -- the same
  "a mutant that faults the machine is a finding about the game, not a
  control" class `kind_frame_offset`'s own mutant note already names,
  confirmed separately via `segment_verify` and the test suite's own
  NativeError-tolerant check.  Milestone tree PASS on all five leaves
  (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-a578`,
  107,519 frames, current receipts).  See `00A578`'s own
  semantic-operation card immediately below.  With this, the ENTIRE
  creature subsystem the 18 September blocker opened
  (`docs/gods/blockers/2026-09-18-00A578.md`) is closed end to end.

### `00A578` semantic-operation card

Per `docs/common/recovery-process.md`'s own card fields, now that the
walk owns real persistent per-slot/per-instance state and composes
several other candidates into a genuine composite region:

- **Semantic operation**: once per tick, while `WALK_GATE` (`FFFFEED1`)
  is nonzero, reset `TRACKED_SIGN` (`FFFFF1BE`) to -1 and walk the
  9(+1)-slot creature list at `FF1496` (`CREATURE_LIST_STRIDE` = 0x12
  bytes each), each slot owning a reserved, fixed-size block of the
  shared instance array at `FFFF2602` (`CREATURE_SLOT_BLOCK` = 0xF0
  bytes, ten instance-sized slots, used or not).  A zero header skips a
  slot outright; header `== 1` walks its own live instances, calling the
  family (00A772) for each with a positive `LIFECYCLE`; any other
  nonzero header spawns `(type_ptr)+1` brand-new instances and
  decrements the header, spreading a batch over several ticks.
- **Entry/exit boundary**: entry `00A578` with the machine parked at
  `WALK_GATE`'s own test.  A zero gate is a bare `rts` at `00A662`.
  Otherwise exit is the SAME `00A662`, reached either directly (every
  slot resolved in pure Python) or through the platform tail described
  above, ceding everything from the first device-touching family
  activation onward.
- **Persistent state**: the 9(+1) list slots themselves (header, type
  pointer, `WAVE_TRIGGERED` latch) and every field of every instance the
  walk creates or steps (`POSITION_X/Y`, `FRAME_STEP`, `LIFECYCLE`,
  `LIFECYCLE_RESET`, `DIRECTION_INDEX`, `FALL_PHASE`, `AIM_WINDOW_STATE`,
  `DISPLAY_TIMER`, `COUNTDOWN`) -- all named in `game/creatures.py`, none
  owned by 00A578 itself beyond the list/slot bookkeeping.  Three
  tick-scoped globals belong to the walk alone: `WALK_SETTLED_COUNT`
  (`F2C6`) and `WALK_DISPLAY_COUNT` (`F2C8`), both reset to 0 at the top
  of every per-frame-update slot, and `WALK_CACHED_POSITION` (`F26C`),
  the last icon-spawn 'display' instance's own position this tick.
  `WALK_A5_SAVE` (`F2C2`) is pure register-spill scratch, read back by
  nothing.
- **External observations**: none of its own beyond what the family
  (00A772) and the two device leaves (`floating_icon_spawn_plan`,
  `static_emit_plan`) already own -- the walk's own new code (the
  spawn-init and icon-spawn bodies) is entirely RAM-only.
- **Pending effects**: none synchronous.  A slot's own header
  transition (activated, decremented, or cleared) and every instance
  field this tick writes become durable the moment the NEXT tick's own
  walk re-reads them; nothing is left pending across a commit boundary.
- **Permitted interference**: not proven for the walk as a whole beyond
  what `creature_family_plan`'s own mutant already demonstrates (a
  corrupted D0 reaching the ceded particle emitter faults or diverges,
  confirmed observable).  No cross-slot or cross-tick reordering has
  been attempted; every admitted activation is still gated as an exact
  L0 region.
- **Proven movable events**: none -- a synchronous per-tick walk, not an
  event queue.
- **Required ordering boundaries**: the outer gate's own `WALK_GATE`
  read must precede everything else; within a slot, the header dispatch
  must precede the type-pointer read (the type pointer is only valid
  once the header is known nonzero); within spawn-init, the zone-mode
  test at `00A600` must read `creature_grid_cell_plan`'s own LIVE exit
  a1 (the grid-cell address `bsr $aa38` just computed), not the walk's
  own entry a1 -- a real ordering bug this session's own FAST tier
  caught directly (`ledger.md`'s own entry).
- **Timing dependency**: none beyond the ordinary once-per-tick call;
  every cost fragment (including the two ADDQ/CLR-to-memory quirks named
  above) is a fixed instruction cost, no duration model needed.
- **Evidence and scope**: `census-0X00A578-*` over all five recordings,
  1,283 retained fixtures (400 max-classes per recording overflows by
  the thousands on the two longest histories, `fb408bc75597…` and
  `7251bbd0ecf7…`, since a 9(+1)-slot walk's own whole-region exit
  signature explodes combinatorially with how many slots are active at
  once -- the census is a representative sample, not exhaustive; the
  milestone tree's own exhaustive per-frame comparison over all five
  recordings is the real authority).  `history-verify` on
  `f0ac19738f19…` (the shortest exercising leaf, 15,148 frames): 6,756
  hits, 70 fallbacks, all adapter refusals or the already-documented
  aim-pool-scan cost-cap decline.  Gated: `creature-walk` (this card),
  composing `creature-family`, `spawn-table-add`, `creature-grid-cell`
  and `static-emit`/the achievement highlight cycle's own inline
  `floating_icon_spawn_plan` use -- every other creature-subsystem leaf
  this session recovered (`creature-attack`, the eight kind handlers,
  `event-consume`, `creature-pickup-check`, `creature-death-bcd`,
  `effect-slot-find`/`effect-slot-add`, `bcd-counter-add`,
  `kind-frame-offset`) is reached exclusively through this one gate now,
  save `kind-frame-offset` itself (the declined moving-arm exception
  already named).

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
| **`014084` hazard tick**: two disjoint bodies behind one early branch -- 'paint' (inactive, or an active object whose grid cell isn't 1: a tile-array write clamped to bounds) and 'spawn' (grid cell 1: a sound request, then a bounded 20-entry pool scan and fill, whether or not a slot was free), the SAME shared fill now shown (17 Sep) to run whether or not the parallel-table type matched the trigger byte -- when it does and the trigger counter has reached 2, `0140CC`'s own `jsr` into the already-recovered proximity table (`00F828`) runs first, landing back at the fill either way; the plan reproduces every fact of the original on all 147 retained fixtures over four recordings; only a type match with the counter still under 2 (real code, unwitnessed), a proximity selector outside 0/1/2, or the proximity table's own pool-full arm still decline as 'trigger' | `factcheck check` on every fixture | `tests/games/gods/test_hazard.py` |
| `hazard-tick` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 26,118 hits, 175 fallbacks (all z80 bank guard, 0 unsupported domain)** -- up from 26,075 hits/218 fallbacks (185 scheduler admission, 33 unsupported domain); `camera-sprites` (all twenty-six gates) on the tree of all eight recordings: **PASS, tree bit-exact** | `history-verify fb408bc75597 --candidate hazard-tick`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-hazard-tick2-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17f` |
| the hazard tick's negative control diverges at frame 2,628 (the first frame the region is exercised on `fb408bc75597…`) | `--candidate hazard-tick-mutant-result` | `artifacts/gods/verify-hazard-tick2-mutant` |
| **`00470C` trigger conditions** (the first Gods dispatcher): the plan reproduces every fact of the original on all 129 retained fixtures over five census directories (fourteen kinds, every witnessed compare position) | `factcheck check` on every fixture | `tests/games/gods/test_conditions.py` |
| `conditions` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 5,247 hits, 36 fallbacks (all scheduler admission)**; `camera-sprites` (all fifteen gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,055,949 hits, 11,521 fallbacks (7,366 scheduler admission, 3,728 seam deadline, 426 declined arms of other regions), 30.6M instructions replaced** | `history-verify f0ac19738f19 --candidate conditions`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-conditions-f0ac1973`, `artifacts/gods/verify-camera-sprites-tree-2026-09-16p` |
| the conditions negative control (a failing condition reported as passing) diverges at frame 993; a register mutant was blind and was dropped | `--candidate conditions-mutant-outcome` | `artifacts/gods/verify-conditions-mutant` |
| **`00364C` score conversion**: 1-3 digit values (0-999), witnessed at both score-update call sites over four recordings; the plan reproduces every fact on all 12 retained fixtures | `factcheck check` on every fixture | `tests/games/gods/test_score.py` |
| `score-convert` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 56 hits, 0 fallbacks**; mutant DIVERGENCE at frame 675 | `history-verify f0ac19738f19 --candidate score-convert` | `artifacts/gods/verify-score-convert-f0ac1973`, `verify-score-convert-mutant` |
| **`00462C` trigger evaluator**: the non-firing arm, a composition of three calls into `00470C` (the boundary owns the call); the plan reproduces every fact on all 21 non-firing retained fixtures over four recordings; firing (11) and disabled (0, unwitnessed) decline | `factcheck check` on every fixture | `tests/games/gods/test_triggers.py` |
| `evaluator` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 1,708 hits, 55 fallbacks (32 firing, 21 scheduler admission, 2 disabled)**; mutant DIVERGENCE at frame 993 | `history-verify f0ac19738f19 --candidate evaluator` | `artifacts/gods/verify-evaluator-f0ac1973`, `verify-evaluator-mutant` |
| **`00F828`/`00F86A` proximity table search-and-add**: `00F828` owns its own call into `00F86A`, and, since 17 Sep, its own found-entry continuation at `00F8A2` too (`game.hazard.proximity_trigger`: a caller-record decrement of the SAME timer word the search tested, gated by which of `conditions.py`'s own `TRACKED` ids is selected -- all three checks always run regardless of which matches, so cost is selector-independent; a decrement past the floor clears to 0). Re-censused with `--max-classes 400` (the default 32-class cap was silently discarding real classes) to reach 25 real 'trigger' fixtures, none previously retained. The plan reproduces every fact on all 39 retained fixtures over two recordings; only 'pool-full' (0, unwitnessed) still declines | `factcheck check` on every fixture | `tests/games/gods/test_proximity.py` |
| `proximity` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 33 hits, 0 fallbacks** -- up from 8 hits/25 fallbacks, every witnessed trigger occurrence now admits; mutant DIVERGENCE at frame 12,890 | `history-verify fb408bc75597 --candidate proximity` | `artifacts/gods/verify-proximity2-fb408bc75597`, `verify-proximity2-mutant` |
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
| **`00BA8E` pickup check, 18 Sep -- the found-message arm**: not a message at all -- 00BBEA-00BC1C is straight-line RAM/register arithmetic (no bsr/jsr) that derives an alternate `(box_result, d3)` pair (an award right-shift by `3-AWARD_SCALE_LEVEL`, or a halving correction when the shift removes no bits) and rejoins the SAME found-sound/found-bare/found-effect tail at its own entry points; a gate scan at the test instruction (not the class-capped census, whose budget the box/scan diversity always exhausted first) found the level is 1 on all 104 real occurrences across the eight recordings, all on `7251bbd0ecf7…` -- found-sound (8), found-bare (4, incl. the halving-correction sub-branch), found-effect (84); any other level stays declined, unwitnessed. Re-censused `00BA8E` on `7251bbd0ecf7…` at `--max-classes 600` (407 real path classes, up from 32) to retain fixtures for it | `factcheck check` on every fixture (1,107 of 1,108 00BA8E/010CD2 fixtures MATCH, 1 correctly declined: found-special-timer) | `tests/games/gods/test_pickup_check.py` |
| `pickup-check` reproduces the original on `f0ac1973…`: **PASS, 15,148 frames, 4,320 hits, 31 fallbacks, unchanged**; on `7251bbd0ecf7…` (the history that witnesses the arm): **PASS, 25,264 frames, 13,606 hits, 30 fallbacks (13 observation deadline, 4 vblank in span, 12 z80 bank guard, 1 found-special-timer) -- the found-message fallback reason is gone**; segment_verify at boundary-6000/12000 PASS, unchanged (231/1, 132/3, all z80 bank guard); mutant `pickup-check-mutant-result` DIVERGENCE at frame 2,034 on `7251bbd0ecf7…` | `history-verify f0ac19738f19 --candidate pickup-check`; `history-verify 7251bbd0ecf7 --candidate pickup-check` | `artifacts/gods/verify-pickup-check3-f0ac1973`, `artifacts/gods/verify-pickup-check3-7251bbd0ecf7`, `artifacts/gods/verify-pickup-check3-mutant` |
| the pickup check's negative control diverges at the first found award | `--candidate pickup-check-mutant-result` | `artifacts/gods/verify-pickup-check2-mutant` |
| **`007986` message display gate + `0079DC` string copy** (`game/messages.py`, the trigger firing subsystem blocker's own part 1): `0079DC` is a plain byte copy bounded by the string's own length (the NUL is read but not written -- the caller's own `clr.b (a1)+` supplies it); `007986` gates a message of priority D7 (negated first when negative, clearing `MESSAGE_BOUND`/`MESSAGE_PENDING`) against the display buffer -- empty, or occupied with a sufficient stored priority (through `MESSAGE_BUFFER_ALT` instead), are both `'ready'`; a stored bound of exactly 0 while occupied (skips the compare outright) is real code no recording enters.  Re-censused `007986` over all eight recordings with `--max-classes 100` (the default 32-class cap already shown this session to discard real classes) to catch the one occupied-buffer occurrence the original two-recording census missed entirely | `factcheck check` on every fixture | `tests/games/gods/test_messages.py` |
| `message-gate` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 31 hits, 0 fallbacks**; `string-copy`: **PASS, 34,904 frames, 69 hits, 9 fallbacks (all z80 bank guard)**; both mutants DIVERGENCE at frame 2,328; `camera-sprites` (all twenty-eight gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,046,975 hits, 5,681 fallbacks, tree bit-exact** | `history-verify fb408bc75597 --candidate message-gate`; `history-verify fb408bc75597 --candidate string-copy`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-message-gate-fb408bc75597`, `artifacts/gods/verify-string-copy-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17g` |
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
| **`0047DA` achievement slot reset** (`game/achievements.py`, the trigger firing subsystem blocker's own part 2, first bite): a platform-tail seam (Aladdin's "one native call inside the branch" shape) over the collected-item icon upload `001648` (disassembled fresh: a VDP command from the table at `0016C2` indexed by D0, then a tile-descriptor stream through `0B5D04`/`0B5E04` or -- the only arm reachable from this caller, since D2 is fixed at -1 on every call -- an 8-longword fill of `FFFFFFFF`/`DDDDDDDD` by D1); D0 (0/1/3 witnessed, 2 declined) selects one of 001648's own four VRAM icon slots | `factcheck check` on every fixture | `tests/games/gods/test_achievements.py` |
| `achievement-slot-reset` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 12 hits (6 seam entries/completions), 1 fallback (icon slot 2, the one real occurrence)**; segment_verify at boundary-6000/12000 PASS, 0/0 hits (too rare for a 300-frame window); mutant DIVERGENCE at frame 20,282; `camera-sprites` (all twenty-nine gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,046,643 hits, 5,538 fallbacks (4,227 z80 bank guard, 443 seam deadline, 345 observation deadline, 304 vblank in span, 190 evaluator firing/disabled, 27 machine admission, 2 achievement-slot-reset icon-slot-2 declines, 1 pickup-check found-special-timer decline, tree bit-exact)** | `history-verify fb408bc75597 --candidate achievement-slot-reset`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-achievement-slot-reset-fb408bc75597`, `artifacts/gods/verify-achievement-slot-reset-mutant2`, `artifacts/gods/verify-camera-sprites-tree-2026-09-18a` |
| **`004790` achievement slot dispatch**: a caller-supplied record pointer's own tracked id, gated by a shared record table's own status word (only 2 witnessed) then checked against 0047DA's own four ids; a miss is a plain leaf, a match is a seam over 0047DA composed one level up (a seam over a seam -- `genesis_re.seam.run_seam` narrows the gate array to the resume PC alone while a seam runs, so 0047DA's own separate gate never fires inside this one even though both are armed in the same composite candidate) | `factcheck check` on every fixture | `tests/games/gods/test_achievements.py` |
| `achievement-slot-dispatch` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 8 hits (2 seam entries/completions), 0 fallbacks**; segment_verify at boundary-6000/12000 PASS, 0/0 hits (too rare for a 300-frame window); mutant DIVERGENCE at frame 24,370; `camera-sprites` (all thirty gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,046,650 hits, 5,538 fallbacks, tree bit-exact -- zero fallbacks at the 004790 gate itself** | `history-verify fb408bc75597 --candidate achievement-slot-dispatch`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-achievement-slot-dispatch-fb408bc75597`, `artifacts/gods/verify-achievement-slot-dispatch-mutant`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17i` |
| **`00475E` slot scan** (the trigger firing subsystem blocker's own part 3 preamble): gates on bit 7 of the caller's own record's `$10` byte; when set, checks three independent flag words in program order and, for whichever is 1, calls the already-recovered `004790` with a pointer two bytes past the flag -- up to three times in one activation, but every witnessed occurrence has at most one flag true. A match composes one level up from `achievement_slot_dispatch_plan` exactly as that planner composes one level up from `achievement_slot_reset_plan`; only the first position's call is ever witnessed to match | `factcheck check` on every fixture | `tests/games/gods/test_achievements.py` |
| `slot-scan` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 68 hits (2 seam entries/completions), 0 fallbacks**; segment_verify at boundary-6000/12000 PASS (0/0, 1/0 hits/fallbacks); mutant DIVERGENCE at frame 24,370; `camera-sprites` (all thirty-one gates) on the tree of all eight recordings: **PASS, tree bit-exact** | `history-verify fb408bc75597 --candidate slot-scan` | `artifacts/gods/verify-slot-scan-fb408bc75597`, `artifacts/gods/verify-slot-scan-mutant` |
| **`004800` record id scan** (the trigger firing subsystem blocker's own part 2, last caller): gates on `d5 = ($10(a1)) & 0x7fff` being one of `{2,3,4,7,8}`; the same three (flag, id) field pairs `00475E` checks, but the id word must fall in one of two ranges (`0x12`-`0x17` or `0x7f`-`0x81`) rather than equal 1. A witnessed pair calls a freshly-disassembled `0048B4` (achievement_slot_dispatch's own id-compare tail with no status gate, reached by a tail `bra.w` straight into `0047DA` -- no bsr, no extra resume layer); every witnessed call is a match | `factcheck check` on every fixture | `tests/games/gods/test_achievements.py` |
| `record-id-scan` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 68 hits (3 seam entries/completions), 1 fallback (icon slot 2)**; segment_verify at boundary-6000/12000 PASS (0/0, 1/0 hits/fallbacks); mutant DIVERGENCE at frame 20,282 (a byte, not a register: a witnessed match reaches icon slot 3, and D0+1 there is out of 001648's own four-entry table); `camera-sprites` (all thirty-two gates) on the tree of all eight recordings: **PASS, tree bit-exact** | `history-verify fb408bc75597 --candidate record-id-scan` | `artifacts/gods/verify-record-id-scan-fb408bc75597`, `artifacts/gods/verify-record-id-scan-mutant` |
| **`0048E4`/`004ACA` action-table handlers** (`game/actions.py`, part 3 of the trigger firing subsystem blocker): the evaluator's own firing tail dispatches its action through the ROM table at `0046D0` via a tail jump (`jmp (a5)`, `0046CE`, disassembled fresh), so a handler's own `rts` returns straight past the whole evaluator activation -- no seam, no frame. `0048E4` is `clr.l ELAPSED; rts` unconditionally (the elapsed-seconds counter `conditions.py`'s own kinds 9/10 already read); `004ACA` clears whichever of `pickups.py`'s three group active-id words matches a caller record's own `+0x12` word (each of the three has its own `rts`; only the second group is ever witnessed to match). The other action-table entries (`004A0A`, `004D04`, `004E1C`, `004E74`, `0048EA`, `005024`, `00772E`; `004A74`/`005074` unwitnessed) call still-unrecovered helpers (`004AAA`, `004926`, `004ECE`/`004D7E`, `0050A4`, `0077A8`, `004F16`) or write the level grid across several blocks -- an ordinary decline | `factcheck check` on every fixture | `tests/games/gods/test_actions.py` |
| `action-reset-elapsed` and `action-clear-group` reproduce the original on `fb408bc75597…`: **PASS, 34,904 frames, 1 hit each, 0 fallbacks**; segment_verify at boundary-6000/12000 PASS (0 hits both, too rare for a 300-frame window); mutants DIVERGENCE at frames 15,102 and 17,112; `camera-sprites` (all thirty-four gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,047,004 hits, 5,540 fallbacks, tree bit-exact** | `history-verify fb408bc75597 --candidate action-reset-elapsed`; `--candidate action-clear-group`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-action-reset-elapsed-fb408bc75597`, `artifacts/gods/verify-action-clear-group-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-17p` |
| **`0075D6` player state machine shared tail** (the supervisor's Decision, `docs/gods/blockers/2026-09-17-005700.md`): a platform-tail seam, gated where every witnessed state handler and the dispatcher's own 'inactive' arm falls through with no frame of its own; the plan reproduces every fact of the original on 654 retained fixtures (the tile trigger scan, `game.player.tile_trigger_scan`; the follow-point step, `game.camera.follow_point_step` -- FOLLOW_X/FOLLOW_Y eased toward the player's position, X by a fixed step within a 0x50/0xD0 band, Y by half the excess within a 0x70/0x20 band, both clamped; the state-table re-index, `game.player.state_table_reindex`, fully witnessed). **18 Sep: the found-tile arm composed over the evaluator** -- a triggered cell's own status word (`game.player.event_status`, `EVENT_STATUS_WORDS`) that is zero or negative still declines and the scan tries the next cell; a STRICTLY POSITIVE status raises one of `EVENT_HANDLERS` (1-11) through the raiser's own preamble (ten unconditional flag-word checks, real code no recording has ever been seen with any of them set, then the table dispatch itself) -- kind 3 (`00462C`, the trigger evaluator) is now ADMITTED on its own non-firing arm (reusing `evaluator_plan`'s own `_evaluator_resolve`, extracted so both callers share one model), and the scan continues after each admitted raise, up to six per activation; every other kind and the evaluator's own firing/disabled arms still decline by name.  **Later the same day: kind 6 (`0044C0`, the trail check, `game/trail.py`) admitted too** on its own 'found' arm (a bounded six-slot position-history box scan, 891 of 903 occurrences on the main history alone), the SAME composition shape (`_trail_check_resolve`); its own 'exhausted' arm (real code through `007B4C`) still declines by name.  Composing kind 6 surfaced three raiser-level facts the kind-3-only composition never needed (the dispatch's own D0 = `(status-1)*4` residue, D1 = the tile row `game.player.tile_row` sets unconditionally before any raise, A1 = the handler's own address unless a handler overwrites it) and a structural bug (register residue must MERGE across raises, not replace) -- all caught by `factcheck check`'s own byte-exact comparison. 483 of 654 retained fixtures now `MATCH` (up from 161), 171 correctly `DECLINE` | `factcheck check` on every fixture (`MATCH (seam: prefix to 001312, suffix from 0013CE)` or a named `DECLINED`) | `tests/games/gods/test_player_tail.py`, `tests/games/gods/test_player.py`, `tests/games/gods/test_trail.py` |
| `player-tail` reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 21,443 hits, 383 fallbacks (331 firing-arm declines, 158 z80 bank guard, 61 kind-6 exhaustion declines, 47 y-minimum-step declines, 49 seam deadline, small per-kind counts the rest)** -- up from 16,386 hits / 2,891 fallbacks (10 Sep, before this composition); `camera-sprites` (extended to forty-one gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,106,185 hits, 6,607 fallbacks (331 firing-arm declines, 4,478 z80 bank guard, 61 kind-6 exhaustion declines, the kind-6 unwitnessed-event fallback reason entirely gone), tree bit-exact** | `history-verify fb408bc75597 --candidate player-tail`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-player-tail6-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-18l` |
| **`0044C0` trail check** (event kind 6): a caller-register-free leaf saving/restoring all eight data registers around a six-slot position-history ring scan (`TRAIL_HISTORY`, `FFFFF272`), stopping at the first 0x80-wide box that contains the current position ('found'); exhausting all six (real code: a ring shift, a counter, a `007B4C` call) declines | `factcheck check` on every fixture | `tests/games/gods/test_trail.py` |
| `trail-check` (standalone) reproduces the original on `fb408bc75597…`: **PASS, 34,904 frames, 884 hits, 19 fallbacks (12 unrecovered exhaustion, 6 z80 bank guard, 1 observation deadline)**; mutant `trail-check-mutant-result` DIVERGENCE at frame 3,876 | `history-verify fb408bc75597 --candidate trail-check` | `artifacts/gods/verify-trail-check-fb408bc75597`, `artifacts/gods/verify-trail-check-mutant` |
| **a naming collision caught before landing, not by guessing**: this session's own first draft of the raise's own cost constants reused the `_TE_*` prefix already bound to `evaluator_plan`'s own module-level constants (`_TE_TAIL` in particular), silently rebinding it to a wrong value and breaking every `test_triggers.py` fixture -- the SAME class of defect `string-copy`'s own `_SC_`/`_STRCPY_` collision left on 17 September (this file's per-region cost constants share one flat namespace).  Fixed by refactoring the whole composition to share `_evaluator_resolve` (extracted from `evaluator_plan`) instead of reimplementing 00462C's own cost/register model a second time | fixed before commit; `run_tests.py gods` clean | `src/gods_sega/boundary.py` |
| the player tail's negative control (a follow-point byte off; a 'hold'/'hold' occurrence passes through unmutated rather than risk STATE_COUNTER, confirmed once to fault the machine outright) diverges at frame 2,261 on `fb408bc75597…` (unchanged) | `--candidate player-tail-mutant-result` | `artifacts/gods/verify-player-tail5-mutant` |
| **`008222` (with `00837E`) movement-cluster contact search** (the supervisor's Decision, `docs/gods/blockers/2026-09-17-008222.md`): a reentrancy-guarded search over the three collectible lists `pickups.GROUP_TABLES` already names, structurally parallel to `hazard.proximity_search`; three independent sub-passes, each gated by its own list's count word and each retrying up to three consecutive 0x18-byte hit records, with a retry budget (`ITEM_CONTACT_WORD`, the item record's own `+0xA` word) that can also latch a duplicate-suppression flag (`CONTACT_LATCH`) when it is exactly 1; censused over all eight recordings (271 real path classes, `--max-classes 400`) found sub-pass 2's own item DOES reach `ITEM_CONTACT_WORD == 1` (96 fixtures, admitted: the latch is always still clear there, since sub-pass 1's own item never has it) -- only sub-pass 1 itself ever setting the latch, a sub-pass 2/3 match then finding it already set ('gated'), and a sub-pass 2/3 with a negative `ITEM_CONTACT_WORD` ('skip-negative') stay declined, unwitnessed by any recording; costed one instruction-block at a time (every instruction's own cost confirmed data-independent), not per fixed path, so the plan generalizes past the retained fixtures | `factcheck check` on every fixture | `tests/games/gods/test_contact_search.py` |
| `contact-search` reproduces the original on `fb408bc75597…`: **PASS, 794 hits of 800 gates, 6 fallbacks (2 observation deadline, 1 vblank in span, 3 z80 bank guard, all exact adapter refusals, 0 unsupported domain)**; `camera-sprites` (all thirty-six gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,098,065 hits, 14,018 fallbacks (11 at the new gate, all exact adapter refusals), tree bit-exact** | `history-verify fb408bc75597 --candidate contact-search`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-contact-search-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-18f` |
| the contact search's negative control (D0/D3 toggled by XOR 1, not the generic +1 register mutant -- both are always exactly 0 or 1, and the first activation in the whole game is itself a 'not found' occurrence, which +1 cannot flip past zero) diverges at frame 2,284, the first frame the region is exercised | `--candidate contact-search-mutant-result` | `artifacts/gods/verify-contact-search-mutant` |
| **`012DA0`/`012E5A` movement-cluster contact consumers** (the family over the item type `pickups.ITEM_RECORDS` names): once `contact_search` has populated a slot, these two near-identical siblings re-read the SAME list's own count word, look the item record up again and dispatch through a second ROM table (`012C3E`) by its own type field (`ITEM_TYPE_PRIMARY` +0x14 for 012DA0, `ITEM_TYPE_SECONDARY` +0x10 for 012E5A) into a per-type handler -- every witnessed type (1/3/7/9 for 012DA0, 0/2/6 for 012E5A) reduces to a small header plus one of two shared bounded-append bodies (up to three quadruples into the hit record's own three status groups, one shape also filling a pool table); the active-selector override and every other type (real ROM code, seen on the tree's own other seven recordings: 8/10/11/14/15) decline, unwitnessed by the census this session ran | `factcheck check` on every fixture | `tests/games/gods/test_contact_consume.py` |
| `contact-consume-primary` reproduces the original on `fb408bc75597…`: **PASS, 401 hits of 402 gates, 1 fallback (z80 bank guard, exact, 0 unsupported domain)**; `contact-consume-secondary`: **PASS, 243 hits of 246 gates, 3 fallbacks (z80 bank guard, exact, 0 unsupported domain)**; `camera-sprites` (all thirty-eight gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,099,857 hits, 14,156 fallbacks (138 at the two new gates, all exact or declined types, tree bit-exact)** | `history-verify fb408bc75597 --candidate contact-consume-primary`; `--candidate contact-consume-secondary`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-contact-consume-primary-fb408bc75597`, `artifacts/gods/verify-contact-consume-secondary-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-18g` |
| both negative controls (the generic "flip the last write") diverge on the full history but DELAYED -- frame 11,306/11,764 of 34,904, not the region's own first activation (~2,625): every consumer of a hit record's own status groups is itself still-unrecovered ROM, so a corrupted byte is not guaranteed to become video/PCM-observable within a short window; recorded, not solved | `--candidate contact-consume-primary-mutant-result`, `--candidate contact-consume-secondary-mutant-result` | `artifacts/gods/verify-contact-consume-primary-mutant`, `artifacts/gods/verify-contact-consume-secondary-mutant` |
| **`006AD8` (state 24) / `006B14` (state 25) movement-cluster hit states**: the first two movement-cluster states composed over the contact-consume family -- a 3-tick shape (STATE_COUNTER) that calls the already-recovered consumer once on tick 1, falls into the shared tail on ticks 1-2, and transitions to state 14 (copying a tracked position into `grid.GRID_Y`) on tick 3; fully witnessed, no declines | `factcheck check` on every fixture | `tests/games/gods/test_movement_states.py` |
| `state-24` reproduces the original on `fb408bc75597…`: **PASS, 153 hits of 153 gates, 0 fallbacks**; `state-25`: **PASS, 52 hits of 52 gates, 0 fallbacks**; `camera-sprites` (all forty gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,100,252 hits, 14,169 fallbacks (13 at the two new gates, all exact adapter refusals), tree bit-exact** | `history-verify fb408bc75597 --candidate state-24`; `--candidate state-25`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-state-24-fb408bc75597`, `artifacts/gods/verify-state-25-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-18h` |
| both negative controls diverge essentially at the first frame each region is exercised (frame 2,736 vs first occurrence 2,733; frame 3,236 vs 3,233) | `--candidate state-24-mutant-result`, `--candidate state-25-mutant-result` | `artifacts/gods/verify-state-24-mutant`, `artifacts/gods/verify-state-25-mutant` |
| **`00722C` box-overlap scan**: a bounded 200-entry scan against a box around the player's own tracked position, stopping on the first entry whose own box contains it; fully witnessed (every skip/fail/found/exhausted shape), no declines -- but its own result is discarded at both witnessed call sites (states 0 and 1), so it is not yet its own gated candidate (no mutant the game can see until composed) | `factcheck check` on every fixture | `tests/games/gods/test_box_overlap_scan.py` |
| **`007282` state 1**: the player state machine's own dispatch table entry 1, a ~130-instruction decision tree over the already-recovered grid cell, contact search and shared tail; every arm the main history witnesses recovered (two wall transitions, a jump-start to state 9, the movement cascade with its own grid tests and shared sub-body, a contact-search-found hand-off into state 5's own dispatch read, and a STATE_COUNTER already above 7 at the cascade's own reset, witnessed 8 times); only the box-overlap scan (`0072D8`) declines, unrecovered | `factcheck check` on all 1,171 retained fixtures (1,164 MATCH, 7 correctly DECLINE) | `tests/games/gods/test_state1.py` |
| `state-1` reproduces the original on `fb408bc75597…`: **PASS, 3,152 hits, 29 fallbacks (20 z80 bank guard, 7 box-overlap declines, 2 observation deadline)**; `camera-sprites` (all forty-two gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,105,568 hits, 6,703 fallbacks (99 at the new gate, all exact or declined), tree bit-exact** | `history-verify fb408bc75597 --candidate state-1`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-state-1-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-18m` |
| the negative control (d7 off by one -- the generic "flip the last write" mutant crashes the machine on two arms whose own semantic stores are empty) diverges at frame 2,284, the first frame the region is exercised | `--candidate state-1-mutant-result` | `artifacts/gods/verify-state-1-mutant` |
| **`006FFE` state 0**: the "move left" counterpart of state 1, NOT a byte-identical copy -- real differences the tracer found (arm A tests EA20 against the literal 1, not its sign; the bit-0 sub-arm's own EA20-positive case reaches its own three-way grid-byte dispatch state 1 has no analogue of; the cascade's own grid offsets, low-bits threshold and position step are mirrored, not identical; the shared sub-body is its own physical copy whose negative-EA1E arm sign-extends d7 to the full register). Every arm the main history witnesses recovered; only the box-overlap scan (`007056`) declines, unrecovered | `factcheck check` on all 879 retained fixtures (866 MATCH, 13 correctly DECLINE) | `tests/games/gods/test_state0.py` |
| `state-0` reproduces the original on `fb408bc75597…`: **PASS, 2,114 hits, 30 fallbacks (16 z80 bank guard, 14 box-overlap declines)**; `camera-sprites` (all forty-three gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,105,086 hits, 6,812 fallbacks (116 at the new gate, all exact or declined), tree bit-exact** | `history-verify fb408bc75597 --candidate state-0`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-state-0-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-18n` |
| the negative control (d7 off by one, the same shape state 1's own mutant uses) diverges at frame 2,400, the first frame the region is exercised | `--candidate state-0-mutant-result` | `artifacts/gods/verify-state-0-mutant` |
| **`006DA6` state 14**: the player state machine's own vertical-movement dispatcher, over the same recovered pieces as states 0/1 plus its own "settle" tail (a STATE_COUNTER wraparound at 0x14, fresh or carried); the settle tail forks on `FFFFF1AE != 0` (`'probe-f1ae'`/`'loopback'`, a real two-pass case an earlier survey wrongly declined by misapplying state 1's own `007386` dead-code argument) and on `FFFFEA20 != 0` (`'rejoin-main'`, handed back to the SAME EA20 arm dispatch via a shared `_state14_main_dispatch` helper, not re-declined). No arm declines by name. Four real bugs a milestone tree run caught outside the single-history census (204 fixtures, 0 mismatches) but a fresh census over each of the other seven recordings (622 more fixtures) exposed: arm B's own `+0x17F` nibble sub-test, thought unwitnessed (`'nibble-declined'`), actually mirrors arm A's own `+0x181` test exactly (a matched byte reaches `'contact-gate-nibble'`, anything else -- including the low nibble already zero -- falls through to `'transition-0'` directly); `FFFFF1A4`'s own unconditional clear (`006DFA`, runs before the retry-budget compare looks at its own result) was missing from three of arm A's own downstream stores; arm B's own retry counter is never re-cleared past its own budget (unlike arm A's own mirror re-clearing `FFFFF1A6`) and three of arm B's own downstream stores wrongly hardcoded zero instead of carrying the incremented value forward; `006E2A`/`006EA0`'s own `move.w f18e,d0;andi.w #$f,d0` overwrites D0 with the low nibble before either arm's own nibble-tested exit, missed on `'contact-gate-nibble'`; a rejoin-main exit left D7 unset instead of the settle head's own live value; and the settle probe's own 'exhausted' exit assumed grid_cell's own `asl.w` was the last flag-setter when two more MOVEs run afterward. All fixed the same way: a real trace outside the single-history census, never guessed | `factcheck check` on all 1,050 fixtures across all eight recordings (0 mismatches, 0 declines) | `tests/games/gods/test_state14.py` |
| `state-14` reproduces the original on `fb408bc75597…`: **PASS, 1,146 hits, 9 fallbacks (all z80 bank guard)**; `camera-sprites` (all forty-four gates) on the tree of all eight recordings: **PASS, 107,519 frames, 1,106,820 hits, 6,827 fallbacks (29 at the new gate, all z80 bank guard), tree bit-exact** | `history-verify fb408bc75597 --candidate state-14`; `history-verify main --candidate camera-sprites --tree` | `artifacts/gods/verify-state-14-fb408bc75597`, `artifacts/gods/verify-camera-sprites-tree-2026-09-18o` |
| the negative control (d7 off by one, the same shape states 0/1's own mutants use) diverges at frame 2,688, the first frame the region is exercised | `--candidate state-14-mutant-result` | `artifacts/gods/verify-state-14-mutant` |
| the suite: `scripts/run_tests.py gods` (common + Gods), about 68 s | 6,772 tests (9 skipped) | — |

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
`011540`) -- unwitnessed by any of the eight recordings even after the
default 32-class-per-node census cap (which had silently discarded rarer
real classes) was raised.  `AWARD_SCALE_LEVEL` (`FFEF46`, formerly read as
an unwitnessed "message" tail) is recovered (18 Sep): a fresh disassembly
showed no call into any message system at all, just a second, RAM-only
front end for the SAME found-sound/found-bare/found-effect tail (an award
right-shift by `3-level`); a gate scan at the test instruction itself (the
32/400-class census never retained a fixture for it -- the box/scan
arithmetic's own diversity always filled the class budget first) found the
level is 1 on all 104 real occurrences, every one on `7251bbd0ecf7…`; any
other level stays declined, unwitnessed.  Within 013316's own debris burst (whether reached from `00BA8E` or
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

**The player state machine** (`005700`, 29 states over `FFF192`, table
`005618`; assigned 17 September as its own subsystem, `game/player.py`):
named the record fields the dispatcher itself reads (`STATE_INDEX`
`FFF192`, `STATE_COUNTER` `FFF190`/D7, `FROZEN_FLAG` `FFFFEECD`,
`ACTIVE_GATE` `FFFFF210` -- dispatch runs only while this is negative) and
all 29 handler addresses, and found that every witnessed activation
(every state but 7 and 15, unwitnessed on all eight recordings) falls
into a SHARED TAIL (`0075D6`) that is itself an unrecovered subsystem:
the tile trigger scan (`00773A`/`0077A8`, characterised as semantics-only
below -- a leaf when it finds nothing, 43% of occurrences, cascading into
deep unrecovered creature/spawn code otherwise), a camera-relative window
clamp (`FFFFF3EE`/`FFFFF3F0`, not yet disassembled past its own branches),
and a SECOND, distinct inline sprite/tile-upload seam (`001312`,
`0018C8`'s own shape with its own descriptor convention, reached by a
platform-tail `jmp` after the window clamp re-indexes `STATE_TABLE` a
second time).  No state's own composition is admissible until this tail
is: escalated `NEW_GODS_SUBSYSTEM`, `docs/gods/blockers/
2026-09-17-005700.md`.  `tile_trigger_scan` (00773A's own clean arm) is
verified against every one of 406 retained fixtures
(`tests/games/gods/test_player.py`) but not registered as a candidate --
a leaf with no durable effect at all (every register it touches is dead
before the tail's own next instruction, and it writes no RAM) has no
mutant the game can see, so it waits to be composed into whichever of the
tail's own pieces is recovered first.  **Superseded 17-18 September**: the
supervisor's own Decision (below the blocker doc's "Decision" heading)
found the tail is one region of a known shape, not a new subsystem -- a
platform-tail seam, recovered as `player-tail` (see its own evidence rows
above); with the tail admitted, the FIRST states composed over it (1, 0,
14, plus the movement-cluster pair 24/25) are gated too.  `005700` itself
is now the **family over `FFFFF192`** its own Decision predicted: a plain
per-state composite, the same shape `achievement-slot-dispatch` already is
over `0047DA`/`004800` -- see its own semantic-operation card below.

### `005700` semantic-operation card

Per `docs/common/recovery-process.md`'s own card fields, now that the
dispatcher owns real persistent state, calls into several now-recovered
subsystems and has become a genuine composite candidate boundary (not a
small leaf):

- **Semantic operation**: read the player's own `STATE_INDEX`
  (`FFFFF192`) and `STATE_COUNTER` (`FFFFF190`, D7 on entry), dispatch
  through the 29-entry ROM table `005618` to the correspondingly-indexed
  state handler body, and -- for every witnessed state but 7 (a bare
  `rts`, unwitnessed) -- fall through unconditionally into the shared
  tail (`0075D6`, already its own recovered candidate, `player-tail`).
- **Entry/exit boundary**: entry `005700` with the machine parked at the
  dispatch's own read of `FFFFF192`, gated only while `FFFFF210`
  (`ACTIVE_GATE`) is negative and `FFFFEECD` (`FROZEN_FLAG`) permits it.
  Exit is either state 7's own bare `rts` (never witnessed) or a
  `bra.w $75d6` into `player-tail`'s own already-armed gate -- the SAME
  "one gate hands off to a separately-armed gate" composition every
  recovered state (1, 0, 14, 24, 25) already draws.
- **Persistent state**: `STATE_INDEX`/`STATE_COUNTER` themselves, plus
  each handler's own state-specific fields (`POSITION_X`/`POSITION_Y`,
  the vertical states' own `FFFFF1A4`/`F1A6`/`F1A8`/`F1AA`/`F1AC`/`F1AE`/
  `F1B0`/`F1B2` retry/settle counters, the movement flag `FFFFF182`) --
  all named per-state in `game/player.py`, none owned by the dispatch
  itself. `FFFFEA1E`/`FFFFEA20`/`FFFFEA23` (pad-intent words) are READ by
  every state but owned further up the input pipeline, not here.
- **External observations**: none of its own. The dispatch and every
  handler are RAM-only; the only platform interaction anywhere in the
  family is inside the ALREADY-recovered shared tail's own ceded sprite
  upload (`001312`) and whatever a raised tile-trigger event's own
  still-unrecovered cascade eventually touches.
- **Pending effects**: none synchronous. A handler's own transition
  (`STATE_INDEX`/`STATE_COUNTER` written this tick) becomes durable the
  next tick this SAME dispatch re-reads `FFFFF192` -- no request is left
  pending across a commit boundary.
- **Permitted interference**: not yet proven for the family as a whole.
  Each recovered state's own negative-control mutant (a `STATE_COUNTER`
  bit flip) is independently confirmed observable through the shared
  tail's own unconditional store at `0075D6`'s own first instruction, but
  no cross-state VBlank-slide-style proof has been attempted for the
  dispatch itself (whether a handler could run one tick later or earlier
  without changing the future) -- deferred, since no candidate needs it
  yet (every recovered state is still gated as an exact L0 region).
- **Proven movable events**: none -- a synchronous per-tick dispatch,
  not an event queue; there is nothing here to reorder.
- **Required ordering boundaries**: the dispatch's own read of
  `FFFFF192`/`FFFFF190` must precede the handler body it selects; a
  handler's own RAM writes must be visible to the SAME activation's own
  tail composition, since several handlers (states 1/0's own
  contact-search-found arms) hand off at `pc = 0x0075DA`, one instruction
  INTO the tail, not a fresh `0075D6` activation -- the boundary a
  handler's own plan draws must match exactly which of the tail's own
  instructions it is skipping.
- **Timing dependency**: none beyond the ordinary once-per-tick call
  every recovered handler already costs from the tracer; no duration
  model has been needed by any state composed so far.
- **Evidence and scope**: a full-history `FFFFF192` tally (all eight
  recordings, since `recovery_census.py`'s own path-signature classifier
  explodes on this dispatcher, `docs/gods/blockers/2026-09-17-005700.md`'s
  own "What was tried") names every state's own frequency on
  `fb408bc75597…` (34,904 frames, 13,488 activations): 1 (3,086), 0
  (2,024), 5 (1,492), 14 (1,155), 6 (950), 9 (796), 26 (634), 8 (601), 13
  (476), 12 (321), 16 (254), 20 (194), 19 (190), 11 (169), 2 (167), 3
  (167), 24 (153), 4 (150), 17 (145), 21 (137), 18 (63), 25 (52), 28
  (38), 22 (36), 27 (19), 23 (13), 10 (6); states 7 and 15 unwitnessed on
  any of the eight recordings. Gated so far: state-1, state-0, state-14,
  state-24, state-25, state-5, state-6, state-9, state-26, state-8,
  state-13, state-12, state-16, state-11, state-2, state-3, state-4,
  state-17, state-21, state-28, state-22, state-27, state-23, state-10
  -- 11,012 of 13,488 activations (82%)
  directly reproduced by their own candidate, every remaining activation
  still running the original but reaching the ALREADY-recovered
  `player-tail` gate one level in.  State 5 (`00746A`, a real sibling of state 1 sharing code
  both ways, "one region, two gates, one planner") and state 6 (its own
  mirror, sharing state 0's own hand-off the same way) are both plain
  leaves composed over the already-recovered contact-consume family;
  state 9 (`0066A8`), state 26 (`0069AC`, a near-twin reusing state 9's
  own jump-arc table and row-gate leaves verbatim) and state 8
  (`00648C`, state 9's own sibling, recovered 18 Sep -- two of its own
  five arms byte-identical to state 9's own ROM code, confirmed against
  the ROM; four real differences: its own resting D7 value (6, not 5),
  its own block-test gate (low5 == 0, not < 8, checking the LEFT
  neighbour's offsets) with one fewer instruction, its own
  ground/landed/trigger targets (states 17/11/21, not 16/12/20) and its
  own re-check gate (0x12, not state 9's 0x16); and its own 'landing-13'
  arm IS witnessed here, unlike state 9's own declined one) are a shared
  falling/jump-arc shape (`game.player._row_gate_open`, the same gate
  test state1_step's own uses, parameterised on the row bias); state
  26's own tail hands off directly into state 9's own gate the same
  "separately armed gate" way state 5/6 hand off to state 1/0.  State 13
  (`006B4E`, recovered 18 Sep) is state 14's own counterpart: its
  contact-search gate (`006C62`-`006CC5`) is byte-identical to state 14's
  own (`006EC4`-`006F27`) and reuses the SAME shared composition
  (`_state14_contact_cost`/`state14_contact`/`state14_contact_found`);
  its two jump-start tails (`0x6FB8` into state 8, `0x6FDA` into state 9)
  are the SAME physical ROM addresses state 14's own arm A/B jump into.
  Real differences: no `FFFFF1B0` store and no separate `FFFFEA1E`-sign
  gate before the `FFFFEA20` dispatch (the "settle, carrying" hand-off
  folds into the `FFFFEA20 == 0` arm itself); arm A/B's own jump-start
  gate is `FFFFEA1E`'s SIGN (not state 14's own `FFFFEA23` bit 0, and arm
  A's own `'transition-9'` is unwitnessed by any of the four recordings
  that reach state 13 at all, declined); arm D's own toggle gate is
  `FFFFEA1E >= 0` / `< 0` (a sign test, not state 14's own exact `== 1`),
  toggling INTO state 14 (the mirror of state 14's own toggle into 13);
  and the settle tail's own retry probe produces two real transitions
  (states 26/10), unlike state 14's own "always exits unchanged or
  loops" shape -- and, unlike state 14's own register-based -6 step
  (saved/restored via `FFFFF1B2`), state 13's own `addq.w #6,f18e.w` is
  an unconditional MEMORY add, so `POSITION_Y` stays at the advanced
  value even on the "exit unchanged" arm.  State 12 (`005FF4`, recovered
  18 Sep) is a genuinely NEW shape -- an oscillating swing/pendulum
  dispatcher, not a horizontal/vertical/falling twin of anything already
  recovered -- sharing the already-recovered grid cell and contact
  search and, for the first time, RAM the zone check's own routine also
  reads (`game/zones.py`'s `COOLDOWN`/`SUPPRESS_COOLDOWN`,
  `FFFFEF3E`/`FFFFF1B6`; state 12 shares the fields, not the routine).
  Its own oscillation head runs unconditionally every activation
  (`FFFFF198`, a tick counter, advances TWICE per tick -- once by the
  OLD `FFFFF194`'s own value shifted right 2, again by a plain +1 after
  `FFFFF194` itself bumps/caps at 10 -- a real defect the FAST tier
  caught: the first addition was missing entirely from an early draft);
  an `FFFFEA20`-gated block test (`== -1`, a LEFT arm provisionally
  setting state 11 -- witnessed only via a real 120-frame continuation
  from a retained fixture, never by any single-tick census entry, since
  605 real census path classes across all five recordings never
  happened to land on it; captured directly from that continuation and
  retained as its own fixture -- or `== 1`, a RIGHT arm provisionally
  setting state 12 itself) may step `POSITION_X`; the tail re-reads the
  grid cell and either finds ground (state 16, with a genuine three-way
  `COOLDOWN`-adjustment tail: exit unchanged within the tick gate, exit
  suppressed, or halve the excess into `COOLDOWN`), opens a trigger gate
  into the already-recovered `contact_search` (state 22), or exits
  unchanged.  Real defects the FAST tier caught before the tree: the
  missing SECOND `FFFFF198` addition above; two word-branch cost tables
  transcribed backwards (`btst`'s own `beq.w`, the search's own
  `bne.w`); a missing detour cost when the right arm's own retry budget
  is open but its own block test is skipped outright; a missing
  `POSITION_X` register update after that same skip; a missing
  `POSITION_Y` write on the ground tail's own "exit unchanged" sub-arm
  (`FFFFF18E`'s own `+6` advance is an unconditional MEMORY write, not
  state 14's own register-based, saved/restored step); and two `D0`
  register updates missing after the tick/cooldown arithmetic overwrites
  it.  State 16 (`006686`, recovered 18 Sep) is a tiny two-step "settle
  then countdown" leaf -- the target both state 9's own "ground-before"/
  "ground-after" arms and state 26's own mirror transition into
  (`_state9_ground_stores`): `FFFFF1B8 == 0` increments it and exits
  unchanged (a one-tick delay); `FFFFF1B8 != 0` decrements `FFFFF198` by
  4, exiting unchanged while non-negative or transitioning to state 1
  (`d7` forced to 2) once it goes negative.  391 real path classes
  across all five recordings collapse to exactly three real terminal
  shapes; the only defect the FAST tier caught was a word-branch cost
  table transcribed backwards (`bpl.w`, the same class of bug states
  12/16's own sessions kept finding).  State 11 (`005D32`, recovered 18
  Sep) is BYTE-IDENTICAL to state 12's own oscillation head and
  `FFFFEA20`-gated block test -- confirmed via a raw ROM diff,
  `rom[0x005D32:0x005E28] == rom[0x005FF4:0x0060EA]`, differing only in
  relocated branch-displacement bytes, down to the LEFT/RIGHT arms' own
  hardcoded provisional `STATE_INDEX` values (0xB/0xC, unchanged, since
  those ARE this dispatcher's own pair of table indices); the ground
  tail's own four stores are the same instructions, just reordered in
  the ROM (`clr f1b8`/`moveq d7`/`move fdf6` BEFORE `andi f18e`, unlike
  state 12's own `andi`-second order), targeting states 17 (ground) and
  23 (trigger) instead of state 12's own 16/22. Every `_S12_*`/`_S12G_*`
  cost constant is reused verbatim; no new defects, since none of state
  12's own nine were specific to its own address range. The LEFT arm
  (`FFFFEA20 == -1`) was, again, invisible to the whole-history census
  (693 real path classes across all five recordings never landed on it)
  and needed the same targeted 120-frame `segment_verify` continuation
  capture as state 12's own.  State 2 (`0074F0`, recovered 18 Sep) is
  another tiny three-arm leaf, the SAME shape as state 16's own "settle
  then countdown": `FFFFEA20 < 0` transitions straight to state 3;
  otherwise a counter (`d7`) counts up and, once it reaches 3, forces
  `d7` to 6 and transitions to state 1.  269 real path classes across
  all five recordings collapse to exactly three real terminal shapes.
  One real defect the FAST tier's own `--perturb-upper-halves` pass
  caught (the plain sweep alone missed it, every witnessed `d7` already
  having a clean upper half): the counting arm's own `addq.w` is a WORD
  op, so the real ROM leaves `d7`'s own upper 16 bits untouched, but an
  early draft returned the masked 16-bit result as the FULL 32-bit
  register, clobbering it -- the transition arm's own `moveq`, by
  contrast, is a real 32-bit LONG move and correctly clears the upper
  half both ways.  State 3 (`007516`, recovered 18 Sep) is a mirror of
  state 2's own shape one step further into the `FFFFEA20`-driven cycle:
  `FFFFEA20 == 1` transitions to state 2 (real ROM, UNWITNESSED by any
  of 270 retained fixtures, declined by name); otherwise a counter
  (`d7`) counts DOWN (state 2's own counts up) and, once it goes
  negative, is forced to 6 and transitions to state 0 (state 2's own
  transitions to state 1).  No defects this time -- the upper-half
  lesson from state 2's own `moveq` vs `addq.w` distinction carried
  straight over.  State 4 (`007538`, recovered 18 Sep) is a genuinely
  different shape: `FFFFEA20 == 0` jumps DIRECTLY into state 15's own
  entry (`006D68`, the STATE_TABLE's own index-15 address) via a plain
  `beq.w`, the SAME "one region, two gates" shared-fallthrough shape
  states 5/6 already use into 1/0 -- the FIRST real evidence of state
  15's own semantics, though state 15 remains unwitnessed as an
  independent dispatch (no recording has ever shown `FFFFF192 == 15`
  directly).  State 15's own body, as reached this way, re-runs the
  already-recovered grid cell lookup (`0063FA`) and tests its own ground
  byte: found exits unchanged (`d7` untouched, no `FFFFF192` write at
  all); NOT found is real ROM this session did not trace further and
  declines by name.  `FFFFEA20 != 0` transitions to state 3 (`d7` forced
  to 0) when negative, or state 2 (`d7` forced to 2) when positive.  81
  real path classes across all five recordings collapse to exactly three
  real terminal shapes.  State 17 (`006666`, recovered 18 Sep) is the
  SAME "settle then countdown" shape as state 16's own, transitioning to
  state 0 instead of state 1 once `FFFFF198` goes negative (`d7` forced
  to 2, the same value state 16's own transition uses) -- not
  byte-identical to state 16's own code (the final store is `clr.w
  f192.w`, not a `move.w #imm`), so costed with its own constants.  298
  real path classes across all five recordings collapse to exactly three
  real terminal shapes.  No defects.  State 21 (`006886`, recovered 18
  Sep) is a genuinely large, three-way hybrid: state 9/26's own jump-arc
  fall step (the SAME shared table `006414`, `_row_gate_open`, reused
  verbatim) combined with state 12's own LEFT block-test gate
  (`FFFFF18C & 0x1F == 0`, offsets -1/0x7F/0xFF, not state 9's own `< 8`
  gate); the head is `FFFFF1BA`-gated exactly like state 26's own
  (`_state26_head`'s own shape, but a genuinely separate ROM copy,
  confirmed by a raw ROM diff); TWO ground-ahead probes, gated by state
  9's own `STATE9_TRIGGER_GATE` (0x16, the first) and state 26's own
  recheck value (0x12, the second) -- a hybrid pairing neither existing
  state uses; and a THIRD real composition, a `jsr` into the already-
  recovered movement-cluster consumer `012E5A` (not state 26's own
  `012DA0`) when the post-head `d7` counter is exactly 1.  The X-advance
  has no `FFFFF19C` gate at all, unlike state 9's own gated version.  The
  doubled fall step (`FFFFF19E != 0`) is modelled directly (a second,
  identical subtraction) rather than declined, since the adjacent ROM
  code for it is trivial, not a guess.  448 real path classes across all
  five recordings collapse to five real terminal shapes; the "D7 < 3, !=
  1" tail's own cap-override (`006994`) is real ROM, unwitnessed, and
  declines by name.  No defects: every composition (`_row_gate_cost`,
  `_cc_resolve`, `GRID_CELL_COST`) was already fully tested by states
  9/26's and the movement-cluster's own earlier sessions, and reusing
  them directly caught every fact on the first attempt.  State 28
  (`005828`, recovered 18 Sep) is the smallest leaf yet: an
  UNCONDITIONAL transition to state 1, `d7` forced to 2, no input ever
  read.  All 71 real path classes across all five recordings agree.
  State 22 (`0062B0`, recovered 18 Sep) is state 21's own `FFFFF1BA`-
  gated head in front of state 12's own ENTIRE oscillation body and BOTH
  block tests, reused verbatim (byte-for-byte the same masks, offsets and
  immediates as state 12's own); a genuine ground-found jump lands on
  the SAME PHYSICAL ground-tail code state 12's own uses (`006134`-
  `006160`, not a relocated copy).  One real, confirmed difference from
  state 12's own: the ALT ground test's own mask is `FFFFF18C & 0x1F`
  here, not state 12's own `0x1C`.  The tail (once neither ground test
  finds anything) is D7-based: exactly 3 transitions to state 12 (`d7`
  forced to 0); exactly 1 calls the already-recovered movement-cluster
  consumer `012DA0` before exiting unchanged; any other value exits
  unchanged directly.  91 real path classes collapse to six real
  terminal shapes.  Two word-branch cost tables transcribed backwards
  (the SAME recurring bug class) were the only defects; one real,
  useful finding along the way: this candidate's own mutant (dropping
  `012DA0`'s own writes wholesale) corrupts a linked-list-style record
  the real game dereferences a few frames later, causing a genuine
  M68000 address error rather than a clean value mismatch on one
  fixture -- `history-verify`'s own crash-tolerant comparison already
  reports this cleanly as DIVERGENCE; `segment_verify`'s own lighter
  check does not, so the test catches the native exception directly.
  State 27 (`00581E`, recovered 18 Sep) is another unconditional leaf,
  the SAME shape as state 28's own: always transitions to state 0
  (`clr.w f192.w`, not state 28's own `move.w #1,f192.w`), `d7` forced
  to 2, no input ever read.  All 55 real path classes across all five
  recordings agree.  State 23 (`006164`, recovered 18 Sep) sits
  IMMEDIATELY BEFORE state 22's own code in ROM and is structurally
  identical to it (the same oscillation, the same LEFT/RIGHT block
  tests, the same ALT ground test with its own 0x1F mask), but the
  ground-found jump lands on state 11's own PHYSICAL ground tail
  (`005E6C`, not state 12's own `00612E`) and the D7-based tail differs
  in its own two targets: exactly 3 transitions to state 11 (not state
  22's own state 12); exactly 1 calls the already-recovered movement-
  cluster consumer `012E5A` SECONDARY (state 21's own choice, not state
  22's own `012DA0` PRIMARY).  34 real path classes collapse to five
  real terminal shapes.  No defects: every `_S22_*`/`_S12_*`/`_S12G_*`
  cost constant was reused directly, confirmed byte-identical via a
  direct disassembly, and caught every fact on the first attempt.  State
  10 (`005EA2`, recovered 18 Sep, the LAST witnessed state in the
  coordinator's own frequency-order list) is state 12's own oscillation
  head and BOTH block tests, reused verbatim, but with NO `FFFFF1BA`-
  gated head this time (state 10 goes straight into the oscillation) and
  its own, genuinely NEW ground tail (`005FBC`-`005FF0`, not a jump into
  any already-recovered state's own shared code): `STATE_INDEX` is set
  to 0x11 unconditionally, then conditionally DECREMENTED to 0x10 when
  `FFFFF1A8` is non-negative -- a mechanic no other state's own ground
  handling uses.  The cooldown adjustment's own three sub-cases (exit
  within the tick gate, suppressed, apply) all converge on the SAME
  single exit (`d7` forced to 0, the sound cue queued into
  `pickups.MOVEMENT_SOUND_CUE`, unlike state 12's own three separate
  exits where the first two skip both).  No D7-based trigger/consume
  tail either: failing to find ground exits unchanged directly.  22 real
  path classes across all five recordings collapse to two real terminal
  shapes.  Two real defects: the RIGHT arm's own gate test
  (`cmpi.w #1,ea20.w`) was missing its own cost entirely (copied from a
  template that already had it inlined into the `if`, an easy one-line
  omission caught immediately by the plain factcheck sweep); and the
  ground tail's own final sound cue used `hazard.SOUND_COMMAND` (FDF4,
  the oscillation head's own cue) instead of `pickups.MOVEMENT_SOUND_CUE`
  (FDF6, the actual target `005FEA move.w #$39,fdf6.w` writes).  State 10
  was the LAST state in the coordinator's own frequency-order list
  (8, 13, 12, 16, 20, 19, 11, 2, 3, 4, 17, 21, 18, 28, 22, 27, 23, 10):
  every witnessed state on that list now has its own gated candidate,
  including 19 and 18 (recovered 18 September, resolving the blocker
  below); state 20 needed no work of its own (already `state-26`).
  States 7 and 15 remain unwitnessed by any of the eight recordings and
  decline by name; nothing in this session found evidence either is ever
  reached.  Every witnessed `005700` activation (13,488 of 13,488,
  `fb408bc75597`'s own tally) is now directly reproduced by its own
  candidate.
- **Resolved** (18 September, same session): `docs/gods/blockers/2026-09-18-005886.md`
  -- state 19 (`005886`, 190 occurrences) turned out NOT to be a same-recipe
  leaf like 8/13/12/16/11: a ten-terminal-shape state spanning at least
  three subsystems (an inline copy of the already-recovered
  `game.movement.box_overlap_scan`, here with its result actually
  consumed, unlike its own twin's two witnessed call sites; a new leaf
  `005CEE` that corrects a belief this session held about
  `game.achievements.ACHIEVEMENT_SLOTS`/`HIGHLIGHT_ID` -- both fields are
  shared beyond the achievement tracker, not owned by it; and a wholly new,
  unrecovered leaf `010D7C`, independently flagged two days earlier from
  `010CD2`'s own investigation), comparable in scope to states 0/1/14's own
  dedicated sessions.  State 18 (`005834`, 63 occurrences) turned out to
  be additional scope inside this SAME blocker, not a separate one: its
  own short head calls the SAME `005CEE` leaf and several of its own
  retained fixtures' terminal PCs are the IDENTICAL addresses state 19's
  own are, evidence of a shared-fallthrough jump into state 19's own body
  (the same "one region, two gates" shape states 4/15, 5/1, 6/0 already
  established), not a duplicated copy (a raw ROM diff of the two heads
  shows they are NOT byte-identical the way states 11/12 or 8/9 are).
  Both states recovered together, in the end, rather than deferred
  further: the box-overlap-scan copy, `005CEE` (`game.achievements.
  achievement_highlight_cycle`) and `010D7C` (`game.spawns.
  floating_icon_spawn`) are all recovered, tested (`tests/games/gods/
  test_state19.py`) and verified (factcheck check MATCH on all 190 + 118
  retained fixtures, including `--perturb-upper-halves`; segment_verify
  PASS; history-verify PASS on `ca2b703b6fd5` for both, 14,583 frames,
  59/57 hits, 1/0 fallbacks; mutant `_mutate_register` DIVERGENCE at
  frames 5,491/8,039 -- `_mutate_outcome`, every other player state's own
  mutant, faults the M68000 here by corrupting a seam's own return
  address, the first player-state candidates for which that shape
  matters).  State 19 took `camera-sprites`' own last gate slot (the
  native machine caps the gate set at 64, PortForge, pinned); state 18
  stays a fully recovered, individually verified standalone candidate.
  State 20 is already gated (a real STATE_TABLE reconstruction from
  `005700`'s own dispatch code, 18 Sep, found `FFFFF192 == 20` reaches
  `0069AC`, the entry the existing `'state-26'` candidate already owns
  end to end; the candidate's own name is a misnomer left as a fact for a
  future session, not acted on -- nothing it proves is wrong, since every
  gate, fixture and test is keyed by the PC, not the name).  States 7 and
  15 decline by name (unwitnessed) until a recording exercises them.  The
  full `STATE_TABLE` (`005618`, 8-byte entries, address at `+4`) is in
  `ledger.md`'s own 18 September entry.  Every witnessed state now has
  its own gated candidate: `005700` is complete as a plain per-state
  composite, the same shape `achievement-slot-dispatch` already is over
  `0047DA`/`004800`.

  **Composed, 18 September (later the same day):** the family itself,
  `player_state_plan` (candidate `'player-state'`, armed inside
  `camera-sprites`) -- the dispatcher's own prefix now owns the jump into
  each recovered state's own planner directly (the same "call the
  callee's own planner, prepend this region's own cost" shape
  `achievement_slot_dispatch_plan` already draws over
  `achievement_slot_reset_plan`), and the 25 individual player-state
  gates this candidate used to arm are retired from its own gate set
  (their own hits replaced by this one dispatcher's; their own standalone
  candidates, gates and tests are untouched).  `camera-sprites` drops
  from sixty-four to forty gates net.  Building the dispatch table
  surfaced the misnomer above as a genuine gap, not merely a naming
  fact: real `STATE_TABLE` index 26 (ROM `005724`) has never been
  recovered as its own leaf -- the `'state-26'` candidate targets index
  20 (`0069AC`), not 26.  Declined here by the same rule as 7/15 (real
  ROM, no candidate, not guessed), and confirmed still real and
  frequently witnessed: 6 of the retained `census-005700-fb408bc75597`
  fixtures reach it, and a full cold run of `ca2b703b6fd5` shows 314 of
  366 fallbacks are this decline (the coordinator's own tally already
  named it the seventh most frequent state, 634 of 13,488 activations).
  Milestone tree PASS (18 Sep, `artifacts/gods/verify-camera-sprites-leaves-2026-09-18t`):
  107,519 frames bit-exact; fallbacks 8,857, of which 1,975 were the
  state-26 decline (second only to 4,468 z80 bank guard).

  **Resolved, later the same day**: real STATE_TABLE index 26 (`005724`)
  is recovered -- `game.player.state_26_step`/`state_26_box_scan`/
  `state_26_actor_scan` (named with an underscore, `state_26_*`, to stay
  distinct from the pre-existing misnomer's own `state26_*` at `0069AC`,
  which is renamed `'state-20'` in `recovery.py`; the gate PC and every
  fixture/test there are unchanged), `boundary.state_26_plan`, folded into
  `_PLAYER_STATE_PLANNERS` and wired as its own standalone candidate
  `'state-26'`.  Four top-level arms (an unconditional transition to
  state 27/28; a bounded 200-entry actor scan over the already-recovered
  `game.movement.BOX_SCAN_TABLE` through `achievements.RECORD_TABLE` and
  `conditions.FLAGGED`; a plain fallthrough into state 15's own shared
  body, factored out of `state4_plan` into `_state15_ground_probe` so both
  callers share it; a 20-entry proximity table distinct from
  `BOX_SCAN_TABLE`, then a grid-cell-driven transition to state 14) --
  see `ledger.md`'s own 18 September entry for the full arm/count
  breakdown.  Milestone tree PASS (`tree-26-leaves-2026-09-18`, standalone
  gate): 107,519 frames, 1,883 hits, 92 fallbacks (22 z80 bank guard, 70 a
  narrow, never-witnessed sub-decline).  `camera-sprites` re-sealed for
  the shared-helper edit: PASS, 107,519 frames, bit-exact, fallbacks 8,857
  -> **6,970** (`artifacts/gods/verify-camera-sprites-leaves-2026-09-18u`).
  No further card revision needed unless a later state surfaces persistent
  state or platform interaction this card does not already cover.

- **19 September, grinder session opening on the `0030CC` assignment**
  (`docs/gods/blockers/2026-09-19-0030CC.md`): its own first bite,
  `004926`, is recovered -- not merely the "RECORD_TABLE scan" the
  assignment's own reconnaissance named, but a box-scan puff spawner.  A
  full-tree census (`--entry 0x004926`, all five recordings, 22 retained
  fixtures; the fifth recording never reaches it) showed the routine's
  own head first finds the spawn queue's own first free slot
  (`spawn_queue.SLOT_BASE`, `0049DA`'s own four slots -- every slot
  occupied is real ROM, the routine's own fallback overwrites the last
  one regardless, never witnessed, declined by name); then walks the SAME
  200-entry `movement.BOX_SCAN_TABLE` the box-overlap scan and `0030CC`
  itself share, each active entry's own `+4` word doubling as an
  `achievements.RECORD_TABLE` index (the SAME double/double/double
  ADDA.W arithmetic `achievements._record_address` already models --
  reused verbatim, not reimplemented) whose own record status of 4 and a
  caller-supplied box (`d0`-`d3`) select up to two consumes per
  activation (a second consume's own early exit, `0049D4`, is real ROM,
  never witnessed by any of the 22 fixtures -- every one finds 0 or 1 --
  declined by name); each consumed entry is marked spent and queued into
  the spawn queue's own next free slot (`x - 8`, raw `y`) with a sound
  cue (`FDF4 = 0x3D`).  One entry's own record header of exactly `0x60`
  takes a second, unwitnessed shape (the QUEUED `y`, not the register,
  also adjusted by `-8`) and stays declined by name too.
  `game.spawn_scan.{find_spawn_slot,scan_and_spawn}`;
  `gods_sega.boundary.spawn_scan_plan`; candidate `'spawn-scan'`.  Two
  real callers reach it (`0048EA`, one of the trigger evaluator's own
  action-table handlers, three of five witnessed firings per
  `docs/gods/blockers/2026-09-16-00462C-firing.md`; and a second,
  unrelated one at `0139D2` inside the collectible-lists subsystem,
  `tick-map.md` order 14) -- NEITHER is recovered, so this leaf is
  verified stand-alone and assumes nothing about either caller.  Writes
  are ordered so the negative control's generic "flip the last write"
  lands on the puff's own durable spawn-queue position, not the scratch
  match counter or the sound cue.  `factcheck check` (22 fixtures) and
  `--perturb-upper-halves` both clean; `run_tests.py gods` (23,059
  passed, 12 skipped).  `camera-sprites` extended to fifty-five gates (a
  new leaf, not a composition: both real callers are still original
  execution).  Reproduces the original on `f0ac19738f19…` (the shortest
  exercising leaf, five hits): PASS, bit-exact; mutant
  `spawn-scan-mutant-result` DIVERGENCE at frame 1019.  Next, per the
  assignment's own order: `0048EA` itself over it (a small leaf: reads
  the caller's own record position at `+0xC`/`+0xE`, one rare
  position/flag substitution gated on `hazard.TRIGGER_COUNTER`, builds a
  ±12 box, calls `spawn_scan` -- disassembled but not yet censused), then
  `003186`'s body and `003284` for the object table update itself, then
  `004926`'s own sibling bite (`0048EA`'s own reachability into the
  evaluator's firing arm as a 6a family).

- **19 September, same session, continuing the `0030CC` assignment**:
  `0048EA` itself is recovered too -- composes `spawn_scan_plan` (004926)
  as a real internal `bsr`, not a seam and not a `_ConstMachine` overlay:
  the prefix (read the record's own position, the substitution test, the
  box arithmetic) never touches RAM, so the live machine is unaffected
  between 0048EA's own entry and the point of "parking" at 004926 for the
  inner call.  A rare position/flag substitution (`x == 0x6CC`, `y ==
  0x3C0`, a global long reading exactly 1) is real ROM, never witnessed by
  any of the 17 retained fixtures (four of the five recordings; the fifth
  never reaches it), declined by name.  One real defect
  `--perturb-upper-halves` caught: `d2`/`d3` are freshly `MOVEQ`'d before
  the box add, so their own exit upper half is always 0, never the
  caller's entry value, unlike `d0`/`d1`'s plain `MOVE.W` load from the
  record.  `game.actions.spawn_puff_box`; `gods_sega.boundary.
  spawn_puff_box_plan`; candidate `'spawn-puff-box'`.  `factcheck check`
  (17 fixtures) and `--perturb-upper-halves` both clean; `run_tests.py
  gods` (23,081 passed, 12 skipped); `camera-sprites` extended to
  fifty-six gates (`SPAWN_SCAN_ENTRY` stays armed too -- it still has a
  second, real, unrecovered caller at `0139D2`).  Reproduces the original
  on `f0ac19738f19…`: PASS, 5 hits, 0 fallbacks, bit-exact; mutant
  `spawn-puff-box-mutant-result` DIVERGENCE at frame 1019.  Milestone tree
  PASS on all five leaves (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-spawnpuffbox`,
  107,519 frames).  With this, both of the `0030CC` assignment's own
  reconnaissance callees for the evaluator's firing arm are recovered;
  what remains of that assignment: the evaluator's firing arm itself (the
  6a family over the record's own `+10` word, removing the 331 declines
  at `00462C`) and the object table update `0030CC` itself (`003186`'s
  body and `003284`, then the 200-slot scan composing it with the phase
  counters and the tail).

- **19 September, later the same session, closing the `NEW_GODS_SUBSYSTEM`
  escalation on the evaluator's own firing arm**: the trigger evaluator's
  firing arm (`00468A`-`0046CE`) is recovered as the recipe-6a family
  `docs/gods/blockers/2026-09-16-00462C-firing.md`'s own Split predicted,
  now that its three real callees (`004926`, `0048EA`, `004AAA`) all
  exist.  `_evaluator_resolve` (shared with `player_tail_plan`'s own
  composed raise) gained an `allow_firing` parameter -- default `False`,
  so `player_tail_plan` still declines the firing arm exactly as before
  (146 declines on this tree, all at its own gate, unchanged) -- passed
  only by `evaluator_plan` itself, which now composes the whole tail
  through a new `_firing_tail_plan`: a message preamble (`game.triggers.
  firing_message_address`, a two-step indirection through work RAM at
  `FFFFAD0E`, NOT the ROM table the original Split assumed -- `$AD0E`
  sign-extends to a work-RAM address; 54 of 360 freshly-censused
  occurrences carry a real message, all `'ready'`, never `'blocked'`)
  composing `message_gate_plan`/`string_copy_plan`; the two unconditional
  calls composing `record_id_scan_plan`/`slot_scan_plan` (either can
  itself reach an unmodelled achievement seam -- declined by name); the
  tail-jump dispatch (`game.triggers.firing_action_target`, the record's
  own `+0x10` word doubled twice, unmasked, bounded to the table's own 60
  bytes) admitting the table entries whose own handler is recovered, by
  ROM address: `0048E4`, `004ACA`, `0048EA`, the three `00475C` bare-`rts`
  entries, and a NEW leaf, `004A0A` (`'spawn-effect-slot'`, table index 0
  -- the SAME record position/substitution `0048EA`'s own head performs,
  then the record's own `+0x12` type word selecting one of three real
  terminal shapes over a found `004AAA` slot: `'in-range'` (`0x40`-`0x43`,
  immediate exit), `'bset'` (exactly `0x53`, also sets `player.
  PROXIMITY_BUSY`'s own bit 2 -- real ROM, never witnessed, declined), or
  `'tail'` (an x/y/type cache write) -- 32 fixtures across four of five
  recordings, all MATCH).  Every real action index the table holds that
  is NOT yet recovered (`2`, `3`, `5`, `7`, `9` -- `004E1C`, `004D04`,
  `00772E`, `005024`, `004E74`) declines by name.  Real defects the FAST
  tier caught in turn: the AND tail's own `d0` (the three-condition AND
  result) is NOT dead on the firing path (unlike non-firing) -- `00468E`'s
  own `movem` push saves it before the message preamble ever reloads
  `d0` -- and needed threading from EVERY condition call's own dispatcher
  residue, not just the AND result; record id scan's own `d5` (the masked
  action word) persists into the dispatch and any composed handler,
  needing a running `live` register dict threaded through each internal
  call rather than a fixed baseline; and the bare-`rts` arm's own exit SR
  is the dispatch's own three flag-setters (`MOVE`, two `ADD.W`
  doublings), not whatever flowed in from `slot_scan_plan`.  `factcheck
  check` (360 fresh fixtures across all five recordings) and
  `--perturb-upper-halves` both clean: 280/274 MATCH, 0 MISMATCH, the
  rest honest declines (or `SKIPPED` under perturbation).  `run_tests.py
  gods` (23,477 passed, 12 skipped) after updating `test_triggers.py`'s
  own firing-arm test (it used to assert firing always declines; now it
  asserts every witnessed arm matches and only the genuinely unrecovered
  ones decline, plus a new test that at least one real firing activation
  composes).  `camera-sprites` extended to fifty-seven gates.  Reproduces
  the original on `f0ac19738f19…`: `evaluator` PASS, 1,726 hits, 37
  fallbacks (2 disabled, 12 unrecovered action index, 3 achievement seam,
  20 z80 bank guard -- all honest), bit-exact; `evaluator-mutant-outcome`
  DIVERGENCE at frame 477 (unchanged mutant, still valid against the
  wider plan); `spawn-effect-slot` PASS, 7 hits, 0 fallbacks, bit-exact;
  its own mutant DIVERGENCE at frame 2333.  Milestone tree PASS on all
  five leaves (`artifacts/gods/verify-camera-sprites-leaves-2026-09-19-firingarm`,
  107,519 frames): the `00462C` gate's own fallbacks fell from several
  hundred to 105 across the whole tree (19+14+18+11+43 by recording), all
  of them the honest declines named above.  This closes the
  `NEW_GODS_SUBSYSTEM` escalation on `00462C`'s firing arm: what remains
  of the `0030CC` assignment is `003186`'s body (and `003284`, censused
  as met) for the object table update, then `0030CC` itself as the
  200-slot scan composing it with the phase counters and the tail (with
  its own semantic-operation card naming the two sound requests as
  pending effects); separately, `004926`'s own second real caller at
  `0139D2` inside the collectible-lists subsystem (`tick-map.md` order
  14) is a fresh bite in its own right.

- **19 September, closing this grinder session**: `003186`'s own body is
  escalated `NEW_GODS_SUBSYSTEM` (`docs/gods/blockers/2026-09-19-003186.md`).
  Its own head (the phase counters, the `0033D4`/`0033EC` delta/cue
  tables) matches the `0030CC` assignment's own read and is likely
  tractable, but its own tail falls unconditionally into `003284`, a
  second real subsystem of its own: an unmodelled screen-visibility gate
  (`003480`, its own `rtr` return convention) feeding the already-
  recovered sprite emitter (`0018C8`) from at least four sites, a genuine
  indirect-`jsr` function-pointer table (`0x370E`, 13 real handlers), a
  further native-ish routine (`001810`), two more persistent structures,
  and a pickup-award integration reading `pickups`' own already-named
  tables through a further multi-call chain.  `census_all.py --entry
  0x003186 --max-classes 400` ran to completion (258-471 s a recording,
  the most expensive census this grinder has run) and confirmed the
  scale directly: four of five recordings overflowed the 400-class cap
  by 3,037-5,410 further occurrences each (54-81% of all activations),
  well over a thousand real distinct path classes across the tree --
  an order of magnitude past any bounded leaf or family this grinder has
  closed.  `0030CC` itself stays blocked behind it.  Next bites, in
  order: `003480`'s own screen-visibility gate (a leaf reused at every
  `0018C8`-emitting arm), the `0370E` table's own individual handlers
  (most already point at the recovered `0018C8`), `FFFFF262`'s own
  triple-buffer, then the pickup-award integration; separately, `003186`'s
  own head alone (over the 400 retained fixtures per recording, already
  parked exactly there) may still be worth a leaf recovery on its own
  merits even before `003284` is closed, and `004926`'s own second real
  caller at `0139D2` remains untouched.

- **19 September, next grinder session (the Decision's own order)**:
  `003480` turned out NOT to be the small screen-visibility gate the prior
  reconnaissance named (ROM read only, never traced): every one of 40
  retained fixtures traced with `factcheck facts --path` shows its
  in-range arm falling through, past the bounds check, into a second real
  body before either of its two `rtr` exits -- a RAM template table
  (`FFFFF8C2`), a further RAM range table (`FFFFF22E`), a SECOND real
  indirect-`jsr` function-pointer table (`0x5958`, 16 entries, one already
  the recovered `0075D6`), a real `jsr` into the SAME unrecovered
  pickup-award entry (`jsr $12C80`) `003186`'s own blocker already named,
  a self-contained 10-slot queue append (`FFFFF09E` via `002F2E`), and a
  number-to-digits routine (`0x364C`) whose own destination is unread;
  instruction counts across the 40 fixtures span 4 to 522.  Escalated
  `NEW_GODS_SUBSYSTEM` (`docs/gods/blockers/2026-09-19-003480.md`).
  Recovered `001810` instead, the Decision's own second bite: a second
  sprite-emitter shape (`game/sprites.py: paint_object_tile`, candidate
  `'object-tile'`) -- off-screen (a 16-pixel margin) is a plain leaf;
  on-screen always uploads fresh (no cache, like `00126A`) but paints
  directly into the scrolling background plane at a nametable cell built
  from the WORLD position (not the screen position), never appending to
  the sprite list; the VDP command formula was verified bit-for-bit
  against three live traced activations before being trusted.  9 fixtures
  over two of five recordings, all MATCH plain and under
  `--perturb-upper-halves`; `f40d7bcc9ddae7a9…`, 17,620 frames, PASS
  bit-exact (11,518 hits, 38 fallbacks, all Z80 bank guard); mutant
  `object-tile-mutant-register` DIVERGENCE at frame 2,236; milestone tree
  PASS (107,519 frames, current receipts).  `camera-sprites` grew
  fifty-seven -> fifty-eight gates.  Reconnaissance only, not attempted:
  `0036E2` (reached from `003284`'s own `status > 4` arm, NOT from
  `003480`) is a genuine 13-entry indirect-`jsr` scan over `0x370E`
  (confirmed by direct ROM read: kinds `0x31/0x83/0x5F/0x6A/0x6B/0x6C/0x67`
  point straight at the already-recovered `0018C8`; `0x37/0x51/0x52`
  point at `00377A`/`0037A0`/`00375C`, each a small per-frame index lookup
  ending in a tail-call into the now-recovered `001810`; `0x6F/0x70/0x72`
  point at `0037C6`/`003884`/`003896`, a further, distinct screen-test +
  device shape reading TWO OTHER solid-pointer globals at `0x67654`/
  `0x675D4` this session did not verify) with a no-match fallback into
  `001810` directly and an exit `bra.w $3158` back into `003284`'s own
  flow (not an `rts`) -- a real "seam over a seam" composition
  (`004790`'s own shape) once censused; the next candidate.

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
