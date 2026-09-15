"""The 66-byte object record: the runtime representation of every game object.

Recovered from the script interpreter (1AC784), the motion runner (1ADE36),
the record initializer (1AD3E8), the template initializer (1AE30A), the
sprite builder (1AB7C4) and the contact callbacks.  Field names are the
game's meaning; the offsets are the machine's.  Every reader of these
fields should go through :class:`RecordView` so that the same code runs
over live machine RAM, a RAM snapshot, or a standalone byte array.
"""
from __future__ import annotations
from dataclasses import dataclass

RECORD_SIZE = 66
RECORD_COUNT = 32                # slot 0 is the player, 1..24 the main pool, 25..30 the extra pool
RECORD_TABLE = 0xFF7E40          # slot 0
PLAYER_RECORD = RECORD_TABLE
MAIN_POOL = RECORD_TABLE + RECORD_SIZE            # FF7E82, 24 slots
EXTRA_POOL = MAIN_POOL + 24 * RECORD_SIZE         # FF84B2, 6 slots
PLAYER_KIND = 0x83
DYING_KIND = 0x84                 # every retirement arm retypes to this and hands the record a death script

# name: (offset, size, signed)
FIELDS = {
    'kind': (0x00, 1, False),          # collision class: index into the callback table at ROM 1CBE
    'hit_points': (0x01, 1, False),    # decremented by a sword hit; retirement at zero
    'x': (0x02, 2, False),             # world X of the feet
    'y': (0x04, 2, False),             # world Y of the feet
    'flags6': (0x06, 1, False),        # bit0 stop-on-ground, bit1 motion frozen, bit3 screen-space, bit5 spawn-bitmap owner, bit6 gravity
    'flags7': (0x07, 1, False),        # bit4 no downward motion when flags6.bit0, bit5 hidden
    'flags8': (0x08, 1, False),        # point value on retirement (added to the score accumulator)
    'facing': (0x09, 1, False),        # 00 right, FF left (opcodes EB/F7, F1/F5 use it)
    'motion_script': (0x0A, 4, False), # secondary channel: (dx, dy) pairs and opcodes 80..94
    'motion_loop': (0x0E, 4, False),   # secondary channel loop start
    'motion_count': (0x12, 1, False),  # secondary channel loop counter
    'frame': (0x14, 4, False),         # current sprite frame descriptor (ROM)
    'vel_x': (0x18, 2, True),          # X velocity, 0x28 per pixel step
    'vel_y': (0x1A, 2, True),          # Y velocity, 0x3C per pixel step
    'delta_x': (0x1C, 1, True),        # this frame's X motion (for riders)
    'delta_y': (0x1D, 1, True),
    'attributes': (0x1E, 2, False),    # OAM palette/priority bits or-ed onto every piece
    'script': (0x20, 4, False),        # animation script pointer (ROM)
    'loop': (0x24, 4, False),          # animation loop start
    'loop_count': (0x28, 1, False),
    'vram_slots': (0x29, 1, False),    # number of VRAM tile slots this object needs
    'vram_map': (0x2A, 4, False),      # pointer into the slot map at FFF008 (released by 1AE372)
    'vram': (0x2E, 4, False),          # VRAM tile address of slot 0 (table at ROM 11F500)
    'spawn_index': (0x32, 2, False),   # level object table index
    'spawn_flag': (0x34, 1, False),    # value restored into the spawn bitmap (FFAE87) when despawned
    'flip': (0x35, 1, False),          # vertical flip (opcode EB argument nonzero)
    'motion_delay': (0x36, 1, False),
    'delay': (0x37, 1, False),         # frames left on the current animation frame
    'saved_script': (0x38, 4, False),  # opcode FC target
    'flags3c': (0x3C, 1, False),       # bit0 no friction, bit1 keep when off-screen, bit2 carries rider, bit5 contact pending
    'flags3d': (0x3D, 1, False),
    'rider': (0x3E, 4, False),         # record carried by this one (opcode F5 modes 5/6)
}


