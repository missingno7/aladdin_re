> **Historical document** (archived 16 September 2026).  Kept as written: its
> commands, paths and names are those of its day.  The current replacement is
> named in [../README.md](../README.md); the lessons are summarised in
> [../../aladdin/convergence.md](../../aladdin/convergence.md).

# Solo recovery handoff

Prepared from main `067b957` on 2026-09-14. This is an operational handoff,
not a second current-status report. Inspect actual HEAD and worktree first.
Use one Terra agent at medium effort; no subagents or supervisor round trips.
Do not run another recovery writer in this checkout at the same time.

## Starting state

Read docs/STATUS.md (current section first), docs/recovery-workflow.md and the
last entries of docs/recovery-cost-log.md. Then inspect the relevant game,
boundary, recovery and tests. Do not reread all historical reports each turn.

Baseline: 1,533 tests; full cold 26,378-frame history PASS with zero restores,
exact state/frame/PCM and current receipts. Local evidence:
artifacts/blocker-review-qualified/comparison.json. Doctor also passed.
Artifacts are ignored local discovery evidence, not guaranteed checkout inputs.
Missing artifacts should be recaptured using scripts/recovery_census.py;
production tests must not require ignored snapshot files.

Semantic source: src/aladdin_sega/game/objects/{contact,collection,lifecycle}.py.
Boundary recipes: src/aladdin_sega/boundary.py. Dispatch/admission/mutants:
src/aladdin_sega/recovery.py. recovered.py exports the recovered source surface.
Live RAM remains authoritative. Keep semantic work reusable outside its adapter.

The contact tick entry 1ABB40 owns reset/bounds, scan 1ABBD6, callbacks via
1ABC82, shared completion 1ABCA0, scan advance 1ABD74 and RTS 1ABD7C.
Recorded enclosing callers return to 1A8C44. RAM child planners compose directly.
Supported collection and sibling sounds use the existing synchronous SoundSeam.
Its suffix reads authoritative post-sound registers/RAM; it must never replay
pre-sound aggregate writes. Scan resume requires D4.W in 0..23 and matching
A1 = FF7E82 + (23-D4.W)*66. Later unsupported sound can fall back locally.
Snapshots are safe outside the active synchronous call; do not add persistence.

## Recovery frontier: evidence, not a fixed queue

Current baseline has 18,411 parent admissions, 155 dispatcher hits, 29,452 gates,
5,256 fallbacks, 206 legacy entries / 187 returns and 49 local fallbacks.
Most refusals (5,086) are scheduler admission: these are not missing gameplay
and are not permission to weaken timing. Recompute after meaningful changes.

Choose observed connected work first. Candidates to inspect include:
- Composition gaps between already-qualified callbacks and the parent sound
  prefix/remaining scan, including RAM callbacks before the first sound.
- Existing collection routes outside the current parent's selected sound domain.
- Remaining observed dispatcher entries: 1AF228 (26), 1AEE40 (20), 1AED86 (10),
  1AF516 (10), 1AE64C (8), 1AF590 (6), 1AEF5C (4).
- Known type-1F sound/device paths and type-44 command98, when existing seams
  actually fit; type-7E stream handoff is a larger unresolved boundary.

These are occurrence counts in one baseline, not independent coverage proof.
1AF516 already has a relocation helper: inspect reuse before transcription.
Do not automatically pick the easiest unseen leaf. A meaningful step should
own game behavior or make recovered calls internal to an enclosing region.
Do not claim a whole routine when only admitted branches are qualified.

## Commands on this Windows checkout

Use D:/Prog/aladdin_re directly. Do not reinstall or rebuild for Python edits.
Only one Machine instance may be live in a Python process; use separate
processes for original/candidate and close each instance before another.

```powershell
Set-Location D:/Prog/aladdin_re
# PYTHONPATH is no longer needed: tests/conftest.py and scripts/run_tests.py set the checkout's paths
$env:GENESIS_NATIVE_LIBRARY="$PWD/build/libgenesis_native.dll"
git -c safe.directory=D:/Prog/aladdin_re status --short
.venv/Scripts/python.exe scripts/dev.py doctor
.venv/Scripts/python.exe -m pytest tests/games/aladdin/test_contact_step.py tests/games/aladdin/test_contact_step_sound.py tests/games/aladdin/test_contact_scan.py tests/games/aladdin/test_contact_family.py -q
```

For every edit, start with the smallest relevant case (`pytest -k ...`). Use
scripts/aladdin/oracle_witness.py's execute_region / qualify_atomic_plan and
fresh_process_future instead of creating another comparison harness.
For discovery use recovery_census.capture_entries with a game-specific
classifier and a fresh output directory; it applies canonical inputs correctly.

At a cohesive milestone, run the full suite and cold integration:

```powershell
.venv/Scripts/python.exe scripts/run_tests.py aladdin
# Replace NAME with a new descriptive batch directory; never mix old evidence.
.venv/Scripts/python.exe scripts/dev.py history-verify main --game aladdin --candidate lifecycle --timeout-seconds 180 --output artifacts/NAME
```

