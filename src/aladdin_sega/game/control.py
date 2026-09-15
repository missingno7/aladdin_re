"""The player's control: walking, the velocity integrator, jumping, throwing apples and the sword.

Five main-loop steps read the pad flags and the sensors the physics left
behind and drive the player's screen offset, velocities and animation
script.  Each button routine is reached through a pointer the game sets
up (FF7DD2 sword, FF7DD6 throw, FF7DDA jump), so the mapping between the
pad bits and the actions is data.

* ``horizontal_control`` (1A9D98): integrate the velocities, then walk
  left / right (speed 3, or 1 while hurt, 2 in the air), crouch, look
  up, and stand; the collapsing-cave debug free-move (FF7273) and the
  carpet ride of level 8 are its two alternatives.
* ``jump_start`` (1A9716): the jump button; holding it for up to ten
  frames keeps adding lift.
* ``throw_input`` (1A9304): the apple button, with a 14-frame cooldown
  and a no-apples sound.
* ``sword_input`` (1A9502): the sword button, a 10-frame cooldown, and a
  pose per state.
"""
from .pad import HELD_RIGHT, HELD_LEFT, HELD_UP, HELD_DOWN, button_a, button_b, button_c, button_start
from . import player as P

SWORD_BUTTON, THROW_BUTTON, JUMP_BUTTON = 0xFF7DD2, 0xFF7DD6, 0xFF7DDA   # longs: the pad routine each action uses
BUTTON_ROUTINES = {0x1B3244: button_b, 0x1B324E: button_c, 0x1B323A: button_a, 0x1B3208: button_start}
DEBUG_FREE_MOVE = 0xFF7273
DYING = 0xFFF0E6
TRANSITION_COUNTDOWN = 0xFFF0E9
CROUCHING, LOOKING_UP = 0xFFF0DE, 0xFFF0DF
PUSHING = 0xFFF0ED                 # TENTATIVE: pressed against a wall / stopped pose pending
STAND_PENDING = 0xFFF101           # TENTATIVE: a stand-up animation is owed after a landing
BLOCKED_RIGHT, BLOCKED_LEFT = 0xFFF0F0, 0xFFF0EF   # TENTATIVE: contact callbacks stop the walk
HURT_TIMER = 0xFFF0EE
STAND_SUPPRESSED_A, STAND_SUPPRESSED_B = 0xFFF0D9, 0xFFF0DA   # TENTATIVE
TILE_CLASS = 0xFFF0C3
JUMP_HOLD = 0xFFF0BF               # frames the jump button has been held (10 = full jump)
THROW_COOLDOWN, SWORD_COOLDOWN = 0xFFF11F, 0xFFEFFF
SWORD_ACTIVE = 0xFFF0D8
APPLES = 0xFFEFE0
CARPET_SPEED = 0xFFF086
CARPET_X = 0xFF7E84                # slot 1's X: the carpet the player rides on level 8
WALL_SOUND, JUMP_SOUND, THROW_SOUND, NO_APPLES_SOUND, SWORD_SOUND = 0x07, 0x02, 0x03, 0x51, 0x01

SCRIPTS = {
    'walk': 0x122006, 'walk_locked': 0x121FD4, 'stand': 0x121D9A, 'stand_locked': 0x121D5A, 'hang_stand': 0x122336,
    'crouch': 0x1222D2, 'crouch_hanging': 0x1223A2, 'look_up': 0x122236, 'stand_up': 0x1232E0, 'push': 0x121FA6,
    'push_release': 0x121FA0, 'wall_stand': 0x121D9A,
    'jump': 0x1220B8, 'jump_run': 0x1220F0, 'jump_stand': 0x1221B0, 'jump_walk': 0x12214E, 'fall': 0x121AD8,
    'throw_crouch': 0x122470, 'throw_air': 0x122504, 'throw_walk': 0x1225A2, 'throw_jump': 0x12262A, 'throw_stand': 0x1223DA,
    'sword_locked': 0x1226E4, 'sword_air': 0x122AF6, 'sword_run_air': 0x12295E, 'sword_run': 0x1228AC,
    'sword_crouch': 0x1227D2, 'sword_up': 0x122A10, 'sword_stand': 0x12271A,
}


