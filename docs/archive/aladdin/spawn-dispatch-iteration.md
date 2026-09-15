# Frozen historical evidence

This report preserves ROM mapping, qualification, and recovery decisions at its source freeze. It is not current operating guidance: use the immutable cold-start input-history workflow in [../history.md](../../common/history-and-replay.md). Current commands do not promise to load legacy replay or snapshot artifacts referenced below.

# Bounded spawn dispatcher iteration

This report records the initial three-target milestone. Subsequent uncommitted
caller recovery expanded the current iteration to 16 targets. Its original
1,217-test and replay receipts do not qualify that expanded source inventory.
See `current-state-review.md` for the combined-tree review and alias correction.

The lifecycle candidate owns one selected callback iteration at
`1AE468..1AE47A`. Native code still performs dispatcher setup, table lookup,
and all following iterations. At the `MOVEM.L D0-D7/A0-A6,-(A7)` entry, the
candidate accepts only the table target already in `A4` when it is one of
`1B6802`, `1B7262`, or `1B735E`. It materializes the native 15-register save,
composes that existing callback through a planned RAM view, restores the same
frame, then applies `ADDA.W D5,A0`, `ADDI.W #$10,D6`, and `DBRA D4`. The
recovered iteration resumes native lookup at `1AE44A`, or the native dispatcher
RTS at `1AE47C` when the DBRA counter expires.

All other observed table targets remain native. Refusal occurs before the
MOVEM writes, so an unrecognized `A4`, an unaligned stack, or overlap with the
dispatcher frame, allocation pool, or position globals leaves the whole
iteration original. This does not claim ownership of the 16-slot loop: the
six-corpus map records 62 targets, only three of which are currently admitted.

The manual machine facts are intentionally small and local: save `128/1`, JSR
`16/1`, restore `132/1`, and tail `26/3` for a taken DBRA or `30/3` for its
final exit. `ADDI.W` supplies the final CCR, including X/C, while DBRA leaves
it intact. The known caller plans, live-RAM alias checks, AtomicPlan
application, planned views, and the ordinary native continuation are reused.
No semantic game source, continuation mechanism, persistent state, or native
API was added.

## Qualification

- `tests/test_spawn_dispatch_iteration.py` compares original and candidate
  outer state plus 150 native instructions for a real selected `1B735E`
  iteration from every replay, and one original iteration each for all three
  accepted targets. It covers unknown-target and frame/global/pool aliases,
  deadline fallback before MOVEM, both DBRA paths, and incoming-X/addition
  carry controls. The internal call/restore oracle remains in
  `tests/test_spawn_dispatch_call.py`.
- `artifacts/grinding/terra/dispatcher-iteration-witness/old-225/report.json`
  is a real selected iteration witness. It verifies the explicit `PC=1AE44A`
  and unchanged `A7` exit contract, strict state/frame/PCM, a 150-instruction
  native future, safe and fresh-process restores, and result/continuation/
  timing controls.
- `artifacts/grinding/terra/dispatcher-iteration-edit-loop/result.json`
  passes with the build DLL unchanged and rejects a disposable mutation that
  forces the DBRA continuation to the dispatcher RTS.
- `artifacts/grinding/terra/dispatcher-iteration-final-suite.xml` records
  **1,217 passing tests** in 57.110 seconds. The six explicit comparison
  receipts and current-source audit are under
  `artifacts/grinding/terra/dispatcher-iteration-final-*` and
  `dispatcher-iteration-final-replay-audit.json`; all report PASS with equal
  terminal state, frame, PCM, timing, and recursive source/native identities.

The next adjacent investigation is the recorded `1B7454` dependency, not an
unmeasured attempt to absorb the dispatcher loop.
