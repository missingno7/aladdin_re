import hashlib
import pytest

from aladdin_sega.machine import Machine, NativeError
from aladdin_sega.profile import FRAME_TICKS, DEFAULT_ROM, read_rom


def synthetic_rom():
    rom = bytearray(1024)
    rom[0:8] = bytes.fromhex("00ff8000 00000200")
    # MOVE.W #$1234,$FF0010 ; BRA.S back to the store.
    rom[0x200:0x20a] = bytes.fromhex("33fc123400ff0010 60f6")
    return bytes(rom)


def test_intercept_before_store_bypass_once_and_restore():
    with Machine(synthetic_rom()) as m:
        m.gate(0x200)
        initial = m.snapshot()
        assert m.run(instructions=10) == "gate"
        assert m.peek_ram(0x10, 2) == b"\0\0"
        assert m.info["m68k_instructions"] == 0
        assert m.snapshot() == initial
        m.gate(0x200, bypass_once=True)
        assert m.run(instructions=10) == "gate"
        assert m.peek_ram(0x10, 2) == b"\x12\x34"
        assert m.info["m68k_instructions"] == 2
        after = m.snapshot()
        address = m.ram_address
        m.restore(initial)
        assert m.ram_address == address
        assert m.peek_ram(0x10, 2) == b"\0\0"
        m.gate(0x200, bypass_once=True)
        m.run(instructions=10)
        assert m.snapshot() == after


def test_snapshot_rejection_is_atomic_and_handles_close():
    m = Machine(synthetic_rom())
    with m:
        m.run(instructions=5)
        original = m.snapshot()
        corrupt = bytearray(original)
        corrupt[20] ^= 1
        with pytest.raises(NativeError, match="integrity"):
            m.restore(corrupt)
        assert m.snapshot() == original
        with pytest.raises(NativeError, match="one active"):
            Machine(synthetic_rom())
    with pytest.raises(NativeError, match="closed"):
        m.peek_ram(0)


def test_chunking_sound_and_snapshot_suffix():
    with Machine(synthetic_rom()) as m:
        m.run(instructions=91)
        anchor = m.snapshot()
        m.audio()
        m.run(instructions=209)
        one_state, one_pcm = m.snapshot(), m.audio()
        m.restore(anchor)
        chunks = []
        for n in [31, 70, 108]:
            m.run(instructions=n)
            chunks.append(m.audio())
        assert m.snapshot() == one_state
        assert b"".join(chunks) == one_pcm
        assert len(one_pcm) > 0


def test_invalid_limits_and_mutant():
    with Machine(synthetic_rom()) as m:
        with pytest.raises(ValueError):
            m.run(target=-1)
        m.run(instructions=3)
        expected = hashlib.sha256(m.snapshot()).digest()
    mutant = bytearray(synthetic_rom())
    mutant[0x203] = 0x35
    with Machine(mutant) as m:
        m.run(instructions=3)
        assert m.peek_ram(0x10, 2) != b"\x12\x34"
        assert hashlib.sha256(m.snapshot()).digest() != expected


def test_irq_admission_precedes_handler_gate_and_trap_resumes():
    rom = bytearray(synthetic_rom())
    rom[0x78:0x7c] = (0x240).to_bytes(4, "big")
    # Enable interrupts and VDP VINT, then spin. Handler writes a witness and RTEs.
    rom[0x200:0x20e] = bytes.fromhex("46fc2000 33fc816400c00004 60fe")
    rom[0x240:0x24a] = bytes.fromhex("33fcbeef00ff0012 4e73")
    with Machine(bytes(rom)) as m:
        m.gate(0x240)
        assert m.run(target=FRAME_TICKS) == "gate"
        assert m.info["vblanks"] == 1
        assert m.info["pc"] == 0x240
        assert m.peek_ram(0x12, 2) == b"\0\0"
        anchor = m.snapshot()
        m.gate(0x240, bypass_once=True)
        m.run(instructions=2)
        assert m.peek_ram(0x12, 2) == b"\xbe\xef"
        expected = m.snapshot()
        m.restore(anchor)
        m.gate(0x240, bypass_once=True)
        m.run(instructions=2)
        assert m.snapshot() == expected
    rom[0x80:0x84] = (0x240).to_bytes(4, "big")
    rom[0x200:0x204] = bytes.fromhex("4e40 60fe")  # TRAP #0; spin
    with Machine(bytes(rom)) as m:
        m.gate(0x240)
        assert m.run(instructions=10) == "gate"
        assert m.info["m68k_instructions"] == 1
        assert m.peek_ram(0x12, 2) == b"\0\0"


@pytest.mark.skipif(not DEFAULT_ROM.exists(), reason="Local user ROM unavailable")
def test_real_rom_boot_restore_with_audio():
    with Machine(read_rom()) as m:
        # Native PCM capture is deliberately bounded.  Drain during the long
        # boot prefix; host output is not part of a native snapshot.
        for frame in range(1, 301):
            m.run(target=FRAME_TICKS * frame)
            m.audio()
        anchor = m.snapshot()
        m.run(target=FRAME_TICKS * 360)
        expected, audio, frame = m.snapshot(), m.audio(), m.frame()
        m.restore(anchor)
        m.run(target=FRAME_TICKS * 360)
        assert m.snapshot() == expected
        assert m.audio() == audio
        assert m.frame() == frame
        assert m.info["z80_instructions"] > 0
        assert len(audio) > 0
