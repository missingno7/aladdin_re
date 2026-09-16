"""The line walker's resume, projectile copy (0093D2): a byte-for-byte duplicate of 00FFF0's own body.

Same evidence shape as `test_walker_resume.py`: the record is game
state (a pooled projectile's progress along its walk), read at the
entry and re-armed at the exit.  Fixture tier: every retained class
across four recordings that fire projectiles MATCHes (the same
`_WR_HEAD`/`_WR_STEP`/`_WR_TAIL` cost fragments `WALKER_RESUME_ENTRY`'s
own plan uses, confirmed identical).  The driver `009210` that calls
this resume once per pooled projectile per tick is read for context
only, not modelled (`docs/gods/blockers/2026-09-16-0091BC.md`).
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

FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0093D2*/0093D2-*-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0093D2')


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.PROJECTILE_RESUME_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        plan = boundary.walker_resume_projectile_plan(machine, registers)
        walk = walker.load(boundary._reader(machine), registers['a3'] & 0xFFFFFF, 'projectile')
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert (facts['exit_pc'] == plan.registers['pc']
           and facts['last_pc'] == plan.last_pc == boundary._WR_PROJECTILE_RTS[walk.phase])


def test_candidate_names_are_explicit():
    assert recovery.Candidate('projectile-resume').gate_pcs == (boundary.PROJECTILE_RESUME_ENTRY,)
    assert boundary.PROJECTILE_RESUME_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('projectile-resume-mutant-result').mutation is recovery._mutate_walk


@needs_census
def test_candidate_matches_the_original_over_real_frames_and_its_mutant_diverges():
    fixture = next(p for p in FIXTURES if p.parent.name.startswith('census-0093D2-fb408bc75597'))
    report = segment_verify.check(fixture, game=GODS, frames=120, candidate='projectile-resume')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    if report['candidate_hits'] == 0:
        pytest.skip('projectile-resume never hits in this window')
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='projectile-resume-mutant-result')
    assert mutant['status'] == 'DIVERGENCE'
