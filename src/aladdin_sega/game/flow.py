"""Level flow inside a frame: falling out, dying, the transition countdown and the per-level tick.

* ``fall_check`` (1A8F0C): below the level, or when the dying countdown
  (FFF0E6) runs out, the life is lost -- both paths lead into the
  respawn / game-over sequence, which restarts the level (a transition).
* ``transition_countdown`` (1A8E3E): FFF0E9 counts down to the level
  change: the next entry of the level sequence (FFF572) is loaded and the
  main loop restarts from the level start.
* ``level_tick`` (1A8F04): the level table's per-frame routine (+0x2C):
  level-end triggers by position, timed spawns, ambient sounds, the
  carpet ride, and the scripted event streams of levels 2, 6 and 8.

Transitions leave the frame loop; natively they are reported as gaps
until the level loader is recovered.
"""
from .objects.record import RECORD_TABLE, RECORD_SIZE
from .objects.lifecycle import initialize
from .rng import SEED_ADDRESS, advance_rng
from . import player as P
from .video import load_palette

DYING = 0xFFF0E6
TRANSITION_COUNTDOWN = 0xFFF0E9
INVULNERABLE = 0xFFF0F2
CARPET_FALLS = 0xFFF006              # level 8: falls before the ride is lost
LEVEL_TICK = 0xFF7DC2                # long: the level table's +0x2C routine
EVENT_STREAM, CARPET_STREAM = 0xFFF132, 0xFFF12E
EVENT_COUNTER = 0xFFF10C
EVENT_HANDLERS = 0x20C0              # ROM: longs by opcode - 0xE6
TEMPLATE_SIZE = 19


class Transition(Exception):
    """The frame loop is left for a level change (death, level complete, bonus)."""


def _w(v):
    return v & 0xFFFF


def _sound(read, services, sound_id, flush=True):
    if read(P.SOUND_ENABLED, 1):
        services.sound(0, sound_id, flush=flush)


def _find_free(read, start, count, direction=1):
    for i in range(count):
        address = start + direction * RECORD_SIZE * i
        if not read(address, 1):
            return address
    return None


def _spawn(read, write, rom, template, record, x, y, **fields):
    for address, value in initialize(record, rom[template:template + TEMPLATE_SIZE]):
        write(address, value, 1)
    write(record + 2, x, 2)
    write(record + 4, y, 2)
    for offset, (value, size) in fields.items():
        write(record + offset, value, size)


def _random(read, write):
    seed, roll = advance_rng(read(SEED_ADDRESS, 4))
    write(SEED_ADDRESS, seed, 4)
    return roll


# -- 1A8F0C --------------------------------------------------------------------------------------
def fall_check(read, write) -> None:
    if _w(read(P.LEVEL_HEIGHT, 2) + 0x100) < read(P.WORLD_Y, 2):
        raise Transition('fell below the level (1A902E)')
    dying = read(DYING, 1)
    if not dying:
        return
    if dying != 0xFF:
        dying -= 1
        write(DYING, dying, 1)
        if dying:
            return
    write(DYING, 0, 1)
    if read(INVULNERABLE, 1):
        return
    write(INVULNERABLE, 0, 1)
    write(0xFF7E47, 0, 1)
    if read(P.LEVEL_INDEX, 1) == 8:
        falls = read(CARPET_FALLS, 1) + 1
        write(CARPET_FALLS, falls, 1)
        if falls < 3:
            raise Transition('life lost on the carpet (1A8F82)')
        write(TRANSITION_COUNTDOWN, 0xFF, 1)
        write(DYING, 0, 1)
        return
    raise Transition('life lost (1A8F82)')


# -- 1A8E3E --------------------------------------------------------------------------------------
def transition_countdown(read, write) -> None:
    remaining = read(TRANSITION_COUNTDOWN, 1)
    if not remaining:
        return
    if remaining != 0xFF:
        remaining -= 1
        write(TRANSITION_COUNTDOWN, remaining, 1)
        if remaining:
            return
    raise Transition('level change (1A8E5C)')


# -- 1A8F04: the per-level tick ------------------------------------------------------------------
def _end_when(read, write, x_min=None, y_max=None, y_min=None, value=0xFF):
    if x_min is not None and read(P.WORLD_X, 2) < x_min:
        return
    if y_max is not None and read(P.WORLD_Y, 2) >= y_max:
        return
    if y_min is not None and read(P.WORLD_Y, 2) < y_min:
        return
    write(TRANSITION_COUNTDOWN, value, 1)


def _countdown(read, write, address):
    if read(address, 1):
        write(address, read(address, 1) - 1, 1)


def _in_zone(read, x0, x1, y0, y1):
    x, y = read(P.WORLD_X, 2), read(P.WORLD_Y, 2)
    return x0 <= x < x1 and y0 <= y < y1


