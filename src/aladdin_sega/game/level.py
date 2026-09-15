"""The level map as the game keeps it in RAM and streams it into the name tables.

A level is a grid of 16x16-pixel cells.  The map proper lives in work RAM
(one word per cell; the level loader decompresses it there), addressed
through a row table at FF9884 that holds, for every pixel row, the address
of that cell row's first word (so 16 equal entries per cell row).  A cell
word is a byte offset into the level's cell table in ROM (FF7DBE): four
name-table words, top-left, top-right, bottom-left, bottom-right.  Half
the same word (``word >> 1``) indexes the spawn flags at FFAE87, which is
why the spawn walk shares the map cursor with the drawing.

The visible window is anchored at (FF7E06, FF7E08).  The camera code
accumulates how far the camera has moved past the anchor in FFF0B2 /
FFF0B4 and raises one of the four strip flags FFF0B9..BC; the main loop's
camera step then draws the newly exposed 16-pixel column or row into the
64x32 name table of plane A (row commands from the table at FF8680) and
walks that strip for objects to spawn.
"""
from __future__ import annotations

MAP_ROW_TABLE = 0xFF9884       # long per pixel row: address of the cell row's first word
NAME_ROW_TABLE = 0xFF8680      # 64 longs: VDP command for each name-table row (words swapped; column OR'd in)
CELL_TILES = 0xFF7DBE          # long: ROM table, 4 name-table words per cell, indexed by the cell word
MAP_STRIDE = 0xFF7DB4          # bytes per map row
MAP_WIDTH = 0xFF7DB6           # cells per map row
MAP_CURSOR = 0xFF7DAC          # the cell word the last strip started at; the spawn walk continues from it
WINDOW_X, WINDOW_Y = 0xFF7E06, 0xFF7E08
COLUMN_DEBT, ROW_DEBT = 0xFFF0B2, 0xFFF0B4       # camera movement past the anchor, not yet drawn
STRIP_LEFT, STRIP_RIGHT, STRIP_TOP, STRIP_BOTTOM = 0xFFF0B9, 0xFFF0BA, 0xFFF0BB, 0xFFF0BC
STRIPS_SUSPENDED = 0xFFF174    # byte: no strips this frame (level transitions)
COLUMN_CELLS, ROW_CELLS = 16, 23
RIGHT_EDGE_CELLS = 22          # the right strip is drawn 22 cells past the anchor


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _settle(read, write, debt_address, origin_address) -> bool:
    """Move the anchor one cell toward the camera when the debt allows; False when nothing is due."""
    debt = read(debt_address, 2)
    probe = (debt + 0x100) & 0xFFFF
    if probe >= 0x110:
        write(debt_address, (debt - 16) & 0xFFFF, 2)
        write(origin_address, (read(origin_address, 2) + 16) & 0xFFFF, 2)
        return True
    if probe >= 0xF1:
        return False
    write(debt_address, (debt + 16) & 0xFFFF, 2)
    write(origin_address, (read(origin_address, 2) - 16) & 0xFFFF, 2)
    return True


def _row_start(read, y):
    return read(MAP_ROW_TABLE + _signed_word((y & 0xFFF0) * 4), 4)


def _name_command(entry, column):
    """The table stores the command's words swapped; the column offset is OR'd into the address word."""
    return (((entry & 0xFFFF) | column) << 16) | (entry >> 16)


def cell_tiles(rom, table, word):
    base = table + word
    return [int.from_bytes(rom[base + k:base + k + 2], 'big') for k in (0, 2, 4, 6)]


def draw_column(read, write, rom, vdp, right: bool) -> bool:
    """1AB34E (left edge) / 1AB44C (right edge): one 16-cell column into plane A."""
    if not _settle(read, write, COLUMN_DEBT, WINDOW_X):
        return False
    wx, wy = read(WINDOW_X, 2), read(WINDOW_Y, 2)
    rows = NAME_ROW_TABLE + ((wy >> 3) & 0x1F) * 4
    column = ((wx >> 2) + (0x58 if right else 0)) & 0x7E
    column2 = (column + 2) & 0x7E
    cursor = _row_start(read, wy) + (0x2C if right else 0)
    cell_x = wx >> 4
    if right:
        if cell_x >= (read(MAP_WIDTH, 2) - RIGHT_EDGE_CELLS) & 0xFFFF:
            return False
    elif cell_x < 1:
        return False
    cursor = (cursor + 2 * cell_x) & 0xFFFFFFFF
    write(MAP_CURSOR, cursor, 4)
    stride = _signed_word(read(MAP_STRIDE, 2))
    table = read(CELL_TILES, 4)
    for _ in range(COLUMN_CELLS):
        tiles = cell_tiles(rom, table, read(cursor, 2))
        upper, lower = read(rows, 4), read(rows + 4, 4)
        rows += 8
        vdp.control_long(_name_command(upper, column)); vdp.data(tiles[0])
        vdp.control_long(_name_command(upper, column2)); vdp.data(tiles[1])
        vdp.control_long(_name_command(lower, column)); vdp.data(tiles[2])
        vdp.control_long(_name_command(lower, column2)); vdp.data(tiles[3])
        cursor = (cursor + stride) & 0xFFFFFFFF
    return True


def draw_row(read, write, rom, vdp, bottom: bool) -> bool:
    """1AB66C (top edge) / 1AB55A (bottom edge): one 23-cell row into plane A."""
    if not _settle(read, write, ROW_DEBT, WINDOW_Y):
        return False
    wx, wy = read(WINDOW_X, 2), read(WINDOW_Y, 2)
    rows = NAME_ROW_TABLE + (((wy >> 3) + (0x1E if bottom else 0)) & 0x1F) * 4
    column = column2 = (wx >> 2) & 0x7E
    cursor = (_row_start(read, (wy + 0xF0) if bottom else wy) + 2 * (wx >> 4)) & 0xFFFFFFFF
    write(MAP_CURSOR, cursor, 4)
    upper, lower = read(rows, 4), read(rows + 4, 4)
    table = read(CELL_TILES, 4)
    for _ in range(ROW_CELLS):
        tiles = cell_tiles(rom, table, read(cursor, 2))
        cursor = (cursor + 2) & 0xFFFFFFFF
        vdp.control_long(_name_command(upper, column)); vdp.data(tiles[0])
        column = (column + 2) & 0x7E
        vdp.control_long(_name_command(upper, column)); vdp.data(tiles[1])
        column = (column + 2) & 0x7E
        vdp.control_long(_name_command(lower, column2)); vdp.data(tiles[2])
        column2 = (column2 + 2) & 0x7E
        vdp.control_long(_name_command(lower, column2)); vdp.data(tiles[3])
        column2 = (column2 + 2) & 0x7E
    return True


# flag byte -> (row strip?, far edge?)  in the order 1AAA2A tests them
STRIPS = ((STRIP_LEFT, False, False), (STRIP_RIGHT, False, True),
          (STRIP_TOP, True, False), (STRIP_BOTTOM, True, True))


def draw_pending_strips(read, write, rom, vdp, spawn_walk) -> None:
    """1AAA2E..1AAA7E: every raised strip flag draws its strip, walks it for spawns, and is cleared."""
    if read(STRIPS_SUSPENDED, 1):
        return
    for flag, row, far in STRIPS:
        if not read(flag, 1):
            continue
        drawn = (draw_row if row else draw_column)(read, write, rom, vdp, far)
        if drawn:
            spawn_walk(row=row, far=far)
        write(flag, 0, 1)
