"""Independent contract review for the bounded 1AE4F8 contact family.

These checks deliberately exercise the live-RAM overlay and the complete byte
domain used by the sound31 suffix.  They do not grant coverage to an
unrecorded machine state; recorded-path and replay gates remain artifact
checks under ``artifacts/grinding/luna/contact-review``.
"""
from __future__ import annotations

import pytest

from aladdin_sega.boundary import (
    CONTACT_ENTRY,
    UnsupportedCandidate,
    begin_contact,
    begin_contact_sound,
    finish_contact_sound,
)
from aladdin_sega.game.objects.contact import contact_decay, contact_path, contact_reaction, contact_reset
from test_recovery import FakeMachine, put


def reader(values):
    return lambda address, size=1: values.get(address, 0)


def test_decay_covers_counter_bytes_and_all_three_guards():
    for counter in (0, 1, 2, 255):
        if counter == 0:
            assert contact_decay(reader({0xFFEFFA: counter})) == [(0xFFF0E6, 10)]
        else:
            assert contact_decay(reader({0xFFEFFA: counter})) == [
                (0xFFEFFA, counter - 1), (0xFFF0F2, 0x28)
            ]
        for gate in (0xFFF0E9, 0xFFF0E6, 0xFF7E20):
            assert contact_decay(reader({gate: 1, 0xFFEFFA: counter})) == []
        expected = [] if counter else [(0xFFF0E6, 10)]
        assert contact_decay(reader({0xFFEFFA: counter, 0xFFF0F2: 1})) == expected


@pytest.mark.parametrize("counter", [0, 1, 2, 255])
def test_reset_uses_its_own_writes_for_repeated_decay(counter):
    values = {0xFF7E21: counter, 0xFFEFFA: counter}
    writes = contact_reset(reader(values), pointer_reset=True)
    # The first 1B03F2 call writes FFF0F2=40; later calls must observe that
    # staged byte, exactly as the native routine does.
    assert tuple(writes[:5]) == ((0xFF7E60, 0), (0xFF7E61, 0x12), (0xFF7E62, 0x26),
                                 (0xFF7E63, 0xCE), (0xFF7E77, 0))
    assert (0xFFF0B0, 0) in writes and (0xFFF0B1, 0) in writes and (0xFFF0CC, 0) in writes
    if counter == 0:
        assert writes[-1] == (0xFFF0E6, 10)
    elif counter == 1:
        assert tuple(writes[-3:]) == ((0xFFEFFA, 0), (0xFFF0F2, 0x28), (0xFFF0E6, 10))
    else:
        assert tuple(writes[-2:]) == ((0xFFEFFA, counter - 1), (0xFFF0F2, 0x28))


def test_path_classification_covers_early_reset_reaction_and_pointer_domains():
    early = (0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2)
    for address in early:
        assert contact_path(reader({address: 1})) == ("early", address)
    assert contact_path(reader({0xFFF0C1: 0})) == ("reset", None)
    assert contact_path(reader({0xFFF0C1: 1, 0xFFF173: 1})) == ("reaction", None)
    assert contact_path(reader({0xFFF0C1: 1, 0xFFF173: 0, 0xFFF0CC: 1})) == ("reset", None)
    assert contact_path(reader({0xFFF0C1: 1})) == ("pointer_reset", None)


def _contact_machine(values=None):
    registers = {**{f"d{i}": 0x100 + i for i in range(8)},
                 **{f"a{i}": 0xFF7000 + i * 0x100 for i in range(8)},
                 "pc": CONTACT_ENTRY, "sr": 0x201f}
    registers["a7"] = 0xFF8000
    machine = FakeMachine(registers)
    for address, value in (values or {}).items():
        put(machine, address, value, 1)
    put(machine, machine._registers["a7"], 0x00123456, 4)
    return machine


