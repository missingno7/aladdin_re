"""State 9 (0066A8): a falling/jump-arc physics dispatcher, paired with state 8 the same way 5/6 and
0/1 are (sharing a jump-arc velocity table and two small grid-probe leaves, 006442/006468, at ROM
addresses right before state 8's own entry 00648C).  The head normalizes STATE_COUNTER; two shared
grid-probe leaves gate an X-advance and, later, two "ground" checks (before and after the fall step)
that transition to state 16; the fall step itself subtracts a jump-arc table entry from POSITION_Y
and, failing both ground checks, either fires a trigger event (state 20, composed with the already-
recovered contact_search) or advances the fall timer, ending unchanged (still state 9) or forcing a
landing (state 12) once the timer caps.  Two EA1E-gated landing checks (transitions to states 14/13)
run first; state 13's own transition is real ROM code, unwitnessed by any of the 1,287 retained
fixtures across all five recordings, and declines by name.  Three tiers as for the other leaves; the
evidence tiers skip when the local census or reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0066A8*/0066A8-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0066A8')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_head_normalizes_state_counter():
    assert player._state9_head(_reader({}), 0xC) == (0xC, 'untouched')          # F19C < 4: stays put
    assert player._state9_head(_reader({(player.F19C & 0xFFFFFF, 2): 4}), 0xC) == (5, 'moveq')
    assert player._state9_head(_reader({}), 5) == (5, 'untouched')
    assert player._state9_head(_reader({}), 0) == (0, 'untouched')
    assert player._state9_head(_reader({(player.F19C & 0xFFFFFF, 2): 4}), 0) == (4, 'addq')
    assert player._state9_head(_reader({}), 3) == (5, 'moveq')                   # any other value -> 5


def test_row_gate_open_direct_match():
    values = {(0x1000 + 0x180, 1): 1}
    assert player._row_gate_open(_reader(values), 0x1000, 0, 0x180) is True


def test_row_gate_open_low_bits_gate():
    # low5 < 8: the second byte is never read, so it cannot rescue a miss.
    values = {(0x1000 + 0x181, 1): 1}
    assert player._row_gate_open(_reader(values), 0x1000, 0, 0x180) is False
    # low5 >= 8: the second byte can find it.
    values = {(0x1000 + 0x181, 1): 1}
    assert player._row_gate_open(_reader(values), 0x1000, 0x10, 0x180) is True


def test_countdown_advances_the_fall_timer_and_stays_in_state_9():
    result = player.state9_fall_tail(_reader({}), None, 0, new_y=0)
    assert result['arm'] == 'countdown'
    assert result['stores'][player.F19C] == (2, 2)


def test_terminal_forces_a_landing_once_the_timer_caps():
    result = player.state9_fall_tail(_reader({}), None, player.STATE9_COUNTDOWN_CAP - 2, new_y=0)
    assert result['arm'] == 'terminal'
    assert result['stores'][player.STATE_INDEX] == (0xC, 2)
    assert result['d7'] == 0


def test_trigger_fires_only_short_of_the_trigger_cap():
    found = player.state9_fall_tail(_reader({}), True, player.STATE9_TRIGGER_CAP - 2, new_y=0)
    assert found['arm'] == 'trigger'
    assert found['stores'][player.STATE_INDEX] == (0x14, 2)
    # STATE9_TRIGGER_CAP + 2 == STATE9_COUNTDOWN_CAP, so "too late for the trigger" always coincides
    # with "the fall timer caps too" -- the tail forces a landing (state 12) instead of a plain
    # countdown once F19C reaches STATE9_TRIGGER_CAP, whether or not a search was found.
    too_late = player.state9_fall_tail(_reader({}), True, player.STATE9_TRIGGER_CAP, new_y=0)
    assert too_late['arm'] == 'terminal'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state9_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'landing-13' in str(error) or 'F19E' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-9').gate_pcs == (boundary.STATE9_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into state 9's
    # own handler; this candidate's own hits replace the direct gate's.
    assert boundary.STATE9_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-9-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_9_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-9', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 9 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-9-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
