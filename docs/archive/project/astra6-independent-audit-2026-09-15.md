> **Historical document** (archived 16 September 2026).  Kept as written: its
> commands, paths and names are those of its day.  The current replacement is
> named in [../README.md](../README.md); the lessons are summarised in
> [../../aladdin/convergence.md](../../aladdin/convergence.md).

# Independent audit: recovery, native execution and verification

**Date:** 15 September 2026  
**Audited HEAD:** `5049f6bc1512cb6f6d873f29f65636a686867989`, **including the working tree**.

**Latest source reread:** 13:56 CEST. Concurrent edits continued during the audit; see the revision qualifications below. This is not certification of an atomically frozen checkout.

## Executive assessment

**This is a legitimate emerging source port, but its current verification does not establish an independently timed, standalone game.** The new code contains substantial recovery of real game structure. It also contains duplicated implementations, unqualified branches and a feedback path from the oracle into native execution. During the audit, concurrent edits extended that feedback from transition timing to input selection on every frame. Those problems need attention before another large expansion of native code.

The right next phase is **verification repair followed by targeted subsystem recovery and integration**, driven by failures of continuous native execution. Restarting the old fallback grinder would optimize the wrong frontier.

### Direct answers

| Question | Assessment |
|---|---|
| 1. Does the growing native implementation look legitimate? | **Yes, as an emerging port.** Scripts, templates, collision, player control, map strips and transitions have recognizable original-code structure. An audit run carried native RAM through 6,100 main-loop iterations and a life loss under the earlier inspected harness; a later edit changed that harness. It is not yet an independently bootable, fully verified game. |
| 2. General game behavior or replay recovery? | **Mostly general behavior, with a significant timing qualification.** HEAD had explicit replay-frame transition tables. The working tree removes those tables, but uses a live oracle clock for transition timing and, in the final inspected version, every frame's input sample. This is an improvement in recording generality, not independence. |
| 3. Which replay pieces are acceptable? | Immutable input histories, fixed-history fixtures, read-only observation checkpoints and explicitly limited seeded tests are appropriate. Production transition tables keyed by absolute replay frame are defects. An oracle-fed clock is acceptable only as a clearly identified diagnostic experiment; its results cannot certify an autonomous runtime. |
| 4. Did the grinder stop too early? | It reached a reasonable stopping point for its bounded gate-based task. **It did not finish the behavior needed by a standalone runtime.** Significant systems already exercised by the old recording were outside that task's frontier. |
| 5. Another grinder now? | **Yes, after tightening the native verification contract**, as a targeted recovery campaign over missing subsystems and branches. Its frontier should be native gaps, independent divergences and unowned executed routines, not fallback totals. |
| 6. How much native gameplay is oracle-grounded? | A substantial core is grounded, and carried RAM execution supplies meaningful evidence. There is no defensible percentage of fully verified gameplay. ROM references, registered callbacks and old lifecycle PASS results are not equivalent to branch-complete native qualification. |
| 7. Biggest architectural risk? | **A split between the semantics that were historically proven and the semantics now running natively, concealed by an oracle-assisted, RAM-only success criterion.** Fixes can land in one implementation without qualifying the other; timing and output errors can escape the newer checks. |
| 8. What next? | Make oracle observation non-causal for an independence check; restore reliable coverage/provenance/failure reporting; reconcile duplicated semantics; recover the first missing connected routes; compare carried video state and sound events; then extend continuous coverage across histories. |

## 1. Scope and evidence discipline

### Observed facts

The starting working tree modified ten tracked files: the semantic map, four verification/witness scripts, messages, contacts, native frame, sequences and state. It also contained untracked `scripts/route_census.py` and `src/aladdin_sega/native/replay.py`. I inspected these current files, not just HEAD. In particular, **the `TRANSITION_TIMING` table in HEAD is absent from the current sequences implementation**.

**Concurrent-change qualification:** This checkout was not frozen. During the audit, `docs/native-frontier.md` appeared, and the final hash comparison found further changes to `scripts/native_replay.py`, `scripts/route_census.py`, `scripts/transition_witness.py`, `native/frame.py` and `native/replay.py`. I did not make those edits. I read their updated contents and incorporated them below. Runtime evidence is explicitly separated into before and after that change; the longer run must not be attributed to the final harness revision.

