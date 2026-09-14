# Recovery factory review: turning the Aladdin recovery workflow into a cheap-model assembly line

Independent process-engineering review of `main` at `4284daf`, 14 September 2026,
Windows x64. Every number below was measured on this checkout during the review
unless it is explicitly attributed to the project's own logs. The review changed no
production source; its prototypes live in the scratch directory and are described
in section 14 so they can be adopted deliberately.

The question was not how to recover one more branch faster. It was: what must
change so that a cheaper model can perform tens of connected recovery steps
autonomously with low error rates, and when must a stronger model step in.

## 1. Current factory baseline: why autonomous grinding stops today

The evidence comes from three sources: the git history (53 commits in 36 hours,
13 to 14 September), the Codex session rollouts of the workers that produced them
(`~/.codex/sessions`, model `gpt-5.6-terra` and `gpt-5.6-luna`, 40 sessions on those
two days), and the project's own cost log and status notes.

### 1.1 The solo Terra session of this morning, turn by turn

The `docs/solo-recovery.md` handoff was executed by one Terra worker at medium effort
from 09:04 to 11:29 local time. Its rollout is the cleanest baseline for "a cheap agent
alone with the current process".

| Measure | Value |
|---|---|
| Wall clock | 145 min |
| Qualified leaves committed | 3 (Type-03 seam, Type-46 seam, Type-20 relocation) plus Type-55 staged but not committed |
| Failed probes abandoned before the first commit | 4 (Type-36 composition, Type-3A twice, Type-2D) |
| Tool calls | 390 (89 file-slice reads, 39 greps, 69 ad-hoc Python probes, 21 pytest runs, 5 cold verifications, 81 process polls) |
| Assistant turns | 168, of which 32 were status-only filler produced by goal re-prompts |
| Reads of `boundary.py` | 29 slices, about 2,500 of its 4,144 lines, several regions twice |
| Context per turn | median 127K tokens, maximum 246K |
| Tokens | 62.8M input (98% cached), 137K output, 52K of them reasoning |
| Per-leaf wall clock | Type-03 43 min after 33 min of failed probes; Type-46 16 min; Type-20 28 min |
| Waiting for verification per leaf | full suite 133 s plus cold history 240 s, twice for Type-20 |

The four abandoned probes all ended the same way: the strict comparison reported that
state or RAM diverged after the native sound path, and the worker could not say which
byte, which cycle or which register was wrong. Its own words: "not byte-exact; isolating
the first divergent byte", "43 instructions and 662 cycles differ, with divergent
RAM/PCM", "strict RAM equality still fails after the real sound path". Each time it
removed the prototype. The Type-46 seam succeeded on the second attempt only after the
worker compared original and planned machine state "immediately at the sound entry" and
found that the native sound routine observes the incremented `D0.B`. In other words,
the worker rediscovered, by hand, the single-step machine trace that section 6 turns
into a tool.

### 1.2 The stop taxonomy

Across the session rollouts, the cost log and the status notes, an autonomous run stops
for these reasons, in decreasing frequency:

| Stop class | Frequency | Examples |
|---|---|---|
| Undiagnosed strict divergence | most common | Type-36, Type-3A, Type-2D, first Type-46 attempt; "43 instructions and 662 cycles differ" |
| Mechanical accounting error caught only by review | common | Type-55 non-borrow return charged the borrow cost (182/16 versus 180/15); contact activation borrowed-versus-unborrowed timing; scan missing X after the coordinate ADD; ADDA.W read as ADDA.L; final-PC and BE/C0 branch costs in the completion suffix |
| Fixture or evidence defect | common | invalid linked pointer in a synthetic record; table kind confused with the record flag byte (0x20 versus 0x36); a gate default overwriting the blocked-contact input; tests loading ignored snapshots; an ad-hoc replay shifting input by one frame |
| Verification-workflow failure | recurring | prose audits standing in for executed mutants; prototypes excluding serialized state from strict assertions; two overlapping cold verifications writing one directory; a live verifier declared blocked after three minutes of polling |
| Native or tooling limit | occasional | 63-gate native limit hit by a new direct gate; census exceeding the foreground execution window; a launcher lacking the DLL environment |
| Integration omission | occasional | family adapters present but parent maps missing them; five Type-20 scan fallbacks visible only in the cold run |
| Genuinely new mechanism | rare, but terminal | Type-7E progress into the `1B2238` command-stream engine; Type-1F kind-21 running 7,867 instructions through `1B24xx..1B26xx` |
| Semantic misclassification | rare | flag branches read as early exits; unsigned borrow negation read as signed absolute distance |

