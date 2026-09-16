"""The fourth recovered Gods region: the work-table reset (004150).

A RAM-only leaf like the camera: fully unrolled, so cost is constant per
arm.  Three tiers: the pure semantics on synthetic reads; the boundary plan
against the tracer's facts on every state the census retained (the common
zero-fill arm, and the rarer poison-fill arm witnessed on one recording);
the candidate over real frames against the reference of the last PASS cold
run, with its negative control diverging.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import tables
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-004150*/004150-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 004150')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    return lambda address: values[address]


def test_a_negative_flag_zero_fills_the_table():
    result = tables.reset_table(_reader({tables.RESET_FLAG: 0x8000}))
    assert result['fill'] == 0 and not result['poisoned']
    assert result['stores'][tables.TABLE_END] == 0 and result['stores'][tables.TABLE_START - 1] == 0
    assert tables.POISON_FLAG not in result['stores']
    assert len(result['stores']) == tables.TABLE_START - tables.TABLE_END


def test_a_non_negative_flag_poison_fills_the_table_and_clears_the_second_flag():
    result = tables.reset_table(_reader({tables.RESET_FLAG: 0x0000}))
    assert result['fill'] == 0xFE and result['poisoned']
    assert result['stores'][tables.TABLE_END] == 0xFE and result['stores'][tables.TABLE_START - 1] == 0xFE
    assert result['stores'][tables.POISON_FLAG] == 0 and result['stores'][tables.POISON_FLAG + 1] == 0
    assert len(result['stores']) == tables.TABLE_START - tables.TABLE_END + 2


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.TABLE_RESET_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.table_reset_plan(machine, machine.registers())
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['interrupts_during_trace'] == 0


def test_candidate_names_are_explicit():
    assert recovery.Candidate('table-reset').gate_pcs == (boundary.TABLE_RESET_ENTRY,)
    assert recovery.Candidate('camera-sprites').gate_pcs == (
        boundary.CAMERA_FOLLOW_ENTRY, boundary.SPRITE_EMIT_ENTRY, boundary.STATIC_EMIT_ENTRY, boundary.TABLE_RESET_ENTRY)
    assert recovery.Candidate('table-reset-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='table-reset',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] == 60 and report['fallbacks'] == 0     # once per game tick, every other frame
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='table-reset-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE', mutant
