"""Contact callbacks: what happens when the player (or a thrown apple) touches an object.

The scans in :mod:`aladdin_sega.game.objects.contact_scan` dispatch by the
struck object's kind through the ROM tables at 1CBE (player) and 1EBA
(projectiles).  The callbacks below are keyed by their ROM address, so
kinds that share a routine share a function.  Their vocabulary is small:

* hurt the player (:func:`aladdin_sega.game.player.hurt`) unless the sword
  is active, in which case the enemy takes a hit: lose a hit point and
  play its hit script, or die -- score, retire, and the smoke puff
  (template 1B7940) or a kind-specific effect in its place;
* collectibles: apples, gems, health, lives, progress flags, then the
  sparkle (template 1B7ABC) and 150 points;
* platforms: snap the player's screen Y to the object when close;
* ropes (kinds 6E/6F/71/72): grab, hang and swing;
* special objects: pushable blocks, springs, the shop keeper.

An address that is not here is reported by the scan as a gap.
"""
from .record import RECORD_TABLE, RECORD_SIZE, RecordView
from .lifecycle import initialize
from .script_engine import Engine
from .ground import _splat
from .contact_scan import (PLAYER_CONTACTS, PROJECTILE_CONTACTS, CONTACT_CANCEL, PLAYER_BOX_LEFT, HURT_TIMER,
                           INVULNERABLE, CONTACT)
from ..pad import HELD_LEFT, HELD_RIGHT, HELD_UP
from ..rng import SEED_ADDRESS, advance_rng
from .. import player as P
from .. import hud
from .. import video
from ..control import CROUCHING, PUSHING, BLOCKED_LEFT, BLOCKED_RIGHT

PUFF, SPARKLE, DUST, SPLASH, HIT_TEMPLATE, GEM_DROP = 0x1B7940, 0x1B7ABC, 0x1B7CC4, 0x1B7E40, 0x1B7CD8, 0x1B8368
TEMPLATE_SIZE = 19
SPAWN_FLAGS = 0xFFAE87
SHOP_LATCH = 0xFFF114
LIVES, CONTINUES = 0xFF7E3C, 0xFF7E3F
ROPE_HOLD = 0xFFF103
LAMP_HITS = 0xFFF125
SCRIPT_SELECTS = {}


class ContactFrameGap(Exception):
    """A callback needs a nested frame (the sword clash flash waits for VBlank)."""


def _w(v):
    return v & 0xFFFF


def _sound(read, services, sound_id, flush=True, slot=0):
    if read(P.SOUND_ENABLED, 1):
        services.sound(slot, sound_id, flush=flush)


def _record(slot):
    return RECORD_TABLE + RECORD_SIZE * slot


def _find_free(read, start, count, direction=1):
    for i in range(count):
        address = start + direction * RECORD_SIZE * i
        if not read(address, 1):
            return address
    return None


def _template(write, rom, record, template):
    for address, value in initialize(record, rom[template:template + TEMPLATE_SIZE]):
        write(address, value, 1)


def _spawn_at(read, write, rom, template, record, x, y):
    _template(write, rom, record, template)
    write(record + 2, x, 2)
    write(record + 4, y, 2)


def _engine(memory, services):
    return Engine(memory, services)


def _view(record, read, write):
    return RecordView(record, read, write)


def _release(memory, services, record):
    _engine(memory, services).release(_view(record, memory.read, memory.write))


def _retire(memory, services, record):
    _engine(memory, services).retire(_view(record, memory.read, memory.write))


def _become(memory, services, record, template):
    """kind = 0, VRAM released, then the template (the puff or another effect) in the same record."""
    memory.write(record, 0, 1)
    _release(memory, services, record)
    _template(memory.write, memory.rom, record, template)


def _score(read, write, record):
    hud.add_points(read, write, read(record + 8, 1))


def _restore_spawn_flag(read, write, record):
    """1AE6DE: put the object's spawn flag back on its map cell."""
    flag = read(record + 0x34, 1)
    if flag:
        write(SPAWN_FLAGS + read(record + 0x32, 2), flag, 1)


def _player_side_ok(read, record):
    """The player must face the object: it lies on the facing side."""
    x = read(P.WORLD_X, 2)
    return x >= read(record + 2, 2) if read(P.FACING, 1) else x < read(record + 2, 2)


def _reselect_player_script(memory, services):
    engine = _engine(memory, services)
    P.set_script(memory.write, engine.player_select(_view(RECORD_TABLE, memory.read, memory.write)))


def _random(read, write):
    seed, roll = advance_rng(read(SEED_ADDRESS, 4))
    write(SEED_ADDRESS, seed, 4)
    return roll


def _copy_record(read, write, source, destination):
    for i in range(0, RECORD_SIZE, 2):
        write(destination + i, read(source + i, 2), 2)


def _clear_map_cells(read, write, classes):
    """1AC386 / 1AC3BC: erase every map cell whose collision class is one of ``classes``."""
    for i in range(0x3840):
        cursor = 0xFF0000 + 2 * i
        if read(P.CELL_ATTRIBUTES + 2 + (read(cursor, 2) >> 1), 1) in classes:
            write(cursor, 0, 2)


# ---- player contacts --------------------------------------------------------------------------
def cancel(read, write, rom, services, memory, record):
    """1AE6B4: refuse the platform landing."""
    write(CONTACT_CANCEL, 0xFF, 1)