**Latest observed regression, at the 13:56 reread:** Another edit introduced `native_replay.arm` and removed `OracleClock.begin`, `_align`, `checkpoint` and `end`, while retaining the base `ReplayClock` methods that raise `NotImplementedError`. `sequences.run_transition` still calls `state.replay.begin(kind)`. Therefore the latest inspected class cannot execute the transition-clock path that passed earlier checks: it inherits the abstract failure. The detailed transition-alignment analysis below refers to the implemented clock inspected earlier, and remains relevant to the proposed architecture; it is not a claim that the removed methods are still present. The per-frame oracle input sampler remains present. This additional regression makes a frozen, qualified revision the immediate prerequisite for any completion claim.

I read the frame pipeline, state/services/VDP, sequence composition, script engine, contact and spawn systems, representative player/control/flow/asset code, old recovery adapters and qualification tests, native verification tools, history identity/cache machinery, recent changes, and existing cartography and verification evidence. I compared representative operations with the original disassembly and directly checked selected instructions in the verified ROM.

This audit did not run the full test suite, build, generate fixtures, capture snapshots, start recovery workers or modify code. Runtime checks used `python -B`, existing snapshot **reads**, memory-only execution and console results. The report is the only file I created. Git inspection used a command-local `safe.directory` exception and disabled optional status locks; no Git configuration was changed by this audit.

Identity anchors:

| Item | Identity |
|---|---|
| ROM SHA-256, checked against actual bytes | `a3779fc77994780e80d05bb557f800110d0398d34b951baa8c0a14910014ded3` |
| Existing native DLL SHA-256 | `26c56f7e63caa2ef885bc73dc7957f8bc8dddde3388a283e93f77ea579d630d9` |
| Frame-fixture history | `44223150b7d6c5664d90f908d765542d89565a8557a8e88b392948998e579fde`, ending at 82,161 |
| Current history `main` | `24c70ffcc5d58108ec539c43e15f307bf0e756add82736ab2463d66fa925c6e3`, ending at 9,811 |
| Earlier audit source inventory digest | `4cf4ac4f219709e1cf0a5ff1733f99982c02ba08ab370cef8263933109e12f84` |
| Intermediate inspected inventory, with per-frame oracle input sampling | `c21e6276d5fe31395b44debe6bef0684dd827454936e8aa5a83b30f4ffc72f0f` |
| Latest inspected inventory, with `arm` and missing transition overrides | `5d6d36cee8bce948d3ad5d2d13d42a14c299b129dadee50840428697f71177c6` |

The inventory digests hash compact, key-sorted JSON mapping relative paths to SHA-256 hashes for `.py`, `.md` and `.txt` files under `src`, `scripts`, `tests` and `docs`, excluding this report. They identify inspected source inventories, not gameplay qualification receipts. Five files changed between the first two inventories; the frontier document and three scripts changed again before the third.

### Fresh, bounded execution evidence

I reconstructed masks from the pinned history using the existing history validation/flattening code without invoking its filesystem-creating constructor. Each comparison carried native state forward and checked RAM after every main-loop iteration using the current `BOOKKEEPING` exclusions. **The following longer checks used the earlier harness, which applied oracle input at VBlank interrupts.** The final revision changes oracle input application to canonical frame-wrap ticks; these earlier matches must not be promoted to canonical-input verification of that revision.

| Starting fixture | Result | Qualification |
|---|---|---|
| `f69586.state` | 100 iterations matched, native frame 69,585 → 69,685 | Replay clock explicitly disabled; ordinary gameplay only. |
| `f69586.state` | 6,100 iterations matched, native frame 69,585 → 75,844; transition 75,278 → 75,438 | Oracle clock enabled. Includes one life-loss sequence, but does **not** independently verify its timing or intermediate video. |
| `f8500.state` | 1,517 iterations matched, then `NativeGap` at frame 10,018: `transition_countdown`, level change at `1A8E5C` | Existing old-history route, not newly recorded behavior. |
| `f11079.state` | 179 iterations matched from boundary 11,080, then `NativeGap` at 11,259: level event E7, handler `1B7840` | Existing old-history level-2 behavior. |
| `f75100.state` | 400 iterations matched after seeding at boundary 75,182 | Seeding itself advanced the oracle substantially. This sample does not prove the skipped interval or the documented death at 75,278. |

