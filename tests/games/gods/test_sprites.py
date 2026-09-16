"""The second recovered Gods region, and the first with a platform operation: the sprite emitter (0018C8).

Three tiers, as for the camera: the pure semantics on synthetic reads; the
plan against the tracer on every state the census retained (the off-screen
and cache-hit arms as one plan, the cache-miss arm as a seam whose prefix
is checked up to the VDP control write and whose suffix is checked from the
resume); the candidate over real frames against the reference of the last
PASS, with two negative controls diverging.  The evidence tiers skip when
the local census/reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0018C8*/0018C8-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0018C8')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

DESCRIPTOR = 0x067334


def _reader(values):
    def read(address, size):
        return values[(address, size)]
    return read


def _world(overrides=()):
    """A synthetic RAM/ROM image: camera at (0x80, 0x40), one descriptor, an empty cache, a list of one record."""
    values = {(sprites.CAMERA_X, 2): 0x80, (sprites.CAMERA_Y, 2): 0x40,
              (sprites.DESCRIPTOR_OFFSETS + 0x8A, 2): DESCRIPTOR - sprites.DESCRIPTORS,
              (DESCRIPTOR + sprites.TILES_POINTER, 4): 0x075200, (DESCRIPTOR + sprites.TILE_BYTES, 2): 0x80,
              (DESCRIPTOR + sprites.X_OFFSET, 2): 0x0004, (DESCRIPTOR + sprites.X_OFFSET_FLIPPED, 2): 0xFFF0,
              (DESCRIPTOR + sprites.Y_OFFSET, 2): 0x0008, (DESCRIPTOR + sprites.SIZE_ATTRIBUTE, 2): 0x0500,
              (sprites.LIST_HEAD, 4): 0xFFFFEC08, (sprites.LIST_COUNT, 2): 1, (sprites.TILE_CURSOR, 2): 0x5000}
    for index in range(sprites.CACHE_SCANNED + 1):
        values[(sprites.CACHE_IDS + 2 * index, 2)] = 0xFFFF
        values[(sprites.CACHE_TILES + 2 * index, 2)] = 0
    values.update(dict(overrides))
    return values


def test_the_screen_margin_rejects_a_sprite_before_any_cache_or_list_work():
    off_x = sprites.emit_sprite(_reader(_world()), 0x80 + 0x141, 0x40, 0x45)
    assert off_x['arm'] == 'offscreen-x' and off_x['stores'] == {} and off_x['screen'] == (0x141, 0)
    assert sprites.emit_sprite(_reader(_world()), 0x80 - 0x21, 0x40, 0x45)['arm'] == 'offscreen-x'   # wraps negative
    off_y = sprites.emit_sprite(_reader(_world()), 0x80, 0x40 + 0xC1, 0x45)
    assert off_y['arm'] == 'offscreen-y' and off_y['scan'] == 0
    assert sprites.emit_sprite(_reader(_world()), 0x80 + 0x140, 0x40 + 0xC0, 0x45)['arm'] == 'miss'      # the limits inclusive


def test_a_miss_claims_the_first_empty_slot_the_next_tiles_and_one_record():
    result = sprites.emit_sprite(_reader(_world()), 0x80 + 0x10, 0x40 + 0x20, 0x45)
    assert result['arm'] == 'miss' and result['scan'] == 1 and result['inserted'] == 0 and not result['flip']
    assert result['descriptor'] == DESCRIPTOR and result['record'] == 0xFFEC08
    assert result['stores'] == {
        sprites.CACHE_IDS: (0x8A, 2), sprites.CACHE_TILES: (0x280, 2),
        sprites.LIST_LAST: (0xFFFFEC08, 4), 0xFFEC08: (0x28, 2), 0xFFEC0A: (0x0501, 2),
        0xFFEC0C: (0x2280, 2), 0xFFEC0E: (0x14, 2), sprites.LIST_HEAD: (0xFFFFEC10, 4), sprites.LIST_COUNT: (2, 2)}
    assert result['upload'] == {'command': 0x50000001, 'source': 0x075200, 'longs': 32, 'bytes': 0x80, 'cursor': 0x5000}


def test_a_hit_reuses_the_cached_tiles_after_the_scan_and_a_full_cache_takes_the_ninth_slot():
    world = _world({(sprites.CACHE_IDS, 2): 0x0002, (sprites.CACHE_IDS + 2, 2): 0x008A, (sprites.CACHE_TILES + 2, 2): 0x0123})
    hit = sprites.emit_sprite(_reader(world), 0x80, 0x40, 0x45)
    assert hit['arm'] == 'hit' and hit['scan'] == 2 and hit['inserted'] is None and hit['upload'] is None
    assert hit['stores'][0xFFEC0C] == (0x2123, 2) and sprites.CACHE_IDS not in hit['stores']
    full = _world({(sprites.CACHE_IDS + 2 * index, 2): 2 * index + 2 for index in range(sprites.CACHE_SCANNED)})
    ninth = sprites.emit_sprite(_reader(full), 0x80, 0x40, 0x45)
    assert ninth['arm'] == 'miss' and ninth['scan'] == 8 and ninth['inserted'] == 8
    assert ninth['stores'][sprites.CACHE_IDS + 16] == (0x8A, 2) and ninth['stores'][sprites.CACHE_TILES + 16] == (0x280, 2)


def test_a_flipped_id_selects_the_flipped_x_offset_and_the_flip_attribute():
    flipped = sprites.emit_sprite(_reader(_world()), 0x80 + 0x10, 0x40 + 0x20, 0x8045)
    assert flipped['flip'] and flipped['arm'] == 'miss' and flipped['descriptor'] == DESCRIPTOR
    assert flipped['stores'][0xFFEC0E] == (0x0000, 2) and flipped['stores'][0xFFEC0C] == (0x2A80, 2)


def check_seam(seam, state):
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
    return facts


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.SPRITE_EMIT_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.sprite_emit_plan(machine, machine.registers())
    if isinstance(plan, boundary.Seam):
        check_seam(plan, state)
        return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


@needs_census
def test_the_flipped_arm_is_declined_and_the_seam_names_its_contract():
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.SPRITE_EMIT_ENTRY
        with pytest.raises(boundary.UnsupportedCandidate, match='flipped sprite arm not witnessed'):
            boundary.sprite_emit_plan(machine, {**registers, 'd2': registers['d2'] | sprites.FLIP_ID_BIT})
        seam = None
        for fixture in FIXTURES:
            machine.restore(fixture.read_bytes())
            plan = boundary.sprite_emit_plan(machine, machine.registers())
            if isinstance(plan, boundary.Seam):
                seam = plan
                break
    assert seam is not None
    assert seam.prefix.registers['pc'] == boundary.SPRITE_EMIT_UPLOAD and seam.prefix.last_pc == boundary.SPRITE_EMIT_PREFIX_LAST_PC
    assert seam.resume_pc == boundary.SPRITE_EMIT_RESUME and seam.guards == ((seam.stack_basis & 0xFFFFFF, boundary.SPRITE_EMIT_FRAME + 4),)
    assert seam.stack_basis == seam.prefix.registers['a7']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('sprites').gate_pcs == (boundary.SPRITE_EMIT_ENTRY,)
    assert recovery.Candidate('camera-sprites').gate_pcs == (
        boundary.CAMERA_FOLLOW_ENTRY, boundary.SPRITE_EMIT_ENTRY, boundary.STATIC_EMIT_ENTRY, boundary.TABLE_RESET_ENTRY, boundary.SPAWN_QUEUE_ENTRY)
    assert recovery.Candidate('sprites-mutant-result').mutation is recovery._mutate_result
    assert recovery.Candidate('sprites-mutant-register').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutants_diverge():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='sprites',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] > 100
    assert set(report['fallback_reasons']) <= {'scheduler admission'}, report['fallback_reasons']
    for mutant in ('sprites-mutant-result', 'sprites-mutant-register'):
        diverged = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                        candidate=mutant, reference=EVIDENCE)
        assert diverged['status'] == 'DIVERGENCE', mutant
        assert diverged['first_difference']['frame'] <= 6002, (mutant, diverged['first_difference'])


@needs_reference
def test_every_seam_entered_over_real_frames_completes_at_its_own_resume():
    from genesis_re.history import HistoryStore
    from genesis_re.history_runtime import GenesisRun
    meta = json.loads((EVIDENCE / 'boundary-6000.json').read_text(encoding='utf-8'))
    store = HistoryStore(GODS.history_path(), GODS.history_root)
    path = store.flatten(store.resolve(meta['history_id']))
    buttons = 0
    for event in path['events']:
        if event['frame'] <= meta['frame']:
            buttons = event['buttons']
    with GenesisRun(GODS, GODS.read_rom(), 'sprites') as run:
        run.machine.restore((EVIDENCE / 'boundary-6000.state').read_bytes())
        run.frame, run.buttons = meta['frame'], buttons
        run.machine.pad(buttons)
        run.advance(meta['frame'] + 60, path['events'])
        stats = run.candidate.stats
        assert not run.machine.in_seam
    # A suffix the native scheduler refuses (an interrupt due inside its span) is run by the original at the
    # resume, which is exact: the only fallback reason a seam may leave is that refusal.
    refused = stats['fallbacks_by_gate'].get('%06X' % boundary.SPRITE_EMIT_RESUME, 0)
    assert stats['seam_entries'] > 0 and stats['seam_completions'] + refused == stats['seam_entries']
    assert set(stats['fallback_reasons']) <= {'scheduler admission'}, stats['fallback_reasons']
    assert stats['seam_foreign_returns'] == 0 and stats['seam_deadline_fallbacks'] == 0
