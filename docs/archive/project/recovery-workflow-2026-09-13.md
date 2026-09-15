> **Historical document** (archived 16 September 2026).  Kept as written: its
> commands, paths and names are those of its day.  The current replacement is
> named in [../README.md](../README.md); the lessons are summarised in
> [../../aladdin/convergence.md](../../aladdin/convergence.md).

# Recovery workflow

For sustained single-agent work, see [Solo recovery handoff](solo-recovery-handoff-2026-09-14.md).

Recovery work now uses immutable cold-start input histories.  A history is a
canonical controller-input DAG, not a machine-state artifact.  The selected ROM
and native binding replay each branch from its root; caches only accelerate a
compatible reconstruction and never prove a candidate.

## Capture and classify

Use the player to create a real input branch, then name the relevant node and
record the ROM entry, occurrence, return PC, input frame, and whether coverage
is recorded or constructed.  A checkpoint is a presentation point on an
existing input path, not an opaque state to edit or pass between recovery
workers.

Use `history-capture` only for deliberately constructed smoke paths.  Keep that
provenance explicit.  It does not substitute for new player histories when
claiming a recorded branch.

## Verify

Every candidate comparison starts separate fresh original and candidate workers
from the cold root.  `history-verify` compares complete observations for every
canonical frame: machine state, rendered frame, PCM, and terminal execution
fields.  `--tree` runs the current DAG from root and constructs prefix states
only in that verification invocation.  It cannot consume persistent player
caches.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --game aladdin --candidate lifecycle --output artifacts\candidate
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --game aladdin --candidate lifecycle --tree --output artifacts\candidate-tree
```

For a narrow recovered region, retain the existing strict outer-state contract:
record exact PC and A7/return-frame identity, run a native future, prove safe
fresh restoration where applicable, reject aliases and deadline handoffs before
candidate writes, and use result/return/timing mutations.  A whole-history PASS
does not replace these controls.

## Source identity and local editing

Run source-tree commands through `scripts/dev.py`, `play.cmd`, or `play.ps1`.
They set `PYTHONPATH` to this checkout and pin
`build/libgenesis_native.dll`; they never reinstall packages.  Rebuild only when
native code or packaged dependencies actually change.  A no-build edit loop
must mutate a disposable semantic copy and demonstrate rejection against a
real or constructed witness while the pinned DLL hash is unchanged.

`scripts/history_edit_check.py` performs that check with `--game`, `--candidate`, `--node`,
`--source`, `--needle`, `--replacement` and `--output`. The replacement must
match exactly once. Both baseline and mutated runs use the same cold history;
the script requires baseline PASS and mutation rejection, and verifies the
native binary was not changed. A 70-frame constructed initializer witness
takes about 1.9 seconds per verdict on the current machine.

`scripts/aladdin/oracle_witness.py` constructs explicit raw ROM entry states for short
allocator/dispatcher discovery qualification. These fixtures are deliberately
not gameplay histories. They compare strict outer state and 150 native future
instructions; `--all-callbacks --fresh-process` also checks the composed
dispatcher callbacks and fresh-process continuation. This keeps synthetic
boundary discovery separate from the portable input-history model.

## Deliberately manual work

ROM mapping, parent selection, supported-data domains, alias boundaries, timing
and CCR recipes, and the difference between recorded and constructed coverage
remain explicit review work.  The history system does not infer them and is not
a replacement for original execution as the oracle.  Do not introduce a generic
continuation framework or treat cache state as a second game-state authority.

## Historical workflow evidence

The prior witness, replay, snapshot, and receipt reports are preserved in
[archive/recovery-workflow-pre-history-2026-09-13.md](../aladdin/recovery-workflow-pre-history-2026-09-13.md)
and the subsystem reports.  They are frozen milestone evidence only.  Current
commands do not promise that their old loaders or artifact formats remain
runnable.
