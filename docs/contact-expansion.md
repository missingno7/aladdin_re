# Contact family and dispatcher composition

This checkpoint expands `1AE4F8` in the existing recovery model and composes
the type-`7B` callback at `1AE9D4` beneath dispatcher `1ABC82`. The original
control-flow map is [contact-region-map.md](contact-region-map.md).

## Recovered ownership

The source now expresses all four early state gates, both reaction outcomes,
the ordered routes into reset, pointer publication, and repeated decay effects.
The carrier qualifies ten reset-prefix routes, seven reaction-prefix routes,
sound-enabled and sound-disabled paths, and count/counter-dependent repeated
calls. The original test order remains significant for exact timing, even when
two paths have the same semantic outcome.

For admitted type-`7B` calls, dispatcher selection, the wrapper BSR, contact
behavior and the wrapper RTS compose directly. Sound still runs original
`1E58B8`/`1E589A`, with the existing synchronous return runner. The composed
suffix returns through the wrapper to `1ABCA0`. There is one real entry stop
without sound, or an entry stop plus the sound-return stop with sound.

The standalone contact gate remains for other original callers. Unknown table
targets, scheduler refusals, unsafe stack aliases and unqualified domains still
execute original code. In particular, sound-disabled reset with `FF7E20 != 0`
is explicitly refused; changed decay guards after sound can cause local suffix
fallback. This is a qualified contact family, not recovery of every surrounding
collision/update routine.

## Verification

`artifacts/grinding/parent/contact-expansion-pytest.log`: **646 passed in 31.35 s**.
Constructed caller tests use original caller/decay instructions and controlled
sound callees to isolate the ABI. Those tests are distinct from the real-ROM
recorded sound witness.

The recorded type-`7B` sound checkpoint, recaptured using the tracked script,
passes complete native snapshot, frame and PCM equality at `1ABCA0`, followed
by 150 original instructions. Entry replay and safe-exit restore also pass in
fresh processes. Its candidate has two real gates, four reported direct Python
calls, one original sound span, zero fallbacks and 67 replaced instructions.
Evidence: `artifacts/grinding/parent/contact-reproduced-witness/report.json`.
The result mutant diverges; continuation and timing mutants produce candidate
errors, all rejected (`contact-expansion-controls/report.json` in the same
parent artifact directory).

Final complete replay receipts are:

- `artifacts/grinding/terra/contact-expansion-final-old-v2/comparison.json`:
  225 observations PASS.
- `artifacts/grinding/terra/contact-expansion-final-new/comparison.json`:
  244 observations PASS.

Both match the current recursive production-source hashes. The earlier
`contact-expansion-final-old` error and pre-fix comparisons are not final proof.
No state mask or relaxed equality was introduced.

Reproduction from the retained new user recording:

```powershell
$env:PYTHONPATH='src;scripts'
$env:ALADDIN_NATIVE_LIBRARY="$PWD/build/libaladdin_native.dll"
.venv/Scripts/python.exe scripts/dispatcher_capture.py --recording recordings/20260913T094652.830908Z.alreplay --entry 1AE9D4 --output artifacts/contact/recorded
.venv/Scripts/python.exe scripts/dispatcher_witness.py --entry 1AE9D4 --fixture-dir artifacts/contact/recorded --output artifacts/contact/witness
```

The ordinary Python edit loop passes in 0.841 s and rejects a semantic clear
mutation in 0.769 s. The native DLL hash is unchanged, with zero builds or
package installs (`artifacts/grinding/parent/contact-expansion-edit-loop/result.json`).

## Marginal recovery work

| Step | Semantic work | Existing machinery reused | New manual machine work |
| --- | --- | --- | --- |
| All early/reaction routes | Ordered state predicates and conditional publication | Live readers, semantic effects, AtomicPlan, original witnesses | Route-specific timing and final flags |
| Reset and pointer outcomes | Pointer publication, reset effects, repeated decay observing prior writes | Same semantic reset/decay functions and one authoritative RAM | Counter-dependent timing and last BSR residue |
| More sound-enabled routes | Same reset semantics before original sound, then repeated decay | Existing sound ABI, return identity, snapshot rule and local fallback | Prefix totals and shared suffix count cases |
| Type-7B direct composition | Dispatcher calls the contact family through its known wrapper | Existing planned-write view and aggregate AtomicPlan | Wrapper BSR/RTS effects and register merge |
| Type-7B sound composition | Resume contact and return through the wrapper | Same sound runner and outer verification tools | Two concrete wrapper entry/exit adapters; no new continuation protocol |

No new native API, snapshot member, scheduler exception, continuation registry
or mutable state copy was required. Numeric compatibility recipes are still
handwritten; they are not counted as generated work. Semantic functions remain
in `game/objects/contact.py` and are independent of the machine API.

Review exposed genuine manual-work costs: wrong predicate ordering under
simultaneous flags, a lost X flag, an unchecked blocked-decay timing domain,
scratch-stack aliases, and missing incoming registers in composed planning.
These were corrected or explicitly excluded before publication. Qualification
also corrected a fixture label that confused admission with sound enable and a
future test that had remained parked at its gate. Passing tests only count when
they actually exercise the claimed boundary.

## Measured composition

These are whole-replay counters, with the same definitions as the baseline in
[recovery-progress.md](recovery-progress.md). API totals include observation
calls; gate stops are not the number of registered gate addresses.

| New recording | Bounded contact `ed2a5e7` | Expanded contact + wrapper |
| --- | ---: | ---: |
| Gate stops | 4,830 | 3,169 |
| Direct Python calls | 622 | 4,142 |
| Original sound spans entered | 22 | 73 |
| Fallbacks | 2,066 | 307 |
| Replaced instructions | 41,462 | 62,910 |
| Dispatcher activations recovered | 19 | 1,727 |
| Contact activations recovered | 1,878 | 1,927 |
| All measured API calls | 166,872 | 144,612 |

More sound spans are now entered from recovered prefixes because more reset
paths are owned; this does not mean the game plays extra sounds. Full PCM and
machine equality remain strict. The substantial boundary reduction comes from
type-`7B` composition, not from hiding unsupported stops. Remaining new-replay
fallbacks are 295 unknown callback targets, ten scheduler refusals and two
legacy deadlines. On the old replay, gates change 2,775 → 2,794 and API calls
132,459 → 132,513; that recording has no type-`7B` callback hits, so it does not
receive the same composition benefit.

**CONTINUE + MECHANIZE.** The additional routes reused machine mechanisms;
the main new work was game-path analysis and numeric recipes. Direct composition
removed production boundaries while the independently callable adapters remain
useful. Repetition is now clear enough to consider a small shared derivation for
the repeated-decay timing/residue recipe used by both sound paths. That is a
concrete candidate for the next mechanical improvement, not evidence that a
generic generator or new carrier framework is needed.
