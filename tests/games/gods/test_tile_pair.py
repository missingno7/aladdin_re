"""003BEC: the tile-pair VDP writer (game.world.paint_tile_pair), a real call boundary (a genuine bsr,
a plain rts) reached from 0032F6's own 0x40-0x43 range arm and, empirically, from real callers this
session did not need to identify (tens of thousands of occurrences per recording).  Off-screen in
either axis (the SAME OBJECT_TILE_MARGIN/SCREEN_X_LIMIT/SCREEN_Y_LIMIT shape 001810's own paint arm
uses) is a plain leaf; on-screen is a Seam over two fixed VDP control writes -- never a data loop,
unlike 0018C8/00126A's own cache-miss uploads.  An earlier note read this region as part of "the map
streaming interpreter [...] which does not return within a frame"; a full-tree census (all five
recordings) shows a clean, bounded 8-35 instruction leaf on every one of ~83,000 real occurrences, no
deadline cut ever -- that note was reconnaissance-stage, not confirmed by any trace.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify
from factcheck import perturb_upper_halves

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import sprites, world
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X003BEC-*/003BEC-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 003BEC')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_offscreen_x_arm():
    values = {(sprites.CAMERA_X & 0xFFFFFF, 2): 0x100}
    result = world.paint_tile_pair(_reader(values), 0x2000, 0, 5)
    assert result['arm'] == 'offscreen-x'


def test_offscreen_y_arm():
    values = {(sprites.CAMERA_X & 0xFFFFFF, 2): 0, (sprites.CAMERA_Y & 0xFFFFFF, 2): 0x100}
    result = world.paint_tile_pair(_reader(values), 0x10, 0x2000, 5)
    assert result['arm'] == 'offscreen-y'


def test_paint_arm_builds_the_nametable_command_and_names_the_index():
    values = {(sprites.CAMERA_X & 0xFFFFFF, 2): 0, (sprites.CAMERA_Y & 0xFFFFFF, 2): 0}
    result = world.paint_tile_pair(_reader(values), 0x80, 0x40, 0)
    assert result['arm'] == 'paint'
    assert result['command'] == world.tile_pair_command(_reader(values), 0x80, 0x40)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.TILE_PAIR_ENTRY
        plan = boundary.tile_pair_plan(machine, registers)
    if isinstance(plan, boundary.Seam):
        facts = pathfacts.trace(state, game=GODS, stop_pc=plan.prefix.registers['pc'])
        problems = [p for p in pathfacts.check_plan(plan.prefix, facts, facts['entry_registers']) if not p.startswith('note:')]
        assert problems == [], ('prefix', fixture, problems)
        resumed = pathfacts.park(state, plan.resume_pc, game=GODS)
        with Machine(GODS.read_rom()) as machine:
            machine.restore(resumed)
            registers = machine.registers()
            assert registers['a7'] == plan.stack_basis
            suffix = plan.suffix(machine, registers)
        facts = pathfacts.trace(resumed, game=GODS, stop_pc=suffix.registers['pc'])
        problems = [p for p in pathfacts.check_plan(suffix, facts, facts['entry_registers']) if not p.startswith('note:')]
        assert problems == [], ('suffix', fixture, problems)
        return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], (fixture, problems)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_under_perturbed_upper_halves(fixture):
    state = perturb_upper_halves(GODS, fixture.read_bytes())
    if state is None:
        pytest.skip('the adapter refused the constructed entry (a bank or interrupt guard)')
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.TILE_PAIR_ENTRY
        plan = boundary.tile_pair_plan(machine, registers)
    if isinstance(plan, boundary.Seam):
        facts = pathfacts.trace(state, game=GODS, stop_pc=plan.prefix.registers['pc'])
        problems = [p for p in pathfacts.check_plan(plan.prefix, facts, facts['entry_registers']) if not p.startswith('note:')]
        assert problems == [], ('prefix', fixture, problems)
        resumed = pathfacts.park(state, plan.resume_pc, game=GODS)
        with Machine(GODS.read_rom()) as machine:
            machine.restore(resumed)
            registers = machine.registers()
            assert registers['a7'] == plan.stack_basis
            suffix = plan.suffix(machine, registers)
        facts = pathfacts.trace(resumed, game=GODS, stop_pc=suffix.registers['pc'])
        problems = [p for p in pathfacts.check_plan(suffix, facts, facts['entry_registers']) if not p.startswith('note:')]
        assert problems == [], ('suffix', fixture, problems)
        return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], (fixture, problems)


def test_candidate_names_are_explicit():
    assert recovery.Candidate('tile-pair').gate_pcs == (boundary.TILE_PAIR_ENTRY,)
    assert boundary.TILE_PAIR_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('tile-pair-mutant-register').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                  candidate='tile-pair', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('tile-pair never hits in this window')
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                  candidate='tile-pair-mutant-register', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
