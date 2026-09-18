"""State 16 (006686): a tiny two-step "settle then countdown" leaf -- the target both state 9's own
"ground-before"/"ground-after" arms and state 26's own mirror transition into.  FFFFF1B8 == 0
increments it to 1 and exits unchanged; FFFFF1B8 != 0 decrements FFFFF198 by 4, exiting unchanged
while non-negative or transitioning to state 1 (d7 forced to 2) once it goes negative.  No d7 is ever
read as an input.  Three tiers as for the other leaves; the evidence tiers skip when the local census
or reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006686*/006686-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006686')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_settle_increments_f1b8():
    result = player.state16_step(_reader({}))
    assert result['arm'] == 'settle'
    assert result['stores'][player.F1B8 & 0xFFFFFF] == (1, 2)


def test_countdown_continues_while_nonnegative():
    values = {(player.F1B8 & 0xFFFFFF, 2): 1, (player.F198 & 0xFFFFFF, 2): 4}
    result = player.state16_step(_reader(values))
    assert result['arm'] == 'countdown'
    assert result['stores'][player.F198 & 0xFFFFFF] == (0, 2)


def test_transition_1_once_negative():
    values = {(player.F1B8 & 0xFFFFFF, 2): 1, (player.F198 & 0xFFFFFF, 2): 2}
    result = player.state16_step(_reader(values))
    assert result['arm'] == 'transition-1'
    assert result['d7'] == 2
    assert result['stores'][player.STATE_INDEX] == (1, 2)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state16_plan(machine, registers)
        except UnsupportedCandidate as error:
            pytest.fail(f'unexpected decline: {error}')
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-16').gate_pcs == (boundary.STATE16_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into state 16's
    # own handler; this candidate's own hits replace the direct gate's.
    assert boundary.STATE16_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-16-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_16_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-16', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 16 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-16-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
