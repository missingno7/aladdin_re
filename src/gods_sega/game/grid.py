"""The grid cell lookup (ROM 0063FA-006412): called from three sites (006468, 006FFE, 007282).

A pure address computation over two fixed words (`GRID_X`, `GRID_Y`): no
loop, no branch, no store.  It returns a pointer into a work-RAM table
(`GRID_TABLE`; the register value 0xFFFF885E resolves to RAM `FF885E`,
not a ROM address) also indexed -- by a different transform -- from
`00FDB8` and (parameterised on X/Y registers instead of the fixed words
here) `010CBC`; what the table holds is not known, but it is live state,
not ROM data.  The names are what the arithmetic supports, not more.
"""
from __future__ import annotations

GRID_X, GRID_Y = 0xFFF18C, 0xFFF18E                 # words: the position the grid cell is computed from
# lea.l $885e.w,a0 is the 68000's absolute-short mode: the 16-bit immediate is sign-extended, so the
# literal register value is 0xFFFF885E -- work RAM FF885E, not a ROM address -- shared with 00FDB8's
# and 010CBC's own (differently transformed) lookups, whatever the table holds.
GRID_TABLE = 0xFFFF885E
GRID_Y_MASK = 0xFFF0                                # the low four bits of Y are dropped before the row shift


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def grid_cell(read):
    """What ``0063FA`` computes: the table address for the current grid cell.

    Returns the address (the literal 32-bit register value ``adda.w``
    leaves, not a resolved memory location -- the routine never
    dereferences it), the pre-shift row word (for the boundary's ASL flag
    bookkeeping) and the two words the routine leaves in D0 (X asr 5) and
    D1 (the shifted row).
    """
    x, y = read(GRID_X, 2), read(GRID_Y, 2)
    column = (_signed_word(x) >> 5) & 0xFFFF        # asr.w #5: arithmetic, floor toward -inf like the 68000
    row_source = y & GRID_Y_MASK
    row = (row_source << 3) & 0xFFFF                 # asl.w #3
    address = (GRID_TABLE + _signed_word(column) + _signed_word(row)) & 0xFFFFFFFF
    return {'address': address, 'd0': column, 'd1': row, 'row_source': row_source}


# What 00FDB8 stamps: a solid's footprint.  The grid is the level's map of
# solid cells, 32 pixels wide and 16 tall, 128 bytes per row (so 4,096
# pixels of level width); a cell holds 1 while a solid stands on it.  The
# 25 solids (definitions at FF65A2, 0x1C bytes each; live records at
# FF4AAE, 0x18 bytes each -- the loop at 00FBB6) are stamped every game tick
# from their world position, and every cell's previous byte goes to an undo
# list (FF4982, 50 six-byte entries: the cell's address, 0, the old byte)
# that 00FAF4 replays before the next tick's stamps.  0063FA and 010CBC read
# the same grid for the player and the movers.
FOOTPRINT_GRID = GRID_TABLE
GRID_ROW_BYTES = 0x80                                 # 16 pixels of height per row
CELL_WIDTH_SHIFT, CELL_HEIGHT_MASK = 5, 0xFFF0        # 32-pixel columns, 16-pixel rows
STAMP_X_BIAS, STAMP_Y_BIAS = 0x10, 0x08               # the position is the solid's centre-ish; cells are taken from here
FOOTPRINT_WIDTH, FOOTPRINT_HEIGHT = 0x1A, 0x1B        # definition bytes: cells minus one; width's bit 7 = no footprint
FOOTPRINT_WIDTH_MASK, NO_FOOTPRINT = 0x07, 0x80
UNDO_ENTRY = 6                                        # long cell address, a zero byte, the cell's old byte
SOLID = 1


def _signed_byte(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def stamp_footprint(read, x, y, definition, cursor):
    """What ``00FDB8`` does for a solid at world ``(x, y)`` with ``definition`` (A2) and the undo cursor (A5).

    Returns the arm (``'none'`` when the definition's width byte has bit 7
    set, ``'stamp'`` otherwise), the rows and cells per row, the durable
    stores as ``{address: (value, size)}`` (each cell set to ``SOLID`` and
    its undo entry), the grid address the first row starts at, the row
    start after the last row (what A0 holds at the exit), the undo cursor
    after the last entry, and the pre-shift row word the boundary needs
    for the X flag.  ``x``/``y`` are words.  A negative height byte would
    make the row count wrap on the 68000 (``dbra``): it is reported so the
    boundary can decline it.
    """
    if read(definition + FOOTPRINT_WIDTH, 1) & NO_FOOTPRINT:
        return {'arm': 'none', 'rows': 0, 'cells': 0, 'stores': {}}
    column = (_signed_word((x + STAMP_X_BIAS) & 0xFFFF) >> CELL_WIDTH_SHIFT) & 0xFFFF
    row_source = ((y + STAMP_Y_BIAS) & 0xFFFF) & CELL_HEIGHT_MASK
    row = (row_source << 3) & 0xFFFF
    first_row = (FOOTPRINT_GRID + _signed_word(column) + _signed_word(row)) & 0xFFFFFFFF
    height = _signed_byte(read(definition + FOOTPRINT_HEIGHT, 1))
    cells = (read(definition + FOOTPRINT_WIDTH, 1) & FOOTPRINT_WIDTH_MASK) + 1
    rows = height + 1
    stores, undo = {}, cursor
    row_start = first_row
    for _ in range(max(rows, 0)):
        for index in range(cells):
            cell = (row_start + index) & 0xFFFFFFFF
            stores[undo & 0xFFFFFF] = (cell, 4)
            stores[(undo + 4) & 0xFFFFFF] = (0, 1)
            stores[(undo + 5) & 0xFFFFFF] = (read(cell & 0xFFFFFF, 1), 1)
            stores[cell & 0xFFFFFF] = (SOLID, 1)
            undo = (undo + UNDO_ENTRY) & 0xFFFFFFFF
        row_start = (row_start + GRID_ROW_BYTES) & 0xFFFFFFFF
    return {'arm': 'stamp', 'rows': rows, 'cells': cells, 'height': height, 'stores': stores,
            'first_row': first_row, 'row_after': row_start, 'cursor': undo,
            'column': column, 'row': row, 'row_source': row_source}
