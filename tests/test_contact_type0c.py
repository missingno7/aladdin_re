"""Original-ROM qualification of the Type-0C own-buffer release and re-template.

1AE9A8 gates on FFF0D8: clear, it returns at once with no writes. Active, it
releases the triggering record's own attached buffer if any
(``_clear_objects`` with ``pair=False``, the same RAM-domain adapter
already proven for ``clear_auxiliary_buffer``) then re-expands the fixed
19-byte template at 1B7CC4 back into the same record through the exact
1AE30A adapter already proven for ``initialize_object`` /
``finish_object`` / ``begin_contact_family_type1a``. Same overall shape as
Type-1A but simpler: no linked record at all.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega import boundary
from test_contact_family import family_fixture, type0c_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


def _assert_matches_oracle(state):
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_type0c_inactive_gate(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AE9A8, 0x0C)
    state = type0c_fixture(active=0)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('own_buffer', (0, 0xFFD000))
def test_type0c_active_with_and_without_buffer(monkeypatch, own_buffer):
    monkeypatch.setitem(TARGET_KINDS, 0x1AE9A8, 0x0C)
    state = type0c_fixture(active=1, own_buffer=own_buffer)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('arm', ('inactive', 'active'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type0c_every_arm_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AE9A8, 0x0C)
    if arm == 'inactive':
        state = type0c_fixture(active=0)
        written_address = None
    else:
        state = type0c_fixture(active=1, own_buffer=0xFFD000)
        written_address = 0xFF6000  # the record's own retemplated kind byte
    if arm == 'inactive' and mutant == 'result':
        pytest.skip('the inactive arm publishes no writes to invert')
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        original = boundary.begin_contact_family_type0c
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == written_address for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type0c', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type0c_declines_unaligned_stack():
    state = type0c_fixture(active=1)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned type0c'):
            boundary.begin_contact_family_type0c(machine, registers)


# --- parent ownership ---------------------------------------------------------


def test_type0c_is_owned_inside_the_complete_contact_scan(monkeypatch):
    original = boundary.begin_contact_family_type0c_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type0c_dispatch', observed)
    state = scan_fixture(kind=0x0C)
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
