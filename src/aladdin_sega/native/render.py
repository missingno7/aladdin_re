"""A frame from the native VDP state: the two planes, the sprites and the backdrop, as the Genesis VDP composes them.

Presentation only.  The game's own outputs are the port writes the VDP model
applies to VRAM, CRAM and VSRAM; this module reads those memories and the
registers and produces the 320 x 224 image a television would show, so the
native player can display it and so a rendered frame can be compared with
the original's.  It models what Aladdin uses: H40, plane sizes from register
0x10, name tables from registers 2 and 4, the horizontal scroll table from
register 0x0D in full / per-cell / per-line mode, vertical scroll from VSRAM
in full or two-cell mode, the sprite table from register 5 with linked
entries and column-major tiles, priority between sprites and planes, and the
backdrop colour from register 7.  Not modelled: the window plane, shadow /
highlight, interlace, the per-line sprite limits.
"""
from __future__ import annotations
import numpy as np

WIDTH, HEIGHT = 320, 224


def cram_rgb(cram: bytes) -> np.ndarray:
    """The 64 CRAM colours as (64, 3) uint8 RGB (3-bit channels scaled to 8)."""
    words = np.frombuffer(bytes(cram), dtype='>u2').astype(np.uint32)
    r = (words & 0x00E) << 4
    g = (words & 0x0E0)
    b = (words & 0xE00) >> 4
    out = np.stack([r, g, b], axis=1).astype(np.uint8)
    out |= out >> 3          # 0xE0 -> 0xFC: spread the 3-bit channel over the byte
    return out


def _tiles(vram: bytes) -> np.ndarray:
    """VRAM as (2048, 8, 8) colour indices (4 bits, high nibble first)."""
    raw = np.frombuffer(bytes(vram), dtype=np.uint8).reshape(2048, 8, 4)
    high = raw >> 4
    low = raw & 0xF
    return np.stack([high, low], axis=3).reshape(2048, 8, 8)


def _plane(vdp, base: int, tiles: np.ndarray, plane_w: int, plane_h: int):
    """A plane's full image: colour index (0 = transparent) with the palette line folded in, and its priority."""
    entries = np.frombuffer(bytes(vdp.vram[base:base + plane_w * plane_h * 2]), dtype='>u2').reshape(plane_h, plane_w)
    index = entries & 0x7FF
    hflip = (entries >> 11) & 1
    vflip = (entries >> 12) & 1
    palette = ((entries >> 13) & 3).astype(np.uint8)
    priority = (entries >> 15) & 1
    img = tiles[index]                                    # (h, w, 8, 8)
    img = np.where(hflip[:, :, None, None] == 1, img[:, :, :, ::-1], img)
    img = np.where(vflip[:, :, None, None] == 1, img[:, :, ::-1, :], img)
    colour = (img + (palette[:, :, None, None] << 4)) * (img != 0)
    colour = colour.transpose(0, 2, 1, 3).reshape(plane_h * 8, plane_w * 8)
    prio = np.repeat(np.repeat(priority, 8, axis=0), 8, axis=1)
    return colour, prio


