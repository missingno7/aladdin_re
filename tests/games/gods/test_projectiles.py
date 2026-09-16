"""The projectile launch (0091BC): the 20-entry pool's own cold start into the walker's projectile copy.

Called from a still-unidentified site or sites (the retained fixtures'
own `caller_return_slot_at_entry` values land in at least two different
places, not inside `010332`'s own code, on the histories censused so
far) with a starting position and a budget; scans the pool for a free
slot and starts a walk toward the tracked position (the player) with
`game/walker.py`'s projectile copy, taking the budget's own steps
immediately.  The pool exhausted (`0091DE`) is real ROM code no
recording enters: declined.  Fixture tier: every retained class across
four recordings MATCHes.  Segment tier: the candidate over real frames
from a retained fixture against a fresh original, and its mutant
diverging at the launch.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import projectiles, walker
from gods_sega.profile import GODS

FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0091BC*/0091BC-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0091BC')


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def test_the_pool_scan_finds_the_first_free_slot_and_starts_a_walk_toward_the_tracked_position():
    values = {(projectiles.GRID_X, 2): 100, (projectiles.GRID_Y, 2): 50}
    base = projectiles.POOL_BASE & 0xFFFFFF
    for tries in range(3):
        values[(base + projectiles.POOL_STRIDE * tries, 4)] = 0        # occupied (non-negative)
    free = (projectiles.POOL_BASE + projectiles.POOL_STRIDE * 3) & 0xFFFFFFFF
    values[(free & 0xFFFFFF, 4)] = 0xFFFFFFFF
    result = projectiles.launch(_reader(values), 10, 10, 5, 0x03)
    assert result['arm'] == 'launched' and result['tries'] == 3 and result['slot'] == free
    assert result['target'] == (108, 56)                                                # GRID_X+8, GRID_Y+6
    assert result['walk'] == walker.start(10, 10, 108, 56)
    assert result['stores'][(free + projectiles.AUX_BUDGET) & 0xFFFFFF] == (5, 2)
    assert result['stores'][(free + projectiles.AUX_FLAG) & 0xFFFFFF] == (1, 2)         # 0x03 & 1
    assert result['stores'][projectiles.LAUNCHED_FLAG & 0xFFFFFF] == (1, 2)


def test_a_fully_occupied_pool_is_pool_full():
    values = {(projectiles.GRID_X, 2): 0, (projectiles.GRID_Y, 2): 0}
    for tries in range(projectiles.POOL_COUNT):
        values[(projectiles.POOL_BASE + projectiles.POOL_STRIDE * tries, 4)] = 0
    result = projectiles.launch(_reader(values), 0, 0, 1, 0)
    assert result['arm'] == 'pool-full' and result['tries'] == projectiles.POOL_COUNT


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.LAUNCH_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.launch_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc == boundary.LAUNCH_LAST_PC


def test_candidate_names_are_explicit():
    assert recovery.Candidate('projectile-launch').gate_pcs == (boundary.LAUNCH_ENTRY,)
    assert boundary.LAUNCH_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('projectile-launch-mutant-result').mutation is recovery._mutate_launch


@needs_census
def test_candidate_matches_the_original_over_real_frames_and_its_mutant_diverges():
    fixture = FIXTURES[0]
    report = segment_verify.check(fixture, game=GODS, frames=120, candidate='projectile-launch')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    if report['candidate_hits'] == 0:
        pytest.skip('projectile-launch never hits in this window')
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='projectile-launch-mutant-result')
    assert mutant['status'] == 'DIVERGENCE'
