"""The fifth recovered Gods region: the spawn queue (0049DA).

A RAM-only leaf that calls the already-recovered sprite emitter sibling
(001164) once per active slot -- the shape the protocol names "calls to
routines already recovered": no platform operation of its own, and
002806/0018C8/001164/004150 already prove the shapes it depends on.
Three tiers: the pure semantics on synthetic reads; the boundary plan
against the tracer's facts on every state the census retained (0-2 active
slots per tick, continuing or retiring); the candidate over real frames
against the reference of the last PASS cold run, with its negative control
diverging.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import spawn_queue, sprites
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0049DA*/0049DA-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0049DA')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

DESCRIPTOR = 0x067512


def _world(counters, overrides=()):
    """A synthetic RAM/ROM image: four slots, camera at the origin, one descriptor per used sprite id, an empty list."""
    values = {(sprites.CAMERA_X, 2): 0, (sprites.CAMERA_Y, 2): 0,
              (sprites.LIST_HEAD, 4): 0xFFFFEC08, (sprites.LIST_COUNT, 2): 0}
    counters = list(counters) + [0xFFFF] * (spawn_queue.SLOT_COUNT - len(counters))
    for index, counter in enumerate(counters):
        base = spawn_queue.SLOT_BASE + spawn_queue.SLOT_SIZE * index
        values[(base, 2)] = counter & 0xFFFF
        values[(base + 2, 2)] = 0x100
        values[(base + 4, 2)] = 0x80
        if counter & 0x8000 == 0:
            sprite = (spawn_queue.SPRITE_ID_BASE + counter) & 0xFFFF
            key = (sprite * 2) & 0xFFFF
            values[(sprites.STATIC_DESCRIPTOR_OFFSETS + key, 2)] = DESCRIPTOR - sprites.DESCRIPTORS
            values[(DESCRIPTOR + sprites.X_OFFSET, 2)] = 4
            values[(DESCRIPTOR + sprites.X_OFFSET_FLIPPED, 2)] = 0xFFF0
            values[(DESCRIPTOR + sprites.Y_OFFSET, 2)] = 8
            values[(DESCRIPTOR + sprites.SIZE_ATTRIBUTE, 2)] = 0x0500
            values[(DESCRIPTOR + sprites.TILE_INDEX, 2)] = 0x14
    values.update(dict(overrides))
    return values


def test_all_slots_empty_does_nothing():
    world = _world([0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF])
    read = lambda a, s: world[(a, s)]
    slots = spawn_queue.scan_spawn_queue(read)
    assert all(not slot['active'] for slot in slots)


def test_an_active_slot_advances_its_counter_until_it_retires():
    world = _world([3, 0xFFFF, 0xFFFF, 0xFFFF])
    read = lambda a, s: world[(a, s)]
    slots = spawn_queue.scan_spawn_queue(read)
    assert slots[0]['active'] and slots[0]['sprite'] == spawn_queue.SPRITE_ID_BASE + 3
    assert not slots[0]['retire'] and slots[0]['counter_store'] == 4
    assert slots[0]['emitted']['arm'] == 'placed'
    world = _world([spawn_queue.RETIRE_LIMIT - 1, 0xFFFF, 0xFFFF, 0xFFFF])
    read = lambda a, s: world[(a, s)]
    slots = spawn_queue.scan_spawn_queue(read)
    assert slots[0]['retire'] and slots[0]['counter_store'] == spawn_queue.EMPTY


def test_two_active_slots_in_one_tick_append_two_records_in_order():
    world = _world([0, 0])
    read = lambda a, s: world[(a, s)]
    slots = spawn_queue.scan_spawn_queue(read)
    assert slots[0]['emitted']['record'] == 0xFFFFEC08 & 0xFFFFFF
    assert slots[1]['emitted']['record'] == (0xFFFFEC08 & 0xFFFFFF) + sprites.RECORD_SIZE
    assert slots[1]['emitted']['stores'][sprites.LIST_COUNT] == (2, 2)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.SPAWN_QUEUE_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.spawn_queue_plan(machine, machine.registers())
    facts = pathfacts.trace(state, game=GODS)
    if facts['interrupts_during_trace']:
        pytest.skip('an interrupt pre-empted the traced activation: not this planner\'s arm')
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('spawn-queue').gate_pcs == (boundary.SPAWN_QUEUE_ENTRY,)
    assert recovery.Candidate('camera-sprites').gate_pcs == (
        boundary.CAMERA_FOLLOW_ENTRY, boundary.SPRITE_EMIT_ENTRY, boundary.STATIC_EMIT_ENTRY,
        boundary.TABLE_RESET_ENTRY, boundary.SPAWN_QUEUE_ENTRY)
    assert recovery.Candidate('spawn-queue-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    # The spawn queue's active (matching) arm is rare: the main history's only witnessed occurrences
    # (the census above) fall at frames 428-2800, before either retained evidence/main boundary state
    # (6000, 12000).  The active-slot fixture itself is a valid state on the same history, so it
    # doubles as the segment base -- the reference is still evidence/main's (same history, cold PASS).
    active_fixture = Path('artifacts/gods/evidence/census-0049DA/0049DA-entry-p1.state')
    if not active_fixture.exists():
        pytest.skip('no local census-0049DA/0049DA-entry-p1.state (an active-slot fixture)')
    report = segment_verify.check(active_fixture, game=GODS, frames=60, candidate='spawn-queue', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] > 0
    assert set(report['fallback_reasons']) <= {'scheduler admission'}, report['fallback_reasons']
    mutant = segment_verify.check(active_fixture, game=GODS, frames=60,
                                  candidate='spawn-queue-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE', mutant

    # The routine also runs constantly (every other tick, all-empty): the standard boundary states
    # exercise that common arm at volume, with no fallback beyond the native scheduler's own refusals.
    common = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='spawn-queue',
                                  reference=EVIDENCE)
    assert common['status'] == 'PASS', common
    assert common['candidate_hits'] > 0
    assert set(common['fallback_reasons']) <= {'scheduler admission'}, common['fallback_reasons']
