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


SELECTOR_FIXTURES = [
    ("old", ROOT / "selector-recorded" / "old.alsnap"),
    ("new", ROOT / "selector-recorded" / "new.alsnap"),
]
SELECTOR_FLAGS = (0xFFF0D7, 0xFFF173, 0xFFF115, 0xFFF0CD, 0xFFF0DB,
                  0xFFF0D0, 0xFFF0D2, 0xFFF0C1, 0xFFF0DE, 0xFFF0DF, 0xFFF0ED)
SELECTOR_SENTINELS = {0xFFF0E7: 0xA5, 0xFF7E77: 0x5A, 0xFFF0CC: 0xC3}


def _selector_cases():
    cases = [("priority_d7", {0xFFF0D7: 1}, 0x121964, 0x00,
                              (0x34, 4)),
             ("priority_f173", {0xFFF173: 1}, 0x121C28, 0x04,
                              (0x92, 10)),
             ("priority_115", {0xFFF115: 1}, 0x125E72, 0x04,
                              (0xA6, 11)),
             ("priority_cd", {0xFFF0CD: 1}, 0x121AD8, 0x04,
                              (0x16E, 26)),
             ("priority_db", {0xFFF0DB: 1}, 0x12181A, 0x00,
                              (0xE4, 16)),
             ("priority_d0", {0xFFF0D0: 1}, 0x1218CA, 0x04,
                              (0x13C, 23)),
             ("priority_d2", {0xFFF0D2: 1}, 0x121C62, 0x00,
                              (0x118, 20)),
             ("priority_c1", {0xFFF0C1: 1}, 0x121D9A, 0x09,
                              (0x1DC, 34)),
             ("priority_de", {0xFFF0DE: 1}, 0x121AD8, 0x04,
                              (0x134, 22)),
             ("priority_df", {0xFFF0DF: 1}, 0x121AD8, 0x04,
                              (0x134, 22)),
             ("priority_ed", {0xFFF0ED: 1}, 0x121AD8, 0x04,
                              (0x134, 22)),
             ("priority_all", {address: 1 for address in SELECTOR_FLAGS},
                              0x121964, 0x00, (0x34, 4))]
    cases.extend([
        ("f173_plus_115", {0xFFF173: 1, 0xFFF115: 1}, 0x121C28, 0x04, (0x92, 10)),
        ("115_plus_cd", {0xFFF115: 1, 0xFFF0CD: 1}, 0x125E72, 0x04, (0xA6, 11)),
        ("cd_miss_plus_db", {0xFFF0CD: 1, 0xFFF0D3: 0x4F, 0xFFF0DB: 1},
         0x12181A, 0x00, (0x11E, 20)),
        ("d3_5e_plus_db", {0xFFF0CD: 1, 0xFFF0D3: 0x5E, 0xFFF0DB: 1},
         0x122336, 0x04, (0x134, 21)),
        ("d3_5e_without_cd", {0xFFF0D3: 0x5E},
         0x122336, 0x04, (0xDE, 15)),
        ("d3_5e_without_cd_db", {0xFFF0D3: 0x5E, 0xFFF0DB: 1},
         0x122336, 0x04, (0xDE, 15)),
        ("d3_5e_without_cd_d0", {0xFFF0D3: 0x5E, 0xFFF0D0: 1},
         0x122336, 0x04, (0xDE, 15)),
        ("d0_plus_d2", {0xFFF0D0: 1, 0xFFF0D2: 1}, 0x1218CA, 0x04, (0x13C, 23)),
        ("c1_plus_de_df_ed", {0xFFF0C1: 1, 0xFFF0DE: 1, 0xFFF0DF: 1, 0xFFF0ED: 1},
         0x12231E, 0x00, (0x14E, 24)),
        ("c1_b0_0_normal", {0xFFF0C1: 1, 0xFFF0B0: 0}, 0x121D9A, 0x09, (0x1DC, 34)),
        ("c1_b0_1_normal", {0xFFF0C1: 1, 0xFFF0B0: 1}, 0x122006, 0x04, (0x1A2, 30)),
        ("c1_b0_2_normal", {0xFFF0C1: 1, 0xFFF0B0: 2}, 0x122006, 0x04, (0x1CE, 33)),
        ("c1_b0_3_normal", {0xFFF0C1: 1, 0xFFF0B0: 3}, 0x121D9A, 0x00, (0x1DC, 34)),
    ])
    for value, selected, ccr, cost in (
        (0x4F, 0x121AD8, 0x04, (0x16E, 26)),
        (0x50, 0x121964, 0x04, (0xF8, 17)),
        (0x51, 0x121964, 0x04, (0xF8, 17)),
        (0x52, 0x121AD8, 0x04, (0x18A, 28)),
        (0x5D, 0x121AD8, 0x04, (0x18A, 28)),
        (0x5E, 0x122336, 0x04, (0x134, 21)),
        (0x5F, 0x121AD8, 0x04, (0x18A, 28)),
        (0x60, 0x122336, 0x04, (0x116, 19)),
        (0x61, 0x121AD8, 0x04, (0x18A, 28)),
    ):
        cases.append((f"d3_{value:02X}", {0xFFF0CD: 1, 0xFFF0D3: value},
                      selected, ccr, cost))
    for c1, b0, selected, ccr, cost in (
        (0, 0, 0x121C28, 0x04, (0x92, 10)),
        (1, 0, 0x121D5A, 0x04, (0xEC, 16)),
        (1, 1, 0x121FD4, 0x04, (0xB2, 12)),
        (1, 2, 0x121FD4, 0x04, (0xCE, 14)),
        (1, 3, 0x121D5A, 0x04, (0xEC, 16)),
    ):
        cases.append((f"f173_c1_{c1}_b0_{b0}",
                      {0xFFF173: 1, 0xFFF0C1: c1, 0xFFF0B0: b0},
                      selected, ccr, cost))
    for value, selected, ccr in (
        (0x0000, 0x1218CA, 0x04), (0x0001, 0x1218CA, 0x04),
        (0x0003, 0x1218CA, 0x04), (0x0004, 0x1218BC, 0x00),
        (0x0007, 0x1218BC, 0x00), (0x0008, 0x1218AE, 0x00),
        (0x003B, 0x121876, 0x00), (0x003C, 0x121868, 0x00),
        (0x003F, 0x121868, 0x00), (0x0040, 0x1218CA, 0x04),
        (0xFFFF, 0x121868, 0x00),
    ):
        cases.append((f"d0_{value:04X}", {0xFFF0D0: 1, 0xFF7E04: value},
                      selected, ccr, (0x13C, 23)))
    return cases


