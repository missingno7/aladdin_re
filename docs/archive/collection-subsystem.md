# Frozen historical evidence

This report preserves ROM mapping, qualification, and recovery decisions at its source freeze. It is not current operating guidance: use the immutable cold-start input-history workflow in [../history.md](../history.md). Current commands do not promise to load legacy replay or snapshot artifacts referenced below.

# Collection outcomes and object retirement — 0.9.0

13 September 2026, Windows x64. Baseline: main `6cb9277` (0.8.0).

This phase recovers a coherent family of object-collection outcomes, rather
than another independent arithmetic leaf. The `lifecycle` replay candidate
combines twelve collection entries and a relocation entry with the existing
cleanup/initialization cluster. The old `carrier` remains a bounded comparison
candidate; ordinary play still defaults to original execution.

## Owned behavior and ROM map

Names below describe demonstrated effects. The two decimal counters and the
accumulator have not been assigned guessed collectible/score identities.

| Entry | Collection behavior | Original sound return | Completion |
|---|---|---|---|
| `1AF468` | Primary decimal counter; at 99 publish the object's state-table byte instead of incrementing | `1AF498`, command 11 | Retire with template `1B7ABC`, RTS `1AF4D6` |
| `1AF21E` | Reject while `FFF0D8` is set; secondary decimal counter and capped state-table publication | `1AF258`, command 13 | Add 15, same retirement |
| `1AF264` | Reject at primary 99; accumulate four subunits, then increment the primary counter | `1AF2A6`, command 12 only at threshold | Add 15, same retirement |
| `1AF4A0`, `1AF53E` | Add 15; second entry first resets word `FFF0A4` | `1AF4BC`, command 11 | Same retirement |
| `1AF3C2` | Set `FFF176`, then add 25 | `1AF3E4`, command 105 | Template `1B7CD8`, RTS `1AF3FE` |
| `1AF4D8` | Increment byte `FFF003`, then add 25 | `1AF4FA`, command 105 | Template `1B7CD8`, RTS `1AF514` |
| `1AF2B0`, `1AF2FA` | Set `FFF177`/`FFF178`, activate object/script, set transition words | `1AF2F2`/`1AF33C`, command 100 | RTS `1AF2F8`/`1AF342`; no retirement |
| `1AF344` | Set timer byte `FFF0E9`; retire before sound, then add 100 | `1AF378`, command 100 | RTS `1AF382` |
| `1AF384` | Retire before sound, then add 100 and set `FFF179` | `1AF3B0`, command 100 | RTS `1AF3C0` |
| `1AF400` | Set `FFF11C`; activate source, search 24 primary slots, initialize a companion at its position if available | `1AF422`, command 93 | RTS `1AF466` |
| `1AF516` | Search six secondary slots; relocate the complete 66-byte object with its new script, or leave it alone when full | None | RTS `1AF53C` |

All sound-enabled paths execute the actual original `1E58B8` and `1E589A` in
the recorded witnesses and integration replay. These are still unresolved
machine operations, not a recovered high-level sound service.

Internal recovered calls include pair/buffer cleanup (`1ABE6E`, `1AE372`),
initialization (`1AE30A`), accumulator additions (`1B0156`, `1B016A`, `1B0188`),
decimal increments (`1B0336`, `1B0394`), state publication (`1AE6DE`), and pool
searches (`1AE27A`, `1AE2DA`). They execute through direct Python composition
inside these handlers. There is no gate between these operations on an admitted
path. An original caller outside this family can still require an old gate.

The entire enclosing object dispatcher, other object-update families, and the
identity/meaning of every template field are not recovered by this milestone.
Malformed decimal encodings, aliases, noncanonical table addresses and unsafe
scheduler windows remain outside the candidate domain. The valid capped paths
and the blocked/full-pool branches above are explicitly qualified.

## Permanent source and remaining carrier

`recovered.py` now contains collection state changes, composed object retirement,
pool search, complete-record relocation, activation and companion initialization.
`retire_collected_object` directly composes the existing pair/buffer and template
semantics. Both old replacement entries and new collection handlers use it.
These functions accept a RAM reader and produce staged byte effects; they do
not import the machine, dispatch, snapshots or verification.

An independent byte-image test calls the same collection and retirement source
with no Machine alive and compares its declared object/buffer/accumulator/flag
effects against original execution. This demonstrates portability of that game
logic, not a CPU-free complete game or independent device service. Production
still has exactly one mutable state authority: original work RAM.

`boundary.py` remains substantial. It owns path admission, final registers/CCR,
aggregate cycles/instructions, original stack residue and the sound call frame.
Some outer control flow remains machine-shaped. The whole family is selected by
one `begin_collection`/`finish_collection` carrier path; it does not yet have an
independent native gameplay driver.

The two pool operations exposed one real read-after-write dependency: activating
the source makes its slot occupied before searching for a companion. The shared
semantic search accepts that occupied slot explicitly. No RAM mirror, generic
overlay or synchronization machinery was added.

## Reused sound and snapshot contract

Every supported sound site uses the already-qualified sequence:

