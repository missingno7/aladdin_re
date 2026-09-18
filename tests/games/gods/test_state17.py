"""State 17 (006666): the SAME "settle then countdown" shape as state 16's own, transitioning to
state 0 instead of state 1 once F198 goes negative (d7 forced to 2, the same value state 16's own
transition uses). Not byte-identical to state 16's own code (the final store is `clr.w f192.w`, not
a `move.w #imm`), so costed with its own constants. Three tiers as for the other leaves; the
evidence tiers skip when the local census or reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006666*/006666-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006666')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_settle_increments_f1b8():
    result = player.state17_step(_reader({}))
    assert result['arm'] == 'settle'
    assert result['stores'][player.F1B8 & 0xFFFFFF] == (1, 2)


def test_countdown_continues_while_nonnegative():
    values = {(player.F1B8 & 0xFFFFFF, 2): 1, (player.F198 & 0xFFFFFF, 2): 4}
    result = player.state17_step(_reader(values))
    assert result['arm'] == 'countdown'
    assert result['stores'][player.F198 & 0xFFFFFF] == (0, 2)


def test_transition_0_once_negative():
    values = {(player.F1B8 & 0xFFFFFF, 2): 1, (player.F198 & 0xFFFFFF, 2): 2}
    result = player.state17_step(_reader(values))
    assert result['arm'] == 'transition-0'
    assert result['d7'] == 2
    assert result['stores'][player.STATE_INDEX] == (0, 2)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state17_plan(machine, registers)
        except UnsupportedCandidate as error:
            pytest.fail(f'unexpected decline: {error}')
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-17').gate_pcs == (boundary.STATE17_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into state 17's
    # own handler; this candidate's own hits replace the direct gate's.
    assert boundary.STATE17_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-17-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_17_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-17', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 17 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-17-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
