# Status - 14 September 2026

The project now has an immutable cold-start input-history model for player
sessions and verification.  It replaces the current play/replay/snapshot
workflow; machine snapshots are disposable Genesis cache material, never
history identity.  Python recovery remains selective.  No claim is made that
the game, its dispatcher, or the recovery task is complete.

## Replay evidence at scale: index, segments, caches

`docs/replay-evidence-at-scale.md` measured how replay-derived evidence should
work now that `main` covers 82,161 frames, and its DO NOW rows are in the
checkout.  `scripts/recovery_census.py` single-steps every occurrence during
the replay and retains one entry state per distinct executed path (plus one
per exit CCR) with the contact-tick parent state that led to it, writing an
`index.json` evidence index; the plain (entry, kind) mode remains behind
`--plain`.  `scripts/segment_verify.py` restores a retained state and verifies
the candidate for a few frames against the stored reference observations of
the last PASS cold run, reporting whether a parent owned or declined its
child; `tests/test_recorded_evidence.py` runs it over every retained parent
when `artifacts/evidence/main` exists.  Original-machine history caches are no
longer keyed by Python source, so a source edit keeps them.  Candidate stats
carry `fallbacks_by_gate`, and the frontier ledger reads the evidence index and
lists scheduler refusals by gate.  Nothing here replaces the every-frame cold
comparison from power-on; it moves the per-leaf work off the replay.

The census of the 18 frontier entries on `main` took 341 s and retained about
190 path classes (385 child and parent states, 96 MB, regenerable) in
`artifacts/evidence/main`; every retained parent verifies over two frames
against the reference in 50 s.  **1,642 tests pass**; the **82,161-frame cold
comparison passes** with zero restores at `artifacts/evidence-tooling-main/`.

The 15,691 scheduler refusals are a phase artifact: the contact tick plan is
2,488 cycles (2 percent of a frame) but the game runs the tick at the end of
the frame, so 16 to 22 percent of ticks straddle the deadline; the 378-cycle
prefix alone would fit in 49 of 54 measured refusals.  The cause and the
answer are in `docs/execution-model-research.md`: the replay's observation and
admission instant sits in the game's busy window at the frame wrap; keeping the
input instant there and moving the observation and deadline to the game's idle
window (raster line 131) removed 3,824 of 3,834 refusals over 20,000 cold frames
in a prototype, frame-exact and trajectory-exact, with no change to `AtomicPlan`.
That report also concludes that no new execution abstraction is needed.

## Grinder tooling landed; baseline on the 82,161-frame main

The review's DO NOW items are in the checkout.  `scripts/factcheck.py`
(`facts`, `check`, `branches`, `segments`) derives every machine fact of a branch
by single-stepping the original and names every fact a plan gets wrong;
`scripts/verify_status.py` is the only reader of verifier state;
`scripts/frontier_ledger.py` ranks what the last cold run still hands to the
original and joins refusals to their boundary function; `scripts/recovery_census.py`
is a command with `--parent` retention; `scripts/leaf_review.py` is the
supervision gate.  `compare_history` runs its two fresh workers in parallel
(`--sequential` opts out) and reports a watchdog expiry as `TIMEOUT` for either
worker.  The lifecycle gate set is pinned at 62 (native limit 64).  The
Type-55 and Type-46 exemplars now keep their predicates and durable writes in
`game/objects/contact.py`; the Type-55 direct and selected-guard arms and the
Type-43 command-63 seam from the review's trial are adopted with their tests,
and Type-55 is owned inside the contact scan.  The step loop is
`docs/recovery-grinder-protocol.md`; the worker prompt is
`docs/recovery-grinder-goal.md`; per-leaf records go to `docs/recovery-ledger.md`.

**1,631 tests pass in 153.98 s**; the current **82,161-frame cold comparison
passes** with zero restores in 403.1 s (parallel workers) at
`artifacts/factory-baseline-main/`.  The ledger of that run: 37,458 fallbacks
against 72,249 candidate hits; the largest unrecovered collection callbacks are
`1AF5F0` (6,668), `1AFB36` (6,277) and `1AFA84` (2,829), the scheduler refused
15,691 admissions, and the spawn dispatcher has 40 unrecovered targets.  The
`.venv` was recreated from the same Python 3.12.14 with `capstone` added to the
test extras.

## Type-20 relocation composed inside contact scan

Recorded Type-36 callbacks at `1AF516` now compose the existing secondary-pool
relocation inside the complete scan and resumed tail. Found/full-pool paths,
outer/future/fresh checks, and result/return/timing mutants pass. **1,568 tests
pass in 135.70 s**; the current **26,378-frame cold comparison passes** with
zero restores at `artifacts/type20-parent-history/`. Five scan fallbacks and
four child dispatcher crossings are removed.

## Type-55 verifier incident resolved

The apparent blocked verifier completed successfully. Both `type55-full` and
`type55-isolated` produced exact cold PASS receipts at 10:50/10:51; absence of
intermediate output was not a failed worker. The duplicate launch was unnecessary.
`scripts/dev.py history-verify` now emits liveness and exit status on stderr;
it does not restart workers or alter watchdogs/qualification.

Independent Type-55 branch qualification found a real accounting error hidden
by the recording: the non-borrow return needs 180 cycles / 15 instructions,
while the borrow/NEG path needs 182 / 16. Both are now checked against original
ROM, including CCR variants, future continuation and fresh restore. The finite
guard remains the only admitted Type-55 path; its transition is still original.
Final qualification: **1,561 tests pass (139.11 s)**; **26,378 cold frames
PASS** with zero restores and current source receipts in
`artifacts/type55-reviewed/`. The visible launcher completed in 245.9 s.