def nothing(read, write, rom, services, memory, record):
    pass


def bottle_pickup(read, write, rom, services, memory, record):
    """1AE64C (kind 43): the object becomes kind 8A at the player's screen X with script 124454."""
    if not read(P.ON_GROUND, 1):
        return
    saved = read(P.SCREEN_X, 2)
    write(P.SCREEN_X, _w(read(record + 2, 2) - read(P.CAMERA_X, 2)), 2)
    write(record, 0x8A, 1)
    write(record + 0x34, 0xFF, 1)
    write(record + 0x20, 0x124454, 4)
    write(record + 0x37, 0, 1)
    cam_x, cam_y = read(P.CAMERA_X, 2), read(P.CAMERA_Y, 2)
    write(0xFF7E0A, _w((cam_x & 0xF) + read(P.SCREEN_X, 2)), 2)
    write(0xFF7E0C, _w((cam_y & 0xF) + read(P.SCREEN_Y, 2)), 2)
    write(0xFF7E0E, cam_x & 0xFFF0, 2)
    write(0xFF7E10, cam_y & 0xFFF0, 2)
    write(0xFFF154, 0xFF, 1)
    _sound(read, services, 0x63)
    write(P.SCREEN_X, saved, 2)


def pushable(read, write, rom, services, memory, record):
    """1AE722: a block the player pushes against."""
    if read(P.WORLD_X, 2) < read(record + 2, 2):
        held, blocked, wall = HELD_RIGHT, BLOCKED_RIGHT, P.WALL_RIGHT
    else:
        held, blocked, wall = HELD_LEFT, BLOCKED_LEFT, P.WALL_LEFT
    if not read(held, 1):
        return
    write(HURT_TIMER, 4, 1)
    write(PUSHING, 0xFF, 1)
    write(blocked, 0xFF, 1)
    if read(P.VELOCITY_Y, 1) or read(P.JUMPING, 1):
        write(wall, 0xFF, 1)


DEATH_SCRIPTS_1AE872 = {0x1E: 0x1234BE, 0x21: 0x12350C, 0x1F: 0x12384A, 0x22: 0x12387A}
PARRY_SCRIPTS = {0x1E: 0x1234F6, 0x21: 0x123544, 0x1F: 0x1238F8, 0x22: 0x1238AA}


def sword_enemy(read, write, rom, services, memory, record):
    """1AE796 (kinds 1E/1F/21/22): a sword-fighting enemy: hit it from the front, or be hurt by its parry."""
    if _player_side_ok(read, record) and read(P.SWORD_ACTIVE, 1):
        if read(record + 0x3C, 1) & 0x20:
            return _sword_clash(read, write, rom, services, record)
        kind = read(record, 1)
        if kind in DEATH_SCRIPTS_1AE872:
            write(record + 0x20, DEATH_SCRIPTS_1AE872[kind], 4)
            write(record, 0x84, 1)
            write(record + 0x37, 0, 1)
            write(record + 0xA, 0, 4)
            write(record + 0x36, 0, 1)
        _enemy_hit_or_die(read, write, memory, services, record)
        return
    if read(record + 0x3C, 1) & 0x20:
        P.hurt(read, write, services)


def _sword_clash(read, write, rom, services, record):
    """1AE7CA: the enemy parries: a white flash for one frame, both fighters recoil."""
    vdp = services.state.vdp
    video.flash_white(vdp)
    services.vblank()
    video.restore_palettes(read, write, rom, vdp)
    if read(P.ON_GROUND, 1) and not read(P.ATTACKING, 1):
        P.set_script(write, 0x1227C2 if read(P.SWORD_ACTIVE, 1) == 1 else 0x1228A0)
    write(P.SWORD_ACTIVE, 0, 1)
    write(record + 0x3C, read(record + 0x3C, 1) & ~0x20, 1)
    write(record + 0x37, 0, 1)
    write(P.WALKING, 0, 1)
    script = PARRY_SCRIPTS.get(read(record, 1))
    if script:
        write(record + 0x20, script, 4)


def _enemy_hit_or_die(read, write, memory, services, record):
    """1AE8F0: on normal / hard with hit points left the enemy loses one; otherwise it dies."""
    if read(P.DIFFICULTY, 1) != 0 and read(record + 1, 1):
        write(record + 1, read(record + 1, 1) - 1, 1)
        _sound(read, services, 0x41)
        write(P.WALKING, 0, 1)
        write(P.WALK_SPEED, 0, 2)
        _reselect_player_script(memory, services)
        write(P.SWORD_ACTIVE, 0, 1)
        write(record + 0x3C, read(record + 0x3C, 1) & ~0x20, 1)
        return
    _score(read, write, record)
    _retire(memory, services, record)
    _become(memory, services, record, PUFF)


