"""The object post-process kind dispatch (``0036E2``), reached from ``003284``'s own body (the
achievements-record status ``> 4`` arm, ``docs/gods/blockers/2026-09-19-003480.md``'s own
reconnaissance) with the entry's own template kind word already in a live register.

A 13-entry ``(kind: word, handler: long)`` function-pointer table at ROM ``0x00370E``: most handlers
are the already-recovered dynamic sprite emitter (``0018C8``) or its sibling tile painter (``001810``,
directly or through a small per-frame index adjustment); a literal kind (``0x71``) short-circuits with
no call at all; an unmatched kind falls back to ``001810`` directly.  Every one of these dispatched
handlers is real ROM code this module does not reproduce -- the boundary cedes to it as one opaque
block (the same shape ``achievement_slot_dispatch_plan`` already proved for ``0047DA``), so only the
table lookup itself is named here as a pure function of ``read(address, size)``.

The dispatch's own EXIT is not an RTS: ``bra.w $3158``, back into ``0030CC``'s own 200-entry object
scan loop.  That address, and everything past it, belongs to the scan, not this dispatch.
"""
from __future__ import annotations

KIND_TABLE = 0x00370E
KIND_TABLE_COUNT = 13
NOOP_KIND = 0x0071
FALLBACK_HANDLER = 0x001810                 # the table's own exhaustion arm: a plain bsr into the tile painter


def classify_object_kind(read, kind):
    """What ``0036E2`` does with the template's own kind word.

    Returns the arm (``'noop'``: no call at all; ``'dispatch'``: the matched
    table entry's own handler, with ``mismatches`` the number of entries
    skipped before it, for the boundary's own cost formula; ``'fallback'``:
    every entry mismatched, `FALLBACK_HANDLER` runs instead) and, for
    ``'dispatch'``, the handler address read directly from the table.
    """
    if kind == NOOP_KIND:
        return {'arm': 'noop'}
    address = KIND_TABLE
    for index in range(KIND_TABLE_COUNT):
        entry_kind = read(address, 2)
        if entry_kind == kind:
            handler = read(address + 2, 4) & 0xFFFFFF
            return {'arm': 'dispatch', 'mismatches': index, 'handler': handler}
        address += 6
    return {'arm': 'fallback', 'mismatches': KIND_TABLE_COUNT, 'handler': FALLBACK_HANDLER}


