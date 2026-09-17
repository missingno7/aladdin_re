"""The message display gate (007986) and string copy (0079DC): shared utilities, not trigger-specific.

007986 is called from many sites (0046AA, the trigger evaluator's own
firing arm, is only one of them); 0079DC is a plain byte copy.  Three
tiers as for the other leaves; the evidence tiers skip when the local
census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import messages
from gods_sega.profile import GODS

GATE_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-007986-*/007986-entry-p*.state')) + \
    sorted(Path('artifacts/gods/evidence/census-triggerfire').glob('007986-*-p*.state'))
COPY_FIXTURES = sorted(Path('artifacts/gods/evidence/census-triggerfire').glob('0079DC-*-p*.state'))
needs_gate_census = pytest.mark.skipif(not GATE_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 007986')
needs_copy_census = pytest.mark.skipif(not COPY_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0079DC')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_a_negative_priority_is_negated_and_clears_the_pending_state():
    values = {(messages.MESSAGE_BUFFER & 0xFFFFFF, 4): 0xFFF200, (0xFFF200, 1): 0}
    result = messages.message_gate(_reader(values), 0xFFE7)   # -25
    assert result['arm'] == 'ready' and result['negated'] and result['bound'] == 25
    assert result['stores'][messages.MESSAGE_BOUND & 0xFFFFFF] == (25, 2)
    assert result['stores'][messages.MESSAGE_PENDING & 0xFFFFFF] == (0, 2)


def test_an_empty_primary_buffer_is_ready_through_it():
    values = {(messages.MESSAGE_BUFFER & 0xFFFFFF, 4): 0xFFF200, (0xFFF200, 1): 0}
    result = messages.message_gate(_reader(values), 5)
    assert result['arm'] == 'ready' and not result['negated'] and result['buffer'] == 0xFFF200


def test_an_occupied_buffer_with_sufficient_priority_uses_the_alternate_buffer():
    values = {(messages.MESSAGE_BUFFER & 0xFFFFFF, 4): 0xFFF200, (0xFFF200, 1): 1,
             (messages.MESSAGE_BOUND & 0xFFFFFF, 2): 10, (messages.MESSAGE_BUFFER_ALT & 0xFFFFFF, 4): 0xFFF300}
    result = messages.message_gate(_reader(values), 8)
    assert result['arm'] == 'ready' and result['buffer'] == 0xFFF300


def test_an_occupied_buffer_with_insufficient_priority_is_blocked():
    values = {(messages.MESSAGE_BUFFER & 0xFFFFFF, 4): 0xFFF200, (0xFFF200, 1): 1,
             (messages.MESSAGE_BOUND & 0xFFFFFF, 2): 3}
    result = messages.message_gate(_reader(values), 8)
    assert result['arm'] == 'blocked' and result['stores'] == {}


def test_an_occupied_buffer_with_a_zero_stored_bound_is_unrecovered():
    values = {(messages.MESSAGE_BUFFER & 0xFFFFFF, 4): 0xFFF200, (0xFFF200, 1): 1,
             (messages.MESSAGE_BOUND & 0xFFFFFF, 2): 0}
    result = messages.message_gate(_reader(values), 8)
    assert result['arm'] == 'unrecovered'


def test_copy_message_stops_at_the_nul_and_reports_every_byte_including_it():
    values = {(0x1000, 1): ord('h'), (0x1001, 1): ord('i'), (0x1002, 1): 0}
    result = messages.copy_message(_reader(values), 0x1000)
    assert result['bytes'] == b'hi\x00' and result['length'] == 3


@needs_gate_census
@pytest.mark.parametrize('fixture', GATE_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_message_gate_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.message_gate_plan(machine, registers)
        except boundary.UnsupportedCandidate:
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_copy_census
@pytest.mark.parametrize('fixture', COPY_FIXTURES, ids=lambda p: p.stem)
def test_string_copy_plan_reproduces_every_fact_of_the_original(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.string_copy_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_names_are_explicit():
    assert recovery.Candidate('message-gate').gate_pcs == (boundary.MESSAGE_GATE_ENTRY,)
    assert recovery.Candidate('string-copy').gate_pcs == (boundary.STRING_COPY_ENTRY,)
    assert boundary.MESSAGE_GATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.STRING_COPY_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('message-gate-mutant-result').mutation is recovery._mutate_result
    assert recovery.Candidate('string-copy-mutant-result').mutation is recovery._mutate_result
