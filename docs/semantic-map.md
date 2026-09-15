# Semantic map of the 82,161-frame recording

Written 15 September 2026 from the existing `main` history alone.  Every
name below carries a confidence mark and the evidence that supports it.
Method: the original was replayed once while recording per-frame RAM
change activity and 64 KB snapshots every 32 frames
(`artifacts/cartography/ram_activity.npz`); one frame in every 250 was then
traced instruction by instruction with routine attribution, call edges and
memory operands (`artifacts/cartography/dense2`); load frames, the game
start and the first score change were traced separately; the checkpoint
screenshots supplied ground truth for the HUD; and object sprites were
isolated by deactivating one object in a scratch copy of the machine and
diffing two rendered frames (`artifacts/cartography/masks`).  Nothing here
comes from a single clue.

Confidence: **CONFIRMED** = read directly from the code plus at least one
independent runtime observation; **STRONG** = two independent runtime
observations that agree; **TENTATIVE** = one observation or an inference.

## 1. The frame

The game is frame-locked.  A frame costs about 10,200 instructions
(median; 90th percentile 10,440; maximum 14,866 -- there are no heavy
frames at all), of which 70 to 83 percent are the idle loop at `1B249E`
(`clr.b FF7E1E`, then `tst.b FF7E1E / beq` until the VBlank handler sets
it).  **CONFIRMED.**  The remaining 2,000 to 3,000 instructions are the
game.

Main loop order, identical in every gameplay sample (329 samples):

```
1AC726  tick timers (FF8880 table, FFEFEF)                 STRONG
1AB776  ?  (reads FF729A, FFEFEC)                           TENTATIVE: pad/latch bookkeeping
1AE0F6  sound queue tick (FFF57C, FFF140)                   TENTATIVE
1AAA2A  camera scroll (FF7DA4 -> level scroll routine) and
        spawn-strip triggers FFF0B9..BC -> 1AB34E/1AB44C/1AB66C/1AB55A   CONFIRMED
1B315C, 1E571C x2  sound driver service                     STRONG
1A91C6 -> 1B3208  VDP/DMA queue flush (FF7E25)              TENTATIVE
1A8E0C  publish player world position (FF7E02/04, FF7E42/44) CONFIRMED
1AD7B4  player ground collision (FF98C4 row table, FF7DBC)   CONFIRMED
1AD632  player wall/ceiling collision, floor type FFF0CB/C5  STRONG
1A986E  jump input                                           CONFIRMED
1A99F0  attack input (sets FFF0D7)                           CONFIRMED
1ADE36  object motion: runs each object's secondary script channel,
        moves objects, computes screen positions FFF090/92   STRONG
1ADB5C  object level collision (reads FF9884, writes +04)    TENTATIVE
1ABB40  contact step: player-vs-object collision scan with the
        per-kind callbacks the grinder recovered              CONFIRMED
1B321C 1B3212 1B3226 1B3230  VDP scroll/plane updates        TENTATIVE
1B1E38  special tile under the player -> FFF0DB              TENTATIVE
1A9D98  horizontal player control (pad -> facing, speed)     CONFIRMED
1A9716  player state transitions (FFF0BE, animation)         STRONG
1AA8FA  camera follow (lookup tables 2A52/2BA4, window FF7DFE/FF7E00) CONFIRMED
1A9304, 1A9502  player state machine / animation selection   STRONG
1ABD7E  contact completion
1B02EC  HUD: health bar (reads FFEFFA, FF7E28)               STRONG
1A8F0C  fall-off-level check (FF7E04 vs FF7DBC, FFF0E6)      STRONG
1A8F04  ?
1B00CA  score tally: FFF14E points -> ASCII digits FF7E2A..2E CONFIRMED
1B01AC  HUD: counters                                        TENTATIVE
1A8E3E  death sequence timer FFF0E9                          STRONG
1AC784  animation script interpreter over 32 object records  CONFIRMED
1AB7C4  sprite table builder: objects, player, HUD digits     STRONG
1B249E  wait for VBlank                                      CONFIRMED
```

