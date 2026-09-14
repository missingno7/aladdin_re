# The execution model for progressive recovery

An architectural research report on how recovery should execute as it grows
from bounded leaves to subsystems and, eventually, the game loop.  Every
contract below was read from the code that enforces it (`native/machine.cpp`,
the donor engine, `machine.py`, `recovery.py`, `boundary.py`,
`history_runtime.py`, `verification.py`, `oracle_witness.py`), and every
number was measured on checkout `cfaca78` against the 82,161-frame `main`
on 14 September 2026.  Experiment scripts are in
`artifacts/replay-evidence-study/` (`slack_study.py`, `idle_boundary.py`,
`decoupled_boundary.py`).  Nothing here changes production source.

## The answer in one paragraph

The project does not need a new execution abstraction.  `AtomicPlan` is the
right unit of *execution replacement* because it is the unit the machine can
admit or refuse without partial effects, and the sound seam already shows how
a semantic region can span several such units with no continuation state
outside the machine.  The contact-tick refusals are not a limit of that
model: the tick is small (2 percent of a frame) and is refused only because
the replay's observation instant sits in the game's busy window at the frame
wrap.  Moving the observation and admission deadline to the game's own idle
instant while keeping the input instant where it is (about fifteen lines in
`GenesisRun.step`, no native change, no new state) removed 574 of 574
refusals in 3,000 frames, kept the candidate frame-exact, left the trajectory
identical at the instruction, and raised owned contact ticks by 26 percent.
Larger semantic regions should keep composing plans at planning time and, when
a region contains a legacy island, call it the way the sound seam does.  The
machinery that remains at 100 percent recovery is the oracle backend and the
seam, which shrinks to zero with the last island.

## 1. The current model, as enforced

### 1.1 State ownership

One authority.  The native `pf::genesis::Machine` owns every mutable byte:
work RAM, VRAM, CPU registers, Z80, VDP, PSG/FM, DMA and bus state.  Python
holds no game state between operations: it reads live RAM through
`peek_ram`/`_read`, computes, and stages effects.  A planning view
(`dispatch_plan_view`) overlays not-yet-applied writes so a later planner in
the same composition reads what the earlier one will write; the overlay lives
only inside one planning call.  Snapshots are opaque native payloads exported
and imported at operation boundaries (`al_export`/`al_import`), never decoded
by Python.  The policy document says it and the code does it: "Python reads
live storage and stages bounded ordered effects; it does not maintain shadow
gameplay objects."

What a second persistent state model would break: every strict comparison
(`state_sha256` is the native snapshot), every fresh-process restore
(`fresh_process_future`), every cache and checkpoint (only machine state is
serialized: "a raw C struct dump, native pointer, Python stack or generator is
not a save format"), and the refusal contract (a refused plan leaves the
machine untouched only because there is nothing else to leave untouched).

### 1.2 Gate contract

Original execution can be intercepted at at most 64 PCs (`al_gates`), plus one
temporary gate with a bypass-once flag (`al_gate`).  The executor checks the
gate set in `run_region` *after* interrupt admission and *before* the
instruction executes, so a gate fires at an instruction boundary with the
interrupt state already settled and nothing of the gated instruction done.
The lifecycle candidate arms 62 gates; the cold run stops at them 109,667
times.  A gate stop costs one Python callback; the census measured about 20
microseconds each, so the gate budget is a count limit, not a time limit.

### 1.3 AtomicPlan contract

`AtomicPlan(cycles, instructions, writes, registers, last_pc, direct_calls)`
represents one contiguous span of original 68000 execution by its final
effect: the work-RAM bytes that differ at the end, the registers that differ
(PC, A7, data/address registers, CCR only in SR), and the cost the machine
must charge (68000 cycles and instruction count, plus the PC of the last
replaced instruction for observers).  It deliberately does not contain
intermediate states, the order of stores, reads, device accesses, or anything
about the Z80.  `al_atomic` enforces the domain: work RAM only, at most 2,048
bytes and 18 register fields, cycles up to 100,000, instructions up to 10,000,
SR changes limited to the CCR, PC even.

