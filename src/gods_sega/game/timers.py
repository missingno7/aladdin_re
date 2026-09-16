"""The rate-gated countdown check (ROM 010332-0103xx), called 412 times / 600 frames from ``0101FA``.

Called with a control byte (A3) and a per-slot record (A5: a position at
``+0``/``+2``, a direction word at ``+0xA``, the countdown word itself at
``+0xC``), both passed by the caller (they vary call to call, not fixed
globals): a control byte of zero disables the slot entirely (the ``'idle'``
arm, no effect); a nonzero control decrements the countdown, and while it
stays nonzero the call is done (the ``'waiting'`` arm, the decremented word
its only durable effect).

Reaching zero reloads the countdown from a rate byte in A3 (``(0x10 -
rate) * 4``) and computes a reload frequency word from the same byte
(``(rate >> 2 + 4)``, scaled by a work-RAM word and mirrored to a global,
``TRIGGER_FREQUENCY``) regardless of what follows.  A further A3 byte
(``TRIGGER_DEEP_GATE``) then either calls an unrecovered pool routine
(``0091BC``, itself calling a further unrecovered routine) -- declined
(``'trigger-deep'``) -- or runs a screen-relative window test on the
record's own position (offset -8 in X for one direction, +0x20 in the
other; the Y window shared) and, inside it, scans a bounded 20-entry pool
at ``SPAWN_POOL_BASE`` (the same screen-relative globals CAMERA_X/CAMERA_Y
as ``hazard.py``'s own pool fill reads) for a free slot (a word < 0,
0018C8's own convention) to fill with the position, the frequency and a
direction-tagged marker.  Outside the window: ``'trigger-reject'``, no pool
touch.  Inside it with a free slot: ``'trigger-spawn'``.  Inside it with
the pool full: ``'trigger-pool-full'`` -- real ROM code (the loop is the
same bounded shape ``01158C``/``0115D4`` share with ``hazard.py``'s pool),
but no recording exhausts it, so it is declined as unwitnessed.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

RATE_ENABLE = 0x13                # control byte (A3): zero disables the check for this call
COUNTDOWN = 0xC                   # countdown word (A5): decremented once per enabled call, reloaded on trigger
TRIGGER_DEEP_GATE = 0x12          # control byte (A3): nonzero calls the unrecovered 0091BC pool (declined)
DIRECTION = 0xA                   # A5 word: zero selects the 01158C variant, nonzero the 0115D4 variant
POSITION_X, POSITION_Y = 0x0, 0x2   # A5 words: the record's own world position
FREQUENCY_SCALE = 0xFFFFEEBE      # word: the reload rate's own multiplier (mulu.w, high word kept)
TRIGGER_FREQUENCY = 0xFFFFF1C2    # word: the computed frequency, also mirrored here before either variant runs
CAMERA_X, CAMERA_Y = 0xFFFFF3EE, 0xFFFFF3F0   # words: the same screen-relative globals hazard.py's OBJECT_X/OBJECT_Y read
SPAWN_POOL_BASE, SPAWN_POOL_STRIDE, SPAWN_POOL_COUNT = 0xFFFFDB74, 8, 0x14
_WINDOW_Y = (-4, 0xC0)                                            # screen_y in [lo, hi), shared by both variants
# 01158C (moving/direction word zero): position biased -8 in X, screen_x in [8, 0x148].
# 0115D4 (direction word nonzero): position biased +0x20 in X, screen_x in [-8, 0x138].
BACK = {'bias': -8, 'x_window': (8, 0x148), 'marker': 0, 'resume': 0x010382}
FORWARD = {'bias': 0x20, 'x_window': (-8, 0x138), 'marker': 3, 'resume': 0x01039A}


def _signed_byte(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _reload(read, control):
    """``moveq #$10,d3; sub.b $13(a3),d3; ext.w d3; add.w d3,d3; add.w d3,d3``: the countdown's new value."""
    diff = (0x10 - read(control + RATE_ENABLE, 1)) & 0xFF
    return (_signed_byte(diff) * 4) & 0xFFFF


def _frequency(read, control):
    """``move.b $13(a3),d3; ext.w; asr.w #2; addq.w #4; mulu.w $eebe.w,d3; swap d3; addq.w #1,d3``.

    Returns the low word (what every later instruction touches -- the
    value stored, negated for ``BACK``) and the swap's own high word
    (``raw``'s low word before the swap): D3's upper 16 bits from here
    onward, through the call and the window test, untouched by anything
    that follows (every later op on D3 is a word op).
    """
    base = (_signed_byte(read(control + RATE_ENABLE, 1)) >> 2) + 4
    raw = (base & 0xFFFF) * read(FREQUENCY_SCALE, 2)
    value = (((raw >> 16) & 0xFFFF) + 1) & 0xFFFF
    return value, raw & 0xFFFF


