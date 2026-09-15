"""In-game text messages (1B2238): each glyph is an object, laid out by a small command language.

A message code (FFF15A) selects a 12-byte entry at ROM 126D7E: the text,
its start position, and a callback the game remembers at FF7286.  The
previous message's glyph objects (kind 85) are removed, then the text is
walked: a printable character spawns a glyph object (template 1B7968)
with the glyph's own animation script (table 4A18) and the message's
motion script at the pen position, and the pen advances by FF728A;
control bytes below 0x20 move the pen, draw tile boxes straight into
plane A (3, 4, 5), wait for frames or a button (6), change the palette
line of later tiles (8..B), select the glyph motion script (C), or spawn
an object inline (F).  Typewriter mode (FFEFFC) waits a frame per glyph.

The shop's "IT'S A DEAL" / "FIND MORE GEMS" / "SOLD OUT!" and the level
hints are plain glyph runs; inside the main loop the commands that wait
for frames are reported as gaps (the frame loop is not nestable there).

``print_text`` is the other walker over the same command table (1B21F6):
the story screens print each character as a tile straight into plane A
at the pen position, and their wait command (06) runs mini frames.
"""
from .objects.record import RECORD_TABLE, RECORD_SIZE
from .objects.lifecycle import initialize
from .objects.script_engine import Engine
from .objects.record import RecordView
from .level import NAME_ROW_TABLE

MESSAGES = 0x126D7E              # ROM: [text long][x word][y word][callback long] per code
COMMANDS = 0x49D8                # ROM: the 16 control-byte handlers (their meaning is fixed here)
GLYPH_SCRIPTS = 0x4A18           # ROM: animation script per character (0 = blank)
GLYPH_TEMPLATE = 0x1B7968
GLYPH_KIND = 0x85
GLYPH_MOTION = 0x11F728          # the default motion script for glyphs
MESSAGE_CALLBACK = 0xFF7286
PEN_ADVANCE = 0xFF728A
TYPEWRITER = 0xFFEFFC
TILE_PALETTE_BITS = 0xFFEFF0
TILE_BASE = 0x87C0
TEMPLATE_SIZE = 19


class MessageGap(Exception):
    """The message needs nested frames (a wait command, typewriter mode, a redraw)."""


def _signed_byte(v):
    return v - 0x100 if v & 0x80 else v


def clear_glyphs(read, write, memory, services) -> None:
    """1A92DC: every kind-85 object goes, with its VRAM."""
    engine = Engine(memory, services)
    for slot in range(1, 32):
        record = RECORD_TABLE + RECORD_SIZE * slot
        if read(record, 1) == GLYPH_KIND:
            write(record, 0, 1)
            engine.release(RecordView(record, read, write))


def _draw_tile(read, vdp, column, row, glyph) -> None:
    """1B21A8: one glyph tile into plane A at (column, row) with the current palette bits."""
    entry = read(NAME_ROW_TABLE + 4 * (row & 0xFFFF), 4)
    command = (((entry & 0xFFFF) | ((column * 2) & 0xFFFF)) << 16) | (entry >> 16)
    vdp.control_long(command)
    vdp.data(((glyph | read(TILE_PALETTE_BITS, 2)) + TILE_BASE) & 0xFFFF)


class _Pen:
    """The walker's registers: the text pointer (a0), the pen (d0 / d1) and the glyph motion script."""
    __slots__ = ('p', 'x', 'y', 'motion', 'done')

    def __init__(self, text, x, y):
        self.p, self.x, self.y, self.motion, self.done = text, x, y, GLYPH_MOTION, False


