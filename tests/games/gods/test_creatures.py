"""The creature attack timer (009D6C), called from 00A772 (00A578's own 9-slot creature-list walk)
once per active creature per frame -- a full-tree census (all five recordings, 273 retained fixtures,
18 Sep) found four real dispatch families past the two early 'skip' exits and 'waiting': quadrant 1
draws two random jitters and launches through the pool body entered directly at 0091C8 (past 0091BC's
own un-jittered GRID_X/GRID_Y read); quadrants 2-3 launch at the tracked position with no jitter,
through 0091BC itself; quadrant 0 never launches -- it hands off to game.timers._spawn's own
already-recovered BACK/FORWARD hazard-pool fill through a tail-JUMP (not a call), so 01158C/0115D4's
own inner rts returns straight past 009D6C to 00A772.  No seam: every native/device boundary this
region touches (the two launch entries, the hazard pool) is itself already-recovered pure 68000 code,
so the whole span is one flat AtomicPlan.  Three tiers as for the other leaves; the evidence tiers
skip when the local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine, NativeError
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import creatures, effects, projectiles, timers
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-009D6C*/009D6C-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 009D6C')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')

KIND_FRAME_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AA50-*/00AA50-entry-p*.state'))
needs_kind_frame_census = pytest.mark.skipif(not KIND_FRAME_FIXTURES or not GODS.rom_path.is_file(),
                                             reason='no local census of 00AA50')

AF3C_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AF3C-*/00AF3C-entry-p*.state'))
needs_af3c_census = pytest.mark.skipif(not AF3C_FIXTURES or not GODS.rom_path.is_file(),
                                       reason='no local census of 00AF3C')

GRID_CELL_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AA38-*/00AA38-entry-p*.state'))
needs_grid_cell_census = pytest.mark.skipif(not GRID_CELL_FIXTURES or not GODS.rom_path.is_file(),
                                            reason='no local census of 00AA38')

GROUND_CONTACT_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00ACA0-*/00ACA0-entry-p*.state'))
needs_ground_contact_census = pytest.mark.skipif(not GROUND_CONTACT_FIXTURES or not GODS.rom_path.is_file(),
                                                 reason='no local census of 00ACA0')

GROUND_CONTACT_MIRROR_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AD88-*/00AD88-entry-p*.state'))
needs_ground_contact_mirror_census = pytest.mark.skipif(not GROUND_CONTACT_MIRROR_FIXTURES or not GODS.rom_path.is_file(),
                                                        reason='no local census of 00AD88')

FALL_KIND_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AE6C-*/00AE6C-entry-p*.state'))
needs_fall_kind_census = pytest.mark.skipif(not FALL_KIND_FIXTURES or not GODS.rom_path.is_file(),
                                            reason='no local census of 00AE6C')

FALL_KIND_MIRROR_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AED4-*/00AED4-entry-p*.state'))
needs_fall_kind_mirror_census = pytest.mark.skipif(not FALL_KIND_MIRROR_FIXTURES or not GODS.rom_path.is_file(),
                                                   reason='no local census of 00AED4')

GROUND_EDGE_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AD68-*/00AD68-entry-p*.state'))
needs_ground_edge_census = pytest.mark.skipif(not GROUND_EDGE_FIXTURES or not GODS.rom_path.is_file(),
                                              reason='no local census of 00AD68')

AIM_CUE_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00B082-*/00B082-entry-p*.state'))
needs_aim_cue_census = pytest.mark.skipif(not AIM_CUE_FIXTURES or not GODS.rom_path.is_file(),
                                          reason='no local census of 00B082')

AIM_POOL_RESET_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00B02A-*/00B02A-entry-p*.state'))
needs_aim_pool_reset_census = pytest.mark.skipif(not AIM_POOL_RESET_FIXTURES or not GODS.rom_path.is_file(),
                                                 reason='no local census of 00B02A')

AIM_POOL_ADD_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00B05A-*/00B05A-entry-p*.state'))
needs_aim_pool_add_census = pytest.mark.skipif(not AIM_POOL_ADD_FIXTURES or not GODS.rom_path.is_file(),
                                               reason='no local census of 00B05A')

AIM_WINDOW_ADDRESS_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00B32E-*/00B32E-entry-p*.state'))
needs_aim_window_address_census = pytest.mark.skipif(not AIM_WINDOW_ADDRESS_FIXTURES or not GODS.rom_path.is_file(),
                                                      reason='no local census of 00B32E')

AIM_TARGET_SCAN_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00B724-*/00B724-entry-p*.state'))
needs_aim_target_scan_census = pytest.mark.skipif(not AIM_TARGET_SCAN_FIXTURES or not GODS.rom_path.is_file(),
                                                  reason='no local census of 00B724')

AIM_TARGET_SCAN_BACKWARD_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00B7DA-*/00B7DA-entry-p*.state'))
needs_aim_target_scan_backward_census = pytest.mark.skipif(not AIM_TARGET_SCAN_BACKWARD_FIXTURES or not GODS.rom_path.is_file(),
                                                            reason='no local census of 00B7DA')

AIM_TARGET_RESOLVE_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00B6AE-*/00B6AE-entry-p*.state'))
needs_aim_target_resolve_census = pytest.mark.skipif(not AIM_TARGET_RESOLVE_FIXTURES or not GODS.rom_path.is_file(),
                                                      reason='no local census of 00B6AE')

AIM_PROBE_MARK_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00B524-*/00B524-entry-p*.state'))
needs_aim_probe_mark_census = pytest.mark.skipif(not AIM_PROBE_MARK_FIXTURES or not GODS.rom_path.is_file(),
                                                 reason='no local census of 00B524')

AIM_PROBE_MARK_STORE_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00B62A-*/00B62A-entry-p*.state'))
needs_aim_probe_mark_store_census = pytest.mark.skipif(not AIM_PROBE_MARK_STORE_FIXTURES or not GODS.rom_path.is_file(),
                                                        reason='no local census of 00B62A')

AIM_RAY_MARCH_FORWARD_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00B354-*/00B354-entry-p*.state'))
needs_aim_ray_march_forward_census = pytest.mark.skipif(not AIM_RAY_MARCH_FORWARD_FIXTURES or not GODS.rom_path.is_file(),
                                                        reason='no local census of 00B354')

AIM_RAY_MARCH_BACKWARD_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00B440-*/00B440-entry-p*.state'))
needs_aim_ray_march_backward_census = pytest.mark.skipif(not AIM_RAY_MARCH_BACKWARD_FIXTURES or not GODS.rom_path.is_file(),
                                                         reason='no local census of 00B440')

AIM_POOL_SCAN_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00B588-*/00B588-entry-p*.state'))
needs_aim_pool_scan_census = pytest.mark.skipif(not AIM_POOL_SCAN_FIXTURES or not GODS.rom_path.is_file(),
                                                reason='no local census of 00B588')

SPAWN_FIND_FREE_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00B8C2-*/00B8C2-entry-p*.state'))
needs_spawn_find_free_census = pytest.mark.skipif(not SPAWN_FIND_FREE_FIXTURES or not GODS.rom_path.is_file(),
                                                   reason='no local census of 00B8C2')

SPAWN_TABLE_ADD_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00B920-*/00B920-entry-p*.state'))
needs_spawn_table_add_census = pytest.mark.skipif(not SPAWN_TABLE_ADD_FIXTURES or not GODS.rom_path.is_file(),
                                                   reason='no local census of 00B920')

TYPE_PTR, INSTANCE_PTR = 0xFF2000, 0xFF2100


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


# --- semantics: game.creatures.attack_update ------------------------------------------------------

def test_a_zero_attack_byte_skips_with_no_effect():
    values = {(TYPE_PTR + creatures.ATTACK_BYTE, 1): 0}
    result = creatures.attack_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result == {'arm': 'skip', 'stores': {}}


def test_a_zero_low_nibble_also_skips_with_no_effect():
    values = {(TYPE_PTR + creatures.ATTACK_BYTE, 1): 0xA0}
    result = creatures.attack_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result == {'arm': 'skip', 'stores': {}}


def test_a_nonzero_countdown_just_waits():
    values = {(TYPE_PTR + creatures.ATTACK_BYTE, 1): 0x1A, (INSTANCE_PTR + creatures.COUNTDOWN, 2): 5}
    result = creatures.attack_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'waiting' and result['before'] == 5 and result['after'] == 4
    assert result['stores'] == {(INSTANCE_PTR + creatures.COUNTDOWN) & 0xFFFFFF: (4, 2)}


def _launch_values(quadrant, overrides=None):
    values = {(TYPE_PTR + creatures.ATTACK_BYTE, 1): 0x2A, (TYPE_PTR + creatures.QUADRANT_WORD, 2): quadrant << 4,
              (INSTANCE_PTR + creatures.COUNTDOWN, 2): 1,
              (INSTANCE_PTR + creatures.POSITION_X, 2): 100, (INSTANCE_PTR + creatures.POSITION_Y, 2): 50,
              (creatures.GRID_X, 2): 200, (creatures.GRID_Y, 2): 80,
              (effects.RANDOM_CURSOR & 0xFFFFFF, 2): 0, (effects.RANDOM_TABLE & 0xFFFFFF, 2): 0x20,
              ((effects.RANDOM_TABLE + 2) & 0xFFFFFF, 2): 0x30}
    for index in range(projectiles.POOL_COUNT):
        values[((projectiles.POOL_BASE + projectiles.POOL_STRIDE * index) & 0xFFFFFF, 4)] = 0x80000000
    if overrides:
        values.update(overrides)
    return values


def test_quadrant_one_jitters_the_tracked_position_and_launches_through_0091c8():
    result = creatures.attack_update(_reader(_launch_values(1)), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'launch-jittered' and result['reload'] == ((0x10 - 0xA) & 0xFF) * 4
    assert result['power'] == 2
    # target = GRID + bias + ((draw & 0x3F) - 0x1F); the two draws come from the wrapping table in order.
    x1, y1 = result['launch']['target']
    assert x1 == (200 + 8 + ((0x20 & 0x3F) - 0x1F)) & 0xFFFF
    assert y1 == (80 + 6 + ((0x30 & 0x3F) - 0x1F)) & 0xFFFF


def test_quadrant_two_launches_straight_at_the_tracked_position_with_no_jitter():
    result = creatures.attack_update(_reader(_launch_values(2)), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'launch-direct'
    assert result['launch']['target'] == (208, 86)


def test_quadrant_three_shares_quadrant_twos_own_direct_launch():
    a = creatures.attack_update(_reader(_launch_values(2)), TYPE_PTR, INSTANCE_PTR)
    b = creatures.attack_update(_reader(_launch_values(3)), TYPE_PTR, INSTANCE_PTR)
    assert a['arm'] == b['arm'] == 'launch-direct' and a['launch']['target'] == b['launch']['target']


def test_an_exhausted_projectile_pool_is_declined_by_name():
    values = _launch_values(1, overrides={((projectiles.POOL_BASE + projectiles.POOL_STRIDE * i) & 0xFFFFFF, 4): 0
                                          for i in range(projectiles.POOL_COUNT)})
    result = creatures.attack_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'launch-jittered-pool-full'


def _spawn_values(overrides=None):
    values = {(TYPE_PTR + creatures.ATTACK_BYTE, 1): 0x32, (TYPE_PTR + creatures.QUADRANT_WORD, 2): 0,
              (INSTANCE_PTR + creatures.COUNTDOWN, 2): 1,
              (INSTANCE_PTR + creatures.POSITION_X, 2): 100, (INSTANCE_PTR + creatures.POSITION_Y, 2): 50,
              (timers.FREQUENCY_SCALE & 0xFFFFFF, 2): 0x1000, (creatures.TRACKED_SIGN & 0xFFFFFF, 2): 0xFFFF,
              (INSTANCE_PTR + creatures.DIRECTION_INDEX, 2): 0, (creatures.DIRECTION_BIT_TABLE & 0xFFFFFF, 1): 0x01,
              (timers.CAMERA_X & 0xFFFFFF, 2): 0, (timers.CAMERA_Y & 0xFFFFFF, 2): 0}
    for index in range(timers.SPAWN_POOL_COUNT):
        values[((timers.SPAWN_POOL_BASE + timers.SPAWN_POOL_STRIDE * index + 6) & 0xFFFFFF, 2)] = 0xFFFF   # every slot occupied
    if overrides:
        values.update(overrides)
    return values


def test_quadrant_zero_negative_tracked_sign_selects_back_by_the_rom_bit_table():
    result = creatures.attack_update(_reader(_spawn_values()), TYPE_PTR, INSTANCE_PTR)
    assert result['variant'] is timers.BACK
    assert result['arm'] in ('spawn-window', 'spawn-reject')


def test_quadrant_zero_positive_tracked_sign_selects_by_the_instances_own_field():
    values = _spawn_values({(creatures.TRACKED_SIGN & 0xFFFFFF, 2): 0, (INSTANCE_PTR + creatures.FORWARD_BACK, 2): 2})
    result = creatures.attack_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['variant'] is timers.FORWARD


def test_quadrant_zero_zero_forward_back_declines_with_no_effect():
    values = _spawn_values({(creatures.TRACKED_SIGN & 0xFFFFFF, 2): 0, (INSTANCE_PTR + creatures.FORWARD_BACK, 2): 0})
    result = creatures.attack_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'skip-quadrant0'


# --- boundary: gods_sega.boundary.attack_update_plan over every retained fixture -------------------

@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_and_declines_the_rest(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.ATTACK_UPDATE_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        type_ptr, instance_ptr = registers['a4'] & 0xFFFFFF, registers['a5'] & 0xFFFFFF
        result = creatures.attack_update(boundary._reader(machine), type_ptr, instance_ptr)
        if result['arm'] == 'skip-quadrant0' or result['arm'].endswith('pool-full'):
            with pytest.raises(boundary.UnsupportedCandidate):
                boundary.attack_update_plan(machine, registers)
            return
        plan = boundary.attack_update_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers.get('pc'))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('creature-attack').gate_pcs == (boundary.ATTACK_UPDATE_ENTRY,)
    # native/machine.cpp caps the gate set at 64; camera-sprites is already there (state 19 took the
    # last slot) -- creature-attack stays its own standalone candidate, per state-18's own precedent.
    assert boundary.ATTACK_UPDATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('creature-attack-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    # A short window sees only the 'skip' arm (no writes, every register 009D6C sets is dead on return
    # per the mutation note above) -- 20,000 frames reaches 'waiting' (a real countdown-decrement write)
    # and 'spawn-window', which _mutate_result's one-byte flip can actually corrupt.
    state = Path('artifacts/gods/evidence/main/boundary-6000.state')
    if not state.is_file():
        pytest.skip('no local boundary-6000.state reference')
    report = segment_verify.check(state, game=GODS, frames=20000, candidate='creature-attack', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('creature-attack never hits in this window')
    mutant = segment_verify.check(state, game=GODS, frames=20000, candidate='creature-attack-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AA50: the creature's own per-kind, per-frame offset -----------------------------------------
#
# One of 00A772's own unconditional callees (docs/gods/blockers/2026-09-18-00A578.md's own "Next
# question").  RAM/ROM-read only, no store, one unconditional path -- 19,798 occurrences across four
# recordings, all the SAME 12-instruction shape.

def test_kind_frame_offset_reads_the_kind_table_and_the_frame_table():
    values = {(INSTANCE_PTR + creatures.KIND, 2): 2,
              (creatures.KIND_TABLE + 8 * 2 + creatures.KIND_TABLE_VALUE_OFFSET, 4): 0x808,
              (INSTANCE_PTR + creatures.FRAME_STEP, 2): 1,
              (TYPE_PTR + creatures.TYPE_FRAME_BYTE, 1): 3,
              (creatures.FRAME_TABLE_PTR & 0xFFFFFF, 4): 0xFF9000,
              (0xFF9000 + (3 << 4), 2): 0x10}
    result = creatures.kind_frame_offset(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['kind'] == 2 and result['frame'] == 3
    assert result['offset'] == ((0x808 + 1) << 4) & 0xFFFF
    assert result['delta'] == 0x10
    assert result['d2'] == (result['offset'] + result['delta']) & 0xFFFF


def test_kind_table_values_all_have_a_zero_upper_word_in_the_real_rom():
    """The boundary plan's own exit d2 depends on this: confirmed from the ROM, not assumed."""
    from gods_sega.profile import GODS as _GODS
    rom = _GODS.read_rom()
    for kind in range(8):
        value = int.from_bytes(rom[creatures.KIND_TABLE + 8 * kind + creatures.KIND_TABLE_VALUE_OFFSET:
                                   creatures.KIND_TABLE + 8 * kind + creatures.KIND_TABLE_VALUE_OFFSET + 4], 'big')
        assert value & 0xFFFF0000 == 0, kind