On the **intermediate inventory**, I repeated a 100-iteration sample from `f69586.state`. It matched with the new oracle input sampler enabled. With `state.replay=None`, the first comparison differed in eight RAM bytes, including the frame counter, RNG and script-related state. This did not demonstrate independence; I did not resolve whether that short discrepancy originates in boundary alignment, timing or semantic execution. The subsequently added `arm` helper changes boundary handling again, so this discrepancy is not assigned to native gameplay or asserted unchanged in the latest revision. A separate probe reproduced **`NativeError: Machine is closed` on the first frame** with the clock attached to a closed machine, matching the still-present `--native` driver's configuration.

Two memory-only probes also reproduced definite findings:

* `flow.tick_level_11` with frame-counter zero, player position `(0x100, 0x150)` and a free object pool raises **`TypeError: keywords must be strings`** on its spawn branch.
* The ROM player callback table maps kind `3B` to `1AF21E`, which the current native registry rejects with `ContactGap`. The related implementation is registered at `1AF228`, an internal entry after the sword-active guard.

**Limits:** These checks are evidence for selected paths and the inspected checkout. They are not a full-history native PASS, complete oracle independence, full-game branch coverage, or video/audio equivalence. I did not independently repeat all eight deaths, continue/prologue routes, input perturbations or newer-history routes described in the docs.

## 2. Game recovery versus replay recovery

### Observed facts: legitimate state and data

The ordinary `game/` modules generally consume current RAM-like state, current pad values and ROM data. Examples include:

* `player.ground_collision`: collision attributes and the ROM height map, not a replay trajectory.
* `control.pressed`: the game's configurable button-routine pointers mapped to semantic pad readers.
* `flow.tick_level_5`: spatial zones, the game's byte frame counter and RNG. Periodic behavior based on `FF7E28` is legitimate game state, not an absolute recording timestamp.
* `pad.attract_input`: the **original ROM's attract demonstration stream**. This is game data, despite being prerecorded input.
* `sequences.lives_display`: the original `0x103` countdown and `0xD2` skip threshold. I checked the original instructions at `1B280A..1B281A`; these constants are not inferred death timestamps.
* `compress.VERIFIED_DIGESTS`: expected asset output hashes consumed by tests. They do not drive gameplay or substitute decoded output.

The RAM layout, ROM addresses, routine registries and fixed templates are not themselves evidence of replay overfitting. I found no current table of future player positions, scores or deaths being copied into ordinary game modules.

### Observed facts: the timing defect changed form

At HEAD, `native/sequences.py` contains `TRANSITION_TIMING`, keyed by eight absolute frames such as `75278` and `79293`, with expected transition kinds, durations and wait counts. That is genuine replay-specific behavior in the runtime, not an original game constant.

The working tree removes that table. Before the latest removal of transition overrides, its implemented feedback path was:

1. `scripts/native_replay.seed_at_boundary` attaches `OracleClock` to `GameState.replay`.
2. `sequences.run_transition` calls its `begin` and `end` methods.
3. `NativeServices.checkpoint` calls its `checkpoint` method.
4. `OracleClock` executes the original to selected PCs, obtains its VBlank count and calls `state.advance_frames(...)`.
5. `advance_frames` runs native VBlank RAM effects and changes `state.buttons` through the recorded-pad provider.

This is a causal input from the oracle. A memory-only `_align` probe changed `(frame, buttons, any-button latch)` from `(10, 0, 0)` to `(12, 64, 255)`. The checkpoint is therefore not merely an observation marker. No RAM block needs to be copied for oracle-derived timing to change gameplay.

**The final inspected version adds a second, broader path:** `run_frame` calls `state.replay.sample_input()` before running its steps. `OracleClock.sample_input` runs the original to controller-read PC `1A8CEE`, then selects the recording's input mask using the original machine's tick. Thus native input selection now depends on original gameplay execution even on ordinary frames. This is not copying a prerecorded outcome, but it violates the independence of the input/time service that the intended architecture requires. The final 100-frame match was obtained with this assistance.

### Strong conclusions

**The current code is less tied to one recording than HEAD, but its demonstrated replay mode depends on the original for transition timing and controller sampling.** Replacing a measured table with an oracle query removes stored replay identity; it does not establish an independent timing implementation.

Oracle-aligned testing remains useful for asking, “Given this alignment and these sampled inputs, did we reconstruct the operations?” It cannot also answer, “Would the standalone runtime reach these states under the original input sequence on its own?” Those must be separate claims.

