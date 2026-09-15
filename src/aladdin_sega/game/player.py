"""The player: fields and the per-frame steps recovered so far.

The player is object slot 0 (FF7E40); its world position is the camera
position plus its screen offset, published every frame to the globals the
collision callbacks read (1A8E0C).  The physics below reads the level's
cell attributes: each map cell word names a 4-byte attribute record at
FFAE84 + word/2 (a ground-height index, the collision class at +2 whose
values above 0xDF are walls, the spawn flag at +3); the ground height for
a sub-cell X comes from the ROM height map at 2FD2 (16 bytes per index,
low six bits the height).

Recovered here: the position publish (1A8E0C), the frame counter
(1A8C16), the wall sensors (1AD632), ground collision and landing
(1AD7B4), the vertical (climb / drop) input (1A986E) and the attack /
throw input (1A99F0).  Horizontal control, the velocity integrator, the
state machine and the camera (1A9D98, 1A9B90, 1A9716, 1A9304, 1A9502,
1AA8FA) are the next steps; their fields are named in
docs/semantic-map.md section 2.
"""
from .pad import HELD_RIGHT, HELD_LEFT, HELD_UP, HELD_DOWN
from .level import MAP_ROW_TABLE, MAP_STRIDE

CAMERA_X, CAMERA_Y = 0xFF7DF6, 0xFF7DF8
SCREEN_X, SCREEN_Y = 0xFF7DFA, 0xFF7DFC      # player offset from the camera (Y carries the 192 plane bias)
WORLD_X, WORLD_Y = 0xFF7E02, 0xFF7E04        # published copies
RECORD_X, RECORD_Y = 0xFF7E42, 0xFF7E44      # the player record's own +02 / +04
CAMERA_TARGET_X, CAMERA_TARGET_Y = 0xFF7DFE, 0xFF7E00   # where the camera wants the player on screen
CAMERA_TARGET_HOLD = 0xFFF167                 # frames the camera keeps a look-up / look-down target
FRAME_COUNTER = 0xFF7E28
SOUND_ENABLED = 0xFFF57D
LEVEL_INDEX = 0xFF7E26
LEVEL_HEIGHT = 0xFF7DBC
MAP_END = 0xFF725C                            # low word of the map buffer's end: probes past it are ignored
FACING = 0xFF7E49                             # 0 right, FF left
SPRITE_FRAME = 0xFF7E54                       # player record +14: zero while the player has no frame (inactive)
VELOCITY_X, VELOCITY_Y = 0xFF7E58, 0xFF7E5A   # player record +18 / +1A
ANIMATION_SCRIPT = 0xFF7E60                   # player record +20
ANIMATION_DELAY = 0xFF7E77                    # player record +37: cleared to restart the script
GROUND_ROW_TABLE = 0xFF98C4                   # the map row table one cell row down (FF9884 + 0x40)
CELL_ATTRIBUTES = 0xFFAE84                    # 4 bytes per cell: [height index] [layer 1 height] [collision] [spawn]
ATTRIBUTE_LAYER = 0xFFF0A4                    # which attribute byte carries the ground for this level
WALL_CLASS = 0xDF                             # collision bytes above this are solid
HEIGHT_MAP = 0x2FD2                           # ROM: 16 height bytes per height index
SOLID_ROW_OFFSET, GROUND_ROW_OFFSET = 0x110, 0x100   # the sensors' base rows relative to the player Y
GRAVITY, TERMINAL_VELOCITY = 0x78, 0x800
HARD_LANDING_FRAMES = 0x28
THROW_VARIANTS = 0x1218D8                     # ROM: throw scripts by (FFF16A >> 2)
FACING_SCRIPTS = 0x121828                     # ROM: scripts by (WORLD_Y >> 2) & 0xF, as the engine's player selector uses them
SCRIPT_HARD_LANDING, SCRIPT_FALLING = 0x121BB6, 0x121AD8
SCRIPT_LAND_IDLE, SCRIPT_LAND_IDLE_FREE, SCRIPT_LAND_WALK, SCRIPT_LAND_RUN = 0x121F74, 0x121F84, 0x121F6A, 0x122080

