"""Real Z80 window accesses cannot silently cross an atomic RAM operation."""
import pytest

from aladdin_sega.machine import Machine, NativeError


def sound_bank_rom(*, read_window):
    rom = bytearray(4096)
    rom[:8] = bytes.fromhex("00ff8000 00000200")
    code = bytearray()
    def word(address, value):
        code.extend(bytes.fromhex("33fc") + value.to_bytes(2, "big") + address.to_bytes(4, "big"))
    word(0xa11100, 0x100)
    word(0xa11200, 0)
    # Nine serial one bits select the top 32 KiB work-RAM bank.
    program = bytes.fromhex("3e01") + bytes.fromhex("320060") * 9
    program += bytes.fromhex("3a0080 18fb") if read_window else bytes.fromhex("18fe")
    for offset, value in enumerate(program):
        code.extend(bytes.fromhex("13fc") + value.to_bytes(2, "big") + (0xa00000 + offset).to_bytes(4, "big"))
    word(0xa11200, 0x100)
    word(0xa11100, 0)
    gate = 0x200 + len(code)
    code.extend(bytes.fromhex("60fe"))
    rom[0x200:0x200 + len(code)] = code
    return bytes(rom), gate


def operation(machine, pc):
    return dict(target=machine.info["tick"] + 100_000, cycles=2000, instructions=1,
                last_pc=pc, writes=[(0xff8000, 0x12)], registers={"pc": pc})


def test_current_shared_bank_refuses_before_candidate_effects():
    rom, gate = sound_bank_rom(read_window=False)
    with Machine(rom) as machine:
        machine.run(target=20_000)
        machine.gates([gate])
        assert machine.run(instructions=1) == "gate"
        before = machine.snapshot()
        assert not machine.atomic(**operation(machine, gate))
        assert machine.snapshot() == before


def test_bank_change_during_atomic_is_detected_before_observation_and_invalidates():
    rom, gate = sound_bank_rom(read_window=True)
    with Machine(rom) as machine:
        machine.gates([gate])
        assert machine.run(instructions=1000) == "gate"
        with pytest.raises(NativeError, match="Atomic execution failed"):
            machine.atomic(**operation(machine, gate))
        with pytest.raises(NativeError, match="Execution failed"):
            machine.snapshot()
        with pytest.raises(NativeError, match="invalidated"):
            machine.run(instructions=1)