def field_offset(name: str) -> int:
    return FIELDS[name][0]


class RecordView:
    """Named access to one record through ``read(address, size)`` / ``write(address, value, size)``.

    ``base`` is the record's address in the machine's address space
    (``FF7E40 + 66 * slot``); a standalone game supplies a byte array
    reader instead of live RAM.
    """
    __slots__ = ('base', '_read', '_write')

    def __init__(self, base: int, read, write=None):
        self.base = base
        self._read = read
        self._write = write

    @property
    def slot(self) -> int:
        return (self.base - RECORD_TABLE) // RECORD_SIZE

    def __getattr__(self, name):
        try:
            offset, size, signed = FIELDS[name]
        except KeyError:
            raise AttributeError(name) from None
        value = self._read(self.base + offset, size)
        if signed and value & (1 << (8 * size - 1)):
            value -= 1 << (8 * size)
        return value

    def __setattr__(self, name, value):
        if name in RecordView.__slots__:
            object.__setattr__(self, name, value)
            return
        offset, size, _ = FIELDS[name]
        if self._write is None:
            raise TypeError('read-only record view')
        self._write(self.base + offset, value & ((1 << (8 * size)) - 1), size)

    def byte(self, offset: int) -> int:
        return self._read(self.base + offset, 1)

    def snapshot(self) -> bytes:
        return bytes(self._read(self.base + i, 1) for i in range(RECORD_SIZE))

    def describe(self) -> dict:
        return {name: getattr(self, name) for name in FIELDS}


def bytes_view(buffer: bytearray, base_address: int = RECORD_TABLE):
    """Return (read, write) closures over a byte array that mirrors RAM from ``base_address``."""
    def read(address, size):
        offset = address - base_address
        return int.from_bytes(buffer[offset:offset + size], 'big')

    def write(address, value, size):
        offset = address - base_address
        buffer[offset:offset + size] = value.to_bytes(size, 'big')
    return read, write


@dataclass(frozen=True)
class ObjectTemplate:
    """The 19 ROM bytes the initializer 1AE30A copies into a fresh record."""
    address: int
    kind: int
    hit_points: int
    flags: bytes            # record +06..+09
    motion_script: int      # +0A
    attributes: int         # +1E
    script: int             # +20
    vram_slots: int         # +29
    flip: int               # +35
    flags3c: int            # +3C

    @classmethod
    def from_rom(cls, rom: bytes, address: int) -> 'ObjectTemplate':
        d = rom[address:address + 19]
        return cls(address, d[0], d[1], bytes(d[2:6]), int.from_bytes(d[6:10], 'big'),
                   int.from_bytes(d[10:12], 'big'), int.from_bytes(d[12:16], 'big'), d[16], d[17], d[18])

    def writes(self, record: int) -> list[tuple[int, int]]:
        """The byte writes the initializer performs (the rest of the record is cleared)."""
        out = [(record, self.kind), (record + 1, self.hit_points)]
        out += [(record + 6 + i, b) for i, b in enumerate(self.flags)]
        out += [(record + 0x0A + i, b) for i, b in enumerate(self.motion_script.to_bytes(4, 'big'))]
        out += [(record + 0x1E + i, b) for i, b in enumerate(self.attributes.to_bytes(2, 'big'))]
        out += [(record + 0x20 + i, b) for i, b in enumerate(self.script.to_bytes(4, 'big'))]
        out += [(record + 0x29, self.vram_slots), (record + 0x35, self.flip), (record + 0x3C, self.flags3c)]
        return out


def template_sites(rom: bytes, start=0x1B5200, end=0x1B7900) -> list[int]:
    """Every template address loaded with ``lea $1B7xxx,a6`` by the spawn callers."""
    found = set()
    for i in range(start, end):
        if rom[i:i + 2] == b'\x4d\xf9' and rom[i + 2:i + 4] == b'\x00\x1b':
            found.add(int.from_bytes(rom[i + 2:i + 6], 'big'))
    return sorted(found)
