"""State 0 (006FFE): the player state machine's own dispatch table entry 0 -- the "move left"
counterpart of state 1, NOT a byte-identical clone: real differences confirmed by the tracer, not
assumed by symmetry (`game.player`'s own module note above `state0_step` names them: arm A compares
FFFFEA20 to the literal 1 rather than testing its sign, the bit-0 sub-arm's own EA20-positive case
reaches a three-way grid-byte dispatch state 1 has no analogue of, and the cascade decrements
POSITION_X with different grid offsets and a different low-bits threshold).  Ends at the shared tail
(0075D6, a separately-armed gate this plan hands off to) or, on a contact-search-found result, one
instruction further in (0075DA) via `game.player.state0_handoff` (STATE_INDEX forced to 6, not 5).
Three tiers as for state 1; the evidence tiers skip when the local census or reference artifacts are
absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006FFE/006FFE-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006FFE')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def _gated(extra=None):
    """RAM values with the grid gate byte ($180(a0)) set to 1, so `state0_step` reaches arm A
    directly regardless of POSITION_X."""
    address = player.state0_step(_reader({}), 0)['address']
    values = {((address + 0x180) & 0xFFFFFF, 1): 1}
    values.update(extra or {})
    return values


def test_gate_direct_when_the_grid_byte_is_one():
    address = player.state0_step(_reader({}), 0)['address']
    result = player.state0_step(_reader({(address + 0x180 & 0xFFFFFF, 1): 1}), 0)
    assert result['gate_direct'] is True
    assert player.state0_step(_reader({}), 0)['gate_direct'] is False


def test_wall_arm_writes_state_0xb_not_0xc():
    values = {(player.POSITION_X & 0xFFFFFF, 2): 0}
    result = player.state0_step(_reader(values), 3)
    assert result['arm'] == 'wall' and result['d7'] == 0
    assert result['stores'][player.STATE_INDEX] == (0xB, 2)


def test_arm_a_compares_ea20_to_the_literal_one_not_its_sign():
    # A negative EA20 does NOT transition here (unlike state 1's own sign-tested arm A) -- it falls
    # through to arm A2 exactly as any other non-1 value would.
    negative = player.state0_step(_reader(_gated({(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF})), 0)
    assert negative['arm'] == 'gate'
    one = player.state0_step(_reader(_gated({(player.EA20_WORD & 0xFFFFFF, 2): 1})), 0)
    assert one['arm'] == 'transition-2' and one['d7'] == 0
    assert one['stores'][player.STATE_INDEX] == (2, 2)


def test_ea1e_one_declines_as_box_overlap():
    result = player.state0_step(_reader(_gated({(player.EA1E_WORD & 0xFFFFFF, 2): 1})), 0)
    assert result['arm'] == 'box-overlap'


def test_bit0_set_ea20_negative_and_zero_both_reach_state_8():
    negative = player.state0_step(_reader(_gated({(player.EA23_WORD & 0xFFFFFF, 1): 1,
                                                   (player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF})), 5)
    assert negative['arm'] == 'jump-start' and negative['f196'] == 0xFFFC
    zero = player.state0_step(_reader(_gated({(player.EA23_WORD & 0xFFFFFF, 1): 1})), 5)
    assert zero['arm'] == 'jump-start' and zero['f196'] == 0
    assert negative['stores'][player.STATE_INDEX] == (8, 2) == zero['stores'][player.STATE_INDEX]


def test_bit0_set_ea20_positive_reaches_state_14_or_declines_by_low5_and_grid_byte():
    address = player.state0_step(_reader({}), 0)['address']
    # low5 <= 0x14 and the grid byte at offset 0 matches 2: state 14 directly (007132, no advance).
    matched = player.state0_step(_reader(_gated({(player.EA23_WORD & 0xFFFFFF, 1): 1,
                                                  (player.EA20_WORD & 0xFFFFFF, 2): 5,
                                                  (player.POSITION_X & 0xFFFFFF, 2): 4,
                                                  (address & 0xFFFFFF, 1): 2})), 0)
    assert matched['arm'] == 'transition-14' and matched['advance'] is False
    assert matched['stores'][player.STATE_INDEX] == (0xE, 2)
    # low5 < 0xc and no grid byte matches: declines into the shared cascade (arm A4), not state 14.
    address2 = player.state0_step(_reader({(player.POSITION_X & 0xFFFFFF, 2): 4}), 0)['address']
    declined = player.state0_step(_reader(_gated({(player.EA23_WORD & 0xFFFFFF, 1): 1,
                                                   (player.EA20_WORD & 0xFFFFFF, 2): 5,
                                                   (player.POSITION_X & 0xFFFFFF, 2): 4})), 0)
    assert declined['arm'] == 'gate' and declined.get('position_positive')


def test_cascade_f182_set_decrements_position_and_advances_counter():
    result = player.state0_cascade(_reader({(player.MOVEMENT_FLAG & 0xFFFFFF, 2): 1}), 3, 0x40, 0)
    assert result['arm'] == 'f182-set' and result['d7'] == 4
    assert result['stores'][player.POSITION_X] == (0x3C, 2)


def test_cascade_grid_block_uses_the_mirrored_offsets():
    address = 0xFFFF8000
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF, ((address + 0x7F) & 0xFFFFFF, 1): 1}
    result = player.state0_cascade(_reader(values), 0, 0, address)   # position_x=0 -> low5=0
    assert result['arm'] == 'grid-block' and result['last_pc'] == 0x007190 and result['checked'] == 2


def test_cascade_position_advance_decrements_and_writes_sound_on_two_and_six():
    for d7, cue in ((2, 0x48), (6, 0x49), (3, None)):
        values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF}
        result = player.state0_cascade(_reader(values), d7, 0x40, 0xFFFF8000)
        assert result['arm'] == 'position-advance' and result['d7'] == (d7 + 1) & 7
        assert result['stores'][player.POSITION_X] == (0x3C, 2)
        from gods_sega.game.pickups import MOVEMENT_SOUND_CUE
        if cue is None:
            assert (MOVEMENT_SOUND_CUE & 0xFFFFFF) not in result['stores']
        else:
            assert result['stores'][MOVEMENT_SOUND_CUE & 0xFFFFFF] == (cue, 2)


def test_cascade_counter_overflow_undoes_the_position_step_and_resets_to_zero():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF}
    result = player.state0_cascade(_reader(values), 0x39, 0x40, 0xFFFF8000)
    assert result['arm'] == 'position-advance' and result.get('overflow') and result['d7'] == 0
    assert result['stores'][player.POSITION_X] == (0x40, 2)   # unchanged: -4 then +4


def test_shared_sub_negative_arm_sign_extends_d7_to_the_full_register():
    result = player.state0_shared_sub(_reader({(player.EA1E_WORD & 0xFFFFFF, 2): 0xFFFF}), 0)
    assert result['arm'] == 'ea1e-negative' and result['d7_full'] == 0xFFFFFFFF
    assert result['stores'][player.STATE_INDEX] == (0x1A, 2)


def test_shared_sub_unchanged_and_reset_arms():
    unchanged = player.state0_shared_sub(_reader({}), 0)
    assert unchanged['arm'] == 'shared-unchanged' and unchanged['d7'] == 0
    reset = player.state0_shared_sub(_reader({}), 5)
    assert reset['arm'] == 'shared-reset' and reset['d7'] == 0x39


def test_handoff_forces_state_index_six():
    values = {(player.STATE1_HANDOFF_TABLE & 0xFFFFFF, 2): 0x1234}
    result = player.state0_handoff(_reader(values))
    assert result['d7'] == 0x1234
    assert result['stores'][player.STATE_INDEX] == (6, 2)
    assert result['stores'][player.STATE_COUNTER] == (0, 2)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: p.stem)
def test_plan_reproduces_every_witnessed_arm_and_declines_the_box_overlap_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state0_plan(machine, registers)
        except boundary.UnsupportedCandidate as error:
            assert 'box-overlap' in str(error)
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-0').gate_pcs == (boundary.STATE0_ENTRY,)
    assert boundary.STATE0_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-0-mutant-result').mutation is recovery._mutate_state0_counter


@needs_reference
def test_state_0_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-0', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 0 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-0-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
