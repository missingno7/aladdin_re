# Recovered object cleanup and initialization

The current [0.8 semantic migration](semantic-migration.md) shares game bodies in
`recovered.py` and retains exact exposed entry/seam effects in `boundary.py`.
The [0.7 synchronous seam](synchronous-seam.md) is unchanged. The original-machine
contracts below still apply; 0.6 remains frozen capability evidence.

The 0.6.0 [connected carrier experiment](carrier-convergence.md) expands this
cluster through the counter and original sound calls, with a snapshot-safe
Python continuation. That report contains the current region map, contract,
qualification and scaffolding verdict; this document retains the underlying
per-region effect domains.

The first semantic candidate is the shared clear routine at `0x1AE372` through
`0x1AE39E` in the USA ROM with SHA-256
`a3779fc77994780e80d05bb557f800110d0398d34b951baa8c0a14910014ded3`.
It is a 46-byte, 15-PC region:

```text
2F 0E 3F 00 2C 69 00 2A BD FC 00 00 00 00 67 18
42 A9 00 2A 42 A9 00 2E 42 40 10 29 00 29 42 29
00 29 42 1E 51 C8 FF FC 30 1F 2C 5F 4E 75
```

Its loop entry is `0x1AE394`; its restore/return epilogue starts at
`0x1AE39A`.  The bounded domain requires all dynamic operands to be canonical,
non-wrapping work RAM spans and requires the record, buffer and guest stack to
be disjoint.  Those are admission guards, not claims that the original never
permits aliases. Word/long operands and the guest stack must be even-aligned;
byte buffers may start on odd addresses. RTS masks the popped return to 24 bits.

At entry it saves `A6` as a long and `D0.W` as a word on the guest stack.  It
loads the byte count from `A1+0x29` and the buffer pointer from `A1+0x2A`.
When the pointer is zero it changes no record/buffer bytes.  Otherwise it
zeros the longs at `A1+0x2A` and `A1+0x2E`, the byte at `A1+0x29`, and exactly
`count + 1` bytes from the loaded buffer.  It restores `D0`, `A6`, and the
stack pointer, then performs a normal RTS.  The temporary guest-stack bytes
remain written after the pop and are part of strict machine equality.

The null path retires 8 M68000 instructions and charges 96 cycles.  For a
non-null buffer of `n = count + 1` bytes, it retires `13 + 2n` instructions and
charges `178 + 22n` cycles.  On both paths the final CCR has the MOVE.W logic
flags for the restored low word of `D0`: N/Z reflect that word, V/C are clear,
and X is preserved. The routine leaves every general register unchanged except
A7, which advances four bytes when RTS consumes the guest return address.

The adjacent selected caller is `0x1AD0FC` through `0x1AD136`.  Its recorded
direct route increments `A2`, consumes one script byte into `D0.B`, takes the
zero branch, tests bit 2 at `A1+0x3C`, clears `*(A1)`, and calls `0x1AE372`
from `0x1AD114`.  After the leaf returns it optionally clears the linked
record at `*(A1+0x3E)`, then overwrites its **outer** return slot with the long
at `0xFF7D9E` before RTS.  That overwritten return is the caller's actual
continuation; a host-language return is not equivalent.

The composed candidate owns all three caller branches within its guarded RAM
domain. On the zero/bit-clear route it calls the Python leaf calculation
directly inside its staged atomic plan. With a null
linked record, its total is `80 + leaf_cycles + 70`; with a non-null linked
record, `80 + leaf_cycles + 152`.  Its instruction total is respectively
`7 + leaf_instructions + 4` or `7 + leaf_instructions + 9`.
Its execution receipt separately reports admitted leaf, pair and caller hits,
direct Python calls within each admitted composition, replaced M68000
instructions, and charged M68000 cycles.  A refused plan is counted as a
fallback and the original resumes at its stopped opcode.

The exact entry adapters live in `src/aladdin_sega/boundary.py` as
`clear_auxiliary_buffer()`, `clear_object_pair()`, `detach_object()`,
`initialize_object()` and `finish_object()`.
`replace_object()` adds the shared replacement tail and its incrementing entry.
All adapters use shared semantic bodies in `recovered.py`; internal buffer/pair
calls no longer construct nested helper plans or intermediate register contracts.
Unsupported operands, aliases and scheduler refusal still fall back from the
unchanged entry. The previous `LegacyExit` marker is removed because its only
dependency is now recovered. No suspended Python stack or second machine is
introduced; each admitted activation completes before returning to dispatch.

