# Gods: the 60/30 Hz timing model, VBlank observability and the verification contract

Research report, 16 September 2026.  Read-only study of the checkout at
`ea33e17` plus the grinder's uncommitted `src/gods_sega` working tree; nothing
under `src/`, `tests/`, the histories or the retained evidence was changed.
Every number below was measured on the **original** machine
(`build/libgenesis_native.dll`, the shared PortForge board) from retained
fixtures under `artifacts/gods/evidence/`; the scripts are under
`scripts/research/` and their outputs under `artifacts/gods/research/`.  Where
a statement is an inference rather than a measurement it says so.

The question: which pieces of Gods genuinely depend on exact mid-tick
hardware timing, and which only look difficult because the current verifier
observes the machine at an inconvenient level?

**Short answer.**  The VBlank handler commutes with every witnessed recovered
region (65 fixture runs at two to seven landing positions each, over 17
regions: the game's RAM, registers and 20-tick future are identical wherever
inside the region the VBlank is made to land).  It does *not* commute with the whole game tick:
the tick reads the handler's pad latches and its 60 Hz counters at several
points, so in a tick whose work runs past the odd VBlank the input sample
and the timers are consumed torn.  That is the only mid-tick timing
dependency found, and it is real: adding 4 % of a frame of work per tick to
a heavy stretch of the long recording changes the recorded playthrough at
the first coinciding input event.  Separately, the great majority of the
scheduler refusals the tree reports are not interrupts at all: the replay
observes Gods in the middle of its busy window (the profile's default
instant), and the rest are VDP FIFO stalls after tile uploads.

## 1. The 60/30 Hz timing model, from code and traces

### 1.1 The code

The interrupt vectors (`ROM 000060`–`00007C`) all point at `0003DA` (a bare
`rte`) except the VBlank vector `000078` → `0003DC`; the VDP register table
at `00059A` is `8004 8104 …`: horizontal interrupts are never enabled.  The
only interrupt in Gods is the VBlank.

The game tick loop (`scripts/research/disasm_range.py 1E80 2140`):

```text
001EB4  bsr.w  $52e             ; wait for FFEEC6 to change (one VBlank)
001EB8  move.w $eec8.w,d0       ; low word of the VBlank counter
001EBC  andi.w #1,d0
001EC0  bne.b  $1eb4            ; odd -> wait for another VBlank
001EC2  bsr.w  $1098            ; flush the sprite table + scroll (VDP, in VBlank)
001EC6..0020AA  ~45 calls        ; the game tick (see the census of hot calls)
0020B0..00213E  ... beq.w $1eb4  ; back to the wait
```

`00052E` is `move.l $eec6.w,d0; cmp.l $eec6.w,d0; beq` — a spin on the
counter the handler increments.  So the 30 Hz cadence is an **explicit
parity gate on the VBlank counter** (`FFEEC8` bit 0 at `001EB8`): a tick
starts only on an even count.  The tick counters the game keeps for itself
are `FFEF4C` (mod 4) and `FFEF4A` (mod 2), incremented at `001ED2`/`001EDC`
once per tick, not per VBlank.

The VBlank handler `0003DC`–`0004EC` in full:

| step | effect |
|---|---|
| `movem.l d0-d1/d7/a0-a1,-(a7)` | supervisor stack `FF0040` downward (the game runs in user mode, SR `0000`, on its own USP) |
| `addq.l #1,$eec6.w` | **video time**: the VBlank counter |
| `tst.b $eedf.w; bne` | pause flag (`002872` sets it, `0028D2`/`002900` clear it) |
| `addq.l #1,$f2aa.w` | **elapsed time** at 60 Hz (the conditions module divides by the rate `FFEEC0`) |
| `tst.w $f19e.w; beq; subq.w #1,$f19e.w` | a **60 Hz countdown** (set to 20 × rate at `005A5C`, tested by player code `0065C4`) |
| `tst.w $f3d8.w` | mode: `≠0` reads the pad into `FFF3DA`; `0` reads it through the table `0004EE` into `FFEA1E`/`FFEA20` (direction words) and `FFEA22` (buttons) |
| `move.b #$40,$a10003 … move.b $a10003,d0` (×2) | the controller port: the **input sample** |
| `tst.b $eecc.w; beq; sf.b $eecc.w; move.l #$c0000000,4(a6); 32 × move.l (a0)+,(a6)` | palette-dirty flag: CRAM upload of the 128-byte palette buffer `FFEA6A`..`FFEAE9` |
| `jsr $f4472` | if `FFFE10`: Z80 bus request, copy the 38-byte **sound command block** `FFFDEA`..`FFFE0F` to `A01F80`, release, then fill the block with `FF` (`0F44AA`) |
| `movem.l (a7)+; rte` | every register and the status word restored |

The handler's dynamic write set from the interrupted traces
(`0018C8-entry-p25`, tracer steps marked `[interrupt handler]`): the
supervisor stack `FF0026`–`FF003F`, `FFEEC9`, `FFF2AD`, `FFFDF4`/`FFFDF5`
(the two bytes of the sound block that were not already `FF`); the pad
latches, `FFF19E` and `FFEECC` were unchanged in those traces because the
pad had not changed, the countdown was zero and no palette was pending.  The
static set is the table above.

### 1.2 The traces: where VBlanks land

`scripts/research/tick_timing_census.py` replays the recorded inputs from a
retained state (the mask set at the frame wrap exactly as
`history_runtime.step` does) with gates at `0003DC`, `001EC2` and `001EB4`
and records every VBlank's pre-empted PC and every tick's work length.

