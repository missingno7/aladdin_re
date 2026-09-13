# Frozen historical evidence

This report preserves ROM mapping, qualification, and recovery decisions at its source freeze. It is not current operating guidance: use the immutable cold-start input-history workflow in [../history.md](../history.md). Current commands do not promise to load legacy replay or snapshot artifacts referenced below.

# Shared semantics in production — 0.8.0

13 September 2026, Windows x64. **CONVERGING for this existing cluster.**
The [ownership experiment](ownership-boundary.md) is now migrated across all
existing callers. There is one production representation, not parallel strict
and semantic candidate modes. No new ROM region or candidate domain was added.

`recovered.py` contains five shared game functions: buffer release, pair clear,
template initialization, decimal-counter increment and linked-object unlink.
They read live RAM through a checked reader and return staged byte effects.
They contain no guest stack, D/A registers, CCR, timing, instruction counts,
AtomicPlan, admission, replay, mutant or continuation policy.

`boundary.py` owns the exposed ROM-entry and sound-seam contracts. Its single
buffer/pair adapter validates the current RAM domain, determines buffer lengths,
calculates aggregate cost and emits final stack residue. Both standalone entries
and the replacement, cleanup and detach callers use these same semantic bodies.
`recovery.py` still owns gates, admission/fallback policy and fault controls.
The native executor and the 0.7 synchronous sound route are unchanged.

## Actual deletions

- Removed `_clear_buffer_effects` and `_clear_pair_effects` from production.
  One `_clear_objects` boundary adapter replaces their duplicated validation,
  length/cost calculations and nested-frame reconstruction.
- Internal callers no longer construct the pair's AtomicPlan, return PC,
  register dictionary or final CCR. The external pair entry still constructs
  its own exact plan because original callers can observe that boundary.
- Removed duplicated buffer-clear and template-expansion write loops. Every
  existing entry now executes the bodies in `recovered.py`.
- Replaced intermediate BSR/save histories with final residue. Replacement and
  cleanup collapse overwritten writes within their already admitted RAM-only
  spans. The repeated null-buffer clear in cleanup needs no second semantic
  call; its remaining stack bytes are retained.
- Extracted counter and unlink behavior from their machine adapters. No second
  mutable object model, new scheduler, native primitive or continuation system.

The new file is not counted as free infrastructure. Combined game + boundary
source falls from **389 to 352 physical lines** (47 + 305), a net deletion of 37.
The prior disposable hybrid would have required 459 lines because its old helper
definitions remained necessary elsewhere; this migration removes that duplication.
Some outer flow and accumulation arithmetic remain machine-like in the boundary
module. This is a shared-helper migration, not a claim that entire surrounding
routines have become semantic source.

## Same contracts and observers

Original entry addresses remain `1AE372`, `1ABE6E`, `1AD0FC`, `1AE30A`,
`1AE954`, `1AF4C2`, `1AF4C6` and carrier `1AF468`. Original sound still executes
`1E58B8` and `1E589A`, returning to Python at `1AF498` under the existing
PC/SP/saved-frame identity check. Capped/unsupported inputs and deadline/scheduler
refusals keep the same fallback behavior.

