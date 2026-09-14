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


CLOSURE_OUTPUTS = {
    0x1B723E: ((0, 0x8A), (0x20, 0x00124494)),
    0x1B728E: ((0, 0x41), (0x20, 0x00125D7E), (0x29, 2)),
    0x1B72AE: ((0, 0x84), (6, 0x21), (0x20, 0x00123E7A), (0x29, 2)),
    0x1B70D4: ((0, 0x4C), (0x20, 0x00123E36), (0x0A, 0), (0x29, 1)),
    0x1B6696: ((0x20, 0x00125348),),
    0x1B6F4A: ((0x20, 0x00125A88),),
    0x1B6F34: ((0x20, 0x00125A68),),
    0x1B6EEE: ((0xA, 0), (0x20, 0x001238B2), (0, 0x22)),
    0x1B6F60: ((0x20, 0x00125AA8),),
    0x1B7018: ((0, 0x47), (0x20, 0x00123E36), (0x0A, 0), (0x29, 1)),
    0x1B70B0: ((0, 0x4B), (0x20, 0x00123E36), (0x0A, 0), (0x29, 1)),
    0x1B7060: ((0, 0x49), (0x20, 0x00123E36), (0x0A, 0), (0x29, 1)),
    0x1B703C: ((0, 0x48), (0x20, 0x00123E36), (0x0A, 0), (0x29, 1)),
}


def _outer_record_bytes(state: bytes, fields):
    from aladdin_sega.machine import Machine
    from aladdin_sega.profile import DEFAULT_ROM, read_rom

    machine = Machine(read_rom(DEFAULT_ROM))
    try:
        machine.restore(state)
        base = machine.registers()["a5"] & 0xFFFF
        ram = machine.peek_ram(0, 65536)
        values = {}
        for offset, expected in fields:
            size = 1 if offset in (0, 6, 0x29) else 4
            values[offset] = int.from_bytes(ram[base + offset:base + offset + size], "big")
        return values
    finally:
        machine.close()