The supervised Terra session of 13 September (618 minutes, 382 assistant turns) received
seven human messages in total. Every one of them corrected a process claim, not a
recovery error: "What exact execution-capacity limit did you hit?", "A long-term goal may
be marked BLOCKED only by an external, verifiable blocking condition", "Check the current
state and continue". The dominant human intervention today is telling the agent it is not
blocked.

### 1.3 Autonomous steps per expensive intervention

Interleaving the commit history with the cost log's review notes, a cheap worker delivered
two to three qualified leaves between strong-model interventions, occasionally six when the
leaves were near-identical wrappers. The interventions were: independent branch matrices
that caught accounting errors, review that restored omitted routing, the false-verifier
incident, and tooling consolidation (named oracle results, shared qualifier, canonical
census). That is the baseline the rest of this review tries to move.

## 2. Cost model: where time, tokens and manual effort go

One leaf, reconstructed from the four commits of this morning and the session rollout:

| Component | Type-03 seam | Type-46 seam | Type-55 arm | Type-20 relocation |
|---|---:|---:|---:|---:|
| Semantic source lines | 0 (reused) | 0 (reused) | 0 (reused) | 0 (reused) |
| Boundary lines | 56 | 71 | 39 | 11 |
| Routing lines | 29 | 14 | 2 | 3 |
| Test lines | 46 | 42 | 55 | 66 |
| Manual machine facts written | 4 cost pairs, 1 CCR formula, 1 prefix identity | 2 cost pairs, 9 frame-slot writes, 1 resume PC, D0 lane residue | 2 cost pairs, 3 register overlays, CCR chain, last PC | 1 identity check |
| Wall clock to commit | 43 min | 16 min | staged at 10 min, then blocked | 28 min |
| Verification waiting | about 6 min | about 6 min | about 4 min | about 13 min (two cold runs) |

Three things dominate marginal cost:

1. Diagnosis of a divergent candidate. When the qualifier says "outer divergence: state,
   ram", the worker spends tens of minutes bisecting by hand or abandons the branch.
2. Reading. About 60 to 100K tokens of source are read before the first edit
   (`boundary.py` alone is 58K tokens), and the same regions are re-read after context
   compaction. The 127K median context is mostly this.
3. Waiting. Six to thirteen minutes of full-suite and cold-history time per leaf, during
   which the worker polls, files status turns, or launches a duplicate.

Token cost is dominated by cached context, not by generation: 30M input tokens per leaf
against 45K output tokens. Halving what a worker must read halves the bill and, more
importantly, keeps the medium model inside the context size where it reasons well.

## 3. Error taxonomy: semantic versus mechanical

Every recorded mistake in the cost log, status notes and this morning's session was
classified:

| Class | Share | Nature |
|---|---:|---|
| Mechanical machine bookkeeping | about 60% | cycle and instruction counts per branch, CCR and X residue, final PC, partial register overlays losing unchanged registers, stack-slot bytes, operand widths, register lanes exposed to native code |
| Verification workflow | about 20% | weakened or prose assertions, ignored-snapshot dependencies, fixture defects, stale receipts, duplicate or misread verifier runs |
| Integration | about 10% | routing omissions, gate-set changes lost across a seam, native gate capacity |
| Semantic | about 10% | branch meaning, signedness, which live byte a guard reads |

The mechanical class is entirely derivable from the original machine, and every one of
its historical instances is reproduced or caught by the trace-based checker in section 6.
The semantic class is small and is exactly where a model's intelligence belongs.

## 4. Automation frontier

Applying the decision model from the brief to every repeated activity in the current loop:

| Activity | Requires game meaning? | Verdict |
|---|---|---|
| Naming the branch predicate and which live bytes it reads | yes | keep AI-driven |
| Deciding supported versus unsupported arms | yes | keep AI-driven, with the fact report showing every observed arm |
| Choosing the enclosing parent and the next connected frontier | yes | keep AI-driven, fed by a mechanical frontier ledger |
| Instruction and cycle counts, last PC, stack delta, return PC | no | derive from the original (done, section 6) |
| Changed registers, lanes, CCR and X at exit | no | derive and check (done) |
| RAM residue, including stack-slot bytes and MOVEM frames | no | derive and check (done) |
| Prefix, native span and suffix split around a sound call | no | derive (done, `split_at_native`) |
| Constancy of cost within a branch across inputs | no | derive (`branches`) |
| Fixture-specific constants in a plan | no | catch mechanically (`check --vary`) |
| Fresh-process, outer, future comparison boilerplate | no | already shared (`qualify_atomic_plan`); keep |
| Canonical census of an entry | no | already mechanized (`recovery_census`); extend to parent-of-child capture |
| Verifier state (running, pass, stale, timeout) | no | classify mechanically (section 10) |
| Deciding that a wrong `last_pc` is invisible behind later original instructions | no | the checker sees it; the qualifier does not |
| A new device protocol, a command-stream engine, a new state authority | yes, and beyond a cheap model | escalate |

