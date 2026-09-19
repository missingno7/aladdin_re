"""004926: the box-scan puff spawner.

Reached from the trigger evaluator's own firing-arm action table (``0048EA``'s own unconditional
callee, ``docs/gods/blockers/2026-09-16-00462C-firing.md``'s Split part 3 -- ``0048EA`` itself is not
yet recovered) and, separately, from a second, unrelated call site at ``0139D2`` inside the
collectible-lists subsystem (`docs/gods/tick-map.md` order 14, `013342`/`013362` -- not recovered
either).  Neither caller's own semantics is assumed here; both leave the same box bounds in
``d0``-``d3`` and the same return address on the stack, and this leaf only ever reads them.

Scans the SAME 200-entry, 8-byte-stride placed-object table ``movement.BOX_SCAN_TABLE`` the
box-overlap scan (`00722C`) and the world update (`0030CC`, `docs/gods/blockers/2026-09-19-0030CC.md`)
share.  An entry's own ``+4`` word is its inactive flag when negative; when non-negative it doubles as
an index into ``achievements.RECORD_TABLE`` (the SAME double/double/double ADDA.W arithmetic
``achievements._record_address`` already models, ten bytes a record) -- a record whose own ``+4``
status word reads 4 is a candidate.  A caller-supplied box (``x_min <= x <= x_max``, ``y_min <= y <=
y_max``, all signed) selects it for real.

Up to two selected entries are consumed per activation (their own ``+4``/``+6`` words cleared to mark
them spent) and queued as a ``spawn_queue`` puff: the first free slot among its four (``0049DA``'s own
``SLOT_BASE`` -- every slot occupied is real ROM, the routine's own fallback overwrites the last slot,
never witnessed by any recording), the entry's own ``x - 8`` and (ordinarily) its raw ``y``; a sound
cue (``FDF4 = 0x3D``) is requested once per activation with at least one consumed entry.

One entry's own record header of exactly ``0x60`` takes a second, unwitnessed shape (the QUEUED ``y``
also adjusted by ``-8`` -- the register ``d7`` itself is never touched, only the spawn-queue memory
copy); no recording has ever reached it, so it stays declined by name, along with a second consumed
entry in the same activation (the scan's own early-exit-at-two-matches path, `0049CE`-`0049D4`) and the
all-slots-occupied spawn case.

Pure function of ``read(address, size)``; no cycles, CCR, stack or registers.
"""
from __future__ import annotations

from . import achievements, movement, pickups, spawn_queue

RECORD_MATCH_STATUS = 4
SPECIAL_RECORD_HEADER = 0x60          # unwitnessed: the extra queued-y -8 adjustment arm
MAX_CONSUMED = 2                      # the scan's own early-exit count; a second consume is unwitnessed
SOUND_CUE = pickups.SOUND_CUE          # FFFDF4: the same sound-command word other regions request through
SPAWN_SOUND_CUE = 0x3D
X_ADJUST = 8
FOUND_COUNT = 0xFFF398                 # word: the scan's own scratch consume counter, cleared every activation


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def find_spawn_slot(read):
    """The routine's own head (`004936`-`004948`): the first `spawn_queue` slot (0-3) whose own
    counter word is negative (empty).  All four occupied is real ROM -- the routine backs its own
    pointer up to slot 3 and overwrites it regardless -- but no recording has ever been witnessed
    with every slot full at once, so ``exhausted`` stays a fact for the boundary to decline.

    Returns ``{'index': the slot to use, 'checked': how many slots this scan tested, 'exhausted':
    bool}``.
    """
    for index in range(spawn_queue.SLOT_COUNT):
        counter = read(spawn_queue.SLOT_BASE + spawn_queue.SLOT_SIZE * index, 2)
        if _signed_word(counter) < 0:
            return {'index': index, 'checked': index + 1, 'exhausted': False}
    return {'index': spawn_queue.SLOT_COUNT - 1, 'checked': spawn_queue.SLOT_COUNT, 'exhausted': True}


