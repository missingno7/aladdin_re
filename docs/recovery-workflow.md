# Recovery workflow: current tooling and limits

## Observed repetition

The spawn region, reverse caller, and upper caller witnesses copied the same
roughly 90-line sequence: restore a parked entry, read its saved return, run the
original to PC plus A7 identity, compare an admitted candidate, continue 150
native instructions, restore a safe exit, run fresh-process replays, and reject
three mutants. Their edit-loop scripts also copied source isolation, native DLL
selection, subprocess comparison, timing, and report assembly. One upper witness
still described the reverse caller in its title.

Full-corpus runners and parent reviews separately parsed receipts. A recent
batch summary reported ERROR before its worker finalized a PASS comparison.
Completed comparison files, not the launcher's summary, are the evidence.

## Consolidated now

- `scripts/return_region_witness.py`: the existing strict sequence, shared by
  three small region wrappers. Each wrapper supplies allowed entries and capture
  provenance. Saved return PC and A7 remain fixture-derived. This supports an
  ordinary guest return, a single admitted candidate, no intervening input,
  and 150 native future instructions. It is not a universal carrier executor.
- `scripts/semantic_edit_check.py`: disposable source-copy comparison with an
  exactly-once semantic replacement. The three wrappers retain the actual
  game-specific mutation. The build DLL is pinned and its hash must not change.
- `scripts/audit_recovery_receipts.py`: read-only completed-report audit. It
  rejects missing terminal fields (including missing on both sides), unequal
  state/frame/PCM/time/register continuation counts, non-PASS status, differing
  source inventories, and a different native binary. The CLI requires one expected replay per comparison and checks its hash. It does not establish corpus completeness:
  callers must explicitly supply every required comparison file.

Existing witness/edit CLI commands and report keys remain available. No game,
boundary, native, admission or snapshot behavior was changed by this tooling
consolidation. Pending upper-caller gameplay edits belong to the preceding
recovery milestone, not this change.

```powershell
$env:PYTHONPATH='src;scripts'
$env:ALADDIN_NATIVE_LIBRARY="$PWD/build/libaladdin_native.dll"
.venv/Scripts/python.exe scripts/spawn_caller_witness.py --fixture <entry.alsnap> --output <directory>
.venv/Scripts/python.exe scripts/spawn_caller_edit_loop.py <directory>/witness.alreplay --output <edit-directory>
.venv/Scripts/python.exe scripts/audit_recovery_receipts.py <comparison1.json> <comparison2.json> --replay <recording1> --replay <recording2> --output <audit.json>
```

## Evidence for this consolidation

All three concrete wrappers ran against real local original-entry fixtures at
1B5266, 1B6802, and 1B735E. Strict exit, frame/PCM, 150 native instructions,
safe restore, fresh entry/exit process replay, and all three negative controls
passed. Reports are under `artifacts/workflow-consolidation/{region,caller,upper}`.
All three edit checks pass and reject their semantic mutation: PASS approximately
0.70 seconds, rejection 0.61--0.64 seconds; no native build or installation.
The new receipt auditor accepts those three actual comparison files.
Sixteen ROM-independent tests reject stale identities, missing fields,
false summary success, and wrong replay identity. This is tooling validation,
not a new full-corpus/gameplay qualification claim.

## Deliberately manual

Semantic names, useful parent selection, supported aliases, finite branch
classification, and timing/CCR derivation remain explicit. Incoming CCR alone
is insufficient: coordinate carry exposed a shared boundary defect. Region
qualification must vary arithmetic operands as well as incoming flags.
The existing allocator ROM recognizer remains narrow; do not generalize it to
arbitrary instruction streams. Historical persistent/synchronous sound and
ownership experiments have different contracts and were not forced into this
ordinary-return witness. Their evidence remains intact.

## Next justified tooling target

Consolidate original replay capture around a bounded input-aware advance loop
with PCM draining and a game-specific classification callback. Several census
scripts already repeat that loop. Fixture identity must include replay hash,
entry, occurrence and classification; stem-only keys can overwrite corpora.
Keep recorded and constructed provenance separate. Capture reproduction should
be tracked; ignored local snapshots must not silently determine test coverage.

Before building a recovery graph, finish the 1AE3FC activation/iteration map:
its probe reaches unknown callbacks/reentries, so current evidence does not
prove whole-iteration ownership. A frontier listing may derive observed targets
and fixture provenance, but must show incomplete/unknown edges. Do not infer
qualification from a report filename or a raw hit count.

The next corpus improvement is one synchronous batch command using the existing
comparison runner and this auditor, with an explicit input list and source freeze
checked before/after execution. No region manifest, MCP server, registry or
new execution framework is needed for the demonstrated duplication.

Review hardening: witnesses pin the build DLL and record execution identity;
disposable edit subprocesses disable bytecode writes so same-size mutations
cannot reuse the baseline cache. CLI replay identity is covered by a negative
test, not only by the library-level audit test.
