# The native path's recovery frontier (15 September 2026)

An audit of every gap and divergence the standalone native runtime has met,
classified by cause, and the frontier of original code the native path
needs next, generated from what the recordings actually execute rather than
from the old fallback frontier.

Recordings used (history node ids, all immutable):

| recording | frames | start | what it is |
|---|---|---|---|
| 44223150 | 82,161 | power-on | the original main recording (levels 1, 2, 3, 0, 4, 5; two deaths in level 5) |
| 2dddf860 | 14,249 | power-on | new: level 1 with different inputs |
| 24c70ffc | 9,811 | power-on | new: level 1 with different inputs |

The evidence snapshots in `artifacts/evidence/frames/` belong to 44223150
(`history_id`); the tools pin that id and never follow the moving `main` ref.

## 1. The invariant, and where it was violated

Native gameplay depends only on the current game state, the current input,
recovered game data and the platform services.  Recordings are inputs.  The
audit found one violation and removed it: `sequences.run_transition` looked a
transition's timing up by its absolute start frame (`TRANSITION_TIMING`) and
refused to run without an entry.  Any death at an unrecorded frame would have
been a gap in the *game*.  The witness table is gone.  What remains:

- the sequences call `services.checkpoint(pc)` where the original reaches
  `pc`; the game does nothing with it;
- the harness's replay clock (`scripts/native_replay.OracleClock`) answers a
  checkpoint by driving the oracle to `pc` and taking its VBlank count, so
  recorded input lines up with the original's *work time* (decompression,
  the screen draw), which the native runtime spends in zero frames.  Nothing
  is stored per recording; a new recording needs no table;
- `state.advance_frames(n)` runs the VBlank handler's RAM effects once per
  frame passed, whether the frame was waited for or spent working (the
  original latches "any button" from the stale pad bytes during a long
  decompression; the native must too).  This is platform semantics, not
  alignment scaffolding: a standalone game with live input passes no work
  frames and latches nothing.

Everything else in `native/sequences.py` and the game modules reads state,
input and ROM data only (`grep state.frame` finds only NativeGap reports).

Recorded input itself is applied as the recording's runtime applies it
(`history_runtime.step`): the mask for the frame interval [f, f+1) is set at
tick f * FRAME_TICKS (`native_replay.run_with_pads`), on every oracle drive;
the oracle so driven is byte-identical to the runtime at the same tick.  The
harness used to set the mask at the VBlank interrupt, which lost the
title-screen Start press of a cold start (no interrupt runs yet): the old
recording replayed from power-on never finished level 1.  The emulated
controller shows a new mask at once, and the main loop's two port reads fall
before or after the wrap depending on the work before them (one read in a
hundred is after it; once in six thousand frames the wrap falls between the
two reads), which the native runtime does not time.  So the replay clock
runs the oracle to each port read and hands the native frame the mask each
read saw (`OracleClock.sample_input`); a standalone game reads its live
controller and has no such question, and without a clock the native frame N
reads `pads(N)`.

One consequence must be stated plainly: under the earlier (interrupt-timed)
input rule the old recording's inputs landed one frame late in about one
frame per hundred, and from level 5 on that produced a different playthrough:
eight deaths, the last life lost, a continue and a level prologue.  Every
native-versus-oracle comparison of that stretch was valid (both sides ran
the same inputs), but those inputs were not the recording's.  Under the
faithful rule the recording's level-5 stretch has two deaths (frames 75050
and 81406) and no continue.  The continue screen and the level prologue thus
stand verified on an *input variant* of the recording (the same standing as
a `--pad` perturbation), not on the recording itself; the two real deaths
are verified below.

Results with all of this in place (`native_diff.py`, whole work RAM compared
after every frame):

| run | outcome |
|---|---|
| 44223150 from power-on (seeded at its first main-loop frame 1002) | **byte- and sound-exact for all 82,161 frames to the recording's end**: six levels, five level changes with the tally, scarab wheel and bonus card, the level events, three deaths |
| 44223150 from f69586 (level 5) | byte-exact to the recording's end (82,161), through its two deaths |
| 44223150 from f44827 (level 0), after the level change and level events were recovered | byte- and sound-exact for 40,000 frames to the end: levels 0, 4 and 5, two level changes with the scarab wheel, two deaths |
| 24c70ffc from power-on (seeded at 2197) | byte-exact to the recording's end (9,811) |
| 2dddf860 from power-on (seeded at 1311) | byte-exact to frame 8197, its level 1 -> 2 change (open, category 3) |

