"""0048EA: spawn a puff in a box around the caller's own record position (`docs/gods/blockers/
2026-09-19-0030CC.md`'s own second bite; `docs/gods/blockers/2026-09-16-00462C-firing.md`'s Split
part 3).  Composes the already-recovered box-scan puff spawner (`spawn_scan_plan`, `004926`) as a
real internal call -- 0048EA is reached by the evaluator's own tail jump, has no frame of its own,
and its own `rts` returns straight past the whole `00462C` activation.  Three tiers as for the other
leaves; the evidence tiers skip when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import actions
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X0048EA-*/0048EA-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0048EA')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_the_box_is_plus_minus_12_around_the_record_position():
    values = {(0x100 + 0xC, 2): 0x50, (0x100 + 0xE, 2): 0x80}
    result = actions.spawn_puff_box(_reader(values), 0x100)
    assert result == {'x': 0x50, 'y': 0x80, 'substitute': False,
                      'x_min': 0x50 - 0xC, 'x_max': 0x50 + 0xC, 'y_min': 0x80 - 0xC, 'y_max': 0x80 + 0xC}


def test_the_position_flag_substitution_is_named_but_never_assumed_safe():
    values = {(0x200 + 0xC, 2): actions.SPAWN_SUBSTITUTE_X, (0x200 + 0xE, 2): actions.SPAWN_SUBSTITUTE_Y,
             (actions.SUBSTITUTE_FLAG & 0xFFFFFF, 4): 1}
    result = actions.spawn_puff_box(_reader(values), 0x200)
    assert result['substitute'] is True and result['y'] == actions.SPAWN_SUBSTITUTE_Y_REPLACEMENT
    # the same position with the flag not set to exactly 1 is NOT a substitution
    values[(actions.SUBSTITUTE_FLAG & 0xFFFFFF, 4)] = 2
    assert actions.spawn_puff_box(_reader(values), 0x200)['substitute'] is False


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.SPAWN_PUFF_BOX_ENTRY
        plan = boundary.spawn_puff_box_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_census
def test_the_position_flag_substitution_is_declined_when_it_would_fire():
    # None of the retained fixtures ever witnesses it (all 17 take the plain arm); confirm the
    # planner declines rather than guesses if a synthetic record ever matched it -- injected the same
    # way test_camera.py's own unwitnessed-clamp test does (machine.atomic as a RAM poke).
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        pc, a1 = registers['pc'], registers['a1']
        assert pc == boundary.SPAWN_PUFF_BOX_ENTRY
        machine.gates([pc])
        assert machine.run(instructions=1) == 'gate'
        writes = (boundary._bytes((a1 + 0xC) & 0xFFFFFF, actions.SPAWN_SUBSTITUTE_X, 2)
                 + boundary._bytes((a1 + 0xE) & 0xFFFFFF, actions.SPAWN_SUBSTITUTE_Y, 2)
                 + boundary._bytes(actions.SUBSTITUTE_FLAG & 0xFFFFFF, 1, 4))
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=pc,
                              writes=list(writes), registers=machine.registers())
        with pytest.raises(UnsupportedCandidate, match='substitution'):
            boundary.spawn_puff_box_plan(machine, machine.registers())


def test_candidate_name_is_explicit():
    assert recovery.Candidate('spawn-puff-box').gate_pcs == (boundary.SPAWN_PUFF_BOX_ENTRY,)
    assert boundary.SPAWN_PUFF_BOX_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    # spawn-scan stays armed too: it has a second, real, still-unrecovered caller (0139D2).
    assert boundary.SPAWN_SCAN_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('spawn-puff-box-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_spawn_puff_box_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='spawn-puff-box', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 0048EA within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='spawn-puff-box-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
