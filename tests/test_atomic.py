"""Atomic native-operation admission is checked against the existing engine."""
import pytest

from genesis_re.machine import Machine, NativeError
from aladdin_sega.profile import FRAME_TICKS


def store_rom():
    rom = bytearray(1024)
    rom[0:8] = bytes.fromhex("00ff8000 00000200")
    # MOVE.W #$1234,$FF0010 ; BRA.S back to the store.
    rom[0x200:0x20A] = bytes.fromhex("33fc123400ff0010 60f6")
    return bytes(rom)


def masked_vint_rom():
    rom = bytearray(store_rom())
    # VINT enabled while reset SR keeps IRQ level 6 masked; then spin.
    rom[0x200:0x20A] = bytes.fromhex("33fc816400c00004 60fe")
    return bytes(rom)


def plan(machine, **changes):
    result = {
        "target": machine.info["tick"] + 1_000,
        "cycles": 20,
        "instructions": 1,
        "last_pc": 0x200,
        "writes": [(0xFF0010, 0x12), (0xFF0011, 0x34)],
        "registers": {"pc": 0x208},
    }
    result.update(changes)
    return result


def park(machine, pc=0x200):
    machine.gates([pc])
    assert machine.run(instructions=1) == "gate"
    assert machine.info["pc"] == pc


def test_atomic_store_matches_one_original_instruction_under_same_rom():
    rom = store_rom()
    with Machine(rom) as original:
        assert original.run(instructions=1) == "limit"
        expected = original.snapshot()
        expected_registers = original.registers()
        expected_ram = original.peek_ram(0x10, 2)

    with Machine(rom) as candidate:
        park(candidate)
        before = candidate.snapshot()
        assert candidate.atomic(**plan(candidate))
        assert candidate.snapshot() == expected
        assert candidate.registers() == expected_registers
        assert candidate.peek_ram(0x10, 2) == expected_ram
        assert before != expected


def test_atomic_deadline_and_masked_irq_refusals_leave_machine_unchanged():
    with Machine(store_rom()) as machine:
        park(machine)
        before = machine.snapshot()
        # Cost must be strictly inside the caller's deadline.
        assert not machine.atomic(**plan(machine, target=140))
        assert machine.snapshot() == before
        assert machine.run(instructions=1) == "gate"

    with Machine(masked_vint_rom()) as machine:
        machine.run(target=FRAME_TICKS)
        pc = machine.info["pc"]
        park(machine, pc)
        before = machine.snapshot()
        assert not machine.atomic(**plan(machine, last_pc=pc, registers={"pc": pc}))
        assert machine.snapshot() == before
        assert machine.run(instructions=1) == "gate"


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"writes": [(0xFEFFFF, 0)]}, "work RAM"),
        ({"writes": [(0xFF0010, 256)]}, "work RAM bytes"),
        ({"last_pc": 0x201}, "last instruction PC"),
        ({"registers": {"pc": 0x209}}, "continuation PC"),
        ({"registers": {"sr": 0}}, "status updates"),
    ],
)
def test_invalid_atomic_effects_are_rejected_without_mutation(changes, error):
    with Machine(store_rom()) as machine:
        park(machine)
        before = machine.snapshot()
        with pytest.raises((ValueError, NativeError), match=error):
            machine.atomic(**plan(machine, **changes))
        assert machine.snapshot() == before
        assert machine.run(instructions=1) == "gate"


def test_gate_list_and_bypass_once_preserve_each_stopped_boundary():
    with Machine(store_rom()) as machine:
        machine.gates([0x200, 0x208])
        assert machine.run(instructions=1) == "gate"
        assert machine.info["pc"] == 0x200
        machine.gate(0x200, bypass_once=True)
        assert machine.run(instructions=1) == "limit"
        assert machine.info["pc"] == 0x208
        assert machine.run(instructions=1) == "gate"
        assert machine.info["pc"] == 0x208
        machine.gates([])
        assert machine.run(instructions=1) == "limit"


def test_trace_guard_refuses_parked_atomic_operation_without_mutation():
    """The public ABI exposes CCR-only effects, so trace is a ROM-level guard."""
    rom = bytearray(store_rom())
    rom[0x24:0x28] = (0x240).to_bytes(4, "big")  # trace vector
    rom[0x200:0x208] = bytes.fromhex("007c8000 60fe")  # ORI.W #trace,SR; spin
    rom[0x240:0x244] = bytes.fromhex("4e71 60fe")
    with Machine(bytes(rom)) as machine:
        machine.gates([0x204])
        assert machine.run(instructions=1) == "limit"
        assert machine.registers()["sr"] & 0x8000
        # The stopped boundary is before trace delivery, which lets the engine
        # see and refuse the staged operation under its trace guard.
        assert machine.run(instructions=1) == "gate"
        assert machine.info["pc"] == 0x204
        before = machine.snapshot()
        assert not machine.atomic(**plan(machine, last_pc=0x204, registers={"pc": 0x204}))
        assert machine.snapshot() == before
