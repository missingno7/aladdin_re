"""Independent native qualification for the adjacent 1AEC00 retirement family."""
from __future__ import annotations

from pathlib import Path

import pytest

from aladdin_sega import artifacts
from aladdin_sega.boundary import (COLLECTION_DISPATCH_RETURN, COLLECTION_DISPATCH_ENTRY,
                                   CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT,
                                   begin_contact_sibling_retirement)
from aladdin_sega.game.objects.contact import contact_sibling_route
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from aladdin_sega.recovery import Candidate
from test_recovery import native_write


ROOT = Path("artifacts/grinding/parent")
TARGETS = ("1AEC00", "1AEC2A", "1AEC32", "1AECD8", "1AED0C")
ENTRY = {name: int(name, 16) for name in TARGETS}


def _reader(values):
    return lambda address, size=1: values.get(address, 0)


@pytest.mark.parametrize("direction,distance,limit,expected", [
    (0, 9, 10, ("retire10", 0x10)),
    (0, 10, 10, ("early", None)),
    (1, 9, 10, ("early", None)),
    (1, 10, 10, ("retire10", 0x10)),
])
def test_sibling_direction_gate_matches_original_order(direction, distance, limit, expected):
    values = {0xFFF0D8: 1, 0xFF7E49: direction, 0xFF7E02: distance,
              0x1002: limit, 0x1000: 0x10, 0x1001: 0}
    assert contact_sibling_route(_reader(values), 0x1000) == expected


@pytest.mark.parametrize("object_type,expected", [
    (0x10, ("retire10", 0x10)), (0x11, ("retire11", 0x11)),
    (0x13, ("type13", 0x13)), (0x18, ("retire18", 0x18)),
    (0x42, ("retire", 0x42)),
])
def test_sibling_counter_arm_selects_type_specific_retirement(object_type, expected):
    values = {0xFFF0D8: 1, 0xFF7E49: 0, 0xFF7E02: 9,
              0x1002: 10, 0x1000: object_type, 0x1001: 0}
    assert contact_sibling_route(_reader(values), 0x1000) == expected


def test_sibling_d8_zero_is_the_existing_contact_wrapper_arm():
    values = {0xFFF0D8: 0, 0x1000: 0x10, 0x1001: 0}
    assert contact_sibling_route(_reader(values), 0x1000) == ("contact", None)


def test_sibling_object_flag_one_is_decrement_arm_before_type_dispatch():
    values = {0xFFF0D8: 1, 0xFF7E49: 0, 0xFF7E02: 9,
              0x1002: 10, 0x1000: 0x13, 0x1001: 1}
    assert contact_sibling_route(_reader(values), 0x1000) == ("decrement", None)


def test_internal_retirement_tail_points_are_oracle_only():
    gates = set(Candidate("lifecycle").gate_pcs)
    assert ENTRY["1AEC00"] in gates
    assert ENTRY["1AECD8"] not in gates
    assert ENTRY["1AED0C"] not in gates


def _fixture_paths():
    paths = [
        (corpus, name, ROOT / corpus / f"{name}.alsnap")
        for corpus in ("sibling-census-old", "sibling-census-new")
        for name in TARGETS
    ]
    missing = [path for _, _, path in paths if not path.exists()]
    if missing:
        pytest.skip("sibling census fixtures are not present")
    return paths


def _observable(machine):
    return (artifacts.snapshot_bytes(machine), machine.info, machine.registers(),
            machine.peek_ram(0, 65536), machine.frame()[2], machine.audio())


def _original(path):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        before = machine.info
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        outer = _observable(machine)
        assert machine.info["pc"] == COLLECTION_DISPATCH_RETURN
        outer_cost = (machine.info["m68k_cycles"] - before["m68k_cycles"],
                      machine.info["m68k_instructions"] - before["m68k_instructions"])
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        return outer, _observable(machine), outer_cost


def _candidate(path, entry):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        assert entry in Candidate("lifecycle").gate_pcs
        machine.gates([entry])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        accepted = candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        outer = _observable(machine)
        assert machine.info["pc"] == COLLECTION_DISPATCH_RETURN
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        return outer, _observable(machine), accepted, candidate.stats


