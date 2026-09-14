"""Original-ROM qualification of the finite Type-55 distance guard."""
import pytest
import oracle_witness as oracle
from test_contact_family import family_fixture, TARGET_KINDS, qualify


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