def tick_level_1(read, write, rom, services, vdp):
    """1B5B4A: the level ends past x 1288 above y 1D6; FFF103 counts down."""
    _end_when(read, write, x_min=0x1288, y_max=0x1D6)
    _countdown(read, write, 0xFFF103)


def tick_level_0(read, write, rom, services, vdp):
    """1B5B66: FFF124 counts down to a palette load; FFF103 counts down."""
    if read(0xFFF124, 1):
        remaining = read(0xFFF124, 1) - 1
        write(0xFFF124, remaining, 1)
        if not remaining:
            load_palette(write, rom, vdp, 2, 0x129092)
    _countdown(read, write, 0xFFF103)


def tick_level_2(read, write, rom, services, vdp):
    """1B5B94: the scripted event stream."""
    event_stream(read, write, rom, services, vdp)


def tick_nothing(read, write, rom, services, vdp):
    """1B5B9A."""


def tick_level_4(read, write, rom, services, vdp):
    """1B5B9C: two one-shot sounds raised by flags; the level ends past x 8D9 above y 1EA."""
    for flag, sound_id in ((0xFFF11A, 0x38), (0xFFF12C, 0x45)):
        if read(flag, 1):
            _sound(read, services, sound_id)
            write(flag, 0, 1)
    if not read(TRANSITION_COUNTDOWN, 1):
        _end_when(read, write, x_min=0x8D9, y_max=0x1EA)


def tick_level_5(read, write, rom, services, vdp):
    """1B5C20: every 64 frames a falling 1B819C object in one of two zones."""
    if read(P.FRAME_COUNTER, 1) & 0x3F:
        return
    for (x0, x1, y0, y1), places in (((0x20, 0x1A0, 0x110, 0x320), ((0x10, 0x140), (0x60, 0x118), (0x1A8, 0x110))),
                                   ((0xB80, 0xC78, 0x218, 0x3B0), ((0xC70, 0x178), (0xBE8, 0x190), (0xBC8, 0x198)))):
        if not _in_zone(read, x0, x1, y0, y1):
            continue
        record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 3, 20)
        if record is None:
            return
        for address, value in initialize(record, rom[0x1B819C:0x1B819C + TEMPLATE_SIZE]):
            write(address, value, 1)
        write(record + 0x1A, 0x400, 2)
        roll = _random(read, write) & 3
        x, y = places[0] if roll < 2 else places[1] if roll == 2 else places[2]
        write(record + 2, x, 2)
        write(record + 4, y, 2)
        return


def tick_level_6(read, write, rom, services, vdp):
    """1B5D3A: the event stream, and the fall timer never counts."""
    event_stream(read, write, rom, services, vdp)
    write(P.FALL_TIMER, 0, 1)


def tick_level_7(read, write, rom, services, vdp):
    """1B5D68: the level ends past x 27C5; timed spawns of 1B81C4 and 1B81D8 by zone."""
    if not read(TRANSITION_COUNTDOWN, 1):
        _end_when(read, write, x_min=0x27C5)
    if not read(P.FRAME_COUNTER, 1) & 0x7F:
        for x0, x1, y0, y1 in ((0x1730, 0x1920, 0x100, 0x230), (0x6A0, 0x920, 0x100, 0x250), (0x9D0, 0xB20, 0x100, 0x250)):
            if not _in_zone(read, x0, x1, y0, y1):
                continue
            record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 3, 20)
            if record is None:
                return
            if x0 == 0x1730:
                x, y = 0x18F0, 0x100
            elif x0 == 0x6A0:
                x, y = (0x820 if _random(read, write) & 0xFF < 0x80 else 0x860), 0x110
            else:
                x, y = 0xAE0, 0x110
            _spawn(read, write, rom, 0x1B81C4, record, x, y, **{0x1A: (0x400, 2)})
            break
    if read(0xFFF113, 1):
        write(0xFFF113, read(0xFFF113, 1) - 1, 1)
        return
    x = read(P.WORLD_X, 2)
    for x0, sx, sy in ((0x360, 0x310, 0x110), (0xE20, 0xDC0, 0x110), (0x1270, 0x1230, 0x160),
                       (0x1550, 0x1530, 0x180), (0x1CD0, 0x1D80, 0x100), (0x2260, 0x21F0, 0x100)):
        if x0 <= x < x0 + 0x10:
            record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 3, 20)
            if record is None:
                return
            _spawn(read, write, rom, 0x1B81D8, record, sx, sy, **{9: (0xFF, 1)})
            write(0xFFF113, 0x3C, 1)
            return


def tick_level_8(read, write, rom, services, vdp):
    """1B6066: the carpet ride: the player follows the carpet, the ride speeds up, the sky scrolls, events stream."""
    raise Transition('the carpet ride tick (1B6066) is not recovered')