## Object-pair clear and completed detach branches (0.3.0)

`0x1ABE6E` through `0x1ABE88` is this 28-byte region in the same verified ROM:

```text
42 11 61 00 25 00 4A A9 00 3E 67 0E 2F 09
22 69 00 3E 42 11 61 00 24 EE 22 5F 4E 75
```

It clears `*(A1)` and directly calls the buffer clear. If the long at `A1+62`
is nonzero, it saves A1, clears the linked object's first byte and buffer,
then restores A1. It preserves the link fields and flags in both records.
The primary record, linked record, buffers and entire nested stack must be
disjoint. Both BSR return addresses and the saved A1/A6/D0 bytes remain in
RAM after their frames are popped and are included in the staged writes.

For a null link the pair costs `72 + first_leaf_cycles` and
`5 + first_leaf_instructions`; the final flags come from `TST.L` of zero.
For a linked object it costs `140 + first_leaf_cycles + second_leaf_cycles`
and `10 + first_leaf_instructions + second_leaf_instructions`; final flags
come from the second leaf's restored D0.W. A1 and D0 are preserved, A7
advances four bytes, and RTS uses the actual guest return slot.

Detach calls this pair routine when its script byte is nonzero or bit 2 at
`A1+60` is set. A nonzero byte costs `46 + pair_cycles + 54` and
`4 + pair_instructions + 3`; the zero/set-bit route costs
`70 + pair_cycles + 54` and `6 + pair_instructions + 3`. Both still overwrite
the outer return with `0xFF7D9E`. The final MOVE.L flags see the full 32-bit
override; RTS masks only the resulting PC. Composition also guards the script
byte, return override and outer return against all nested writes.

The `pair` replay candidate gates just the pair entry. `composed` gates all
three entries, so internal calls become direct Python calculations. The 48
native differential cases in `tests/test_recovery.py` execute the verbatim
ROM bodies with synthetic initial state, covering all detach branches,
null/non-null links and buffers, maximum 256-byte loops, odd byte buffers,
D0 width, X/N/Z flags, and high-byte return masking. They compare full native
state and PCM immediately and after a 100-instruction continuation. Separate
tests require alias/alignment refusal before atomic submission. These fixtures
do not initialize video; rendering is checked by the real-recording witnesses.

## Object initializer and cleanup/template path (0.4.0)

The 104-byte initializer at `0x1AE30A` through `0x1AE370` expands the 19-byte
template at A6 into selected fields of the 66-byte record at A5:

| Template bytes | Destination offset | Width |
| --- | --- | --- |
| 0, 1, 2, 3, 4, 5 | 0, 1, 6, 7, 8, 9 | Six bytes |
| 6–9 | 10 | Long |
| 10–11 | 30 | Word |
| 12–15 | 32 | Long |
| 16, 17, 18 | 41, 53, 60 | Three bytes |

It clears byte 19, bytes 20–29, bytes 42–52, bytes 54–55, and bytes 61–65.
All other record bytes remain untouched. It consumes exactly 19 source bytes,
advances A6 accordingly, and returns through the guest stack. A5 and all data
registers are preserved. Final flags are Z=1 and N/V/C=0 with X preserved.
Every activation costs 476 cycles and 27 instructions and stages 48 byte writes.
Templates may be in immutable ROM or canonical work RAM. The record, template
when in RAM, and return slot must be disjoint; record, source and stack must
be even-aligned. Unsupported ranges and aliases fall back before admission.

Tracing the first pair caller revealed the 36-byte path at `0x1AE954` through
`0x1AE976`. `finish_object()` clears D7.W, loads the byte at A1+8 into D7.B,
adds that value to the word at `0xFFF14E`, calls the pair clear, clears the
current object's first byte again, calls the buffer clear again, then sets
A5=A1 and initializes it with the fixed ROM template at `0x1B7940`. The gameplay
meaning of the accumulated word is not yet identified; the implementation
preserves its observed arithmetic without assigning a score/reward meaning.

The repeated buffer call must see the pointer already cleared by the pair.
Its known null path is composed explicitly, including the BSR and saved A6/D0
stack bytes. It never rereads the stale original pointer from live storage
while effects are still staged. No shadow machine or generic write overlay is
needed. The initializer then overwrites selected fields of the cleared current
record from immutable ROM. The nested stack and accumulated word must be
disjoint from both records and their buffers.