Admission succeeds only inside the engine's own dispatch loop: the operation
is executed as one region, effects applied by a closure, cycles and
instructions charged, then the Z80 is caught up to the completed boundary and
the pass observers see the machine.  If admission fails, nothing was applied
(`e.declined && !e.completed` returns before any write), the executor stays
parked at the gate, and the caller runs one original instruction.  A failure
after effects invalidates the machine (`h.failed = true`); the original is
never rerun over a partial replacement.

### 1.4 Scheduler and admission contract

The engine admits a native operation only when all of these hold
(`genesis_engine.hpp`, the `use_native` condition):

- no bus access or VDP DMA stall is in progress;
- the trace bit is clear;
- no vertical interrupt is requested (a pending VBlank must be taken first);
- `cycles < deadline - cpu_cycles`, where the deadline is the next VBlank
  admission instant, recomputed after DMA stalls;
- `cycles < (master_limit - master_cycles) / divider`, the caller's time
  limit, which `al_atomic` also checks itself against its `target`;
- the Z80 is not banked over work RAM, and a shared-RAM observer throws if
  the Z80 touches work RAM during the span.

So the observations that could happen inside a replaced span, and how each is
handled: a VBlank interrupt (refused before the span if pending, and the span
may not reach the next instant); raster and DMA (the VDP's stall flag and the
deadline recomputation); Z80 and shared RAM (catch-up at the boundary plus the
observer guard); audio (PCM is produced by the devices during catch-up, so a
span produces the same samples as the original instructions would, provided
no 68000 sound write lies inside it, which the planners refuse); input and
frame boundaries (the caller's `target`); trace and checkpoint boundaries (the
trace bit and the executor's `observe_window`).  Only one of these is not a
machine event: the caller's `target`, which today is the replay's frame wrap.

### 1.5 Outer-state contract

After a replaced region the machine must equal the original's machine at the
same instruction boundary in everything the snapshot holds: RAM, all
registers including A7 and the CCR, PC, devices, and the cycle and instruction
counters (`observable()` returns `state_sha256`, the video hash, the PCM
chain, tick, PC, SR and the counters).  `qualify_atomic_plan` and
`execute_region` compare all of it, and a regression proves a wrong `last_pc`
that leaves everything else equal is still rejected.

### 1.6 Future-continuation contract

Equality at the outer boundary is checked, then 150 original instructions
are executed and compared again, then the outer state is restored in a fresh
process and the same 150 instructions must agree.  The 150-instruction future
catches stack residue and flag differences that the boundary snapshot alone
cannot distinguish from irrelevant scratch; the fresh process catches state
that only existed in the planning process.  The recorded case that justified
this: a control omitting final stack residue passed later full-replay
observations yet differed by ten bytes after 150 instructions.

### 1.7 Sound-seam contract

`SoundSeam(prefix, stack_basis, resume_pc, return_slot, saved_frame,
frame_size, return_delta, suffix)` is the existing mixed-mode composition.
The prefix plan ends with the PC at a native sound entry (`1E58B8`,
`1E58F4`, `1E589A`) and the request frame already pushed.  `_run_sound_seam`
then arms a gate at the resume PC, runs the original machine to the frame
deadline, and on each stop proves activation identity: A7 equals the
expected stack basis, the saved frame bytes are unchanged, the return slot
holds the expected PC.  A foreign return (another activation of the same
routine) is bypassed.  On the proven return the suffix planner reads live
state and produces a second plan, admitted atomically; if the suffix declines
or the deadline arrives, the original owns the rest.  No Python state
survives across the native span: the continuation is the machine's own stack
plus a planner that recomputes from live state.  `_contact_scan_resume` does
the same at `1ABD74` after an original callback.

This is the precedent that matters: a semantic region already spans several
atomic units and a native island without a second state authority, because
its resumption point is a real original PC with a real stack.

## 2. Pressure points

| Pressure | Evidence | Kind |
|---|---|---|
| The replay observes and schedules at the frame wrap, which sits inside the game's busy window | the 68000 is idle at `1B24F2` from raster line 60 to line 224 (60 percent of the frame) and busy from the VBlank at line 225 through the wrap to line 37; the contact tick starts at line 256 (median phase 125,237 of 128,005 cycles); 22 percent of ticks straddle the wrap and are refused although the plan is 2,488 cycles (2 percent of a frame) | incidental to the replay model, not to the machine |
| Gate budget | 62 of 64 gates armed; every new parent entry or resume point costs one | real, structural |
| Machine facts dominate the boundary layer | `boundary.py` 4,256 lines, 238 mentions of `cycles`, 157 CCR helpers, 291 of `a7`, against 739 semantic lines with none | grows with every leaf, shrinks only when parents collapse |
| Owned execution is small | 12.6 million of 842 million instructions replaced on `main`, 1.5 percent | parent collapse is the only lever that moves it |
| Legacy islands are called, not gated | 547 seam entries, 507 proven returns, 129 local fallbacks; the sound driver is the island every subsystem touches | the seam is the mechanism that must scale |

The first row is the only one that refuses correct recovered behavior today.

## 3. Is the contact-tick issue fundamental?

No.  Facts from the straddling parent states:

- No interrupt occurs inside a straddling tick: `interrupts_during_trace` is
  0 for the recorded `1AF590` and `1AF5F0` parents (291 and 331
  instructions).  The VBlank instant is at line 225 and the tick runs at
  line 256; the engine's device deadline is a full frame away.
- The only boundary the tick crosses is the replay's `target`, the frame wrap
  at `(frame + 1) * FRAME_TICKS`, which is where `GenesisRun.step` observes
  the frame and applies the next input.  It is a logical clock, not a machine
  event; the machine has no raster interrupt at line 0 in this game.
- The tick has natural boundaries: the prefix ends at the scan entry
  `1ABBD6`; the scan loop head `1ABBE0` is reached 24 times with the loop
  state entirely in A1, D4 and the stack; the completion exit `1ABD74` is
  already a resume point; the scan exit `1ABD7C` and the caller return.  The
  planner composes the tick from exactly these pieces (`_contact_step_prefix`,
  `_contact_scan_prefix` per slot, `complete_contact_plan`, `_join_plans`) at
  planning time.  State at every one of them is fully representable by the
  machine; handing execution across them needs no continuation beyond a
  gate.  So the tick is decomposable, but decomposing it at execution time
  would cost gates (one per boundary class) for a problem that is not the
  tick's.
- The kind-21 command-stream tick is different: 8,155 instructions, 106,146
  cycles (83 percent of a frame) and one interrupt inside.  No plan of that
  size can be admitted anywhere in the frame; that is the case that would
  need real decomposition or a legacy call, and it is already an escalation
  in the grinder protocol.

### 3.1 The experiment: decouple the input instant from the observation instant

Prototype (`decoupled_boundary.py`): the input for frame *f* is still
applied at the first operation boundary at or after the wrap `f * FRAME_TICKS`,
exactly as today; the observation and the admission deadline move to
`f * FRAME_TICKS + FRAME_TICKS / 2`, raster line 131, in the idle window.  A
plan admitted before the wrap may end after it.  This is safe for the same
reason the original already applies the pad "after the operation crossing the
boundary": a recovered region contains no controller read (the game samples
the pad at lines 231 to 246, inside the VBlank handler, and a plan cannot
model an I/O read), so the game cannot observe whether the pad changed one
instruction or one plan after the wrap.

