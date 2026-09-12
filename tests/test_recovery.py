"""Pure contract checks for the deliberately small recovery candidate."""
from __future__ import annotations

import ctypes as C

import pytest
from aladdin_sega.recovered import clear_auxiliary_buffer, detach_object, LegacyExit

from aladdin_sega.machine import Machine
from aladdin_sega.recovery import (
    CALLER_ENTRY, LEAF_ENTRY, ROM_SHA256, Candidate, UnsupportedCandidate,
)


class FakeMachine:
    def __init__(self, registers, *, pc=LEAF_ENTRY, atomic_result=True, rom_sha256=ROM_SHA256):
        self._registers = dict(registers)
        self.info = {"pc": pc, "tick": 100}
        self.rom_sha256, self.ram = rom_sha256, bytearray(65536)
        self.atomic_result, self.atomic_call, self.gate_call, self.run_call = atomic_result, None, None, None
        self.rom = bytearray(0x400000)

    def registers(self):
        return dict(self._registers)

    def peek_ram(self, offset, size):
        return bytes(self.ram[offset:offset + size])

    def peek_rom(self, offset, size):
        if offset < 0 or offset + size > len(self.rom):
            raise ValueError("ROM range out of bounds")
        return bytes(self.rom[offset:offset + size])

    def atomic(self, **kwargs):
        self.atomic_call = kwargs
        return self.atomic_result

    def gate(self, pc, bypass_once=False):
        self.gate_call = (pc, bypass_once)

    def run(self, *, instructions):
        self.run_call = instructions

    def gates(self, pcs):
        self.armed = tuple(pcs)


def put(machine, address, value, width):
    machine.ram[address & 0xffff:(address & 0xffff) + width] = value.to_bytes(width, "big")


def leaf_machine(*, count=0, pointer=0xff2000, d0=0, sr=0x2000, a1=0xff1000, a7=0xff8000):
    registers = {**{f"d{i}": 0 for i in range(8)}, **{f"a{i}": 0 for i in range(8)}, "pc": LEAF_ENTRY, "sr": sr}
    registers.update({"d0": d0, "a1": a1, "a6": 0x001ad0fc, "a7": a7})
    machine = FakeMachine(registers)
    put(machine, a1 + 41, count, 1)
    put(machine, a1 + 42, pointer, 4)
    put(machine, a7, 0x00123456, 4)
    return machine


def test_leaf_null_path_preserves_register_width_and_sets_move_word_ccr():
    machine = leaf_machine(pointer=0, d0=0xfeed8000, sr=0x201f)
    plan = clear_auxiliary_buffer(machine, machine.registers())
    assert (plan.cycles, plan.instructions) == (96, 8)
    assert plan.registers == {"d0": 0xfeed8000, "pc": 0x123456, "a7": 0xff8004, "sr": 0x2018}
    assert plan.writes == ((0xff7ffc, 0x00), (0xff7ffd, 0x1a), (0xff7ffe, 0xd0), (0xff7fff, 0xfc),
                           (0xff7ffa, 0x80), (0xff7ffb, 0x00))


def test_leaf_nonnull_count_maximum_has_exact_loop_cost_and_byte_writes():
    machine = leaf_machine(count=255, d0=0x00001234)
    plan = clear_auxiliary_buffer(machine, machine.registers())
    assert (plan.cycles, plan.instructions) == (5810, 525)
    assert len(plan.writes) == 271  # two saved values, three record clears, and 256 DBF bytes
    assert plan.writes[-256:] == tuple((0xff2000 + offset, 0) for offset in range(256))
    assert plan.registers["sr"] == 0x2000


def test_leaf_alias_is_refused_before_staging_writes():
    machine = leaf_machine(pointer=0xff1010)
    with pytest.raises(UnsupportedCandidate, match="aliases"):
        clear_auxiliary_buffer(machine, machine.registers())


def test_caller_direct_route_models_overwritten_return_and_link_clear():
    machine = leaf_machine(count=0, pointer=0xff2000, d0=0xabcd1234, sr=0x201f)
    registers = machine._registers
    registers.update({"pc": CALLER_ENTRY, "a0": 0xff4000, "a2": 0xff3000})
    put(machine, 0xff3001, 0, 1)
    put(machine, 0xff103c, 0, 1)
    put(machine, 0xff103e, 0xff5000, 4)
    put(machine, 0xff503c, 0x07, 1)
    put(machine, 0xff503e, 0xdeadbeef, 4)
    put(machine, 0xff7d9e, 0x00456789, 4)
    plan = detach_object(machine, machine.registers())
    assert (plan.cycles, plan.instructions) == (432, 31)
    assert plan.registers == {"d0": 0xabcd1200, "a2": 0xff3002, "a7": 0xff8004,
                              "pc": 0x456789, "sr": 0x2010}
    assert plan.writes[-1] == (0xff8003, 0x89)
    assert (0xff503c, 0x03) in plan.writes
    assert any(address == 0xff503e for address, _ in plan.writes)


def test_caller_accepts_immutable_rom_script_source_without_a_ram_alias():
    machine = leaf_machine(count=0, pointer=0xff2000)
    machine._registers.update({"pc": CALLER_ENTRY, "a2": 0x100, "a0": 0xff4000})
    machine.rom[0x101] = 0
    put(machine, 0xff103c, 0, 1)
    put(machine, 0xff103e, 0, 4)
    put(machine, 0xff7d9e, 0x123456, 4)
    plan = detach_object(machine, machine.registers())
    assert plan.registers["a2"] == 0x102