| window (fixture, frames) | VBlanks | ticks | VBlanks pre-empting the wait loop | pre-empting game code | ticks with the odd VBlank inside | tick work, frames (min / median / p90 / max) | gaps of 4 VBlanks (dropped tick) |
|---|---|---|---|---|---|---|---|
| `main/boundary-6000.state`, 6000–6600 (`f0ac1973…`) | 601 | 300 | 601 | **0** | 0 | 0.557 / 0.765 / 0.835 / 0.953 | 0 |
| `main/boundary-12000.state`, 12000–13200 | 1201 | 600 | 1192 | 9 | 11 | 0.446 / 0.607 / 0.802 / 1.646 | 0 |
| `census-0018C8-fb408bc7/0018C8-entry-p25.state`, 26348–27548 (`fb408bc7…`) | 1201 | 434 | 993 | **208** | 113 (+3 with two inside, +1 transition of 196 VBlanks) | 0.438 / 0.663 / 1.297 / 196.8 | **3** |

(`artifacts/gods/research/tick-timing-*.json`.)  The VBlank instant is at
frame offset 0.8555 (raster line 224 of the replay's frame, whose wrap is
line 0); a tick starts at offset 0.8674 (right after the handler) and its
work ends anywhere between offset 0.20 and 0.95 of the *next* frame in the
light windows, and past that frame's VBlank in a quarter of the ticks of the
heavy window.  The busy VBlanks of the heavy window land in the loop-body
callees `0129E2` (the level transition), `005700` (the player/object update:
31), `003C96` (map streaming: 25), `00A578` (24), `00FBB6` (the solids pass:
15), `011D88` (9), then a tail.

Measured, therefore: gameplay executes **exactly every second VBlank** —
the parity gate makes the cadence exact, not average — **unless a tick's
work exceeds about 1.99 frames**, in which case the gate waits for the next
even count and a whole game tick is dropped (game time slows by two
frames).  Three of the 434 ticks of the heaviest witnessed window drop; none
of the 900 ticks of the two lighter windows do.  The work length itself is
dominated by VDP FIFO stalls: the sprite emitter's upload arm
(`0018C8-entry-p0-ccr00`) is 121 instructions and 1,662 CPU cycles but
28,056 master ticks (the equivalent of 4,008 cycles) because every
`move.l (a0)+,(a6)` at `001986` stalls 340–682 master ticks during active
display.  A tick's wall time — and so whether it drops — is a VDP-timing
quantity, not a 68000 instruction count.

### 1.3 The four clocks

| clock | where | rate | who reads it |
|---|---|---|---|
| video time | `FFEEC6` (long) | 60 Hz, handler | the wait `00052E`, the parity gate `001EB8`, `001CEA`/`0022A2`/`00BE98`/`00CAFE` (waits), cleared at `002288`/`001CB2`/… |
| elapsed time | `FFF2AA` (long), rate `FFEEC0` | 60 Hz while `FFEEDF` = 0 | conditions kinds 9/10 (`004BA0`/`004BB8`: elapsed ÷ rate vs 5 × argument), `00F456` (9 × rate), saved/restored around menus (`007FFC`/`008040`) |
| a 60 Hz countdown | `FFF19E` | 60 Hz, handler | set to 20 s at `005A5C`; player code `0065C4`, `0067E4`, `006900`, `006A2A` (a speed boost) |
| game time | `FFEF4A`/`FFEF4C` | 30 Hz, the tick | animation phases (`FFEF4C` × 4 added to the scroll at `001EEC`) |

