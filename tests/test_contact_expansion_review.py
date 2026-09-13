"""Independent native checks for the contact expansion boundary.

The long original-ROM measurements live under the ignored grinding artifact
directory and are audited by their evidence scripts. These tests construct
their states directly so a clean checkout still exercises candidate behavior.
"""
from __future__ import annotations

import pytest
from pathlib import Path

from aladdin_sega import artifacts
from aladdin_sega.boundary import (COLLECTION_DISPATCH_ENTRY, COLLECTION_DISPATCH_RETURN,
                                   CONTACT_ENTRY, CONTACT_GLOBALS, UnsupportedCandidate,
                                   begin_contact_sound)
from aladdin_sega.game.objects.contact import contact_route
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from aladdin_sega.recovery import Candidate
from test_contact import contact_dispatch_machine, contact_machine
from test_recovery import FakeMachine, native_replace_rom, native_write, put


def reader(values):
    return lambda address, size=1: values.get(address, 0)


@pytest.mark.parametrize("address", [0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4])
def test_original_prefix_order_keeps_c1zero_before_later_reset_gates(address):
    assert contact_route(reader({0xFFF0C1: 0, address: 1})) == ("reset", "c1zero")


@pytest.mark.parametrize("address", [0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4])
def test_candidate_combined_c1zero_later_gate_matches_original(address):
    writes = [(0xFFF0C1, 0), (0xFFF57D, 0), (0xFFEFFA, 1), (0xFF7E21, 0),
              (address, 1)]
    with contact_machine() as machine:
        for at, value in writes:
            native_write(machine, at, bytes((value,)))
        initial = machine.snapshot()
        machine.gates([0])
        machine.gate(0x1AE4F8, bypass_once=True)
        assert machine.run(instructions=10_000) == "gate"
        machine.gates([])
        expected = (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio())

        machine.restore(initial)
        machine.audio()
        machine.gates([0x1AE4F8])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        assert candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats["contact_hits"] == 1


def _soundoff_machine():
    registers = {**{f"d{i}": 0x100 + i for i in range(8)},
                 **{f"a{i}": 0xFF7000 + i * 0x100 for i in range(8)},
                 "pc": 0x1AE4F8, "sr": 0x201F, "a7": 0xFF8000}
    machine = FakeMachine(registers)
    for address, value in ((0xFFF0C1, 0), (0xFFF57D, 0),
                           (0xFFF11F, 1), (0xFFEFFA, 1), (0xFF7E21, 0)):
        put(machine, address, value, 1)
    return machine


@pytest.mark.parametrize("address", [
    0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2,
    0xFFF0BE, 0xFFF0C1, 0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4,
    0xFFF173, 0xFFF0CC, 0xFFEFFF, 0xFFF11F, 0xFFF0D8, 0xFFF57D,
    0xFF7E21, 0xFF7E20, 0xFFEFFA, 0xFFF0B0, 0xFF7E60,
])
def test_soundoff_guard_rejects_global_alias_in_saved_return_scratch(address):
    machine = _soundoff_machine()
    machine._registers["a7"] = (address + 4) & ~1
    put(machine, machine._registers["a7"], 0x00123456, 4)
    before = machine.peek_ram(0, 65536), machine.registers()
    from aladdin_sega.boundary import begin_contact
    with pytest.raises(UnsupportedCandidate, match="aliases"):
        begin_contact(machine, machine.registers())
    assert (machine.peek_ram(0, 65536), machine.registers()) == before


def test_soundoff_ff7e20_blocked_decay_falls_back_to_original_timing():
    with contact_machine() as machine:
        for address, value in ((0xFFF0C1, 0), (0xFFF57D, 0),
                               (0xFFF11F, 1), (0xFFEFFA, 1),
                               (0xFF7E21, 0), (0xFF7E20, 1)):
            native_write(machine, address, bytes((value,)))
        initial = machine.snapshot()
        machine.gates([0])
        machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == "gate"
        machine.gates([])
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()

        machine.restore(initial)
        machine.audio()
        machine.gates([CONTACT_ENTRY])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        assert not candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
        machine.gates([0])
        assert machine.run(instructions=10_000) == "gate"
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected


