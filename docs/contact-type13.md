# Type-13 contact allocation retirement

`1AEC00` now composes the type-`0x13`, zero-counter retirement arm through
`1AF1AC`. The direct entry, wrappers `1AE9C6`/`1AE9DA`, and the existing
`1ABC82` dispatcher share the same bounded operation. The internal `1AECD8`
type-13 exhausted-pool arm is an oracle only; no new production gate was added.

## Bounded behavior

The callee clears/releases the retiring record through `1AE372`, initializes
that source with `1B7CC4` through `1AE30A`, then scans the measured 24-slot pool
from `FF8470` down to `FF7E82` in `0x42`-byte steps. A free destination is
initialized with `1B8368`, receives the source coordinates with its Y word
reduced by `0x20`, gets byte `+9 = FF`, and publishes `FFF124 = 08`.

The source may equal one complete pool slot because the first initializer makes
it active before the reverse scan. A partial pool overlap, overlapping
stack/global/buffer span, or unaligned source is refused before candidate
writes. Exhaustion leaves `A5 = FF7E40` and returns without the second
initialization, position transfer, transition flag, or sound helper.

Every free-slot arm enters original stateful helper `1E58F4`. Its measured
five-register frame is 20 bytes at `S-20..S-1`, with JSR return slot
`S-24 = 1AF1F6`. The existing synchronous runner is reused with those measured
dimensions, retaining PC, stack, frame, return-slot, deadline, foreign-return,
and snapshot checks. When `FFF57F == 0`, Python restores and returns through
`1AECEE`. When it is nonzero, the fixed helper remains committed but the
distinct optional command-`0x14` request/flush suffix stays original at
`1AF1F6`; that is a local suffix fallback, not recovery of command `0x14`.

## Qualification and limits

`1AF1AC` has **zero recorded hits in all six current user replays**. Type-13
proof is synthetic original-ROM qualification, not gameplay coverage. Old/new
`1AECD8` snapshots cover first-free, second-free and exhausted pools, both
`FFF57F` values, both direction prefixes, direct/C6/DA wrappers, dispatcher
composition, strict outer state/frame/PCM, and 150 native future instructions.
The exhausted `1AECD8` arm is separately compared as an internal oracle.

The allocator itself has recorded coverage: all six original-ROM replays contain
118 calls, selecting free indices 0 through 7. 117 return to `1B525A` and one
to `1AC260`; those callers establish the reusable reverse-pool contract, not
type-13 gameplay witnesses. See
`artifacts/grinding/luna/allocator-census/allocator-contract.md`.

The focused synthetic suite is `tests/test_contact_type13.py`, including a
deadline case where the fixed-helper prefix commits and native code resumes
when the remaining scheduler window cannot admit the helper. Final full-suite
and replay receipts are retained under `artifacts/grinding/terra/`.

Final frozen evidence is `type13-final-suite.xml`: **1,021 tests, no failures,
errors or skips, 46.573 seconds**. `type13-final-replay-audit.json` records six
PASS comparisons for the explicit old-225, new-244, and four later recordings;
every reference/candidate/current receipt agrees on all 19 Python modules and
terminal state, frame and PCM. `type13-edit-loop-strict/result.json` passes in
1.199 seconds and rejects a one-slot reverse-allocator mutation in 1.239
seconds with the build DLL unchanged and no build or installation. Synthetic
result, continuation and timing mutants each diverge or reject. Aligned partial
pool, frame and global overlaps reject without planner writes; a tight deadline
also matches the complete original outer state and 150-instruction future.

New semantic work is the reverse allocator and allocation-backed type-13 state
change. New handwritten machine accounting covers the scan, template calls,
position writes, caller returns, and 20-byte helper frame. Existing release and
initializer semantics, planning views, AtomicPlans, wrappers/dispatcher, and
the synchronous runner are reused. No continuation object, scheduler rule,
native API, or persistent mirror was added.