The runtime with `replay=None` avoids this feedback, but omits work time spent on decompression/drawing. With time-indexed inputs, faster transitions can change button sampling and route choices. “The game just runs the transition faster” is a source-port timing policy, not proof of the requested replay-equivalent behavior.

### Risks and required distinction

Acceptable temporary scaffolding includes pinned input histories, explicit initial-state seeding, diagnostic oracle clocks with qualified results, and checkpoint collection that does not affect execution. Architectural defects include replay-frame tables in gameplay, treating an oracle-fed clock as an independent platform implementation, and using aligned RAM results as proof of unaligned timing.

A general solution needs an explicit timing/input contract whose runtime behavior derives from state, input, recovered data and independent services. For compatibility with these recordings, work-time accounting or scheduling must preserve the relevant input/interrupt boundaries without asking the oracle what happened on this run. Simply moving the current alignment hook to another directory will not achieve that.

## 3. Provenance and the speed of native growth

### Observed facts

The volume is real: commit `2df82e4` added 3,237 lines across main-loop systems, and `d65a45f` added 1,517 lines around camera, player, map and spawn behavior. Before the concurrent final edits, the `game/` directory had 7,200 lines and `native/` 1,806, including comments and compatibility semantics. Line counts explain the audit concern; they are not a measure of recovered behavior.

There is substantive provenance behind that growth:

| Area | Evidence path | Where the chain weakens |
|---|---|---|
| Templates and object state | ROM template expansion → `lifecycle.initialize` → `RecordView` / `ObjectTemplate` → engine, spawn and sequences | Allocation/retirement behavior around the shared initializer has multiple owners. |
| Animation and motion | Original dispatcher/handlers → decoded script operations → `Engine` → frame wrappers → boundary tests and carried RAM runs | Tests omit some handoff-owned object differences; not every script/native-call branch is qualified. |
| Player, camera and map strips | Original listings and lookup tables → semantic modules → frame composition → per-step logs and continuous RAM | Per-step coverage has dispatch flaws; long logs lack current source/history receipts. |
| Asset decompression | Original decompressors → explicit Huffman/LZ implementation → seven pinned output digests and tests | The digest provenance is asserted in comments; the referenced ad hoc verification producer is not a durable checked-in tool. Seven assets do not prove every asset or VDP state. |
| Life loss | Original helper listings → fades/mini frames/retirement/draw/reinitialization → sequence composition | Fresh evidence includes one carried transition, but timing is oracle-assisted and intermediate ports are not compared. |
| Continue, story and later-level code | Original routine/data references and readable reconstruction | Much weaker branch-level evidence. Some branches are only described as listing-derived, and concrete untested code failures exist. |

For example, `contacts.bottle_pickup` follows `1AE64C` closely: save player screen X, align it with the object, retype to `8A`, set script `124454`, save the checkpoint, play sound `63`, restore screen X. The original listing supports this sequence. Likewise `sequences.mini_frame` follows the original motion → animation → sprite table → VBlank → uploads order. These are not generic platformer guesses.

### Strong conclusions

**Most inspected core code is best characterized as original-code reconstruction with varying amounts of oracle qualification**, rather than speculative game design. There is also real composition of proven pieces. However, “names an original PC” is a provenance starting point, not a completed proof chain.

The later-level spawn failure illustrates the difference. `flow.tick_level_11` follows the original zone and spawn routine at `1B6258`, yet calls `_spawn(..., **{9: (...)})`. Python rejects integer keyword names before the helper can run. The same pattern appears in `tick_level_7`, `tick_level_9` and `tick_level_12`. This is faithful-looking reconstruction with an unexecuted implementation defect, not a general verified subsystem. It also escapes the advertised precise `NativeGap` reporting.

**Uncertain:** There is insufficient evidence to label all unexercised branches speculative, or to assign a percentage of native lines that are oracle-proven. The appropriate missing artifact is a routine/branch qualification inventory, not a guessed recovery percentage.

## 4. Architecture: promising structure, but two semantic paths

### What is working

