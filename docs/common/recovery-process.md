# The recovery process

How a bounded region of an original Genesis game becomes readable source that
provably does what the original did.  This is the loop Aladdin converged on
after two weeks of grinding (`../aladdin/convergence.md`) and the loop the
first Gods region went through unchanged (`../gods/STATUS.md`, region
`002806`).  It is game-neutral: it names mechanisms and evidence, never a
game's addresses.  Each game's own playbook says how the loop maps onto that
game's code.

## The idea

The original machine is the oracle.  A recovered region is never trusted
because it reads well; it is trusted because, on every state a real player
history reaches, the machine ends in exactly the state the original would
have produced, and the rest of the game runs on from there identically.  The
loop below exists to make that claim cheaply, repeatedly and honestly.

```text
real player history
        v
deterministic original execution (the oracle)
        v
execution census: which regions run, how often, how long
        v
choose one bounded candidate
        v
retain one real entry state per executed path class
        v
extract the exact original facts of each path
        v
write the semantics (readable, pure)
        v
write the boundary plan (exact machine effects, per-path cost)
        v
gate the candidate; the adapter admits the plan or the original runs
        v
strict immediate witness (plan == traced facts, every path)
        v
future continuation from retained states (segments)
        v
fresh-process verification of the whole history
        v
negative control (a wrong plan must diverge)
        v
record; update the frontier; choose the next candidate
```

## The stages, and why each exists

### 1. Real player history

`play.cmd --game GAME` records controller input as an immutable cold-start
history (`history-and-replay.md`).  Inputs, not machine snapshots, are the
evidence: they are small, portable, game-identified, and replaying them from
power-on reconstructs every state the player reached.  Constructed input
(`history-capture`, test fixtures) is useful for smoke checks and is always
labelled constructed; it never stands in for gameplay.  A region is only as
recovered as the recordings that exercise it.

### 2. Deterministic original execution

Before any recovery: the same history from cold reset must give the same
per-frame state, video and PCM in two fresh processes
(`history-verify NODE --game GAME --candidate original`, `--tree` over every
branch), the player's cache must land where a cold run lands, and a shifted
input must diverge detectably.  If the original is not reproducible there is
no oracle, and nothing later means anything.  A machine defect found here is
fixed in the shared machine with a regression test, never with a game-specific
hack.

### 3. Execution census

`scripts/hot_calls.py --game GAME --from F --to F` single-steps a window of
gameplay and lists every callee with its call count and activation lengths.
`scripts/recovery_census.py OUT --game GAME --entry PC ...` then replays the
whole history with a gate at chosen entries, single-steps every occurrence,
groups occurrences by executed path (the *path signature*: the PCs executed
outside native callees plus the depth-zero calls) and retains one real entry
state per class, plus one per exit CCR.  Regions are chosen from what the
recordings execute, not from reading the ROM top-down: a region that runs
6,000 times in four minutes of play is both worth recovering and thoroughly
witnessed.

The census is discovery, not evidence.  It changes nothing about the
trajectory (the terminal observation is recorded so a cold run can confirm).

### 4. Choosing a candidate

A good first candidate has a clear entry and return (JSR target, RTS), small
size (tens to a few hundred instructions), work-RAM-only effects, no device
access, no calls (or only calls the game's playbook already knows how to seam),
a bounded loop count, and every path class covered by recordings.  A region
whose device work is one bounded block — a call to a sound or video helper,
or an inline upload loop — with recovered code before and after it is the
next shape, the seam (§7b).  Regions with device accesses interleaved with
RAM work in several blocks, the controller ports, interrupt handlers,
command interpreters or unbounded loops are deferred until the game has a
mechanism for them; that deferral is a result, not a failure.

### 5. Exact facts

`scripts/factcheck.py facts FIXTURE.state --game GAME [--path]` single-steps
the original from a retained state and reports, per path: instructions,
cycles, last PC, exit PC, stack delta, every RAM byte written, every changed
register, the CCR at exit and where each flag last changed, calls and
returns.  `branches --vary ADDR=v1,v2` sweeps inputs to find arms and check
whether cost is constant inside a path; `segments` splits an activation at
native callees.  Numbers are derived, never counted by hand: the historical
mistakes were all hand-counted cycles, mis-read flags and unnoticed extra
writes, and the tracer reproduces every one of them in milliseconds.

### 6. Semantics

Under the game's package (`src/<game>/game/...`): a pure function of a reader
over live RAM that returns what to store and what the routine decided.  No
cycles, stack slots, CCR, registers, gates or plans here.  Names are what the
arithmetic supports, not more.  Arms the recordings never entered may be
written when they are readable in the ROM, but they are not recovered until
witnessed; the boundary declines them.

### 7. Boundary plan

Under the game's package (`src/<game>/boundary.py`): a planner that reads the
parked machine at the entry and returns an `AtomicPlan`: the exact byte
writes, the register file at the exit (data registers, `A7`, the return `PC`
from the stack, `SR` with the CCR the last flag-setting instruction leaves,
including `X`), the instruction and cycle cost of the path taken, and the
last PC.  It raises `UnsupportedCandidate` for anything outside what has been
witnessed.  Every constant in it comes from the fact report.

### 7b. The seam: a platform operation inside a region

When the executed path contains one bounded platform operation (Aladdin: a
JSR to the sound request or the VDP tile upload; Gods: an inline VDP data
loop), the planner returns a `Seam` (`src/genesis_re/seam.py`) instead of a
plan: a **prefix** plan that ends with the PC at the operation's first
instruction and every register it reads in place, the **resume PC** after
the operation, the activation's **identity** at the resume (the expected
`A7`, guarded stack spans that must be unchanged, slots that must hold a
known return address), and a **suffix** planner that reads the live state
at the resume.  `run_seam` is the shared mechanism: the prefix is admitted
and committed, only the resume PC is gated while the machine runs the
operation, a foreign activation at the resume is bypassed, a changed guard
raises, the suffix is planned from live RAM and admitted, and a frame
deadline inside the operation leaves the rest of the activation to the
original (the prefix was exact).  Two rules Aladdin paid for: never chain
seams to own the wrapper code between two platform calls — cede the whole
tail to the machine and resume at the region's own RTS; and never put a
device access in the prefix or suffix.  What the recordings must witness
is the same as for a leaf, plus the suffix's identity on every retained
path; the strict check (`factcheck check`) compares the prefix to the
platform entry and the suffix from the resume.

