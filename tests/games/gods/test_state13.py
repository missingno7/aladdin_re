"""State 13 (006B4E): state 14's own counterpart, a vertical-movement dispatcher.  The contact-
search gate (006C62-006CC5) is byte-identical to state 14's own (006EC4-006F27) and reuses the SAME
shared composition; the two jump-start tails (0x6FB8 into state 8, 0x6FDA into state 9) are the SAME
physical ROM addresses state 14's own arm A/B jump into.  Real differences from state 14's own shape:
no FFFFF1B0 store and no separate FFFFEA1E-sign gate before the FFFFEA20 dispatch (the "settle,
carrying" hand-off is folded into the FFFFEA20 == 0 arm itself, gated on FFFFEA1E == 1 there); arm
A/B's own jump-start gate is FFFFEA1E's sign (not FFFFEA23 bit 0); arm D's own toggle gate is
FFFFEA1E >= 0 / < 0 (a sign test) rather than state 14's own exact == 1, and it toggles INTO state 14;
and the settle tail's own retry probe produces two real transitions (states 26/10), not state 14's
own "always exits unchanged or loops" shape.  Three tiers as for the other leaves; the evidence tiers
skip when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006B4E*/006B4E-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006B4E')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_frozen_gate():
    assert player.state13_step(_reader({}), 0)['arm'] == 'frozen'


def test_wrap_resets_to_settle():
    values = {(player.FROZEN_LIKE_FLAG & 0xFFFFFF, 2): 1}
    result = player.state13_step(_reader(values), player.STATE13_WRAP)
    assert result['arm'] == 'settle' and result['reset'] is True and result['settle_d7'] == 0


def test_ea20_zero_and_ea1e_one_carries_into_settle():
    values = {(player.FROZEN_LIKE_FLAG & 0xFFFFFF, 2): 1, (player.EA20_WORD & 0xFFFFFF, 2): 0,
              (player.EA1E_WORD & 0xFFFFFF, 2): 1}
    result = player.state13_step(_reader(values), 5)
    assert result['arm'] == 'settle' and result['reset'] is False and result['settle_d7'] == 5


def test_ea20_zero_and_ea1e_not_one_clears_and_continues_to_main():
    values = {(player.FROZEN_LIKE_FLAG & 0xFFFFFF, 2): 1, (player.EA20_WORD & 0xFFFFFF, 2): 0,
              (player.EA1E_WORD & 0xFFFFFF, 2): 0}
    result = player.state13_step(_reader(values), 5)
    assert result['arm'] == 'main'
    assert result['stores'][player.F1A4 & 0xFFFFFF] == (0, 2)
    assert result['stores'][player.F1A6 & 0xFFFFFF] == (0, 2)


def test_ea20_nonzero_skips_the_clears():
    values = {(player.FROZEN_LIKE_FLAG & 0xFFFFFF, 2): 1, (player.EA20_WORD & 0xFFFFFF, 2): 1}
    result = player.state13_step(_reader(values), 5)
    assert result['arm'] == 'main' and result['stores'] == {} and result['ea20_one'] is True


def test_arm_d_toggles_on_negative_ea1e_into_state_14():
    values = {(player.EA1E_WORD & 0xFFFFFF, 2): 0xFFFF}   # -1
    result = player.state13_arm_d(_reader(values))
    assert result['arm'] == 'transition-14'
    assert result['stores'][player.STATE_INDEX] == (player.STATE13_TO_STATE14, 2)
    assert result['stores'][player.STATE_INDEX][0] == 0xE


def test_arm_d_exits_unchanged_on_nonnegative_ea1e():
    values = {(player.EA1E_WORD & 0xFFFFFF, 2): 0}
    assert player.state13_arm_d(_reader(values))['arm'] == 'unchanged'


def test_settle_probe_blocked_transitions_to_state_26():
    from gods_sega.game.grid import _grid_cell_address
    position_y = 0x100
    address = _grid_cell_address(0, position_y + 6)['address']
    values = {(player.POSITION_Y & 0xFFFFFF, 2): position_y, ((address + 0x180) & 0xFFFFFF, 1): 1}
    result = player.state13_settle_probe(_reader(values), 3)
    assert result['arm'] == 'blocked'
    assert result['stores'][player.STATE_INDEX] == (player.STATE13_TO_STATE26, 2)
    assert result['d7'] == 0


def test_settle_probe_clear_transitions_to_state_10():
    result = player.state13_settle_probe(_reader({}), 3)
    assert result['arm'] == 'clear'
    assert result['stores'][player.STATE_INDEX] == (player.STATE13_TO_STATE10, 2)
    assert result['d7'] == 0


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state13_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'transition-9' in str(error) or 'more than two passes' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-13').gate_pcs == (boundary.STATE13_ENTRY,)
    assert boundary.STATE13_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-13-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_13_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-13', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 13 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-13-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
