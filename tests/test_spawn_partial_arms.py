"""Qualification of the spawn dispatcher's partial-decline children.

1B6C0E, 1B72FC, 1B6FAE, 1B6756 and 1B6C2E are spawn dispatcher callbacks
(``--parent 1AE46C`` census) whose recorded evidence shows a RAM-only
recipe-matched arm alongside an arm no recipe reaches: 1B6C0E's, 1B6FAE's
and 1B6C2E's successful-allocation/FFF175-clear arm (when 1B6FAE's own
FF7E26 selector also mismatches) continues into 1B2650's VDP tile-data
upload (a device port write inside the ``1B263C..1B26D0`` command-stream
engine range); 1B72FC's FFEFE0==0x3030 arm is an unrecorded four-slot
allocation sequence with no retained fixture; 1B6756's FF7E26==0x0B arm
nests a second guard, a second reverse-pool spawn and a second 1B2650 VDP
call, also with no retained fixture.  None fit the plain/offset/closure
table shapes tests/test_spawn_oracle.py exercises generically, and none
may join oracle_witness's DISPATCH_CALLBACKS bulk matrix: that suite's
default fixture leaves FFF175/FFEFE0/FF7E26 at their cold-boot RAM
residue, which lands 1B6C0E, 1B6FAE, 1B6756 and 1B6C2E on their declining
arm and would break the suite's blanket ``fallbacks == 0`` assumption.
This module qualifies all five directly instead, mirroring
oracle_witness.dispatcher_fixture and execute_dispatch without touching
their shared dicts.
"""
from __future__ import annotations

import pytest
import oracle_witness as oracle
from aladdin_sega.boundary import (SPAWN_DISPATCH_ITERATION_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                                   SPAWN_REGION_REVERSE_ENTRY,
                                   SPAWN_UPPER_TILE_CALLER_ENTRY, SPAWN_CAP_GUARD_TWO_ENTRY,
                                   SPAWN_UPPER_TILE_WORD_CALLER_ENTRY,
                                   SPAWN_REVERSE_GUARD_CALLER_ENTRY,
                                   SPAWN_UPPER_TILE_TWO_CALLER_ENTRY,
                                   SPAWN_UPPER_GUARD_TILE_ENTRY,
                                   SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY,
                                   UnsupportedCandidate, spawn_upper_tile_caller,
                                   spawn_cap_guard_two, spawn_upper_tile_word_caller,
                                   spawn_reverse_guard_caller, spawn_upper_tile_two_caller,
                                   spawn_upper_guard_tile_caller, spawn_upper_tile_four_caller)
from aladdin_sega.recovery import Candidate


def _dispatch_fixture(target, pool_entry, *, free=0, incoming_x=False, pokes=()):
    """Mirror oracle_witness.dispatcher_fixture for a target outside its shared dicts."""
    machine = oracle.cold_fixture(pool_entry, free=free, incoming_x=incoming_x,
                                  pc_entry=SPAWN_DISPATCH_ITERATION_ENTRY)
    machine.gates([SPAWN_DISPATCH_ITERATION_ENTRY])
    assert machine.run(instructions=1) == "gate"
    registers = machine.registers()
    registers.update({"a0": 0xFF6000, "a4": target, "d0": 0, "d4": 2, "d5": 0, "d6": 0})
    assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                          last_pc=SPAWN_DISPATCH_ITERATION_ENTRY, writes=list(pokes),
                          registers=registers)
    return machine


def _run_dispatch(target, pool_entry, *, free, incoming_x, candidate, pokes=()):
    """Mirror oracle_witness.execute_dispatch, but tolerate a decline.

    ``execute_dispatch`` asserts a single ``on_gate`` call returns True,
    which only holds for a target that always recovers.  1B6C0E and 1B72FC
    each have one arm that declines by design, so this loops (as
    ``execute_region`` does for the contact-family declines) until the
    walker's own entry/exit gate is reached, tolerating one or more
    ``on_gate`` calls that fall back to the original instruction.
    """
    machine = _dispatch_fixture(target, pool_entry, free=free, incoming_x=incoming_x, pokes=pokes)
    try:
        walker_gates = (0x1AE44A, 0x1AE47C)
        machine.gates([SPAWN_DISPATCH_ITERATION_ENTRY, *walker_gates])
        assert machine.run(instructions=1) == "gate"
        recovery = Candidate(candidate) if candidate else None
        if recovery:
            recovery.arm(machine)
            machine.gates(list(dict.fromkeys((*recovery.gate_pcs, *walker_gates))))
            for _ in range(32):
                if machine.run(instructions=100_000) != "gate":
                    raise RuntimeError("dispatch fixture did not reach a gate")
                if machine.info["pc"] in walker_gates:
                    break
                recovery.on_gate(machine, machine.info["tick"] + 1_000_000)
            else:
                raise RuntimeError("dispatch fixture did not settle within 32 gates")
        else:
            machine.gate(SPAWN_DISPATCH_ITERATION_ENTRY, bypass_once=True)
            assert machine.run(instructions=20_000) == "gate"
        at_outer = oracle.observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        future = oracle.observable(machine)
        return oracle.ExecutionResult(at_outer, future, recovery.stats if recovery else None)
    finally:
        machine.close()