Keeping semantics and boundary apart is what makes recovered source readable
and the machine contract exact at the same time: the semantics survive the
machine, the boundary is the adapter that will disappear with it.

### 8. Gate and admission

The game's dispatcher (`src/<game>/recovery.py`, a `Candidate` with `arm`,
`on_gate`, `stats`) arms the entry PCs as gates.  When the original reaches
one, the replay runner calls `on_gate` with the frame's deadline; the planner
runs; `Machine.atomic(...)` asks the shared adapter to apply the plan as one
operation with the original's cost charged.  The adapter refuses (returns
`False`, machine untouched) when the operation would cross the deadline or an
interrupt would fall inside it; the planner refuses for unwitnessed arms.
Either way the original executes the region (a *fallback*), counted by gate
and reason in `stats`.  Nothing is half-applied, and a fallback never changes
the trajectory.

### 9. Strict immediate witness

`scripts/factcheck.py check FIXTURE.state <game>.boundary:PLANNER --game GAME`
runs the planner on the retained state, traces the original from the same
state, and reports every fact the plan gets wrong: `MATCH`, `MISMATCH` (which
fact) or `DECLINED`.  Required on every retained fixture of every path class
the plan claims, and on every `--vary` combination that selects a claimed arm.
A `DECLINED` on a claimed arm is a wrong guard; a `MISMATCH` is a wrong
number.  Fixtures are never adjusted to make a plan match.

### 10. Future continuation

`scripts/segment_verify.py FIXTURE.state --game GAME --candidate NAME
--frames N` restores a retained real state into a candidate run, advances it
N frames with the recorded inputs under real deadlines, and compares every
frame's state, video and PCM with the reference observations of the last PASS
cold run of the same history (`reference.json`, retained beside the
fixtures).  Seconds, independent of history length.  It catches what an
immediate witness cannot: an effect the original would have consumed later.

### 11. Fresh-process history verification

`scripts/dev.py history-verify NODE --game GAME --candidate NAME --output
artifacts/...` starts two fresh workers, original and candidate, from
power-on, and compares every canonical frame: full native state hash, video,
PCM chain and byte count, CPU/Z80 counters, PC/SR, terminal.  `--tree`
does it for every branch of the history.  `scripts/verify_status.py DIR`
reads the result as one word (PASS, DIVERGENCE, NOT_EXERCISED,
STALE_EVIDENCE, TIMEOUT, ...).  A PASS with zero candidate hits is
`NOT_EXERCISED`, not evidence.

### 12. Negative control

A candidate name whose plan is deliberately wrong (one stored byte off, a
different return, a different cost) must produce `DIVERGENCE` on the same
history, at the first frame that enters the region.  Without it a PASS could
mean the comparison is not looking.

### 13. Record and continue

One ledger line per recovered region (entry, paths, hits, fallbacks, the
artifacts directory of the PASS, the commit); the game's STATUS updated once
per milestone; the next candidate chosen from the fallback counts of the last
PASS (`scripts/frontier_ledger.py`) and the census.  Milestone gates: the
game's test scope (`scripts/run_tests.py GAME`), the cold comparison, then
push.

## The confidence hierarchy

Each tier proves something the tier below cannot; none proves the tier above.

```text
unit semantics (synthetic reads)
  < exact local machine witness (factcheck check on real retained states)
    < segment future continuation (segment_verify from retained states)
      < complete recorded-history comparison (history-verify, fresh workers)
        < tree / several histories (history-verify --tree, more recordings)
          < independent native execution (the recovered code runs the game
            without the original CPU; Aladdin only)
```

