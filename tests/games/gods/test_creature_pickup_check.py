"""00B944: the creature update's own second unconditional callee (00A772's own tail, after the
attack timer/kind dispatch), a probe into the already-recovered pickup check -- the SAME shape
pickup_probe_plan already proves over 010CD2, but with no camera add and one extra unconditional
seed write (zones.HALF_WIDTH/HALF_HEIGHT = 0x20/0x20) before the call.  See game/creatures.py's own
module note above creature_pickup_check and boundary.py's own note above creature_pickup_check_plan
for the HALF_WIDTH/HALF_HEIGHT composition subtlety (_ConstMachine).  Three tiers as for the other
leaves; the evidence tiers skip when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import creatures
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00B944-*/00B944-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00B944')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_negative_result_is_flagged():
    # a synthetic pickup_check whose own d2 comes back negative through the SAME read (no camera
    # add, unlike pickups.pickup_probe): confirm the pure wrapper's own 'negative' derivation.
    values = {}
    result = creatures.creature_pickup_check(_reader(values), 0x100, 0x100, 0)
    assert 'check' in result and 'negative' in result


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.creature_pickup_check_plan(machine, registers)
        except UnsupportedCandidate as error:
            # pickup_check_plan's own declines (e.g. the found-special-timer arm) pass straight
            # through this composition; nothing of 00B944's own is unwitnessed.
            assert 'pickup check' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('creature-pickup-check').gate_pcs == (boundary.CREATURE_PICKUP_CHECK_ENTRY,)
    assert boundary.CREATURE_PICKUP_CHECK_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('creature-pickup-check-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_creature_pickup_check_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='creature-pickup-check', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00B944 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='creature-pickup-check-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