## Contact integration reviewed and qualified

The reviewed batch combines parent sound composition and the adjacent
type-79, type-1F, type-15 and type-44 callback domains described below. These
are bounded supported paths, not complete recovery of those game routines.
The latest pre-review cold receipt in `artifacts/history-verify-current/`
matched source and passed with zero restores; the older per-milestone receipts
are historical and must not be treated as current cold-run evidence.

Review fixes validate the post-sound scan cursor (24-slot bound and matching
A1/D4 position), execute wrong cursor/return/timing controls, remove ignored
snapshot dependencies from family tests, and restore the blocked-contact
fixture parameter that a second gate setting had overwritten. The four new
family RAM adapters are now selected by the owned scan as well as the standalone
dispatcher; sound/device branches without a parent contract remain local
fallbacks.

**1,538 tests pass in 128.08 s.** The final **26,378-frame cold comparison
passes** with zero restores, exact state/video/PCM equality and current source
receipts: `artifacts/type46-dispatch-full/comparison.json`.
Against the incoming worktree's cold receipt, parent admissions rise
18,364 -> 18,411; dispatcher hits fall 202 -> 155; gates fall 29,499 ->
29,452; fallbacks fall 5,303 -> 5,256. Legacy entries/returns remain 206/187
and local fallbacks remain 49. The review added no native API, continuation
persistence, snapshot format or mutable state authority.

The earlier `blocker-review-full` attempt was rejected because implementation
changed while it ran; it is not qualification evidence. Remaining unsupported
sound/device paths are explicit recovery frontiers, not a claim of complete
routine/subsystem ownership.

## Type-03 D8-zero contact sound wrapper

Recorded table callback `1AED86` now admits only its two-instruction,
D8-zero branch into the existing C6 contact sound wrapper.  Its mutable D8
arm remains original-owned.  The composed plan preserves the dispatcher A4
residue, lets the native command-31 request run, proves the saved local frame
and return slot, then joins the existing suffix through `1ABD74`.  The direct
entry replaces the unused direct sibling gate so the native 63-PC gate limit
remains respected; dispatcher ownership is unchanged.

Self-contained original-ROM tests require exact outer state, PCM/timing,
150-instruction future execution, fresh-process restore, and result/
continuation/timing negative controls.  The captured current-main Type-03
state separately reaches the same `1ABD74` observable boundary exactly.
The full 26,378-frame cold comparison remains strict-PASS with zero restores;
the candidate reports 26 sibling hits and explicit D8-mutation fallbacks only.

## Type-46 command-66 replacement

Recorded callback `1AEF5C` now composes its sound-on counter path through the
existing native seam and counted replacement.  The saved D0 word and the live
incremented D0 byte are both preserved; capped and sound-off arms remain
original-owned.  Strict outer/future/fresh tests and the cold history pass.

## Type-79 collection guard return

The collection dispatcher now admits `1AEB7C` on either measured guard return:
`FFF0E7 == 0` and `FFF0D8 != 0` (five instructions / 70 cycles), or the
following `FFF0F2 != 0` tail (seven instructions / 94 cycles).  Neither path
writes RAM; each returns to `1ABCA0` with its final `TST.B` CCR result.  All
transition and helper arms remain explicit original fallbacks.

Its separately measured inactive sound arm is now also admitted when
`FFF0E7`, `FFF0D8`, and `FFF0F2` are all zero and the existing contact reset
seam is applicable.  The `1AEB7C` wrapper costs 118 cycles / 8 instructions
before that seam; its command-31 return then proves the local BSR/RTS chain
back to `1ABCA0`.  Strict state, PCM, timing, 150-instruction continuation,
and fresh-process restore all match the original fixture.

## Type-1F inactive callback tail

The collection dispatcher admits `1AE796`'s bit-5-clear RTS tails: both
direction-aware position failures and position-admitted inactive (`FFF0D8 ==
0`) paths.  Their measured costs are 104–142 cycles / 8–11 instructions.
Each copies `FF7E02` into `D7.W`, preserves the compare residue where `BTST`
only changes Z, and returns to `1ABCA0`.  Nested-contact, retirement, and
device-helper arms remain original execution.

The recorded inactive bit-5 contact arm is also composed through its measured
`1AE4F8` BSR (138 cycles / 10 instructions): finite early-contact returns
close directly, while reset cases use the existing command-31 seam and prove
the local return before the callback RTS.  Strict outer state, PCM, timing,
continuation, and fresh-process restore match the original fixtures.

## Type-15 sibling callback wrapper

Table callback `1AE978` now composes its `1AEC00` sibling call and the shared
`FFF0D8`/RTS tail. Its BSR stack word is the callback-specific `1AE97C`, not
the neighboring wrapper's return. Directional early and counter-decrement
paths are qualified against the original; the nested contact path remains
explicitly original-owned.

## Type-44 counter replacement

The sound-disabled `1AEF12` arm now owns its byte counter clamp and composes
the existing counted-replacement boundary. Clamp and non-clamp cases match the
original. Its command-98 sound arm remains original-owned pending a dedicated
local-resume proof.


One direct Type-1F transition is now composed as well: the active,
direction-zero, bit-5-clear `0x1F` record with a zero per-record counter takes
the 336-cycle / 25-instruction script/state prefix to the existing `1AE954`
retirement boundary.  Command-41 counter-nonzero transitions and the other
type-specific/direct-helper cases remain original execution.