# --- 002F2E: the effect queue append (reached from 003480's own body; the DRAIN half, 0x2F68 --
# pulling the queue's own head, decrementing a per-entry lifetime, calling the already-recovered
# 001164 -- is a separate, still-unrecovered caller, not modelled here) -------------------------
#
# A 10-slot, 10-byte-stride queue at QUEUE_BASE: the first word negative marks a slot free.  QUEUE_GATE
# (FFFFF240), when already zero, skips the scan entirely and writes straight into slot 0 (real ROM
# guarantees slot 0 is free whenever the gate reads zero -- the gate is exactly "the queue has never
# been appended to" as far as this routine's own logic assumes, never independently verified here);
# otherwise the ten slots are scanned in order for the first free one.  A found slot gets the caller's
# own D0/D1/D2 (position and a caller-chosen word) plus two fixed words (LIFETIME, START_FLAG) and the
# gate is set to 1.  Exhausting every slot with none free is real ROM (a silent drop, no store at all)
# no recording enters: declined.
QUEUE_BASE = 0xFFFF09FE
QUEUE_GATE = 0xFFFFF240
QUEUE_SLOT_STRIDE = 0xA
QUEUE_SLOT_COUNT = 10
QUEUE_LIFETIME = 0x0006     # the fixed word every append writes at the entry's own +6
QUEUE_START_FLAG = 0xFFF4   # the fixed word every append writes at the entry's own +8
QUEUE_WITNESSED_SCAN_DEPTH = range(0, 7)   # 0-6 occupied slots checked before a free one, all witnessed


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def queue_append(read, d0, d1, d2):
    """002F2E: append (d0, d1, d2) to the effect queue.

    Returns the arm (``'direct'``: QUEUE_GATE was zero, slot 0 used with no scan at all; ``'found'``:
    the scan found a free slot after ``depth`` occupied ones; ``'full'``: every slot occupied, a real,
    unwitnessed silent drop), the chosen slot's own address (``None`` for ``'full'``) and the stores.
    """
    if read(QUEUE_GATE, 2) == 0:
        slot = QUEUE_BASE
        arm, depth = 'direct', None
    else:
        slot, depth = None, None
        for index in range(QUEUE_SLOT_COUNT):
            candidate = (QUEUE_BASE + QUEUE_SLOT_STRIDE * index) & 0xFFFFFFFF
            if _signed_word(read(candidate & 0xFFFFFF, 2)) < 0:
                slot, depth = candidate, index
                break
        if slot is None:
            return {'arm': 'full', 'slot': None, 'depth': QUEUE_SLOT_COUNT, 'stores': {}}
        arm = 'found'
    address = slot & 0xFFFFFF
    # QUEUE_GATE is ordered first, not last: every future append sets it back to exactly 1 regardless
    # of what it held, so a generic "flip the last write" negative control on it would self-heal on
    # the very next append, before the drain half could ever observe the corruption.  The slot's own
    # fields persist until THIS slot is next reused, which is far less frequent.
    stores = {QUEUE_GATE & 0xFFFFFF: (1, 2), (address + 8) & 0xFFFFFF: (QUEUE_START_FLAG, 2),
             (address + 6) & 0xFFFFFF: (QUEUE_LIFETIME, 2), (address + 4) & 0xFFFFFF: (d2 & 0xFFFF, 2),
             (address + 2) & 0xFFFFFF: (d1 & 0xFFFF, 2), address: (d0 & 0xFFFF, 2)}
    return {'arm': arm, 'slot': slot, 'depth': depth, 'stores': stores}


# --- the 005958 table's own witnessed handlers (jsr'd from 00352C, inside 003480's own still-
# unrecovered body -- docs/gods/blockers/2026-09-19-003480.md) -----------------------------------
#
# A ROM-constant scan over a 192-byte table (SOUND_SCAN_TABLE) counts zero bytes among the caller's
# own status-many entries (status is SIGNED: a subq.w #1/bmi test, not a plain count -- status <= 0
# scans nothing), doubled twice into a real 23-entry (not 16: the prior reconnaissance's own read
# stopped at the first table-shaped run of bytes, but table-shaped code follows -- confirmed by this
# session's own full-tree trace of every occurrence, and by reading the ROM past entry 15 directly)
# function-pointer table at KIND_DISPATCH_TABLE.  Fifteen of the twenty-three are witnessed; seven are
# recovered here as their own leaves (indices 0, 3, 10, 14, 15, 16, 21); the rest (1, 2, 4, 6, 17, 18,
# 19, 22 -- witnessed but not yet recovered; and every unwitnessed index) decline by name.  Each
# handler ends in a plain rts (no seam, no tail branch): 003480's own body resumes at 003532 either
# way, and at least one of them (index 10, ROM 0x5A48) has a second, independent real caller elsewhere
# (exit 008616 in this session's own census) -- the leaf does not assume which caller it serves.
SOUND_SCAN_TABLE = 0x00014B42
SOUND_SCAN_TABLE_SIZE = 192
KIND_DISPATCH_TABLE = 0x00005958
KIND_DISPATCH_COUNT = 23
KIND_DISPATCH_WITNESSED = frozenset({0, 1, 2, 3, 4, 6, 10, 14, 15, 16, 17, 18, 19, 21, 22})
KIND_DISPATCH_ADMITTED = frozenset({0, 3, 10, 14, 15, 16, 21})


def kind_table_count(read, status):
    """0x3502-351E: the zero-byte count over SOUND_SCAN_TABLE's own first max(status, 0) bytes."""
    limit = status if status > 0 else 0
    return sum(1 for i in range(limit) if read((SOUND_SCAN_TABLE + i) & 0xFFFFFF, 1) == 0)