Cold from power-on over the first 3,000 frames of `main` (215 input events):

| Measure | Frame-wrap boundary (today) | Idle-window boundary |
|---|---|---|
| Original trajectory at the same idle instruction after the same tick | identical | identical (same state hash, tick 2689240148, instruction 32,008,759) |
| Candidate equal to original on every frame (state, video, PCM) | yes | yes |
| Scheduler refusals | 574 | 2 |
| Contact ticks owned | 1,580 | 1,987 (+26 percent) |
| Instructions replaced | 372,904 | 471,028 (+26 percent) |
| Gate stops | 2,720 | 2,535 |
| Operations that crossed the input wrap | 0 | 427 |

A first variant that moved the input instant together with the observation
diverged from the recorded trajectory (the game polls the pad continuously in
some modes), which is why the input instant must stay where the recordings
mean it.  A longer run over 20,000 frames is reported in the addendum.

What this costs: about fifteen lines in `GenesisRun.step`, a `cache_contract`
bump (frame-end states move to the idle instant), one fixed offset in the
profile, and a re-verification.  What it does not cost: no change to
`AtomicPlan`, `al_atomic`, the gates, the seam or any planner; no new state;
the original's own semantics are unchanged to the instruction.

## 4. Precedents, as lessons

| Project | Execution owner | State owner | Legacy code | Recovered code | Crossing | Timing | Stop inside recovered code | Final artifact | Temporary machinery |
|---|---|---|---|---|---|---|---|---|---|
| Sonic 3 A.I.R. (Oxygen, LemonScript) | the engine's frame loop calls per-frame script functions | emulated RAM by absolute address plus script variables; `A0..A7`/`D0..D7` exist as script variables | none executes: the whole game was translated to script | script, gradually renamed (`objA0.position.x.u16` beside `u16[A2 + 0x10]`) | direct script calls; engine services for input, rendering, audio | frame-based; no 68000 cycles | the top-level loop yields to the engine per frame; object updates run to completion | script that still carries registers and addresses in many places | the RAM-image runtime is permanent |
| N64Recomp | recompiled C owns control; the runtime hosts it | an RDRAM byte array and a register `ctx` struct passed to every function | mechanically translated C per function, `LOOKUP_FUNC(ctx->r25)(rdram, ctx)` for indirect calls | handwritten C linked before the recompiled output so "the patches taking priority" | ordinary C calls through the same table | not cycle-accurate; OS threads mapped to real threads | yes, native code | recompiled C plus patches; not source | permanent |
| OpenGOAL | native x86 built from decompiled GOAL; a C++ runtime for kernel and I/O | the game's own data structures | none: "it shouldn't be emulated, interpreted, or transpiled" | decompiled GOAL, compiled by `goalc` | ordinary calls | the runtime's frame pacing | yes | `goal_src/`, real source | none, but the game did not run until decompilation was nearly complete |
| Matching decompilations (SM64, OOT) | the original target CPU, on hardware or emulator | the original binary's memory | assembly files linked into the same binary | C compiled to byte-identical code | ordinary calls, same ABI | the machine's | yes | C source; assembly islands shrink to zero | none |
| This repository's ownership study (13 September) | original 68000 with recovered islands at gates | one native machine | original instructions | Python plans and semantic bodies | gates in, seams out | 68000 cycles charged per plan | no; resumption is a real PC plus a replan | Python source | plans, gates, seams |