@pytest.mark.parametrize("source,flag", [(1, 0), (0, 4)])
def test_open_caller_legacy_seam_leaves_entry_unchanged(source, flag):
    machine = leaf_machine()
    machine.info["pc"] = CALLER_ENTRY
    machine._registers.update(pc=CALLER_ENTRY, a2=0x100)
    machine.rom[0x101] = source
    put(machine, 0xff103c, flag, 1)
    before = bytes(machine.ram), machine.registers()
    with pytest.raises(LegacyExit) as error:
        detach_object(machine, machine.registers())
    assert error.value.target == 0x1ABE6E
    assert (bytes(machine.ram), machine.registers()) == before
    assert not Candidate("composed").on_gate(machine, 10000)
    assert machine.atomic_call is None
    assert machine.gate_call == (CALLER_ENTRY, True)
    assert machine.run_call == 1
    candidate = Candidate("composed")
    candidate.on_gate(machine, 10000)
    assert any("legacy 0x1ABE6E" in reason for reason in candidate.stats["fallback_reasons"])


@pytest.mark.parametrize("name", ["mutant-result", "mutant-continuation", "mutant-timing"])
def test_named_mutants_stage_a_distinct_leaf_result(name):
    machine = leaf_machine(count=0)
    original = clear_auxiliary_buffer(machine, machine.registers())
    mutant = Candidate(name)._mutate(original)
    assert mutant != original


def test_atomic_uses_the_scheduler_deadline_and_refusal_falls_back_one_opcode():
    accepted = leaf_machine(count=0)
    candidate = Candidate()
    assert candidate.on_gate(accepted, 10000)
    assert accepted.atomic_call["target"] == 10000
    assert accepted.atomic_call["last_pc"] == 0x1ae39e
    assert candidate.stats["leaf_hits"] == 1
    assert candidate.stats["replaced_m68k_instructions"] == 15
    assert candidate.stats["charged_m68k_cycles"] == 200
    refused = leaf_machine(count=0, d0=0x1234)
    refused.atomic_result = False
    assert not candidate.on_gate(refused, 10000)
    assert refused.gate_call == (LEAF_ENTRY, True)
    assert refused.run_call == 1
    assert candidate.stats["fallback_reasons"] == {"scheduler admission": 1}


def test_arm_refuses_any_rom_other_than_the_verified_rom():
    machine = leaf_machine()
    machine.rom_sha256 = "0" * 64
    with pytest.raises(UnsupportedCandidate, match="verified USA ROM"):
        Candidate().arm(machine)


LEAF_BYTES = bytes.fromhex(
    "2f0e3f002c69002abdfc00000000671842a9002a42a9002e42401029002942290029421e51c8fffc301f2c5f4e75"
)


def native_leaf_rom():
    """A cartridge whose reset code enters the exact ROM leaf at its real PC."""
    rom = bytearray(0x200000)
    rom[:8] = (0xfff000).to_bytes(4, "big") + (0x200).to_bytes(4, "big")
    # supervisor SR; D0; A1; A6; A7; JMP 0x1AE372
    startup = bytes.fromhex("46fc201f203cdeadbeef227c00ff10002c7c001ad0fc2e7c00ff80004ef9001ae372")
    rom[0x200:0x200 + len(startup)] = startup
    rom[0x300:0x302] = bytes.fromhex("60fe")
    rom[LEAF_ENTRY:LEAF_ENTRY + len(LEAF_BYTES)] = LEAF_BYTES
    return bytes(rom)


def native_write(machine, address, data):
    C.memmove(machine.ram_address + (address & 0xffff), data, len(data))


def prepared_native_leaf(count, pointer):
    machine = Machine(native_leaf_rom())
    native_write(machine, 0xff1029, bytes([count]))
    native_write(machine, 0xff102a, pointer.to_bytes(4, "big"))
    native_write(machine, 0xff102e, b"\x12\x34\x56\x78")
    if pointer:
        native_write(machine, pointer, bytes((index * 13) & 0xff for index in range(count + 1)))
    native_write(machine, 0xff8000, (0x300).to_bytes(4, "big"))
    machine.gates([LEAF_ENTRY])
    assert machine.run(instructions=64) == "gate"
    assert machine.info["pc"] == LEAF_ENTRY
    return machine


@pytest.mark.parametrize("count,pointer", [(0, 0), (255, 0xff2000)])
def test_native_atomic_leaf_matches_exact_rom_leaf_full_state(count, pointer):
    """This uses the exact 46 ROM bytes, not the plan-only fake machine."""
    original = prepared_native_leaf(count, pointer)
    try:
        stopped = original.snapshot()
        original.gates([LEAF_ENTRY, 0x300])
        original.gate(LEAF_ENTRY, bypass_once=True)
        assert original.run(instructions=1000) == "gate"
        expected = original.snapshot()
    finally:
        original.close()
    replacement = Machine(native_leaf_rom())
    try:
        replacement.restore(stopped)
        replacement.gates([LEAF_ENTRY])
        assert replacement.run(instructions=1) == "gate"
        plan = clear_auxiliary_buffer(replacement, replacement.registers())
        assert replacement.atomic(target=replacement.info["tick"] + 1_000_000,
                                  cycles=plan.cycles, instructions=plan.instructions,
                                  writes=list(plan.writes), registers=plan.registers,
                                  last_pc=plan.last_pc)
        assert replacement.info["pc"] == 0x300
        assert replacement.snapshot() == expected
    finally:
        replacement.close()
