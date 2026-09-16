"""An interrupt handler the machine enters mid-region is set aside by the tracer.

Gods' VBlank lands inside about one per cent of a busy leaf's activations.
Before the tracer marked the handler's steps, every landing position made a
new path class in the census (59 of the sprite sibling's 82 fixtures were
handler variants of four arms) and no plan could be checked on them.  Now
the identity is the region's own path, and ``region_only`` gives the plan
check the region's facts alone.  Pinned on the sprite emitter's retained
fixtures that carry an interrupt (skipped when the local census is absent).
"""
from pathlib import Path

import pytest
import pathfacts

from genesis_re.machine import Machine
from gods_sega import boundary
from gods_sega.profile import GODS

FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0018C8*/0018C8-entry-*.state'))
pytestmark = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0018C8')


def _traces():
    """Every retained fixture's facts, split into interrupted and clean."""
    interrupted, clean = [], {}
    for fixture in FIXTURES:
        facts = pathfacts.trace(fixture.read_bytes(), game=GODS)
        if facts['interrupts_during_trace']:
            interrupted.append((fixture, facts))
        else:
            clean[pathfacts.signature_key(pathfacts.path_signature(facts))] = (fixture, facts)
    return interrupted, clean


def test_handler_steps_are_marked_and_the_pre_empted_instruction_runs_after_the_rte():
    interrupted, _ = _traces()
    if not interrupted:
        pytest.skip('no retained 0018C8 fixture carries an interrupt')
    fixture, facts = interrupted[0]
    steps = facts['steps']
    handler = [step for step in steps if step['interrupt']]
    assert facts['interrupt_steps'] == len(handler) > 0
    first, last = handler[0], handler[-1]
    assert last['text'].startswith('rte')
    # The step that delivered the interrupt names the pre-empted instruction; it executes again after the RTE.
    assert steps[last['n'] + 1]['pc'] == first['pc'] and not steps[last['n'] + 1]['interrupt']
    assert all(not step['interrupt'] for step in steps[:first['n']])
    # The handler's own calls are not the region's.
    assert all(call['step'] < first['n'] or call['step'] > last['n'] for call in facts['calls'])


def test_an_interrupted_occurrence_belongs_to_its_uninterrupted_class_and_checks_region_only():
    interrupted, clean = _traces()
    if not interrupted:
        pytest.skip('no retained 0018C8 fixture carries an interrupt')
    for fixture, facts in interrupted:
        signature = pathfacts.path_signature(facts)
        assert signature['interrupted']
        key = pathfacts.signature_key(signature)
        assert key in clean, f'{fixture.name}: its region path matches no uninterrupted class'
        twin = clean[key][1]
        region = pathfacts.region_only(facts)
        assert region['interrupt_steps'] == 0 and region['interrupts_set_aside'] == facts['interrupts_during_trace']
        assert (region['instructions'], region['cycles']) == (twin['instructions'], twin['cycles'])
        assert region['instructions'] < facts['instructions'] and region['cycles'] < facts['cycles']
        # The plan (a seam here: the upload is where the VBlank lands) checks against the region's facts.
        with Machine(GODS.read_rom()) as machine:
            machine.restore(fixture.read_bytes())
            plan = boundary.sprite_emit_plan(machine, machine.registers())
        prefix = plan.prefix if isinstance(plan, boundary.Seam) else plan
        stop = prefix.registers['pc'] if isinstance(plan, boundary.Seam) else None
        checked = pathfacts.region_only(pathfacts.trace(fixture.read_bytes(), game=GODS, stop_pc=stop))
        problems = [p for p in pathfacts.check_plan(prefix, checked, checked['entry_registers']) if not p.startswith('note:')]
        assert problems == [], (fixture.name, problems)
