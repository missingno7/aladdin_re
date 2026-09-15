# Archive: frozen historical material

Everything here is evidence of what was believed, measured or decided at the
time it was written.  It is not operating guidance: commands, paths, package
names, environment variables and artifact formats are those of its day
(`aladdin_sega.machine`, `libaladdin_native.dll`, `ALADDIN_NATIVE_LIBRARY`,
`docs/STATUS.md`, `.alsnap`/`.alreplay`, `tests/test_*.py`, `scripts/*.py`
for what is now `scripts/aladdin/*.py`).  Nothing here has been rewritten to
match the current architecture; the current replacements are named below.
The lessons are summarised, with what replaced them, in
[../aladdin/convergence.md](../aladdin/convergence.md).

## `project/` — the studies and audits that shaped the shared method

| document | what it was | current replacement |
|---|---|---|
| `aladdin_re_implementation_spec.md` | the original specification (12–13 September): snapshot format, recording workflow, verification, carrier | `../common/` |
| `architecture-review.md` | "is this the smallest useful recovery system?" (13 September) | `../common/architecture.md`, `../common/machine-ownership.md` |
| `ownership-boundary.md` | where exact machine semantics belong: the experiment that produced the semantics/boundary/policy split (13 September) | `../common/recovery-process.md` §6–7 |
| `recovery-workflow-2026-09-13.md` | the workflow document of the history redesign | `../common/recovery-process.md` |
| `solo-recovery-handoff-2026-09-14.md`, `solo-recovery-goal-2026-09-14.txt` | the single-agent handoff and goal of 14 September | `../aladdin/recovery-playbook.md`, `../aladdin/grinder-goal.md` |
| `recovery-factory-review-2026-09-14.md` | the process-engineering review that produced the tracer, the status classifier and the grinder protocol | `../common/recovery-process.md` §5, §9 |
| `execution-model-research-2026-09-14.md` | the study of execution models; landed the decoupled observation instant; rejected coroutines, mixed-mode runtimes, whole-frame plans | `../aladdin/convergence.md` §8 |
| `replay-evidence-at-scale-2026-09-14.md` | how evidence should scale with history length; produced the path-signature census and the segment check | `../aladdin/convergence.md` §7 |
| `astra6-independent-audit-2026-09-15.md` | the independent audit of the native runtime; produced the independent contract | `../aladdin/native-frontier.md` §1 |

## `aladdin/` — Aladdin's own reports and logs

| document | what it was |
|---|---|
| `status-log-2026-09-12-to-16.md` | the chronological status log, every milestone with its numbers (the former `docs/STATUS.md`) |
| `recovery-cost-log.md` | per-milestone cost observations |
| `STATUS-pre-history-2026-09-13.md`, `recovery-workflow-pre-history-2026-09-13.md` | status and workflow before input histories replaced snapshot replays |
| `current-state-review.md` | a working-tree review before the history redesign |
| `recovery-first.md`, `recovery-progress.md`, `component-migration.md` | the first recovered regions and the donor-component separation |
| `carrier-convergence.md` (0.6, NOT CONVERGING), `synchronous-seam.md` (0.7), `semantic-migration.md` (0.8) | the three experiments that fixed the plan, the seam and the semantics split |
| `collection-subsystem.md`, `contact-*.md`, `spawn-*.md` | the per-family reports of the first grinding week (addresses, fixtures, decisions) |

Current Aladdin documents: [../aladdin/](../aladdin/).