# ---------------------------------------------------------------------------
# 1B6C0E: upper-pool creation plus an FFF175-gated VDP tile upload.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_tile_recovered_skip_arm_matches_original(free, incoming_x):
    """FFF175 set (or allocation exhausted): the recorded, recovered arm."""
    pokes = [(0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=free, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=free, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_tile_vdp_arm_declines_to_original(incoming_x):
    """FFF175 clear and a successful allocation: the undeclined VDP upload."""
    pokes = [(0xFFF175, 0x00)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 0
    assert actual.stats["fallbacks"] == 1


def test_upper_tile_isolated_plan_declines_on_the_vdp_arm():
    machine = oracle.cold_fixture(SPAWN_REGION_UPPER_ENTRY, free=0,
                                  pc_entry=SPAWN_UPPER_TILE_CALLER_ENTRY)
    try:
        machine.gates([SPAWN_UPPER_TILE_CALLER_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                              last_pc=SPAWN_UPPER_TILE_CALLER_ENTRY, writes=[(0xFFF175, 0)],
                              registers=registers)
        with pytest.raises(UnsupportedCandidate, match="1B2650 VDP tile upload"):
            spawn_upper_tile_caller(machine, machine.registers())
    finally:
        machine.close()


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_upper_tile_mutants_diverge_at_the_dispatcher_boundary(mutant):
    pokes = [(0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate=f"lifecycle-mutant-{mutant}",
                           pokes=pokes)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


# ---------------------------------------------------------------------------
# 1B72FC: an FFEFE0 cap guard whose recorded arm never reaches an allocator.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cap", (0x0000, 0x2FFF, 0x3031, 0xFFFF), ids=lambda v: f"cap-{v:04X}")
def test_cap_guard_recovered_arm_matches_original(cap):
    """Any FFEFE0 value other than 0x3030: the recorded, recovered arm."""
    pokes = list(oracle.write_word(0xFFEFE0, cap))
    expected = _run_dispatch(SPAWN_CAP_GUARD_TWO_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_CAP_GUARD_TWO_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_cap_guard_reached_arm_declines_to_original():
    pokes = list(oracle.write_word(0xFFEFE0, 0x3030))
    expected = _run_dispatch(SPAWN_CAP_GUARD_TWO_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_CAP_GUARD_TWO_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 0
    assert actual.stats["fallbacks"] == 1


def test_cap_guard_isolated_plan_declines_at_exactly_0x3030():
    machine = oracle.cold_fixture(SPAWN_REGION_UPPER_ENTRY, free=0,
                                  pc_entry=SPAWN_CAP_GUARD_TWO_ENTRY)
    try:
        machine.gates([SPAWN_CAP_GUARD_TWO_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                              last_pc=SPAWN_CAP_GUARD_TWO_ENTRY,
                              writes=list(oracle.write_word(0xFFEFE0, 0x3030)),
                              registers=registers)
        with pytest.raises(UnsupportedCandidate, match="unrecorded four-slot spawn sequence"):
            spawn_cap_guard_two(machine, machine.registers())
    finally:
        machine.close()


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_cap_guard_mutants_diverge_at_the_dispatcher_boundary(mutant):
    pokes = list(oracle.write_word(0xFFEFE0, 0x0000))
    expected = _run_dispatch(SPAWN_CAP_GUARD_TWO_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_CAP_GUARD_TWO_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate=f"lifecycle-mutant-{mutant}",
                           pokes=pokes)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


# ---------------------------------------------------------------------------
# 1B6FAE: upper-pool creation, an FFF175 guard, and an FF7E26 word-write arm.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_tile_word_recorded_arm_matches_original(free, incoming_x):
    """FFF175 clear and FF7E26==5: the arm every recorded fixture exercises."""
    pokes = [(0xFFF175, 0x00), (0xFF7E26, 0x05)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=free, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=free, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_tile_word_guard_set_arm_matches_original(incoming_x):
    """FFF175 set: the same early-return shape as 1B6C0E, unobserved but proven."""
    pokes = [(0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_upper_tile_word_vdp_arm_declines_to_original():
    """FFF175 clear and FF7E26 != 5: the undeclined VDP upload."""
    pokes = [(0xFFF175, 0x00), (0xFF7E26, 0x00)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 0
    assert actual.stats["fallbacks"] == 1


def test_upper_tile_word_isolated_plan_declines_on_the_vdp_arm():
    machine = oracle.cold_fixture(SPAWN_REGION_UPPER_ENTRY, free=0,
                                  pc_entry=SPAWN_UPPER_TILE_WORD_CALLER_ENTRY)
    try:
        machine.gates([SPAWN_UPPER_TILE_WORD_CALLER_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                              last_pc=SPAWN_UPPER_TILE_WORD_CALLER_ENTRY,
                              writes=[(0xFFF175, 0), (0xFF7E26, 0)], registers=registers)
        with pytest.raises(UnsupportedCandidate, match="1B2650 VDP tile upload"):
            spawn_upper_tile_word_caller(machine, machine.registers())
    finally:
        machine.close()


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_upper_tile_word_mutants_diverge_at_the_dispatcher_boundary(mutant):
    pokes = [(0xFFF175, 0x00), (0xFF7E26, 0x05)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate=f"lifecycle-mutant-{mutant}",
                           pokes=pokes)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


# ---------------------------------------------------------------------------
# 1B6756: an FF7E26 selector guarding an unconditional reverse-pool spawn.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("free", (0, 23, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_reverse_guard_recorded_arm_matches_original(free, incoming_x):
    """FF7E26 != 0x0B (every recorded fixture): unconditional reverse spawn."""
    pokes = [(0xFF7E26, 0x00)]
    expected = _run_dispatch(SPAWN_REVERSE_GUARD_CALLER_ENTRY, SPAWN_REGION_REVERSE_ENTRY,
                             free=free, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_REVERSE_GUARD_CALLER_ENTRY, SPAWN_REGION_REVERSE_ENTRY,
                           free=free, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_reverse_guard_0x0b_arm_declines_to_original():
    pokes = [(0xFF7E26, 0x0B)]
    expected = _run_dispatch(SPAWN_REVERSE_GUARD_CALLER_ENTRY, SPAWN_REGION_REVERSE_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_REVERSE_GUARD_CALLER_ENTRY, SPAWN_REGION_REVERSE_ENTRY,
                           free=0, incoming_x=False, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 0
    assert actual.stats["fallbacks"] == 1


def test_reverse_guard_isolated_plan_declines_at_exactly_0x0b():
    machine = oracle.cold_fixture(SPAWN_REGION_REVERSE_ENTRY, free=0,
                                  pc_entry=SPAWN_REVERSE_GUARD_CALLER_ENTRY)
    try:
        machine.gates([SPAWN_REVERSE_GUARD_CALLER_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                              last_pc=SPAWN_REVERSE_GUARD_CALLER_ENTRY,
                              writes=[(0xFF7E26, 0x0B)], registers=registers)
        with pytest.raises(UnsupportedCandidate, match="unrecorded FF7E26==0x0B chain"):
            spawn_reverse_guard_caller(machine, machine.registers())
    finally:
        machine.close()


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_reverse_guard_mutants_diverge_at_the_dispatcher_boundary(mutant):
    pokes = [(0xFF7E26, 0x00)]
    expected = _run_dispatch(SPAWN_REVERSE_GUARD_CALLER_ENTRY, SPAWN_REGION_REVERSE_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_REVERSE_GUARD_CALLER_ENTRY, SPAWN_REGION_REVERSE_ENTRY,
                           free=0, incoming_x=False, candidate=f"lifecycle-mutant-{mutant}",
                           pokes=pokes)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


# ---------------------------------------------------------------------------
# 1B6C2E: byte-for-byte the same shape as 1B6C0E, different template.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_tile_two_recovered_skip_arm_matches_original(free, incoming_x):
    """FFF175 set (or allocation exhausted): the recorded, recovered arm."""
    pokes = [(0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_TWO_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=free, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_TWO_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=free, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_tile_two_vdp_arm_declines_to_original(incoming_x):
    """FFF175 clear and a successful allocation: the undeclined VDP upload."""
    pokes = [(0xFFF175, 0x00)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_TWO_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_TWO_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 0
    assert actual.stats["fallbacks"] == 1


def test_upper_tile_two_isolated_plan_declines_on_the_vdp_arm():
    machine = oracle.cold_fixture(SPAWN_REGION_UPPER_ENTRY, free=0,
                                  pc_entry=SPAWN_UPPER_TILE_TWO_CALLER_ENTRY)
    try:
        machine.gates([SPAWN_UPPER_TILE_TWO_CALLER_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                              last_pc=SPAWN_UPPER_TILE_TWO_CALLER_ENTRY, writes=[(0xFFF175, 0)],
                              registers=registers)
        with pytest.raises(UnsupportedCandidate, match="1B2650 VDP tile upload"):
            spawn_upper_tile_two_caller(machine, machine.registers())
    finally:
        machine.close()


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_upper_tile_two_mutants_diverge_at_the_dispatcher_boundary(mutant):
    pokes = [(0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_TWO_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_TWO_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate=f"lifecycle-mutant-{mutant}",
                           pokes=pokes)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


# ---------------------------------------------------------------------------
# 1B6F82: an FF7E21 guard wrapped around 1B6C0E's own upper-tile shape.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_guard_tile_recovered_skip_arm_matches_original(free, incoming_x):
    """FF7E21 set, FFF175 set (or allocation exhausted): the recovered arm."""
    pokes = [(0xFF7E21, 0x01), (0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_GUARD_TILE_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=free, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_GUARD_TILE_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=free, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_upper_guard_tile_outer_guard_clear_matches_original():
    """FF7E21 clear: declines directly, no spawn attempted."""
    pokes = [(0xFF7E21, 0x00)]
    expected = _run_dispatch(SPAWN_UPPER_GUARD_TILE_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_GUARD_TILE_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_upper_guard_tile_vdp_arm_declines_to_original():
    """FF7E21 set, FFF175 clear and a successful allocation: the VDP upload."""
    pokes = [(0xFF7E21, 0x01), (0xFFF175, 0x00)]
    expected = _run_dispatch(SPAWN_UPPER_GUARD_TILE_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_GUARD_TILE_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 0
    assert actual.stats["fallbacks"] == 1


def test_upper_guard_tile_isolated_plan_declines_on_the_vdp_arm():
    machine = oracle.cold_fixture(SPAWN_REGION_UPPER_ENTRY, free=0,
                                  pc_entry=SPAWN_UPPER_GUARD_TILE_ENTRY)
    try:
        machine.gates([SPAWN_UPPER_GUARD_TILE_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                              last_pc=SPAWN_UPPER_GUARD_TILE_ENTRY,
                              writes=[(0xFF7E21, 1), (0xFFF175, 0)], registers=registers)
        with pytest.raises(UnsupportedCandidate, match="1B2650 VDP tile upload"):
            spawn_upper_guard_tile_caller(machine, machine.registers())
    finally:
        machine.close()


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_upper_guard_tile_mutants_diverge_at_the_dispatcher_boundary(mutant):
    pokes = [(0xFF7E21, 0x01), (0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_GUARD_TILE_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_GUARD_TILE_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate=f"lifecycle-mutant-{mutant}",
                           pokes=pokes)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


# ---------------------------------------------------------------------------
# 1B75D6: byte-for-byte the same shape as 1B6C0E, different template.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_tile_four_recovered_skip_arm_matches_original(free, incoming_x):
    """FFF175 set (or allocation exhausted): the recovered arm."""
    pokes = [(0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=free, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=free, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_upper_tile_four_vdp_arm_declines_to_original(incoming_x):
    """FFF175 clear and a successful allocation: the undeclined VDP upload."""
    pokes = [(0xFFF175, 0x00)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=incoming_x, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=incoming_x, candidate="lifecycle", pokes=pokes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 0
    assert actual.stats["fallbacks"] == 1


def test_upper_tile_four_isolated_plan_declines_on_the_vdp_arm():
    machine = oracle.cold_fixture(SPAWN_REGION_UPPER_ENTRY, free=0,
                                  pc_entry=SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY)
    try:
        machine.gates([SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY])
        assert machine.run(instructions=1) == "gate"
        registers = machine.registers()
        assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                              last_pc=SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY, writes=[(0xFFF175, 0)],
                              registers=registers)
        with pytest.raises(UnsupportedCandidate, match="1B2650 VDP tile upload"):
            spawn_upper_tile_four_caller(machine, machine.registers())
    finally:
        machine.close()


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_upper_tile_four_mutants_diverge_at_the_dispatcher_boundary(mutant):
    pokes = [(0xFFF175, 0x01)]
    expected = _run_dispatch(SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                             free=0, incoming_x=False, candidate=None, pokes=pokes)
    actual = _run_dispatch(SPAWN_UPPER_TILE_FOUR_CALLER_ENTRY, SPAWN_REGION_UPPER_ENTRY,
                           free=0, incoming_x=False, candidate=f"lifecycle-mutant-{mutant}",
                           pokes=pokes)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)
