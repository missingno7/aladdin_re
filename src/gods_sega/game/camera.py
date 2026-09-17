"""The camera follow step (ROM 002806-002850): once per game tick from the main loop (001F40).

The camera's x eases toward the follow point by four units per tick; its y
snaps to the follow point's y.  The halved values, clamped, are what the
scroll pipeline reads.  Addresses are the game's; the names are what the
arithmetic says they are, not more.
"""
from __future__ import annotations

FOLLOW_X, FOLLOW_Y = 0xFFF3EE, 0xFFF3F0          # the point the camera follows (words)
CAMERA_X, CAMERA_Y = 0xFFEA38, 0xFFEA3A          # the camera position (words)
SCROLL_X, SCROLL_Y = 0xFFEA3C, 0xFFEA3E          # camera / 2, clamped: 0..67F and 0..FF (words)
STEP = 4
SCROLL_X_LIMIT, SCROLL_Y_LIMIT = 0x680, 0x100


def _signed(word: int) -> int:
    return word - 0x10000 if word & 0x8000 else word


def camera_follow(read_word):
    """One tick of the camera.  ``read_word(address)`` returns an unsigned word.

    Returns the words to store, the value the routine leaves in D0.W, and the
    branch it took (``'hold'``, ``'right'`` or ``'left'``) with the clamps
    that fired, so a boundary can admit only what a recording witnessed.
    """
    dx = _signed((read_word(FOLLOW_X) - read_word(CAMERA_X)) & 0xFFFF)
    camera_x = read_word(CAMERA_X)
    if dx > 0:
        branch, camera_x = 'right', (camera_x + STEP) & 0xFFFF
    elif dx < 0:
        branch, camera_x = 'left', (camera_x - STEP) & 0xFFFF
    else:
        branch = 'hold'
    clamps = []
    x = _signed(camera_x)
    if x < 0:                                     # 002822 moveq #0,d0: never witnessed
        clamps.append('x-negative'); x = 0
    scroll_x = x >> 1
    if scroll_x >= SCROLL_X_LIMIT:                # 00282C move.w #$67f,d0 (the right end of a wide level)
        clamps.append('x-limit'); scroll_x = SCROLL_X_LIMIT - 1
    y = _signed(read_word(FOLLOW_Y))
    if y < 0:                                     # 00283A moveq #0,d0: never witnessed
        clamps.append('y-negative'); y = 0
    camera_y = y & 0xFFFF
    scroll_y = y >> 1
    if scroll_y >= SCROLL_Y_LIMIT:                # 002848 move.w #$ff,d0
        clamps.append('y-limit'); scroll_y = SCROLL_Y_LIMIT - 1
    stores = {CAMERA_X: camera_x, SCROLL_X: scroll_x, CAMERA_Y: camera_y, SCROLL_Y: scroll_y}
    return {'stores': stores, 'd0': scroll_y, 'branch': branch, 'clamps': clamps,
            'x_flag': y & 1}                       # asr.w #1 of the y word leaves its low bit in X


# --- The follow point's own step (ROM 0075E2-00766C): the player state machine's shared tail ------
#
# The OTHER half of the camera subsystem: once every activation of the
# player state machine's shared tail (0075D6, ``docs/gods/blockers/
# 2026-09-17-005700.md``), when FFFFEF4E is zero, FOLLOW_X/FOLLOW_Y --
# the same words ``camera_follow`` reads above -- ease toward the
# player's own position (``game.player.POSITION_X``/``POSITION_Y``).
# FOLLOW_X moves by a fixed step of four inside a dead band (dx between
# 0x50 and 0xD0 holds); FOLLOW_Y moves by half the distance beyond its own
# band (0x70 above, 0x20 below), rounded toward the target with a minimum
# step of one, so it always closes some distance once outside the band.
# Both clamp: FOLLOW_X to 0..0xEC0, FOLLOW_Y to 0..0x340.  Called only
# when FFFFEF4E is zero; the other arm (FFFFEF4E nonzero, ROM 00755A) is a
# distinct cutscene-style tracker toward a scripted point and is not
# modelled here (unwitnessed by every recording, ``game.player``).
FOLLOW_X_DECREASE_BAND, FOLLOW_X_INCREASE_BAND = 0x50, 0xD0
FOLLOW_X_STEP = 4
FOLLOW_X_LIMIT = 0xEC0
FOLLOW_Y_INCREASE_BAND, FOLLOW_Y_DECREASE_BAND = 0x70, 0x20
FOLLOW_Y_LIMIT = 0x340


