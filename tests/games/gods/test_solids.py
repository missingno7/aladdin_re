"""The solid drawer (00FC8E): one sprite-list append per active solid, the second leaf over 00FDB8's own definition.

Shares the definition struct (A2) and the rows/cells convention with
``00FDB8`` (``stamp_footprint``): the width and height bytes bound the
grid, but this routine draws sprites instead of stamping the level grid,
appending into the same sprite list the emitters use.  Three tiers as for
the other leaves; the evidence tiers skip when the local census or
reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import solids
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00FC8E*/00FC8E-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00FC8E')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

DEFINITION = 0xFF65A2
TABLE = 0x001000                     # a ROM address stands in for the table the pointer resolves to
CAMERA_X, CAMERA_Y = 0, 0
HEAD_VALUE, COUNT_VALUE = 0xFFFFEC00, 3    # the current contents of LIST_HEAD / LIST_COUNT for these tests


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def _world(type_id, tile, width, height, *, entries=None, camera=(CAMERA_X, CAMERA_Y),
           head=HEAD_VALUE, count=COUNT_VALUE):
    entries = entries or [(type_id, tile)]
    values = {
        (solids.SOLID_TILE_TABLE, 4): TABLE,
        (solids.CAMERA_X, 2): camera[0], (solids.CAMERA_Y, 2): camera[1],
        (solids.LIST_HEAD, 4): head, (solids.LIST_COUNT, 2): count,
        (DEFINITION + solids.SOLID_TYPE, 1): type_id,
        (DEFINITION + 0x1A, 1): width, (DEFINITION + 0x1B, 1): height,
    }
    for index, (entry_type, entry_tile) in enumerate(entries):
        values[(TABLE + 2 * index, 2)] = (entry_tile << 8) | (entry_type & 0xFF)
    values[(TABLE + 2 * len(entries), 2)] = 0     # the terminator past the declared entries
    return values


def test_a_one_cell_solid_appends_one_record_and_advances_the_list():
    result = solids.draw_solid(_reader(_world(0x05, 0x09, 0x00, 0x00)), 0x0140, 0x0030, DEFINITION)
    assert (result['arm'], result['rows'], result['cells'], result['visible']) == ('sprite', 1, 1, 1)
    assert result['tile'] == 0x09 and result['scanned'] == 1
    assert result['final_head'] == HEAD_VALUE + solids.RECORD_SIZE
    record = HEAD_VALUE & 0xFFFFFF
    assert result['stores'] == {
        solids.LIST_LAST: (HEAD_VALUE, 4),
        record: (0x0030 + solids.POSITION_BIAS, 2),
        record + 2: ((COUNT_VALUE | solids.CELL_ATTRIBUTE) & 0xFFFF, 2),
        record + 4: (0x09, 2),
        record + 6: (0x0140 + solids.POSITION_BIAS, 2),
        solids.LIST_COUNT: (COUNT_VALUE + 1, 2),
        solids.LIST_HEAD: (HEAD_VALUE + solids.RECORD_SIZE, 4),
    }


def test_the_table_scan_advances_past_a_mismatch_and_stops_at_the_first_match():
    result = solids.draw_solid(_reader(_world(0x61, 0x09, 0, 0, entries=[(0x4C, 1), (0x61, 9)])), 0, 0, DEFINITION)
    assert result['scanned'] == 2 and result['tile'] == 9


def test_an_unterminated_or_unmatched_scan_is_reported_not_looped_forever():
    values = _world(0x61, 0x09, 0, 0, entries=[(0x01, 1)])
    del values[(TABLE + 2, 2)]           # no terminator either: the scan must still stop
    result = solids.draw_solid(_reader(values), 0, 0, DEFINITION)
    assert result['arm'] in ('unmatched', 'unbounded')


def test_a_negative_tile_index_is_the_upload_arm_and_a_negative_height_wraps():
    result = solids.draw_solid(_reader(_world(0x05, 0x80, 0, 0)), 0, 0, DEFINITION)
    assert result['arm'] == 'upload'
    result = solids.draw_solid(_reader(_world(0x05, 0x09, 0, 0xFF)), 0, 0, DEFINITION)
    assert result['arm'] == 'wrap'


def test_width_and_height_bytes_bound_the_grid_like_the_footprint_stamp():
    result = solids.draw_solid(_reader(_world(0x05, 0x09, 0x02, 0x01)), 0, 0, DEFINITION)
    assert (result['rows'], result['cells']) == (2, 3)


def test_an_off_screen_cell_is_skipped_but_still_advances_the_grid():
    # Far to the right: the x test fails, no record, no list movement.
    result = solids.draw_solid(_reader(_world(0x05, 0x09, 0, 0)), 0x0400, 0x0030, DEFINITION)
    assert result['arm'] == 'sprite' and result['visible'] == 0 and result['x_skips'] == 1 and result['y_skips'] == 0
    assert result['stores'] == {solids.LIST_HEAD: (HEAD_VALUE, 4)}
    # Far below: the x test passes, the y test fails.
    result = solids.draw_solid(_reader(_world(0x05, 0x09, 0, 0)), 0x0140, 0x0400, DEFINITION)
    assert result['visible'] == 0 and result['x_skips'] == 0 and result['y_skips'] == 1


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.SOLID_DRAW_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.draw_solid_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


@needs_census
def test_an_unwitnessed_arm_is_declined_and_the_original_runs_it():
    # The height byte lives in the definition (work RAM), unlike the tile table (ROM): poison it
    # negative to force the 'wrap' arm, which no recording enters.
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.SOLID_DRAW_ENTRY
        definition = registers['a2'] & 0xFFFFFF
        height_address = (definition + 0x1B) & 0xFFFF
        machine.gates([registers['pc']])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=registers['pc'],
                              writes=[(0xFF0000 | height_address, 0xFF)], registers=registers)
        with pytest.raises(boundary.UnsupportedCandidate, match='not witnessed'):
            boundary.draw_solid_plan(machine, machine.registers())
        candidate = recovery.Candidate('solid-draw')
        candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000) is False
        assert candidate.stats['fallbacks'] == 1 and candidate.stats['candidate_hits'] == 0


def test_candidate_names_are_explicit():
    assert recovery.Candidate('solid-draw').gate_pcs == (boundary.SOLID_DRAW_ENTRY,)
    assert boundary.SOLID_DRAW_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('solid-draw-mutant-result').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='solid-draw',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= {'scheduler admission', 'unsupported domain'}
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='solid-draw-mutant-result', reference=EVIDENCE)
    if mutant['candidate_hits'] == 0:
        pytest.skip('solid-draw never hits in this window; nothing for the mutant to diverge from')
    assert mutant['status'] == 'DIVERGENCE'