```
commit recovered prefix
MOVEM-equivalent D0/D1/A0/A1/A6 save + command + original return in guest RAM
original 1E58B8 -> original 1E589A
recognize site return PC + expected SP + saved 28-byte frame + return slot
restore saved registers and execute recovered suffix
```

Only the concrete ROM return/command data changes between sites. The Python
activation retains its entry; there are no resume tokens or persisted records.
The existing dispatcher loop now accepts those site facts. A foreign stack
activation is bypassed; a matching-stack corrupted frame fails closed.

Snapshots remain safe at entry/exit or after explicit handback to original code.
A portable snapshot during the active synchronous call is rejected. A deadline
inside sound retains the committed prefix and hands the remaining original
continuation back without delaying input. A suffix admission refusal also falls
back locally. No new snapshot format or scheduler exception was introduced.

One native capacity limit was raised: `al_gates` accepts up to 64 addresses instead
of 16. The family needs 19 base gates. The vector representation and all execution,
timing, device and snapshot code are unchanged. The pre-change DLL is preserved
in `artifacts/lifecycle/baseline`. Ordinary Python edits still require no build.

## Lightweight recovery-cost log

These are qualitative development observations, not fabricated time sheets.
Semantic work and new protocol work are deliberately separated from new numeric
recipes. The latter remained manual even when they reused a known pattern.
The rows group meaningful work units, not ten separate commits: the initial
sound/retirement variants were explored and qualified together, followed by
relocation, companion allocation, shared retirement and capped-state expansion.
There are no measured per-region person-hours. Sequential reuse is particularly
clear in the two pool operations and in extending the same sound dispatcher.

| Step | Semantic work | Reused machinery | New manual machine work / result |
|---|---|---|---|
| 1. Flag +25 retirement | Identify ordering, accumulator width and alternate template | Pair/buffer/init composition; synchronous sound frame; exact witness | Site addresses and straight-line sums. Parameterized the existing retirement recipe; no new return protocol |
| 2. Byte-counter +25 | Preserve byte wrap and distinguish its X effect from the later word addition | Same retirement and sound path | One existing-ADD flag calculation, reused in a shared width-aware helper. No new seam |
| 3. Secondary-pool relocation | First free slot, full-pool behavior, 66-byte copy, source deactivation | AtomicPlan, checked RAM, original-byte fixtures, stack byte writes | DBRA cost/count and final A5/D0/D7 recipe; one A1 save residue. New numeric recipe, no scheduler/continuation mechanism |
| 4. Plain/reset +15 and secondary decimal | Counter address, reset ordering, blocked return, rollover | Same counter semantics, retirement, sound and test harness | Fixed branch/call sums and two short-return contracts; no new protocol |
| 5. Quarter-threshold collection | Four-subunit threshold, wrap, conditional sound/increment | Decimal helper, byte ADD flags, +15 retirement | Another branch recipe; sound protocol unchanged |
| 6. Flag/transition pair | Which flag differs; source script/transition-word changes | Same frame, native sound and return-only suffix | Two address substitutions, one shared path recipe; no new machine concept |
| 7. Retirement-before-sound +100 pair | Reverse service/retirement order; post-sound accumulation and flag | Existing retirement/template body and same sound frame | Composition must save the already-updated A6; shared word-ADD CCR. One recipe reused for both entries |
| 8. Companion activation/allocation | Primary pool, source occupancy, full case and position inheritance | Step 3 pool search; template initialization; same sound seam | Same 40-cycle/four-instruction skipped-slot pattern; final MOVE flags and endpoint constants. Read-after-write issue resolved semantically |
| 9. Capped state publication | At 99, publish byte +52 using signed word +50 into table `FFAE87` | Checked spans, byte effects, original witnesses, same retirement | Preserve low D0 when publication occurs; aggregate saved-register path. No new persistence/return mechanism |
| 10. Share permanent retirement source | One semantic accumulation/clear/init unit used by all replacement callers | Existing semantic helpers and boundary validation | Internal effect construction consolidated; external exact adapters retained |

No production carrier code was generated in this phase. Disassembly and original
execution measurements supplied mechanical evidence; `_bytes`, shared field
expansion and existing AtomicPlan admission supplied reusable mechanics. The
straight-line/path constants and register endpoints are still handwritten.
Capstone was used only as a local inspection tool, not a runtime or test dependency.

New protocol count did not grow with the handler count: all sound sites retain
one frame/return contract, one snapshot rule and one scheduler-admission route.
The new gate-capacity limit is a fixed capability change. This does not mean
machine work became zero: arithmetic flags, branch sums and loop endpoints still
required attention for each distinct shape.

Useful corrections during qualification were an omitted final CCR propagation
on a silent return and an overly broad global exclusion that incorrectly rejected
real buffers at `FFF042`/`FFF04B`. Both were fixed within the existing contracts.
No equality mask or new verification path was used to make them pass.

## Verification and coverage limits

The original-only census of the user's 225.02-second recording finds:

- 78 primary-counter entries (already covered in 0.8, now shared by `lifecycle`);
- four byte-counter/+25 entries;
- one flag/+25 entry, including a linked-object retirement;
- three secondary-pool relocation entries.

