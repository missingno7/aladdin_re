"""State 21 (006886): a hybrid of state 9/26's own jump-arc fall step (the SAME shared table
006414, `_row_gate_open`) and state 12's own LEFT block-test gate (FFFFF18C & 0x1F == 0, offsets
-1/0x7F/0xFF), plus a THIRD real composition into the already-recovered movement-cluster consumer
012E5A. Two ground-ahead probes gated by STATE9_TRIGGER_GATE (0x16, the first) and
STATE21_RECHECK_GATE (0x12, the second, state 26's own value). The tail is D7-based like state 26's
own but targets state 8 (not 9) once D7 reaches 3, and calls 012E5A (not 012DA0) when D7 is exactly
1. Three tiers as for the other leaves; the evidence tiers skip when the local census or reference
artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006886*/006886-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006886')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_head_bumps_d7_when_f1ba_clear():
    new_d7, f1ba_was_set = player._state21_head(_reader({}), 2)
    assert new_d7 == 3
    assert f1ba_was_set is False


def test_head_decrements_d7_when_f1ba_set():
    values = {(player.F1BA & 0xFFFFFF, 2): 1}
    new_d7, f1ba_was_set = player._state21_head(_reader(values), 2)
    assert new_d7 == 1
    assert f1ba_was_set is True


def test_tail_trigger_forces_d7_to_6():
    result = player.state21_tail(3, 0x10)
    assert result['arm'] == 'trigger'
    assert result['capped'] is False


def test_tail_consume_at_exactly_one():
    result = player.state21_tail(1, 0x10)
    assert result['arm'] == 'consume'


def test_tail_countdown_otherwise():
    result = player.state21_tail(0, 0x10)
    assert result['arm'] == 'countdown'


def test_tail_caps_at_the_threshold():
    result = player.state21_tail(3, player.STATE21_CAP - 2)
    assert result['capped'] is True


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state21_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'not witnessed' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-21').gate_pcs == (boundary.STATE21_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into state 21's
    # own handler; this candidate's own hits replace the direct gate's.
    assert boundary.STATE21_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-21-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_21_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-21', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 21 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-21-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
