# First recovery candidate: shared clear and detach caller

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
permits aliases.

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

The composed candidate owns only that observed zero/bit-clear caller route.
It falls back before any write for a nonzero script byte, a set bit, a
noncanonical/overlapping RAM span, or atomic scheduler refusal.  It calls the
Python leaf calculation directly inside its staged atomic plan.  With a null
linked record, its total is `80 + leaf_cycles + 70`; with a non-null linked
record, `80 + leaf_cycles + 152`.  Its instruction total is respectively
`7 + leaf_instructions + 4` or `7 + leaf_instructions + 9`.
Its execution receipt separately reports admitted leaf and caller hits,
direct Python leaf calculations made by caller composition, replaced M68000
instructions, and charged M68000 cycles.  A refused plan is counted as a
fallback and the original resumes at its stopped opcode.

## User-recording witness

The 225.0231-second cold-start recording
`recordings/20260912T210640.729016Z.alreplay` reaches the leaf 1,047 times and
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
`--candidate leaf` or `--candidate composed`. It writes the parked gate
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

The full user replay passes with 1,040 admitted leaf calls and seven timing
fallbacks. Composed mode passes with 581 caller activations, 459 other leaf
activations and nine fallbacks, eliminating 581 internal guest call transitions.
Both compare all 225 ordered observations and whole-run PCM; composed mode also
passes using the installed package. Wrong-result, wrong-continuation and
wrong-timing candidates are rejected under the same ROM/profile. See
[STATUS.md](STATUS.md) for reports and the distinction from hardware validation.