The recorded counter-nonzero `0x1E`/`0x1F` variants now cross their measured
command-41 seam: native sound/flush returns at `1AE920`, then the existing
priority selector is composed with the 108-cycle publication/RTS suffix. Both
type-specific prefixes have strict outer-state, audio, continuation, and
fresh-process qualification.

The matching sound-disabled direct selector route is qualified for all four
admitted type prefixes (`0x1E`, `0x1F`, `0x21`, and `0x22`); it remains an
atomic selector/publication/RTS composition with no sound seam.

For `FF7E21 == 0`, the same four direct type prefixes bypass counter and sound
handling and compose into the existing `1AE954` finish-object boundary.  All
four have strict outer-state and future qualification; complete canonical
history verification remains exact.

The captured dispatcher state matches strict outer state and 150 native future
instructions.  The focused contact suite has **96 passing tests** and the full
**26,378-frame** checkpoint-assisted history comparison passes with exact state, video, PCM,
timing, and continuation equality.  Evidence:
`artifacts/contact-type79-current/`.

## Contact tick composes sibling command-8 sound

The `1ABB40` parent can now cross a selected `1AE9C6`/`1AE9DA` sibling
decrement through the existing command-8 sound seam, then resume the shared
completion, the remaining scan, and the caller's real RTS.  This is a bounded
composition: unsupported callback targets and later sound calls still return
to original execution locally.

Two synthetic ROM-table cases (`0x05` and `0x06`) qualify strict outer state,
150 native continuation instructions, and fresh-process restore.  The focused
parent suite has **43 passing tests**.  The full **26,378-frame** cold-history
comparison passes with exact state, video, PCM, timing, and continuation
equality.  The 20 recorded `contact sibling decrement requires command8 seam`
fallbacks are gone; parent admissions rise **18,338 -> 18,364**.  Evidence:
`artifacts/contact-step-sibling-sound-current/`.

## Sibling wrappers compose inside the contact tick

Existing `1AE9C6` / `1AE9DA` planners now run directly inside the owned scan.
Four new self-contained cases qualify two callbacks per tick, including early
returns and counter decrements, strict outer state, 150 original instructions
and fresh-process restore. No new native API or snapshot mechanism was added.

All **1,474 tests pass (117.82 s)**. Full **26,378-frame cold comparison passes**
with zero restores and exact state/video/PCM equality. Parent admissions rise
18,152 -> 18,201; dispatcher hits fall 344 -> 294; total gates fall
29,693 -> 29,643. Legacy entries/returns remain 199/180. Evidence:
`artifacts/contact-wrappers-full/comparison.json`, milestone `592c9e4`.

The figures below describe the preceding parent milestone.

## Contact tick owns the scan and caller return

The production entry is now `1ABB40`, covering contact countdowns/latches,
player-bound preparation, the qualified 24-record scan and the real RTS at
`1ABD7C`. Known recorded calls return to `1A8C44`. The former `1ABBD6` scan
gate is no longer armed in production; its adapter remains usable by explicit
oracle witnesses. Unsupported callbacks decline before any prefix is committed,
and existing dispatcher/child recovery remains available during original flow.
This is whole-routine ownership for the admitted RAM-only domain, not coverage
of every callback or removal of the original CPU/sound subsystem.

**1,470 tests pass in 116.93 s**. Full **26,378-frame** cold comparison passes
with zero restores, strict state/video/PCM equality and matching current source
and native receipts. `history-verify --timeout-seconds 180` takes **236.22 s**
for both fresh workers and comparison. Fresh-interpreter outer-tick witness
(including 150 native instructions and fresh-process continuation) has a
**0.423 s** median across five runs, with no native rebuild.

The parent admits 18,152 times. Configured gates remain62; standalone scan hits
fall18,665->0. Total gates29,689->29,693 and dispatcher hits340->344: the wider
atomic interval declines slightly more often. Fallbacks5052->5565, replaced
instructions3,674,268->4,088,159. Existing recovered-callee accounting52,532
and legacy entries199/returns180 remain unchanged. This absorbs a previous
production boundary without claiming an overall crossing reduction.

The 34 new self-contained tests cover countdown saturation, descriptor/player
guards, mirroring, staged descriptor aliases, real caller returns, stack/register
variations, partial callback register effects, deadlines and four mutants.
They also prove a first landing changes the player's position and rejects the
second object's collision. Five actual outer-entry fixtures independently
qualify;23 captured configurations require unsupported callbacks.
Evidence: `artifacts/contact-step-full/{comparison,latency}.json` and
`artifacts/contact-parent-frontier/production-step-qualified.json`.

Next measured opportunity: four recorded scan fixtures can directly compose
existing sibling wrappers `1AE9C6`/`1AE9DA`; two require the command8 sound seam.
That extension is qualified as an artifact, not yet production. No new leaf,
continuation mechanism or native API is needed for the four admitted cases.

Earlier milestone sections below are historical baselines.

## Scan milestone (`caec59b`)


The lifecycle candidate owns the complete 24-record pass from `1ABBD6` to
before the RTS at `1ABD7C` when its collisions select the five supported
RAM-only callback families. Geometry, callback selection, recovered callbacks
and shared completion compose in one admitted plan; later iterations read prior
planned writes. Unknown/device/sound callbacks and scheduler refusals leave the
entry unchanged and retain the previous dispatcher recovery opportunities.
This does not recover all contact callbacks or remove original sound execution.

