# Recovery grinder protocol

This is the step loop for the long-running recovery worker (the "grinder").
It recovers ONE bounded branch of the original Genesis game at a time into
Python, proves it against the original machine, records it, and moves to the
next branch that the recorded evidence ranks highest.  The original machine is
the oracle: a plan must reproduce its exact effects.  The machine handles
deterministic mechanics, you handle meaning, the oracle handles truth.

Read this file, the current section of `docs/STATUS.md` and the tail of
`docs/recovery-ledger.md` at the start of a session.  Do not redesign anything.
Do not read `boundary.py` from the top; read the named functions a step points
you to.  Anything not covered by a recipe below is an escalation, not a
puzzle: write the blocker package (section 7) and move to the next ledger row.

## 1. Environment

PowerShell, from the checkout root (`D:\Prog\aladdin_re`):

```powershell
$env:PYTHONPATH = 'src;scripts;tests'
$env:ALADDIN_NATIVE_LIBRARY = "$PWD\build\libaladdin_native.dll"
$py = '.\.venv\Scripts\python.exe'
```

Rules of the machine:

- One native `Machine` per process.  Never hold two at once; every tool
  here opens and closes its own.
- Live RAM is the only state.  Read it through the machine; never cache it.
- Freeze `src/` while a cold verification runs.  A changed module invalidates
  the receipt (`STALE_EVIDENCE`).  Do read-only ledger work meanwhile.
- The history under `history/` and the ROM are never edited to obtain a PASS.

## 2. Tools

Every machine number a planner needs comes from these commands, never from
reading the ROM by eye or counting cycles by hand.

| Command | What it answers |
|---|---|
| `& $py scripts\frontier_ledger.py ARTIFACTS --index artifacts\evidence\main` | What the last cold run still hands to the original, ranked by count, with the boundary function that refused it, the scheduler refusals by gate, and the evidence index: every recorded behavior class with its count, first frame, cost, native shape, child and parent fixtures. |
| `& $py scripts\recovery_census.py artifacts\evidence\main --entry PC [--entry PC] --parent 1ABB40` | The discovery pass: one original replay that single-steps every occurrence of the entries, retains one entry state per distinct executed path (plus one per exit CCR) with the contact-tick parent state that led to it (`parent-*.state`), and writes `index.json`, the evidence index the ledger reads.  Run it once per history extension, for all frontier entries together. |
| `& $py scripts\segment_verify.py FIXTURE.state --frames 120 [--reference ARTIFACTS]` | Restores a retained state, runs the candidate for N frames under real deadlines and compares every frame with the stored reference observations of the last PASS cold run (copy its `reference.json` into the evidence directory).  For a `parent-*` fixture it says whether the child was owned or declined.  Seconds, independent of replay length. |
| `& $py scripts\factcheck.py facts FIXTURE.state [--park PC] [--stop PC] [--path]` | Instructions, cycles, last_pc, stack delta, changed registers, CCR, every RAM byte written, calls/returns, and with `--path` each executed instruction. |
| `& $py scripts\factcheck.py segments FIXTURE.state [--park PC]` | The PYTHON / NATIVE split around sound calls (1E58B8, 1E58F4, 1E589A): the prefix you may own, the native call, the resumed suffix, each with its own facts. |
| `& $py scripts\factcheck.py branches FIXTURE.state --park PC --vary ADDR[.w]=v1,v2` | Which executed path each input takes and whether the cost is constant inside a path. |
| `& $py scripts\factcheck.py check FIXTURE.state aladdin_sega.boundary:PLANNER --park PC [--vary ...]` | Every fact your plan gets wrong.  `MATCH` (exit 0), `MISMATCH` (1) or `DECLINED` (2).  A `SoundSeam` planner is checked through its prefix. |
| `& $py scripts\verify_status.py ARTIFACTS` | The one word about a verification directory: RUNNING, PASS, STALE_EVIDENCE, DIVERGENCE, TIMEOUT, DEPENDENCY_FAILURE, NOT_EXERCISED, ERROR, NO_EVIDENCE.  This is the only way to read verifier state. |
| `& $py scripts\leaf_review.py [--artifacts DIR]` | The review gate for one leaf: diff, removed guards/assertions, gate count, changed test modules, focused suites, verification status. |
| `& $py scripts\dev.py history-verify main --history history --candidate lifecycle --timeout-seconds 1800 --output artifacts\NAME` | The cold comparison (two fresh workers in parallel).  Give it at least 20 seconds of timeout per 1,000 frames of `main`. |