def sword_hit(read, write, rom, services, memory, record) -> None:
    """1AEC00: the generic sword hit on an enemy in front of the player."""
    if not read(P.SWORD_ACTIVE, 1) or not _player_side_ok(read, record):
        return
    kind = read(record, 1)
    if read(record + 1, 1):
        write(record + 1, read(record + 1, 1) - 1, 1)
        _sound(read, services, 0x08)
        _reselect_player_script(memory, services)
        write(P.WALK_SPEED, 0, 2)
        write(P.WALKING, 0, 1)
        if kind == 0x13:
            write(record, 0x84, 1)
            write(record + 0x20, 0x12474C, 4)
            write(record + 0x37, 0, 1)
            write(record + 0xA, 0, 4)
            write(record + 0x36, 0, 1)
            _sound(read, services, 0x6A)
        elif kind == 0x18:
            write(record, 0x84, 1)
            write(record + 0x20, 0x1248B6, 4)
            write(record + 0x37, 0, 1)
        return
    _score(read, write, record)
    if kind == 0x13:
        return _drop_gem(read, write, rom, services, memory, record)
    if kind in (0x10, 0x11):
        write(P.TRANSITION_COUNTDOWN, 0x20, 1)
    _retire(memory, services, record)
    _become(memory, services, record, PUFF)


def _drop_gem(read, write, rom, services, memory, record):
    """1AF1AC: the kind-13 enemy leaves a dust puff and drops a gem (1B8368) with its jingle."""
    _become(memory, services, record, DUST)
    drop = _find_free(read, _record(24), 24, -1)
    if drop is None:
        return
    _spawn_at(read, write, rom, GEM_DROP, drop, read(record + 2, 2), _w(read(record + 4, 2) - 0x20))
    write(drop + 9, 0xFF, 1)
    write(0xFFF124, 8, 1)
    services.sound_command(0x16)
    if read(0xFFF57F, 1):
        services.sound(0, 0x14, flush=True)


def sword_or_hurt(read, write, rom, services, memory, record):
    """1AE9C6 (kinds 05/0E/13/1D/20/2A...): sword hit, otherwise the player is hurt."""
    sword_hit(read, write, rom, services, memory, record)
    if not read(P.SWORD_ACTIVE, 1):
        P.hurt(read, write, services)


def sword_only(read, write, rom, services, memory, record):
    """1AE9DA (kinds 06/0F)."""
    sword_hit(read, write, rom, services, memory, record)


def apple_thief(read, write, rom, services, memory, record):
    """1AE978 (kind 15): sword-hittable; otherwise it steals three apples and flees as kind 14."""
    sword_hit(read, write, rom, services, memory, record)
    if read(P.SWORD_ACTIVE, 1):
        return
    for _ in range(3):
        hud.remove_apple(read, write)
    write(record, 0x14, 1)
    P.set_script(write, P.SCRIPT_HURT)


def dust_on_sword(read, write, rom, services, memory, record):
    """1AE9A8 (kind 0C): the sword turns it into dust."""
    if read(P.SWORD_ACTIVE, 1):
        _become(memory, services, record, DUST)


def _flag_on_sword(flag, clear_classes=None):
    def handler(read, write, rom, services, memory, record):
        """1AE9E0 / 1AEA00 / 1AEA24: the sword breaks it: a progress flag, the puff (and map cells cleared)."""
        if not read(P.SWORD_ACTIVE, 1):
            return
        if clear_classes:
            _clear_map_cells(read, write, clear_classes)
        write(flag, 0xFF, 1)
        _retire(memory, services, record)
        _template(write, rom, record, PUFF)
    return handler


def lamp_or_pot(read, write, rom, services, memory, record):
    """1AEA48: hurts unless the sword is out; kind 19 sounds; otherwise ten hits break it."""
    if not read(P.SWORD_ACTIVE, 1):
        return P.hurt(read, write, services)
    if read(record, 1) == 0x19:
        if read(INVULNERABLE, 1):
            return
        _sound(read, services, 0x21)
        return P.hurt(read, write, services)
    if not _player_side_ok(read, record):
        return
    hits = read(LAMP_HITS, 1) + 1
    write(LAMP_HITS, hits, 1)
    if hits < 0xA:
        write(record, 0x84, 1)
        write(record + 0x20, 0x1248B6, 4)
        write(record + 0x37, 0, 1)
        write(record + 0xA, 0, 4)
        write(record + 0x36, 0, 1)
        _sound(read, services, 0x08)
        _reselect_player_script(memory, services)
        write(P.WALK_SPEED, 0, 2)
        write(P.WALKING, 0, 1)
        write(P.SWORD_ACTIVE, 0, 1)
        return
    write(record, 0x84, 1)
    _release(memory, services, record)
    _template(write, rom, record, DUST)
    write(0xFFF112, 0xFF, 1)
    _score(read, write, record)
    services.sound_command(0x16)
    if read(0xFFF57F, 1):
        services.sound(0, 0x23, flush=True)


def hurt_unless_armed(read, write, rom, services, memory, record):
    """1AEB7C."""
    if read(P.FROZEN, 1) or read(P.SWORD_ACTIVE, 1) or read(INVULNERABLE, 1):
        return
    write(P.WALKING, 0, 1)
    P.hurt(read, write, services)


def _hurt_when_centred(read, write, services, record):
    """1AEBDC: with the sword out only a hit in the object's middle 16 pixels hurts."""
    if read(P.SWORD_ACTIVE, 1):
        left = read(PLAYER_BOX_LEFT, 2)
        edge = _w(read(record + 2, 2) + 8)
        if left >= edge or left < _w(edge - 0x10):
            return
    P.hurt(read, write, services)


def deadly_centre(read, write, rom, services, memory, record):
    """1AEBDC."""
    _hurt_when_centred(read, write, services, record)


