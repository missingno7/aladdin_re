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


def _spawn(read, cell, row, a3, d0, d1):
    type_byte = read((cell + TYPE_TABLE_OFFSET) & 0xFFFFFF, 1)
    counter = _signed_word(read(TRIGGER_COUNTER, 2))
    if type_byte == TRIGGER_TYPE and counter >= 2:
        return {'arm': 'trigger', 'stores': {}}
    slot = None
    for index in range(POOL_COUNT):
        entry = POOL_BASE + POOL_STRIDE * index
        if _signed_word(read(entry, 2)) < 0:
            slot = entry
            break
    stores = {SOUND_COMMAND & 0xFFFFFF: (SOUND_REQUEST, 2), a3 & 0xFFFFFF: (0, 2)}
    result = {'arm': 'spawn', 'slot': slot, 'stores': stores}
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


def hazard_tick(read, a1, a3, d0, d1):
    """What ``014084`` does for object ``a1``, the secondary record ``a3`` and position ``(d0, d1)``.

    Returns the arm (``'paint'``, ``'spawn'`` or ``'trigger'`` -- the last
    calls an unrecovered routine and is declined) and the durable stores.
    ``'spawn'`` also reports the pool slot filled, or ``None`` if the pool
    was full (the caller's own pending flag at A3 is still cleared either
    way).
    """
    if read(a1 + ACTIVE_FLAG, 1) == 0:
        return _paint(read, a3, d0, d1)
    cell, row = _cell_address(read, d0, d1)
    if read(cell & 0xFFFFFF, 1) != SOLID_CELL:
        return _paint(read, a3, d0, d1)
    return _spawn(read, cell, row, a3, d0, d1)
