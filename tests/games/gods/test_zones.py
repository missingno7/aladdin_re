"""The zone check (00BCCE): a box test around the player's own position, fully witnessed -- no declines.

'held' (a global flag's sign bit set) skips the whole test.  Otherwise a
box is built around the player's position (widened on two levels) and
tested against the caller's position; 'outside' leaves nothing behind
(all eight registers the routine touches are restored from its own
save/restore frame -- the whole box arithmetic is scratch).  'inside'
additionally decrements a shared cooldown (unless suppressed) and may
set D2 to -1.  Three tiers as for the other leaves; the evidence tiers
skip when the local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import zones
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00BCCE-fresh*/00BCCE-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00BCCE')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def _world(overrides=None):
    values = {
        (zones.HOLD_FLAG, 2): 0, (zones.GRID_X, 2): 0, (zones.GRID_Y, 2): 0,
        (zones.LEVEL_NUMBER, 2): 0, (zones.HALF_WIDTH, 2): 0, (zones.HALF_HEIGHT, 2): 0,
        (zones.SUPPRESS_COOLDOWN, 2): 0, (zones.COOLDOWN, 2): 0, (zones.RESULT_FLAG, 2): 1,
    }
    values.update(overrides or {})
    return values


def test_the_hold_flag_skips_the_whole_test():
    values = _world({(zones.HOLD_FLAG, 2): 0x8000})
    assert zones.zone_check(_reader(values), 0, 0, 0)['arm'] == 'held'


def test_a_position_inside_the_box_is_inside_and_outside_it_is_outside():
    # near_x=0xA, far_x=0x16 (no half-extent widening): d0=0x10 is inside.
    values = _world()
    result = zones.zone_check(_reader(values), 0x10, 0x8, 0)
    assert result['arm'] == 'inside'
    result = zones.zone_check(_reader(values), 0x100, 0x8, 0)
    assert result['arm'] == 'outside' and result['fail'] == 'x_far'


def test_the_box_widens_on_the_two_special_levels():
    # near_y=0x8, far_y=0x26 normally; +0x14 more on levels 0x12-0x13.
    values = _world({(zones.LEVEL_NUMBER, 2): 0x12})
    result = zones.zone_check(_reader(values), 0x10, 0x38, 0)   # inside only with the widened box
    assert result['arm'] == 'inside'
    values[(zones.LEVEL_NUMBER, 2)] = 0x14
    result = zones.zone_check(_reader(values), 0x10, 0x38, 0)
    assert result['arm'] == 'outside' and result['fail'] == 'y_far'


def test_inside_decrements_the_cooldown_unless_suppressed_and_sets_d2_unless_flagged():
    values = _world()
    result = zones.zone_check(_reader(values), 0x10, 0x8, 0)
    assert result['stores'] == {zones.COOLDOWN & 0xFFFFFF: ((0 - result['scale']) & 0xFFFF, 2)}
    assert result['new_d2'] is None      # RESULT_FLAG is 1 by default in _world()
    values[(zones.RESULT_FLAG, 2)] = 0
    result = zones.zone_check(_reader(values), 0x10, 0x8, 0)
    assert result['new_d2'] == 0xFFFFFFFF
    values[(zones.SUPPRESS_COOLDOWN, 2)] = 1
    result = zones.zone_check(_reader(values), 0x10, 0x8, 0)
    assert result['stores'] == {}


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.ZONE_CHECK_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.zone_check_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('zone-check').gate_pcs == (boundary.ZONE_CHECK_ENTRY,)
    assert boundary.ZONE_CHECK_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('zone-check-mutant-result').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='zone-check',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('zone-check never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='zone-check-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