def deadly_or_cutscene(read, write, rom, services, memory, record):
    """1AEBA4: in a cutscene the level-end pose; otherwise instant dying, then the centred hurt check."""
    if read(P.CAMERA_LOCK, 1):
        P.set_script(write, P.SCRIPT_HURT_LOCKED)
        write(P.FROZEN, 0xFF, 1)
        if not read(P.SWORD_ACTIVE, 1):
            write(P.SWORD_COOLDOWN, 1, 1)
        return
    write(P.DYING, 1, 1)
    _hurt_when_centred(read, write, services, record)


def stomp_or_hurt(read, write, rom, services, memory, record):
    """1AED24: landing on it from above bounces the player and kills it; otherwise hurt."""
    if not read(P.ON_GROUND, 1) and read(P.WORLD_Y, 2) < read(record + 4, 2):
        write(P.VELOCITY_Y, 0xFC00, 2)
        P.set_script(write, 0x12222E)
        write(P.JUMPING, 0xFF, 1)
        write(P.JUMP_SETTLED, 0, 1)
        _score(read, write, record)
        _retire(memory, services, record)
        _become(memory, services, record, PUFF)
        return
    P.hurt(read, write, services)


def burst(read, write, rom, services, memory, record):
    """1AEE18: hurts unless the sword is out; either way it bursts into the puff with script 123024."""
    if not read(P.SWORD_ACTIVE, 1):
        P.hurt(read, write, services)
    _release(memory, services, record)
    _template(write, rom, record, PUFF)
    write(record + 0x20, 0x123024, 4)


def apple_thrower(read, write, rom, services, memory, record):
    """1AEE40 (kind 2D): with the sword out its apple is knocked into the extra pool as kind 7F and it splashes."""
    if not read(P.SWORD_ACTIVE, 1):
        write(record, 0, 1)
        _release(memory, services, record)
        return P.hurt(read, write, services)
    extra = _find_free(read, _record(25), 6)
    if extra is not None:
        write(record, 0x7F, 1)
        write(record + 6, 0x40, 1)
        write(record + 0x1A, 0xF600, 2)
        write(record + 9, read(record + 9, 1) ^ 0xFF, 1)
        write(record + 0xA, 0x1209BE, 4)
        _copy_record(read, write, record, extra)
        write(record, 0, 1)
    _sound(read, services, 0x21)
    splash = _find_free(read, _record(1), 24)
    if splash is not None:
        _spawn_at(read, write, rom, SPLASH, splash, read(record + 2, 2), read(record + 4, 2))


def cut_rope_object(read, write, rom, services, memory, record):
    """1AEECA (kind 23): the sword cuts it: script 12319C, a kind-3B drop (1B79B8) and dust."""
    if not read(P.SWORD_ACTIVE, 1):
        return
    write(record, 0x84, 1)
    write(record + 0x20, 0x12319C, 4)
    write(record + 0x37, 0, 1)
    drop = _find_free(read, _record(3), 20)
    if drop is None:
        return
    _spawn_at(read, write, rom, 0x1B79B8, drop, read(record + 2, 2), read(record + 4, 2))
    write(drop, 0x3B, 1)
    write(drop + 0x20, 0x122BD8, 4)
    dust = _find_free(read, _record(1), 24)
    if dust is None:
        return
    _spawn_at(read, write, rom, DUST, dust, read(record + 2, 2), read(record + 4, 2))


def _collect(read, write, rom, services, memory, record, points=True):
    """1AF4C2 / 1AF4C6: 150 points (or none), then the sparkle in the object's place."""
    if points:
        hud.add_points(read, write, hud.POINT_ADDERS[0x1B0156])
    _retire(memory, services, record)
    _template(write, rom, record, SPARKLE)


def health_full(read, write, rom, services, memory, record):
    """1AEEE0."""
    _sound(read, services, 0x62)
    write(P.HEALTH, read(P.MAX_HEALTH, 1), 1)
    _collect(read, write, rom, services, memory, record)


def health_up(read, write, rom, services, memory, record):
    """1AEF12 (kind 44): 3 - difficulty points of health, capped at the maximum."""
    _sound(read, services, 0x62)
    health = (3 - read(P.DIFFICULTY, 1) + read(P.HEALTH, 1)) & 0xFF
    if health >= read(P.MAX_HEALTH, 1):
        health = read(P.MAX_HEALTH, 1)
    write(P.HEALTH, health, 1)
    _collect(read, write, rom, services, memory, record)


def extra_life(read, write, rom, services, memory, record):
    """1AEF5C."""
    if read(LIVES, 1) == 0x39:
        return
    hud.extra_life(read, write, lambda sound_id: services.sound(0, sound_id))
    _collect(read, write, rom, services, memory, record)


def _progress(flag):
    def handler(read, write, rom, services, memory, record):
        """1AEFB0 / 1AEFDC / 1AF008 / 1AF034 / 1AF060 / 1AF08C: a progress flag with its jingle."""
        write(flag, 0xFF, 1)
        _sound(read, services, 0x67)
        _collect(read, write, rom, services, memory, record)
    return handler


def gem(read, write, rom, services, memory, record):
    """1AF228 (kind 3A)."""
    if read(hud.GEMS, 2) == 0x3939:
        _restore_spawn_flag(read, write, record)
    hud.add_gem(read, write)
    _sound(read, services, 0x0D)
    _collect(read, write, rom, services, memory, record)


def apple(read, write, rom, services, memory, record):
    """1AF468 (kind 40)."""
    if read(hud.APPLES, 2) == 0x3939:
        _restore_spawn_flag(read, write, record)
    hud.add_apple(read, write)
    _sound(read, services, 0x0B)
    _collect(read, write, rom, services, memory, record, points=False)


