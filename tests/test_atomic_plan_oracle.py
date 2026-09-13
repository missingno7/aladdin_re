"""Direct prototype qualification must retain the complete machine contract."""
from dataclasses import replace

import pytest
import oracle_witness as oracle
from aladdin_sega.boundary import (
    COLLECTION_DISPATCH_ENTRY, COLLECTION_DISPATCH_RETURN,
    begin_collection_dispatch, begin_contact_type7e_dispatch,
    begin_contact_activation_dispatch,
)
from test_contact_type7e import fixture
from test_contact_activation import activation_fixture


def type7e_plan(machine, registers):
    _, prefix = begin_collection_dispatch(machine, registers)
    return begin_contact_type7e_dispatch(machine, registers, prefix)


def activation_plan(machine, registers):
    _, prefix = begin_collection_dispatch(machine, registers)
    return begin_contact_activation_dispatch(machine, registers, prefix)


def qualify(state, planner):
    return oracle.qualify_atomic_plan(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     exit_pc=COLLECTION_DISPATCH_RETURN,
                                     plan_factory=planner)


def test_direct_plan_uses_full_outer_future_and_fresh_contract():
    result = qualify(fixture(ready=0, armed=0x80), type7e_plan)
    assert result.stats['candidate_hits'] == 1
    assert result.stats['fallbacks'] == 0
    assert result.outer_state and result.future_state


def test_second_existing_contact_plan_uses_same_qualifier():
    result = qualify(activation_fixture(player_x=80), activation_plan)
    assert result.stats['candidate_hits'] == 1
    assert result.outer['registers']['pc'] == COLLECTION_DISPATCH_RETURN


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing', 'last-pc'])
def test_direct_plan_mutants_are_rejected(mutant):
    def wrong(machine, registers):
        plan = type7e_plan(machine, registers)
        if mutant == 'result':
            return replace(plan, writes=(*plan.writes, (0xFF7DFF, 0xB1)))
        if mutant == 'continuation':
            return replace(plan, registers={**plan.registers, 'pc': COLLECTION_DISPATCH_RETURN+2})
        if mutant == 'timing':
            return replace(plan, cycles=plan.cycles+4)
        return replace(plan, last_pc=plan.last_pc+2)
    with pytest.raises((AssertionError, RuntimeError)):
        qualify(fixture(), wrong)


def test_last_instruction_mismatch_cannot_hide_behind_visible_fields():
    state = fixture()
    def wrong(machine, registers):
        plan = type7e_plan(machine, registers)
        return replace(plan, last_pc=plan.last_pc+2)
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     expected_return=COLLECTION_DISPATCH_RETURN, candidate=None)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   expected_return=COLLECTION_DISPATCH_RETURN, candidate=None,
                                   plan_factory=wrong)
    assert all(actual.outer[k] == expected.outer[k] for k in ('info','registers','ram','frame','pcm'))
    assert actual.outer['state'] != expected.outer['state']
    with pytest.raises(AssertionError, match='outer divergence: state'):
        qualify(state, wrong)


def test_direct_plan_and_production_dispatch_are_mutually_exclusive():
    with pytest.raises(ValueError, match='cannot also dispatch'):
        oracle.execute_region(b'', entry=COLLECTION_DISPATCH_ENTRY,
                              candidate='lifecycle', plan_factory=type7e_plan)
