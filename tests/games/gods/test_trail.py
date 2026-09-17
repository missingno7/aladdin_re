"""0044C0/004550: the trail check (event kind 6, `game.trail`).  A caller-register-free leaf: the
current position against up to six recorded slots, in order, stopping at the first box that
contains it ('found', 891 of 903 occurrences on the main history alone, `--classifier entry`, 18
Sep).  'exhausted' (no slot matches) is real ROM code this module does not model (the ring shift,
the counter, the 007B4C call) and declines.  Three tiers: unit tests against synthetic reads, the
standalone plan (`trail_check_plan`) checked against every retained fixture, and `player_tail_plan`'s
own composition (covered by `test_player_tail.py`, which already exercises every kind-6 fixture the
tail's own census retains).
"""
from pathlib import Path

import pytest
import pathfacts

from genesis_re.machine import Machine
from gods_sega import boundary
from gods_sega.game import player, trail
from gods_sega.profile import GODS

FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0044C0*/0044C0-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0044C0')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def _slot(index, x, y):
    address = (trail.TRAIL_HISTORY + trail.TRAIL_HISTORY_STRIDE * index) & 0xFFFFFF
    return {(address, 2): x & 0xFFFF, (address + 2, 2): y & 0xFFFF}


def test_a_slot_whose_box_contains_the_position_stops_the_scan_immediately():
    values = _slot(0, 0x100, 0x200)
    result = trail.trail_check(_reader(values), 0x100, 0x200)
    assert result['arm'] == 'found' and result['slot'] == 0 and len(result['checks']) == 1
    assert result['checks'][0]['hit']


def test_a_miss_advances_to_the_next_slot_and_a_later_slot_can_still_be_found():
    values = {}
    values.update(_slot(0, 0x1000, 0x1000))   # far away: misses every axis
    values.update(_slot(1, 0x100, 0x200))     # contains the position
    result = trail.trail_check(_reader(values), 0x100, 0x200)
    assert result['arm'] == 'found' and result['slot'] == 1
    assert len(result['checks']) == 2 and not result['checks'][0]['hit'] and result['checks'][1]['hit']
    assert result['checks'][0]['fail_at'] is not None


def test_all_six_slots_missing_is_exhausted():
    values = {}
    for index in range(trail.TRAIL_HISTORY_SLOTS):
        values.update(_slot(index, 0x1000 + index, 0x1000 + index))
    result = trail.trail_check(_reader(values), 0x100, 0x200)
    assert result['arm'] == 'exhausted' and len(result['checks']) == trail.TRAIL_HISTORY_SLOTS
    assert all(not c['hit'] for c in result['checks'])


def test_the_box_margin_is_inclusive_on_every_edge():
    values = _slot(0, 0x100, 0x100)
    read = _reader(values)
    for x, y in ((0x100 - trail.TRAIL_BOX_MARGIN, 0x100), (0x100 + trail.TRAIL_BOX_MARGIN, 0x100),
                (0x100, 0x100 - trail.TRAIL_BOX_MARGIN), (0x100, 0x100 + trail.TRAIL_BOX_MARGIN)):
        assert trail.trail_check(read, x, y)['arm'] == 'found'
    just_outside = trail.trail_check(read, 0x100 - trail.TRAIL_BOX_MARGIN - 1, 0x100)
    assert just_outside['arm'] == 'exhausted'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_trail_check_plan_reproduces_every_fact_of_the_original_or_declines_exhaustion(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.TRAIL_CHECK_ENTRY
        read = boundary._reader(machine)
        result = trail.trail_check(read, read(player.POSITION_X, 2), read(player.POSITION_Y, 2))
        try:
            plan = boundary.trail_check_plan(machine, registers)
        except boundary.UnsupportedCandidate as error:
            assert result['arm'] == 'exhausted' and '007B4C' in str(error)
            return
    assert result['arm'] == 'found'
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_wired():
    from gods_sega import recovery
    assert boundary.TRAIL_CHECK_ENTRY in recovery.PLANNERS['trail-check']
    assert recovery.PLANNERS['trail-check'][boundary.TRAIL_CHECK_ENTRY] is boundary.trail_check_plan
    assert boundary.TRAIL_CHECK_ENTRY in recovery.PLANNERS['camera-sprites']
    assert 'trail-check-mutant-result' in recovery.MUTATIONS
