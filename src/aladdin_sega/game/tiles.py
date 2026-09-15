"""Special tiles under the player (1B1E38): the cell's collision class selects a handler.

Every frame the class byte of the cell the player stands in (attribute +2,
see :mod:`aladdin_sega.game.player`) is stored in FFF0C3 and, when not
zero, dispatched through the ROM table at 4554: conveyors, springs,
ropes and ladders (they enable the vertical input), the layer switch that
flips which attribute byte carries the ground, kill tiles, exits, and the
progress flags that later spawn sites test.  214 of the 256 classes have
no handler.  The handlers are keyed by their ROM address so classes that
share one share the function.
"""
from .pad import HELD_LEFT, HELD_RIGHT
from .rng import SEED_ADDRESS, advance_rng
from .objects.record import RECORD_TABLE, RECORD_SIZE
from .objects.lifecycle import initialize
from .objects.script_engine import Engine
from .objects.record import RecordView
from .level import MAP_ROW_TABLE
from . import player as P

HANDLERS = 0x4554                  # ROM: 256 longs by collision class
NO_HANDLER = 0x1B65BE
TILE_CLASS = 0xFFF0C3              # the class under the player this frame
LAYER_SWITCHED = 0xFFF0C2          # the layer-switch tile was already taken this visit
SCRIPT_115 = 0xFFF115              # TENTATIVE: sinking; the engine's player selector picks script 125E72
INVINCIBLE = 0xFF7E20              # TENTATIVE: no health loss (cheat / demo)
PROGRESS_FLAGS = {0x1B5450: 0xFFF0E4, 0x1B5458: 0xFFF105, 0x1B5460: 0xFFF107, 0x1B5468: 0xFFF106,
                  0x1B575C: 0xFFF16F, 0x1B5764: 0xFFF170, 0x1B576C: 0xFFF171, 0x1B5774: 0xFFF172}
LEVEL_11_FLAG = 0xFFF11D
DYING = 0xFFF0E6
TEMPLATE_SIZE = 19
SCRIPT_CLIMB_OUT, SCRIPT_SINK, SCRIPT_ATTACK, SCRIPT_FALL = 0x1223D0, 0x12181A, 0x121964, 0x121AD8
DUST_TEMPLATE, DUST_SCRIPT_A, DUST_SCRIPT_B = 0x1B805C, 0x1250DE, 0x1250CE


class TileGap(Exception):
    def __init__(self, tile_class, target):
        super().__init__(f'special tile handler for class {tile_class:02X} ({target:06X}) is not recovered')
        self.tile_class, self.target = tile_class, target


def _w(v):
    return v & 0xFFFF


