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
    assert boundary.ATTACK_UPDATE_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
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
    assert boundary.KIND_FRAME_OFFSET_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
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
