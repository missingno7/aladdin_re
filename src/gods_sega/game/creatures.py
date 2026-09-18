"""The creature attack timer (ROM 009D6C-009D6A / 009CF2-009DEA), called once per active creature per
frame from ``00A772`` (the per-creature family 00A578's own 9-slot list walk calls for each live
instance).

Two pointers, both owned by the caller and never advanced here: ``type_ptr`` (A4) is the creature
TYPE's own shared, read-only template (``00A578``'s own per-list definition table); ``instance_ptr``
(A5) is this one creature's own live 24-byte state (the record ``00A578`` itself walks in 0x18-byte
steps).  A zero attack byte, or its own low nibble zero, leaves everything alone (``'skip'``).
Otherwise the per-instance countdown at ``COUNTDOWN`` is decremented; while it stays nonzero the call
is done (``'waiting'``).  Reaching zero reloads it from the low nibble (``(16-kind)*4``) and reads the
aim quadrant from the type's own word at ``QUADRANT_WORD`` (bits 4-5): quadrant 1 draws two jitters
from the shared random table (``effects.next_random``, applied to the tracked position the same way
``projectiles.launch`` biases it) and launches through ``projectiles.launch_toward`` (ROM 0091C8 --
``launch``'s own pool body entered past its GRID_X/GRID_Y read, with the jittered target supplied
directly); quadrants 2-3 launch at the tracked position with no jitter, through ``projectiles.launch``
itself (0091BC).  Both share the launch's own ``'pool-full'`` decline (unwitnessed).

Quadrant 0 never launches a projectile: it computes a frequency word with the exact shape
``timers._frequency`` uses (``swap(power * FREQUENCY_SCALE) + 1``) but fed from the attack byte's own
high nibble (``power``) rather than a control byte, then hands off to ``timers._spawn``'s own
BACK/FORWARD hazard-pool fill.  Which variant runs is selected by whichever of two ROM tests fires
first: while the shared word ``TRACKED_SIGN`` is negative, a fixed one-byte ROM table
(``DIRECTION_BIT_TABLE``) is tested at the bit ``DIRECTION_INDEX`` selects; otherwise the instance's own
``FORWARD_BACK`` word does directly (zero declines with no effect at all, ``'skip-quadrant0'``).  Both
tests are plain mirrors of the ROM's own two branches -- not a guess -- and both reach the identical
BACK/FORWARD tail ``timers._spawn`` already proves; only the *dispatch* differs.

Pure functions of ``read(address, size)``; calls into ``game/timers.py``, ``game/effects.py`` and
``game/projectiles.py``'s own pure functions for the rest.
"""
from __future__ import annotations

from . import effects, projectiles, timers
from .grid import GRID_X, GRID_Y

ATTACK_BYTE = 0x6                  # type_ptr byte: 0 disables the creature's attack entirely
QUADRANT_WORD = 0x4                # type_ptr word: bits 4-5 (>>4 & 3) select the aim quadrant
COUNTDOWN = 0xE                    # instance_ptr word: ticks down to zero, then reloads
POSITION_X, POSITION_Y = 0x0, 0x2  # instance_ptr words: this creature's own world position
DIRECTION_INDEX = 0xA              # instance_ptr word: bit index into DIRECTION_BIT_TABLE
FORWARD_BACK = 0x12                # instance_ptr word: sign selects BACK(<0)/skip(==0)/FORWARD(>0)
DIRECTION_BIT_TABLE = 0x009DEA     # ROM byte: bit N (mod 8) set selects BACK, clear selects FORWARD
TRACKED_SIGN = 0xFFFFF1BE          # word: negative routes through DIRECTION_BIT_TABLE, else FORWARD_BACK
LAUNCH_POSITION_BIAS = 0x10        # instance position -> the launch's own x0 (X only)
TARGET_BIAS_X, TARGET_BIAS_Y = 0x8, 0x6   # matches projectiles.TARGET_BIAS_X/Y (tracked position bias)
AIM_JITTER_MASK, AIM_JITTER_BIAS = 0x3F, 0x1F   # jitter = (next_random() & 0x3F) - 0x1F, one draw per axis
LAUNCH_FLAG = 0                    # moveq #0,d6: the launch's own flag argument, fixed (not caller-derived)


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _overlay(read, stores):
    """A ``read`` wrapped so an address just written (by an earlier draw in the same call) is seen with
    its new value -- real hardware, unlike this module's own ``stores`` bookkeeping, sees every write
    immediately."""
    def wrapped(address, size):
        address &= 0xFFFFFF
        if address in stores:
            value, _ = stores[address]
            return value
        return read(address, size)
    return wrapped