The whole path costs `706 + pair_cycles` and `45 + pair_instructions`, including
the repeated null leaf and initializer. It returns using the actual outer
stack slot. Final A5=A1, A6=`0x1B7953`, D7's high word is retained and its low
word holds the consumed byte. Final X is the carry from the 16-bit addition;
Z=1 and N/V/C=0 come from the initializer's last clear. The native tests cover
zero, signed overflow without carry, and unsigned wraparound, including both
objects with 256-byte buffers and the nested stack's final contents.

Use `--candidate init` or `--candidate finish` for isolated replay checks.
`composed` now gates all five recovered entries and composes their internal
calls. The first recorded initializer and cleanup path each pass original vs
replacement state/frame/PCM equality, restored 100-instruction continuation,
and fresh-process short replay. The original recording visits the initializer
1,059 times, always from ROM, and the cleanup path five times, always with a
single object and no counter carry. RAM templates, linked cleanup and arithmetic
edge cases are synthetic differential coverage, not recorded gameplay coverage.

## Shared replacement tail and incrementing entry (0.5.0)

The 18-byte tail at `0x1AF4C6` through `0x1AF4D6` calls the pair clear, sets
A5=A1 and A6=`0x1B7ABC`, calls the initializer, then returns through the actual
outer stack slot. It reinitializes the current record and clears its link;
the optional linked object is only processed by the pair clear. A5 ends at
A1, A6 at `0x1B7ACF`, A7 advances four bytes, and all data registers remain
unchanged. Final Z=1 and N/V/C=0, while X is preserved. The two nested BSR
return addresses, `0x1AF4CA` and `0x1AF4D6`, and the pair's saved-register
bytes are included in the ordered effects. Cost is `544 + pair_cycles` and
`32 + pair_instructions`, including the 476-cycle/27-instruction initializer.

The entry four bytes earlier, `0x1AF4C2`, first calls the two-instruction
helper at `0x1B0156`, which adds 15 to the word at `0xFFF14E` and returns.
`replace_object(..., increment_total=True)` composes that call before the
same tail, adding 58 cycles and three instructions. The final X flag is the
carry from this addition. The counter must be disjoint from records, buffers
and stack for this entry. The plain tail does not read the counter and does
not impose this extra guard. Both entries share the existing canonical RAM,
alignment, alias and native scheduler admission rules.

These are **two entries into a bounded shared tail**, not a recovered outer
gameplay routine. Earlier branches include sound calls and other unrecovered
effects. Original execution reaches either entry before replacement is offered;
a refusal retires one original opcode from the untouched stopped state. There
is no suspended Python call awaiting the earlier sound work. The standalone
`replace` candidate gates both entries, and `composed` includes them alongside
the five previous gates. `counted_replace_hits` is a subset of `replace_hits`.

Original execution reaches the tail 88 times: 86 single-object and two linked
paths, all with a non-null primary buffer. Ten visits include the incrementing
prefix. The other 78 pass through `0x1AF478`, with sound enabled at the sampled
entry. The 48 new native differential cases cover both entries, null and
maximum-size buffers, links, X preservation and carry/signed-overflow boundaries.
They compare full native state and PCM immediately and after 100 instructions.
The recorded prefix witness also compares rendered frames and resumes from its
portable replacement snapshot. Reports are under `artifacts/object-replace/`.

Integrated replay admits 81 replacements, of which nine include the prefix.
Total gate stops fall from 2,098 to 2,025; direct nested calls increase from
700 to 871. Replaced instructions increase by 432 to 56,796. There are 34
scheduler fallbacks and no domain fallbacks. All 225 state/frame/PCM observations
and terminal results match. This is primarily composition of previously
recovered bodies; it does not demonstrate a frame-rate improvement.

## User-recording witness

The 225.0231-second cold-start recording
`recordings/current/20260912T210640.729016Z.alreplay` reaches the leaf 1,047 times and
the caller 583 times.  The `0x1AD114 -> 0x1AE372` call site also reaches 583
times, so every caller entry observed in this recording takes the direct route.
The first call stands at `0x1AD114` on master tick 165,050,180 and reaches the
leaf at tick 165,050,306: the 18-cycle BSR costs 126 master ticks in this
profile.  The first leaf record has `A1=0xFF8368`, `A6=0x1AD0FC`,
`A7=0xFFEFC2`, `D0=0`, count 4, and buffer `0x00FFF01A`; it is within the
candidate's guarded RAM domain.

