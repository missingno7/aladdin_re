# Gods grinder protocol

One recovery iteration on Gods, step by step, with the exact commands.  It
is the loop of `../common/recovery-process.md` instantiated on this game and
is a transcript of the two iterations that recovered the camera follow
step `002806` (a RAM-only leaf) and the sprite emitter `0018C8` (a leaf with
a platform operation inside it, recovered as a seam) — `STATUS.md`,
`ledger.md`.  They are the canonical examples: when in doubt, do what they
did.  Nothing here requires Aladdin's documentation for a leaf of either
shape.  Aladdin is the reference implementation of *execution shapes*
(`../aladdin/recovery-playbook.md` §4): before calling a shape new, check
whether Aladdin has proven it; adapt the shape, never its addresses,
dispatchers or object layouts.

## 0. Environment and rules

PowerShell, from the checkout root:

```powershell
$py = '.\.venv\Scripts\python.exe'
# scripts/run_tests.py and tests/conftest.py set the import paths and the native library;
# for ad-hoc commands: $env:GENESIS_NATIVE_LIBRARY = "$PWD\build\libgenesis_native.dll"
```

- One native `Machine` per process; every tool opens and closes its own.
- Live RAM is the only state; read it through the machine.
- Freeze `src/` while a cold verification runs (`STALE_EVIDENCE` otherwise).
- `history/gods/`, the ROM, retained fixtures and test assertions are never
  edited to obtain a PASS.
- Pin history node ids in commands and artifacts, never `main`: `main`
  moves whenever the user records.
- Gods code lives in `src/gods_sega/` only: `game/<concern>.py` (semantics),
  `boundary.py` (plans), `recovery.py` (the dispatcher and candidate names),
  `profile.py` (the cartridge).  Nothing Gods-specific goes into
  `src/genesis_re/` or `scripts/` outside `scripts/gods/`.

## 1. Where the frontier is

Two sources, both from the recorded histories:

```powershell
# what the last cold run of the current candidate still hands to the original, by gate and reason
& $py scripts\frontier_ledger.py artifacts\gods\<last PASS dir> --boundary src\gods_sega\boundary.py
# which routines a window of real play enters, how often and how long (discovery, ~30 s per 600 frames)
& $py scripts\hot_calls.py --game gods --node <NODE> --from 6000 --to 6600 --top 45 --json artifacts\gods\census\hot-calls-<NODE>-6000-6600.json
```

`STATUS.md` lists the current next bites.  The fallback reasons of the last
PASS are arms the candidate declined; the callee census is where new regions
come from.

## 2. Choose one candidate

Prefer, in this order: many calls in the window; small (tens of instructions)
or medium (a few hundred) with constant or path-determined length
(`min`/`max`/`mean` in the census); a clear entry and RTS (no `unreturned`);
no calls, or calls to routines already recovered; RAM-only.  Screen the
shortlist with the tracer before deciding:

```powershell
& $py scripts\factcheck.py facts artifacts\gods\evidence\main\boundary-6000.state --game gods --park <PC> --path
```

Look at the executed path: absolute addresses and address-register targets
must lie in work RAM (`FF0000`–`FFFFFF`) or ROM (`000000`–`0FFFFF`).  A
device access (`A0xxxx` Z80 window or I/O, `C000xx` VDP, or `(a6)` with
`a6 = C00000`, which is how Gods writes the VDP) is not a deferral by
itself: if the device accesses form **one contiguous block** with a
RAM-only prefix before it and a RAM-only suffix after it (a VDP control
write followed by a data loop, then the register restore and the RTS, as
in `0018C8`), the region is a seam candidate (section 6b).  Defer when the
device accesses are interleaved with RAM work in more than one block, when
the region calls an unrecovered routine that is not itself the platform
operation, when an interrupt handler is entered inside the trace, or when a
loop's count no RAM byte or ROM table bounds.  Write the chosen entry and
the reason as the first line of the session notes.

## 3. Census the entry over the recorded histories

```powershell
& $py scripts\recovery_census.py artifacts\gods\evidence\census-<PC> --game gods --classifier entry --entry <PC> --node <NODE>
```

