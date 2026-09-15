# How Aladdin converged

Reconstructed from the git history (164 commits, 12 to 16 September 2026),
the surviving mechanisms in `src/`, `scripts/` and `tests/`, and the retained
reports under `../archive/`.  This is not the chronological log (that is
`../archive/aladdin/status-log-2026-09-12-to-16.md`); it is the answer to one
question:

> If we started another Genesis game knowing everything Aladdin taught us,
> what would we do from the beginning — and what would we not do again?

The short answer is the loop in `../common/recovery-process.md`.  The stages
below say where each piece of it came from, what it replaced, and what the
evidence was.  Dates are given so the archive can be consulted; nothing here
needs the archive to be understood.

## The stages

### 1. A machine that is an oracle (12–13 September)

The first commit (`b3c78ac`) already had the shape that survived: the pinned
PortForge Genesis machine behind a small C ABI (`native/machine.cpp`), driven
from Python one batch at a time, never calling back into Python inside a
step, exporting explicit state.  The choices that mattered and still hold:

- **One state authority.**  The native machine owns every mutable byte; Python
  reads live RAM through it and holds no game state between operations.  Every
  later attempt to keep state on the Python side (a continuation record, a
  cached RAM image) was the source of a bug or a dead end.
- **Donor, not rewrite.**  The 68000, Z80, VDP and the engine are borrowed
  and locked byte-for-byte (`scripts/check_sources.py`; a changed locked file
  refuses to build).  The three platform fixes the Gods boot path needed
  (S-CTRL writes, Z80-window writes into the cartridge, the window plane's
  row stride) were made in PortForge and re-pinned (`695bc65`); the machine
  was never forked per game.
- **Explicit contracts at the boundary.**  Gates (stop at a PC before
  executing it), `atomic` (apply a plan as one operation or refuse with the
  machine untouched), snapshots with an identity header, PCM draining.  These
  four calls are the whole recovery surface; nothing else was ever needed.

What belongs to the platform: timing, devices, interrupt delivery, the
snapshot codec, cartridge identity.  What belongs to the game: everything a
plan reads or writes.  `docs/common/machine-ownership.md` is the policy.

### 2. Inputs are the evidence, snapshots are caches (13 September, `b6ba9c1`)

The first replay model recorded machine snapshots (`.alsnap`) and replays
keyed to them (`.alreplay`), with per-region witness scripts that restored a
parked entry, ran the candidate and compared.  It worked for the first three
regions and then stopped scaling: every witness copied the same ninety lines,
every fixture carried an opaque state whose provenance was a filename, and a
"replay" was only as portable as the binary that wrote it.

The replacement is the immutable cold-start input history (`history.py`): a
node is the root record, the ordered input stream and the end frame; nothing
else enters its identity.  Checkpoints are navigation points; caches are
disposable accelerators keyed by ROM, native binary, profile, state contract
and (for candidates) source; a fresh process reconstructs any node from
power-on.  Verification became "two fresh workers, every canonical frame,
state + video + PCM + counters" (`verification.py`), and `--tree` verifies
every branch with prefix states computed in that run only.

Lesson: the durable artifact is the player's input.  Every later tool
(census, segments, the native runtime's replay clock, the Gods bring-up)
consumed histories and produced disposable state from them.

### 3. Bounded replacement: the plan as the unit (13 September)

Recovery began with the smallest thing that could be proven: a 15-instruction
leaf (`1AE372`, the object clear).  The mechanism that survived from that
first region to the last is the **AtomicPlan**: computed from live RAM at a
gate, admitted by the machine as one operation charged with the original's
instruction and cycle cost, refused whole when it cannot fit before the
deadline.  Everything the original leaves behind — every RAM byte, the data
and address registers, the stack pointer, the return PC, the CCR including X
— is part of the plan, and a plan that gets one of them wrong diverges within
frames.

Two alternatives were built and measured before this settled:

- The **connected carrier** (0.6, `fc66041`): let recovered Python continue
  *across* an original sound call by snapshotting inside the callee and
  resuming a Python continuation.  It worked, including in a fresh process,
  and was judged NOT CONVERGING: 58 lines of recovered source cost 167 lines
  of dispatch and a second state authority (`../archive/aladdin/carrier-convergence.md`).
- The **synchronous seam** (0.7, `a72ed9e`): end the plan with the callee's
  frame pushed and the PC at the callee, let the machine run the original
  callee to a measured resume PC (identified by A7, the saved frame and the
  return slot), then plan the suffix from live state.  No continuation state,
  the same full replay passing, less code (`../archive/aladdin/synchronous-seam.md`).
  This is the seam every later native island used.

### 4. Semantics apart from the machine contract (13 September, 0.8, `6cb9277`)

The ownership experiment (`../archive/project/ownership-boundary.md`) asked
where exact machine semantics belong and answered: not in the game code.
`recovered.py` (later `game/`) holds pure functions over a reader that return
staged writes and decisions; `boundary.py` turns them into exact outer
effects (stack residue, register file, CCR via `_logic_sr`/`_cmp_sr`/
`_sub_sr`/`_add_sr`, per-path cost tables); `recovery.py` holds gates,
admission, fallback and mutation policy.  `scripts/check_architecture.py`
enforces that game semantics import no machine, boundary or policy module.

This split is the single most reusable decision in the repository.  It is
why the Gods camera step is thirty readable lines plus a planner, and why the
Aladdin native runtime could later reuse the same `game/` modules without the
oracle.

### 5. Composition through the game's own dispatchers (13–14 September)

Leaves were composed upward through the dispatchers that call them — the
collection dispatcher, the contact tick and its scan, the spawn walker — so
that one gate owns a whole callback family and the plan for a parent joins
its children's plans at planning time (a planning view overlays staged writes
so a later planner sees them).  Where a child needed a platform call, the
parent's batch was truncated at the seam rather than declined whole
(`202dac9`, fallbacks 686 → 379).  Where an activation ran several platform
calls, the prefix ended at the first and the original ran to the activation's
own RTS (the *platform-tail bridge*, `fc91e46`) — no chained seam was ever
built, and the audit that proposed one found it unnecessary.