What no tier proves: arms no recording entered, behaviour on inputs no one
played, and anything about a different ROM revision.  A PASS is a statement
about one history, one candidate name, one native build and one source tree
(the receipts in every report pin all four).

## Refusals, fallbacks and blockers

- A **fallback** is correct behaviour: the original runs the region.  Its
  reason is counted (`unsupported domain: ...`, `scheduler admission`).
  Fallbacks are the frontier.
- A **refusal** by the planner (`UnsupportedCandidate`) is the honest edge
  of the evidence: an arm not witnessed, a state outside the guards.
- A **blocker** is a candidate whose execution shape no game in the
  repository has proven: recovered writes needed between two platform
  operations, a device access in the prefix or suffix itself, an interrupt
  handler inside the region, an unbounded loop, a data structure nobody
  has named.  A shape one game has proven and another has not implemented
  yet is not a blocker: the second game reproduces the shape (its own
  addresses, its own semantics) and verifies it through the full ladder.
  The right result for a real blocker is a blocker package (where, code,
  observed facts, fixtures, what was tried, the one question a stronger
  model can answer) and the next candidate.  Grinders do not build
  mechanisms.

## The three things a game is, and the order of work

There are exactly three concepts: the **original** (the oracle: the ROM on
the shared machine, replayed from recorded inputs), the **recovery
workbench** (the original with recovered regions admitted inside it —
gates, plans, seams, the exact temporal machinery, every comparison in
this document), and the **native source port** (the game as readable,
maintainable, extendable source, verified against the oracle and the
recordings).  Nothing else is a mode, a stage or a progress category.
Exact temporal machinery belongs to the workbench; the port is what
remains when the workbench's adapters are taken away.

The lasting artifact is the recovered semantic implementation.  During
recovery it runs as *original machine → boundary adapter → recovered
semantic function*; in the port it runs as *native subsystem → the same
semantic function*.  Adapters own guest registers, stack conventions,
timing facts, resume identities, machine side effects and comparison
mechanics.  Semantic functions own gameplay behaviour, meaningful state
and meaningful ordering.  There is one implementation: no separate exact
and native versions, and no gameplay decision accumulates in an adapter.
A small native-composition test that drives a recovered subsystem
through a native-state adapter is useful evidence that the semantics are
not tied to the machine; a native runtime, scheduler or whole-frame
driver is not built until the phase below says so.

The order of work is the one Aladdin converged on, and the port is built
last: bounded leaves → their callers → dispatcher families → larger owned
regions → grind the bounded frontier → concentrate the remaining gaps →
understand the tick → only then compose the native driver.  Ownership
rises through the original call graph (leaf → handler → dispatcher family
→ subsystem → subsystem caller → larger owned region) and verification
rises with it: leaf boundary → caller → dispatcher family → subsystem →
tick region, the original remaining the strongest oracle while the
regions are discovered.  The signal to start composing the native driver
is architectural, not a percentage: most remaining work is composing
already-recovered subsystems into the loop rather than discovering
isolated semantics — the cheap frontier largely exhausted, the important
dispatcher families owned as parents, the remaining original execution
concentrated in a few understood hard regions, the tick semantically
mapped.  Aladdin still had concentrated hard gaps when it got there; that
is allowed.  Then: map the loop, build the driver around the recovered
implementations, fail loudly on the gaps, verify steps, ticks, device
effects and full recordings against the oracle.

A **temporal adapter** — recovered code that stays owned across a machine
event such as a VBlank inside an activation — is recovery scaffolding, to
be added only for a specific witnessed region/event interaction that the
seam and atomic mechanisms demonstrably cannot own, with the intermediate
state that must survive named, the smallest extension that solves the
case, interruption/resumption/ordering tests, and an explicit retirement
condition.  It is never a second runtime, a project phase or the default
model of recovered functions.  Where composition later shows the real
ordering to be *update phase A → video commit → update phase B*, the port
keeps that ordering directly; guest PCs, resume labels and register
restoration recipes are not game concepts and do not survive into it.

## What is shared and what is per game

Shared (`src/genesis_re`, `scripts/`): the machine and its atomic admission,
the admission contract (`AtomicPlan`, `UnsupportedCandidate`), the seam and
its runner (`Seam`, `run_seam`), histories, the replay runner and its
deadlines, verification, the tracer (`pathfacts`, `factcheck`), the census,
the segment check, the status classifier, the frontier ledger, the callee
census.  Per game (`src/<game>/`): the profile, the semantics, the boundary
planners and their seam plans (where a region resumes, what its frame looks
like, what the suffix means), the dispatcher and its candidate names and
counters, the fixtures and the tests.  A mechanism moves into the shared
layer only after a second game has needed the same one: the seam runner
moved when Gods' sprite emitter reproduced the shape Aladdin's sound
requests had proven.
