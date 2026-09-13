# Connected recovery progress

The starting evidence is main `5d96527` (0.9.0), described in
[collection-subsystem.md](collection-subsystem.md). This log follows successive
connected recoveries; finishing a small assignment does not finish the subsystem.

## Working loop

Choose an adjacent caller or mechanism from actual ROM and replay evidence.
Recover and conservatively name its behavior, qualify against original code,
compose existing helpers directly, and continue upward. Keep original RAM as
the one authority, strict exposed machine effects and the existing synchronous
sound seam. Preserve standalone adapters while original callers need them.

Terra maps and implements bounded recovery steps. Luna handles independent
tracing, fixtures and verification work. The parent reviews, integrates and
immediately assigns follow-up work. File ownership is explicit while workers
share this checkout. The continuous parent goal replaces the paused hourly
automation; progress does not wait for another clock interval.

## Current checkpoint

- Terra: the four type-73--76 callback handlers and the narrow `1ABC82` parent
  dispatcher are composed through the existing lifecycle candidate.
- Luna: independently qualified callback fixtures and dispatcher checkpoints,
  including sound-disabled and inside-sound deadline cases.
- Parent: final code review and receipt audit completed; both the original
  225-second replay and new 244.30-second corpus are integration gates.

## Cost log

| Step | Semantic reasoning | Existing machinery | New machine concepts | Mechanical work / evidence |
|---|---|---|---|---|
| Repeated collection sound-site facts | No new game behavior; established sound commands only | Twelve qualified collection routes and their existing sound ABI | None | `scripts/collection_sound_sites.py` recognizes the exact repeated instruction sequence and derives command, call/return addresses, frame size and fixed timing sums. Eight checks pass, including changed branch/frame/call/restore rejection. No production executor or new dependency. |
| Four type-73--76 callbacks | Each callback stores its type-specific flag (`FFF128`, `FFF129`, `FFF116`, or `FFF12A`), emits sound 103, then shares the established +15 retirement and `1B7ABC` template | Existing collection state, synchronous sound frame, pair/buffer release, initializer, exact outer witness and fresh restore | None; the common sound/retirement contract is reused | Original-ROM constructed callback fixtures all pass strict state/frame/PCM, 150 original instructions, safe restore and fresh-process replay. Evidence: `artifacts/grinding/luna/flag103-witnesses/report.json`. The source recording has zero hits for these four entries. |
| `1ABC82` collection dispatcher | Materialize `D1` type, `A4` callback, `FFF0F5/FFF0F6`, and the original `1ABCA0` JSR return, then enter only a callback already in `COLLECTION_ROUTES` | One existing lifecycle candidate, one combined `AtomicPlan`, the same sound seam and callback completion | **One new planning concept:** read-only `_DispatchPlanView` exposes the planned prefix bytes/registers to callback planning. It is not a mutable state authority or persisted continuation. It avoids a second atomic/native park because callback planning needs the new return slot and prefix RAM effects in the same plan. | Four synthetic type-73--76 checkpoints pass outer equality at `1ABCA0`, one real dispatcher gate, 150-instruction continuation, safe restore and fresh-process replay. Candidate stats show `collection_dispatch_hits=1`, `gates=2`, and no synthetic callback stop. Evidence: `artifacts/grinding/luna/dispatcher-parent-witnesses/report.json`. |
| Dispatcher edge contracts | Preserve the ordinary original sound-disabled path and hand back at an input deadline inside `1E57AC` | Existing audio/device state and deadline fallback | None | Type-73 sound-disabled witness passes in `artifacts/grinding/luna/dispatcher-soundoff-witness/report.json`; inside-sound input passes with exactly one `legacy_deadline_fallbacks` in `artifacts/grinding/luna/dispatcher-deadline/report.json`. |

Sound-site output is under `artifacts/grinding/sound-sites.json`. This is a
qualification aid, not a replacement for independent native differential tests.
Cycle formulas are explicit for this single demonstrated sequence; the tool does
not claim to derive timings for arbitrary instructions or device interactions.

Before publishing a recovered milestone, require focused strict witnesses,
appropriate wrong-result/return/timing controls, future native continuation,
regression tests and full replay integration. Report constructed-fixture coverage
separately from recorded gameplay coverage. Never infer dead state from an
unobserved difference in one replay.

The dispatcher census contains **661 real `1ABC82` activations**, but none of
the recorded objects have types 73--76. The dispatcher fixtures therefore start
from the first recorded `1ABC82` snapshot and use one admitted synthetic byte
write to select each known table slot; original ROM dispatcher instructions then
reach the callback. This proves the callback table, prefix effects, return frame,
sound seam and continuation contract for those constructed states. It does not
turn the four handlers into recorded gameplay coverage. The old 225-second user
replay remains an independent integration gate; the 244.30-second corpus is a
second user recording and must be compared separately once the implementation is
stable.

The unmodified dispatcher qualification is recorded at
`artifacts/grinding/luna/real-dispatch/original/report.json` and
`artifacts/grinding/luna/real-dispatch/witness/report.json`. Each of those three
user-derived checkpoints reaches the original `1ABCA0` boundary with strict
state/frame/PCM equality, one dispatcher candidate hit, one carrier completion,
150 native future instructions, safe restore, and fresh-process replay. The
source recording has 661 dispatcher activations in total; this extraction found
one checkpoint for each named target, while the new 244.30-second census has no
per-target fixture and must not be presented as four-handler recorded coverage.
The new recording is at `recordings/20260913T094652.830908Z.alreplay` (not under
`recordings/current/`). The parent verified its presence and original execution;
its 2,029-dispatch census must not be confused with distinct recovered callbacks.

