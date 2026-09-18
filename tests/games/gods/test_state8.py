"""State 8 (00648C): state 9's own sibling, sharing the SAME jump-arc velocity table
(``STATE9_FALL_TABLE``) and the SAME two row-gate leaves (006442/006468, ``_row_gate_open``) verbatim
-- confirmed against the ROM, not assumed.  NOT a byte-identical copy overall: the head's own resting
value is 6 (not state 9's 5), the block test gates on low5 == 0 (not low5 < 8) and checks the LEFT
neighbour's offsets (-1/0x7F/0xFF, not +1/+0x81/+0x101), and the ground/landed/trigger targets are
states 17/11/21 (not 16/12/20).  Two of its five arms ARE byte-identical to state 9's own ROM code:
arm A ('landing-14') and arm B ('landing-13') -- and, unlike state 9's own declined arm B, state 8's
own 'landing-13' IS witnessed (one real occurrence, `f40d7bcc9dda...`).  Three tiers as for the other
leaves; the evidence tiers skip when the local census or reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00648C*/00648C-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00648C')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_head_normalizes_state_counter():
    assert player._state8_head(_reader({}), 0xD) == (0xD, 'untouched')          # F19C < 4: stays put
    assert player._state8_head(_reader({(player.F19C & 0xFFFFFF, 2): 4}), 0xD) == (6, 'moveq')
    assert player._state8_head(_reader({}), 6) == (6, 'untouched')
    assert player._state8_head(_reader({}), 0) == (0, 'untouched')
    assert player._state8_head(_reader({(player.F19C & 0xFFFFFF, 2): 4}), 0) == (5, 'addq')
    assert player._state8_head(_reader({}), 3) == (6, 'moveq')                   # any other value -> 6


def test_countdown_advances_the_fall_timer_and_stays_in_state_8():
    result = player.state8_fall_tail(_reader({}), None, 0, new_y=0)
    assert result['arm'] == 'countdown'
    assert result['stores'][player.F19C] == (2, 2)


def test_terminal_forces_a_landing_once_the_timer_caps():
    result = player.state8_fall_tail(_reader({}), None, player.STATE9_COUNTDOWN_CAP - 2, new_y=0)
    assert result['arm'] == 'terminal'
    assert result['stores'][player.STATE_INDEX] == (player.STATE8_LANDED_INDEX, 2)
    assert result['stores'][player.STATE_INDEX][0] == 0xB
    assert result['d7'] == 0


def test_trigger_fires_only_short_of_the_trigger_cap():
    found = player.state8_fall_tail(_reader({}), True, player.STATE9_TRIGGER_CAP - 2, new_y=0)
    assert found['arm'] == 'trigger'
    assert found['stores'][player.STATE_INDEX] == (player.STATE8_TRIGGER_INDEX, 2)
    assert found['stores'][player.STATE_INDEX][0] == 0x15
    too_late = player.state8_fall_tail(_reader({}), True, player.STATE9_TRIGGER_CAP, new_y=0)
    assert too_late['arm'] == 'terminal'


def test_ground_stores_target_state_17_not_state_9s_16():
    stores = player._state8_ground_stores(0x1234)
    assert stores[player.STATE_INDEX] == (0x11, 2)
    assert stores[player.STATE_INDEX][0] == player.STATE8_GROUND_INDEX


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state8_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'landing-13' in str(error) or 'F19E' in str(error) or 'fall table index' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-8').gate_pcs == (boundary.STATE8_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into state 8's
    # own handler; this candidate's own hits replace the direct gate's.
    assert boundary.STATE8_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-8-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_8_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-8', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 8 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-8-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