@pytest.mark.parametrize("gate,index", [(0xFFF0E6, 1), (0xFFF0F2, 3)])
def test_begin_contact_early_plans_preserve_return_and_logic_ccr(gate, index):
    machine = _contact_machine({gate: 1})
    plan = begin_contact(machine, machine.registers())
    assert (plan.cycles, plan.instructions, plan.last_pc) == (42 + 28 * index, 3 + 2 * index,
                                                               CONTACT_ENTRY + 6 * index)
    assert plan.writes == ()
    assert plan.registers["pc"] == 0x123456 and plan.registers["a7"] == 0xFF8004


def test_begin_contact_reaction_plan_matches_both_final_flag_domains():
    machine = _contact_machine({0xFFF0BE: 1, 0xFFF0C1: 1, 0xFFF173: 1, 0xFFF0D8: 0})
    plan = begin_contact(machine, machine.registers())
    assert (plan.cycles, plan.instructions, plan.last_pc) == (310, 20, 0x1AE618)
    assert (0xFFF0E7, 0xFF) in plan.writes and (0xFFF0E9, 0x32) in plan.writes
    assert (0xFFEFFF, 1) in plan.writes
    d8_machine = _contact_machine({0xFFF0BE: 1, 0xFFF0C1: 1, 0xFFF173: 1, 0xFFF0D8: 1})
    d8_plan = begin_contact(d8_machine, d8_machine.registers())
    assert (d8_plan.cycles, d8_plan.instructions, d8_plan.last_pc) == (292, 19, 0x1AE616)
    assert (0xFFEFFF, 1) not in d8_plan.writes


def test_sound31_prefix_and_suffix_have_exact_frame_contract():
    machine = _contact_machine({0xFFF0C1: 0, 0xFFF57D: 1, 0xFFF11F: 1, 0xFFEFFA: 1})
    prefix = begin_contact_sound(machine, machine.registers())
    assert (prefix.cycles, prefix.instructions, prefix.last_pc, prefix.direct_calls) == (340, 21, 0x1AE5AA, 1)
    assert prefix.registers == {"a7": 0xFF7FE4, "pc": 0x1E58B8, "sr": 0x2010}
    for address, value in prefix.writes:
        put(machine, address, value, 1)
    # The contact body performs its second JSR after command 31 returns.  Its
    # return slot is the same four bytes and is therefore overwritten with
    # 1AE5B6 before the local suffix gate is observed.
    put(machine, 0xFF8000 - 28, 0x1AE5B6, 4)
    # The sound callee has returned through RTS, so SP advanced by its four
    # byte return slot before the 1AE5B6 local gate is observed.
    restored = dict(machine.registers())
    restored.update(prefix.registers)
    restored.update(pc=0x1AE5B6, a7=prefix.registers["a7"] + 4)
    suffix = finish_contact_sound(machine, restored)
    assert (suffix.cycles, suffix.instructions, suffix.last_pc, suffix.direct_calls) == (300, 19, 0x1AE5DC, 1)
    assert suffix.registers["pc"] == 0x123456
    assert suffix.registers["a7"] == 0xFF8004
    assert (0xFFEFFA, 0) in suffix.writes and (0xFFF0F2, 0x28) in suffix.writes


@pytest.mark.parametrize("stack", [0xFF8001, 0xFFF100])
def test_sound31_prefix_rejects_unaligned_or_global_aliasing_stack(stack):
    machine = _contact_machine({0xFFF0C1: 0, 0xFFF57D: 1, 0xFFF11F: 1, 0xFFEFFA: 1})
    machine._registers["a7"] = stack
    before = machine.peek_ram(0, 65536)
    with pytest.raises(UnsupportedCandidate):
        begin_contact_sound(machine, machine.registers())
    assert machine.peek_ram(0, 65536) == before


@pytest.mark.parametrize("stack", [0xFFF0B4, 0xFF7E64])
def test_soundoff_reset_rejects_the_bsr_residue_alias_surface(stack):
    machine = _contact_machine({0xFFF0C1: 0, 0xFFF57D: 0, 0xFFF11F: 1, 0xFFEFFA: 1})
    machine._registers["a7"] = stack
    before = machine.peek_ram(0, 65536), machine.registers()
    with pytest.raises(UnsupportedCandidate, match="aliases"):
        begin_contact(machine, machine.registers())
    assert (machine.peek_ram(0, 65536), machine.registers()) == before


