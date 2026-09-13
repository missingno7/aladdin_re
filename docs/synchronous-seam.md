# Synchronous sound seam experiment — 0.7.0

**CONVERGING WITH SYNCHRONOUS LEGACY SEAM.** Experiment A identifies avoidable
continuation cost: production dispatch/support falls from 1,165 to 1,079 physical
lines, with `recovered.py` byte-for-byte unchanged. The same full replay passes
all 225 observations. No native API, game domain, comparison mask or machine
component changed. This is evidence that this seam can be cheaper, not proof
that all future recovery will converge.

## Frozen reference

The complete 0.6 implementation, tests and witness are pinned at
`evidence/carrier-v0.6.0`, commit `fc6604131d3f03409b0a9843d75a932e43c3bc6d`.
[Its report](carrier-convergence.md) and existing `artifacts/carrier/` evidence
remain unchanged, including the NOT CONVERGING verdict and inside-callee save.

`scripts/carrier_v060.py` extracts that exact commit into a temporary source
directory and runs it against the existing native DLL. It can run the original
witness, its 19 continuation tests, comparisons, and version 3 snapshot playback.
This is a qualification tool, not a second production continuation mode. The
old `scripts/carrier_witness.py` command delegates to this frozen implementation.
Its original experimental source remains available at the pinned commit.

The frozen witness and all 19 tests were rerun successfully. Its strong
inside-callee snapshot and fresh-process Python-resume capability is preserved.

## A. Supported synchronous call

