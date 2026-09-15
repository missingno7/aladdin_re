"""Outer contact-tick qualification using self-contained original-ROM states."""
from dataclasses import replace
import pytest
import oracle_witness as oracle
import aladdin_sega.boundary as boundary
from aladdin_sega.recovery import Candidate
from test_contact_scan import scan_fixture, RECORD, PLAYER_SHAPE

ENTRY, RETURN = 0x1ABB40, 0x1B65BE


def step_fixture(*, ee=0, f2=0, active=1, shape=PLAYER_SHAPE, mirrored=0,
                 two=False, ccr=31, high=0xA500, stack=0xFFEC00, kind=0x6A):
    state=scan_fixture(two=two,ccr=ccr,high=high,stack=stack,kind=kind)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); pc=machine.info['pc']
        machine.gates([pc]); assert machine.run(instructions=1)=='gate'
        regs={**machine.registers(),'pc':ENTRY}
        writes=[(0xFFF0EE,ee),(0xFFF0F2,f2),(0xFFF0D3,0xA5),
                (0xFF7E40,active),(0xFF7E49,mirrored),
                (PLAYER_SHAPE+2,0),(PLAYER_SHAPE+4,10),
                *oracle.write_long(0xFF7E54,shape),
                *oracle.write_word(0xFF7E42,100),*oracle.write_word(0xFF7E44,101)]
        assert machine.atomic(target=machine.info['tick']+1_000_000,cycles=1,instructions=1,
                              last_pc=ENTRY,writes=writes,registers=regs)
        return machine.snapshot()


def qualify(state,factory=None):
    return oracle.qualify_atomic_plan(state,entry=ENTRY,exit_pc=RETURN,
                                      plan_factory=factory or boundary.contact_step_plan)


@pytest.mark.parametrize('values',(
    {},{'shape':0},{'active':0},{'mirrored':1},
    {'ee':1},{'f2':1},{'ee':255,'f2':255},
    {'shape':0,'ee':1},{'active':0,'f2':1},
    {'shape':0xFFF0EC,'ee':1,'f2':5},
))
@pytest.mark.parametrize('ccr',(0,31))
def test_tick_timers_guards_bounds_and_rts_are_strict(values,ccr):
    result=qualify(step_fixture(ccr=ccr,**values))
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(result.outer_state)
        assert machine.registers()['a7']==0xFFEC04
        assert machine.peek_ram(0xF0D4,1)==b'\xA5'
        assert machine.peek_ram(0xF0EE,1)==bytes([max(0,values.get('ee',0)-1)])
        assert machine.peek_ram(0xF0F2,1)==bytes([max(0,values.get('f2',0)-1)])


@pytest.mark.parametrize('stack,high',((0xFFEC00,0xA500),(0xFFE000,0x5A00),(0xFFD800,0xF123)))
def test_outer_entry_owns_scan_and_position_changes_later_contact(stack,high):
    state=step_fixture(two=True,stack=stack,high=high)
    expected=oracle.execute_region(state,entry=ENTRY,candidate=None,expected_return=RETURN,include_raw=True)
    actual=oracle.execute_region(state,entry=ENTRY,candidate='lifecycle',expected_return=RETURN,include_raw=True)
    assert actual.outer==expected.outer
    assert actual.future==expected.future
    assert oracle.fresh_process_future(actual.outer_state)==actual.future
    assert actual.stats['contact_step_hits']==1
    assert actual.stats['collection_dispatch_hits']==0
    assert actual.stats['fallbacks']==0
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(actual.outer_state)
        assert machine.peek_ram(RECORD&65535,1)==b'k'
        # Landing updated the real player's Y, rejecting the later rectangle.
        assert machine.peek_ram((RECORD+23*66)&65535,1)==b'j'


@pytest.mark.parametrize('kind',(0x4F,0x7B,0x02))
def test_unsupported_parent_path_truncates_at_the_scan_loop_head(kind):
    """An unresolved callback at the record's own slot 0 no longer discards
    contact_step_plan's whole composed prefix: the inner contact_scan_plan
    truncates at the loop head (0x1ABBE0) and contact_step_plan's own
    _pop_contact_scan_return leaves that state as-is (nothing pushed for an
    outer return yet) instead of misreading it as one -- the per-slot
    COLLECTION_DISPATCH_ENTRY gate then owns the record directly, exactly
    as it already does for a fresh (non-scan) dispatch to this same
    unresolved target."""
    state=step_fixture(kind=kind)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        plan=boundary.contact_step_plan(machine,machine.registers())
        assert plan.registers['pc']==0x1ABBE0
        assert plan.registers['a1']==RECORD
    expected=oracle.execute_region(state,entry=ENTRY,candidate=None,expected_return=RETURN,include_raw=True)
    actual=oracle.execute_region(state,entry=ENTRY,candidate='lifecycle',expected_return=RETURN,include_raw=True)
    assert actual.outer==expected.outer
    assert actual.future==expected.future
    assert oracle.fresh_process_future(actual.outer_state)==actual.future
    assert actual.stats['fallbacks']<=1
    if actual.stats['fallbacks']:
        assert all(reason.startswith('unsupported domain:')
                  for reason in actual.stats['fallback_reasons'])


