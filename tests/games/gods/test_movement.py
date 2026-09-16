"""The collision gate (010A14): a phase counter and a +-4 residue test, both over a caller-supplied state struct.

'held' (the global gate word is set) and 'gated' (the residue after the
phase advance is nonzero) are a plain leaf, no frame, no calls.  'collision'
(the residue is zero) calls 010CBC and dereferences the level grid: declined
even though witnessed.  The phase>7 arm ('over') is real ROM code but no
recording that reaches this entry (only two of the eight) ever takes it, so
it is declined as unwitnessed.  Three tiers as for the other leaves; the
evidence tiers skip when the local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import movement
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-010A14*/010A14-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 010A14')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

STATE = 0xFF3800


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def test_the_global_gate_holds_the_phase_and_touches_nothing_else():
    values = {(STATE + movement.PHASE, 2): 3, (movement.GLOBAL_GATE, 2): 1}
    result = movement.collision_gate(_reader(values), STATE, 0x100)
    assert result['arm'] == 'held' and result['tail_d2'] == 3 and result['d0'] == 0x100
    assert result['stores'] == {movement.TAIL_BASE & 0xFFFFFF: (movement.TAIL_BASE_VALUE, 2)}


def test_the_phase_advances_mod_eight_and_d0_moves_by_the_moving_state_sign():
    values = {(STATE + movement.PHASE, 2): 7, (movement.GLOBAL_GATE, 2): 0, (STATE + movement.MOVING_STATE, 2): 1}
    result = movement.collision_gate(_reader(values), STATE, 0x100)
    assert result['tail_d2'] == 0 and result['d0'] == 0x104     # (7+1)&7 == 0; +4 since moving != 0
    assert result['stores'][(STATE + movement.PHASE) & 0xFFFFFF] == (0, 2)
    values[(STATE + movement.MOVING_STATE, 2)] = 0
    values[(STATE + movement.PHASE, 2)] = 2
    result = movement.collision_gate(_reader(values), STATE, 0x104)
    assert result['d0'] == 0x100                                 # -4 since moving == 0


def test_a_zero_residue_is_the_collision_arm_and_phase_over_seven_is_the_over_arm():
    values = {(STATE + movement.PHASE, 2): 0, (movement.GLOBAL_GATE, 2): 0, (STATE + movement.MOVING_STATE, 2): 0}
    result = movement.collision_gate(_reader(values), STATE, 4)      # (0+1)&7=1, d0-4=0, residue 0
    assert result['arm'] == 'collision'
    result = movement.collision_gate(_reader({(STATE + movement.PHASE, 2): 9}), STATE, 0)
    assert result['arm'] == 'over' and result['tail_d2'] == 8
    assert result['stores'][(STATE + movement.PHASE) & 0xFFFFFF] == (8, 2)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_the_held_and_gated_arms_and_declines_the_rest(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.COLLISION_GATE_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        record = registers['a5'] & 0xFFFFFF
        result = movement.collision_gate(boundary._reader(machine), record, registers['d0'] & 0xFFFF)
        if result['arm'] in ('collision', 'over'):
            with pytest.raises(boundary.UnsupportedCandidate):
                boundary.collision_gate_plan(machine, registers)
            return
        plan = boundary.collision_gate_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('collision-gate').gate_pcs == (boundary.COLLISION_GATE_ENTRY,)
    assert boundary.COLLISION_GATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('collision-gate-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='collision-gate',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('collision-gate never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='collision-gate-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
