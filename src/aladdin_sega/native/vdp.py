"""The VDP as the game drives it: the control and data ports, its memories and 68k-to-VDP DMA.

Every recovered step that talks to the video chip drives this object through
the same two ports the original writes (C00004 control, C00000 data), so
the native runtime keeps a real VRAM / CRAM / VSRAM image and, for
verification, an exact log of the port words in order.  The oracle side of
that comparison is :func:`aladdin_sega.native.oracle.trace_port_writes`.
"""
from __future__ import annotations

VRAM_WRITE, CRAM_WRITE, VSRAM_WRITE = 1, 3, 5


class Vdp:
    def __init__(self, read_memory=None):
        self.vram = bytearray(0x10000)
        self.cram = bytearray(0x80)
        self.vsram = bytearray(0x50)
        self.registers = [0] * 32
        self.registers[15] = 2
        self.read_memory = read_memory      # callable(address, size) over the 68k bus, for DMA sources
        self.log = []                       # every port write in order: ('control' | 'data', word)
        self._pending = None
        self._code = 0
        self._address = 0

    # -- the two ports -------------------------------------------------------------------------
    def control(self, word: int) -> None:
        word &= 0xFFFF
        self.log.append(('control', word))
        if self._pending is not None:
            first, self._pending = self._pending, None
            self._command(first, word)
        elif word & 0xC000 == 0x8000:
            self.registers[(word >> 8) & 0x1F] = word & 0xFF
        else:
            self._pending = word

    def control_long(self, value: int) -> None:
        self.control(value >> 16)
        self.control(value & 0xFFFF)

    def data(self, word: int) -> None:
        word &= 0xFFFF
        self.log.append(('data', word))
        self._pending = None
        self._store(word)

    def data_long(self, value: int) -> None:
        self.data(value >> 16)
        self.data(value & 0xFFFF)

    # -- memories ------------------------------------------------------------------------------
    def _store(self, word: int) -> None:
        target, a = self._code & 0xF, self._address
        if target == VRAM_WRITE:
            self.vram[a & 0xFFFE:(a & 0xFFFE) + 2] = word.to_bytes(2, 'big')
        elif target == CRAM_WRITE:
            self.cram[a & 0x7E:(a & 0x7E) + 2] = word.to_bytes(2, 'big')
        elif target == VSRAM_WRITE and (a & 0x7E) < 0x50:
            self.vsram[a & 0x7E:(a & 0x7E) + 2] = word.to_bytes(2, 'big')
        self._address = (a + self.registers[15]) & 0xFFFF

    def _command(self, first: int, second: int) -> None:
        self._code = ((first >> 14) & 3) | ((second >> 2) & 0x3C)
        self._address = (first & 0x3FFF) | ((second & 3) << 14)
        if self._code & 0x20 and self.registers[1] & 0x10:
            self._dma()

    def _dma(self) -> None:
        r = self.registers
        if r[0x17] & 0x80:
            raise NotImplementedError('VRAM fill / copy DMA is not modelled')
        length = ((r[0x14] << 8) | r[0x13]) or 0x10000
        source = (((r[0x17] & 0x7F) << 16) | (r[0x16] << 8) | r[0x15]) << 1
        if self.read_memory is None:
            raise RuntimeError('DMA needs a bus reader')
        for i in range(length):
            self._store(self.read_memory(source + 2 * i, 2))

    # -- views ---------------------------------------------------------------------------------
    def name_table_a(self) -> int:
        return (self.registers[2] & 0x38) << 10

    def name_table_b(self) -> int:
        return (self.registers[4] & 7) << 13