EF3C_BYPASS = 0xFFFFEF3C
EF3E_COUNTER = 0xFFFFEF3E
EF3E_CAP = 0x18
ACCUM_CUE_ADDRESS = 0xFFFFFDF6
ACCUM_CUE = 0x52
SPECIAL_TIMER = 0xFFFFF156   # the SAME SPECIAL_TIMER game.pickups already names
# (increment, has its own sound cue) per handler index; index 20 (increment 4) is real ROM, witnessed
# by no recording, and stays undescribed here on purpose -- only the four this session found in the
# ROM at all are named, and only three of those (0, 3, 21) are witnessed.
ACCUMULATOR_PARAMS = {0: (0xC, True), 3: (0x18, True), 21: (3, False)}


def accumulator_step(read, index):
    """Indices 0, 3, 21: EF3C negative bypasses entirely; otherwise EF3E is incremented by the
    index's own amount (always stored, even when the cap check below fails), and indices 0/3 ALSO
    write a fixed sound cue (0x52) unconditionally before the cap check.  Once EF3E exceeds EF3E_CAP
    it is reset to the cap and the excess, scaled by 32, is folded into SPECIAL_TIMER when
    SPECIAL_TIMER is not itself negative."""
    increment, has_cue = ACCUMULATOR_PARAMS[index]
    if _signed_word(read(EF3C_BYPASS, 2)) < 0:
        return {'arm': 'bypass', 'stores': {}}
    stores = {}
    if has_cue:
        stores[ACCUM_CUE_ADDRESS & 0xFFFFFF] = (ACCUM_CUE, 2)
    counter = (read(EF3E_COUNTER, 2) + increment) & 0xFFFF
    stores[EF3E_COUNTER & 0xFFFFFF] = (counter, 2)
    if _signed_word(counter) <= EF3E_CAP:
        return {'arm': 'below-cap', 'stores': stores}
    stores[EF3E_COUNTER & 0xFFFFFF] = (EF3E_CAP, 2)
    d0 = ((counter - EF3E_CAP) << 5) & 0xFFFF
    timer = read(SPECIAL_TIMER, 2)
    if _signed_word(timer) < 0:
        return {'arm': 'accumulate-skip', 'stores': stores, 'd0': d0}
    stores[SPECIAL_TIMER & 0xFFFFFF] = ((timer + d0) & 0xFFFF, 2)
    return {'arm': 'accumulate', 'stores': stores, 'd0': d0}


SOUND_CUE_PAIR_FDF4 = 0xFFFFFDF4
SOUND_CUE_PAIR_FDF6 = 0xFFFFFDF6
SOUND_CUE_PAIR_COUNTER = 0xFFFFF1CC


def sound_cue_pair(read):
    """Index 10 (ROM 0x5A48): two fixed sound cues and a shared counter incremented by one."""
    value = (read(SOUND_CUE_PAIR_COUNTER, 2) + 1) & 0xFFFF
    return {'stores': {SOUND_CUE_PAIR_FDF4 & 0xFFFFFF: (0x4C, 2), SOUND_CUE_PAIR_FDF6 & 0xFFFFFF: (0x4D, 2),
                       SOUND_CUE_PAIR_COUNTER & 0xFFFFFF: (value, 2)}}


COPY_TABLE_DEST = 0xFFFFF53A
COPY_TABLE_LONGS = 6
COPY_SOURCE = {14: 0x0142BC, 15: 0x0142D4, 16: 0x0142EC}


def copy_table(read, index):
    """Indices 14/15/16 (ROM 0x142A6/0x14292/0x1429C): the shared 24-byte (six-long) ROM-to-RAM copy
    (0x142AA) each feeds with its own fixed source block.  Index 14 reaches the copy by falling
    through with no store of its own D3 (whatever the caller's D3 already held survives, a real
    difference from 15/16's own explicit ``moveq #1,d3``, which the boundary's own register file
    must reproduce, not this pure function)."""
    source = COPY_SOURCE[index]
    stores = {(COPY_TABLE_DEST + 4 * i) & 0xFFFFFF: (read((source + 4 * i) & 0xFFFFFF, 4), 4)
             for i in range(COPY_TABLE_LONGS)}
    return {'stores': stores}