### 6. Facts, not guesses (14 September, `207ed2f`)

The factory review (`../archive/project/recovery-factory-review-2026-09-14.md`)
measured where cheap workers failed: hand-counted cycles, a mis-read flag, an
unnoticed write (the Type-55 182/16 accounting bug).  The answer was the
tracer: `scripts/pathfacts.py` single-steps the original from a retained
state and reports every fact a plan needs; `scripts/factcheck.py check`
compares a planner's output with those facts and names the first wrong one.
With it, four cheap-model runs recovered frontier leaves with zero
interventions.  Since then no number in a boundary file is typed from the ROM.

### 7. The census: retained real states per executed path (14 September, `8b65e82`, `c06c2d4`)

The long recording is a database of situations, not the unit of daily work
(`../archive/project/replay-evidence-at-scale-2026-09-14.md`).  One replay
pass with gates at the frontier entries single-steps every occurrence,
groups them by path signature, retains one entry state per class (plus one
per exit CCR, plus the parent state that led there) and writes the evidence
index the ledger reads.  Recovery then runs in constant time on those states:
`factcheck` in milliseconds, `segment_verify` in seconds against the
reference observations of the last PASS.  Only the publication proof — the
every-frame cold comparison — stays linear in history length, and it runs
in parallel workers.

### 8. Where to observe the machine (14 September, `d089038`)

Scheduler refusals were the largest fallback class until the execution-model
study (`../archive/project/execution-model-research-2026-09-14.md`) found why:
the replay observed the machine and deadlined plans at the frame wrap, inside
the game's busy window, so a plan straddling the wrap was refused.  Moving
the observation and the admission deadline to the game's idle instant (raster
line 131, half a frame later) while leaving the input instant at the wrap
removed 574 of 574 refusals in 3,000 frames and changed no recorded
trajectory by one instruction.  The instant is a profile field
(`observation_offset_ticks`), measured per game.  The study also rejected,
with measurements, resumable coroutines, a mixed-mode script runtime, an
`AtomicPlan` of a whole frame and a generic IR.

### 9. The grinder (14–15 September)

With facts, census, segments, a status classifier (`verify_status.py`), a
frontier ledger and a review gate (`scripts/aladdin/leaf_review.py`), the loop
was written down as a protocol and a goal prompt and run by cheaper models
under supervision: seven stints took fallbacks from 21,840 to 379 with
milestone cold PASSes every three leaves, escalating with blocker packages
(`blockers/`) when a row needed a mechanism.  The supervisor then bridged
the platform tails (379 → 152) and closed the bounded frontier (152 → 137).
The residue on the 82,161-frame recording is the scheduler in about thirty
frames and the command-stream engine — not leaves.

### 10. From islands to a runtime (15 September)

Bottom-up recovery had converged; the remaining original code was the game
loop itself.  The semantic map (`semantic-map.md`, from one replay with RAM
activity sampling) named the main loop's steps and RAM, and the native
runtime phase (`c0d165b` to `3d49fba`) recovered the main loop as game code:
`native/frame.py` runs the loop's 36 steps over the same RAM layout, backed by
`game/` modules, a VDP model (`native/vdp.py`) and a renderer; transitions
(respawn, continue, level change, story pages, title, options, pause) as
nested-frame sequences; power-on as recovered initialisation; the ROM's Z80
sound driver as a platform service on a dedicated machine.  Nothing on the
native path executes original 68000 code; what is not recovered raises
`NativeGap` with the ROM address.

