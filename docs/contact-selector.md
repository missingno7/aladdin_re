# Contact decrement and script selector

`1AEC00` now owns its non-`0x13` counter-decrement branch through `1AD150`.
The selector is a finite live-RAM priority tree: it chooses the next script in
`A2`, clears its documented state bytes, and has one immutable ROM-table arm.
The caller stores that pointer in `FF7E60`, clears its local mode state, and
performs the `0x18` object rewrite when required.  Command `8` uses the
existing synchronous sound runner with the original 28-byte MOVEM/argument/JSR
frame; the direct entry, C6/DA wrappers, and dispatcher compose that same seam.

The only production gates remain `1AEC00`, `1AE9C6`, `1AE9DA`, and the already
owned `1ABC82` dispatcher.  `1AD150` has no standalone gate because later
recordings show other callers.  Type `0x13` remains whole-entry fallback before
any decrement write, including its command-`0x6A` path.

## Exact bounded domain

The semantic selector orders `FFF0D7`, `FFF173`, `FFF115`, `FFF0CD/D3`, the
unconditional `D3 == 0x5E` check, `FFF0DB`, `FFF0D0` with the 16-entry ROM
table at `121828`, `FFF0D2`, `FFF0C1`, `DE/DF/ED`, and `FFF0B0`.  Its live-RAM
inputs and writes are disjoint from the record and guest frame before planning.
The table arm preserves D0's upper word, writes the low-word shifted index, and
has its distinct X/CCR residue.  Every selector route preserves the original
RTS last-PC identity in its oracle plan.

For the decrement caller, `A1+1` must be nonzero, so counter wrap remains an
original fallback.  Directional entry prefixes are `118 / 9` cycles /
instructions for `FF7E49 == 0` and `126 / 10` otherwise.  The sound-off
inner decrement is `92 / 6`; its baseline selector is `308 / 22`; its local
non-`0x18` suffix is `152 / 10` and the `0x18` suffix is `202 / 13`.
The command-`8` prefix is `124 / 6`, returns first at `1AEC4C`, and the shared
runner admits the actual second-JSR residue `1AEC52` before applying its local
suffix.  The sound argument is decimal **8**, not command `0x31`.

## Qualification

- `artifacts/grinding/luna/selector-1ad150/report.json` records 76 paired
  original-ROM selector cases.  Parent's full AtomicPlan review is
  `artifacts/grinding/parent/selector-plan-review.json`; all 50 current
  branch/CCR/last-PC cases pass.
- `tests/test_contact_selector_review.py` composes table and non-table selector
  residue through the real `1AEC00` entry and checks 150 native instructions.
- Disposable strict matrices under `artifacts/grinding/terra/` cover old/new,
  directions, types `0x10`/`0x18`/ordinary non-`0x13`, command-8 direct/C6/DA,
  dispatcher C6/DA, an `FFF57D=0x80` prefix CCR, and a nondefault ROM-table
  selector.  They compare the complete native snapshot, registers, RAM,
  frame, PCM, cycles, and instructions.
- The recorded state-changing dispatcher witness is
  `artifacts/grinding/parent/decrement-recorded-witness/report.json`: strict
  exit, 150-original-instruction future, and fresh-process restore pass with
  two gates, six direct Python calls, one original sound span, 65 instructions,
  and 970 charged cycles.  Result, continuation, and timing controls reject in
  `artifacts/grinding/parent/decrement-controls/report.json`.
- `artifacts/grinding/parent/decrement-edit-loop/result.json` passes in
  0.849 s and a pointer mutation diverges in 0.779 s, with the native DLL
  unchanged and no build or installation.

## Manual cost and limits

The new semantic work is the flag-priority script selection and the connected
counter/type state change.  Reused machinery is the live-RAM reader, planned
write view, AtomicPlan admission, wrapper/dispatcher composition, and the
existing synchronous sound runner with its frame, return-slot, deadline,
foreign-return, and snapshot guards.  New handwritten machine recipes are the
selector's branch timing/CCR/last-RTS matrix, two directional caller prefixes,
and the command-8 local suffix.  No continuation object, scheduler rule,
native API, persistent mirror, or generic sound framework was added.

This does not recover standalone `1AD150` callers, counter wrap, or type-`0x13`
retirement/command `0x6A`.  Those domains retain original execution.
