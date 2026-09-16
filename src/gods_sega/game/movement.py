"""The collision gate (ROM 010A14-010AAC), called 412 times / 600 frames from ``010200``.

Called with a state struct (A5: a phase word at ``+4``, cycled 0-7 and
occasionally driven back down from 8; a moving-state word at ``+0xA``), a
second record (A3, read-only, gating the deep collision search below) and
a position word (D0).  Every call refreshes a global word (``TAIL_BASE``,
always ``0x2010``) and builds a result in D2 from the phase (or, once the
phase exceeds 7, the literal 8) shifted and added to that global -- tagged
with bit 15 when the moving-state word is zero.

While a global gate word (``GLOBAL_GATE``) is nonzero, or the phase is
being walked back down from above 7, the call is done there: nothing else
happens.  Otherwise the phase advances (mod 8) and D0 is nudged by 4 (the
sign taken from the moving-state word) to compute a residue mod 32; a
nonzero residue ends the call the same way ('gated'), but a zero residue
calls ``010CBC`` (``grid.grid_cell_at``, a parameterised twin of
``0063FA``'s own grid computation) with the phase-adjusted D0 and the
caller's own D1 (never written), then reads three grid neighbours ahead of
that cell in the direction ``moving`` selects.  If the near or mid
neighbour is solid, or the far one is not, the moving-state word is
toggled ('collision-clear': the routine's own record of "am I blocked"
flips).  Otherwise (far neighbour solid, near and mid clear) a further
byte in A3 (``COLLISION_RECORD_GATE``) gates a deeper, unbounded grid
search this module does not model: zero on every occurrence any recording
witnesses ('collision-held': the tail runs with nothing else touched),
nonzero enters that search ('collision-deep' -- declined, unwitnessed).

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

from . import grid

PHASE = 0x4                          # A5 word: 0-7 cycles; readvanced (decremented) while it exceeds 7
MOVING_STATE = 0xA                   # A5 word: zero tags the D2 result with bit 15
GLOBAL_GATE = 0xFFFFEF4A             # word: nonzero holds the phase where it is for this call
TAIL_BASE = 0xFFFFEF88               # word: always refreshed to 0x2010
TAIL_BASE_VALUE = 0x2010
RESULT_TAG = 0x8000
RESIDUE_MASK = 0x1F
COLLISION_RECORD_GATE = 0x12         # A3 byte: zero on every witnessed occurrence (see module docstring)
# moving == 0: the previous-column neighbour, one and two rows up (bytes at A0-1, A0+0x7F, A0+0xFF).
# moving != 0: the next-column neighbour, one and two rows down (bytes at A0+1, A0+0x81, A0+0x101).
_COLLISION_OFFSETS_BACK = (-1, 0x7F, 0xFF)
_COLLISION_OFFSETS_FORWARD = (1, 0x81, 0x101)


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def collision_gate(read, state, a3, d0, d1):
    """What ``010A14`` does for state struct ``state`` (A5), record ``a3``, position ``d0``, ``d1``.

    Returns the arm (``'over'``: phase > 7, real ROM code but not witnessed
    by any recording; ``'held'``: the global gate is set; ``'gated'``: the
    phase advanced but the residue was nonzero; ``'collision-clear'``: the
    residue was zero and a near/mid/far grid test toggled the moving-state
    word; ``'collision-held'``: the same test found the far neighbour alone
    solid, but the deep-search gate was zero, so the tail runs untouched;
    ``'collision-deep'``: the deep-search gate was nonzero -- declined),
    the raw D2 tail value (before the final shift-and-add every arm
    shares), the new D0, and the durable stores.  The collision arms also
    return ``cell`` (``grid.grid_cell_at``'s own result, for the boundary's
    ASL flag bookkeeping) and ``moving_after`` (the moving-state word's
    value by the time the shared tail reads it).
    """
    stores = {TAIL_BASE & 0xFFFFFF: (TAIL_BASE_VALUE, 2)}
    phase = read(state + PHASE, 2)
    if _signed_word(phase) > 7:
        stores[(state + PHASE) & 0xFFFFFF] = ((phase - 1) & 0xFFFF, 2)
        return {'arm': 'over', 'tail_d2': 8, 'd0': d0 & 0xFFFF, 'stores': stores}
    if read(GLOBAL_GATE, 2) != 0:
        return {'arm': 'held', 'tail_d2': phase, 'd0': d0 & 0xFFFF, 'stores': stores}
    new_phase = (phase + 1) & 7
    stores[(state + PHASE) & 0xFFFFFF] = (new_phase, 2)
    moving = read(state + MOVING_STATE, 2)
    new_d0 = ((d0 + 4) if moving != 0 else (d0 - 4)) & 0xFFFF
    if new_d0 & RESIDUE_MASK:
        return {'arm': 'gated', 'tail_d2': new_phase, 'd0': new_d0, 'stores': stores}
    cell = grid.grid_cell_at(new_d0, d1)
    offsets = _COLLISION_OFFSETS_FORWARD if moving != 0 else _COLLISION_OFFSETS_BACK
    near, mid, far = (read((cell['address'] + offset) & 0xFFFFFF, 1) for offset in offsets)
    result = {'tail_d2': new_phase, 'd0': new_d0, 'stores': stores, 'cell': cell,
              'near': near, 'mid': mid, 'far': far}
    if near == 1 or mid == 1 or far != 1:
        stores[(state + MOVING_STATE) & 0xFFFFFF] = ((moving ^ 1) & 0xFFFF, 2)
        result['arm'], result['moving_after'] = 'collision-clear', moving ^ 1
        return result
    result['moving_after'] = moving
    if read((a3 + COLLISION_RECORD_GATE) & 0xFFFFFF, 1) != 0:
        result['arm'] = 'collision-deep'
        return result
    result['arm'] = 'collision-held'
    return result