Lessons that transfer: (1) matching decompilations are the only precedent
where the game runs at every stage and the artifact is source, and their
mechanism is "link legacy islands into the same execution and call them
normally", which is what the seam does here; (2) N64Recomp and S3AIR show
that a shared memory image plus a register context lets legacy and recovered
code call each other freely, at the price of machine-shaped source that
persists (S3AIR still reads `u16[A2 + 0x10]` a decade on); (3) OpenGOAL shows
the cost of having no mixed mode: nothing runs until nearly everything is
recovered; (4) every port that dropped machine timing did so when the
original CPU no longer executed game code, not before.

## 5. Candidate models

Criteria: correctness (C), grinder ergonomics (E), semantic convergence (S),
scheduler compatibility (D), single state (T), continuation complexity (K),
tooling burden (B), gate pressure (G), disappearance at 100 percent (F),
cost (X).

### Model A: keep all-or-nothing plans, accept refusals

Today's model.  C, T, K, B unchanged and strong.  The refusals are harmless
to correctness and, as section 3 shows, are an artifact of where the replay
observes.  Convergence does continue: children are still recovered
individually inside a refused tick, and parent collapse is limited by
unrecovered children, not by refusals.  But F is weak in one respect: the
larger the recovered parent, the more of it a frame-wrap refusal throws
away, so the metric the grinder optimizes (fallbacks) stays polluted, and
parent-ownership evidence on recorded states is inconclusive in 16 to 22
percent of cases.  Verdict: keep, with the boundary fix of section 3.

