"""00722C: the 200-entry box-overlap scan states 0 and 1 both call.  Real ROM code, structurally
recoverable (RAM-only, bounded, no calls) -- but its own result is discarded at BOTH witnessed call
sites (game.movement's own module docstring), so it has no mutant the game can see yet, the same
reason tile_trigger_scan (00773A) is not its own gated candidate: it waits to be composed into
whichever of states 0/1 is recovered first.  Two tiers only, matching that precedent: unit tests
against synthetic reads, and the plan checked against every retained fixture.
"""
from pathlib import Path

import pytest
import pathfacts

from genesis_re.machine import Machine
from gods_sega import boundary
from gods_sega.game import movement
from gods_sega.profile import GODS

FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00722C-entry*/00722C-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00722C')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def _world(overrides=None):
    values = {}
    for index in range(movement.BOX_SCAN_COUNT):
        entry = (movement.BOX_SCAN_TABLE + movement.BOX_SCAN_STRIDE * index) & 0xFFFFFF
        values[(entry + movement.BOX_SCAN_STATUS_A, 2)] = 0xFFFF   # negative: every entry skipped by default
    values.update(overrides or {})
    return values


def test_every_entry_skipped_scans_all_two_hundred_and_reports_not_found():
    from gods_sega.game.grid import GRID_X, GRID_Y
    values = _world({(GRID_X & 0xFFFFFF, 2): 0, (GRID_Y & 0xFFFFFF, 2): 0})
    result = movement.box_overlap_scan(_reader(values))
    assert result['arm'] == 'not-found' and len(result['entries']) == movement.BOX_SCAN_COUNT
    assert all(e['arm'] == 'skip-negative' for e in result['entries'])
    assert result['player_x'] == movement.BOX_SCAN_PLAYER_X_MARGIN
    assert result['player_y'] == movement.BOX_SCAN_PLAYER_Y_MARGIN


def test_a_zero_status_b_also_skips_the_entry():
    from gods_sega.game.grid import GRID_X, GRID_Y
    entry = movement.BOX_SCAN_TABLE & 0xFFFFFF
    values = _world({(GRID_X & 0xFFFFFF, 2): 0, (GRID_Y & 0xFFFFFF, 2): 0,
                     (entry + movement.BOX_SCAN_STATUS_A, 2): 0, (entry + movement.BOX_SCAN_STATUS_B, 2): 0})
    result = movement.box_overlap_scan(_reader(values))
    assert result['entries'][0]['arm'] == 'skip-zero'


def test_an_entry_whose_box_contains_the_player_position_stops_the_scan_early():
    from gods_sega.game.grid import GRID_X, GRID_Y
    entry_addr = (movement.BOX_SCAN_TABLE + movement.BOX_SCAN_STRIDE * 5) & 0xFFFFFF
    values = _world({(GRID_X & 0xFFFFFF, 2): 0, (GRID_Y & 0xFFFFFF, 2): 0,
                     (entry_addr + movement.BOX_SCAN_STATUS_A, 2): 0, (entry_addr + movement.BOX_SCAN_STATUS_B, 2): 1,
                     (entry_addr, 2): movement.BOX_SCAN_PLAYER_X_MARGIN,
                     (entry_addr + 2, 2): movement.BOX_SCAN_PLAYER_Y_MARGIN})
    result = movement.box_overlap_scan(_reader(values))
    assert result['arm'] == 'found' and len(result['entries']) == 6   # indices 0-4 skipped, 5 found
    assert result['found']['index'] == 5 and (result['found']['entry'] & 0xFFFFFF) == entry_addr


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_box_overlap_scan_plan_reproduces_every_fact_of_the_original(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.box_overlap_scan_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc
