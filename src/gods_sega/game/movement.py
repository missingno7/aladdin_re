"""The collision gate (ROM 010A14-010AAC), called 412 times / 600 frames from ``010200``.

Called with a state struct (A5: a phase word at ``+4``, cycled 0-7 and
occasionally driven back down from 8; a moving-state word at ``+0xA``) and
a position word (D0).  Every call refreshes a global word (``TAIL_BASE``,
always ``0x2010``) and builds a result in D2 from the phase (or, once the
phase exceeds 7, the literal 8) shifted and added to that global -- tagged
with bit 15 when the moving-state word is zero.

While a global gate word (``GLOBAL_GATE``) is nonzero, or the phase is
being walked back down from above 7, the call is done there: nothing else
happens.  Otherwise the phase advances (mod 8) and D0 is nudged by 4 (the
sign taken from the moving-state word) to compute a residue mod 32; a
nonzero residue ends the call the same way, but a zero residue calls
``010CBC`` (a parameterised twin of ``0063FA``'s own grid computation) and
dereferences the level grid the player and the movers consult (``0063FA``,
``010CBC``) through a further three-way check this module does not model.
That arm -- ``'collision'`` -- is declined: A3, the collision record it
reads, and the grid checks themselves are outside what this leaf covers.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

PHASE = 0x4                          # A5 word: 0-7 cycles; readvanced (decremented) while it exceeds 7
MOVING_STATE = 0xA                   # A5 word: zero tags the D2 result with bit 15
GLOBAL_GATE = 0xFFFFEF4A             # word: nonzero holds the phase where it is for this call
TAIL_BASE = 0xFFFFEF88               # word: always refreshed to 0x2010
TAIL_BASE_VALUE = 0x2010
RESULT_TAG = 0x8000
RESIDUE_MASK = 0x1F


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def collision_gate(read, state, d0):
    """What ``010A14`` does for state struct ``state`` (A5) and position ``d0``.

    Returns the arm (``'over'``: phase > 7, real ROM code but not witnessed
    by any recording; ``'held'``: the global gate is set; ``'gated'``: the
    phase advanced but the residue was nonzero; ``'collision'``: the
    residue was zero -- declined), the raw D2 tail value (before the final
    shift-and-add every arm shares), the new D0, and the durable stores.
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
    return {'arm': 'collision', 'tail_d2': new_phase, 'd0': new_d0, 'stores': stores}