Modes.  Title, level-name cards and loading frames call only `1B3736`
(+`1B3778`) or `1B38B8` (+`1B38FA`): decompression/upload loops (34,000
instructions at frame 380 and 12,958).  Level-name cards (25,640, 50,240)
run `1AC726 1AB776 1B1432 1E571C 1B28AE`.  At a level start (975, 12,973,
69,391) the loop runs a reduced cycle `1AAA2A 1AB44C 1AC726 1AB776 1ADE36
1AC784 1AB7C4` eleven to sixteen times inside two frames: a pre-roll that
places the level's objects before the first displayed frame.  **STRONG.**

## 2. Player

Record.  The player is object slot 0 at `FF7E40` (66 bytes, kind byte
`0x83`); the 24-slot main pool follows at `FF7E82`, and six more slots at
`FF84B2` (32 records in all, walked by the interpreter).  **CONFIRMED**
(interpreter loop `lea FF7E40,a1 / move.w #$1F,d4 / adda #$42`).

| field | name | confidence | evidence |
|---|---|---|---|
| FF7DF6 / FF7DF8 | camera X / Y (world) | CONFIRMED | parallax scroll code at 1AAA88 negates FF7DF6 into the VDP hscroll; 1AA8FA moves it against FF7DFA to keep the world position fixed |
| FF7DFA / FF7DFC | player screen X / Y (relative to camera; Y has a +192 plane offset) | CONFIRMED | `1A8E0C`: FF7E02 = FF7DF6 + FF7DFA, FF7E04 = FF7DF8 + FF7DFC; identity holds in 2,326 of 2,340 snapshots |
| FF7E02 / FF7E04, FF7E42 / FF7E44 | player world X / Y (published each frame) | CONFIRMED | same routine; every contact callback compares `2(a1)` against FF7E02 |
| FF7E58 / FF7E5A | player X / Y velocity (sub-pixel, applied in 0x28 / 0x3C steps) | CONFIRMED | `1A9B90`; jump sets FF7E5A, landing clears both |
| FF7E49 | facing (00 right, FF left) | CONFIRMED | `1A9D98` clears it on right, sets on left; every callback's direction test |
| FFF07C / FFF07D | right / left held | CONFIRMED | `1A9D98` |
| FFF07C..FFF07F | right / left / up / down held (FF), from the raw pad bytes FFF156 (TH high) and FFF155 (TH low) | CONFIRMED | main loop 1A8C44..1A8C86 (`game.pad`); B, C, A and Start are tested from the raw bytes by 1B3244 / 1B324E / 1B323A / 1B3208 |
| FFF0B0 | walk speed (word; 3 = running) | CONFIRMED | `1A9D98` adds it to FF7DFA; the idle script 122006 writes it with opcode ED |
| FFF0CC | walking flag | STRONG | `1A9D98` sets 1 when moving; idle script tests it |
| FFF0D0 | in air | STRONG | set by the jump handler, cleared on landing, tested by the attack script |
| FFF0C1 | on ground | STRONG | written every frame by ground collision 1AD7B4, read by control and animation |
| FFF0D7 | attacking (sword) | CONFIRMED | `1A99F0` sets it; opcode F8 selects script 121964 when set |
| FFF0D8 | sword hit-box active | CONFIRMED | written only by the interpreter (opcode ED in the attack scripts); every enemy callback branches on it (hit vs touch) |
| FFF0CD, FFF0D3 | hanging / ledge state | TENTATIVE | 1ABB40 writes both; control skips when FFF0D3 == 0x5E |
| FFF0DB, FFF0DC | special-tile poses (the sink pose, the grab pose's four-frame hold) | STRONG | `game.tiles` |
| FFF0DE / FFF0DF | crouching / looking up | CONFIRMED | `game.control` (1A9FBE / 1AA060 set them with scripts 1222D2 / 122236) |
| FFF0ED | pushing against a wall or object (the push pose 121FA6 is up) | STRONG | `game.control` |
| FFF0BF | frames the jump button has been held, 1..10 (10 = full height) | CONFIRMED | 1A9716 |
| FFF11F / FFEFFF | throw / sword cooldown frames (14 / 10) | CONFIRMED | 1A9304 / 1A9502 |
| FFF0C5..FFF0CB | wall sensors: left near/far/farther, right near/far/farther, ceiling | CONFIRMED | 1AD632 (`game.player.wall_sensors`) |
| FFF0C3 | the collision class of the cell under the player (0x47 = the layer switch, 0xB0 = wall-stand) | CONFIRMED | 1B1E38 |
| FFF0A4 | which attribute byte carries the ground (the layer switch toggles it) | CONFIRMED | 1B5470 / 1B5492 / 1B549C |
| FFF0EE | hurt walk timer (speed 1 while set) | STRONG | 1AE722, 1A9D98 |
| FFF0F0 / FFF0EF | blocked right / left by an object this frame | STRONG | contact callbacks, 1A9D98 |
| FFF0D6 / FFF0CE / FFF0CF | attack allowed / climbable / climb-up blocked, from the tile under the player | STRONG | 1B1E38 handlers |
| FFF15A / FF7286 / FF728A | message code, callback, pen advance | CONFIRMED | 1B2238 (`game.messages`) |
| FFF0F2 | invulnerability frames after damage (set to 0x28) | CONFIRMED | `1B03F2`; timeline shows 0x28 decaying |
| FFF0E6 | dying (set to 0x0A when health hits zero) | CONFIRMED | `1B03F2`, `1A8F0C` fall check |
| FFF0E9 | death sequence countdown | STRONG | `1A8E3E` decrements it and plays the death sound |
| FFF0E7 | frozen / level complete | TENTATIVE | every control routine returns when set; "blocked" in the contact recipes |
| FFF173 | camera locked / cutscene | STRONG | `1AA8FA` skips scrolling; contact reset reads it |
| FF7E60, FF7E77 | player animation script pointer and restart flag | CONFIRMED | player record +20; written by 1A9B38, 1AD7B4, 1A9502, 1A9716, 1B1FAE/1B1FFE (state changes) |
| FF7E54 | player current sprite frame pointer (+14) | CONFIRMED | written by the interpreter only |
| FF7E26 | level type code (0..5, 8 = special) | TENTATIVE | control tests `== 8`; the music byte FFF575 follows it exactly |
| FFEFEA | extra-life progress: tally units (10 points each) since the last extra life; reset at 5,000 / 7,500 / 10,000 points by difficulty | CONFIRMED | `1B00CA` increments it per tally unit and calls the extra-life routine at the threshold (an earlier reading as a stage index was wrong: its high byte merely steps with the score) |
| FF7DFE / FF7E00 | camera window target for the player (0x70, 0x150) | CONFIRMED | `1AA8FA` compares FF7DFA/FC against them |
| FF7DB8 / FF7DBC | level width / height | STRONG | camera right limit = FF7DB8 - 0x161; fall check uses FF7DBC |
| FF7DB4, FF9884, FF98C4, FFAE86 | level collision map base and row pointers | STRONG | ground collision indexes FF98C4 by tile row; readers are only the collision routines |
| FF7DA4 | pointer to the current level's scroll routine | CONFIRMED | `1AAA80: move.l FF7DA4,-(a7); rts` |
| FF7E28 | frame counter | STRONG | written by the main loop each frame; interpreter tests bit 0 |
| FF7E1E | VBlank happened | CONFIRMED | idle loop |

Player control flow (CONFIRMED from code): `1A9D98` reads FFF07C/7D, sets
facing, adds FFF0B0 to FF7DFA (screen X), guarded by FFF0E6/E7/E9, FFF0DB,
FFF0DC; `1A9B90` integrates FF7E58/5A into FF7DFA/FC; `1A986E` starts a
jump (FF7DFC += 2, FF7E00 = 0x150, FFF0D0 = 1) on FFF07E/7F; `1A99F0`
starts an attack (FFF0D7 = 1, animation via 1A9B38); `1AA8FA` scrolls the
camera toward the window using the speed tables at ROM 2A52/2BA4 and
raises FFF0B9..BC, which `1AAA2A` turns into object spawn strips.

## 3. Health, lives, score, apples, gems (the HUD)

All five HUD numbers are stored as ASCII digits, and all four counters
matched the checkpoint screenshots at every one of 13 checkpoints with a
single consistent address each.  **CONFIRMED.**

| field | name | evidence |
|---|---|---|
| FFEFFA | health (0..8) | `1B03F2` decrements it on damage when FFF0F2 is clear and sets FFF0E6 = 0x0A (dying) at zero; `1B0434` heals by one up to FFEFFB; timeline: 8 at every level start, drops by one per hit, reaches 0 exactly before each life loss; read every frame by the HUD bar 1B02EC |
| FFEFFB | maximum health (8) | never changes; the heal cap |
| FFEFFA += 3 - FF7E21 | health pickup (type44 callback, 1AEF12) | FF7E21 = 1 throughout (difficulty); timeline shows +2 jumps |
| FFEFE0..E1 | apples, two ASCII digits | matches "10", "66", "77", "94", "99", "22", "31", "19", "16", "20", "9"; `1B0360` (recovered as the two-digit counter) spends one; read every frame by the sprite builder for the HUD digits |
| FFEFE2..E3 | gems (rubies), two ASCII digits | matches 5, 3, 2, 10, 13, 24; `1B03BE` spends one; the shop (type7E) spends five |
| FF7E3C | lives, one ASCII digit | matches 3, 6, 8, 4; `1AEF70` adds one capped at '9' (extra life, also the type46 pickup); drops by one at each death (frames 30720, 38752, 57088, 75136, 81504) |
| FF7E2A..2E | score, five ASCII digits | `1B00CA` moves points from FFF14E into the digits with carries at the first score change (frame 2752) |
| FFF14E | pending score in tally units of 10 points | `1B0138..1B0192` add 1, 5, 10, 15, 20, 25, 50, 75, 100 or 1,000 units; `1AE95A` adds the object's own value `8(a1)`; `1B00CA` moves one unit per even frame into the digits (`game.hud.score_tally`) |
| FFF0F2 | invulnerability timer | see above |

Shop.  Object kind 7E (the WISH merchant, sprite confirmed) requires at
least 5 gems and fewer than 9 lives, spends five gems, plays sound 0x48
and adds a life; the timeline shows gems 5 -> 0 with lives 3 -> 4 at frame
9,312 and 7 -> 2 with 7 -> 8 at 22,016.  **CONFIRMED.**

## 4. Objects

Record layout (66 bytes), from the interpreter, the initializer 1AE30A
and the callbacks:

| offset | meaning | confidence |
|---|---|---|
| +00 | kind: index into the collision callback table at ROM 1CBE | CONFIRMED |
| +01 | hit points | CONFIRMED (sword hit decrements it; retirement when zero; templates carry 1, 2, 3, 9, 10, 20) |
| +02 / +04 | world X / Y (feet) | CONFIRMED |
| +06..+09 | flags; +09 facing | STRONG (opcodes EB, F7 flip +09) |
| +0A | secondary (motion) script pointer | STRONG (opcode EC arg, 1ADE36 runs it with FF7DA2 set) |
| +0E, +12 | secondary channel loop pointer / counter | STRONG |
| +14 | current sprite frame descriptor (ROM pointer) | CONFIRMED |
| +18 / +1A | X / Y velocity | STRONG (opcode F9 homes them toward the player) |
| +1C | signed displacement | STRONG |
| +1E | template word (graphics / palette selector?) | TENTATIVE |
| +20 | animation script pointer | CONFIRMED |
| +24 / +28 | loop start / loop counter | CONFIRMED (opcodes EE, EF) |
| +29, +2A, +2E | attached buffer length, pointer, and a second pointer | STRONG (1AE372 release) |
| +32, +34 | publication index / flag | STRONG |
| +35 | flip flag | STRONG (opcode EB) |
| +36, +37 | frame delay (secondary / primary) | CONFIRMED |
| +38 | saved script pointer | STRONG (opcode FC) |
| +3C | flags; bit 5 = contact pending | STRONG |

Kind 0x84 is the universal "dying / one-shot effect" retype: every
recovered retirement arm writes `84` plus a death script; 85 objects
templates exist in ROM (`lea 1B7xxx,a6` sites, decoded in
`artifacts/cartography/templates.txt`), and kind 84 objects account for a
third of all pool samples.  **CONFIRMED.**

## 5. The script engine (the "command-stream" question)

The 8,000-instruction ticks are not an interpreter.  They are the kind-21
callback waiting for VBlank inside the contact scan (`1B24EC: tst.b
FF7E1E / beq`, 7,657 iterations) around four VDP tile uploads; that path
needs a "wait for VBlank" service, nothing more.  **CONFIRMED** from the
trace of every such tick.

The real behavior engine is `1AC784`, called once per frame from the main
loop: for each of the 32 records with a nonzero kind it reads the
animation script at +20.  A word below 0xE000 is a sprite frame: the word
is a ROM address whose long is the frame descriptor stored at +14 (a
change calls `1AC6D0`, which marks the tile upload); +37 then holds the
frame for its delay.  A byte 0xEA..0xFE is an opcode dispatched through
the table at ROM 4954:

| op | meaning | handler |
|---|---|---|
| EA | jump (long) | 1AC850 |
| EB | flip facing / flip flag | 1AC856 |
| EC | end script (primary or secondary channel) | 1AC86C |
| ED | set memory: byte/word/long, absolute FF0000+word or record-relative | 1AC89A |
| EE | wait N frames (bit 7) or set loop counter | 1AC8E0 |
| EF | loop | 1AC926 |
| F0 | random branch (RNG 1B3032, threshold byte, long target) | 1AC950 |
| F1 | move X by word in the facing direction | 1AC968 |
| F2 | add to memory | 1AC98E |
| F3 | play sound (byte id; 1E58B8 + 1E589A) | 1AC9D2 |
| F4 | branch if memory byte/word/long compares (mode bits) | 1ACA14 |
| F5 | spawn / child object action, sub-modes 0..6 (templates) | 1AD00E |
| F6 | destroy self (1ABE6E release) | 1AD0FC |
| F7 | face the player | 1AD138 |
| F8 | player: select script by state (FFF0D7 -> 121964 ...) | 1AD150 |
| F9 | home velocity toward the player | 1AD2DC |
| FA | set memory variant | 1AD314 |
| FB | call native code (pushes a long and returns into it) | 1AD372 |
| FC | jump to the saved pointer at +38 | 1AD378 |
| FD | branch if the player is within N horizontally | 1AD392 |
| FE | branch if the player is within N vertically | 1AD3C2 |

`1ADE36` runs the same opcode set on each object's secondary channel (+0A)
with FF7DA2 set, which is where objects move (it writes +02/+04 more than
anything else).  **STRONG.**  The player's own scripts use the engine too:
the idle script 122006 sets FFF0B0 (walk speed) and tests FFF0CC; the
attack script 121964 branches on FFF0D0/FFF0DC/FFF0D6 and the sword
hit-box flag FFF0D8 is written by the attack animation itself.  This is
why every "script pointer" in the contact recipes is an animation: the
retirement arms simply hand the object a death animation.

The engine therefore is: 32 records x (animation channel + motion
channel) x 21 opcodes, calling five services (sound F3, spawn F5, release
F6, RNG in F0, player position in F7/F9/FD/FE).  It is small (about 50
instructions of dispatcher plus the handlers above) and is the single
highest-value recovery target: recovering the dispatcher and handlers
in Python turns every object's behavior into readable script data.

## 6. Level flow

Stage index FFEFEA and the recording: 384 game start (attract play in
Agrabah Market), 6,426 title, 8,536 Agrabah Market (real play), 10,931
"Abu in Agrabah" bonus, 12,821 "The Desert", 24,935 Genie bonus wheel,
25,600 "Agrabah Rooftops", 49,504 bonus, 50,201 "Sultan's Dungeon", 68,338
bonus, 69,586 to 82,161 the cave stage (checkpoint screenshots).  Loads
are RAM-change bursts (3,000 to 5,000 bytes in one frame into FF9Dxx to
FFADxx and FF68xx: collision map and tile buffers) at 975, 11,063,
12,955-12,973, 25,752-25,777, 50,416-50,446, 69,373-69,391, each preceded
by the `1B3736` / `1B38B8` decompression loops and followed by the
pre-roll.  **STRONG.**  Objects are streamed in by the four spawn-strip
walkers (`1AE3FC` left, `1AE406` right, row low/high) driven by the camera
flags FFF0B9..BC, reading the level object table with the "already
spawned" bitmap at FFAE87 -- the walkers the grinder recovered.

## 7. Object identities (sprite evidence)

Sprites were isolated per object by deactivating that object alone in a
scratch copy of the machine and diffing two rendered frames
(`scripts/cartography/object_masks.py`; 927 masks, one per script family
per kind on the sheet `artifacts/cartography/mask_sheet_*.png`).  The
identities below combine the sprite with the callback's recovered
behavior; the ones marked "ask" are extracted but not yet named.

| kind | callback / template | identity | confidence |
|---|---|---|---|
| 40 | 1AF8F6, level table | apple (pickup; sprite is the red apple) | CONFIRMED |
| 3A | collection type3A (1AF228) | red gem / ruby (pickup; gems counter) | CONFIRMED |
| 44 | type44 (1AEF12), template 1B7ABC | blue heart: health pickup (+3 - difficulty) | CONFIRMED |
| 46 | type46 (1AEF5C), template 1B79CC | Aladdin-face token: extra life (lives capped at 9) | CONFIRMED |
| 41 | activation (1AFD84) | Abu-face token (bonus stage entry) | STRONG |
| 34 | 1AF6DC | Genie-face token (bonus wheel entry) | STRONG |
| 7E | 1AFE1C shop | WISH merchant: 5 gems buys a life | CONFIRMED |
| 23, 2A | type23 (1AEECA), sibling wrapper | clay pot (breakable, spawns contents) | CONFIRMED (sprite + double-spawn code) |
| 43 | type43 (1AE64C) | large blue vase (hidden item container) | STRONG |
| 07 | sibling wrapper, hp 2, template 1B8070 | green cobra (snake-charmer snake) | CONFIRMED |
| 05 | sibling wrapper, templates 1B7A80/94/A8 | bat (dungeon / cave) | STRONG |
| 21 | type1f family (1AE796) | fat palace guard with scimitar | STRONG |
| 1E, 1F | type1f family, hp 1 | thin palace guards (sword) | STRONG |
| 10 | sibling wrapper, hp 9, template 1B7B84 | large sword guard (mini-boss of the market) | STRONG |
| 13 | sibling wrapper, hp 10, template 1B7F1C | knife-wielding guard | STRONG |
| 0A | sibling wrapper, hp 1 | tall skinny swordsman | TENTATIVE |
| 0C, 0D | type0c (1AE9A8), hp 1 | pot-throwing woman (arms raised) | TENTATIVE |
| 87 | 1ABF8E | turbaned man in blue (three poses) | ask |
| 84 | 1AC1B4 | dying object / thrown apple in flight / hit sparkle / falling guard | CONFIRMED |
| 8C | 1AC60E | fire column (fire-breather flame) | STRONG |
| 8D | -- | magic sparkle effect | STRONG |
| 8A | -- | the Genie (bonus host) | STRONG |
| 2D | -- | thrown dagger (projectile) | STRONG |
| 2F | type2F (1AEDA8) | wooden barrel / bucket | TENTATIVE |
| 55 | type55 (1AF590) | desert stone column segment | TENTATIVE |
| 58 | type58 (1AF5F0) | cave stone ledge (moving platform?) | TENTATIVE |
| 62 | type63 (1AF81C) | blue crystal / rock (cave) | ask |
| 6A, 6B, 6C | motion family (1AF978) | wooden beams / rooftop planks (moving platforms) | TENTATIVE |
| 6E, 70, 71, 73, 72 | 1AFB36 family | ropes / poles Aladdin climbs (72 shows him hanging) | STRONG |
| 74, 75, 76, 77, 89 | type74 (1AFA84), secondary motion | flat dark winged shapes in the cave (carpet? bats?) | ask |
| 78 | type78 (1AEBDC) | iron ball on a chain (dungeon) | STRONG |
| 7A, 7C | type78 / sibling wrapper | dark dungeon guard with spear; blue dungeon creature | ask |
| 15, 17, 1A, 1D, 20, 0F, 06, 03, 01, 2B, 2C, 2E, 31, 36, 3E, 3F, 47, 49, 4C, 65, 79, 80, 82 | various | extracted, identity pending (see the sheets) | ask |

## 8. Recovered structure (code and data, verified)

`src/aladdin_sega/game/` is the game as semantic modules; every module
names the RAM fields it owns and the ROM routine it was recovered from.

- `objects/record.py`, `scripts.py`, `assets.py`: the 66-byte record as
  named fields (`RecordView`), templates (the 19 bytes 1AE30A copies,
  85 sites), the 21-opcode script language as data (`decode_op`, with
  opcode FC's call / return forms and the compare-branch's "anything
  else is below" default), sprite frames, pieces and tile records.
- `objects/script_engine.py`: the animation and motion channels (1AC784,
  1ADE36), all opcodes including spawn (F5: six pools, rider links),
  the VRAM allocator with its exact scan budget (1AD3E8), the odd-frame
  prologue (the sword and stance flags, the upload queue count), the
  tile-upload queue the flush step drains (1AC6D0), and a registry of
  the native routines scripts call through FB (flag bits, companion
  spawns, random sounds and velocities, the vertical scroll streams,
  the homing helpers, the kind-89 transforms).
- `objects/ground.py`: objects against the level (1ADB5C: landing,
  bouncing, the splat effect 1ABE8A, leaving the map).
- `objects/contact_scan.py`, `objects/contacts.py`: the player-versus-
  object and projectile-versus-object scans (hit boxes from the frame
  descriptors, 0x80-biased and mirrored by facing), and the callbacks by
  ROM address: 50 of the 74 player callbacks (sword hits and deaths,
  collectibles, platforms, ropes, the pushable block, the spring, the
  shop, the sword clash with its one-frame white flash) and 11 of the 31
  projectile callbacks.
- `spawn.py`, `level.py`, `scroll.py`, `camera.py`: the spawn-caller
  table 0x4154 decoded into spawn sites (all 127 callers decode; pools,
  guards, adjustments, palette loads, sounds), the level map in RAM (row
  table FF9884, cell tiles FF7DBE, attributes FFAE84, spawn flags
  FFAE87) with the strip drawing into plane A, the nine per-level
  scroll routines, and the camera's eased follow with the strip debts.
- `player.py`, `control.py`, `tiles.py`: the wall sensors, ground
  collision, landing and gravity; hurt and health loss (1AE4F8 /
  1B03F2); walking, the velocity integrator, jumping, throwing, the
  sword (1A9D98, 1A9B90, 1A9716, 1A9304, 1A9502); the special tiles
  under the player (33 handlers: conveyors, springs, climbables, the
  layer switch, quicksand, kill and damage tiles, the progress flags).
- `hud.py`, `flow.py`, `sprites.py`, `messages.py`, `video.py`,
  `pad.py`, `pause.py`: the counters (score tally, apples, gems, health,
  the token digits), the fall check, the transition countdown, the 13
  per-level tick routines, the sprite attribute table builder (HUD
  pieces and every object's pieces, culled and flipped), the in-game
  message language (glyph objects, tile boxes, palette lines), the three
  VDP upload steps and palette loads, the pad and attract stream, the
  pause decision.

## 9. The native runtime

`src/aladdin_sega/native/`: `GameState` (the original's 64 KB work RAM as
the backing store, the ROM, the VBlank-count frame clock, an event
stream, a `Vdp` model with VRAM / CRAM / VSRAM and 68k-to-VDP DMA) and
`frame.STEPS`, the original main loop 1A8C16..1A8CEE as 36 ordered steps
(33 distinct entries; each step's exit is the next call's entry, so the
main loop itself brackets every step).  Every step is native; nothing in
the native path executes original code.  Effects the runtime cannot own
yet raise `NativeGap` with the ROM address: the pause loop, the
Start-release wait, the level transitions (a life lost, a level change,
the bonus stages), message commands that wait for frames, and the
callbacks or native routines not yet in a registry.

Verification rises with the abstraction:

- `scripts/native_replay.py --verify FRAME COUNT` proves each step in
  place: the semantic step runs over a copy of the oracle's RAM at the
  step's entry and is compared byte for byte at its exit; steps that
  write the VDP are also compared word for word against the port writes
  the oracle makes (`native/oracle.py` single-steps the original and
  evaluates every `move` to C00000 / C00004).
- `scripts/verify_step.py STEP FRAME COUNT ...` does the same for one
  step over long windows and tallies the events it produced.
- `scripts/native_diff.py FRAME COUNT` is the whole-frame boundary: the
  native runtime and the oracle run side by side from the same frame
  boundary with the recorded pads applied per VBlank, and the whole work
  RAM is compared after every frame; a divergence is attributed to the
  step that produced it.  From the seven recorded states the native
  runtime matches the oracle on every byte of every frame until a
  declared gap: 3,400 to 5,700 frames from each of levels 0, 1, 3, 4 and
  5, stopping at the first level change (frame 10018 from level 1,
  48930 from level 0), a life lost (75278 in level 5), or one of the
  callbacks still to recover.

Three defects the whole-frame comparison found that the per-step
comparison could not: the odd-frame prologue that clears the sword
flags, opcode FC's call form (the per-step check re-seeds the saved
script pointer from the oracle), and the compare-branch default mode.

## 10. What to recover next

1. The transitions, as sequences of nested frames over the same steps:
   the life-lost respawn (1A902E / 1A8F82: fade, re-initialisation,
   screen redraw through the strip and object passes, fade in), the
   level change (1A8E5C: the end-of-level tally 1B0D70, the level
   sequence stream FFF572, the level loader 1AA484 with its two
   decompressors 1B35D0 / 1B3818, the level init routines and the
   intro screens), and the bonus stages.  The fade (1B278A / 1B29B0) is
   47 nested VBlank frames of CRAM interpolation; the VDP model already
   keeps CRAM.
2. The 24 player callbacks and 20 projectile callbacks not yet met by
   the recording (kind 3E at 1AF2B0 is the next one it meets).
3. The level event streams of levels 2, 6 and 8 (1B634E over the table
   at 20C0) and the carpet ride (1B6066).
4. Then the outer game: boot, title, attract, the options and the
   game-over screens, so the whole recording runs from power-on.

## 11. Tools

`scripts/cartography/`: `ram_activity.py` (per-frame RAM change activity,
instruction counts and snapshots every 32 frames), `frame_sampler.py`
(instruction-level trace of chosen frames with routine attribution, call
edges, memory operands and the ordered main-loop sequence),
`aggregate_dense.py` (routine totals, readers/writers per address and
per object field, frame modes), `analyze_samples.py`, `object_boxes.py`,
`object_masks.py` (sprite isolation by deactivation diff), `hud_search.py`
(find RAM fields matching screenshot values), and the fallback audit
scripts `fallback_log.py`, `fallback_states.py`, `trace_fb.py`,
`classify_fb.py`.  All need `ALADDIN_NATIVE_LIBRARY`, numpy and Pillow
(installed in `.venv` only).