* `GameState` owns native RAM, ROM, an event stream and VDP state. With the replay service detached, frame execution does not call `Machine` or execute an unrecovered callback on the original CPU. The attached oracle sampler is the important exception described above.
* `Step` records the original boundary and the semantic callable. The per-step verifier and native frame runner use that same callable. This is a useful shared-implementation design.
* `RecordView`, script operations, templates, sprite pieces, level data and named player fields are emerging domain structures. Keeping a RAM backing store is a reasonable migration step.
* Unknown contact callbacks and script native-call targets stop execution through native services. They are not silently handed to a 68000 fallback by the core runner.
* Sound requests are explicit semantic events. The fact that their final platform implementation is incomplete does not require preserving original gameplay execution.

### Observed split in semantic ownership

The historically verified lifecycle candidate still flows through `recovery.py` → `boundary.py` → `recovered.py` → older `game.objects.contact`, `collection` and `lifecycle` functions. New native contacts largely flow through **`game.objects.contacts`**, player helpers and a new scan implementation.

Concrete duplication:

* `contact.contact_type43_update` and `contacts.bottle_pickup` implement overlapping `1AE64C` state changes; the native function does not call the older semantic operation.
* `collection.collection_state` owns progress/counter/flag operations used by old boundary plans. New `_progress`, `_level_flag_item`, `gem` and other handlers implement overlapping behavior separately.
* Spawn placement/allocation and release behavior have older qualified recipes and newer implementations in `spawn.py` / `Engine`, sharing only some primitives such as template initialization and RNG.

The gem wrapper is a particularly clear integration gap. The old `COLLECTION_ROUTES` recognizes `1AF21E`; the old full-recording receipt records **13 entries** there. The native registry recognizes `1AF228` instead. ROM kind `3B` selects `1AF21E`, whose sword-active guard precedes the existing gem body. This is already-recovered behavior missing from native composition, not evidence that another recording must be collected.

### Strong conclusions

There **is** one implementation shared between the newer per-step oracle checks and native composition. There is **not yet** one semantic implementation shared across all old recovery qualification and new native gameplay. Consequently, the old PASS history cannot be inherited wholesale by the newer implementation.

This is repairable: converge proven operations at the semantic layer, leaving register/stack/cycle adaptation in boundary machinery. Do not rewrite thousands of lines simply to remove addresses. First make each mature behavior have one owner and a contract tested from both relevant adapters.

`spawn.site` deserves a precise label. It decodes a bounded subset of original spawn-caller instructions into named operations, and `run_site` executes those operations with explicit rejection of unsupported instructions. It is not an unrestricted 68000 fallback. It is nevertheless a small runtime translation/interpreter layer with condition flags, instruction-shaped locals and a Capstone dependency. Extracting qualified `SpawnSite` data is a plausible route to removing that machine-shaped adapter. “All callers decode” alone does not prove their branches, pool exhaustion or flags.

### Current standalone limitations

`seed_cold` explicitly lets the oracle perform boot/title work before copying RAM at a gameplay boundary. The normal play command still uses the Genesis history/session backend. Native VDP state has no integrated full-game renderer or sound-event playback path demonstrated here.

There is also a direct driver bug: `native_replay.native()` seeds a state with an attached `OracleClock`, then closes its machine before running native frames. In the final version, the **first frame's `sample_input()`** calls that clock against the closed machine (previously it failed when a transition needed the clock). The remedy is not to keep an undisclosed oracle alive in “native” mode; that mode needs an explicit independent service configuration.

The live-input migration also needs resumable transitions: `continue_screen` loops synchronously until left or right. With `replay=None`, no pad provider and neither direction held, the caller cannot deliver a later `run_frame(buttons=...)` while that call is blocked. An input/time service or yielded sequence is needed for a usable interactive runtime.

## 5. Verification: stronger at the old boundary than at the new one

### 5.1 Historical qualification is real but belongs to its implementation

`artifacts/audit-frontier17/comparison.json` contains a historical PASS for the 82,161-frame lifecycle run, zero restores, 92,588 candidate hits and 137 fallbacks. It compares strict Genesis state, frame output and PCM with implementation receipts. The old tests also include varied branch inputs and mutants intended to demonstrate that wrong results, continuations and timing are detected.

This is substantial evidence for that recovery architecture. During this audit, `verify_status.classify` correctly returned **`STALE_EVIDENCE`** for that directory against the current checkout. The source identity differs. The stored PASS is historical evidence, not a present native certification.

The 18,133,788 replaced instructions are roughly 2.15% of 841,993,642 total instructions. That ratio includes idle/platform work and is not a gameplay-completion percentage. Nor does 137 fallbacks mean only 137 pieces of original behavior remain: unarmed regions never enter the fallback denominator.

