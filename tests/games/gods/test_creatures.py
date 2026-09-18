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

GRID_CELL_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AA38-*/00AA38-entry-p*.state'))
needs_grid_cell_census = pytest.mark.skipif(not GRID_CELL_FIXTURES or not GODS.rom_path.is_file(),
                                            reason='no local census of 00AA38')

GROUND_CONTACT_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00ACA0-*/00ACA0-entry-p*.state'))
needs_ground_contact_census = pytest.mark.skipif(not GROUND_CONTACT_FIXTURES or not GODS.rom_path.is_file(),
                                                 reason='no local census of 00ACA0')

GROUND_EDGE_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00AD68-*/00AD68-entry-p*.state'))
needs_ground_edge_census = pytest.mark.skipif(not GROUND_EDGE_FIXTURES or not GODS.rom_path.is_file(),
                                              reason='no local census of 00AD68')

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


def test_ground_contact_update_near_trigger_cell_high_declines_by_name():
    values = _reload_base(x=0x214, y=0x40, fall_phase=0)                # post-subq low5 (0x210) is >= 8
    cell = _grid_address(0x214, 0x40)                                   # creature_grid_cell reads the ENTRY x
    values[(cell + 0x100) & 0xFFFFFF, 1] = 0                            # first probe misses
    values[(cell + 0x101) & 0xFFFFFF, 1] = creatures.GROUND_EDGE_FLAG   # second probe matches
    result = creatures.ground_contact_update(_reader(values), TYPE_PTR, INSTANCE_PTR)
    assert result['arm'] == 'near-trigger-cell-high'


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