## 2. Every gap and divergence met, classified

1 = recovered logic composed wrongly; 2 = harness / oracle / timing;
3 = behaviour the old recording exercised but the grinder never recovered;
4 = new behaviour exposed only by the new recordings.

| where | what | class | resolution |
|---|---|---|---|
| 44223150 level 5: deaths at 75050 and 81406 (and eight on the interrupt-timed input variant) | respawn as nested frames: fades, lives screen, level init, redraw | 3 | recovered (1A8F82 / 1A902E / 1A9088), byte-exact at 22 checkpoints each |
| respawn, first attempt | 47-frame fade used where the original fades in 16 (1B278A vs 1B26F0) | 1 | fixed |
| respawn | 1B1F28 start-script branch order; name-row table word order; 1B28A6 counter | 1 | fixed |
| respawn | decompressor tables 0x1B0 below the stack compared as game RAM | 2 | bookkeeping region extended |
| whole-frame tools | mini frames call the main loop's first step; boundary mis-detected | 2 | boundary recognised by return address |
| 44223150 input variant, f79293 | continue screen, level card, story, level intro, loader, prologue | 3 | recovered (1B0CBC, 1B080E, 1A8B50 route) on the input variant; high-score screen from the listing only, unexercised |
| 44223150 f79293 | story checkpoint placed on a routine the level-5 path never calls | 1 | fixed |
| 44223150 f79293 | pad-polling loop started 55 frames early: no checkpoint after the loading work | 2 | checkpoints before the polling loops (1B0916, 1B1570, 1B12DE) |
| 44223150 f79293 | latch set by the ISR during decompression work | 2 (platform) | handler runs per elapsed frame |
| 2dddf860 f2041 | contact callback kind 65 (1AFBF4, the bounce pad) | 4 | recovered with kinds 66 and 4F (1AFC4E) |
| 24c70ffc f3296 | contact callback kind 7B (1AE9D4) | 4 | it is the plain hurt (1AE4F8, already recovered): registered |
| 2dddf860 f6853, 44223150 f8425 | kind-01 spring (1AFD84) launched the player from a plain landing | 1 | the new kind-65 function shadowed the existing `spring`: renamed |
| 44223150 f8425 | the same defect, in a frame no snapshot-seeded run had ever covered (f1000 reached 6700, the next seed was 8500) | 1 | cold starts now run the whole recording from its first main-loop frame |
| 44223150 f10018, f24593, f48929 | level change (1A8E5C: tally 1B0D70, scarab screen 1B16E0, sequence stream, 1A8B50 prologue) | 3 | recovered; verified at every checkpoint for the 1->2, 3->0 and 0->4 changes |
| 44223150 level 2 | level event stream handlers (1B634E over the table at 20C0) | 3 | recovered for the non-carpet levels (E6..F2); the carpet ride's stay gaps |
| all, frame 0 | boot, title, attract, options (1B3B4A, 1B43C4.., 1B47xx, 1B0BBE) | 3 | **open**: the oracle seeds the native runtime at the first main-loop boundary |
| any | messages with wait commands inside the main loop; pause loop; Start-release wait; game over 1B0558; declined continue (title) | 3 | **open**, fail loud |
| any | 22 player and 20 projectile contact callbacks no recording has met | 4 (future) | fail loud with the ROM address |
| independent audit (docs/astra6-independent-audit.md) | kind 3B enters the gem through the sword guard 1AF21E, an entry the old recovery qualified 13 times; the native registry had only the body 1AF228 | 1 | registered (`gem_unless_sword`) |
| independent audit | the level ticks of levels 7, 9, 11, 12 passed record offsets as keyword names to `_spawn`: a TypeError on their spawn branches, unreached by the recordings | 1 | fixed; probed over a sweep of player X |
| independent audit | `native_replay --native` closed the oracle and then let the clock use it | 2 | it is now the explicitly independent driver (no clock after the seed) |
| independent audit | the per-step verifier skipped a step whose entry was the previous step's exit, and exited 0 on mismatches | 2 | fixed: exit 2 on mismatch, 3 on a recovered step not exercised |
| independent audit | transition checkpoints proved only that the oracle eventually reached each pc; the entry and the resumed state were not asserted | 2 | `verify_sequence` gates every known checkpoint (route order), asserts the entry, compares the resumed boundary |
| independent audit | snapshots named their recording by a second resolution of the moving `main` ref | 2 | resolved once, written once; regenerate whole sets only |
| independent audit | level-2 event E7 handler 1B7840 (old recording, frame 11259) | 3 | recovered (a sound) |

