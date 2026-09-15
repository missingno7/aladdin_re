# Frozen historical evidence

This report preserves ROM mapping, qualification, and recovery decisions at its source freeze. It is not current operating guidance: use the immutable cold-start input-history workflow in [../history.md](../../common/history-and-replay.md). Current commands do not promise to load legacy replay or snapshot artifacts referenced below.

# Contact sibling retirement cost log

## Bounded ownership

The production entries are `1AEC00`, `1AE9C6`, `1AE9DA`, and the existing
`1ABC82` dispatcher prefix when its ROM table selects C6 or DA.  `1AECD8` and
`1AED0C` are oracle-plan construction points only; they are deliberately not
armed as standalone production gates.

The shared `_finish_object_plan` is a private planning construction used by
the existing `1AE954` finish entry and the sibling tail.  It reuses the
already-qualified pair cleanup (`1ABE6E`), buffer release (`1AE372`), and
template initialization (`1AE30A`) effects.  It is not a new continuation or
mutable protocol.

## Measured recipes

`1AED0C` is the shared tail at **670 cycles / 42 instructions** before the
existing pair/buffer/initializer aggregate.  `1AECD8` adds the counter total,
type tests, and optional mode write:

| object type | added cycles / instructions | effect |
| --- | ---: | --- |
| `0x18` | 88 / 8 | bypasses the extra comparisons |
| `0x10` | 122 / 10 | stores `FFF0E9=0x20` |
| `0x11` | 140 / 12 | stores `FFF0E9=0x20` |
| every other non-`0x13` type | 122 / 11 | comparison path only |

The accepted `1AEC00` direction prefix contributes **116 / 9** when
`FF7E49=0`, **124 / 10** when `FF7E49!=0`.  Its non-retirement exits are also
measured: D8-zero return is **42 / 3**; directional early returns are
**108 / 8** (`FF7E49=0`) or **106 / 8** (`FF7E49!=0`).

Wrappers add exact BSR/RTS structure after a nonzero sibling return:
`1AE9DA` adds **34 / 2** and `1AE9C6` adds **60 / 4**.  C6 D8-zero first
builds the sibling/contact BSR path (**106 / 7** before contact), then uses
the pre-existing direct contact plan or command-`0x31` synchronous sound seam;
its final RTS is included in the suffix.  The dispatcher continues to use its
recorded **98 / 9** prefix and supplies the wrapper's real JSR frame.

## Exclusions and evidence

Type `0x13` (`1AF1AC`) and every `A1+1 != 0` decrement route (`1AD150`,
command 8/106) fall back before any atomic production write.  Direction
rejections are represented by their measured ordinary returns.  No new sound
ABI was introduced: C6 uses the existing 28-byte saved frame, command `0x31`,
return `1AE5B6`, frame identity, return-slot, deadline, foreign-return, and
safe-restore machinery.

Focused final receipt: `sibling-final-suite.xml` (794 tests, 0 failures,
0 errors, 0 skips, 37.631 s).  The focused fixture suite covers all four
non-13 type classes, both directions, D8-zero direct and sound contact,
dispatcher C6/DA, pair/buffer/carry matrix, outer snapshot and 150-step
future.  Parent strict recorded witnesses are
`artifacts/grinding/parent/sibling-witness-1AE9C6/report.json` and
`sibling-witness-1AE9DA/report.json`; Luna's state-changing dispatcher
retirement witness is
`artifacts/grinding/luna/contact-expansion/sibling-dispatch-retirement-new/report.json`.
Result, continuation, and timing controls are retained at
`artifacts/grinding/parent/sibling-controls/report.json`.

## Final integration and marginal work

Both final full recordings pass with current recursive source receipts:
`artifacts/grinding/terra/sibling-final-old-v2/comparison.json` (225 checkpoints)
and `sibling-final-new/comparison.json` (244). Parent independently checked every
module hash and identical reference/candidate observation hashes in
`artifacts/grinding/parent/sibling-full-audit.json`. The first old run selected
an obsolete v1 recording and failed before comparison; it is not qualification.

The real state-changing retirement witness owns dispatcher -> wrapper ->
directional retirement -> pair cleanup/release/initialization with one gate,
five direct Python calls, zero legacy spans/fallbacks, 100 replaced instructions
and 1386 charged cycles. This is one recorded route, not all surrounding code.
The recorded C6 contact/sound route uses two gates, six direct calls and one
original sound span, with no fallback. Both witnesses preserve strict full
native snapshot, frame/PCM, 150 subsequent original instructions and fresh-process
entry/exit restore. Wrong result/return/timing controls are rejected.

The edit-to-verdict check on the recorded retirement takes 0.822 s to PASS and
0.736 s to reject a deliberately wrong buffer clear. Native binary unchanged;
zero rebuilds or reinstalls (`artifacts/grinding/parent/sibling-edit-loop/result.json`).

Semantic reasoning: direction predicates, counter-versus-type ordering,
non-13 retirement classes, optional E9 write, and wrapper contact selection.
Reused machinery: RAM readers, shared finish effects, read-only planned-write
view, AtomicPlan admission, synchronous sound runner and existing witness tools.
New manual machine work: numeric branch costs, wrapper stack residue and final
CCR composition. No new continuation protocol, snapshot member, scheduler rule,
native API or verification mechanism. These numeric recipes remain handwritten,
not generated; the shared finish-tail construction amortizes an existing pattern.

Three production entries were added (1AEC00 and its two wrappers). Internal
1AECD8/1AED0C plans remain oracle-only, and calls to known cleanup/initialization
and contact behavior compose directly beneath the dispatcher. Standalone helpers
remain for original callers; their existence is not an extra internal crossing.

Verdict: CONTINUE + MECHANIZE. This step reused the existing machine concepts
while adding connected control flow. It does not yet prove an asymptotic cost
slope: numeric timing/CCR/stack work remains the repeatable manual cost. The next
adjacent dependency is the script selector1AD150 used by the decrement arm;
original evidence identifies a finite flag-priority decision tree, not a new
platform seam. Recover it with this substrate before considering new machinery.
