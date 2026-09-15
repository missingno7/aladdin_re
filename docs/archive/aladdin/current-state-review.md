> **Historical document** (archived 16 September 2026).  Kept as written: its
> commands, paths and names are those of its day.  The current replacement is
> named in [../README.md](../README.md); the lessons are summarised in
> [../../aladdin/convergence.md](../../aladdin/convergence.md).

# Historical combined working-tree review

This records the pre-history-redesign checkout review. For current status see
[STATUS.md](status-log-2026-09-12-to-16.md). The indexed-clear regression now lives in
`tests/test_spawn_oracle.py`. The subsequent spawn-neighbor milestone qualifies
`1B6ED0` and fixes gate preservation across normal and deadline sound returns.


Main remains `498f531`. The working tree combines the dispatcher iteration
milestone with further caller recovery from another task. It now directly
composes 16 callback targets within one admitted iteration. Dispatcher setup,
lookup, empty slots and remaining callbacks still execute originally; this is
not whole-dispatcher ownership.

## Findings

- The previous six dispatcher-iteration replay receipts refer to different
  versions of `boundary.py`, `recovery.py`, `recovered.py`, and
  `game/objects/lifecycle.py`. Their PASS status is historical evidence only.
- A constructed indexed clear inside the saved MOVEM frame exposed a real
  mismatch: with `A2=entry_A7-60+5`, `D2=0`, and `D1=12345678`, the original
  restores `D1=12005678`; the candidate incorrectly restored `12345678`.
  Admission now excludes indexed-clear overlap with the saved frame and return
  slot before materializing any writes. The regression lives in
  `test_spawn_dispatch_iteration.py`.
- ROM opcode `D0C5` at `1AE472` is `ADDA.W D5,A0`. The signed-word implementation
  agrees with original probes using D5 values `10`, `10010`, `8000`, and
  `FFFFFFF0`; two original-mapping notes incorrectly called this ADDA.L and
  have been corrected.
- `1B6ED0` is a partial addition: it is enabled separately in `Candidate.arm`
  rather than declared in `gate_pcs`, and no dedicated test or witness was
  found at review start. This needs explicit qualification and consistent gate
  registration before publication. A corpus PASS alone cannot close that gap.
  Subsequent build-pinned read-only qualification found no semantic mismatch
  across four recorded direct fixtures (both saved returns) and synthetic
  exhaustion, including strict outer state and 150 native future instructions.
  See `artifacts/grinding/terra/review-1b6ed0-report.json`. That local probe is
  not yet a tracked regression test or complete witness.
  This is also an execution-coverage defect: `_run_sound_seam` restores gates
  from `gate_pcs`, so the separately appended gate disappears after a sound
  seam. Test gate-set preservation across that seam when consolidating the
  declaration; original fallback can conceal this loss in replay equality.
- New direct caller tests use local fixture globs. They do check nonempty
  fixture sets, but fixture inventory and capture reproduction remain an
  outstanding workflow concern. Several new parent cases are explicitly
  constructed, rather than captured parent activations.

## Verification performed

All runs pin `build/libaladdin_native.dll`.

- Before the correction: 1,409 tests passed in 90.50 seconds.
- After the correction: 1,410 tests passed in 77.05 seconds;
  `artifacts/current-state-review/final-suite.xml`.
- Focused dispatcher call/iteration: 29 tests passed.
- Current iteration witness passes strict exit state/frame/PCM, 150 native
  future instructions, safe restore, fresh-process entry/exit replay and all
  result/continuation/timing negative controls;
  `artifacts/current-state-review/witness/report.json`.
- Disposable edit check passes in 0.85 seconds and rejects the wrong
  continuation in 0.78 seconds, without a native build or binary change;
  `artifacts/current-state-review/edit/result.json`.
- All six explicit replay comparisons passed; see
  `artifacts/current-state-review/corpus-audit.json`. The completed reports
  were reaudited against current source inventory, build DLL and each expected
  replay hash. State/frame/PCM and terminal timing/continuation fields match.
  Source identity remained stable across the batch. This qualifies recorded
  behavior, not every admitted synthetic domain or uninterrupted gate coverage.

No whole-subsystem completion or publication is claimed by this review.
