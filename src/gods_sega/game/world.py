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
