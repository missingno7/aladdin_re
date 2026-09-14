# Replay evidence at scale

A study of how replay-derived evidence and targeted verification should work
now that `main` covers 82,161 frames (about half of the game), and what should
change before the history grows further.  Every number below was measured on
the current checkout (`207ed2f`) and the current `main`
(`44223150b7d6`, 17 nodes, 82,161 frames) on 14 September 2026.  The
experiment scripts and their compact results are in
`artifacts/replay-evidence-study/` (regenerable; nothing here changes the
production source).

## The model in one paragraph

The long replay is a database of real execution situations and the one
end-to-end proof; it is not the unit of day-to-day work.  Discovery (finding
every situation an entry reaches and retaining one real state per distinct
behavior) costs one pass over the replay, paid once per history extension for
all entries together.  Routine recovery work then runs on those retained
states in constant time: a branch first seen at frame 51,251 is qualified from
its 162 KB state in milliseconds, and its enclosing parent or a 300-frame
segment around it is verified in seconds, frame-exact against the canonical
run.  Only publication evidence (the every-frame cold comparison from
power-on) must stay linear in replay length, and it is already parallel.  The
current implementation supports this model for children and, since this
week, for parents; what it lacks is an equivalence class better than the
record kind byte, an index that names the retained evidence, a segment check
that reuses the reference observations, and original-machine caches that
survive a source edit.

## 1. What the current implementation already does well

- **Faithful mid-trajectory states.**  A census state captured at a gate on
  frame 51,251 restores in 1 ms, and an original run advanced from it matches
  the canonical cold run's state and video hash on every one of the next 300
  frames.  The snapshot is the complete machine (162,172 bytes); nothing
  about the trajectory needs power-on replay once the state exists.
- **Bounded qualification from a state.**  `execute_region`,
  `qualify_atomic_plan` and `fresh_process_future` already run one entry to
  its outer boundary, 150 original instructions further, and again in a fresh
  process.  The retained parent state (contact tick `1ABB40`) replays the
  whole tick through the production candidate in 0.04 s and names the child
  it declines.  Child fixtures and parent fixtures are both first-class
  inputs to the same runner.
- **Cheap discovery per pass.**  One original replay with gates on 18
  entries and two parents, single-stepping every occurrence to its return
  (380,000 stepped instructions, 9,111 entry snapshots, 53,000 parent
  snapshots) took 302.5 s against 269 s for the plain census: the signature
  work adds 12 percent.  The probe left the terminal state identical to the
  reference run, so replay-time analysis does not perturb the trajectory.
- **The publication proof is strong and its cost is bounded.**  The
  every-frame strict comparison with fresh parallel workers takes 403 s for
  82,161 frames (4.9 ms per frame), zero restores, current receipts.
- **Constructed fixtures already cover values the replay never reaches.**
  The Type-55 accounting error (180/15 versus 182/16) sat in an arm the
  recording never exercised; the branch matrix in `family_fixture` found it
  while the full replay passed.  Values are the constructed layer's job; the
  replay's job is situations.

## 2. What breaks or becomes inefficient as the replay grows

| Symptom | Evidence | Why it matters at 300,000 frames |
|---|---|---|
| Discovery is a full replay every time | census 269 s, signature census 302 s for 82K frames; 3.3 ms per frame | ~17 min per pass; tolerable only if one pass serves every entry and the results are kept |
| Original-machine caches die on every source edit | the cache key hashes Python modules even for `candidate=original`; the four cache sets on disk all belong to old implementations and none is valid now | "replay to frame F" has no shortcut, so every fixture regeneration is a power-on replay |
| The equivalence class is the record kind byte | 9,111 occurrences in 33 (entry, kind) classes hide 195 distinct execution paths; `1AFA84` kind 74 alone has 23 paths behind one class | the first-three rule retained 55 of 195 paths (28 percent); the rest were discarded as duplicates |
| Retention is by occurrence order | for the ten largest classes the first three occurrences covered 1 to 3 paths each | the dominant path is over-represented, the rare arms are what recovery needs |
| Evidence has no index | fixtures are ignored files named by class and index; two tests skip when a directory is absent; the ledger cannot see which classes have fixtures or which are recovered | the grinder cannot choose a bite without re-reading directories, and a stronger model cannot tell recorded evidence from constructed |
| Reference observations are written and forgotten | `reference.json` is 35.7 MB per run (435 bytes per frame) and is the exact oracle for any segment, but no command reads it | every segment check re-runs the original for the same frames |
| Scheduler refusals are unattributed | 15,691 on `main`; in a 300-frame segment all 22 were at gate `1ABB40`, refused with 500 to 18,000 master ticks of slack | a plan larger than the remaining frame slack is a mechanism question, not a grinder task; the ledger should say so |
| Observation JSON grows linearly | 35.7 MB per worker per run | fine at 300K frames (130 MB) if it is written once per publication and read, not regenerated, for segments |