The [observability analysis](ownership-boundary.md#observability-with-the-limits-of-the-evidence)
still governs deletion. Final stack residue is preserved, including bytes below
A7. Final registers, CCR, continuation, last PC, cycles and instruction counts
remain exact. Intermediate values are removed only inside a non-aliasing RAM
span admitted by the existing native observer/device/IRQ guards. The verification
contract has no ignored bytes or new masks.

Portable snapshot rules are unchanged: safe entry/exit and explicit original-
ownership handback are supported; an active synchronous sound call cannot be
serialized. Frozen 0.6 inside-callee persistence evidence remains available.

## Measurements against frozen 0.7

Baseline: `a72ed9e00fa8f24000e4df9fe4e3a29d4c7a68cc`. All execution measurements
use the same native DLL, ROM, cold-start user replay and 0.6 short witness.
The checked-in tests and measurement tools are qualification code; their changes
are not included in the production LOC reduction.

| Measure | 0.7 | 0.8 |
|---|---:|---:|
| Mixed recovered source, physical LOC | 389 | 0 |
| Shared semantic source, physical LOC | Included above | 47 |
| Boundary source, physical LOC | Included above | 305 |
| Combined game + boundary LOC | 389 | 352 |
| Dispatch LOC | 231 | 231 |
| Machine/artifacts/CLI/frontend LOC | 848 | 848 |
| Combined production surfaces above | 1,468 | 1,431 |
| Plan constructions, short carrier | 4 | 3 |
| Native atomic executions, short | 2 | 2 |
| Replacement write bytes, short | 77 | 63 |
| Shared byte-expansion calls, short carrier | 26 | 11 |
| Base gates / distinct including sound return | 7 / 8 | 7 / 8 |
| Gate stops / gate-set calls, full | 2,085 / 157 | 2,085 / 157 |
| Python/native execution crossings, full | 35,248 | 35,248 |
| All measured API crossings, full | 247,180 | 247,180 |
| Direct semantic calls, short / full | 5 / 1,041 | 5 / 1,619 |
| Original sound spans entered / Python returns, full | 78 / 76 | 78 / 76 |
| Fallbacks, full | 4 | 4 |
| Replaced M68000 instructions, full | 58,652 | 58,652 |
| Charged M68000 cycles, full | 902,420 | 902,420 |
| Persistent continuation records | 0 | 0 |
| Forced-cold short comparison, seconds | 1.127 | 1.074 |
| Full comparison, seconds | 65.993 | 65.997 |
| Full replay observations | 225 PASS | 225 PASS |

Crossings use the established convention: twice `(run + atomic)` for execution,
twice all measured API calls for total API crossings. Source extraction is outside
timing; comparisons run serially with empty bytecode caches. Single samples do
not establish a speedup.

The extra 578 reported direct semantic calls are **not new game recovery**:
583 existing detach activations now explicitly call the extracted unlink helper,
including its null case, while five cleanup activations no longer count the
redundant null-buffer clear. Other entry counts and admitted behavior are identical.
This change is reported rather than used as an architectural success score.

The deletion signal is one shared implementation, fewer internal machine
contracts and lower combined production LOC. No reduction in native crossings
is claimed: 0.7 already composed these calls inside the same admitted regions.

## Verification and fast edit loop

- All **253 production tests** pass. Existing native fixtures cover standalone
  entries and composed callers, null/linked buffers, maximum lengths, template
  sources, carry/CCR cases, aliases, silent/capped paths and sound/deadline cases.
  Tests importing entry adapters now use the existing recovery entry surface;
  the cleanup direct-call expectation changes because its redundant call is gone.
- The real short witness matches all native state bytes, RAM/registers, exact
  exit tick, frame and PCM; **150 subsequent original instructions** also match.
- Safe-exit snapshot and fresh-process continuation, in-call snapshot rejection,
  original-ownership deadline handback and exact inside-sound input timing pass.
- Wrong result, wrong continuation and wrong timing controls are rejected.
  A real semantic source edit changing buffer clear 0→1 changes PASS to DIVERGENCE
  in **0.599 s** (unedited 0.656 s), with zero builds/installs and the same DLL.
  That disposable-copy loop allows ordinary standard-library bytecode caches;
  it is distinct from the forced-cold timings above.
- The full 225.02-second recording passes all **225 observations**, complete
  terminal state/frame and whole-run PCM. Both source versions produce observation
  stream SHA-256 `09477e90802b93bb1485df361f83f2c0777d7145ee5be9e600083f66fe96d551`.
- The architecture guard passes and now rejects machine-effect imports/construction
  in semantic source. Frozen **19** persistent-continuation tests still pass.
  The earlier ownership experiment still reproduces its 202 checks, passing
  hybrid, rejected source edit and rejected short no-residue control. It now
  extracts its original tests so changing production cannot rewrite its evidence.

Evidence: `artifacts/migration/{economics,witness,edit-loop,effects.json,
frozen-experiment-check}`. The unchanged development DLL SHA-256 is
`e801a550885dc598c2a5b84941b6c92c803267c4e49ef4b57660163c251b430a`.
No native source or verification policy changed.

After source qualification, one final wheel installation updated the local
launcher to 0.8.0. Installed Python module hashes match the checkout and the
native source identity is unchanged. The installed carrier passes the short
comparison; original play also resumes the safe exit snapshot for 60 muted
frames. This packaging step is outside the Python edit-to-verdict measurements.
Its receipts are `artifacts/migration/installed-{receipt.json,short,player.json}`.

Reproduction from the repository root:

```powershell
$env:PYTHONPATH='src'
$env:ALADDIN_NATIVE_LIBRARY="$PWD/build/libaladdin_native.dll"
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/synchronous_witness.py --output artifacts/migration/new-witness
.venv/Scripts/python.exe scripts/edit_loop_check.py artifacts/carrier/witness-v060/witness.alreplay --candidate carrier --output artifacts/migration/new-edit
.venv/Scripts/python.exe scripts/seam_economics.py --baseline a72ed9e00fa8f24000e4df9fe4e3a29d4c7a68cc --output artifacts/migration/new-economics
```

## Next recovery rule

The same-cluster migration gate from the previous report is satisfied. Further
recovery can use semantic helpers inside one qualified outer adapter; it should
not reintroduce a helper-level plan merely because the original used a BSR.
Retain original sound/device execution until its specific semantics are known.
Select the next region from current traces and coverage, and measure combined
source and boundary costs again. This bounded result does not prove that every
larger region will converge.
