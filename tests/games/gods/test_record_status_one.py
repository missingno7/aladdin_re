"""00354C: the record-status-1 sub-dispatch (game.world.record_status_one_dispatch), reached from
object_activity_gate's own body (achievements.RECORD_TABLE record status == 1) by a plain branch, not
a bsr -- the same non-call-boundary shape 0036E2 (object-kind-dispatch) already proved.  Status
outside [0xC, 0x12) ('award') converts the achievements record's own +6 field through the
already-recovered score conversion (00364C) and queues it (002F2E); status odd inside the range
('odd') is a plain store; status even inside the range keys a derived index against the 4-entry
FFFFF22E table ('found'/'not-found').  Every arm rejoins object_activity_gate's own shared 'pass'
exit (0034B2's own movem-pop/clr/rtr tail), which this planner owns directly -- the exit PC varies by
fixture (003480 is itself bsr'd from at least three call sites), so every trace here stops at the
plan's own claimed exit rather than a single fixed address.

Fixtures are captured directly at the gate with a word-wide D2 classifier
(`recovery_census.capture_entries`, plain mode) over the whole history, one method for both the
census tool and this test: the standard census tool cannot classify a mid-function branch target
either way (`docs/gods/blockers/2026-09-19-003480.md`, `2026-09-19-003186.md`'s own 0036E2 account).
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X00354C-d2-*/00354C-d2-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00354C')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_award_arm_outside_the_table_window_low():
    result = world.record_status_one_dispatch(_reader({}), 5, 0x1000)
    assert result['arm'] == 'award'


def test_award_arm_outside_the_table_window_high():
    result = world.record_status_one_dispatch(_reader({}), 0x20, 0x1000)
    assert result['arm'] == 'award'


def test_odd_arm_inside_the_window():
    result = world.record_status_one_dispatch(_reader({}), 0xD, 0x1000)
    assert result['arm'] == 'odd'


def test_found_arm_when_the_derived_index_matches_a_table_slot():
    index = ((0x10 - world.RECORD_ONE_RANGE_LOW) >> 1) + 0x15
    values = {(world.RECORD_ONE_TABLE & 0xFFFFFF, 2): 0xFFFF, ((world.RECORD_ONE_TABLE + 2) & 0xFFFFFF, 2): index}
    result = world.record_status_one_dispatch(_reader(values), 0x10, 0x1000)
    assert result['arm'] == 'found' and result['slot'] == 1 and result['index'] == index


def test_not_found_arm_when_no_table_slot_matches():
    values = {(world.RECORD_ONE_TABLE & 0xFFFFFF, 2): 0xFFFF, ((world.RECORD_ONE_TABLE + 2) & 0xFFFFFF, 2): 0xFFFF,
             ((world.RECORD_ONE_TABLE + 4) & 0xFFFFFF, 2): 0xFFFF, ((world.RECORD_ONE_TABLE + 6) & 0xFFFFFF, 2): 0xFFFF}
    result = world.record_status_one_dispatch(_reader(values), 0x10, 0x1000)
    assert result['arm'] == 'not-found'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_and_declines_the_rest(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.RECORD_ONE_ENTRY
        try:
            plan = boundary.record_status_one_plan(machine, registers)
        except UnsupportedCandidate:
            return
        stop = plan.registers['pc']
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=stop))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], (fixture, problems)
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_under_perturbed_upper_halves(fixture):
    state = perturb_upper_halves(GODS, fixture.read_bytes())
    if state is None:
        pytest.skip('the adapter refused the constructed entry (a bank or interrupt guard)')
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.RECORD_ONE_ENTRY
        try:
            plan = boundary.record_status_one_plan(machine, registers)
        except UnsupportedCandidate:
            return
        stop = plan.registers['pc']
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=stop))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], (fixture, problems)
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_names_are_explicit_and_standalone():
    assert recovery.Candidate('record-status-one').gate_pcs == (boundary.RECORD_ONE_ENTRY,)
    assert boundary.RECORD_ONE_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('record-status-one-mutant-register').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='record-status-one', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 00354C within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='record-status-one-mutant-register',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
