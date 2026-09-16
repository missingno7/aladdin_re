# Gods: verification pass over the timing report (16 September 2026)

A read-only attempt to falsify `timing-and-verification-2026-09-16.md` before it is relied on.
Everything below was run against the **committed** tree at `8c6533db0bfa6f805a6a7cb53fefb3e2ca9203be`
(HEAD when the pass started; the grinder committed `8c6533d` at 17:19 and its working tree was never
imported): `git ls-tree -r --name-only HEAD src scripts` was exported to
`artifacts/gods/research/src-at-HEAD/` and every script of this pass puts that copy first on `sys.path`
(`scripts/research/vp_common.py`, which also refuses to run if a product module resolves to the
checkout).  Native library `build/libgenesis_native.dll`, SHA-256 `8a2fbdfc…` (the same binary as the
baselines `verify-camera-sprites-tree-2026-09-16t`/`…v`).  Nothing under `src/`, `tests/`, the
histories, the fixtures or the product caches was changed; the only things created are under
`docs/gods/research/`, `scripts/research/vp_*.py` and `artifacts/gods/research/`.

"Measured" below means a number this pass produced with the named script and artifact; "inferred"
is marked as such.  The strict original machine stayed the authority throughout: the only
interventions anywhere are time-only or single-byte `Machine.atomic` operations inside isolated
experiments (§6, §8), never in a verification run.

