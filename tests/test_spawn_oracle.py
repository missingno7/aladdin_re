"""Raw cold-root spawn qualification; no legacy snapshot/replay input."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "oracle_witness", Path(__file__).parents[1] / "scripts" / "oracle_witness.py")
oracle = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(oracle)


@pytest.mark.parametrize("entry", tuple(oracle.ENTRY_BASES))
@pytest.mark.parametrize("free", (0, 1, None), ids=("first-free", "second-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_four_spawn_arms_match_original_full_outer_and_future(entry, free, incoming_x):
    expected, expected_future, _ = oracle.execute(
        entry, free=free, candidate=None, incoming_x=incoming_x)
    actual, actual_future, stats = oracle.execute(
        entry, free=free, candidate="lifecycle", incoming_x=incoming_x)
    assert actual == expected
    assert actual_future == expected_future
    assert stats["spawn_region_hits"] == 1
    assert stats["fallbacks"] == 0


@pytest.mark.parametrize("entry", tuple(oracle.ENTRY_BASES))
def test_spawn_alias_at_saved_return_frame_falls_back_without_effects(entry):
    base, _, _ = oracle.ENTRY_BASES[entry]
    machine = oracle.cold_fixture(entry, free=0)
    try:
        machine.gates([entry])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        registers["a7"] = base
        assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=1, instructions=1, last_pc=entry,
                              writes=[], registers=registers)
        from aladdin_sega.recovery import Candidate
        recovery = Candidate("lifecycle")
        recovery.arm(machine)
        assert machine.run(instructions=1) == "gate"
        assert recovery.on_gate(machine, machine.info["tick"] + 1_000_000) is False
        # The alias is supplied to planning only after parking; no candidate
        # writes may occur before the explicit original fallback instruction.
        assert recovery.stats["fallbacks"] == 1
        assert recovery.stats["candidate_hits"] == 0
        assert recovery.stats["spawn_region_hits"] == 0
        assert machine.info["pc"] != entry
    finally:
        machine.close()


@pytest.mark.parametrize("entry", tuple(oracle.ENTRY_BASES))
@pytest.mark.parametrize("mutant", ("lifecycle-mutant-result", "lifecycle-mutant-timing"))
def test_spawn_mutants_cannot_match_original_outer_or_future(entry, mutant):
    expected, expected_future, _ = oracle.execute(
        entry, free=0, candidate=None, incoming_x=False)
    actual, actual_future, _ = oracle.execute(
        entry, free=0, candidate=mutant, incoming_x=False)
    assert (actual, actual_future) != (expected, expected_future)


@pytest.mark.parametrize("target", tuple(oracle.DISPATCH_CALLBACKS))
def test_dispatch_callbacks_match_original_outer_and_future(target):
    expected, expected_future, _ = oracle.execute_dispatch(
        target, free=0, candidate=None, incoming_x=False)
    actual, actual_future, stats = oracle.execute_dispatch(
        target, free=0, candidate="lifecycle", incoming_x=False)
    assert actual == expected
    assert actual_future == expected_future
    assert stats["spawn_caller_hits"] == 1
    assert stats["fallbacks"] == 0


def test_dispatch_candidate_future_matches_from_raw_state_in_fresh_process():
    _, outer_state, expected_future, _, _ = oracle.execute_dispatch(
        oracle.SPAWN_UPPER_CALLER_ENTRY, free=0, candidate="lifecycle",
        incoming_x=False, include_raw=True)
    assert oracle.fresh_process_future(outer_state) == expected_future


def test_dispatch_wrong_continuation_mutant_cannot_match_outer_or_future():
    """A continuation mutation is observable at the composed caller boundary."""
    expected, expected_future, _ = oracle.execute_dispatch(
        oracle.SPAWN_UPPER_CALLER_ENTRY, free=0, candidate=None, incoming_x=False)
    actual, actual_future, _ = oracle.execute_dispatch(
        oracle.SPAWN_UPPER_CALLER_ENTRY, free=0,
        candidate="lifecycle-mutant-continuation", incoming_x=False)
    assert (actual, actual_future) != (expected, expected_future)


def test_dispatch_indexed_clear_alias_falls_back_before_movem_effects():
    from aladdin_sega.boundary import SPAWN_DISPATCH_ITERATION_ENTRY
    from aladdin_sega.recovery import Candidate

    machine = oracle.dispatcher_fixture(oracle.SPAWN_UPPER_CALLER_ENTRY, free=0)
    try:
        machine.gates([SPAWN_DISPATCH_ITERATION_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        # The callback's MOVEM frame begins at (A7 - 60) - 4.  D2=3, so
        # choose A2 such that its indexed CLR aliases that frame byte range.
        registers["a2"] = (registers["a7"] - 64 - 3) & 0xFFFFFF
        assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=SPAWN_DISPATCH_ITERATION_ENTRY,
                              writes=[], registers=registers)
        recovery = Candidate("lifecycle")
        recovery.arm(machine)
        assert machine.run(instructions=1) == "gate"
        assert recovery.on_gate(machine, machine.info["tick"] + 1_000_000) is False
        assert recovery.stats["fallbacks"] == 1
        assert recovery.stats["candidate_hits"] == 0
    finally:
        machine.close()


def test_dispatch_unknown_callback_is_rejected_before_saved_frame_write():
    from aladdin_sega.boundary import SPAWN_DISPATCH_ITERATION_ENTRY
    from aladdin_sega.recovery import Candidate

    machine = oracle.dispatcher_fixture(oracle.SPAWN_UPPER_CALLER_ENTRY, free=0)
    try:
        machine.gates([SPAWN_DISPATCH_ITERATION_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        registers["a4"] = 0x1AFD12
        assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=SPAWN_DISPATCH_ITERATION_ENTRY,
                              writes=[], registers=registers)
        before = machine.peek_ram(0, 65536)
        recovery = Candidate("lifecycle")
        recovery.arm(machine)
        assert machine.run(instructions=1) == "gate"
        assert recovery.on_gate(machine, machine.info["tick"] + 1_000_000) is False
        assert recovery.stats["candidate_hits"] == 0
        # Fallback retires the native entry; its one instruction is a MOVEM
        # and therefore cannot have modified the callback's frame contents.
        assert machine.peek_ram(0, 65536) != before
    finally:
        machine.close()


@pytest.mark.parametrize("target", tuple(oracle.CALLER_POOLS))
@pytest.mark.parametrize("free", (0, 19, None))
@pytest.mark.parametrize("incoming_x", (False, True))
@pytest.mark.parametrize("parent", (False, True))
def test_spawn_neighbors_outer_and_future(target, free, incoming_x, parent):
    execute = oracle.execute_dispatch if parent else oracle.execute
    expected = execute(target, free=free, candidate=None, incoming_x=incoming_x)
    actual = execute(target, free=free, candidate="lifecycle", incoming_x=incoming_x)
    assert actual[:2] == expected[:2]
    assert actual[2]["fallbacks"] == 0


@pytest.mark.parametrize("target", tuple(oracle.CALLER_POOLS))
def test_spawn_neighbors_fresh_process(target):
    _, state, future, _, _ = oracle.execute_dispatch(
        target, free=0, candidate="lifecycle", incoming_x=False, include_raw=True)
    assert oracle.fresh_process_future(state) == future


@pytest.mark.parametrize("target", tuple(oracle.CALLER_POOLS))
@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_spawn_neighbors_negative_controls(target, mutant):
    expected = oracle.execute_dispatch(target, free=0, candidate=None, incoming_x=False)
    actual = oracle.execute_dispatch(target, free=0, candidate="lifecycle-mutant-" + mutant, incoming_x=False)
    assert actual[:2] != expected[:2]


@pytest.mark.parametrize("target", oracle.GUARD_TARGETS)
@pytest.mark.parametrize("guard_value", (0, 1), ids=("guard-clear", "guard-set"))
@pytest.mark.parametrize("free", (0, None), ids=("slot-available", "pool-exhausted"))
@pytest.mark.parametrize("parent", (False, True), ids=("direct", "dispatcher"))
def test_recorded_dispatch_guards_match_original_outer_and_future(
        target, guard_value, free, parent):
    """Qualify three observed targets in constructed strict fixtures."""
    execute = oracle.execute_dispatch if parent else oracle.execute
    expected = execute(target, free=free, candidate=None, incoming_x=False,
                       guard_value=guard_value)
    actual = execute(target, free=free, candidate="lifecycle", incoming_x=False,
                     guard_value=guard_value)
    assert actual[:2] == expected[:2]
    assert actual[2]["fallbacks"] == 0


@pytest.mark.parametrize("target", oracle.GUARD_TARGETS)
@pytest.mark.parametrize("guard_value", (0, 1), ids=("guard-clear", "guard-set"))
def test_recorded_dispatch_guards_survive_fresh_process(target, guard_value):
    _, state, future, _, _ = oracle.execute_dispatch(
        target, free=0, candidate="lifecycle", incoming_x=False,
        guard_value=guard_value, include_raw=True)
    assert oracle.fresh_process_future(state) == future


@pytest.mark.parametrize("target", oracle.GUARD_TARGETS)
def test_guard_reads_see_parent_planned_frame_writes(target):
    """A guard may alias the parent MOVEM/JSR bytes when the planned view is used."""
    kwargs = dict(free=0, incoming_x=False, guard_value=0,
                  stack=0xFFF1AC, initial_d0=0x00010100)
    expected = oracle.execute_dispatch(target, candidate=None, **kwargs)
    actual = oracle.execute_dispatch(target, candidate="lifecycle", **kwargs)
    assert actual[:2] == expected[:2]
    assert actual[2]["fallbacks"] == 0


def test_lower_reset_cannot_alias_parent_saved_registers():
    from aladdin_sega.boundary import spawn_dispatch_iteration, UnsupportedCandidate
    machine = oracle.dispatcher_fixture(0x1B6F0C)
    try:
        registers = machine.registers()
        registers["a7"] = 0xFFF120
        before = machine.snapshot()
        with pytest.raises(UnsupportedCandidate):
            spawn_dispatch_iteration(machine, registers)
        assert machine.snapshot() == before
    finally:
        machine.close()
