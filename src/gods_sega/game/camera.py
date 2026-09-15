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
    if scroll_x >= SCROLL_X_LIMIT:                # 00282C move.w #$67f,d0: never witnessed
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