def test_parent_deadline_refusal_preserves_original_progress():
    state=step_fixture()
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); machine.gates([ENTRY]); assert machine.run(instructions=1)=='gate'
        machine.gate(ENTRY,bypass_once=True); assert machine.run(instructions=1)=='limit'
        expected=oracle.observable(machine)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); machine.gates([ENTRY]); assert machine.run(instructions=1)=='gate'
        candidate=Candidate('lifecycle');candidate.arm(machine)
        assert not candidate.on_gate(machine,machine.info['tick'])
        assert oracle.observable(machine)==expected


def test_internal_scan_gate_is_oracle_only():
    gates=Candidate('lifecycle').gate_pcs
    assert ENTRY in gates
    assert boundary.CONTACT_SCAN_ENTRY not in gates


def test_odd_outer_return_declines_without_mutation():
    state=step_fixture(shape=0)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state);machine.gates([ENTRY]);assert machine.run(instructions=1)=='gate'
        assert machine.atomic(target=machine.info['tick']+1_000_000,cycles=1,instructions=1,
                              last_pc=ENTRY,writes=list(oracle.write_long(0xFFEC00,RETURN+1)),
                              registers=machine.registers())
        before=machine.snapshot()
        with pytest.raises(boundary.UnsupportedCandidate,match='return PC'):
            boundary.contact_step_plan(machine,machine.registers())
        assert machine.snapshot()==before


def test_unchanged_callback_register_is_taken_from_collision_prefix(monkeypatch):
    original=boundary.begin_contact_family_motion_dispatch
    def partial(machine,registers,dispatch):
        plan=original(machine,registers,dispatch)
        # This callback leaves D3 unchanged; its adapter may omit that effect.
        final=dict(plan.registers);final.pop('d3',None)
        return replace(plan,registers=final)
    monkeypatch.setattr(boundary,'begin_contact_family_motion_dispatch',partial)
    qualify(step_fixture())


@pytest.mark.parametrize('mutant',('result','return','timing','last-pc'))
def test_outer_tick_contract_rejects_mutants(mutant):
    state=step_fixture()
    def wrong(machine,registers):
        plan=boundary.contact_step_plan(machine,registers)
        if mutant=='result': return replace(plan,writes=(*plan.writes,(0xFFF0D4,0)))
        if mutant=='return': return replace(plan,registers={**plan.registers,'pc':RETURN+2})
        if mutant=='timing': return replace(plan,cycles=plan.cycles+2)
        return replace(plan,last_pc=plan.last_pc-2)
    with pytest.raises((AssertionError,RuntimeError)):
        qualify(state,wrong)


@pytest.mark.parametrize('kind', (0x05, 0x06))
@pytest.mark.parametrize('route', ('early', 'decrement'))
def test_sibling_wrappers_compose_inside_outer_tick(kind, route):
    state = step_fixture(kind=kind, two=True)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        machine.gates([ENTRY]); assert machine.run(instructions=1) == 'gate'
        writes = [(0xFFF0D8, 1), (0xFFF57D, 0),
                  *oracle.write_word(0xFF7E02, 100 if route == 'early' else 99)]
        for record in (RECORD, RECORD + 23 * 66):
            writes += [(record + 1, 2), (record + 6, 0)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1, last_pc=ENTRY,
                              writes=writes, registers=machine.registers())
        state = machine.snapshot()
    qualify(state)
    expected = oracle.execute_region(state, entry=ENTRY, candidate=None,
                                     expected_return=RETURN, include_raw=True)
    actual = oracle.execute_region(state, entry=ENTRY, candidate='lifecycle',
                                   expected_return=RETURN, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['contact_step_hits'] == 1
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] == 0
    assert actual.stats['direct_python_calls'] >= 4
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(actual.outer_state)
        for record in (RECORD, RECORD + 23 * 66):
            assert machine.peek_ram((record + 1) & 65535, 1) == bytes([2 if route == 'early' else 1])
