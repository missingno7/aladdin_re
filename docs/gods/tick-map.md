# The Gods game tick, mapped

Supervisor cartography, 17 September 2026: the phases a logical game tick
(`001EC2`, every other frame) runs, in order, with the mean instructions
per tick each phase and its callees executed over frames 15,000–15,120 of
`fb408bc75597…` (level-1 gameplay, `scripts/hot_calls.py`; the window is
a property of that stretch, not of the game), what is recovered inside
each, and the shape read from the disassembly.  Names marked *(reading)*
come from the code, not from evidence; a census names a region for real.
A tick in that window runs ~17,900 instructions of which ~6,600 are the
VBlank wait (`00052E`): the active tick is ~11,300 instructions.

| order | entry | per tick | recovered inside | shape *(reading)* |
|---|---|---|---|---|
| 1 | `001098` | 64 | — | sprite list flush to the VDP (device) |
| 2 | `002852` | 5 | — | stub |
| 3 | `004348` | 3 | — | stub; `bne 0043E2` on its result |
| 4 | `004150` | 38 | **yes** (`004150`) | the pad latch → intents |
| 5 | `002806` | 17 | **yes** (`002806`) | camera follow |
| 6 | `000DC0` | 49 | — | list walk (21–433) |
| 7 | `00100A` | 35 | — | list walk (21–433) |
| 8 | `00F938` | 170 | — | a 40-entry list at `FF0C70` (`moveq #$27,d7`): per-entry `movem.w (a0),d0-d2`, negative = free — the effects / particles list *(reading)* |
| 9 | `00F44A` | 3 | — | stub |
| 10 | `002E8E` | 42 (10–1,917) | `001164` (via `002E4E`) | the sprite emitters' pass |
| 11 | `0030CC` | **1,410** | — | clears `F260/F388/F250`, counts `F252` (mod 32) and `F206` (mod 5), then a long per-tick loop: the world / tile-animation update *(reading)*; the largest phase |
| 12 | `010DA6` | 3 | — | stub |
| 13 | `003036` | 3 | — | stub |
| 14 | `013342` | 124 | — | three lists (`FFEF8C`, `FFF01E`, `FFF0B0`) walked by `013362` with `F1FC` = 0/1/2: the collectible lists (the address-error precondition retires `FFF01E`) |
| 15 | `0134FA` | 3 | — | stub |
| 16 | `01116C` | 3 | — | stub |
| 17 | `0100FE` | 59 | — | fixed-length |
| 18 | `010454` / `010670` / `010790` | 3 each | — | stubs (inactive systems in this level) |
| 19 | `002F68` | 3 | — | stub |
| 20 | `0049DA` | 19 | **yes** | trigger/pad composition |
| 21 | `0025AE` | — | — | (not in the window) |
| 22 | `005700` | **620** | `0063FA` grid cell (from six state handlers), `00470C` | **the player state machine**: `jmp table[005618][F192].handler`, 29 states (index `F192`, `F190` in d7; a state is inactive on `EECD`/`F210`) |
| 23 | `00A476` | 157 | — | camera-relative window (`F18C/F18E` − `F3EE/F3F0`, a 6-entry table at `00A4EE`) *(reading)* |
| 24 | `00A578` | 261 | `00126A`, the pickup chain `00B944`→`00BA8E`→…, `00A772` | **the creature update**: walks the 9-slot list at `FF1496` (`FF2602` per slot); per creature `00A772` → `009D6C` (movement/attack, the `009D16` blocker) then `jsr table[00A538][kind].handler`, 8 kinds (`00AA76`, `00AB50`, `00AE6C`, `00AED4`, `00ACA0`, `00AD88`, `00AA80`, `00AB5A`) |
| 25 | `0141E6`, `011D88`, `0041F0`, `0122EC`, `012058` | 3 each | — | stubs |
| 26 | `00A578`'s tail / `00200A`… | — | `002D5E`, `009558` | level-end and menu checks |

Event kinds: `0077BE`–`007876` (ten unconditional flag-word checks, real
code no recording has ever been seen with any of them set, then the table
dispatch itself) raise an event index `d0` (1–11) through the table at
`004494` — `0045D0`, `00457A`, `00462C` (the trigger evaluator; its
non-firing arm is composed into the tail's own raise, `player-tail`, 18
September, reusing `evaluator_plan`'s own `_evaluator_resolve`; its firing
arm stays open), `0094D0`, `009514`, `0044C0` (the trail check, `game/
trail.py`; its 'found' arm composed the same way the same day, reusing
`_trail_check_resolve`; its 'exhausted' arm, real code through `007B4C`,
stays open), `00FB28`/`2C`/`30`/`34`, `00D2BA` — raised from the tile
trigger scan `00773A`/`0077A8` (a tile at the camera-relative cell of
`00885E` with a byte > 2) and from the player state machine (`005700` →
`0075DC` → `00773A`), which continues the scan after each admitted raise
(up to six per activation).  The trigger evaluator's call stack on every
witnessed firing: `001FD0 jsr 005700` → `0075E0` → `007768` → `007876 jsr
(a1)` → `00462C`.

## What this says about the frontier

The bounded-leaf grind has recovered most of what the smaller phases call
(34 regions, ~320 instructions per frame replaced of ~5,650 active).  The
tick's mass is in three places, all dispatcher families with a persistent
record per entry: the player state machine (29 state handlers over the
player record, `005700`), the creature update (8 kind handlers over the
creature slots, `00A772`/`00A538`, with `009D6C` in front of each), and
the world update (`0030CC`).  These are the next subsystems, in that
order: each is recipe 6a over a table the ROM names, the handlers are the
leaves, and the state index / kind byte is the census classifier.  The
timing context stays the machine's; nothing here needs it.
