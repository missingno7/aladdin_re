# Status — 14 September 2026

The project now has an immutable cold-start input-history model for player
sessions and verification.  It replaces the current play/replay/snapshot
workflow; machine snapshots are disposable Genesis cache material, never
history identity.  Python recovery remains selective.  No claim is made that
the game, its dispatcher, or the recovery task is complete.

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

The full current user history (`4b153763…`, 26,378 frames) passes original versus
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
