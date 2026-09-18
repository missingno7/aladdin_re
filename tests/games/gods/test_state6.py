"""State 6 (0074C2): a byte-for-byte MIRROR of state 5's own shape (`game.player.state6_step`), ALSO
reached by a `bra.w` fallthrough from inside state 0's own body (`state0_handoff`, `0074A2`).  Calls
the SECONDARY contact-consume routine (`012E5A`) instead of the primary, and its own fallback lands
on state 0's own gate (`pc = 0x006FFE`, `STATE_INDEX` cleared to 0) instead of state 1's.  The
handoff and contact-search-gate arms are the exact same shared code state 5's own entry reaches.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0074C2*/0074C2-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0074C2')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_counter_under_five_takes_the_table_handoff_without_touching_ea23():
    result = player.state6_step(_reader({}), 0)
    assert result['arm'] == 'handoff' and result['counter'] == 1 and not result['calls_consumer']


def test_counter_reaching_exactly_three_also_calls_the_consumer():
    result = player.state6_step(_reader({}), 2)
    assert result['arm'] == 'handoff' and result['counter'] == 3 and result['calls_consumer']


def test_counter_five_or_more_with_bit2_clear_falls_back():
    result = player.state6_step(_reader({}), 4)
    assert result['arm'] == 'fallback' and result['counter'] == 5 and not result['calls_consumer']


def test_counter_five_or_more_with_bit2_set_gates_on_contact_search():
    values = {(player.EA23_WORD & 0xFFFFFF, 1): 4}
    result = player.state6_step(_reader(values), 4)
    assert result['arm'] == 'gate' and result['counter'] == 5


def test_fallback_clears_state_index_to_zero_not_state_counter():
    stores = player.state6_fallback_stores()
    assert stores == {player.STATE_INDEX: (0, 2)}
    assert player.STATE_COUNTER not in stores


def test_state6_reuses_the_shared_handoff_table_state5_uses():
    values = {(player.STATE1_HANDOFF_TABLE & 0xFFFFFF, 2): 0x4321}
    result = player.state5_handoff(_reader(values), 0)
    assert result['d7'] == 0x4321
    assert result['stores'][player.STATE_COUNTER] == (0, 2)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state6_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'contact consume' in str(error) or 'active-selector override' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-6').gate_pcs == (boundary.STATE6_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into state 6's
    # own handler; this candidate's own hits replace the direct gate's.
    assert boundary.STATE6_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-6-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_6_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-6', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 6 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-6-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
