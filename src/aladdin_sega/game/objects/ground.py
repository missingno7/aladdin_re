"""Objects against the level (1ADB5C): landing on the ground, bouncing, leaving the map.

Every active record in slots 1..31 is probed against the same cell
attributes the player uses (see :mod:`aladdin_sega.game.player`).  Two
behaviours are selected by the record's flags:

* flags3c bit 3: the object dies inside solid ground (a thrown apple, a
  falling pot) -- its cell is probed once, on both height layers and the
  collision class, and a hit retires it through 1ABE8A;
* otherwise, when flags6 bit 0 marks it as ground-bound and it is not
  moving up, three cell rows below it are probed for a ground height; the
  first hit snaps its Y to the ground, records the ground's collision class
  at +3D and raises flags7 bit 4 ("landed"); flags3c bit 4 makes it bounce
  (half the velocity, reversed, a bounce sound) instead of stopping, and a
  slope table in ROM (683E) turns it to face downhill.  No ground and no
  float flag (flags6 bit 7) means gravity.  Past the level's bottom or the
  map's end the object is switched from ground-bound to "gone" (flags6
  bits 0 and 6).
"""
from .record import RECORD_TABLE, RECORD_SIZE, RecordView
from .script_engine import Engine
from .lifecycle import initialize
from ..player import LEVEL_HEIGHT, MAP_END, CELL_ATTRIBUTES, HEIGHT_MAP, WALL_CLASS, FRAME_COUNTER
from ..level import MAP_ROW_TABLE, MAP_STRIDE

LAST_GROUND_INDEX = 0xFFF10D       # the height index of the last cell an object was probed on
SLOPE_TABLE = 0x683E               # ROM: per height index, bit 7 = the slope faces left
BOUNCE_SOUND = 0x50
SPLASH_KIND = 0x31                 # objects of this kind bounce silently
SOUND_ENABLED = 0xFFF57D
APPLE_KIND = 0x2D                  # TENTATIVE: the thrown apple; it splats with its own sound
SPLAT_TEMPLATES = {APPLE_KIND: 0x1B7E40}
SPLAT_TEMPLATE = 0x1B792C
APPLE_SPLAT_SOUND, HIT_SOUND, SPLAT_SOUND = 0x21, 0x03, 0x22
TEMPLATE_SIZE = 19


def _w(v):
    return v & 0xFFFF


def _sw(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _height(rom, index, sub_x):
    return rom[HEIGHT_MAP + (index << 4) + sub_x] & 0x3F


def object_level_collision(read, write, rom, services, memory) -> None:
    engine = Engine(memory, services)
    level_height = read(LEVEL_HEIGHT, 2)
    map_end = read(MAP_END, 2)
    stride = _sw(read(MAP_STRIDE, 2))
    for slot in range(1, 32):
        record = RECORD_TABLE + RECORD_SIZE * slot
        kind = read(record, 1)
        if not kind:
            continue
        write(record + 7, read(record + 7, 1) & ~0x10, 1)
        y = read(record + 4, 2)
        x = read(record + 2, 2)
        sub_x = x & 0xF
        if read(record + 0x3C, 1) & 0x08:
            if not read(record + 0x14, 4) or _w(level_height + 0xE0) < y:
                continue
            cursor = read(MAP_ROW_TABLE + _sw(_w(y - 0xF0) * 4), 4) + 2 * (_w(x + 16) >> 4)
            if (cursor & 0xFFFF) >= map_end:
                _gone(read, write, record)
                continue
            attributes = CELL_ATTRIBUTES + (read(cursor, 2) >> 1)
            if (_height(rom, read(attributes, 1), sub_x) or _height(rom, read(attributes + 1, 1), sub_x)
                    or read(attributes + 2, 1) > WALL_CLASS):
                engine.release(RecordView(record, read, write))
                _splat(read, write, rom, services, slot, record)
            continue
        flags6 = read(record + 6, 1)
        if not flags6 & 0x01 or read(record + 0x1A, 2) & 0x8000 or not read(record + 0x14, 4):
            continue
        write(record + 0x3D, 0, 1)
        if _w(level_height + 0xC8) < y:
            _gone(read, write, record)
            continue
        ground_y = _w(y - 16)
        cursor = read(MAP_ROW_TABLE + _sw(_w(y - 0xF0) * 4), 4) + 2 * (_w(x + 16) >> 4)
        height = 0
        for _ in range(3):
            if (cursor & 0xFFFF) >= map_end:
                _gone(read, write, record)
                break
            cell = read(cursor, 2) >> 1
            index = read(CELL_ATTRIBUTES + cell, 1)
            write(LAST_GROUND_INDEX, index, 1)
            height = _height(rom, index, sub_x)
            if height:
                break
            cursor += stride
            ground_y = _w(ground_y + 16)
        else:
            if not flags6 & 0x80:
                write(record + 0x1A, _w(read(record + 0x1A, 2) + 0x78), 2)
            continue
        if not height:
            continue
        write(record + 0x3D, read(CELL_ATTRIBUTES + cell + 2, 1), 1)
        if read(record + 0x3C, 1) & 0x10:
            write(record + 9, 0xFF if rom[SLOPE_TABLE + index] & 0x80 else 0, 1)
            write(record + 0x1A, _w(-(read(record + 0x1A, 2) >> 1)), 2)
            if kind != SPLASH_KIND:
                if read(SOUND_ENABLED, 1):
                    services.sound(slot, BOUNCE_SOUND, flush=False)
                if read(SOUND_ENABLED, 1):
                    services.sound(slot, BOUNCE_SOUND, flush=True)
        else:
            write(record + 0x1A, 0, 2)
        write(record + 4, _w((ground_y & 0xFFF0) + ((height - 1) & 0xFF)), 2)
        write(record + 7, read(record + 7, 1) | 0x10, 1)


def _gone(read, write, record) -> None:
    """1ADE10: the object is past the map: no longer ground-bound, flagged gone."""
    write(record + 6, (read(record + 6, 1) & ~0x01) | 0x40, 1)


def _splat(read, write, rom, services, slot, record) -> None:
    """1ABE8A: an object that entered solid ground becomes its splat effect, facing by the frame clock."""
    kind = read(record, 1)
    if kind in SPLAT_TEMPLATES:
        if read(SOUND_ENABLED, 1):
            services.sound(slot, APPLE_SPLAT_SOUND, flush=True)
        template = SPLAT_TEMPLATES[kind]
    else:
        if read(SOUND_ENABLED, 1):
            services.sound(slot, HIT_SOUND, flush=False)
        if read(SOUND_ENABLED, 1):
            services.sound(slot, SPLAT_SOUND, flush=True)
        template = SPLAT_TEMPLATE
    for address, value in initialize(record, rom[template:template + TEMPLATE_SIZE]):
        write(address, value, 1)
    if read(FRAME_COUNTER, 1) & 0x02:
        write(record + 9, 0xFF, 1)
