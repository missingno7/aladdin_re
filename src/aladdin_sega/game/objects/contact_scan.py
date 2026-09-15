"""The two contact scans: the player against objects (1ABB40) and projectiles against objects (1ABD7E).

A sprite frame descriptor's header carries the hit box as four 0x80-biased
bytes at +2..+5 (left, top, right, bottom).  A record facing left mirrors
its box by negating the byte, which with the bias keeps every edge at
``X + 0x80 +/- extent``.  When the player's box overlaps an object's, the
object's kind selects a contact callback from the ROM table at 1CBE; the
callback is the object's whole reaction (damage, collection, riding, ...)
and afterwards an object whose flags6 bit 4 marks it as a platform lets
the player stand on it (FFF0CD, with the landing animation chosen from
the player's state).  The projectile scan does the same for the extra
pool (slots 25..31: thrown apples and the like) against the main pool
with the table at 1EBA, indexed by the struck object's kind.

The callbacks are registered here as they are recovered; an unrecovered
callback stops native execution with its kind and ROM address.
"""
from .record import RECORD_TABLE, RECORD_SIZE
from ..player import (FACING, SPRITE_FRAME, JUMPING, JUMP_SETTLED, FROZEN, VELOCITY_Y, CAMERA_LOCK, WALK_SPEED,
                      FALL_TIMER, LANDING_FLAG, ON_GROUND, HANGING, WALKING, HARD_LANDING_FRAMES,
                      SCRIPT_HARD_LANDING, SCRIPT_LAND_IDLE, SCRIPT_LAND_IDLE_FREE, set_script, publish_position)

PLAYER_CALLBACKS = 0x1CBE           # ROM: 0x7F longs by object kind
PROJECTILE_CALLBACKS = 0x1EBA       # ROM: 0x32 longs by the struck object's kind
NO_CALLBACK = 0x1B65BE              # a bare RTS
PLAYER_BOX_LEFT, PLAYER_BOX_RIGHT = 0xFFF08C, 0xFFF08E
HURT_TIMER = 0xFFF0EE               # TENTATIVE: counts down after a hit
INVULNERABLE = 0xFFF0F2             # frames of invulnerability after a hit
CONTACT_RESULT_A, CONTACT_RESULT_B = 0xFFF0F0, 0xFFF0EF   # TENTATIVE: cleared before the scan, set by callbacks
CONTACT_KIND = 0xFFF0F6             # the kind whose callback is running
CONTACT_CANCEL = 0xFFF0F5           # a callback sets it to refuse the platform landing
CONTACT, PREVIOUS_CONTACT = 0xFFF0D3, 0xFFF0D4   # the kind the player stands on, this frame and last
SCRIPT_CONTACT_ATTACK, SCRIPT_CONTACT_RIDE = 0x121964, 0x1220AA
PLAYER_CONTACTS = {}                # ROM address -> callable(read, write, rom, services, memory, record)
PROJECTILE_CONTACTS = {}            # ROM address -> callable(read, write, rom, services, memory, projectile, target)


class ContactGap(Exception):
    def __init__(self, table, kind, target):
        super().__init__(f'contact callback for kind {kind:02X} ({target:06X}) is not recovered')
        self.table, self.kind, self.target = table, kind, target


def _w(v):
    return v & 0xFFFF


def _edge(x, byte, mirrored):
    return _w(x + ((-byte) & 0xFF if mirrored else byte))


def _record(slot):
    return RECORD_TABLE + RECORD_SIZE * slot


def _callback(rom, table, kind, registry):
    target = int.from_bytes(rom[table + 4 * kind:table + 4 * kind + 4], 'big')
    if target == NO_CALLBACK:
        return None
    try:
        return registry[target]
    except KeyError:
        raise ContactGap(table, kind, target) from None


