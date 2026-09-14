"""Self-contained original-ROM qualification of the connected contact scan."""
from dataclasses import replace
import pytest
import oracle_witness as oracle
import aladdin_sega.boundary as boundary
from aladdin_sega.recovery import Candidate
from test_contact_family import family_fixture

ENTRY, EXIT = boundary.CONTACT_SCAN_ENTRY, boundary.CONTACT_SCAN_EXIT
RECORD, PLAYER, PLAYER_SHAPE, SHAPE = 0xFF7E82, 0xFF9100, 0xFF9200, 0xFF9300


def scan_fixture(*, branch='contact', mirrored=0, x=100, high=0xA500,
                 ccr=0x17, stack=0xFFEC00, two=False, kind=0x6A):
    state = family_fixture(0x1AF978, kind=0x6A, previous=100, object_y=100,
                           vertical=0x800, flags=0x10, stack=stack)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        pc=machine.info['pc']; machine.gates([pc]); assert machine.run(instructions=1)=='gate'
        source=machine.peek_ram(0x6000,66)
        writes=[(RECORD+66*slot,0) for slot in range(24)]
        for at in (RECORD,RECORD+23*66) if two else (RECORD,):
            writes += [(at+i,value) for i,value in enumerate(source)]
            writes += [(at,kind),(at+9,mirrored),*oracle.write_word(at+2,x),
                       *oracle.write_word(at+4,100),*oracle.write_long(at+20,SHAPE)]
        writes += [(SHAPE+2,1),(SHAPE+3,1),(SHAPE+4,5),(SHAPE+5,5),
                   (PLAYER_SHAPE+3,0),(PLAYER_SHAPE+5,2)]
        left=(x+(251 if mirrored else 1))&65535
        right=(x+(255 if mirrored else 5))&65535
        player_right=left+1; player_left=0; player_y=101
        if branch=='inactive': writes.append((RECORD,0))
        elif branch=='non-contact-kind': writes.append((RECORD,0x7F))
        elif branch=='no-shape': writes += list(oracle.write_long(RECORD+20,0))
        elif branch=='left': player_right=left-1
        elif branch=='above': player_y=98
        elif branch=='right': player_left=right
        elif branch=='below': player_y=105
        elif branch!='contact': raise ValueError(branch)
        writes += [*oracle.write_word(0xFFF08E,player_right&65535),
                   *oracle.write_word(0xFFF08C,player_left),
                   *oracle.write_word(PLAYER+4,player_y)]
        regs=machine.registers()
        regs.update(pc=ENTRY,a2=PLAYER,a3=PLAYER_SHAPE,sr=(regs['sr']&~31)|ccr)
        for i in range(8): regs[f'd{i}']=(high<<16)|(0x1234+i)
        assert machine.atomic(target=machine.info['tick']+1_000_000,cycles=1,instructions=1,
                              last_pc=ENTRY,writes=writes,registers=regs)
        return machine.snapshot()


def qualify(state, factory=boundary.contact_scan_plan):
    return oracle.qualify_atomic_plan(state,entry=ENTRY,exit_pc=EXIT,plan_factory=factory)


@pytest.mark.parametrize('branch',('inactive','non-contact-kind','no-shape','left','above','right','below','contact'))
@pytest.mark.parametrize('mirrored',(0,1))
def test_each_geometry_exit_is_reached_and_whole_scan_qualifies(branch,mirrored):
    state=scan_fixture(branch=branch,mirrored=mirrored,x=0xFFFF if mirrored else 100)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        _,actual=boundary._contact_scan_prefix(machine,{**machine.registers(),'a1':RECORD})
        assert actual==branch
    result=qualify(state)
    assert result.stats['candidate_hits']==1
    assert result.stats['fallbacks']==0


@pytest.mark.parametrize('stack,high,ccr',((0xFFEC00,0xA500,0),(0xFFE000,0x5A00,31),(0xFFD800,0xF123,16)))
def test_two_callbacks_and_live_register_stack_variants(stack,high,ccr):
    state=scan_fixture(two=True,stack=stack,high=high,ccr=ccr)
    expected=oracle.execute_region(state,entry=ENTRY,candidate=None,expected_return=EXIT,include_raw=True)
    actual=oracle.execute_region(state,entry=ENTRY,candidate='lifecycle',expected_return=EXIT,include_raw=True)
    assert actual.outer==expected.outer
    assert actual.future==expected.future
    assert oracle.fresh_process_future(actual.outer_state)==actual.future
    assert actual.stats['contact_scan_hits']==1
    assert actual.stats['collection_dispatch_hits']==0
    assert actual.stats['direct_python_calls']>=4
    assert actual.stats['fallbacks']==0
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(actual.outer_state)
        assert machine.peek_ram(RECORD&65535,1)==b'k'
        assert machine.peek_ram((RECORD+23*66)&65535,1)==b'k'


def test_later_callback_must_read_staged_motion(monkeypatch):
    state=scan_fixture(two=True)
    qualify(state)
    original=boundary.begin_contact_family_motion_dispatch
    calls=0
    def stale(machine,registers,dispatch):
        nonlocal calls
        calls+=1
        if calls==2:
            dummy=boundary.AtomicPlan(1,1,tuple(oracle.write_word(0xFF7DFC,100)),{},ENTRY)
            machine=boundary.dispatch_plan_view(machine,dummy)
        return original(machine,registers,dispatch)
    monkeypatch.setattr(boundary,'begin_contact_family_motion_dispatch',stale)
    with pytest.raises(AssertionError,match='divergence'):
        qualify(state)
    assert calls==2


@pytest.mark.parametrize('kind',(0x4F,0x7B,0x02))
def test_unresolved_or_sound_callback_does_not_commit_a_partial_scan(kind):
    state=scan_fixture(kind=kind)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); machine.gates([ENTRY]); assert machine.run(instructions=1)=='gate'
        before=machine.snapshot()
        with pytest.raises(boundary.UnsupportedCandidate):
            boundary.contact_scan_plan(machine,machine.registers())
        assert machine.snapshot()==before


def test_callback_stack_alias_is_refused():
    state=scan_fixture()
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        before=machine.snapshot()
        with pytest.raises(boundary.UnsupportedCandidate):
            boundary.contact_scan_plan(machine,{**machine.registers(),'a7':0xFF7E04})
        assert machine.snapshot()==before


def test_deadline_refusal_matches_one_original_instruction():
    state=scan_fixture()
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); machine.gates([ENTRY]); assert machine.run(instructions=1)=='gate'
        machine.gate(ENTRY,bypass_once=True); assert machine.run(instructions=1)=='limit'
        expected=oracle.observable(machine)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); machine.gates([ENTRY]); assert machine.run(instructions=1)=='gate'
        candidate=Candidate('lifecycle'); candidate.arm(machine)
        assert not candidate.on_gate(machine,machine.info['tick'])
        assert oracle.observable(machine)==expected
        assert candidate.stats['fallback_reasons']=={'scheduler admission':1}


@pytest.mark.parametrize('mutant',('result','return','timing','last-pc'))
def test_scan_contract_rejects_mutants(mutant):
    state=scan_fixture(two=True)
    def wrong(machine,registers):
        plan=boundary.contact_scan_plan(machine,registers)
        if mutant=='result': return replace(plan,writes=(*plan.writes,(0xFFF101,0xA5)))
        if mutant=='return': return replace(plan,registers={**plan.registers,'pc':EXIT+2})
        if mutant=='timing': return replace(plan,cycles=plan.cycles+2)
        return replace(plan,last_pc=plan.last_pc-2)
    with pytest.raises((AssertionError,RuntimeError)):
        qualify(state,wrong)
