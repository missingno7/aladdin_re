"""The movement-cluster hit states (006AD8 = state 24, 006B14 = state 25): the contact-consume
family's own callers.  A 3-tick sequence over STATE_COUNTER -- tick 1 calls the already-recovered
consumer (012DA0 for state 24, 012E5A for state 25) once, tick 2 just falls into the shared tail,
tick 3 transitions to state 14 and copies a tracked position into the camera's own GRID_Y.  A leaf
composing an internal JSR into contact-consume (`boundary._cc_resolve`, the shape `0049DA` calling
`001164` already proved).  Three tiers as for the other leaves; the evidence tiers skip when the
local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import grid, player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
STATE24_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006AD8-entry*/006AD8-entry-p*.state'))
STATE25_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006B14-entry*/006B14-entry-p*.state'))
needs_state24_census = pytest.mark.skipif(not STATE24_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006AD8')
needs_state25_census = pytest.mark.skipif(not STATE25_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006B14')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_ticks_one_and_two_do_not_transition_and_only_tick_one_calls_the_consumer():
    tick1 = player.movement_hit_state(_reader({}), 0, 0)
    assert tick1['arm'] == 'call' and tick1['calls_consumer'] and tick1['counter'] == 1
    assert tick1['stores'] == {player.CONTACT_DIRECTION & 0xFFFFFF: (1, 2)}
    tick2 = player.movement_hit_state(_reader({}), 0, 1)
    assert tick2['arm'] == 'wait' and not tick2['calls_consumer'] and tick2['counter'] == 2


def test_tick_three_transitions_to_state_fourteen_and_copies_the_tracked_y():
    values = {(player.CONTACT_OVERRIDE_FLAG & 0xFFFFFF, 1): 0, (player.CONTACT_OVERRIDE_COUNTER & 0xFFFFFF, 2): 7,
             (player.CONTACT_OVERRIDE_Y & 0xFFFFFF, 2): 0x140}
    result = player.movement_hit_state(_reader(values), 0, 2)
    assert result['arm'] == 'transition' and not result['calls_consumer'] and result['counter'] == 7
    assert result['stores'][player.STATE_INDEX] == (0xE, 2)
    assert result['stores'][grid.GRID_Y] == (0x140, 2)
    assert not result['override_flag']


def test_the_override_flag_bit_set_keeps_the_counter_at_its_own_reset_value_per_routine():
    values = {(player.CONTACT_OVERRIDE_FLAG & 0xFFFFFF, 1): 1, (player.CONTACT_OVERRIDE_Y & 0xFFFFFF, 2): 0}
    state24 = player.movement_hit_state(_reader(values), 0, 2)
    state25 = player.movement_hit_state(_reader(values), 1, 2)
    assert state24['counter'] == 3 and state24['override_flag']
    assert state25['counter'] == 1 and state25['override_flag']
    assert state24['stores'][player.CONTACT_DIRECTION & 0xFFFFFF] == (1, 2)
    assert state25['stores'][player.CONTACT_DIRECTION & 0xFFFFFF] == (0xFFFF, 2)


@needs_state24_census
@pytest.mark.parametrize('fixture', STATE24_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_state_24_plan_reproduces_every_fact_of_the_original(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.movement_hit_primary_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=player.TAIL_ENTRY))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_state25_census
@pytest.mark.parametrize('fixture', STATE25_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_state_25_plan_reproduces_every_fact_of_the_original(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.movement_hit_secondary_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=player.TAIL_ENTRY))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_names_are_explicit():
    assert recovery.Candidate('state-24').gate_pcs == (boundary.STATE24_ENTRY,)
    assert recovery.Candidate('state-25').gate_pcs == (boundary.STATE25_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into states 24/25's own
    # handlers; this candidate's own hits replace the direct gates'.
    for entry in (boundary.STATE24_ENTRY, boundary.STATE25_ENTRY):
        assert entry not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-24-mutant-result').mutation is recovery._mutate_result
    assert recovery.Candidate('state-25-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_state_24_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in STATE24_FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-24', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 24 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-24-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


@needs_reference
def test_state_25_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in STATE25_FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-25', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 25 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-25-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
