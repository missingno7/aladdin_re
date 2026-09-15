# Aladdin recovery playbook

How the shared recovery loop (`../common/recovery-process.md`) maps onto
Aladdin's code: its dispatchers, its seams, its recipes, its tools and its
escalation codes.  This is the factory manual the supervised grind of 14–15
September ran on, with the generic methodology removed and the paths
updated.  Read the loop first; this file assumes it.

Aladdin's candidate grind is currently paused with its bounded frontier
exhausted on the long recording (`STATUS.md`).  Everything below still
applies the day a longer recording or a decision about the command-stream
engine reopens it.

## 1. Environment and rules

PowerShell, from the checkout root:

```powershell
$py = '.\.venv\Scripts\python.exe'
# scripts/run_tests.py and tests/conftest.py set the import paths and GENESIS_NATIVE_LIBRARY;
# for ad-hoc commands: $env:GENESIS_NATIVE_LIBRARY = "$PWD\build\libgenesis_native.dll"
```

- One native `Machine` per process; every tool opens and closes its own.
- Live RAM is the only state; read it through the machine, never cache it.
- Freeze `src/` while a cold verification runs (a changed module makes the
  result `STALE_EVIDENCE`); do read-only ledger work meanwhile.
- `history/aladdin/`, the ROM, fixtures and test assertions are never edited
  to obtain a PASS.
- Do not read `boundary.py` (7,800 lines) from the top; read the functions a
  recipe names.

## 2. Tools, with Aladdin's arguments