The second user recording is now independently compared at
`artifacts/grinding/luna/full-new-replay/comparison.json`: **244 observations
PASS**, equal terminal state and frame, and equal 52,052,100-byte PCM
(`98eb726176a1988b30dcfbaa4b54818d70e1259c04b6e70d7f775825675a4abd`). Its
candidate receipt records 19 real `collection_dispatch_hits`, all 19 completing
through `1AF468`; unsupported table targets remain explicit original fallbacks
(2,011 fallback stops in this corpus). The parent separately captured the
original baseline at `artifacts/grinding/new-corpus/original-replay.txt` and
`original-observations.jsonl`; this candidate report does not replace that
baseline. An interim full regression run was **384 passed in 21.67 s**; rerun it
after Terra's admitted-route fixture expansion and label any changed-source
result with its new receipt.

The retained 225-second user replay also independently compares **PASS** at
`artifacts/grinding/luna/full-original-replay/comparison.json` with 225 matching
observations and equal terminal state/frame/PCM. The dispatcher and callback
negative controls remain recorded at `dispatcher-parent-mutants.json` and
`flag103-mutants.json`: wrong results diverge, while continuation/timing mutants
fail candidate execution.

The dispatcher witness and its negative controls are reproducible with:

```powershell
$env:PYTHONPATH='src;scripts'
$env:ALADDIN_NATIVE_LIBRARY="$PWD/build/libaladdin_native.dll"
.venv/Scripts/python.exe artifacts/grinding/luna/capture_dispatcher_callbacks.py
.venv/Scripts/python.exe artifacts/grinding/luna/dispatcher_witness.py
.venv/Scripts/python.exe artifacts/grinding/luna/capture_real_dispatch_targets.py --recording recordings/current/20260912T210640.729016Z.alreplay --output artifacts/grinding/luna/real-dispatch/original
.venv/Scripts/python.exe artifacts/grinding/luna/dispatcher_witness.py --fixture-dir artifacts/grinding/luna/real-dispatch/original --output artifacts/grinding/luna/real-dispatch/witness --entry 1AF3C2 --entry 1AF468 --entry 1AF4D8 --scope 'unmodified dispatcher checkpoints from retained user recording' --recorded-dispatch-activations 661
.venv/Scripts/python.exe artifacts/grinding/luna/prepare_dispatcher_soundoff.py
.venv/Scripts/python.exe artifacts/grinding/luna/dispatcher_witness.py --fixture-dir artifacts/grinding/luna/dispatcher-soundoff --output artifacts/grinding/luna/dispatcher-soundoff-witness --entry 1AF008
.venv/Scripts/python.exe artifacts/grinding/luna/dispatcher_deadline.py
.venv/Scripts/python.exe artifacts/grinding/luna/run_dispatcher_mutants.py
```

## Final dispatcher milestone

**CONTINUE.** The four new handlers reuse sound and retirement without a new
machine protocol. Upward composition adds one narrow planning view; it is an
explicit cost, not a claim of zero glue. Existing helper gates remain for original
callers, but known dispatch callbacks no longer park at their own native gate.
The same semantic collection and retirement functions survive the new entry.

Final production receipts (matching the checkout module hashes) are:

- `artifacts/grinding/terra/full-old-final/comparison.json`: 225 observations PASS.
- `artifacts/grinding/terra/full-new/comparison.json`: 244 observations PASS.
- `artifacts/grinding/terra/pytest-final.log`: **427 passed in 21.30 s**.
- `artifacts/grinding/published-witness/report.json`: three unmodified recorded
  dispatcher checkpoints, strict `1ABCA0` boundary, 150 original instructions,
  safe restore and fresh-process replay PASS.
- `artifacts/grinding/final-controls/report.json`: result DIVERGENCE;
  continuation/timing CANDIDATE_ERROR, all rejected.
- `artifacts/grinding/final-edit-loop/result.json`: PASS in 0.674 s; deliberately
  wrong semantic clear rejected in 0.616 s, unchanged DLL, zero builds/installs.

An early combined plan lost dispatcher `D1/A4` effects when a callback did not
explicitly overwrite those registers. Expanded original-ROM fixtures caught it;
the final merger retains prefix effects unless the callback replaces them.
All sixteen admitted targets now have constructed dispatcher qualification,
including actual capped-counter and pre-threshold paths. No state mask was added.

On the retained replay, replaced instructions rise 58,983 -> 59,730 and reported
direct Python calls 1,738 -> 1,821, with the same 2 scheduler and 2 legacy-deadline
fallbacks. The new broad dispatcher entry also observes 578 unsupported targets:
total fallback stops rise 4 -> 582. These are explicit domain refusals, not new
timing failures. On the new replay, 19 callbacks are owned and 2,010 unsupported
targets plus one scheduler refusal remain. Subsequent work should connect those
actual paths, not optimize the counters by hiding original execution.

The two reusable recorded-dispatch tools are now tracked in `scripts/`, so the
main witness does not depend on disposable agent scripts:

```powershell
$env:PYTHONPATH='src;scripts'
$env:ALADDIN_NATIVE_LIBRARY="$PWD/build/libaladdin_native.dll"
.venv/Scripts/python.exe scripts/dispatcher_capture.py
.venv/Scripts/python.exe scripts/dispatcher_witness.py
.venv/Scripts/python.exe scripts/collection_sound_sites.py
.venv/Scripts/python.exe scripts/dev.py compare recordings/20260913T094652.830908Z.alreplay --candidate lifecycle --diagnostics --output artifacts/dispatcher/full-new
```

The user also supplied `recordings/20260913T094506.477102Z.alsnap` during a camel
jump. Original play restores it and runs 150 headless frames successfully; this
is a continuation smoke check, not candidate equivalence evidence.
