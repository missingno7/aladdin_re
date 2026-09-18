"""State 3 (007516): a mirror of state 2's own countdown/gate shape.  `FFFFEA20 == 1` transitions
to state 2 (real ROM, UNWITNESSED by any recording, declined by name); otherwise a counter (`d7`)
counts DOWN and, once it goes negative, is forced to 6 and transitions to state 0.  Three tiers as
for the other leaves; the evidence tiers skip when the local census or reference artifacts are
absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-007516*/007516-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 007516')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_ea20_one_transitions_to_state_2():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 1}
    result = player.state3_step(_reader(values), 5)
    assert result['arm'] == 'transition-2'
    assert result['d7'] == 5   # unchanged: 00751E never touches d7


def test_counter_continues_while_nonnegative():
    result = player.state3_step(_reader({}), 2)
    assert result['arm'] == 'counting'
    assert result['d7'] == 1


def test_counter_forces_d7_to_6_once_it_goes_negative():
    result = player.state3_step(_reader({}), 0)
    assert result['arm'] == 'transition-0'
    assert result['d7'] == player.STATE3_RESET_COUNTER


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state3_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'transition-2' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-3').gate_pcs == (boundary.STATE3_ENTRY,)
    assert boundary.STATE3_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-3-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_3_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-3', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 3 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-3-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
