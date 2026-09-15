# EMPTY_FRONTIER: spawn dispatcher children census (`--parent 1AE46C`)

## Where

The spawn dispatcher's JSR at `1AE46C` (parent gate), whose children were
census'd this stint via `recovery_census.py ... --parent 1AE46C` into
`artifacts/evidence/spawn` (169 path rows over 40 (entry, kind) classes,
retained from the `44223150b7d6` history, 82,161 frames).

## Code

`EMPTY_FRONTIER`. `frontier_ledger.py` on the final cold comparison of
this stint (`artifacts/spawn-final10`, PASS, 82,161 frames, 0 restores,
91,763 candidate hits, 1,514 fallbacks) lists exactly four remaining
`UNRECOVERED_TARGET` rows whose target is a spawn dispatcher child, and
section 3 of the protocol admits none of them:

```
   211  UNRECOVERED_TARGET  1B67C2    spawn dispatcher target 1B67C2 is not recovered
    46  UNRECOVERED_TARGET  1B65F4    spawn dispatcher target 1B65F4 is not recovered
    12  UNRECOVERED_TARGET  1B6D1E    spawn dispatcher target 1B6D1E is not recovered
     5  UNRECOVERED_TARGET  1B6C5A    spawn dispatcher target 1B6C5A is not recovered
```

## Observed / why each remaining row is inadmissible

- **`1B67C2`** (211 fallbacks) -- already escalated this stint. See
  `docs/blockers/2026-09-14-1B67C2.md`, code `DATA_STRUCTURE`: 23
  retained path classes, every one calling a previously-unnamed bounded
  PRNG subroutine (`1B3032`, closed form `new_seed = 13*seed + 7 mod
  2^32`) two or three times to gate up to two independent reverse-pool
  spawns, each with its own RNG-jittered position and a two-bit
  conditional script write. One branch (the bit-1-clear continuation
  inside the shared `1B6794` sub-body) was never reached by any retained
  fixture and remains uncharacterized.

- **`1B65F4`** (46 fallbacks) -- already escalated this stint. See
  `docs/blockers/2026-09-14-1B65F4.md`, code `NEW_MACHINE_MECHANISM`: its
  own allocator call target `1B52A0` is a fifth pool entry
  `_SPAWN_REGION_ARMS` in `boundary.py` does not yet name (only the four
  entries `1B524E`/`1B5256`/`1B525E`/`1B5266` are proven).

- **`1B6D1E`** (12 fallbacks, never escalated -- no recipe fit was
  attempted). `factcheck.py facts artifacts/evidence/spawn/1B6D1E-kind02-p0.state`
  (SHA-256 `65a4af205aeb9986c4cdc7d47724e41e0b46b9d233d8d72fe2bc2e1e3c9edf4a`)
  shows: `TST.B FFF179` guard, an upper-pool spawn (`1B5266`), a
  `1B2650` VDP tile upload, then **three** separate native sound-seam
  calls in sequence (`1E58F4`, `1E58B8`, `1E589A` -- 216 instructions,
  5 native entries total). Section 3 step 2's skip condition ("more than
  one native call in its native shape with writes between them")
  excludes this row outright; it was never chosen as this stint's next
  bite.

- **`1B6C5A`** (5 fallbacks, never escalated -- no recipe fit was
  attempted). `factcheck.py facts artifacts/evidence/spawn/1B6C5A-kind02-p0.state`
  (SHA-256 `3dd1bd33526113eb3c353bb55117d218d8965a9732a410e454ae7d4b9c6708d5`)
  shows a `1B5256` reverse-pool spawn followed by a `MOVEM.L`/`JSR
  1E58F4` sound-seam call (169 instructions). This is a single-native-call
  shape (matching the "branch with one sound call" recipe class used
  elsewhere for the contact family -- e.g. `begin_contact_family_type46_sound_seam`),
  not a hard blocker in principle, but implementing a spawn-family
  SoundSeam caller needs the same stack-basis/ABI care that caught a real
  bug in `1AF81C`'s own sound seam earlier this stint, and its
  fallback count (5) did not justify that investment this stint relative
  to the remaining higher-value rows, all of which are now recovered.
  This row is a legitimate candidate for a future stint with the sound
  seam recipe already proven for the contact family; it is not
  architecturally blocked, only deprioritized.

No other spawn dispatcher child target appears anywhere in the
`UNRECOVERED_TARGET` listing of `artifacts/spawn-final10`'s frontier
report. Every other census row (34 (entry, kind) classes) was recovered
this stint; see `docs/recovery-ledger.md` for each one's own line and
`docs/STATUS.md`'s "1B75D6 recovered; spawn dispatcher family frontier
EMPTY" section for the full roster.

## Fixtures used

All evidence referenced above lives in `artifacts/evidence/spawn/` (not
committed; regenerate via `recovery_census.py ... --parent 1AE46C`
against the `44223150b7d6` history if absent). The cold-run receipt
referenced is `artifacts/spawn-final10/comparison.json` (also not
committed).

## What was tried

- Ran `frontier_ledger.py` on `artifacts/spawn-final10` (the final PASS
  cold comparison of this stint) and filtered its `UNRECOVERED_TARGET`
  rows to `reason` strings containing "spawn dispatcher target".
- Confirmed `1B67C2` and `1B65F4` are the two already-escalated rows.
- Traced `1B6D1E` and `1B6C5A` far enough (`facts`, no `--path`, single
  fixture each) to classify their shape against section 3's admission
  filter and the existing recipe set; neither was carried further.

## Next question

For `1B6C5A` specifically: does adapting one of the proven contact-family
sound-seam recipes (`begin_contact_family_type46_sound_seam` or
`begin_contact_family_type43_sound_seam`, both in `boundary.py`) to a
spawn-family caller (reverse-pool creation, then a single `1E58F4`
sound-seam call with the callback's own stack-basis) recover `1B6C5A`
cleanly, the way the closure/offset/guard shapes were reused across
`1B6696`/`1B6F4A`/`1B6F34`/etc. this stint -- or does the spawn
dispatcher's own MOVEM save/restore frame (distinct from the contact
scan's frame shape) require a genuinely new stack-basis derivation?