RECORDED_DISPATCH_FIXTURE = Path(
    "artifacts/grinding/luna/next-subsystem/20260913T094652.830908Z/1AE9D4.dispatcher.alsnap"
)


def _observable(machine):
    return (machine.info, machine.registers(), machine.peek_ram(0, 65536),
            machine.frame()[2], machine.audio())


def _recorded_dispatch_run(candidate_mode):
    if not RECORDED_DISPATCH_FIXTURE.exists():
        pytest.skip("Original recorded dispatcher fixture is not present")
    rom = read_rom(DEFAULT_ROM)
    snapshot = artifacts.read_bounded(RECORDED_DISPATCH_FIXTURE)
    with Machine(rom) as machine:
        artifacts.restore_snapshot(machine, snapshot)
        if candidate_mode:
            machine.gates([COLLECTION_DISPATCH_ENTRY])
            assert machine.run(instructions=1) == "gate"
            candidate = Candidate("lifecycle")
            assert candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
            stats = candidate.stats
        else:
            machine.gates([COLLECTION_DISPATCH_RETURN])
            assert machine.run(instructions=100_000) == "gate"
            stats = None
        machine.gates([])
        outer = _observable(machine)
        assert machine.info["pc"] == COLLECTION_DISPATCH_RETURN
        assert not machine.in_sound_call
        assert machine.run(instructions=150) == "limit"
        future = _observable(machine)
        return outer, future, stats


def test_recorded_type7b_sound_witness_matches_outer_and_native_future():
    """Use the original-only census fixture for the real sound dispatcher seam."""
    original_outer, original_future, _ = _recorded_dispatch_run(False)
    candidate_outer, candidate_future, stats = _recorded_dispatch_run(True)
    fresh_outer, fresh_future, fresh_stats = _recorded_dispatch_run(True)
    assert candidate_outer == original_outer
    assert candidate_future == original_future
    assert fresh_outer == candidate_outer and fresh_future == candidate_future
    assert stats["gates"] == 2  # dispatcher entry + native sound return
    assert stats["collection_dispatch_hits"] == stats["contact_hits"] == 1
    assert stats["legacy_returns"] == 1
    assert stats["fallbacks"] == 0
    assert fresh_stats["gates"] == 2 and fresh_stats["fallbacks"] == 0


def _sound_prefix_machine():
    registers = {**{f"d{i}": 0x100 + i for i in range(8)},
                 **{f"a{i}": 0xFF7000 + i * 0x100 for i in range(8)},
                 "pc": 0x1AE4F8, "sr": 0x201F, "a7": 0xFF8000}
    machine = FakeMachine(registers)
    for address, value in ((0xFFF0C1, 0), (0xFFF57D, 1),
                           (0xFFF11F, 1), (0xFFEFFA, 1)):
        put(machine, address, value, 1)
    return machine


@pytest.mark.parametrize("address", [
    0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2,
    0xFFF0BE, 0xFFF0C1, 0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4,
    0xFFF173, 0xFFF0CC, 0xFFEFFF, 0xFFF11F, 0xFFF0D8, 0xFFF57D,
    0xFF7E21, 0xFF7E20, 0xFFEFFA, 0xFFF0B0, 0xFF7E60,
])
def test_sound_prefix_rejects_every_contact_global_alias_in_full_scratch_frame(address):
    machine = _sound_prefix_machine()
    machine._registers["a7"] = (address + 28) & ~1
    before = machine.peek_ram(0, 65536), machine.registers()
    with pytest.raises(UnsupportedCandidate, match="(aliases|unaligned)"):
        begin_contact_sound(machine, machine.registers())
    assert (machine.peek_ram(0, 65536), machine.registers()) == before


def test_sound_prefix_guard_covers_all_declared_contact_globals():
    declared = {address for _, address, _ in CONTACT_GLOBALS}
    assert {0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2, 0xFFF0BE, 0xFFF0C1,
            0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4, 0xFFF173, 0xFFF0CC,
            0xFFEFFF, 0xFFF11F, 0xFFF0D8, 0xFFF57D, 0xFF7E21, 0xFF7E20,
            0xFFEFFA, 0xFFF0B0, 0xFF7E60} <= declared


