"""The tracer derives a branch's machine facts from the original; the checker names every fault.

These tests pin the facts a grinder relies on instead of counting by hand:
the Type-55 cost table (including the historical 180/15 versus 182/16
accounting bug), the seam split of a sound-requesting callback, and the
checker's report for each class of injected fault.
"""
from dataclasses import replace

import pytest
import pathfacts
from aladdin_sega.profile import ALADDIN
import factcheck
from aladdin_sega import boundary
from genesis_re.machine import Machine
from aladdin_sega.profile import read_rom
from test_contact_family import family_fixture, type46_fixture, TARGET_KINDS

TYPE55 = 0x1AF590


def parked_type55(monkeypatch, **values):
    monkeypatch.setitem(TARGET_KINDS, TYPE55, 0x55)
    state = family_fixture(TYPE55, object_y=100, origin_x=0, flags=0x10, **values)
    return pathfacts.park(state, TYPE55, game=ALADDIN)


def plan_for(state, planner):
    with Machine(read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        return planner(machine, registers), registers


@pytest.mark.parametrize('previous,cycles,instructions', [(100, 180, 15), (0, 182, 16)])
def test_tracer_reproduces_the_type55_cost_table_and_the_plan_matches(monkeypatch, previous, cycles, instructions):
    state = parked_type55(monkeypatch, previous=previous)
    facts = pathfacts.trace(state, game=ALADDIN)
    assert (facts['cycles'], facts['instructions'], facts['last_pc']) == (cycles, instructions, 0x1AE6BA)
    assert facts['exit_pc'] == facts['caller_return_slot_at_entry']
    assert facts['stack_delta'] == 4
    assert facts['ram_writes_final'] == {0xFFF0F5: 0xFF}
    assert facts['interrupts_during_trace'] == 0
    plan, registers = plan_for(state, boundary.begin_contact_family_type55)
    assert pathfacts.check_plan(plan, facts, registers) == []


def test_direct_and_selector_arms_cost_what_the_original_charges(monkeypatch):
    for values, cycles, instructions in (({'be': 1, 'c0': 0}, 86, 6), ({'be': 1, 'c0': 0xFF}, 206, 17)):
        state = parked_type55(monkeypatch, previous=100, **values)
        facts = pathfacts.trace(state, game=ALADDIN)
        assert (facts['cycles'], facts['instructions']) == (cycles, instructions)
        plan, registers = plan_for(state, boundary.begin_contact_family_type55)
        assert pathfacts.check_plan(plan, facts, registers) == []


def test_checker_names_each_injected_fault(monkeypatch):
    state = parked_type55(monkeypatch, previous=100)
    facts = pathfacts.trace(state, game=ALADDIN)
    plan, registers = plan_for(state, boundary.begin_contact_family_type55)
    faults = {
        'cycles': replace(plan, cycles=plan.cycles + 2),
        'instructions': replace(plan, instructions=plan.instructions + 1),
        'last_pc': replace(plan, last_pc=0x1AE6B8),
        'wrong write': replace(plan, writes=((0xFFF0F5, 0xFE),)),
        'missing write': replace(plan, writes=()),
        'extra write': replace(plan, writes=(*plan.writes, (0xFFF0F6, 0x01))),
        'register d7': replace(plan, registers={**plan.registers, 'd7': plan.registers['d7'] ^ 1}),
        'register d3': replace(plan, registers={**plan.registers, 'd3': 0x12345678}),
    }
    for name, wrong in faults.items():
        problems = [p for p in pathfacts.check_plan(wrong, facts, registers) if not p.startswith('note')]
        assert len(problems) == 1 and name in problems[0], (name, problems)
    redundant = replace(plan, writes=(*plan.writes, (0xFFF0F4, facts['entry_ram'][0xF0F4])))
    notes = pathfacts.check_plan(redundant, facts, registers)
    assert notes == ['note: 1 plan writes store the value RAM already held (harmless)']


def test_seam_split_matches_the_type46_prefix_and_native_sound_entry():
    state = pathfacts.park(type46_fixture(), 0x1AEF5C, game=ALADDIN)
    facts = pathfacts.trace(state, game=ALADDIN)
    segments = pathfacts.split_at_native(facts)
    assert segments[0]['kind'] == 'python' and segments[1]['kind'] == 'native'
    assert segments[1]['callee'] == 0x1E58B8
    seam, registers = plan_for(state, boundary.begin_contact_family_type46_sound_seam)
    prefix = seam.prefix
    assert (segments[0]['cycles'], segments[0]['instructions'], segments[0]['last_pc']) == (
        prefix.cycles, prefix.instructions, prefix.last_pc)
    assert segments[0]['registers_after']['a7'] == prefix.registers['a7']
    resume = segments[2]
    assert resume['kind'] == 'python' and resume['entry_pc'] == 0x1AEFA0  # the JSR return slot the prefix pushed
    assert any(segment['kind'] == 'python' and segment['entry_pc'] == seam.resume_pc for segment in segments[2:])
    prefix_facts = pathfacts.trace(state, stop_pc=0x1E58B8, game=ALADDIN)
    assert pathfacts.check_plan(prefix, prefix_facts, registers) == []


def test_factcheck_check_varies_every_type55_arm_and_reports_declines(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(TARGET_KINDS, TYPE55, 0x55)
    fixture = tmp_path / 'type55.state'
    fixture.write_bytes(family_fixture(TYPE55, previous=100, object_y=100, origin_x=0, flags=0x10))
    planner = 'aladdin_sega.boundary:begin_contact_family_type55'
    code = factcheck.main(['check', '--game', 'aladdin', str(fixture), planner, '--park', '1AF590',
                           '--vary', 'FFF0BE=0,1', '--vary', 'FFF0C0=0,0xFF', '--vary', 'FF7DFC.w=100,0'])
    out = capsys.readouterr().out
    assert code == 0
    assert out.count('\nMATCH') == 8 and 'MISMATCH' not in out
    code = factcheck.main(['check', '--game', 'aladdin', str(fixture), planner, '--park', '1AF590', '--vary', 'FF7DFC.w=84'])
    out = capsys.readouterr().out
    assert code == 2 and 'DECLINED: type55 transition arm is not recovered' in out
    assert 'original: ' not in out and 'instructions:' in out


def test_factcheck_checks_a_seam_planner_through_its_prefix(tmp_path, capsys):
    fixture = tmp_path / 'type46.state'
    fixture.write_bytes(type46_fixture())
    code = factcheck.main(['check', '--game', 'aladdin', str(fixture), 'aladdin_sega.boundary:begin_contact_family_type46_sound_seam',
                           '--park', '1AEF5C'])
    out = capsys.readouterr().out
    assert code == 0 and 'seam: checking the prefix up to native entry 1E58B8' in out
    assert 'finish_contact_family_type46_sound' in out and out.rstrip().endswith('MATCH')


def test_factcheck_branches_groups_variations_by_executed_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(TARGET_KINDS, TYPE55, 0x55)
    fixture = tmp_path / 'type55.state'
    fixture.write_bytes(family_fixture(TYPE55, previous=100, object_y=100, origin_x=0, flags=0x10))
    code = factcheck.main(['branches', '--game', 'aladdin', str(fixture), '--park', '1AF590', '--vary', 'FF7DFC.w=100,0,84'])
    out = capsys.readouterr().out
    assert code == 0 and '3 variations, 3 distinct executed paths' in out
    assert 'WARNING' not in out


def test_parse_vary_pokes_bytes_words_and_longs():
    assert factcheck.parse_vary(['FFF0BE=0,1']) == [[((0xFFF0BE, 0),), ((0xFFF0BE, 1),)]]
    assert factcheck.parse_vary(['FF7DFC.w=0x1234']) == [[((0xFF7DFC, 0x12), (0xFF7DFD, 0x34))]]
    assert factcheck.parse_vary(['FF7E60.l=0x001226CE']) == [[((0xFF7E60, 0), (0xFF7E61, 0x12), (0xFF7E62, 0x26), (0xFF7E63, 0xCE))]]


def test_tracer_on_a_live_machine_matches_trace_and_signatures_separate_arms(monkeypatch):
    state = parked_type55(monkeypatch, previous=100)
    expected = pathfacts.trace(state, game=ALADDIN)
    rom = read_rom()
    with Machine(rom) as machine:
        machine.restore(state)
        machine.gates([TYPE55, 0x1AE6BA])  # gates armed inside the region must not disturb the trace
        tracer = pathfacts.Tracer(machine, rom, natives=ALADDIN.tracer_native_entries)
        while not tracer.at_exit():
            tracer.step()
        live = tracer.facts()
    for key in ('cycles', 'instructions', 'last_pc', 'exit_pc', 'ram_writes_final', 'changed_registers'):
        assert live[key] == expected[key], key
    guard = pathfacts.path_signature(expected)
    borrow = pathfacts.path_signature(pathfacts.trace(parked_type55(monkeypatch, previous=0), game=ALADDIN))
    direct = pathfacts.path_signature(pathfacts.trace(parked_type55(monkeypatch, previous=100, be=1, c0=0), game=ALADDIN))
    assert guard['exit'] == borrow['exit'] == direct['exit'] == '1ABCA0'
    assert len({pathfacts.signature_key(s) for s in (guard, borrow, direct)}) == 3
    assert (guard['instructions'], borrow['instructions'], direct['instructions']) == (15, 16, 6)
    assert guard['writes'] == ['FFF0F5'] and guard['natives'] == [] and guard['calls'] == []
    untracked = pathfacts.path_signature(pathfacts.trace(state, track_ram=False, game=ALADDIN))
    assert pathfacts.signature_key(untracked) == pathfacts.signature_key(guard) and untracked['writes'] == []
    seam = pathfacts.path_signature(pathfacts.trace(pathfacts.park(type46_fixture(), 0x1AEF5C, game=ALADDIN), game=ALADDIN))
    # Type-46 requests its sound from inside a local BSR: the native shape is
    # visible, the depth-zero call is the BSR itself.
    assert seam['natives'] == ['1E58B8', '1E589A'] and seam['calls'][0] == '1AEF70'
    # Record and global writes are labels; the activation's stack slots are not.
    assert 'FF7E3C' in seam['writes'] and all(not w.startswith('stk') for w in seam['writes'])
