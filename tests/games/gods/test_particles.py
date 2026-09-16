"""The particle drawer's own emitter (00126A): 0018C8's own seam shape, no cache -- every on-screen call uploads.

Called from the particle drawer's jump table (010248) with a world
position and a descriptor byte *offset* (not an id needing a lookup
table, unlike the dynamic and static emitters).  Off-screen is a plain
leaf; on-screen is always a seam (there is no cache to hit).  Three
tiers as for the other leaves; the evidence tiers skip when the local
census or reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00126A-fresh*/00126A-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00126A')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

DESCRIPTOR_OFFSET = 0x120


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def _world(**overrides):
    descriptor = sprites.DESCRIPTORS + DESCRIPTOR_OFFSET
    values = {
        (sprites.CAMERA_X, 2): 0, (sprites.CAMERA_Y, 2): 0,
        (descriptor + sprites.X_OFFSET, 2): 0, (descriptor + sprites.X_OFFSET_FLIPPED, 2): 0,
        (descriptor + sprites.Y_OFFSET, 2): 0, (descriptor + sprites.SIZE_ATTRIBUTE, 2): 0,
        (sprites.LIST_HEAD, 4): 0xFFFFEC00, (sprites.LIST_COUNT, 2): 3, (sprites.TILE_CURSOR, 2): 0x100,
        (descriptor + sprites.TILES_POINTER, 4): 0x090000,
    }
    values.update(overrides)
    return values


def test_a_visible_particle_uploads_with_the_fixed_priority_attribute():
    result = sprites.emit_particle_sprite(_reader(_world()), 0x40, 0x30, DESCRIPTOR_OFFSET)
    assert result['arm'] == 'upload' and not result['flip']
    record = 0xFFFFEC00 & 0xFFFFFF
    assert result['stores'][record + 4] == ((0x100 >> 5) | sprites.PARTICLE_PRIORITY_ATTRIBUTE, 2)
    assert result['upload']['source'] == 0x090000


def test_the_flip_bit_selects_the_flipped_x_offset_and_attribute():
    values = _world()
    values[(sprites.DESCRIPTORS + DESCRIPTOR_OFFSET + sprites.X_OFFSET_FLIPPED, 2)] = 7
    result = sprites.emit_particle_sprite(_reader(values), 0x40, 0x30, DESCRIPTOR_OFFSET | sprites.FLIP_ID_BIT)
    assert result['flip']
    record = 0xFFFFEC00 & 0xFFFFFF
    assert result['stores'][record + 6] == (0x40 + 7, 2)
    assert result['stores'][record + 4][0] & sprites.FLIP_ATTRIBUTE


def test_off_screen_is_offscreen_x_or_offscreen_y_with_no_stores():
    result = sprites.emit_particle_sprite(_reader(_world()), 0x400, 0x30, DESCRIPTOR_OFFSET)
    assert result['arm'] == 'offscreen-x' and result['stores'] == {}
    result = sprites.emit_particle_sprite(_reader(_world()), 0x40, 0x400, DESCRIPTOR_OFFSET)
    assert result['arm'] == 'offscreen-y' and result['stores'] == {}


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
    assert meta['entry'] == boundary.PARTICLE_EMIT_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.particle_emit_plan(machine, machine.registers())
    if isinstance(plan, boundary.Seam):
        _check_seam(plan, state)
        return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('particle-emit').gate_pcs == (boundary.PARTICLE_EMIT_ENTRY,)
    assert boundary.PARTICLE_EMIT_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('particle-emit-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='particle-emit',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('particle-emit never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='particle-emit-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
