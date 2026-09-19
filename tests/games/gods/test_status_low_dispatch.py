"""0032C2: the object post-process low-status dispatch (game.world.status_low_buffer_append /
status_low_kind_dispatch), reached from 003284's own head by fallthrough (not even a branch) when the
matched achievements record's own status is < 3.  The SAME FFFFF260/FFFFF262 buffer 003BBA's own
region already proves, appending (D0, D1, D3) with a real, witnessed reset when D3 == 0x2D, then a
second kind dispatch (0032F6, over the achievements record's own first word) whose 'default'/'0x53'/
'0x36' arms fold in the SAME object_activity_gate-real-call/sprite_emit-opaque-seam pair
status_high_dispatch_plan already proves; '0x6D'/'0x6E' and the 0x40-0x43 range decline by name.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify
from factcheck import perturb_upper_halves

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import world
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X0032C2-kind-*/0032C2-kind*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0032C2')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_append_arm_when_the_counter_stays_within_the_cap():
    values = {(world.STATUS_LOW_BUFFER_POINTER & 0xFFFFFF, 4): 0xFFFF0C04}
    result = world.status_low_buffer_append(_reader(values), 0x100, 0x200, 5)
    assert result['arm'] == 'append' and result['pointer'] == 0xFFFF0C04


def test_reset_append_arm_when_d3_is_the_reset_kind():
    result = world.status_low_buffer_append(_reader({}), 0x100, 0x200, world.STATUS_LOW_RESET_KIND)
    assert result['arm'] == 'reset-append' and result['pointer'] == world.STATUS_LOW_RESET_BASE
    assert result['counter'] == world.STATUS_LOW_BUFFER_CAP


def test_default_kind_dispatch_arm_feeds_the_raw_kind():
    result = world.status_low_kind_dispatch(_reader({}), 0x45)
    assert result['arm'] == 'default' and result['value'] == 0x45


def test_53_kind_dispatch_arm_reads_the_phase_table():
    values = {(world.PHASE_COUNTER_53 & 0xFFFFFF, 2): 2,
             ((world.KIND_DISPATCH2_TABLE_53 + 4) & 0xFFFFFF, 2): 0x108}
    result = world.status_low_kind_dispatch(_reader(values), 0x53)
    assert result['arm'] == '0x53' and result['value'] == 0x108


def test_unrecovered_arms_are_named_not_guessed():
    assert world.status_low_kind_dispatch(_reader({}), 0x6D)['arm'] == 'unrecovered'
    assert world.status_low_kind_dispatch(_reader({}), 0x6E)['arm'] == 'unrecovered'
    assert world.status_low_kind_dispatch(_reader({}), 0x41)['arm'] == 'unrecovered'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_and_declines_the_rest(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.STATUS_LOW_ENTRY
        try:
            plan = boundary.status_low_dispatch_plan(machine, registers)
        except UnsupportedCandidate:
            return
    assert isinstance(plan, boundary.Seam)
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.prefix.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan.prefix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('prefix', fixture, problems)
    resumed = pathfacts.park(state, plan.resume_pc, game=GODS)
    with Machine(GODS.read_rom()) as machine:
        machine.restore(resumed)
        registers = machine.registers()
        assert registers['a7'] == plan.stack_basis
        suffix = plan.suffix(machine, registers)
    facts = pathfacts.trace(resumed, game=GODS, stop_pc=boundary.OBJECT_KIND_SCAN_LOOP)
    problems = [p for p in pathfacts.check_plan(suffix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('suffix', fixture, problems)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_under_perturbed_upper_halves(fixture):
    state = perturb_upper_halves(GODS, fixture.read_bytes())
    if state is None:
        pytest.skip('the adapter refused the constructed entry (a bank or interrupt guard)')
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.STATUS_LOW_ENTRY
        try:
            plan = boundary.status_low_dispatch_plan(machine, registers)
        except UnsupportedCandidate:
            return
    facts = pathfacts.trace(state, game=GODS, stop_pc=plan.prefix.registers['pc'])
    problems = [p for p in pathfacts.check_plan(plan.prefix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('prefix', fixture, problems)
    resumed = pathfacts.park(state, plan.resume_pc, game=GODS)
    with Machine(GODS.read_rom()) as machine:
        machine.restore(resumed)
        registers = machine.registers()
        assert registers['a7'] == plan.stack_basis
        suffix = plan.suffix(machine, registers)
    facts = pathfacts.trace(resumed, game=GODS, stop_pc=boundary.OBJECT_KIND_SCAN_LOOP)
    problems = [p for p in pathfacts.check_plan(suffix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('suffix', fixture, problems)


def test_candidate_names_are_explicit():
    assert recovery.Candidate('status-low-dispatch').gate_pcs == (boundary.STATUS_LOW_ENTRY,)
    assert boundary.STATUS_LOW_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('status-low-dispatch-mutant-register').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='status-low-dispatch', reference=EVIDENCE)
        if report['candidate_hits'] >= 1 and set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS:
            break
    else:
        pytest.skip('no retained fixture reaches 0032C2 cleanly within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='status-low-dispatch-mutant-register',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