`artifacts/recovery-recon/first_entry_witness.json` records a direct local
qualification of that exact stopped entry. It runs the original leaf to its
RTS return gate, separately restores the stopped entry and admits the staged
replacement, then compares full snapshot bytes, frame bytes, and the PCM
emitted across the leaf. The result is `PASS`: 23 instructions, 288 cycles,
and 20 ordered byte writes. This is a bounded activation witness, not a
whole-replay equivalence result.

`scripts/recovery_witness.py` makes this qualification reproducible for
`--candidate leaf`, `--candidate pair`, `--candidate init`, `--candidate finish`,
`--candidate replace` (the incrementing entry)
or `--candidate composed` (the detach witness). It writes the parked gate
snapshot, a zero-input replay from that safe boundary through the region and
100-instruction tail, a post-replacement snapshot, and a receipt. For each
form it compares the selected original region with the admitted replacement,
restores the replacement snapshot in a fresh machine, then runs the same
tail. A fresh subprocess also replays the derived artifact. The leaf and the
first composed caller entries from the user recording pass every check.

The older pinned carrier is supporting evidence only.  Its connected
detachment differential compared 448 original-ROM cases covering all 28
entries, nested calls, register/CCR effects, stack overlap and rewritten
returns.  It did not qualify this Python candidate or this user recording.

## Atomic execution boundary

`Machine.atomic()` stages all ordered byte writes and final register fields.
The native executor offers the staged plan through the existing
`GenesisNativeOperation` path.  The existing scheduler only admits it when it
fits before the next admission/deadline, no trace or pending VINT applies, no
bus observer or VDP stall requires intermediate observation, and the requested
instruction budget and master limit permit the operation.  It catches the Z80
up before the operation and again after the charged time.  Candidate code does
not maintain a separate clock.

The leaf's RAM-only preflight is intentionally conservative.  The native
admission path refuses the operation while the running Z80 bank already maps
RAM, and installs a temporary Z80-window observer that invalidates the run if
the Z80 reaches work RAM during the atomic span.  It also refuses when another
sound observer is active.  This means the candidate only claims atomicity
when neither processor can observe an intermediate RAM write; a future wider
domain needs its own measured observer policy.

## Integrated qualification

Before pair recovery, composed mode passed with 581 caller activations, 459
other leaf activations and nine scheduler fallbacks. With pair recovery in 0.3.0 it
passes with 581 caller, 101 pair and 355 leaf activations, plus 12 scheduler
fallbacks. All 225 observations, terminal state/frame and whole-run PCM match.
It replaces 28,099 of 140,704,253 M68000 instructions (about 0.0200%), up 520.
There are 685 direct nested Python calls, up 104; total observed gates remain
1,049 because the new pair gates replace internal leaf gates. This is a small
increase in recovered game behavior, not a demonstrated frame-rate improvement.

The original recording enters the pair 104 times: 101 single-object and three
linked-object paths. Every visited buffer is non-null. It never exercises the
nonzero or set-bit detach routes, which remain covered by synthetic ROM tests.
The first pair activation at tick 1,066,357,857 passes immediate full-state,
frame and PCM equality, restored continuation, and fresh-process short replay.
Reports and its portable snapshots/replay live under
`artifacts/pair-recovery/`; `coverage.json` separately records original entry
and branch counts. Wrong-result, wrong-continuation and wrong-timing controls
are rejected under the same ROM/profile. See
[STATUS.md](STATUS.md) for reports and the distinction from hardware validation.

With initialization and cleanup composition in 0.4.0, the full replay admits
1,040 initializer, five cleanup, 581 detach, 96 pair and 350 leaf activations.
There are 26 scheduler fallbacks and no domain fallbacks. All 225 observations,
terminal state/frame and whole-run PCM still match. Replaced instructions rise
from 28,099 to 56,364 (about 0.0401% of 140,704,253); direct nested calls rise
from 685 to 700. Total gates rise from 1,049 to 2,098 because the initializer
now has its own entry gate. No overall speedup is claimed. Reports, exact source
identities and short witnesses live under `artifacts/object-init/`.