### Model B: one semantic region, several machine regions

The planners already do this at planning time (`_join_plans`).  Doing it at
execution time means admitting the prefix at `1ABB40`, then the scan at its
own gate, then slots at the loop head, each with the full atomic contract.
Natural boundaries exist (section 3) and original execution can resume at
any of them because the state is in the machine.  It scales to any loop
whose iteration state is in registers and RAM.  Costs: one gate per boundary
class (G is the binding constraint at 62 of 64), a re-entry planner per
boundary (`_contact_scan_resume` is the template), and a weaker locality of
qualification (each piece qualified separately, the composition qualified by
the cold run).  Verdict: correct and stateless, but only worth its gates
when a region genuinely straddles a machine event, which today is the
kind-21 command stream and nothing else.  Experiment when such a region is
next.

### Model C: resumable recovered execution (coroutines)

A Python function that yields at a scheduler event would carry its locals
across the yield: a second state authority, not serializable by the snapshot
("recovered locals must be materialized in machine state or a small explicit
continuation before a suspension point"), invisible to fresh-process restore,
and impossible to fall back from midway without either discarding effects
already applied or replaying them.  The seam shows the alternative: yield at
a real PC and replan from live state.  Verdict: reject; it creates exactly
the continuation state the policy forbids, for no gain over B.

### Model D: a mixed-mode runtime (S3AIR style)

A RAM image plus register context in which script and translated code call
each other.  It solves crossing by making everything the same kind of code,
but the "everything" is machine-shaped source that the project would then
have to clean, and the runtime (rendering from VRAM-like structures, audio,
timing) is a second machine.  The repository already has the machine; what
S3AIR bought with its runtime, this project gets from the oracle.  Verdict:
too large, and it optimizes execution coverage over semantic recovery.

### Model E: mechanically translated legacy fallback

Translate remaining original routines to Python or C over the shared RAM
image so recovered code can call them and they can call recovered code.  It
would duplicate the interpreter that already exists behind the ABI, it makes
"coverage" trivial while semantic recovery slows (N64Recomp's shape), and
the translated islands need the same alias, timing and observer proofs as
plans.  The one place it could help is the seam's other direction, calling a
legacy routine from recovered code, and the seam already does that on the
real machine with exact timing.  Verdict: wait; revisit only if the number of
legacy islands called from recovered code stops shrinking.

### Model F: put the compatibility boundary where the game is idle

Keep A, B-at-planning-time and the seam, and fix the one non-machine
boundary: observe and admit at the game's idle instant, apply input at the
wrap.  Measured in section 3.1.  Scores: C unchanged (equality proven every
frame, trajectory proven at the instruction), E better (fallback counts mean
recovery gaps), S unchanged, D better (only machine events bound a plan), T
and K unchanged (nothing new persists), B negligible, G unchanged, F trivial
(the boundary is the game's own frame wait, which is where a recovered game
loop yields anyway), X about fifteen lines.

### Comparison

| | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| Correctness provable locally and globally | yes | yes | weak | weak | weak | yes |
| Grinder can use it repeatedly | yes | with gates | no | no | no | yes |
| Semantic convergence | continues | continues | continues | slows | slows | continues |
| Scheduler compatibility | refuses at the wrap | fine | needs a runtime | needs a runtime | needs proofs | fine |
| Single state | yes | yes | no | no | shared image | yes |
| Hidden continuation | none | none | Python frames | script frames | none | none |
| New machinery to learn | none | re-entry planners | a runtime | a runtime | a translator | none |
| Gate pressure | none | one per boundary | none | none | none | none |
| Disappears at 100 percent | yes | yes | no | no | maybe | yes |
| Cost | none | medium | high | very high | high | trivial |

## 6. Semantic ownership versus execution replacement

The distinction is real and the code already has it: `game/objects` holds
what a routine does (pure functions over a reader, no cycles, no A7), the
boundary holds how the machine must see it (cost table, residue, CCR,
aliases), and the runner decides where it executes (gate, seam, fallback).
Making it explicit is useful in one way: a semantic region should be judged
"owned" when its semantic function exists and every execution piece of it
is either a plan or a seam, regardless of how many machine operations the
compatibility layer needs for it in a given frame.  That lets the ledger
count semantic ownership separately from replaced instructions.  It is not
useful as a new runtime concept: the execution pieces are the existing
plans, and section 3.1 shows that the number of pieces a region needs is a
property of the boundary placement, not of the region.

## 7. Long-term evolution of the recommended path (A plus F, B at planning time, the seam for islands)

| Stage | Who owns control flow | Where the scheduling boundary is | How original code is entered | What remains |
|---|---|---|---|---|
| Today | the 68000; recovered code at 62 gates, 1.5 percent of instructions | the replay's frame instant (moved to the idle window by F) | it is the default; recovered code is the exception | everything |
| Whole subsystem (contact, spawn) | the 68000 still calls the subsystem entry; one gate per subsystem entry owns the whole call, children composed at planning time, legacy children through seams | the same | at seams inside the subsystem | gates shrink to entries; child gates disappear |
| Most gameplay | a handful of gates at the frame's top-level calls; each owns a whole system | the same | seams to the remaining routines | the boundary layer shrinks as parents absorb children |
| Game loop recovered | Python owns the frame: it runs recovered systems in order and calls legacy islands through the seam mechanism in the other direction (set registers and stack, run the machine to the return gate, read effects); the machine's devices run for the frame's time | the recovered loop's own VBlank wait: Python advances the machine to the next VBlank instant, which is where it observes | only through seams | `AtomicPlan` disappears (there is nothing original to replace); gates remain only as seam return points; cycle charging remains only inside seams |
| Full source port | Python owns everything; the Genesis machine is the oracle and the device backend until rendering and audio are re-implemented | game time, one frame | never | `AtomicPlan` 0, gates 0, seams 0, 68000 timing only in the oracle backend, the VM only as oracle |

The inversion happens at the game-loop stage and it uses machinery that
exists: the seam run in reverse.  Today the runner's `_run_sound_seam` is
"recovered code calls a legacy routine and resumes"; a recovered frame loop
is that call repeated for every remaining island, with the frame's VBlank
wait as the yield.  The mechanism's size follows the number of islands:
547 seam entries per run today, fewer with every recovered routine, zero at
the end.

Timing.  Machine-exact cycles are needed exactly as long as original 68000
code shares a frame with recovered code, because the original's raster,
Z80 and interrupt behavior depends on when the recovered span ends.  Once no
original code runs inside gameplay frames (islands only through seams, and
the seam charges real cycles natively), the cycles in plans stop mattering
to anything observable; the phase transition to game timing is safe when
the cold comparison passes with cycle charging removed from every plan that
no original code follows in its frame.  The evidence that the moment has
come is measurable: every-frame equality with `cycles` set to a nominal
constant.  Semantic game source should never contain cycle accounting; the
boundary layer should, until it is deleted; the oracle backend always will.

## 8. Recommendation

| Change | Verdict | Why |
|---|---|---|
| Decouple the input instant from the observation and admission instant: input at the frame wrap, observation and deadline at the idle instant (raster line 131), `cache_contract` bump | DO NOW | measured: 574 to 2 refusals, +26 percent owned ticks, frame-exact, trajectory-exact; about fifteen lines; no new state or abstraction |
| Report semantic ownership in the ledger separately from replaced instructions | DO NOW | makes the distinction of section 6 visible without new machinery |
| A "legacy call" primitive generalizing the sound seam to any island called from a recovered parent (contact scan calling an unrecovered child natively instead of declining the whole scan) | EXPERIMENT NEXT | it is the inversion mechanism of section 7 in miniature; the scan with an unrecovered child is the bounded case |
| Execution-time decomposition of a region at natural boundaries with re-entry planners | EXPERIMENT NEXT, only for the kind-21 command-stream tick | the only region that straddles a machine event; gates are the cost |
| Removing cycle charging from plans that no original code follows | WAIT | until a whole frame's busy window is recovered |
| Mechanically translated legacy fallback | WAIT | until the island count stops falling |
| Resumable Python coroutines, a mixed-mode script runtime, `AtomicPlan(entire_frame)`, a generic IR | REJECT | second state authority, machine-shaped source, or both |

The project does not currently need a new execution abstraction.

## 9. Answers

1. **Why does `AtomicPlan` exist?**  Because the machine can only admit or
   refuse a replacement as one indivisible region without partial effects,
   and because its final-effect form is what can be qualified against the
   original at an instruction boundary.
2. **Essential versus accidental.**  Essential: final effects only, work-RAM
   domain, cost charged, refusal without mutation, one authority.  Accidental:
   the 64-gate limit, the 2,048-byte and 18-field caps, and the fact that
   the caller's deadline is the replay's frame wrap.
3. **One semantic region = one plan?**  Never was; the seam and the scan
   resume already break it.  It is one semantic function, as many plans as
   the boundary placement requires, composed at planning time when the span
   is unbroken and at seams when it is not.
4. **Is the contact-tick issue fundamental?**  No.  It is the replay
   observing in the game's busy window.
5. **Preserve the atomic contract while composing larger systems?**  Yes:
   every piece keeps "whole operation or nothing"; composition is by planning
   view and by seams whose resumption is a real PC.
6. **Natural scheduler-safe boundaries?**  Yes: the game's idle wait at
   `1B24F2` for the frame, and within regions every loop head and completion
   label whose state is in the machine.
7. **Would resumable execution create unacceptable continuation
   complexity?**  Yes; the seam's replan-from-live-state is the stateless
   form of the same idea and is enough.
8. **Is an S3AIR-style runtime relevant?**  As a warning: it is how a project
   ends with source that reads `u16[A2 + 0x10]`.  The oracle gives this
   project what the runtime gave S3AIR.
9. **Recomp fallback as temporary infrastructure?**  Possible but not
   needed; the seam calls islands on the real machine with exact timing.
10. **How control inverts.**  At the game-loop stage the frame function is
    Python and calls islands through seams; the VBlank wait becomes the
    yield; gates remain only as seam returns.
11. **What disappears at 100 percent.**  Plans, gates, seams, cycle
    charging; the machine remains as oracle and, until re-implemented, as
    device backend.
12. **Smallest change now.**  The decoupled boundary.
13. **Deliberately postpone.**  Decomposition gates, legacy-call
    generalization beyond one experiment, timing removal, any runtime.
14. **Experiment that most reduces uncertainty.**  Already run for the
    boundary; next, the legacy call on the contact scan with one
    unrecovered child, measuring gates, refusals and qualification effort
    against the same scan today.

## Addendum: the decoupled boundary over 20,000 frames

The same prototype cold from power-on over the first 20,000 frames of
`main` (boot, title, the first levels):

| Measure | Frame-wrap boundary | Idle-window boundary |
|---|---|---|
| Original trajectory at the same idle instruction after the same tick | identical | identical (tick 17921920081, instruction 206,616,503) |
| Candidate equal to original on every frame | yes | yes |
| Scheduler refusals | 3,824 | 10 |
| Legacy-deadline seam handoffs | 15 | 0 |
| Contact ticks owned | 14,251 | 17,106 (+20 percent) |
| Instructions replaced | 3,236,829 | 3,867,337 (+19 percent) |
| Gate stops | 22,587 | 21,506 |
| Operations that crossed the input wrap | 0 | 2,977 |

Original run time was unchanged (94.7 s against 95.4 s).  The ten remaining
refusals are plans that reached the idle instant itself, which happens when a
frame's work overruns into the idle window; they are the honest residue of a
busy frame, not a phase artifact.
