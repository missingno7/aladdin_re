# Reverse-pool spawn caller `1B6802`

## Scope

The lifecycle candidate owns the recorded enclosing routine
`1B6802..1B681A`, rather than adding a hook at the allocator return:

```text
1B6802  LEA.L  $1B7D8C,A6
1B6808  BSR.W  $1B5256
1B680C  BNE.B  $1B681A
1B680E  ADDI.W #8,$2(A5)
1B6814  SUBI.W #1,$4(A5)
1B681A  RTS
```

It composes the existing reverse 24-slot allocation, initializer, placement,
and indexed-clear plan with the caller's successful-slot position correction.
The correction reads the planned initialized object from the existing
read-only planning view, adds eight to `A5+2`, then subtracts one from `A5+4`.
On exhaustion, `BNE` skips both writes and returns the allocator's `D0=FFFF`,
`A5=FF7E40`, and CCR state unchanged apart from the branch/RTS path.

The normal recorded domain has 16 original entry hits across six replays: seven
in old-225, two in new-244, and seven in the 115733 later segment.  This is
recorded enclosing-caller coverage.  First, middle, final, and exhausted slots
are constructed from those original entry snapshots and remain labelled
synthetic branch coverage.

## Adjacent return at `1B7374`

`1B7374` belongs to a different guarded caller:

```text
1B7354  TST.B  $FFF171
1B735A  BEQ.W  $1B6EB0
1B735E  CMPI.W #3939,$FFEFE0
1B7366  BEQ.W  $1B7388
1B736A  LEA.L  $1B79B8,A6
1B7370  BSR.W  $1B5266
1B7374  BNE.B  $1B7388
1B7376  MOVE.B #$40,(A5)
1B737A  MOVE.L #$122C12,$20(A5)
1B7382  CLR.B  $29(A5)
1B7388  RTS
```

All 53 recorded `1B7354` entries have `FFF171=0` and enter unresolved
`1B6EB0` before the allocator.  The recovered `1B5266` callee remains
independently qualified through its saved return at `1B7374`, but this does
not establish the caller's guarded true path.  `1B7354` is therefore outside
this admission scope.

## Exact boundary and evidence

The combined successful path is 53 instructions and 828 68000 cycles: a
30-cycle/two-instruction `LEA`/`BSR` prefix, the existing 734/47 reverse
allocator plan, and a 64/4 post-return correction.  Exhaustion is 106/1100
and has no post-success object writes.  The boundary preserves live RAM and
checks the complete pool, globals, and the outer 12-byte frame before any
candidate write.

`tests/test_spawn_caller.py` compares complete original outer snapshots, frame
and PCM plus 150 native future instructions for all recorded fixture families
and free indices 0, 7, 23, and exhaustion.  It also checks aligned pool/frame
alias refusal before planning writes, deadline fallback for the whole outer
routine, and result/continuation/timing mutants.

Independent review at
`artifacts/grinding/luna/spawn-callers-1b680c-1b7374/caller-exit-review.json`
confirms all five pool states at the outer return after `1B681A`, including
position arithmetic, 150-native future, alias/deadline refusal, and three
controls.  The recorded strict witness is
`artifacts/grinding/terra/spawn-callers/recorded-witness/report.json`: state,
frame, PCM, 150-instruction future, safe restore, fresh entry/exit replay all
pass; result and continuation controls diverge and timing raises candidate
error.  The disposable edit loop changes only the semantic `+8` correction to
`+9` and changes PASS to DIVERGENCE without rebuilding the native DLL at
`artifacts/grinding/terra/spawn-callers/edit-loop/result.json`.

## Manual cost

The new semantic fact is the caller-specific position correction and template
identity.  The new machine work is only the measured prefix, BNE/RTS branch,
word-subtraction CCR residue, outer return, and combined fixed costs.  It
reuses reverse allocation, initializer/placement semantics, pool and alias
admission, the immutable planning view, `AtomicPlan`, and existing recovery
scheduling.  It adds no sound seam, continuation, snapshot state, native API,
or ROM decoder.


## Frozen integration

`artifacts/grinding/terra/spawn-callers/final-suite.xml` records **1,112
passing tests**, no failures, errors, or skips in 52.523 seconds.  The six
explicit terminal comparisons are `final-old-225`, `final-new-244`,
`final-late-115733`, `final-late-120021`, `final-late-120456`, and
`final-late-120812` under `artifacts/grinding/terra/spawn-callers/`.  Each
passes complete terminal state, frame, and PCM comparison; the compact receipt
audit at `final-replay-audit.json` confirms both original/candidate receipts
match the frozen current 19-module source tree.
