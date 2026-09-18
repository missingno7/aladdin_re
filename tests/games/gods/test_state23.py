"""State 23 (006164): state 21/22's own FFFFF1BA-gated head and D7-based tail shape, sitting
immediately before state 22's own code in ROM (006164-0062AC, then 0062B0 is STATE22_ENTRY itself).
Structurally identical to state 22's own body (the same oscillation, the same LEFT/RIGHT block
tests, the same ALT ground test with its own 0x1F mask), but the ground-found jump lands on state
11's own PHYSICAL ground tail (005E6C, not state 12's own 00612E) and the D7-based tail differs in
its own two targets: exactly 3 transitions to state 11 (not state 22's own state 12); exactly 1
calls the already-recovered movement-cluster consumer 012E5A SECONDARY (not state 22's own 012DA0
PRIMARY). Three tiers as for the other leaves; the evidence tiers skip when the local census or
reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine, NativeError
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-006164*/006164-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 006164')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_head_bumps_d7_when_f1ba_clear():
    new_d7, f1ba_was_set = player._state23_head(_reader({}), 2)
    assert new_d7 == 3
    assert f1ba_was_set is False


def test_tail_reaches_trigger_at_exactly_3():
    result = player.state23_step(_reader({}), 2)
    assert result['arm'] == 'trigger'
    assert result['d7'] == 3


def test_tail_reaches_consume_at_exactly_1():
    result = player.state23_step(_reader({}), 0)
    assert result['arm'] == 'consume'
    assert result['d7'] == 1


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state23_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'not witnessed' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-23').gate_pcs == (boundary.STATE23_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into state 23's
    # own handler; this candidate's own hits replace the direct gate's.
    assert boundary.STATE23_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-23-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_23_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-23', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 23 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    try:
        mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-23-mutant-result', reference=EVIDENCE)
    except NativeError:
        # The same class of crash-as-divergence state 22's own mutant produces (dropping
        # contact_consume's own writes wholesale corrupts a record the real game dereferences a few
        # frames later): a legitimate divergence history-verify's own crash-tolerant comparison
        # reports cleanly, which segment_verify's own lighter check does not catch.
        return
    assert mutant['status'] == 'DIVERGENCE'