def attack_update(read, type_ptr, instance_ptr):
    """009D6C: one creature's own attack-timer tick.

    Returns the arm (``'skip'``, ``'waiting'``, ``'launch-jittered'``, ``'launch-direct'`` (each with a
    ``-pool-full`` suffix if the projectile pool is exhausted -- declined, unwitnessed), ``'spawn-window'``
    /``'spawn-reject'``/``'spawn-pool-full'`` (the last declined, unwitnessed) or ``'skip-quadrant0'``
    (declined, unwitnessed as its own combination though its own effect is none) -- the countdown's value
    before/after where it changed, and the durable stores.
    """
    type_ptr &= 0xFFFFFF
    instance_ptr &= 0xFFFFFF
    attack_byte = read(type_ptr + ATTACK_BYTE, 1) & 0xFF
    if attack_byte == 0:
        return {'arm': 'skip', 'stores': {}}
    kind = attack_byte & 0xF
    if kind == 0:
        return {'arm': 'skip', 'stores': {}}
    before = read(instance_ptr + COUNTDOWN, 2) & 0xFFFF
    after = (before - 1) & 0xFFFF
    if after != 0:
        return {'arm': 'waiting', 'before': before, 'after': after,
                'stores': {(instance_ptr + COUNTDOWN) & 0xFFFFFF: (after, 2)}}
    reload = (((0x10 - kind) & 0xFF) * 4) & 0xFFFF
    stores = {(instance_ptr + COUNTDOWN) & 0xFFFFFF: (reload, 2)}
    power = (attack_byte >> 4) & 0xF
    quadrant = (read(type_ptr + QUADRANT_WORD, 2) >> 4) & 0x3
    result = {'before': before, 'after': after, 'reload': reload, 'kind': kind, 'power': power,
              'quadrant': quadrant, 'stores': stores}
    if quadrant != 0:
        x0 = (read(instance_ptr + POSITION_X, 2) + LAUNCH_POSITION_BIAS) & 0xFFFF
        y0 = read(instance_ptr + POSITION_Y, 2) & 0xFFFF
        if quadrant == 1:
            x1 = (read(GRID_X, 2) + TARGET_BIAS_X) & 0xFFFF
            y1 = (read(GRID_Y, 2) + TARGET_BIAS_Y) & 0xFFFF
            draw_x = effects.next_random(read)
            stores.update(draw_x['stores'])
            x1 = (x1 + (((draw_x['value'] & AIM_JITTER_MASK) - AIM_JITTER_BIAS) & 0xFFFF)) & 0xFFFF
            draw_y = effects.next_random(_overlay(read, draw_x['stores']))
            stores.update(draw_y['stores'])
            y1 = (y1 + (((draw_y['value'] & AIM_JITTER_MASK) - AIM_JITTER_BIAS) & 0xFFFF)) & 0xFFFF
            result['draws'] = (draw_x, draw_y)
            launch = projectiles.launch_toward(read, x0, y0, x1, y1, power, LAUNCH_FLAG)
            result['arm'] = 'launch-jittered'
        else:
            launch = projectiles.launch(read, x0, y0, power, LAUNCH_FLAG)
            result['arm'] = 'launch-direct'
        stores.update(launch['stores'])
        result['launch'] = launch
        if launch['arm'] == 'pool-full':
            result['arm'] += '-pool-full'
        return result
    # quadrant == 0: the frequency/hazard-pool arm -- timers._frequency's own shape, a local 'power' base.
    raw = (power * read(timers.FREQUENCY_SCALE, 2)) & 0xFFFFFFFF
    frequency = (((raw >> 16) & 0xFFFF) + 1) & 0xFFFF
    frequency_upper = raw & 0xFFFF   # swap's own leftover high word -- D5 keeps it until 01158C/0115D4 overwrite D5 entirely (spawn-window only)
    tracked = _signed_word(read(TRACKED_SIGN, 2))
    if tracked < 0:
        index = read(instance_ptr + DIRECTION_INDEX, 2) & 0x7
        bit = (read(DIRECTION_BIT_TABLE, 1) >> index) & 1
        variant = timers.BACK if bit else timers.FORWARD
    else:
        select = _signed_word(read(instance_ptr + FORWARD_BACK, 2))
        if select == 0:
            result['arm'] = 'skip-quadrant0'
            return result
        variant = timers.FORWARD if select > 0 else timers.BACK
    if variant is timers.BACK:
        frequency = (-frequency) & 0xFFFF
    spawn = timers._spawn(read, instance_ptr, variant, frequency)
    stores[timers.TRIGGER_FREQUENCY & 0xFFFFFF] = (frequency, 2)
    stores.update(spawn['stores'])
    result.update(frequency=frequency, frequency_upper=frequency_upper, variant=variant, spawn=spawn)
    if not spawn['windowed']:
        result['arm'] = 'spawn-reject'
    elif spawn['slot'] is not None:
        result['arm'] = 'spawn-window'
    else:
        result['arm'] = 'spawn-pool-full'
    return result
