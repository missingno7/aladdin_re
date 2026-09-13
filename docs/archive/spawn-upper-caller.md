# Frozen historical evidence

This report preserves ROM mapping, qualification, and recovery decisions at its source freeze. It is not current operating guidance: use the immutable cold-start input-history workflow in [../history.md](../history.md). Current commands do not promise to load legacy replay or snapshot artifacts referenced below.

# Dispatcher upper-spawn callback `1B735E`

The lifecycle candidate owns direct table callback `1B735E..1B7388`.  It returns
at the saved caller slot (both recorded `1AE46E` and `1AE4EA`), preserves the
`FFEFE0 == 0x3939` cap return, otherwise composes existing `1B5266` upper-pool
allocation/initializer/placement and writes type `0x40`, script `0x122C12`,
and clears `A5+0x29`.  Recorded coverage is 763 direct calls: 538 allocations
and 225 cap returns.  Exhaustion is synthetic and strict-qualified.

The manual machine work is the cap/branch caller envelope, saved BSR frame,
BNE exhaustion timing (22-cycle taken BNE/RTS suffix), and CCR: CMP preserves
incoming X; successful allocation retains the X produced by the common tail's final Y-coordinate `ADD.W` (and exhaustion preserves incoming X).  Existing allocator, planning
view, alias guards and `AtomicPlan` are reused; no new seam or framework.

Evidence: `artifacts/grinding/terra/dispatcher-parent/final-suite.xml` has
1,147 passing tests after the final shared-CCR regression; `witness/report.json` passes strict state/frame/PCM, F150,
safe/fresh restore and result/continuation/timing controls at saved return
`1AE4EA`.  `audit_receipts.py` confirms six final replay comparisons all PASS
with matching 19-module receipts.  The initial summary race is superseded by
that audit, which reads completed comparison receipts directly.