## 5. Python and C++ placement

| Component | Measured | Placement |
|---|---|---|
| Genesis execution (`al_run`) | 2.3 to 2.9 ms per frame; 55 to 60% of a verification worker | KEEP C++ (donor) |
| Snapshot export | 1.0 ms per frame, 162 KB; 20% of a worker | KEEP C++; digest-only export would save under a fifth of it |
| Frame render and copy | 1.0 ms per frame; 20% of a worker | KEEP C++ |
| Copy to Python and SHA-256 | 0.05 ms (copy) plus 0.15 ms (hash) per frame; 3 to 5% | NO BENEFIT FOUND in a native digest observer: the copy is already negligible and hashing is 3% |
| Observation cadence | every frame adds 33% to a worker; every 60th frame adds nothing measurable | KEEP PYTHON; a policy decision, not a C++ one |
| `info` and register FFI calls | 6,633 `info` calls cost 35 ms in a 6.3 s run | NO BENEFIT FOUND in batched status |
| Python planning inside a candidate run | 0.37 s of a 6.3 s lifecycle run (231 atomic plans, whole-scan planner 51 ms cumulative) | KEEP PYTHON |
| Two sequential fresh workers | 240 s for 26,378 frames; 127 s when run in parallel with identical observations | KEEP PYTHON; run in parallel (DO NOW) |
| Machine construction in a live process | 9 ms; a fresh Python process with DLL, ROM and machine 80 ms | KEEP as is |
| Fresh-process continuation (`fresh_process_future`) | 0.13 s per call, dominated by interpreter start | KEEP as is |
| Path tracing (single-step through the C ABI) | 0.02 to 0.6 ms per instruction; a 257-instruction whole tick in 0.06 s, a 7,867-instruction command-stream path in 0.18 s | KEEP PYTHON now; MOVE TO C++ only when traces exceed roughly 100K instructions. The donor interpreter already exposes `replay::Observer`, `BusTap::access` and `last_cycles()`, so a native tracer is a bounded 100-line addition when needed |
| Recovery policy, boundary recipes, semantic game code, fixtures, census, history graph, verification policy | edited on every step | KEEP PYTHON |
| AtomicPlan application, scheduler admission, Z80 guard | stable, in the hot path | KEEP C++ (already) |

The whole-history verification floor is set by execution plus observation, roughly
4.5 ms per frame per worker. With `main` now at 57,289 frames after this morning's play
session (it was 26,378 when the docs were written), a sequential cold comparison will take
about nine minutes and a parallel one about half that. Nothing in C++ changes that materially;
cadence and parallelism do.

## 6. Mechanical-fact experiments

A Python-side tracer (`pathfacts.py`, no native change) single-steps the original machine
from a parked fixture until it returns to its caller, disassembles each instruction with
Capstone, and records per instruction: cycles, branch decision, register changes, RAM
bytes changed, calls and returns. From that it reports the AtomicPlan-shaped facts a
boundary planner must reproduce, and a checker compares a planner's plan against them.

### 6.1 Reproducing the historical Type-55 mistake

| Input | Original facts (traced) | Boundary plan | Check |
|---|---|---|---|
| `FF7DFC=100`, non-borrow | 15 instructions, 180 cycles, last PC `1AE6BA`, writes `FFF0F5=FF`, D0/D2/D7 lanes, CCR clear | 180 / 15 | MATCH |
| `FF7DFC=76`, borrow and NEG | 16 instructions, 182 cycles, X=1 Z=1 at exit | 182 / 16 | MATCH |
| Non-borrow plan with the historical 182/16 | | | `cycles: plan 182 vs original 180; instructions: plan 16 vs original 15` |

Each fixture, park, trace and check takes 0.06 s. The strong-model review that found this
bug this morning took a separate session.

