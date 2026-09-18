"""State 4 (007538): FFFFEA20 == 0 jumps directly into state 15's own entry (006D68, the SAME
"one region, two gates" shared-fallthrough shape as states 5/6 into 1/0) -- the FIRST real evidence
of state 15's own semantics, though state 15 remains unwitnessed as an independent dispatch.
FFFFEA20 < 0 transitions to state 3 (d7 forced to 0); FFFFEA20 > 0 transitions to state 2 (d7
forced to 2). Three tiers as for the other leaves; the evidence tiers skip when the local census or
reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-007538*/007538-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 007538')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_negative_ea20_transitions_to_state_3():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0xFFFF}
    result = player.state4_step(_reader(values), 5)
    assert result['arm'] == 'transition-3'
    assert result['d7'] == 0


def test_positive_ea20_transitions_to_state_2():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 1}
    result = player.state4_step(_reader(values), 5)
    assert result['arm'] == 'transition-2'
    assert result['d7'] == 2


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state4_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'ground not found' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-4').gate_pcs == (boundary.STATE4_ENTRY,)
    assert boundary.STATE4_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-4-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_4_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-4', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 4 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-4-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