def scan_and_spawn(read, x_min, y_min, x_max, y_max):
    """The 200-entry scan itself (`00494A`-`0049D8`).

    Returns:

    ``entries``: one dict per visited entry, in scan order, each carrying its own ``arm`` (one of
    ``'inactive'``, ``'status-miss'``, ``'box-miss-x-min'``, ``'box-miss-x-max'``,
    ``'box-miss-y-min'``, ``'box-miss-y-max'``, ``'match'``) for the boundary's own per-entry costing.

    ``consumed``: up to two matches, in scan order, each ``{'index', 'addr', 'header', 'x', 'y',
    'queued_x', 'queued_y', 'special'}`` -- ``queued_x``/``queued_y`` are what the spawn-queue slot
    itself receives (``x - 8`` always; ``y`` unless ``special``, unwitnessed, also ``-8``).

    ``last_active``: the LAST entry's own (non-negative) header, or ``None`` if every one of the 200
    was inactive -- ``d5``/``a2``'s own exit residue (`004954`-`004962` runs for this entry alone, and
    for no other).

    ``last_status_match``: ``(d6, d7)`` as the LAST entry to reach the record-status compare (`004964`)
    leaves them -- ``d7`` is always that entry's own raw ``y`` (the register itself is never adjusted,
    matched or not); ``d6`` is that entry's own raw ``x`` UNLESS it was also consumed, in which case
    it is ``x - 8`` (the consume block's own ``subq.w #8,d6`` acts on the register directly).  ``None``
    if no entry ever reached the compare.

    ``end_index``: always 200 in the witnessed domain (a second consume's own early exit, `0049D4`, is
    never modelled: the boundary declines a ``consumed`` list longer than one entry outright).
    """
    entries = []
    consumed = []
    last_active = None
    last_status_match = None
    xmin, xmax = _signed_word(x_min), _signed_word(x_max)
    ymin, ymax = _signed_word(y_min), _signed_word(y_max)
    addr = movement.BOX_SCAN_TABLE
    for index in range(movement.BOX_SCAN_COUNT):
        header = read((addr + 4) & 0xFFFFFF, 2)
        if _signed_word(header) < 0:
            entries.append({'index': index, 'addr': addr, 'arm': 'inactive'})
            addr = (addr + movement.BOX_SCAN_STRIDE) & 0xFFFFFFFF
            continue
        last_active = header
        record = achievements._record_address(header)
        status = read((record + 4) & 0xFFFFFF, 2)
        if status != RECORD_MATCH_STATUS:
            entries.append({'index': index, 'addr': addr, 'header': header, 'record': record,
                            'status': status, 'arm': 'status-miss'})
            addr = (addr + movement.BOX_SCAN_STRIDE) & 0xFFFFFFFF
            continue
        x = read(addr & 0xFFFFFF, 2)
        y = read((addr + 2) & 0xFFFFFF, 2)
        sx, sy = _signed_word(x), _signed_word(y)
        last_status_match = (x, y)
        if not (xmin <= sx):
            entries.append({'index': index, 'addr': addr, 'header': header, 'x': x, 'y': y,
                            'arm': 'box-miss-x-min'})
            addr = (addr + movement.BOX_SCAN_STRIDE) & 0xFFFFFFFF
            continue
        if not (sx <= xmax):
            entries.append({'index': index, 'addr': addr, 'header': header, 'x': x, 'y': y,
                            'arm': 'box-miss-x-max'})
            addr = (addr + movement.BOX_SCAN_STRIDE) & 0xFFFFFFFF
            continue
        if not (ymin <= sy):
            entries.append({'index': index, 'addr': addr, 'header': header, 'x': x, 'y': y,
                            'arm': 'box-miss-y-min'})
            addr = (addr + movement.BOX_SCAN_STRIDE) & 0xFFFFFFFF
            continue
        if not (sy <= ymax):
            entries.append({'index': index, 'addr': addr, 'header': header, 'x': x, 'y': y,
                            'arm': 'box-miss-y-max'})
            addr = (addr + movement.BOX_SCAN_STRIDE) & 0xFFFFFFFF
            continue
        special = (header & 0xFFFF) == SPECIAL_RECORD_HEADER
        queued_x = (x - X_ADJUST) & 0xFFFF
        queued_y = ((y - X_ADJUST) & 0xFFFF) if special else y
        last_status_match = (queued_x, y)
        match = {'index': index, 'addr': addr, 'header': header, 'x': x, 'y': y,
                'queued_x': queued_x, 'queued_y': queued_y, 'special': special}
        entries.append({**match, 'arm': 'match'})
        consumed.append(match)
        addr = (addr + movement.BOX_SCAN_STRIDE) & 0xFFFFFFFF
        if len(consumed) >= MAX_CONSUMED:
            break
    return {'entries': entries, 'consumed': consumed, 'last_active': last_active,
            'last_status_match': last_status_match, 'end_index': len(entries)}