def _sw(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _sound(read, services, sound_id, flush=True):
    if read(P.SOUND_ENABLED, 1):
        services.sound(0, sound_id, flush=flush)


def _find_free(read, start, count, direction=1):
    for i in range(count):
        address = start + direction * RECORD_SIZE * i
        if not read(address, 1):
            return address
    return None


def _spawn(read, write, rom, template, record, x, y):
    for address, value in initialize(record, rom[template:template + TEMPLATE_SIZE]):
        write(address, value, 1)
    write(record + 2, x, 2)
    write(record + 4, y, 2)


def special_tile(read, write, rom, services, memory) -> None:
    if read(P.LEVEL_INDEX, 1) == 8 or not read(P.SPRITE_FRAME, 4):
        return
    for flag in (P.CLIMBABLE, P.CLIMB_UP_BLOCKED, SCRIPT_115, P.ATTACK_ENABLED, P.SPECIAL_TILE):
        write(flag, 0, 1)
    if read(P.SPECIAL_TILE_2, 1):
        remaining = read(P.SPECIAL_TILE_2, 1) - 1
        write(P.SPECIAL_TILE_2, remaining, 1)
        if not remaining:
            _sound(read, services, 0x27, flush=False)
    y = _w(read(P.SCREEN_Y, 2) + read(P.CAMERA_Y, 2) - 0xF0)
    if y & 0x8000 or y >= _w(read(P.LEVEL_HEIGHT, 2) - 0x20):
        return
    cursor = read(MAP_ROW_TABLE + _sw(y * 4), 4) + 2 * (_w(read(P.CAMERA_X, 2) + read(P.SCREEN_X, 2) + 16) >> 4)
    if (cursor & 0xFFFF) >= read(P.MAP_END, 2):
        return
    tile_class = read(P.CELL_ATTRIBUTES + 2 + (read(cursor, 2) >> 1), 1)
    write(TILE_CLASS, tile_class, 1)
    if tile_class != 0x47:
        write(LAYER_SWITCHED, 0, 1)
    if not tile_class:
        return
    target = int.from_bytes(rom[HANDLERS + 4 * tile_class:HANDLERS + 4 * tile_class + 4], 'big')
    if target == NO_HANDLER:
        return
    try:
        handler = TILE_HANDLERS[target]
    except KeyError:
        raise TileGap(tile_class, target) from None
    handler(read, write, rom, services, memory)


# -- handlers, by ROM address --------------------------------------------------------------------
def kill(read, write, rom, services, memory):
    """1B5318: an instant-death tile."""
    write(DYING, 0xFF, 1)


def hidden_spawn(read, write, rom, services, memory):
    """1B5320: spawn the 1B7E2C object at the player once (unless kind 8C is already out)."""
    if read(P.LEVEL_INDEX, 1) == 0xB and not read(LEVEL_11_FLAG, 1):
        return
    for i in range(24):
        if read(RECORD_TABLE + RECORD_SIZE * (1 + i), 1) == 0x8C:
            return
    if not read(P.ON_GROUND, 1):
        return
    record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 3, 20)
    if record is not None:
        _spawn(read, write, rom, 0x1B7E2C, record, read(P.WORLD_X, 2), read(P.WORLD_Y, 2))


def conveyor_right(read, write, rom, services, memory):
    """1B536C."""
    write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) + 8), 2)
    write(P.WALK_SPEED, 0, 2)


def conveyor_left(read, write, rom, services, memory):
    """1B53A2."""
    write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) - 8), 2)
    write(P.WALK_SPEED, 0, 2)


def spring(read, write, rom, services, memory):
    """1B537A: launch the player upward."""
    write(P.VELOCITY_Y, _w(read(P.VELOCITY_Y, 2) - 0x7C), 2)
    write(P.WALK_SPEED, 0, 2)
    write(P.ON_GROUND, 0xFF, 1)
    P.snap_x(read, write)
    write(P.WALKING, 0, 1)
    write(P.IN_AIR, 0xFF, 1)


def crush(read, write, rom, services, memory):
    """1B53B0: the player dies in place; a 1B82A0 effect takes the spot."""
    if read(DYING, 1):
        return
    write(DYING, 0x20, 1)
    record = _find_free(read, RECORD_TABLE + RECORD_SIZE, 24)
    if record is None:
        return
    write(RECORD_TABLE, 0, 1)
    Engine(memory, services).release(RecordView(RECORD_TABLE, read, write))
    _spawn(read, write, rom, 0x1B82A0, record, read(P.WORLD_X, 2), read(P.WORLD_Y, 2))


def sink(read, write, rom, services, memory):
    """1B53F6: quicksand pulls the player down three frames in four."""
    if not read(P.FRAME_COUNTER, 1) & 3:
        return
    write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) + 1), 2)
    if read(P.VELOCITY_Y, 2) & 0x8000:
        return
    if read(P.JUMPING, 1) and not read(P.JUMP_SETTLED, 1):
        return
    write(SCRIPT_115, 0xFF, 1)
    write(P.HANGING, 0xFF, 1)
    write(P.JUMPING, 0, 1)
    write(P.ON_GROUND, 0xFF, 1)
    write(P.VELOCITY_Y, 0, 2)