**1,436 tests pass in 110.56 s**. The full **26,378-frame** cold comparison passes,
including every canonical state/frame/PCM observation and terminal state, with
zero restores and matching current source/native receipts. The first candidate
worker exceeded the default 120-second watchdog. Re-running that worker with a
300-second limit completed in **120.64 s**; the already completed original trace
was retained and validated with the existing execution validator. Equality was
not relaxed. Use `history-verify --timeout-seconds 180` for this current corpus.
The original timeout report remains alongside `comparison-completed.json` in
`artifacts/contact-scan-full/`.

The scan admits 18,665 times and absorbs 255 previous dispatcher/completion
entries: standalone dispatcher admissions fall 595 to 340. Replaced instructions
rise 464,365 to 3,674,268. Total gates rise 7,609 to 29,689 because the added
scan gate runs each gameplay tick; fallbacks rise 1,382 to 5,052. Configured
entries rise 61 to 62. Existing recovered-callee accounting stays 52,532 and
legacy entries/returns stay 199/180. This is actual internal composition, not
an overall crossing reduction. Geometry Python calls are not included in that
historical direct-callee counter.

The 29 self-contained new witnesses include all eight collision edges, mirror
and word wrap, two real callback transitions, register/stack variations,
unchanged-state refusals, deadlines and result/return/timing/final-PC mutants.
A stale second-callback motion read is rejected with all stores retained.
Stronger CCR variation found and fixed the final coordinate ADD's X residue.
Ten genuine full scan fixtures (eight contact-bearing) independently qualify;
39 retained fixtures require unsupported callbacks. Fresh-interpreter whole-scan
outer/150-native/fresh-restore witness median is **0.413 s**, without a rebuild.

The next enclosing entry is confirmed as `1ABB40`, called from `1A8C40`.
Original-only census observes 22,335 entries with exact terminal equality.
Its contact timers/latches/player-bounds prefix is qualified as a prototype;
five complete recorded outer paths compose with the scan. No production hook
for that parent has yet been added. See `artifacts/contact-parent-frontier/`.

## Shared-completion milestone (`82d0257`)

Lifecycle callback plans returning to `1ABCA0` can now own the common contact
completion through `1ABD74`. Landing script selection, position calculation and
publication are semantic functions in `game/objects/contact.py`; the boundary
preserves exact guards, CCR, stack residue and timing. The `1A8E0C` position
helper becomes a direct Python call inside accepted landing paths. No new gate,
native API, snapshot state or legacy seam was added. If the aggregate cannot be
admitted, the existing shorter callback plan remains available and original
execution continues from its old boundary.

**1,407 tests pass in 104.99 s**. The full **26,378-frame** cold comparison passes
with zero restores and matching production hashes. Completion is absorbed on
604 activations, including 12 position-publication calls. Gate hits remain 7,609,
candidate activations 6,246, dispatcher admissions 595 and fallbacks 1,382.
Direct-call accounting rises 52,520 to 52,532 and replaced instructions rise
462,239 to 464,365. This is more ownership behind the same entry boundaries,
not a reduction in measured total gate hits. Fresh-interpreter outer-plus-150
witness median: 0.279 s (five runs; no rebuild).

Production witnesses now observe `1ABD74`; direct callback adapter witnesses
retain `1ABCA0`. The shared qualifier enforces complete serialized state, 150
native continuation instructions and fresh-process restore. New completion tests
cover all selectors, combined guards, register/stack variation, output/return
aliases, deadline fallback and result/return/timing/final-PC mutants. Root also
qualified 64 selector/guard combinations against the production plan.
Evidence: `artifacts/contact-completion-full/{comparison,latency}.json`,
`tests/test_contact_completion.py`, and the production completion matrix under
`artifacts/contact-parent-frontier/`.

Whole-scan recovery remains a prototype. Forty-nine genuine scan-entry states
were captured across 28 configurations with exact original terminal equality.
Ten full 24-slot passes qualify, including eight contact-bearing passes through
four known callback families; a constructed two-callback pass also qualifies.
Thirty-nine captured cases require unsupported/device/sound paths. These are
explicit remaining dependencies, not evidence of a complete CPU-free scan.
See `artifacts/contact-parent-frontier/{scan-qualified,recorded-collision-qualified}.json`.

## Contact scan frontier and type-7E readiness exits

The dispatcher now also owns `1AFE1C`'s blocked, not-ready and already-armed
exits. The type-7E semantic helper publishes motion parameters and conditionally
clears its armed flag. Ready/unarmed progress stays original: both recorded
progress paths enter the unresolved `1B2238` command-stream subsystem.
This is bounded callback ownership, not recovery of that engine.

Canonical census finds 161 not-ready, six already-armed and two progress visits.
The production batch passes **1,342 tests in 95.44 s** and the full **26,378-frame**
cold strict comparison with zero restores and matching current source hashes.
It admits 163 of the 167 eligible visits; four scheduler refusals stay original.
Gate hits remain 7,609. Dispatcher admissions rise 432 to 595, fallbacks fall
1,545 to 1,382, direct calls rise 52,194 to 52,520 and replaced instructions rise
459,462 to 462,239. Fresh-interpreter edit-to-verdict median is 0.274 s across
five original/candidate outer-plus-150-instruction checks; no native rebuild.
Six retained eligible callback states also qualify after an explicitly constructed
rewind to their dispatcher entry. Standalone constructed cases cover guard priority,
register/stack variation, fresh restore, aliases, deadlines and all three mutants.
Evidence: `artifacts/contact-type7e-full/{comparison,latency}.json` and
`artifacts/contact-next-frontier/`.

