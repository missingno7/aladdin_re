"""The object tile painter (001810): a second sprite-emitter shape, no cache, no sprite-list append.

Called from the object post-process dispatch (`docs/gods/blockers/
2026-09-19-003480.md`'s own reconnaissance) with a world position and the
SAME descriptor id table `game/sprites.py: emit_sprite` uses.  Off-screen
(a 16-pixel margin, not the other emitters' 32) is a plain leaf; on-screen
always uploads fresh (like the particle emitter) but paints directly into
the scrolling background plane at a nametable cell derived from the WORLD
position, never appending to the sprite list.  Three tiers as for the
other leaves; the evidence tiers skip when the local census or reference
artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import sprites
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X001810-*/001810-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 001810')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

DESCRIPTOR_ID = 0x28


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def _world(overrides=()):
    key = (DESCRIPTOR_ID * 2) & 0xFFFF
    values = {
        (sprites.CAMERA_X, 2): 0, (sprites.CAMERA_Y, 2): 0,
        (sprites.DESCRIPTOR_OFFSETS + key, 2): 0x1200,
    }
    values.update(dict(overrides))
    return values


def test_the_screen_margin_rejects_a_tile_before_any_descriptor_or_command_work():
    off_x = sprites.paint_object_tile(_reader(_world()), 0x180, 0, DESCRIPTOR_ID)
    assert off_x['arm'] == 'offscreen-x' and off_x['screen'] == (0x180, 0)
    off_y = sprites.paint_object_tile(_reader(_world()), 0, 0xF1, DESCRIPTOR_ID)
    assert off_y['arm'] == 'offscreen-y' and off_y['screen'] == (0, 0xF1)
    # the limits are inclusive: margin (0x10) + position == the limit still passes
    assert sprites.paint_object_tile(_reader(_world()), 0x150, 0xD0, DESCRIPTOR_ID)['arm'] == 'paint'


def test_a_visible_tile_looks_up_the_same_descriptor_table_emit_sprite_uses():
    result = sprites.paint_object_tile(_reader(_world()), 0x40, 0x30, DESCRIPTOR_ID)
    assert result['arm'] == 'paint'
    assert result['descriptor'] == (sprites.DESCRIPTORS + 0x1200) & 0xFFFFFF


def test_the_command_is_built_from_the_world_position_not_the_screen_position():
    # the SAME world position gives the SAME command regardless of the camera (only the on-screen
    # test is camera-relative; the nametable cell the command addresses is world-tile addressed).
    with_camera = sprites.paint_object_tile(
        _reader(_world({(sprites.CAMERA_X, 2): 0x30, (sprites.CAMERA_Y, 2): 0x10})),
        0x140, 0xB0, DESCRIPTOR_ID)
    without_camera = sprites.paint_object_tile(_reader(_world()), 0x140, 0xB0, DESCRIPTOR_ID)
    assert with_camera['arm'] == without_camera['arm'] == 'paint'
    assert with_camera['command'] == without_camera['command']
    assert without_camera['command'] & 0xC0000000 == 0x40000000   # the VRAM-write command bit always set


def _check_seam(seam, state):
    """The strict witness of a seam: the prefix to the platform entry, the suffix from the resume."""
    facts = pathfacts.trace(state, game=GODS, stop_pc=seam.prefix.registers['pc'])
    problems = [p for p in pathfacts.check_plan(seam.prefix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('prefix', problems)
    resumed = pathfacts.park(state, seam.resume_pc, game=GODS)
    with Machine(GODS.read_rom()) as machine:
        machine.restore(resumed)
        registers = machine.registers()
        assert registers['a7'] == seam.stack_basis
        suffix = seam.suffix(machine, registers)
    facts = pathfacts.trace(resumed, game=GODS, stop_pc=suffix.registers['pc'])
    problems = [p for p in pathfacts.check_plan(suffix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('suffix', problems)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.OBJECT_TILE_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.object_tile_plan(machine, machine.registers())
    if isinstance(plan, boundary.Seam):
        _check_seam(plan, state)
        return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('object-tile').gate_pcs == (boundary.OBJECT_TILE_ENTRY,)
    assert boundary.OBJECT_TILE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('object-tile-mutant-register').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300, candidate='object-tile',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('object-tile never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                  candidate='object-tile-mutant-register', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