def _w(v):
    return v & 0xFFFF


def _sw(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _sb(v):
    v &= 0xFF
    return v - 0x100 if v & 0x80 else v


def _sound(read, services, sound_id):
    if read(P.SOUND_ENABLED, 1):
        services.sound(0, sound_id, flush=True)


def pressed(read, pointer) -> bool:
    """The action's button, through its routine pointer."""
    routine = read(pointer, 4)
    try:
        return BUTTON_ROUTINES[routine](read)
    except KeyError:
        raise LookupError(f'button routine {routine:06X} is not a pad reader') from None


def walk_script(read, write) -> None:
    """1B1FFE."""
    P.set_script(write, SCRIPTS['walk_locked'] if read(P.CAMERA_LOCK, 1) else SCRIPTS['walk'])


def stand_script(read, write) -> None:
    """1B1FAE."""
    if read(P.HANGING, 1) and read(0xFFF0D3, 1) == 0x5E:
        P.set_script(write, SCRIPTS['hang_stand'])
    elif read(P.CAMERA_LOCK, 1):
        P.set_script(write, SCRIPTS['stand_locked'])
    else:
        P.set_script(write, SCRIPTS['stand'])


# -- 1A9B90 ------------------------------------------------------------------------------------
def integrate_velocity(read, write, services) -> None:
    """The velocities move the screen offset by their high byte and decay by 0x28 / 0x3C per frame."""
    vx = _sw(read(P.VELOCITY_X, 2))
    if vx > 0:
        if vx < 0x28 or read(P.WALL_RIGHT, 1):
            write(P.VELOCITY_X, 0, 2)
        else:
            if read(P.SCREEN_X, 2) < 0x130:
                write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) + _sb(read(P.VELOCITY_X, 1))), 2)
            write(P.VELOCITY_X, _w(vx - 0x28), 2)
    elif vx < 0:
        if read(P.WALL_LEFT, 1) or read(P.SCREEN_X, 2) < 0x14 or -vx < 0x28:
            write(P.VELOCITY_X, 0, 2)
        else:
            write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) + _sb(read(P.VELOCITY_X, 1))), 2)
            write(P.VELOCITY_X, _w(vx + 0x28), 2)
    vy = _sw(read(P.VELOCITY_Y, 2))
    if vy == 0:
        return
    if vy > 0:
        if vy < 0x3C:
            write(P.VELOCITY_Y, 0, 2)
            write(P.JUMP_SETTLED, 0xFF, 1)
            return
        write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) + _sb(read(P.VELOCITY_Y, 1))), 2)
        write(P.VELOCITY_Y, _w(vy - 0x3C), 2)
        return
    if read(P.SCREEN_Y, 2) < 0x14:
        write(P.VELOCITY_Y, _w(vy + 0x3C), 2)
        return
    if -vy < 0x3C:
        write(P.VELOCITY_Y, 0, 2)
        write(P.JUMP_SETTLED, 0xFF, 1)
        return
    if read(P.CEILING_BLOCKED, 1):
        _sound(read, services, WALL_SOUND)
        write(P.JUMPING, 0, 1)
        write(P.VELOCITY_Y, 0, 2)
        write(P.JUMP_SETTLED, 0xFF, 1)
        return
    write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) + _sb(read(P.VELOCITY_Y, 1))), 2)
    write(P.VELOCITY_Y, _w(vy + 0x3C), 2)