# state bytes (docs/semantic-map.md section 2; TENTATIVE names carry the address in their comment)
WALK_SPEED = 0xFFF0B0          # word
GROUND_IGNORED = 0xFFF0BD      # TENTATIVE: set while dropping through the ground
JUMPING = 0xFFF0BE
JUMP_SETTLED = 0xFFF0C0        # the vertical velocity ran out (set by the integrator)
ON_GROUND = 0xFFF0C1           # the ground height found under the player (0 = none)
WALL_LEFT, WALL_LEFT_FAR, WALL_LEFT_FARTHER = 0xFFF0C5, 0xFFF0C6, 0xFFF0C7
WALL_RIGHT, WALL_RIGHT_FAR, WALL_RIGHT_FARTHER = 0xFFF0C8, 0xFFF0C9, 0xFFF0CA
CEILING_BLOCKED = 0xFFF0CB
WALKING = 0xFFF0CC
HANGING = 0xFFF0CD
CLIMBABLE = 0xFFF0CE           # TENTATIVE: vertical input allowed (rope / ledge)
CLIMB_UP_BLOCKED = 0xFFF0CF    # TENTATIVE
IN_AIR = 0xFFF0D0
ATTACK_ENABLED = 0xFFF0D6      # TENTATIVE
ATTACKING = 0xFFF0D7
SPECIAL_TILE = 0xFFF0DB
SPECIAL_TILE_2 = 0xFFF0DC
FROZEN = 0xFFF0E7
FALL_TIMER = 0xFFF0EB
LANDING_FLAG = 0xFFF101        # TENTATIVE: cleared on every landing
THROW_COUNTER = 0xFFF16A
CAMERA_LOCK = 0xFFF173


DYING = 0xFFF0E6               # the dying countdown (FF = immediate)
TRANSITION_COUNTDOWN = 0xFFF0E9
INVULNERABLE = 0xFFF0F2
PREVIOUS_CONTACT = 0xFFF0D4
SWORD_ACTIVE = 0xFFF0D8
SWORD_COOLDOWN = 0xFFEFFF
THROW_COOLDOWN = 0xFFF11F
HEALTH, MAX_HEALTH = 0xFFEFFA, 0xFFEFFB
DIFFICULTY = 0xFF7E21
INVINCIBLE = 0xFF7E20          # TENTATIVE: no health loss (cheat / demo)
HURT_SOUND = 0x31
SCRIPT_HURT, SCRIPT_HURT_LOCKED = 0x1226CE, 0x1226B2


def _w(v):
    return v & 0xFFFF


