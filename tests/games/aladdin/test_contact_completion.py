"""Strict qualification of the shared contact completion suffix.

The suffix is an internal continuation of the collection callback.  These
fixtures deliberately park the real ROM at 1ABCA0 so the direct oracle can
qualify the suffix without changing the collection return constant.  The
production tests below enter through the collection dispatcher and observe
the wider 1ABD74 completion boundary.
"""
from dataclasses import replace

import pytest
import oracle_witness as oracle

from aladdin_sega.boundary import (
    COLLECTION_DISPATCH_ENTRY,
    COLLECTION_DISPATCH_RETURN,
    CONTACT_COMPLETION_EXIT,
    UnsupportedCandidate,
    complete_contact_plan,
)
from aladdin_sega.recovery import Candidate


ENTRY = 0x1ABCA0
EXIT = CONTACT_COMPLETION_EXIT
RECORD = 0xFF8470
STACK = 0xFFEC00
SAFE_RETURN = 0x1B65BE


def _word(address, value):
    return list(oracle.write_word(address, value))


def suffix_fixture(*, kind=0x50, flags=0x10, vertical=0x0600,
                   callback_block=0, player_be=0, player_c0=0xFF,
                   player_e7=0, special=0, mode=0, age=0x40,
                   x=0x1200, y=0x1300, dx=0x0010, dy=0x0020,
                   incoming_x=False, sr=None, register_updates=None,
                   stack=STACK, alias_record=RECORD):
    """Create a real-ROM state parked at the internal suffix entry."""
    machine = oracle.cold_fixture(0x1B5266, pc_entry=ENTRY,
                                  incoming_x=incoming_x, stack=stack)
    try:
        machine.gates([ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        registers.update(a1=alias_record, a7=stack,
                         d0=0xABCD1234, d1=0x13572468,
                         d2=0x98764321, d3=0x76543210)
        if sr is not None:
            registers["sr"] = sr
        if register_updates:
            registers.update(register_updates)
        writes = [
            (alias_record + offset, 0xA5) for offset in range(66)
        ]
        writes += [item for index in range(-16, 152)
                   for item in oracle.write_long(stack + 4 * index,
                                                 SAFE_RETURN)]
        writes += [
            (alias_record, kind), (alias_record + 6, flags),
            (0xFFF0F5, callback_block), (0xFFF0BE, player_be),
            (0xFFF0C0, player_c0), (0xFFF0E7, player_e7),
            (0xFFF173, special), (0xFFF0EB, age),
        ]
        writes += _word(0xFFF0B0, mode)
        writes += _word(0xFF7E5A, vertical)
        writes += _word(0xFF7DF6, x)
        writes += _word(0xFF7DF8, y)
        writes += _word(0xFF7DFA, dx)
        writes += _word(0xFF7DFC, dy)
        assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=1, instructions=1, last_pc=ENTRY,
                              writes=writes, registers=registers)
        return machine.snapshot()
    finally:
        machine.close()


def qualify_suffix(state, plan_factory=complete_contact_plan):
    return oracle.qualify_atomic_plan(
        state, entry=ENTRY, exit_pc=EXIT, plan_factory=plan_factory)


@pytest.mark.parametrize("values", [
    {},
    {"vertical": 0},
    {"kind": 0x51, "age": 0x20},
    {"special": 1},
    {"mode": 1},
    {"age": 0x10},
    {"player_be": 1, "player_c0": 0},
    {"player_be": 1, "player_c0": 1},
    {"player_be": 1, "player_c0": 1, "player_e7": 1},
    {"player_e7": 1},
    {"flags": 0},
])
@pytest.mark.parametrize("incoming_x", [False, True])
def test_completion_strict_outer_future_and_fresh(values, incoming_x):
    state = suffix_fixture(incoming_x=incoming_x, **values)
    result = qualify_suffix(state)
    assert result.outer_state and result.future_state
    assert result.stats["candidate_hits"] == 1
    assert result.stats["fallbacks"] == 0


@pytest.mark.parametrize("mutant", ["result", "continuation", "timing", "last-pc"])
def test_completion_mutants_are_rejected_by_full_contract(mutant):
    def wrong(machine, registers):
        plan = complete_contact_plan(machine, registers)
        if mutant == "result":
            return replace(plan, writes=(*plan.writes, (0xFF7E08, 0xA7)))
        if mutant == "continuation":
            return replace(plan, registers={**plan.registers, "pc": EXIT + 2})
        if mutant == "timing":
            return replace(plan, cycles=plan.cycles + 4)
        return replace(plan, last_pc=plan.last_pc + 2)

    with pytest.raises((AssertionError, RuntimeError)):
        qualify_suffix(suffix_fixture(), wrong)


@pytest.mark.parametrize("sr", [0x2000, 0x2007, 0x2010, 0x2017])
def test_completion_preserves_incoming_ccr_and_live_registers(sr):
    state = suffix_fixture(
        sr=sr,
        register_updates={"d0": 0xDEADBE00, "d1": 0xCAFEBABE,
                          "d2": 0x89ABCDEF, "d3": 0x10203040},
        x=0xFF00, y=0xFF80, dx=0x0200, dy=0x0181,
        stack=0xFFED00)
    result = qualify_suffix(state)
    assert result.stats["candidate_hits"] == 1
    assert result.stats["fallbacks"] == 0


@pytest.mark.parametrize("values", [
    {"callback_block": 1},
    {"player_be": 1, "player_c0": 0},
    {"player_e7": 1},
    {"player_be": 1, "player_c0": 1, "player_e7": 1},
])
def test_completion_guard_priority_remains_strict(values):
    result = qualify_suffix(suffix_fixture(**values))
    assert result.stats["candidate_hits"] == 1
    assert result.stats["fallbacks"] == 0


def test_completion_alias_is_refused_before_atomic_commit():
    # A record beginning at FFF0F5 aliases the callback-block byte.  The
    # planner must reject the overlapping read/write domain instead of
    # claiming a direct suffix replacement.
    state = suffix_fixture(alias_record=0xFFF0F5)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([ENTRY])
        assert machine.run(instructions=1) == "gate"
        before = machine.snapshot()
        with pytest.raises(UnsupportedCandidate):
            complete_contact_plan(machine, machine.registers())
        assert machine.snapshot() == before
    finally:
        machine.close()


def test_completion_output_and_return_slot_alias_is_refused():
    # The helper's BSR return slot is SP-4.  Place it directly over FF7E02,
    # one of the two X publication copies.  The completed plan must refuse
    # before atomic admission because the helper would overwrite its own RTS
    # address while publishing the result.
    state = suffix_fixture(stack=0xFF7E06)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([ENTRY])
        assert machine.run(instructions=1) == "gate"
        with pytest.raises(UnsupportedCandidate):
            complete_contact_plan(machine, machine.registers())
    finally:
        machine.close()


@pytest.mark.parametrize("kind", [0x4F, 0x50, 0x51, 0x52])
@pytest.mark.parametrize("selector", [
    {"special": 1}, {"mode": 1}, {"age": 0x10}, {"age": 0x40},
])
def test_completion_landing_selector_kind_boundaries_are_strict(kind, selector):
    result = qualify_suffix(suffix_fixture(kind=kind, **selector))
    assert result.stats["candidate_hits"] == 1
    assert result.stats["fallbacks"] == 0


@pytest.mark.parametrize("target,values", [
    (0x1AF978, {"kind": 0x6A, "vertical": 0x0800,
                "previous": 100, "object_y": 108}),
    (0x1AFC4E, {"vertical": 0x0800, "player_x": 100,
                "object_x": 100}),
])
@pytest.mark.parametrize("sound", [0, 1])
def test_completion_production_path_observes_wider_exit(target, values, sound):
    # The production candidate enters through the existing dispatcher and
    # owns the suffix through 1ABD74; no new gate is introduced for it.
    from test_contact_family import family_fixture
    state = family_fixture(target, sound=sound, be=0, **values)
    expected = oracle.execute_region(
        state, entry=COLLECTION_DISPATCH_ENTRY, candidate=None,
        expected_return=EXIT, include_raw=True)
    actual = oracle.execute_region(
        state, entry=COLLECTION_DISPATCH_ENTRY, candidate="lifecycle",
        expected_return=EXIT, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["fallbacks"] == 0
    assert actual.stats["contact_completion_hits"] == 1
    if target == 0x1AFC4E and sound:
        assert actual.stats["legacy_entries"] == 1
        assert actual.stats["legacy_returns"] == 1
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_completion_deadline_keeps_shorter_callback_boundary_exact():
    # 404 callback cycles fit in this deadline, while the 1048-cycle
    # callback-plus-completion aggregate does not.  Lifecycle therefore
    # commits the old callback plan and leaves 1ABCA0 to original execution.
    from test_contact_family import family_fixture
    state = family_fixture(0x1AF978, kind=0x6A, vertical=0x0800,
                           previous=100, object_y=108, be=0)
    expected = oracle.execute_region(
        state, entry=COLLECTION_DISPATCH_ENTRY, candidate=None,
        expected_return=COLLECTION_DISPATCH_RETURN, include_raw=True)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        candidate.arm(machine)
        assert candidate.on_gate(machine, machine.info["tick"] + 7000)
        assert machine.info["pc"] == COLLECTION_DISPATCH_RETURN
        assert oracle.observable(machine) == expected.outer
        assert candidate.stats["collection_dispatch_hits"] == 1
        assert candidate.stats["contact_completion_hits"] == 0
    finally:
        machine.close()
