# Spawn-region allocation and placement

The lifecycle candidate owns the four adjacent entry arms `1B524E`, `1B5256`,
`1B525E`, and `1B5266` through the shared `1B526C..1B529E` initializer and
placement tail.  `1B5266` was rechecked as `BSR.W 1AE262`; `1AFD12` is inside
an unrelated instruction and is not an entry.

## Recovered behavior

Each arm selects an inactive 66-byte primary-pool object, initializes it with
the caller's 19-byte `A6` template through the established `1AE30A` effect,
stores `D2` and `D3` at offsets `+0x32/+0x34`, writes positions from
`FFF150 + FF7DB0` and `FFF152 + FF7DB2`, clears `(A2,D2.W)`, and returns with
the measured `D0`/CCR residue.  The selectors are live-RAM scans:

| Entry | Selector | Pool view | Direction | Exhausted A5 |
|---|---|---|---|---|
| `1B524E` | `1AE27A` | `FF7E82`, 24 slots | ascending | `FF84B2` |
| `1B5256` | `1AE292` | `FF8470`, 24 slots | descending | `FF7E40` |
| `1B525E` | `1AE2AA` | `FF8368`, 20 slots | descending | `FF7E40` |
| `1B5266` | `1AE262` | `FF7F06`, 20 slots | ascending | `FF842E` |

The views overlap, so every admitted arm guards the complete 24-slot primary
pool.  It also rejects an unsafe template, stack frame, globals, or indexed
clear alias before any candidate writes.  The allocator itself is pure semantic
source in `game/objects/lifecycle.py`; the boundary retains the measured scan,
template, stack, register, CCR, and timing recipes.

The initial upper-exhaustion mismatch was traced to the candidate's exhausted
`A5` constant (`FF8436`) rather than a device scheduling difference.  The
measured value is `FF842E`; with that correction, its whole 884-cycle,
86-instruction plan is byte-identical to the original machine snapshot.  The
arm remains one admitted operation and adds no split continuation or new
execution mechanism.  Six further full-ROM exhaustion comparisons derive the
same enclosing state from recorded `1AE262 -> 1B526A` stops at distinct replay
device phases; each compares strict outer state and 150 native instructions.

## Evidence and limits

The six-replay original census records 27 `1B524E` entries, 117 `1B5256`
entries, 224 `1B5266` entries, and 2,278 direct `1AE262` calls.  Direct
selector counts are not presented as enclosing-arm coverage.  No recorded
exhaustion or indexed-clear alias is claimed; free-index, final-index,
exhaustion, and alias cases are constructed from recorded stops and checked
against the original USA ROM.

`tests/test_spawn_region.py` and Luna's independent
`tests/test_spawn_region_review.py` compare complete outer snapshots, frame,
PCM, and 150 native future instructions for all four arms.  They cover first
and second free slots, lower/upper final slots, exhaustion, deadline fallback,
and planner-before-write alias rejection.  The upper exhausted-plan test spans
the recorded old/new/later `1AE262` selector phases in addition to its recorded
`1B5266` fixture.  The recorded `1B5256` and `1B5266`
witnesses pass strict exit, safe restore, fresh-process entry/exit continuation,
and result/return/timing controls at:

- `artifacts/grinding/terra/spawn-region/final-witness-1B5256/report.json`
- `artifacts/grinding/terra/spawn-region/final-witness-1B5266/report.json`

The disposable edit loop changes the semantic indexed clear from zero to one
and changes the recorded upper-arm verdict from PASS to DIVERGENCE without a
native build or installation:
`artifacts/grinding/terra/spawn-region/final-edit-loop/result.json`.

Frozen final evidence is `artifacts/grinding/terra/spawn-region/final-suite.xml`:
**1,063 tests with no failures, errors, or skips in 49.665 seconds**.  The six
explicit comparison receipts are `spawn-region-final-{old225,new244,late1,
late2,late3,late4}` under `artifacts/grinding/terra/`; each passes and both
reference and lifecycle receipts match all 19 current Python module hashes.
Their compact audit is
`artifacts/grinding/terra/spawn-region/final-replay-audit.json`.

The region itself has no sound or device call.  It does not recover unrelated
standalone selector callers or caller-specific post-return customization.
Those continue through original code.

## Cumulative recovery shape

Recent contact, selector/decrement, type-13, and spawn work adds small pure
object semantics: contact predicates and decay, the finite script selector,
reverse allocation/type-13 effects, and this placement residue.  Each reuses
live RAM, existing release/initializer effects, planning views, `AtomicPlan`
admission, wrapper/dispatcher composition where recorded, and the one
synchronous sound seam where the original calls it.  The new manual work is
limited to measured branch costs, CCR residues, caller frames, and return
addresses.  Stable game behavior lives under `game/objects`; `boundary.py` and
`recovery.py` are machine-facing carriers.  No persistent mirror, generic
continuation, scheduler rule, or native API was introduced.
