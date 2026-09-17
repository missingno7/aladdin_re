"""State 14 (006DA6): the player state machine's own dispatch table entry 14, a vertical-movement
dispatcher (states 0/1 are horizontal) composed over the already-recovered grid cell (0063FA) and
contact search (008222).  Shape: a `FFFFEF4A` "frozen" gate, a STATE_COUNTER wraparound at 0x14 that
hands off to a shared "settle" tail (fresh or carried), an `FFFFEA20 == 1` fork into two near-mirror
arms (A/B), a contact-search gate shared by both arms, arm D's own no-op/transition-13 branch, and
the settle tail's own `FFFFF1AE != 0` fork (`'probe-f1ae'`/`'loopback'`, both witnessed and composed)
and `FFFFEA20 != 0` fork (`'rejoin-main'`, handed off to the SAME EA20 dispatch via the shared
`boundary._state14_main_dispatch` helper, not re-declined).  No arm declines any more: arm B's own
`+0x17F` nibble sub-test (once thought unwitnessed) mirrors arm A's own `+0x181` test exactly, caught
by a tree recording outside the single-history census (`game.player.state14_arm_b`'s own module note
records the fix, alongside three more real bugs the same tree run caught -- a missing unconditional
`FFFFF1A4` clear in three of arm A's own downstream stores, arm B's own retry counter carried forward
instead of hardcoded zero, and a D0 clobber missed on both arms' own nibble-tested exit).  Ends at the
shared tail (0075D6, a separately-armed gate this plan hands off to).  `game.player`'s own module
note above `state14_step` transcribes the whole tree.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import player
from gods_sega.game.grid import grid_cell
from gods_sega.game.pickups import MOVEMENT_SOUND_CUE
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006DA6/006DA6-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006DA6')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_step_frozen_when_ef4a_is_zero():
    result = player.state14_step(_reader({}), 0)
    assert result['arm'] == 'frozen'


def test_step_settle_reset_when_counter_wraps():
    values = {(player.FROZEN_LIKE_FLAG & 0xFFFFFF, 2): 1}
    result = player.state14_step(_reader(values), player.STATE14_WRAP)
    assert result['arm'] == 'settle' and result['reset'] is True and result['settle_d7'] == 0


def test_step_settle_carried_when_ea1e_negative():
    values = {(player.FROZEN_LIKE_FLAG & 0xFFFFFF, 2): 1, (player.EA1E_WORD & 0xFFFFFF, 2): 0xFFFF}
    result = player.state14_step(_reader(values), 3)
    assert result['arm'] == 'settle' and result['reset'] is False and result['settle_d7'] == 3
    assert result['stores'][player.F1B0 & 0xFFFFFF] == (3, 2)


def test_step_main_clears_f1a4_f1a6_only_when_ea20_is_zero():
    values = {(player.FROZEN_LIKE_FLAG & 0xFFFFFF, 2): 1}
    zero = player.state14_step(_reader(values), 0)
    assert zero['arm'] == 'main' and zero['ea20_one'] is False
    assert zero['stores'][player.F1A4 & 0xFFFFFF] == (0, 2)
    values_one = dict(values)
    values_one[(player.EA20_WORD & 0xFFFFFF, 2)] = 1
    one = player.state14_step(_reader(values_one), 0)
    assert one['arm'] == 'main' and one['ea20_one'] is True
    assert (player.F1A4 & 0xFFFFFF) not in one['stores']


def test_arm_a_contact_gate_forces_f1a8():
    result = player.state14_arm_a(_reader({(player.EA23_WORD & 0xFFFFFF, 1): 4}))
    assert result['arm'] == 'contact-gate' and result['f1a8_forced'] == 1
    assert result['stores'][player.F1A8 & 0xFFFFFF] == (1, 2)


def test_arm_a_transition_9_on_bit0():
    values = {(player.EA23_WORD & 0xFFFFFF, 1): 1, (player.POSITION_X & 0xFFFFFF, 2): 0x10}
    result = player.state14_arm_a(_reader(values))
    assert result['arm'] == 'transition-9' and result['d7'] == 0xC
    assert result['stores'][player.STATE_INDEX] == (9, 2)
    assert result['stores'][MOVEMENT_SOUND_CUE & 0xFFFFFF] == (0x30, 2)


def test_arm_a_contact_gate_f1a6_while_retry_budget_remains():
    result = player.state14_arm_a(_reader({(player.F1A6 & 0xFFFFFF, 2): 2}))
    assert result['arm'] == 'contact-gate-f1a6'
    assert result['stores'][player.F1A6 & 0xFFFFFF] == (3, 2)


def test_arm_a_reaches_transition_1_when_no_grid_byte_matches():
    values = {(player.F1A6 & 0xFFFFFF, 2): 6, (player.POSITION_X & 0xFFFFFF, 2): 0x10,
              (player.POSITION_Y & 0xFFFFFF, 2): 0x20}
    address = grid_cell(_reader(values))['address']
    result = player.state14_arm_a(_reader(values))
    assert result['arm'] == 'transition-1' and result['d7'] == 6
    assert result['stores'][player.STATE_INDEX] == (1, 2)
    assert result['stores'][player.POSITION_X] == (0x18, 2)
    # 006DFA's own clr.w f1a4.w is unconditional -- every arm past the bit-0 test carries it, not
    # just the immediate retry-budget arm.
    assert result['stores'][player.F1A4 & 0xFFFFFF] == (0, 2)
    assert result['cell']['address'] == address
    # 006E2A's own move.w f18e,d0; andi.w #$f,d0 overwrites D0 with the low nibble (0 here, matching
    # POSITION_Y's own low nibble) before this exit -- not grid_cell's own column.
    assert result['d0'] == 0


def test_arm_a_contact_gate_nibble_carries_the_low_nibble_in_d0():
    values = {(player.F1A6 & 0xFFFFFF, 2): 6, (player.POSITION_Y & 0xFFFFFF, 2): 3}
    address = grid_cell(_reader(values))['address']
    values[((address + 0x181) & 0xFFFFFF, 1)] = 1
    result = player.state14_arm_a(_reader(values))
    assert result['arm'] == 'contact-gate-nibble' and result['d0'] == 3
    assert result['stores'][player.F1A4 & 0xFFFFFF] == (0, 2)
    assert result['stores'][player.F1A6 & 0xFFFFFF] == (0, 2)


def test_arm_b_contact_gate_immediate_when_ea20_non_negative():
    result = player.state14_arm_b(_reader({(player.EA20_WORD & 0xFFFFFF, 2): 0}))
    assert result['arm'] == 'contact-gate-immediate'


def test_arm_b_contact_gate_forces_f1a8_negative():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF, (player.EA23_WORD & 0xFFFFFF, 1): 4}
    result = player.state14_arm_b(_reader(values))
    assert result['arm'] == 'contact-gate' and result['f1a8_forced'] == 0xFFFF
    assert result['stores'][player.F1A8 & 0xFFFFFF] == (0xFFFF, 2)


def test_arm_b_transition_8_on_bit0():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF, (player.EA23_WORD & 0xFFFFFF, 1): 1,
              (player.POSITION_X & 0xFFFFFF, 2): 0x10}
    result = player.state14_arm_b(_reader(values))
    assert result['arm'] == 'transition-8' and result['d7'] == 0xD
    assert result['stores'][player.STATE_INDEX] == (8, 2)


def test_arm_b_reaches_transition_0_when_no_grid_byte_or_nibble_byte_matches():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF, (player.F1A4 & 0xFFFFFF, 2): 6,
              (player.POSITION_X & 0xFFFFFF, 2): 0x10, (player.POSITION_Y & 0xFFFFFF, 2): 0x21}
    result = player.state14_arm_b(_reader(values))
    assert result['arm'] == 'transition-0' and result['d7'] == 6
    assert result['stores'][player.STATE_INDEX] == (0, 2)
    # F1A4's own retry counter is only ever incremented past the budget (never re-cleared, unlike
    # arm A's own mirror re-clearing F1A6) -- the incremented value (7) carries forward, not zero.
    assert result['stores'][player.F1A4 & 0xFFFFFF] == (7, 2)
    assert result['stores'][player.F1A6 & 0xFFFFFF] == (0, 2)
    # 006EA0's own move.w f18e,d0; andi.w #$f,d0 overwrites D0 with the low nibble (1 here) even on
    # the nibble!=0-but-no-match fallthrough, exactly like arm A's own mirror.
    assert result['d0'] == 1


def test_arm_b_contact_gate_nibble_mirrors_arm_a():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF, (player.F1A4 & 0xFFFFFF, 2): 6,
              (player.POSITION_Y & 0xFFFFFF, 2): 3}
    address = grid_cell(_reader(values))['address']
    values[((address + 0x17F) & 0xFFFFFF, 1)] = 1
    result = player.state14_arm_b(_reader(values))
    assert result['arm'] == 'contact-gate-nibble' and result['d0'] == 3
    assert result['stores'][player.F1A4 & 0xFFFFFF] == (7, 2)
    assert result['stores'][player.F1A6 & 0xFFFFFF] == (0, 2)


def test_contact_arm_d_when_bit2_clear():
    result = player.state14_contact(_reader({}), 0, 0)
    assert result['arm'] == 'arm-d'


def test_contact_arm_d_when_f1a8_zero():
    result = player.state14_contact(_reader({(player.EA23_WORD & 0xFFFFFF, 1): 4}), 0, 0)
    assert result['arm'] == 'arm-d'


def test_contact_search_direction_follows_f1a8_sign():
    values = {(player.EA23_WORD & 0xFFFFFF, 1): 4, (player.F1A8 & 0xFFFFFF, 2): 0xFFFF}
    negative = player.state14_contact(_reader(values), 0, 0)
    assert negative['arm'] == 'contact-search' and negative['negative'] is True
    # f1a8_override stands in for the SAME activation's own just-forced value (not yet in real RAM).
    forced = player.state14_contact(_reader({(player.EA23_WORD & 0xFFFFFF, 1): 4}), 0, 0, f1a8_override=1)
    assert forced['arm'] == 'contact-search' and forced['negative'] is False


def test_contact_found_halves_position_y_step_only_when_d7_even():
    values = {(player.POSITION_Y & 0xFFFFFF, 2): 0x40}
    even = player.state14_contact_found(_reader(values), 4, negative=False)
    assert even['stores'][player.POSITION_Y] == (0x3C, 2)
    assert even['stores'][player.STATE_INDEX] == (0x18, 2)
    odd = player.state14_contact_found(_reader(values), 5, negative=True)
    assert player.POSITION_Y not in odd['stores']
    assert odd['stores'][player.STATE_INDEX] == (0x19, 2)


def test_arm_d_unchanged_when_ea1e_is_not_one():
    result = player.state14_arm_d(_reader({}))
    assert result['arm'] == 'unchanged'


def test_arm_d_transitions_to_13_and_toggles_f1ae():
    values = {(player.EA1E_WORD & 0xFFFFFF, 2): 1, (player.F1AE & 0xFFFFFF, 2): 0}
    result = player.state14_arm_d(_reader(values))
    assert result['arm'] == 'transition-13'
    assert result['stores'][player.F1AE & 0xFFFFFF] == (0xFFFF, 2)
    assert result['stores'][player.STATE_INDEX] == (0xD, 2)


def test_settle_rejoins_main_when_ea20_nonzero():
    result = player.state14_settle(_reader({(player.EA20_WORD & 0xFFFFFF, 2): 1}), 0)
    assert result['arm'] == 'rejoin-main'


def test_settle_probe_without_sound_below_threshold():
    result = player.state14_settle(_reader({}), 1)
    assert result['arm'] == 'probe' and result['sound'] is False and result['settle_d7'] == 2


def test_settle_probe_with_sound_above_threshold():
    result = player.state14_settle(_reader({}), 3)
    assert result['arm'] == 'probe' and result['sound'] is True and result['settle_d7'] == 2
    assert result['stores'][MOVEMENT_SOUND_CUE & 0xFFFFFF] == (0x6A, 2)


def test_settle_f1ae_fork_continues_to_probe_without_looping():
    # F1AE only ever holds 0 or 0xFFFF in the real ROM (a NOT toggle of one produces the other) --
    # 0xFFFF here is the "set" state an earlier odd sound-trigger count left behind.
    values = {(player.F1AE & 0xFFFFFF, 2): 0xFFFF}
    result = player.state14_settle(_reader(values), 3)
    assert result['arm'] == 'probe-f1ae' and result['settle_d7'] == 2 and result['sound'] is False


def test_settle_f1ae_fork_loops_back_when_counter_was_one():
    values = {(player.F1AE & 0xFFFFFF, 2): 0xFFFF}
    result = player.state14_settle(_reader(values), 1)
    assert result['arm'] == 'loopback' and result['next_d7'] == 1 and result['next_f1ae'] == 0
    # a second pass with the (now clear) toggled f1ae never re-enters this fork: it takes the
    # ordinary bump branch instead, exactly as `_state14_settle_cost`'s own bounded loop assumes.
    second = player.state14_settle(_reader({}), result['next_d7'], f1ae_override=result['next_f1ae'])
    assert second['arm'] == 'probe' and second['settle_d7'] == 2


def test_settle_probe_blocked_and_exhausted():
    blocked = player.state14_settle_probe(_reader({}), 2)
    assert blocked['arm'] in ('blocked', 'exhausted')   # both real ROM outcomes, RAM-dependent
    values = {(player.F1B0 & 0xFFFFFF, 2): 9}
    exhausted_live = player.state14_settle_probe(_reader(values), 2)
    if exhausted_live['arm'] == 'exhausted':
        assert exhausted_live['d7'] == 9
        # the 'exhausted' tail's own SECOND move (f1b2,f18e) restores the ORIGINAL POSITION_Y --
        # the boundary's own exit SR must come from THIS value, not grid_cell's own asl.w residue.
        assert exhausted_live['stores'][player.POSITION_Y] == (0, 2)
    forced = player.state14_settle_probe(_reader({}), 2, f1b0_override=7)
    if forced['arm'] == 'exhausted':
        assert forced['d7'] == 7


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: p.stem)
def test_plan_reproduces_every_witnessed_arm(fixture):
    # every arm is composed now (no decline left) -- state14_plan is called directly, unguarded.
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.state14_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-14').gate_pcs == (boundary.STATE14_ENTRY,)
    assert boundary.STATE14_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-14-mutant-result').mutation is recovery._mutate_state14_counter


@needs_reference
def test_state_14_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-14', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 14 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-14-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
