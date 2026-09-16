"""The sixth recovered Gods region: the grid cell lookup (0063FA).

The simplest shape: one straight-line path, no writes, no branch, called
from three sites.  Three tiers: the pure semantics on synthetic reads; the
boundary plan against the tracer's facts on every state the census
retained (a single path class over four recordings); the candidate over
real frames against the reference of the last PASS cold run, with its
negative control (a register, since the routine stores nothing) diverging.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import grid
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0063FA*/0063FA-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0063FA')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    return lambda address, size: values[(address, size)]


def test_the_column_shifts_arithmetically_and_the_row_masks_then_shifts():
    result = grid.grid_cell(_reader({(grid.GRID_X, 2): 0x00E4, (grid.GRID_Y, 2): 0x0200}))
    assert result['d0'] == 0x0007 and result['d1'] == 0x1000
    assert result['address'] == (grid.GRID_TABLE + 0x0007 + 0x1000) & 0xFFFFFFFF


def test_a_negative_x_shifts_toward_negative_infinity():
    result = grid.grid_cell(_reader({(grid.GRID_X, 2): 0xFF00, (grid.GRID_Y, 2): 0x0000}))
    assert result['d0'] == 0xFFF8            # -256 >> 5 == -8, not -7


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.GRID_CELL_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.grid_cell_plan(machine, machine.registers())
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['interrupts_during_trace'] == 0


def test_candidate_names_are_explicit():
    assert recovery.Candidate('grid-cell').gate_pcs == (boundary.GRID_CELL_ENTRY,)
    assert boundary.GRID_CELL_ENTRY in recovery.Candidate('camera-sprites').gate_pcs   # the combined candidate grows with every leaf
    assert recovery.Candidate('grid-cell-mutant-result').mutation is recovery._mutate_address


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='grid-cell',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] > 0 and report['fallbacks'] == 0
    # The control is the cell address the caller dereferences (a0 one cell off): it is seen on the
    # first frame.  The earlier d0 control was only architectural residue caught by the mid-frame
    # observation instant; once the instant moved to the idle window it passed, blind.
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='grid-cell-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE', mutant
    assert mutant['first_difference']['frame'] == 6001