def tick_level_9(read, write, rom, services, vdp):
    """1B614C: a timed 1B7FA8 spawn, the level end past x 1B9E, a 1B80D4 spawn in a zone, a counter."""
    count = read(0xFFF118, 1) + 1
    write(0xFFF118, count, 1)
    if count >= 0x50:
        write(0xFFF118, 0, 1)
        if read(P.WORLD_Y, 2) >= 0x19B and 0x6B0 <= read(P.WORLD_X, 2) < 0x9C8:
            record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 24, 24, -1)
            if record is not None:
                _spawn(read, write, rom, 0x1B7FA8, record, 0xA22, 0,
                       **{0: (0x50, 1), 0x20: (0x124B94, 4), 0xA: (0x1203F2, 4), 9: (0xFF, 1), 0x3C: (2, 1)})
                write(record + 4, 0x220 + (_random(read, write) & 0x20), 2)
    if not read(TRANSITION_COUNTDOWN, 1):
        _end_when(read, write, x_min=0x1B9E, value=1)
    if 0x4D3 <= read(P.WORLD_X, 2) < 0x6AC and read(P.FRAME_COUNTER, 1) & 0x7F == 0x49:
        record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 3, 20)
        if record is not None:
            _spawn(read, write, rom, 0x1B80D4, record, 0x5A0, 0x100)
    write(0xFFF109, (read(0xFFF109, 1) + 1) & 0x7F, 1)


def tick_level_10(read, write, rom, services, vdp):
    """1B623A: the level ends past x C4A below y 496."""
    _end_when(read, write, x_min=0xC4A, y_min=0x496, value=1)


def tick_level_11(read, write, rom, services, vdp):
    """1B6258: at frame 0 of each 256 a 1B8214 object in the zone."""
    if read(P.FRAME_COUNTER, 1) or not _in_zone(read, 0x10, 0x470, 0x130, 0x1D0):
        return
    record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 3, 20)
    if record is not None:
        _spawn(read, write, rom, 0x1B8214, record, 0x4C0, 0x1B0, **{9: (0xFF, 1)})


def tick_level_12(read, write, rom, services, vdp):
    """1B62B6: at frame 13 a 1B7BE8 object; every 128 frames slot 1 becomes a 1B8278 object by the player's side."""
    counter = read(P.FRAME_COUNTER, 1)
    if counter == 0xD:
        record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 3, 20)
        if record is not None:
            _spawn(read, write, rom, 0x1B7BE8, record, 0x2B1, 0x22A)
        return
    if counter & 0x7F:
        return
    record = RECORD_TABLE + RECORD_SIZE
    if read(P.WORLD_X, 2) >= 0x182:
        _spawn(read, write, rom, 0x1B8278, record, 0x184, 0x166, **{0x20: (0x125AFE, 4)})
    else:
        _spawn(read, write, rom, 0x1B8278, record, 0x184, 0x166, **{0x20: (0x125B42, 4), 9: (0xFF, 1)})


def event_stream(read, write, rom, services, vdp):
    """1B634E: [delay, opcode, x, y] events from the level's stream, each after its delay."""
    pointer = read(EVENT_STREAM, 4)
    delay = rom[pointer]
    if not delay:
        return
    count = read(EVENT_COUNTER, 1) + 1
    write(EVENT_COUNTER, count, 1)
    if delay >= count:
        return
    opcode = rom[pointer + 1]
    write(EVENT_STREAM, pointer + 6, 4)
    write(EVENT_COUNTER, 0, 1)
    target = int.from_bytes(rom[EVENT_HANDLERS + 4 * (opcode - 0xE6):EVENT_HANDLERS + 4 * (opcode - 0xE6) + 4], 'big')
    raise Transition(f'level event handler {opcode:02X} ({target:06X}) is not recovered')


LEVEL_TICKS = {
    0x1B5B4A: tick_level_1, 0x1B5B66: tick_level_0, 0x1B5B94: tick_level_2, 0x1B5B9A: tick_nothing,
    0x1B5B9C: tick_level_4, 0x1B5C20: tick_level_5, 0x1B5D3A: tick_level_6, 0x1B5D68: tick_level_7,
    0x1B6066: tick_level_8, 0x1B614C: tick_level_9, 0x1B623A: tick_level_10, 0x1B6258: tick_level_11,
    0x1B62B6: tick_level_12,
}


def level_tick(read, write, rom, services, vdp) -> None:
    routine = read(LEVEL_TICK, 4)
    try:
        tick = LEVEL_TICKS[routine]
    except KeyError:
        raise Transition(f'level tick {routine:06X} is not recovered') from None
    tick(read, write, rom, services, vdp)
