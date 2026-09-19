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