def _contact_dispatch_machine_with_filler():
    """Build the dispatcher fixture with an explicit safe outer continuation."""
    original = Path("assets/Aladdin (USA).md")
    if not original.exists():
        pytest.skip("Original USA ROM required for contact qualification")
    rom = bytearray(native_replace_rom(COLLECTION_DISPATCH_ENTRY, 0x2000))
    source = original.read_bytes()
    for start, end in ((0x1CBE, 0x20BE), (0x1ABC82, 0x1ABCA2),
                       (0x1AE9D4, 0x1AE9DA), (0x1AE4F8, 0x1AE61A)):
        rom[start:end] = source[start:end]
    # The copied dispatcher fixture ends at the outer return. Fill its caller
    # continuation with NOPs so a real 150-instruction future can be compared.
    rom[COLLECTION_DISPATCH_RETURN:COLLECTION_DISPATCH_RETURN + 0x300] = b"\x4e\x71" * 0x180
    machine = Machine(bytes(rom))
    machine.gates([COLLECTION_DISPATCH_ENTRY])
    assert machine.run(instructions=64) == "gate"
    return machine


def _contact_machine_with_x_set():
    """Build the sound fixture with incoming CCR X set in the reset SR."""
    original = Path("assets/Aladdin (USA).md")
    if not original.exists():
        pytest.skip("Original USA ROM required for contact qualification")
    rom = bytearray(native_replace_rom(CONTACT_ENTRY, 0x2010))
    source = original.read_bytes()
    rom[0x1AE4F8:0x1AE61A] = source[0x1AE4F8:0x1AE61A]
    rom[0x1B03F2:0x1B0434] = source[0x1B03F2:0x1B0434]
    rom[0x1E58B8:0x1E58C8] = bytes.fromhex("203c12345678227c00ff43214e754e714e71")
    rom[0x1E589A:0x1E58A2] = bytes.fromhex("2c7c00ff67894e75")
    machine = Machine(bytes(rom))
    machine.gates([CONTACT_ENTRY])
    assert machine.run(instructions=64) == "gate"
    assert machine.registers()["sr"] & 0x10
    return machine


def test_type7b_dispatcher_has_one_real_gate_and_outer_future_equivalence():
    """Qualify 1ABC82 -> 1AE9D4 -> 1AE4F8 through 1ABCA0 and 150 native steps."""
    with _contact_dispatch_machine_with_filler() as machine:
        native_write(machine, 0xFF1000, b"\x7b")
        native_write(machine, 0xFFF0E6, b"\x01")
        initial = machine.snapshot()
        machine.gates([COLLECTION_DISPATCH_RETURN])
        machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == "gate"
        expected = (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio())
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        expected_future = (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio())

        machine.restore(initial)
        machine.audio()
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        assert candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
        assert candidate.stats["gates"] == 1
        assert candidate.stats["collection_dispatch_hits"] == 1
        assert candidate.stats["contact_hits"] == 1
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected_future


def test_sound_prefix_preserves_incoming_x_at_first_native_callee_entry():
    """Compare original/candidate at 1E58B8 with an incoming X-set CCR."""
    with _contact_machine_with_x_set() as machine:
        for address, value in ((0xFFF0C1, 1), (0xFFF57D, 1),
                               (0xFFF11F, 1), (0xFFEFFA, 1)):
            native_write(machine, address, bytes((value,)))
        initial_info = machine.info
        initial = machine.snapshot()
        machine.gates([0x1E58B8])
        machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == "gate"
        expected = (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio())

        machine.restore(initial)
        machine.audio()
        machine.gates([CONTACT_ENTRY])
        assert machine.run(instructions=1) == "gate"
        prefix = begin_contact_sound(machine, machine.registers())
        assert prefix.registers["pc"] == 0x1E58B8
        # Compare at the first native callee, before the sound body can hide
        # an incorrect incoming CCR transformation.
        assert prefix.registers["sr"] == expected[1]["sr"]
        assert prefix.cycles == expected[0]["m68k_cycles"] - initial_info["m68k_cycles"]
