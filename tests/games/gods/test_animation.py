"""The animation step (00FE08): the shared frame-budget refresh, once per active solid per tick.

The 'idle' arm (the live record's own moving flag negative) is a plain
leaf, and by far the dominant occurrence.  The 'moving' arm is common too
but calls the unrecovered coroutine and per-type dispatch at 00FFF0
(a resumable Bresenham-style line walk that stores its own continuation
address back into the record, then a jump-table dispatch on a state byte):
not a leaf, so the boundary declines it regardless of how often it runs.
Three tiers as for the other leaves; the evidence tiers skip when the
local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import animation
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00FE08*/00FE08-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00FE08')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

RECORD, DEFINITION = 0xFF4AAE, 0xFF65A2


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def test_the_idle_arm_refreshes_the_budget_and_touches_nothing_else():
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0x02, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x80}
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['arm'] == 'idle' and result['budget'] == 3 and result['budget_before'] == 2
    assert result['stores'] == {0xFFF1FE: (3, 2)}


def test_a_non_negative_moving_flag_selects_the_moving_arm():
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x01}
    assert animation.animation_step(_reader(values), RECORD, DEFINITION)['arm'] == 'moving'


def test_the_definition_index_byte_is_signed_and_the_budget_wraps_like_the_68000():
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0xFF, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x80}
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['budget_before'] == 0xFFFF and result['budget'] == 0    # -1 + 1


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_the_idle_arm_and_declines_the_moving_one(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.ANIMATION_STEP_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        record, definition = registers['a1'] & 0xFFFFFF, registers['a2'] & 0xFFFFFF
        moving = not (machine.peek_ram((record + animation.LIVE_MOVING_FLAG) & 0xFFFF, 1)[0] & 0x80)
        if moving:
            with pytest.raises(boundary.UnsupportedCandidate, match='calls unrecovered'):
                boundary.animation_step_plan(machine, registers)
            return
        plan = boundary.animation_step_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('animation-step').gate_pcs == (boundary.ANIMATION_STEP_ENTRY,)
    assert boundary.ANIMATION_STEP_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('animation-step-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='animation-step',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= {'scheduler admission', 'unsupported domain: animation step arm calls unrecovered 00FFF0: moving'}
    if report['candidate_hits'] == 0:
        pytest.skip('animation-step never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='animation-step-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