@pytest.mark.parametrize("entry", tuple(oracle.ENTRY_BASES))
@pytest.mark.parametrize("free", (0, 1, None), ids=("first-free", "second-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_four_spawn_arms_match_original_full_outer_and_future(entry, free, incoming_x):
    expected = oracle.execute(entry, free=free, candidate=None, incoming_x=incoming_x)
    actual = oracle.execute(entry, free=free, candidate="lifecycle", incoming_x=incoming_x)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_region_hits"] == 1
    assert actual.stats["fallbacks"] == 0


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
    expected = oracle.execute(entry, free=0, candidate=None, incoming_x=False)
    actual = oracle.execute(entry, free=0, candidate=mutant, incoming_x=False)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


@pytest.mark.parametrize("target", tuple(oracle.DISPATCH_CALLBACKS))
def test_dispatch_callbacks_match_original_outer_and_future(target):
    expected = oracle.execute_dispatch(target, free=0, candidate=None, incoming_x=False)
    actual = oracle.execute_dispatch(target, free=0, candidate="lifecycle", incoming_x=False)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_dispatch_candidate_future_matches_from_raw_state_in_fresh_process():
    result = oracle.execute_dispatch(
        oracle.SPAWN_UPPER_CALLER_ENTRY, free=0, candidate="lifecycle",
        incoming_x=False, include_raw=True)
    assert oracle.fresh_process_future(result.outer_state) == result.future


def test_dispatch_wrong_continuation_mutant_cannot_match_outer_or_future():
    """A continuation mutation is observable at the composed caller boundary."""
    expected = oracle.execute_dispatch(
        oracle.SPAWN_UPPER_CALLER_ENTRY, free=0, candidate=None, incoming_x=False)
    actual = oracle.execute_dispatch(
        oracle.SPAWN_UPPER_CALLER_ENTRY, free=0,
        candidate="lifecycle-mutant-continuation", incoming_x=False)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


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


def _assert_spawn_neighbor(execute, target, free, incoming_x):
    expected = execute(target, free=free, candidate=None, incoming_x=incoming_x)
    actual = execute(target, free=free, candidate="lifecycle", incoming_x=incoming_x)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("target", tuple(oracle.DIRECT_CALLER_POOLS))
@pytest.mark.parametrize("free", (0, 19, None))
@pytest.mark.parametrize("incoming_x", (False, True))
def test_existing_spawn_neighbors_direct_outer_and_future(target, free, incoming_x):
    _assert_spawn_neighbor(oracle.execute, target, free, incoming_x)


@pytest.mark.parametrize("target", tuple(oracle.CALLER_POOLS))
@pytest.mark.parametrize("free", (0, 19, None))
@pytest.mark.parametrize("incoming_x", (False, True))
def test_spawn_neighbors_dispatch_outer_and_future(target, free, incoming_x):
    _assert_spawn_neighbor(oracle.execute_dispatch, target, free, incoming_x)


@pytest.mark.parametrize("target", tuple(oracle.CALLER_POOLS))
def test_spawn_neighbors_fresh_process(target):
    result = oracle.execute_dispatch(
        target, free=0, candidate="lifecycle", incoming_x=False, include_raw=True)
    assert oracle.fresh_process_future(result.outer_state) == result.future


@pytest.mark.parametrize("target", tuple(oracle.CALLER_POOLS))
@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_spawn_neighbors_negative_controls(target, mutant):
    expected = oracle.execute_dispatch(target, free=0, candidate=None, incoming_x=False)
    actual = oracle.execute_dispatch(target, free=0, candidate="lifecycle-mutant-" + mutant, incoming_x=False)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


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
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("target", oracle.GUARD_TARGETS)
@pytest.mark.parametrize("guard_value", (0, 1), ids=("guard-clear", "guard-set"))
def test_recorded_dispatch_guards_survive_fresh_process(target, guard_value):
    result = oracle.execute_dispatch(
        target, free=0, candidate="lifecycle", incoming_x=False,
        guard_value=guard_value, include_raw=True)
    assert oracle.fresh_process_future(result.outer_state) == result.future


@pytest.mark.parametrize("target", oracle.GUARD_TARGETS)
def test_guard_reads_see_parent_planned_frame_writes(target):
    """A guard may alias the parent MOVEM/JSR bytes when the planned view is used."""
    kwargs = dict(free=0, incoming_x=False, guard_value=0,
                  stack=0xFFF1AC, initial_d0=0x00010100)
    expected = oracle.execute_dispatch(target, candidate=None, **kwargs)
    actual = oracle.execute_dispatch(target, candidate="lifecycle", **kwargs)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["fallbacks"] == 0


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


KNOWN_WALKER_A = 0x1B72D4
KNOWN_WALKER_B = 0x1B6802
UNKNOWN_WALKER = 0x1B6F34
WALKER_CASES = (
    ("empty", (None,) * 16),
    ("owned-single", (KNOWN_WALKER_A,) + (None,) * 15),
    ("owned-multiple", (KNOWN_WALKER_A, KNOWN_WALKER_B) + (None,) * 14),
    ("unresolved", (KNOWN_WALKER_A, UNKNOWN_WALKER) + (None,) * 14),
)


@pytest.mark.parametrize("name,callbacks", WALKER_CASES,
                         ids=[case[0] for case in WALKER_CASES])
def test_constructed_whole_walker_matches_outer_and_future(name, callbacks):
    """Constructed cases qualify the aggregate boundary without artifacts."""
    state = oracle.constructed_walker_state(callbacks=callbacks)
    expected = oracle.execute_walker(state, candidate=None)
    actual = oracle.execute_walker(state, candidate="lifecycle")
    assert expected.iterations == 16
    assert actual.stats["spawn_walker_hits"] == 1
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["candidate_hits"] > 0
    if name != "unresolved":
        assert actual.iterations == 1
        assert actual.stats["spawn_caller_hits"] == 0


@pytest.mark.parametrize("name,callbacks", WALKER_CASES,
                         ids=[case[0] for case in WALKER_CASES])
def test_constructed_whole_walker_candidate_survives_fresh_process(name, callbacks):
    state = oracle.constructed_walker_state(callbacks=callbacks)
    result = oracle.execute_walker(
        state, candidate="lifecycle", include_raw=True)
    assert result.iterations <= 16
    assert result.stats["candidate_hits"] > 0
    assert oracle.fresh_process_future(result.outer_state) == result.future


@pytest.mark.parametrize("count", (1, 2, 16))
def test_walker_counts_match_original(count):
    state = oracle.constructed_walker_state(count=count)
    expected = oracle.execute_walker(state, candidate=None)
    actual = oracle.execute_walker(state, candidate="lifecycle")
    assert expected.iterations == count
    assert actual.stats["spawn_walker_hits"] == 1
    assert actual.outer == expected.outer
    assert actual.future == expected.future


@pytest.mark.parametrize("d5,count", ((2, 2), (0xFFFF_FFFE, 2),
                                      (0x1234_0002, 1)))
def test_walker_signed_stride_and_high_word_match(d5, count):
    state = oracle.constructed_walker_state(count=count, stride=d5)
    expected = oracle.execute_walker(state, candidate=None)
    actual = oracle.execute_walker(state, candidate="lifecycle")
    assert actual.outer == expected.outer
    assert actual.future == expected.future


def test_walker_last_cursor_crossing_24bit_ram_preserves_32bit_register():
    state = oracle.constructed_walker_state(count=1, stride=2)
    # Move the sole cursor word to the final two bytes of the 24-bit RAM
    # window; the post-step register is still a full 32-bit value.
    expected = oracle.execute_walker(state, candidate=None,
                                     register_overrides={"a0": 0x00FF_FFFE},
                                     writes=oracle.write_word(0x00FF_FFFE, 0x200))
    actual = oracle.execute_walker(state, candidate="lifecycle",
                                   register_overrides={"a0": 0x00FF_FFFE},
                                   writes=oracle.write_word(0x00FF_FFFE, 0x200))
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.outer["registers"]["a0"] == 0x0100_0000
    assert actual.stats["spawn_walker_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_walker_incoming_x_matches_original():
    state = oracle.constructed_walker_state(count=2, incoming_x=True)
    expected = oracle.execute_walker(state, candidate=None)
    actual = oracle.execute_walker(state, candidate="lifecycle")
    assert actual.outer == expected.outer
    assert actual.future == expected.future


def test_walker_planned_register_frame_may_alias_cursor():
    """The second selection sees the first callback's planned MOVEM write."""
    cursor = oracle.STACK - 60
    state = oracle.constructed_walker_state(
        count=2, callbacks=(KNOWN_WALKER_A, KNOWN_WALKER_B), stride=2,
        cursor=cursor, slot_indices=(0x100, 0), initial_d0=4)
    # D0's saved low word overwrites the second slot with 4 (flag index 2).
    # Seed that resulting index as well, so a second callback really executes.
    writes = ((0xFFAE89, oracle._callback_flag(KNOWN_WALKER_B)),)
    expected = oracle.execute_walker(state, candidate=None, writes=writes)
    actual = oracle.execute_walker(state, candidate="lifecycle", writes=writes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.outer["registers"]["d2"] & 0xFFFF == 2
    assert actual.outer["registers"]["a4"] == KNOWN_WALKER_B
    assert actual.stats["candidate_hits"] > 0
    assert actual.stats["spawn_walker_hits"] == 1
    assert actual.stats["spawn_caller_hits"] == 0


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_whole_walker_negative_controls(mutant):
    state = oracle.constructed_walker_state(count=1)
    expected = oracle.execute_walker(state, candidate=None)
    actual = oracle.execute_walker(state, candidate="lifecycle-mutant-" + mutant,
                                   stop_after_first=True)
    assert actual.outer != expected.outer


# 1B6C0E is the proven VDP tile-upload seam (spawn_upper_tile_caller); a
# fresh constructed fixture's FFF175 guard byte is clear by construction, so
# this slot always reaches the seam rather than its local-return arm.
WALKER_SEAM_CALLER = 0x1B6C0E
WALKER_SEAM_CASES = (
    ("seam-first", (WALKER_SEAM_CALLER,) + (None,) * 15),
    ("owned-then-seam", (KNOWN_WALKER_A, WALKER_SEAM_CALLER) + (None,) * 14),
    ("owned-owned-then-seam",
     (KNOWN_WALKER_A, KNOWN_WALKER_A, WALKER_SEAM_CALLER) + (None,) * 13),
)


@pytest.mark.parametrize("name,callbacks", WALKER_SEAM_CASES,
                         ids=[case[0] for case in WALKER_SEAM_CASES])
def test_walker_truncates_batch_before_a_vdp_seam(name, callbacks):
    """A seam slot mid-pass truncates the batch instead of discarding it.

    Every iteration before the seam slot is admitted as one plan ending at
    the loop head with the loop state exactly as the original leaves it
    there; the single-iteration gate then owns the seam slot (and, since
    this fixture's trailing slots are all empty, the remaining tail is
    admitted as a second, fresh batch) -- exactly one decline regardless of
    how many good iterations preceded the seam in this same pass.
    """
    state = oracle.constructed_walker_state(callbacks=callbacks)
    expected = oracle.execute_walker(state, candidate=None)
    actual = oracle.execute_walker(state, candidate="lifecycle")
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["fallbacks"] == 1
    assert actual.stats["fallback_reasons"] == {
        "unsupported domain: spawn dispatcher walker cannot batch a "
        "VDP tile-upload seam mid-loop": 1}
    assert actual.stats["spawn_caller_hits"] == 1
    # The seam-first case has nothing to truncate to (the very first slot in
    # its call is already the seam), so only the post-seam tail becomes a
    # walker hit; every other case also admits the pre-seam prefix as its
    # own walker hit.
    assert actual.stats["spawn_walker_hits"] == (1 if name == "seam-first" else 2)


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_walker_seam_truncation_negative_controls(mutant):
    """The truncated prefix plan itself still rejects a wrong witness."""
    state = oracle.constructed_walker_state(
        callbacks=(KNOWN_WALKER_A, WALKER_SEAM_CALLER) + (None,) * 14)
    expected = oracle.execute_walker(state, candidate=None)
    actual = oracle.execute_walker(state, candidate="lifecycle-mutant-" + mutant,
                                   stop_after_first=True)
    assert actual.outer != expected.outer


ROW_KNOWN_A = 0x1B72D4
ROW_KNOWN_B = 0x1B6802
ROW_UNKNOWN = 0x1B6D1E  # inadmissible (multi-native-call prefix); stays unrecovered
ROW_CASES = (
    ("empty", (None,) * 23),
    ("single", (ROW_KNOWN_A,) + (None,) * 22),
    ("multiple", (ROW_KNOWN_A, ROW_KNOWN_B) + (None,) * 21),
    ("unknown", (ROW_KNOWN_A, ROW_UNKNOWN) + (None,) * 21),
)


@pytest.mark.parametrize("name,callbacks", ROW_CASES,
                         ids=[case[0] for case in ROW_CASES])
def test_constructed_row_walker_matches_outer_and_future(name, callbacks):
    state = oracle.constructed_row_walker_state(callbacks=callbacks)
    expected = oracle.execute_walker(state, candidate=None, row=True)
    actual = oracle.execute_walker(state, candidate="lifecycle", row=True)
    assert expected.iterations == 23
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["fallbacks"] == (2 if name == "unknown" else 0)
    assert actual.stats["spawn_row_walker_hits"] == 1
    # The first two plans encounter the unknown second slot; after original
    # execution passes it, the remaining empty suffix is admitted in Python.
    assert actual.iterations == (3 if name == "unknown" else 1)


@pytest.mark.parametrize("count", (1, 2, 23))
def test_constructed_row_walker_counts_match_original(count):
    state = oracle.constructed_row_walker_state(count=count)
    expected = oracle.execute_walker(state, candidate=None, row=True)
    actual = oracle.execute_walker(state, candidate="lifecycle", row=True)
    assert expected.iterations == count
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_row_walker_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_row_walker_postincrement_crossing_24bit_ram_preserves_32bit_a0():
    state = oracle.constructed_row_walker_state(count=1, cursor=0x00FF_FFFE,
                                                slot_indices=(0x100,))
    expected = oracle.execute_walker(state, candidate=None, row=True)
    actual = oracle.execute_walker(state, candidate="lifecycle", row=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.outer["registers"]["a0"] == 0x0100_0000
    assert actual.stats["spawn_row_walker_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_row_walker_a0_advance_alias_is_visible_to_planned_movem():
    state = oracle.constructed_row_walker_state(
        count=2, callbacks=(ROW_KNOWN_A, ROW_KNOWN_B), cursor=oracle.STACK - 60,
        slot_indices=(0x100, 0), initial_d0=4)
    # The first row advances A0 before its callback frame is materialized. The
    # second indexed flag is therefore supplied through the planned alias.
    writes = ((0xFFAE89, oracle._callback_flag(ROW_KNOWN_B)),)
    expected = oracle.execute_walker(state, candidate=None, row=True, writes=writes)
    actual = oracle.execute_walker(state, candidate="lifecycle", row=True, writes=writes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.outer["registers"]["d2"] & 0xFFFF == 2
    assert actual.outer["registers"]["a0"] == oracle.STACK - 56
    assert actual.outer["registers"]["a4"] == ROW_KNOWN_B
    assert actual.stats["spawn_row_walker_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_row_deadline_refusal_preserves_only_the_original_first_instruction():
    state = oracle.constructed_row_walker_state(
        callbacks=(ROW_KNOWN_A,) + (None,) * 22)
    entry = oracle.SPAWN_ROW_DISPATCH_WALKER_ENTRY
    with oracle.Machine(oracle.read_rom()) as original:
        original.restore(state)
        original.gates([entry])
        assert original.run(instructions=1) == "gate"
        original.gate(entry, bypass_once=True)
        assert original.run(instructions=1) == "limit"
        expected = oracle.observable(original)
    with oracle.Machine(oracle.read_rom()) as actual:
        actual.restore(state)
        candidate = oracle.Candidate("lifecycle")
        candidate.arm(actual)
        assert actual.run(instructions=1) == "gate"
        assert candidate.on_gate(actual, actual.info["tick"] + 1) is False
        assert candidate.stats["fallback_reasons"] == {"scheduler admission": 1}
        assert candidate.stats["candidate_hits"] == 0
        assert oracle.observable(actual) == expected


@pytest.mark.parametrize("name,callbacks", ROW_CASES[:3],
                         ids=[case[0] for case in ROW_CASES[:3]])
def test_constructed_row_walker_survives_fresh_process(name, callbacks):
    state = oracle.constructed_row_walker_state(callbacks=callbacks)
    result = oracle.execute_walker(
        state, candidate="lifecycle", row=True, include_raw=True)
    assert result.stats["spawn_row_walker_hits"] == 1
    assert result.iterations == 1
    assert oracle.fresh_process_future(result.outer_state) == result.future


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_row_walker_negative_controls_reject_outer_boundary(mutant):
    state = oracle.constructed_row_walker_state(count=1, callbacks=(ROW_KNOWN_A,))
    expected = oracle.execute_walker(state, candidate=None, row=True)
    actual = oracle.execute_walker(state, candidate="lifecycle-mutant-" + mutant,
                                   row=True, stop_after_first=True)
    assert actual.outer != expected.outer
    assert actual.stats["spawn_row_walker_hits"] == 1


def test_row_walker_unknown_callback_falls_back_to_native_row_execution():
    state = oracle.constructed_row_walker_state(count=1, callbacks=(ROW_UNKNOWN,))
    expected = oracle.execute_walker(state, candidate=None, row=True)
    actual = oracle.execute_walker(state, candidate="lifecycle", row=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_row_walker_hits"] == 0
    assert actual.stats["fallbacks"] == 1


@pytest.mark.parametrize("entry", tuple(oracle.PLAIN_WRAPPERS))
@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_plain_wrapper_direct_plan_matches_original(entry, free, incoming_x):
    expected = oracle.execute_wrapper(entry, free=free, candidate=None,
                                      incoming_x=incoming_x)
    actual = oracle.execute_wrapper(entry, free=free, candidate="lifecycle",
                                    incoming_x=incoming_x)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["candidate_hits"] == 1
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("entry", tuple(oracle.OFFSET_WRAPPERS))
@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
@pytest.mark.parametrize("wrap", (False, True), ids=("ordinary", "coordinate-wrap"))
def test_offset_wrapper_direct_plan_matches_original(entry, free, incoming_x, wrap):
    setup = ()
    if wrap:
        _, _, x_delta, y_delta = oracle.OFFSET_WRAPPERS[entry]
        x_base = 4 if x_delta < 0 else 0xFFF8
        y_base = (-y_delta) & 0xFFFF
        setup = (oracle.write_word(0xFFF150, x_base) +
                 oracle.write_word(0xFF7DB0, 0) +
                 oracle.write_word(0xFFF152, y_base) +
                 oracle.write_word(0xFF7DB2, 0))
    expected = oracle.execute_wrapper(entry, free=free, candidate=None,
                                      incoming_x=incoming_x, setup_writes=setup)
    actual = oracle.execute_wrapper(entry, free=free, candidate="lifecycle",
                                    incoming_x=incoming_x, setup_writes=setup)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["candidate_hits"] == 1
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("entry", tuple((*oracle.PLAIN_WRAPPERS, *oracle.OFFSET_WRAPPERS)))
def test_new_wrapper_direct_plan_survives_fresh_process(entry):
    result = oracle.execute_wrapper(
        entry, free=0, candidate="lifecycle", incoming_x=False, include_raw=True)
    assert result.stats["candidate_hits"] == 1
    assert oracle.fresh_process_future(result.outer_state) == result.future


@pytest.mark.parametrize("entry", tuple(oracle.CLOSURE_WRAPPERS))
@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_remaining_recorded_closures_direct_outer_future_and_fresh(entry, free, incoming_x):
    expected = oracle.execute_wrapper(entry, free=free, candidate=None,
                                      incoming_x=incoming_x)
    actual = oracle.execute_wrapper(entry, free=free, candidate="lifecycle",
                                    incoming_x=incoming_x, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["candidate_hits"] == 1
    assert actual.stats["fallbacks"] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize("entry,fields", tuple(CLOSURE_OUTPUTS.items()))
def test_remaining_closure_semantic_suffix_writes_are_present(entry, fields):
    result = oracle.execute_wrapper(
        entry, free=0, candidate="lifecycle", incoming_x=False, include_raw=True)
    assert result.stats["candidate_hits"] == 1
    observed = _outer_record_bytes(result.outer_state, fields)
    assert observed == {offset: expected for offset, expected in fields}


@pytest.mark.parametrize("guard_value", (0, 1), ids=("guard-clear", "guard-set"))
@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
def test_remaining_guarded_closure_direct_skip_taken_and_exhausted(guard_value, free):
    setup = ((0xFFF12A, guard_value),)
    expected = oracle.execute_wrapper(0x1B71A0, free=free, candidate=None,
                                      incoming_x=False, setup_writes=setup)
    actual = oracle.execute_wrapper(0x1B71A0, free=free, candidate="lifecycle",
                                    incoming_x=False, setup_writes=setup)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["candidate_hits"] == 1
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("target", (*oracle.CLOSURE_WRAPPERS, oracle.SAFE_RETURN))
@pytest.mark.parametrize("free", (0, 19, None), ids=("first-free", "late-free", "exhausted"))
@pytest.mark.parametrize("incoming_x", (False, True), ids=("x-clear", "x-set"))
def test_remaining_callbacks_dispatcher_outer_future_and_fresh(target, free, incoming_x):
    expected = oracle.execute_dispatch(target, free=free, candidate=None,
                                       incoming_x=incoming_x)
    actual = oracle.execute_dispatch(target, free=free, candidate="lifecycle",
                                     incoming_x=incoming_x)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0
    result = oracle.execute_dispatch(
        target, free=free, candidate="lifecycle", incoming_x=incoming_x,
        include_raw=True)
    assert result.stats["spawn_caller_hits"] == 1
    assert oracle.fresh_process_future(result.outer_state) == result.future


@pytest.mark.parametrize("guard_value", (0, 1), ids=("guard-clear", "guard-set"))
@pytest.mark.parametrize("free", (0, None), ids=("slot-available", "pool-exhausted"))
def test_remaining_guarded_closure_dispatcher_skip_taken_and_exhausted(guard_value, free):
    expected = oracle.execute_dispatch(0x1B71A0, free=free, candidate=None,
                                       incoming_x=False, guard_value=guard_value)
    actual = oracle.execute_dispatch(0x1B71A0, free=free, candidate="lifecycle",
                                     incoming_x=False, guard_value=guard_value)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_safe_return_callback_is_handled_only_as_dispatcher_child():
    """1B65BE is a real selected child, never a standalone global hook."""
    assert oracle.SAFE_RETURN not in oracle.Candidate("lifecycle").gate_pcs
    expected = oracle.execute_dispatch(oracle.SAFE_RETURN, free=0, candidate=None,
                                       incoming_x=False)
    actual = oracle.execute_dispatch(oracle.SAFE_RETURN, free=0,
                                     candidate="lifecycle", incoming_x=False)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0
    assert actual.stats["direct_python_calls"] == 1


@pytest.mark.parametrize("free", (0, 19))
def test_guarded_spawn_success_installs_its_script(free):
    result = oracle.execute_wrapper(
        0x1B71A0, free=free, candidate="lifecycle", incoming_x=False,
        setup_writes=((0xFFF12A, 1),), include_raw=True)
    assert result.stats["candidate_hits"] == 1
    assert _outer_record_bytes(result.outer_state, ((0x20, 0x124318),)) == {0x20: 0x124318}


DOUBLE_CAP_ENTRY = 0x1B67C2


def _double_cap_seed_writes(seed):
    return tuple((0xFF7DEA + index, (seed >> (8 * (3 - index))) & 0xFF) for index in range(4))


@pytest.mark.parametrize("name,seed,free,extra_free", (
    # roll 1 low byte 0xCA (>= 0xC8): skip the first attempt, go straight to
    # the shared second/skip-arm tail; that lone allocation succeeds.
    ("skip-first", 0xF, 0, ()),
    # roll 1 low byte 0x07 (< 0xC8): attempt the first spawn, but the pool is
    # fully occupied (free=None) so its allocation fails with no roll spent
    # on jitter and no second cap check at all.
    ("attempt-first-alloc-fails", 0x0, None, ()),
    # roll 1 low byte 0x48 (< 0xC8): first spawn succeeds and its jitter
    # writes (bit 0 set, bit 1 clear); roll 4 (the second cap check) is
    # 0xEB (>= 0xC8), so the second attempt is skipped.
    ("attempt-first-then-skip-second", 0x5, 0, ()),
    # roll 1 low byte 0x07 (< 0xC8): first spawn succeeds (script written,
    # bit 0 set); roll 4 is 0x14 (< 0xC8) so a second, independent
    # allocation is attempted and also succeeds (both jitter bits clear).
    ("double-spawn", 0x0, 0, (0xFF842E,)),
))
def test_reverse_double_cap_matches_original_outer_and_future(name, seed, free, extra_free):
    writes = _double_cap_seed_writes(seed) + tuple((address, 0) for address in extra_free)
    expected = oracle.execute_dispatch(DOUBLE_CAP_ENTRY, free=free, candidate=None,
                                       incoming_x=False, setup_writes=writes)
    actual = oracle.execute_dispatch(DOUBLE_CAP_ENTRY, free=free, candidate="lifecycle",
                                     incoming_x=False, setup_writes=writes)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_caller_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_reverse_double_cap_skip_first_matches_the_bare_second_attempt_shape():
    """The skip-first arm reaches the same 1B67E6 tail with no roll spent
    on a first attempt: only one allocation and one jitter/script pair."""
    writes = _double_cap_seed_writes(0xF)
    result = oracle.execute_dispatch(DOUBLE_CAP_ENTRY, free=0, candidate="lifecycle",
                                     incoming_x=False, setup_writes=writes, include_raw=True)
    assert result.stats["spawn_caller_hits"] == 1
    assert oracle.fresh_process_future(result.outer_state) == result.future


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_reverse_double_cap_double_spawn_negative_controls(mutant):
    writes = _double_cap_seed_writes(0x0) + ((0xFF842E, 0),)
    expected = oracle.execute_dispatch(DOUBLE_CAP_ENTRY, free=0, candidate=None,
                                       incoming_x=False, setup_writes=writes)
    actual = oracle.execute_dispatch(DOUBLE_CAP_ENTRY, free=0,
                                     candidate="lifecycle-mutant-" + mutant,
                                     incoming_x=False, setup_writes=writes)
    assert (actual.outer, actual.future) != (expected.outer, expected.future)


SETUP_KNOWN_A = 0x1B72D4
SETUP_KNOWN_B = 0x1B6802
SETUP_UNKNOWN = 0x1B6D1E  # inadmissible (multi-native-call prefix); stays unrecovered


def _setup_callbacks(entry, case):
    count = 23 if entry in (oracle.SPAWN_SETUP_ROW_LOW_ENTRY,
                            oracle.SPAWN_SETUP_ROW_HIGH_ENTRY) else 16
    if case == "empty":
        values = ()
    elif case == "multiple":
        values = (SETUP_KNOWN_A, SETUP_KNOWN_B)
    elif case == "unknown":
        values = (SETUP_KNOWN_A, SETUP_UNKNOWN)
    else:
        raise ValueError(case)
    return values + (None,) * (count - len(values))


@pytest.mark.parametrize("entry", oracle.SETUP_ENTRIES)
@pytest.mark.parametrize("case", ("empty", "multiple", "unknown"))
def test_constructed_full_setup_matches_original_outer_and_future(entry, case):
    state = oracle.constructed_setup_state(
        entry, callbacks=_setup_callbacks(entry, case),
        position=0x1237, varying=0x245F)
    expected = oracle.execute_setup(state, entry=entry, candidate=None)
    actual = oracle.execute_setup(state, entry=entry, candidate="lifecycle")
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    if case == "unknown":
        # The aggregate setup plan is correctly declined before writing. The
        # remaining native loop may still admit an empty suffix after the
        # unresolved callback has returned.
        assert actual.stats["spawn_setup_hits"] == 0
        assert actual.stats["fallbacks"] >= 1
    else:
        assert actual.stats["spawn_setup_hits"] == 1
        assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("entry", oracle.SETUP_ENTRIES)
def test_full_setup_truncates_its_composed_walker_before_a_vdp_seam(entry):
    """spawn_setup_dispatch must not treat a truncated walker as complete.

    The setup composes its own prefix directly onto the walker's plan (it
    is not reached through the walker's own gate), so it has to recognize
    a truncated batch itself: composing the outer-return read against a
    walker that only reached the loop head -- not its RTS -- would misread
    the stack as a return address that was never pushed. This mirrors
    ``test_walker_truncates_batch_before_a_vdp_seam`` one level out.
    """
    row = entry in (oracle.SPAWN_SETUP_ROW_LOW_ENTRY, oracle.SPAWN_SETUP_ROW_HIGH_ENTRY)
    count = 23 if row else 16
    callbacks = (KNOWN_WALKER_A, WALKER_SEAM_CALLER) + (None,) * (count - 2)
    state = oracle.constructed_setup_state(
        entry, callbacks=callbacks, position=0x1237, varying=0x245F)
    expected = oracle.execute_setup(state, entry=entry, candidate=None)
    actual = oracle.execute_setup(state, entry=entry, candidate="lifecycle")
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_setup_hits"] == 1
    assert actual.stats["fallbacks"] == 1
    assert actual.stats["fallback_reasons"] == {
        "unsupported domain: spawn dispatcher walker cannot batch a "
        "VDP tile-upload seam mid-loop": 1}
    # The composed prefix (setup + pre-seam iterations) is admitted as the
    # setup's own hit; the post-seam tail (all empty slots) is admitted as
    # a second, ordinary walker hit reached directly through the loop head.
    assert actual.stats["spawn_walker_hits"] == 2


@pytest.mark.parametrize("entry", oracle.SETUP_ENTRIES)
def test_full_setup_preserves_register_words_stride_and_coordinate_masks(entry):
    row = entry in (oracle.SPAWN_SETUP_ROW_LOW_ENTRY,
                    oracle.SPAWN_SETUP_ROW_HIGH_ENTRY)
    state = oracle.constructed_setup_state(
        entry, callbacks=_setup_callbacks(entry, "empty"),
        incoming_x=True, cursor=(0x00FF_F000 if row else 0x00FF_FFFE),
        stride=(0xFFFE if not row else 0x7FFF),
        position=0x1237, varying=0x245F,
        initial_d0=0xABCD0001, initial_d4=0x13570003,
        initial_d5=0x2468A002, initial_d6=0xFACE0004)
    expected = oracle.execute_setup(state, entry=entry, candidate=None)
    actual = oracle.execute_setup(state, entry=entry, candidate="lifecycle")
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_setup_hits"] == 1
    assert actual.stats["fallbacks"] == 0


@pytest.mark.parametrize("entry", oracle.SETUP_ENTRIES)
def test_full_setup_candidate_outer_state_survives_fresh_process(entry):
    state = oracle.constructed_setup_state(
        entry, callbacks=_setup_callbacks(entry, "multiple"))
    result = oracle.execute_setup(
        state, entry=entry, candidate="lifecycle", include_raw=True)
    assert result.stats["spawn_setup_hits"] == 1
    assert oracle.fresh_process_future(result.outer_state) == result.future


@pytest.mark.parametrize("mutant", ("result", "timing", "continuation"))
def test_full_setup_negative_controls_reject_outer_boundary(mutant):
    entry = oracle.SPAWN_SETUP_LEFT_ENTRY
    state = oracle.constructed_setup_state(
        entry, callbacks=_setup_callbacks(entry, "empty"))
    expected = oracle.execute_setup(state, entry=entry, candidate=None)
    actual = oracle.execute_setup(
        state, entry=entry, candidate="lifecycle-mutant-" + mutant,
        stop_after_first=True)
    assert actual.outer != expected.outer
    assert actual.stats["spawn_setup_hits"] == 1


def test_setup_gate_set_stays_within_native_capacity_and_is_unique():
    gates = oracle.Candidate("lifecycle").gate_pcs
    assert len(gates) <= 64
    assert len(gates) == len(set(gates))


def test_setup_rts_reads_return_slot_overwritten_by_allocated_object():
    entry = oracle.SPAWN_SETUP_LEFT_ENTRY
    # A free primary object aliases the caller's return slot. Initialization
    # installs template byte 1 = 1 and X = 0x200, changing RTS to 0x010200.
    # This deliberately constructed return enters ROM data: qualify four
    # native instructions there; ordinary setup fixtures cover 150 and restore.
    state = oracle.constructed_setup_state(
        entry, callbacks=(0x1B6C4E,) + (None,) * 15,
        stack=0xFF7E82, position=0x210)
    expected = oracle.execute_setup(
        state, entry=entry, candidate=None,
        expected_return=0x010200, future_instructions=4)
    actual = oracle.execute_setup(
        state, entry=entry, candidate="lifecycle",
        expected_return=0x010200, future_instructions=4)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats["spawn_setup_hits"] == 1
    assert actual.stats["fallbacks"] == 0


def test_setup_odd_stack_is_refused_before_candidate_writes():
    from aladdin_sega.recovery import Candidate

    entry = oracle.SPAWN_SETUP_LEFT_ENTRY
    state = oracle.constructed_setup_state(
        entry, callbacks=_setup_callbacks(entry, "empty"), stack=oracle.STACK + 1)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([entry])
        assert machine.run(instructions=1) == "gate"
        recovery = Candidate("lifecycle")
        recovery.arm(machine)
        assert machine.run(instructions=1) == "gate"
        assert recovery.on_gate(machine, machine.info["tick"] + 1_000_000) is False
        assert recovery.stats["spawn_setup_hits"] == 0
        assert recovery.stats["fallbacks"] == 1
        assert recovery.stats["candidate_hits"] == 0
    finally:
        machine.close()


def test_setup_deadline_refusal_preserves_only_original_first_instruction():
    entry = oracle.SPAWN_SETUP_LEFT_ENTRY
    state = oracle.constructed_setup_state(
        entry, callbacks=_setup_callbacks(entry, "empty"))
    from aladdin_sega.recovery import Candidate

    original = oracle.Machine(oracle.read_rom())
    try:
        original.restore(state)
        original.gates([entry])
        assert original.run(instructions=1) == "gate"
        original.gate(entry, bypass_once=True)
        assert original.run(instructions=1) == "limit"
        expected = oracle.observable(original)
    finally:
        original.close()

    actual = oracle.Machine(oracle.read_rom())
    try:
        actual.restore(state)
        recovery = Candidate("lifecycle")
        recovery.arm(actual)
        assert actual.run(instructions=1) == "gate"
        assert recovery.on_gate(actual, actual.info["tick"] + 1) is False
        assert recovery.stats["fallback_reasons"] == {"scheduler admission": 1}
        assert recovery.stats["candidate_hits"] == 0
        assert oracle.observable(actual) == expected
    finally:
        actual.close()