Nothing in the table is a timing rule fitted to a recording.  The two
category-2 items that touched the runtime (the handler per elapsed frame,
the checkpoints before polling loops) are platform semantics and progress
marks; the rest of category 2 is tooling.

The independent contract.  A standalone run has no oracle, so it states
its own timing contract and the oracle is checked *under that contract*:
input advances per game frame (the mask for game frame W applies when the
game returns from its W-th VBlank wait, `WAIT_RETURN` 1B24F4, never with
elapsed work time), and a routine that always spans frames in the original
(a decompression, the screen draw) carries `services.work()`, which runs
the VBlank handler's effects once, the same result as any number of
handler passes under an unchanged mask.  `native_diff.py --independent`
runs the native side with no clock and the oracle by that contract
(`OracleDriver(by_waits=True)`), comparing whole RAM and the ordered sound
driver calls (request / flush / command, from the driver entries' stack
argument) after every frame.  Under it the recordings become slightly
different playthroughs than under the faithful rule, which is what makes
this a check of independence rather than of alignment: nothing flows from
the oracle into the native run.

| independent run | outcome |
|---|---|
| 24c70ffc from power-on | byte-exact and sound-exact to the recording's end |
| 44223150 from f69586 | byte-exact and sound-exact for 12,600 frames to the end, through its deaths |
| 2dddf860 from power-on | byte-exact and sound-exact to its level change at 8197 |
| 44223150 from power-on, later | byte- and sound-exact to frame 26798, where its input variant declines a continue: the title screen is a gap |

What an aligned run proves, and what it does not.  The independent audit
is right that an oracle-fed clock is a diagnostic instrument: an aligned
run proves that the native operations reconstruct the original's RAM
under the original's timing and the input it actually read.  It does not
prove that the standalone runtime, on its own clock, would take the same
route.  So the tools name their mode: `native_diff.py` runs *aligned* by
default and `--independent` with the clock detached after the seed
(native frame N reads pads(N), transitions spend no work time, the oracle
only compares), and `native_replay.py --native` is the independent driver
with no oracle at all.  A divergence in an independent run that the
aligned run does not show is a timing difference of the standalone
policy; one that both show is semantic.  The remaining items of that
audit (one owner for the operations the old boundary machinery and the
new modules both implement, carried video and sound-event comparison, a
schedulable input service so a transition can accept live input) are
the verification and integration work of the next phase, listed in
section 4; they are not blockers for the recovery frontier below.

## 3. The frontier, from route censuses

`scripts/route_census.py FROM TO [--recording ID | --seed FRAME]` replays a
window of a recording with every bsr / jsr / jmp target of the game's code
region gated (in batches of 63) and lists the routines entered, marking the
ones no native module cites by address.  Two windows so far:

**Level 1 -> 2 change (44223150, frames 10000..11100, seeded at f9300).**
Entered and not cited: the scarab screen and its helpers (1B16E0, 1B1AD6:
the scarab count digits from the table at 4A58; 1B1B3C: the HUD flash on
frame-counter phases 0x0A / 0x1E; 1B16B4), the end-of-level tally 1B0D70,
1B50EE, 1B2584 (a name table from a word list), 1B2E86.  The rest of the
window (the loader, the decompressors' inner loops 1B38B8.., the fades,
pad helpers) is recovered under other labels.  This is the open blocker of
the old recording at frame 10018 and the first target of the next phase.