### 6.2 What each tier says about a wrong plan

Eight faults injected into the correct Type-55 plan and pushed through the real production
route:

| Fault | Existing narrow qualifier (outer and future equality) | Trace checker |
|---|---|---|
| cycles +2 | DIVERGE outer=[state, info] | `cycles: plan 182 vs original 180` |
| instructions -1 | DIVERGE outer=[state, info] | `instructions: plan 14 vs original 15` |
| last PC +2 | PASS | `last_pc: plan 1AE6BC vs original 1AE6BA` |
| wrong result byte | DIVERGE outer=[state, ram] | `wrong write FFF0F5: plan FE vs original FF` |
| missing write | DIVERGE outer=[state, info, registers, ram, pcm] | `missing write FFF0F5=FF` |
| wrong D7 lane | DIVERGE outer=[state, registers] | `register d7: plan 76540013 vs original 76540012` |
| wrong X flag | DIVERGE outer=[state, info, registers] | `register sr: plan changes it to 2010, original left 2000` |
| wrong continuation | NativeError: unsupported opcode at 1ABCAA | `register pc: plan 1ABCA2 vs original 1ABCA0` |

Two findings matter for the factory. The qualifier's verdict is a set of coarse keys, which
is why workers bisect by hand. And a wrong `last_pc` passes the qualifier whenever original
instructions run between the plan and the observation point, because `standing_pc` is
overwritten; the existing regression only covers the case where the observation sits
exactly at the plan's end. The checker sees it directly.

### 6.3 Larger regions and the seam split

The whole contact tick (`1ABB40` through its real RTS, 236 to 257 instructions with two
callbacks and the shared completion) traces in 0.06 s and its production plan matches every
cycle, register and changed byte. The only flags were plan writes storing the value RAM
already held, which a diff-based trace cannot see and which the checker now reports as
harmless notes.

For the recorded Type-43 callback (`1AE64C`, 114 instructions), the tracer splits the path
around the native sound calls into the contract a `SoundSeam` needs: a 32-instruction,
510-cycle prefix ending at `1E58B8` with the exact saved-frame bytes, two native spans, and a
four-instruction restore suffix returning to `1ABCA0`. That is the information whose absence
ended the Type-3A and Type-2D probes.

### 6.4 Verdict on fact extraction

Machine-fact extraction is worthwhile and cheap. It reproduces every historical mechanical
mistake, diagnoses faults the qualifier only detects, and costs 0.06 s per branch. It needs
no C++ today.

## 7. Recipe experiments

Repeated shapes in `boundary.py`, counted:

| Shape | Concrete instances | What varies | What is machine residue |
|---|---:|---|---|
| LEA/BSR/RTS allocator wrapper (`spawn_plain_caller`) | 12 | template, allocator arm | fixed 30/2 prefix, 16/1 RTS |
| allocation success with position offset | 3 | X and Y deltas | 64/4 suffix, `_add_sr` |
| closure callback with distinct suffix | 4 plus one guard | type, script, mode | suffix cost, final CCR |
| guard then RTS or fallthrough | 6 spawn, several contact | which byte, polarity | 42/3 versus 28/2 |
| dispatcher child composition (`_contact_family_dispatch`) | 10 users | callback planner | JSR frame identity |
| synchronous sound seam (`SoundSeam` construction) | 13 | command, resume PC, stack basis | 24/28/28 frame, five saved registers, command long, return slot |
| MOVEM save frame written by hand | 8 copies | command, return | identical five-register loop |
| MOVEM restore at resume written by hand | 5 copies | | identical |
| explicit unsupported-arm refusals | 21 messages | | the frontier, embedded in code |

The seam shape is the recipe that matters, because section 1 shows the seam is where cheap
workers fail, and the census in section 13 shows every remaining recorded contact-frontier
branch except Type-55 crosses it. The eight hand-written frame builders and five hand-written
restores are the concrete duplication. A checked recipe (`sound_request_frame(registers, sp,
command, return_pc)` and `sound_resume_frame(machine, sp)`) whose facts are verified by the
tracer's native-segment boundaries would replace them without a generic interpreter.

The cheap-model trial in section 13 measures whether the recipe plus facts changes
autonomy; the count alone does not.

## 8. Emitter verdict