def _direct_retirement_plan(path, **case):
    """Qualify an internal 1AECD8/1AED0C plan without adding a gate."""
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_retirement_case(machine, **case)
        before = machine.info
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        expected = _observable(machine)
        cost = (machine.info["m68k_cycles"] - before["m68k_cycles"],
                machine.info["m68k_instructions"] - before["m68k_instructions"])
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_retirement_case(machine, **case)
        entry = int(path.stem, 16)
        machine.gates([entry])
        assert machine.run(instructions=1) == "gate"
        plan = begin_contact_sibling_retirement(machine, machine.registers())
        assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=plan.cycles, instructions=plan.instructions,
                              writes=list(plan.writes), registers=plan.registers,
                              last_pc=plan.last_pc)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        return expected, _observable(machine), cost


@pytest.mark.parametrize("corpus,name,path", [row for row in _fixture_paths()
                                               if row[1] == "1AEC00"],
                         ids=lambda value: str(value))
def test_retirement_fixture_matches_outer_and_native_future(corpus, name, path):
    expected_outer, expected_future, cost = _original(path)
    actual_outer, actual_future, accepted, stats = _candidate(path, ENTRY[name])
    assert actual_outer == expected_outer
    assert actual_future == expected_future
    assert accepted
    assert stats["candidate_hits"] >= 1
    assert stats["contact_sibling_hits"] >= 1
    assert cost[0] > 0 and cost[1] > 0


@pytest.mark.parametrize("corpus,name,path", [row for row in _fixture_paths()
                                               if row[1] == "1AEC00"],
                         ids=lambda value: str(value))
def test_retirement_fixture_same_process_candidate_restore_is_identical(corpus, name, path):
    first = _candidate(path, ENTRY[name])
    second = _candidate(path, ENTRY[name])
    assert second == first


@pytest.mark.parametrize("corpus,name,path", [row for row in _fixture_paths()
                                               if row[1] in {"1AECD8", "1AED0C"}],
                         ids=lambda value: str(value))
def test_internal_retirement_points_have_original_outer_and_future_receipts(corpus, name, path):
    outer, future, cost = _original(path)
    assert outer[1]["pc"] == COLLECTION_DISPATCH_RETURN
    assert future[1]["m68k_instructions"] - outer[1]["m68k_instructions"] == 150
    assert cost[0] > 0 and cost[1] > 0


def _prepare_retirement_case(machine, *, object_type, total, amount, linked, buffer):
    record = machine.registers()["a1"]
    native_write(machine, record, bytes((object_type, 0)))
    native_write(machine, record + 8, bytes((amount,)))
    native_write(machine, 0xFFF14E, total.to_bytes(2, "big"))
    if buffer:
        native_write(machine, record + 41, b"\x02")
        native_write(machine, record + 42, buffer.to_bytes(4, "big"))
        native_write(machine, buffer, b"\x01\x02\x03")
    else:
        native_write(machine, record + 41, b"\x00")
        native_write(machine, record + 42, b"\x00\x00\x00\x00")
    if linked:
        pair = 0xFF8200
        native_write(machine, record + 62, pair.to_bytes(4, "big"))
        native_write(machine, pair, bytes((0x33,)) * 66)
        native_write(machine, pair + 41, b"\x02")
        native_write(machine, pair + 42, (0xFF9100).to_bytes(4, "big"))
        native_write(machine, 0xFF9100, b"\x11\x22\x33")
    else:
        native_write(machine, record + 62, b"\x00\x00\x00\x00")


def _run_retirement_case(path, entry, **case):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_retirement_case(machine, **case)
        before = machine.info
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        expected = _observable(machine)
        cost = (machine.info["m68k_cycles"] - before["m68k_cycles"],
                machine.info["m68k_instructions"] - before["m68k_instructions"])
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_retirement_case(machine, **case)
        machine.gates([entry])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        accepted = candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        actual = _observable(machine)
        return expected, actual, accepted, candidate.stats, cost


