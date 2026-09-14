"""Bounded collection-dispatch recovery for type-7E's finite exits."""
from pathlib import Path

import pytest
import oracle_witness as oracle
from aladdin_sega.boundary import (COLLECTION_DISPATCH_ENTRY,
                                   COLLECTION_DISPATCH_RETURN,
                                   CONTACT_COMPLETION_EXIT)


RECORD = 0xFF6000
SAFE_RETURN = 0x1B65BE
TARGET = 0x1AFE1C


def fixture(*, blocked=0, ready=0, armed=0, record=RECORD, stack=0xFFEC00,
            incoming_x=False, d0=0xABCD1234, d1=0x13572468):
    """Park a real table dispatch before type 7E; vary only owned guard RAM."""
    rom = oracle.read_rom()
    assert int.from_bytes(rom[0x1CBE + 4 * 0x7E:0x1CBE + 4 * 0x7E + 4], 'big') & 0xFFFFFF == TARGET
    machine = oracle.cold_fixture(0x1B5266, pc_entry=COLLECTION_DISPATCH_ENTRY,
                                  incoming_x=incoming_x)
    try:
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        registers.update(a1=record, a7=stack, d0=d0, d1=d1, d2=0x98764321,
                         d7=0x76543210, a3=0x0012A3B4)
        writes = [(record + i, 0xA5) for i in range(66)]
        writes += [item for i in range(-16, 152) for item in oracle.write_long(stack + 4 * i, SAFE_RETURN)]
        writes += [(record, 0x7E), (0xFFF0E7, blocked), (0xFFF07E, ready),
                   (0xFFF114, armed), (0xFFF0F5, 0x35)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=writes, registers=registers)
        return machine.snapshot()
    finally:
        machine.close()


def qualify(state, candidate, **kwargs):
    return oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY, candidate=candidate,
                                 expected_return=CONTACT_COMPLETION_EXIT,
                                 future_instructions=150, include_raw=True, **kwargs)


@pytest.mark.parametrize('values', [
    {'blocked': 1, 'ready': 0, 'armed': 0},
    {'blocked': 0, 'ready': 0, 'armed': 0},
    {'blocked': 0, 'ready': 0xFF, 'armed': 0xFF},
])
@pytest.mark.parametrize('incoming_x', [False, True])
def test_type7e_finite_dispatch_exits_match_original_future_and_fresh(values, incoming_x):
    state = fixture(incoming_x=incoming_x, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('values', [
    {'blocked': 0x80, 'ready': 0xFF, 'armed': 0xA5},
    {'blocked': 0, 'ready': 0, 'armed': 0xA5},
    {'blocked': 0, 'ready': 1, 'armed': 0x80},
])
@pytest.mark.parametrize('stack,d0,d1', [
    (0xFFE000, 0xFFFFFFFF, 0x80000000),
    (0xFFEA00, 0x00000000, 0x0000FFFF),
])
def test_type7e_live_register_stack_and_guard_priority(values, stack, d0, d1):
    state = fixture(stack=stack, d0=d0, d1=d1, incoming_x=True, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type7e_mutants_diverge(mutant):
    state = fixture(blocked=0, ready=0, armed=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle-mutant-' + mutant, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type7e_progress_handoff_falls_back_as_one_untouched_dispatch():
    state = fixture(blocked=0, ready=0xFF, armed=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] == 1
    assert actual.stats['fallback_reasons'] == {
        'unsupported domain: type7E progress/stream handoff': 1}


def test_type7e_alias_refuses_before_dispatch_commit():
    # The record span covers FFF114, the owned armed byte; do not collapse it.
    state = fixture(record=0xFFF100, blocked=0, ready=0, armed=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['fallbacks'] == 1


def test_type7e_deadline_refuses_without_partial_dispatch():
    state = fixture(blocked=1)
    original = oracle.Machine(oracle.read_rom())
    try:
        original.restore(state); original.gates([COLLECTION_DISPATCH_ENTRY])
        assert original.run(instructions=1) == 'gate'
        original.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
        assert original.run(instructions=1) == 'limit'
        expected = oracle.observable(original)
    finally:
        original.close()
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = oracle.Candidate('lifecycle'); candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        assert not candidate.on_gate(machine, machine.info['tick'] + 1)
        assert candidate.stats['fallback_reasons'] == {'scheduler admission': 1}
        assert oracle.observable(machine) == expected
    finally:
        machine.close()


def test_type7e_retained_eligible_fixture_classes_are_present():
    report = Path('artifacts/contact-next-frontier/census4/report.json')
    if not report.exists():
        pytest.skip('optional local census evidence is absent')
    import json
    data = json.loads(report.read_text())
    assert data['counts']['1AFE1C:not-ready'] == 161
    assert data['counts']['1AFE1C:already-armed'] == 6
    assert data['counts']['1AFE1C:low-progress'] == 2


def _recorded_callback_as_dispatch_entry(path):
    """Rewind a parked recorded callback one JSR frame to its real parent."""
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(path.read_bytes())
        machine.gates([TARGET])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1, last_pc=TARGET, writes=(),
                              registers={'a7': registers['a7'] + 4,
                                         'pc': COLLECTION_DISPATCH_ENTRY})
        return machine.snapshot()
    finally:
        machine.close()


def test_type7e_all_retained_eligible_recorded_fixtures_qualify():
    root = Path('artifacts/contact-next-frontier/census4')
    if not root.exists():
        pytest.skip('optional local census evidence is absent')
    paths = [*(root.glob('1AFE1C-not-ready-*.state')),
             *(root.glob('1AFE1C-already-armed-*.state'))]
    assert len(paths) == 6
    for path in paths:
        state = _recorded_callback_as_dispatch_entry(path)
        expected = qualify(state, None)
        actual = qualify(state, 'lifecycle')
        assert actual.outer == expected.outer
        assert actual.future == expected.future
        assert actual.stats['collection_dispatch_hits'] == 1
        assert actual.stats['fallbacks'] == 0
        assert oracle.fresh_process_future(actual.outer_state) == actual.future