### 5.2 Per-step checking skips coverage and can exit successfully on errors

In `native_replay.verify`, after running the oracle to a step's exit, the loop bypasses the gate at that exit. When the exit is the next step's entry, this skips that next step's verification on that traversal. `test_frame_steps` has the same pattern. The existing `verify_loop_long.log` reflects this: its tallies omit several intervening steps rather than demonstrating all 36 calls.

Further limitations:

* `native_replay.verify` returns zero after printing mismatches and gaps.
* `verify_step.py` prints mismatch/gap counters without making them a failing process result.
* `test_frame_steps` checks only the first six numerically sorted fixtures, over two frames; it gathers `NativeGap`s without requiring their absence. It can skip when nothing is checked and breaks on a bracketing `RuntimeError` without requiring complete coverage.
* `test_script_engine` excludes whole object records associated with non-upload handoffs. That is a valid partial ownership test, but cannot certify those objects' complete behavior.

**Conclusion:** Current “recovered steps” and successful process exits can overstate exercised native behavior. Required boundary/branch coverage and failure status must be explicit before expanding this system.

### 5.3 Whole-frame RAM equality leaves important output blind spots

`native_diff` compares RAM after each main-loop iteration, using these half-open exclusions:

| Excluded range | Current label | Audit assessment |
|---|---|---|
| `FF769A..FF7A00` | DMA queue | Gameplay-generated output consumed by video uploads. Excluding it without an equivalent carried output comparison can hide missing/wrong sprite uploads. |
| `FFED00..FFEFDC` | Stack and decompressor scratch | Plausible representation-specific exclusion, but needs boundary-specific evidence that omitted data cannot affect future semantic behavior. |
| `FF7D9A..FF7DA3` | Continuations | Includes the engine's channel flag `FF7DA2`; its semantic replacement/irrelevance should be documented explicitly. |
| `FFEFEE..FFEFF0` | Queue counters | Active video-queue state; same concern as the queue itself. |

The masks differ between the frame scripts, engine tests and frame-step tests. A broad name such as “bookkeeping” does not establish that a field has no semantic or visible effect.

The newer VDP-writing steps can compare ordered port words, which is valuable. However:

* Whole-frame `native_diff` does not compare `vdp.log`, VRAM/CRAM/VSRAM/registers, rendered frames or sound events. It only prints an event count.
* `Step.ports` covers the initial upload/scroll steps. Other calls can write video, including contact sword clashes, level ticks, messages and transitions; their normal step checks do not automatically compare those ports.
* `GameState.from_machine` copies RAM only. `Vdp` begins with empty video memories and mostly zero registers, not the oracle's current video state. Port equality from an isolated step does not establish equal initial or final video state, DMA contents or timing.
* Fades read native CRAM into RAM. This makes video state part of future semantic computation, not merely an unimportant presentation buffer.
* Sound event IDs, order, flush distinctions and timestamps are not compared to original sound requests. The old candidate's PCM equality does not qualify these new event emitters.

**Conclusion:** The current ladder meaningfully tests many player/object/script fields and RAM sprite-table construction. It does not yet prove whole-frame visible output, transition rendering or native sound semantics.

### 5.4 Transition checkpoints do not prove the claimed route or timing

In the implemented clock inspected before the latest regression, `OracleClock.checkpoint(pc)` gates only the requested PC and VBlank, then runs until that PC or a generous timeout. It does not observe all alternative checkpoints or require this PC to be the next semantic event. An oracle route can take extra unobserved work and later rejoin the requested PC. The latest class instead inherits `NotImplementedError` here, as noted in the scope section.

`_align` rejects native arrival later than the oracle but pads earlier arrival to the oracle's time. Missing waits can therefore be absorbed by alignment. `end()` aligns the resume boundary similarly. This is useful diagnostic synchronization, not symmetric timing verification.

`ComparingClock` compares RAM at reached checkpoints, but inherits this behavior. `verify_sequence.main` also accepts `die_pc` without using it to assert the transition entry and does not perform a final RAM comparison at the resumed main-loop boundary. Native checkpoint RAM agreement is narrower than an end-to-end transition PASS.

**Risk:** A changed route that rejoins, missing work time, or wrong intermediate video can survive these comparisons. Checkpoint sequence/order, consumed inputs, interrupt events and resume state need independently observed contracts.

