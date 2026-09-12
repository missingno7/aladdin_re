# Status — 13 September 2026

The review continuation preserves original play and the user's captures, fixes
confirmed reliability defects, and qualifies a Python helper and its adjacent
caller. Recovery is opt-in for replay; `play.cmd` still runs the original game.
Windows x64 remains the supported target per the user's decision.

## Review findings

Intake HEAD was `b3c78ace104a68d7dc3ba64670a8778483da8654`. Only README, STATUS
and the specification had uncommitted Windows-scope amendments. The baseline
Python package and DLL were preserved under `artifacts/baseline-b3c78ac`, with
hashes, before native changes. Original captures were never rewritten.

| Finding | Disposition | Change and executed evidence |
|---|---|---|
| A: configure-only validation / stale source ID | Confirmed, fixed | Disposable incremental build rejects a changed locked header without changing the DLL. Restoring it and editing the adapter refreshes the compiled ID. Toolchain/options are in build receipts. |
| A: exact source check blocks wrapper migration | Confirmed, qualified | Exact remains default. One named directional transition is tested; unknown, reverse and wrong-profile pairs fail. Preserved baseline/current full-corpus observations match. |
| B: ignored gates / non-progress | Confirmed, fixed | Explicit dispatch, diagnostics and bounded zero-time handling. Tests cover unexpected/recognized gates, bypass-once, same-tick events and unreachable input. |
| C: silent native PCM loss | Confirmed, fixed | A real undrained 121-frame run fails and invalidates execution. Chunked capture succeeds beyond that capacity. Explicit discard preserves chips; restore cuts old output and preserves future PCM. |
| D: single execution mislabeled PASS | Confirmed, fixed | Replay reports COMPLETED / compared:false. Fresh-worker comparison checks ordered state/frame/PCM observations and rejects zero-hit candidates. Three same-ROM mutants fail. |
| Fixed watchdog / unstructured timeout | Confirmed, fixed | Configurable guard and separate TIMEOUT, DEPENDENCY_FAILURE, CANDIDATE_ERROR and DIVERGENCE. Failure reports preserve completed checkpoints. |
| Python's fixed native trailer offset | Confirmed, fixed | Native versioned inspection owns timestamp validation. Bad imports and forged manifest timestamps leave state unchanged. |
| Save failure skips cleanup | Confirmed, fixed | Failed sessions retain a labeled valid input prefix and original exception. Save/audio/pygame cleanup is independent; injected tests need no ROM. |
| Reinstall required for Python edits | Confirmed, fixed | Source runner uses the existing DLL in fresh processes. Editing the real Python clearing loop changes PASS to DIVERGENCE with no native build/install. |
| Host music stutter | Already fixed before review | Continuous FIFO retained unchanged. Native overflow above is a separate defect; prior delivery measurements are retained below. |
| Independent console/video accuracy | Not established | Renderer still samples current VDP state. No full hardware or raster-fidelity claim. |

## Corpus and compatibility

`20260912T210640.729016Z.alreplay` is the existing 225.0231-second cold-boot
recording with 1,008 input changes, terminal tick 12,082,203,375. Level 1 → bonus
→ level 2 is user-described coverage; the later save's desert scene was visually
inspected during earlier intake. No new human coverage is claimed.

```text
recording cd63a64fd08a25887e99fbc9150f3b42c6ccc6a837a6b7dbd110ba980d6e21a3
state     8f15dafc6d6a4429e1e88c52421f6a13e27b74255d9d3bdda4ffc3aa2c521b18
frame     d51bd1fb5a77cb7a6f41cef752a820c9e7e1a5484e1984c87083f2204ac047fa
PCM       878623149f19c75892fa5ef52833419e53df5096f4248ab12e27688de9200f16
PCM bytes 47,945,248
```

Preserved baseline and current original execution match all **225 ordered
observations**. The observation files share SHA-256
`a5c0219682a7c689b9ead02ca837ae0a7700345cdc2ea2cd74447bcdfebcf369`.
Contract `full-machine-frame-pcm-60frames-v1` compares full snapshots, sampled
frames and PCM chunk hashes/counts every 60 frames plus terminal, and whole-run
PCM. It does not assert equality at every unobserved instruction or independent
hardware fidelity.

Both unchanged user saves again match replay at their exact timestamps. Their
fresh-process suffixes match uninterrupted final state, frame and PCM. These
checks also pass in the newly installed package, without source/DLL overrides.

| Snapshot | Tick | Next input / remaining | SHA-256 |
|---|---:|---:|---|
| `20260912T210626.701921Z.alsnap` | 11,342,074,505 | 964 / 44 | `5bc444e0ac82d9009c3673f8cb74a8c1e1e3d13eb4e92c4099cb787dcb1639bd` |
| `20260912T210633.203951Z.alsnap` | 11,685,257,649 | 982 / 26 | `b4b8241def59cdc244ee07d87b0c7c358a44b57f45363c25f3a2d5a66e4eb3a7` |

