"""The animation step (ROM 00FE08-00FE8C): once per active solid per tick, from ``00FBB6``, before ``00FDB8``.

Called with the live record (A1, ``FF4AAE`` + 0x18 per solid: world x/y at
``+0``/``+2``, a byte at ``+4``, the byte this routine reads at ``+5``, four
longs from ``+6``) and the same definition (A2, ``FF65A2``) ``00FDB8`` and
``00FC8E`` read, at a field of their own (``+5``) neither of those two
touches.  Every call refreshes the shared frame-budget word ``FRAME_BUDGET``
from the definition's own field, and leaves ``A3`` pointing somewhere in the
live record's own walker sub-record regardless of arm (at ``+6`` for the
idle arm, further along after a moving call runs).

When the live record's own byte at ``+5`` is negative the routine returns
immediately (the ``'idle'`` arm: no other durable effect).  Otherwise (the
``'moving'`` arm) it calls ``00FFF0``: the walker's own object-copy resume
(``game/walker.py``), stepping the walk in the record's own ``+6`` sub-record
by the budget just refreshed.  The walker's y result is stored back as the
record's own ``x``/``y`` (``+0``/``+2``).  If the walk did not finish this
call (the final counter still non-negative -- ``'moving-continue'``) that is
everything: the routine returns.  If it finished (the final counter negative
-- the SAME byte at ``+5`` that gated the ``'moving'`` arm is read again, as
a waypoint slot: ``(slot - 1) * 4`` indexes a long in the definition's own
table at ``+6``, loaded over the record's ``x``/``y`` as the next waypoint.
A byte at ``+4`` (a remaining-waypoint count) then decides: more than one
left, this call is done and the slot byte is reset to -1 (``'moving-complete'``,
waiting for something else to arm a fresh slot); one or none left, the
routine falls into a cold start of a fresh walk toward the next slot -- a
per-object-type dispatch through a state byte at ``+4`` into one of two
four-entry jump tables (``00FEC0``/``00FF54``) that no recording ever enters
(screened over all eight recordings, 16 Sep), then ``walker.start`` /
``walker.run`` again.  ``'moving-coldstart'`` is declined for that reason,
not because the walk or the waypoint arithmetic themselves are unbounded.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers -- except for calling into ``game/walker.py``'s own
pure step function, the shape ``00BA8E``'s composition over its own callees
proved.
"""
from __future__ import annotations

from . import walker

LIVE_MOVING_FLAG = 0x5           # live record byte: negative selects the 'idle' (immediate-return) arm; else a waypoint slot
DEFINITION_INDEX = 0x5           # definition byte: refreshes FRAME_BUDGET on every call, either arm
FRAME_BUDGET = 0xFFFFF1FE        # word: the shared per-tick work budget the walker counts down
WALKER_RECORD_OFFSET = 0x6       # the walker's own 18-byte sub-record lives at the live record's +6
REMAINING_WAYPOINTS = 0x4        # live record byte: compared to 1 on completion; <=1 falls to the (unwitnessed) cold start


def _signed_byte(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def animation_step(read, record, definition):
    """What ``00FE08`` does for one active solid's live ``record`` (A1) and ``definition`` (A2).

    Returns the arm (``'idle'``, ``'moving-continue'``, ``'moving-complete'``
    or ``'moving-coldstart'``), the new ``FRAME_BUDGET`` value (ext.w of the
    definition's own byte, plus one -- stored on every arm) and the durable
    stores.  ``'moving-coldstart'`` is never admitted by the boundary: no
    recording enters it, so the per-object-type waypoint dispatch it would
    need (``00FEC0``/``00FF54``) is not recovered.
    """
    before = _signed_byte(read(definition + DEFINITION_INDEX, 1)) & 0xFFFF   # the value addq.w #1 adds to (sets X/C)
    budget = (before + 1) & 0xFFFF
    stores = {FRAME_BUDGET & 0xFFFFFF: (budget, 2)}
    moving = not (read(record + LIVE_MOVING_FLAG, 1) & 0x80)
    if not moving:
        return {'arm': 'idle', 'budget': budget, 'budget_before': before, 'stores': stores}
    if budget == 0:
        return {'arm': 'moving-zero-budget', 'budget': budget, 'budget_before': before, 'stores': stores}
    walker_record = record + WALKER_RECORD_OFFSET
    walk = walker.load(read, walker_record, 'object')
    if walk is None:
        return {'arm': 'moving-unrecovered-record', 'budget': budget, 'budget_before': before, 'stores': stores}
    after, left, steps, completed = walker.run(walk, budget, 'object')
    stores[FRAME_BUDGET & 0xFFFFFF] = (left, 2)             # subq.w #1,$f1fe.w inside the walk: the budget it leaves
    stores.update(walker.stores(after, walker_record, 'object'))
    stores[record] = (after.x, 2)
    stores[record + 2] = (after.y, 2)
    result = {'budget': budget, 'budget_before': before, 'stores': stores, 'walk': walk, 'after': after,
              'left': left, 'steps': steps}
    if not (after.counter & 0x8000):                       # tst.w d7; bpl: the walk has not finished as of this call
        result['arm'] = 'moving-continue'
        return result
    # Completed: the SAME byte that gated 'moving' is re-read as a waypoint slot (move.b $5(a1),d3; ext.w;
    # subq.w #1,d3; add.w d3,d3 twice -- a signed word index, *4, into the definition's own table at +6).
    slot = _signed_byte(read(record + LIVE_MOVING_FLAG, 1))
    index = _signed_word(((slot - 1) * 4) & 0xFFFF)
    waypoint_address = (definition + 6 + index) & 0xFFFFFFFF
    waypoint = read(waypoint_address, 4)
    del stores[record + 2]                                  # move.l $6(a2,d3.w),(a1) overwrites the x/y just stored above
    stores[record] = (waypoint, 4)
    remaining = read(record + REMAINING_WAYPOINTS, 1)
    if _signed_byte(remaining) <= 1:
        result['arm'] = 'moving-coldstart'                  # calls the unrecovered 00FEC0/00FF54 dispatch: not witnessed
        return result
    stores[record + 5] = (0xFF, 1)
    result['arm'] = 'moving-complete'
    result['slot'] = slot
    result['index'] = index
    return result
