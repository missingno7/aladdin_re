"""State 26 (0069AC): a near-twin of state 9's own falling/jump-arc shape, reusing the SAME jump-arc
table (006414) and the SAME two row-gate leaves (006442/006468, `game.player._row_gate_open`) --
confirmed byte-identical in cost, not assumed.  Three real differences from state 9: the head
normalizes STATE_COUNTER from FFFFF1BA (a flag), not F19C; the X-advance has no F19C gate at all
(it always applies once the grid-block test declines) and, unlike state 9, the grid cell is NOT
re-read after it; and the re-check ground-ahead probe (after the fall step) uses
STATE26_RECHECK_GATE (0x12), not STATE9_TRIGGER_GATE (0x16).  In place of state 9's own trigger
gate, state 26's own tail is D7-based: D7 at or past 3 hands off straight into state 9 (D7 forced to
5, STATE_INDEX to 9); short of 3, D7 == 1 also calls the already-recovered contact-consume primary
(012DA0) first.  Three tiers as for the other leaves; the evidence tiers skip when the local census
or reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0069AC*/0069AC-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0069AC')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_head_bumps_state_counter_from_f1ba_not_f19c():
    assert player._state26_head(_reader({}), 4) == (5, False)               # F1BA clear: += 1
    assert player._state26_head(_reader({(player.F1BA & 0xFFFFFF, 2): 1}), 4) == (3, True)   # F1BA set: -= 1


def test_tail_hands_off_to_state_9_at_or_past_three():
    result = player.state26_tail(_reader({}), 3)
    assert result['arm'] == 'to-state9'
    assert result['d7'] == player.STATE26_TO_STATE9_D7
    assert result['stores'][player.STATE_INDEX] == (player.STATE26_TO_STATE9_STATE_INDEX, 2)


def test_tail_calls_the_consumer_only_at_exactly_one():
    consume = player.state26_tail(_reader({}), 1)
    assert consume['arm'] == 'consume' and consume['calls_consumer']
    wait = player.state26_tail(_reader({}), 0)
    assert wait['arm'] == 'wait' and not wait['calls_consumer']
    wait2 = player.state26_tail(_reader({}), 2)
    assert wait2['arm'] == 'wait' and not wait2['calls_consumer']


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state26_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'contact consume' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-26').gate_pcs == (boundary.STATE26_ENTRY,)
    assert boundary.STATE26_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-26-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_26_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-26', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 26 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-26-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
