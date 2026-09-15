"""Original-ROM qualification of Type20's secondary-pool relocation callback."""
import pytest
import oracle_witness as oracle
from test_contact_family import family_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


def type20_fixture(*, slots=0):
    # The table kind is 0x36; the recorded 0x20 value is record flag byte +6.
    state = family_fixture(0x1AF516, kind=0x36)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        machine.gates([machine.info['pc']])
        assert machine.run(instructions=1) == 'gate'
        writes = [(0xFF84B2 + 66 * index, 1) for index in range(slots)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=machine.info['pc'], writes=writes,
                              registers=machine.registers())
        return machine.snapshot()


@pytest.mark.parametrize('slots', (0, 3, 6))
def test_type20_dispatch_relocation_matches_original_outer_future_and_fresh(slots, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF516, 0x36)
    state = type20_fixture(slots=slots)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type20_dispatch_mutants_diverge(monkeypatch, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF516, 0x36)
    state = type20_fixture(slots=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle-mutant-' + mutant, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type20_relocation_is_owned_inside_the_complete_contact_scan(monkeypatch):
    from aladdin_sega import boundary
    original = boundary.begin_contact_collection_relocation_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_collection_relocation_dispatch', observed)
    state = scan_fixture(kind=0x36)
    expected = oracle.execute_region(state, entry=SCAN_ENTRY, candidate=None,
                                     expected_return=SCAN_EXIT, include_raw=True)
    actual = oracle.execute_region(state, entry=SCAN_ENTRY, candidate='lifecycle',
                                   expected_return=SCAN_EXIT, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['contact_scan_hits'] == 1
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] == 0
    assert calls == 1
