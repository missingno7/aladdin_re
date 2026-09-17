"""The trigger evaluator's action table (game/actions.py) -- part 3 of the trigger firing subsystem
blocker's Split: the two admissible handlers, each reached by the evaluator's own firing tail through
a tail jump (0046CE) with no frame of its own, so a handler's own entry PC needs no seam at all.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import actions, conditions, pickups
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


# --- 0048E4: reset the elapsed-seconds counter -----------------------------------------------------

RESET_ELAPSED_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0048E4-*/0048E4-entry-*.state'))
needs_reset_elapsed_census = pytest.mark.skipif(not RESET_ELAPSED_FIXTURES or not GODS.rom_path.is_file(),
                                                reason='no local census of 0048E4')


def test_reset_elapsed_always_targets_the_conditions_elapsed_word():
    assert actions.reset_elapsed(_reader({})) == conditions.ELAPSED


@needs_reset_elapsed_census
@pytest.mark.parametrize('fixture', RESET_ELAPSED_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_action_reset_elapsed_plan_reproduces_every_fact_of_the_original(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.ACTION_RESET_ELAPSED_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.action_reset_elapsed_plan(machine, machine.registers())
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_reset_elapsed_candidate_names_are_explicit():
    assert recovery.Candidate('action-reset-elapsed').gate_pcs == (boundary.ACTION_RESET_ELAPSED_ENTRY,)
    assert boundary.ACTION_RESET_ELAPSED_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('action-reset-elapsed-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_reset_elapsed_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='action-reset-elapsed', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('action-reset-elapsed never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='action-reset-elapsed-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 004ACA: clear a matched pickup group's own active-id word ---------------------------------------

CLEAR_GROUP_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-004ACA-*/004ACA-entry-*.state'))
needs_clear_group_census = pytest.mark.skipif(not CLEAR_GROUP_FIXTURES or not GODS.rom_path.is_file(),
                                              reason='no local census of 004ACA')


def test_clear_matched_group_finds_each_of_the_three_positions():
    for index, address in enumerate(pickups.GROUP_TABLES):
        world = {(a, 2): (99 + i) for i, a in enumerate(pickups.GROUP_TABLES)}
        world[(address, 2)] = 42
        assert actions.clear_matched_group(_reader(world), 42) == address


def test_clear_matched_group_is_none_on_a_miss():
    world = {(a, 2): 99 for a in pickups.GROUP_TABLES}
    assert actions.clear_matched_group(_reader(world), 42) is None


def test_witnessed_action_clear_group_arms():
    # only the second group (FFF01E) has ever been witnessed to match; a miss, and a match against
    # the first or third group, are real code no recording enters.
    assert boundary.WITNESSED_ACTION_CLEAR_GROUP_ARMS == (1,)


@needs_clear_group_census
@pytest.mark.parametrize('fixture', CLEAR_GROUP_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_action_clear_group_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_arm(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.ACTION_CLEAR_GROUP_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.action_clear_group_plan(machine, registers)
        except boundary.UnsupportedCandidate:
            return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_clear_group_candidate_names_are_explicit():
    assert recovery.Candidate('action-clear-group').gate_pcs == (boundary.ACTION_CLEAR_GROUP_ENTRY,)
    assert boundary.ACTION_CLEAR_GROUP_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('action-clear-group-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_clear_group_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='action-clear-group', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('action-clear-group never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='action-clear-group-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
