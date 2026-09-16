"""The work-table reset (ROM 004150-0041EE): once per game tick from the main loop (001F40), like the camera.

A fixed-size work table (`FFBB7A`-`FFC1B9`, 1,600 bytes, below the level's
tile-clip data at `FFC1BA`) is unconditionally rewritten every tick with one
repeating fill byte: zero, or -- when `RESET_FLAG` is not negative -- 0xFE,
in which case a second word (`POISON_FLAG`) is also cleared.  The table's own
purpose is not known; the names are what the arithmetic supports, not more.
"""
from __future__ import annotations

TABLE_END, TABLE_START = 0xFFBB7A, 0xFFC1BA        # the table spans [TABLE_END, TABLE_START), falling addresses
RESET_FLAG = 0xFFF210                              # word: negative selects the plain (zero) reset
POISON_FLAG = 0xFFEF5C                             # word: cleared only on the non-negative (poison-fill) arm
ZERO_FILL, POISON_FILL = 0x00, 0xFE


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def reset_table(read_word):
    """One tick's table reset.  ``read_word(address)`` returns an unsigned word.

    Returns the fill byte, whether ``POISON_FLAG`` is also cleared, and every
    store: the whole table plus ``POISON_FLAG`` when it applies.
    """
    negative = _signed_word(read_word(RESET_FLAG)) < 0
    fill = ZERO_FILL if negative else POISON_FILL
    stores = {address: fill for address in range(TABLE_END, TABLE_START)}
    if not negative:
        stores[POISON_FLAG] = 0
        stores[POISON_FLAG + 1] = 0
    return {'fill': fill, 'poisoned': not negative, 'stores': stores}