def ground_on(read, write, rom, services, memory):
    """1B5440."""
    write(P.GROUND_IGNORED, 0, 1)


def ground_off(read, write, rom, services, memory):
    """1B5448."""
    write(P.GROUND_IGNORED, 0xFF, 1)


def _progress(address):
    def handler(read, write, rom, services, memory):
        write(address, 0xFF, 1)
    return handler


def clear_flag_172(read, write, rom, services, memory):
    """1B577C."""
    write(0xFFF172, 0, 1)


def layer_switch(read, write, rom, services, memory):
    """1B5470: toggle which attribute layer carries the ground, once per visit."""
    if read(P.GROUND_IGNORED, 1) or read(LAYER_SWITCHED, 1):
        return
    write(LAYER_SWITCHED, 0xFF, 1)
    write(P.ATTRIBUTE_LAYER, read(P.ATTRIBUTE_LAYER, 2) ^ 1, 2)


def layer_0(read, write, rom, services, memory):
    """1B5492."""
    write(P.ATTRIBUTE_LAYER, 0, 2)


def layer_1(read, write, rom, services, memory):
    """1B549C."""
    write(P.ATTRIBUTE_LAYER, 1, 2)


def climb_out(read, write, rom, services, memory):
    """1B54A6: the top of a climb: 80 pixels up, the climb-out animation, frozen."""
    write(P.CLIMB_UP_BLOCKED, 0xFF, 1)
    write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) - 0x50), 2)
    P.set_script(write, SCRIPT_CLIMB_OUT)
    write(P.FROZEN, 0xFF, 1)
    write(P.WALKING, 0, 1)


def climbable_top(read, write, rom, services, memory):
    """1B54D2: climbable, but not upward."""
    write(P.CLIMB_UP_BLOCKED, 0xFF, 1)
    write(P.CLIMBABLE, 0xFF, 1)


def climbable(read, write, rom, services, memory):
    """1B54D8."""
    write(P.CLIMBABLE, 0xFF, 1)


def attack_allowed(read, write, rom, services, memory):
    """1B54E0: the attack input works here; on level 5 the sand dusts too."""
    write(P.ATTACK_ENABLED, 0xFF, 1)
    if read(P.LEVEL_INDEX, 1) == 5:
        sand_dust(read, write, rom, services, memory)


def exit_when_landed(read, write, rom, services, memory):
    """1B54F4: a damaging tile (classes 9, 11, 12), taken when the player is not moving up."""
    if not read(P.VELOCITY_Y, 2) & 0x8000:
        P.hurt(read, write, services)


def sink_pose(read, write, rom, services, memory):
    """1B5502: the special-tile pose (script 12181A) when standing in the tile."""
    if read(P.FROZEN, 1) or read(P.VELOCITY_Y, 2) & 0x8000 or read(P.ON_GROUND, 1):
        return
    write(P.JUMPING, 0, 1); write(P.WALKING, 0, 1); write(P.WALK_SPEED, 0, 2)
    write(P.VELOCITY_X, 0, 2); write(P.FALL_TIMER, 0, 1)
    write(P.SCREEN_X, _w(((read(P.WORLD_X, 2) & 0xFFF0) | 6) - read(P.CAMERA_X, 2)), 2)
    P.set_script(write, SCRIPT_SINK)
    write(P.SPECIAL_TILE, 1, 1)
    if read(P.VELOCITY_Y, 1) < 8:
        write(P.VELOCITY_Y, _w(read(P.VELOCITY_Y, 2) + 0x78), 2)


def launcher(read, write, rom, services, memory):
    """1B557E: a diagonal launch up and to the left, as a jump."""
    if read(P.JUMPING, 1):
        return
    write(P.VELOCITY_Y, 0xFB00, 2)
    write(P.VELOCITY_X, 0xFC00, 2)
    write(P.ANIMATION_DELAY, 0, 1)
    write(P.JUMPING, 0xFF, 1)
    write(P.JUMP_SETTLED, 0, 1)
    write(P.WALKING, 0, 1)
    _sound(read, services, 0x3F)