**Boot to the first main-loop frame (2dddf860, frames 0..1311).**  Entered
and not cited: the title and option screens (1B43C4, 1B434E, 1B430C,
1B4410, 1B3B4A: the title palette cycle over 129DAA, 1B3B96, 1B477C..1B47F0),
the attract-demo pad reader 1B0BA6 / 1B0BBE (recovered as
`pad.attract_input` under 1B315C), the level-0/1 story pages 1B4920 / 1B4A7A
/ 1B4DF8 (the level-5 pages are recovered; the others follow the same
`story_page` shape).  The outer game is the last phase.

**The main loop itself** (the 330-frame dense census of 44223150): 98.8 %
of the sampled instructions run in routines the native modules cite; the
remaining 1.2 % are the decompressors' and pad readers' inner helpers and
the sound driver (platform).  The main loop is not where recovery is
missing.

## 3b. The cold-start frontier (audit of 15 September, evening)

What runs from reset to the first main-loop frame, traced on the old
recording with every call target gated (`scripts/route_census.py 0 1002`
and a first-hit trace): ROM 21A (the console's reset code: TMSS, the VDP
and the Z80, the region check) -> 1A8A4A (stack, interrupts) ->
1AA344 (game init) -> 1A8A58 (new game: VDP registers, font and HUD tiles,
planes, scroll table, objects) -> 1A8B24 (title entry) -> 1B3B96 (logos,
title, the 1500-frame attract timeout, the Start / Options menu) -> the
session counters -> 1A8B50 (prologue: title card 1B1486, the level-1 title
1B202A, the story 1B0F66, the level intro 1B1260, the loader, the draw) ->
1A8C16.  The attract demo is the same prologue and main loop with FFF57C
set and the pad from the ROM stream; a button ends it at 1B3182, which
returns to 1A8B24; a declined continue goes to 1A8A58; the game over is
1B0558.

| region | class | state |
|---|---|---|
| reset code 21A..6A8 (TMSS, VDP, Z80, region) | 4 (platform) | the power-on contract: zeroed RAM, the VDP as the reset code leaves it (`boot.power_on`); the sound driver's tables are a platform service |
| game init 1AA344, session defaults 1AA41C, high-score and button-routine tables 1AFFE4 / 1B32E2, new-game console setup 1A8A58 | 1 | recovered in `native/boot.py`; verified from reset at 1AA344, 1A8A58, 1A8B2C (`verify_sequence.py --boot`) |
| title, logos, attract timeout, Start / Options menu 1B3B96..~1B4800 with 1B3B4A, 1B43C4.., 1B477C.., 1B4410.., 1B4802, 1B4836, 1B3548, 1B0BA6 | 3 | grinder in progress (`native/title.py`); verification: the three power-on recordings through `--boot` |
| level-1 title 1B202A | 3 | grinder in progress |
| story pages of levels 1, 7, 9, A, B | 3 (1, 7 partly composition) | grinder in progress; levels 7, 9, A, B unreachable by any recording: listing-only until a recording reaches them |
| attract exit 1B3182 and the demo run | 1 | composition: a transition kind 'attract_end' back to the title entry (grinder) |
| declined continue -> 1A8A58 | 1 | composition once the title lands |
| game over 1B0558 | 3 | grinder, listing-only (no recording reaches it) |
| options screen (from the menu) | 3 | within the title grinder's scope if the menu reaches it; else a NativeGap |
| ending 1B4F7C | 4 | not on the path to the milestone |
| sound output | 4 | the driver's calls are events; audible playback needs the Z80 driver as a service, later |

## 4. The loop, as it now runs

native run (`native_diff.py --cold RECORDING N`, or from a snapshot) ->
a precise gap or divergence (NativeGap with the ROM address, or the first
differing RAM field attributed to its step) -> oracle evidence
(`route_census.py` for the window, `verify_sequence.py` for a transition's
checkpoints, `--pad` for inputs the recording never made) -> the routine
recovered as a game module function -> the same run continues.

Next phase, in order: the level change (category 3, the old recording's
blocker at 10018), the level-2 event stream, the remaining story pages, the
game-over and title paths, then boot.  No new alignment machinery is
planned; every remaining blocker is missing game logic.