The other family entries are not exercised by this recording. Their supported
branches are qualified using the original ROM bytes in constructed machines:
sound on/off, counter rollover/caps, byte/word carry and overflow, linked/null
buffers, blocked entry, every secondary slot, primary search/exhaustion and an
initially inactive source in the searched pool. Sound stubs deliberately clobber
saved registers in these fixtures. They do not stand in for real sound evidence.

Every strict fixture compares the complete native snapshot and PCM at the outer
exit and after 150 further original instructions. No stack bytes are excluded.
The new recorded witnesses additionally compare frames, safe-exit restore in a
fresh process, and original-vs-candidate replay. Wrong-result, wrong-return and
wrong-timing controls are rejected; an input inside original sound is delivered
at the exact original tick with local handback. Frozen 0.6 tests remain intact.

Final measured results are recorded in `artifacts/lifecycle`: `final-witnesses`,
`full-final`, `edit-loop-final`, and `summary.json`. `economics` retains the earlier
same-DLL 0.8 comparison before the capped path was added. It is intermediate
evidence; final source hashes and counts come from `full-final`.

Final qualification: **345 Python tests, seven native suites and 19 frozen 0.6
tests pass**. Full replay: **225 observations PASS**, original terminal state,
frame and whole PCM unchanged. Compared with 0.8, pair gates fall 13 -> 8 and
initializer gates 967 -> 962; three relocation entries now execute in Python.
Fallbacks remain four. Execution crossings are 35,248 -> 35,260, and measured
API crossings 247,180 -> 247,182. Increased stops/crossings reflect the newly
owned entry/return paths, not new internal helper bridges. The gate set is 7 ->
19; replaced instructions are 58,652 -> 58,983 on this particular recording.
Existing plan-reported direct composition rises 1,619 -> 1,738, including the
new shared retirement helper; this is not a count of newly recovered mechanisms.

The recorded flag/+25 witness owns 97 instructions with direct linked cleanup
and initialization; its previous 0.8 path replaced 81 through separate helper
entries. Both make ten measured execution crossings, while API crossings fall
98 -> 84 in the intermediate same-witness measurement. Wider synthetic paths
also include threshold branches and pool loops. No claim is made that every
handler appears in the user's recording.

The final edit loop measures 0.677 s for PASS and 0.624 s for DIVERGENCE with
unchanged DLL hash `26c56f7e63caa2ef885bc73dc7957f8bc8dddde3388a283e93f77ea579d630d9`.
The intermediate full comparison took 65.47 s versus 67.48 s for the baseline;
these single samples do not establish a speedup. No exact wall-time claim is
attached to the subsequent final full run. Production scaffolding grew; no LOC
ratio was used to choose the decision below.

The strict outer contract remains machine-local/carrier-boundary equality. The
separate byte-image test checks a named semantic projection; it does not relax
production comparisons. Audio and scheduling remain original-machine services.

The installed 0.9.0 package also passes the focused comparison. Its Python module
hashes match the checkout, and native source identity/build options match the
qualified development DLL. The packaged PE binary has a different binary hash;
both receipts are retained. Packaging is outside the Python edit-loop timings.

## Retrospective and next decision

**CONTINUE + MECHANIZE.** Across this family, new machine protocols did not keep
appearing. Later steps mostly required game-state/control-flow reasoning plus
new numbers in familiar machine recipes. The two pool searches and the repeated
two-call sound sites provide multiple real examples of reuse. This is enough to
justify continued expansion; it is not proof that unrelated subsystems will have
the same cost.

On the five new recorded sound paths, pair and initializer entries became internal
calls. Their gates remain necessary for other original callers. Relocation owns
the search and copy as one admitted operation. The old counter helper and capped
publication call are also internal. Whole-game cold start, device independence
and complete surrounding-dispatch ownership remain future work.

The next justified automation is narrow: derive/check the repeated sound-site
addresses and straight-line cost sums from verified instruction sequences, and
cross-check the shared search-loop cost formula. Preserve independent native
qualification. Do not build another continuation system or general effect IR.
The amount of handwritten compatibility source increased substantially; the
stream of novel machine protocols did not. That is the relevant positive result.

## Reproduce

From the repository root, with the existing Windows build and supplied USA ROM:

```powershell
$env:PYTHONPATH='src'
$env:ALADDIN_NATIVE_LIBRARY="$PWD/build/libaladdin_native.dll"
.venv/Scripts/python.exe scripts/lifecycle_probe.py
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/collection_witness.py --output artifacts/lifecycle/new-witnesses
.venv/Scripts/python.exe scripts/edit_loop_check.py artifacts/lifecycle/new-witnesses/1AF3C2/witness.alreplay --candidate lifecycle --output artifacts/lifecycle/new-edit
.venv/Scripts/python.exe scripts/dev.py compare recordings/current/20260912T210640.729016Z.alreplay --candidate lifecycle --diagnostics --output artifacts/lifecycle/new-full
.venv/Scripts/python.exe scripts/carrier_v060.py test
```
