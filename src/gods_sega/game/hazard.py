"""The hazard tick (ROM 014084-01415C/014106), called 300-330 times / 600 frames from ``013F3A``.

Called with an object record (A1: an active byte at ``+0x48``), a second
record (A3, read or cleared depending on the arm) and a world position
(D0/D1).  When the object is active, its position (offset by the shared
pair ``OBJECT_X``/``OBJECT_Y``, the same globals the pool fill below also
reads) is turned into a cell address in the level grid (``0063FA``'s and
``00FDB8``'s own table, ``FF885E``, by the same asr/andi/asl arithmetic,
just its own bias) -- a cell holding 1 (the ``'spawn'`` arm) requests a
sound, then (rarely, gated by a byte in a parallel table 0x2000 before the
grid cell and a counter) calls an unrecovered routine (declined), then
scans a fixed 20-entry pool at ``FFF90E`` for an empty slot (a word < 0)
and fills it with the position, clearing the caller's own pending flag
(A3) whether or not a slot was free.  Inactive, or a cell holding anything
else, falls through to the ``'paint'`` arm instead: a byte from A3+1 is
written into up to two of four fixed cells of a second array (``FFBBDE``,
bounds ``FFBBAA``-``FFC156``) picked by the position and its own low bits,
or nothing at all outside those bounds.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

from .grid import GRID_TABLE

ACTIVE_FLAG = 0x48                     # A1 byte: zero selects the 'paint' arm outright
OBJECT_X, OBJECT_Y = 0xFFFFF3EE, 0xFFFFF3F0    # words: added to D0/D1 for both the grid cell and the pool fill
CELL_BIAS = 8                            # both axes biased by the same 8 pixels here (unlike 00FDB8's 0x10/0x8)
CELL_ROW_MASK = 0xFFF0
SOLID_CELL = 1                            # the grid cell value that selects the 'spawn' arm
SOUND_COMMAND, SOUND_REQUEST = 0xFFFFFDF4, 0x38
TYPE_TABLE_OFFSET = -0x2000              # relative to the grid cell address, not a fixed base
TRIGGER_TYPE = 0x14
TRIGGER_COUNTER = 0xFFFFEEF8             # word, signed: trigger needs this >= 2
POOL_BASE, POOL_STRIDE, POOL_COUNT = 0xFFFF090E, 0xC, 0x14
POOL_COUNTER = 0xFFFFF25E
TILE_BASE, TILE_LOW, TILE_HIGH = 0xFFFFBBDE, 0xFFFFBBAA, 0xFFFFC156
TILE_ROW = 0x30                          # the second array's own row stride


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _cell_address(read, x, y):
    ex = (x + read(OBJECT_X, 2) + CELL_BIAS) & 0xFFFF
    ey = (y + read(OBJECT_Y, 2) + CELL_BIAS) & 0xFFFF & CELL_ROW_MASK
    column = (_signed_word(ex) >> 5) & 0xFFFF
    row = (ey << 3) & 0xFFFF
    address = (GRID_TABLE + _signed_word(column) + _signed_word(row)) & 0xFFFFFFFF
    return address, row


def _paint(read, a3, d0, d1):
    # Each adda.w sign-extends its own word operand before adding: three separate signed adds,
    # not one combined offset (an intermediate word can carry a sign the combined total would not).
    x_shift = (_signed_word(d0) >> 3) & 0xFFFF
    y_masked = d1 & 0xFFF8
    doubled1 = (y_masked * 2) & 0xFFFF          # add.w d5,d5 (the first doubling)
    doubled2 = (doubled1 * 2) & 0xFFFF          # add.w d5,d5 again: the tile-setup block's final X-setter
    address = TILE_BASE
    address = (address + _signed_word(x_shift)) & 0xFFFFFFFF
    address = (address + _signed_word(doubled1)) & 0xFFFFFFFF
    address = (address + _signed_word(doubled2)) & 0xFFFFFFFF
    result = {'arm': 'paint', 'a0': address, 'x_shift': x_shift, 'doubled1': doubled1, 'doubled2': doubled2,
              'painted': False, 'stores': {}}
    if not (TILE_LOW <= address < TILE_HIGH):
        return result
    value = read(a3 + 1, 1)
    address &= 0xFFFFFF
    if d1 & 4:
        offsets = (TILE_ROW, TILE_ROW + 0x30, TILE_ROW + 1, TILE_ROW + 0x31)
    else:
        offsets = (0, TILE_ROW, 1, TILE_ROW + 1)
    stores = {(address + offset) & 0xFFFFFF: (value, 1) for offset in offsets}
    result.update(painted=True, stores=stores, d4=d1 & 4, value=value)
    return result


def _spawn(read, a1, cell, row, a3, d0, d1):
    # 0140BC-0140CA: a type match against a parallel table (0x2000 before the grid cell) AND the
    # trigger counter reaching 2 gate a call into the proximity table (00F828, game.hazard.
    # proximity_search/proximity_add/proximity_trigger, all recovered on their own merits) BEFORE
    # this SAME pool fill -- a type mismatch, or a match with the counter still under 2, skips the
    # call outright and falls straight into the fill (0140D2 onward, common to every arm here).
    type_match = read((cell + TYPE_TABLE_OFFSET) & 0xFFFFFF, 1) == TRIGGER_TYPE
    counter = _signed_word(read(TRIGGER_COUNTER, 2))
    proximity = None
    if type_match:
        if counter < 2:
            return {'arm': 'trigger', 'reason': 'gate-unwitnessed', 'stores': {}}
        search = proximity_search(read, cell)
        if search['arm'] == 'trigger':
            entry_base = (PROXIMITY_TABLE + PROXIMITY_STRIDE * search['index']) & 0xFFFFFFFF
            sub = proximity_trigger(read, a1, entry_base)
            if sub['arm'] == 'unrecovered':
                return {'arm': 'trigger', 'reason': 'proximity-selector-unwitnessed', 'stores': {},
                        'selector': sub['selector']}
            proximity = {'kind': 'trigger', 'search': search, 'result': sub}
        else:
            added = proximity_add(read, search['offset'], search['d4'], search['d5'])
            if added['arm'] == 'pool-full':
                return {'arm': 'trigger', 'reason': 'proximity-pool-full', 'stores': {}}
            proximity = {'kind': 'added', 'search': search, 'result': added}
    slot = None
    for index in range(POOL_COUNT):
        entry = POOL_BASE + POOL_STRIDE * index
        if _signed_word(read(entry, 2)) < 0:
            slot = entry
            break
    stores = {SOUND_COMMAND & 0xFFFFFF: (SOUND_REQUEST, 2), a3 & 0xFFFFFF: (0, 2)}
    if proximity is not None:
        stores.update(proximity['result']['stores'])
    result = {'arm': 'spawn', 'slot': slot, 'stores': stores, 'proximity': proximity}
    if slot is not None:
        obj_x = (d0 + read(OBJECT_X, 2)) & 0xFFFF
        obj_y = (d1 + read(OBJECT_Y, 2)) & 0xFFFF
        stores[slot & 0xFFFFFF] = (0, 2)
        stores[(slot + 2) & 0xFFFFFF] = (obj_x, 2)
        stores[(slot + 4) & 0xFFFFFF] = (obj_y, 2)
        stores[(slot + 6) & 0xFFFFFF] = (0, 4)
        stores[(slot + 0xA) & 0xFFFFFF] = (0, 2)
        counter_before = read(POOL_COUNTER, 2)
        stores[POOL_COUNTER & 0xFFFFFF] = ((counter_before + 1) & 0xFFFF, 2)
        result.update(d4=obj_x, d5=obj_y, a1=(slot + POOL_STRIDE) & 0xFFFFFFFF, counter_before=counter_before)
    else:
        # The loop's own dbra runs D4 down to -1 (0xFFFF) without ever finding a slot; D5 is
        # never touched inside the loop, so it keeps the grid computation's own row word.
        result.update(a1=(POOL_BASE + POOL_STRIDE * POOL_COUNT) & 0xFFFFFFFF, d4=0xFFFF, d5=row)
    return result


def effect_pool_add(read, d0, d1, d2, d3):
    """00932C: the general form of the pool fill ``_spawn`` inlines with ``d2=d3=0``.

    Scans the same 20-entry pool for a free slot (a word < 0) and, when one
    exists, fills it with ``(d0+OBJECT_X, d1+OBJECT_Y, d2, d3, 0)`` and
    advances ``POOL_COUNTER``; an exhausted pool is the ``'full'`` arm
    (no store).  Called separately from the pickup check ``00BA8E``
    (``game/pickups.py: pickup_check``) with the caller's own D2/D3.
    """
    for index in range(POOL_COUNT):
        entry = POOL_BASE + POOL_STRIDE * index
        if _signed_word(read(entry, 2)) < 0:
            obj_x = (d0 + read(OBJECT_X, 2)) & 0xFFFF
            obj_y = (d1 + read(OBJECT_Y, 2)) & 0xFFFF
            counter_before = read(POOL_COUNTER, 2)
            stores = {entry & 0xFFFFFF: (0, 2), (entry + 2) & 0xFFFFFF: (obj_x, 2),
                     (entry + 4) & 0xFFFFFF: (obj_y, 2), (entry + 6) & 0xFFFFFF: (d2 & 0xFFFF, 2),
                     (entry + 8) & 0xFFFFFF: (d3 & 0xFFFF, 2), (entry + 0xA) & 0xFFFFFF: (0, 2),
                     POOL_COUNTER & 0xFFFFFF: ((counter_before + 1) & 0xFFFF, 2)}
            return {'arm': 'added', 'index': index, 'slot': entry, 'stores': stores,
                    'obj_x': obj_x, 'obj_y': obj_y, 'counter_before': counter_before}
    return {'arm': 'full', 'index': None, 'slot': None, 'stores': {}}


def hazard_tick(read, a1, a3, d0, d1):
    """What ``014084`` does for object ``a1``, the secondary record ``a3`` and position ``(d0, d1)``.

    Returns the arm (``'paint'`` or ``'spawn'``) and the durable stores.
    ``'spawn'`` also reports the pool slot filled (``None`` if the pool was
    full; the caller's own pending flag at A3 is still cleared either way)
    and, when the parallel-table type matched and the trigger counter had
    reached 2, a ``'proximity'`` sub-result (the 00F828 call this same
    activation makes before the fill: ``'added'`` or ``'trigger'``, both
    recovered on their own merits).  ``'trigger'`` is a decline: the type
    matched but the counter had not yet reached 2 (real code, unwitnessed),
    the proximity search's own found entry used a selector outside 0/1/2,
    or the proximity table itself was full -- none witnessed by any
    recording.
    """
    if read(a1 + ACTIVE_FLAG, 1) == 0:
        return _paint(read, a3, d0, d1)
    cell, row = _cell_address(read, d0, d1)
    if read(cell & 0xFFFFFF, 1) != SOLID_CELL:
        return _paint(read, a3, d0, d1)
    return _spawn(read, a1, cell, row, a3, d0, d1)


# --- 00F828/00F86A: the proximity table (014084's own 'trigger' callee) -----
#
# A 40-entry table at ``PROXIMITY_TABLE``, keyed by the same grid-table
# offset ``0063FA``/``00FDB8``/``010CBC`` all derive from a world position
# (here reversed out of a grid *address*, A1, rather than computed from a
# position directly): ``00F86A`` searches it for an entry whose key matches
# and whose timer word is negative (a fresh, unconsumed entry); if it finds
# one it falls into a further caller-record dispatch and a timer decrement
# at ``00F8A2`` and returns past *both* stack frames at once (a deliberate
# double-return, not a bug) -- real ROM code, declined here as the
# ``'trigger'`` arm.  If no such entry exists, ``00F828`` itself (which
# called ``00F86A`` first) scans the same table again for a free slot
# (a negative key word) and adds one; a table with no free slot at all
# (``'pool-full'``) is real code too, but no recording has ever exercised
# it, so it stays declined alongside ``'trigger'``.
PROXIMITY_TABLE, PROXIMITY_COUNT, PROXIMITY_STRIDE = 0xFFFF0C70, 40, 6
PROXIMITY_COUNTER = 0xFFFFF1FA                     # word: how many entries have ever been added
PROXIMITY_FLAG = 0xFFFFEED7                        # byte: set (0xFF) whenever an entry is added


def _proximity_key(a1):
    """Both 00F828 and 00F86A derive the same (d4, d5) key from a grid-cell address (A1):
    the offset from ``GRID_TABLE``, split back into its column (d4, word) and row (d5, long)
    components -- the inverse of the ``column``/``row`` arithmetic ``grid.py`` computes forward.
    """
    offset = (a1 - GRID_TABLE) & 0xFFFFFFFF
    d5_full = (offset & 0x00FFFF80) >> 3                    # lsr.l #3: a long shift, the full 32-bit result
    d4 = ((offset & 0x7F) << 5) & 0xFFFF                     # lsl.w #5: a word shift
    return offset, d4, d5_full


def proximity_search(read, a1):
    """00F86A: the 40-entry search.  ``positions`` is one of 'miss'/'close'/'stale'/'trigger'
    per entry examined, in order; 'trigger' (a matching, still-negative-timer entry) stops the
    search early and is declined by the boundary.  Otherwise every entry is examined ('miss': the
    key's first word differs; 'close': it matches but the second word does not; 'stale': both
    match but the timer is not negative, i.e. already consumed) and the arm is ``'not-found'``.
    """
    offset, d4, d5 = _proximity_key(a1)
    d5_word = d5 & 0xFFFF
    positions = []
    for index in range(PROXIMITY_COUNT):
        base = (PROXIMITY_TABLE + PROXIMITY_STRIDE * index) & 0xFFFFFF
        if read(base, 2) != d4:
            positions.append('miss')
            continue
        if read(base + 2, 2) != d5_word:
            positions.append('close')
            continue
        if read(base + 4, 2) & 0x8000:
            positions.append('trigger')
            return {'arm': 'trigger', 'offset': offset, 'd4': d4, 'd5': d5, 'positions': positions,
                   'index': index}
        positions.append('stale')
    return {'arm': 'not-found', 'offset': offset, 'd4': d4, 'd5': d5, 'positions': positions, 'index': None}


TRIGGER_SELECTOR = 0xFFFFF1FC         # word: 0/1/2 selects which of conditions.py's own TRACKED slots
TRIGGER_BONUS_ID = 0xA                # that slot's active id, when it is this, adds a bonus decrement
TRIGGER_BONUS = 0x32
TRIGGER_FLOOR = -0xC8                 # 0xff38 signed: a decremented timer below this clears to 0 instead


def proximity_trigger(read, a2, entry_base):
    """00F8A2: the matching, still-fresh entry's own continuation (found by ``proximity_search``,
    the 'trigger' arm) -- a caller-record decrement of the SAME timer word ``proximity_search`` tested
    for negativity, gated by which of conditions.py's own TRACKED ids is currently selected
    (``TRIGGER_SELECTOR``).  All three checks execute regardless of which one matches (the ROM's own
    three independent cmpi/bne pairs are not mutually exclusive branches, just three redundant tests
    of the same word), so the cost is the same whichever of 0/1/2 is selected; a selector outside that
    range leaves the ROM's own d5 uninitialised and is declined as unwitnessed.
    """
    from .conditions import TRACKED
    selector = read(TRIGGER_SELECTOR, 2)
    if selector not in (0, 1, 2):
        return {'arm': 'unrecovered', 'selector': selector}
    active = read(TRACKED[selector] & 0xFFFFFF, 2)
    base_decrement = read((a2 + 8) & 0xFFFFFF, 2)
    bonus = active == TRIGGER_BONUS_ID
    decrement = (base_decrement + TRIGGER_BONUS) & 0xFFFF if bonus else base_decrement
    timer_address = (entry_base + 4) & 0xFFFFFF
    new_timer = (read(timer_address, 2) - decrement) & 0xFFFF
    cleared = _signed_word(new_timer) < TRIGGER_FLOOR
    final = 0 if cleared else new_timer
    return {'arm': 'trigger-decrement', 'selector': selector, 'active': active, 'bonus': bonus,
            'decrement': decrement, 'cleared': cleared, 'final': final,
            'stores': {timer_address: (final, 2)}}


def proximity_add(read, offset, d4, d5):
    """00F828's own scan (after 00F86A finds nothing): the first free slot (key word negative),
    filled with (d4, d5, -1) -- a fresh, unconsumed entry -- or 'pool-full' if none of the 40 is
    free (real ROM code, unwitnessed).  The key is recomputed from ``offset`` exactly as the ROM's
    own redundant second computation does (word ops on d4, long ops on d5, matching ``_proximity_key``).
    """
    positions = []
    for index in range(PROXIMITY_COUNT):
        base = (PROXIMITY_TABLE + PROXIMITY_STRIDE * index) & 0xFFFFFF
        if read(base, 2) & 0x8000:
            positions.append('free')
            counter_before = read(PROXIMITY_COUNTER & 0xFFFFFF, 2)
            stores = {base: (d4, 2), base + 2: (d5 & 0xFFFF, 2), base + 4: (0xFFFF, 2),
                     PROXIMITY_COUNTER & 0xFFFFFF: ((counter_before + 1) & 0xFFFF, 2),
                     PROXIMITY_FLAG & 0xFFFFFF: (0xFF, 1)}
            return {'arm': 'added', 'index': index, 'positions': positions, 'stores': stores,
                    'counter_before': counter_before}
        positions.append('occupied')
    return {'arm': 'pool-full', 'positions': positions}