Its verification is a different ladder from the candidate's: per-step
byte-exact at entry and exit, VDP steps word-exact against the oracle's port
writes, and whole-frame RAM comparison every frame (`native_diff.py`) —
which found defects the per-step check could not (state carried across
frames).  The independent audit of 15 September
(`../archive/project/astra6-independent-audit-2026-09-15.md`) named the risk
of an oracle-assisted, RAM-only success criterion; the response was the
*independent contract*: recordings are inputs only, no per-recording tables
(a transition-timing table keyed by absolute frames was found and removed),
the replay clock asks the oracle online only for the VBlank count at a
checkpoint, and `native_diff --independent` runs with no oracle feedback,
comparing sound-driver calls and work markers.  Milestone: the whole
82,161-frame recording runs natively from its first main-loop frame to the
end byte- and sound-exact (aligned); cold start from power-on runs on the
four recordings; independent mode holds to frame 26,798.

### 11. Two games (15 September, `de17384`)

The shared layer was split out (`src/genesis_re`), games became explicit
profiles in a registry, histories and tests became per-game, and Gods went
through stages 1, 2, 3, 4, 6, 7 and the verification ladder with no change to
the machine, the histories, the runner, the verifier or the tracer
(`../gods/STATUS.md`).  Stage 5 (dispatcher composition), stage 8 (the
observation instant) and stage 10 (a native runtime) are Aladdin's so far.

## What we would do from the beginning

1. Pin the machine; prove the original reproducible from cold on real
   recordings before recovering anything (stages 1–2).
2. Record real play early and often; every tool consumes histories.
3. Start with a leaf: RAM-only, bounded, hot, every path recorded (stage 3,
   7).  The Gods camera step took one afternoon this way.
4. Separate semantics from boundary from policy from day one (stage 4).
5. Never type a machine number: census, trace, check (stages 6–7).
6. Measure the observation instant per game before blaming the scheduler
   (stage 8).
7. Compose upward through the game's dispatchers; seam platform calls, bridge
   platform tails, never chain seams (stage 5).
8. Grind with a protocol, a ledger and blocker packages; escalate mechanisms
   to a stronger model (stage 9).
9. When leaves are exhausted, map the loop and recover it as a runtime with
   a whole-frame comparison and an independent contract (stage 10).

## Approaches we no longer use

**Snapshot-keyed replays (`.alsnap`/`.alreplay`, 12–13 September).**  Natural
first step: save state, replay from it.  Insufficient because a state is
opaque and binary-bound, so provenance and portability were lost and every
witness carried its own copy of the machinery.  Replaced by immutable input
histories with disposable caches (stage 2).

**Per-region witness scripts.**  Each recovered region got a script that
parked, ran, compared and mutated.  Reasonable for three regions; by the
fourth they were copies (`../archive/aladdin/recovery-workflow-pre-history-2026-09-13.md`).
Replaced by the census, `factcheck` and `segment_verify`, which work on any
retained state of any entry.

**The connected carrier with Python continuation (0.6).**  Letting recovered
code span an original call by keeping a continuation looked like the road to
larger regions.  Measured NOT CONVERGING: more scaffolding than source, a
second state authority.  Replaced by the synchronous seam (stage 3).

**Hand-derived costs and flags.**  Counting cycles and reading CCR effects
from the listing looked cheap.  It produced the Type-55 accounting bug and
the failures that stopped cheap workers.  Replaced by the tracer (stage 6).

**Observation at the frame wrap.**  The natural place to observe a frame is
its boundary; it is inside the game's busy window, and plans that straddled
it were refused by the hundreds.  Replaced by the measured idle instant with
the input instant unchanged (stage 8).

**A chained seam.**  Proposed for activations with several platform calls.
The audit of every remaining fallback showed each native island is a thin
platform call, so the prefix ends at the first and the original runs to the
activation's RTS.  Never built (stage 5).

**Transition timing keyed by absolute recording frames.**  The native
runtime's first transitions looked up their timing by the frame they started
at; it made a recording part of the game.  Found by the independent audit,
removed; the replay clock asks the oracle online and stores nothing per
recording (stage 10).

**Rejected without building (measured or reasoned in the execution-model
study):** resumable Python coroutines, a mixed-mode script runtime, an
`AtomicPlan` covering a whole frame, a generic IR or mechanically translated
fallback, a generated skeleton emitter carrying fixture constants into code, a
native (C++) tracer, a plugin/registry framework for games.  Each would have
added a second state authority, machine-shaped source, or machinery no
measured problem needed.

## Where the detail is

- The chronological log with every milestone's numbers:
  `../archive/aladdin/status-log-2026-09-12-to-16.md`; per-milestone cost
  notes: `../archive/aladdin/recovery-cost-log.md`.
- The per-region reports of the first week: `../archive/aladdin/` (carrier,
  seam, semantic migration, contact and spawn families).
- The studies that decided the shared model: `../archive/project/`
  (implementation spec, architecture review, ownership boundary, execution
  model, replay evidence at scale, factory review, independent audit).
- What runs today: `STATUS.md`; how to recover more of Aladdin:
  `recovery-playbook.md`; the native runtime's gaps: `native-frontier.md`.
