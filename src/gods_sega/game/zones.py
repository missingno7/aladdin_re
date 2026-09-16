"""The zone check (ROM 00BCCE-00BD50), called 412-670 times / 600 frames from ``00BA8E``.

Called with a position (D0/D1, a word each) and a word (D2).  Builds a
box around the player's own world position (``GRID_X``/``GRID_Y``, the
same words ``0063FA``'s grid lookup reads) widened by fixed margins and,
on two specific levels, an extra bottom margin; the box is then grown
again by half of two further sizes (``HALF_WIDTH``/``HALF_HEIGHT``,
themselves halved again here).  When ``HOLD_FLAG``'s sign bit is set the
whole test is skipped (the ``'held'`` arm).  Otherwise the box test runs;
outside it (the ``'outside'`` arm) nothing else happens.  Inside it (the
``'inside'`` arm) a value derived from D2 is subtracted from a shared
cooldown word unless ``SUPPRESS_COOLDOWN`` is set, and D2 becomes -1
unless ``RESULT_FLAG`` is nonzero.

All eight registers the routine touches (D0-D7) are saved on entry and
restored from that same frame on every exit: the whole box arithmetic is
scratch, and the position/size words are never written back.  The only
durable effects are the two words above and D2's own final value.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

from .grid import GRID_X, GRID_Y

HOLD_FLAG = 0xFFFFEF3C                # word: bit 15 set skips the whole test (the 'held' arm)
LEVEL_NUMBER = 0xFFFFF192             # word: levels 0x12-0x13 get a widened box (see WIDE_LEVEL_*)
HALF_WIDTH, HALF_HEIGHT = 0xFFFFF382, 0xFFFFF384   # words, halved again here for the box's half-extents
COOLDOWN = 0xFFFFEF3E                 # word: decremented on the 'inside' arm unless SUPPRESS_COOLDOWN is set
SUPPRESS_COOLDOWN = 0xFFFFF1B6        # word: nonzero skips the COOLDOWN decrement
RESULT_FLAG = 0xFFFFEF14              # word: zero makes D2 become -1 on the 'inside' arm
X_NEAR_MARGIN, X_FAR_MARGIN = 0xA, 0xC      # near/far box edges relative to the player's X
Y_NEAR_MARGIN, Y_FAR_MARGIN = 0x8, 0x1E     # near/far box edges relative to the player's Y
WIDE_LEVEL_LOW, WIDE_LEVEL_HIGH, WIDE_Y_BONUS = 0x12, 0x13, 0x14


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _asr(value, shift):
    return _signed_word(value) >> shift


def zone_check(read, d0, d1, d2):
    """What ``00BCCE`` does for position ``(d0, d1)`` and ``d2``.

    Returns the arm (``'held'``, ``'outside'`` or ``'inside'``), which of
    the four box tests decided an ``'outside'`` result (``'x_near'``,
    ``'x_far'``, ``'y_near'``, ``'y_far'``; ``None`` otherwise), whether the
    box was widened, the two X-relevant values (the last ADD before the
    tests, needed for the CCR) and the durable stores.
    """
    if read(HOLD_FLAG, 2) & 0x8000:
        return {'arm': 'held', 'fail': None, 'wide': None, 'stores': {}}
    near_x = (read(GRID_X, 2) + X_NEAR_MARGIN) & 0xFFFF
    far_x = (near_x + X_FAR_MARGIN) & 0xFFFF
    near_y = (read(GRID_Y, 2) + Y_NEAR_MARGIN) & 0xFFFF
    far_y = (near_y + Y_FAR_MARGIN) & 0xFFFF
    level = read(LEVEL_NUMBER, 2)
    wide = WIDE_LEVEL_LOW <= _signed_word(level) <= WIDE_LEVEL_HIGH
    if wide:
        far_y = (far_y + WIDE_Y_BONUS) & 0xFFFF
    half_x = _asr(read(HALF_WIDTH, 2), 1)
    d0_eff = (d0 + half_x) & 0xFFFF
    near_x = (near_x - half_x) & 0xFFFF
    far_x_before_add, far_x = far_x, (far_x + half_x) & 0xFFFF
    half_y = _asr(read(HALF_HEIGHT, 2), 1)
    d1_eff = (d1 + half_y) & 0xFFFF
    near_y = (near_y - half_y) & 0xFFFF
    far_y_before_add, far_y = far_y, (far_y + half_y) & 0xFFFF

    def signed(v):
        return _signed_word(v)

    fail, stores = None, {}
    if signed(d0_eff) < signed(near_x):
        fail = 'x_near'
    elif signed(d0_eff) > signed(far_x):
        fail = 'x_far'
    elif signed(d1_eff) < signed(near_y):
        fail = 'y_near'
    elif signed(d1_eff) > signed(far_y):
        fail = 'y_far'
    x_operands = (far_y_before_add, half_y)     # the last ADD before any test: add.w d3,d7
    tests = {'x_near': (d0_eff, near_x), 'x_far': (d0_eff, far_x), 'y_near': (d1_eff, near_y), 'y_far': (d1_eff, far_y)}
    if fail:
        return {'arm': 'outside', 'fail': fail, 'wide': wide, 'x_operands': x_operands, 'stores': stores,
                'test_operands': tests[fail]}
    result = _inside(read, d2, x_operands)
    result['test_operands'] = tests['y_far']
    return result


def _inside(read, d2, x_operands):
    incremented = (d2 + 1) & 0xFFFF          # move.w d2,d3; addq.w #1,d3 (word-wrapped, then signed for the shift)
    shifted = _asr(incremented, 5) & 0xFFFF  # asr.w #5,d3
    scale = (shifted + 5) & 0xFFFF           # addq.w #5,d3
    stores = {}
    suppressed = read(SUPPRESS_COOLDOWN, 2) != 0
    cooldown_before = read(COOLDOWN, 2)
    if not suppressed:
        stores[COOLDOWN & 0xFFFFFF] = ((cooldown_before - scale) & 0xFFFF, 2)
    result_flag = read(RESULT_FLAG, 2)
    new_d2 = 0xFFFFFFFF if result_flag == 0 else None
    return {'arm': 'inside', 'fail': None, 'wide': None, 'x_operands': x_operands, 'stores': stores,
            'shifted': shifted, 'scale': scale, 'suppressed': suppressed, 'cooldown_before': cooldown_before,
            'result_flag': result_flag, 'new_d2': new_d2}
