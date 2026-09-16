"""The line walker's resume (00FFF0): the object copy stepping a solid's walk from its persistent record.

The first stateful Gods subsystem: the record is game state (the solid's
progress along its waypoint line), read at the entry and re-armed at the
exit, and the next call continues from what this call wrote — so the
evidence tiers here run more than one invocation.  Fixture tier: every
retained 00FFF0 class MATCHes (the step arithmetic, the yield on the budget
or on the counter, the register residue with movem's sign extension).
Segment tier: the candidate over real frames from a retained walker state
against the original, with dozens of consecutive invocations of the same
records, and its mutant diverging at the first re-armed record.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import walker
from gods_sega.profile import GODS

FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00FFF0*/00FFF0-*-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00FFF0')


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.WALKER_RESUME_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.walker_resume_plan(machine, registers)
        walk = walker.load(boundary._reader(machine), registers['a3'] & 0xFFFFFF, 'object')
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc == boundary._WR_RTS[walk.phase]


@needs_census
def test_a_record_that_is_not_a_walk_and_a_zero_budget_are_declined():
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        record = registers['a3'] & 0xFFFF
        machine.gates([registers['pc']])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=registers['pc'],
                              writes=[(walker.BUDGET, 0), (walker.BUDGET + 1, 0)], registers=registers)
        with pytest.raises(boundary.UnsupportedCandidate, match='zero budget'):
            boundary.walker_resume_plan(machine, machine.registers())
        machine.restore(state)
        machine.gates([registers['pc']])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=registers['pc'],
                              writes=[(0xFF0000 | record, 0x00), (0xFF0000 | record + 1, 0x00), (0xFF0000 | record + 2, 0x12),
                                      (0xFF0000 | record + 3, 0x34)], registers=registers)
        with pytest.raises(boundary.UnsupportedCandidate, match='not one of the object walker bodies'):
            boundary.walker_resume_plan(machine, machine.registers())


def test_candidate_names_are_explicit():
    assert recovery.Candidate('walker').gate_pcs == (boundary.WALKER_RESUME_ENTRY,)
    assert boundary.WALKER_RESUME_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('walker-mutant-result').mutation is recovery._mutate_walk


@needs_census
def test_consecutive_invocations_continue_from_the_re_armed_record_and_the_mutant_diverges():
    """The persistent-state tier: invocation N writes the record invocation N+1 reads, over real frames."""
    fixture = next(p for p in FIXTURES if p.parent.name == 'census-00FFF0')
    report = segment_verify.check(fixture, game=GODS, frames=300, candidate='walker')
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] >= 10 and set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=300, candidate='walker-mutant-result')
    assert mutant['status'] == 'DIVERGENCE' and mutant['first_difference']['frame'] == report['from_frame'] + 1
