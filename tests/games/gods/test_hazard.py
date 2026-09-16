"""The hazard tick (014084): a grid-gated pool spawn, or a tile-array paint, over a caller-supplied object.

No frame at all -- D4/D5/A0/A1/A2 are live scratch the routine never
saves.  'paint' (inactive, or an active object whose grid cell is not 1)
and 'spawn' (active, grid cell 1, whether or not the pool has a free
slot) are recovered; 'trigger' (the pool scan's own rare gate, keyed by a
byte in a parallel table and a counter) calls an unrecovered routine and
is declined even though witnessed.  Three tiers as for the other leaves;
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
from gods_sega.game import hazard
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-014084-fresh*/014084-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 014084')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

OBJECT, PENDING = 0xFF9000, 0xFF9100


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def _world(active=1, cell_value=1, **overrides):
    values = {
        (OBJECT + hazard.ACTIVE_FLAG, 1): active,
        (hazard.OBJECT_X, 2): 0, (hazard.OBJECT_Y, 2): 0,
        (PENDING + 1, 1): 0x42,
        (hazard.TRIGGER_COUNTER, 2): 0,
        (hazard.POOL_COUNTER, 2): 5,
    }
    values.update(overrides)
    cell, _ = hazard._cell_address(_reader(values), 0x100, 0x80)
    values[(cell & 0xFFFFFF, 1)] = cell_value
    values[((cell + hazard.TYPE_TABLE_OFFSET) & 0xFFFFFF, 1)] = 0
    for index in range(hazard.POOL_COUNT):
        values[(hazard.POOL_BASE + hazard.POOL_STRIDE * index, 2)] = 0    # occupied by default
    return values


def test_inactive_falls_straight_to_paint():
    values = _world(active=0)
    result = hazard.hazard_tick(_reader(values), OBJECT, PENDING, 0x100, 0x80)
    assert result['arm'] == 'paint'


def test_a_mismatched_grid_cell_also_falls_to_paint():
    values = _world(cell_value=2)
    result = hazard.hazard_tick(_reader(values), OBJECT, PENDING, 0x100, 0x80)
    assert result['arm'] == 'paint'


def test_a_matched_cell_spawns_and_fills_the_first_free_pool_slot():
    values = _world(cell_value=1)
    values[(hazard.POOL_BASE + 3 * hazard.POOL_STRIDE, 2)] = 0xFFFF   # the fourth entry is free
    result = hazard.hazard_tick(_reader(values), OBJECT, PENDING, 0x100, 0x80)
    assert result['arm'] == 'spawn' and result['slot'] == hazard.POOL_BASE + 3 * hazard.POOL_STRIDE
    assert result['stores'][hazard.SOUND_COMMAND & 0xFFFFFF] == (hazard.SOUND_REQUEST, 2)
    assert result['stores'][PENDING & 0xFFFFFF] == (0, 2)
    assert result['stores'][hazard.POOL_COUNTER & 0xFFFFFF] == (6, 2)


def test_a_full_pool_still_clears_the_pending_flag():
    values = _world(cell_value=1)
    result = hazard.hazard_tick(_reader(values), OBJECT, PENDING, 0x100, 0x80)
    assert result['arm'] == 'spawn' and result['slot'] is None
    assert result['stores'][PENDING & 0xFFFFFF] == (0, 2)
    assert hazard.POOL_BASE not in result['stores']


def test_the_trigger_arm_is_declined():
    values = _world(cell_value=1)
    cell, _ = hazard._cell_address(_reader(values), 0x100, 0x80)
    values[(cell + hazard.TYPE_TABLE_OFFSET) & 0xFFFFFF, 1] = hazard.TRIGGER_TYPE
    values[(hazard.TRIGGER_COUNTER, 2)] = 2
    result = hazard.hazard_tick(_reader(values), OBJECT, PENDING, 0x100, 0x80)
    assert result['arm'] == 'trigger'


def test_paint_is_clamped_to_the_tile_array_bounds():
    values = _world(active=0)
    result = hazard.hazard_tick(_reader(values), OBJECT, PENDING, 0x8000, 0x8000)  # far outside
    assert result['arm'] == 'paint' and not result['painted'] and result['stores'] == {}


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.HAZARD_TICK_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        a1, a3 = registers['a1'] & 0xFFFFFF, registers['a3'] & 0xFFFFFF
        d0, d1 = registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF
        result = hazard.hazard_tick(boundary._reader(machine), a1, a3, d0, d1)
        if result['arm'] == 'trigger':
            with pytest.raises(boundary.UnsupportedCandidate, match='trigger'):
                boundary.hazard_tick_plan(machine, registers)
            return
        plan = boundary.hazard_tick_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('hazard-tick').gate_pcs == (boundary.HAZARD_TICK_ENTRY,)
    assert boundary.HAZARD_TICK_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('hazard-tick-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='hazard-tick',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('hazard-tick never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='hazard-tick-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
