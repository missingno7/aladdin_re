"""The spawn queue (ROM 0049DA-004A08): once per game tick from the main loop (001FBA), like the camera.

Four fixed 6-byte slots (`SLOT_BASE`) each hold an animation counter (word
0, negative when the slot is empty) and a world position (words at +2,
+4).  An active slot draws one static sprite this tick -- id
`SPRITE_ID_BASE` plus the counter, through `game.sprites.emit_static_sprite`
-- then advances the counter; at `RETIRE_LIMIT` the slot is marked empty
again.  What the effect actually is (a puff, a spark, ...) is not known;
the names are what the arithmetic supports, not more.
"""
from __future__ import annotations

from . import sprites

SLOT_BASE, SLOT_COUNT, SLOT_SIZE = 0xFFF39A, 4, 6
SPRITE_ID_BASE = 0x2F
RETIRE_LIMIT = 7
EMPTY = 0xFFFF


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def scan_spawn_queue(read):
    """One tick over all four slots, in order.

    ``read(address, size)`` must reflect each slot's own emitted sprite
    before the next slot is read (the routine's list append is sequential:
    a second active slot in the same tick sees the first one's updated
    list head), so calls are layered over a small local cache of the
    stores made so far -- the only addresses re-read across slots are
    ``sprites.LIST_HEAD`` and ``sprites.LIST_COUNT``.

    Returns one entry per slot: ``{'active': False}``, or ``{'active':
    True, 'sprite': id, 'emitted': emit_static_sprite's result,
    'counter_store': the word written back, 'retire': bool}``.
    """
    pending = {}

    def live(address, size):
        cached = pending.get(address)
        if cached is not None and cached[1] == size:
            return cached[0]
        return read(address, size)

    results = []
    for index in range(SLOT_COUNT):
        base = SLOT_BASE + SLOT_SIZE * index
        counter = live(base, 2)
        if _signed_word(counter) < 0:
            results.append({'active': False, 'counter': counter})
            continue
        x, y = live(base + 2, 2), live(base + 4, 2)
        sprite = (SPRITE_ID_BASE + counter) & 0xFFFF
        emitted = sprites.emit_static_sprite(live, x, y, sprite)
        for address, (value, size) in emitted['stores'].items():
            pending[address] = (value, size)
        next_counter = (counter + 1) & 0xFFFF
        retire = next_counter >= RETIRE_LIMIT
        results.append({'active': True, 'counter': counter, 'sprite': sprite, 'x': x, 'y': y, 'emitted': emitted,
                        'counter_store': EMPTY if retire else next_counter, 'retire': retire})
    return results
