"""Original-ROM qualification of the Type-6E gate cascade and distance guard.

1AFB36 is reached by six adjacent collection-dispatch kinds (0x6E-0x73) that
share this one entry; the record's own kind byte plays no part in the body.
A new FFF0E7 gate and FF7E5A sign test precede the familiar FFF0BE/FFF0C0
family selector and record-plus-6 bit-4 activity test (the same shape as
Type-55/58/74's own guard); only past those does the dual-axis distance
guard run (record+2 against FF7DF6 into a running FF7DFA word, limit 0xC,
same borrow/negate shape as the sibling guards).  A guard pass always
republishes the Y delta (record+4 against FF7DF8, plus 0x10) into FF7DFC,
then keys a small state machine off FFF103: nonzero lands on the immediate
FFF0D7/FFF0D0/FFF103 tail, zero also fires the 1AFBA6 reinitialisation
block first.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega import boundary
from aladdin_sega.game.objects import contact as game
from test_contact_family import family_fixture, type6e_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


# object_x=100, origin_x2=0 (the default) puts the X delta at 100 throughout;
# FF7DFA ("motion") is the running previous word the guard compares it
# against, limit 0xC.

PASS_MOTION = (89, 95, 100, 101, 105, 111)   # distance 11,5,0,1,5,11 (mixed borrow)
FAIL_MOTION = (0, 50, 88, 112, 113, 65535)   # distance 100,50,12,12,13,65435


def _assert_matches_oracle(state):
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('motion', PASS_MOTION)
@pytest.mark.parametrize('fff103', (0, 1))
@pytest.mark.parametrize('be_c0', ((0, 0xFF), (1, 1)))
def test_type6e_distance_pass_branches(motion, fff103, be_c0, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AFB36, 0x6E)
    be, c0 = be_c0
    state = type6e_fixture(motion=motion, fff103=fff103, be=be, c0=c0)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('motion', FAIL_MOTION)
@pytest.mark.parametrize('be_c0', ((0, 0xFF), (1, 1)))
def test_type6e_distance_fail_branches(motion, be_c0, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AFB36, 0x6E)
    be, c0 = be_c0
    state = type6e_fixture(motion=motion, be=be, c0=c0)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('kind', (0x6E, 0x6F, 0x70, 0x71, 0x72, 0x73))
def test_type6e_shares_one_entry_across_every_kind(kind, monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AFB36, kind)
    state = type6e_fixture(kind=kind, motion=89)
    _assert_matches_oracle(state)


def test_type6e_inactive_gate(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AFB36, 0x6E)
    state = type6e_fixture(blocked=1)
    _assert_matches_oracle(state)


def test_type6e_negative_state(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AFB36, 0x6E)
    state = type6e_fixture(vertical=0x8000)
    _assert_matches_oracle(state)


def test_type6e_direct_return(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AFB36, 0x6E)
    state = type6e_fixture(be=1, c0=0)
    _assert_matches_oracle(state)


def test_type6e_bit4_inactive(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AFB36, 0x6E)
    state = type6e_fixture(flags=0)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('arm', ('inactive', 'negative', 'direct', 'bit4_inactive',
                                 'guard_fail', 'guard_pass_immediate', 'guard_pass_reinit'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type6e_every_arm_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AFB36, 0x6E)
    if arm == 'inactive':
        state = type6e_fixture(blocked=1)
        written_address = None
    elif arm == 'negative':
        state = type6e_fixture(vertical=0x8000)
        written_address = 0xFFF0F5
    elif arm == 'direct':
        state = type6e_fixture(be=1, c0=0)
        written_address = 0xFFF0F5
    elif arm == 'bit4_inactive':
        state = type6e_fixture(flags=0)
        written_address = 0xFFF0F5
    elif arm == 'guard_fail':
        state = type6e_fixture(motion=0)
        written_address = 0xFFF0F5
    elif arm == 'guard_pass_immediate':
        state = type6e_fixture(motion=89, fff103=1)
        written_address = 0xFF7DFA
    else:
        state = type6e_fixture(motion=89, fff103=0)
        written_address = 0xFF7E60
    if arm == 'inactive' and mutant == 'result':
        pytest.skip('the inactive arm publishes no writes to invert')
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        original = boundary.begin_contact_family_type6e
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == written_address for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type6e', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


# --- parent ownership ---------------------------------------------------------


@pytest.mark.parametrize('kind', (0x6E, 0x73))
def test_type6e_is_owned_inside_the_complete_contact_scan(monkeypatch, kind):
    original = boundary.begin_contact_family_type6e_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type6e_dispatch', observed)
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


# --- semantic layer -----------------------------------------------------------


def test_type6e_semantics_select_every_arm_from_a_reader():
    def reader(values):
        return lambda address, size: values.get(address, 0)
    record = 0xFF6000
    # delta = record+2(100) - FF7DF6(0) = 100 throughout.
    base = {record + 2: 100, 0xFF7DF6: 0, record + 6: 0x10, record + 4: 108,
           0xFF7DF8: 0, 0xFFF103: 1}
    assert game.contact_type6e_guard(reader({**base, 0xFFF0E7: 1}), record)[0] == 'inactive'
    assert game.contact_type6e_guard(reader({**base, 0xFF7E5A: 0x8000}), record)[0] == 'negative'
    assert game.contact_type6e_guard(reader({**base, 0xFFF0BE: 1, 0xFFF0C0: 0}), record)[0] == 'direct'
    assert game.contact_type6e_guard(reader({**base, record + 6: 0}), record)[0] == 'bit4_inactive'
    # previous(FF7DFA)=89 < delta=100: borrowed, distance 11 stays under the 0xC limit.
    arm, facts = game.contact_type6e_guard(reader({**base, 0xFF7DFA: 89}), record)
    assert (arm, facts['delta'], facts['distance'], facts['borrowed']) == ('guard_pass', 100, 11, True)
    # previous=111 >= delta=100: no borrow, distance 11 still under the limit.
    arm, facts = game.contact_type6e_guard(reader({**base, 0xFF7DFA: 111}), record)
    assert (arm, facts['delta'], facts['distance'], facts['borrowed']) == ('guard_pass', 100, 11, False)
    # previous=0: borrowed, distance 100 clears the 0xC limit.
    arm, facts = game.contact_type6e_guard(reader({**base, 0xFF7DFA: 0}), record)
    assert (arm, facts['distance'], facts['borrowed']) == ('guard_fail', 100, True)
    # previous=113: no borrow, distance 13 clears the 0xC limit.
    arm, facts = game.contact_type6e_guard(reader({**base, 0xFF7DFA: 113}), record)
    assert (arm, facts['distance'], facts['borrowed']) == ('guard_fail', 13, False)
    assert game.contact_type6e_fail() == [(0xFFF0F5, 0xFF)]

    # guard-pass writes: the X delta publishes as-is, the Y delta
    # (108 - 0 + 0x10 = 124 = 0x7C) always recomputes, and FFF103 keys the tail.
    read_immediate = reader({**base, 0xFF7DFA: 89, 0xFFF103: 1})
    writes, reinit = game.contact_type6e_pass(read_immediate, record, 100)
    assert reinit is False
    assert (0xFF7DFA, 0x00) in writes and (0xFF7DFB, 0x64) in writes
    assert (0xFF7DFC, 0x00) in writes and (0xFF7DFD, 0x7C) in writes
    assert (0xFFF0D7, 0xFF) in writes and (0xFFF0D0, 0xFF) in writes and (0xFFF103, 0x04) in writes
    assert (0xFF7E60, 0x00) not in [w for w in writes if w[0] == 0xFF7E60]

    read_reinit = reader({**base, 0xFF7DFA: 89, 0xFFF103: 0})
    writes, reinit = game.contact_type6e_pass(read_reinit, record, 100)
    assert reinit is True
    for pair in game.contact_type6e_reinit():
        assert pair in writes
    assert (0xFFF0D7, 0xFF) in writes and (0xFFF0D0, 0xFF) in writes and (0xFFF103, 0x04) in writes

    assert game.contact_type6e_reinit() == [
        (0xFF7E60, 0x00), (0xFF7E61, 0x12), (0xFF7E62, 0x19), (0xFF7E63, 0x64),
        (0xFF7E77, 0),
        (0xFF7DFE, 0x00), (0xFF7DFF, 0xB0),
        (0xFF7E00, 0x01), (0xFF7E01, 0x50),
        (0xFFF0B0, 0x00), (0xFFF0B1, 0x00),
        (0xFFF0CC, 0),
        (0xFF7E58, 0x00), (0xFF7E59, 0x00),
        (0xFF7E5A, 0x00), (0xFF7E5B, 0x00),
    ]


def test_type6e_declines_unaligned_record_or_stack():
    state = type6e_fixture(motion=89)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a1'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned type6e'):
            boundary.begin_contact_family_type6e(machine, registers)
