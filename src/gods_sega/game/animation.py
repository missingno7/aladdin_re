"""The animation step (ROM 00FE08-00FE5A): once per active solid per tick, from ``00FBB6``, before ``00FDB8``.

Called with the live record (A1, ``FF4AAE`` + 0x18 per solid: world x/y at
``+0``/``+2``, a byte at ``+4``, the byte this routine reads at ``+5``, four
longs from ``+6``) and the same definition (A2, ``FF65A2``) ``00FDB8`` and
``00FC8E`` read, at a field of their own (``+5``) neither of those two
touches.  Every call refreshes the shared frame-budget word ``FRAME_BUDGET``
from the definition's own field, and leaves ``A3`` at the live record's
``+6`` regardless of arm.

When the live record's own byte at ``+5`` is negative the routine returns
immediately (the ``'idle'`` arm: no other durable effect).  Otherwise (the
``'moving'`` arm) it calls ``00FFF0``: a resumable Bresenham-style line
walk that stores its own continuation address back into the record's own
longs (``move.l #$10022,(a3)+`` and similar, at ``00FE08``'s neighbours) so
a later tick can resume mid-line, and afterwards a per-object-type
dispatch through a jump table indexed by a state byte (``00FEC0``/
``00FF54``, four handlers each) that is not recovered.  Both are a
script/coroutine engine, not a leaf: the ``'moving'`` arm is declined here,
not because no recording enters it (it is common), but because the boundary
cannot reproduce a call into unrecovered code exactly.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

LIVE_MOVING_FLAG = 0x5           # live record byte: negative selects the 'idle' (immediate-return) arm
DEFINITION_INDEX = 0x5           # definition byte: refreshes FRAME_BUDGET on every call, either arm
FRAME_BUDGET = 0xFFFFF1FE        # word: the shared per-tick work budget 00FFF0's coroutine counts down


def _signed_byte(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def animation_step(read, record, definition):
    """What ``00FE08`` does for one active solid's live ``record`` (A1) and ``definition`` (A2).

    Returns the arm (``'idle'`` or ``'moving'``), the new ``FRAME_BUDGET``
    value (ext.w of the definition's own byte, plus one -- stored on both
    arms) and the durable stores.  ``'moving'`` is never admitted by the
    boundary: it calls into the unrecovered coroutine and state dispatch at
    ``00FFF0``.
    """
    before = _signed_byte(read(definition + DEFINITION_INDEX, 1)) & 0xFFFF   # the value addq.w #1 adds to (sets X/C)
    budget = (before + 1) & 0xFFFF
    stores = {FRAME_BUDGET & 0xFFFFFF: (budget, 2)}
    moving = not (read(record + LIVE_MOVING_FLAG, 1) & 0x80)
    return {'arm': 'moving' if moving else 'idle', 'budget': budget, 'budget_before': before, 'stores': stores}