Upward discovery now maps the 24-object contact scan (`1ABBE0` loop head,
`1ABD74` advance, `1ABD7C` RTS), with dispatcher `1ABC82..1ABCA0` inside it.
The original census completes 22,335 passes: 21,596 without callbacks, 437 with
then-supported targets and 302 with an unsupported target; type-7E alone accounts
for 169 of the latter. These are structural counts before this batch, not whole-scan
admission. Shared completion `1ABCA0..1ABD74` has 748 visits including 13 landing
paths. Collision predicates pass 387 recorded-derived and 544 constructed
original branch-edge checks, but exact scan effects are not yet production-owned.

Next composition work targets that collision prefix and shared completion.
The other frequent callback `1AE796` has 67 recorded visits and unresolved VDP,
controller/Z80 and buffer-processing dependencies. Those boundaries are explicit;
no new legacy runner is introduced merely to increase callback coverage.
Discovery evidence: `artifacts/contact-parent-frontier/` and
`artifacts/contact-remaining-frontier/`. All canonical census terminal fields
match the completed original reference.

## Dispatcher-owned contact family

Four adjacent callbacks now compose inside `1ABC82` through `1ABCA0`:
`1AFBF4` type-66 transition, `1AF978` motion/type-6B publication,
`1AF9F6` signed motion/type-77 directional transition, and `1AFC4E` launch
with optional original sound command `4B`. Game writes remain in
`game/objects/contact.py`; exact outer effects remain in `boundary.py`.
The sound path reuses the existing synchronous runner and safe-boundary rule.
No child gate, native API, snapshot metadata or execution protocol was added.

The canonical history observes 37 visits to `1AFBF4` and 25 to `1AF978`;
the other two callbacks are **constructed adjacent coverage**, not recorded
hits. Twelve recorded states pass strict outer equality, 150 native instructions
and fresh-process restore. The family has 53 tests including varied live
registers/stack, alias fallback, deadlines and result/return/timing mutants;
a separate seeded 160-case original-ROM variation check passes. The complete
suite passes **1,322 tests in 93.91 s**.

Full cold history passes **26,378 frames**, zero restores, strict state/frame/PCM
comparison and matching current production hashes. Relative to contact activation,
dispatcher admissions rise 372 to 432, fallbacks fall 1,605 to 1,545, direct
Python calls rise 52,110 to 52,194, and replaced instructions rise 458,330 to
459,462. Gate hits remain 7,609; configured gates remain 61.

Qualification caught fixture-specific register/publication constants and incorrect
branch timing/CCR recipes before integration. Unique execution mechanisms stayed
at zero, but manual exact accounting and review cost remain significant.
The oracle also now reinstates its observation gates after synchronous sound
restores production gates. This changes qualification plumbing, not game policy.
Evidence: `artifacts/contact-family-frontier/current-canonical/report.json`,
`recorded-qualified.json`, `varied_state_check.json`, and
`artifacts/contact-family-full/comparison.json`. The older `current/` capture
used shifted input timing and is invalid as canonical evidence.

## Dispatcher-owned contact activation

The existing `1ABC82` dispatcher now composes type `01`'s `1AFD84` contact
activation directly through its guarded exits, `1AE6B4` dispatch-flag tail,
or accepted motion/script/object transition to `1ABCA0`. No child gate or
new execution mechanism was introduced. Semantic writes live in
`game/objects/contact.py`; exact registers, CCR, timing and alias admission
remain in `boundary.py`.

The current cold history contains 121 visits: 79 negative-motion exits,
33 shared-tail exits and nine activations (three left, six right). The blocked
flag branch is constructed coverage. Eight recorded fixtures pass strict
outer equality, 150 native instructions and fresh-process restore. **1,268
tests pass** (84.14 s), including 42 new checks for arithmetic boundaries,
register words, both directions, alias fallback, deadlines and all three mutants.

The full **26,378-frame** comparison passes with zero restores and matching
production hashes. Contact activation admits 119 plans; two scheduler refusals
execute original code. Total gate hits stay 7,609 and configured gates stay 61;
fallbacks fall 1,724 to 1,605. Dispatcher admissions rise 253 to 372 and replaced
instructions 456,364 to 458,330. This owns one connected contact transition,
not every contact object or the surrounding update loop.

Evidence: `artifacts/contact-activation-frontier/{census,prototype}.json` and
`artifacts/contact-activation-full/comparison.json`. The shared oracle now
returns named `ExecutionResult` fields and exposes the existing entry/return
runner as `execute_region`; qualification strength is unchanged.

## Whole spawn-strip setup parents

The four recorded setup entries `1AE3FC`, `1AE406`, `1AE47E`, and `1AE488`
now own coordinate masking, strip offsets, their column/row walker, and the
outer RTS. `game.objects.lifecycle.prepare_spawn_strip` holds the semantic
preparation; existing planned RAM reads compose callbacks and exact outer
effects. No new native API, snapshot state or continuation protocol was added.

**1,226 tests pass** in 81.54 seconds. Eight recorded parent fixtures pass
strict outer equality, 150-instruction native continuation and fresh-process
restore. Portable cases cover unknown callbacks, register words, signed stride,
deadlines and result/timing/continuation mutants. A constructed allocation that
overwrites the caller return slot also matches the original updated RTS target;
its deliberately data-directed return is checked for four further instructions.