## 3. Which parts of verification should depend on replay length

| Tier | What it proves | Cost now (82K frames) | Scales with |
|---|---|---|---|
| Discovery | which situations an entry reaches, one real state per distinct behavior, the parent that led there | 302 s per pass, all entries at once | replay length, once per history extension |
| Routine edit and test | the plan reproduces the original's exact effects on a retained state, 150 instructions further, and in a fresh process; the branch matrix covers values | 0.06 s per trace, 0.5 to 2 s per qualified case, 30 s for the focused suites | the number of retained classes, not frames |
| Subsystem integration | the parent owns the child; a segment of real gameplay around the situation is frame-exact | parent replay 0.04 s; 300-frame segment 3 s (1.5 s original, 1.6 s candidate) | segment length (seconds), not replay length |
| Publication | the whole trajectory from power-on matches on every frame under the current implementation | 403 s parallel | replay length, linear, once per milestone |

The replay should matter twice: when it is extended (one discovery pass) and
when a milestone is published (one cold comparison).  Everything between is a
function of the retained evidence, which grows with distinct behaviors, not
with frames.

## 4. Which parts become constant-time after discovery

After one pass, every relevant situation exists as a 162 KB state with its
frame, entry, kind, path class and parent.  From there:

- a plan check against the original is 60 ms (`factcheck.py check`);
- an outer/future/fresh qualification is one to two seconds;
- a parent replay is 40 ms;
- a segment check of N frames is about 5 ms per frame per side, and the
  original side can be replaced by the stored reference observations
  (state, video, PCM chain seed at the segment start), halving it;
- a fresh-process restore is 80 ms.

None of these reads the history.  The 300-frame segment from frame 51,251
took 3 s and contained 425 occurrences of the very entry under study, so a
segment is also a dense, real stress test of the plan under real deadlines:
the 22 scheduler refusals in that segment are the same phenomenon the full run
reports 15,691 times.

## 5. How repeated occurrences should be grouped

**What defines equivalence today.**  The census groups by (entry PC, record
kind byte at A1).  Tests group constructed fixtures by hand-named branches
(`be`, `c0`, `flags`, `previous`).  Nothing groups by what the original
actually executed.

**What separates occurrences in practice.**  The signature census reduced
each occurrence to (entry, exit PC, hash of the executed PCs outside native
sound calls, call targets at depth zero, set of changed registers), plus
facets that were tested and kept out of the identity:

| Candidate dimension | Effect on the 9,111 occurrences | Verdict |
|---|---|---|
| executed path (PCs, native segments collapsed) | 195 classes; every arm, every loop trip count, every early exit is a distinct path | the identity |
| call targets at depth zero and native-call shape | consistent within a path; distinguish the `(1E58B8, 1E589A)` seam arms from RAM-only arms of the same entry | part of the identity (implied by the path, useful as a label) |
| changed-register set | consistent within a path | part of the identity |
| cycles and instructions | implied by the path | cost table, not identity |
| exit CCR | varies inside 23 of 195 paths (value-dependent flags) | a facet: keep one extra fixture per distinct exit CCR (31 fixtures in total) |
| entry X flag | never varied inside a path | facet only |
| write shape from RAM diffs | 415 raw signatures, mostly noise: a store of a value already present is invisible to a diff, and the sound routine's ring buffer moves | exclude stack and native-segment writes; keep record-relative and global writes as a label, not identity |
| register or input values | not tested as identity | belong to constructed branch matrices |
| parent context | 364 of 415 signatures fired in the same frame as the retained contact tick, the rest one frame later (the tick straddled a frame boundary) | a property of the class, recorded once |