def render(vdp) -> np.ndarray:
    """The frame as (224, 320, 3) uint8 RGB."""
    r = vdp.registers
    tiles = _tiles(vdp.vram)
    colours = cram_rgb(vdp.cram)
    size = r[0x10]
    plane_w = (32, 64, 32, 128)[size & 3]
    plane_h = (32, 64, 32, 128)[(size >> 4) & 3]
    base_a, base_b = vdp.name_table_a(), vdp.name_table_b()
    hscroll_base = (r[0x0D] & 0x3F) << 10
    hmode = r[0x0B] & 3
    vmode = (r[0x0B] >> 2) & 1
    W, H = plane_w * 8, plane_h * 8
    ys = np.arange(HEIGHT)
    xs = np.arange(WIDTH)
    hs_words = np.frombuffer(bytes(vdp.vram[hscroll_base:hscroll_base + HEIGHT * 4]), dtype='>u2').reshape(HEIGHT, 2)
    vs_words = np.frombuffer(bytes(vdp.vsram[:0x50]), dtype='>u2').reshape(20, 2)
    frame_colour = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    frame_layer = np.zeros((HEIGHT, WIDTH), dtype=np.int8)       # 0 backdrop, 1 B low, 2 A low, 3 B high, 4 A high
    for plane_index, base in ((1, base_b), (0, base_a)):
        colour, prio = _plane(vdp, base, tiles, plane_w, plane_h)
        if hmode == 3:
            hs = hs_words[:, plane_index].astype(np.int64)
        elif hmode == 2:
            hs = hs_words[(ys // 8) * 8, plane_index].astype(np.int64)
        else:
            hs = np.full(HEIGHT, int(hs_words[0, plane_index]), dtype=np.int64)
        hs = np.where(hs >= 0x8000, hs - 0x10000, hs)
        if vmode:
            vs = vs_words[np.clip(xs // 16, 0, 19), plane_index].astype(np.int64)
        else:
            vs = np.full(WIDTH, int(vs_words[0, plane_index]), dtype=np.int64)
        X = (xs[None, :] - hs[:, None]) % W
        Y = (ys[:, None] + vs[None, :]) % H
        c = colour[Y, X]
        p = prio[Y, X]
        layer = np.where(p == 1, 3 + (1 - plane_index), 1 + (1 - plane_index))
        visible = (c != 0) & (layer > frame_layer)
        frame_colour = np.where(visible, c, frame_colour)
        frame_layer = np.where(visible, layer, frame_layer)
    # sprites, in link order: an earlier sprite hides a later one of the same priority
    table = (r[5] & 0x7F) << 9
    sprite_colour = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    sprite_prio = np.full((HEIGHT, WIDTH), -1, dtype=np.int8)
    seen = set()
    link = 0
    for _ in range(80):
        if link in seen:
            break
        seen.add(link)
        e = table + link * 8
        y = int.from_bytes(vdp.vram[e:e + 2], 'big') & 0x3FF
        size_link = int.from_bytes(vdp.vram[e + 2:e + 4], 'big')
        attr = int.from_bytes(vdp.vram[e + 4:e + 6], 'big')
        x = int.from_bytes(vdp.vram[e + 6:e + 8], 'big') & 0x1FF
        w, h = ((size_link >> 10) & 3) + 1, ((size_link >> 8) & 3) + 1
        link = size_link & 0x7F
        sx, sy = x - 128, y - 128
        if sx >= WIDTH or sy >= HEIGHT or sx + 8 * w <= 0 or sy + 8 * h <= 0:
            if link == 0:
                break
            continue
        index, hflip, vflip = attr & 0x7FF, (attr >> 11) & 1, (attr >> 12) & 1
        palette, priority = (attr >> 13) & 3, (attr >> 15) & 1
        block = np.zeros((8 * h, 8 * w), dtype=np.uint8)
        for col in range(w):
            for row in range(h):
                t = tiles[(index + col * h + row) & 0x7FF]
                block[row * 8:row * 8 + 8, col * 8:col * 8 + 8] = t
        if hflip:
            block = block[:, ::-1]
        if vflip:
            block = block[::-1, :]
        x0, y0 = max(sx, 0), max(sy, 0)
        x1, y1 = min(sx + 8 * w, WIDTH), min(sy + 8 * h, HEIGHT)
        part = block[y0 - sy:y1 - sy, x0 - sx:x1 - sx]
        target_c = sprite_colour[y0:y1, x0:x1]
        target_p = sprite_prio[y0:y1, x0:x1]
        put = (part != 0) & (target_p < 0)
        target_c[put] = (part + (palette << 4))[put]
        target_p[put] = priority
        if link == 0:
            break
    above = ((sprite_prio == 1) & (sprite_colour != 0)) | ((sprite_prio == 0) & (sprite_colour != 0) & (frame_layer <= 2))
    final = np.where(above, sprite_colour, frame_colour)
    backdrop = ((r[7] >> 4) & 3) * 16 + (r[7] & 0xF)
    final = np.where((final == 0) & (frame_layer == 0) & ~above, backdrop, final)
    return colours[final]
