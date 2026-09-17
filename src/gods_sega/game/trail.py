"""The trail check (ROM 0044C0-00454E, with its own box-test helper 004550): event kind 6, raised
from the tile trigger scan's own found-tile dispatch (``EVENT_HANDLERS[5]``, ``game.player``).

Reads the player's own current position (``player.POSITION_X``/``POSITION_Y``) and tests it, in
order, against up to six recently-recorded positions (``TRAIL_HISTORY``, a 6-slot ring at
``0xFFFFF272``, 4 bytes each -- a long per slot, x then y): a 0x80-wide box centred on each recorded
slot (``TRAIL_BOX_MARGIN`` either side).  The current position is copied into a scratch long
(``TRAIL_LAST_POSITION``, ``0xFFFFF1EC``) unconditionally, on every call, before the scan starts.

The first slot whose box contains the current position stops the scan immediately ('found') -- no
further RAM effect.  If none of the (up to) six slots match, real ROM code this module does not
model runs instead: the ring is shifted (the oldest slot dropped, the current position inserted at
the front), a counter (``TRAIL_COUNTER``, ``0xFFFFF270``) is incremented, and a call into ``007B4C``
follows (a tracked object record's own state field compared against the fresh counter -- real,
further code, not characterised here).  On the eight recordings, 'found' is the overwhelming
majority (891 of 903 occurrences on the main history alone, `--classifier entry`); only the
exhaustion arm ('exhausted') declines.
"""
from __future__ import annotations

TRAIL_COUNTER = 0xFFFFF270              # word: incremented only when all six slots miss
TRAIL_HISTORY = 0xFFFFF272              # six 4-byte slots (x word, y word), a position ring
TRAIL_HISTORY_STRIDE = 4
TRAIL_HISTORY_SLOTS = 6
TRAIL_LAST_POSITION = 0xFFFFF1EC        # long: a scratch copy of the current position, every call
TRAIL_BOX_MARGIN = 0x40                 # the box half-extent tested around each recorded slot


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _slot_overlap(read, slot_index, x, y):
    """004550: does the box (slot +/- TRAIL_BOX_MARGIN) contain (x, y)? A caller-record-free leaf --
    every input is one of the six fixed ``TRAIL_HISTORY`` slots. Returns the slot's own (sx, sy) and
    ``fail_at`` (the 0-based index, in ROM order -- near x, near y, far x, far y -- of the first
    comparison that fails, or ``None`` when all four pass: the boundary's own cost is a formula in
    this, each of the four chained ``cmp.w``/``Bcc`` pairs costing the same regardless of position)."""
    address = (TRAIL_HISTORY + TRAIL_HISTORY_STRIDE * slot_index) & 0xFFFFFFFF
    sx = read(address & 0xFFFFFF, 2)
    sy = read((address + 2) & 0xFFFFFF, 2)
    near_x, near_y = (sx - TRAIL_BOX_MARGIN) & 0xFFFF, (sy - TRAIL_BOX_MARGIN) & 0xFFFF
    far_x, far_y = (sx + TRAIL_BOX_MARGIN) & 0xFFFF, (sy + TRAIL_BOX_MARGIN) & 0xFFFF
    # cmp.w d0,d2; bgt (near_x > x -> fail); cmp.w d1,d3; bgt (near_y > y -> fail);
    # cmp.w d0,d4; blt (far_x < x -> fail); cmp.w d1,d5; blt (far_y < y -> fail)
    tests = (_signed_word(near_x) > _signed_word(x), _signed_word(near_y) > _signed_word(y),
            _signed_word(far_x) < _signed_word(x), _signed_word(far_y) < _signed_word(y))
    for fail_at, failed in enumerate(tests):
        if failed:
            return False, sx, sy, fail_at
    return True, sx, sy, None


def trail_check(read, x, y):
    """0044C0: the current position against up to six recorded slots, in order.

    Returns ``{'arm': 'found', 'slot': i, 'checks': [...]}`` on the first slot whose box contains
    (x, y) -- ``checks`` lists every slot tried, each ``{'index', 'sx', 'sy', 'hit', 'fail_at'}`` --
    or ``{'arm': 'exhausted', 'checks': [...]}`` when none of the six do (real ROM code beyond this
    point: the ring shift, the counter, the ``007B4C`` call -- not modelled)."""
    checks = []
    for index in range(TRAIL_HISTORY_SLOTS):
        hit, sx, sy, fail_at = _slot_overlap(read, index, x, y)
        checks.append({'index': index, 'sx': sx, 'sy': sy, 'hit': hit, 'fail_at': fail_at})
        if hit:
            return {'arm': 'found', 'slot': index, 'checks': checks}
    return {'arm': 'exhausted', 'checks': checks}
