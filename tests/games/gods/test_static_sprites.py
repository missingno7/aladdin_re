"""The third recovered Gods region: the sprite emitter's RAM-only sibling (001164).

Same shape as the camera follow step: a RAM-only leaf, no platform
operation.  Three tiers: the pure semantics on synthetic reads; the boundary
plan against the tracer's facts on every state the census retained (four
recordings: off-screen x/y, a placed record with and without the flip
attribute); the candidate over real frames against the reference of the
last PASS cold run, with its negative control diverging.  The list-full
guard (``'full'``) is unwitnessed by every recording censused so far and is
declined, like the camera's negative clamps.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-001164*/001164-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 001164')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

DESCRIPTOR = 0x067412


def _reader(values):
    def read(address, size):
        return values[(address, size)]
    return read


def _world(overrides=()):
    """A synthetic RAM/ROM image: camera at (0x80, 0x40), one descriptor, a list of one record."""
    values = {(sprites.CAMERA_X, 2): 0x80, (sprites.CAMERA_Y, 2): 0x40,
              (sprites.STATIC_DESCRIPTOR_OFFSETS + 0x2E, 2): DESCRIPTOR - sprites.DESCRIPTORS,
              (DESCRIPTOR + sprites.X_OFFSET, 2): 0x0004, (DESCRIPTOR + sprites.X_OFFSET_FLIPPED, 2): 0xFFF0,
              (DESCRIPTOR + sprites.Y_OFFSET, 2): 0x0008, (DESCRIPTOR + sprites.SIZE_ATTRIBUTE, 2): 0x0500,
              (DESCRIPTOR + sprites.TILE_INDEX, 2): 0x0014,
              (sprites.LIST_HEAD, 4): 0xFFFFEC08, (sprites.LIST_COUNT, 2): 1}
    values.update(dict(overrides))
    return values


def test_the_screen_margin_rejects_a_sprite_before_the_descriptor_or_list_work():
    off_x = sprites.emit_static_sprite(_reader(_world()), 0x80 + 0x141, 0x40, 0x17)
    assert off_x['arm'] == 'offscreen-x' and off_x['stores'] == {} and off_x['screen'] == (0x141, 0)
    assert sprites.emit_static_sprite(_reader(_world()), 0x80 - 0x21, 0x40, 0x17)['arm'] == 'offscreen-x'
    off_y = sprites.emit_static_sprite(_reader(_world()), 0x80, 0x40 + 0xC1, 0x17)
    assert off_y['arm'] == 'offscreen-y' and off_y['descriptor'] is None
    assert sprites.emit_static_sprite(_reader(_world()), 0x80 + 0x140, 0x40 + 0xC0, 0x17)['arm'] == 'placed'


def test_a_placed_sprite_appends_one_record_with_the_fixed_tile_and_no_cache_stores():
    result = sprites.emit_static_sprite(_reader(_world()), 0x80 + 0x10, 0x40 + 0x20, 0x17)
    assert result['arm'] == 'placed' and not result['flip'] and result['descriptor'] == DESCRIPTOR
    assert result['record'] == 0xFFEC08 and result['count'] == 1
    assert result['stores'] == {
        sprites.LIST_LAST: (0xFFFFEC08, 4), 0xFFEC08: (0x28, 2), 0xFFEC0A: (0x0501, 2),
        0xFFEC0C: (0x2014, 2), 0xFFEC0E: (0x14, 2), sprites.LIST_HEAD: (0xFFFFEC10, 4), sprites.LIST_COUNT: (2, 2)}


def test_a_flipped_id_selects_the_flipped_x_offset_and_the_flip_attribute():
    flipped = sprites.emit_static_sprite(_reader(_world()), 0x80 + 0x10, 0x40 + 0x20, 0x8017)
    assert flipped['flip'] and flipped['arm'] == 'placed'
    assert flipped['stores'][0xFFEC0C] == (0x2814, 2) and flipped['stores'][0xFFEC0E] == (0x0000, 2)


def test_the_list_full_guard_drops_the_sprite_without_a_store():
    full = sprites.emit_static_sprite(_reader(_world({(sprites.LIST_HEAD, 4): sprites.LIST_FULL})),
                                      0x80 + 0x10, 0x40 + 0x20, 0x17)
    assert full['arm'] == 'full' and full['stores'] == {} and full['descriptor'] == DESCRIPTOR
    assert sprites.emit_static_sprite(_reader(_world({(sprites.LIST_HEAD, 4): sprites.LIST_FULL - 2})),
                                      0x80 + 0x10, 0x40 + 0x20, 0x17)['arm'] == 'placed'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.STATIC_EMIT_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.static_emit_plan(machine, machine.registers())
    # A VBlank that pre-empts the activation is set aside: the plan is the region's alone, and the
    # candidate never plans such a state (the scheduler refuses a span with an interrupt due).
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


@needs_census
def test_the_list_full_arm_is_declined_and_the_original_runs_it():
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        pc = machine.info['pc']
        assert pc == boundary.STATIC_EMIT_ENTRY
        machine.gates([pc])
        assert machine.run(instructions=1) == 'gate'
        # A list head at or beyond LIST_FULL: the 0011E0 arm no recording has entered.
        head = sprites.LIST_FULL
        writes = [(sprites.LIST_HEAD + i, (head >> (8 * (3 - i))) & 0xFF) for i in range(4)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=pc,
                              writes=writes, registers=machine.registers())
        with pytest.raises(boundary.UnsupportedCandidate, match='full'):
            boundary.static_emit_plan(machine, machine.registers())
        candidate = recovery.Candidate('sprites-static')
        candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000) is False
        assert candidate.stats['fallbacks'] == 1 and candidate.stats['candidate_hits'] == 0
        assert machine.info['pc'] == 0x001168     # the original executed the entry instruction (movem, 4 bytes)


def test_candidate_names_are_explicit():
    assert recovery.Candidate('sprites-static').gate_pcs == (boundary.STATIC_EMIT_ENTRY,)
    assert recovery.Candidate('camera-sprites').gate_pcs == (
        boundary.CAMERA_FOLLOW_ENTRY, boundary.SPRITE_EMIT_ENTRY, boundary.STATIC_EMIT_ENTRY, boundary.TABLE_RESET_ENTRY, boundary.SPAWN_QUEUE_ENTRY, boundary.GRID_CELL_ENTRY)
    assert recovery.Candidate('sprites-static-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='sprites-static',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] > 0
    assert set(report['fallback_reasons']) <= {'scheduler admission'}, report['fallback_reasons']
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='sprites-static-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE', mutant