| Level | Meaning | Verdict |
|---|---|---|
| 0 | fully handwritten boundary | current state; too error-prone for a cheap model |
| 1 | handwritten semantic source, mechanically checked facts | DO NOW; measured above |
| 2 | Level 1 plus narrow checked recipes for the seam and the dispatcher child | DO NOW for the seam; WAIT for others until a sibling case exists |
| 3 | partially generated planner skeleton | REJECT for values, ACCEPT for the cost table only |
| 4 | generic emitted machine-shaped implementation | REJECT |

The Level-3 prototype (`factcheck.py skeleton`) generates a correct per-path cost table
(cycles, instructions, last PC, exit) from traced variations, which is legitimately
mechanical. It also fills every RAM value and register with the fixture's observed constant
and marks them "TODO(semantic)". A cheap model given that skeleton is invited to leave the
constants in place, which is precisely the "fixture-specific A3/D1/publication constants"
failure the cost log records from a draft this weekend. The varied-state checker catches
that, but the safer product is not to generate the values at all. The donor already contains
a Level-4 emitter (`pf_genesis_emit`, emitted units, code census); the project's own 0.6
carrier verdict and the semantic-migration reports explain why execution ownership without
semantic ownership does not converge, and nothing measured here contradicts them.

## 9. Validation cadence

Measured tier costs on this host (26,378-frame history unless stated):

| Tier | Cost | What it catches | What it misses |
|---|---:|---|---|
| T0 trace check (`factcheck check`) | 0.06 s | every mechanical fact, including wrong `last_pc` | semantic domain, aliases, scheduler refusals |
| T0v varied-state check (`check --vary`) | 0.06 s per variation | fixture constants, wrong branch predicate | |
| T1 fixture qualification (`qualify_atomic_plan`, fresh process) | 0.25 s | outer, future and fresh-process equality | which fact is wrong; wrong `last_pc` behind later instructions |
| T2 the branch's test module with mutants | 3 to 5 s | routing, mutants, refusal and deadline behaviour | |
| T2p parent-ownership replay of retained recorded parent fixtures | 0.04 s per fixture | the parent declining a child it should own (the Type-20 finding) | |
| T3 focused subsystem suites | 30 to 35 s | interactions within the family | |
| T4 full suite | 162 s | gate capacity, history and machine invariants | |
| T5 cold history comparison | 127 s parallel, 240 s sequential; double on the 57K-frame main | publication evidence | nothing, but it does not explain |

Fault injection shows T0 already reports every mechanical fault T1 through T5 would find,
with a diagnosis, so the grinding cadence should be:

```text
after edit:            T0, T0v on the fixture matrix (sub-second)
after branch:          T1, T2 (seconds)
after integration:     T2p on the retained parent fixtures, T3 (under a minute)
after a connected batch: T4 (2.7 min)
before publication:    T5 with parallel workers, source frozen (2 to 5 min)
```

Publication evidence is unchanged: every-frame strict comparison, fresh workers, current
receipts, zero restores. Only its timing changes.