def _spawn(read, record, variant, frequency):
    """The window test and, inside it, the bounded pool scan+fill (both ``01158C`` and ``0115D4``'s own shape)."""
    pos_x = (read(record + POSITION_X, 2) + variant['bias']) & 0xFFFF
    pos_y = read(record + POSITION_Y, 2)
    screen_x = _signed_word((pos_x - read(CAMERA_X, 2)) & 0xFFFF)
    screen_y = _signed_word((pos_y - read(CAMERA_Y, 2)) & 0xFFFF)
    x_lo, x_hi = variant['x_window']
    y_lo, y_hi = _WINDOW_Y
    result = {'windowed': y_lo <= screen_y < y_hi and x_lo <= screen_x <= x_hi,
              'slot': None, 'tries': 0, 'pos_x': pos_x, 'pos_y': pos_y,
              'screen_x': screen_x, 'screen_y': screen_y, 'stores': {}}
    if not result['windowed']:
        return result
    for tries in range(SPAWN_POOL_COUNT):
        entry = SPAWN_POOL_BASE + SPAWN_POOL_STRIDE * tries
        if _signed_word(read((entry + 6) & 0xFFFFFFFF, 2)) < 0:   # tst.w $6(a0): the marker word, not offset 0
            result.update(slot=entry, tries=tries,
                           stores={entry & 0xFFFFFF: (pos_x, 2), (entry + 2) & 0xFFFFFF: (pos_y, 2),
                                   (entry + 4) & 0xFFFFFF: (frequency, 2), (entry + 6) & 0xFFFFFF: (variant['marker'], 2)})
            return result
    result['tries'] = SPAWN_POOL_COUNT
    return result


def countdown_check(read, control, countdown):
    """What ``010332`` does for one call with control struct ``control`` (A3) and record ``countdown`` (A5).

    Returns the arm (``'idle'``, ``'waiting'``, ``'trigger-deep'``
    (declined), ``'trigger-reject'``, ``'trigger-spawn'`` or
    ``'trigger-pool-full'`` (declined)), the countdown's value before and
    after (``'idle'`` leaves it untouched: ``before == after``), and the
    durable stores.  The trigger arms also report ``reload`` (the
    countdown's new value), and, once past the deep gate, ``frequency``,
    ``variant`` (``BACK``/``FORWARD``, carrying the resume PC the boundary
    needs) and the window/pool detail ``_spawn`` returns.
    """
    if read(control + RATE_ENABLE, 1) == 0:
        return {'arm': 'idle', 'before': None, 'after': None, 'stores': {}}
    before = read(countdown + COUNTDOWN, 2)
    after = (before - 1) & 0xFFFF
    if after != 0:
        return {'arm': 'waiting', 'before': before, 'after': after,
                'stores': {(countdown + COUNTDOWN) & 0xFFFFFF: (after, 2)}}
    reload = _reload(read, control)
    stores = {(countdown + COUNTDOWN) & 0xFFFFFF: (reload, 2)}
    result = {'before': before, 'after': after, 'reload': reload, 'stores': stores}
    if read(control + TRIGGER_DEEP_GATE, 1) != 0:
        result['arm'] = 'trigger-deep'
        return result
    variant = FORWARD if read(countdown + DIRECTION, 2) != 0 else BACK
    frequency, frequency_upper = _frequency(read, control)
    if variant is BACK:
        frequency = (-frequency) & 0xFFFF
    spawn = _spawn(read, countdown, variant, frequency)
    stores[TRIGGER_FREQUENCY & 0xFFFFFF] = (frequency, 2)
    stores.update(spawn['stores'])
    result.update(frequency=frequency, frequency_upper=frequency_upper, variant=variant, resume=variant['resume'],
                   windowed=spawn['windowed'], slot=spawn['slot'], tries=spawn['tries'],
                   pos_x=spawn['pos_x'], pos_y=spawn['pos_y'],
                   screen_x=spawn['screen_x'], screen_y=spawn['screen_y'])
    if not spawn['windowed']:
        result['arm'] = 'trigger-reject'
    elif spawn['slot'] is not None:
        result['arm'] = 'trigger-spawn'
    else:
        result['arm'] = 'trigger-pool-full'
    return result