## 3. Choosing the next bite

1. Run `frontier_ledger.py` on the newest artifacts directory whose
   `verify_status` is PASS, with `--index` pointing at the evidence
   directory of the same history (`artifacts/evidence/main`).
2. Take the entry with the highest fallback count whose evidence rows have a
   child fixture, then work its path classes from the most frequent down;
   every class is one arm to recover or to decline explicitly.  Skip a class
   when its row shows any of: a read or write outside work RAM
   (`FF0000`-`FFFFFF`) and ROM in `facts --path` that is not inside a
   `NATIVE_ENTRIES` callee, a loop whose trip count is not bounded by a RAM
   byte you can name, or more than about 600 instructions.  Those rows are
   escalations (section 7).  A row with two or more native calls is not an
   escalation: bridge them (the third recipe in step 2 of section 4).
3. Write the chosen row and its reason as the first line of your session
   notes before touching any source.

## 4. The step loop for one leaf

1. **FACTS.** For every fixture of the row: `facts --path` from the entry
   (`--park` when the fixture stands at the dispatcher, `1ABC82`).  Note the
   entry PC, exit PC (caller return), RAM bytes written, registers changed,
   CCR residue, and any NATIVE segment.  Run `branches` with the RAM bytes
   the path tests (`--vary`) so each arm and its cost are known.
2. **CLASSIFY** the shape and pick exactly one recipe:
   - *RAM-only leaf returning to its caller*: copy the shape of
     `begin_contact_family_type55` (boundary) and `contact_type55_guard` /
     `contact_type55_return` (semantics), routed through
     `begin_contact_family_type55_dispatch` and the `family_planner` map in
     `recovery.py`, plus the two callback maps in `contact_scan_plan` and
     `_contact_scan_resume` when the caller is the contact scan.
   - *Branch with one native call*: the callee is one of the native seam
     routines in `pathfacts.NATIVE_ENTRIES` (the sound request 1E58B8, its
     helper 1E58F4, the flush 1E589A, and the VDP tile upload 1B2650, a
     39-instruction routine that writes VRAM through the VDP ports and
     returns).  The prefix plan ends with the PC at the callee and the
     frame pushed; the seam runs the original through the callee to the
     resume PC; the suffix plan continues from live state.  Copy the shape
     of `begin_contact_family_type46_sound_seam`, its `_dispatch_sound_seam`
     wrapper and `finish_contact_family_type46_sound` (boundary),
     `contact_type46_request` (semantics) and the `TYPE46` arm in
     `recovery.py`.  `begin_contact_family_type43_sound_seam` is the second
     exemplar (a longer prefix, a second native call inside the seam).  A
     device access inside the callee is the callee's business; a device
     access in your own prefix or suffix is an escalation.
   - *Branch with a run of platform calls*: two or more `NATIVE_ENTRIES`
     callees in one activation (a VDP upload then sound requests, a sound
     request then a second one after a selector).  Do not chain seams.
     End the prefix at the first platform entry with its frame pushed and
     resume at the activation's own RTS: `_platform_tail_bridge_seam`
     (spawn callers `1B6C5A`/`1B6D1E`) and the type-13 arm of
     `begin_contact_sibling_sound_seam` (resume `CONTACT_SIBLING_TYPE13_RETURN`)
     are the exemplars, with `saved_frame 0, frame_size 4, return_delta 0`
     and the return slot at SP as the identity.  The machine runs every
     platform call and the wrapper code between them; the suffix is the
     RTS plus whatever the caller composes after it.  Own the logic between
     two platform calls only when a later audit shows it is worth a
     mechanism; record the ceded instructions in the ledger line.
   - *A call to the random number generator* (`1B3032`): compose
     `rng_step` from boundary.py into your plan the way `initialize_object`
     is composed; its semantics are `game.advance_rng`.  Sweep the seed with
     `--vary FF7DEA.l=...` to reach arms the recording never took.
   - Anything else is UNSUPPORTED: raise `UnsupportedCandidate` for that arm
     and write the blocker package.
