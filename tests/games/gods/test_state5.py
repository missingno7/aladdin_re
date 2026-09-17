"""State 5 (00746A): the player state machine's own dispatch table entry 5, ALSO reached by a
`bra.w` fallthrough from inside state 1's own body (0073E0) -- "one region, two gates, one planner"
(`docs/gods/blockers/2026-09-17-005700.md`'s Decision).  A counter under 5 (post-increment; a
counter that becomes exactly 3 also calls the already-recovered contact-consume primary `012DA0`
first) always takes a deterministic table hand-off into the shared tail (`pc = 0x0075DA`); a counter
of 5 or more gates on `FFFFEA23` bit 2 -- clear, or a contact-search (`008222`) 'not found' result,
falls all the way OUT of state 5's own body into state 1's own gate (`pc = 0x007282`, a SEPARATELY
ARMED candidate this plan hands off to rather than inlining); a contact-search 'found' result takes
the SAME table hand-off through its own index-0 entry.  Three tiers as for the other leaves; the
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00746A*/00746A-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00746A')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_counter_under_five_takes_the_table_handoff_without_touching_ea23():
    result = player.state5_step(_reader({}), 0)
    assert result['arm'] == 'handoff' and result['counter'] == 1 and not result['calls_consumer']
    result = player.state5_step(_reader({}), 3)
    assert result['arm'] == 'handoff' and result['counter'] == 4 and not result['calls_consumer']


def test_counter_reaching_exactly_three_also_calls_the_consumer():
    result = player.state5_step(_reader({}), 2)
    assert result['arm'] == 'handoff' and result['counter'] == 3 and result['calls_consumer']


def test_counter_five_or_more_with_bit2_clear_falls_back():
    result = player.state5_step(_reader({}), 4)
    assert result['arm'] == 'fallback' and result['counter'] == 5 and not result['calls_consumer']


def test_counter_five_or_more_with_bit2_set_gates_on_contact_search():
    values = {(player.EA23_WORD & 0xFFFFFF, 1): 4}
    result = player.state5_step(_reader(values), 4)
    assert result['arm'] == 'gate' and result['counter'] == 5


def test_handoff_reads_the_shared_table_at_the_live_index_and_stores_it_as_the_counter():
    values = {(player.STATE1_HANDOFF_TABLE + 2 & 0xFFFFFF, 2): 0x99}
    result = player.state5_handoff(_reader(values), 1)
    assert result['d7'] == 0x99
    assert result['stores'][player.STATE_COUNTER] == (1, 2)


def test_handoff_index_zero_matches_state1_handoffs_own_table_read():
    values = {(player.STATE1_HANDOFF_TABLE & 0xFFFFFF, 2): 0x1234}
    result = player.state5_handoff(_reader(values), 0)
    assert result['d7'] == 0x1234
    assert result['stores'][player.STATE_COUNTER] == (0, 2)


def test_fallback_stores_only_state_index_not_state_counter():
    stores = player.state5_fallback_stores()
    assert stores == {player.STATE_INDEX: (1, 2)}
    assert player.STATE_COUNTER not in stores


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state5_plan(machine, registers)
        except UnsupportedCandidate as error:
            # A counter of 3 also calls the already-recovered contact-consume primary (012DA0)
            # internally; a type that routine itself does not recognise (or the active-selector
            # override, unwitnessed by any recording) is its own decline, not state 5's.
            assert 'contact consume' in str(error) or 'active-selector override' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-5').gate_pcs == (boundary.STATE5_ENTRY,)
    assert boundary.STATE5_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-5-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_state_5_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-5', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 5 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-5-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
