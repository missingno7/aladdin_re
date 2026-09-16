"""The projectile launch (ROM 0091BC-0091F6): the 20-entry projectile pool's own cold start.

Called with a walk's own starting position (D0, D1 -- the same ``x0``/``y0``
argument order ``game/walker.py``'s ``start`` takes), a step budget (D4,
also stored again into the shared ``FRAME_BUDGET`` word ``FFF1FE``) and a
caller-owned flag (D6, only bit 0 kept).  Scans a fixed 20-entry, 22-byte
pool at ``POOL_BASE`` for a free slot (the first long negative) and, on a
hit, starts a walk from ``(x0, y0)`` toward the tracked position
(``grid.GRID_X``/``GRID_Y`` -- the player -- biased ``+8``/``+6``) with the
projectile copy of the walker, taking the budget's own steps immediately
(the cold start falls straight into the same loop the resume would jump
to), then stores the caller's own budget again at the slot's own ``+0x12``
word and the flag at ``+0x14``, and sets ``LAUNCHED_FLAG``.  The pool
exhausted (``0091DE``) is real ROM code no recording enters: declined.

Pure functions of ``read(address, size)``; calls into ``game/walker.py``'s
own pure step functions for the walk itself -- the shape ``00BA8E``'s
composition over its own callees proved.
"""
from __future__ import annotations

from . import walker
from .grid import GRID_X, GRID_Y

POOL_BASE = 0xFFFFE19E
POOL_STRIDE = 0x16              # 22 bytes
POOL_COUNT = 20
AUX_BUDGET = 0x12               # slot word: the caller's own budget, stored again (read by something later, not traced)
AUX_FLAG = 0x14                 # slot word: the caller's own D6, masked to bit 0
TARGET_BIAS_X, TARGET_BIAS_Y = 0x8, 0x6
LAUNCHED_FLAG = 0xFFFFF386
BUDGET_WORD = 0xFFFFF1FE


def launch(read, x0, y0, budget, flag):
    """0091BC: scan the pool for a free slot and launch a projectile walk from ``(x0, y0)`` toward the
    tracked position; ``'pool-full'`` is declined (real ROM code, unwitnessed).

    ``slot`` in the result is the free record's own full-width address (as a real A3 would hold it,
    ``0xFFFFxxxx``); every RAM address in ``stores`` is masked to the 24-bit work-RAM form.
    """
    x1 = (read(GRID_X, 2) + TARGET_BIAS_X) & 0xFFFF
    y1 = (read(GRID_Y, 2) + TARGET_BIAS_Y) & 0xFFFF
    budget &= 0xFFFF
    stores = {BUDGET_WORD & 0xFFFFFF: (budget, 2)}
    for tries in range(POOL_COUNT):
        record = (POOL_BASE + POOL_STRIDE * tries) & 0xFFFFFFFF
        record24 = record & 0xFFFFFF
        if read(record24, 4) & 0x80000000:
            walk = walker.start(x0, y0, x1, y1)
            after, left, steps, completed = walker.run(walk, budget, 'projectile')
            stores[BUDGET_WORD & 0xFFFFFF] = (left, 2)
            stores.update({(address & 0xFFFFFF): value for address, value in walker.stores(after, record24, 'projectile').items()})
            stores[(record24 + AUX_BUDGET) & 0xFFFFFF] = (budget, 2)
            stores[(record24 + AUX_FLAG) & 0xFFFFFF] = (flag & 1, 2)
            stores[LAUNCHED_FLAG & 0xFFFFFF] = (1, 2)
            return {'arm': 'launched', 'slot': record, 'tries': tries, 'walk': walk, 'after': after,
                    'left': left, 'steps': steps, 'budget': budget, 'target': (x1, y1), 'stores': stores}
    return {'arm': 'pool-full', 'tries': POOL_COUNT, 'target': (x1, y1), 'stores': stores}