@pytest.mark.parametrize("entry", [ENTRY["1AECD8"]])
@pytest.mark.parametrize("object_type", [0x00, 0x10, 0x11, 0x18, 0xFF])
@pytest.mark.parametrize("total,amount", [(0, 0), (0xFFFF, 1), (0xFFFE, 2)])
@pytest.mark.parametrize("linked,buffer", [(False, 0), (False, 0xFF9000),
                                            (True, 0), (True, 0xFF9000)])
def test_retirement_counter_overflow_pair_and_buffer_domains(entry, object_type, total, amount, linked, buffer):
    paths = [row for row in _fixture_paths() if row[1] == "1AECD8"]
    for _, _, path in paths:
        expected, actual, cost = _direct_retirement_plan(
            path, object_type=object_type, total=total, amount=amount,
            linked=linked, buffer=buffer)
        assert actual == expected
        assert cost[0] > 0 and cost[1] > 0


def _prepare_wrapper(machine, entry, *, d8, direction=0, distance=0, limit=1,
                     object_type=0, contact_early=False, contact_sound=False):
    """Turn the recorded sibling caller frame into a real wrapper activation."""
    registers = machine.registers()
    machine.gates([registers["pc"]])
    assert machine.run(instructions=1) == "gate"
    registers.update(pc=entry, a7=registers["a7"] + 4)
    assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                          writes=[], registers=registers, last_pc=entry)
    record = registers["a1"]
    native_write(machine, 0xFFF0D8, bytes((d8,)))
    native_write(machine, 0xFF7E49, bytes((direction,)))
    native_write(machine, 0xFF7E02, distance.to_bytes(2, "big"))
    native_write(machine, record, bytes((object_type, 0)))
    native_write(machine, record + 2, limit.to_bytes(2, "big"))
    if contact_early:
        native_write(machine, 0xFFF0E7, b"\x00")
        native_write(machine, 0xFFF0E6, b"\x01")
        native_write(machine, 0xFFF0E9, b"\x00")
        native_write(machine, 0xFFF0F2, b"\x00")
    if contact_sound:
        for address, value in ((0xFFF0E7, 0), (0xFFF0E6, 0), (0xFFF0E9, 0),
                               (0xFFF0F2, 0), (0xFFF0BE, 0), (0xFFF0C1, 0),
                               (0xFFF173, 0), (0xFFF57D, 1), (0xFF7E20, 0),
                               (0xFF7E21, 0), (0xFFEFFA, 0)):
            native_write(machine, address, bytes((value,)))


def _run_wrapper_case(path, entry, **case):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_wrapper(machine, entry, **case)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        expected = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        expected_future = _observable(machine)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_wrapper(machine, entry, **case)
        machine.gates([entry])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        accepted = candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        actual = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        return expected, expected_future, actual, _observable(machine), accepted, candidate.stats


@pytest.mark.parametrize("entry", [CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT])
@pytest.mark.parametrize("object_type", [0, 0x10, 0x11, 0x18])
def test_sibling_wrappers_compose_retirement_and_future(entry, object_type):
    paths = [row for row in _fixture_paths() if row[1] == "1AEC00"]
    for _, _, path in paths:
        expected, expected_future, actual, actual_future, accepted, stats = _run_wrapper_case(
            path, entry, d8=1, object_type=object_type)
        assert accepted
        assert actual == expected
        assert actual_future == expected_future
        assert stats["contact_sibling_hits"] == 1


@pytest.mark.parametrize("entry", [CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT])
@pytest.mark.parametrize("direction,distance,limit", [(0, 1, 1), (1, 0, 1)])
def test_sibling_wrappers_keep_directional_early_exit(entry, direction, distance, limit):
    path = ROOT / "sibling-census-old" / "1AEC00.alsnap"
    expected, expected_future, actual, actual_future, accepted, _ = _run_wrapper_case(
        path, entry, d8=1, direction=direction, distance=distance, limit=limit)
    assert accepted
    assert actual == expected
    assert actual_future == expected_future