3. **SEMANTICS FIRST.** In `src/aladdin_sega/game/objects/contact.py` (or the
   family's module) write the predicate and the durable RAM writes as a pure
   function of a `read(address, size)` reader, returning `(writes, facts)` or
   `(arm, facts)` like the exemplars.  No cycles, stack slots or CCR here.
   Export it through `recovered.py`.
4. **BOUNDARY.** In `boundary.py` write the planner from the recipe: alias
   guards (`_spans_disjoint` over the record, the stack frame and every
   global read or written), the cost table in the docstring, register residue,
   CCR via `_logic_sr/_cmp_sr/_sub_sr/_add_sr`.  Every number comes from the
   fact report.
5. **CHECK.** `factcheck.py check` must print `MATCH` for every fixture and
   for every `--vary` combination that selects an arm you claim.  `DECLINED`
   on a claimed arm means your guard is wrong; `MISMATCH` names the fact.
   Fix facts until it matches; never adjust the fixture.
6. **ROUTE.** Add the dispatcher arm in `recovery.py` exactly as the copied
   recipe does, and the entry to `begin_collection_dispatch`'s accepted list.
   A RAM-only callback whose caller is the contact scan also goes into both
   scan callback maps (that is what makes the parent own it).
7. **QUALIFY.** Add tests modelled on `tests/test_contact_type55.py`
   (RAM-only) or the Type-43/Type-46 tests in `tests/test_contact_family.py`
   (seam): outer equality, future equality, `fresh_process_future`, one
   dispatcher hit and zero fallbacks per admitted arm; each unsupported arm
   declines with `fallbacks >= 1` and no writes; the three mutants
   (result, continuation, timing) diverge.  Then run `segment_verify.py` on every retained child and
   parent fixture of the class (`--frames 120`): each must PASS against the
   reference, and a parent fixture must report the child as owned unless the
   arm is one you declined on purpose.  `tests/test_recorded_evidence.py` is
   the tracked form of that check; it runs whenever the evidence directory
   exists.
8. **REVIEW.** `leaf_review.py` must print `leaf review: PASS`.  Read its
   `guards` line: a removed refusal or assertion is a widening you must be
   able to justify from facts, or revert.
9. **MILESTONE GATES** (after three leaves or about ninety minutes of recovery
   work, whichever comes first, and always before a push): full suite with
   `-n 8`, then
   the cold comparison into a fresh `artifacts\NAME`, started in the
   background.  While it runs, touch nothing under `src/` or `tests/`; do the
   read-only preparation of the next row instead.  Read the result only
   through `verify_status.py`.  Between milestones, commit each qualified leaf
   locally once its focused tests, `leaf_review` and segment checks pass; do
   not push until the milestone gates pass.
   `TIMEOUT` means rerun with a longer watchdog; `STALE_EVIDENCE` means you
   edited source during the run, rerun; `DIVERGENCE` means the leaf is wrong
   even though its tests passed, investigate the first differing frame with
   `facts` before changing anything.
10. **RECORD.** Append one line to `docs/recovery-ledger.md` (format in that
    file), then commit and push (section 6).  Do not edit `docs/STATUS.md`
    per leaf; update its current section once per milestone commit.

## 5. Cadence

| When | Run |
|---|---|
| after each edit | the test module you are writing (`pytest tests\test_<name>.py -q -p no:cacheprovider`) |
| after `check` matches, before each local commit | `leaf_review.py` (focused suites, about 30 s), then `segment_verify.py` on the class's child and parent fixtures (seconds) |
| at a milestone: after three leaves or about ninety minutes of recovery work, whichever comes first, and always before a push | full suite with `-n 8` (`pytest -q -p no:cacheprovider -n 8`, about a minute), then the cold comparison started in the background (about 8 min for 82,000 frames); while it runs, do read-only preparation for the next row (`frontier_ledger`, `facts`, `branches`, `segments`) and touch nothing under `src/` or `tests/` |
| after a milestone PASS | copy its `reference.json` into `artifacts/evidence/main`, run `frontier_ledger.py --index` on the new artifacts, update the current section of `docs/STATUS.md`, push; rerun the census only after a history extension |

Do not run the full suite or the cold comparison after exploratory edits.
Do not poll a running verifier more often than every two minutes; a quiet
process is not a failed process.

## 6. Commit and publication rules

- Commit each qualified leaf locally once its focused tests, `leaf_review.py`
  and the segment checks on its class's child and parent fixtures pass.  One
  leaf (or one small cohesive batch) per commit; the ledger line, the tests
  and the source go together.
- Message: first line `Recover <entry> <kind/arm> <recipe>`, body with the
  test count and, for a milestone, the cold-run frames and artifacts
  directory and the fallback count before and after.  End with the
  attribution line the host requires.
- Push to `main` only after a milestone's full suite and cold comparison
  PASS with current receipts.  If a milestone cold run diverges, the local
  commits since the last push stay unpushed until the responsible leaf is
  found through its fixtures and segments and fixed.  Never force-push, never
  rewrite history, never commit the ROM, private recordings or `artifacts/`.
- Never weaken an assertion, delete a test, edit a fixture, or widen a guard
  to obtain a PASS.  A caught exception is not a PASS: `UnsupportedCandidate`
  is a supported refusal; any other exception is a bug to fix.
- Log every command you run, one per line, in `artifacts/grinder/commands.log`.

## 7. Escalation

Stop working on a row and write a blocker package when any of these holds.
Then continue with the next ledger row; do not spend more than three attempts
on one fact.

| Code | Condition |
|---|---|
| `NEW_MACHINE_MECHANISM` | the arm needs something no recipe provides: two native calls in one prefix with writes between them, a device register in your own prefix or suffix (not inside a `NATIVE_ENTRIES` callee), an interrupt, a loop without a RAM-named bound, the command-stream engine (1ACD54 / 1B249E / 1B263C), a native callee outside `NATIVE_ENTRIES` |
| `NEW_SUBSYSTEM` | the entry is not a collection dispatcher child or contact-tick callee, or its caller is not an existing gate |
| `AMBIGUOUS_ARCHITECTURE` | two existing recipes both almost fit and choosing one changes what the parent owns |
| `DATA_STRUCTURE` | the facts show a record layout, table or pointer domain no existing semantic function names |
| `FACTORY_DEFECT` | a tool disagrees with the oracle (for example `check` says MATCH but qualification diverges), or a tool crashes |
| `VERIFIER_BLOCKED` | three consecutive milestone runs end in TIMEOUT, DEPENDENCY_FAILURE or ERROR |
| `EMPTY_FRONTIER` | the ledger has no recorded row left that section 3 admits |

Blocker package: `docs/blockers/<date>-<entry>.md` with these headings:
Where (entry PC, kind, caller), Code, Observed (the fact report, the branch
table), Why the recipe does not fit (one paragraph), Fixtures used (paths and
SHA-256), What was tried (each attempt in one line), Next question (one
sentence a stronger model can answer).  Commit the blocker package alone with
the message `Escalate <entry>: <code>`.

## 8. Reporting

At the end of a session or every milestone, write three lines to
`artifacts/grinder/session.log`: leaves recovered (entry, arm, fallbacks
before and after), escalations written (entry, code), next row.  Nothing else
is a status report; do not write progress prose anywhere else.
