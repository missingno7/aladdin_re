"""The pickup check (00BA8E): the player's box scanned against the pickup grid, and its two small
callees, the next-random draw (014A3C) and the effect pool add (00932C).

014A3C and 00932C get their own gates too (both have real callers elsewhere: 014A3C is drawn from
3,971 times / 34,904 frames, almost all outside 00BA8E; 00932C is the general form of the pool fill
hazard.py's own '_spawn' inlines with d2=d3=0, called from the hazard tick's own spawn arm).  00BA8E
composes calls into both of them plus the already-recovered zone check (00BCCE) and pickup award
(013264), the shape 00462C's evaluator and 0049DA's spawn queue already proved.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import effects, hazard, pickups, zones
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
RANDOM_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-014A3C/014A3C-*-p*.state'))
POOL_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00932C/00932C-*-p*.state'))
CHECK_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00BA8E-fresh*/00BA8E-*-p*.state'))
PROBE_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-010CD2/010CD2-*-p*.state'))
REFERENCE_FIXTURES = sorted(Path('artifacts/gods/evidence/census-00BA8E-fresh-f0ac19738f19').glob('00BA8E-*-p*.state'))
needs_random_census = pytest.mark.skipif(not RANDOM_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 014A3C')
needs_pool_census = pytest.mark.skipif(not POOL_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00932C')
needs_check_census = pytest.mark.skipif(not CHECK_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00BA8E')
needs_probe_census = pytest.mark.skipif(not PROBE_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 010CD2')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not REFERENCE_FIXTURES
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


# --- 014A3C: next_random ------------------------------------------------------

def test_next_random_reads_the_table_at_the_cursor_and_advances_it_wrapping_every_256_entries():
    result = effects.next_random(_reader({(effects.RANDOM_CURSOR & 0xFFFFFF, 2): 4,
                                          ((effects.RANDOM_TABLE + 4) & 0xFFFFFF, 2): 0x1234}))
    assert result == {'value': 0x1234, 'stores': {effects.RANDOM_CURSOR & 0xFFFFFF: (6, 2)}}
    wrapped = effects.next_random(_reader({(effects.RANDOM_CURSOR & 0xFFFFFF, 2): 0x1FE}))
    assert wrapped['stores'][effects.RANDOM_CURSOR & 0xFFFFFF] == (0, 2)


@needs_random_census
@pytest.mark.parametrize('fixture', RANDOM_FIXTURES, ids=lambda p: p.stem)
def test_next_random_plan_reproduces_every_fact_of_the_original(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.next_random_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems


# --- 00932C: effect_pool_add --------------------------------------------------

def test_effect_pool_add_fills_the_first_free_slot_and_declines_nothing_when_full():
    base = hazard.POOL_BASE & 0xFFFFFF
    slot0_free = {(base, 2): 0xFFFF, (hazard.OBJECT_X & 0xFFFFFF, 2): 5, (hazard.OBJECT_Y & 0xFFFFFF, 2): 9,
                  (hazard.POOL_COUNTER & 0xFFFFFF, 2): 3}
    added = hazard.effect_pool_add(_reader(slot0_free), 10, 20, 30, 40)
    assert added['arm'] == 'added' and added['index'] == 0 and added['slot'] == hazard.POOL_BASE
    assert added['stores'] == {base: (0, 2), base + 2: (15, 2), base + 4: (29, 2),
                               base + 6: (30, 2), base + 8: (40, 2),
                               base + 0xA: (0, 2), hazard.POOL_COUNTER & 0xFFFFFF: (4, 2)}
    full = {((base + hazard.POOL_STRIDE * i) & 0xFFFFFF, 2): 0 for i in range(hazard.POOL_COUNT)}
    assert hazard.effect_pool_add(_reader(full), 0, 0, 0, 0) == {'arm': 'full', 'index': None, 'slot': None, 'stores': {}}


@needs_pool_census
@pytest.mark.parametrize('fixture', POOL_FIXTURES, ids=lambda p: p.stem)
def test_effect_pool_add_plan_reproduces_every_fact_of_the_original(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.effect_pool_add_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems


# --- 00BA8E: pickup_check ------------------------------------------------------

def test_a_forced_zone_result_is_an_immediate_cue_and_nothing_else():
    world = {(zones.HOLD_FLAG & 0xFFFFFF, 2): 0, (zones.GRID_X & 0xFFFFFF, 2): 0,
            (zones.GRID_Y & 0xFFFFFF, 2): 0, (zones.LEVEL_NUMBER & 0xFFFFFF, 2): 0,
            (zones.HALF_WIDTH & 0xFFFFFF, 2): 0, (zones.HALF_HEIGHT & 0xFFFFFF, 2): 0,
            (zones.SUPPRESS_COOLDOWN & 0xFFFFFF, 2): 1, (zones.RESULT_FLAG & 0xFFFFFF, 2): 0,
            (pickups.CHECK_SOUND_ON & 0xFFFFFF, 2): 0}
    # (15, 20) lands inside the box the world above builds (near/far X 10/22, near/far Y 8/44 -- both
    # margins added, HALF_WIDTH/HALF_HEIGHT are 0 here).
    result = pickups.pickup_check(_reader(world), 15, 20, 0)
    assert result['arm'] == 'zone-cue'
    assert result['stores'][pickups.CHECK_SOUND_CUE & 0xFFFFFF] == (pickups.ZONE_CUE_SOUND_OFF, 2)


@needs_check_census
@pytest.mark.parametrize('fixture', CHECK_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_pickup_check_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_arm(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.PICKUP_CHECK_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.pickup_check_plan(machine, registers)
        except boundary.UnsupportedCandidate:
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_a_found_code_013264_itself_declines_is_declined_here_too_not_a_crash():
    # 013264's own pickup_award_plan already declines code -4 and below (the continuation into
    # 013316, not recovered); the composition must decline the whole found arm the same way instead
    # of falling through to _pickup_award_cost's cost table, which only knows -1/-2/-3.
    with pytest.raises(boundary.UnsupportedCandidate):
        boundary._pickup_award_cost(lambda a, s: 0, {'arm': 'unrecovered', 'code': -4})
    with pytest.raises(boundary.UnsupportedCandidate):
        boundary._pickup_award_cost(lambda a, s: 0, {'arm': 'unrecovered', 'code': -100})


def test_found_sound_leaves_the_check_own_cue_not_the_award_own_cue():
    # A real bug this caught: 013264's own cue (PICKUP_CUE=0x38, requested when SOUND_ON) must not
    # survive past this routine's own cue store (0x3C/0x4F) on the found-sound arm -- both land at
    # the same word (SOUND_CUE == CHECK_SOUND_CUE & 0xFFFFFF == 0xFFFDF4).  Composing the two calls
    # into one atomic write set once let the award's own write win by being re-applied last, which
    # only desynced the Z80 (a wrong sound command byte, invisible to every 68000-side check) --
    # found on the tree over fb408bc75597, not on any per-region history.
    d0, d1, d2 = 100, 100, 5
    half = 0x40
    # Mirror pickup_check's own address arithmetic to find the grid byte it will actually read,
    # rather than hand-computing it (and risking exactly the kind of off-by-mask error this bug was).
    raw = (d0 + 4) & 0xFFF8
    cell_x = raw >> 3
    base = (pickups.PICKUP_GRID + cell_x + (raw & 0xFFF8) * 6) & 0xFFFFFF
    record = 0xFFF600
    world = {(zones.HOLD_FLAG & 0xFFFFFF, 2): 0x8000,                # 'held': d2 passes through unchanged
            (pickups.CAMERA_X & 0xFFFFFF, 2): 0, (pickups.CAMERA_Y & 0xFFFFFF, 2): 0,
            (zones.HALF_WIDTH & 0xFFFFFF, 2): half, (zones.HALF_HEIGHT & 0xFFFFFF, 2): half,
            (pickups.ARRAY_GATE & 0xFFFFFF, 2): 0x8000,             # append skipped
            (base, 1): 1,                                            # item code 1: found at the very first cell
            (pickups.GROUP_TABLES[0] & 0xFFFFFF, 2): 0,             # active id 0
            (pickups.ITEM_RECORDS & 0xFFFFFF, 4): record, (record + pickups.ITEM_VALUE, 2): 6,
            (pickups.SOUND_ON & 0xFFFFFF, 2): 1,                     # collect() requests its own cue (0x38)
            (pickups.CHECK_SOUND_ON & 0xFFFFFF, 2): 1}               # this routine's own cue is 0x4F, not 0x3C
    result = pickups.pickup_check(_reader(world), d0, d1, d2)
    assert result['arm'] == 'found-sound'
    assert result['collect']['cue']
    assert result['stores'][pickups.SOUND_CUE] == (pickups.ZONE_CUE_SOUND_ON, 2)


# --- 013316: the grid inverse and debris burst, 013264's own code -4-and-below continuation -------
#
# No separate gate (013316 has no other caller): boundary._grid_inverse_award_plan composes it into
# PICKUP_AWARD_ENTRY (013264) itself, the way 00BA8E owns its own callees.  Fixture coverage for the
# full composition lives in test_pickups.py (every census-013264-* fixture, including the eleven with
# code <= -4); this covers the semantics directly.

def test_grid_inverse_position_converts_the_grid_bytes_own_address_back_to_a_world_position():
    world = {(pickups.CAMERA_X & 0xFFFFFF, 2): 0x100, (pickups.CAMERA_Y & 0xFFFFFF, 2): 0x200}
    # Row 2, column 3 of the grid (48 bytes/row): address = PICKUP_GRID + 2*48 + 3.
    address = (pickups.PICKUP_GRID + 2 * pickups.PICKUP_GRID_ROW + 3) & 0xFFFFFFFF
    x, y = pickups.grid_inverse_position(_reader(world), address)
    assert (x, y) == ((3 << 3) + 0x100, (2 << 3) + 0x200)


def test_grid_inverse_award_places_eight_particles_in_the_shared_pool_with_a_table_driven_offset():
    base = 0xFFFF123E & 0xFFFFFF
    world = {(pickups.CAMERA_X & 0xFFFFFF, 2): 0, (pickups.CAMERA_Y & 0xFFFFFF, 2): 0,
            (pickups.SOUND_ON & 0xFFFFFF, 2): 0,
            (pickups.DEBRIS_RATE_FLAG & 0xFFFFFF, 2): 0xFFFF, (pickups.DEBRIS_RATE_COUNTER & 0xFFFFFF, 2): 0,
            (pickups.RANDOM_CURSOR & 0xFFFFFF, 2): 0}
    for index in range(pickups.DEBRIS_POOL_COUNT):
        world[(base + pickups.DEBRIS_POOL_STRIDE * index, 2)] = 0xFFFF   # every slot free
    result = pickups.grid_inverse_award(_reader(world), pickups.PICKUP_GRID & 0xFFFFFFFF)
    assert result['arm'] == 'debris'
    assert len(result['particles']) == pickups.DEBRIS_PARTICLES
    assert [p['skipped'] for p in result['particles']] == [0] * pickups.DEBRIS_PARTICLES
    first = result['particles'][0]
    assert result['stores'][first['address'] & 0xFFFFFF] == (0, 2)          # x
    assert result['stores'][(first['address'] + 4) & 0xFFFFFF] == (first['table_value'], 2)


def test_grid_inverse_award_declines_sound_on_and_the_rate_limit():
    world = {(pickups.CAMERA_X & 0xFFFFFF, 2): 0, (pickups.CAMERA_Y & 0xFFFFFF, 2): 0,
            (pickups.SOUND_ON & 0xFFFFFF, 2): 1}
    assert pickups.grid_inverse_award(_reader(world), pickups.PICKUP_GRID & 0xFFFFFFFF)['arm'] == 'grid-code'
    limited = {**world, (pickups.SOUND_ON & 0xFFFFFF, 2): 0, (pickups.DEBRIS_RATE_FLAG & 0xFFFFFF, 2): 1,
              (pickups.DEBRIS_RATE_COUNTER & 0xFFFFFF, 2): pickups.DEBRIS_RATE_LIMIT}
    assert pickups.grid_inverse_award(_reader(limited), pickups.PICKUP_GRID & 0xFFFFFFFF)['arm'] == 'debris-limited'


# --- 010CD2: the pickup probe (game/pickups.py: pickup_probe) ---------------
#
# A caller-supplied record's own camera-relative call into the already-recovered pickup check; the
# 15 September blocker's own reading of this address range (0091BC, 01158C/0115D4, the 010D7C literal
# test) turned out to belong to a SEPARATE, adjacent routine (010CF8 onward, not called from here):
# a fresh census shows 010CD2's own body (010CD2-010CF6) calls only 00BA8E, on every one of 32 real
# path classes over 1,721 occurrences.

def test_pickup_probe_adds_the_camera_and_calls_the_pickup_check_with_the_records_own_d2():
    world = {(pickups.CAMERA_X & 0xFFFFFF, 2): 5, (pickups.CAMERA_Y & 0xFFFFFF, 2): 7,
            (zones.HOLD_FLAG & 0xFFFFFF, 2): 0x8000}   # 'held': the check's own d2 passes through
    result = pickups.pickup_probe(_reader(world), 100, 200, 3)
    assert (result['x'], result['y']) == (105, 207)
    assert result['check']['arm'] == 'clean' and not result['negative']


@needs_probe_census
@pytest.mark.parametrize('fixture', PROBE_FIXTURES, ids=lambda p: p.stem)
def test_pickup_probe_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.pickup_probe_plan(machine, registers)
        except boundary.UnsupportedCandidate:
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_names_are_explicit():
    assert recovery.Candidate('next-random').gate_pcs == (boundary.NEXT_RANDOM_ENTRY,)
    assert recovery.Candidate('effect-pool-add').gate_pcs == (boundary.EFFECT_POOL_ADD_ENTRY,)
    assert recovery.Candidate('pickup-check').gate_pcs == (boundary.PICKUP_CHECK_ENTRY,)
    assert recovery.Candidate('pickup-probe').gate_pcs == (boundary.PICKUP_PROBE_ENTRY,)
    for entry in (boundary.NEXT_RANDOM_ENTRY, boundary.EFFECT_POOL_ADD_ENTRY, boundary.PICKUP_CHECK_ENTRY,
                 boundary.PICKUP_PROBE_ENTRY):
        assert entry in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('next-random-mutant-result').mutation is recovery._mutate_register
    assert recovery.Candidate('effect-pool-add-mutant-result').mutation is recovery._mutate_result
    assert recovery.Candidate('pickup-check-mutant-result').mutation is recovery._mutate_result
    assert recovery.Candidate('pickup-probe-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_pickup_check_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in REFERENCE_FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='pickup-check', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches a witnessed arm within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= {'scheduler admission'}
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='pickup-check-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
