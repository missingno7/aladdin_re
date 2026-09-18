"""The floating icon/message spawn record (ROM 010D7C), reached only from the achievement highlight
cycle's own "slot not empty" arm (``game.achievements.achievement_highlight_cycle``, states 19/18's
own ``005CEE``) with the tracked position (``GRID_X`` + 8, ``GRID_Y`` + 0x20) and a kind word (the
consumed achievement slot's own stored value, biased +0xB by the caller).  A fourth subsystem, distinct
from ``game.messages``'s own ``MESSAGE_BOUND``/``MESSAGE_BUFFER`` fields
(``docs/gods/blockers/2026-09-18-005886.md``): four fields no other recovered code touches, gated by a
busy test on the last of them.  Witnessed once (states 19/18's own census, five recordings): the
'spawn' arm below.  'special' (kind == 0x3D) and 'busy' (a spawn already pending) are real ROM code
this session did not trace past their own first branch and are declined by name.

Pure function of ``read(address, size)``; no cycles, CCR, stack or registers.
"""
from __future__ import annotations

SPAWN_X = 0xFFFFF1F0        # word: world x (the caller's own D0)
SPAWN_Y = 0xFFFFF1F2        # word: world y (the caller's own D1)
SPAWN_TIMER = 0xFFFFF1F4    # word: always -3 (0xFFFD) on the witnessed store
SPAWN_KIND = 0xFFFFF1F6     # word: doubles as the busy flag -- negative is free, >=0 is occupied
SPAWN_TIMER_INIT = 0xFFFFFFFD & 0xFFFF
SPECIAL_KIND = 0x3D          # cmpi.w #$3d,d2 -- a distinct dispatch (010D9E) this session did not trace


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def floating_icon_spawn(read, x, y, kind):
    """010D7C: ``kind == 0x3D`` is a distinct, unwitnessed dispatch (``'special'``, declined); otherwise
    a busy test on SPAWN_KIND gates the one witnessed arm (``'spawn'``): a record already pending
    (SPAWN_KIND non-negative) is real code no recording enters (``'busy'``, declined -- the ROM's own
    010E28 continuation); a free record (SPAWN_KIND negative) stores all four fields unconditionally.
    """
    kind &= 0xFFFF
    if kind == SPECIAL_KIND:
        return {'arm': 'special', 'kind': kind}
    if _signed_word(read(SPAWN_KIND, 2)) >= 0:
        return {'arm': 'busy', 'kind': kind}
    return {'arm': 'spawn', 'x': x & 0xFFFF, 'y': y & 0xFFFF, 'kind': kind,
            'stores': {SPAWN_X & 0xFFFFFF: (x & 0xFFFF, 2), SPAWN_Y & 0xFFFFFF: (y & 0xFFFF, 2),
                       SPAWN_TIMER & 0xFFFFFF: (SPAWN_TIMER_INIT, 2), SPAWN_KIND & 0xFFFFFF: (kind, 2)}}
