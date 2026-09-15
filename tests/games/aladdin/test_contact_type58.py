"""Original-ROM qualification of the bounded Type-58 distance guard.

1AF5F0 is structurally the same dispatch as Type-55 (the same FFF0BE
selector, the same record-plus-6 bit-4 activity test, the same shared
1AE6B4 tail) but its own guard adds 2 to the delta rather than subtracting
18, its limit is 0xC rather than 6, and -- unlike Type-55 -- both sides of
the comparison are observed on the recorded history and recovered here: a
guard pass rewrites FF7DFC and returns locally at 1AF636, a guard fail
publishes the same FFF0F5 tail flag as the direct and inactive arms.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega.game.objects import contact as game
from test_contact_family import family_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


# object_y=100, origin_x=0 puts delta at 100 - 0 + 2 = 102.

PASS_PREVIOUS = (91, 95, 101, 102, 105, 113)  # distance 11,7,1,0,3,11 (mixed borrow)
FAIL_PREVIOUS = (0, 50, 90, 114, 115, 65535)  # distance 102,52,12,12,13,65433


@pytest.mark.parametrize('previous', PASS_PREVIOUS)
@pytest.mark.parametrize('incoming_x', (False, True))
def test_type58_distance_pass_branches(previous, incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    state = family_fixture(0x1AF5F0, previous=previous, object_y=100,
                           origin_x=0, flags=0x10, incoming_x=incoming_x)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('previous', FAIL_PREVIOUS)
@pytest.mark.parametrize('incoming_x', (False, True))
def test_type58_distance_fail_branches(previous, incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    state = family_fixture(0x1AF5F0, previous=previous, object_y=100,
                           origin_x=0, flags=0x10, incoming_x=incoming_x)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type58_pass_mutants_diverge(monkeypatch, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    state = family_fixture(0x1AF5F0, previous=101, object_y=100, origin_x=0)
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        from aladdin_sega import boundary
        original = boundary.begin_contact_family_type58
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert (0xFF7DFC, plan.writes[0][1]) in plan.writes or plan.writes[0][0] == 0xFF7DFC
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type58', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type58_fail_mutants_diverge(monkeypatch, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    state = family_fixture(0x1AF5F0, previous=0, object_y=100, origin_x=0)
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        from aladdin_sega import boundary
        original = boundary.begin_contact_family_type58
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert (0xFFF0F5, 0xFF) in plan.writes
            return replace(plan, writes=tuple((at, value ^ 1 if at == 0xFFF0F5 else value)
                                              for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type58', wrong)
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


@pytest.mark.parametrize('previous', (91, 102, 113))
def test_type58_selected_guard_pass_branches(previous, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    state = family_fixture(0x1AF5F0, previous=previous, object_y=100,
                           origin_x=0, flags=0x10, be=1, c0=0xFF)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('previous', (0, 90, 114))
def test_type58_selected_guard_fail_branches(previous, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    state = family_fixture(0x1AF5F0, previous=previous, object_y=100,
                           origin_x=0, flags=0x10, be=1, c0=0xFF)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('flags', (0x00, 0x10))
@pytest.mark.parametrize('incoming_x', (False, True))
def test_type58_direct_return_branches(flags, incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    state = family_fixture(0x1AF5F0, previous=100, object_y=100, origin_x=0,
                           flags=flags, incoming_x=incoming_x, be=1, c0=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_type58_selected_guard_bit4_unset_declines_without_writes(monkeypatch):
    from aladdin_sega import boundary
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    state = family_fixture(0x1AF5F0, previous=100, object_y=100, origin_x=0,
                           flags=0x00, be=1, c0=0xFF)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); before = machine.snapshot()
        with pytest.raises(boundary.UnsupportedCandidate, match='guard arm is not active'):
            boundary.begin_contact_family_type58(machine, machine.registers())
        assert machine.snapshot() == before


@pytest.mark.parametrize('arm', ('selected-guard-pass', 'selected-guard-fail', 'direct'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type58_selected_and_direct_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF5F0, 0x58)
    if arm == 'direct':
        state = family_fixture(0x1AF5F0, previous=100, object_y=100, origin_x=0,
                               flags=0x10, be=1, c0=0)
        written_address = 0xFFF0F5
    elif arm == 'selected-guard-pass':
        state = family_fixture(0x1AF5F0, previous=101, object_y=100, origin_x=0,
                               flags=0x10, be=1, c0=0xFF)
        written_address = 0xFF7DFC
    else:
        state = family_fixture(0x1AF5F0, previous=0, object_y=100, origin_x=0,
                               flags=0x10, be=1, c0=0xFF)
        written_address = 0xFFF0F5
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        from aladdin_sega import boundary
        original = boundary.begin_contact_family_type58
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == written_address for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type58', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


# --- semantic layer -----------------------------------------------------------


def test_type58_semantics_select_every_arm_from_a_reader():
    def reader(values):
        return lambda address, size: values.get(address, 0)
    record = 0xFF6000
    # delta = (record+4) - FF7DF8 + 2 = 100 - 0 + 2 = 102 throughout.
    base = {record + 4: 100, record + 6: 0x10, 0xFF7DF8: 0, 0xFF7DFC: 100}
    assert game.contact_type58_guard(reader({**base, 0xFFF0BE: 1, 0xFFF0C0: 0}), record) == ('direct', {'selector': 1})
    # previous=100 < delta=102: borrowed, difference 2 stays under the 0xC limit.
    arm, facts = game.contact_type58_guard(reader(base), record)
    assert (arm, facts['delta'], facts['distance'], facts['borrowed']) == ('guard_pass', 102, 2, True)
    # previous=113 >= delta=102: no borrow, distance 11 still under the limit.
    arm, facts = game.contact_type58_guard(reader({**base, 0xFF7DFC: 113}), record)
    assert (arm, facts['delta'], facts['distance'], facts['borrowed']) == ('guard_pass', 102, 11, False)
    # previous=0: borrowed, distance 102 clears the 0xC limit.
    arm, facts = game.contact_type58_guard(reader({**base, 0xFF7DFC: 0}), record)
    assert (arm, facts['delta'], facts['distance'], facts['borrowed']) == ('guard_fail', 102, 102, True)
    # previous=115: no borrow, distance 13 clears the 0xC limit.
    arm, facts = game.contact_type58_guard(reader({**base, 0xFF7DFC: 115}), record)
    assert (arm, facts['distance'], facts['borrowed']) == ('guard_fail', 13, False)
    assert game.contact_type58_guard(reader({**base, record + 6: 0}), record)[0] == 'inactive'
    assert game.contact_type58_fail() == [(0xFFF0F5, 0xFF)]
    assert game.contact_type58_pass(0x0165) == [(0xFF7DFC, 0x01), (0xFF7DFD, 0x65)]


# --- parent ownership ---------------------------------------------------------


def test_type58_is_owned_inside_the_complete_contact_scan(monkeypatch):
    from aladdin_sega import boundary
    original = boundary.begin_contact_family_type58_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type58_dispatch', observed)
    state = scan_fixture(kind=0x58)
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
