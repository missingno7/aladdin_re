# Gods grinder protocol

One recovery iteration on Gods, step by step, with the exact commands.  It
is the loop of `../common/recovery-process.md` instantiated on this game and
is a transcript of the iteration that recovered the camera follow step
`002806` (`STATUS.md`, `ledger.md`), which is the canonical example: when in
doubt, do what that iteration did.  Nothing here requires Aladdin's
documentation; Aladdin's recipes are not Gods' recipes.

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
must lie in work RAM (`FF0000`–`FFFFFF`) or ROM (`000000`–`0FFFFF`).  Any
`A0xxxx` (Z80 window, I/O) or `C000xx` (VDP) access, any `jsr`/`bsr` to an
unrecovered routine, any interrupt inside the trace, any loop whose count no
RAM byte bounds: defer the region and pick another.  Write the chosen entry
and the reason as the first line of the session notes.

## 3. Census the entry over the recorded histories

```powershell
& $py scripts\recovery_census.py artifacts\gods\evidence\census-<PC> --game gods --classifier entry --entry <PC> --node <NODE>
```

`--classifier entry` carries no game knowledge (Gods has no object-table
convention yet; `kind` is Aladdin's).  The report lists the executed path
classes with counts, and retains one entry state per class plus one per
exit CCR (`<PC>-entry-p<N>[-ccr<XX>].state` + `.json`).  Run it on the
longest history; if another recording reaches the routine in situations the
first does not, run it there too into a separate directory.  `cut > 0` means
an occurrence ran past the frame deadline: those states are classified
offline and are fine as fixtures, but note them.

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
recordings did not witness.  Model: `camera_follow_plan`.

## 7. Dispatcher

`src/gods_sega/recovery.py`: add the entry to `PLANNERS['<candidate>']` (a
new candidate name for a new region, or extend the existing one when the
regions are meant to be verified together), and a mutant to `MUTATIONS`
(`<candidate>-mutant-result`: one stored byte off).  The `Candidate` class
needs no change for a plain leaf.

## 8. Tests, then the strict witness on every retained path

`tests/games/gods/test_<concern>.py` modelled on `test_camera.py`: the
semantics on synthetic reads (always runs); the plan against the tracer on
every retained fixture (`pathfacts.check_plan` must return no problems;
skipif the census directory is absent); the declined arms decline and the
original runs them; the segment tier (below).

```powershell
& $py scripts\run_tests.py gods -- -k <concern>
foreach ($f in Get-ChildItem artifacts\gods\evidence\census-<PC>\*.state) { & $py scripts\factcheck.py check $f.FullName gods_sega.boundary:<region>_plan --game gods }
```

Every fixture must print `MATCH`.  `MISMATCH` names the wrong fact: fix the
plan.  `DECLINED` on a claimed arm: the guard is wrong.  Never touch the
fixture.

## 9. Future continuation

```powershell
& $py scripts\segment_verify.py artifacts\gods\evidence\main\boundary-6000.state --game gods --candidate <candidate> --frames 300
& $py scripts\segment_verify.py artifacts\gods\evidence\main\boundary-12000.state --game gods --candidate <candidate> --frames 300
```

PASS with `candidate hits > 0` and `fallbacks 0` on witnessed arms.  The
reference is `artifacts\gods\evidence\main\reference.json`, the reference
worker's observations of the last original-vs-original PASS of that history
(`f0ac19738f19…`); if you retain states from another history, verify it with
`--candidate original` first and keep its `reference.json` beside them.

## 10. Fresh-process verification of the whole history

```powershell
& $py scripts\dev.py history-verify <NODE> --game gods --candidate <candidate> --timeout-seconds 900 --output artifacts\gods\verify-<candidate>-<NODE>
& $py scripts\verify_status.py artifacts\gods\verify-<candidate>-<NODE>
```

About 60 s per 15,000 frames with parallel workers; give 20 s of timeout per
1,000 frames.  Read the result only through `verify_status.py`.  `PASS` with
hits > 0 is the qualification; `NOT_EXERCISED` means the region never ran on
that history; `DIVERGENCE` names the first differing frame — inspect it with
`facts` from a retained state near it before changing anything.

## 11. Negative control

```powershell
& $py scripts\dev.py history-verify <NODE> --game gods --candidate <candidate>-mutant-result --timeout-seconds 900 --output artifacts\gods\verify-<candidate>-mutant
```

Must be `DIVERGENCE` at the first frame that enters the region (or the
segment check must diverge at the first frame after the fixture).  A PASS
here is a `FACTORY_DEFECT` escalation.

## 12. Milestone: the tree, the suite, the record

```powershell
& $py scripts\run_tests.py gods
& $py scripts\dev.py history-verify main --game gods --candidate <candidate> --tree --timeout-seconds 1800 --output artifacts\gods\verify-<candidate>-tree-<date>
```

The tree verifies every recorded branch (about 2 s per 1,000 frames of tree
edges with parallel workers).  Then: one line in `ledger.md`, the region and
the next bites in `STATUS.md`, commit (`Gods: recover <PC> <region> (<shape>)`
with hits and fallbacks in the body), push.  Between milestones commit
locally once steps 8–11 pass.

## Candidate selection rules

Take first: frequently executed, small or medium, clear entry/return,
RAM-only, no device access, few arms, every arm recorded, deterministic cost
per arm.

Defer (a deferral is a result, write it in the session notes): direct VDP
access (`C00000`/`C00004`), Z80 window or I/O access (`A0xxxx`, `A1xxxx`), the
VBlank handler and anything reached from it, loops without a RAM-named
bound, command or script interpreters, routines whose arms are mostly
unwitnessed, anything needing a mechanism `recovery.py` does not have (Gods
has no seam for a platform call inside a region yet).

## Escalation

Stop work on the candidate, write the blocker package, continue with another
admissible candidate.  Do not spend more than three attempts on one fact.

| code | condition |
|---|---|
| `NEW_SHARED_MECHANISM` | the region needs something `Machine.atomic` and a plain plan cannot express: a platform call inside the region (a seam), writes between two platform calls, an interrupt inside the region, a device register in the region's own code |
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

Three lines per session or milestone in `artifacts/gods/grinder/session.log`:
regions recovered (entry, arms, hits, fallbacks), escalations (entry, code),
next candidate.  Every command run goes to
`artifacts/gods/grinder/commands.log`.  Nothing else is a status report.
