"""Real STATE_TABLE index 26 (005724) -- not `test_state26.py`, which is 0069AC, real index 20 (a
misnomer renamed candidate 'state-20', 18 September, real-index-26 recovery session).  The tree's
largest single decline before this session (1,975 of 8,857 fallbacks,
`artifacts/gods/verify-camera-sprites-leaves-2026-09-18t`).

Four top-level arms (`game.player.state_26_step`): `FFFFEA20 != 0` (an unconditional transition to
state 27/28); `FFFFEA20 == 0` with `FFFFEA23` bit 2 set (`state_26_actor_scan`, a bounded 200-entry
scan of `game.movement.BOX_SCAN_TABLE` over `achievements.RECORD_TABLE` and `conditions.FLAGGED`);
bit 2 clear with `FFFFEA1E >= 0` (state 15's own shared body, `_state15_ground_probe` in
boundary.py, factored out of `state4_plan` this session so both callers share it); bit 2 clear with
`FFFFEA1E < 0` (`state_26_box_scan`, a 20-entry table distinct from `game.movement.BOX_SCAN_TABLE`,
then a grid-cell-driven transition-14 arm).  See game/player.py's own module note above
`state_26_step` for the full count breakdown.  Three tiers as for the other leaves; the evidence
tiers skip when the local census or reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-005724-*/005724-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 005724')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_head_transitions_on_nonzero_ea20():
    positive = player.state_26_step(_reader({(player.EA20_WORD & 0xFFFFFF, 2): 1}))
    assert positive['arm'] == 'transition-28' and positive['d7'] == 0
    assert positive['stores'][player.STATE_INDEX] == (player.STATE_26_TO_28, 2)
    negative = player.state_26_step(_reader({(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF}))
    assert negative['arm'] == 'transition-27'
    assert negative['stores'][player.STATE_INDEX] == (player.STATE_26_TO_27, 2)


def test_head_routes_to_actor_scan_on_ea23_bit2():
    result = player.state_26_step(_reader({(player.EA23_WORD & 0xFFFFFF, 1): 4}))
    assert result['arm'] == 'actor-scan'


def test_box_scan_finds_first_eligible_entry_inside_the_box():
    table = player.STATE_26_BOX_SCAN_TABLE
    values = {(player.POSITION_X & 0xFFFFFF, 2): 0x100, (player.POSITION_Y & 0xFFFFFF, 2): 0x100,
             (table & 0xFFFFFF, 2): 0x100, ((table + 2) & 0xFFFFFF, 2): 0x100,
             ((table + 4) & 0xFFFFFF, 2): 1, ((table + 6) & 0xFFFFFF, 2): 0x42}
    result = player.state_26_box_scan(_reader(values))
    assert result['arm'] == 'found'
    assert result['stores'][player.STATE_26_BOX_FOUND & 0xFFFFFF] == (1, 2)
    assert result['stores'][player.STATE_26_BOX_PAYLOAD & 0xFFFFFF] == (0x42, 2)


def test_box_scan_exhausts_when_every_entry_is_ineligible():
    result = player.state_26_box_scan(_reader({}))   # status (+4) reads 0 everywhere: ineligible
    assert result['arm'] == 'not-found'
    assert len(result['entries']) == player.STATE_26_BOX_SCAN_COUNT


def test_actor_scan_declines_when_busy_or_pending_gate_blocks():
    busy = player.state_26_actor_scan(_reader({(player.PROXIMITY_BUSY & 0xFFFFFF, 1): 4}))
    assert busy['arm'] == 'busy-declined'
    pending = player.state_26_actor_scan(_reader({(player.PROXIMITY_PENDING & 0xFFFFFF, 2): 0}))
    assert pending['arm'] == 'pending-declined'


def test_actor_scan_already_active_short_circuits():
    result = player.state_26_actor_scan(_reader({(player.PROXIMITY_ACTIVE & 0xFFFFFF, 2): 1}))
    assert result['arm'] == 'already-active'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state_26_plan(machine, registers)
        except UnsupportedCandidate as error:
            # The narrow declines this session's own census found: the low5<0x10 box-not-found arm's
            # own second test, the actor scan's PROXIMITY_BUSY/PENDING gates and a fully exhausted
            # conditions.FLAGGED search, and state 15's own shared 'not-found' body -- all real ROM,
            # none witnessed by any of the five recordings.
            assert 'not witnessed by a recording' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-26').gate_pcs == (boundary.STATE_26_ENTRY,)
    assert boundary.STATE_26_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
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