def bonus_1000(read, write, rom, services, memory, record):
    """1AF384 (kind 3D): 1,000 points and the level's bonus flag."""
    _retire(memory, services, record)
    _template(write, rom, record, SPARKLE)
    _sound(read, services, 0x64)
    hud.add_points(read, write, hud.POINT_ADDERS[0x1B0188])
    write(0xFFF179, 0xFF, 1)


def points_item(read, write, rom, services, memory, record):
    """1AF4A0."""
    _sound(read, services, 0x0B)
    _collect(read, write, rom, services, memory, record)


def scarab(read, write, rom, services, memory, record):
    """1AF4D8 (kind 34): one more piece counted in FFF003, 250 points, the hit effect."""
    write(0xFFF003, read(0xFFF003, 1) + 1, 1)
    _sound(read, services, 0x69)
    hud.add_points(read, write, hud.POINT_ADDERS[0x1B016A])
    _retire(memory, services, record)
    _template(write, rom, record, HIT_TEMPLATE)


def bonus_flag_item(read, write, rom, services, memory, record):
    """1AF3C2 (kind 41): the bonus-stage flag, 250 points, the hit effect."""
    write(0xFFF176, 0xFF, 1)
    _sound(read, services, 0x69)
    hud.add_points(read, write, hud.POINT_ADDERS[0x1B016A])
    _retire(memory, services, record)
    _template(write, rom, record, HIT_TEMPLATE)


def sword_breaks_kind_03(read, write, rom, services, memory, record):
    """1AED86 (kind 03): the sword breaks it (script 122E16) and clears the player's +34; otherwise as 1AE9C6."""
    if not read(P.SWORD_ACTIVE, 1):
        return sword_or_hurt(read, write, rom, services, memory, record)
    write(record, 0x84, 1)
    write(record + 0x20, 0x122E16, 4)
    write(record + 0x37, 0, 1)
    write(RECORD_TABLE + 0x34, 0, 1)


def pot_2f(read, write, rom, services, memory, record):
    """1AEDA8 (kind 2F): it breaks (script 123A96); with the sword out a splash effect, otherwise the player is hurt."""
    write(record, 0x84, 1)
    write(record + 0x20, 0x123A96, 4)
    write(record + 0x37, 0, 1)
    if not read(P.SWORD_ACTIVE, 1):
        return P.hurt(read, write, services)
    _sound(read, services, 0x21)
    splash = _find_free(read, _record(1), 24)
    if splash is not None:
        _spawn_at(read, write, rom, SPLASH, splash, read(record + 2, 2), read(record + 4, 2))


def carried_object(read, write, rom, services, memory, record):
    """1AF516 (kind 36): moves to the extra pool as kind 82 with script 125710."""
    extra = _find_free(read, _record(25), 6)
    if extra is None:
        return
    write(record, 0x82, 1)
    write(record + 0x20, 0x125710, 4)
    write(record + 0x37, 0, 1)
    _copy_record(read, write, record, extra)
    write(record, 0, 1)


def _layer(value):
    def handler(read, write, rom, services, memory, record):
        """1AF53E / 1AF54A: the ground layer switch item."""
        write(P.ATTRIBUTE_LAYER, value, 2)
        points_item(read, write, rom, services, memory, record)
    return handler


def _clear_kind(kind):
    def handler(read, write, rom, services, memory, record):
        """1AF556 / 1AF562: every main-pool object of the kind is removed, then the points item."""
        for slot in range(1, 25):
            other = _record(slot)
            if read(other, 1) == kind:
                write(other, 0, 1)
                _release(memory, services, other)
        points_item(read, write, rom, services, memory, record)
    return handler


def _platform(read, write, record, offset, tolerance) -> bool:
    """The shared platform snap: refuse while a jump is still rising, or when too far from the top."""
    if read(P.JUMPING, 1) and not read(P.JUMP_SETTLED, 1):
        write(CONTACT_CANCEL, 0xFF, 1)
        return False
    if not read(record + 6, 1) & 0x10:
        write(CONTACT_CANCEL, 0xFF, 1)
        return False
    target = _w(read(record + 4, 2) - read(P.CAMERA_Y, 2) + offset)
    distance = _w(read(P.SCREEN_Y, 2) - target)
    if distance & 0x8000:
        distance = _w(-distance)
    if distance >= tolerance:
        write(CONTACT_CANCEL, 0xFF, 1)
        return False
    write(P.SCREEN_Y, target, 2)
    return True


def platform_2(read, write, rom, services, memory, record):
    """1AF5F0 (kind 58)."""
    _platform(read, write, record, 2, 0xC)


def platform_switch(read, write, rom, services, memory, record):
    """1AF590: a platform that becomes kind 56 with script 122D58 when stood on."""
    if _platform(read, write, record, -0x12, 6) and read(record, 1) not in (0x56, 0x57):
        write(record, 0x56, 1)
        write(record + 0x20, 0x122D58, 4)


def platform_sink(read, write, rom, services, memory, record):
    """1AF81C (kinds 62/63): stood on, it becomes kind 63 with motion script 121598."""
    if _platform(read, write, record, 0, 0xA) and read(record, 1) != 0x63:
        write(record, 0x63, 1)
        write(record + 0xA, 0x121598, 4)
        _sound(read, services, 0x45)