**Answer.**  Two occurrences are equivalent for recovery when the original
executes the same instruction path outside native calls with the same
depth-zero call targets (which carry the native-call shape).  Implementing
this showed two more dimensions to keep out of the identity: the exit PC is
the caller's return site (a five-instruction boot leaf called from five
sites is one behavior), and the changed-register set is value-blind like a
RAM diff (a register rewritten with its old value is not "changed"); both
stay as facets.  Within such a class
the plan's arithmetic is exact by construction and the checker proves it on
any member; the only value-dependent residue is the CCR, which is worth one
fixture per distinct exit CCR.  Could two occurrences fall into one (entry,
kind) bucket today while behaving differently?  Yes, everywhere: kind 74 of
`1AFA84` holds 23 paths, kind 73 of `1AFB36` ten, kind 1E of `1AE796` thirty.
Are we retaining fixtures that add nothing?  Also yes: for `1AF5F0` the first
three of 3,337 occurrences are three members of the dominant path.

## 6. How rare cases should be retained

Uniform sampling would lose them; order-based retention already does.  The
facts:

- Of 195 path classes, 77 occur exactly once in 82,161 frames; 31 of those
  first appear after frame 50,000.
- New path classes keep arriving at a steady rate: 33, 9, 38, 31, 11, 18, 19
  and 36 per 10,000-frame bucket.  There is no saturation at half the game.
- Whole entries appear late: `1AF5F0` (the largest unrecovered callback,
  3,337 hits) is never executed before frame 51,251; `1AFA84`, `1AE9A8`,
  `1AEB7A` and `1AF81C` first fire after frame 69,000.  Level structure, not
  time, decides coverage.
- Inside one entry the rare arm is where the recovery risk is: `1AE9E0`
  kind 1A has 159 occurrences of one path and one of another.

**Rule.**  Retain the first occurrence of every path class, plus one per
distinct exit CCR inside a path, plus the parent state that led to each.  That
is 195 plus 31 child states (36 MB) and the same number of parent states for
the whole current frontier, against 14 MB retained today that cover 28
percent of the classes.  Counts are recorded per class so frequency is
visible without keeping members.  Boundary values (distance exactly six,
counter exactly `0x39`) are not a replay retention problem: the constructed
matrix already targets them, and the path class tells the grinder which arms
exist so it knows which boundaries to construct.

## 7. Is a mechanical behavior signature useful?

Yes, and the existing tooling already computes everything it needs.  The
signature is the tracer's fact report reduced to identity: exit PC, the path
hash over python segments, depth-zero calls, native-call shape, changed
registers.  It costs 22 ms per fixture offline and 12 percent extra during a
replay online.  It is bounded (one line per occurrence, one row per class),
regenerable, and needs no new native code.

What it must not include, learned from the raw census: RAM-diff write sets
(value-blind and polluted by the sound ring), stack-slot writes (mechanical,
implied by the path), cycle counts (implied by the path), and anything from
inside a native segment.  What it cannot do: distinguish values on one path
(the constructed matrix does) or say whether a path is recoverable (the
recipe classification does, from the native shape and the instruction count
the signature carries).

A raw path hash is opaque to a reader; the class should carry the human
facts next to it: instruction and cycle counts, native shape, the record
fields and globals written, the first frame, the count.  That is what the
grinder reads.

## 8. How child and parent fixtures should interact

The distinction is real and general.  Every child class in the census fired
inside a contact tick (`1ABB40`), the tick preceding the child by at most one
frame; the retained tick state replays the entire scan through the
production candidate and reports either ownership (`contact_scan_hits`,
zero dispatcher hits) or the exact reason the scan declined the child.  This
is how the Type-20 omission and the Type-55 scan-map gap were found, and it
runs in 40 ms.  A child fixture proves the leaf; a parent fixture proves the
composition; a segment proves the leaf under real deadlines and the frames
around it.  All three come from the same census pass and the same state
format.