Full suite currently takes about two minutes; full original+candidate cold
comparison roughly four minutes on this host (not a time guarantee). Do not
run both after every exploratory edit. Run focused tests per edit, expanded
qualification after the branch works, full gates before committing production.
Freeze source while cold verification runs; changed source invalidates receipts.
Use --tree additionally when the actual current history has multiple branches
needed for the scope. Never replace cold qualification with player-cache restore.

## Qualification and self-review

1. Capture/classify real occurrences; map original control flow and dependencies.
2. Understand the game behavior; implement or reuse semantic functions and the
   smallest existing boundary recipe. Name only what the evidence supports.
3. Check strict complete outer state (including serialized machine state),
   registers/CCR/PC/stack/RAM/timing, frame and PCM. Check at least 150 original
   future instructions and fresh-process restore at a safe boundary.
4. Execute result, continuation and timing mutations. A list of guards is not
   a negative-control test. An exception or an inequality must be asserted.
   Do not report PASS while merely recording outer_equal=false in JSON.
5. Test alias/domain/deadline refusal and local fallback. UnsupportedCandidate
   is a supported refusal; an unexplained assertion/runtime error is a failure
   to investigate, not an unsupported-domain pass.
6. Prove parent ownership explicitly: parent hits, direct calls, disappearance
   of child gates and appropriate fallback counts. Equality alone can pass
   because original fallback did all the work. Keep pure discovery/oracle tests
   separate from production-admission claims.
7. Review the diff independently from the implementation reasoning. Check
   staged-write reads, partial register overlays, finite loops, CCR/X variants,
   pointer domains and guest-frame identity. Then run milestone gates.
8. Verify receipts match current source/native/ROM/history, status PASS,
   every-frame and terminal equality, and zero persistent restores for cold mode.

Recent errors to avoid: a fixture gate default overwrote blocked-contact inputs;
family adapters existed but parent maps omitted them; tests loaded ignored
snapshots; prose audit claims replaced executed mutants; resumed loops had no
cursor bound. These mistakes passed narrower tests, so self-review is essential.

## Sustained work and publication

Use an active goal for sustained execution, not an hourly scheduled task. Each
completed milestone should lead immediately to the next justified adjacent step.
No arbitrary token budget. Do not mark a subsystem goal complete after one leaf,
one report or a passing test batch. Follow the host's actual goal/blocking rules.
If goals are unavailable, disclose that limitation; do not pretend a final reply
keeps a worker running. User interruption or pause takes precedence.

Work locally without routine permission or status questions. Commit and push
verified cohesive milestones to main; use the existing git safe.directory form.
No force pushes, discarding other work, or changing history/ROM to get a PASS.
If another writer appears, do not overwrite its work; resolve ownership first.
Keep one compact progress/cost-log entry per meaningful milestone: behavior,
reused machinery, new manual machine concepts, internalized boundaries,
qualification scope, latency when measured, next frontier. Update current STATUS;
keep historical evidence historical. No milestone report per trivial leaf.

Use concise updates for meaningful findings, completion, failure or blockers,
subject to host-required communication. Avoid full-history context rereads,
large JSON dumps and routine agent polling. Track actual process handles,
wait rather than restart live commands, and inspect their terminal results.
While tests run, do read-only analysis or documentation; do not mutate the source
being compared. If one frontier is blocked, record a precise reason and continue
another useful adjacent path. A reproducible failed integration is a fix task,
not a reason to silently reduce coverage or invent a new framework.

The working hypothesis is CONTINUE + small evidence-driven mechanization:
reuse existing recovery rules, compose upward, and track new manual machine
reasoning per meaningful behavior. Do not optimize raw LOC or instruction count.
Do not redesign the CPU, scheduler, snapshot format, sound system or state model
unless a concrete unavoidable blocker has first been demonstrated.


## Quiet verifier is not a blocker (Type-55 incident)

`history-verify` runs original and candidate sequentially and writes
comparison.json only at completion. Five minutes without a final receipt can
be normal on this host. The Type-55 run started at 10:46 and passed at 10:51;
its agent incorrectly blocked before completion and launched a duplicate.

Use scripts/dev.py history-verify: it now emits PID/liveness/exit messages on
stderr every 30 seconds while the existing verifier owns worker watchdogs.
Keep stdout and stderr available; retain the returned tool session handle.
A wait timeout is just an observation boundary, not worker failure. Do not
start another verifier or mark the goal blocked because output/receipt is absent.
Wait on the same handle and check the final receipt even if the launcher has
already exited. PID liveness alone is not proof of progress, and an exited PID
alone is not proof of failure. Inspect exit status and comparison.json.

Before declaring a real failure, distinguish worker TIMEOUT, nonzero exit,
missing input, stale implementation receipt and actual DIVERGENCE. A live
worker still inside its configured deadline is a verified wait. If truly past
the configured watchdog, inspect its process/children and diagnostics; do not
turn repeated observations of one ongoing run into repeated independent failures.
When a blocked goal is resumed, recheck artifacts first: completed evidence may
already resolve the purported blocker. Never dump frame-level JSON into chat;
parse it and print only status, equality, frames, restores and source mismatches.