def test_soundoff_reset_refuses_the_unmeasured_decay_blocker_before_writes():
    machine = _contact_machine({0xFFF0C1: 0, 0xFFF57D: 0, 0xFFF11F: 1,
                                0xFFEFFA: 1, 0xFF7E20: 1})
    before = machine.peek_ram(0, 65536), machine.registers()
    with pytest.raises(UnsupportedCandidate, match="decay blocker"):
        begin_contact(machine, machine.registers())
    assert (machine.peek_ram(0, 65536), machine.registers()) == before


def test_sound31_suffix_rejects_a_foreign_local_activation():
    machine = _contact_machine({0xFFF0C1: 0, 0xFFF57D: 1, 0xFFF11F: 1, 0xFFEFFA: 1})
    prefix = begin_contact_sound(machine, machine.registers())
    for address, value in prefix.writes:
        put(machine, address, value, 1)
    restored = dict(machine.registers())
    restored.update(prefix.registers)
    restored.update(pc=0x1AE4F8, a7=prefix.registers["a7"] + 4)
    with pytest.raises(UnsupportedCandidate):
        finish_contact_sound(machine, restored)


@pytest.mark.parametrize("address,cycles,instructions", [
    (0xFFF0BE, 312, 19), (0xFFF0D0, 368, 23), (0xFFF0D7, 396, 25),
    (0xFFF0CD, 424, 27), (0xFFF0D4, 452, 29),
])
def test_sound31_measures_each_early_reset_gate(address, cycles, instructions):
    machine = _contact_machine({0xFFF0C1: 1, 0xFFF57D: 1, 0xFFF11F: 1,
                                0xFFEFFA: 1, address: 1})
    before = machine.peek_ram(0, 65536)
    plan = begin_contact_sound(machine, machine.registers())
    assert (plan.cycles, plan.instructions) == (cycles, instructions)
    assert machine.peek_ram(0, 65536) == before


@pytest.mark.parametrize("address", [0xFFF0E9, 0xFFF0E6, 0xFF7E20, 0xFFF0F2])
def test_sound31_suffix_rechecks_each_decay_guard_after_native_sound(address):
    machine = _contact_machine({0xFFF0C1: 0, 0xFFF57D: 1, 0xFFF11F: 1, 0xFFEFFA: 1})
    prefix = begin_contact_sound(machine, machine.registers())
    for at, value in prefix.writes:
        put(machine, at, value, 1)
    put(machine, prefix.registers["a7"], 0x1AE5B6, 4)
    put(machine, address, 1, 1)
    returned = dict(machine.registers())
    returned.update(prefix.registers, pc=0x1AE5B6, a7=prefix.registers["a7"] + 4)
    with pytest.raises(UnsupportedCandidate, match="return domain"):
        finish_contact_sound(machine, returned)


@pytest.mark.parametrize("address,value", [(0xFFF0CC, 1), (0xFFEFFF, 1), (0xFFF11F, 0),
                                            (0xFF7E21, 1), (0xFFEFFA, 0)])
def test_sound31_accepts_each_measured_reset_or_decay_domain(address, value):
    machine = _contact_machine({0xFFF0C1: 0, 0xFFF57D: 1, 0xFFF11F: 1, 0xFFEFFA: 1,
                                address: value})
    before = machine.peek_ram(0, 65536)
    plan = begin_contact_sound(machine, machine.registers())
    assert plan.last_pc == 0x1AE5AA
    assert machine.peek_ram(0, 65536) == before


def test_sound31_still_rejects_an_early_return_gate_before_writes():
    machine = _contact_machine({0xFFF0C1: 1, 0xFFF57D: 1, 0xFFF11F: 1,
                                0xFFEFFA: 1, 0xFFF0F2: 1})
    before = machine.peek_ram(0, 65536)
    with pytest.raises(UnsupportedCandidate):
        begin_contact_sound(machine, machine.registers())
    assert machine.peek_ram(0, 65536) == before
