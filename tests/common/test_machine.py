import hashlib
import ctypes as C
import pytest

from genesis_re.machine import Machine, NativeError
from genesis_re.profile import FRAME_TICKS
from genesis_re.games import GAMES

GAME = GAMES["aladdin"]   # the common suite exercises real-cartridge mechanisms on this registered game
DEFAULT_ROM = GAME.rom_path


def _sized_export(machine):
    """Independent two-call ABI reference for byte-exact export qualification."""
    size = C.c_uint64()
    machine._call('export', None, 0, C.byref(size))
    buf = (C.c_uint8 * size.value)()
    machine._call('export', buf, len(buf), C.byref(size))
    return bytes(buf)


def test_single_export_matches_sized_export_and_returns_owned_bytes():
    with Machine(synthetic_rom()) as machine:
        previous = None
        for instructions in (0, 7, 29):
            if instructions:
                machine.run(instructions=instructions)
            expected = _sized_export(machine)
            count = machine.calls.get('export', 0)
            actual = machine.snapshot()
            assert machine.calls['export'] == count + 1
            assert actual == expected
            if previous:
                assert previous[0] == previous[1]  # next export cannot alias earlier bytes
                assert actual != previous[0]
            previous = actual, bytes(bytearray(actual))
        buffer = machine._snapshot_buffer
        machine.restore(previous[0])
        assert machine.snapshot() == previous[0]
        assert machine._snapshot_buffer is buffer
    assert machine._snapshot_buffer is None


def test_direct_frame_copy_matches_byte_sequence_and_keeps_exact_length():
    with Machine(GAME.read_rom()) as machine:
        first = None
        for frame in range(1, 121):
            machine.run(target=frame * FRAME_TICKS)
            machine.audio()
            if frame not in (1, 70, 120):
                continue
            buf = (C.c_uint8 * (320 * 240 * 3))()
            width, height = C.c_uint32(), C.c_uint32()
            machine._call('frame', buf, len(buf), C.byref(width), C.byref(height))
            expected = bytes(buf[:width.value * height.value * 3])
            actual = machine.frame()
            assert actual == (width.value, height.value, expected)
            assert len(actual[2]) == width.value * height.value * 3
            if first:
                assert first[0] == first[1]
            else:
                first = actual[2], bytes(bytearray(actual[2]))


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


def test_gate_capacity_supports_collection_family_and_rejects_overflow():
    with Machine(synthetic_rom()) as m:
        m.gates(list(range(0x200, 0x280, 2)))
        before = m.snapshot()
        with pytest.raises(NativeError, match='Invalid gate set'):
            m.gates(list(range(0x200, 0x282, 2)))
        assert m.snapshot() == before
        assert m.run(instructions=1) == 'gate'
        assert m.info['pc'] == 0x200


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
    with Machine(GAME.read_rom()) as m:
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