`--classifier entry` carries no game knowledge (`kind` is Aladdin's
object-table convention).  A dispatcher whose selector arrives in a
register is censused per selector value with `--classifier reg:d5.w`
(the trigger conditions `00470C`: one class per kind in D5, fixtures named
`00470C-d5-0007-p0.state`); the class counts are then the kinds' own.  The report lists the executed path
classes with counts, and retains one entry state per class plus one per
exit CCR (`<PC>-entry-p<N>[-ccr<XX>].state` + `.json`).  Run it on the
longest history; if another recording reaches the routine in situations the
first does not, run it there too into a separate directory.  `cut > 0` means
an occurrence ran past the frame deadline: those states are classified
offline and are fine as fixtures, but note them.  A VBlank that lands
inside an activation does not make a new class: the tracer marks the
handler's steps (`[interrupt handler]` in `facts --path`) and leaves them
out of the path identity; `check` and the tests compare the plan against
the region's own facts (`pathfacts.region_only`).  Such states are never
planned by the candidate (the scheduler refuses a span with an interrupt
due, a `scheduler admission` fallback), so they cost nothing to keep.

A census whose summary line carries `overflow N` (and the WARNING under
it) is incomplete: N occurrences fell into path classes beyond
`--max-classes` and no fixture was retained for them.  Rerun with a larger
cap (`--max-classes 400` is cheap) before any arm is declined as
unwitnessed; on 17 September six arms of `00BA8E` had been declined
because the default cap of 32 had discarded their classes.

## 4. Facts of every path

```powershell
& $py scripts\factcheck.py facts artifacts\gods\evidence\census-<PC>\<PC>-entry-p0.state --game gods --path
```

