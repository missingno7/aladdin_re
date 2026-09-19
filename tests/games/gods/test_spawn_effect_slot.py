"""004A0A: allocate a new effect-slot entry near the record's own position (`docs/gods/blockers/
2026-09-16-00462C-firing.md`'s Split part 3; the trigger evaluator's firing arm, table index 0).
Composes the already-recovered effect-slot pool scan (`effect_slot_find_free_plan`, `004AAA`, itself
00A772's own tail) as a real internal `bsr` -- the SAME "no _ConstMachine needed" shape
`spawn_puff_box_plan` already proves.  Three tiers as for the other leaves; the evidence tiers skip
when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import actions
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X004A0A-*/004A0A-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 004A0A')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_the_type_word_selects_one_of_three_real_terminal_shapes():
    values = {(0x100 + 0xC, 2): 0x10, (0x100 + 0xE, 2): 0x20, (0x100 + 0x12, 2): 0x41}
    result = actions.spawn_effect_slot(_reader(values), 0x100)
    assert result == {'x': 0x10, 'y': 0x20, 'substitute': False, 'type': 0x41, 'arm': 'in-range'}

    values[(0x100 + 0x12, 2)] = actions.EFFECT_SLOT_BSET_TYPE
    assert actions.spawn_effect_slot(_reader(values), 0x100)['arm'] == 'bset'

    values[(0x100 + 0x12, 2)] = 0x05
    assert actions.spawn_effect_slot(_reader(values), 0x100)['arm'] == 'tail'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.SPAWN_EFFECT_SLOT_ENTRY
        plan = boundary.spawn_effect_slot_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('spawn-effect-slot').gate_pcs == (boundary.SPAWN_EFFECT_SLOT_ENTRY,)
    assert boundary.SPAWN_EFFECT_SLOT_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('spawn-effect-slot-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_spawn_effect_slot_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='spawn-effect-slot', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 004A0A within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='spawn-effect-slot-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