The region is exactly the uncapped 0.6 path; the existing
[ROM-address map](carrier-convergence.md#region-selected-from-current-evidence)
still applies:

```text
1AF468: Python counter/sound prefix, including direct 1B0336 semantics
  → materialize original MOVEM / argument / JSR state
  → original 1E58B8, including nested 1E57AC
  → original return 1AF492 and JSR 1E589A
  → recognize 1AF498 in the same Python call
  → Python suffix: replacement, pair clear, buffer clear, initialization
  → outer RTS at 1AF4D6
```

`Candidate._transition()` calls the unchanged recovered prefix, runs the
original sound span synchronously, and calls the unchanged recovered suffix.
It owns normal Python locals rather than a persisted activation record.
No coroutine, generator, resume ID, continuation object or generic call API
was introduced. `Machine.run()` and the existing temporary native gate suffice.

Let S be the entry A7. The prefix materializes exactly the same five saved
registers, long argument 11 and guest return slots as 0.6. Return recognition
requires PC=`0x1AF498`, A7=S−24, the long at S−28=`0x1AF498`, and equality of the
28 saved-frame/outer-return bytes at S−24 through S+3. These bytes and S are
immutable locals in the active Python call. There is no digest or entry-tick
record to serialize. The native run API remains monotonic in machine time.

Only `0x1AF498` is gated during sound. A return at another stack depth is
bypassed once and executes original code; it cannot resume the outer Python
activation. A matching depth with a wrong frame or slot fails explicitly.
A synthetic native test nests another original caller and proves that the
foreign return executes normally before the correct outer return is recognized.

## Safe snapshot and fallback rule

A portable recovery snapshot is legal **when no synchronous sound call is
active**: before carrier admission, after completion, or after explicit
handoff back to original execution. `snapshot_bytes()` rejects a save during
the active call using one transient boolean on `Machine`. `Recorder` uses
the same guard. Native-only debug inspection remains available and is tested
inside the original callee; it does not promise a portable Python continuation.

There is no new snapshot format. Production writes/reads ordinary version 2
archives with native state contract 1. Current production rejects the historical
version 3 persistent-continuation archive. To inspect or resume that evidence,
use the frozen 0.6 launcher; no existing archive was migrated or overwritten.

Fallback has three concrete routes:

1. Unsupported prefix operands or failed atomic admission leave the prefix
   uncommitted and execute its original entry instruction.
2. A recognized sound return whose suffix cannot be admitted delegates from
   `0x1AF498`. It keeps the completed prefix and sound work.
3. An input, comparison-checkpoint or terminal deadline reached before return
   relinquishes Python ownership at that native instruction boundary. It does
   not step again, delay the input, or store a pending continuation. Original
   control flow owns the remaining route; independently recovered child entries
   may still run under the selected candidate.

In the third case a subsequent snapshot is legal: the Python call has ended,
so there is nothing to restore except original machine state. That differs
deliberately from saving an active Python continuation inside the callee.
Gate configuration and the active-call flag are cleared in `finally`.

## The per-frame limit was a second avoidable restriction

The first synchronous trial kept 0.6's exact per-frame callback budget. It
passed the full replay and removed 87 production lines, but introduced 12
deadline handoffs: only 59 suffixes completed in Python, versus 71 in 0.6.
Its unchanged evidence is under `artifacts/synchronous/economics/` and
`frame-budget-source/`. That loss of ownership is not hidden in the final table.

Inspection showed that the frame deadline was the event driver's **PCM-drain
batch size**, not its verification boundary. The existing verifier already
observes every 60 frames, plus the terminal state; inputs have their own exact
ticks. The driver now gives a gated carrier `min(next input/terminal,
next existing checkpoint)` as its deadline. Ordinary native runs still use
per-frame drain batches. Neither the checkpoint schedule nor its equality
contract changed. There is no new event scheduler or native scheduling rule.

This small refinement lets sound cross incidental drain boundaries without
crossing an externally required stop. The native lossless PCM capacity exceeds
the maximum 60-frame checkpoint interval plus the preceding partial frame;
its existing overflow rejection remains active. No samples are discarded.
Atomic admission still enforces the native machine's own device/interrupt rules.

The refinement also removes artificial admission pressure on the existing
recovered entries: the game-source functions and their guarded domains are
unchanged, but more existing plans now fit their caller-supplied budget.

## B. Direct economics comparison

`scripts/seam_economics.py` runs both implementations serially in fresh
processes, using the same ROM, DLL, exact short replay, full user replay,
diagnostics and observations. Archive extraction is outside timing. Both use
an empty bytecode-cache prefix. Timings are single local samples, not evidence
of a speedup. Counts use the same 0.6 definitions: execution crossings are
`2 × (run + atomic)`; all-API crossings are twice the sum of measured calls,
sampled before final result hashing and excluding construction/destruction.

| Production/source metric | Frozen 0.6 | Synchronous 0.7 |
|---|---:|---:|
| Dispatch/policy LOC | 275 | 231 |
| Supporting runtime LOC: machine/artifacts/CLI/player | 890 | 848 |
| Total above | 1,165 | 1,079 |
| Increment over the pre-carrier 0.5 baseline | 167 | 81 |
| Recovered-source LOC | 389 | 389, identical bytes |
| Concrete supported sound-call contracts | 1 | 1 |
| Persistent continuation contracts | 1 | 0 |
| Persisted activation fields | 4 | 0 |
| Additional continuation snapshot members | 1 | 0 |
| Continuation restore / auto-arm paths | Present | Removed |
| Active-call snapshot prohibition | None | One boolean / guard |
| Temporary native return gate per sound span | 1 | 1 |
| External resume dispatch registrations | 1 supported return case | 0 |

LOC includes comments and blank lines. Supporting files individually change:
machine 216→215, artifacts 273→251, CLI 207→198, player 194→184. The saved 86
lines are 7.4% of the combined surface, and remove 51.5% of the 0.6 experiment's
167-line increment. Qualification launchers, tests and reports are reported
separately from production; the preserved historical implementation is not
being counted as deleted repository history.

The three new qualification scripts total 245 lines: 44 for the frozen reference
launcher, 64 for paired measurements and 137 for the synchronous witness. They
are not imported by the production package. Tests and retained reports also
grow; the claim is a smaller production seam, not fewer total repository lines.

| Full replay metric | Frozen 0.6 | Synchronous 0.7 |
|---|---:|---:|
| Active gates outside / inside sound | 7 / 1 | 7 / 1 |
| Distinct gate PCs over the run | 8 | 8 |
| Gate stops | 2,103 | 2,085 |
| Gate-set calls | 155 | 157 |
| Python/native execution crossings | 35,448 | 35,248 |
| All measured API crossings | 250,194 | 247,180 |
| Direct semantic Python calls | 1,017 | 1,041 |
| Legacy spans entered | 77 | 78 |
| Returns recognized by Python | 77 | 76 |
| Python suffixes completed | 71 | 76 |
| Fallbacks | 34 scheduler | 2 scheduler + 2 hard-deadline handoffs |
| Replaced M68000 instructions | 58,102 | 58,652 |
| Charged M68000 cycles | 893,340 | 902,420 |
| Full original/candidate comparison latency | 65.497 s | 66.012 s |

All 78 recorded outer entries are now admitted; two hand off at required
deadlines. A missing Python-return count on those two does not mean the original
sound callee failed to return. Original execution completes the route. Gate-set
calls increase by two because one additional prefix is admitted; there are
still two temporary gate-set changes per admitted sound span. This machinery
did not disappear. More replaced instructions reflect fewer refusals of existing
behavior, not a new recovered function or wider game domain.

| Same short witness | Frozen 0.6 | Synchronous 0.7 |
|---|---:|---:|
| Gate stops / gate-set calls | 2 / 3 | 2 / 3 |
| Execution crossings | 12 | 12 |
| All API crossings | 124 | 98 |
| Direct semantic Python calls | 5 | 5 |
| Legacy spans / fallbacks | 1 / 0 | 1 / 0 |
| Replaced instructions | 69 | 69 |
| Forced-cold comparison latency | 1.112 s | 1.056 s |

The separate disposable Python edit check changes `ones + 1` to `ones + 2`:
PASS in 0.661 s becomes DIVERGENCE in 0.611 s. This fresh-source check uses normal
standard-library caches, unlike the forced-cold measurement above. It performs
zero builds or installs and verifies the unchanged DLL hash. The ordinary
Python workflow remains fast; not every forced-cold launch is sub-second.

## C. Machinery actually removed from production

- The `pending_transition` record and its validation, frame digest and entry tick.
- The `object-transition.json` member, version 3 ownership codec, binding and
  restoration/validation path. Ordinary native snapshot integrity remains.
- Candidate re-arming from persisted return context and dispatching a later
  `on_gate()` invocation as a resumed Python activation.
- Pending-carrier special cases in replay, resume-check, event playback and
  the player, including the player-specific candidate loop.
- Repeated accounting/admission/fallback code, shared by the existing normal
  entries and synchronous stages through small private methods. Some savings
  therefore come from ordinary deduplication, not persistence removal alone.

The saved guest frame, return-slot check, native return gate, two atomic stages,
and both gate-set changes remain necessary for this implementation. They are
not claimed as deletions. Neither the game-domain guards nor stack/CCR/timing
recipes in `recovered.py` were removed.

## D/E. Ownership and exact verification contract

Experiment B was **not needed to obtain the measured reduction**. No scratch
RAM, register, CCR, timing or instruction-counter differences are ignored.
The batching refinement did not move a verification checkpoint. In particular,
we have not demonstrated that retained scratch-stack bytes are dead to future
execution and do not claim that they can now be omitted.

The distinctions remain explicit:

- **Machine-local qualification:** the existing ROM differential tests retain
  exact routine effects and native continuation checks. The 0.6 persistent
  witness remains available for inside-callee investigation.
- **Carrier-boundary qualification:** the synchronous witness compares complete
  native state, all RAM/register effects, continuation, frame, PCM and time at
  the same outer exit. It then executes 150 original instructions and compares
  again. This is still full machine equality, stronger than a masked semantic
  boundary comparison.
- **Whole-replay qualification:** the unmodified comparator checks all 225
  ordered native-state/frame/PCM observations and terminal/full-PCM state on
  the same 225.023-second user recording.

The guest sound argument and call/return stack are observed by original code;
saved registers are read by the suffix; device timing and PCM remain native
observations. Scratch bytes left by recovered helpers remain visible to the
strict outer snapshot. There was no observability proof authorizing their
deletion. The already-omitted transient counter `:` and overwritten counter
return slot were 0.6 savings and are not counted again.

Evidence under `artifacts/synchronous/` includes:

- `v060-witness/report.json`: rerun of the frozen persistent experiment.
- `boundary-witness/report.json`: exact synchronous exit and 150-instruction
  continuation, forbidden in-call portable save, fresh safe-exit restore,
  deadline handback snapshot/replay, and an input deliberately placed inside
  the sound call at the old 0.6 snapshot tick.
- `boundary-witness/carrier-mutant-*/comparison.json`: wrong result is
  DIVERGENCE; wrong return and timing are CANDIDATE_ERROR. None passes.
- `economics/report.json`: the first per-frame-budget synchronous trial.
- `final-economics/report.json` and its four comparisons: final paired metrics.
- `edit-loop/result.json`: actual Python edit rejection and unchanged DLL.
- `installed-{short,full}/comparison.json`: installed 0.7 also passes with
  module hashes matching the checkout. `installed-player.json` records a
  successful 60-frame muted player run from the safe exit snapshot.

The 253-test production suite includes prefix and local-suffix refusal, hard
deadline handback, in-call snapshot rejection, wrong frame/return slot, a real
nested original return at the same PC/different SP, and exact state/PCM at the
existing observer/input deadlines. The frozen 0.6 continuation suite separately
retains its 19 tests. The architecture boundary check passes.

## F. Decision

**CONTINUATION COST IDENTIFIED.** Persistent restart ownership and an incidental
per-frame execution budget were substantial avoidable costs. The synchronous
case removes production machinery while retaining faithful original sound,
more completed recovered suffixes, local fallback and strict future equality.
It is the sole near-term production legacy seam. The stronger 0.6 mechanism
remains a frozen reference, not an equal runtime option.

No new game region was recovered during this investigation. Future expansion
can use this narrow pattern when its observed dependencies fit; a second case
must provide evidence before generalizing it. Exact-effect adapters and the
legacy gate itself still cost code and crossings, so this result does not
justify claiming universal amortization or a performance improvement.

**Final verdict: CONVERGING WITH SYNCHRONOUS LEGACY SEAM.**

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\carrier_v060.py witness
.\.venv\Scripts\python.exe scripts\carrier_v060.py test
$env:PYTHONPATH = "$PWD/src"
$env:ALADDIN_NATIVE_LIBRARY = "$PWD/build/libaladdin_native.dll"
.\.venv\Scripts\python.exe scripts\synchronous_witness.py --evidence artifacts\synchronous\v060-witness
.\.venv\Scripts\python.exe scripts\seam_economics.py --witness artifacts\synchronous\v060-witness\witness.alreplay
.\.venv\Scripts\python.exe scripts\dev.py compare artifacts\synchronous\v060-witness\witness.alreplay --candidate carrier --diagnostics --output artifacts\synchronous\short
# Historical version 3 saves use their frozen implementation:
.\.venv\Scripts\python.exe scripts\carrier_v060.py play --snapshot artifacts\carrier\witness-v060\inside.alsnap
```