# -- 1A9D98 ------------------------------------------------------------------------------------
def horizontal_control(read, write, services) -> None:
    if read(DEBUG_FREE_MOVE, 1):
        return _free_move(read, write)
    if read(DYING, 1):
        return
    integrate_velocity(read, write, services)
    for flag in (P.SPECIAL_TILE, P.SPECIAL_TILE_2, P.FROZEN, TRANSITION_COUNTDOWN):
        if read(flag, 1):
            return
    if read(P.LEVEL_INDEX, 1) == 8:
        return _carpet(read, write)
    if read(P.IN_AIR, 1):
        if read(HELD_UP, 1):
            return _look_up(read, write)
        if read(HELD_DOWN, 1):
            return _crouch(read, write)
    if read(HELD_RIGHT, 1):
        return _walk(read, write, right=True)
    if read(HELD_LEFT, 1):
        return _walk(read, write, right=False)
    return _crouch(read, write)


def _hanging_on_ledge(read):
    return read(P.HANGING, 1) and read(0xFFF0D3, 1) == 0x5E


def _walk(read, write, *, right: bool) -> None:
    write(P.FACING, 0 if right else 0xFF, 1)
    if _hanging_on_ledge(read):
        return _crouch(read, write)
    if read(P.IN_AIR, 1):
        return _stop(read, write)
    if read(P.WALL_RIGHT if right else P.WALL_LEFT, 1):
        return _wall_bump(read, write)
    if read(CROUCHING, 1):
        return _crouch(read, write)
    if read(LOOKING_UP, 1):
        return _look_up(read, write)
    screen_x = read(P.SCREEN_X, 2)
    if (screen_x >= 0x130) if right else (screen_x < 0x14):
        return
    if read(P.JUMPING, 1) or not read(P.ON_GROUND, 1):
        speed = read(P.WALK_SPEED, 2) or 2
        write(P.SCREEN_X, _w(screen_x + (speed if right else -speed)), 2)
        return
    if read(BLOCKED_RIGHT if right else BLOCKED_LEFT, 1):
        return _blocked(read, write, right)
    if read(HURT_TIMER, 1):
        return _hurt_walk(read, write, right)
    state = 1 if right else 0xFF
    if read(P.WALKING, 1) != state:
        write(P.WALK_SPEED, 3, 2)
        walk_script(read, write)
        write(P.CAMERA_TARGET_X, 0x70 if right else 0xF0, 2)
        write(P.CAMERA_TARGET_HOLD, 7, 1)
        write(SWORD_COOLDOWN, 0, 1)
        write(THROW_COOLDOWN, 0, 1)
        write(P.WALKING, state, 1)
    speed = read(P.WALK_SPEED, 2)
    write(P.SCREEN_X, _w(screen_x + (speed if right else -speed)), 2)


def _blocked(read, write, right: bool) -> None:
    """1AA238 / 1AA25E: an object in the way: the push pose and no movement."""
    state = 3 if right else 0xFD
    if read(P.WALKING, 1) != state:
        P.set_script(write, SCRIPTS['push'])
        write(P.WALKING, state, 1)
        if not right:
            write(P.CAMERA_TARGET_X, 0x70, 2)
            write(P.CAMERA_TARGET_HOLD, 7, 1)


def _hurt_walk(read, write, right: bool) -> None:
    """1AA294 / 1AA2EC: walking while hurt: speed 1 and the push pose."""
    state = 3 if right else 0xFD
    if read(P.WALKING, 1) != state:
        write(P.WALK_SPEED, 1, 2)
        write(P.CAMERA_TARGET_X, 0x70 if right else 0xF0, 2)
        write(P.CAMERA_TARGET_HOLD, 7, 1)
        P.set_script(write, SCRIPTS['push'])
        write(P.WALKING, state, 1)
        write(P.CAMERA_TARGET_X, 0x70, 2)
        write(P.CAMERA_TARGET_HOLD, 7, 1)
    speed = read(P.WALK_SPEED, 2)
    write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) + (speed if right else -speed)), 2)


def _stop(read, write) -> None:
    """1AA224."""
    write(PUSHING, 0, 1)
    write(P.WALKING, 0, 1)
    write(P.WALK_SPEED, 0, 2)


