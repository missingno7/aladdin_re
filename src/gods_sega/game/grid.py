"""The grid cell lookup (ROM 0063FA-006412): called from three sites (006468, 006FFE, 007282).

A pure address computation over two fixed words (`GRID_X`, `GRID_Y`): no
loop, no branch, no store.  It returns a pointer into a ROM table
(`GRID_TABLE`, 0x00885E) also indexed -- by a different transform -- from
`00FDB8`; what the table holds is not known.  The names are what the
arithmetic supports, not more.
"""
from __future__ import annotations

GRID_X, GRID_Y = 0xFFF18C, 0xFFF18E                 # words: the position the grid cell is computed from
# lea.l $885e.w,a0 is the 68000's absolute-short mode: the 16-bit immediate is sign-extended, so the
# literal register value is 0xFFFF885E, not 0x00885E -- the table is shared with 00FDB8's own
# (differently transformed) lookup, whatever it is.
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
