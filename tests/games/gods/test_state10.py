"""State 10 (005EA2): state 12's own oscillation head and BOTH block tests, reused verbatim (no
FFFFF1BA-gated head this time -- state 10 goes straight into the oscillation), with its OWN,
genuinely new ground tail (005FBC-005FF0): STATE_INDEX is set to 0x11 unconditionally, then
conditionally decremented to 0x10 when FFFFF1A8 is non-negative; the cooldown adjustment's own three
sub-cases all converge on the SAME single exit (d7 forced to 0, the sound cue queued). No D7-based
trigger/consume tail either: failing to find ground exits unchanged directly. Three tiers as for
the other leaves; the evidence tiers skip when the local census or reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-005EA2*/005EA2-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 005EA2')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


_GROUND_BYTE_ADDRESS = (0xFFFF885E + 0x180) & 0xFFFFFF   # grid_cell's own address with POSITION_X/Y == 0


def test_ground_index_stays_at_0x11_when_f1a8_negative():
    values = {(_GROUND_BYTE_ADDRESS, 1): 1, (player.F1A8 & 0xFFFFFF, 2): 0xFFFF}
    result = player.state10_step(_reader(values))
    assert result['arm'] == 'ground'
    assert result['f1a8_negative'] is True


def test_ground_index_adjusts_when_f1a8_nonnegative():
    values = {(_GROUND_BYTE_ADDRESS, 1): 1, (player.F1A8 & 0xFFFFFF, 2): 0}
    result = player.state10_step(_reader(values))
    assert result['arm'] == 'ground'
    assert result['f1a8_negative'] is False


def test_ground_tail_exits_unchanged_within_the_tick_gate():
    result = player.state10_ground_tail(_reader({}), 0x10)
    assert result['cooldown_delta'] is None


def test_ground_tail_suppressed_by_flag():
    values = {(0xFFFFF1B6 & 0xFFFFFF, 2): 1}
    result = player.state10_ground_tail(_reader(values), 0x20)
    assert result['cooldown_delta'] is None


def test_ground_tail_applies_half_the_excess():
    result = player.state10_ground_tail(_reader({}), 0x20)
    assert result['cooldown_delta'] == 6


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state10_plan(machine, registers)
        except UnsupportedCandidate as error:
            pytest.fail(f'unexpected decline: {error}')
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-10').gate_pcs == (boundary.STATE10_ENTRY,)
    assert boundary.STATE10_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-10-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_10_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-10', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 10 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-10-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