Two gaps in the cheaper tiers were found: the 63-gate native limit is only caught by T4
(a 0.1 s assertion on `len(Candidate('lifecycle').gate_pcs)` belongs in T2), and parent
non-ownership was only visible in T5 (the parent-of-child census in section 14 supplies
T2p's fixtures).

T2p was validated on `main` as it stands. A census that retains the contact-tick entry
state whenever a frontier callback actually fires (82 s over 26,378 frames, 48 fixtures)
replayed each retained parent through the production candidate in 0.04 s and named the
declined child every time: `1AE64C`, `1AF228` and `1AEE40` as unrecovered targets; the
Type-1F sound arms; and, notably, the recorded Type-55 at scan slot 19. Type-55 was
recovered at the dispatcher level this morning, but the owned scan's callback map was not
extended, so the parent still declines it three times in the cold run. That is the same
integration omission the Type-20 cold run exposed, now visible without the cold run. A census
that only asks whether a kind is present in the pool does not find this; the child must
actually fire.

## 10. Operational stalls and context economics

Operational stalls in the rollouts were not recovery difficulty: a verifier declared blocked
after 3 minutes of a 4-minute run; two overlapping verifications writing one directory; a
launcher without the DLL environment; a census killed by the foreground execution window;
`CANDIDATE_ERROR` reported for what was a watchdog `TIMEOUT` (the comparator folds the
candidate worker's timeout kind into `CANDIDATE_ERROR`); 81 process-polling commands and 32
status-only turns in one session.

A read-only classifier (`verify_status.py`) maps an evidence directory to exactly one of
`RUNNING`, `PASS`, `STALE_EVIDENCE`, `DIVERGENCE`, `TIMEOUT`, `DEPENDENCY_FAILURE`,
`NOT_EXERCISED`, `ERROR`, `NO_EVIDENCE` by reading the launcher PID, `comparison.json` and the
receipts against current source hashes. On the existing artifacts it returns `PASS` for the
current Type-20 receipt, `STALE_EVIDENCE` for the Type-55 receipt (boundary and recovery have
changed since), `TIMEOUT` for the old watchdog run, `NO_EVIDENCE` for a missing directory.
No strong reasoning is required to read it.

Context: the mandatory reading list in the handoff (status, workflow, cost log, handoff,
boundary, recovery, oracle, family tests) is about 120K tokens. The worker read `boundary.py`
in 29 slices. A subsystem split of `boundary.py` (spawn, collection, contact family, contact
tick, sound seams, machine helpers) plus a one-page recipe index (shape, exemplar function,
test module) would let a worker read two functions instead of twenty slices. The trial's B arm,
whose protocol names exact exemplar functions, measures that directly (section 13).

## 11. Cheap-agent recovery protocol

The protocol used in the trial is `trial/PROTOCOL.md` in this review's scratch directory; its
loop is:

```text
1  SELECT a frontier entry from the ledger (fallback count, refusal site, recorded fixtures)
2  CENSUS the entry and its parent (recovery_census; parent-of-child capture)
3  FACTS  trace the recorded fixture: path, writes, registers, CCR, calls, seam split
4  CLASSIFY into one recipe: RAM-only leaf / dispatcher child / single sound seam / UNSUPPORTED
5  WRITE the semantic predicate and durable writes in game/objects/*.py
6  WRITE the boundary planner from the recipe, every number from the fact report
7  CHECK  factcheck check, then check --vary over the observed branch inputs, until MATCH
8  ROUTE  the dispatcher arm exactly as the exemplar; assert the gate set fits
9  QUALIFY T1/T2 with mutants; T2p on retained parent fixtures
10 INTEGRATE upward only when the parent's retained fixtures show it declining the child
11 LEDGER  recompute the fallback ledger; pick the next connected entry
12 ESCALATE with a blocker package when step 4 says UNSUPPORTED or step 7 fails three times
```

## 12. Escalation rules

A cheap worker stops and writes a blocker package (where, observed behaviour from the fact
report, why the recipe does not fit, relevant facts, fixture, failed hypotheses, next
questions) when any of these hold:

| Code | Trigger, mechanically observable |
|---|---|
| NEW_MACHINE_MECHANISM | the trace shows a second native call outside the known sound entries, a device register access, or an interrupt inside the region |
| NEW_DEVICE_INTERACTION | a call into an address outside ROM code seen before, or a Z80/VDP touch in the native segment |
| NEW_STATE_AUTHORITY_REQUIRED | the plan would need to keep state between two gate hits |
| UNKNOWN_SOUND_PROTOCOL | a seam whose frame is not the 24/28/28 five-register shape or whose resume is not the instruction after the second JSR |
| UNSAFE_ALIAS_MODEL | `_spans_disjoint` refuses on the recorded fixture itself |
| NEW_DATA_STRUCTURE | more than three record fields the semantic layer has never named |
| PARENT_BOUNDARY_UNCLEAR | the caller return is not a single known site across the recorded fixtures |
| REPEATED_PATTERN_WITHOUT_RECIPE | the third hand-copied shape of one kind |
| VERIFICATION_ARCHITECTURE_FAILURE | T0 matches but T1 diverges, or T5 diverges after T1 through T4 pass |
| SEMANTIC_MODEL_CONTRADICTION | the fact report and the semantic function disagree on which bytes a branch reads |
| NATIVE_LIMIT | the gate set exceeds 63 or the atomic cost bounds |

Type-1F kind 21 is the canonical example: the trace enters `1ACD54`, `1B249E`, `1B263C..1B26D0`
for 7,867 instructions. That is NEW_MACHINE_MECHANISM by rule, and no cheap worker should
attempt it.

## 13. Assembly-line trial

Four Sonnet runs, two targets, two arms each, in isolated worktrees of `4284daf` with
junctions to the ROM, DLL, venv and history. Arm A received the project's own handoff
(`docs/solo-recovery.md`, the workflow, status and cost-log documents) and the recorded
fixtures. Arm B received the protocol, the tracer and checker, the fact report for its
target, and the same fixtures. Budget: 60 minutes or 80 tool calls; no commits; no full
suite or cold verification inside the box. The targets:

- T1, the `FFF0BE != 0` arms of Type-55 at `1AF590`: a RAM-only sibling arm with one
  recorded decline in the ledger.
- T3, the recorded Type-43 callback at `1AE64C`: activation writes, a helper call, a
  command-0x63 sound request through the two native calls, restore and RTS. This is the
  class that ended four probes in the Terra session this morning.

| Arm | Target | Status | Agent time | Tool calls | Tokens | Built its own tracer | Independent verification |
|---|---|---|---:|---:|---:|---|---|
| A (handoff only) | T1 Type-55 arms | DONE | 16.5 min | 58 | 199K | yes, five probe scripts | 12 of 12 varied states match or decline correctly; 85 module tests, 334 focused tests pass |
| B (protocol + facts) | T1 Type-55 arms | DONE | 12.5 min | 53 | 172K | no, every number from the checker | 12 of 12; 48 module tests, 297 focused tests pass |
| A (handoff only) | T3 Type-43 seam | DONE | 27 min | 78 | 298K | yes: single-step register and RAM diff, ROM byte dump, hand-decoded 68000 opcodes, formula verifier | prefix and suffix match on all three recorded fixtures; real-route parent replay equal with fresh-process continuation; 278 focused tests pass |
| B (protocol + facts) | T3 Type-43 seam | DONE | 22 min | 68 | 256K | no | same checks, all pass; 275 focused tests pass |

Every run left the gate set at 62, removed no assertion, and admitted no fixture
constant (the varied-state check across both guard bytes and three motion values was
clean for both T1 planners; both T3 planners read every input from live RAM). Nobody
intervened in any run.

What the trial shows:

1. Neither branch class is beyond a cheap model. The seam branch that stalled the
   medium-effort Terra worker four times was recovered correctly by both Sonnet arms.
2. Both baseline arms built a tracer before they could proceed. The T3 baseline
   single-stepped the original with register and RAM diffs, dumped ROM bytes and
   hand-decoded the opcodes, which is the step where this morning's Type-55
   misclassification happened. The provided tool removed that step: 19 to 24% less agent
   time, 9 to 13% fewer tool calls, 13 to 14% fewer tokens, and zero hand-derived numbers.
3. The Terra worker did not build a tracer and abandoned its seam probes; the Sonnet
   baseline did build one and succeeded. The tool's value is therefore largest for the
   worker that would not have built it, and this trial cannot measure that directly. The
   next trial should run the actual grinder model at medium effort with the protocol.
4. All four runs inlined the semantic writes in `boundary.py`, against the protocol's
   step 5, because the exemplars they were told to copy (Type-46, Type-55) are themselves
   inlined. A cheap model copies the exemplar's shape over an instruction. The exemplar
   must have the shape the factory wants.
5. The protocol arm found a defect in the checker (a second machine opened inside the
   first one's context on a declined plan) and worked around it; it was fixed during the
   trial. The baseline arm misused the qualifier once (a raw-entry state with the wrong
   exit) and judged the failure benign after a trace. Both are the kind of tooling-state
   confusion the status classifier in section 10 exists to remove.
6. What the trial does not show: frontier selection, census and fixture construction were
   done by the strong model, which is the intended division of labour, so these numbers
   measure implement-and-qualify, not discover.

## 14. Recommended architecture changes

Landed on 14 September (afternoon): every DO NOW row below is in the checkout as a tracked script with tests, the exemplars are split, the trial recoveries are adopted and the trial worktrees are removed; see `docs/recovery-grinder-protocol.md`, `docs/recovery-ledger.md` and the STATUS section of the same date.

| Change | Evidence | Verdict |
|---|---|---|
| Adopt the tracer and checker (`pathfacts.py`, `factcheck.py`) into `scripts/`, with the Type-55, tick and mutant cases as tests | sections 6 and 9 | DO NOW |
| Run the two verification workers in parallel in `compare_history` | 127 s versus 240 s, identical observations | DO NOW |
| Add `verify_status` and report worker timeouts as `TIMEOUT`, not `CANDIDATE_ERROR` | section 10 | DO NOW |
| Frontier ledger from `comparison.json` fallback reasons joined to the boundary's refusal sites | 21 explicit refusal markers, 3 unrecovered targets | DO NOW |
| Parent-of-child census retaining the parent state when a frontier child fires, as T2p fixtures | the Type-20 finding | DO NOW |
| Gate-count assertion in the fast tier | the Type-03 full-suite failure | DO NOW |
| Checked sound-seam recipe (frame builder and resume restorer) verified against the tracer's native-segment boundaries | 8 plus 5 hand copies, seam failures in section 1 | EXPERIMENT NEXT, gated on the trial |
| Split `boundary.py` by subsystem and add a recipe index | 29 slice reads per step | EXPERIMENT NEXT, measured by reads per step |
| Give the exemplar planners the semantic split the factory wants (predicate and writes in `game/objects`, facts in the boundary), because cheap models copy the exemplar's shape | trial finding 4 | DO NOW |
| Run the protocol with the actual grinder model at medium effort on the next three ledger entries | trial finding 3 | EXPERIMENT NEXT |
| Cost-table generation only (`skeleton` without values) | section 8 | WAIT |
| Native tracer in `machine.cpp` | 0.18 s for 7,867 instructions | WAIT until traces exceed 100K instructions |
| Native digest observer | 3 to 5% of a worker | REJECT |
| Batched run and status FFI | 35 ms in 6 s | REJECT |
| Generic emitted machine-shaped code | sections 7 and 8 | REJECT |
| Reference-stream cache for the original worker | sound in principle, but publication requires fresh workers | WAIT; use only in the grinding tier |

## 15. Final answers

**Can this process plausibly become a long-running cheap-model recovery loop?** Yes for
the recovered-object, contact and collection subsystems as long as the machine facts are
derived rather than counted. Four cheap-model runs recovered two frontier branches,
including a sound seam, with zero interventions and zero errors on independent review.

**What currently prevents it?** Three things, in order: a qualifier that says only which
observation key differed, so a stuck worker bisects by hand or abandons the branch; a
reading load of about 120K tokens per step from one 4,144-line boundary file and the
handoff documents; and operational ambiguity around the verifier (timeouts reported as
candidate errors, no single status word), which produced the only human interventions
of the weekend.

**Which intervention produced the largest improvement?** Machine-fact extraction with a
plan checker. It reproduces every historical mechanical mistake in 0.06 s, diagnoses
faults the qualifier only detects, and removed the hand-decoding step from the cheap
model's loop.

**How many recovery steps can the improved process sustain before escalation?** Today's
baseline is two to three leaves per strong-model intervention. With facts, the checker,
the parent-ownership tier and the status classifier, the remaining recorded contact
frontier (Type-3A, Type-2D, the Type-1F sound arms, the Type-03 mutation arm, the parent
compositions of the seams) is eight to twelve connected steps with no new mechanism, so
a run of that length is the realistic expectation. The command-stream engine behind
Type-1F kind 21 and Type-7E progress is the first NEW_MACHINE_MECHANISM escalation.

**Is machine-fact extraction worthwhile?** Yes, measured. Python-side, zero native
change, 0.06 s per branch.

**Are narrow recipes worthwhile?** For the sound seam, yes: thirteen hand-built seams and
eight hand-copied frames, and the seam is where the medium worker failed. The other shapes
already have shared helpers; leave them until a sibling appears.

**Is a larger emitter worthwhile?** No. Generated skeletons carry fixture constants into
code; only per-path cost tables are legitimately generated. The donor's emitter answers a
different question (execution ownership) from the one this project asks (semantic
ownership).

**Which Python work should move to C++?** None now. A native tracer becomes worthwhile
only past roughly 100K-instruction traces; a native digest observer would save under 5%
of a verification worker.

**Which Python work must remain Python?** Recovery policy, boundary recipes, semantic
game code, fixtures, census, the history graph, verification policy and the fact tools:
everything a worker edits or reads on every step.

**Is current convergence compatible with eventually consuming most or all gameplay this
way?** For subsystems built from bounded RAM-effect callbacks and the known sound ABI,
yes: the mechanisms have been stable for the last twenty milestones and the frontier ledger
now enumerates the remaining arms. The command-stream engine, VDP and controller paths,
and Z80 interactions are outside that domain and will each need a strong-model phase
that defines a new seam before cheap grinding resumes there. `main` growing from 26,378
to 57,289 frames this morning also means the frontier grows with recordings; the ledger
must be recomputed per recording.

**What should the next factory-improvement cycle focus on?** Adopt the DO NOW rows of
section 14, give the exemplar planners the semantic split, then run the actual grinder
model with the protocol on the next three ledger entries and measure steps per
intervention again.