def _sw(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def lose_health(read, write) -> None:
    """1B03F2: one point of health with 40 frames of invulnerability; at zero, the dying countdown."""
    if read(TRANSITION_COUNTDOWN, 1) or read(DYING, 1) or read(INVINCIBLE, 1):
        return
    if not read(HEALTH, 1):
        write(DYING, 0xA, 1)
        return
    if read(INVULNERABLE, 1):
        return
    write(HEALTH, read(HEALTH, 1) - 1, 1)
    write(INVULNERABLE, 0x28, 1)


def _take_hit(read, write, services) -> None:
    """1AE58E: stop, the hurt sound, and up to three health calls (the first grants invulnerability)."""
    write(WALK_SPEED, 0, 2)
    write(WALKING, 0, 1)
    if read(SOUND_ENABLED, 1):
        services.sound(0, HURT_SOUND, flush=True)
    lose_health(read, write)
    if read(DIFFICULTY, 1) == 0:
        return
    lose_health(read, write)
    if read(DIFFICULTY, 1) == 1:
        return
    lose_health(read, write)


def _hurt_locked(read, write) -> None:
    """1AE5EA: hurt during a cutscene: the falling pose, frozen, and the transition in 50 frames."""
    set_script(write, SCRIPT_HURT_LOCKED)
    write(FROZEN, 0xFF, 1)
    write(TRANSITION_COUNTDOWN, 0x32, 1)
    if not read(SWORD_ACTIVE, 1):
        write(SWORD_COOLDOWN, 1, 1)


def hurt(read, write, services) -> None:
    """1AE4F8: the player is hurt by a tile or an object (unless already dying or invulnerable)."""
    for flag in (FROZEN, DYING, TRANSITION_COUNTDOWN, INVULNERABLE):
        if read(flag, 1):
            return
    settled = not (read(JUMPING, 1) or not read(ON_GROUND, 1) or read(IN_AIR, 1) or read(ATTACKING, 1)
                   or read(HANGING, 1) or read(PREVIOUS_CONTACT, 1))
    if settled:
        if read(CAMERA_LOCK, 1):
            return _hurt_locked(read, write)
        if read(WALKING, 1):
            return _take_hit(read, write, services)
        if not (read(SWORD_COOLDOWN, 1) or read(THROW_COOLDOWN, 1)):
            set_script(write, SCRIPT_HURT)
            return _take_hit(read, write, services)
    if read(CAMERA_LOCK, 1):
        return _hurt_locked(read, write)
    return _take_hit(read, write, services)


def publish_position(read, write) -> None:
    """1A8E0C: world = camera + screen offset, into the globals and the player record."""
    x = (read(CAMERA_X, 2) + read(SCREEN_X, 2)) & 0xFFFF
    y = (read(CAMERA_Y, 2) + read(SCREEN_Y, 2)) & 0xFFFF
    write(WORLD_X, x, 2); write(RECORD_X, x, 2)
    write(WORLD_Y, y, 2); write(RECORD_Y, y, 2)


def advance_frame_counter(read, write) -> None:
    """1A8C16: the loop's own frame counter (bit 0 gates the animation and score passes)."""
    write(FRAME_COUNTER, (read(FRAME_COUNTER, 1) + 1) & 0xFF, 1)


def set_script(write, script) -> None:
    write(ANIMATION_SCRIPT, script, 4)
    write(ANIMATION_DELAY, 0, 1)


# -- the level under the player --------------------------------------------------------------
def _solid(read, cursor) -> bool:
    return read(CELL_ATTRIBUTES + 2 + (read(cursor, 2) >> 1), 1) > WALL_CLASS


def _ground_height(read, rom, attributes, cursor, sub_x) -> int:
    index = read(attributes + (read(cursor, 2) >> 1), 1)
    return rom[HEIGHT_MAP + (index << 4) + sub_x] & 0x3F


def wall_sensors(read, write) -> None:
    """1AD632: the six wall sensors and the ceiling sensor around the player's cell."""
    if read(LEVEL_INDEX, 1) == 8:
        return
    write(CEILING_BLOCKED, 0, 1)
    if not read(SPRITE_FRAME, 4):
        return
    top = _w(read(SCREEN_Y, 2) + read(CAMERA_Y, 2) - SOLID_ROW_OFFSET)
    if top & 0x8000 or top >= _w(read(LEVEL_HEIGHT, 2) - 0x30):
        return
    row = read(MAP_ROW_TABLE + _sw(top * 4), 4)
    cursor = row + 2 * (_w(read(CAMERA_X, 2) + read(SCREEN_X, 2)) >> 4)
    stride = _sw(read(MAP_STRIDE, 2))
    on_ground = read(ON_GROUND, 1)
    for near, far, farther, start, side in ((WALL_LEFT, WALL_LEFT_FAR, WALL_LEFT_FARTHER, cursor, -1),
                                             (WALL_RIGHT, WALL_RIGHT_FAR, WALL_RIGHT_FARTHER, cursor + 4, 1)):
        write(near, 0, 1); write(far, 0, 1); write(farther, 0, 1)
        probe = start
        blocked = _solid(read, probe)
        if not blocked:
            probe += stride
            blocked = _solid(read, probe)
            if not blocked:
                if _solid(read, probe + 2 * side):
                    write(far, 0xFF, 1)
                if _solid(read, probe + 4 * side):
                    write(farther, 0xFF, 1)
                probe += stride
                blocked = _solid(read, probe)
                if not blocked and not on_ground:
                    probe += stride
                    blocked = _solid(read, probe)
        if blocked:
            write(near, 0xFF, 1)
    probe = cursor + 2
    if (probe & 0xFFFF) < read(MAP_END, 2) and _solid(read, probe):
        write(CEILING_BLOCKED, 0xFF, 1)


def ground_collision(read, write, rom) -> None:
    """1AD7B4: find the ground under the player, snap to it, land or fall."""
    if read(LEVEL_INDEX, 1) == 8:
        return
    if not read(SPRITE_FRAME, 4):
        write(ON_GROUND, 0, 1)
        return
    if read(HANGING, 1):
        return
    if read(IN_AIR, 1) and read(ATTACKING, 1) and read(SPECIAL_TILE_2, 1) and read(HELD_UP, 1):
        return
    y = _w(read(SCREEN_Y, 2) + read(CAMERA_Y, 2))
    ground_y = _w(y - 16)
    probe_y = _w(y - GROUND_ROW_OFFSET)
    if probe_y & 0x8000 or probe_y >= _w(read(LEVEL_HEIGHT, 2) - 0x20):
        return _airborne(read, write)
    x = _w(read(CAMERA_X, 2) + read(SCREEN_X, 2))
    sub_x = x & 0xF
    cursor = read(GROUND_ROW_TABLE + _sw(probe_y * 4), 4) + 2 * (_w(x + 16) >> 4)
    attributes = CELL_ATTRIBUTES + _sw(read(ATTRIBUTE_LAYER, 2))
    stride = _sw(read(MAP_STRIDE, 2))
    map_end = read(MAP_END, 2)
    height = 0
    for row, probe_x in enumerate((sub_x, sub_x, 2)):     # the third probe reuses the row count as its X (original quirk)
        if (cursor & 0xFFFF) >= map_end:
            return _airborne(read, write)
        height = _ground_height(read, rom, attributes, cursor, probe_x)
        if height:
            break
        cursor += stride
        ground_y = _w(ground_y + 16)
    else:
        write(ON_GROUND, 0, 1)
        return _airborne(read, write)
    if read(GROUND_IGNORED, 1):
        return _airborne(read, write)
    write(ON_GROUND, height, 1)
    ground_y = (ground_y & 0xFF00) | (((ground_y & 0xF0) | ((height - 1) & 0xFF)) & 0xFF)
    ground_offset = _w(ground_y - read(CAMERA_Y, 2))
    current = read(SCREEN_Y, 2)
    if current < ground_offset:
        if read(JUMPING, 1) and not read(JUMP_SETTLED, 1):
            write(ON_GROUND, 0xFF, 1)
            return
        if _w(ground_offset - current) >= 8:
            write(ON_GROUND, 0, 1)
            return _airborne(read, write)
        write(SCREEN_Y, ground_offset, 2)
    elif current > ground_offset:
        if _w(current - ground_offset) > 8:
            write(ON_GROUND, 0, 1)
            return _airborne(read, write)
        write(SCREEN_Y, ground_offset, 2)
    # landed
    if read(JUMPING, 1):
        if not read(JUMP_SETTLED, 1):
            write(ON_GROUND, 0, 1)
            return
        return _land(read, write)
    fallen = read(FALL_TIMER, 1)
    if not fallen:
        return
    write(LANDING_FLAG, 0, 1)
    write(FALL_TIMER, 0, 1)
    if fallen < HARD_LANDING_FRAMES:
        return _land(read, write)
    write(VELOCITY_Y, 0, 2)
    write(CAMERA_TARGET_X, 0xB0, 2)
    write(CAMERA_TARGET_Y, 0x190, 2)
    set_script(write, SCRIPT_HARD_LANDING)
    write(WALKING, 0, 1)
    write(FALL_TIMER, 0, 1)
    write(WALK_SPEED, 0, 2)
    write(LANDING_FLAG, 0, 1)


def _land(read, write) -> None:
    """1AD9D8: the jump ends on the ground; pick the landing script by walking state."""
    write(JUMPING, 0, 1)
    write(VELOCITY_Y, 0, 2)
    if not (read(HELD_LEFT, 1) | read(HELD_RIGHT, 1)):
        write(WALKING, 0, 1)
    if not read(WALKING, 1):
        if read(FROZEN, 1):
            return
        set_script(write, SCRIPT_LAND_IDLE)
        if not read(CAMERA_LOCK, 1):
            set_script(write, SCRIPT_LAND_IDLE_FREE)
        write(FROZEN, 0, 1)
        return
    if read(FROZEN, 1):
        return
    script = SCRIPT_LAND_WALK
    if not read(CAMERA_LOCK, 1):
        script = SCRIPT_LAND_IDLE_FREE if read(WALK_SPEED, 2) & 0xFF == 0 else SCRIPT_LAND_RUN
    set_script(write, script)
    write(FROZEN, 0, 1)


def _airborne(read, write) -> None:
    """1ADAB0: gravity while nothing holds the player up; the falling animation after 40 frames."""
    if read(JUMPING, 1) and not read(JUMP_SETTLED, 1):
        return
    if read(IN_AIR, 1) or read(ATTACKING, 1) or read(SPECIAL_TILE, 1):
        return
    velocity = _w(read(VELOCITY_Y, 2) + GRAVITY)
    if velocity < TERMINAL_VELOCITY:
        write(VELOCITY_Y, velocity, 2)
    if read(FALL_TIMER, 1) != 0xFF:
        write(FALL_TIMER, read(FALL_TIMER, 1) + 1, 1)
    if read(FALL_TIMER, 1) == HARD_LANDING_FRAMES:
        set_script(write, SCRIPT_FALLING)


# -- input ------------------------------------------------------------------------------------
def select_facing_script(read, write, rom) -> None:
    """1A9986: facing and script from the world Y's sub-cell nibble (the engine's player selector does the same)."""
    if read(FROZEN, 1):
        return
    write(FACING, 0, 1)
    index = ((read(WORLD_Y, 2) & 0xFF) >> 2) & 0xF
    if index >= 8:
        write(FACING, 0xFF, 1)
    set_script(write, int.from_bytes(rom[FACING_SCRIPTS + 4 * index:FACING_SCRIPTS + 4 * index + 4], 'big'))


def _select_facing_script_odd_frames(read, write, rom) -> None:
    """1A997A: the same, only on odd frames."""
    if read(FRAME_COUNTER, 1) & 1:
        select_facing_script(read, write, rom)


def snap_x(read, write) -> None:
    """1A99C6: centre the player in its cell horizontally and reset the camera target."""
    write(SCREEN_X, _w(((read(WORLD_X, 2) & 0xFFF0) | 8) - read(CAMERA_X, 2)), 2)
    write(CAMERA_TARGET_X, 0xB0, 2)
    write(CAMERA_TARGET_HOLD, 0, 1)


def snap_y(read, write) -> None:
    """1A9B6C: align the player to its cell vertically."""
    write(SCREEN_Y, _w(((read(WORLD_Y, 2) & 0xFFF0) | 4) - read(CAMERA_Y, 2)), 2)
    write(CAMERA_TARGET_X, 0xB0, 2)


def vertical_input(read, write, rom) -> None:
    """1A986E: up / down on something climbable; the in-air flag reports the result."""
    if not read(CLIMBABLE, 1):
        write(IN_AIR, 0, 1)
        return
    velocity = _sw(read(VELOCITY_Y, 2))
    if velocity <= 0:
        if not read(JUMPING, 1):
            return _vertical_input_grounded(read, write, rom)
        if not read(JUMP_SETTLED, 1):
            write(IN_AIR, 0, 1)
            return
    if read(CEILING_BLOCKED, 1):
        write(IN_AIR, 0, 1)
        return
    select_facing_script(read, write, rom)
    write(VELOCITY_X, 0, 2); write(VELOCITY_Y, 0, 2); write(WALK_SPEED, 0, 2)
    write(JUMPING, 0, 1); write(FALL_TIMER, 0, 1); write(IN_AIR, 0xFF, 1); write(WALKING, 0, 1)
    snap_x(read, write)


def _vertical_input_grounded(read, write, rom) -> None:
    if read(FROZEN, 1):
        write(IN_AIR, 0xFF, 1)
        return
    if read(FALL_TIMER, 1):
        _select_facing_script_odd_frames(read, write, rom)
        write(FALL_TIMER, 0, 1)
    if read(HELD_UP, 1):
        if read(CEILING_BLOCKED, 1) or read(CLIMB_UP_BLOCKED, 1):
            write(IN_AIR, 0xFF, 1)
            return
        write(SCREEN_Y, _w(read(SCREEN_Y, 2) - 1), 2)
        if read(FRAME_COUNTER, 1) & 1:
            write(SCREEN_Y, _w(read(SCREEN_Y, 2) - 1), 2)
        write(CAMERA_TARGET_Y, 0x190, 2)
    elif read(HELD_DOWN, 1):
        if read(ON_GROUND, 1):
            write(IN_AIR, 0, 1)
            return
        write(SCREEN_Y, _w(read(SCREEN_Y, 2) + 2), 2)
        write(CAMERA_TARGET_Y, 0x150, 2)
    else:
        write(IN_AIR, 0xFF, 1)
        return
    write(CAMERA_TARGET_HOLD, 0, 1)
    _select_facing_script_odd_frames(read, write, rom)
    snap_x(read, write)
    write(IN_AIR, 0xFF, 1)


def throw_script(read, write, rom) -> None:
    """1A9B38: the throw animation variant from the throw counter; walking speed 2."""
    if read(FROZEN, 1):
        return
    index = read(THROW_COUNTER, 1) & 0xFC
    set_script(write, int.from_bytes(rom[THROW_VARIANTS + index:THROW_VARIANTS + index + 4], 'big'))
    write(WALK_SPEED, 2, 2)


def attack_input(read, write, rom) -> None:
    """1A99F0: the attack / throw button; the attacking flag reports the result."""
    if not read(ATTACK_ENABLED, 1):
        write(ATTACKING, 0, 1)
        return
    if read(VELOCITY_Y, 2) & 0x8000:
        write(ATTACKING, 0, 1)
        return
    if read(JUMPING, 1):
        if not read(JUMP_SETTLED, 1):
            write(ATTACKING, 0, 1)
            return
        throw_script(read, write, rom)
        write(VELOCITY_X, 0, 2); write(VELOCITY_Y, 0, 2); write(WALK_SPEED, 0, 2)
        write(JUMPING, 0, 1); write(FALL_TIMER, 0, 1); write(ATTACKING, 0xFF, 1); write(WALKING, 0, 1)
        snap_y(read, write)
        return
    write(VELOCITY_Y, 0, 2)
    if not read(FROZEN, 1):
        if read(FALL_TIMER, 1):
            throw_script(read, write, rom)
            write(FALL_TIMER, 0, 1)
        held = read(HELD_LEFT, 1) or read(HELD_RIGHT, 1)
        if held:
            write(FACING, 0xFF if read(HELD_LEFT, 1) else 0, 1)
            counter = (read(THROW_COUNTER, 1) + 1) & 0xFF
            write(THROW_COUNTER, 0 if counter >= 0x28 else counter, 1)
            throw_script(read, write, rom)
    snap_y(read, write)
    if read(HELD_UP, 1):
        if read(CAMERA_TARGET_Y, 2) != 0x1B0:
            write(CAMERA_TARGET_Y, 0x1B0, 2)
            write(CAMERA_TARGET_HOLD, 7, 1)
    elif read(HELD_DOWN, 1):
        if read(CAMERA_TARGET_Y, 2) != 0x130:
            write(CAMERA_TARGET_Y, 0x130, 2)
            write(CAMERA_TARGET_HOLD, 7, 1)
    else:
        write(CAMERA_TARGET_X, 0xB0, 2)
        write(CAMERA_TARGET_Y, 0x150, 2)
        write(CAMERA_TARGET_HOLD, 0, 1)
    write(ATTACKING, 0xFF, 1)
