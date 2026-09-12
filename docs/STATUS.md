# Status — 13 September 2026

The architecture continuation is implemented on Windows x64. Python owns editable
Aladdin source, dispatch, artifacts and verification; a small machine API hides
retained Genesis components. Direct Nuked OPN2/PSG sources are now in this repo.
Original play remains the default; recovery is opt-in for replay.

## Diagnostic follow-up (0.2.1)

`compare --diagnostics` now captures terminal/failure PC, SR, all M68000 registers
and work RAM through the existing machine API. Reports include exact changed RAM
addresses, a bounded 32-byte listing and total count, register differences, and a
same-tick indicator. Fresh output directories retain the exact replay used by both
workers and their snapshots when capture is valid. Failed native execution retains
its original error and can expose inspection data without claiming a usable save.
This does not localize the first bad instruction or decode private device state.

Fallback counts now distinguish scheduler admission, unsupported data domains and
explicit legacy exits. Removed unused candidate aliases and no-op CLI options;
`play.cmd` and `play.ps1` use the simplified launch command. Artifact/state contracts
and native source are unchanged, so current recordings need no regeneration.

New diagnostic tests cover bounded address reporting, different stop ticks, failed
snapshot capture, noninterference with state/PCM, and fresh capture directories.
**75 Python tests pass.** The negative controls now show the wrong-store byte at
`0xFF8392`, register/PC differences for the invalid continuation, and different stop
ticks for wrong timing. The actual Python clearing-loop edit still changes PASS
to DIVERGENCE in about 0.6 seconds with the same native DLL and no rebuild/install.
The full composed replay again matches all 225 observations and terminal state,
frame and PCM, with the same 581 caller / 459 leaf hits and nine scheduler
fallbacks. Its diagnostic register/RAM diff is empty. Installed 0.2.1 passes the
composed short comparison with diagnostics and a 60-frame snapshot-resumed player
smoke using dummy SDL devices. The source-tree native DLL hash is unchanged.
Reports are under `artifacts/diagnostics-continuation/`, including
`full-composed/comparison.json`, `negative-controls.json`, `edit-loop/result.json`
and `installed-short/comparison.json`.

## Architecture changes

- Audited active compiler dependencies, not just the old lock. Runtime requires
  27 donor headers; 19 additional donor files are native-test-only. Session,
  census, input-script and verdict helpers do not compile into the native DLL.
- Compiled both independent sound cores directly from pinned project copies,
  with original licenses and byte hashes. Borrowed Genesis sound wrappers still
  use donor declaration headers; build checks enforce exact declaration equality.
  That remaining bridge is explicit, not a claim of full sound-adapter migration.
- Kept the working GenesisEngine, M68000/Z80, VDP and native state codec behind
  the project ABI. Four runtime framework headers remain transitively included.
  Their next removal triggers are recorded in the component ledger.
- Deleted `compatibility.py`, `qualify_baseline.py` and their obsolete transition
  tests. Removed compatibility CLI flags and source-transition plumbing.
- Version 2 archives use explicit machine-state contract 1. The behavioral
  profile no longer contains donor commit or private codec names. Source/build
  hashes remain exact execution provenance; Python treats native state as opaque.
- Separated game behavior into `recovered.py` and dispatch/mutant policy into
  `recovery.py`. Added explicit `LegacyExit(0x1ABE6E, reason)` for the open region.
- Added a lightweight architecture guard, intentional-leak test and tests that
  reject old formats/changed state contracts while allowing different build
  provenance under the same supported contract.

[component-migration.md](component-migration.md) contains the architecture map,
complete component inventory, ranked leakage findings and removal triggers.
[third_party/dependencies.json](../third_party/dependencies.json) is the generated
active compiler graph. Runtime-only disposable builds succeed without donor
session, census, input or verdict headers; changing locked bytes stops a rebuild.

## Current recordings and continuation

The original user archives remain untouched. Version 2 files were regenerated
from validated user input events, starting the current machine from cold boot,
and saving again at the original timestamps/input cursors. No native state
layout was decoded or patched in Python. These are derived copies of the same
coverage, not newly recorded gameplay.

Use the matching names under `recordings/current/`:

| Artifact | Tick / duration | SHA-256 |
|---|---|---|
| `20260912T210640.729016Z.alreplay` | 225.0231 seconds; 1,008 inputs | `f51c9192d35a1ed2d8839e5b04a747d61962860f6036ae90cde708ddb3965891` |
| `20260912T210626.701921Z.alsnap` | 11,342,074,505; cursor 964 | `c04e354361ae7cd3aff4d3315dbe32ac9b134197f9b092669262038db57134f1` |
| `20260912T210633.203951Z.alsnap` | 11,685,257,649; cursor 982 | `4892d8489c65e21807af9c2219353fd1d1fb580fd1b77e1053b08543988fd031` |

`recordings/current/provenance.json` records parent hashes and derivation. Both
saved states exactly match replay at their ticks. Their 44- and 26-input suffixes
match uninterrupted terminal state, final frame and all suffix PCM in fresh
processes. The installed 0.2.1 package supports these files; early version 1
archives are intentionally rejected with a regeneration message.