For each class: entry, exit PC (the caller's return), last PC, instructions,
cycles, stack delta, every RAM byte written, changed registers, exit CCR and
where each flag last changed, the executed instructions with their cycles and
taken branches.  Use `branches --vary ADDR[.w|.l]=v1,v2,...` on the RAM
bytes the path tests to confirm which arms exist and that cost is constant
inside an arm.  Disassemble the whole routine once (`pathfacts.disasm`) to
see the arms no recording entered; name them in the semantics, do not claim
them.

## 5. Semantics

`src/gods_sega/game/<concern>.py`: a pure function of `read_word` /
`read(address, size)` returning the stores, the value left in the result
register, the branch taken and the clamps or guards that fired (so the
boundary can decline what was not witnessed).  Constants named for what the
arithmetic supports.  No cycles, CCR, stack or registers.  Model:
`game/camera.py`.

## 6. Boundary plan

`src/gods_sega/boundary.py`: `<region>_plan(machine, registers)` returning an
`AtomicPlan` — `writes` as `(address, byte)` pairs, `registers` with the data
registers the routine changes (upper halves preserved as the original does),
`a7` after the RTS, `pc` read from the stack, `sr` with the CCR of the last
flag-setting instruction (N/Z/V/C from that instruction, X only from the last
shift/arithmetic that set it), `instructions` and `cycles` per path from the
trace, `last_pc` (the RTS).  Raise `UnsupportedCandidate` for every arm the
recordings did not witness.  Model: `camera_follow_plan`.  A routine that
saves registers (`movem.l ...,-(a7)`) writes its whole frame in the plan
(`_frame_writes`); the tracer only sees the bytes that changed, and
`check_plan` accepts a planned write of a byte RAM already held.

`AtomicPlan`, `UnsupportedCandidate` and `Seam` are the shared admission
contract (`src/genesis_re/seam.py`); the boundary imports them.  The 68000
flag helpers (`_logic_sr`, `_cmp_sr`, `_add_sr`) and the alias guard
(`_spans_disjoint`) are Gods' own copies in `boundary.py`.

## 6a. A dispatcher: one gate, the kinds as arms

A routine that selects a handler through a table indexed by a register
(`00470C`: `move.w d5,d0; add; add; movea.l (pc,d0),a5; jmp (a5)` into
seventeen predicates) is one gate and one planner when every handler is a
small leaf: the semantics take the kind as an argument and return the
handler's outcome (`conditions.evaluate`), the boundary owns the head's
cost and register residue plus a per-kind cost table, and the set of
witnessed `(kind, arm)` pairs (`CONDITION_WITNESSED`) is the admission
domain — a kind, or a compare position inside a kind, that no recording
entered is declined, not guessed.  Kinds whose handler calls an
unrecovered routine are `'unrecovered'` in the semantics and declined in
the boundary until that routine is a leaf.  This is Aladdin's family
dispatch shape (its contact families) with the selector in a register
instead of a record byte.

## 6b. Boundary plan with a platform operation inside: the seam

The shape Aladdin proved for its sound requests and platform tails, on
Gods' inline VDP upload (`sprite_emit_plan`): the planner returns a `Seam`
instead of a plan when the executed arm reaches the device block.

- **prefix**: an `AtomicPlan` of everything before the first device
  access, ending with `pc` at that instruction (`SPRITE_EMIT_UPLOAD`) and
  *every* register the platform operation reads in place (the VDP
  command in `d0`, the descriptor in `a0`, the counters...), `a7` after the
  frame push, `sr` from the last flag-setter before the block, `last_pc`
  the instruction before the block.  Its cost is the prefix's own; the
  machine charges the ceded block itself.
- **the ceded block**: from the first device access to the resume PC —
  the control write, the data loop, and any RAM work between them (the
  tile-cursor advance inside `0018C8`'s block stays with the machine; do
  not chain a second seam to own it — Aladdin's lesson).
- **resume_pc**: the first instruction after the block (`00198C`), gated
  alone while the machine runs.
- **identity**: `stack_basis` (the expected `a7` at the resume) and
  `guards` (the saved frame plus the caller's return slot, read after the
  prefix, unchanged at the resume); `expect` for a slot the operation
  itself rewrites (Aladdin's sound seam checks the last JSR's return
  address that way; Gods' upload pushes nothing).
- **suffix**: `<region>_suffix(machine, registers)` planning the rest from
  the live state at the resume — here the `movem.l (a7)+` restore read from
  RAM, `a7` after the RTS, `pc` from the stack, the machine's own `sr`
  (movem/rts leave the CCR the data loop left).

The dispatcher (`recovery.Candidate._run_seam`) admits the prefix, calls
`genesis_re.seam.run_seam`, and records the outcome: `completed`, a
`refused` or `declined` suffix (the original runs the suffix from the
resume: exact, counted as a fallback at the resume gate), or `deadline`
(the frame's observation instant fell inside the block; the prefix stands
and the original owns the rest).  No checkpoint is taken inside a seam
(`machine.in_seam`).  Foreign returns (another activation at the resume
PC) are bypassed and counted.

What the recordings must witness for a seam: every prefix arm (as for a
leaf), and that the suffix's identity holds on every retained path
(`factcheck check` parks the original at the resume and checks the suffix
plan there).  A device access in the *prefix or suffix* is not a seam:
that is a blocker.

## 7. Dispatcher

`src/gods_sega/recovery.py`: add the entry to `PLANNERS['<candidate>']` (a
new candidate name for a new region, or extend the existing one when the
regions are meant to be verified together), and a mutant to `MUTATIONS`
(`<candidate>-mutant-result`: one stored byte off).  The `Candidate` class
needs no change for a plain leaf.  Choose a mutant that the game can
*see*: a register the caller reloads is dead residue and a register-only
mutant then passes (`conditions-mutant-register` did, over 102 hits); a
stored value that is re-read as a sign or a zero test must be flipped
across that test, not nudged by one.  The right control for a predicate
is its outcome (`_mutate_outcome`: a failing condition reported as
passing).  A mutant that passes the segment tier is not evidence of
anything until it is understood.

## 8. Tests, then the strict witness on every retained path

`tests/games/gods/test_<concern>.py` modelled on `test_camera.py`: the
semantics on synthetic reads (always runs); the plan against the tracer on
every retained fixture (`pathfacts.check_plan` must return no problems;
skipif the census directory is absent); the declined arms decline and the
original runs them; the segment tier (below).

```powershell
& $py scripts\run_tests.py gods -- -k <concern>
foreach ($f in Get-ChildItem artifacts\gods\evidence\census-<PC>*\*-p*.state) { & $py scripts\factcheck.py check $f.FullName gods_sega.boundary:<region>_plan --game gods }
```

Every fixture must print `MATCH`.  `MISMATCH` names the wrong fact: fix the
plan.  `DECLINED` on a claimed arm: the guard is wrong.  Never touch the
fixture.  For a seam, `check` compares the prefix against the trace up to
the platform entry, then parks the original at the resume and compares the
suffix against the trace from there (`MATCH (seam ...)`); both must hold.

## 9. Future continuation

```powershell
& $py scripts\segment_verify.py artifacts\gods\evidence\main\boundary-6000.state --game gods --candidate <candidate> --frames 300
& $py scripts\segment_verify.py artifacts\gods\evidence\main\boundary-12000.state --game gods --candidate <candidate> --frames 300
```

PASS with `candidate hits > 0`; the only fallback reasons a witnessed arm
may leave are the adapter's refusals of an exact span
(`recovery.ADAPTER_REFUSALS`: `observation deadline`, `z80 bank guard`,
`vblank in span`, `machine admission`; the original runs the span, which
is exact).  Since the observation instant moved to the parity wait just
before the vertical interrupt (16 September) these are a fraction of a
per cent of activations, most of them the Z80 bank guard.  The
reference is `artifacts\gods\evidence\main\reference.json`, the reference
worker's observations of the last original-vs-original PASS of that history
(`f0ac19738f19…`); if you retain states from another history, verify it with
`--candidate original` first and keep its `reference.json` beside them.

## 10. Fresh-process verification of one history — the region seal

```powershell
& $py scripts\dev.py history-verify <NODE> --game gods --candidate <candidate> --timeout-seconds 900 --output artifacts\godserify-<candidate>-<NODE>
& $py scriptserify_status.py artifacts\godserify-<candidate>-<NODE>
```

About 7 s per 1,000 frames (`fb408bc7…`, 34,904 frames: ~4 min; `f0ac1973…`,
15,148 frames: ~1.7 min); give 20 s of timeout per 1,000 frames.  Pick the
**shortest leaf that exercises the region** (the census prints the
occurrences per node); a longer leaf adds prefix replay, not evidence, once
every witnessed path class has its fixture MATCH.  Launch the negative
control (step 11) **concurrently** in a second shell — they share nothing.
Read the result only through `verify_status.py`.  `PASS` with hits > 0 is
the qualification; `NOT_EXERCISED` means the region never ran on that
history; `DIVERGENCE` names the first differing frame — inspect it with
`facts` from a retained state near it before changing anything.

## 11. Negative control

```powershell
& $py scripts\dev.py history-verify <NODE> --game gods --candidate <candidate>-mutant-result --timeout-seconds 900 --output artifacts\godserify-<candidate>-mutant
```

Must be `DIVERGENCE` at the first frame that enters the region (or the
segment check must diverge at the first frame after the fixture).  A PASS
here is a `FACTORY_DEFECT` escalation.  A mutant that faults the machine
(an address error, a cartridge write) is a finding about the game, not a
control: choose a mutation the game consumes (a stored position, a record
field the next invocation reads) and record the fault in the ledger.

## 12. Milestone: the tree, the suite, the record

```powershell
& $py scriptsun_tests.py gods
& $py scripts	ree_verify.py --game gods --candidate <candidate> --output artifacts\godserify-<candidate>-leaves-<date>
& $py scriptserify_status.py artifacts\godserify-<candidate>-leaves-<date>
```

`tree_verify.py` verifies every leaf of the tree as its own cold run from
power-on, all leaves at once (five for Gods: ten worker processes; about
4 min, the longest leaf's time, against 13 min for the single-process
`--tree` walk with restores).  It makes the same claim — every recorded
branch, every frame — without a restore anywhere.  Then: one line in
`ledger.md`, the region and the next bites in `STATUS.md`, commit, push.

## The three tiers, and when each runs

Expensive linear-in-history work is a seal, not the inner loop.

**FAST** (while planning an arm or a path class; seconds): `factcheck
check` on the fixtures of the affected classes; the region's own test
module (`run_tests.py gods -- -k <module>`); one `segment_verify` from a
retained fixture of the class (300 frames, ~2 s).  Iterate here until the
plan MATCHes.

**REGION SEAL** (before a region's commit; ~5 min, mostly concurrent):
every retained fixture MATCH (the test module); the full `run_tests.py
gods`; the segment tier from the boundary states; the shortest exercising
leaf's `history-verify` and the mutant, launched together.  Commit locally.

**MILESTONE SEAL** (before a push; ~5 min): `tree_verify.py` on the exact
commit + the full suite.  A milestone is up to **five** sealed regions of
one subsystem, or ninety minutes, or a subsystem boundary moving upward
(a family composed, a parent's declines removed), whichever first; a tree
that fails names the region by its first differing frame, and the last
five commits are small enough to bisect in one run each.  A change to a
shared module (`recovery.py`'s dispatcher, `boundary.py`'s helpers, a
`game/` module several plans read) is a milestone by itself.

What no tier skips: the strict witness on every retained fixture (the
32-bit register file, the CCR, every write, the cost) before a region is
called recovered; a fresh-process cold run with hits before its commit; a
mutant the game can see; the tree with current receipts before a push.

## Candidate selection rules

Take first: frequently executed, small or medium, clear entry/return,
RAM-only, no device access, few arms, every arm recorded, deterministic cost
per arm.

A **caller-supplied record is not a reason to defer.**  A routine that
reads its inputs through a pointer register (a definition in `A2`, an
output cursor in `A5`, a position in `D0`/`D1`) is a leaf like any other:
the semantics take the pointer as an argument (`grid.stamp_footprint(read,
x, y, definition, cursor)`), the boundary reads the registers, the alias
guard covers the record and every span the plan writes.  A loop whose
count is a byte of that record is admissible: the cost is a formula in
the count, verified on every count the recordings witnessed (the
footprint stamp `00FDB8`: rows × cells, four combinations), and a count
outside the verified domain is declined.  What genuinely needs the
object-record convention is a *dispatch* through a type byte into
handlers that are not recovered (a `jsr (a4)` from a table indexed by a
record field) — that is a composition question, not a leaf's.

Take next: a region whose only device work is one contiguous block with a
RAM-only prefix and suffix (a seam, section 6b), including a region that
*calls* one such routine once (Aladdin's "one native call inside the
branch": the prefix ends at the JSR with the frame pushed, the resume is
the return site) or a run of them (Aladdin's platform tail: end the prefix
at the first platform entry, resume at the region's own RTS).

Defer (a deferral is a result, write it in the session notes): device
accesses interleaved with RAM work in several blocks, Z80 window or I/O
access in the region's own prefix or suffix (`A0xxxx`, `A1xxxx`), the VBlank
handler and anything reached from it, loops without a RAM- or ROM-named
bound, command or script interpreters, routines whose arms are mostly
unwitnessed.

## Escalation

Stop work on the candidate, write the blocker package, continue with another
admissible candidate.  Do not spend more than three attempts on one fact.

| code | condition |
|---|---|
| `NEW_SHARED_MECHANISM` | the region needs an execution shape **no game in the repository has proven**: check `../aladdin/recovery-playbook.md` §4 and section 6b here first.  A shape Aladdin proved and Gods has not implemented yet is not this code: reproduce it, verify it through the full ladder, and only then write up what (if anything) turned out to be a genuinely different contract.  What remains this code: writes that must be recovered *between* two platform blocks, an interrupt handler inside the region, a device register in the prefix or suffix itself |
| `NEW_GODS_SUBSYSTEM` | the region is an interpreter, a dispatcher family or a data structure that needs its own semantic module and naming before any leaf can be planned |
| `INSUFFICIENT_EVIDENCE` | the recordings reach fewer arms than the routine has and the unwitnessed arms dominate; ask for a recording that reaches them |
| `ORACLE_OR_TOOL_DISAGREEMENT` | `check` says MATCH but a segment or the cold run diverges, or a tool crashes |
| `VERIFICATION_DIVERGENCE` | a cold run diverges and the first differing frame cannot be attributed to the new region within three attempts |
| `UNSUPPORTED_PLATFORM_SEAM` | the region's only path forward is a device access or a Z80 transfer |

Blocker package: `docs/gods/blockers/<date>-<PC>.md` with Where (entry PC,
caller, census directory), Code, Observed (the fact report, the branch table),
Why the current mechanism does not fit (one paragraph), Fixtures used (paths
and SHA-256), What was tried (one line each), Next question (one sentence a
stronger model can answer).  Commit it alone: `Escalate <PC>: <code>`.

## Reporting

## Review gate

Gods has no `leaf_review` yet.  Until enough leaves exist to define one,
the review is: every retained fixture `MATCH` (a seam: prefix and suffix),
the segment tier from both retained boundary states, the mutant
divergence, and a diff read for removed guards or assertions — a guard
removed without a fact that justifies it is a failure even when every test
passes.  For a region whose census retained VBlank-pre-empted occurrences
(the tracer set the handler aside), also run the strict-original slide
check on one such fixture:

```powershell
& $py scripts\gods\vblank_slide.py artifacts\gods\evidence\census-<PC>\<PC>-entry-p0.state --ticks 20
```

Every landing must be `EQUIVALENT` (the exit state and twenty tick starts
equal with the interrupt slid inside the region); a `DIFFERS` names a live
byte the handler and the region share and is a finding to write up, not a
region to admit.  A fixture from a level intro or a transition reports
that the tick loop stopped; use a gameplay fixture.

## Reporting

Three lines per session or milestone in `artifacts/gods/grinder/session.log`:
regions recovered (entry, arms, hits, fallbacks), escalations (entry, code),
next candidate.  Every command run goes to
`artifacts/gods/grinder/commands.log`.  Nothing else is a status report.
