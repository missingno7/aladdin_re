"""zb_common: shared setup for the Z80 bank-guard study (2026-09-16).  Read-only research tooling.

Puts the checkout's ``src`` and ``scripts`` on sys.path (the WORKING tree: the native library in
build/ is ABI 3, which the committed tree's binding predates), records the provenance of what ran
(HEAD, the working-tree diff digest, the native binary's digest) and decodes the Z80 box's state out
of a native snapshot for diagnostics only -- the production binding never decodes a snapshot; this
is research instrumentation and the layout it assumes is the pinned donor's PFGENS02 codec
(``port_forge/src/platform/genesis/snapshot.hpp``: zcpu, ram[8192], four booleans, bank u16,
bank_bits u32, then the counters).
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('GENESIS_NATIVE_LIBRARY', str(ROOT / 'build' / 'libgenesis_native.dll'))

from gods_sega.profile import GODS  # noqa: E402

FT = GODS.board.frame_ticks
DIV = GODS.board.m68k_divider
ZDIV = GODS.board.z80_divider
LINE = FT / 262.0
VBLANK_IRQ = 766_080                  # measured in the verification pass: raster line 224.0
Z80_CODE_BASE = 0xF4570               # the driver the 68000 copies to Z80 RAM 0000 (0F44CE)
Z80_CODE_SIZE = 0x1074

# The Gods driver's two bank routines (Z80 addresses; artifacts/gods/research/z80-bank-guard/gods-z80-driver.asm).
BANK_A = (0x013C, 0x0169)             # cells 1FA6/1FA8 -> bank 01E (ROM 0F0000): called at IRQ entry 004F and init 0004
BANK_B = (0x0169, 0x0196)             # cells 1FAA/1FAC -> bank 01F (ROM 0F8000): called at IRQ exit 00F5
BANK_WRITE_PCS = (0x0144, 0x0151, 0x0171, 0x017E)


def provenance():
    def git(*args):
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    diff = git('diff', '--', 'src', 'native', 'scripts').encode()
    lib = Path(os.environ['GENESIS_NATIVE_LIBRARY'])
    return {'head': git('rev-parse', 'HEAD'), 'working_tree_diff_sha256': hashlib.sha256(diff).hexdigest(),
            'native_library': str(lib), 'native_library_sha256': hashlib.sha256(lib.read_bytes()).hexdigest()}


class Z80View:
    """Locate the Z80 box inside a native snapshot once (by the driver image) and decode it afterwards."""
    def __init__(self, rom, base=Z80_CODE_BASE, offset=0, length=64):
        """``rom[base:]`` is the driver image the 68000 copies to Z80 RAM 0000; the locator is its
        ``length`` bytes at ``offset`` (choose code the driver never overwrites)."""
        self.code = rom[base + offset:base + offset + length]
        self.offset = offset
        self.ram_at = None

    def decode(self, snapshot):
        if self.ram_at is None or snapshot[self.ram_at + self.offset:self.ram_at + self.offset + len(self.code)] != self.code:
            i = snapshot.find(self.code)
            if i < 0:
                return None
            self.ram_at = i - self.offset
        z = self.ram_at
        cpu = z - 31
        u16 = lambda at: int.from_bytes(snapshot[at:at + 2], 'little')
        u32 = lambda at: int.from_bytes(snapshot[at:at + 4], 'little')
        u64 = lambda at: int.from_bytes(snapshot[at:at + 8], 'little')
        tail = z + 8192
        return {'pc': u16(cpu + 22), 'sp': u16(cpu + 20), 'ix': u16(cpu + 16), 'iy': u16(cpu + 18),
                'hl': (snapshot[cpu + 6] << 8) | snapshot[cpu + 7], 'de': (snapshot[cpu + 4] << 8) | snapshot[cpu + 5],
                'a': snapshot[cpu], 'b': snapshot[cpu + 2],
                'iff1': bool(snapshot[cpu + 26]), 'halted': bool(snapshot[cpu + 29]),
                'bus_requested': bool(snapshot[tail]), 'reset_asserted': bool(snapshot[tail + 1]),
                'bank': u16(tail + 4), 'bank_bits': u32(tail + 6), 'master_position': u64(tail + 10),
                't_states': u64(tail + 18), 'instructions': u64(tail + 26), 'interrupts_taken': u64(tail + 34),
                'ram': snapshot[z:z + 8192]}


def frame_line(tick):
    return (tick % FT) / LINE


def load_fixture(game, fixture):
    """The fixture's frame, the pad mask in force and the input events from that frame on."""
    import json
    from genesis_re.history import HistoryStore
    fixture = Path(fixture)
    meta = json.loads(fixture.with_suffix('.json').read_text())
    frame = meta['frame']
    store = HistoryStore(game.history_path(), game.history_root)
    path = store.flatten(store.resolve(meta['history_id']))
    buttons = 0
    for e in path['events']:
        if e['frame'] < frame:
            buttons = e['buttons']
    events = [e for e in path['events'] if e['frame'] >= frame]
    return fixture.read_bytes(), frame, buttons, events, meta
