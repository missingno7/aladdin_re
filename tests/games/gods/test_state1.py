"""State 1 (007282): the player state machine's own dispatch table entry 1 -- a ~130-instruction
decision tree over the already-recovered grid cell (0063FA), the contact search (008222) and the
box-overlap scan (00722C, declined here), ending at the shared tail (0075D6, a separately-armed
gate this plan hands off to) or, on a contact-search-found result, one instruction further in
(0075DA), via the same deterministic hand-off `game.player.state1_handoff` names
(`docs/gods/blockers/2026-09-17-008222.md`'s "18 September (continued)" addendum transcribes the
whole tree).  Three tiers as for the other leaves; the evidence tiers skip when the local census or
reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-007282/007282-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 007282')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def _gated(extra=None):
    """RAM values with the grid gate byte ($180(a0)) set to 1, so `state1_step` reaches arm A
    directly regardless of POSITION_X -- what every test past the wall/gate split needs."""
    address = player.state1_step(_reader({}), 0)['address']
    values = {((address + 0x180) & 0xFFFFFF, 1): 1}
    values.update(extra or {})
    return values


def test_gate_direct_when_the_grid_byte_is_one():
    address = player.state1_step(_reader({}), 0)['address']
    result = player.state1_step(_reader({(address + 0x180 & 0xFFFFFF, 1): 1}), 0)
    assert result['gate_direct'] is True
    # A bare reader (every byte 0) means the grid gate byte is 0 (not 1): the low-bits path runs.
    assert player.state1_step(_reader({}), 0)['gate_direct'] is False


def test_wall_arm_when_the_low_bits_are_small():
    values = {(player.POSITION_X & 0xFFFFFF, 2): 0}   # low = 0 & 0x1e = 0 < 8
    result = player.state1_step(_reader(values), 3)
    assert result['arm'] == 'wall' and result['d7'] == 0
    assert result['stores'][player.STATE_INDEX] == (0xC, 2)


def test_wall_arm_when_the_low_bits_are_large_and_the_second_gate_byte_misses():
    address = player.state1_step(_reader({}), 0)['address']
    values = {(player.POSITION_X & 0xFFFFFF, 2): 0x18, (address + 0x181 & 0xFFFFFF, 1): 2}
    result = player.state1_step(_reader(values), 0)
    assert result['arm'] == 'wall' and result['low_lt_8'] is False


def test_negative_ea20_transitions_to_state_3():
    result = player.state1_step(_reader(_gated({(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF})), 0)
    assert result['arm'] == 'negative' and result['d7'] == 2
    assert result['stores'][player.STATE_INDEX] == (3, 2)


def test_ea1e_one_declines_as_box_overlap():
    result = player.state1_step(_reader(_gated({(player.EA1E_WORD & 0xFFFFFF, 2): 1})), 0)
    assert result['arm'] == 'box-overlap'


def test_bit0_set_is_jump_start_with_ea20_zero_or_positive():
    zero = player.state1_step(_reader(_gated({(player.EA23_WORD & 0xFFFFFF, 1): 1})), 5)
    assert zero['arm'] == 'jump-start' and zero['f196'] == 0 and zero['d7'] == 0
    positive = player.state1_step(_reader(_gated({(player.EA23_WORD & 0xFFFFFF, 1): 1, (player.EA20_WORD & 0xFFFFFF, 2): 4})), 5)
    assert positive['arm'] == 'jump-start' and positive['f196'] == 4


def test_bit2_selects_whether_the_boundary_must_call_contact_search():
    clear = player.state1_step(_reader(_gated()), 0)
    assert clear['arm'] == 'gate' and clear['needs_search'] is False
    setbit = player.state1_step(_reader(_gated({(player.EA23_WORD & 0xFFFFFF, 1): 4})), 0)
    assert setbit['arm'] == 'gate' and setbit['needs_search'] is True


def test_cascade_f182_set_advances_position_and_counter():
    result = player.state1_cascade(_reader({(player.MOVEMENT_FLAG & 0xFFFFFF, 2): 1}), 3, 0x40, 0)
    assert result['arm'] == 'f182-set' and result['d7'] == 4
    assert result['stores'][player.POSITION_X] == (0x44, 2)


def test_cascade_grid_block_exits_without_stores():
    address = 0xFFFF8000
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 1, ((address + 0x81) & 0xFFFFFF, 1): 1}
    result = player.state1_cascade(_reader(values), 0, 4, address)   # position_x=4 -> low5=4 < 8
    assert result['arm'] == 'grid-block' and result['last_pc'] == 0x007414 and result['checked'] == 2


def test_cascade_position_advance_writes_sound_on_two_and_six():
    for d7, cue in ((2, 0x48), (6, 0x49), (3, None)):
        values = {(player.EA20_WORD & 0xFFFFFF, 2): 1}
        result = player.state1_cascade(_reader(values), d7, 0x40, 0xFFFF8000)   # low5=0 < 8, no grid match
        assert result['arm'] == 'position-advance' and result['d7'] == (d7 + 1) & 7
        from gods_sega.game.pickups import MOVEMENT_SOUND_CUE
        if cue is None:
            assert (MOVEMENT_SOUND_CUE & 0xFFFFFF) not in result['stores']
        else:
            assert result['stores'][MOVEMENT_SOUND_CUE & 0xFFFFFF] == (cue, 2)


def test_cascade_counter_overflow_undoes_the_position_step_and_resets_to_zero():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 1}
    result = player.state1_cascade(_reader(values), 0x2D, 0x40, 0xFFFF8000)
    assert result['arm'] == 'position-advance' and result.get('overflow') and result['d7'] == 0
    assert result['stores'][player.POSITION_X] == (0x40, 2)   # unchanged: +4 then -4


def test_cascade_shared_sub_body_three_arms():
    negative = player.state1_cascade(_reader({(player.EA1E_WORD & 0xFFFFFF, 2): 0xFFFF}), 0, 0x40, 0)
    assert negative['arm'] == 'ea1e-negative' and negative['d7'] == 1
    unchanged = player.state1_cascade(_reader({}), 0, 0x40, 0)
    assert unchanged['arm'] == 'shared-unchanged' and unchanged['d7'] == 0
    reset = player.state1_cascade(_reader({}), 5, 0x40, 0)
    assert reset['arm'] == 'shared-reset' and reset['d7'] == 0x2D


def test_handoff_is_deterministic_and_always_reads_table_index_zero():
    values = {(player.STATE1_HANDOFF_TABLE & 0xFFFFFF, 2): 0x1234}
    result = player.state1_handoff(_reader(values))
    assert result['d7'] == 0x1234
    assert result['stores'][player.STATE_INDEX] == (5, 2)
    assert result['stores'][player.STATE_COUNTER] == (0, 2)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: p.stem)
def test_plan_reproduces_every_witnessed_arm_and_declines_the_box_overlap_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state1_plan(machine, registers)
        except boundary.UnsupportedCandidate as error:
            assert 'box-overlap' in str(error)
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-1').gate_pcs == (boundary.STATE1_ENTRY,)
    assert boundary.STATE1_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-1-mutant-result').mutation is recovery._mutate_state1_counter


@needs_reference
def test_state_1_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-1', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 1 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-1-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
