"""Original-ROM qualification of the finite Type-55 distance guard."""
import pytest
import oracle_witness as oracle
from aladdin_sega.game.objects import contact as game
from test_contact_family import family_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


@pytest.mark.parametrize('previous', (0, 75, 76, 88, 89, 100, 65535))
@pytest.mark.parametrize('incoming_x', (False, True))
def test_type55_distance_return_branches(previous, incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF590, 0x55)
    state = family_fixture(0x1AF590, previous=previous, object_y=100,
                           origin_x=0, flags=0x10, incoming_x=incoming_x)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('previous', (77, 82, 87))
def test_type55_transition_domain_declines_without_writes(previous, monkeypatch):
    from aladdin_sega import boundary
    monkeypatch.setitem(TARGET_KINDS, 0x1AF590, 0x55)
    state = family_fixture(0x1AF590, previous=previous, object_y=100, origin_x=0)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); before = machine.snapshot()
        with pytest.raises(boundary.UnsupportedCandidate, match='transition arm'):
            boundary.begin_contact_family_type55(machine, machine.registers())
        assert machine.snapshot() == before


@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type55_mutants_diverge(monkeypatch, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF590, 0x55)
    state = family_fixture(0x1AF590, previous=100, object_y=100, origin_x=0)
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        # The generic first-write mutation hits a temporary dispatcher slot
        # which the composed completion overwrites. Mutate the real result.
        from dataclasses import replace
        from aladdin_sega import boundary
        original = boundary.begin_contact_family_type55
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert (0xFFF0F5, 0xFF) in plan.writes
            return replace(plan, writes=tuple((at, value ^ 1 if at == 0xFFF0F5 else value)
                                              for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type55', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


# --- FFF0BE != 0 arms --------------------------------------------------------
#
# When FFF0BE != 0 the ROM tests FFF0C0 before the bit-4/distance guard:
# FFF0C0 == 0 takes a direct flag return through 1AE6B4 (the record's flag
# byte is never read); FFF0C0 != 0 falls into the very same guard two
# instructions later, with the bit-4/distance domain boundary unchanged.


@pytest.mark.parametrize('previous', (0, 75, 76, 88, 89, 100, 65535))
@pytest.mark.parametrize('incoming_x', (False, True))
def test_type55_selected_guard_distance_return_branches(previous, incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF590, 0x55)
    state = family_fixture(0x1AF590, previous=previous, object_y=100,
                           origin_x=0, flags=0x10, incoming_x=incoming_x,
                           be=1, c0=0xFF)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('flags', (0x00, 0x10))
@pytest.mark.parametrize('incoming_x', (False, True))
def test_type55_direct_return_branches(flags, incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF590, 0x55)
    state = family_fixture(0x1AF590, previous=100, object_y=100, origin_x=0,
                           flags=flags, incoming_x=incoming_x, be=1, c0=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('previous', (77, 82, 87))
def test_type55_selected_guard_transition_domain_declines_without_writes(previous, monkeypatch):
    from aladdin_sega import boundary
    monkeypatch.setitem(TARGET_KINDS, 0x1AF590, 0x55)
    state = family_fixture(0x1AF590, previous=previous, object_y=100, origin_x=0,
                           flags=0x10, be=1, c0=0xFF)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); before = machine.snapshot()
        with pytest.raises(boundary.UnsupportedCandidate, match='transition arm'):
            boundary.begin_contact_family_type55(machine, machine.registers())
        assert machine.snapshot() == before


def test_type55_selected_guard_bit4_unset_declines_without_writes(monkeypatch):
    from aladdin_sega import boundary
    monkeypatch.setitem(TARGET_KINDS, 0x1AF590, 0x55)
    state = family_fixture(0x1AF590, previous=100, object_y=100, origin_x=0,
                           flags=0x00, be=1, c0=0xFF)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); before = machine.snapshot()
        with pytest.raises(boundary.UnsupportedCandidate, match='guard arm is not active'):
            boundary.begin_contact_family_type55(machine, machine.registers())
        assert machine.snapshot() == before


@pytest.mark.parametrize('arm', ('selected-guard', 'direct'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type55_selected_and_direct_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF590, 0x55)
    state = family_fixture(0x1AF590, previous=100, object_y=100, origin_x=0,
                           flags=0x10, be=1, c0=0xFF if arm == 'selected-guard' else 0)
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        from aladdin_sega import boundary
        original = boundary.begin_contact_family_type55
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert (0xFFF0F5, 0xFF) in plan.writes
            return replace(plan, writes=tuple((at, value ^ 1 if at == 0xFFF0F5 else value)
                                              for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type55', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


# --- semantic layer -----------------------------------------------------------


def test_type55_semantics_select_every_arm_from_a_reader():
    def reader(values):
        return lambda address, size: values.get(address, 0)
    record = 0xFF6000
    base = {record + 4: 100, record + 6: 0x10, 0xFF7DF8: 0, 0xFF7DFC: 100}
    assert game.contact_type55_guard(reader({**base, 0xFFF0BE: 1, 0xFFF0C0: 0}), record) == ('direct', {'selector': 1})
    arm, facts = game.contact_type55_guard(reader(base), record)
    assert (arm, facts['delta'], facts['distance'], facts['borrowed']) == ('guard', 82, 18, False)
    arm, facts = game.contact_type55_guard(reader({**base, 0xFF7DFC: 0}), record)
    assert (arm, facts['distance'], facts['borrowed'], facts['difference']) == ('guard', 82, True, (-82) & 0xFFFF)
    assert game.contact_type55_guard(reader({**base, 0xFF7DFC: 84}), record)[0] == 'transition'
    assert game.contact_type55_guard(reader({**base, record + 6: 0}), record)[0] == 'inactive'
    assert game.contact_type55_return() == [(0xFFF0F5, 0xFF)]


# --- parent ownership ---------------------------------------------------------


def test_type55_is_owned_inside_the_complete_contact_scan(monkeypatch):
    from aladdin_sega import boundary
    original = boundary.begin_contact_family_type55_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type55_dispatch', observed)
    state = scan_fixture(kind=0x55)
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