def test_sibling_wrapper_d8_zero_composes_existing_direct_contact_path():
    path = ROOT / "sibling-census-old" / "1AEC00.alsnap"
    expected, expected_future, actual, actual_future, accepted, stats = _run_wrapper_case(
        path, CONTACT_SIBLING_WRAPPER, d8=0, contact_early=True)
    assert accepted
    assert actual == expected
    assert actual_future == expected_future
    assert stats["contact_sibling_hits"] == 1


def test_sibling_wrapper_d8_zero_reuses_contact_command_31_seam():
    path = ROOT / "sibling-census-old" / "1AEC00.alsnap"
    expected, expected_future, actual, actual_future, accepted, stats = _run_wrapper_case(
        path, CONTACT_SIBLING_WRAPPER, d8=0, contact_sound=True)
    assert accepted
    assert actual == expected
    assert actual_future == expected_future
    assert stats["legacy_entries"] == stats["legacy_returns"] == 1


def test_sibling_direct_wrapper_d8_zero_keeps_1aec00_early_return():
    path = ROOT / "sibling-census-old" / "1AEC00.alsnap"
    expected, expected_future, actual, actual_future, accepted, _ = _run_wrapper_case(
        path, CONTACT_SIBLING_DIRECT, d8=0)
    assert accepted
    assert actual == expected
    assert actual_future == expected_future


def _prepare_dispatch_wrapper(machine, object_type, *, contact_sound=False):
    registers = machine.registers()
    machine.gates([registers["pc"]])
    assert machine.run(instructions=1) == "gate"
    registers.update(pc=COLLECTION_DISPATCH_ENTRY, a7=registers["a7"] + 4)
    assert machine.atomic(target=machine.info["tick"] + 1_000_000, cycles=1, instructions=1,
                          writes=[], registers=registers, last_pc=COLLECTION_DISPATCH_ENTRY)
    record = registers["a1"]
    native_write(machine, record, bytes((object_type, 0)))
    native_write(machine, record + 2, b"\x00\x01")
    native_write(machine, record + 8, b"\x01")
    native_write(machine, 0xFFF0D8, bytes((0 if contact_sound else 1,)))
    native_write(machine, 0xFF7E49, b"\x00")
    native_write(machine, 0xFF7E02, b"\x00\x00")
    if contact_sound:
        for address, value in ((0xFFF0E7, 0), (0xFFF0E6, 0), (0xFFF0E9, 0),
                               (0xFFF0F2, 0), (0xFFF0BE, 0), (0xFFF0C1, 0),
                               (0xFFF173, 0), (0xFFF57D, 1), (0xFF7E20, 0),
                               (0xFF7E21, 0), (0xFFEFFA, 0)):
            native_write(machine, address, bytes((value,)))


@pytest.mark.parametrize("object_type", [0x05, 0x06])
def test_dispatcher_composes_recorded_sibling_wrapper_callbacks(object_type):
    path = ROOT / "sibling-census-old" / "1AEC00.alsnap"
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_dispatch_wrapper(machine, object_type)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        expected = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        expected_future = _observable(machine)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_dispatch_wrapper(machine, object_type)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        assert candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        assert _observable(machine) == expected
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        assert _observable(machine) == expected_future
        assert candidate.stats["collection_dispatch_hits"] == 1


def test_dispatcher_c6_wrapper_reuses_contact_command_31_seam():
    path = ROOT / "sibling-census-old" / "1AEC00.alsnap"
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_dispatch_wrapper(machine, 0x05, contact_sound=True)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        expected = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        expected_future = _observable(machine)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_dispatch_wrapper(machine, 0x05, contact_sound=True)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == "gate"
        candidate = Candidate("lifecycle")
        assert candidate.on_gate(machine, machine.info["tick"] + 1_000_000)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == "gate"
        assert _observable(machine) == expected
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        assert _observable(machine) == expected_future
        assert candidate.stats["legacy_entries"] == candidate.stats["legacy_returns"] == 1
