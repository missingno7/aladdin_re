"""The achievement/collectible-slot reset (0047DA): a platform tail via bsr into the collected-item
icon upload (001648), Aladdin's "one native call inside the branch" shape reproduced with Gods' own
device convention.  0047DA always calls 001648 with D2=-1 (the icon upload's own 'clear' arm); D0
selects one of 001648's own four VRAM icon slots (0, 1 and 3 witnessed; 2 declined).
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import achievements
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0047DA-fresh-*/0047DA-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0047DA')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def test_marks_the_matching_slot_empty_and_defaults_to_the_ffffffff_fill():
    result = achievements.achievement_slot_reset(_reader({(achievements.HIGHLIGHT_ID, 2): 5}), 1)
    assert result['slot'] == 1
    assert result['stores'] == {(achievements.ACHIEVEMENT_SLOTS + 2) & 0xFFFFFF: (0xFFFF, 2)}
    assert not result['highlighted'] and result['icon_d1'] == 0 and result['icon_d2'] == 0xFFFF


def test_a_matching_highlight_id_selects_the_dddddddd_fill():
    result = achievements.achievement_slot_reset(_reader({(achievements.HIGHLIGHT_ID, 2): 3}), 3)
    assert result['highlighted'] and result['icon_d1'] == 1
    assert result['stores'] == {(achievements.ACHIEVEMENT_SLOTS + 6) & 0xFFFFFF: (0xFFFF, 2)}


def _check_seam(seam, state):
    """The strict witness of a seam: the prefix to the platform entry, the suffix from the resume."""
    facts = pathfacts.trace(state, game=GODS, stop_pc=seam.prefix.registers['pc'])
    problems = [p for p in pathfacts.check_plan(seam.prefix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('prefix', problems)
    resumed = pathfacts.park(state, seam.resume_pc, game=GODS)
    with Machine(GODS.read_rom()) as machine:
        machine.restore(resumed)
        registers = machine.registers()
        assert registers['a7'] == seam.stack_basis
        suffix = seam.suffix(machine, registers)
    facts = pathfacts.trace(resumed, game=GODS, stop_pc=suffix.registers['pc'])
    problems = [p for p in pathfacts.check_plan(suffix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('suffix', problems)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_icon_slot(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.ACHIEVEMENT_SLOT_RESET_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.achievement_slot_reset_plan(machine, registers)
        except boundary.UnsupportedCandidate:
            return
    assert isinstance(plan, boundary.Seam)
    _check_seam(plan, state)


def test_witnessed_icon_slots_exclude_2():
    # D0=2 is real ROM code (the table at 0016C2 has four entries) but no recording ever calls 0047DA
    # with it: every witnessed occurrence uses 0, 1 or 3.
    assert achievements.WITNESSED_ICON_SLOTS == (0, 1, 3)


@needs_census
def test_pickup_check_plan_declines_an_unwitnessed_icon_slot():
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        pc = machine.info['pc']
        machine.gates([pc])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        # Force D0 to the one table slot no recording ever reaches (2): must decline, not silently admit.
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=pc,
                              writes=[], registers={**registers, 'd0': (registers['d0'] & 0xFFFF0000) | 2})
        with pytest.raises(boundary.UnsupportedCandidate, match='icon slot'):
            boundary.achievement_slot_reset_plan(machine, machine.registers())


def test_candidate_names_are_explicit():
    assert recovery.Candidate('achievement-slot-reset').gate_pcs == (boundary.ACHIEVEMENT_SLOT_RESET_ENTRY,)
    assert boundary.ACHIEVEMENT_SLOT_RESET_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('achievement-slot-reset-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='achievement-slot-reset', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('achievement-slot-reset never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='achievement-slot-reset-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'


# --- 004790: the slot dispatch (game/achievements.py: achievement_slot_dispatch) -----------------
#
# A caller-supplied record pointer's own tracked id, gated by a shared per-id status word (only 2 is
# witnessed) then checked against 0047DA's own four ids.  A miss is a plain leaf; a match is a
# platform tail one level up from achievement_slot_reset_plan -- the whole of 0047DA (itself a seam
# over 001648) is one opaque ceded block to this composition.

DISPATCH_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-004790-fresh-*/004790-entry-*.state'))
needs_dispatch_census = pytest.mark.skipif(not DISPATCH_FIXTURES or not GODS.rom_path.is_file(),
                                           reason='no local census of 004790')


def test_a_witnessed_status_with_no_matching_id_is_a_plain_miss():
    world = {(achievements.RECORD_TABLE & 0xFFFFFF, 2): 5}  # a2 -> tracked id 5
    world[((achievements.RECORD_TABLE + achievements.RECORD_STRIDE * 5 + 4) & 0xFFFFFF, 2)] = 2  # status
    for address in achievements.TRACKED_IDS:
        world[(address, 2)] = 999   # none of the four tracked ids is 5
    result = achievements.achievement_slot_dispatch(_reader(world), achievements.RECORD_TABLE)
    assert result == {'arm': 'no-match', 'tracked': 5, 'record': result['record'], 'status': 2, 'match': None}


def test_a_matching_tracked_id_names_its_own_slot():
    tracked = 7
    world = {(achievements.RECORD_TABLE & 0xFFFFFF, 2): tracked}
    world[((achievements.RECORD_TABLE + achievements.RECORD_STRIDE * tracked + 4) & 0xFFFFFF, 2)] = 2
    world[(achievements.TRACKED_IDS[2], 2)] = tracked
    result = achievements.achievement_slot_dispatch(_reader(world), achievements.RECORD_TABLE)
    assert result['arm'] == 'match' and result['match'] == 2


def test_an_unwitnessed_status_is_blocked():
    world = {(achievements.RECORD_TABLE & 0xFFFFFF, 2): 0}
    world[((achievements.RECORD_TABLE + 4) & 0xFFFFFF, 2)] = 1   # neither 0 nor 2
    result = achievements.achievement_slot_dispatch(_reader(world), achievements.RECORD_TABLE)
    assert result['arm'] == 'blocked'
    assert 1 not in achievements.WITNESSED_STATUS


@needs_dispatch_census
@pytest.mark.parametrize('fixture', DISPATCH_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_dispatch_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_status(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.ACHIEVEMENT_DISPATCH_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.achievement_slot_dispatch_plan(machine, registers)
        except boundary.UnsupportedCandidate:
            return
    if isinstance(plan, boundary.Seam):
        _check_seam(plan, state)
        return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_dispatch_candidate_names_are_explicit():
    assert recovery.Candidate('achievement-slot-dispatch').gate_pcs == (boundary.ACHIEVEMENT_DISPATCH_ENTRY,)
    assert boundary.ACHIEVEMENT_DISPATCH_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('achievement-slot-dispatch-mutant-result').mutation is recovery._mutate_register


@needs_reference
def test_dispatch_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='achievement-slot-dispatch', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('achievement-slot-dispatch never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='achievement-slot-dispatch-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
