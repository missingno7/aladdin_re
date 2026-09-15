"""Standalone game state with a RAM-like backing store.

The representation is deliberately the original's 64 KB work RAM (plus the
ROM) so that every recovered component keeps its exact, testable mapping
to the original; ownership of execution is what distinguishes the native
runtime, not the memory layout.  Named views (records, player, HUD) are
built on top through :mod:`aladdin_sega.game.objects.record` and the
address tables in :mod:`aladdin_sega.game.objects.script_engine`.
"""
from __future__ import annotations
from ..game.objects.record import RecordView, RECORD_TABLE, RECORD_SIZE, RECORD_COUNT
from ..game.objects.script_engine import Memory
from .vdp import Vdp


class NativeGap(Exception):
    """Native execution reached behavior that is not recovered yet."""
    def __init__(self, step: str, pc: int, detail: str = '', frame: int | None = None):
        super().__init__(f'NativeGap at {step} ({pc:06X}) frame {frame}: {detail}')
        self.step, self.pc, self.detail, self.frame = step, pc, detail, frame


class GameState:
    """Work RAM, ROM and the frame clock; the sole owner of state in native execution."""
    def __init__(self, ram: bytearray, rom: bytes, frame: int = 0):
        self.ram = ram
        self.rom = rom
        self.frame = frame
        self.buttons = 0
        self.buttons_low = None   # the mask the second port read (the TH-low byte) saw, when it differs
        self.events = []          # platform-facing event stream: ('sound', id), ('frame_upload', slot, descriptor), ...
        self.vdp = Vdp(self.bus_read)
        self.pads = None          # callable(frame) -> recorded pad mask; the frame clock is the VBlank count
        self.replay = None        # a replay.ReplayClock when recorded input must line up with the original's timing
        self.on_vblank = None     # the VBlank handler's RAM effects (frame.py sets it): run once per VBlank passed

    def advance_frames(self, count: int = 1) -> None:
        """VBlanks passed (waited for, or spent working): the handler runs for each, the pad clock moves with them."""
        for _ in range(count):
            if self.on_vblank is not None:
                self.on_vblank(self)
            self.frame += 1
            self.buttons_low = None
            if self.pads is not None:
                self.buttons = self.pads(self.frame)

    def bus_read(self, address: int, size: int = 1) -> int:
        """A read on the 68k bus as the VDP's DMA sees it: ROM below 400000, work RAM at FF0000."""
        if address < 0x400000:
            return int.from_bytes(self.rom[address:address + size], 'big')
        return self.read(address, size)

    @classmethod
    def from_machine(cls, machine, frame: int, rom: bytes) -> 'GameState':
        return cls(bytearray(machine.peek_ram(0, 65536)), rom, frame)

    def read(self, address: int, size: int = 1) -> int:
        a = address & 0xFFFF
        return int.from_bytes(self.ram[a:a + size], 'big')

    def write(self, address: int, value: int, size: int = 1) -> None:
        a = address & 0xFFFF
        self.ram[a:a + size] = (value & ((1 << (8 * size)) - 1)).to_bytes(size, 'big')

    def memory(self) -> Memory:
        return Memory(self.read, self.write, self.rom)

    def record(self, slot: int) -> RecordView:
        return RecordView(RECORD_TABLE + RECORD_SIZE * slot, self.read, self.write)

    def records(self):
        return [self.record(slot) for slot in range(RECORD_COUNT)]

    def copy(self) -> 'GameState':
        other = GameState(bytearray(self.ram), self.rom, self.frame)
        other.buttons = self.buttons
        return other