def _wall_bump(read, write) -> None:
    """1AA196: walking into a wall."""
    write(P.VELOCITY_X, 0, 2)
    write(P.WALK_SPEED, 0, 2)
    write(P.WALKING, 0, 1)
    if read(P.JUMPING, 1):
        return
    if read(TILE_CLASS, 1) == 0xB0 or read(P.HANGING, 1):
        P.set_script(write, SCRIPTS['wall_stand'])
        write(P.CAMERA_TARGET_Y, 0x190, 2)
        write(CROUCHING, 0, 1)
        write(LOOKING_UP, 0, 1)
        return
    if not read(P.ON_GROUND, 1) or read(PUSHING, 1):
        return
    P.set_script(write, SCRIPTS['push'])
    write(PUSHING, 0xFF, 1)
    write(CROUCHING, 0, 1)
    write(LOOKING_UP, 0, 1)
    write(STAND_PENDING, 0, 1)


def _crouch(read, write) -> None:
    """1A9FBE: down held (or nothing held): crouch, or fall through to the look-up / stand logic."""
    if read(P.IN_AIR, 1):
        return _stop(read, write)
    if read(P.CAMERA_LOCK, 1):
        return _stand(read, write)
    if read(HELD_DOWN, 1):
        if read(CROUCHING, 1) or not read(P.ON_GROUND, 1) or read(P.VELOCITY_Y, 2):
            return
        P.set_script(write, SCRIPTS['crouch_hanging'] if _hanging_on_ledge(read) else SCRIPTS['crouch'])
        write(PUSHING, 0, 1)
        write(CROUCHING, 0xFF, 1)
        write(P.WALKING, 0, 1)
        write(STAND_PENDING, 0, 1)
        return
    if read(CROUCHING, 1):
        write(P.CAMERA_TARGET_Y, 0x170, 2)
        write(CROUCHING, 0, 1)
        write(STAND_PENDING, 0, 1)
    return _look_up(read, write)


def _look_up(read, write) -> None:
    """1AA060: up held: look up, or fall through to standing."""
    if _hanging_on_ledge(read):
        return
    if read(P.CAMERA_LOCK, 1):
        return _stand(read, write)
    if read(HELD_UP, 1):
        if not read(P.ON_GROUND, 1) or read(P.VELOCITY_Y, 2) or read(LOOKING_UP, 1):
            return
        if not read(P.IN_AIR, 1):
            P.set_script(write, SCRIPTS['look_up'])
            write(LOOKING_UP, 0xFF, 1)
            write(P.WALKING, 0, 1)
            write(STAND_PENDING, 0, 1)
            return
    elif read(LOOKING_UP, 1):
        write(P.CAMERA_TARGET_Y, 0x170, 2)
        write(LOOKING_UP, 0, 1)
        write(STAND_PENDING, 0, 1)
    return _stand(read, write)


def _stand(read, write) -> None:
    """1AA0EE: nothing held on the ground: stand up, release a push, or stand still."""
    if not read(P.ON_GROUND, 1) or read(P.JUMPING, 1):
        return
    if read(P.HANGING, 1):
        write(STAND_PENDING, 0, 1)
    elif read(STAND_PENDING, 1):
        P.set_script(write, SCRIPTS['stand_up'])
        write(STAND_PENDING, 0, 1)
        write(PUSHING, 0, 1)
        write(P.WALKING, 0, 1)
        return
    write(P.WALK_SPEED, 0, 2)
    if read(PUSHING, 1):
        P.set_script(write, SCRIPTS['push_release'])
        write(PUSHING, 0, 1)
        write(P.CAMERA_TARGET_Y, 0x190, 2)
        return
    if not read(P.WALKING, 1) or read(STAND_SUPPRESSED_A, 1) or read(STAND_SUPPRESSED_B, 1):
        return
    stand_script(read, write)
    write(P.CAMERA_TARGET_Y, 0x190, 2)
    write(PUSHING, 0, 1)
    write(P.WALKING, 0, 1)