def _command(read, write, rom, vdp, pen: _Pen, c: int, wait, what: str) -> None:
    """One control byte (< 0x20) through the handler table at 49D8; ``wait(count)`` serves command 06."""
    p = pen.p
    if c == 0x00:
        pen.done = True
    elif c == 0x01:
        pen.x = (pen.x + _signed_byte(rom[p])) & 0xFFFF; p += 1
    elif c == 0x02:
        pen.y = (pen.y + _signed_byte(rom[p])) & 0xFFFF; p += 1
    elif c == 0x03:
        count, glyph = rom[p], (rom[p + 1] - 0x20) & 0xFF; p += 2
        for _ in range(count):
            _draw_tile(read, vdp, pen.x, pen.y, glyph); pen.x = (pen.x + 1) & 0xFF
    elif c == 0x04:
        count, glyph = rom[p], (rom[p + 1] - 0x20) & 0xFF; p += 2
        for _ in range(count):
            _draw_tile(read, vdp, pen.x, pen.y, glyph); pen.y = (pen.y + 1) & 0xFF
    elif c == 0x05:
        width, height, glyph = rom[p], rom[p + 1], (rom[p + 2] - 0x20) & 0xFF; p += 3
        for _ in range(height):
            column = pen.x
            for _ in range(width):
                _draw_tile(read, vdp, column, pen.y, glyph); column = (column + 1) & 0xFF
            pen.y = (pen.y + 1) & 0xFF
    elif c == 0x06:
        if wait is None:
            raise MessageGap(f'{what} waits {rom[p]} frames (1B2380)')
        wait(rom[p]); p += 1
    elif c == 0x07:
        pen.y = (pen.y + 1) & 0xFFFF; pen.x &= 0xFF00
    elif c in (0x08, 0x09, 0x0A, 0x0B):
        write(TILE_PALETTE_BITS, (c - 0x08) * 0x2000, 2)
    elif c == 0x0C:
        pen.motion = int.from_bytes(rom[p:p + 3], 'big'); p += 3
    elif c == 0x0F:
        template = int.from_bytes(rom[p:p + 4], 'big')
        ox, oy = int.from_bytes(rom[p + 4:p + 6], 'big'), int.from_bytes(rom[p + 6:p + 8], 'big'); p += 8
        for i in range(20):
            record = RECORD_TABLE + RECORD_SIZE * (3 + i)
            if not read(record, 1):
                for a, value in initialize(record, rom[template:template + TEMPLATE_SIZE]):
                    write(a, value, 1)
                write(record + 2, ox, 2); write(record + 4, oy, 2)
                break
    else:
        raise MessageGap(f'{what} uses control byte {c:02X} (redraw / fade)')
    pen.p = p


def print_text(read, write, rom, vdp, text, column, row, wait, latched) -> None:
    """1B21F6: the text as tiles into plane A from (column, row); stops once the any-button latch is set.

    ``wait(count)`` runs the frames of command 06 (1B2380); ``latched()`` reads FF7E22.
    Typewriter mode's per-glyph wait (1B2EE0) is an RTS here.
    """
    pen = _Pen(text, column, row)
    while not latched() and not pen.done:
        c = rom[pen.p]
        pen.p += 1
        if c < 0x20:
            _command(read, write, rom, vdp, pen, c, wait, f'text {text:06X}')
        else:
            _draw_tile(read, vdp, pen.x, pen.y, c - 0x20)
            pen.x = (pen.x & 0xFF00) | ((pen.x + 1) & 0xFF)


def show(read, write, rom, vdp, memory, services, code) -> None:
    entry = MESSAGES + 12 * code
    text = int.from_bytes(rom[entry:entry + 4], 'big')
    pen = _Pen(text, int.from_bytes(rom[entry + 4:entry + 6], 'big'), int.from_bytes(rom[entry + 6:entry + 8], 'big'))
    write(MESSAGE_CALLBACK, int.from_bytes(rom[entry + 8:entry + 12], 'big'), 4)
    clear_glyphs(read, write, memory, services)
    write(PEN_ADVANCE, 0x11, 2)
    while True:
        c = rom[pen.p]
        pen.p += 1
        if c == 0x20:
            pen.x = (pen.x + read(PEN_ADVANCE, 2)) & 0xFFFF
            continue
        if c < 0x20:
            _command(read, write, rom, vdp, pen, c, None, f'message {code:02X}')
            if pen.done:
                return
            continue
        x, y, motion = pen.x, pen.y, pen.motion
        if read(TYPEWRITER, 1):
            raise MessageGap(f'message {code:02X} in typewriter mode waits a frame per glyph (1B2EAC)')
        script = int.from_bytes(rom[GLYPH_SCRIPTS + 4 * (c - 0x20):GLYPH_SCRIPTS + 4 * (c - 0x20) + 4], 'big')
        if script:
            record = None
            for slot in range(1, 32):
                candidate = RECORD_TABLE + RECORD_SIZE * slot
                if not read(candidate, 1):
                    record = candidate
                    break
            if record is None:
                return
            for a, value in initialize(record, rom[GLYPH_TEMPLATE:GLYPH_TEMPLATE + TEMPLATE_SIZE]):
                write(a, value, 1)
            write(record + 0x20, script, 4)
            write(record + 0xA, motion, 4)
            write(record + 2, x, 2)
            write(record + 4, y, 2)
        pen.x = (x + read(PEN_ADVANCE, 2)) & 0xFFFF