| command | what it answers |
|---|---|
| `& $py scripts\frontier_ledger.py ARTIFACTS --index artifacts\evidence\main` | what the last cold run still hands to the original, ranked by count, with the boundary function that refused it, the scheduler refusals by gate, and the evidence index (every recorded behaviour class with count, first frame, cost, native shape, child and parent fixtures).  `--boundary` defaults to `src/aladdin_sega/boundary.py`. |
| `& $py scripts\recovery_census.py artifacts\evidence\main --game aladdin --entry PC [--entry PC] --parent 1ABB40` | the discovery pass over `main`: one entry state per executed path (`--classifier kind`, the record kind byte at (A1), is Aladdin's object-table convention and the default), plus one per exit CCR, plus the contact-tick parent state (`parent-*.state`); writes `index.json`.  Once per history extension, all frontier entries together. |
| `& $py scripts\segment_verify.py FIXTURE.state --game aladdin --candidate lifecycle --frames 120 [--reference ARTIFACTS]` | the retained state run under the candidate for N frames against the reference of the last PASS (`reference.json` beside the fixtures); a `parent-*` fixture says whether the child was owned or declined. |
| `& $py scripts\factcheck.py facts FIXTURE.state --game aladdin [--park PC] [--stop PC] [--path]` | the tracer's facts; `--park 1ABC82` when the fixture stands at the collection dispatcher. |
| `& $py scripts\factcheck.py segments FIXTURE.state --game aladdin [--park PC]` | the PYTHON / NATIVE split around the native entries (`aladdin_sega.profile.TRACER_NATIVE_ENTRIES`: the sound request `1E58B8`, its fixed helper `1E58F4`, the flush `1E589A`, the VDP tile upload `1B2650`). |
| `& $py scripts\factcheck.py branches FIXTURE.state --game aladdin --park PC --vary ADDR[.w]=v1,v2` | which path each input takes and whether cost is constant inside a path. |
| `& $py scripts\factcheck.py check FIXTURE.state aladdin_sega.boundary:PLANNER --game aladdin --park PC [--vary ...]` | `MATCH` (0), `MISMATCH` (1, names the fact), `DECLINED` (2).  A `SoundSeam` planner is checked through its prefix. |
| `& $py scripts\verify_status.py ARTIFACTS` | one word: RUNNING, PASS, STALE_EVIDENCE, DIVERGENCE, TIMEOUT, DEPENDENCY_FAILURE, NOT_EXERCISED, ERROR, NO_EVIDENCE. |
| `& $py scripts\aladdin\leaf_review.py [--artifacts DIR]` | the review gate for one leaf: diff, removed guards/assertions, gate count (62 of the native limit 64), changed test modules, focused suites, verification status. |
| `& $py scripts\dev.py history-verify 44223150b7d6c5664d90f908d765542d89565a8557a8e88b392948998e579fde --game aladdin --candidate lifecycle --timeout-seconds 1800 --output artifacts\NAME` | the cold comparison of the long route (about 7 minutes with parallel workers; 20 s of timeout per 1,000 frames).  Pin the node id, not `main`: `main` moves when the user records. |
| `& $py scripts\history_edit_check.py --game aladdin --candidate lifecycle --node NODE --source game/objects/lifecycle.py --needle ... --replacement ... --output DIR` | the no-rebuild edit loop: baseline PASS and a semantic mutation rejected, native binary unchanged. |

## 3. Choosing the next bite

1. `frontier_ledger.py` on the newest PASS artifacts named in `ledger.md`,
   `--index artifacts\evidence\main`.
2. Take the entry with the highest fallback count whose evidence rows have a
   child fixture; work its path classes from the most frequent down; every
   class is one arm to recover or to decline explicitly.  Skip (escalate) a
   class whose row shows a read or write outside work RAM and ROM that is not
   inside a native-entry callee, a loop whose trip count no RAM byte bounds,
   or more than about 600 instructions.  A row with two or more native calls
   is a bridge (recipe 3), not an escalation.
3. Write the chosen row and its reason as the first line of the session notes
   before touching source.

## 4. The recipes

Every Aladdin leaf recovered so far fits one of these shapes.  Copy the named
exemplar; do not invent a fifth shape (that is an escalation).

1. **RAM-only leaf returning to its caller.**  Exemplar:
   `begin_contact_family_type55` (boundary) with `contact_type55_guard` /
   `contact_type55_return` (semantics, `game/objects/contact.py`), routed
   through `begin_contact_family_type55_dispatch` and the `family_planner`
   map in `recovery.py`, plus the two callback maps in `contact_scan_plan`
   and `_contact_scan_resume` when the caller is the contact scan (that is
   what makes the parent own it).
2. **One native call inside the branch.**  The callee is one of the native
   entries.  The prefix plan ends with the PC at the callee and the frame
   pushed; the seam runs the original through the callee to the resume PC;
   the suffix plan continues from live state.  Exemplar:
   `begin_contact_family_type46_sound_seam`, its `_dispatch_sound_seam`
   wrapper and `finish_contact_family_type46_sound` (boundary),
   `contact_type46_request` (semantics), the `TYPE46` arm in `recovery.py`;
   `begin_contact_family_type43_sound_seam` is the second exemplar (a longer
   prefix, a second native call inside the seam).  A device access inside the
   callee is the callee's business; one in your own prefix or suffix is an
   escalation.
3. **A run of platform calls.**  Two or more native-entry callees in one
   activation.  Do not chain seams: end the prefix at the first platform
   entry with its frame pushed and resume at the activation's own RTS
   (`_platform_tail_bridge_seam`, spawn callers `1B6C5A`/`1B6D1E`; the
   type-13 arm of `begin_contact_sibling_sound_seam`, resume
   `CONTACT_SIBLING_TYPE13_RETURN`; `saved_frame 0, frame_size 4,
   return_delta 0`, the return slot at SP as the identity).  The machine runs
   every platform call and the wrapper code between them.  Record the ceded
   instructions in the ledger line.
4. **A call to the random number generator (`1B3032`).**  Compose `rng_step`
   from `boundary.py` into the plan the way `initialize_object` is composed;
   semantics `game.rng.advance_rng`.  Sweep the seed with
   `--vary FF7DEA.l=...` to reach arms the recording never took.
5. **Anything else** is `UnsupportedCandidate` for that arm and a blocker
   package (section 7).

Dispatcher topology the recipes assume: the collection dispatcher `1ABC82`
(return `1ABCA0`), the contact tick `1ABB40` and its scan `1ABBD6`
(callbacks return through `1AE6B4`), the object transition `1AF468` with the
sound return `1AF498`, the spawn walker and the setup parents
(`SPAWN_REGION_ENTRIES` in `boundary.py`).  The gate list is
`Candidate.gate_pcs` in `recovery.py`; the native limit is 64 gates.

## 5. One leaf, step by step

1. **Facts** for every fixture of the row (`facts --path`, `--park` at the
   dispatcher when needed); `branches --vary` over the RAM bytes the path
   tests.
2. **Semantics first**, in `src/aladdin_sega/game/objects/<family>.py`: the
   predicate and the durable RAM writes as a pure function of a
   `read(address, size)` reader, returning `(writes, facts)` or `(arm, facts)`
   like the exemplars; no cycles, stack slots or CCR.  Export through
   `recovered.py`.
3. **Boundary**, in `boundary.py`: the planner from the recipe — alias guards
   (`_spans_disjoint` over the record, the stack frame and every global read
   or written), the cost table in the docstring, register residue, CCR via
   `_logic_sr/_cmp_sr/_sub_sr/_add_sr`.  Every number from the fact report.
4. **Check**: `factcheck.py check` must print `MATCH` for every fixture and
   every `--vary` combination that selects a claimed arm.
5. **Route**: the dispatcher arm in `recovery.py` exactly as the copied
   recipe does, and the entry in `begin_collection_dispatch`'s accepted list;
   a RAM-only callback whose caller is the contact scan also goes into both
   scan callback maps.
6. **Qualify**: tests modelled on `tests/games/aladdin/test_contact_type55.py`
   (RAM-only) or the Type-43/Type-46 tests in
   `tests/games/aladdin/test_contact_family.py` (seam): outer equality,
   future equality, `fresh_process_future`, one dispatcher hit and zero
   fallbacks per admitted arm; each unsupported arm declines with
   `fallbacks >= 1` and no writes; the three mutants (result, continuation,
   timing — the `lifecycle-mutant-*` candidate names) diverge.  Then
   `segment_verify.py` on every retained child and parent fixture of the
   class; a parent fixture must report the child as owned unless the arm was
   declined on purpose.  `tests/games/aladdin/test_recorded_evidence.py` is
   the tracked form of that check.
7. **Review**: `leaf_review.py` must print `leaf review: PASS`; a removed
   refusal or assertion on its `guards` line is a widening to justify from
   facts, or revert.
8. **Milestone gates** (three leaves or ninety minutes, and always before a
   push): `scripts\run_tests.py aladdin`, then the cold comparison of the
   long route into a fresh `artifacts\NAME` in the background; touch nothing
   under `src/` or `tests/` while it runs.  `TIMEOUT`: rerun with a longer
   watchdog.  `STALE_EVIDENCE`: source was edited during the run, rerun.
   `DIVERGENCE`: the leaf is wrong although its tests passed; investigate the
   first differing frame with `facts` before changing anything.
9. **Record**: one line in `ledger.md` (format at its top); `STATUS.md` once
   per milestone, not per leaf.  After a milestone PASS copy its
   `reference.json` into `artifacts/evidence/main` and rerun the frontier
   ledger; rerun the census only after a history extension.

## 6. Commit and publication

- One leaf (or one small cohesive batch) per local commit once its focused
  tests, `leaf_review` and the segment checks pass; the ledger line, tests and
  source together.  Message: `Recover <entry> <kind/arm> <recipe>`, body with
  the test count and, for a milestone, the cold-run frames, artifacts
  directory and fallback count before and after.
- Push only after a milestone's suite and cold comparison PASS with current
  receipts.  Never force-push, rewrite history, or commit the ROM, private
  recordings or `artifacts/`.
- Never weaken an assertion, delete a test, edit a fixture or widen a guard
  to obtain a PASS.  `UnsupportedCandidate` is a supported refusal; any other
  exception is a bug.
- Log every command run in `artifacts/grinder/commands.log`; three lines per
  session in `artifacts/grinder/session.log` (leaves, escalations, next row).

## 7. Escalation codes and the blocker package

| code | condition |
|---|---|
| `NEW_MACHINE_MECHANISM` | the arm needs what no recipe provides: writes between two native calls in one prefix, a device register in your own prefix or suffix, an interrupt inside the region, a loop without a RAM-named bound, the command-stream engine (`1ACD54` / `1B249E` / `1B263C`), a native callee outside the native entries |
| `NEW_SUBSYSTEM` | the entry is not a collection dispatcher child or contact-tick callee, or its caller is not an existing gate |
| `AMBIGUOUS_ARCHITECTURE` | two recipes both almost fit and the choice changes what the parent owns |
| `DATA_STRUCTURE` | the facts show a record layout, table or pointer domain no semantic function names |
| `FACTORY_DEFECT` | a tool disagrees with the oracle (`check` says MATCH but qualification diverges) or crashes |
| `VERIFIER_BLOCKED` | three consecutive milestone runs end in TIMEOUT, DEPENDENCY_FAILURE or ERROR |
| `EMPTY_FRONTIER` | no recorded row left that section 3 admits |

Blocker package: `blockers/<date>-<entry>.md` with the headings Where (entry
PC, kind, caller), Code, Observed (the fact report, the branch table), Why the
recipe does not fit, Fixtures used (paths and SHA-256), What was tried (one
line each), Next question (one sentence a stronger model can answer).  Commit
it alone: `Escalate <entry>: <code>`.  Three existing packages are under
`blockers/`; two of them (`1B65F4`, `1B67C2`) were later recovered by the
supervisor with a new arm each, which is the intended outcome.

## 8. What the native runtime changes

The candidate grind and the native runtime share `game/` semantics but are
different verification ladders.  A leaf recovered for the candidate is a
plan at a gate inside original execution; the native runtime runs the whole
frame without the original.  Its loop, tools and gap classification are in
`native-frontier.md` §4; its harness tools are `scripts/aladdin/native_diff.py`,
`native_replay.py`, `verify_step.py`, `verify_sequence.py`, `verify_ports.py`,
`route_census.py`.  Do not mix the two ledgers: a native gap is not a
candidate fallback.