### 5.5 History identity improved; fixture provenance remains weak

The underlying history model is good: canonical events contain only `{frame, buttons}`; immutable node identity derives from input and duration, with presentation and machine caches kept separate. The established cold verifier resolves `main` once and sends the resolved ID to its workers.

The native tools now default to the frame directory's `history_id`, not the moving `main`. This matters: the two currently name different recordings, one ending at 82,161 and the other at 9,811. Using the latter for old late-game fixtures would feed mostly default-zero masks beyond its end.

However, `frame_states.py` writes snapshots from the initially resolved `main` into shared `fFRAME.state` names, and writes a **second resolution of `main`** into the directory marker at the end. It neither namespaces fixtures by history nor binds every existing fixture to the marker. A subset regeneration can mix histories; a ref change during capture can mislabel all newly written files. Snapshot format/ROM validation does not establish input-history provenance.

Other gaps: native results lack the older verifier's source/fixture receipts; ID prefixes select the first matching node rather than requiring uniqueness; input exhaustion defaults to zero; and `native_diff` reports an ending frame as `seed + count` even though nested waits make that inaccurate.

The semantic map is also internally stale: it mentions nonexistent `native/witnesses.py`, `--measure` and `--auto` workflows, older callback counts and early incorrect routine identities alongside later corrections. These are reasons to distrust its completion claims until reconciled, not reasons to discard the underlying cartography.

The concurrent edits introduce `run_with_pads`, applying masks at frame-wrap ticks as `history_runtime.step` does. That is a necessary distinction from the earlier VBlank-based oracle feeding. However, solving the native side by asking the oracle when its controller read occurred creates the feedback problem above. Input-instant corrections also invalidate assumptions behind previously reported aligned runs unless requalified.

## 6. What the fallback grinder left behind

### Classification from current evidence

| Category | Concrete evidence | Consequence |
|---|---|---|
| **A. Recovered behavior composed incorrectly or incompletely** | The missing `1AF21E` wrapper despite old qualification and 13 historical entries; duplicated contact/collection semantics; invalid later-level `_spawn` calls | Reuse/reconcile existing semantics and qualify native composition. Do not treat every native gap as fresh discovery. |
| **B. Verification/replay/timing infrastructure** | Oracle-clock feedback; closed-machine native driver; skipped step gates; RAM masks/output omissions; fixture-history marker weakness | Repair the contract before trusting increasingly long PASS-like runs. |
| **C. Existing-recording behavior never recovered by the old grinder** | Fresh gaps at old-history level change 10,018 and level event 11,259; original main-loop/script/loader/outer-flow ownership absent from the old gate frontier | Substantial. Recover connected systems already present in available evidence. |
| **D. Behavior exposed only by newer recordings** | The newly read `docs/native-frontier.md` attributes bounce/hurt callbacks to histories `2dddf860` and `24c70ffc`; this audit did not independently trace those novel branches | Some D work is reported, but it is not established as the main cause of today's blockers. |

The grinder protocol deliberately focused on bounded branches, recognized seams and measured costs, escalating larger/device-owning regions. Its gate set and refusal counts could never enumerate the full main loop, loading sequences or all script services. The later discovery that “command-stream” fallback time included VBlank waiting, while the real object interpreter lived elsewhere, demonstrates the limitations of ranking by fallback label alone.

**Strong conclusion:** Category C is substantial, with important A and B failures alongside it. Finishing the original protocol was not finishing the game. Its stopping decision was reasonable within its scope; interpreting that as readiness for full standalone composition was not.

### What should drive a targeted recovery phase

Use an ownership frontier with, for every blocking route: immutable history and input digest, first native gap/divergence, original entry/exit, branch predicate, owning subsystem, existing semantic implementation if any, missing operation, and required verification boundary. Split A/B integration defects from C/D recovery work before assigning a task.

`route_census.py` is a useful start toward discovering unarmed execution, but not a recovery-completion oracle. It finds direct call targets and labels addresses **cited** in source. A gap stub, comment or old semantic helper counts as a citation; indirect dispatch targets can be absent from its initial target set. Supplement it with executed indirect targets and actual native ownership/branch coverage.

`docs/native-frontier.md` usefully names level-change and event-stream ownership as the next frontier. Its stronger claims are not established: “98.8% of sampled instructions in cited routines” is not native qualification, and “every remaining blocker is missing game logic” conflicts with the demonstrated driver, input-service and verifier defects. Its claim that callbacks no recording has met are all future category D also overlooks old qualified entries such as `1AF21E`.

