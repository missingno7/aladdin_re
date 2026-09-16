"""The solid drawer (ROM 00FC8E-00FE06): one sprite-list append per active solid, once per game tick from ``00FC08``.

Called with a solid's world position (``d0``/``d1``, camera-relative once
subtracted here) and the same definition pointer (``a2``) that ``00FDB8``
(``game/grid.py: stamp_footprint``) reads: the type id at ``+4``, the width
and height bytes at ``+0x1A``/``+0x1B``.  The type id is looked up in a
work-RAM table of ``(type id, tile index)`` words at a pointer held in
``SOLID_TILE_TABLE`` (a per-level table, in ROM once resolved, terminated by
a zero word); a found entry with its high byte's sign bit set means the
tiles are not in the table at all but uploaded fresh by an inline VDP block
(``00FD28``-``00FDB4``) -- an arm no recording enters, so the boundary
declines it.  Otherwise the byte pair (rows, cells: the same fields and the
same ``+1`` dbra convention footprint's grid stamp uses) is walked row by
row, column by column; each cell in the 352x224 screen box before the
common per-frame camera subtraction gets one four-word hardware sprite
record appended to the same list ``game/sprites.py``'s emitters use
(``LIST_HEAD``, ``LIST_LAST``, ``LIST_COUNT``, ``RECORD_SIZE``); an
off-screen cell is skipped (no record, no count) but still costs a loop
trip.  Every cell of the grid shares the same tile index -- the solids
this can draw are a single repeating tile, not a per-cell mosaic.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

from .sprites import CAMERA_X, CAMERA_Y, LIST_COUNT, LIST_HEAD, LIST_LAST, RECORD_SIZE, SCREEN_MARGIN, \
    SCREEN_X_LIMIT, SCREEN_Y_LIMIT
from .grid import FOOTPRINT_HEIGHT, FOOTPRINT_WIDTH, FOOTPRINT_WIDTH_MASK

SOLID_TYPE = 0x4                                    # definition byte: the type id the tile table is keyed on
SOLID_TILE_TABLE = 0xFFFFF2D6                        # long: a pointer (itself RAM) to the (id, tile index) word table
SOLID_TILE_TABLE_MAX_SCAN = 16                       # the verified domain: every recording matches within 3 entries
UPLOAD_TILE_BIT = 0x8000                             # a found entry with this bit set: the inline VDP upload arm
ROW_HEIGHT, COLUMN_WIDTH = 0x10, 0x20                # 16 and 32 screen pixels between successive cells
Y_MARGIN = 0x10                                      # the y off-screen test's own margin (the x test uses SCREEN_MARGIN)
POSITION_BIAS = 0x80                                 # the fixed sprite-coordinate offset added to both x and y
CELL_ATTRIBUTE = 0xD00                               # the fixed size/priority code every solid cell's record carries


def _signed_byte(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def draw_solid(read, x, y, definition):
    """What ``00FC8E`` does for one active solid at world ``(x, y)`` with ``definition`` (A2).

    Returns the arm (``'upload'`` when the table entry's tile index has its
    sign bit set -- unwitnessed, the boundary declines it; ``'sprite'``
    otherwise), how many table entries the scan tested, the tile index and
    the rows/cells (``None`` for ``'upload'``), the durable stores, how many
    cells were actually visible (drawn), and the last row's and last
    column's screen position before the ``POSITION_BIAS`` add -- the
    boundary needs both for the CCR (the last flag-setting instruction) and
    for the transient per-cell stack scratch, which nothing clears once the
    loop's last iteration pops it.  A negative height byte is reported
    (``height`` < 0) rather than looped over: like ``stamp_footprint``, the
    68000's ``dbra`` would wrap it into a huge count.
    """
    type_id = read(definition + SOLID_TYPE, 1) & 0xFF
    pointer = read(SOLID_TILE_TABLE, 4) & 0xFFFFFF
    entry, scanned = 0, 0
    address = pointer
    for _ in range(SOLID_TILE_TABLE_MAX_SCAN):
        entry = read(address, 2)
        scanned += 1
        address = (address + 2) & 0xFFFFFF
        if (entry & 0xFF) == type_id:
            break
        if entry == 0:
            break
    else:
        return {'arm': 'unbounded', 'scanned': scanned, 'stores': {}}
    matched = (entry & 0xFF) == type_id
    if not matched:
        return {'arm': 'unmatched', 'scanned': scanned, 'matched': False, 'stores': {}}
    if entry & UPLOAD_TILE_BIT:
        return {'arm': 'upload', 'scanned': scanned, 'matched': True, 'stores': {}}
    tile = (entry >> 8) & 0xFF
    screen_x = (x - read(CAMERA_X, 2)) & 0xFFFF
    screen_y = (y - read(CAMERA_Y, 2)) & 0xFFFF
    height = _signed_byte(read(definition + FOOTPRINT_HEIGHT, 1))
    if height < 0:
        return {'arm': 'wrap', 'scanned': scanned, 'matched': True, 'stores': {}, 'height': height}
    rows = height + 1
    cells = (read(definition + FOOTPRINT_WIDTH, 1) & FOOTPRINT_WIDTH_MASK) + 1
    head = read(LIST_HEAD, 4)                        # kept sign-extended (0xFFFFxxxx), like the other emitters' pointers
    record_full = head
    count = read(LIST_COUNT, 2)
    stores, visible, x_skips, y_skips = {}, 0, 0, 0
    last_row_y = last_col_x = 0
    for row in range(rows):
        row_y = (screen_y + ROW_HEIGHT * row) & 0xFFFF
        col_x = screen_x
        for _ in range(cells):
            last_row_y, last_col_x = row_y, col_x
            if ((col_x + SCREEN_MARGIN) & 0xFFFF) > SCREEN_X_LIMIT:
                x_skips += 1
            elif ((row_y + Y_MARGIN) & 0xFFFF) > SCREEN_Y_LIMIT:
                y_skips += 1
            else:
                record = record_full & 0xFFFFFF
                stores[LIST_LAST] = (record_full, 4)
                stores[record] = ((row_y + POSITION_BIAS) & 0xFFFF, 2)
                stores[record + 2] = ((count | CELL_ATTRIBUTE) & 0xFFFF, 2)
                stores[record + 4] = (tile, 2)
                stores[record + 6] = ((col_x + POSITION_BIAS) & 0xFFFF, 2)
                record_full = (record_full + RECORD_SIZE) & 0xFFFFFFFF
                count = (count + 1) & 0xFFFF
                stores[LIST_COUNT] = (count, 2)
                visible += 1
            col_x = (col_x + COLUMN_WIDTH) & 0xFFFF
    final_head = record_full
    stores[LIST_HEAD] = (final_head, 4)              # 00FD1E stores it unconditionally, even when visible == 0
    return {'arm': 'sprite', 'scanned': scanned, 'matched': True, 'tile': tile, 'rows': rows, 'cells': cells,
            'stores': stores, 'visible': visible, 'x_skips': x_skips, 'y_skips': y_skips, 'final_head': final_head,
            'last_row_y': last_row_y, 'last_col_x': last_col_x}
