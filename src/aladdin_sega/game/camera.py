"""The camera (1AA8FA): it eases toward where the player should sit on screen.

The player's target screen position (FF7DFE / FF7E00) is set by the
control code (looking up or down moves it); the distance between the
player's screen offset and that target indexes two ROM tables of step
sizes (2A52 horizontally, 2BA4 vertically), so the camera accelerates
with distance.  Every step moves the camera and the player's screen
offset in opposite directions, adds to the strip debt the map code pays
off (FFF0B2 / FFF0B4) and raises the strip flag for the edge that was
uncovered.  The level's width / height (FF7DB8 / FF7DBC) and a 17-pixel
margin at the origin bound it; FFF167 holds it still for a few frames
after a look-up / look-down, and FFF173 locks it for cutscenes.
"""
from .player import (SCREEN_X, SCREEN_Y, CAMERA_X, CAMERA_Y, CAMERA_TARGET_X, CAMERA_TARGET_Y,
                     CAMERA_TARGET_HOLD, CAMERA_LOCK, LEVEL_HEIGHT)
from .level import (WINDOW_X, WINDOW_Y, COLUMN_DEBT, ROW_DEBT,
                    STRIP_LEFT, STRIP_RIGHT, STRIP_TOP, STRIP_BOTTOM)

LEVEL_WIDTH = 0xFF7DB8
STEPS_X, STEPS_Y = 0x2A52, 0x2BA4     # ROM: step size by distance from the target
ORIGIN_MARGIN = 0x11
RIGHT_MARGIN, BOTTOM_MARGIN = 0x161, 0xF1


def _w(v):
    return v & 0xFFFF


def _sw(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _shift(read, write, screen, camera, debt, flag, step, toward_origin: bool) -> None:
    sign = -1 if toward_origin else 1
    write(screen, _w(read(screen, 2) - sign * step), 2)
    write(camera, _w(read(camera, 2) + sign * step), 2)
    write(debt, _w(read(debt, 2) + sign * step), 2)
    write(flag, 0xFF, 1)


def follow(read, write, rom) -> None:
    hold = read(CAMERA_TARGET_HOLD, 1)
    if hold:
        write(CAMERA_TARGET_HOLD, hold - 1, 1)
        return
    if read(CAMERA_LOCK, 1):
        return
    screen_x, target_x = read(SCREEN_X, 2), read(CAMERA_TARGET_X, 2)
    distance = _w(screen_x - target_x)
    if distance:
        if screen_x < target_x:
            step = rom[STEPS_X + _sw(-distance)]
            if step and read(WINDOW_X, 2) >= ORIGIN_MARGIN:
                _shift(read, write, SCREEN_X, CAMERA_X, COLUMN_DEBT, STRIP_LEFT, step, True)
        else:
            step = rom[STEPS_X + _sw(distance)]
            if step and _w(read(WINDOW_X, 2) + read(COLUMN_DEBT, 2) + step) < _w(read(LEVEL_WIDTH, 2) - RIGHT_MARGIN):
                _shift(read, write, SCREEN_X, CAMERA_X, COLUMN_DEBT, STRIP_RIGHT, step, False)
    distance = _w(read(SCREEN_Y, 2) - read(CAMERA_TARGET_Y, 2))
    if distance & 0x8000:
        step = rom[STEPS_Y + _sw(-distance)]
        if read(WINDOW_Y, 2) >= ORIGIN_MARGIN:
            _shift(read, write, SCREEN_Y, CAMERA_Y, ROW_DEBT, STRIP_TOP, step, True)
    elif distance:
        step = rom[STEPS_Y + _sw(distance)]
        if _w(read(WINDOW_Y, 2) + read(ROW_DEBT, 2) + step) < _w(read(LEVEL_HEIGHT, 2) - BOTTOM_MARGIN):
            _shift(read, write, SCREEN_Y, CAMERA_Y, ROW_DEBT, STRIP_BOTTOM, step, False)