def _selector_run(path, changes, incoming_x=None):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        for address in SELECTOR_FLAGS:
            native_write(machine, address, b"\0")
        native_write(machine, 0xFFF0D3, b"\0")
        native_write(machine, 0xFFF0B0, b"\0\0")
        native_write(machine, 0xFF7E04, b"\0\0")
        for address, value in SELECTOR_SENTINELS.items():
            native_write(machine, address, bytes((value,)))
        for address, value in changes.items():
            native_write(machine, address, value.to_bytes(2 if address in (0xFFF0B0, 0xFF7E04) else 1, "big"))
        if incoming_x is not None:
            selector_pc = machine.info["pc"]
            machine.gates([selector_pc])
            assert machine.run(instructions=1) == "gate"
            registers = machine.registers()
            sr = (registers["sr"] & ~0x10) | (0x10 if incoming_x else 0)
            assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                                  cycles=1, instructions=1, last_pc=selector_pc,
                                  writes=[], registers={"sr": sr})
        before = machine.info
        before_ram = machine.peek_ram(0, 65536)
        machine.gates([0x1AEC64])
        assert machine.run(instructions=10000) == "gate"
        outer = (artifacts.snapshot_bytes(machine), machine.info, machine.registers(),
                 machine.peek_ram(0, 65536), machine.frame()[2], machine.audio())
        changed = {offset: (old, new) for offset, (old, new) in enumerate(zip(before_ram, outer[3]))
                   if old != new}
        cost = (outer[1]["m68k_cycles"] - before["m68k_cycles"],
                outer[1]["m68k_instructions"] - before["m68k_instructions"])
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        future = (artifacts.snapshot_bytes(machine), machine.info, machine.registers(),
                  machine.peek_ram(0, 65536), machine.frame()[2], machine.audio())
    return outer, future, changed, cost


