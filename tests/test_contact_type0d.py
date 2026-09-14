"""Original-ROM qualification of the unconditional-RTS dispatch stubs.

1AEB7A (kind 0x0D) and 1AEBFE (kind 0x14, and also reached by the kind
0x2B collection-dispatch slot) are each a single instruction: RTS, with no
gate, no write and no flag change (RTS never touches CCR).
"""
import pytest
import oracle_witness as oracle
from aladdin_sega import boundary
from test_contact_family import family_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


def _assert_matches_oracle(state):
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('target,kind,planner_name', [
    (0x1AEB7A, 0x0D, 'begin_contact_family_type0d'),
    (0x1AEBFE, 0x14, 'begin_contact_family_type14'),
    (0x1AEBFE, 0x2B, 'begin_contact_family_type14'),
])
def test_noop_stub_matches_original(monkeypatch, target, kind, planner_name):
    monkeypatch.setitem(TARGET_KINDS, target, kind)
    state = family_fixture(target, kind=kind)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('target,kind,planner_name,dispatch_name', [
    (0x1AEB7A, 0x0D, 'begin_contact_family_type0d', 'begin_contact_family_type0d_dispatch'),
    (0x1AEBFE, 0x14, 'begin_contact_family_type14', 'begin_contact_family_type14_dispatch'),
])
@pytest.mark.parametrize('mutant', ('continuation', 'timing'))
def test_noop_stub_mutants_diverge(monkeypatch, target, kind, planner_name, dispatch_name, mutant):
    # A 'result' mutant has no write to invert (the stub publishes none);
    # only the continuation and timing facets are checkable here.
    monkeypatch.setitem(TARGET_KINDS, target, kind)
    state = family_fixture(target, kind=kind)
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type0d_declines_unaligned_stack():
    state = family_fixture(0x1AEB7A, kind=0x0D)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned noop'):
            boundary.begin_contact_family_type0d(machine, registers)


def test_type14_declines_unaligned_stack():
    state = family_fixture(0x1AEBFE, kind=0x14)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned noop'):
            boundary.begin_contact_family_type14(machine, registers)


# --- parent ownership ---------------------------------------------------------


@pytest.mark.parametrize('target,kind,dispatch_name', [
    (0x1AEB7A, 0x0D, 'begin_contact_family_type0d_dispatch'),
    (0x1AEBFE, 0x14, 'begin_contact_family_type14_dispatch'),
    (0x1AEBFE, 0x2B, 'begin_contact_family_type14_dispatch'),
])
def test_noop_stub_is_owned_inside_the_complete_contact_scan(monkeypatch, target, kind, dispatch_name):
    original = getattr(boundary, dispatch_name)
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, dispatch_name, observed)
    state = scan_fixture(kind=kind)
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
