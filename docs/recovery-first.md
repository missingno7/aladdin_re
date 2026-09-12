# Recovered object cleanup: buffer, object pair and detach caller

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

The implementation lives in `src/aladdin_sega/recovered.py` as
`clear_auxiliary_buffer()`, `clear_object_pair()` and `detach_object()`.
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
`--candidate leaf`, `--candidate pair` or `--candidate composed`. It writes the parked gate
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
other leaf activations and nine scheduler fallbacks. With pair recovery it
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