def _carpet(read, write) -> None:
    """1A9D18: level 8: the carpet carries the player; up / down steer within the screen."""
    x = _w(read(P.SCREEN_X, 2) + read(CARPET_SPEED, 2))
    write(P.SCREEN_X, x, 2)
    world_x = _w(x + read(P.CAMERA_X, 2))
    write(P.WORLD_X, world_x, 2)
    write(CARPET_X, _w(read(CARPET_X, 2) + read(CARPET_SPEED, 2)), 2)
    write(P.CAMERA_X, _w(world_x - 0x78), 2)
    write(P.SCREEN_X, 0x78, 2)
    if read(HELD_UP, 1):
        if read(P.SCREEN_Y, 2) >= 0x112:
            write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) - 4), 2)
    elif read(HELD_DOWN, 1):
        if read(P.SCREEN_Y, 2) < 0x187:
            write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) + 4), 2)


def _free_move(read, write) -> None:
    """1A9C9A: the debug free move: no player object, the pad moves the view."""
    write(P.SPRITE_FRAME, 0, 4)
    write(0xFF7E40, 0, 1)
    if read(HELD_RIGHT, 1) and read(P.SCREEN_X, 2) < 0x130:
        write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) + 8), 2)
    if read(HELD_LEFT, 1) and read(P.SCREEN_X, 2) >= 0x10:
        write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) - 8), 2)
    if read(HELD_UP, 1) and read(P.SCREEN_Y, 2) >= 0x10:
        write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) - 8), 2)
    if read(HELD_DOWN, 1) and read(P.SCREEN_Y, 2) < 0x1E0:
        write(P.SCREEN_Y, _w(read(P.SCREEN_Y, 2) + 8), 2)


# -- 1A9716 ------------------------------------------------------------------------------------
def jump_start(read, write, services) -> None:
    if read(P.FROZEN, 1) or read(P.LEVEL_INDEX, 1) == 8 or read(P.SPECIAL_TILE, 1) or read(P.SPECIAL_TILE_2, 1):
        return
    if read(P.JUMPING, 1):
        held = read(JUMP_HOLD, 1)
        if held == 0xA:
            return
        write(JUMP_HOLD, held + 1, 1)
        if pressed(read, JUMP_BUTTON):
            write(P.VELOCITY_Y, _w(read(P.VELOCITY_Y, 2) - 0x6C), 2)
            write(PUSHING, 0, 1)
        return
    if not (read(P.IN_AIR, 1) or read(P.ATTACKING, 1) or read(P.ON_GROUND, 1)):
        return
    if not pressed(read, JUMP_BUTTON):
        write(JUMP_HOLD, 0, 1)
        return
    if read(JUMP_HOLD, 1):
        return
    _sound(read, services, JUMP_SOUND)
    write(CROUCHING, 0, 1)
    write(LOOKING_UP, 0, 1)
    write(P.JUMPING, 0xFF, 1)
    write(P.JUMP_SETTLED, 0, 1)
    write(JUMP_HOLD, 1, 1)
    write(P.VELOCITY_Y, 0xFE00, 2)
    if read(P.ATTACK_ENABLED, 1):
        write(P.VELOCITY_Y, 0x400, 2)
        script = SCRIPTS['fall']
    else:
        script = SCRIPTS['jump']
        if not read(P.IN_AIR, 1):
            script = SCRIPTS['jump_run']
            if not read(P.CAMERA_LOCK, 1):
                script = SCRIPTS['jump_stand']
            if read(P.WALKING, 1):
                script = SCRIPTS['jump_run']
                if not read(P.CAMERA_LOCK, 1):
                    script = SCRIPTS['jump_walk']
    P.set_script(write, script)
    write(P.CAMERA_TARGET_Y, 0x170, 2)
    write(P.CAMERA_TARGET_X, 0xB0, 2)
    write(P.CAMERA_TARGET_HOLD, 7, 1)