Prioritize completion of connected native routes and elimination of unsupported behavior over instruction volume or raw hit counts. Reuse the old branch witnesses and input/state perturbation discipline; do not recreate all of the old machine-cycle plumbing for every higher-level function.

## 7. Recommended next phase and acceptance criteria

### 1. Establish trustworthy native verification first

Separate diagnostic oracle-aligned runs from independent runs in result names and receipts. In an independent run, after explicit seeding the oracle must not advance native time, choose input or update native state. Preserve the diagnostic mode because it helps localize work-time versus semantic failures.

Require mismatches and unexpected gaps to fail, and absent required boundaries to report NOT_EXERCISED. Correct step-gate traversal and assert which steps/branches actually ran. Compare sequence checkpoint order and final resumed state, not merely eventually reached PCs. Add targeted verifier mutation checks for omitted waits, omitted uploads, wrong sounds and skipped callbacks.

Bind fixtures and results to an immutable input history, per-fixture digest and capture boundary, ROM/DLL identity, current semantic source and comparison mask. Resolve mutable refs once. Record actual native iterations, elapsed VBlanks, consumed input interval and the first unsupported behavior.

**Acceptance:** A deliberately wrong semantic output, missing wait or output event cannot receive an independent PASS; each result states exactly what executed and what was excluded.

### 2. Reconcile overlapping semantics and small composition failures

Start with old recovered callbacks missing from native registries, including the `1AF21E` wrapper, and the invalid `_spawn` calling convention. Establish one owner for mature counter, pickup, checkpoint, allocation and release operations. Adapt the old machine-boundary verifier to that owner where useful, rather than silently maintaining a second behavior implementation.

**Acceptance:** Old qualified branches and their native entry wrappers both exercise the same semantic operation, including guards, exhaustion/cap behavior and service effects.

### 3. Recover the first connected missing routes

Use the pinned old recording to drive the level-change sequence from `1A8E5C` and the level-2 event dispatch from `1B634E`/its handler table, including E7 at `1B7840`. Recover the required tally/scarab/bonus/prologue work in bounded subsystem contracts as the route demands. Keep unsupported branches explicit.

Continue/prologue and high-score branches already written should be qualified on their active paths, not counted as completed because an inactive guard returns. Use perturbed inputs around skip thresholds, continue choices, inventory caps and pool exhaustion without changing production logic per recording.

**Acceptance:** Continuous native execution crosses these formerly blocking boundaries without oracle feedback or reseeding, or fails at a newly identified precise gap.

### 4. Raise output and platform boundaries

Initialize native video state through recovered initialization or an explicitly identified complete seed. Compare carried VRAM/CRAM/VSRAM/register state and sprite output, plus ordered semantic sound requests. Validate transition intermediate frames, especially fades and the sword flash. Replace queue exclusions with equivalent semantic/output checks where possible.

Define a schedulable input/VBlank/work service so transitions can receive live input and yield control while preserving the chosen compatibility contract. This is more urgent than polishing a renderer around incomplete state.

**Acceptance:** RAM agreement cannot conceal a blank/wrong screen, missing sound, wrong DMA payload or a transition that cannot accept later input.

### 5. Expand generality, then simplify representations

Run multiple immutable histories and intentional input variants through the same semantic code. Attribute each new blocker to A/B/C/D. After connected gameplay and transitions are reliable, recover boot/title/options and remaining bonus/late-game systems until oracle seeding can disappear.

Then migrate mature RAM fields into structured player/level/object state and predecode qualified spawn/script data where helpful. Preserve oracle adapters as verification tools. Do not begin a broad “clean architecture” rewrite while semantics and scheduling are still changing.

## Final judgment

The recovery work has produced something materially more valuable than a replay imitation: a recognizable, executable model of important Aladdin systems. The carried-state results support continuing toward a source port, within the revision and timing qualifications above.

The project should nevertheless **pause indiscriminate native expansion**. Its most urgent problem is the gap between what is implemented, what is actually independently executed, and what a reported match proves. Repair that gap, converge semantic ownership, and resume targeted recovery from standalone subsystem failures. The existing recordings already contain enough unrecovered behavior to justify that phase.

No recommendations were implemented as part of this audit.