def _follow_x_step(follow_x, dx):
    if dx <= FOLLOW_X_DECREASE_BAND:
        new_x = (follow_x - FOLLOW_X_STEP) & 0xFFFF
        if _signed(new_x) < 0:
            return 'decrease-clamped', 0
        return 'decrease', new_x
    if dx < FOLLOW_X_INCREASE_BAND:
        return 'hold', follow_x
    new_x = (follow_x + FOLLOW_X_STEP) & 0xFFFF
    if _signed(new_x) >= FOLLOW_X_LIMIT:
        return 'increase-clamped', FOLLOW_X_LIMIT
    return 'increase', new_x


def _follow_y_step(follow_y, dy):
    """Returns the arm, the new FOLLOW_Y, and D3's own raw halved step (``asr.w #1,d3`` -- BEFORE the
    minimum-of-one override, which the ROM applies straight to FOLLOW_Y and never writes back into
    D3): the boundary needs it verbatim, since D3 is live (and checked) at the tail's own jmp into
    the second inline upload whenever this axis is not 'hold'."""
    if dy > FOLLOW_Y_INCREASE_BAND:
        step = _signed((dy - FOLLOW_Y_INCREASE_BAND) & 0xFFFF) >> 1
        new_y = (follow_y + (step or 1)) & 0xFFFF
        if _signed(new_y) >= FOLLOW_Y_LIMIT:
            return 'increase-clamped', FOLLOW_Y_LIMIT, step
        return 'increase', new_y, step
    if dy >= FOLLOW_Y_DECREASE_BAND:
        return 'hold', follow_y, None
    step = _signed((FOLLOW_Y_DECREASE_BAND - dy) & 0xFFFF) >> 1
    new_y = (follow_y - (step or 1)) & 0xFFFF
    if _signed(new_y) < 0:
        return 'decrease-clamped', 0, step
    return 'decrease', new_y, step


def follow_point_step(read_word, position_x, position_y):
    """One activation of the shared tail's follow-point step (FFFFEF4E == 0 arm).

    Returns the words to store (only the ones the ROM's own branch
    actually reaches -- a 'hold' axis stores nothing), the arm each axis
    took (``'decrease'``, ``'decrease-clamped'``, ``'hold'``,
    ``'increase'``, ``'increase-clamped'``) so the boundary can admit only
    what a recording witnessed, whether the minimum-of-one override fired
    on the y axis (``y_rounded``), and D3's own final low word at the
    tail's own jmp into the second inline upload (``d3``: 0xD0 -- the x
    axis's own comparison constant, still live -- when the y axis holds
    and the x axis is not 'decrease'/'decrease-clamped'; the y axis's own
    raw step when the y axis does not hold; ``None`` when nothing in this
    step touches D3 at all, leaving the caller's own entry value live).
    """
    follow_x, follow_y = read_word(FOLLOW_X), read_word(FOLLOW_Y)
    dx = _signed((position_x - follow_x) & 0xFFFF)
    dy = _signed((position_y - follow_y) & 0xFFFF)
    x_branch, new_x = _follow_x_step(follow_x, dx)
    y_branch, new_y, y_step = _follow_y_step(follow_y, dy)
    stores = {}
    if x_branch != 'hold':
        stores[FOLLOW_X] = new_x
    if y_branch != 'hold':
        stores[FOLLOW_Y] = new_y
    if y_branch != 'hold':
        d3 = y_step & 0xFFFF
    elif x_branch not in ('decrease', 'decrease-clamped'):
        d3 = FOLLOW_X_INCREASE_BAND
    else:
        d3 = None
    y_rounded = y_branch != 'hold' and y_step == 0
    return {'stores': stores, 'x_branch': x_branch, 'y_branch': y_branch, 'dx': dx, 'dy': dy,
            'y_rounded': y_rounded, 'd3': d3}
