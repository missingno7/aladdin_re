"""Original-ROM qualification of the Type-78/7A FFF0D8 gate, window guard
and shared-CONTACT_ENTRY BSR.

1AEBDC gates on FFF0D8: clear, it falls straight through into a BSR of the
shared 1AE4F8 contact root.  Active, a +/-8 window first compares D0 (the
caller's own distance/threshold register) against the triggering record's
own record+2 field: outside ``[record+2 - 8, record+2 + 8)`` it returns at
once with no writes and no call; inside it also BSRs 1AE4F8.  Both kind
0x78 and kind 0x7A collection-dispatch slots share this one entry -- the
ROM's own dispatch table routes both to 0x1AEBDC.  The nested call is
composed exactly as ``begin_contact_dispatch``/``begin_contact_dispatch_sound``
compose type 7B's own BSR: through the already-proven ``begin_contact``
(RAM-only early/reaction/reset arms) or ``begin_contact_sound`` (the
command-31 seam); only the gate/window prefix and its call composition,
plus the extra local RTS that unwinds our own frame, are new.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega import boundary
from test_contact_family import family_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


def type78_fixture(*, active_d8=1, window=100, object_x=100, sound=0, **kwargs):
    """Construct a valid Type-78 collection record over the original ROM.

    ``family_fixture`` seeds the record's own FFF0D8 gate (``active_d8``)
    and record+2 (``object_x``); ``window`` sets D0's low word, the value
    the +/-8 window (when the gate is active) compares against ``object_x``.
    """
    return family_fixture(0x1AEBDC, active_d8=active_d8, object_x=object_x,
                          initial_d0=0xABCD0000 | (window & 0xFFFF),
                          sound=sound, **kwargs)


def _assert_matches_oracle(state):
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('kind', (0x78, 0x7A))
def test_type78_gate_clear_calls_contact_root(monkeypatch, kind):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, kind)
    state = type78_fixture(active_d8=0, kind=kind)
    _assert_matches_oracle(state)


def test_type78_window_upper_fail_returns_without_a_call(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    state = type78_fixture(active_d8=1, object_x=100, window=1000)
    _assert_matches_oracle(state)


def test_type78_window_lower_fail_returns_without_a_call(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    state = type78_fixture(active_d8=1, object_x=1000, window=100)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('window', (92, 100, 107))
def test_type78_window_pass_calls_contact_root(monkeypatch, window):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    state = type78_fixture(active_d8=1, object_x=100, window=window)
    _assert_matches_oracle(state)


def test_type78_window_boundary_is_exact(monkeypatch):
    """record+2=100: window is [92, 108).  99 fails low, 92 passes low;
    107 passes high, 108 fails high -- the same edges the ROM's own two
    CMP/Bcc pairs draw."""
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    for window, arm in ((91, 'fail'), (92, 'pass'), (107, 'pass'), (108, 'fail')):
        state = type78_fixture(active_d8=1, object_x=100, window=window)
        _assert_matches_oracle(state)


def test_type78_sound_arm_gate_clear_matches_original(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    state = type78_fixture(active_d8=0, sound=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type78_sound_arm_window_pass_matches_original(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    state = type78_fixture(active_d8=1, object_x=100, window=100, sound=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type78_sound_arm_declines_a_window_fail(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    state = type78_fixture(active_d8=1, object_x=100, window=1000, sound=1)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        machine.gates([boundary.COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        with pytest.raises(boundary.UnsupportedCandidate, match='outside the window pass'):
            boundary.begin_contact_family_type78_sound(machine, registers)


@pytest.mark.parametrize('arm', ('gate_clear', 'window_upper_fail', 'window_lower_fail', 'window_pass'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type78_every_arm_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    if arm == 'gate_clear':
        state = type78_fixture(active_d8=0)
        written_address = 0xFFF0CC
    elif arm == 'window_upper_fail':
        state = type78_fixture(active_d8=1, object_x=100, window=1000)
        written_address = None
    elif arm == 'window_lower_fail':
        state = type78_fixture(active_d8=1, object_x=1000, window=100)
        written_address = None
    else:
        state = type78_fixture(active_d8=1, object_x=100, window=100)
        written_address = 0xFFF0CC
    if written_address is None and mutant == 'result':
        pytest.skip('this arm publishes no writes to invert')
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        original = boundary.begin_contact_family_type78
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == written_address for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type78', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type78_declines_unaligned_stack(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEBDC, 0x78)
    state = type78_fixture(active_d8=1)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned type78'):
            boundary.begin_contact_family_type78(machine, registers)


# --- parent ownership ---------------------------------------------------------


def test_type78_is_owned_inside_the_complete_contact_scan(monkeypatch):
    original = boundary.begin_contact_family_type78_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type78_dispatch', observed)
    state = scan_fixture(kind=0x78)
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


def test_type78_is_owned_inside_the_complete_contact_scan_kind_7a(monkeypatch):
    original = boundary.begin_contact_family_type78_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type78_dispatch', observed)
    state = scan_fixture(kind=0x7A)
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