def platform_lift_switch(read, write, rom, services, memory, record):
    """1AF978 (kinds 69/6A/...): stood on, kinds 6A and 69 become kind 6B with their lift scripts."""
    if not _platform(read, write, record, -8, 0xC):
        return
    kind = read(record, 1)
    if kind in (0x6A, 0x69):
        write(record, 0x6B, 1)
        write(record + 0x20, 0x12408E if kind == 0x6A else 0x12404E, 4)
        write(record + 0x37, 0, 1)
        _restore_spawn_flag(read, write, record)


def platform_tilt(read, write, rom, services, memory, record):
    """1AF9F6 (kinds 76/77): a platform that carries the player sideways and tilts (kind 77) under them."""
    if not _platform(read, write, record, -0xB, 6):
        return
    dx = read(record + 0x1C, 1)
    write(P.SCREEN_X, _w(read(P.SCREEN_X, 2) + (dx - 0x100 if dx & 0x80 else dx)), 2)
    if read(record, 1) != 0x76:
        return
    x, ox = read(P.WORLD_X, 2), read(record + 2, 2)
    if x >= _w(ox + 8):
        write(record + 0x20, 0x1241C8, 4)
        write(record, 0x77, 1)
    elif x < _w(ox - 8):
        write(record + 0x20, 0x124198, 4)
        write(record, 0x77, 1)


def platform_break(read, write, rom, services, memory, record):
    """1AFA84 (kinds 74/75): a platform that breaks under the player standing in its middle."""
    if not _platform(read, write, record, -0xB, 0xA):
        return
    x, ox = read(P.WORLD_X, 2), read(record + 2, 2)
    if x >= _w(ox + 0x10) or x < _w(ox - 0x10) or read(record, 1) != 0x74:
        return
    if read(P.SWORD_ACTIVE, 1) or read(P.VELOCITY_Y, 2) & 0x8000 or not read(P.VELOCITY_Y, 2):
        return
    write(P.WALKING, 0, 1)
    write(P.WALK_SPEED, 0, 2)
    write(record + 0xA, 0x120A42, 4)
    write(record + 0x36, 0, 1)
    write(record, 0x75, 1)
    piece = _find_free(read, _record(3), 20)
    if piece is not None:
        _spawn_at(read, write, rom, 0x1B7E7C, piece, ox, read(record + 4, 2))


def rope(read, write, rom, services, memory, record):
    """1AFB36 (kinds 6E/6F/71/72): grab the rope when close and not rising."""
    if read(P.FROZEN, 1):
        return
    if read(P.VELOCITY_Y, 2) & 0x8000 or (read(P.JUMPING, 1) and not read(P.JUMP_SETTLED, 1)):
        return cancel(read, write, rom, services, memory, record)
    if not read(record + 6, 1) & 0x10:
        return cancel(read, write, rom, services, memory, record)
    target_x = _w(read(record + 2, 2) - read(P.CAMERA_X, 2))
    distance = _w(read(P.SCREEN_X, 2) - target_x)
    if distance & 0x8000:
        distance = _w(-distance)
    if distance >= 0xC:
        return cancel(read, write, rom, services, memory, record)
    write(P.SCREEN_X, target_x, 2)
    write(P.SCREEN_Y, _w(read(record + 4, 2) - read(P.CAMERA_Y, 2) + 0x10), 2)
    if not read(ROPE_HOLD, 1):
        P.set_script(write, 0x121964)
        write(P.CAMERA_TARGET_X, 0xB0, 2)
        write(P.CAMERA_TARGET_Y, 0x150, 2)
        write(P.WALK_SPEED, 0, 2)
        write(P.WALKING, 0, 1)
        write(P.VELOCITY_X, 0, 2)
        write(P.VELOCITY_Y, 0, 2)
    write(P.ATTACKING, 0xFF, 1)
    write(P.IN_AIR, 0xFF, 1)
    write(ROPE_HOLD, 4, 1)


def spring(read, write, rom, services, memory, record):
    """1AFD84 (kind 01): landing on it launches the player up with a sideways nudge."""
    if read(P.VELOCITY_Y, 2) & 0x8000 or read(P.FROZEN, 1):
        return
    target = _w(read(record + 4, 2) - read(P.CAMERA_Y, 2))
    distance = _w(read(P.SCREEN_Y, 2) - target)
    if distance & 0x8000:
        distance = _w(-distance)
    if distance >= 6:
        return cancel(read, write, rom, services, memory, record)
    write(P.SCREEN_Y, target, 2)
    write(P.VELOCITY_Y, 0xF800, 2)
    write(P.CAMERA_TARGET_X, 0xB0, 2)
    P.set_script(write, 0x121C62)
    write(P.JUMPING, 0xFF, 1)
    write(P.JUMP_SETTLED, 0, 1)
    write(record, 0x84, 1)
    write(record + 0x20, 0x122DB2, 4)
    write(record + 0x37, 0, 1)
    delta = _w(read(P.WORLD_X, 2) - read(record + 2, 2))
    if delta & 0x8000:
        nudge = (-(((-delta) & 0xFF) >> 3)) & 0xFF
    else:
        nudge = (delta & 0xFF) >> 3
    write(P.VELOCITY_X, nudge, 1)


