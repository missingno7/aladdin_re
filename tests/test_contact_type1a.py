"""Original-ROM qualification of the Type-1A pair-release and re-template.

1AE9E0 gates on FFF0D8: clear, it returns at once with no writes. Active, it
runs the exact external 1ABE6E pair-release on the triggering record itself
-- its own type byte and attached buffer, and if its own record+62 link is
set, that linked record's type byte and buffer too -- then re-expands the
fixed 19-byte template at 1B7940 back into the triggering record through the
exact 1AE30A adapter already proven for ``initialize_object``/
``finish_object``. Both internal calls are plain 68000 subroutines this
boundary already owns (``_clear_objects``, ``_initialize_object_effects``),
not a native re-entry, so this is one RAM-only leaf despite its two BSRs.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega import boundary
from test_contact_family import family_fixture, type1a_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


def _assert_matches_oracle(state):
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_type1a_inactive_gate(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AE9E0, 0x1A)
    state = type1a_fixture(active=0)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('own_buffer', (0, 0xFFD000))
@pytest.mark.parametrize('linked', (0, 0xFFD200))
@pytest.mark.parametrize('linked_buffer', (0, 0xFFD100))
def test_type1a_active_owns_every_buffer_and_link_combination(monkeypatch, own_buffer, linked, linked_buffer):
    monkeypatch.setitem(TARGET_KINDS, 0x1AE9E0, 0x1A)
    state = type1a_fixture(active=1, own_buffer=own_buffer, linked=linked, linked_buffer=linked_buffer)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('arm', ('inactive', 'active'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type1a_every_arm_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AE9E0, 0x1A)
    if arm == 'inactive':
        state = type1a_fixture(active=0)
        written_address = None
    else:
        state = type1a_fixture(active=1, own_buffer=0xFFD000, linked=0xFFD200, linked_buffer=0xFFD100)
        written_address = 0xFFF10E
    if arm == 'inactive' and mutant == 'result':
        pytest.skip('the inactive arm publishes no writes to invert')
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        original = boundary.begin_contact_family_type1a
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == written_address for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type1a', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


# --- parent ownership ---------------------------------------------------------


def test_type1a_is_owned_inside_the_complete_contact_scan(monkeypatch):
    original = boundary.begin_contact_family_type1a_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type1a_dispatch', observed)
    state = scan_fixture(kind=0x1A)
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


def test_type1a_declines_unaligned_stack():
    state = type1a_fixture(active=1)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned type1a'):
            boundary.begin_contact_family_type1a(machine, registers)