Full **26,378-frame** cold history passes strict state/frame/PCM and terminal
comparison with zero restores; receipt source hashes match current production.
Compared with the row milestone, 2,441 setup plans absorb their walker entry,
leaving 90 standalone walker admissions. Combined walker admissions remain
2,531. Gates/fallbacks increase by 96, entirely scheduler admission refusals;
candidate activations remain 5,904. Direct semantic calls rise 49,543 to 51,984,
replaced instructions 424,317 to 456,364. There are 61 configured gates of 64.
These are bounded recorded-path results, not ownership of the surrounding
scrolling/render coordinators or all ROM callback identities.

Evidence: `artifacts/spawn-setup/full/comparison.json` and
`artifacts/spawn-setup-frontier/setup-report.json`. Historical receipts remain
separate; the executable fixtures do not require local capture artifacts.

## Shared column and row spawn walkers

Production now owns the row loop `1AE4C6` through the boundary before RTS
`1AE4F6`, for one to 23 remaining slots. It reuses the column call, iteration
and walker bodies with explicit row facts: postincrement A0 before callback,
X-offset write, guest PCs and loop timing. One entry gate is added; admission
and fallback share the column handler. No new native or snapshot mechanism.

Eight recorded row states pass strict outer, 150-instruction future and fresh
restore checks. **1,199 tests pass** in 78.80 seconds. Portable tests cover counts, empty/multiple/unknown callbacks,
32-bit cursor crossing, planned MOVEM aliases, mutants and deadline refusal.
The oracle retains all production gates after fallback, including retries at
later row heads. It does not suppress these retries to make a witness pass.

Full **26,378-frame** cold history passes with zero restores. There are 619
admitted row plans (not necessarily 619 complete 23-slot passes). Standalone
spawn-caller activations fall 101 to 23 and allocator activations 17 to 2.
Total candidate activations rise 5378 to 5904, and fallbacks 1010 to 1628;
the entire added fallback count is scheduler refusal. Direct calls rise
35762 to 49543, including slot selection. Internal callback boundaries shrink,
but global execution crossings do not. Receipt: `artifacts/spawn-row/full/comparison.json`.

The next setup frontier has four observed entries: `1AE3FC`, `1AE406`,
`1AE47E`, `1AE488`. Their 586/1330/330/291 visits account for every recorded
column/row pass. Eight prefix prototypes match exact original states and
fresh continuation; setup is still native in production.

## Remaining observed spawn callbacks (`186d56e`)

The dispatcher now composes **37 targets**. Added successful type/script/mode
suffixes for `1B723E`, `1B728E`, `1B72AE`, `1B70D4`, the `FFF12A`-guarded lower
spawn `1B71A0`, and the selected RTS callback `1B65BE`. The latter is never a
global gate: its production ownership exists only inside the dispatcher.
The type `8A`, `41`, `84`, `4C` and guarded-script effects live in lifecycle
helpers; original ROM shape, registers, timing and admission remain in boundary.

**1,182 tests pass** in 76.95 seconds. Production guard skip/taken and allocation
first/late/exhausted branches are compared strictly, including 150 subsequent
native instructions and fresh processes. Explicit output checks protect the
guarded success script write that review caught missing from the first draft.
Full **26,378-frame** cold history passes with zero restores and matching source
receipts: `artifacts/spawn-closure/full/comparison.json`. Against `c87ca97`,
fallbacks drop 1069 to 1010, allocator activations 21 to 17, total candidate
activations 5382 to 5378, direct Python calls rise 35695 to 35762.

These targets close the unresolved callback identities in the recorded column
and row censuses. This does not prove all ROM table targets or unrecorded paths
are recovered. The row walker remains native; its eight-state prototype passes
strict outer/future/fresh-process checks using the column carrier's mechanics.

## Recorded spawn callback families (`c87ca97`)

The spawn dispatcher now composes **31 callback targets**, adding six plain
template/allocator callers and three allocation-success position adjustments.
Twelve plain callers (six existing, six new) share one ROM-validated LEA/BSR/RTS
recipe. The three positional callers share `offset_spawn_position` in semantic
source and a second exact outer recipe. Six duplicated adapter bodies now
delegate to the shared recipe; their original callers remain supported.

New recorded targets: `1B700C`, `1B6D84`, `1B6726`, `1B68CA`, `1B6C4E`, `1B65D4`,
`1B66F2`, `1B670C`, `1B6870`. The last three apply respective X/Y offsets
`(+8,+12)`, `(-8,+4)`, `(+9,+7)` after successful lower-pool allocation.
Templates and allocator arms remain explicit, checked against original ROM.

These nine are **direct dispatcher/walker children**, not new standalone
production gates. Adding every child gate exceeded the native gate limit;
the existing parent entry already provides the required production boundary.
Direct atomic oracle fixtures retain independent strict qualification without
expanding the gate set or native API.

**1,033 tests pass** (57.14 seconds). Qualification covers first/late/exhausted
allocation, incoming X, coordinate wrap, strict outer and 150-instruction
future state, and fresh processes. The CLI witness passes all 31 callbacks
and eight captured walkers (`artifacts/spawn-nine/witness.json`).
Full **26,378-frame** cold history comparison passes with zero restores and
matching source receipts (`artifacts/spawn-nine/full/comparison.json`). Against
the walker baseline, fallbacks drop **1,493 to 1,069**, allocator activations
63 to 21, and total candidate activations 5,420 to 5,382. Direct calls rise
35,209 to 35,695. Known callback composition removes more original boundaries;
unsupported surrounding behavior still falls back.

## Bounded spawn walker baseline (`cf064b5`)

