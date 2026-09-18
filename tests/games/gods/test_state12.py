"""State 12 (005FF4): an oscillating swing/pendulum dispatcher -- a genuinely NEW shape, not a
horizontal/vertical/falling twin of anything already recovered.  Shares the already-recovered grid
cell and contact search, and the zone check's own COOLDOWN/SUPPRESS_COOLDOWN fields (game/zones.py,
FFFFEF3E/FFFFF1B6 -- state 12 shares the same RAM words, not the zone check's own routine).  The
oscillation head runs unconditionally every activation; an EA20-gated block test (FFFFEA20 == -1,
provisionally setting STATE_INDEX 11 -- witnessed only via a real 120-frame continuation, not any
single-tick census entry -- or == 1, provisionally setting STATE_INDEX 12) may step POSITION_X; the
retry-budget-exhausted sub-case (FFFFF1A0 >= 6) is real ROM, unwitnessed, and declines by name.  The
tail re-reads the grid cell and either finds ground (state 16, with a three-way COOLDOWN-adjustment
tail), opens a trigger gate into the already-recovered contact_search (state 22), or exits unchanged.
Three tiers as for the other leaves; the evidence tiers skip when the local census or reference
artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-005FF4*/005FF4-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 005FF4')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_oscillate_advances_and_caps():
    result = player.state12_oscillate(_reader({(player.F194 & 0xFFFFFF, 2): 20}))
    assert result['f194'] == player.STATE12_OSCILLATION_CAP
    assert result['position_y_delta'] == 4 + player.STATE12_OSCILLATION_CAP


def test_oscillate_holds_when_ef4c_set():
    values = {(player.F194 & 0xFFFFFF, 2): 3, (player.F194_HOLD & 0xFFFFFF, 2): 1}
    result = player.state12_oscillate(_reader(values))
    assert result['f194'] == 3   # unchanged: the hold flag skips the bump entirely


def test_oscillate_sound_at_tick_cap():
    values = {(player.F198 & 0xFFFFFF, 2): player.STATE12_TICK_CAP - 1}
    result = player.state12_oscillate(_reader(values))
    assert result['f198'] == player.STATE12_TICK_CAP
    assert result['sound'] is True


def test_block_test_right_skips_when_low_bits_mid_range():
    # low = position_x & 0x1c == 8: neither the "== 0x1c" nor the "< 8" gate opens the test.
    blocked = player.state12_block_test_right(_reader({(0x1000 + 1, 1): 1}), 0x1008, 0x1000)
    assert blocked is False


def test_block_test_right_runs_when_low_bits_at_mask():
    blocked = player.state12_block_test_right(_reader({(0x1000 + 1, 1): 1}), 0x101C, 0x1000)
    assert blocked is True


def test_ground_tail_exits_unchanged_within_the_tick_gate():
    result = player.state12_ground_tail(_reader({}), 0x10)   # f198 - 0x14 <= 0
    assert result['cooldown_delta'] is None


def test_ground_tail_suppressed_by_flag():
    values = {(0xFFFFF1B6 & 0xFFFFFF, 2): 1}
    result = player.state12_ground_tail(_reader(values), 0x20)
    assert result['cooldown_delta'] is None


def test_ground_tail_applies_half_the_excess():
    result = player.state12_ground_tail(_reader({}), 0x20)   # excess = 0xc
    assert result['cooldown_delta'] == 6


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state12_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'retry budget exhausted' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-12').gate_pcs == (boundary.STATE12_ENTRY,)
    assert boundary.STATE12_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-12-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_12_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-12', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 12 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-12-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