Two refinements are worth making when the census is productionized: record
the parent's activation identity (its A7 and return slot) so the pairing is
proven rather than inferred from frame numbers, and record the parent gate
for children reached by other parents (spawn dispatcher children through
`1AE46C`, collection dispatch outside the tick) so the same tier applies to
the spawn frontier, where 40 unrecovered targets sit.

## 9. What the grinder should see when choosing the next frontier

One record per (entry, kind, path class), regenerated by the discovery pass
and joined to the last cold comparison:

```text
entry, kind, path class id        1AF5F0 58 p3
count, first frame, last frame    2697  51260  81990
instructions, cycles, exit        17  206  1AE6BA
native shape                      none            (or 1E58B8,1E589A)
writes                            FFF0F5          (record fields, globals)
status                            unrecovered target | arm declined <reason> | owned by <parent> | recovered
fallbacks in the last cold run    6668
child fixture, parent fixture     sha256 and local path (regenerable)
parent gate                       1ABB40, same activation
evidence quality                  recorded (this history) | constructed only
```

That is enough to choose: the highest fallback count whose native shape and
instruction count fit a recipe, with a fixture and a parent to test against,
skipping classes flagged as mechanism escalations.  It needs neither the
replay nor the repository.  The frontier ledger already produces the status
and count columns from `comparison.json`; the class and fixture columns come
from the census once it retains by path.

## 10. What should remain full cold-history verification

The cold comparison proves something no fixture can: the whole trajectory
from power-on under the current implementation, including every deadline,
every composition and every gate interaction.  The repository's history shows
what each layer catches:

| Found by | Case | Lesson |
|---|---|---|
| full cold run only | five Type-20 scan fallbacks: adapters existed, parent maps omitted them | integration omissions are invisible to child fixtures; now visible to parent fixtures in 40 ms |
| full cold run only | the 63-gate native limit hit by a new direct gate (the Type-03 full-suite failure) | a limit of the full gate set; now a fast-tier assertion |
| full cold run only | scheduler refusals under real frame deadlines | real deadlines exist only in replay; a segment from a real state reproduces them |
| bounded witness while the full run passed | a control omitting final stack residue: ten bytes differ after 150 instructions, yet later full-replay observations pass (reconvergence) | full replay is not permission to weaken the outer contract |
| branch matrix while the full run passed | Type-55 non-borrow return charged the borrow cost | the recording exercised one arm; values and arms need constructed evidence |
| shared full-state qualifier | a wrong `last_pc` that leaves info, registers, RAM, frame and PCM identical and changes only serialized state | serialized state must stay in every strict comparison, at every tier |

Neither layer subsumes the other.  The cadence that follows:

- **Per leaf:** child fixture qualification, parent replay, and a segment
  check of a few hundred frames around a recorded occurrence, using the
  stored reference observations as the oracle.  Seconds; independent of
  replay length.
- **Per milestone commit (one to three leaves):** full suite and the full
  cold comparison with parallel workers.  Seven minutes now, about 25 at
  300,000 frames; still one coffee, not one day.
- **Per history extension:** one discovery pass with signature retention,
  which refreshes the evidence index; the cold comparison of the new tail is
  implied by the next milestone run.
- **Optional history-segment tier:** when a leaf touches a subsystem that
  first appears in one node (the index says which frames), replay that node's
  segment from its retained state instead of the whole path.  About a minute
  per node.  Useful; not a substitute for the milestone run.
- **Tree mode:** only when off-main branches carry situations `main` does
  not; today there is one off-main node.

## 11. What is worth implementing now

Landed the same afternoon: the first five rows below are in the checkout
(census path-class retention with `index.json`, `segment_verify.py`,
original cache keys without source, `fallbacks_by_gate`, ledger index
support), with tests; see the STATUS section of the same date.

Hypotheses, ranked by evidence and size.  None adds a trace system; the
largest artifact any of them writes is the existing 162 KB state.