The column spawn loop `1AE44A` now owns selection, empty slots and direct
composition of the 22 supported callbacks across up to 16 remaining slots.
It exits **before** the original RTS at `1AE47C`; setup and unsupported callbacks
remain original. Unsupported later selections discard the staged plan before
admission. Existing per-iteration recovery remains available on fallback.
RAM stays authoritative; no new snapshot, native API or continuation mechanism.

**853 tests pass** (41.42 seconds), including constructed empty/multiple/unknown
paths, counts, signed strides, planned MOVEM aliasing, strict outer state,
150 original future instructions, fresh-process restore and negative controls.
Eight explicitly captured original walkers also pass that qualification.
The cursor edge test exposed and fixed 24-bit truncation of ADDA.W's 32-bit A0.

The full **26,378-frame** cold history passes strict comparison with zero
restores. Standalone spawn-caller activations fall **435 to 105**, while 1,904
walker plans execute. Total candidate activations increase 3,846 to 5,420 and
fallbacks 681 to 1,493: empty passes now have an entry gate and unsuccessful
aggregate plans can retry at shorter boundaries. This is real internal caller
composition, **not** evidence of a global crossing reduction. Direct calls
5,365 to 35,209 include slot-selector calls, not just fused callbacks.

Evidence: `artifacts/spawn-walker/full/comparison.json` and
`artifacts/spawn-walker/recorded.json`. Reproduce captured-state qualification:
`python scripts/oracle_witness.py --walker-directory artifacts/spawn-frontier --fresh-process`.
Default tests construct their inputs and do not depend on ignored artifacts.

## Guarded callback composition baseline (`e7cf15d`)

The dispatcher callback map now includes **22 targets**: the prior 19 plus
`1B7354`, `1B742A`, and `1B744A`. Their existing recovered guards read `FFF171`,
`FFF172`, and `FFF16F`; zero skips allocation, otherwise execution falls through
to already recovered callers. No new semantic helper, timing recipe, native API,
snapshot rule, or gate was required. Three map entries compose those existing
callers; the redundant iteration support whitelist was deleted. Unsupported
targets still fail planning before admission or machine writes.

The full source-pinned suite passes **821 tests** in 39.36 seconds. Constructed
guard matrices cover skipped/taken guards, allocation/exhaustion, independent
and parent execution, strict outer and 150-instruction future comparison, plus
fresh-process restoration. The original census records 26 guard callback visits
across 21 formerly unresolved complete walker passes. See the compact
[recovery cost log](recovery-cost-log.md) for the enclosing ownership frontier.
Full 26,378-frame cold history comparison passes with zero restores: fallbacks
707 to 681, direct Python calls 5,339 to 5,365, and unchanged total candidate
activations (3,846). This removes the 26 selected guard fallbacks without adding
an execution gate. Receipts: `artifacts/spawn-guards/full/comparison.json`.

## Recorded spawn-neighbor expansion (`1e43a73` baseline)

The bounded dispatcher iteration at `1AE468` now composes **19 callback targets**
(previously 16). Added composition for the existing type-33 callback `1B6ED0`
(template `1B7C24`, script `1235AC`) and recovered two observed neighbors:

- `1B6F0C`: clear byte `FFF104`, allocate through descending pool entry `1B525E`
  using template `1B7C4C`, return at `1B6F1C`. Clearing also occurs on exhaustion;
  the flag's wider game meaning is deliberately unnamed.
- `1B6F1E`: allocate through `1B525E` using template `1B8250`; on success install
  script `125A4C`; exit at `1B6F32`. Allocation failure leaves that script untouched.

The parent calls these adapters directly, including the existing allocator,
then restores its outer ABI and continues at `1AE44A` / `1AE47C`. Dispatcher
setup, lookup and remaining callbacks remain original. No whole-dispatcher claim.
The type-33 gate now belongs to the canonical gate set; sound returns and sound
deadline fallback no longer silently remove it. The reset callback also excludes
aliasing its flag with the parent's saved register frame before committing writes.

Verification: **737 tests pass** (32.65 seconds), including the reusable raw-ROM
witness matrix for first/last free slot and exhaustion, both incoming X states,
independent caller and composed parent, strict full machine/RAM/register/time/
frame/PCM equality and 150 native future instructions. All three parents have
fresh-process continuation and result/return/timing negative controls. Separately,
all **29 recorded entry occurrences** pass strict outer and future equality plus
fresh-process restore: 13 enclosing iterations and 16 original callback entries.
These counts overlap the same original flows; they are not 29 distinct gameplay events.
Evidence is in `artifacts/spawn-neighbors/`; the reproducible constructed oracle
and regressions are `scripts/oracle_witness.py` and `tests/test_spawn_oracle.py`.

Recovery-cost note: semantic work was identifying the reset ordering and successful
script assignment, plus qualifying the existing typed variant. Mechanical work
was two familiar BSR/RTS aggregates and final CCR formulas (50 boundary lines),
checked against the ROM. Existing planned views, allocator, alias spans, AtomicPlan,
mutants, future execution and fresh-process oracle were reused. **No new machine
execution concept** was introduced. The three callback/allocator boundaries are
internal on admitted parent paths; independent adapters remain for original callers.
This is another bounded composition step, not evidence of a CPU-free subsystem.

The full current user history (`4b153763Ă˘â‚¬Â¦`, 26,378 frames) passes original versus
lifecycle with zero restores and strict equality at every canonical frame. The
new original observations also exactly match the prior optimization baseline.

