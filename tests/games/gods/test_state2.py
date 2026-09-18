"""State 2 (0074F0): a tiny three-arm leaf, the SAME shape as state 16's own "settle then
countdown" leaf.  `FFFFEA20 < 0` transitions straight to state 3; otherwise a counter (`d7`) counts
up and, once it reaches 3, forces `d7` to 6 and transitions to state 1.  No memory is read besides
`FFFFEA20`.  Three tiers as for the other leaves; the evidence tiers skip when the local census or
reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0074F0*/0074F0-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0074F0')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_negative_ea20_transitions_to_state_3():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF}
    result = player.state2_step(_reader(values), 1)
    assert result['arm'] == 'transition-3'
    assert result['d7'] == 1   # unchanged: 0074F6 never touches d7


def test_counter_continues_below_the_cap():
    result = player.state2_step(_reader({}), 1)
    assert result['arm'] == 'counting'
    assert result['d7'] == 2


def test_counter_forces_d7_to_6_once_it_reaches_the_cap():
    result = player.state2_step(_reader({}), 2)
    assert result['arm'] == 'transition-1'
    assert result['d7'] == player.STATE2_RESET_COUNTER


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state2_plan(machine, registers)
        except UnsupportedCandidate as error:
            pytest.fail(f'unexpected decline: {error}')
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-2').gate_pcs == (boundary.STATE2_ENTRY,)
    assert boundary.STATE2_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-2-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_2_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-2', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 2 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-2-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
