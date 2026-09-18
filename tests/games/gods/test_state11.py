"""State 11 (005D32): BYTE-IDENTICAL to state 12's own oscillation head and EA20-gated block test
(confirmed via a raw ROM diff, rom[0x005D32:0x005E28] == rom[0x005FF4:0x0060EA], differing only in
relocated branch displacement bytes); the ground tail's real instructions are the same four stores,
just reordered in the ROM.  `game.player.state11_step`/`state11_ground_tail` reuse state 12's own
`state12_oscillate`/`state12_block_test_left`/`state12_block_test_right` directly and target
STATE_INDEX 17 (ground) / 23 (trigger, state 23) instead of state 12's own 16/22.  Three tiers as
for the other leaves; the evidence tiers skip when the local census or reference artifacts are
absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-005D32*/005D32-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 005D32')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_ground_tail_reuses_state_12s_own_shape():
    # Same three real outcomes as state12_ground_tail, just under state 11's own name.
    assert player.state11_ground_tail(_reader({}), 0x10)['cooldown_delta'] is None
    values = {(0xFFFFF1B6 & 0xFFFFFF, 2): 1}
    assert player.state11_ground_tail(_reader(values), 0x20)['cooldown_delta'] is None
    assert player.state11_ground_tail(_reader({}), 0x20)['cooldown_delta'] == 6


def test_ground_tail_targets_are_state_11s_own():
    assert player.STATE11_GROUND_INDEX == 0x11
    assert player.STATE11_TRIGGER_INDEX == 0x17


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state11_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'retry budget exhausted' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-11').gate_pcs == (boundary.STATE11_ENTRY,)
    assert boundary.STATE11_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-11-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_11_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-11', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 11 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-11-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