| Full-history measurement | Before | After |
| --- | ---: | ---: |
| Fallback activations | 720 | 707 |
| Spawn caller activations | 419 | 435 |
| Standalone allocator activations | 79 | 63 |
| Direct Python calls | 5,299 | 5,339 |
| Total candidate activations | 3,846 | 3,846 |
| Replaced M68000 instructions | 127,469 | 127,634 |

The unchanged total activations and 16 fewer standalone allocator hits reflect
callers absorbing allocator work rather than adding another machine visit.
All 13 formerly unsupported selected dispatcher targets disappear from fallback
reasons. Other original callers still use standalone adapters. Full receipts:
`artifacts/spawn-neighbors/full/comparison.json` and its reference/candidate files.

## Current player and history model

Each history begins at one fixed cold root.  A node stores an immutable embedded
input segment with normalized frame/button events.  Its ID depends on the root,
input digest, and end frame, not on checkpoint placement, a label, screenshot,
cache, or `main` reference.  Continuing a checkpoint creates a new child.

The Genesis runner may complete the native instruction that crosses the logical
frame boundary; resulting ticks are observable execution details, not part of
the history identity.  Caches remain separately keyed by compatible ROM, native
binary, Python source, and state contract and can be discarded safely.

The pygame player opens a timeline before gameplay.  It exposes cold **New**,
the `main` reference, and checkpoint branches; F5/F6 make manual checkpoints
and a clean exit checkpoints automatically.  Every ordinary step journals its
held input mask.  A resumed branch releases saved held input through the next
canonical zero-mask frame instead of modifying prior history.

`history-run` executes a path cold by default.  `--cache` is an explicit player
optimization only.  `history-verify` uses fresh workers; `--tree` calculates
its own prefix states and compares every current branch.  `history-export`,
`history-validate`, and `history-capture` provide export, integrity, and
constructed-smoke operations.  Details and examples are in [history.md](history.md).

The redesign's source-pinned suite passed **681 tests** in 31.25 seconds. A constructed
4,200-frame continuous cold comparison matches original and lifecycle execution
at every frame: **205 candidate activations**, **zero restores**. Result,
continuation and timing controls each diverge on the 70-frame cold witness.
The disposable semantic edit check takes about **1.9 seconds per verdict**, with
no rebuild or reinstall. Native code and its binary are unchanged.

History tests cover checkpoint-independent identity, branching/autosave,
screenshots, incompatible/corrupt cache regeneration, fresh-process cold/cache
state/frame/PCM equality, shared-prefix traversal, and export without ROM/DLL.
Constructed raw-ROM witnesses retain strict allocator and dispatcher callback
qualification plus 150 original instructions and fresh-process continuation.
Receipts: [final audit](../artifacts/history-redesign/final-audit.json),
[full suite](../artifacts/history-redesign/final-suite.xml),
[cold comparison](../artifacts/history-redesign/verified-final/comparison.json).
Those redesign fixtures are constructed paths, not a recorded playthrough.

The subsequent user history through reported level 3 is now qualified on this
source: **9 checkpoints, 26,378 frames (440.20 seconds), 2,090 input changes**.
Both fresh-worker checkpoint traversal and uninterrupted cold original/lifecycle
comparison pass at every frame. All nine player caches and screenshots match
cold reconstruction; 480 recorded continuation frames after cache restore match,
and the latest cache matches in a fresh process. The candidate executes 3,846
activations, 5,299 direct Python calls and 199 legacy sound spans. Its 720
fallbacks preserve original execution and the strict comparison remains equal.
History/UI/verification tests (31) and machine/audio/carrier tests (34) pass.
The history was not modified. This qualifies the recorded path, not the whole
game. See the [level-3 operational report](../artifacts/level3-check/report.json).

Observation transfer now avoids the per-pixel Python list and exports each
snapshot only once into reusable 4 MiB scratch storage (the existing native
import limit). Returned snapshots remain independent bytes. No native API,
binary, state format or comparison contract changed. **683 tests pass** in
28.83 seconds. A controlled three-sample benchmark improves from 2.230 to
1.303 seconds per 300 observed original frames (**1.71x**), with identical
state/pixels/PCM. The complete 26,378-frame original/lifecycle cold comparison
passes in **230.74 seconds**; every original observation also equals the
pre-optimization run. The previous full comparison took approximately 405
seconds while another verification ran concurrently, so the controlled sample
is the cleaner speedup measurement. Evidence:
[benchmark](../artifacts/observation-speed/benchmark.json),
[full comparison](../artifacts/observation-speed/full/comparison.json),
[suite](../artifacts/observation-speed/suite.xml).

## Recovery remains in progress

The committed spawn milestones are described above; subsequent work is qualified
and published in separate batches. Replay receipts are source-version specific
and are regenerated after a production source freeze. Existing fallback,
strict state/PCM/future, fresh-process, alias, and mutation requirements remain
the acceptance bar for any admitted region.

Earlier collection, contact, selector, type-13, allocator, and spawn milestones
are retained as historical evidence.  They describe the ROM facts, constructed
fixtures, and recordings that existed at their freeze points; they do not assert
that legacy replay or snapshot loaders are available in the current player.
See [archive/STATUS-pre-history-2026-09-13.md](archive/STATUS-pre-history-2026-09-13.md)
and the retained subsystem reports for that evidence.

## Boundaries

The repository is a Windows x64 development environment for one verified USA
ROM revision.  It does not distribute a ROM, promise hardware accuracy, or turn
a comparison result into independent-console proof.  The native binding still
owns Genesis CPU/device execution; editable Python owns history, orchestration,
and recovered semantic islands.  Dependency and license details remain in
[third_party/README.md](../third_party/README.md).