| Change | Evidence | Verdict |
|---|---|---|
| Retain census fixtures by path class (plus one per exit CCR), record counts per class, exclude stack and native writes from the identity | 195 classes behind 33 buckets; 28 percent covered today; 12 percent replay overhead; 22 ms offline per fixture | DO NOW |
| Write an evidence index (section 9) from the census and have the frontier ledger read it | the grinder's selection needs class, fixture, parent and status in one place | DO NOW, with the census change |
| A segment check command: restore a retained state, advance N frames, compare with the stored reference observations | 3 s per 300 frames, frame-exact; reproduces deadline behavior | DO NOW; it is the missing tier between parent replay and the cold run |
| Key original-machine caches by ROM, native binary, profile and state version, not Python source | no valid cache exists for the current source; the original's trajectory does not depend on Python | DO NOW, small; keeps "never replace cold qualification with a cache" intact |
| Attribute fallback reasons to the gate PC in the candidate stats | scheduler refusals all sit at `1ABB40` with large slack; the ledger should show it | DO NOW, two lines |
| Record parent activation identity and parent gates for spawn children in the census | the pairing is inferred from frames today | EXPERIMENT NEXT, when the spawn frontier is worked |
| Retention by value boundaries, alias relationships or input state | no case in the repository was found by the replay and missed by the constructed matrix | WAIT |
| A coverage framework, instruction or bus traces, generated datasets | the signature is one line per occurrence and the state is 162 KB; nothing larger was needed to answer any question here | REJECT |

## Addendum: the scheduler refusals, measured

Over four 150-frame segments from retained parent states (336 contact ticks,
`artifacts/replay-evidence-study/slack_study.py`):

- The tick plan is small: 2,488 cycles median, 3,250 at most, 2 percent of
  the 128,005-cycle frame; no plan exceeds a tenth of a frame.
- The game runs the contact tick at the very end of the frame: median phase
  125,237 cycles into the frame.  54 of 336 ticks (16 percent; 22 percent on
  the whole of `main`) straddle the frame deadline, and the native admission
  rule rightly refuses a plan that would end after the boundary.
- At refusal the slack is 1,327 cycles median (9 to 3,077).  The tick's
  RAM-only prefix is 378 cycles and would fit in 49 of the 54; the 24-slot
  scan (about 2,100 cycles) is what does not.  Capping plans at 2,000 cycles
  would still leave 37 refusals; no plan size fixes a phase problem.

So the 15,691 scheduler refusals on `main` are neither a recovery gap nor a
grinder task.  Two honest options: (A) admit the tick in pieces, the prefix
at `1ABB40` and then as many scan slots as fit before the deadline, leaving
the rest of the scan to the original in that frame (a runner and planner
mechanism that changes the "deadline refusal is one original instruction"
contract deliberately, and needs a gate budget, 62 of 64 used); or (C) keep
the mechanism and read the ledger's `fallbacks by gate` line as the phase
artifact it is.  Either way the parent-ownership tier must treat a refused
parent plan as inconclusive, which `segment_verify` now does.

## Appendix: experiments and how to rerun them

All scripts read the checkout and the local history; none writes to the
repository.  Outputs are regenerable.

- `artifacts/replay-evidence-study/sig_census.py OUT [node]`: the signature
  census (302.5 s on `main`); writes `report.json` (raw signatures with
  frames, counts, fixtures and parent fixtures) and the retained states.
- `artifacts/replay-evidence-study/segment_check.py FIXTURE.state FRAMES`:
  restores a census state into an original and a candidate run, compares
  every frame, and checks the original against the reference observations.
- `artifacts/replay-evidence-study/sched_attrib.py FIXTURE.state FRAMES`:
  attributes fallback reasons to gates and measures the slack at refused
  admissions over a segment.
- `artifacts/replay-evidence-study/slack_study.py FRAMES PARENT.state ...`:
  contact tick admissions against frame slack over segments.
- `paths.json`: the 195 path classes with counts, first frames, cost,
  native shape and fixtures; `report.json`: the 415 raw signatures.

Measured figures used above: full cold comparison 403.1 s (parallel) for
82,161 frames; plain census 269 s; signature census 302.5 s with the terminal
state equal to the reference; fixture 162,172 bytes, restore 1 ms; 300-frame
segment 1.5 s (original) and 1.6 to 1.8 s (candidate), every frame equal to
the reference; offline signature 22 ms per fixture; reference observations
35.7 MB per run; history caches 1.9 MB in four implementation sets, none
current.
