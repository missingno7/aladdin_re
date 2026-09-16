"""014A3C: a one-word draw from a wrapping work-RAM table, called 3,971 times / 34,904 frames.

Reads the word at a cursor (``RANDOM_CURSOR``) into a 256-entry table
(``RANDOM_TABLE``, work RAM: the table's own contents are whatever the game
last wrote there -- not a fixed ROM sequence, but every witnessed read is
reproduced exactly since the table lives in the machine's own RAM), then
advances the cursor by one word and wraps it to the table's own span.  No
branch: the table is read, not interpreted.  Used by the pickup check's own
found-effect composition (``game/pickups.py: pickup_check``) to jitter the
effect's spawn position on each axis.

Pure function of ``read(address, size)``; no cycles, CCR, stack or registers.
"""
from __future__ import annotations

RANDOM_CURSOR = 0xFFFFEEF0             # word: the table offset of the next draw
RANDOM_TABLE = 0xFFFFB97A              # work RAM, 256 words (512 bytes), the cursor wraps mod 0x200
RANDOM_TABLE_SPAN = 0x200


def next_random(read):
    """014A3C: draw the word at the cursor and advance it, wrapping every 256 entries."""
    cursor = read(RANDOM_CURSOR, 2)
    value = read((RANDOM_TABLE + cursor) & 0xFFFFFF, 2)
    new_cursor = (cursor + 2) & (RANDOM_TABLE_SPAN - 1)
    return {'value': value, 'stores': {RANDOM_CURSOR & 0xFFFFFF: (new_cursor, 2)}}