Two defects in the report's own tooling were found on the way and are load-bearing for its
conclusions; they are stated where they matter (§6: the slide tool never advanced its "20-tick
future"; §2: the "FIFO stall" refusal class is the adapter's Z80 bank guard).

---

## 1. Full-tree results with the moved observation instant

Tool: `scripts/research/vp_tree_run.py` — the same DFS over `history/gods/` that
`genesis_re.verification.execute_history(tree=True)` performs (every recorded branch, in-memory
saved states at branch points, `GenesisRun.observable()` at every canonical frame; no persistent
cache is read or written), with the observation instant replaced for the process only by
`dataclasses.replace(GODS, observation_offset_ticks=757_154)` (0.845 × FRAME_TICKS; the input
instant, the frame wrap, is untouched).  Compared frame by frame with
`scripts/research/vp_compare_runs.py` on all thirteen observation fields (`state_sha256`,
`frame_sha256`, `pcm_sha256`, `pcm_bytes`, `tick`, `pc`, `sr`, the three instruction/cycle counters,
`vblanks`, `frame`, `buttons`).

| run | candidate | instant | frames | result | artifact |
|---|---|---|---|---|---|
| R1 | original | 757,154 | 107,519 (8 nodes) | — | `artifacts/gods/research/tree-original-moved-A/` (632 s) |
| R2 | original | 757,154 | 107,519 | **identical to R1 on every field of every frame; endpoints equal** | `tree-original-moved-B/` |
| R3 | `camera-sprites` | 757,154 | 107,519 | **identical to R1 on every field of every frame; endpoints equal** | `tree-candidate-moved/` (770 s) |
| R4 | `camera-sprites` | 448,020 (product default) | 107,519 | **identical to the baseline `verify-camera-sprites-tree-2026-09-16v/reference.json` on every frame** and reproduces its candidate counters exactly (1,041,739 hits, 13,151 fallbacks) | `tree-candidate-default/` (784 s) |
| — | R1 vs the default-instant reference | both | 107,519 | every frame differs in `state_sha256`/`pcm`/`tick`/cycle counters (a different instant is observed), `frame_sha256` differs in 8,219 frames, **`vblanks` and `buttons` equal on every frame** | `vp_compare_runs.py` |

So: the original's observations at the new instant are self-consistent (R1 = R2), the candidate at
the new instant equals the original at the new instant everywhere (R3 = R1: no divergence, hence
"observation-only" holds on the whole tree), and the candidate at HEAD still passes at the default
instant (R4 = baseline reference).  The baseline named in the task, `…16t`, is one commit older
(`ea33e17`, 11,631 fallbacks); the numbers below are against `…16v`, which is the run that matches
HEAD's candidate (the `…16t` → `…16v` difference is the three regions `8c6533d` added).

Candidate counters, before/after (measured, whole tree):

| counter | default instant (R4 = `…16v`) | moved instant (R3) | change |
|---|---|---|---|
| candidate hits | 1,041,739 | 1,047,692 | +5,953 |
| fallbacks, total | 13,151 | 6,790 | −6,361 (−48 %) |
| — scheduler admission | 7,939 | 4,864 | −3,075 |
| — seam deadline | 3,728 | 443 | −3,285 (−88 %) |
| — unsupported domain (declined arms) | 1,483 | 1,483 | 0 |
| — gate without a planner (foreign-return edge) | 1 | 0 | −1 |
| seam entries / completions | 105,964 / 101,583 | 106,079 / 105,037 | |
| instructions replaced | 34,057,407 | 34,182,989 | |

The report's extrapolation ("every deadline refusal and all but one seam deadline disappear") is
**not** what the tree shows: 333 deadline refusals and 443 seam deadlines remain (§2), because ticks
that are still working at 0.845 of the frame exist in every recording (2,125 of the 40,845 gameplay
ticks run longer than one frame, §4).  The direction and the order of magnitude hold.

## 2. Exact refusal breakdown, before and after, measured on the full tree

Every `Machine.atomic` refusal of R3/R4 was classified before the native call (the wrapper in
`vp_tree_run.py --classify`, the same split as `refusal_classifier.py` but with the VBlank IRQ
instant measured rather than assumed: `scripts/research/vp_vblank_instant.py` puts the handler
entry at 766,522–766,646 master ticks into the frame over 600 idle VBlanks, i.e. the IRQ at
766,080 = raster line 224.0, exception entry 44 cycles + the wait loop's own instruction).  The
per-refusal records are `tree-candidate-*/refusals.json`; the tables are printed by
`scripts/research/vp_refusal_report.py`.

| refusal class | default instant | moved instant | where |
|---|---|---|---|
| `deadline` (plan reaches the caller's deadline = the observation instant; `al_atomic`'s first test) | 3,383 (all at frame offsets 0.45–0.5, just before the deadline) | 333 (all at 0.75–0.849) | `001164` 1,170→146, `00FC8E` 650→56, `00BA8E` 494→48, `00FDB8` 414→27, `00FE08` 206→18, `00BCCE` 183→17, `00126A` 140→14 … |
| `vblank-in-span` (the plan's cycles reach the IRQ instant, margin ≤ 64 cycles) | 314 | 308 | `001164` 105, `00BA8E` 62–65, `00FC8E` 55, `00BCCE` 26, `00FDB8` 25, `00126A` 16, `00FE08` 14, … all at offset 0.85–0.855 |
| `engine-other` (the engine or `al_atomic` refuses for a reason independent of the deadline and of the IRQ) | 4,242 | 4,223 | `0018C8` 1,104, `00198C` 583, `014084` 530, `0063FA` 422, `0049DA` 366, `001164` 219, `00126A` 180, `00BA8E` 138, `00BCCE` 134, `010332` 105, … |
| seam deadline (`run_seam` hits the observation instant inside the ceded upload) | 3,728 | 443 | `001308`/`001306`/`00130C` 2,543+820+75 → 317+120+17, `001988`/`001986` 262+80 → 4+0 |
| unsupported semantic domain (the planner declined) | 1,483 | 1,483 | unchanged by construction |
| other (gate without a planner) | 1 | 0 | |

**What `engine-other` actually is (measured, and it contradicts the report).**  The report inferred
"the engine's `vdp.stall_master` guard — the FIFO still draining after a tile upload".  Two
measurements refute that:

1. The refusals cluster by raster line, not by gate: 3,551 of 4,223 fall in the 0.05–0.15 bin
   (raster lines 7–46, peak 17–29) and they hit RAM-only regions with no upload anywhere near them
   (`0049DA` 366, `0063FA` 422, `010332` 105) exactly like the seam resume `00198C`.
2. `scripts/research/vp_engine_probe.py` re-asks the parked machine for a 1-cycle, 1-instruction,
   write-free operation at each such refusal: **45 of 45** in the light window (`boundary-6000`,
   600 frames, moved instant) are refused too, so the condition is independent of the span.  Reading
   the Z80 bank register out of a snapshot (`Z80Box::State.bank`, located behind the driver image
   the 68000 copies to Z80 RAM 0000 from ROM `0F4570`) at each of those instants gives windows
   `F80000` (11), `F08000` (18) and `E18000` (16) — all ≥ `E00000`, i.e. the bank register is
   transiently pointing at 68000 work RAM.  That is the first guard in `al_atomic`
   (`native/machine.cpp`: `if (m.z80.running() && (bank << 15) >= 0xe00000u) return;`), and the
   transient values are the intermediate states of the sound driver's bit-serial bank-register
   write (the driver switches between ROM banks `01E`/`01F`/`03E` once per frame around lines
   7–46; `vp_engine_probe.py` prints the bank and its bit count).  `stall_master` cannot be the
   cause: `machine.sync()` drains it to zero after every step, and `bus.access` is zero at an
   instruction boundary.

So of the 7,939 admission refusals at the default instant: 43 % are the observation deadline, 4 %
are a VBlank inside the span, 53 % are the adapter's Z80-bank guard tripped by the sound driver's
bank switch.  At the moved instant: 7 % / 6 % / 87 %.  The report's ranking ("mostly the deadline,
then the FIFO guard, then a small interrupt residue") is right about the deadline and the residue
and wrong about the second class's cause.  The bank-guard class does not move with the instant and
it is not a game timing property at all; whether the guard needs to be that conservative during a
bit-serial write is a machine-adapter question, outside this pass.

## 3. Confirmed tick-boundary semantics: `001EB4` vs `001EC2`

From the disassembly (`scripts/research/vp_disasm.py 001D7E-0020B0 0020B0-002160`; the linear
sweep `artifacts/gods/research/vp-sweep-disasm.txt` for the branch targets):

- `001EB4 bsr $52e` waits for `FFEEC6` to change (one VBlank); `001EB8–001EC0` tests bit 0 of the
  low word and loops back to `001EB4` if odd.  `001EC2` is reached **only** by falling through that
  test — no other instruction in the code region jumps to `001EC2`, `001EB8` or `001EC6`
  (the sweep's only references to `$1eb4`/`$1ec2` are `001EC0`, `00213E`, `002734`, `00273C`,
  `002756`, `0027CA`, all targeting `001EB4`).
- `001EB4` is entered from the tick's end (`00213E`), from the parity retry (`001EC0`), from the
  `FFEF54` sub-mode path (`002722`–`0027CA`, RAM-only, returns to `001EB4`) and by fall-through
  from the level prologue (`001EAE`).  It is visited once per VBlank waited: twice per normal tick
  (odd, then even), once when the odd VBlank fell inside the body, and it carries no tick identity.
- The loop body is straight-line from `001EC2` to `0020B0` apart from the mode branches; the
  alternate body at `002C08` (taken at `001F34`/`001F38` on `FFEF3C` ≤ 0) rejoins at `001FDC`.
  The pause (`002852`, called at `001EC6`) spins **inside** the tick on the pad latch `FFEA23` bit 3
  until Start is released and pressed again; the tick then continues.  The attract-mode exit
  (`001ECA bsr $4348; bne $43e2`) and the level change (`00212C bne $1d90`) leave the loop from
  inside a tick and re-enter it at `001EB4` after the prologue, without passing `001EC2`.

Measured over the five leaf recordings (which cover all 107,519 tree frames once;
`scripts/research/vp_recording_census.py`, pass T, `artifacts/gods/research/census-T-*.json`,
summary `census-T-summary.json`):

| recording | VBlanks | `001EC2` | gameplay / pause-transition / intro-script / demo | VBlanks between consecutive `001EC2` | `001EB4` visits before a tick start |
|---|---|---|---|---|---|
| `ca2b703b…` | 14,578 | 4,756 | 4,752 / 4 / 0 / 0 | 2: 4,751; 40: 2; 84: 1; 146: 1 | 1: 109; 2: 4,647 |
| `fb408bc7…` | 34,899 | 13,742 | 13,693 / 19 / 30 / 0 | 2: 13,664; **4: 58**; 40: 13; 42: 3; 198, 702, 3,518: 1 each | 1: 1,054; 2: 12,688 |
| `7251bbd0…` | 25,259 | 8,931 | 8,921 / 10 / 0 / 0 | 2: 8,882; **4: 38**; 40: 9; 3,011: 1 | 1: 429; 2: 8,502 |
| `f0ac1973…` | 15,143 | 6,658 | 6,653 / 5 / 0 / 0 | 2: 6,640; **4: 12**; 40: 4; 116: 1 | 1: 123; 2: 6,535 |
| `f40d7bcc…` | 17,615 | 6,838 | 6,826 / 12 / 0 / 0 | 2: 6,820; **4: 5**; 40: 11; 228: 1 | 1: 347; 2: 6,491 |

Answers: `001EB4` is reached repeatedly without a tick starting (the odd-parity retry every normal
tick; 40–3,518 times across a transition or a pause whose spin is inside the body).  `001EC2` is
reached exactly once per loop-body pass, and every 30 Hz update is one pass: 40,821 of the 40,925
tick-to-tick gaps are exactly two VBlanks; the 113 gaps of four are dropped ticks (§10); the larger
gaps are the pause/transition ticks (they still pass `001EC2` once).  During a dropped tick
`001EC2` still enumerates the ticks that execute (the skipped one never starts; `FFEF4A`/`FFEF4C`
advance once, §10).  Mode paths: the pause is inside a tick (one `001EC2`, many VBlanks); the level
prologue, the shop/menus reached through `002722`/`001E6A` and the attract exit run **between**
ticks with no `001EC2`; the demo (`FFF3D8` ≠ 0) uses the same loop.  There is no better cut for
"GameTick N": `001EC2` is the unique parity-passed entry, `001EB4`'s first visit after `001EC2` is
the tick's output boundary (`001ECA`/`001ECE` would exclude the pause spin and the attract exit but
they are inside the same pass).  Confirmed as the owner interprets it.

## 4. All-recording torn-input and dropped-tick exposure

Pass T of `vp_recording_census.py` gates `0003DC`/`0004E8` (handler entry/exit: pre-empted PC,
counter, latches before/after), `001EC2`, `001EB4`, `000492` (the palette upload), `0F4478` (the
sound transfer), `00211C`, `002142` and the nine gameplay read sites of the 60 Hz counters
(`004BA0 004BB8 0065C4 0067E4 006900 006A2A 00F456 00F4AA 00F4BE`); when an odd VBlank lands inside
a tick and the handler's sample **changed** a latch, the rest of that tick is single-stepped to
`001EB4` and every read of `FFEA1E/20/22/23`, `FFF3DA`, `FFEEC6/8`, `FFF2AA`, `FFF19E` after the
VBlank is recorded (`torn_witness`).  "Gameplay" excludes the demo, the intro script
(`FFF210` ≥ 0, which itself writes the latches at `0025D0`/`0025E6`) and ticks spanning more than
eight VBlanks (pause/transition).

| recording | gameplay ticks | odd VBlank inside | two inside (dropped) | inside **and** the sample changed | … and a latch read after it | … and a gameplay 60 Hz read after it | input events | tick work, frames (median / p90 / max) |
|---|---|---|---|---|---|---|---|---|
| `ca2b703b…` | 4,752 | 107 (2.3 %) | 0 | 16 | **0** | 0 | 1,382 | 0.636 / 0.819 / 1.647 |
| `fb408bc7…` | 13,693 | 1,097 (8.0 %) | 58 | 154 | **0** | 0 | 3,450 | 0.675 / 0.952 / 3.837 |
| `7251bbd0…` | 8,921 | 462 (5.2 %) | 38 | 96 | **0** | 0 | 2,561 | 0.635 / 0.896 / 2.543 |
| `f0ac1973…` | 6,653 | 131 (2.0 %) | 12 | 10 | **0** | 0 | 1,594 | 0.624 / 0.807 / 3.549 |
| `f40d7bcc…` | 6,826 | 344 (5.0 %) | 5 | 58 | **0** | 0 | 1,725 | 0.665 / 0.913 / 2.352 |
| **all** | **40,845** | **2,141 (5.2 %)** | **113 (0.28 %)** | **334 (0.82 %)** | **0** | **0** | 10,712 | 0.650 / 0.900 / 3.837 (p99 1.350; 2,125 ticks > 1 frame) |

The in-tick VBlanks pre-empt the drawing tail: `0013xx` (the particle drawer's upload) 502,
`003Dxx` (map streaming) 378, `00B3xx–00B5xx` 353, `00FBxx/00FCxx` (solids) 199, `0011xx` (the
map upload) 97; 396 landed inside `00126A`'s tile loop, 3 inside `0018C8`'s, 42 inside `00112E`'s.
The nine gameplay counter-read sites executed 6,767 times in total and **never** after an in-tick
odd VBlank; the only counter reads found after such a VBlank are the wait loop's own `000534`
(seven ticks that call `bsr $52e` from inside the body).

Separated as asked: "odd VBlank inside the tick" happens in 5.2 % of gameplay ticks and the new
input sample it took was different from the previous one in 0.82 %; "…and its new state observably
consumed" happened **zero** times in 107,519 frames — every latch read of those 334 ticks preceded
the VBlank.  The margin is small, though: in `fb408bc7…` tick 10030 (frame 26468, work 1.32 frames,
VBlank at `0013C4`, a C-button press sampled), 3,171 instructions remained after the VBlank with no
latch read; with 5,000 more cycles of work before the player update the same tick reads
`00747E btst.b #2,$ea23.w` after the VBlank (`scripts/research/vp_l2_contract.py --mutation phase`
and the ad-hoc trace in this pass), which is precisely the report's phase-shift divergence at
"tick 58, frame 26470".  The report's mechanism is right; its rate in the recordings is 0.

## 5. The `FFEECC` / VDP-address hazard: **A** (impossible by game ordering), with 0 of 107,494 VBlanks as witnesses

Static (the sweep, `grep eecc`): the flag is referenced at exactly 13 sites — tested and cleared by the handler
(`00048C`/`000492`), set at `0006FC`, `000C96`, `000CCE`, `000D46`, `001C98`, `001CE0`, `00211C`, `007E28`,
`007E54`, `00BE78`, `00D306`.  Every setter but `00211C` sits in transition/menu code and is
followed by a `bsr/jmp $52e` VBlank wait before any further VDP data write (`000CD6`/`000D78`
fade loops, `001C9C`, `007E2C`/`007E58`, `00BE7C`–`00BE88`, `00D30A`); the flag is therefore
consumed by the handler before the next data stream.  `00211C` is the tick's own tail
(`FFF210` reaching −1: the end of a level's intro script), executed after every drawing call of
the tick; from there the loop goes to `001EB4` (a wait), to `002722` (RAM only, then the wait), to
`002142` (which calls the fade `000D78`, itself ending in a wait, before `001104`'s scroll writes)
or to `001D90` (a level reload, only if the level index changed in the same tick as the intro
ended).  No code addresses `FF0000`–`FF003F`, and the only indirect writers of the flag byte would
be pointer stores, which the dynamic census covers.

Dynamic (pass T, all five recordings): 4,488 palette uploads by the handler; 3,506 of them while
the game was inside a tick, **every one** pre-empting the wait loop (`000534`/`000538`: fades run
from inside a transition tick) except one pre-empting `00BE7C` (a "wait for button release" spin);
**0** pre-empting an upload loop (`001974–00198C`, `0012F4–00130C`, `00FD86–00FD9E`,
`0010C8–0010D6`, `001104–00112E`, `00112E–001164`); of the 441 VBlanks that landed inside one of
those loops, **0** had `FFEECC` set; of all in-tick VBlanks, the flag was set only at those
3,506 wait-loop instants.  `00211C` executed once in all recordings (`fb408bc7…` frame 27269, tick
10332, at frame offset 0.359 with no VBlank yet inside the tick) and `002142` never.

Verdict **A**: the game sets the flag only after its uploads and always waits a VBlank before the
next VDP stream, so the handler's CRAM redirect can never land inside a tile upload.  The seams'
identity guards do not need the flag.  (The report's "should be censused before any normalization"
is now done; nothing needs to be generalized over the seams.)

## 6. Remaining slide results — and a defect in the original slide tool

**Defect.**  `scripts/research/vblank_slide.py`'s `run_gates` re-arms the tick-start gate while the
machine is parked at it and runs again without a bypass, so the engine yields at the same PC
without executing: every "tick_start" observation after the first is the same instant re-observed.
Its JSON shows it (`slide-batch/001164-entry-p0.json`: observations 1…20 all at tick 2,054,500,842,
counter 164; `slide-0018C8-p25.json`: all at 23,609,639,148).  The report's "20-tick future
identical" for 17 regions is therefore evidence about the region's exit, the tick end and **one**
tick start.  `scripts/research/vp_slide.py` fixes this (bypass once when parked) and chains
time-only stalls (`Machine.atomic` caps one at 100,000 cycles; a region 0.95 frame before the VBlank
needs ~121,000), which is what made the "not established" regions testable; the verdict is taken at
tick starts, and the tick-end observation — which legitimately differs in the handler's bytes — is
reported beside it.  The pad is constant (the fixture's mask), as in the report.

Every censused region was re-run with the fixed tool (`scripts/research/vp_slide_batch.py --only
<all 22 regions> --per-dir 2 --ticks 20 --positions 4`, outputs `artifacts/gods/research/slide-vp-all/`,
classified by `scripts/research/vp_slide_summary.py` into EQUIVALENT / DROP / PAD / OTHER):

| region | fixture runs | distinct landing steps inside the region | burns EQUIVALENT | DROP | PAD | OTHER |
|---|---|---|---|---|---|---|
| `002806` camera | 4 | 23 | 27 | 0 | 0 | 0 |
| `004150` table reset | 4 | 24 | 28 | 0 | 0 | 0 |
| `00364C` score conversion | 8 | 38 | 56 | 0 | 0 | 0 |
| `010A14` collision gate | 4 | 24 | 21 | 0 | 7 | 0 |
| `010332` countdown check | 8 | 21 (the 3-step arm cannot be entered) | 56 | 0 | 0 | 0 |
| `00BA8E` pickup check | 9 | 63 | 63 | 0 | 0 | 0 |
| `00932C` effect pool add | 2 | 12 | 14 | 0 | 0 | 0 |
| `014A3C` next random | 2 | 6 | 14 | 0 | 0 | 0 |
| `013316` | 2 | 8 | 12 | 0 | 0 | 0 |
| `001164` | 7 | 27 | 42 | 7 | 0 | 0 |
| `00126A` | 9 | 45 | 56 | 0 | 7 | 0 |
| `0018C8` sprite emitter (p25, p26, p0-ccr00 of `fb408bc7`, p10 of `7251bbd0`/`f40d7bcc`) | 5 | 26 | 24 | 0 | 7 | 0 |
| `00462C` | 5 | 35 | 28 | 7 | 0 | 0 |
| `00470C` | 10 | 37 | 55 | 14 | 0 | 0 |
| `0049DA` | 4 | 20 | 21 | 0 | 0 | 0 |
| `0063FA` | 3 | 12 | 21 | 0 | 0 | 0 |
| `00BCCE` | 9 | 47 | 56 | 7 | 0 | 0 |
| `00F828` | 4 | 28 | 21 | 0 | 7 | 0 |
| `00FC8E` | 6 | 35 | 41 | 0 | 0 | 0 |
| `00FDB8` | 5 | 27 | 27 | 0 | 0 | 0 |
| `00FE08` | 4 | 21 | 28 | 0 | 0 | 0 |
| `013264` | 8 | 49 | 56 | 0 | 0 | 0 |
| `014084` | 10 | 70 | 70 | 0 | 0 | 0 |
| **total** | **132** (44 more fixtures errored: their tick does not reach `001EB4` within four frames — a level transition, as in the report) | **698** | **837** | **35** | **28** | **0** |

Per burn: region exit (live RAM at or above A7 minus the handler's bytes, the dead residue counted,
the full register file, the sound block), then the tick end and 20 real tick starts (masked live RAM
hash, rendered frame, VBlank counter, plus elapsed/countdown/latches).

- **EQUIVALENT (837)**: exit RAM and registers equal, every tick-start observation equal.
- **DROP (35; `001164` 7251bbd0 p0, `00462C` 7251bbd0 p0, `00470C` f0ac1973/fb408bc7, `00BCCE`
  7251bbd0)**: RAM and frame equal at every tick start, VBlank counter +2 from the first: the stall
  needed to reach a region entered 0.4–0.5 frame into a heavy tick pushed that tick past its even
  VBlank — the parity drop of §10, a property of the stall, not of the region.
- **PAD (28; `010A14` p1 of `census-010A14`, `00126A` p0 of `census-00126A-fresh-f40d7bcc9dda`, `00F828` p0 of `census-00F828-7251bbd0ecf7`, `0018C8` p10 of `census-0018C8-7251bbd0ecf7`)**: the fixture's
  own mask has a button the previous sample did not (`FFEA22` `0000` → `0004` at the moved VBlank),
  the tick consumed it after the moved VBlank and the player bytes (`FFF191/193/1A3`, the player's
  sprite record `FFEC3x`) diverge one tick early; for `010A14` p1 the two runs re-converge after one
  tick (`FFF1A3` set one tick earlier, then equal for the remaining 19), for the other three the
  playthroughs part.  This is the pad-latch channel, witnessed at the region level.
- **OTHER: none.**

So the regions the report left "not established" (`002806`, `004150`, `00364C`, `010A14`,
`010332`, `00BA8E`, `00932C`) are now established on the same footing as the others — and the
others are established on a real 20-tick future for the first time.  Two corrections to the
report's table: `014084`'s slide fixtures (`p0-ccr10`) are the **paint** arm (traced:
`014084 → 014108`, no request written); the "sound block differs at exit" there was a request
written earlier in the tick and consumed by the moved handler.  The spawn-arm fixtures are the
`census-014084-fresh-*/014084-entry-p10…` ones (123 of the 147 hazard fixtures), used in §8.

## 7. Sound requests inside one tick

Code: the block `FFFDEA`–`FFFE0B` has no reader but the handler's transfer (`0F4472`: copied every
VBlank while `FFFE10` ≠ 0, which `0F4544` sets once at driver init, then cleared to `FF` — `FFFDFC`–
`FFFDFF` and `FFFE0C`–`FFFE0F` are outside the cleared span); the sweep finds 152 references to the block's addresses
(the handler's own transfer and clear, `move.w #imm,$fdf4/$fdf6/$fdf0/$fdea` stores, four table-indexed
stores, `0F446C`) and no read outside the handler, so "the
clearing changes later gameplay writes" is impossible: no write is conditional on the slot.
Passes S1–S3 of `vp_recording_census.py` gate those sites in three thirds over each recording and
record, per write, the slot's value before it, the new value and whether the odd VBlank had already
run inside the tick (`artifacts/gods/research/census-S{1,2,3}-*.json`, summarized by
`scripts/research/vp_sound_report.py`):

| recording | gated writes (in a tick) | fresh (slot was `FFFF`) | overwrite, same value | overwrite, other value | written after the in-tick odd VBlank | ticks with > 1 write to one slot | … with a VBlank between the writes (both delivered) | commonest pairs |
|---|---|---|---|---|---|---|---|---|
| `ca2b703b…` | 2,335 (2,159) | 1,741 | 290 | 128 | 68 | 361 | 7 | `$35`×2 214, `$38`×2 22, `$33`/`$38` 16 |
| `fb408bc7…` | 8,455 (8,374) | 5,253 | 2,701 | 420 | 369 | 1,521 | 32 | `$35`×2 632, `$38`×2 452, `$33`/`$38` 28 |
| `7251bbd0…` | 4,571 (4,373) | 2,960 | 1,253 | 160 | 257 | 811 | 18 | `$35`×2 385, `$38`×2 226, `$35`/`$5F` 16 |
| `f0ac1973…` | 2,979 (2,968) | 2,319 | 495 | 154 | 60 | 560 | 8 | `$35`×2 343, `$38`×2 57, `$33`/`$38` 11 |
| `f40d7bcc…` | 3,659 (3,450) | 2,185 | 1,027 | 238 | 71 | 507 | 8 | `$35`×2 222, `$38`×2 114, `$35`/`$5F` 85 |
| **all** | **21,999 (21,324)** | **14,458** | **5,766** | **1,100** | **825** | **3,760 of 40,925 ticks (9.2 %)** | **73** | |

(139 gated sites: the 152 static references minus the handler's own stores and the reads; the
overwriting sites are the pickup/object routines `0131D2`, `013222`, `012E32`, `012EE6`, `012F0E`,
`012F6E`, `0134C6`, the hazard spawn `0140B6` and the player's `0031C2`/`00317E`/`00327E`.)

Classification:

- **delivery-frame-only**: a fresh request written after an in-tick odd VBlank is transferred at the
  even VBlank instead of the odd one — 825 writes in the recordings, plus every request
  that was pending when an odd VBlank landed inside a tick (1,634 non-empty transfers at in-tick
  VBlanks) is delivered one frame earlier than a port that commits at the tick's end would.
- **semantic loss/replacement (VBlank-position dependent)**: two writes to the same slot within one
  tick with no VBlank between them deliver only the second; a VBlank between them delivers both.
  Same-value pairs (the same effect requested by two objects — 5,766 overwrites, most of the 3,760 multi-write ticks) collapse to one trigger
  vs. two; different-value pairs (1,100 overwrites) lose the first request vs. deliver both.  Measured on
  a real spawn fixture (`census-014084-fresh-7251bbd0ecf7/014084-entry-p10.state`, frame 8403,
  `vp_l2_contract.py --mutation sound --param 100150`): the original transfers one `$38` at VBlank
  8075; with the VBlank moved before `0140B6`'s write the block is transferred at 8075 **and** at
  8076 with `$38` both times — the sound plays twice.  RAM at every tick start is identical for 150
  ticks; only the stream differs.  In the recordings themselves a VBlank fell between two same-slot
  writes 73 times (§7 table): those are the audio outcomes that actually depended on
  mid-tick timing.
- **reordering**: not possible — slots are independent and each is a single word.

This is stronger than the report's "a one-frame delivery shift": the count of deliveries of a
request can depend on where the odd VBlank lands.  It is still entirely inside the "sound commit"
channel; the port's contract must say whether a request slot is a latch (last writer wins per tick)
or a queue, and the stream's transfer entries (§8) are what checks it.

## 8. Adversarial L2 results

`scripts/research/vp_l2_contract.py` observes the original at every `001EC2`: (a) the RAM hash at or
above the main loop's user SP (`FF0400`; §9 says why not lower) and, separately, the hash of
`FF0040`–`FF03FF`; (b) `FFEEC6`, `FFEF4A/4C`, `FFF2AA`, `FFF19E`, the latches; (c) the ordered
platform event stream of the finished tick, each entry stamped with the VBlank counter: the sprite-
table/scroll commit at `0010C8` (record count, words, hash), every tile-upload block entered
(`001974`/`0012F4`/`00FD86`/`00112E`: source, counts, data hash), the palette commit (`000492`), the
sound transfer (`0F4478`, non-empty blocks), the input sample (latches after `0004E8`, whether the
tick was running, whether the value changed) and the rendered frame after each VBlank.  The
mutations are single `Machine.atomic` interventions in the experiment's own copy of the run
(outputs `artifacts/gods/research/l2/`):

| mutation | how | first rejection, by component | RAM / video later |
|---|---|---|---|
| dropped tick | `boundary-6000`, tick 20: a chained stall at `004150` up to the odd VBlank, then a second at `0012F4` up to the even one; the tick's rest crosses it | **tick 21: VBlank counter 5754 → 5756, `FFF2AA` +2**, stream (an `input-sample` inside the tick); RAM hash also differs at tick 21 through `FFEEC9`/`FFF2AD` only | latches differ from tick 29 (the recorded events land in other ticks), video from tick 31 |
| torn input | `0018C8-entry-p25` (`fb408bc7…` 26348), +5,000 cycles at `004150` every tick | **stream at tick 4** (`input-sample … in-tick` where the original had `idle`), i.e. the contract flags the exposure before it is consumed; RAM at tick 58 (frame 26470: `FFED11/12/1D`, `FFF191/193/1A3`, `FFF36F…`) | video from tick 59 |
| audio delivery | the spawn fixture above, the VBlank moved into `014084` | **stream at tick 0** (`sound-transfer` at VBlank 8076 added); RAM, counters, latches, video equal for all 150 ticks | never |
| palette delivery | `0018C8-entry-p25`, an 80,000-cycle stall at `004150` in the tick whose tail sets `FFEECC` (`FFF210` = 0 at its start; `00211C` then runs at offset 0.976, after the odd VBlank) | **stream at tick 360**: `palette-commit` at VBlank 18856 instead of 18855, and `video-after-vblank` 18855 differs; RAM, counters, tick-start video equal for all 379 ticks | never (converges at the next VBlank) |
| hidden state | `boundary-6000`, tick 20: one atomic write `FFEEF1 += 2` (the random cursor's low byte) at `004150` | **RAM at tick 21** (`FFEEF1 54/56`, one byte) | video equal for all 180 remaining ticks; counters, latches, stream equal |

Every mutation is rejected by the component that claims it, at the first tick it exists.  Two
things the prototype showed that the report did not say: the drop is also visible in the RAM hash
(the counters are RAM bytes; a hash that does not mask them needs no separate counter check), and
the input-sample entry's "inside the tick" flag rejects a phase shift 54 ticks before the game
consumes anything — a conservative rejection, which is what a contract wants.

## 9. The verified RAM exclusion policy

Measured, from the traces and the mutations:

- `FF0000`–`FF003F` is the supervisor stack (initial SSP `FF0040` from ROM vector 0; the game runs
  in user mode: `SR` has S = 0 and IPL = 0 at the observation instant of 107,489 of the 107,519
  frames of R1, the other 30 being the boot code before `000234 move a6,usp`).  The exception frame and the handler's
  `movem` live at `FF0026`–`FF003F`; no instruction in the code region addresses that range (the
  two `.w` short operands below `$40` in the sweep, `014456`/`015ECA`, are data mis-decoded), and no
  future difference in the 837 equivalent burns ever traced to it although it differs between every
  A/B pair.  **Architectural residue; exclude.**
- `FF0040`–`FF03FF` is the user stack's dead space below the main loop's SP (`FF0400` at `001EC2`).
  It is **not** timing-neutral: the wait loop `00052E` pushes `d0` = the VBlank counter there
  (`FF03F8`–`FF03FB`), so the dropped-tick mutation changed `FF03FB` (`01/00`) and the report's
  "64 K minus `FF0000–FF003F` and nothing else masked" hash would fail on stack residue rather than
  on the counter.  At the cut it is below SP, hence dead by construction; whether anything reads it
  as gameplay state cannot be excluded statically (uninitialised locals), but every read would be a
  read below SP at `001EC2` — none is witnessed by the 837 equivalent burns.  **Dead stack residue;
  exclude at the cut, i.e. hash from the user SP up** — which is what the report's slide tool actually
  did (`ram[a7:]`), and what its text should say.
- The handler's own bytes (`FFEEC6`–`FFEEC9`, `FFF2AA`–`FFF2AD`, `FFF19E`–`FFF19F`, `FFEA1E`–`FFEA23`,
  `FFF3DA`–`FFF3DB`, `FFEECC`, the sound block `FFFDEA`–`FFFE0B`) are game-semantic or platform
  buffers whose values at `001EC2` are determined by the VBlank count and the tick's own writes:
  **keep** (they are what catches the drop and the delivery shifts; masking them is what the slide
  tool needs *inside* a tick, not at the cut).
- Everything else (`FF0400`–`FFFFFF` minus the above) is game state, platform buffers written by the
  game (sprite table, palette buffer, tile double buffer, scroll words) or unknown: **keep**.  No
  byte in it was found to differ between two runs with equal VBlank counts in which every input
  sample was consumed by the same tick, in any experiment of this pass.

So the safest contract is exactly "all 64 K at or above the user SP at the cut, nothing masked",
plus the explicit platform state of §8's stream.  Not "64 K minus `FF0000`–`FF003F`", and no list
of annoying bytes.

## 10. Direct traces of every dropped tick

`artifacts/gods/research/dropped-ticks.json` (extracted from pass T): 113 dropped ticks in gameplay
(`fb408bc7…` 58, `7251bbd0…` 38, `f0ac1973…` 12, `f40d7bcc…` 5, `ca2b703b…` 0), in heavy stretches
(`fb408bc7…` frames 12794–13054 and 20678–20718; `7251bbd0…` 15636–15718 and 19883–20475;
`f0ac1973…` 7767 and 13971–14043; `f40d7bcc…` 6940 and 10506–10538).  For every one of them:

- the tick's work was ≥ 2.00 frames (2.00–3.84); two VBlanks landed inside with counter parities
  (0, 1) — the odd one then the even one — in 106 cases, three with parities (0, 1, 0) in 7 (the
  3.5-frame ticks of `f0ac1973…` 14019–14027); the pre-empted PCs are drawing/streaming code
  (`00B3xx–00B5xx`, `003Dxx`, `001306`, `00FCxx`);
- `001EB4` was then visited twice (once for the seven triple ones) before the next `001EC2`: the
  parity gate saw an odd count first — the game's own gate, not the replay's;
- the next tick start is 4 VBlanks later (`FFEEC6` +4 in all 113), `FFF2AA` +4 in all 113 (the 60 Hz
  clock never stopped), `FFF19E` unchanged (it was 0 in all of them), `FFEF4A` +1 mod 2 and
  `FFEF4C` +1 mod 4 in all 113 (game time advanced by the one executed tick);
- input kept being sampled: the latches changed at one of the inside VBlanks in 32 of the 113 (the
  sample is consumed by the next tick — the pad channel of §4, not a torn read); a non-empty sound
  block was transferred at an inside VBlank in 33 (delivery continued); the palette flag was set at
  none (no palette commit in a dropped tick in any recording).

Not an artifact of the replay: re-running the whole `f40d7bcc…` census with the observation instant
moved to 757,154 (`census-T-f40d7bcc9dda-offset757154.json`) gives a tick table identical to the
default-instant one on every field (6,838 ticks: start/end master tick, VBlank counts, counters,
latches, pre-empted PCs; 17,615 VBlanks identical), drops included; and R1's per-frame `vblanks`
equal the default-instant reference's on all 107,519 frames.  The drop is decided by the tick's wall
time against the parity gate at `001EB8`, exactly as the report says.

## 11. Newly discovered temporal dependencies (and one that is not the game's)

Searched for: a future gameplay difference under a legal alternative VBlank landing, for a reason
other than pad latch, 60 Hz counter, sound commit, palette commit or the VDP-address hazard.

- 900 accepted burns over 132 fixtures and 22 regions (§6): every difference was PAD or DROP; OTHER
  = 0.  The phase-shift and L2 runs (§8): first differences at player bytes right after an input
  sample moved inside a tick, or at the counters.  No difference in any experiment was traced to
  the supervisor or user stack residue, the RNG cursor, a coroutine word or an object record except
  through those channels.  **No counterexample found.**
- Within the sound channel the dependency is stronger than "delivery frame": same-slot double
  requests in one tick are collapsed or doubled by the VBlank's position (§7).  New in kind
  (count, not time), not new in channel.
- The dominant admission-refusal class is the adapter's Z80 bank guard during the sound driver's
  bit-serial bank switch (§2), not a game timing dependency and not the VDP FIFO.  It appears in
  every recording at raster lines 7–46 regardless of the instant.

The core conclusion — Gods needs no arbitrary resumable native execution; the witnessed regions
commute with the VBlank; the temporal semantics are the 60 Hz service, torn reads in long ticks,
commit timing and the parity drop rule — survived the attempt.  It is now supported by a real
20-tick future for every region (the report's evidence was one tick start), by a full-tree
measurement of the refusal classes, and by whole-recording counts of each channel's actual
incidence: torn reads consumed 0 times, drops 113 ticks (0.28 %), same-slot double sound requests in 3,760
ticks of which 73 were split by a VBlank (§7), palette commits inside gameplay ticks 0.  Two of its supporting statements are corrected
(the FIFO cause; the `014084` fixture arm) and one of its numbers is restated (the moved instant
removes 90 % of the deadline refusals and 88 % of the seam deadlines on the tree, not all of them).

## 12. Classification of the original report's claims

| claim (section of the report) | status | evidence here |
|---|---|---|
| The only interrupt is the VBlank; the 30 Hz cadence is an explicit parity gate on `FFEEC8` (§1.1) | PROVEN | §3 disassembly; 40,821 of 40,925 gaps exactly 2 VBlanks |
| Handler write set and the four clocks (§1.1, §1.3) | PROVEN | §3, §10 (`FFF2AA` +4 per dropped tick, `FFEF4A/4C` +1) |
| The tick starts at 0.867 and its work ends at 0.20–0.95 of the next frame in light play, past the VBlank in a quarter of heavy ticks (§1.2) | PROVEN, with the tree's numbers | §4: median 0.650, p90 0.900, 5.2 % of gameplay ticks with the odd VBlank inside over all recordings (2.0–8.0 % per recording) |
| Gameplay executes exactly every second VBlank unless a tick exceeds ≈1.99 frames, then one tick is dropped (§1.2, §7.2) | PROVEN | §10: 113 drops, all ≥ 2.00 frames, all +4 VBlanks / +1 game tick |
| Tick work time is dominated by VDP FIFO stalls (§1.2) | NOT ESTABLISHED (not re-measured here; the report's cycle-vs-tick figures for `0018C8` stand on their own) | — |
| VBlank is the clock, the sampler, the palette/sound commit point and two 60 Hz counters; it never reads the sprite list or object tables (§2) | PROVEN | §3, §5, §7 (no reader of the block but the handler) |
| Interrupted-trace evidence establishes the region's own path, not commutation (§4) | PROVEN (a statement about the tests) | — |
| The handler commutes with every witnessed region: RAM, registers and **20-tick future** identical (§5.2, 17 regions) | DISPROVEN as stated (the tool observed one tick start, not 20), then RE-ESTABLISHED by this pass on a real 20-tick future for 22 regions, 837 equivalent burns, with the PAD/DROP classes named | §6 |
| `002806`, `004150`, `00364C`, `010A14`, `010332`, `00BA8E`, `00932C` not establishable with the tool (§5.2) | SUPERSEDED: established by chaining stalls | §6 |
| `014084` 'spawn' writes a sound request and its slide shows the block consumed by the moved handler (§5.2) | SUPPORTED BUT DOMAIN-LIMITED: the fixture used was the paint arm; the spawn arm behaves as described and, in addition, can double-deliver (§7) | §6, §7, §8 |
| `0049DA`'s DIFFERS is a dropped tick, not a region property (§5.2) | PROVEN (35 DROP burns across four regions, same signature) | §6 |
| The `FFEECC` CRAM-redirect hazard: possible, to be censused (§5.2) | RESOLVED as **A**: impossible by ordering; 0 witnesses in 107,494 VBlanks | §5 |
| Natural cut points: `001EC2` tick start, `001EB4` tick output (§6) | PROVEN | §3 |
| The replay's default instant sits in the busy window; 0.845 is idle (§6, §12) | PROVEN on the tree: deadline refusals 3,383 → 333, seam deadlines 3,728 → 443 | §1, §2 |
| Moving the instant "removes every deadline refusal and all but one seam deadline" (§7.1, §12) | DISPROVEN as a tree statement (333 and 443 remain: heavy ticks still work at 0.845); SUPPORTED as an order of magnitude | §1, §2 |
| The trajectory is untouched by the instant "by construction" (§12) | PROVEN on the tree: R1 = R2 = R3 |  §1 |
| `engine-other` refusals are the VDP FIFO stall guard (§7.1) | DISPROVEN: they are `al_atomic`'s Z80 bank guard during the driver's bit-serial bank write; 45/45 refuse a 1-cycle probe; 53 % / 87 % of admission refusals | §2 |
| Interrupt-in-span refusals are "a few per cent" of the admission class (§7.1) | PROVEN: 314 of 7,939 (4.0 %) and 308 of 4,864 (6.3 %) | §2 |
| Torn input: which VBlank's sample a tick consumes depends on the tick's work time; 0.04 frame suffices in the heavy window (§7.3) | PROVEN as a mechanism (reproduced: `00747E` after the VBlank at +5,000 cycles); its incidence in the recordings is 0 consumed reads over 334 exposed ticks | §4, §8 |
| The same mechanism applies to the sound block, the palette and the mid-tick 60 Hz reads, "all invisible in light windows" (§7.3) | SUPPORTED BUT DOMAIN-LIMITED: sound — yes and stronger (§7); palette — never inside a gameplay tick in any recording (§5); 60 Hz reads — never after an in-tick VBlank in any recording (§4) |  |
| No persistent continuation is needed, in the workbench or the port (§8) | SUPPORTED (nothing found that a region-level adapter would fix; every residual is a tick-level or platform-level statement) | §6, §11 |
| L2 contract: RAM "with `FF0000`–`FF003F` excluded and nothing else masked" (§9) | DISPROVEN in that wording (dead user stack carries the counter); the corrected domain is "at or above the user SP at the cut" | §9 |
| L2 stream and counters catch the drop, the torn input, audio/palette delivery, hidden state (§9, §10) | PROVEN by mutation for all five | §8 |
| A contract masking the counters or latches passes wrongly on a drop (§10, §12) | PROVEN (the DROP class is invisible to the masked RAM hash and caught by the counter) | §6, §8 |
| Whether the sound block is ever written twice into the same slot within one tick (§12, "needs more evidence") | ANSWERED: yes, in 9.2 % of ticks; a VBlank fell between the writes 73 times; the moved VBlank can double a delivery (§7, §8) | §7 |
| The smallest next experiments (§11): exposure census, `FFEECC` census, tree re-run under the moved instant | DONE; results above | §1–§5 |

## Files created by this pass

Scripts (`scripts/research/`): `vp_common.py` (isolation, profile replacement), `vp_disasm.py`,
`vp_sweep_disasm.py`, `vp_timing_probe.py`, `vp_vblank_instant.py`, `vp_tree_run.py`,
`vp_compare_runs.py`, `vp_refusal_report.py`, `vp_engine_probe.py`, `vp_recording_census.py`,
`vp_census_report.py`, `vp_sound_report.py`, `vp_slide.py`, `vp_slide_batch.py`,
`vp_slide_summary.py`, `vp_l2_contract.py`, `vp_census_all.sh`.

Artifacts (`artifacts/gods/research/`): `src-at-HEAD/` (+ `HEAD.txt`), `vp-sweep-disasm.txt`,
`vp-vblank-instant.json`, `tree-original-moved-A/`, `tree-original-moved-B/`,
`tree-candidate-moved/` (with `refusals.json`), `tree-candidate-default/` (with `refusals.json`),
`engine-probe-6000.json`, `census-T-<node>.json` ×5, `census-T-f40d7bcc9dda-offset757154.json`,
`census-T-summary.json`, `census-S{1,2,3}-<node>.json` ×15, `dropped-ticks.json`,
`slide-vp/` (first batch), `slide-vp-all/` (every region; `summary.txt`, `summary.json`,
`classified.json`), `l2/l2-6000-drop.json`, `l2/l2-6000-hidden.json`,
`l2/l2-fb408bc7-phase5000.json`, `l2/l2-014084-sound.json`, `l2/l2-fb408bc7-palette.json`, and the
run logs `*.log`.

Fixtures read (never written): `artifacts/gods/evidence/main/boundary-6000.state`,
`census-0018C8-fb408bc7/0018C8-entry-p25.state`, `census-014084-fresh/014084-entry-p0-ccr10.state`,
`census-014084-fresh-7251bbd0ecf7/014084-entry-p10.state`, and the first two `-p*` fixtures of every
`census-*` directory (listed in `slide-vp-all/summary.txt`).  Histories: all eight nodes of
`history/gods/` (the five leaves `ca2b703b…`, `fb408bc7…`, `7251bbd0…`, `f0ac1973…`, `f40d7bcc…`
cover every tree edge from power-on).
