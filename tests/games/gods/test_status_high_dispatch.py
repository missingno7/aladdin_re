"""003BBA: the object post-process high-status dispatch (game.world.status_high_buffer_append),
reached from 003284's own head (`docs/gods/blockers/2026-09-19-003186.md`'s own Progress note) when
the entry's own object status word is already >= 0xC0.  A fourth FFFFF262-gated triple-buffer append
(mirroring 0032C2's own shape), then a Seam: the prefix folds in a real internal call into the
already-recovered object_activity_gate (003480, always a plain AtomicPlan) and ends at the second bsr
(0018C8's own entry); the ceded block is the whole sprite_emit call, opaque; the suffix is the same
"restore d7/a0/a2, bra the scan loop" tail 0036E2's own suffix already proves.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X003BBA-d2-*/003BBA-d2-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 003BBA')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_append_arm_advances_the_pointer_by_one_triple():
    values = {(world.STATUS_HIGH_COUNTER & 0xFFFFFF, 2): 0, (world.STATUS_HIGH_BUFFER_POINTER & 0xFFFFFF, 4): 0xFFFF0C04}
    result = world.status_high_buffer_append(_reader(values), 0x100, 0x200, 0xC0)
    assert result['arm'] == 'append' and result['pointer'] == 0xFFFF0C04 and result['next_pointer'] == 0xFFFF0C0A


def test_skip_arm_once_the_counter_would_exceed_the_cap():
    values = {(world.STATUS_HIGH_COUNTER & 0xFFFFFF, 2): world.STATUS_HIGH_BUFFER_CAP}
    result = world.status_high_buffer_append(_reader(values), 0, 0, 0)
    assert result['arm'] == 'skip'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_and_declines_the_rest(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.STATUS_HIGH_ENTRY
        try:
            plan = boundary.status_high_dispatch_plan(machine, registers)
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
        assert registers['pc'] == boundary.STATUS_HIGH_ENTRY
        try:
            plan = boundary.status_high_dispatch_plan(machine, registers)
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
    assert recovery.Candidate('status-high-dispatch').gate_pcs == (boundary.STATUS_HIGH_ENTRY,)
    assert boundary.STATUS_HIGH_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('status-high-dispatch-mutant-register').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    # Some retained fixtures' own 120-frame window also reaches a LATER real occurrence of this same
    # gate whose composed object_activity_gate_plan hits pickup_award_group_plan's own honest
    # 'unrecovered-leading-group' decline (a real, already-named fallback of an already-recovered
    # candidate, not a defect here) -- skip those windows for a clean one rather than loosen the check.
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='status-high-dispatch', reference=EVIDENCE)
        if report['candidate_hits'] >= 1 and set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS:
            break
    else:
        pytest.skip('no retained fixture reaches 003BBA cleanly within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='status-high-dispatch-mutant-register',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
