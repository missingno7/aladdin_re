"""012C80: the pickup award group dispatch, with its own chain (012D30/012A3E/012A34/011468)
(`docs/gods/blockers/2026-09-19-003186.md`'s own Decision, the last bite in its order).  Bumps an
already-tracked item's own contact record (`game.pickups.ITEM_RECORDS`) or registers a newly-tracked
one into one of the three `GROUP_TABLES`, either way recomputing TIME_MARK from the currently active
groups.  Three tiers as for the other leaves; the evidence tiers skip when the local census or
reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import pickups
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X012C80-*/012C80-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 012C80')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def _world(active0=-1, active1=-1, active2=-1):
    values = {(pickups.GROUP_TABLES[0] & 0xFFFFFF, 2): active0 & 0xFFFF,
             (pickups.GROUP_TABLES[1] & 0xFFFFFF, 2): active1 & 0xFFFF,
             (pickups.GROUP_TABLES[2] & 0xFFFFFF, 2): active2 & 0xFFFF}
    for item_id in range(pickups.ITEM_RECORD_COUNT):
        record = 0x1000 + 0x50 * item_id
        values[(pickups.ITEM_RECORDS + 4 * item_id, 4)] = record
        values[((record + pickups.ITEM_RANGE_LOW) & 0xFFFFFF, 2)] = 1
        values[((record + pickups.ITEM_VALUE) & 0xFFFFFF, 2)] = 1
    values[(pickups.SPECIAL_TIMER & 0xFFFFFF, 2)] = 0xFFFF   # negative: the witnessed arm
    return values


def test_an_already_active_item_bumps_its_own_value_and_recomputes_time_mark():
    result = pickups.award_group_dispatch(_reader(_world(active0=3)), 3)
    assert result['arm'] == 'already-active' and result['matched'] == 0
    record = 0x1000 + 0x50 * 3
    assert result['stores'][(record + pickups.ITEM_VALUE) & 0xFFFFFF] == (2, 2)
    # the tally re-reads ITEM_VALUE AFTER this activation's own increment (1 -> 2): range_low=1,
    # value=2, so the group's own contribution is two steps of range_low (1+1), not one.
    assert result['tally']['stores'][pickups.TIME_MARK & 0xFFFFFF] == (2, 2)


def test_a_new_item_registers_into_the_first_free_group():
    result = pickups.award_group_dispatch(_reader(_world()), 5)
    assert result['arm'] == 'register' and result['group'] == 0 and result['group_arm'] == 'group0'
    assert result['stores'][pickups.GROUP_TABLES[0] & 0xFFFFFF] == (5, 2)


def test_item_id_2_always_overrides_to_group_2():
    result = pickups.award_group_dispatch(_reader(_world()), 2)
    assert result['arm'] == 'register' and result['group'] == 2 and result['group_arm'] == 'override'
    assert result['stores'][pickups.CONTACT_POOL_INDEX_BASE & 0xFFFFFF] == (pickups.GROUP_OVERRIDE_POOL_BASE, 2)


def test_the_contested_and_generic_group2_arms_and_a_non_negative_leading_recheck_are_unrecovered():
    # every group already holds a different item and the item's own record word is nonzero: 'contested'
    values = _world(active0=9, active1=8, active2=7)
    values[(0x1000 + 0x50 * 5, 2)] = 1   # item 5's own record[0] nonzero -- group 0 is not the free-record shortcut
    result = pickups.award_group_dispatch(_reader(values), 5)
    assert result['arm'] == 'unrecovered-contested'
    # SPECIAL_TIMER non-negative: leading_group_recheck's own declined arm
    values2 = _world()
    values2[(pickups.SPECIAL_TIMER & 0xFFFFFF, 2)] = 1
    result2 = pickups.award_group_dispatch(_reader(values2), 5)
    assert result2['arm'] == 'unrecovered-leading-group'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.PICKUP_AWARD_GROUP_ENTRY
        from genesis_re.seam import UnsupportedCandidate
        try:
            plan = boundary.pickup_award_group_plan(machine, registers)
        except UnsupportedCandidate:
            pytest.skip('a real, unwitnessed arm (see test_pickup_award_group.py declines)')
            return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('pickup-award-group').gate_pcs == (boundary.PICKUP_AWARD_GROUP_ENTRY,)
    # Retired from camera-sprites 20 September: its only real caller is OBJECT_ACTIVITY_GATE_ENTRY's
    # own '>= 0xC0' arm (docs/gods/blockers/2026-09-19-003480.md's own Progress notes) -- now that
    # object_activity_gate_plan is armed there and composes it internally, the native machine never
    # independently reaches 012C80 as a gate hit.  This candidate's own PLANNERS entry is unchanged.
    assert boundary.PICKUP_AWARD_GROUP_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.OBJECT_ACTIVITY_GATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('pickup-award-group-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_pickup_award_group_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='pickup-award-group', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 012C80 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='pickup-award-group-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
