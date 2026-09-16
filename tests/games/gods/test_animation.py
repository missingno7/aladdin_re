"""The animation step (00FE08): the shared frame-budget refresh, once per active solid per tick.

The 'idle' arm (the live record's own moving flag negative) is a plain
leaf.  The 'moving' arm calls the walker's own object-copy resume
(00FFF0, `game/walker.py`) the way 0049DA owns its call into 001164: the
walk's own step arithmetic is the walker's, the surrounding code (the
position store, the completion test, and on completion the next-waypoint
load) is this routine's own.  'moving-continue' (the walk has not finished
as of this call) and 'moving-complete' (it has, and more than one waypoint
remains) are both recovered; 'moving-coldstart' (it has, and at most one
waypoint remains) falls into a per-object-type dispatch (00FEC0/00FF54)
that no recording enters on any of the eight recordings (16 Sep census) and
stays declined, along with a zero budget and a record whose continuation is
not one of the walker's own bodies.  Three tiers as for the other leaves;
the evidence tiers skip when the local census or reference artifacts are
absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import animation, walker
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00FE08*/00FE08-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00FE08')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

RECORD, DEFINITION = 0xFF4AAE, 0xFF65A2
WALKER_RECORD = RECORD + animation.WALKER_RECORD_OFFSET


def _reader(values):
    def read(address, size):
        if (address, size) in values:
            return values[(address, size)]
        # a read wider than a poked entry: assemble it from byte pokes if present, else 0
        total = 0
        for index in range(size):
            total = (total << 8) | values.get((address + index, 1), 0)
        return total
    return read


def _walker_record_values(walk, base=WALKER_RECORD):
    stored = walker.stores(walk, base, 'object')
    values = {}
    for address, (value, size) in stored.items():
        for index in range(size):
            values[(address + index, 1)] = (value >> (8 * (size - index - 1))) & 0xFF
    return values


def test_the_idle_arm_refreshes_the_budget_and_touches_nothing_else():
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0x02, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x80}
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['arm'] == 'idle' and result['budget'] == 3 and result['budget_before'] == 2
    assert result['stores'] == {0xFFF1FE: (3, 2)}


def test_the_definition_index_byte_is_signed_and_the_budget_wraps_like_the_68000():
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0xFF, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x80}
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['arm'] == 'idle'
    assert result['budget_before'] == 0xFFFF and result['budget'] == 0    # -1 + 1


def test_a_moving_arm_with_a_zero_budget_is_declined_rather_than_run_unbounded():
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0xFF, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x01}
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['budget'] == 0 and result['arm'] == 'moving-zero-budget'


def test_a_moving_walk_that_does_not_finish_this_call_is_moving_continue():
    walk = walker.start(0, 0, 100, 1)                                     # a long shallow walk: far from completing
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0x02, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x01}
    values.update(_walker_record_values(walk))
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['arm'] == 'moving-continue'
    assert result['stores'][RECORD] == (result['after'].x, 2) and result['stores'][RECORD + 2] == (result['after'].y, 2)
    assert not (result['after'].counter & 0x8000)


def test_a_completed_walk_with_waypoints_left_loads_the_next_one_and_resets_the_slot():
    walk = walker.start(0, 0, 3, 1)                                       # a short walk: completes within the budget
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0x7F, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x02,
              (RECORD + animation.REMAINING_WAYPOINTS, 1): 0x03, (DEFINITION + 6 + 4, 4): 0x00120034}
    values.update(_walker_record_values(walk))
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['arm'] == 'moving-complete' and result['after'].counter & 0x8000
    assert result['slot'] == 2 and result['index'] == 4
    assert result['stores'][RECORD] == (0x00120034, 4)                    # the waypoint long overwrites x/y together
    assert RECORD + 2 not in result['stores']
    assert result['stores'][RECORD + 5] == (0xFF, 1)                      # the slot byte reset to -1


def test_a_completed_walk_with_one_or_no_waypoint_left_is_moving_coldstart():
    walk = walker.start(0, 0, 3, 1)
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0x7F, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x01,
              (RECORD + animation.REMAINING_WAYPOINTS, 1): 0x01, (DEFINITION + 6, 4): 0}
    values.update(_walker_record_values(walk))
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['arm'] == 'moving-coldstart'


def test_a_record_whose_continuation_is_not_a_walker_body_is_unrecovered():
    values = {(DEFINITION + animation.DEFINITION_INDEX, 1): 0x00, (RECORD + animation.LIVE_MOVING_FLAG, 1): 0x01,
              (WALKER_RECORD, 4): 0x123456}
    result = animation.animation_step(_reader(values), RECORD, DEFINITION)
    assert result['arm'] == 'moving-unrecovered-record'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_and_declines_the_unwitnessed_arms(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.ANIMATION_STEP_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        record, definition = registers['a1'] & 0xFFFFFF, registers['a2'] & 0xFFFFFF
        result = animation.animation_step(boundary._reader(machine), record, definition)
        if result['arm'] in boundary._AS_DECLINED_ARMS:
            with pytest.raises(boundary.UnsupportedCandidate):
                boundary.animation_step_plan(machine, registers)
            return
        plan = boundary.animation_step_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_names_are_explicit():
    assert recovery.Candidate('animation-step').gate_pcs == (boundary.ANIMATION_STEP_ENTRY,)
    assert boundary.ANIMATION_STEP_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('animation-step-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='animation-step',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS | {
        'unsupported domain: animation step arm calls unrecovered 00FEC0/00FF54: moving-coldstart',
        'unsupported domain: animation step arm not witnessed: moving-zero-budget',
        'unsupported domain: animation step arm not witnessed: moving-unrecovered-record'}
    if report['candidate_hits'] == 0:
        pytest.skip('animation-step never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='animation-step-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