def player_contact_scan(read, write, rom, services, memory, bus) -> None:
    write(CONTACT_RESULT_A, 0, 1)
    write(CONTACT_RESULT_B, 0, 1)
    for timer in (HURT_TIMER, INVULNERABLE):
        if read(timer, 1):
            write(timer, read(timer, 1) - 1, 1)
    write(PREVIOUS_CONTACT, read(CONTACT, 1), 1)
    write(CONTACT, 0, 1)
    write(CONTACT_KIND, 0, 1)
    write(HANGING, 0, 1)
    frame = read(SPRITE_FRAME, 4)
    player = _record(0)
    if not frame or not read(player, 1):
        return
    px = read(player + 2, 2)
    if read(FACING, 1):
        left, right = _edge(px, bus(frame + 4, 1), True), _edge(px, bus(frame + 2, 1), True)
    else:
        left, right = _edge(px, bus(frame + 2, 1), False), _edge(px, bus(frame + 4, 1), False)
    write(PLAYER_BOX_LEFT, left, 2)
    write(PLAYER_BOX_RIGHT, right, 2)
    for slot in range(1, 25):
        record = _record(slot)
        kind = read(record, 1)
        if not kind or kind >= 0x7F:
            continue
        descriptor = read(record + 0x14, 4)
        if not descriptor:
            continue
        ox, oy, mirrored = read(record + 2, 2), read(record + 4, 2), read(record + 9, 1)
        py = read(player + 4, 2)        # per object: a landing earlier in the scan republishes the player's Y
        if right < (_edge(ox, bus(descriptor + 4, 1), True) if mirrored else _edge(ox, bus(descriptor + 2, 1), False)):
            continue
        if _w(bus(frame + 5, 1) + py) < _w(bus(descriptor + 3, 1) + oy):
            continue
        if left >= (_edge(ox, bus(descriptor + 2, 1), True) if mirrored else _edge(ox, bus(descriptor + 4, 1), False)):
            continue
        if _w(bus(frame + 3, 1) + py) >= _w(bus(descriptor + 5, 1) + oy):
            continue
        write(CONTACT_CANCEL, 0, 1)
        write(CONTACT_KIND, kind, 1)
        callback = _callback(rom, PLAYER_CALLBACKS, kind, PLAYER_CONTACTS)
        if callback is not None:
            callback(read, write, rom, services, memory, record)
        if not read(record + 6, 1) & 0x10 or read(CONTACT_CANCEL, 1):
            continue
        if read(JUMPING, 1):
            if not read(JUMP_SETTLED, 1):
                continue
            write(JUMPING, 0, 1)
        if read(FROZEN, 1):
            continue
        if read(VELOCITY_Y, 2):
            write(LANDING_FLAG, 0, 1)
            kind = read(record, 1)
            if 0x50 <= kind < 0x52:
                script = SCRIPT_CONTACT_ATTACK
            elif read(CAMERA_LOCK, 1):
                script = SCRIPT_LAND_IDLE
            elif read(WALK_SPEED, 2):
                script = SCRIPT_CONTACT_RIDE
            elif read(FALL_TIMER, 1) >= HARD_LANDING_FRAMES:
                script = SCRIPT_HARD_LANDING
            else:
                script = SCRIPT_LAND_IDLE_FREE
            write(VELOCITY_Y, 0, 2)
            set_script(write, script)
            write(WALKING, 0, 1)
        write(FALL_TIMER, 0, 1)
        write(ON_GROUND, 0xFF, 1)
        write(CONTACT, read(record, 1), 1)
        write(HANGING, 0xFF, 1)
        publish_position(read, write)


def projectile_contact_scan(read, write, rom, services, memory, bus) -> None:
    for projectile in range(25, 32):
        record = _record(projectile)
        kind = read(record, 1)
        if not kind or kind >= 0x83:
            continue
        box = read(record + 0x14, 4)
        if not box:
            continue
        x1, y1 = read(record + 2, 2), read(record + 4, 2)
        for slot in range(1, 25):
            other = _record(slot)
            other_kind = read(other, 1)
            if not other_kind or other_kind >= 0x32:
                continue
            other_box = read(other + 0x14, 4)
            if not other_box:
                continue
            x2, y2 = read(other + 2, 2), read(other + 4, 2)
            if _w(bus(box + 4, 1) + x1) < _w(bus(other_box + 2, 1) + x2):
                continue
            if _w(bus(box + 5, 1) + y1) < _w(bus(other_box + 3, 1) + y2):
                continue
            if _w(bus(box + 2, 1) + x1) >= _w(bus(other_box + 4, 1) + x2):
                continue
            if _w(bus(box + 3, 1) + y1) >= _w(bus(other_box + 5, 1) + y2):
                continue
            callback = _callback(rom, PROJECTILE_CALLBACKS, other_kind, PROJECTILE_CONTACTS)
            if callback is not None:
                callback(read, write, rom, services, memory, record, other)