def shop(read, write, rom, services, memory, record):
    """1AFE1C (kind 7E): the peddler: up on his left buys a life for 5 gems, on his right a continue for 10."""
    if read(P.FROZEN, 1):
        return _shop_camera(write)
    if not read(HELD_UP, 1):
        write(SHOP_LATCH, 0, 1)
        return _shop_camera(write)
    if read(SHOP_LATCH, 1):
        return _shop_camera(write)
    if read(P.WORLD_X, 2) < read(record + 2, 2):
        if read(hud.GEMS, 2) < 0x3035:
            return _shop_refuse(read, write, services, memory)
        write(SHOP_LATCH, 0xFF, 1)
        if read(LIVES, 1) == 0x39:
            services.show_message(0x16)
            write(SHOP_LATCH, 0xFF, 1)
            return
        for _ in range(5):
            hud.remove_gem(read, write)
        _sound(read, services, 0x48)
        hud.extra_life(read, write, lambda sound_id: services.sound(0, sound_id))
    else:
        if read(hud.GEMS, 2) < 0x3130:
            return _shop_refuse(read, write, services, memory)
        write(SHOP_LATCH, 0xFF, 1)
        for _ in range(10):
            hud.remove_gem(read, write)
        _sound(read, services, 0x48)
        write(CONTINUES, read(CONTINUES, 1) + 1, 1)
    write(hud.MESSAGE, 0x14, 1)
    services.show_message(0x14)
    _shop_camera(write)


def _shop_camera(write):
    write(P.CAMERA_TARGET_X, 0xB0, 2)
    write(P.CAMERA_TARGET_Y, 0x180, 2)


def _shop_refuse(read, write, services, memory):
    """1AFF40: not enough gems: the refusal message unless a kind-85 object is already out."""
    for slot in range(1, 25):
        if read(_record(slot), 1) == 0x85:
            return
    write(hud.MESSAGE, 0x11, 1)
    services.show_message(0x11)
    write(SHOP_LATCH, 0xFF, 1)


PLAYER_CALLBACKS = {
    0x1AE64C: bottle_pickup, 0x1AE6B4: cancel, 0x1AE722: pushable, 0x1AE796: sword_enemy, 0x1AE978: apple_thief,
    0x1AE9A8: dust_on_sword, 0x1AE9C6: sword_or_hurt, 0x1AE9DA: sword_only,
    0x1AE9E0: _flag_on_sword(0xFFF10E), 0x1AEA00: _flag_on_sword(0xFFF10F, (0x4F, 0xFE)),
    0x1AEA24: _flag_on_sword(0xFFF110, (0x4E, 0xFD)), 0x1AEA48: lamp_or_pot, 0x1AEB7A: nothing,
    0x1AEB7C: hurt_unless_armed, 0x1AEBA4: deadly_or_cutscene, 0x1AEBDC: deadly_centre, 0x1AEBFE: nothing,
    0x1AED24: stomp_or_hurt, 0x1AED86: sword_breaks_kind_03, 0x1AEDA6: nothing, 0x1AEDA8: pot_2f, 0x1AEE18: burst, 0x1AEE40: apple_thrower, 0x1AEECA: cut_rope_object, 0x1AEEDE: nothing,
    0x1AEEE0: health_full, 0x1AEF12: health_up, 0x1AEF5C: extra_life,
    0x1AEFB0: _progress(0xFFF126), 0x1AEFDC: _progress(0xFFF127), 0x1AF008: _progress(0xFFF128),
    0x1AF034: _progress(0xFFF129), 0x1AF060: _progress(0xFFF116), 0x1AF08C: _progress(0xFFF12A),
    0x1AF228: gem, 0x1AF384: bonus_1000, 0x1AF3C2: bonus_flag_item, 0x1AF468: apple, 0x1AF4A0: points_item, 0x1AF4D8: scarab,
    0x1AF516: carried_object, 0x1AF53E: _layer(0), 0x1AF54A: _layer(1), 0x1AF556: _clear_kind(8), 0x1AF562: _clear_kind(9),
    0x1AF590: platform_switch, 0x1AF5F0: platform_2, 0x1AF81C: platform_sink, 0x1AF978: platform_lift_switch,
    0x1AF9F6: platform_tilt, 0x1AFA84: platform_break,
    0x1AFB36: rope, 0x1AFD84: spring, 0x1AFE1C: shop,
}