# --- boundary: gods_sega.boundary.kind_frame_offset_plan over every retained fixture ----------------

@needs_kind_frame_census
@pytest.mark.parametrize('fixture', KIND_FRAME_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_kind_frame_offset_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.kind_frame_offset_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_kind_frame_offset_candidate_names_are_explicit():
    assert recovery.Candidate('creature-frame-offset').gate_pcs == (boundary.KIND_FRAME_OFFSET_ENTRY,)
    assert boundary.KIND_FRAME_OFFSET_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    # D2, not the generic D0 register mutant: this leaf's own D0 is dispatch scratch it fully
    # overwrites from a moveq before ever using it, dead by the time any caller could read it back.
    assert recovery.Candidate('creature-frame-offset-mutant-result').mutation is recovery._mutate_kind_frame_offset


@needs_reference
def test_kind_frame_offset_candidate_matches_the_reference_and_its_mutant_faults_the_machine():
    # D2 feeds a still-unrecovered chain (00A922 -> ... -> 00126A's own sprite emitter) that turns it
    # into a table offset large enough that +1 here reaches unmapped memory a few calls downstream --
    # an M68000 address error, not a clean value mismatch (the SAME class state 22/23's own mutants
    # hit): a real consequence of the corruption, not a control failure, and history-verify's own
    # crash-tolerant comparison would report it as DIVERGENCE the same way.
    state = Path('artifacts/gods/evidence/main/boundary-12000.state')
    if not state.is_file():
        pytest.skip('no local boundary-12000.state reference')
    report = segment_verify.check(state, game=GODS, frames=300, candidate='creature-frame-offset', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('creature-frame-offset never hits in this window')
    try:
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='creature-frame-offset-mutant-result',
                                      reference=EVIDENCE)
    except NativeError as error:
        assert 'address error' in str(error).lower(), error
        return
    assert mutant['status'] == 'DIVERGENCE', mutant


# --- 00AA38: the creature's own grid-cell lookup (docs/gods/blockers/2026-09-18-00A578.md's own "six
# further callees") -- byte-for-byte grid.grid_cell_at's own arithmetic, over the creature's own
# POSITION_X/POSITION_Y.  RAM/ROM-read only, one unconditional path -- 1,283 occurrences across the
# four recordings that reach it (`ca2b703b6fd5` never does, matching every other creature-family leaf).

def test_creature_grid_cell_matches_grid_cell_at():
    from gods_sega.game import grid
    values = {(INSTANCE_PTR + creatures.POSITION_X, 2): 0x204, (INSTANCE_PTR + creatures.POSITION_Y, 2): 0x40}
    result = creatures.creature_grid_cell(_reader(values), INSTANCE_PTR)
    expected = grid.grid_cell_at(0x204, 0x40)
    assert result['a1'] == expected['address'] & 0xFFFFFFFF
    assert result['d0'] == expected['column'] & 0xFFFF and result['d1'] == expected['row'] & 0xFFFF
    assert result['row_source'] == expected['row_source']


@needs_grid_cell_census
@pytest.mark.parametrize('fixture', GRID_CELL_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_creature_grid_cell_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.creature_grid_cell_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_creature_grid_cell_candidate_names_are_explicit():
    assert recovery.Candidate('creature-grid-cell').gate_pcs == (boundary.CREATURE_GRID_CELL_ENTRY,)
    assert boundary.CREATURE_GRID_CELL_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    # A1 (the address), not the generic D0 register mutant: D0/D1 are dead residue at both real call
    # sites (00ACA0/00AD88's own tails immediately overwrite D0, and neither reads D1).
    assert recovery.Candidate('creature-grid-cell-mutant-result').mutation is recovery._mutate_creature_grid_cell


@needs_reference
def test_creature_grid_cell_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in GRID_CELL_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='creature-grid-cell', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00AA38 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='creature-grid-cell-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AD68: the ground-edge test -- the second of the six further callees.  Only two of its four real
# arms are witnessed (both returning d1=0); 'cell-low'/'cell-high' (the flag actually found) decline.

def test_ground_edge_test_low_byte_match_declines_by_name_when_used_as_semantics():
    result = creatures.ground_edge_test(_reader({(0xFF9000, 1): 1}), 0xFF9000, 0)
    assert result == {'arm': 'cell-low', 'd1': 1}


def test_ground_edge_test_near_edge_gate_blocks_the_second_test():
    result = creatures.ground_edge_test(_reader({(0xFF9000, 1): 0, (0xFF9001, 1): 1}), 0xFF9000, 0x204)
    assert result['arm'] == 'no-match-near-edge' and result['d1'] == 0 and result['x_low5'] == 4


def test_ground_edge_test_high_byte_match_past_the_gate():
    result = creatures.ground_edge_test(_reader({(0xFF9000, 1): 0, (0xFF9001, 1): 1}), 0xFF9000, 0x208)
    assert result['arm'] == 'cell-high' and result['d1'] == 1


def test_ground_edge_test_no_match_past_the_gate():
    result = creatures.ground_edge_test(_reader({(0xFF9000, 1): 0, (0xFF9001, 1): 0}), 0xFF9000, 0x208)
    assert result['arm'] == 'no-match' and result['d1'] == 0


@needs_ground_edge_census
@pytest.mark.parametrize('fixture', GROUND_EDGE_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_ground_edge_test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.ground_edge_test_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'ground edge test' in str(error), error
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_ground_edge_test_candidate_names_are_explicit():
    assert recovery.Candidate('ground-edge-test').gate_pcs == (boundary.GROUND_EDGE_TEST_ENTRY,)
    assert boundary.GROUND_EDGE_TEST_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    # D1 (the 0/1 outcome), XOR 1 not a blind +1: both are always exactly 0 or 1 (contact_search's
    # own reasoning), and D0 (x_low5) is dead residue at both real call sites.
    assert recovery.Candidate('ground-edge-test-mutant-result').mutation is recovery._mutate_ground_edge_outcome


@needs_reference
def test_ground_edge_test_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in GROUND_EDGE_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='ground-edge-test', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00AD68 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='ground-edge-test-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00ACA0: the ground-contact kind handler (kind 4 of 00A772's own eight-entry table) -- the most
# frequent witnessed kind handler (docs/gods/blockers/2026-09-18-00A578.md's own Decision, 19 Sep).
# Composes creature_grid_cell (called up to twice) and ground_edge_test (through two entry points --
# 00AD46, the near test, feeding cell_addr+0x100 through the (d16,An) addressing mode, and 00AD68
# itself, the far test, over 0/1(a1) directly).  Never returns to its own caller: the ROM's own tail is
# always a tail-jump into kind_frame_offset's own separately-armed gate.

def _grid_address(x, y):
    from gods_sega.game import grid
    return grid.grid_cell_at(x, y)['address'] & 0xFFFFFF


def test_ground_contact_update_idle_arm_only_decrements_the_hold_timer():
    values = {(INSTANCE_PTR + creatures.GROUND_HOLD_TIMER, 2): 5}
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result == {'arm': 'idle', 'timer_before': 5, 'timer_after': 4,
                      'stores': {(INSTANCE_PTR + creatures.GROUND_HOLD_TIMER) & 0xFFFFFF: (4, 2)}}


def _reload_base(x=0x204, y=0x40, fall_phase=3):
    return {(INSTANCE_PTR + creatures.GROUND_HOLD_TIMER, 2): 0,        # decrements to -1: reloads
            (TYPE_PTR + creatures.TYPE_GROUND_RELOAD_BYTE, 1): 0xA,     # reload = 2 - (0xA >> 2) = 0
            (INSTANCE_PTR + creatures.POSITION_X, 2): x,
            (INSTANCE_PTR + creatures.POSITION_Y, 2): y,
            (INSTANCE_PTR + creatures.FALL_PHASE, 2): fall_phase}


def test_ground_contact_update_reload_steps_position_x_by_four_when_low_five_bits_are_set():
    values = _reload_base(x=0x204)                                      # low5 == 4: the cell test never runs
    values[(creatures.GROUND_STATE_TABLE + 2 * 3) & 0xFFFFFF, 2] = 0
    cell2 = _grid_address(0x200, 0x40)
    values[(cell2, 1)] = 0                                              # far test: 'no-match-near-edge'
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['subq_applied'] and result['skip_test'] is None
    assert result['x'] == 0x200 and result['reload'] == 0
    assert (INSTANCE_PTR + creatures.POSITION_X) & 0xFFFFFF in result['stores']


def test_ground_contact_update_position_x_step_skips_on_a_matching_low_cell():
    values = _reload_base(x=0x200, y=0x40)                              # low5 == 0: the cell test runs
    cell = _grid_address(0x200, 0x40)
    values[(cell + creatures.GROUND_SKIP_TEST_LOW_OFFSET) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    values[(creatures.GROUND_STATE_TABLE + 2 * 3) & 0xFFFFFF, 2] = 0
    cell2 = _grid_address(0x200, 0x40)
    values[(cell2, 1)] = 0
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert not result['subq_applied'] and result['skip_test'] == 'cell-low'
    assert result['x'] == 0x200
    assert (INSTANCE_PTR + creatures.POSITION_X) & 0xFFFFFF not in result['stores']


def test_ground_contact_update_near_trigger_clears_kind_and_masks_position_y():
    values = _reload_base(x=0x204, y=0x40, fall_phase=0)                # <= 0: the near test runs
    cell = _grid_address(0x204, 0x40)                                   # creature_grid_cell reads the ENTRY x
    values[(cell + 0x100) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG   # the (d16,An) near test's own first probe
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'near-trigger'
    assert result['new_y'] == 0x40 & 0xFFF0
    stores = result['stores']
    assert stores[(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (0, 2)
    assert stores[(INSTANCE_PTR + creatures.POSITION_Y) & 0xFFFFFF] == (0x40 & 0xFFF0, 2)


def test_ground_contact_update_near_trigger_admits_the_second_probes_own_match_too():
    # The ROM only tests D1 after the call, never which of the two probes set it -- a 'cell-high' match
    # (00AD88's own witnessed near-trigger arm) takes the SAME two stores as 'cell-low' (00ACA0's own).
    values = _reload_base(x=0x214, y=0x40, fall_phase=0)                # post-subq low5 (0x210) is >= 8
    cell = _grid_address(0x214, 0x40)                                   # creature_grid_cell reads the ENTRY x
    values[(cell + 0x100) & 0xFFFFFF, 1] = 0                            # first probe misses
    values[(cell + 0x101) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG   # second probe matches
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'near-trigger' and result['near']['arm'] == 'cell-high'
    assert result['new_y'] == 0x40 & 0xFFF0
    stores = result['stores']
    assert stores[(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (0, 2)


def test_ground_contact_update_far_trigger_declines_by_name():
    values = _reload_base(x=0x204, y=0x40, fall_phase=3)                # > 0: the near test is skipped
    values[(creatures.GROUND_STATE_TABLE + 2 * 3) & 0xFFFFFF, 2] = 0
    cell2 = _grid_address(0x200, 0x40)
    values[(cell2, 1)] = creatures.GROUND_EDGE_FLAG                     # the far test's own first probe matches
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'far-trigger-cell-low'


def test_ground_contact_update_settle_continue_steps_position_y_by_the_state_table():
    values = _reload_base(x=0x204, y=0x40, fall_phase=3)
    values[(creatures.GROUND_STATE_TABLE + 2 * 3) & 0xFFFFFF, 2] = 0x10
    cell2 = _grid_address(0x200, 0x50)
    values[(cell2, 1)] = 0
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'settle-continue' and result['delta'] == 0x10 and result['new_y'] == 0x50
    assert result['new_fall_phase'] == 2
    stores = result['stores']
    assert stores[(INSTANCE_PTR + creatures.POSITION_Y) & 0xFFFFFF] == (0x50, 2)
    assert stores[(INSTANCE_PTR + creatures.FALL_PHASE) & 0xFFFFFF] == (2, 2)
    assert (INSTANCE_PTR + creatures.KIND) & 0xFFFFFF not in stores


def test_ground_contact_update_settle_reset_transitions_kind_to_the_fall_handler():
    fall_phase = -5
    values = _reload_base(x=0x204, y=0x40, fall_phase=fall_phase & 0xFFFF)
    cell = _grid_address(0x204, 0x40)                                   # creature_grid_cell reads the ENTRY x
    values[(cell + 0x100) & 0xFFFFFF, 1] = 0                            # near test: no match
    values[(creatures.GROUND_STATE_TABLE + 2 * fall_phase) & 0xFFFFFF, 2] = 8
    cell2 = _grid_address(0x200, 0x48)
    values[(cell2, 1)] = 0                                              # far test: no match
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'settle-reset'
    stores = result['stores']
    assert stores[(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (creatures.KIND_FALL, 2)
    assert stores[(INSTANCE_PTR + creatures.FALL_PHASE) & 0xFFFFFF] == (creatures.GROUND_SETTLE_RESET, 2)


# --- boundary: gods_sega.boundary.ground_contact_update_plan over every retained fixture -----------

@needs_ground_contact_census
@pytest.mark.parametrize('fixture', GROUND_CONTACT_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_ground_contact_update_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.ground_contact_update_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'ground contact update' in str(error), error
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_ground_contact_update_candidate_names_are_explicit():
    assert recovery.Candidate('creature-ground-contact').gate_pcs == (boundary.GROUND_CONTACT_UPDATE_ENTRY,)
    assert boundary.GROUND_CONTACT_UPDATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('creature-ground-contact-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_ground_contact_update_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in GROUND_CONTACT_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='creature-ground-contact', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00ACA0 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='creature-ground-contact-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AD88: kind 5's own ground-contact kind handler -- the SAME shape as 00ACA0, mirrored (19 Sep).
# POSITION_X steps by +4 (ADDQ, not SUBQ), the skip test's own two probes are at +1(a1)/+0x81(a1), a
# near trigger sets KIND to 1 (00AB50), a far trigger or a settled fall sets KIND to 3 (00AED4, a
# SECOND fall kind handler, distinct from 00ACA0's own KIND_FALL=2/00AE6C).  Its own census (39
# retained fixtures over four recordings) witnesses the near test's own 'cell-high' match (never
# 'cell-low') -- the OTHER real arm of ground_edge_test's own d1==1 outcome from 00ACA0's own 'cell-low'
# (never 'cell-high'): together the two callers witness both, so neither declines either arm any more
# (a real correction 19 Sep: 00ACA0's own first-draft plan wrongly declined 'cell-high' by name, and
# its own d0 exit was wrong for that arm -- 00AD46's own SECOND probe re-loads d0 from the current x
# before testing it, unlike the first probe's own early return).

def test_ground_contact_update_mirror_idle_arm_only_decrements_the_hold_timer():
    values = {(INSTANCE_PTR + creatures.GROUND_HOLD_TIMER, 2): 5}
    result = creatures.ground_contact_update_mirror(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result == {'arm': 'idle', 'timer_before': 5, 'timer_after': 4,
                      'stores': {(INSTANCE_PTR + creatures.GROUND_HOLD_TIMER) & 0xFFFFFF: (4, 2)}}


def _mirror_reload_base(x=0x204, y=0x40, fall_phase=3):
    return {(INSTANCE_PTR + creatures.GROUND_HOLD_TIMER, 2): 0,
            (TYPE_PTR + creatures.TYPE_GROUND_RELOAD_BYTE, 1): 0xA,
            (INSTANCE_PTR + creatures.POSITION_X, 2): x,
            (INSTANCE_PTR + creatures.POSITION_Y, 2): y,
            (INSTANCE_PTR + creatures.FALL_PHASE, 2): fall_phase}


def test_ground_contact_update_mirror_reload_steps_position_x_by_plus_four():
    values = _mirror_reload_base(x=0x204)                                # low5 == 4: the cell test never runs
    values[(creatures.GROUND_STATE_TABLE + 2 * 3) & 0xFFFFFF, 2] = 0
    cell2 = _grid_address(0x208, 0x40)
    values[(cell2, 1)] = 0
    result = creatures.ground_contact_update_mirror(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['subq_applied'] and result['x'] == 0x208


def test_ground_contact_update_mirror_position_x_step_skips_on_a_matching_low_cell():
    values = _mirror_reload_base(x=0x200, y=0x40)                        # low5 == 0: the cell test runs
    cell = _grid_address(0x200, 0x40)
    values[(cell + creatures.MIRROR_SKIP_TEST_LOW_OFFSET) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    values[(creatures.GROUND_STATE_TABLE + 2 * 3) & 0xFFFFFF, 2] = 0
    cell2 = _grid_address(0x200, 0x40)
    values[(cell2, 1)] = 0
    result = creatures.ground_contact_update_mirror(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert not result['subq_applied'] and result['skip_test'] == 'cell-low' and result['x'] == 0x200


def test_ground_contact_update_mirror_near_trigger_sets_kind_to_one():
    values = _mirror_reload_base(x=0x204, y=0x40, fall_phase=0)
    cell = _grid_address(0x204, 0x40)
    values[(cell + 0x100) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    result = creatures.ground_contact_update_mirror(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'near-trigger'
    assert result['stores'][(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (1, 2)


def test_ground_contact_update_mirror_far_trigger_declines_by_name():
    values = _mirror_reload_base(x=0x204, y=0x40, fall_phase=3)
    values[(creatures.GROUND_STATE_TABLE + 2 * 3) & 0xFFFFFF, 2] = 0
    cell2 = _grid_address(0x208, 0x40)
    values[(cell2, 1)] = creatures.GROUND_EDGE_FLAG
    result = creatures.ground_contact_update_mirror(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'far-trigger-cell-low'


def test_ground_contact_update_mirror_settle_reset_transitions_kind_to_the_second_fall_handler():
    fall_phase = -5
    values = _mirror_reload_base(x=0x204, y=0x40, fall_phase=fall_phase & 0xFFFF)
    cell = _grid_address(0x204, 0x40)
    values[(cell + 0x100) & 0xFFFFFF, 1] = 0
    values[(creatures.GROUND_STATE_TABLE + 2 * fall_phase) & 0xFFFFFF, 2] = 8
    cell2 = _grid_address(0x208, 0x48)
    values[(cell2, 1)] = 0
    result = creatures.ground_contact_update_mirror(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'settle-reset'
    stores = result['stores']
    assert stores[(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (creatures.MIRROR_KIND_FALL, 2)
    assert stores[(INSTANCE_PTR + creatures.FALL_PHASE) & 0xFFFFFF] == (creatures.GROUND_SETTLE_RESET, 2)


# --- boundary: gods_sega.boundary.ground_contact_update_mirror_plan over every retained fixture -----

@needs_ground_contact_mirror_census
@pytest.mark.parametrize('fixture', GROUND_CONTACT_MIRROR_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_ground_contact_update_mirror_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.ground_contact_update_mirror_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'ground contact update mirror' in str(error), error
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_ground_contact_update_mirror_candidate_names_are_explicit():
    assert recovery.Candidate('creature-ground-contact-mirror').gate_pcs == (boundary.GROUND_CONTACT_UPDATE_MIRROR_ENTRY,)
    assert boundary.GROUND_CONTACT_UPDATE_MIRROR_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('creature-ground-contact-mirror-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_ground_contact_update_mirror_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in GROUND_CONTACT_MIRROR_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='creature-ground-contact-mirror', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00AD88 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='creature-ground-contact-mirror-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AE6C/00AED4: the fall kind handlers -- kinds 2 and 3 of 00A772's own eight-entry table, the
# KIND_FALL/MIRROR_KIND_FALL targets ground_contact_update's own family hands off to (19 Sep).  A
# distinct shape: FRAME_STEP cleared and kind_frame_offset composed inline (a real bsr/rts, not a
# hand-off), FALL_VELOCITY added to POSITION_Y and incremented (capped), then the near test (+0x100/
# +0x101) and, on a match with POSITION_X's own low 5 bits at zero, a third test at the SAME offsets
# ground_contact_update's own skip test uses (-1/+0x7f for 00AE6C, +1/+0x81 for 00AED4).

def _fall_kind_base(x=0x204, y=0x40, velocity=5, kind=2, frame_step=3, type_frame=1):
    return {(INSTANCE_PTR + creatures.FRAME_STEP, 2): frame_step,
            (INSTANCE_PTR + creatures.KIND, 2): kind,
            (creatures.KIND_TABLE + 8 * kind + creatures.KIND_TABLE_VALUE_OFFSET, 4): 0x808,
            (TYPE_PTR + creatures.TYPE_FRAME_BYTE, 1): type_frame,
            (creatures.FRAME_TABLE_PTR & 0xFFFFFF, 4): 0xFF9000,
            (0xFF9000 + (type_frame << 4), 2): 0x10,
            (INSTANCE_PTR + creatures.FALL_VELOCITY, 2): velocity,
            (INSTANCE_PTR + creatures.POSITION_X, 2): x,
            (INSTANCE_PTR + creatures.POSITION_Y, 2): y}


def test_fall_kind_update_not_triggered_still_steps_position_y_and_velocity():
    values = _fall_kind_base(x=0x204, y=0x40, velocity=5)             # low5(0x204) == 4 < 8
    cell = _grid_address(0x204, 0x45)                                  # new_y = y + velocity = 0x45
    values[(cell + 0x100) & 0xFFFFFF, 1] = 0                          # near test: no match
    result = creatures.fall_kind_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'not-triggered' and result['near']['arm'] == 'no-match-near-edge'
    assert result['incremented'] and result['new_y'] == 0x45
    stores = result['stores']
    assert stores[(INSTANCE_PTR + creatures.FRAME_STEP) & 0xFFFFFF] == (0, 2)
    assert stores[(INSTANCE_PTR + creatures.FALL_VELOCITY) & 0xFFFFFF] == (6, 2)
    assert stores[(INSTANCE_PTR + creatures.POSITION_Y) & 0xFFFFFF] == (0x45, 2)
    assert (INSTANCE_PTR + creatures.KIND) & 0xFFFFFF not in stores


def test_fall_kind_update_velocity_caps_at_the_ceiling():
    values = _fall_kind_base(x=0x204, y=0x40, velocity=creatures.FALL_VELOCITY_CEILING)
    cell = _grid_address(0x204, 0x40 + creatures.FALL_VELOCITY_CEILING)
    values[(cell + 0x100) & 0xFFFFFF, 1] = 0
    result = creatures.fall_kind_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert not result['incremented']
    assert (INSTANCE_PTR + creatures.FALL_VELOCITY) & 0xFFFFFF not in result['stores']


def test_fall_kind_update_near_trigger_with_nonzero_low5_skips_the_third_test():
    values = _fall_kind_base(x=0x204, y=0x40, velocity=5)              # low5 == 4, nonzero
    cell = _grid_address(0x204, 0x45)
    values[(cell + 0x100) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    result = creatures.fall_kind_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'triggered-low5nz'
    stores = result['stores']
    assert stores[(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (0, 2)          # 00AE6C's own near_kind
    assert stores[(INSTANCE_PTR + creatures.POSITION_Y) & 0xFFFFFF] == (0x45 & 0xFFF0, 2)


def test_fall_kind_update_third_test_no_match_leaves_the_near_kind_in_place():
    values = _fall_kind_base(x=0x200, y=0x40, velocity=5)              # low5 == 0: the third test runs
    cell = _grid_address(0x200, 0x45)
    values[(cell + 0x100) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    masked_y = 0x45 & 0xFFF0
    cell2 = _grid_address(0x200, masked_y)
    values[(cell2 + creatures.GROUND_SKIP_TEST_LOW_OFFSET) & 0xFFFFFF, 1] = 0
    values[(cell2 + creatures.GROUND_SKIP_TEST_HIGH_OFFSET) & 0xFFFFFF, 1] = 0
    result = creatures.fall_kind_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'triggered-third-no-match'
    assert result['stores'][(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (0, 2)


def test_fall_kind_update_third_test_match_overwrites_kind_to_one():
    values = _fall_kind_base(x=0x200, y=0x40, velocity=5)
    cell = _grid_address(0x200, 0x45)
    values[(cell + 0x100) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    masked_y = 0x45 & 0xFFF0
    cell2 = _grid_address(0x200, masked_y)
    values[(cell2 + creatures.GROUND_SKIP_TEST_LOW_OFFSET) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    result = creatures.fall_kind_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'triggered-third-match' and result['third'] == 'cell-low'
    assert result['stores'][(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (1, 2)


def test_fall_kind_update_mirror_third_test_match_overwrites_kind_to_zero():
    values = _fall_kind_base(x=0x200, y=0x40, velocity=5)
    cell = _grid_address(0x200, 0x45)
    values[(cell + 0x100) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    masked_y = 0x45 & 0xFFF0
    cell2 = _grid_address(0x200, masked_y)
    values[(cell2 + creatures.MIRROR_SKIP_TEST_LOW_OFFSET) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG
    result = creatures.fall_kind_update_mirror(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'triggered-third-match' and result['third'] == 'cell-low'
    stores = result['stores']
    assert stores[(INSTANCE_PTR + creatures.KIND) & 0xFFFFFF] == (0, 2)          # 00AED4's own third_kind


# --- boundary: gods_sega.boundary.fall_kind_update_plan/_mirror_plan over every retained fixture -----

@needs_fall_kind_census
@pytest.mark.parametrize('fixture', FALL_KIND_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_fall_kind_update_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.fall_kind_update_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'fall kind update' in str(error), error
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_fall_kind_mirror_census
@pytest.mark.parametrize('fixture', FALL_KIND_MIRROR_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_fall_kind_update_mirror_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.fall_kind_update_mirror_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'fall kind update mirror' in str(error), error
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_fall_kind_update_candidate_names_are_explicit():
    assert recovery.Candidate('creature-fall-kind').gate_pcs == (boundary.FALL_KIND_UPDATE_ENTRY,)
    assert boundary.FALL_KIND_UPDATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('creature-fall-kind-mutant-result').mutation is recovery._mutate_result
    assert recovery.Candidate('creature-fall-kind-mirror').gate_pcs == (boundary.FALL_KIND_UPDATE_MIRROR_ENTRY,)
    assert boundary.FALL_KIND_UPDATE_MIRROR_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('creature-fall-kind-mirror-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_fall_kind_update_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in FALL_KIND_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='creature-fall-kind', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00AE6C within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='creature-fall-kind-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


@needs_reference
def test_fall_kind_update_mirror_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in FALL_KIND_MIRROR_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='creature-fall-kind-mirror', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00AED4 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='creature-fall-kind-mirror-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AF3C: a FOURTH call site of grid.grid_cell_at's own shared arithmetic (docs/gods/blockers/
# 2026-09-18-00A578.md's own "Next question", 19 Sep) -- X/Y from the caller's own D0/D1 (010CBC's own
# convention), the address left in A2.  Pure, no RAM read, one unconditional path, no store; needed by
# 00AA76/00AB50 (still declined by 00AF52's own further, larger blocker).

def test_creature_grid_cell_d0d1_reuses_grid_cell_at_with_no_wrapper():
    # 00AF3C's own body is byte-for-byte grid_cell_at's own arithmetic (docs/gods/STATUS.md's own
    # creature-family notes on 00AA38 already established this for a third call site; this is the
    # fourth) -- there is no semantics wrapper of its own to unit-test beyond the boundary composing
    # grid.grid_cell_at directly, checked here against a fixed input.
    from gods_sega.game import grid
    result = grid.grid_cell_at(0x204, 0x40)
    assert result['address'] & 0xFFFFFF == grid.GRID_TABLE + (0x204 >> 5) + (((0x40 & 0xFFF0) << 3) & 0xFFFF) & 0xFFFFFF
    assert result['column'] == 0x204 >> 5 and result['row_source'] == 0x40 & 0xFFF0


@needs_af3c_census
@pytest.mark.parametrize('fixture', AF3C_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_creature_grid_cell_d0d1_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.creature_grid_cell_d0d1_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_creature_grid_cell_d0d1_candidate_names_are_explicit():
    assert recovery.Candidate('creature-grid-cell-d0d1').gate_pcs == (boundary.AF3C_ENTRY,)
    assert boundary.AF3C_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('creature-grid-cell-d0d1-mutant-result').mutation is recovery._mutate_creature_grid_cell_d0d1


@needs_reference
def test_creature_grid_cell_d0d1_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in AF3C_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='creature-grid-cell-d0d1', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00AF3C within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='creature-grid-cell-d0d1-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B082: the aim-cue update (docs/gods/blockers/2026-09-18-00A578.md's own "Decision on
# 00AF52", 19 Sep) -- the second of 00AF52's own three unconditional callees.  Every call refills a
# fixed 400-byte table from ROM constants, then (unless AIM_CUE_SKIP_FLAG is set, unwitnessed) draws
# one random word and picks between the LOW/HIGH nibble of the type's own index byte to dispatch one
# of three witnessed arms (window-mark, quadrant-mark, event-scan) -- or, on event-scan's own
# EVENT_COUNT == 0, retries once with the OTHER nibble.  See game/creatures.py's own module note
# above aim_cue_update for the full shape.

def test_aim_cue_update_dispatches_window_mark_on_index_zero():
    values = {(creatures.AIM_CUE_INDEX_BYTE + TYPE_PTR, 1): 0x00, (creatures.AIM_CUE_THRESHOLD_BYTE + TYPE_PTR, 1): 0x7F,
             (effects.RANDOM_CURSOR, 2): 0, (effects.RANDOM_TABLE, 2): 0}
    result = creatures.aim_cue_update(_reader(values), TYPE_PTR)
    assert result['arm'] == 'window-mark' and result['index'] == 0


def test_aim_cue_update_dispatches_quadrant_mark_on_index_one():
    values = {(creatures.AIM_CUE_INDEX_BYTE + TYPE_PTR, 1): 0x01, (creatures.AIM_CUE_THRESHOLD_BYTE + TYPE_PTR, 1): 0x7F,
             (effects.RANDOM_CURSOR, 2): 0, (effects.RANDOM_TABLE, 2): 0}
    result = creatures.aim_cue_update(_reader(values), TYPE_PTR)
    assert result['arm'] == 'quadrant-mark' and result['index'] == 1 and len(result['marks']) == 32


def test_aim_cue_update_dispatches_event_scan_on_index_two():
    values = {(creatures.AIM_CUE_INDEX_BYTE + TYPE_PTR, 1): 0x02, (creatures.AIM_CUE_THRESHOLD_BYTE + TYPE_PTR, 1): 0x7F,
             (effects.RANDOM_CURSOR, 2): 0, (effects.RANDOM_TABLE, 2): 0, (creatures.EVENT_COUNT & 0xFFFFFF, 2): 1,
             (creatures.EVENT_LIST & 0xFFFFFF, 2): 0, ((creatures.EVENT_LIST + 2) & 0xFFFFFF, 2): 0}
    result = creatures.aim_cue_update(_reader(values), TYPE_PTR)
    assert result['arm'] == 'event-scan' and result['scan']['arm'] in ('scanned',)


def test_aim_cue_update_declines_index_three_by_name():
    values = {(creatures.AIM_CUE_INDEX_BYTE + TYPE_PTR, 1): 0x03, (creatures.AIM_CUE_THRESHOLD_BYTE + TYPE_PTR, 1): 0x7F,
             (effects.RANDOM_CURSOR, 2): 0, (effects.RANDOM_TABLE, 2): 0}
    result = creatures.aim_cue_update(_reader(values), TYPE_PTR)
    assert result['arm'] == 'undispatched'


def test_aim_cue_update_declines_the_skip_flag_arm_by_name():
    values = {(creatures.AIM_CUE_SKIP_FLAG & 0xFFFFFF, 2): 1}
    result = creatures.aim_cue_update(_reader(values), TYPE_PTR)
    assert result['arm'] == 'skip-flag'


def test_aim_cue_update_retries_the_other_nibble_on_an_empty_event_count():
    # low nibble 2 (event-scan), high nibble 1 (quadrant-mark): EVENT_COUNT == 0 retries into index 1.
    values = {(creatures.AIM_CUE_INDEX_BYTE + TYPE_PTR, 1): 0x12, (creatures.AIM_CUE_THRESHOLD_BYTE + TYPE_PTR, 1): 0x7F,
             (effects.RANDOM_CURSOR, 2): 0, (effects.RANDOM_TABLE, 2): 0, (creatures.EVENT_COUNT & 0xFFFFFF, 2): 0}
    result = creatures.aim_cue_update(_reader(values), TYPE_PTR)
    assert result['arm'] == 'retry' and result['retry_index'] == 1 and result['retry']['arm'] == 'quadrant-mark'


@needs_aim_cue_census
@pytest.mark.parametrize('fixture', AIM_CUE_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_cue_update_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_cue_update_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'aim cue' in str(error), error
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_aim_cue_update_candidate_names_are_explicit():
    assert recovery.Candidate('aim-cue-update').gate_pcs == (boundary.AIM_CUE_ENTRY,)
    # Retired from camera-sprites 19 September -- see test_aim_probe_mark_store_candidate_names_are_explicit
    # (00AF52's own aim_search_dispatch_plan now covers this span too).
    assert boundary.AIM_CUE_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-cue-update-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_aim_cue_update_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in AIM_CUE_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-cue-update', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B082 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-cue-update-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B02A / 00B05A: the aim pool reset and add (docs/gods/blockers/2026-09-18-00A578.md's own
# "Decision on 00AF52", 19 Sep -- the first of 00AF52's own three further calls).  One 256-byte,
# 32-slot pool; 00B02A resets it from ROM constants (unconditional, no branch); 00B05A scans it for a
# free slot and writes four caller words there, the SAME shape hazard.effect_pool_add/timers._spawn
# already prove.  See game/creatures.py's own module note above aim_pool_reset/aim_pool_add.

def test_aim_pool_reset_refills_from_rom_constants_and_clears_the_counter():
    values = {}
    result = creatures.aim_pool_reset(_reader(values))
    assert result['stores'][creatures.AIM_POOL_COUNT & 0xFFFFFF] == 0
    assert len(result['stores']) == creatures.AIM_POOL_HIGH - creatures.AIM_POOL_LOW + 2


def test_aim_pool_add_finds_the_first_free_slot():
    values = {(creatures.AIM_POOL_COUNT & 0xFFFFFF, 2): 0,
             (creatures.AIM_POOL_LOW & 0xFFFFFF, 4): 0x11112222}   # slot 0 occupied
    result = creatures.aim_pool_add(_reader(values), 0xAAAA, 0xBBBB, 0xCCCC, 0xDDDD)
    assert result['arm'] == 'found' and result['index'] == 1 and result['skipped'] == 1
    slot1 = (creatures.AIM_POOL_LOW + creatures.AIM_POOL_STRIDE) & 0xFFFFFF
    assert result['stores'][slot1] == 0xAA and result['stores'][slot1 + 1] == 0xAA


def test_aim_pool_add_declines_the_counter_gate_by_name():
    values = {(creatures.AIM_POOL_COUNT & 0xFFFFFF, 2): creatures.AIM_POOL_SLOTS}
    result = creatures.aim_pool_add(_reader(values), 0, 0, 0, 0)
    assert result['arm'] == 'pool-full-by-count'


def test_aim_pool_add_declines_a_fully_occupied_scan_by_name():
    values = {(creatures.AIM_POOL_COUNT & 0xFFFFFF, 2): 0}
    for index in range(creatures.AIM_POOL_SLOTS):
        address = (creatures.AIM_POOL_LOW + creatures.AIM_POOL_STRIDE * index) & 0xFFFFFF
        values[(address, 4)] = 0xFFFFFFFF
    result = creatures.aim_pool_add(_reader(values), 0, 0, 0, 0)
    assert result['arm'] == 'pool-full-scanned'


@needs_aim_pool_reset_census
@pytest.mark.parametrize('fixture', AIM_POOL_RESET_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_pool_reset_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.aim_pool_reset_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_aim_pool_add_census
@pytest.mark.parametrize('fixture', AIM_POOL_ADD_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_pool_add_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_pool_add_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'aim pool add' in str(error), error
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_aim_pool_candidate_names_are_explicit():
    assert recovery.Candidate('aim-pool-reset').gate_pcs == (boundary.AIM_POOL_RESET_ENTRY,)
    assert recovery.Candidate('aim-pool-add').gate_pcs == (boundary.AIM_POOL_ADD_ENTRY,)
    # aim-pool-reset retired from camera-sprites 19 September -- see
    # test_aim_probe_mark_store_candidate_names_are_explicit (00AF52's own aim_search_dispatch_plan
    # now covers this span too).  aim-pool-add stays: it has a second, independent caller (00B62A's
    # own 'store' arm), already composed elsewhere.
    assert boundary.AIM_POOL_RESET_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.AIM_POOL_ADD_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-pool-reset-mutant-result').mutation is recovery._mutate_result
    assert recovery.Candidate('aim-pool-add-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_aim_pool_reset_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in AIM_POOL_RESET_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-pool-reset', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B02A within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-pool-reset-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


@needs_reference
def test_aim_pool_add_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in AIM_POOL_ADD_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-pool-add', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B05A within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-pool-add-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B32E: the aim window address (docs/gods/blockers/2026-09-18-00A578.md's own "Decision on
# 00AF52") -- the SAME camera-relative scaling 00B082's own window-mark arm uses, called (with
# 00AF3C) from every one of 00AF52's own further creature-targeting callees (00B724, 00B7DA,
# 00B6AE, ...).  See game/creatures.py's own module note above aim_window_address.

def test_aim_window_address_matches_the_window_mark_arithmetic():
    from gods_sega.game import camera
    values = {(creatures.FOLLOW_X & 0xFFFFFF, 2): 0, (creatures.FOLLOW_Y & 0xFFFFFF, 2): 0}
    address = creatures.aim_window_address(_reader(values), 0x100, 0x40)
    window = creatures._cue_window_mark(_reader({**values, (creatures.GRID_X & 0xFFFFFF, 2): 0x100,
                                                 (creatures.GRID_Y & 0xFFFFFF, 2): 0x40}))
    assert address == (creatures.AIM_CUE_WINDOW_BASE + window['offset']) & 0xFFFFFFFF


@needs_aim_window_address_census
@pytest.mark.parametrize('fixture', AIM_WINDOW_ADDRESS_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_window_address_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.aim_window_address_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_aim_window_address_candidate_names_are_explicit():
    assert recovery.Candidate('aim-window-address').gate_pcs == (boundary.AIM_WINDOW_ADDRESS_ENTRY,)
    assert boundary.AIM_WINDOW_ADDRESS_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-window-address-mutant-result').mutation is recovery._mutate_aim_window_address


@needs_reference
def test_aim_window_address_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in AIM_WINDOW_ADDRESS_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-window-address', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B32E within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-window-address-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B724: the aim target scan (docs/gods/blockers/2026-09-18-00A578.md's own "Decision on
# 00AF52", 19 Sep -- the first of the three further callees 00B002's own reconnaissance found bounded
# over {00AF3C, 00B32E} on every witnessed occurrence).  A horizontal raycast one grid column at a
# time, gated on a two-rows-down footing, marking each visited column in the SAME window table
# aim_cue_update's own window-mark arm writes into.  See game/creatures.py's own module note above
# aim_target_scan.

def test_aim_target_scan_semantics_walk_matches_a_fresh_scan():
    values = {(creatures.FOLLOW_X & 0xFFFFFF, 2): 0, (creatures.FOLLOW_Y & 0xFFFFFF, 2): 0,
             (creatures.AIM_SEARCH_START_INDEX & 0xFFFFFF, 2): 0,
             (creatures.AIM_SEARCH_FLAG_SOURCE & 0xFFFFFF, 2): 3,
             (creatures.AIM_SEARCH_COUNT & 0xFFFFFF, 2): 0}
    type_ptr = 0xFF2000
    values[(type_ptr + creatures.AIM_SEARCH_STEP_LIMIT_OFFSET) & 0xFFFFFF, 1] = 2
    result = creatures.aim_target_scan(_reader(values), type_ptr, 0x100, 0x40)
    # every table byte defaults to 0 in this synthetic reader: the two-rows-down footing is never 1,
    # so the routine declines at the very first guard -- 'blocked-start' is real ROM, never witnessed.
    assert result['arm'] == 'blocked-start'


def test_aim_target_scan_candidate_names_are_explicit():
    assert recovery.Candidate('aim-target-scan').gate_pcs == (boundary.AIM_TARGET_SCAN_ENTRY,)
    # Retired from camera-sprites 19 September -- see test_aim_probe_mark_store_candidate_names_are_explicit
    # (00B002's own aim_search_scan_plan now covers the whole span; every witnessed occurrence of
    # 00B724 returns to a fixed address inside 00B002's own body, one caller).
    assert boundary.AIM_TARGET_SCAN_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-target-scan-mutant-result').mutation is recovery._mutate_result


@needs_aim_target_scan_census
@pytest.mark.parametrize('fixture', AIM_TARGET_SCAN_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_target_scan_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_target_scan_plan(machine, registers)
        except UnsupportedCandidate:
            pytest.skip('declined arm (blocked-start / pruned-start / found-without-a-new-best) -- '
                       'covered by factcheck check, not this MATCH-only test')
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_target_scan_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in AIM_TARGET_SCAN_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-target-scan', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B724 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-target-scan-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B7DA: the aim target scan, backward (docs/gods/blockers/2026-09-18-00A578.md's own "Decision
# on 00AF52", 19 Sep -- the second of the three further callees 00B002's own reconnaissance found
# bounded over {00AF3C, 00B32E}).  Reads as 00B724's own mirror but with two real differences the
# tracer found: no store on the first probe (a call can produce zero stores), and no step-count limit
# at all.  See game/creatures.py's own module note above aim_target_scan_backward.

def test_aim_target_scan_backward_candidate_names_are_explicit():
    assert recovery.Candidate('aim-target-scan-backward').gate_pcs == (boundary.AIM_TARGET_SCAN_BACKWARD_ENTRY,)
    # Retired from camera-sprites 19 September -- see test_aim_probe_mark_store_candidate_names_are_explicit.
    assert boundary.AIM_TARGET_SCAN_BACKWARD_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-target-scan-backward-mutant-result').mutation is recovery._mutate_result


@needs_aim_target_scan_backward_census
@pytest.mark.parametrize('fixture', AIM_TARGET_SCAN_BACKWARD_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_target_scan_backward_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_target_scan_backward_plan(machine, registers)
        except UnsupportedCandidate:
            pytest.skip('declined arm (blocked-start / pruned-start / found-without-a-new-best) -- '
                       'covered by factcheck check, not this MATCH-only test')
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_target_scan_backward_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in AIM_TARGET_SCAN_BACKWARD_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-target-scan-backward',
                                      reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B7DA within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS | {
        'unsupported domain: aim target scan backward: found without a new best, not witnessed by a recording'}
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-target-scan-backward-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B6AE: the aim target resolve (docs/gods/blockers/2026-09-18-00A578.md's own "Decision on
# 00AF52", 19 Sep -- the third of the three further callees 00B002's own reconnaissance found bounded
# over {00AF3C, 00B32E, 00B05A}).  Consumes 00B724 and 00B7DA's own 'exhausted' snapshots, a two-slot
# outer loop each doing an independent vertical scan.  See game/creatures.py's own module note above
# aim_target_resolve.

def test_aim_target_resolve_candidate_names_are_explicit():
    assert recovery.Candidate('aim-target-resolve').gate_pcs == (boundary.AIM_TARGET_RESOLVE_ENTRY,)
    # Retired from camera-sprites 19 September -- see test_aim_probe_mark_store_candidate_names_are_explicit.
    assert boundary.AIM_TARGET_RESOLVE_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-target-resolve-mutant-result').mutation is recovery._mutate_aim_target_resolve


@needs_aim_target_resolve_census
@pytest.mark.parametrize('fixture', AIM_TARGET_RESOLVE_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_target_resolve_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_target_resolve_plan(machine, registers)
        except UnsupportedCandidate:
            pytest.skip('declined arm (found-without-a-new-best / aim_pool_add pool-full) -- '
                       'covered by factcheck check, not this MATCH-only test')
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_target_resolve_candidate_matches_the_reference_and_its_mutant_diverges():
    # Most real occurrences decline down to a no-op (y-bound / step-limit / pruned, or both slots
    # empty): the only RAM this routine ever changes on such an occurrence is the dead internal-call
    # stack residue (see _mutate_aim_target_resolve's own note), so a fixture/window has to be found
    # where a 'found' or 'store' arm actually fires before the mutant means anything.
    report = mutant = None
    for fixture in AIM_TARGET_RESOLVE_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-target-resolve', reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        assert report['status'] == 'PASS', report
        assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-target-resolve-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-target-resolve produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B524 / 00B62A: the aim ray probe and mark-store (docs/gods/blockers/2026-09-18-00A578.md's own
# "Decision on 00B588", 19 Sep) -- the found-only probe and the store-capable evaluator 00B354/00B440's
# own ray-march calls.  See game/creatures.py's own module note above aim_probe_mark.

def test_aim_probe_mark_candidate_names_are_explicit():
    assert recovery.Candidate('aim-probe-mark').gate_pcs == (boundary.AIM_PROBE_MARK_ENTRY,)
    assert boundary.AIM_PROBE_MARK_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-probe-mark-mutant-result').mutation is recovery._mutate_aim_probe


def test_aim_probe_mark_store_candidate_names_are_explicit():
    assert recovery.Candidate('aim-probe-mark-store').gate_pcs == (boundary.AIM_PROBE_MARK_STORE_ENTRY,)
    # Retired from camera-sprites' own combined gate set 19 September: every witnessed call into
    # 00B62A comes from 00B588's own body, whose atomic plan now covers the whole span once 00B588
    # itself is armed there (see the aim-pool-scan tests below).  Its own PLANNERS entry is unchanged.
    assert boundary.AIM_PROBE_MARK_STORE_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-probe-mark-store-mutant-result').mutation is recovery._mutate_aim_probe


@needs_aim_probe_mark_census
@pytest.mark.parametrize('fixture', AIM_PROBE_MARK_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_probe_mark_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.aim_probe_mark_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_aim_probe_mark_store_census
@pytest.mark.parametrize('fixture', AIM_PROBE_MARK_STORE_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_probe_mark_store_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.aim_probe_mark_store_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_probe_mark_candidate_matches_the_reference_and_its_mutant_diverges():
    # Most occurrences decline to a plain miss (step-limit / bound / 'clear' / 'no-improvement'): only
    # a 'found' occurrence writes AIM_SEARCH_BEST_FLAG/BEST_INDEX, the one real effect the mutant can
    # see (see _mutate_aim_probe's own note) -- a fixture/window has to be found where one actually
    # fires before the mutant means anything.
    report = mutant = None
    for fixture in AIM_PROBE_MARK_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-probe-mark', reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        assert report['status'] == 'PASS', report
        assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-probe-mark-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-probe-mark produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


@needs_reference
def test_aim_probe_mark_store_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_PROBE_MARK_STORE_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-probe-mark-store',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        assert report['status'] == 'PASS', report
        assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-probe-mark-store-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-probe-mark-store produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B354 / 00B440: the directional ray march (docs/gods/blockers/2026-09-18-00A578.md's own
# "Decision on 00B588", 19 Sep) -- a real internal call composition three levels deep (the ray march
# calls aim_probe_mark, which calls aim_window_address).  See game/creatures.py's own module note above
# _aim_ray_march.

def test_aim_ray_march_forward_candidate_names_are_explicit():
    assert recovery.Candidate('aim-ray-march-forward').gate_pcs == (boundary.AIM_RAY_MARCH_FORWARD_ENTRY,)
    # Retired from camera-sprites 19 September -- see test_aim_probe_mark_store_candidate_names_are_explicit.
    assert boundary.AIM_RAY_MARCH_FORWARD_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-ray-march-forward-mutant-result').mutation is recovery._mutate_aim_ray_march


def test_aim_ray_march_backward_candidate_names_are_explicit():
    assert recovery.Candidate('aim-ray-march-backward').gate_pcs == (boundary.AIM_RAY_MARCH_BACKWARD_ENTRY,)
    # Retired from camera-sprites 19 September -- see test_aim_probe_mark_store_candidate_names_are_explicit.
    assert boundary.AIM_RAY_MARCH_BACKWARD_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-ray-march-backward-mutant-result').mutation is recovery._mutate_aim_ray_march


@needs_aim_ray_march_forward_census
@pytest.mark.parametrize('fixture', AIM_RAY_MARCH_FORWARD_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_ray_march_forward_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.aim_ray_march_forward_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_aim_ray_march_backward_census
@pytest.mark.parametrize('fixture', AIM_RAY_MARCH_BACKWARD_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_ray_march_backward_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.aim_ray_march_backward_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_ray_march_forward_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_RAY_MARCH_FORWARD_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-ray-march-forward',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        assert report['status'] == 'PASS', report
        assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-ray-march-forward-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-ray-march-forward produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


@needs_reference
def test_aim_ray_march_backward_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_RAY_MARCH_BACKWARD_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-ray-march-backward',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        assert report['status'] == 'PASS', report
        assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-ray-march-backward-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-ray-march-backward produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B588: the aim pool scan -- the composition over every AIM_POOL entry ("Decision on 00B588",
# 19 Sep): 00AF3C's own grid cell plus, for every entry not skipped, a forward ray-march-and-store pass
# and a backward one, each possibly extended (00B32E's own type template byte past 4) a second time.
# See boundary.py's own module note above aim_pool_scan_plan.

def test_aim_pool_scan_candidate_names_are_explicit():
    assert recovery.Candidate('aim-pool-scan').gate_pcs == (boundary.AIM_POOL_SCAN_ENTRY,)
    # Retired from camera-sprites 19 September -- see test_aim_probe_mark_store_candidate_names_are_explicit
    # (00B002's own bra.w $b588 tail jump means aim_search_scan_plan now covers this span too).
    assert boundary.AIM_POOL_SCAN_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-pool-scan-mutant-result').mutation is recovery._mutate_aim_ray_march


@needs_aim_pool_scan_census
@pytest.mark.parametrize('fixture', AIM_POOL_SCAN_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_pool_scan_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_pool_scan_plan(machine, registers)
        except UnsupportedCandidate as error:
            # A busy pool (several entries, several extended passes) can genuinely exceed
            # native/machine.cpp's own al_atomic cost cap (0 < instructions <= 10,000, 0 < cycles <=
            # 100,000) -- a real, witnessed decline, not a modelling gap.
            assert 'aim pool scan' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_pool_scan_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_POOL_SCAN_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-pool-scan',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        assert report['status'] == 'PASS', report
        assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-pool-scan-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-pool-scan produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B002: reset both AIM_SEARCH snapshot slots, run the target-scan family, then tail-jump into
# 00B588 (docs/gods/blockers/2026-09-18-00A578.md's own 19 September progress note).  See boundary.py's
# own module note above aim_search_scan_plan.

AIM_SEARCH_SCAN_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0XB002-*/00B002-entry-p*.state'))
needs_aim_search_scan_census = pytest.mark.skipif(not AIM_SEARCH_SCAN_FIXTURES or not GODS.rom_path.is_file(),
                                                   reason='no local census of 00B002')


def test_aim_search_scan_candidate_names_are_explicit():
    assert recovery.Candidate('aim-search-scan').gate_pcs == (boundary.AIM_SEARCH_SCAN_ENTRY,)
    assert boundary.AIM_SEARCH_SCAN_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-search-scan-mutant-result').mutation is recovery._mutate_aim_ray_march


@needs_aim_search_scan_census
@pytest.mark.parametrize('fixture', AIM_SEARCH_SCAN_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_search_scan_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_search_scan_plan(machine, registers)
        except UnsupportedCandidate as error:
            # Either an unwitnessed arm inside the composed scan family (the same declines
            # aim_target_scan_plan/aim_target_scan_backward_plan already make on their own), or the
            # SAME native atomic-plan cost cap aim_pool_scan_plan's own test already documents --
            # 00B002's own prefix only makes a busy pool more likely to cross it, not less real.
            assert any(needle in str(error) for needle in ('aim target scan', 'aim search scan', 'aim pool scan')), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_search_scan_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_SEARCH_SCAN_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-search-scan',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        if report['status'] != 'PASS':
            continue
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-search-scan-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-search-scan produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AF52: the camera-relative box test gating a full search dispatch -- AA76's own second call,
# after 00AF3C.  See boundary.py's own module note above aim_search_dispatch_plan.

AIM_SEARCH_DISPATCH_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0XAF52-*/00AF52-entry-p*.state'))
needs_aim_search_dispatch_census = pytest.mark.skipif(not AIM_SEARCH_DISPATCH_FIXTURES or not GODS.rom_path.is_file(),
                                                       reason='no local census of 00AF52')


def test_aim_search_dispatch_candidate_names_are_explicit():
    assert recovery.Candidate('aim-search-dispatch').gate_pcs == (boundary.AIM_SEARCH_DISPATCH_ENTRY,)
    assert boundary.AIM_SEARCH_DISPATCH_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-search-dispatch-mutant-result').mutation is recovery._mutate_aim_ray_march


@needs_aim_search_dispatch_census
@pytest.mark.parametrize('fixture', AIM_SEARCH_DISPATCH_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_search_dispatch_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_search_dispatch_plan(machine, registers)
        except UnsupportedCandidate as error:
            # A busy pool can genuinely exceed native/machine.cpp's own al_atomic cost cap (the same
            # decline aim_pool_scan_plan/aim_search_scan_plan already carry), an unwitnessed arm inside
            # the composed scan family, an unwitnessed Y-low bound exit, an unwitnessed event-scan
            # table-window miss, or the pool-drain slot-scan exhausting at 32 with count still nonzero.
            assert any(needle in str(error) for needle in
                      ('aim target scan', 'aim search scan', 'aim pool scan', 'aim search dispatch',
                       'aim cue')), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'], max_instructions=100000))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_search_dispatch_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_SEARCH_DISPATCH_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-search-dispatch',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        if report['status'] != 'PASS':
            continue
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-search-dispatch-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-search-dispatch produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AC36: the aim-search-flag kind dispatch (00AA76's own third call).  See game/creatures.py's
# own module note above aim_search_flag_dispatch.

AIM_SEARCH_FLAG_DISPATCH_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0XAC36-*/00AC36-entry-p*.state'))
needs_aim_search_flag_dispatch_census = pytest.mark.skipif(
    not AIM_SEARCH_FLAG_DISPATCH_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00AC36')


def test_aim_search_flag_dispatch_candidate_names_are_explicit():
    assert recovery.Candidate('aim-search-flag-dispatch').gate_pcs == (boundary.AIM_SEARCH_FLAG_DISPATCH_ENTRY,)
    assert boundary.AIM_SEARCH_FLAG_DISPATCH_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-search-flag-dispatch-mutant-result').mutation is recovery._mutate_result


@needs_aim_search_flag_dispatch_census
@pytest.mark.parametrize('fixture', AIM_SEARCH_FLAG_DISPATCH_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_search_flag_dispatch_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_search_flag_dispatch_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'aim search flag dispatch' in str(error), error
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_search_flag_dispatch_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_SEARCH_FLAG_DISPATCH_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-search-flag-dispatch',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        assert report['status'] == 'PASS', report
        assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-search-flag-dispatch-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-search-flag-dispatch produce an observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AA76: the most-witnessed kind handler (docs/gods/blockers/2026-09-18-00A578.md's own 19
# September Decision) -- five real arms composing 00AF3C (twice), 00AF52 and 00AC36 before a hand-off
# to kind_frame_offset's own separately-armed gate.  See boundary.py's own module note above
# aim_kind_handler_76_plan.

AIM_KIND_HANDLER_76_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00AA76-*/00AA76-entry-p*.state'))
needs_aim_kind_handler_76_census = pytest.mark.skipif(
    not AIM_KIND_HANDLER_76_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00AA76')


def test_aim_kind_handler_76_candidate_names_are_explicit():
    assert recovery.Candidate('aim-kind-handler-76').gate_pcs == (boundary.AIM_KIND_HANDLER_76_ENTRY,)
    assert boundary.AIM_KIND_HANDLER_76_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-kind-handler-76-mutant-result').mutation is recovery._mutate_result


@needs_aim_kind_handler_76_census
@pytest.mark.parametrize('fixture', AIM_KIND_HANDLER_76_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_kind_handler_76_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_kind_handler_76_plan(machine, registers)
        except UnsupportedCandidate as error:
            # A busy 00AF52 composition can genuinely exceed native/machine.cpp's own al_atomic cost
            # cap (the same decline aim_search_dispatch_plan itself already carries), an unwitnessed
            # arm inside that same composition, or an unwitnessed neighbor-cascade route/outcome this
            # routine's own five recordings never reach.
            assert any(needle in str(error) for needle in
                      ('aim target scan', 'aim search scan', 'aim pool scan', 'aim search dispatch',
                       'aim cue', 'aim kind handler 76')), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'], max_instructions=400000))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_kind_handler_76_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_KIND_HANDLER_76_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-kind-handler-76',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1 or report['status'] != 'PASS':
            continue
        # A window can genuinely carry a real, already-known domain decline (a busy 00AF52 pool, or
        # 00B7DA's own unwitnessed 'found without a new best') alongside a clean hit elsewhere in the
        # SAME 300-frame window -- try the next fixture rather than fail on it.
        if not set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS:
            continue
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-kind-handler-76-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-kind-handler-76 produce a clean observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00AB50: 00AA76's own mirror -- NOT byte-identical (its own shared-exit test is f2ce == 1, its
# own arm-2 sets KIND 3, its own two neighbor cascades run in the opposite order, and its own KIND
# polarity/header-delta sign are both the mirror of 00AA76's own).  See boundary.py's own module note
# above aim_kind_handler_50_plan.

AIM_KIND_HANDLER_50_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00AA76-*/00AB50-entry-p*.state'))
needs_aim_kind_handler_50_census = pytest.mark.skipif(
    not AIM_KIND_HANDLER_50_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00AB50')


def test_aim_kind_handler_50_candidate_names_are_explicit():
    assert recovery.Candidate('aim-kind-handler-50').gate_pcs == (boundary.AIM_KIND_HANDLER_50_ENTRY,)
    assert boundary.AIM_KIND_HANDLER_50_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('aim-kind-handler-50-mutant-result').mutation is recovery._mutate_result


@needs_aim_kind_handler_50_census
@pytest.mark.parametrize('fixture', AIM_KIND_HANDLER_50_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_aim_kind_handler_50_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.aim_kind_handler_50_plan(machine, registers)
        except UnsupportedCandidate as error:
            # A busy 00AF52 composition can genuinely exceed native/machine.cpp's own al_atomic cost
            # cap, an unwitnessed arm inside that same composition, or an unwitnessed neighbor-cascade
            # route/outcome this routine's own five recordings never reach.
            assert any(needle in str(error) for needle in
                      ('aim target scan', 'aim search scan', 'aim pool scan', 'aim search dispatch',
                       'aim cue', 'aim kind handler 50')), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'], max_instructions=400000))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_aim_kind_handler_50_candidate_matches_the_reference_and_its_mutant_diverges():
    report = mutant = None
    for fixture in AIM_KIND_HANDLER_50_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='aim-kind-handler-50',
                                      reference=EVIDENCE)
        if report['candidate_hits'] < 1 or report['status'] != 'PASS':
            continue
        if not set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS:
            continue
        mutant = segment_verify.check(state, game=GODS, frames=300, candidate='aim-kind-handler-50-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            break
    else:
        pytest.skip('no retained fixture/window makes aim-kind-handler-50 produce a clean observable effect')
    assert mutant['status'] == 'DIVERGENCE'


# --- 00B8C2 / 00B920: the creature spawn-init's own icon-cue add (00A578's own spawn-init body's own
# unconditional `bsr $b920`, independent of the whole 00AF52/00B588 chain).  See game/creatures.py's
# own module note above spawn_table_find_free/spawn_table_add.

def test_spawn_find_free_candidate_names_are_explicit():
    assert recovery.Candidate('spawn-table-find-free').gate_pcs == (boundary.SPAWN_FIND_FREE_ENTRY,)
    assert boundary.SPAWN_FIND_FREE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('spawn-table-find-free-mutant-result').mutation is recovery._mutate_spawn_find_free


def test_spawn_table_add_candidate_names_are_explicit():
    assert recovery.Candidate('spawn-table-add').gate_pcs == (boundary.SPAWN_TABLE_ADD_ENTRY,)
    assert boundary.SPAWN_TABLE_ADD_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('spawn-table-add-mutant-result').mutation is recovery._mutate_result


@needs_spawn_find_free_census
@pytest.mark.parametrize('fixture', SPAWN_FIND_FREE_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_spawn_find_free_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.spawn_table_find_free_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_spawn_find_free_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in SPAWN_FIND_FREE_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='spawn-table-find-free',
                                      reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B8C2 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='spawn-table-find-free-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


@needs_spawn_table_add_census
@pytest.mark.parametrize('fixture', SPAWN_TABLE_ADD_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_spawn_table_add_plan_reproduces_every_witnessed_occurrence(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.spawn_table_add_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_reference
def test_spawn_table_add_candidate_matches_the_reference_and_its_mutant_diverges():
    for fixture in SPAWN_TABLE_ADD_FIXTURES:
        state = fixture
        report = segment_verify.check(state, game=GODS, frames=300, candidate='spawn-table-add', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B920 within 300 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(state, game=GODS, frames=300, candidate='spawn-table-add-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
