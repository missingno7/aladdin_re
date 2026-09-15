"""The sound driver as a platform service: the ROM's Z80 driver on a dedicated machine, fed the native runtime's calls.

The game's side of the sound driver is a family of tiny entry points at
1E589A.. (each: link, a command byte in d0 to 1E57F4, an optional long
argument from 8(a6) to 1E5800, unlink): a request 1E58B8, the flush
1E589A, the fixed commands 1E58F4 (16), 1E5908 (1C) and 1E5912 (1D).
The driver itself is the Z80 program with the YM2612 and the PSG, which
the native runtime does not model: this service runs it on its own
Machine, the 68000 parked in a self-branch (ROM 2630: ``bra.s *``) after
the driver's initialisation 1E584A, and makes the entry-point calls on
that 68000 exactly as the game would (the argument on the stack, the
return into the park), so the driver sees the same command stream.  Each
game frame it runs the machine one frame and returns the PCM.

The native runtime's events ('sound', 'sound_flush', 'sound_command')
are its input; nothing here feeds back into the game.
"""
from __future__ import annotations
from ..machine import Machine

from ..profile import FRAME_TICKS
PARK = 0x2630                       # bra.s *
DRIVER_INIT_DONE = 0x1AA36C         # game init, after 1E584A: the first command follows
REQUEST, FLUSH = 0x1E58B8, 0x1E589A
ENTRY_FAMILY = (0x1E5890, 0x1E5960)


class SoundDriver:
    def __init__(self, rom: bytes):
        self.m = Machine(rom)
        self.m.audio_policy('capture')
        m = self.m
        m.gates([DRIVER_INIT_DONE])
        assert m.run(target=400 * FRAME_TICKS) == 'gate', 'the driver initialisation was not reached'
        self.commands = self._entries(rom)
        regs = dict(m.registers()); regs.update(pc=PARK)
        self._atomic(regs)
        m.gates([])
        m.audio()                                    # the boot's silence

    @staticmethod
    def _entries(rom):
        """code -> entry pc for the argument-less commands (jsr 1E57AC; moveq #code, d0)."""
        out = {}
        lo, hi = ENTRY_FAMILY
        for pc in range(lo, hi, 2):
            if rom[pc:pc + 6] == b'\x4E\xB9\x00\x1E\x57\xAC' and rom[pc + 6] == 0x70:
                out[rom[pc + 7]] = pc
        return out

    def _atomic(self, regs, writes=()):
        m = self.m
        assert m.atomic(target=m.info['tick'] + 1000, cycles=1, instructions=1, last_pc=PARK,
                        writes=list(writes), registers=regs)

    def call(self, routine, arg=None):
        """The game's call: the argument pushed, the return into the park, the routine run to its RTS."""
        m = self.m
        m.gates([PARK])
        assert m.run(target=m.info['tick'] + 2000) == 'gate'
        r = m.registers(); sp = r['a7']
        writes = [(sp - 8 + i, b) for i, b in enumerate(PARK.to_bytes(4, 'big'))]
        if arg is not None:
            writes += [(sp - 4 + i, b) for i, b in enumerate((arg & 0xFFFFFFFF).to_bytes(4, 'big'))]
        regs = dict(r); regs.update(pc=routine, a7=sp - 8)
        self._atomic(regs, writes)
        assert m.run(target=m.info['tick'] + FRAME_TICKS) == 'gate', f'the driver call {routine:06X} did not return'
        regs = dict(m.registers()); regs.update(a7=sp)
        self._atomic(regs)
        m.gates([])

    def event(self, event):
        kind = event[0]
        if kind == 'sound':
            _, _, sound_id, flush = event
            self.call(REQUEST, sound_id)
            if flush:
                self.call(FLUSH, sound_id)
        elif kind == 'sound_flush':
            self.call(FLUSH, event[2])
        elif kind == 'sound_command':
            code = event[2]
            if code not in self.commands:
                raise KeyError(f'no argument-less sound driver entry for command {code:02X}')
            self.call(self.commands[code])
        # 'sound_driver_init': the machine's own boot ran 1E584A with the same tables

    def advance(self) -> bytes:
        """One frame of the driver: little-endian stereo int16 PCM."""
        m = self.m
        m.run(target=m.info['tick'] + FRAME_TICKS)
        return m.audio()

    def close(self):
        self.m.close()
