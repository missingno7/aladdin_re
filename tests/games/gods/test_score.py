"""The score conversion (00364C): called from the score-update sites (0035B2, 003604) and,
unwitnessed, from the trigger conditions' score kinds (13/14) through 004C4E's tail jump.

Three tiers: the pure semantics (BCD add, carry propagation) on synthetic
reads; the boundary plan against the tracer's facts on every state the
census retained (three path classes -- 1, 2 and 3 digits -- over four
recordings); the candidate over real frames against the reference of the
last PASS cold run, with its negative control diverging.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import score
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00364C*/00364C-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00364C')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    return lambda address, size: values[(address, size)]


def test_a_single_digit_adds_into_the_low_nibble_with_no_carry():
    result = score.convert_score(_reader({(0xFF0000, 2): 0x0000, (0xFF0002, 2): 0x0000,
                                          (0xFF0004, 2): 0x0000, (0xFF0006, 2): 0x0000}),
                                 9, 0xFF0000, entry_x=False)
    assert result['digits'] == 1
    assert result['words'] == (0x0009, 0x0000, 0x0000, 0x0000)
    assert result['stores'] == {0xFF0000: (0x0009, 2)}
    assert result['x'] is False


def test_two_digits_pack_into_the_same_word_low_then_high_nibble():
    result = score.convert_score(_reader({(0xFF0000, 2): 0x0000, (0xFF0002, 2): 0x0000,
                                          (0xFF0004, 2): 0x0000, (0xFF0006, 2): 0x0000}),
                                 50, 0xFF0000, entry_x=False)
    assert result['digits'] == 2
    assert result['words'][0] == 0x0050          # the tens digit (5) in the high nibble, ones (0) in the low


def test_a_bcd_carry_ripples_into_the_next_word():
    # existing digit 91 (FF0000) + new digit 9 = 100: wraps to 00 with a carry into d1 (existing 02 -> 03)
    result = score.convert_score(_reader({(0xFF0000, 2): 0x0091, (0xFF0002, 2): 0x0002,
                                          (0xFF0004, 2): 0x0000, (0xFF0006, 2): 0x0000}),
                                 9, 0xFF0000, entry_x=False)
    assert result['words'][0] == 0x0000 and result['words'][1] == 0x0003


def test_the_callers_x_flag_seeds_the_first_digits_carry_in():
    result = score.convert_score(_reader({(0xFF0000, 2): 0x0000, (0xFF0002, 2): 0x0000,
                                          (0xFF0004, 2): 0x0000, (0xFF0006, 2): 0x0000}),
                                 9, 0xFF0000, entry_x=True)
    assert result['words'][0] == 0x0010          # 0 + 9 + 1(carry-in) = 10, BCD


def test_a_fourth_division_is_declined_as_unwitnessed():
    result = score.convert_score(_reader({(0xFF0000, 2): 0, (0xFF0002, 2): 0, (0xFF0004, 2): 0, (0xFF0006, 2): 0}),
                                 1000, 0xFF0000, entry_x=False)
    assert result['digits'] is None


def test_a_negative_value_is_declined():
    result = score.convert_score(_reader({}), -1, 0xFF0000, entry_x=False)
    assert result['digits'] is None


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.SCORE_CONVERT_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.score_convert_plan(machine, machine.registers())
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['interrupts_during_trace'] == 0


def test_candidate_names_are_explicit():
    assert recovery.Candidate('score-convert').gate_pcs == (boundary.SCORE_CONVERT_ENTRY,)
    assert boundary.SCORE_CONVERT_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('score-convert-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='score-convert',
                                  reference=EVIDENCE)
    assert report['status'] in ('PASS', 'NOT_EXERCISED'), report
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                  candidate='score-convert-mutant-result', reference=EVIDENCE)
    assert mutant['status'] in ('PASS', 'DIVERGENCE', 'NOT_EXERCISED'), mutant
