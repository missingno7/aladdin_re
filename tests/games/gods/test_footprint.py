"""The footprint stamp (00FDB8): a solid's cells set in the level grid, their old bytes queued for undo.

The first Gods leaf over a caller-supplied record: the definition in A2
(its width and height bytes bound the two loops), the undo cursor in A5,
the world position in D0/D1.  Three tiers as for the other leaves; the
evidence tiers skip when the local census or reference artifacts are
absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00FDB8*/00FDB8-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00FDB8')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

DEFINITION, CURSOR = 0xFF65DA, 0xFFFF4982


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def _world(width, height, cells=()):
    values = {(DEFINITION + grid.FOOTPRINT_WIDTH, 1): width, (DEFINITION + grid.FOOTPRINT_HEIGHT, 1): height}
    values.update({(address, 1): value for address, value in dict(cells).items()})
    return values


def test_a_one_cell_solid_marks_its_cell_and_queues_the_old_byte():
    result = grid.stamp_footprint(_reader(_world(0, 0, {0xFF89F8: 0x07})), 0x0340, 0x0030, DEFINITION, CURSOR)
    assert (result['arm'], result['rows'], result['cells']) == ('stamp', 1, 1)
    assert result['first_row'] == 0xFFFF89F8 and result['row_after'] == 0xFFFF8A78 and result['cursor'] == CURSOR + 6
    assert result['stores'] == {0xFF4982: (0xFFFF89F8, 4), 0xFF4986: (0, 1), 0xFF4987: (0x07, 1), 0xFF89F8: (1, 1)}
    assert (result['column'], result['row'], result['row_source']) == (0x1A, 0x180, 0x30)


def test_width_and_height_bytes_bound_the_cells_and_rows_and_the_bias_and_signs_follow_the_shifts():
    result = grid.stamp_footprint(_reader(_world(0x02, 0x01)), 0x0000, 0x0000, DEFINITION, CURSOR)
    assert (result['rows'], result['cells']) == (2, 3) and len(result['stores']) == 6 * 4
    assert sorted(a for a, (v, s) in result['stores'].items() if s == 1 and v == 1) == [0xFF885E, 0xFF885F, 0xFF8860,
                                                                                         0xFF88DE, 0xFF88DF, 0xFF88E0]
    # x = -17 (the 16-pixel bias makes -1): asr.w #5 rounds toward minus infinity, and adda.w sign-extends.
    behind = grid.stamp_footprint(_reader(_world(0, 0)), 0xFFEF, 0x0000, DEFINITION, CURSOR)
    assert behind['column'] == 0xFFFF and behind['first_row'] == 0xFFFF885D
    # Bit 7 of the width byte: no footprint at all.
    assert grid.stamp_footprint(_reader(_world(0x80, 0)), 0, 0, DEFINITION, CURSOR)['arm'] == 'none'
    # A negative height byte is reported, not looped over.
    assert grid.stamp_footprint(_reader(_world(0, 0xFF)), 0, 0, DEFINITION, CURSOR)['height'] == -1


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.FOOTPRINT_STAMP_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.footprint_stamp_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


@needs_census
def test_unwitnessed_arms_are_declined_and_the_original_runs_them():
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.FOOTPRINT_STAMP_ENTRY
        width = (registers['a2'] & 0xFFFF) + grid.FOOTPRINT_WIDTH
        original = machine.peek_ram(width, 1)[0]
        machine.gates([registers['pc']])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=registers['pc'],
                              writes=[(0xFF0000 | width, original | grid.NO_FOOTPRINT)], registers=registers)
        with pytest.raises(boundary.UnsupportedCandidate, match='no-footprint arm'):
            boundary.footprint_stamp_plan(machine, machine.registers())
        candidate = recovery.Candidate('footprint')
        candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000) is False
        assert candidate.stats['fallbacks'] == 1 and candidate.stats['candidate_hits'] == 0
        assert machine.info['pc'] == 0x00FDBE     # the original executed the entry instruction


def test_candidate_names_are_explicit():
    assert recovery.Candidate('footprint').gate_pcs == (boundary.FOOTPRINT_STAMP_ENTRY,)
    assert boundary.FOOTPRINT_STAMP_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('footprint-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='footprint',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] >= 60 and set(report['fallback_reasons']) <= {'scheduler admission'}
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='footprint-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE' and mutant['first_difference']['frame'] <= 6002