# -- 1A9304 ------------------------------------------------------------------------------------
def throw_input(read, write, services) -> None:
    if read(P.FROZEN, 1):
        return
    if read(P.ATTACKING, 1) and read(HELD_RIGHT, 2):
        return
    if read(P.IN_AIR, 1) and read(HELD_UP, 2):
        return
    if read(P.LEVEL_INDEX, 1) == 8 or read(P.CAMERA_LOCK, 1) or not read(P.SPRITE_FRAME, 4):
        return
    if read(PUSHING, 1) or read(P.SPECIAL_TILE, 1) or read(P.SPECIAL_TILE_2, 1):
        return
    cooldown = read(THROW_COOLDOWN, 1)
    if not pressed(read, THROW_BUTTON):
        if cooldown:
            write(THROW_COOLDOWN, cooldown - 1, 1)
        return
    if cooldown:
        if cooldown != 1:
            write(THROW_COOLDOWN, cooldown - 1, 1)
        return
    write(THROW_COOLDOWN, 0xE, 1)
    if read(APPLES, 2) == 0x3030:
        _sound(read, services, NO_APPLES_SOUND)
        return
    if read(CROUCHING, 1):
        if not read(P.ON_GROUND, 1):
            return
        P.set_script(write, SCRIPTS['throw_crouch'])
        _sound(read, services, THROW_SOUND)
        return
    if read(P.IN_AIR, 1) or read(P.ATTACKING, 1):
        P.set_script(write, SCRIPTS['throw_air'])
        return
    if read(P.JUMPING, 1) or not read(P.ON_GROUND, 1):
        P.set_script(write, SCRIPTS['throw_jump'])
    elif read(P.WALKING, 1):
        P.set_script(write, SCRIPTS['throw_walk'])
    else:
        P.set_script(write, SCRIPTS['throw_stand'])
    _sound(read, services, THROW_SOUND)


# -- 1A9502 ------------------------------------------------------------------------------------
def sword_input(read, write, services) -> None:
    if read(P.FROZEN, 1) or read(P.LEVEL_INDEX, 1) == 8 or not read(P.SPRITE_FRAME, 4):
        return
    if read(PUSHING, 1) or read(P.SPECIAL_TILE, 1) or read(P.SPECIAL_TILE_2, 1):
        return
    if read(P.ATTACKING, 1) and read(HELD_RIGHT, 2):
        return
    if read(P.IN_AIR, 1) and read(HELD_UP, 2):
        return
    if not pressed(read, SWORD_BUTTON):
        write(SWORD_COOLDOWN, 0, 1)
        return
    cooldown = read(SWORD_COOLDOWN, 1)
    if cooldown:
        if cooldown != 1:
            write(SWORD_COOLDOWN, cooldown - 1, 1)
        return
    if read(SWORD_ACTIVE, 1):
        return
    if read(P.CAMERA_LOCK, 1):
        P.set_script(write, SCRIPTS['sword_locked'])
        write(SWORD_COOLDOWN, 0xA, 1)
        _sound(read, services, SWORD_SOUND)
        return
    if read(P.ATTACKING, 1):
        P.set_script(write, SCRIPTS['sword_air'])
        write(SWORD_COOLDOWN, 0xA, 1)
        return
    if read(P.IN_AIR, 1):
        P.set_script(write, SCRIPTS['sword_air'])
        write(SWORD_COOLDOWN, 0xA, 1)
        _sound(read, services, SWORD_SOUND)
        return
    if read(P.WALKING, 1):
        P.set_script(write, SCRIPTS['sword_run'] if read(P.ON_GROUND, 1) else SCRIPTS['sword_run_air'])
        write(SWORD_COOLDOWN, 0xA, 1)
        return
    if not read(P.ON_GROUND, 1):
        P.set_script(write, SCRIPTS['sword_run_air'])
        write(SWORD_COOLDOWN, 0xA, 1)
        return
    if read(CROUCHING, 1):
        P.set_script(write, SCRIPTS['sword_crouch'])
        write(SWORD_COOLDOWN, 0xA, 1)
        _sound(read, services, SWORD_SOUND)
        return
    P.set_script(write, SCRIPTS['sword_up'] if read(HELD_UP, 1) else SCRIPTS['sword_stand'])
    write(SWORD_COOLDOWN, 0xA, 1)