Animation time is game time (the per-tick counters and the recovered
animation step's frame budget), not video time.

## 2. The exact role of VBlank relative to gameplay

Per tick the order is fixed by the code:

```text
even VBlank  H: counters, pad sample -> latches, palette upload if flagged, sound block -> Z80 and cleared
tick start   001098: sprite table (FFEC00.., FFEBF6/F8/FC) and scroll words -> VDP (still in vertical blanking),
             dynamic-tile double buffer swapped (FFEE80/EE82, EE86/EE8A, EE8E/EE90)
tick body    ~45 calls: game logic; dynamic tile uploads into the back buffer (seams); sound requests written
             into FFFDEA..; palette changes written into FFEA6A.. and FFEECC set
odd VBlank   H again -- inside the wait loop in light play, inside the tick body in heavy play
wait         until the counter is even
```

So VBlank is (a) the clock the tick is phase-locked to, (b) the input
sampler, (c) the palette and sound *commit* point, and (d) two 60 Hz
counters the tick reads.  It is **not** a consumer of the sprite list or of
any game object: the tick flushes its own sprite table at the start of the
next tick, and the handler never reads `FFEC00`.., the object tables, the
grid or the solids.  This is the structural reason the region-level
experiments of §5 come out clean: the handler's read set is five words and
two buffers, none of which any recovered region writes.

## 3. Which classes of state the handler observes or alters

Using the three kinds the question asks for:

**Game-semantic state the handler alters**: `FFF2AA` (elapsed), `FFF19E`
(the countdown) — both consumed by gameplay decisions (trigger conditions,
the player's speed boost, the 9-second event at `00F44A`) — and, indirectly,
the pad latches `FFEA1E`/`FFEA20`/`FFEA22`/`FFF3DA`, which are read at 27 +
36 + 32 + 2 sites (`001F20` early in the tick; the pause/reset combination
tests `00287A`–`00288A`; the attract-mode override `00438C`–`00439A`, which
*writes* them from a ROM stream; and the player state machine
`005728`–`006CC6`).  The handler reads the pause flag `FFEEDF` and the mode
`FFF3D8` (game-semantic, written by the tick).

**Platform-visible state**: the palette buffer `FFEA6A`..`FFEAE9` and its
flag `FFEECC` (written by the tick at 13 sites, e.g. `00211C` after the fade
copy at `00210C`–`002118`), the sound command block `FFFDEA`..`FFFE0B`
(written by the tick's request sites, consumed and cleared by the handler),
the controller port, CRAM, the Z80 window.  The sprite table, scroll words
and tile uploads are platform-visible but are committed by the **tick**
(`001098`, the seams), not by the handler.

**Incidental architectural state**: the supervisor stack `FF0000`–`FF003F`
(the game's own stack is the USP, elsewhere), the exception frame, the
handler's register save area.  Every register and the status word are
restored by `movem.l (a7)+` and `rte`, so at the region level the
architectural state *is* irrelevant (the tracer's `region_only` relies on
exactly this and §5 confirms it dynamically) — with one caveat: the
supervisor-stack bytes differ between two runs whose VBlank landed at
different depths, which is why a whole-RAM hash taken at an arbitrary
instant cannot be the equality contract; a hash of RAM at or above the
user stack pointer with `FF0000`–`FF003F` excluded can (§9).

## 4. Do interrupted leaves appear semantically interrupt-transparent?

What the interrupted-trace evidence proves and does not prove.  The tracer
marks the handler's steps and `region_only` drops them; the tests
(`tests/games/gods/test_interrupted_traces.py`) show every interrupted
occurrence maps onto an uninterrupted path class with the same instruction
and cycle totals, and `factcheck check` passes against the region's own
facts.  That establishes: *the region's own instruction path, RAM writes,
register results and CCR do not depend on the handler having run inside
it* — for the landing positions the recordings happened to produce.  It
does **not** establish that the machine after the interrupted activation
equals the machine after an uninterrupted one followed by the handler
(commutation), nor anything about the future; the handler's own effects are
simply set aside.  §5 supplies the missing half.

Note that today the candidate never plans an interrupted occurrence anyway
(`al_atomic` and the engine refuse a span with a pending or in-span VBlank),
so the exactness of the workbench never depended on this question.  What
depended on it is the *fallback count* — and §7.1 shows how small that
dependence actually is.

## 5. Can VBlank be moved across witnessed regions?  Per region

### 5.1 The experiment

Interrupts cannot be masked from Python (`al_atomic` may change the CCR only;
no register write outside a plan), so the handler is moved by moving the
machine's own clock: `scripts/research/vblank_slide.py` restores a fixture
standing at a region's entry, and in run B applies one `Machine.atomic` with
no writes and no register change but a cost of *b* CPU cycles — the 68000
stalls for *b* cycles, the devices run.  The 60 Hz VBlank therefore lands
*b* cycles earlier in the region: at a chosen step, or inside a region whose
VBlank had fallen after the exit.  The engine refuses a stall that reaches
the VBlank instant, so the earliest constructible landing is after the
region's first instruction; the latest is the region's exit.  This is a
legitimate execution of the strict original (a bus stall), not a modified
oracle.

Both runs are single-stepped to the region's exit (the caller's return with
the entry A7 restored) and compared on: every live work-RAM byte (at or
above the user SP) except the handler's own bytes (its counters, latches,
flag, sound block — compared separately), the dead supervisor/user stack
residue (counted, not judged), the full register file, the sound block;
then run through the tick loop head and 20 further tick starts, hashing at
each the masked live RAM, the rendered frame and the VBlank counter.

### 5.2 Results (`artifacts/gods/research/slide-batch/summary.txt`, per-fixture JSON beside it)

65 fixture runs (up to two interrupted and one clean fixture per census
directory, several directories per region), each at two to seven landing
positions, wherever the fixture is close enough to a VBlank for the stall
to be admissible (the atomic cap is 100,000 cycles; fixtures standing near
a tick's start — every `002806`, `004150`, `010A14`, `00BA8E` and `00932C`
fixture tried — are ≈0.98 frame from the VBlank and could not be run: "not
established" below means that, not a failure).

| region | fixtures (kind) | landing steps tried (of region steps) | game RAM + registers at exit | 20-tick future | verdict |
|---|---|---|---|---|---|
| `0018C8` sprite emitter (incl. the upload seam) | p25, p26 (interrupted, two dirs), p0-ccr00 (clean) | 2, 4, 24, 65–155 of 121–249 | equal | equal | **VBlank may slide anywhere in the region: proven on these states** |
| `001164` sibling | p10, p11 (interrupted), p0 (clean) | 2, 7, 17, 25, 26 of 38 | equal | equal | proven |
| `00126A` particle emitter (seam) | p10, p11 (interrupted), p0-ccr00/04/08 (clean) | 2, 5, 25, 79–239 of 14–305 | equal | equal | proven |
| `00FDB8` footprint stamp | p1, p2, p3, p10 (interrupted), p0 (clean) | 2, 10–41 of 27–47 | equal | equal | proven |
| `00FE08` animation step | p2, p16 (interrupted), p0 (clean) | 2, 6–36 of 10–52 | equal | equal | proven |
| `00BCCE` zone check | p13, p15 (interrupted), p0-ccr08, p0 (clean) | 3, 4, 5, 15 of 27–29 | equal | equal | proven |
| `013264` pickup award | p6 (interrupted, 269 steps), p0 ×4 (clean) | 3, 12, 17, 87, 192 of 26–269 | equal | equal | proven |
| `014084` hazard tick ('spawn': writes a sound request) | p0-ccr10 ×4 (clean) | 3, 13, 14, 24, 33 of 42 | equal (sound block differs at exit: consumed by the moved handler, see §7.3) | equal | proven for RAM; audio delivery frame moves (§7.3) |
| `00F828` proximity | p0 ×2 (clean) | 2, 10, 29, 39, 88, 137 of 188 | equal | equal | proven |
| `00FC8E` solid drawer | p0-ccr08, p0-ccr18 ×2 (clean) | 3, 4, 9–47 of 33–64 | equal | equal | proven |
| `00462C` evaluator | p0 ×2 (clean) | 3, 8–52 of 75 | equal | equal | proven |
| `00470C` conditions | p0, d5-0000-p0 (clean) | 5 of 6 (landing at the region's exit only) | equal | equal | proven at the exit; the region is 6 instructions |
| `0063FA` grid cell | p0, p0-ccr04 (clean) | 3 of 9 | equal | equal | proven |
| `00364C` score conversion | p0 (clean) | 2, 3, 14, 20, 36 of 52 | equal | equal | proven |
| `010332` countdown check | p0 (clean) | 3 of 5 | equal | equal | proven at the exit |
| `014A3C` | p0-ccr04 (clean) | 2, 3 of 8 | equal | equal | proven |
| `0049DA` spawn queue | p0-ccr08 (clean) | 2, 3, 7, 13 of 19 | equal | game RAM equal at every tick start, **VBlank counter +2 from the first tick start** | proven for the region; the 0.59-frame stall it needed pushed the whole tick past two frames — a dropped tick (§7.2), not a property of the region |
| `002806`, `004150`, `010A14`, `00BA8E`, `00932C` | — | — | — | — | **not established with this tool** (VBlank too far from the entry for an admissible stall; a fixture parked later in the tick would do) |

Several fixture runs (`00470C d5-0000`, `00FE08 p0`, `0063FA p0`,
`00FC8E p0`, one `001164 p0`, one `00462C p0`) also failed the *future*
part because the continuation did not reach `001EB4` within four frames (a
transition in progress in that census directory's history); their exit
comparison was equal and the same fixtures passed in full from another
directory.

Three of the 65 fixture runs report DIFFERS and all three are the `0049DA`
dropped-tick case: the game's RAM is identical tick for tick, the VBlank
counter is two ahead — the same game states two frames later, which the
60 Hz counters will eventually make visible.

**What this proves.**  For every region above, R-prefix → H → R-suffix and
R → H (or the original's own ordering) leave the game's RAM, the register
file and the next 20 ticks identical, with a constant pad.  The handler and
these regions are independent: no region writes a byte the handler reads
(the five words and two buffers of §1.1), and the handler writes nothing a
region reads later in the same activation.

**The one region-level hazard the experiment could not exercise.**  The
handler's palette upload sets the VDP address (`move.l #$c0000000,4(a6)`)
and does not restore it.  A VBlank landing inside a seam's tile-upload loop
(`0018C8`: `001984`–`001988`; `00126A`: `0012F4`+) *while `FFEECC` is set*
would therefore redirect the rest of the tile data to CRAM address 0 —
corrupting the palette and losing tiles.  The measured equality of the
upload seams under a landing inside the loop (steps 65–155 of
`0018C8 p0-ccr00`) shows only that the flag was clear at those instants,
which is the ordinary case (`00211C` sets it at the end of the tick, after
the drawing).  Whether the game ever sets the flag while a seam upload can
still be interrupted is a property of the tick's ordering (the other
setters `0006FC`/`000C96`/`000CCE`/`000D46`/`007E28`/`007E54`/`00BE78`/
`00D306` run from other contexts) and should be censused before any
normalization touches the seams (§11).  On real hardware this would be a
one-frame palette glitch in a heavy tick, not a gameplay divergence.

## 6. Natural semantic cut points larger than instructions

Yes, and Gods hands them over directly:

1. **The tick start `001EC2`** (equivalently the loop head `001EB4` once the
   parity gate has passed).  The supervisor stack is empty, the user stack
   is at the main loop's depth, no plan is in flight, the handler has just
   run, the sprite list of the last tick is complete and about to be
   flushed.  Everything gameplay-relevant is in RAM plus two platform
   buffers.  The tick-timing census shows it is reached exactly once per two
   VBlanks in normal play.
2. **The wait entry `001EB4`** (the tick's end): the same state before the
   odd VBlank has been seen.  It is the right place to observe *the tick's
   output* (sprite list, requests, palette, RAM) before the handler
   consumes any of it.
3. **The VBlank instant itself** as a 60 Hz event boundary.
4. Inside the tick, the ~45 top-level calls of the loop body are the
   subsystem boundaries the semantic map should name; the loop body is
   straight-line except three mode branches (`FFEF14`, `FFF210`, `FFEF3C`).
5. Inside `001098` the video commit is one contiguous block; inside the
   handler the palette and sound commits are two contiguous blocks.

The replay's observation instant is none of these: `observation_offset_ticks`
for Gods is the profile default (`FRAME_TICKS // 2`, raster line 131),
which the census shows falls inside the tick's work for 269 of 300 ticks in
the light window and 281 of 434 in the heavy one.  Gods is idle just
*before* the VBlank (offset ≈0.85) in both frames of a normal tick, and
during the whole second frame when its work ends before the odd VBlank.

## 7. The true hard temporal cases

### 7.1 What the scheduler refusals actually are

`scripts/research/refusal_classifier.py` wraps `Machine.atomic` in a
candidate run from a retained state and classifies every refusal *before*
the native call: `deadline` when the plan's cycles reach the caller's
deadline (the observation instant; the first test in `al_atomic`),
`engine-irq-in-span` when the next VBlank instant lies inside the plan's
cycles, `engine-other` otherwise (the engine's remaining conditions:
`vdp.stall_master`, `bus.access`, the trace bit, a Z80 bank over work RAM).

| window, candidate | admitted | deadline | engine, VBlank in span | engine, other | seam deadlines |
|---|---|---|---|---|---|
| 6000–6600 `camera-sprites` (light) | 7,471 | 15 | **0** | 45 | 0 |
| 6000–6600 `camera-sprites`, instant moved to offset 0.845 | 7,486 | **0** | 0 | 45 | 0 |
| 26348–27548 `sprites` (heavy) | 4,627 | 12 | **0** | 28 | 24 |
| 26348–27548 `sprites`, instant at 0.845 | 4,672 | 0 | 0 | 28 | **1** |
| 26348–27548 `sprites-static` (heavy) | 2,495 | 4 | **4** | 5 | 0 |
| 26348–27548 `particle-emit` (heavy) | 622 | 0 | 0 | 1 | 0 |
| 26348–27548 `particle-emit`, instant at 0.845 | 609 | 2 | 0 | 1 | 10 |

The "engine-other" refusals all occur at frame offsets 0.06–0.15 (raster
lines 16–40, just after active display begins), at gates that follow a VDP
upload (`00198C` is the seam resume right after the tile loop; `0018C8`,
`00126A`, `014084` are entered right after other uploads).  Inferred, not
measured (the flag is not exported): they are the engine's
`vdp.stall_master` guard — the FIFO is still draining when the plan asks to
be charged exact cycles.  They are exact by construction and have nothing
to do with interrupts.

So of the tree's 7,199 "scheduler admission" fallbacks (plus 3,728 seam
deadlines), the part that is genuinely *an interrupt inside the span* is —
by inference from these windows, not measured on the tree — a few per cent
(4 of 13 in the heaviest window for the one region long enough to catch
it; 0 of 40 for the emitter; 0 of 60 in the light window, where no VBlank
ever lands in game code).  `STATUS.md`'s explanation of
this class ("an interrupt is due inside its span") describes the minority.
The majority is the observation instant sitting in Gods' busy window, and a
second class is the FIFO stall guard.  Moving the instant to offset 0.845
removes every deadline refusal and all but one seam deadline in the
windows measured; in the heavy window it also moves *which* gates the
remaining busy instants hit (the late-tick drawing instead of the mid-tick
logic), which is why `particle-emit` alone gets worse there — the total
falls.

### 7.2 Dropped ticks

A tick whose work exceeds ≈1.99 frames drops a game tick (3 of 434 in the
heavy window; the 196-VBlank level transition drops 97).  The decision
depends on the tick's wall time, which §1.2 shows is dominated by VDP FIFO
stalls during active display.  A source port with its own clock never drops
(or drops differently); the two 60 Hz counters then diverge from the
recording's, and the trigger conditions on elapsed time and the player's
countdown fire at different world states.  This is Aladdin's "work frames"
problem (decompression, screen draws) reappearing inside ordinary gameplay,
and it is the first genuinely hard case: **reproducing a recording through
a heavy window requires the original's tick work time** — a machine
quantity — or an aligned clock that asks the oracle how many VBlanks each
tick consumed (Aladdin's `OracleClock` shape), or the acceptance that the
recording becomes a slightly different playthrough under the port's
contract (Aladdin's independent mode).

### 7.3 Torn input and 60 Hz reads inside a heavy tick

`scripts/research/phase_shift_sweep.py` replays the recorded inputs and, in
run B, stalls the CPU by *b* cycles at `004150` in **every** tick (the
game's work is *b* cycles longer from then on, so the odd VBlank lands *b*
cycles earlier in every tick's logic while the input still changes at the
same wall-clock frames).  Tick-start observations as in §5.

| window (frames, input events) | +b per tick (frame) | ticks | game RAM at tick starts | first difference | VBlank counter |
|---|---|---|---|---|---|
| 6000–7200, 135 events | 5,000 (0.04), 20,000 (0.16), 45,000 (0.35) | 544 | **all equal** | — | equal |
| same | 60,000 (0.47) | 544 | 322 differ | tick 222 (frame 6443): `FFEC2A`/`FFEC35` (the player's sprite record), `FFF191`/`FFF193`/`FFF1A3`/`FFF1A7` (player state); an input event at frame 6442 | equal |
| same | 90,000 (0.70) | 544 | 514 differ | tick 30 (frame 6059), same bytes, input event at 6058 | equal |
| 12000–13200, 163 events | 5,000, 20,000 | 601 | all equal | — | equal |
| same | 45,000 (0.35) | 600 | 385 differ | tick 215 (frame 12431), player bytes, input at 12429 | +2 from tick 214 (one drop) |
| 26348–27548 (`fb408bc7…`, heavy), 71 events | 500, 2,000 | 435 | all equal | — | equal |
| same | **5,000 (0.04)** | 435 | **377 differ** | tick 58 (frame 26470): `FFED11`/`FFED12`/`FFED1D` (sprite record), `FFF191`/`FFF193`/`FFF1A3`; input events at 26468–26469 | equal |

(`artifacts/gods/research/phase-shift-*.json`.)  The mechanism, from the
addresses and the code: the player update (`005700` → `0057xx`–`006Cxx`)
reads `FFEA1E`/`FFEA20`/`FFEA22` and `FFF19E`; when the odd VBlank lands
before those reads the tick consumes the *new* sample one tick earlier
than the original did, and the trajectories part.  In the light window the
VBlank must be pulled ≈0.47 frame earlier to reach the player code; in the
heavy window, where a quarter of the ticks already run past the odd
VBlank, 4 % of a frame is enough.  Nothing else moved: pad latches, the
countdown and the elapsed counter are equal at every tick start in every
run, and no other RAM byte differed before the player bytes did.

This is the second hard case, and the precise statement of "input sampled
at the wrong time" for Gods: **which VBlank's sample a tick consumes is a
function of the tick's work time.**  Light windows: always the even
sample.  Heavy windows: the odd sample for the reads that follow the
VBlank, in the ticks that run long.  A port that samples once per tick
matches the original everywhere the original's tick finished inside its
first frame — 100 % of the two light windows, 74 % of the heavy one — and
is *undetectably different* elsewhere unless an input changed in exactly
that frame.

The same mechanism, one step weaker, applies to the sound block (a request
written after the odd VBlank's clear is delivered one frame later; the
region-level experiment shows the block "differs at exit" whenever the
VBlank crossed the exit, which is the same delivery-frame question), to the
palette (`FFEECC` set before or after the odd VBlank decides which frame
shows the new colours) and to the two 60 Hz counters read mid-tick
(`0065C4`, `004BA0`/`004BB8`, `00F456`): all decided by where the odd VBlank
falls, all invisible in light windows.

### 7.4 Everything else is not hard

The 17 witnessed regions commute with the handler (§5).  The tick loop
body is straight-line.  Video is committed by the tick at its own start,
into a double-buffered tile area.  The RNG question does not arise from the
handler (it writes no RNG state).  The open address error of `STATUS.md`
(`012E46`: `FFF01E` retired between `008306` and `012DD6`) involves no byte
the handler touches; it is the game's own ordering inside a tick, and the
only timing path into it is the torn-input path of §7.3 (a different
player action in a heavy tick).

### 7.5 Aladdin, as evidence

Aladdin was easy for a measurable reason (`execution-model-research-2026-09-14.md`
§2–3): the 68000 idles from raster line 60 to 224 (60 % of the frame), the
contact tick is 2 % of a frame and starts at line 256, and
`interrupts_during_trace` was 0 for the straddling parents — the VBlank
never landed inside a bounded region; the only boundary the tick crossed
was the replay's own wrap, fixed by moving the observation instant.  Its
hard cases were the same two Gods has, in different clothes: the kind-21
command-stream tick (83 % of a frame with one interrupt inside — Gods'
heavy tick), and work spanning frames with input latched from stale pad
bytes during decompression (`native-frontier.md` §1: the handler run per
elapsed frame, the two port reads falling on either side of the wrap "once
in six thousand frames" — Gods' torn input, at a far lower rate).  Aladdin
solved the first by never owning that tick (escalated, still original) and
the second cleanly at the platform level (the handler's RAM effects per
elapsed frame are platform semantics; the input rule was made faithful,
then a declared independent contract).  What was *aligned by tooling*
rather than solved: the oracle clock that tells the native runtime how many
VBlanks a transition consumed.  Gods will need the same instrument inside
gameplay, not only in transitions.

## 8. Are persistent recovery continuations necessary?

No — on the evidence, in neither concept where they might have been argued
for.

*In the workbench*: an interrupt inside a plan's span is refused today and
the original runs the activation, exactly.  §7.1 measures that class at a
few per cent of the refusals; §5 shows the handler commutes with every such
region, so an adapter that kept recovered code owned across the VBlank
would buy nothing the fallback does not already give, at the cost of a
second state authority.  The recovery-process document's rule (a temporal
adapter only for a specific witnessed interaction that seam and atomic
cannot own) is met by no Gods region.

*In the port*: the tick's semantics decompose at the cut points of §6.
Where composition later shows *update phase A → commit → update phase B*
(here: `001098` commit → logic → the handler's commits at the next VBlank),
the port keeps that ordering directly.  The handler is a platform service
run once per VBlank with the pad sample, the two counters, the palette and
sound commits; the only design decision is §7.3's sampling contract, which
is a *statement*, not a continuation.

## 9. A layered verification contract that stays strong as boundaries rise

The principle: two states equivalent at boundary B only if every future
behaviour under the same admissible inputs is equivalent over the declared
domain.  No finite check proves that; each layer below states what
approximates it and what would slip through.

**L0 — exact architectural boundary (today).**  `factcheck check` MATCH on
every retained path class; every-frame state hash, video, PCM, counters in
two fresh workers.  Strongest local statement; blind only to arms no
recording entered.  Keep as the oracle tier; nothing above replaces it.

**L1 — subsystem composition.**  Complete effect set (every RAM byte, the
register file, the CCR incl. X) at the subsystem's exit *plus* the
20-to-300-tick future from retained states (`segment_verify`) *plus* the
commutation witness of §5 for any subsystem the port will run at a
different instant than the original.  Adds to L0 exactly what §5 measures:
the subsystem's independence from the platform event it will be moved
across.

**L2 — the logical game tick.**  At the cut `001EC2` (or `001EB4`), compare:
(a) the game's RAM at or above the user SP with `FF0000`–`FF003F` excluded
and **nothing else masked** — the two 60 Hz counters, the countdown and the
pad latches are *part of the contract* here because at the cut their values
are determined by the VBlank count, and masking them is what would hide a
dropped tick; (b) the ordered **platform event stream** of the tick, taken
from the original by gating the VDP control writes, the pad reads and
`0F4472`: the sprite-table words and scroll words flushed at the start, each
tile upload (VRAM address, word count, data hash), the palette upload if it
happened and at which VBlank, the sound block transferred and at which
VBlank, and the *pad sample index* consumed (which VBlank's latches the
player code read: even, or odd-after-tearing); (c) the VBlank count and the
tick counters `FFEF4A`/`FFEF4C` — so a dropped tick is a first-class
difference.  A port at this layer states its timing contract (§10) and is
compared *under it*, exactly as Aladdin's `--independent` runs are.

**L3 — long trajectory.**  Replay inputs from power-on; chain the L2 tick
hashes; compare per-frame video hashes and the per-frame audio event stream
(the Z80 command block as transferred, per VBlank — the PCM digest is the
strict form and remains available while the machine is the sound backend);
report the first differing tick and classify it by the L2 component that
differed (RAM, stream, counters).

**L4 — adversarial.**  The mutations of §10 must be *detected* at the layer
that claims to cover them, with the tick and bytes named.  A layer with no
detected mutation is not evidence.

Why this is stronger than "position and score" and less machine-shaped
than a snapshot: the tick RAM covers every hidden variable (timers,
countdowns, spawn queues, coroutine continuations stored in records, pool
tables, the grid, the undo list) because they are all bytes in the same
64 K; the event stream covers what RAM cannot (what was committed to the
VDP and Z80 and *when*, in VBlank units); the counters cover time itself;
and the future-window and chaining make "same now, different later"
visible at the first tick it becomes RAM.  What it still cannot see:
VRAM/CRAM contents that no stream entry and no rendered frame reveals
(mitigated by the per-frame video hash), and Z80-internal state (mitigated
by the transferred-block stream and, while available, the PCM digest).

## 10. Negative controls an insufficient contract must fail

Each row names the way a contract could pass wrongly and the mutation that
must be *rejected* (the layer in brackets).

| hazard | mutation / control | detected by | measured |
|---|---|---|---|
| event a frame early/late (palette) | set `FFEECC` one tick late, or commit CRAM at the even instead of the odd VBlank | per-frame video hash of the odd frame; L2 stream's "palette at VBlank n" [L2/L3] | not run; the stream is not built yet |
| input consumed at the wrong time | the phase-shift sweep of §7.3 (+0.04 frame/tick in a heavy window; +0.47 in a light one) | tick RAM at the first coinciding input event: `FFF191`/`FFF193`/`FFF1A3`, the player's sprite record | **detected at tick 58 / 222 respectively; a contract with only player X/Y would see it a few ticks later, one with only score would not** |
| intermediate state visible to VBlank | set `FFEECC` before the 8-long palette copy `00210C`–`002118` completes; interrupt a seam upload with the flag set | video hash of that frame; the seam's own guards do not cover it | not run — the census of §11 comes first |
| audio delayed | deliver the block one VBlank late | PCM digest per frame (L0); L2 stream "block transferred at VBlank n" | PCM: existing negative controls already diverge on a byte off; the stream: not built |
| partially produced render buffer committed | flush the sprite table at `001098` before the list is complete (impossible in the original ordering; a port mutation) | video hash of the next frame; L2 stream (record count `FFEBF6`) | not run |
| RNG / hidden timer drift | the dropped-tick control: a 0.59-frame stall in one tick (§5, `0049DA`) — RAM identical for 20 ticks, `FFEEC6` +2 | a contract that masks the counters **passes wrongly**; L2 with counters in the hash rejects it at the first tick start | **measured: my own region-level mask hid it; the separate counter check caught it** |
| transition takes the wrong number of ticks | the 196-VBlank level transition; any port that spends work in zero frames | VBlank count and tick counters at the cut; Aladdin's checkpoint-and-work model | measured for the original only |
| same current state, different future | a candidate mutant that fixes the exit state but not a byte read two ticks later | the future window and the hash chain; segment_verify with `--frames` ≥ the longest countdown (the 20 s boost: 600 ticks) | existing mutants diverge within frames; the long-countdown case argues for a longer segment window |
| the pre2 weakness: fitted to the oracle | a per-recording table of drop frames or sample indices | forbid tables keyed by frame; the independent run (no oracle after the seed) must still pass on the light windows and be *reported* as a different playthrough on heavy ones | Aladdin's rule; adopt as written |

## 11. The smallest next experiment that distinguishes the competing models

The competing models are: (A) "Gods gameplay is interrupt-transparent; the
VBlank is a clock and a sampler and everything can be normalized to the
tick cut" versus (B) "mid-tick hardware timing is load-bearing".  §7.3
already shows the answer is A for light play and B for heavy play through
exactly one channel (the player code's reads of the latches and counters
relative to the odd VBlank), plus the drop rule.  The experiment that
settles what remains costs an hour and needs no new mechanism:

1. **Census the odd-VBlank exposure over all eight recordings**: run
   `tick_timing_census.py` from the retained boundary states and, for the
   recordings without one, from the first census fixture of each
   (`fb408bc7…`, `7251bbd0…`, `f40d7bcc…`), full length.  Report per
   recording: ticks with the odd VBlank inside gameplay code, dropped
   ticks, and how many of the exposed ticks coincide with an input event.
   That number is the exact size of the part of the recordings a port
   under a "sample at the even VBlank, never drop" contract cannot
   reproduce — and whether it is 0.1 % or 5 % decides whether the
   independent contract alone is acceptable or an aligned clock is needed
   inside gameplay.
2. **Census `FFEECC` at seam entries**: gate `0018C8`/`00126A`/`00FC8E`'s
   upload arms and read `FFEECC` at the first `move.l (a0)+,(a6)`; if it is
   ever set, the §5.2 CRAM-redirect hazard is live and the seams' identity
   guards must include it before any normalization of the seam's timing.
3. **Re-run the tree's fallbacks under the moved instant** (a single
   `--tree` run with `observation_offset_ticks = int(0.845 * FRAME_TICKS)`
   — 757,154 — set for the run only, or as a profile change with the cache
   contract bumped) to turn §7.1's window measurements into the tree's own
   numbers.

## 12. Recommendations for the supervisor

**Safe to adopt now**

- Set Gods' `observation_offset_ticks` to the measured idle instant just
  before the VBlank (≈0.845 × `FRAME_TICKS` = 757,154; raster line ≈221),
  with the `cache_contract` bump and a re-verification, exactly as Aladdin's
  stage 8 did.  Measured: every deadline refusal and all but one seam
  deadline disappear in the windows tested; the input instant stays at the
  wrap; the trajectory is untouched by construction.  Expected (not yet
  measured on the tree): the 3,728 seam deadlines and most of the 7,199
  admission fallbacks go; the FIFO-stall residue stays.
- Correct `STATUS.md`'s explanation of the `scheduler admission` class:
  mostly the observation deadline, then the VDP FIFO-stall guard, and a
  small interrupt-in-span residue.  Have the dispatcher record the three
  causes separately (`refusal_classifier.py` shows the split is decidable
  before the native call).
- Make the tick cut (`001EC2`/`001EB4`) the unit of the Gods semantic map
  and of every future "subsystem" verification (L1/L2 above): the
  tick-start RAM-above-USP hash with `FF0000`–`FF003F` excluded is a
  legitimate equality witness; a whole-RAM hash at an arbitrary instant is
  not, because of the supervisor-stack residue.
- Add the VBlank-slide check (`vblank_slide.py`) to the leaf review for any
  region long enough to be interrupted in the census (`001164`, `0049DA`,
  `0018C8`, `00126A`, `013264`): it is a one-second, fixture-based, strict-
  original test of the commutation the tracer's `region_only` assumes.
- Fix the grinder's working-tree defect found on the way: the uncommitted
  `boundary.py` `_pickup_award_cost` raises `KeyError: -4` instead of
  `UnsupportedCandidate` on the code −4 pickup arm (it aborted every
  `camera-sprites` run over `fb408bc7…` 26348–27548 here).

**Needs more evidence**

- The size of the torn-input/drop exposure across all eight recordings
  (§11.1) before choosing between "independent contract only" and "aligned
  clock inside gameplay" for the port.
- The `FFEECC`-during-upload hazard (§11.2) before any change to how the
  seams are timed.
- Whether the sound block is ever written twice into the same slot within
  one tick (a request lost or kept depending on the odd VBlank): gate
  `0F446C`'s request sites over a heavy window and count same-slot writes
  between VBlanks.
- The regions not reached by the slide tool (`002806`, `004150`, `00364C`,
  `010A14`, `010332`): park fixtures later in a tick and repeat; expected
  to pass for the same structural reason, but "not established" until run.

**Do not build yet**

- Any temporal adapter or recovered-code continuation across the VBlank:
  the interrupt-in-span refusals are a few per cent of a class that is
  itself about to shrink by an order of magnitude, and the handler
  commutes with every region it would have been built for.
- A tick-level equality contract that masks the 60 Hz counters or the pad
  latches: the dropped-tick control shows it passes wrongly.
- A per-recording table of sample indices or drop frames for the port:
  it is the pre2 fit.  The port states its sampling and drop contract; the
  oracle is checked under it; heavy windows are reported as input variants
  until an aligned clock inside gameplay is justified by §11.1.
- A modified oracle of any kind.  Every experiment here ran the unmodified
  machine; the only intervention was a CPU stall, which the machine also
  performs on its own during DMA and FIFO waits.

## Files, fixtures and re-run commands

Scripts (new, under `scripts/research/`; each opens and closes its own
`Machine`; `GENESIS_NATIVE_LIBRARY` set to `build/libgenesis_native.dll`):

- `disasm_range.py START END` — disassembly of a ROM range via
  `pathfacts.disasm` (used for `0003DC`–`000560`, `001098`–`001164`,
  `001D90`–`002160`, `004B96`–`004BD0`, `005A50`–`005A70`, `0065B8`–`0065D4`,
  `00F44A`–`00F470`, `0F4472`–`0F4530`).
- `tick_timing_census.py --fixture F --frames N [--json OUT]` — §1.2;
  outputs `artifacts/gods/research/tick-timing-6000-6600.json`,
  `tick-timing-12000-13200.json`, `tick-timing-fb408bc7-26348.json`.
- `refusal_classifier.py --fixture F --frames N [--candidate C] [--offset T] [--verbose]` — §7.1.
- `vblank_slide.py FIXTURE [--ticks 20] [--positions 3] [--json OUT]` — §5;
  `slide_batch.py [--only PC,PC] [--ticks 20] [--positions 3]` runs it over
  every census directory; outputs `artifacts/gods/research/slide-batch/`
  (`summary.txt`, `summary.json`, one JSON per fixture) and
  `slide-0018C8-p25.json`.
- `phase_shift_sweep.py --fixture F --frames N --burns a,b,c [--burn-gate 004150] [--json OUT]` — §7.3;
  outputs `phase-shift-6000.json`, `phase-shift-12000.json`,
  `phase-shift-fb408bc7-26348.json`.

Fixtures read (never written): `artifacts/gods/evidence/main/boundary-6000.state`,
`boundary-12000.state` (`f0ac19738f19…`, frame-boundary states);
`census-0018C8-fb408bc7/0018C8-entry-p25.state`, `-p26.state`,
`-p0-ccr00.state` (`fb408bc75597…`, frame 26348); the first interrupted and
first clean fixture of every other `census-*` directory as listed in
`slide-batch/summary.txt`.  Histories: `history/gods/` nodes
`f0ac19738f19…` and `fb408bc75597…` for the recorded inputs.

Machine facts relied on: `native/machine.cpp` (`al_atomic`: deadline test
first, work-RAM writes only, CCR-only SR changes, the engine's own
admission afterwards), the donor engine's `use_native` condition
(`genesis_engine.hpp` lines 351–360: bus access, `vdp.stall_master`, trace
bit, VBlank requested, next admission instant), `history_runtime.step`
(input at the wrap, observation at `wrap + observation_offset_ticks`),
`src/genesis_re/profile.py` (Gods inherits the default offset).