# ---- projectile contacts (an apple from the extra pool hits a main-pool object) ------------------
def _apple_lands(read, write, rom, services, memory, projectile) -> bool:
    """1AC458 head: the apple splats; True when it was a kind-82 (already spent) one."""
    spent = read(projectile, 1) == 0x82
    write(projectile, 0, 1)
    _release(memory, services, projectile)
    _splat(read, write, rom, services, (projectile - RECORD_TABLE) // RECORD_SIZE, projectile)
    return spent


def _apple_kill(read, write, rom, services, memory, target):
    """1AC484: score, the boss countdown for kinds 10/11/13, retire, the puff, the hit sound."""
    _score(read, write, target)
    if read(target, 1) in (0x10, 0x13, 0x11):
        write(P.TRANSITION_COUNTDOWN, 0x20, 1)
    _retire(memory, services, target)
    _become(memory, services, target, PUFF)
    _sound(read, services, 0x03, flush=False)


def apple_hit(read, write, rom, services, memory, projectile, target):
    """1AC458 (kind 0A and the shared tail): the apple splats; a hit point is lost or the object dies."""
    if _apple_lands(read, write, rom, services, memory, projectile):
        return _apple_kill(read, write, rom, services, memory, target)
    if read(target + 1, 1):
        write(target + 1, read(target + 1, 1) - 1, 1)
        return
    _apple_kill(read, write, rom, services, memory, target)


def apple_hit_with_script(script, motion=None, kind=None):
    def handler(read, write, rom, services, memory, projectile, target):
        """1AC1B4 / 1AC318 / 1AC334: the struck object's reaction script, then the shared hit."""
        write(target + 0x20, script, 4)
        write(target + 0x37, 0, 1)
        if kind is not None:
            write(target, kind, 1)
        write(target + 0xA, motion or 0, 4)
        write(target + 0x36, 0, 1)
        apple_hit(read, write, rom, services, memory, projectile, target)
    return handler


def apple_hit_gem_enemy(read, write, rom, services, memory, projectile, target):
    """1AC1D0 (kind 13): a hit point lost with its script and sound, or death with a dust puff and a gem drop."""
    write(projectile, 0, 1)
    _release(memory, services, projectile)
    _splat(read, write, rom, services, (projectile - RECORD_TABLE) // RECORD_SIZE, projectile)
    if read(target + 1, 1):
        write(target + 1, read(target + 1, 1) - 1, 1)
        write(target + 0x20, 0x12474C, 4)
        write(target + 0x37, 0, 1)
        write(target + 0xA, 0, 4)
        write(target + 0x36, 0, 1)
        _sound(read, services, 0x6B)
        return
    _score(read, write, target)
    _retire(memory, services, target)
    _become(memory, services, target, DUST)
    _sound(read, services, 0x03, flush=False)
    drop = _find_free(read, _record(24), 24, -1)
    if drop is None:
        return
    _spawn_at(read, write, rom, GEM_DROP, drop, read(target + 2, 2), _w(read(target + 4, 2) - 0x20))
    write(drop + 9, 0xFF, 1)
    write(0xFFF124, 8, 1)
    services.sound_command(0x16)
    if read(0xFFF57F, 1):
        services.sound(0, 0x14, flush=True)


def apple_hit_boss_10(read, write, rom, services, memory, projectile, target):
    """1AC2BC (kind 10): the apple splats; a hit point lost plays script 1239A0, none left kills it."""
    write(projectile, 0, 1)
    _release(memory, services, projectile)
    _splat(read, write, rom, services, (projectile - RECORD_TABLE) // RECORD_SIZE, projectile)
    if read(target + 1, 1):
        write(target + 1, read(target + 1, 1) - 1, 1)
        write(target + 0x20, 0x1239A0, 4)
        write(target + 0x37, 0, 1)
        return
    _apple_kill(read, write, rom, services, memory, target)


def apple_hit_kind_03(read, write, rom, services, memory, projectile, target):
    """1AC0EE (kind 03): script 122E16, the spawn flag byte cleared, then the shared hit."""
    write(target + 0x20, 0x122E16, 4)
    write(target + 0x37, 0, 1)
    write(target + 0x34, 0, 1)
    apple_hit(read, write, rom, services, memory, projectile, target)


def apple_hit_or_stun(read, write, rom, services, memory, projectile, target):
    """1AC350 (kinds 1D/20): a spent apple kills; a fresh one stuns the object three times in four."""
    if read(projectile, 1) == 0x82:
        return _apple_kill(read, write, rom, services, memory, target)
    write(projectile, 0, 1)
    _release(memory, services, projectile)
    _splat(read, write, rom, services, (projectile - RECORD_TABLE) // RECORD_SIZE, projectile)
    if _random(read, write) & 0xFF >= 0xC8:
        write(target + 0x20, 0x1233CC, 4)
        write(target + 0x37, 0, 1)
        write(target + 0xA, 0, 4)
        write(target + 0x36, 0, 1)
        return
    _apple_kill(read, write, rom, services, memory, target)


def apple_caught(read, write, rom, services, memory, projectile, target):
    """1AC6A2 (kind 2D): the apple thrower catches a fresh apple (kind 80) or is hit by a spent one."""
    kind = read(projectile, 1)
    if kind == 0x80:
        write(projectile, 0x84, 1)
        write(projectile + 0x20, 0x122B6E, 4)
        write(projectile + 0x37, 0, 1)
        write(projectile + 0xA, 0, 4)
    elif kind != 0x82:
        return
    write(target, 0x84, 1)
    write(target + 6, 0x40, 1)


PROJECTILE_CALLBACKS = {
    0x1AC458: apple_hit, 0x1AC1B4: apple_hit_with_script(0x1252A8, 0x120D4C),
    0x1AC318: apple_hit_with_script(0x1234BE, kind=0x84), 0x1AC334: apple_hit_with_script(0x12350C, kind=0x84),
    0x1AC350: apple_hit_or_stun, 0x1AC1D0: apple_hit_gem_enemy, 0x1AC6A2: apple_caught,
    0x1AC0EE: apple_hit_kind_03, 0x1AC2BC: apple_hit_boss_10,
    0x1AC2E0: apple_hit_with_script(0x12384A, kind=0x84), 0x1AC2FC: apple_hit_with_script(0x12387A, kind=0x84),
}

PLAYER_CONTACTS.update(PLAYER_CALLBACKS)
PROJECTILE_CONTACTS.update(PROJECTILE_CALLBACKS)
