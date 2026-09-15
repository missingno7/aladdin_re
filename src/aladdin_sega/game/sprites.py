"""The sprite attribute table builder (1AB7C4): HUD pieces and every object's sprite pieces into FF729A.

Each entry is the VDP's 8-byte sprite: y, size | link, attributes (palette,
flips, tile index), x, with the link chaining every entry to the next and
a final entry linked to 0.  The HUD comes first: the lives icon and digit,
the apples and gems counters (each blinking when low), the health bar
(blinking when low; its bars wobble through a ROM stream at FF7DA8) and
the score without leading zeros.  Then every visible record's frame
descriptor is walked: a piece is placed at the record's position plus its
0x80-biased offset (mirrored through the tile record's width / height
when the record faces left or is upside down), culled outside the screen,
shifted by the vertical offset and shake the scroll code left in FFF080 /
FFF082, and given the tile record's size and the record's attribute word
plus the VRAM slot.  The player flickers on odd invulnerability frames.
"""
from .objects.record import RECORD_TABLE, RECORD_SIZE, RECORD_COUNT
from . import player as P

SPRITE_TABLE = 0xFF729A
SPRITE_COUNT = 0xFFEFED           # the low byte of the count word the upload reads
LEADING_DIGIT_SEEN = 0xFFF0FE
LIVES, APPLES, GEMS, HEALTH, SCORE = 0xFF7E3C, 0xFFEFE0, 0xFFEFE2, 0xFFEFFA, 0xFF7E29
HEALTH_WOBBLE = 0xFF7DA8          # long: cursor in the ROM stream of health-bar tiles (29A6), 0 restarts it
HEALTH_WOBBLE_STREAM = 0x29A6
VERTICAL_OFFSET, SHAKE_OFFSET = 0xFFF080, 0xFFF082
INVULNERABLE = 0xFFF0F2
DIGIT_TILE, SCORE_DIGIT_TILE = 0xE6E0, 0xE7C0
LIVES_ICON, APPLES_ICON, GEMS_ICON, FACE_TILE, FACE_TILE_2, HEALTH_BAR_TILE = 0xE6EA, 0xE6F3, 0xE6F7, 0xE680, 0xE68C, 0xE6A0
SCREEN_HEIGHT_LIMIT, SCREEN_WIDTH_LIMIT = 0x15F, 0x1BF


def _w(v):
    return v & 0xFFFF


def _b(v):
    return v & 0xFF


class _Table:
    def __init__(self, write):
        self.write = write
        self.cursor = SPRITE_TABLE
        self.link_size = 0x0A01       # size in the high byte, link in the low byte

    def entry(self, y, tile, x, size=None):
        if size is not None:
            self.link_size = (self.link_size & 0xF0FF) | size
        for value in (y, self.link_size, tile, x):
            self.write(self.cursor, _w(value), 2)
            self.cursor += 2
        self.link_size = (self.link_size & 0xFF00) | ((self.link_size + 1) & 0xFF)

    def finish(self):
        for value in (1, 0, 0, 1):
            self.write(self.cursor, value, 2)
            self.cursor += 2
        self.write(SPRITE_COUNT, self.link_size & 0xFF, 1)


def _digit(read, address):
    return _w(DIGIT_TILE + (((read(address, 1) - 0x30) & 0xFF) - (0x100 if (read(address, 1) - 0x30) & 0x80 else 0)))


def _counter(read, table, address, icon_tile, icon_x, digits_x, low_threshold):
    """Apples and gems: the icon and up to two digits, blinking below the threshold."""
    value = read(address, 2)
    if value == 0x3030:
        return
    x = digits_x
    if value >= low_threshold or (read(P.FRAME_COUNTER, 1) & 0xF) >= 5:
        table.entry(0x140, icon_tile, icon_x, size=0x500)
        table.link_size &= 0xF0FF
        if read(address, 1) != 0x30:
            table.entry(0x148, _digit(read, address), x)
            x += 8
    table.entry(0x148, _digit(read, address + 1), x)


