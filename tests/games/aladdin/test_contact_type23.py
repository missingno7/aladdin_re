"""Original-ROM qualification of the Type-23 self-retype and double spawn.

1AEECA gates on FFF0D8: clear, it returns at once with no writes. Active,
the triggering record retypes itself to a used kind-0x84 marker before
either spawn attempt, then seeks a child in the 20-slot FF7F06 pool (the
same pool and scan shape already proven for
``begin_contact_family_type74``'s own spawn); found, it is expanded from a
fixed template, given the triggering record's own position, and retyped a
second time to kind 0x3B with its own +0x20 long field overwritten. Only
then is a second child sought in the wider 24-slot FF7E82 pool (the pool
the contact scan itself walks); found, it is expanded from a different
fixed template and given the same position, with no further retype.
Either pool's own exhaustion abandons only what follows it -- a committed
primary spawn is never undone. Neither spawn is a native re-entry: both
reuse the exact 1AE262/1AE30A adapters already proven for
``begin_contact_family_type74``.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega import boundary
from test_contact_family import family_fixture, type23_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


def _assert_matches_oracle(state):
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_type23_inactive_gate(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEECA, 0x23)
    state = type23_fixture(active=0)
    _assert_matches_oracle(state)


def test_type23_active_finds_both_pools_at_index0(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEECA, 0x23)
    state = type23_fixture(active=1)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('occupy_primary,occupy_secondary', [
    ((0, 1), ()),           # primary found at local index 2
    ((), (0,)),             # secondary found at index 1
    ((0, 1), (0, 1)),       # both found past index 0
])
def test_type23_active_finds_a_later_index(monkeypatch, occupy_primary, occupy_secondary):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEECA, 0x23)
    state = type23_fixture(active=1, occupy_primary=occupy_primary, occupy_secondary=occupy_secondary)
    _assert_matches_oracle(state)


def test_type23_active_primary_pool_exhausted(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEECA, 0x23)
    state = type23_fixture(active=1, occupy_primary=range(20))
    _assert_matches_oracle(state)


def test_type23_active_secondary_pool_exhausted(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEECA, 0x23)
    # Leave secondary index 2 (== primary's own index 0, FF7F06) free so the
    # primary spawn succeeds there first; by the time the secondary scan
    # runs, that slot's own override has filled it too, and every other
    # secondary slot is occupied here from the start.
    state = type23_fixture(active=1, occupy_secondary=[i for i in range(24) if i != 2])
    _assert_matches_oracle(state)


@pytest.mark.parametrize('arm', ('inactive', 'primary_exhausted', 'secondary_exhausted', 'both_found'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type23_every_arm_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEECA, 0x23)
    if arm == 'inactive':
        state = type23_fixture(active=0)
        written_address = None
    elif arm == 'primary_exhausted':
        state = type23_fixture(active=1, occupy_primary=range(20))
        written_address = 0xFF6000  # the self-retype's own kind byte
    elif arm == 'secondary_exhausted':
        state = type23_fixture(active=1, occupy_secondary=[i for i in range(24) if i != 2])
        written_address = 0xFF7F06  # the primary spawn's own retyped slot
    else:
        state = type23_fixture(active=1)
        written_address = 0xFF7E82  # the secondary spawn's own slot
    if arm == 'inactive' and mutant == 'result':
        pytest.skip('the inactive arm publishes no writes to invert')
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        original = boundary.begin_contact_family_type23
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == written_address for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type23', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


# --- parent ownership ---------------------------------------------------------


def test_type23_is_owned_inside_the_complete_contact_scan(monkeypatch):
    original = boundary.begin_contact_family_type23_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type23_dispatch', observed)
    state = scan_fixture(kind=0x23)
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


def test_type23_declines_unaligned_stack():
    state = type23_fixture(active=1)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned type23'):
            boundary.begin_contact_family_type23(machine, registers)