def drag_left(read, write, rom, services, memory):
    """1B55D8."""
    write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) + 1), 2)
    write(P.VELOCITY_X, _w(read(P.VELOCITY_X, 2) + 0xFFBA), 2)


def grab_pose(read, write, rom, services, memory):
    """1B55E8: snap to the cell and hold the attack pose for four frames."""
    if read(P.FROZEN, 1) or read(P.JUMPING, 1):
        return
    write(P.VELOCITY_X, 0, 2); write(P.VELOCITY_Y, 0, 2); write(P.WALKING, 0, 1)
    write(P.WALK_SPEED, 0, 2); write(P.FALL_TIMER, 0, 1)
    if not read(P.SPECIAL_TILE_2, 1):
        P.set_script(write, SCRIPT_ATTACK)
        cam_y, cam_x = read(P.CAMERA_Y, 2), read(P.CAMERA_X, 2)
        write(P.SCREEN_Y, _w((_w(cam_y + read(P.SCREEN_Y, 2)) & 0xFFF0) - cam_y), 2)
        write(P.SCREEN_X, _w((_w(cam_x + read(P.SCREEN_X, 2)) | 0x1F) - cam_x), 2)
        write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) - 4), 2)
        write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) + 2), 2)
        _sound(read, services, 0x27)
    write(P.SPECIAL_TILE_2, 4, 1)
    write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) - 4), 2)
    write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) + 2), 2)


def knock_back(read, write, rom, services, memory):
    """1B56B6: thrown back and down with the falling animation."""
    write(P.VELOCITY_X, 0xFC00, 2)
    write(P.VELOCITY_Y, 0x200, 2)
    P.set_script(write, SCRIPT_FALL)
    _sound(read, services, 0x27, flush=False)


def sand_dust(read, write, rom, services, memory):
    """1B56F4: dust puffs while walking on sand."""
    if not (read(HELD_LEFT, 1) or read(HELD_RIGHT, 1)):
        return
    seed, roll = advance_rng(read(SEED_ADDRESS, 4))
    write(SEED_ADDRESS, seed, 4)
    if roll & 0xFF >= 0x28:
        return
    record = _find_free(read, RECORD_TABLE + RECORD_SIZE * 3, 20)
    if record is None:
        return
    x = _w(read(P.WORLD_X, 2) + (((roll & 7) - 3) & 0xFF))     # subq.b: the offset wraps as a byte
    _spawn(read, write, rom, DUST_TEMPLATE, record, x, _w(read(P.WORLD_Y, 2) - 0x2A))
    if roll & 0xFF < 0x1B:
        write(record + 0x20, DUST_SCRIPT_A, 4)
        if roll & 0xFF < 0xD:
            write(record + 0x20, DUST_SCRIPT_B, 4)


def nothing(read, write, rom, services, memory):
    """1B5784."""


TILE_HANDLERS = {
    0x1B5318: kill, 0x1B5320: hidden_spawn, 0x1B536C: conveyor_right, 0x1B537A: spring, 0x1B53A2: conveyor_left,
    0x1B53B0: crush, 0x1B53F6: sink, 0x1B5440: ground_on, 0x1B5448: ground_off, 0x1B5470: layer_switch,
    0x1B5492: layer_0, 0x1B549C: layer_1, 0x1B54A6: climb_out, 0x1B54D2: climbable_top, 0x1B54D8: climbable,
    0x1B54E0: attack_allowed, 0x1B54F4: exit_when_landed, 0x1B5502: sink_pose, 0x1B557E: launcher,
    0x1B55D8: drag_left, 0x1B55E8: grab_pose, 0x1B56B6: knock_back, 0x1B56F4: sand_dust, 0x1B577C: clear_flag_172,
    0x1B5784: nothing,
    **{address: _progress(flag) for address, flag in PROGRESS_FLAGS.items()},
}