Capture provenance, loader compatibility and verification identity are separate.
Legacy captures identify native source/profile but did not record Python code.
Execution receipts now identify the artifact, native binary/source, build,
Python module hashes/path, interpreter and candidate; comparison names its
contract. Workers reject implementation-file changes during execution.
`review-baseline-v1` qualifies only the baseline source
`baf0418522d9332bcab75b407e0a66c0e41ed10a562ec819a7cd2104e315f40c` →
`51a3dab483142fc918862ab4a7dc768e0706ef750bd490acac5a76d08a441d5c`
under the current profile. Further native changes need explicit qualification.

## Replacement and composition

[recovery-first.md](recovery-first.md) records original bytes, aliases, flags,
stack effects, timing and conservative domains. Python replaces the auxiliary
buffer clear at `0x1AE372` and the adjacent detach caller at `0x1AD0FC`. It reads
live RAM and immutable ROM; original execution never calculates its answer.

| Full user replay | Leaf hits | Caller hits | Fallbacks | Original M68K instructions replaced | Direct Python calls |
|---|---:|---:|---:|---:|---:|
| Leaf | 1,040 | 0 | 7 | 21,023 | 0 |
| Composed | 459 | 581 | 9 | 27,579 | 581 |

Both pass all ordered and terminal comparisons; composed mode also passes in
the installed package. Original census is 1,047 leaf and 583 caller entries.
Watching both would require 1,630 gates; composition uses 1,049, eliminating
581 internal guest call round trips while preserving written guest return slots.
Actual interpreted M68K work decreases from 140,704,253 to 140,676,674 operations
in composed mode. Compatibility timing/counts are unchanged; the Z80 still
interprets 82,982,725 instructions. This is not a CPU-free port.

Plans enter the existing scheduler only at parked gates. Trace, IRQ, DMA,
deadlines and observers can refuse before effects. Running Z80 RAM banks are
refused; a bank change reaching RAM during execution is caught before access
and invalidates the machine. Both cases have runtime tests. There is no fallback
after partial effects. Unsupported caller branches explicitly return to original
execution at the untouched entry, including the `0x1ABE6E` dependency. Snapshots
are supported at completed boundaries, not arbitrary Python expressions.

Local comparisons cover the first real helper/caller activation, null and
maximum-length helper paths, flags/widths and alias refusal. Both real witnesses
pass region comparison, restored-snapshot continuation and fresh-process short
replay. Wrong-result, wrong-return and wrong-timing candidates are rejected by
the production full-corpus command, with last matching checkpoints and failure
intervals. A separate Python loop edit produced PASS in 0.72 s before editing and
DIVERGENCE in 0.67 s afterward; the DLL stayed unchanged, zero builds/installs.

## Validation and evidence

This review run: **70 Python tests passed, zero failed/skipped; seven native
CTest executables passed**. This includes the disposable build regression and
actual-ROM tests. Python 3.12.14, GCC 12.2, CMake/Ninja built and installed the
package. Installed doctor loads `.venv/Lib/site-packages/aladdin_sega`. Snapshot-
resumed `play.cmd --frames 60 --mute` passed with SDL dummy presentation devices.

Derived evidence remains local:

- `artifacts/review/baseline-final/qualification.json`: baseline transition.
- `artifacts/review/{leaf,composed,installed-composed}/comparison.json`: full corpus.
- `artifacts/review/mutant-*/comparison.json`: rejected mutants and diagnostics.
- `artifacts/review/edit-loop/result.json`: actual source edit-to-verdict check.
- `artifacts/review-installed-snapshots.json`: installed fresh save continuations.
- `artifacts/recovery-recon/reusable-{leaf,composed}/`: local witnesses/safe saves.

[README.md](../README.md) gives executable commands. Authorized local workers
can export the exact 52-file dependency closure with notices; a disposable copy
builds with the documented Windows toolchain. Public source/binary distribution
remains unresolved: no top-level PortForge license was found. The locked source
is submodule `6c971b08c0698cd5fe56ab0ed855df4cbfc0b511` under
`D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge`; old references were
read-only. ROM SHA-256 is
`a3779fc77994780e80d05bb557f800110d0398d34b951baa8c0a14910014ded3`.

Prior audio results remain under `artifacts/intake-20260912`: the old pygame
queue discarded 12/180 chunks and inserted about 9.1% silence in a three-second
diagnostic. The continuous FIFO delivered all samples in the same test; a
600-frame resumed session had zero underruns. Subjective listening and broader
audio-device coverage remain open.

Next: expand neighboring detach paths around the explicit legacy exit using
the short witnesses and full-corpus gate. Obtain focused independent device
reference evidence when a new region needs it. Linux, arbitrary-expression
snapshots and full-console hardware accuracy are outside current acceptance.
