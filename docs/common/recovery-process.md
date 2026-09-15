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
a bounded loop count, and every path class covered by recordings.  Regions
that touch the VDP, the Z80 window, the controller ports, interrupts,
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
- A **blocker** is a candidate the current mechanisms cannot express: a
  device access in the region's own code, a platform call the game has no
  seam for, an interrupt inside the region, an unbounded loop, a data
  structure nobody has named.  The right result is a blocker package
  (where, code, observed facts, fixtures, what was tried, the one question
  a stronger model can answer) and the next candidate.  Grinders do not
  build mechanisms.

## What is shared and what is per game

Shared (`src/genesis_re`, `scripts/`): the machine and its atomic admission,
histories, the replay runner and its deadlines, verification, the tracer
(`pathfacts`, `factcheck`), the census, the segment check, the status
classifier, the frontier ledger, the callee census.  Per game
(`src/<game>/`): the profile, the semantics, the boundary planners, the
dispatcher and its candidate names, the seams it has (Aladdin has a sound
seam and a platform-tail bridge; Gods has none yet), the fixtures and the
tests.  A mechanism moves into the shared layer only after a second game has
needed the same one.
