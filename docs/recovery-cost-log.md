# Recovery cost log

Compact observations from successive connected expansions. Counts describe the
named verified boundary, not complete game or dispatcher ownership. Historical
experiments remain in `docs/archive`; current execution contracts live in source
and tests. New machine concepts count protocols, state authorities and execution
rules, not handwritten lines.

| Step | Durable ownership / composition | Reused mechanics | New machine concepts | Repetitive manual work / evidence |
| --- | --- | --- | ---: | --- |
| `1e43a73` spawn neighbors | Reset-before-lower-allocation and successful script installation; existing type-33 callback joins parent; dispatcher 16 to 19 targets | Allocator, staged reads/writes, exact outer plan, alias guard, strict oracle/future/restore/mutants | 0 | Two familiar BSR/RTS aggregates and final CCR recipes; 737 tests, 29 recorded occurrences, full 26,378-frame PASS; allocator activations 79 to 63, direct calls 5299 to 5339 |
| Guard composition | Existing guards `1B7354`, `1B742A`, `1B744A` become internal calls; dispatcher 19 to 22 targets | Existing guard/caller plans and all qualification machinery | 0 | Three routing entries; deleted duplicate support whitelist. No new semantic body or machine recipe. 821 tests and full 26,378-frame history pass; fallbacks 707 to 681, direct calls 5339 to 5365, unchanged 3846 candidate activations. |

## Bounded whole column walker

`1AE44A` through the boundary before RTS `1AE47C` now composes slot selection,
empty slots and supported callbacks. Reused AtomicPlan, staged RAM reads,
callback/allocator adapters, scheduler admission, strict oracle and restore
rules; **zero new execution protocols or state authorities**. Manual work was
loop/branch accounting and outer-register effects, including a discovered
32-bit ADDA.W correction. Semantic selection is durable source, but the outer
loop still lives in the exact carrier; this is not yet a detached subsystem.

853 tests pass in 41.42 seconds; eight captured walkers pass strict outer,
150-instruction future and fresh-process checks. Full 26,378-frame history
passes. Spawn-caller activations 435 to 105 demonstrate 330 swallowed inner
boundaries. Candidate activations 3846 to 5420 and fallbacks 681 to 1493 increase:
empty passes acquire a gate, unsupported aggregate plans retry, and scheduler
refusals rise 127 to 490. Direct calls 5365 to 35209 include the new selector;
replaced instructions 127790 to 337688. Original oracle loop-stop counts are
not production gates and must not be presented as sixteen removed gates.

Next observed repetition: six additional plain template/allocator callers
match six existing qualified wrappers; three positional callbacks share an
allocation-success offset pattern. Disposable original-ROM prototypes pass,
but these nine targets are not yet production recovery. They account for 43
of the 50 remaining observed callback visits and justify narrow shared recipes,
without a new framework or machine API.

## Original frontier evidence

Cold original census of history `4b1537634fdda81e023983a12acdafca3607cc7fd7db7a7f98372340554e5b60`
found 1,916 complete passes of the 16-slot loop `1AE44A..1AE47C`:
1,577 entirely empty, 272 nonempty using only the 19 recovered callback targets,
and 67 with unresolved targets. This is structural coverage, not proof of atomic
admission. The subsequently composed guard targets `1B7354`, `1B742A`, `1B744A`
close 21 of those unresolved passes (26 callback visits), leaving 46.

The original loop reads a slot word through A0, halves it for the byte flag index
at A2, selects the callback through A1's table, sets the Y offset, preserves the
outer registers, invokes the callback, advances A0 by signed D5 and D6 by 16,
and repeats through D4. Exact map: selection `1AE44A..1AE462`, existing recovered
callback envelope `1AE468..1AE478`, final RTS `1AE47C`. Empty slots branch directly
to `1AE472`. This map defines the now-qualified bounded walker.

Evidence: `artifacts/spawn-frontier/walker-census.json`; original entry fixtures
include empty, single, multiple and unresolved callback passes. In particular,
frame 1725 directly connects `1B72D4` and `1B6802` within one original pass.
The capture files are raw discovery oracle states with history/frame provenance;
they are not portable gameplay histories or a new snapshot contract.
