"""Original-ROM qualification of 1AFA84's distance guard, window/kind/state
gate and child spawn.

1AFA84 is reached by both the kind-0x74 and kind-0x75 collection-dispatch
slots.  It opens with the same FFF0BE/FFF0C0 family selector as Type-55/58's
own guard (but no bit-4 activity test), subtracts 0xB and bounds the result
to 0xA; a pass continues into a horizontal-window, kind and state gate, and
only when every one of those checks clears does the triggering record
retype itself to a used kind-0x75 marker and spawn a child from the fixed
1B7E7C template into the first free FF7F06 pool slot.  A kind-0x75 record
always fails the kind recheck, which is why the kind-0x75 collection-dispatch
slot that shares this entry never re-spawns.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega.game.objects import contact as game
from test_contact_family import family_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


TARGET = 0x1AFA84
# object_y=111, origin_x=0 puts delta at 111 - 0 - 0xB = 100 throughout.
DELTA_Y, DELTA_ORIGIN = 111, 0


@pytest.mark.parametrize('previous', (105, 95, 91, 109))  # distance 5,5,9,9 (mixed borrow)
@pytest.mark.parametrize('incoming_x', (False, True))
def test_type74_distance_pass_branches(previous, incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=previous, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=5000, player_x=6000, incoming_x=incoming_x)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('previous', (115, 85, 90, 110))  # distance 15,15,10,10 (mixed borrow)
@pytest.mark.parametrize('incoming_x', (False, True))
def test_type74_distance_fail_branches(previous, incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=previous, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           incoming_x=incoming_x)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('player_x', (210, 5000))
def test_type74_window_upper_fail_branches(player_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=105, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=200, player_x=player_x)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('player_x', (189, 0))
def test_type74_window_lower_fail_branches(player_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=105, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=200, player_x=player_x)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_type74_kind_mismatch_branch(monkeypatch):
    # A kind-0x75 record shares this same entry (both dispatch slots resolve
    # to 1AFA84) but always fails the kind==0x74 recheck.
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x75)
    state = family_fixture(TARGET, kind=0x75, previous=105, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=200, player_x=200)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_type74_state_gate_branch(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=105, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=200, player_x=200, active_d8=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('vertical', (0x8000, 0xFFFF, 0x7FFF))
def test_type74_negative_state_branch(vertical, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=105, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=200, player_x=200, vertical=vertical)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_type74_zero_state_branch(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=105, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=200, player_x=200, vertical=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('vertical', (1, 0x0800, 0x7FFF))
def test_type74_spawn_branches(vertical, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=105, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=200, player_x=200, vertical=vertical, active_d8=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


# --- FFF0BE != 0 arms --------------------------------------------------------
#
# When FFF0BE != 0 the ROM tests FFF0C0 before the distance guard: FFF0C0
# == 0 takes a direct flag return through 1AE6B4 (the record is never
# read); FFF0C0 != 0 falls into the very same guard two instructions later.


@pytest.mark.parametrize('previous', (105, 115))
def test_type74_selected_guard_branches(previous, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=previous, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           object_x=200, player_x=200, be=1, c0=0xFF)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('incoming_x', (False, True))
def test_type74_direct_return_branches(incoming_x, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    state = family_fixture(TARGET, previous=100, object_y=DELTA_Y, origin_x=DELTA_ORIGIN,
                           incoming_x=incoming_x, be=1, c0=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('arm', ('guard_fail', 'window_upper', 'kind_mismatch',
                                 'state_gate', 'negative_state', 'zero_state', 'spawn'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type74_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, TARGET, 0x74)
    kwargs = dict(previous=105, object_y=DELTA_Y, origin_x=DELTA_ORIGIN, object_x=200, player_x=200)
    written_address = 0xFF7DFC
    if arm == 'guard_fail':
        kwargs['previous'] = 115
        written_address = 0xFFF0F5
    elif arm == 'window_upper':
        kwargs['player_x'] = 5000
    elif arm == 'kind_mismatch':
        monkeypatch.setitem(TARGET_KINDS, TARGET, 0x75)
        kwargs['kind'] = 0x75
    elif arm == 'state_gate':
        kwargs['active_d8'] = 1
    elif arm == 'negative_state':
        kwargs['vertical'] = 0x8000
    elif arm == 'zero_state':
        kwargs['vertical'] = 0
    else:
        kwargs['vertical'] = 1
    state = family_fixture(TARGET, **kwargs)
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        from aladdin_sega import boundary
        original = boundary.begin_contact_family_type74
        def wrong(*args, **kwargs2):
            plan = original(*args, **kwargs2)
            assert any(at == written_address for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type74', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


# --- semantic layer -----------------------------------------------------------


def test_type74_semantics_select_every_arm_from_a_reader():
    def reader(values):
        return lambda address, size: values.get(address, 0)
    record = 0xFF6000
    # delta = (record+4) - FF7DF8 - 0xB = 111 - 0 - 11 = 100 throughout.
    base = {record + 4: 111, 0xFF7DF8: 0, 0xFF7DFC: 105}
    assert game.contact_type74_guard(reader({**base, 0xFFF0BE: 1, 0xFFF0C0: 0}), record) == ('direct', {'selector': 1})
    arm, facts = game.contact_type74_guard(reader(base), record)
    assert (arm, facts['delta'], facts['distance'], facts['borrowed']) == ('guard_pass', 100, 5, False)
    arm, facts = game.contact_type74_guard(reader({**base, 0xFF7DFC: 115}), record)
    assert (arm, facts['delta'], facts['distance'], facts['borrowed']) == ('guard_fail', 100, 15, False)
    assert game.contact_type74_fail() == [(0xFFF0F5, 0xFF)]
    assert game.contact_type74_pass(100) == [(0xFF7DFC, 0x00), (0xFF7DFD, 0x64)]

    target_base = {record + 2: 200, record: 0x74, 0xFFF0D8: 0, 0xFF7E5A: 1}
    assert game.contact_type74_target(reader(target_base), record, 5000)[0] == 'window_upper'
    assert game.contact_type74_target(reader(target_base), record, 0)[0] == 'window_lower'
    assert game.contact_type74_target(reader({**target_base, record: 0x75}), record, 200)[0] == 'kind_mismatch'
    assert game.contact_type74_target(reader({**target_base, 0xFFF0D8: 1}), record, 200)[0] == 'state_gate'
    assert game.contact_type74_target(reader({**target_base, 0xFF7E5A: 0x8000}), record, 200)[0] == 'negative_state'
    assert game.contact_type74_target(reader({**target_base, 0xFF7E5A: 0}), record, 200)[0] == 'zero_state'
    assert game.contact_type74_target(reader(target_base), record, 200)[0] == 'spawn'

    assert game.contact_type74_retype(record) == [
        (0xFFF0CC, 0), (0xFFF0B0, 0), (0xFFF0B1, 0),
        (record + 0xA, 0x00), (record + 0xB, 0x12), (record + 0xC, 0x0A), (record + 0xD, 0x42),
        (record + 0x36, 0), (record, 0x75)]
    assert game.contact_type74_position(0xFF7F06, 0x1234, 0x5678) == [
        (0xFF7F08, 0x12), (0xFF7F09, 0x34), (0xFF7F0A, 0x56), (0xFF7F0B, 0x78)]


# --- parent ownership ---------------------------------------------------------


@pytest.mark.parametrize('kind', (0x74, 0x75))
def test_type74_is_owned_inside_the_complete_contact_scan(monkeypatch, kind):
    from aladdin_sega import boundary
    original = boundary.begin_contact_family_type74_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type74_dispatch', observed)
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