def build_sprite_table(read, write, rom, bus) -> None:
    """``bus(address, size)`` reads ROM or work RAM: frame descriptors can live in either."""
    write(LEADING_DIGIT_SEEN, 0, 1)
    table = _Table(write)
    cam_x, cam_y = read(P.CAMERA_X, 2), read(P.CAMERA_Y, 2)
    table.entry(0x138, LIVES_ICON, 0x90)
    table.link_size &= 0xF0FF
    table.entry(0x148, _digit(read, LIVES), 0xAA)
    _counter(read, table, APPLES, APPLES_ICON, 0x18E, 0x1A0, 0x3036)
    _counter(read, table, GEMS, GEMS_ICON, 0x16A, 0x17C, 0)
    health = read(HEALTH, 1)
    if health >= 3 or (read(P.FRAME_COUNTER, 1) & 0xF) >= 5:
        table.entry(0x94, FACE_TILE, 0x92, size=0xE00)
        table.entry(0x94, FACE_TILE_2, 0xB2, size=0x500)
        table.link_size = (table.link_size & 0xF0FF) | 0x100
        if health:
            x = 0xC2
            table.entry(0x8C, _w(HEALTH_BAR_TILE - 2 * health), x)
            x += 8
            cursor = read(HEALTH_WOBBLE, 4)
            tile = int.from_bytes(rom[cursor:cursor + 2], 'big')
            cursor += 2
            if not tile:
                cursor = HEALTH_WOBBLE_STREAM
                tile = int.from_bytes(rom[cursor:cursor + 2], 'big')
                cursor += 2
            write(HEALTH_WOBBLE, cursor, 4)
            tile = _w(tile - 2 * (health - 1))
            for _ in range(health):
                table.entry(0x8C, tile, x)
                x += 8
                tile = _w(tile + 2)
    table.link_size = (table.link_size & 0xF0FF) | 0x500
    x = 0x134
    for i in range(6):
        digit = read(SCORE + i, 1)
        if digit != 0x30 or read(LEADING_DIGIT_SEEN, 1):
            write(LEADING_DIGIT_SEEN, 0xFF, 1)
            table.entry(0x9A, _w(SCORE_DIGIT_TILE + 4 * (digit - 0x30)), x)
        x += 0x12
    vertical, shake = read(VERTICAL_OFFSET, 2), read(SHAKE_OFFSET, 2)
    for slot in range(RECORD_COUNT):
        if slot == 0 and read(INVULNERABLE, 1) & 1:
            continue
        record = RECORD_TABLE + RECORD_SIZE * slot
        descriptor = read(record + 0x14, 4)
        if not read(record, 1) or not descriptor or read(record + 7, 1) & 0x20:
            continue
        count = bus(descriptor, 2)
        piece = descriptor + 6
        attributes = _w((read(record + 0x2E, 4) >> 5) + read(record + 0x1E, 2))
        mirrored, upside_down = read(record + 9, 1), read(record + 0x35, 1)
        x0, y0 = read(record + 2, 2), read(record + 4, 2)
        for _ in range(count + 1):
            tile_record = bus(piece, 2)
            dy, dx = bus(piece + 3, 1), bus(piece + 2, 1)
            if read(record + 6, 1) & 0x08:
                y = _w(dy + y0 - 0x100)
                if y < SCREEN_HEIGHT_LIMIT:
                    if mirrored:
                        dx = _b(-dx - rom[tile_record + 8])
                    x = _w(dx + x0 - 0x80)
                    visible = x < SCREEN_WIDTH_LIMIT
                else:
                    visible = False
            else:
                if upside_down:
                    dy = _b(-dy - rom[tile_record + 9])
                y = _w(dy + y0 - cam_y - 0x100)
                if y < SCREEN_HEIGHT_LIMIT:
                    if mirrored:
                        dx = _b(-dx - rom[tile_record + 8])
                    x = _w(dx + x0 - cam_x)
                    visible = x < SCREEN_WIDTH_LIMIT
                else:
                    visible = False
            if visible:
                flags = attributes
                if mirrored:
                    flags = (flags & 0xF7FF) | 0x800
                if upside_down:
                    flags = (flags & 0xEFFF) | 0x1000
                table.entry(_w(y + vertical), flags, _w(x - shake),
                            size=int.from_bytes(rom[tile_record + 6:tile_record + 8], 'big'))
            attributes = _w(attributes + bus(piece + 0xA, 2))
            piece += 12
    table.finish()
