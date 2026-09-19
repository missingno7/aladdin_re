"""003480: the object activity gate (`docs/gods/blockers/2026-09-19-003480.md`), composing the
bounds-check head, the achievements.RECORD_TABLE dispatch, and the pickup-award (012C80),
sound-request (the 005958 table's own admitted handlers + 002F2E) and record-status-one (00354C,
game/test_record_status_one.py) arms as real internal jsr/bsr calls, the same "virtual park"
technique spawn_puff_box_plan already proves. 00354C's own table-match ('found') sub-arm and 005958
indices 4/6/17/18 (each its own real, unrecovered complexity) decline by name. Three tiers as for
the other leaves; the evidence tiers skip when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify
from factcheck import perturb_upper_halves

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import world
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X003480-*/003480-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 003480')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_bypass_arm_skips_the_box_test_entirely():
    result = world.object_activity_gate(_reader({(world.CAMERA_GATE_BYPASS & 0xFFFFFF, 2): 0xFFFF}), 0x1000, 0, 0)
    assert result['arm'] == 'bypass' and result['stores'] == {}


def test_box_miss_on_each_of_the_four_edges():
    base = {(world.CAMERA_GATE_BYPASS & 0xFFFFFF, 2): 0,
           (world.CAMERA_GATE_X & 0xFFFFFF, 2): 0x100, (world.CAMERA_GATE_Y & 0xFFFFFF, 2): 0x100}
    # camera_x=0x100 -> x_low=0xFC, x_high=0x124; camera_y=0x100 -> y_low=0xFC, y_high=0x134
    assert world.object_activity_gate(_reader(base), 0, 0xF0, 0x100)['arm'] == 'box-miss'      # x < x_low
    assert world.object_activity_gate(_reader(base), 0, 0x120, 0x100)['arm'] == 'box-miss'     # x > x_high
    assert world.object_activity_gate(_reader(base), 0, 0x100, 0xF0)['arm'] == 'box-miss'      # y < y_low
    assert world.object_activity_gate(_reader(base), 0, 0x100, 0x130)['arm'] == 'box-miss'     # y > y_high


def _in_box(status):
    return {(world.CAMERA_GATE_BYPASS & 0xFFFFFF, 2): 0,
           (world.CAMERA_GATE_X & 0xFFFFFF, 2): 0, (world.CAMERA_GATE_Y & 0xFFFFFF, 2): 0,
           ((0x2000 + world.OBJECT_STATUS_OFFSET) & 0xFFFFFF, 2): status}


def test_pickup_award_arm_when_status_is_at_or_above_the_threshold():
    status = world.PICKUP_AWARD_GROUP_THRESHOLD + 5
    result = world.object_activity_gate(_reader(_in_box(status)), 0x2000, 0, 0)
    assert result['arm'] == 'pickup-award' and result['item_id'] == 5
    assert result['stores'][(0x2000 + world.OBJECT_STATUS_OFFSET) & 0xFFFFFF] == (0xFFFF, 2)
    assert result['stores'][(0x2000 + world.OBJECT_TEMPLATE_OFFSET) & 0xFFFFFF] == (0, 2)


def test_record_status_fail_when_the_matched_record_status_exceeds_one():
    from gods_sega.game.achievements import _record_address
    status = 3
    values = _in_box(status)
    record = _record_address(status)
    values[(record + world.OBJECT_STATUS_OFFSET) & 0xFFFFFF, 2] = 2
    result = world.object_activity_gate(_reader(values), 0x2000, 0, 0)
    assert result['arm'] == 'record-status-fail'
    assert result['stores'][world.GATE_FIELD_WORD & 0xFFFFFF] == (status, 2)


def test_record_status_one_hands_off_to_the_sub_dispatch_with_f3f2_stored():
    from gods_sega.game.achievements import _record_address
    status = 3
    values = _in_box(status)
    record = _record_address(status)
    values[(record + world.OBJECT_STATUS_OFFSET) & 0xFFFFFF, 2] = 1
    result = world.object_activity_gate(_reader(values), 0x2000, 0, 0)
    assert result['arm'] == 'record-status-one'
    assert result['stores'][world.GATE_FIELD_WORD & 0xFFFFFF] == (status, 2)


def test_sound_request_arm_when_the_matched_record_status_is_zero_or_negative():
    from gods_sega.game.achievements import _record_address
    status = 3
    values = _in_box(status)
    record = _record_address(status)
    values[(record + world.OBJECT_STATUS_OFFSET) & 0xFFFFFF, 2] = 0
    result = world.object_activity_gate(_reader(values), 0x2000, 0, 0)
    assert result['arm'] == 'sound-request' and result['kind_count_status'] == status
    assert result['stores'][world.GATE_FIELD_WORD & 0xFFFFFF] == (status, 2)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_and_declines_the_rest(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.OBJECT_ACTIVITY_GATE_ENTRY
        # A DECLINE may be object_activity_gate_plan's own (the 0x354C sub-dispatch, an unrecovered
        # 005958 index) or may propagate uncaught from a virtual-parked composed leaf's own decline
        # (pickup_award_group_plan's own unwitnessed arms included) -- either is a legitimate named
        # decline, the same "just catch it" shape creature_family_plan's own composed-leaf test uses.
        try:
            plan = boundary.object_activity_gate_plan(machine, registers)
        except UnsupportedCandidate:
            return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], (fixture, problems)
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_under_perturbed_upper_halves(fixture):
    # "movem.w (a7)+,d0-d2" (the box test's own D0-D2 restore, every non-bypass exit) sign-extends
    # each pushed WORD back into a full 32-bit register rather than restoring the caller's own
    # original upper half -- a real defect the first factcheck run caught: exit D0-D2 held the
    # entry's own 5A5A garbage instead of the sign-extended residue.  perturb_upper_halves builds a
    # real machine snapshot with every data register's upper word set to 0x5A5A and re-traces the
    # ORIGINAL hardware from it, the same instrument `factcheck.py check --perturb-upper-halves` uses.
    state = perturb_upper_halves(GODS, fixture.read_bytes())
    if state is None:
        pytest.skip('the adapter refused the constructed entry (a bank or interrupt guard)')
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.OBJECT_ACTIVITY_GATE_ENTRY
        try:
            plan = boundary.object_activity_gate_plan(machine, registers)
        except UnsupportedCandidate:
            return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], (fixture, problems)
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit_and_composes_the_retired_gates():
    assert recovery.Candidate('object-activity-gate').gate_pcs == (boundary.OBJECT_ACTIVITY_GATE_ENTRY,)
    assert boundary.OBJECT_ACTIVITY_GATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    # 012C80/002F2E are retired from camera-sprites now that this composes them internally (their own
    # PLANNERS entries and standalone tests are unchanged -- see test_pickup_award_group.py and
    # test_queue_append.py's own updated test_candidate_name_is_explicit).
    assert boundary.PICKUP_AWARD_GROUP_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.QUEUE_APPEND_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    # The 005958 table's own ten composed handlers stay standalone-only; sound-cue-pair (index 10)
    # too, since it has a second, independent real caller this composition does not cover.
    # 00354C (record-status-one) stays standalone-only too: this composition already reaches it
    # internally.
    for entry_name in ('ACCUMULATOR_0_ENTRY', 'ACCUMULATOR_3_ENTRY', 'ACCUMULATOR_19_ENTRY',
                       'ACCUMULATOR_21_ENTRY', 'SOUND_CUE_PAIR_ENTRY', 'COPY_TABLE_14_ENTRY',
                       'COPY_TABLE_15_ENTRY', 'COPY_TABLE_16_ENTRY', 'HALF_FRAME_COUNTER_ENTRY',
                       'RECORD_ONE_ENTRY'):
        entry = getattr(boundary, entry_name)
        assert entry not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('object-activity-gate-mutant-result').mutation is recovery._mutate_register


@needs_reference
def test_object_activity_gate_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='object-activity-gate', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 003480 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='object-activity-gate-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