@pytest.mark.parametrize("corpus,path", SELECTOR_FIXTURES)
@pytest.mark.parametrize("name,changes,selected,ccr,cost", _selector_cases(),
                         ids=lambda value: str(value))
def test_selector_matrix_full_original_state(corpus, path, name, changes, selected, ccr, cost):
    first = _selector_run(path, changes)
    second = _selector_run(path, changes)
    assert first == second
    outer, future, changed, actual_cost = first
    assert outer[1]["pc"] == 0x1AEC64
    assert outer[2]["a2"] & 0xFFFFFF == selected
    assert outer[2]["sr"] & 0x1F == ccr
    assert actual_cost == cost
    assert future[1]["m68k_instructions"] - outer[1]["m68k_instructions"] == 150
    assert set(changed) <= {0x7E77, 0xF0E7, 0xF0CC}


SELECTOR_TABLE_X_CASES = [
    (value, selected, ccr)
    for value, selected, ccr in (
        (0x0000, 0x1218CA, 0x04), (0x0001, 0x1218CA, 0x04),
        (0x0003, 0x1218CA, 0x04), (0x0004, 0x1218BC, 0x00),
        (0x0007, 0x1218BC, 0x00), (0x0008, 0x1218AE, 0x00),
        (0x003B, 0x121876, 0x00), (0x003C, 0x121868, 0x00),
        (0x003F, 0x121868, 0x00), (0x0040, 0x1218CA, 0x04),
        (0xFFFF, 0x121868, 0x00),
    )
]


@pytest.mark.parametrize("corpus,path", SELECTOR_FIXTURES)
@pytest.mark.parametrize("incoming_x", [0, 1])
@pytest.mark.parametrize("value,selected,ccr", SELECTOR_TABLE_X_CASES)
def test_selector_table_shifts_have_full_x_and_future_contract(corpus, path, incoming_x,
                                                               value, selected, ccr):
    changes = {0xFFF0D0: 1, 0xFF7E04: value}
    first = _selector_run(path, changes, incoming_x=incoming_x)
    second = _selector_run(path, changes, incoming_x=incoming_x)
    assert first == second
    outer, future, changed, cost = first
    assert outer[2]["a2"] & 0xFFFFFF == selected
    assert outer[2]["sr"] & 0x1F == ccr
    assert bool(outer[2]["sr"] & 0x10) is False
    assert cost == (0x13C, 23)
    assert future[1]["m68k_instructions"] - outer[1]["m68k_instructions"] == 150
    assert set(changed) <= {0x7E77, 0xF0E7, 0xF0CC}


@pytest.mark.parametrize("corpus,path", SELECTOR_FIXTURES)
@pytest.mark.parametrize("incoming_x", [0, 1])
@pytest.mark.parametrize("changes,selected,ccr", [
    ({0xFFF0D7: 1}, 0x121964, 0x00),
    ({0xFFF173: 1}, 0x121C28, 0x04),
    ({0xFFF0C1: 1}, 0x121D9A, 0x09),
])
def test_selector_non_table_routes_preserve_incoming_x(corpus, path, incoming_x,
                                                        changes, selected, ccr):
    outer, future, _, cost = _selector_run(path, changes, incoming_x=incoming_x)
    assert outer[2]["a2"] & 0xFFFFFF == selected
    assert outer[2]["sr"] & 0x1F == (ccr | (0x10 if incoming_x else 0))
    assert cost[0] > 0 and cost[1] > 0
    assert future[1]["m68k_instructions"] - outer[1]["m68k_instructions"] == 150


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
