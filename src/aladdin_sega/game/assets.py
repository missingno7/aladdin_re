"""ROM assets behind the object system: sprite frames, pieces, tile data, templates.

Recovered from the script interpreter's frame resolution (1AC784), the
frame-change hook that queues VRAM uploads (1AC6D0), the sprite table
builder (1AB7C4) and the DMA queue flush (1AC726).

A frame word in an animation script is the ROM address of a long that
points at a *frame descriptor*: a 6-byte header (piece count minus one,
then four bytes of extent) followed by 12-byte pieces.  Each piece names a
*tile record* (a 16-bit ROM address) holding the DMA length, the VRAM
advance, the OAM size/flags word and the piece's pixel width and height,
plus the piece's signed x/y offset from the object's feet, the DMA source
(VDP registers 95/96/97, in words) and the tile-index advance.  Tiles are
plain 4bpp Genesis tiles, uploaded by DMA when the frame changes.
"""
from __future__ import annotations
from dataclasses import dataclass
from .objects.record import ObjectTemplate, template_sites

FRAME_TABLE_TOP = 0xE000


@dataclass(frozen=True)
class TileRecord:
    address: int
    dma_words: int        # VDP registers 93/94
    vram_advance: int     # bytes of VRAM the piece occupies (word at +4)
    oam_size: int         # OAM size/link bits or-ed into the sprite entry (word at +6)
    width: int            # pixels (byte at +8), used for horizontal flip
    height: int           # pixels (byte at +9), used for vertical flip

    @classmethod
    def from_rom(cls, rom: bytes, address: int) -> 'TileRecord':
        d = rom[address:address + 10]
        return cls(address, (d[3] << 8) | d[1], int.from_bytes(d[4:6], 'big'),
                   int.from_bytes(d[6:8], 'big'), d[8], d[9])

    @property
    def tiles(self) -> int:
        return self.dma_words * 2 // 32

    @property
    def size_tiles(self) -> tuple[int, int]:
        """OAM size field: (width, height) in tiles."""
        size = (self.oam_size >> 8) & 0xF
        return (size >> 2) + 1, (size & 3) + 1


@dataclass(frozen=True)
class SpritePiece:
    address: int
    tile_record: TileRecord
    dx: int               # signed offset from the object's feet
    dy: int
    source: int           # ROM byte address of the tile data
    tile_advance: int     # tile-index advance to the next piece (word at +A)

    @classmethod
    def from_rom(cls, rom: bytes, address: int) -> 'SpritePiece':
        d = rom[address:address + 12]
        ref = int.from_bytes(d[0:2], 'big')
        # offsets carry the OAM's 0x80 bias (the builder subtracts 0x80 / 0x100 - 0x80)
        dx, dy = d[2] - 0x80, d[3] - 0x80
        source_words = d[5] | (d[7] << 8) | (d[9] << 16)
        return cls(address, TileRecord.from_rom(rom, ref), dx, dy, source_words * 2,
                   int.from_bytes(d[10:12], 'big'))


@dataclass(frozen=True)
class SpriteFrame:
    address: int
    extent: bytes         # header bytes 2..5
    pieces: tuple

    @classmethod
    def from_rom(cls, rom: bytes, address: int) -> 'SpriteFrame':
        count = int.from_bytes(rom[address:address + 2], 'big') + 1
        pieces = tuple(SpritePiece.from_rom(rom, address + 6 + 12 * i) for i in range(count))
        return cls(address, bytes(rom[address + 2:address + 6]), pieces)

    @classmethod
    def from_word(cls, rom: bytes, word: int) -> 'SpriteFrame':
        return cls.from_rom(rom, int.from_bytes(rom[word:word + 4], 'big'))

    @property
    def sources(self) -> tuple:
        return tuple(sorted({(p.source, p.tile_record.dma_words) for p in self.pieces}))


def decode_tile(rom: bytes, address: int) -> list[list[int]]:
    """One 8x8 4bpp tile as rows of palette indices."""
    rows = []
    for y in range(8):
        row = []
        for x in range(4):
            b = rom[address + y * 4 + x]
            row += [b >> 4, b & 0xF]
        rows.append(row)
    return rows


GRAY = [(0, 0, 0, 0)] + [(17 * i, 17 * i, 17 * i, 255) for i in range(1, 16)]


def render_frame(rom: bytes, frame: SpriteFrame, palette=None, *, scale=1):
    """Compose a frame's pieces into an RGBA image (needs Pillow); the origin is the feet."""
    from PIL import Image
    palette = palette or GRAY
    xs = [p.dx for p in frame.pieces] + [p.dx + 8 * p.tile_record.size_tiles[0] for p in frame.pieces]
    ys = [p.dy for p in frame.pieces] + [p.dy + 8 * p.tile_record.size_tiles[1] for p in frame.pieces]
    x0, y0 = min(xs), min(ys)
    image = Image.new('RGBA', (max(xs) - x0, max(ys) - y0), (0, 0, 0, 0))
    pixels = image.load()
    for piece in frame.pieces:
        w, h = piece.tile_record.size_tiles
        index = 0
        for column in range(w):          # Genesis sprites store tiles column by column
            for row in range(h):
                tile = decode_tile(rom, piece.source + 32 * index)
                index += 1
                for ty in range(8):
                    for tx in range(8):
                        v = tile[ty][tx]
                        if v:
                            pixels[piece.dx - x0 + column * 8 + tx, piece.dy - y0 + row * 8 + ty] = palette[v]
    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
    return image, (x0, y0)


def templates(rom: bytes) -> list[ObjectTemplate]:
    return [ObjectTemplate.from_rom(rom, address) for address in template_sites(rom)]