```powershell
.\play.cmd --snapshot recordings\current\20260912T210633.203951Z.alsnap
.\play.cmd --record-from-start
```

Level 1 → bonus → level 2 remains user-described coverage. Independent hardware
accuracy and broader scenario coverage are not established by replay agreement.

## Migration and recovery evidence

The pre-change package/DLL from `3b9cc76` is preserved locally under
`artifacts/architecture-20260913/previous/`. Running its original executor and
the current one from cold boot with identical validated inputs and the same new
behavioral profile yields **225 identical ordered state/frame/PCM observations**.
This is offline migration evidence, not a second production backend. Full state
hashes changed from old archives because snapshots include the profile digest;
we did not strip or patch serialized metadata to compare them.

```text
profile   371f1ac29f39f24d3f4d0afd5bf89abf445ea6eeb17748e31cbf980f2a0b1456
state     34af78131fd69200ed1b9bf6817ebaca53e76e368e5ffe5cfff9cfb3f6acd6e8
frame     d51bd1fb5a77cb7a6f41cef752a820c9e7e1a5484e1984c87083f2204ac047fa
PCM       878623149f19c75892fa5ef52833419e53df5096f4248ab12e27688de9200f16
PCM bytes 47,945,248
```

Frame and whole-run PCM hashes also match the historical run unchanged.
Comparison contract `full-machine-frame-pcm-60frames-v1` observes full state,
frame and PCM chunks every 60 frames plus terminal and complete PCM. It does
not claim equality at every unobserved instruction or independent hardware fidelity.

| Full regenerated user replay | Leaf hits | Caller hits | Fallbacks | Original M68000 instructions replaced | Direct Python calls |
|---|---:|---:|---:|---:|---:|
| Leaf: PASS | 1,040 | 0 | 7 | 21,023 | 0 |
| Composed: PASS | 459 | 581 | 9 | 27,579 | 581 |

The real buffer clear at `0x1AE372` and the open detach region at `0x1AD0FC`
use live RAM and immutable ROM, with no original execution to calculate their
answers. The caller directly composes the clear calculation and preserves its
rewritten guest return. Unknown script paths decline before effects through an
explicit legacy seam. Those branches have refusal tests but are not exercised
by this user scenario; no wider domain is claimed.

Both focused witnesses pass original-region equality, snapshot continuation
and fresh-process short replay. Wrong-output, wrong-continuation and wrong-timing
mutants are rejected by the production comparator. A disposable edit to the actual
Python clearing loop changes PASS to DIVERGENCE in about 0.6 seconds, with zero
native builds or installs. Atomic guard, gate, Z80/PCM overflow and restore tests
remain in place. [recovery-first.md](recovery-first.md) gives the exact domains.

## Validation and local reports

The current suite passes **71 Python tests** and **seven native CTest groups**.
Windows toolchain: Python 3.12.14, MinGW 12.2, CMake 4.4.3, Ninja 1.13.2.
Cold boot and snapshot round trip pass for 300 frames. The installed package's
snapshot-resumed player passes 60 frames with dummy SDL devices, and both
installed fresh-process save continuations pass. Dummy presentation is an
integration check, not subjective listening or interactive visual validation.

Derived reports are under `artifacts/architecture-20260913/`:

- `migration-comparison.json` and `before.observations.json`: pre/post native migration.
- `{leaf,composed}/comparison.json`: complete regenerated user corpus.
- `{leaf-witness,composed-witness}/report.json`: parked gates and safe continuations.
- `snapshots.json`, `installed-snapshots.json`: save equality and fresh suffixes.
- `mutants.json`, `mutant-*/comparison.json`, `edit-loop/result.json`: negative controls.
- `regeneration.json`, `installed-doctor.json`, `boot.stdout.json`: artifact/build provenance and startup.

Earlier audio diagnostics under `artifacts/intake-20260912` found the old pygame
queue discarded 12/180 chunks and inserted about 9.1% silence. The continuous
FIFO fixed that test; a 600-frame resumed session had zero underruns. The native
queue also now invalidates execution on overflow. This continuation preserves
that behavior; subjective listening and broader device coverage remain open.

## Necessity review of the current code

The [current architecture review](architecture-review.md) rechecked the actual
compiler graph and measured restore, short verification and full replay without
changing runtime code. The boundaries are proportionate to this game, but the
leaf/composed experiment is too small to demonstrate sustained scaffolding
convergence. `LegacyExit` is whole-entry fallback, not a Python/legacy/Python
continuation. The failing-witness register/RAM diagnostic follow-up above implements that
review priority; a new engine, emitter or generic continuation registry is not justified.

## Next bounded milestone

Recover the adjacent script dependency at the explicit `0x1ABE6E` seam, qualify
its actual return behavior, and compose it into the open region. Use focused
witnesses during editing and the full replay as the integration gate. Absorb
additional board/scheduler/sound glue only when that recovery exposes concrete
friction. No Linux build or speculative CPU rewrite is required. Public combined
source/binary distribution remains unresolved; ROMs and user artifacts stay local.
