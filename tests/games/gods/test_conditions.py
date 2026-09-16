"""The trigger conditions (00470C): Gods' first dispatcher, one small predicate per kind.

The evaluator calls it with the kind in D5, the argument in D6 and the
result slot in A3; the kind selects a predicate through a ROM table and
the predicate clears the slot when its condition fails.  One gate, one
planner, the kinds as arms; a kind or a compare position no recording
entered is declined.  Three tiers as for the other regions; the evidence
tiers skip when the local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import conditions
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00470C*/00470C-*-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00470C')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

SLOT = 0xFFFFF38C


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_the_membership_kinds_report_the_matching_position_and_clear_on_the_opposite_outcome():
    markers = {(conditions.MARKERS[i], 2): value for i, value in enumerate((0x11, 0x22, 0x33, 0x44))}
    any_equal = conditions.evaluate(_reader(markers), 1, 0x33, SLOT)
    assert (any_equal['arm'], any_equal['matched'], any_equal['stores']) == ('true', 2, {})
    none_equal = conditions.evaluate(_reader(markers), 2, 0x33, SLOT)
    assert (none_equal['arm'], none_equal['stores']) == ('false', {0xFFF38C: (0, 2)})
    assert conditions.evaluate(_reader(markers), 1, 0x99, SLOT)['arm'] == 'false'
    assert conditions.evaluate(_reader(markers), 2, 0x99, SLOT) == {**conditions.evaluate(_reader(markers), 2, 0x99, SLOT), 'arm': 'true'}
    tracked = {(conditions.TRACKED[1], 2): 0x0007}
    assert conditions.evaluate(_reader(tracked), 3, 7, SLOT)['matched'] == 1
    assert conditions.evaluate(_reader(tracked), 4, 7, SLOT)['arm'] == 'false'
    assert all(conditions.evaluate(_reader({}), kind, 0, SLOT)['handler'] == conditions.HANDLERS[kind] for kind in range(conditions.KINDS))


def test_the_table_progress_elapsed_and_flagged_kinds():
    status = {(0xFF502A + 4 * 2, 2): 0x8001}                   # argument 3: the third word, negative
    assert conditions.evaluate(_reader(status), 5, 3, SLOT)['arm'] == 'true'
    assert conditions.evaluate(_reader(status), 6, 3, SLOT)['arm'] == 'false'
    assert conditions.evaluate(_reader(status), 5, 3, SLOT)['entry'] == 0xFFFF5032
    progress = {(conditions.PROGRESS_A, 2): 0x0100, (conditions.PROGRESS_B, 2): 0xFFF0}
    assert conditions.evaluate(_reader(progress), 7, 0x00FF, SLOT)['arm'] == 'true'     # below A
    assert conditions.evaluate(_reader(progress), 8, 0x00FF, SLOT)['arm'] == 'false'
    assert conditions.evaluate(_reader(progress), 15, 0x0000, SLOT)['arm'] == 'false'   # -16 is below 0, not above
    assert conditions.evaluate(_reader(progress), 16, 0x0000, SLOT)['arm'] == 'true'
    elapsed = {(conditions.ELAPSED, 4): 0x0000_0BB9, (conditions.RATE, 2): 60}         # 3001 // 60 = 50 seconds, remainder 1
    nine = conditions.evaluate(_reader(elapsed), 9, 9, SLOT)                            # 45 < 50
    assert (nine['arm'], nine['quotient'], nine['scaled'], nine['remainder']) == ('true', 50, 45, 1)
    assert conditions.evaluate(_reader(elapsed), 10, 9, SLOT)['arm'] == 'false'
    assert conditions.evaluate(_reader({**elapsed, (conditions.RATE, 2): 0}), 9, 9, SLOT)['arm'] == 'unrecovered'
    flagged = {(0xFF62F6 + 6 * 4 + 5, 1): 0x01}
    eleven = conditions.evaluate(_reader(flagged), 11, 4, SLOT)
    assert (eleven['arm'], eleven['entry'], eleven['scaled']) == ('true', 0xFFFF630E, 16)
    assert conditions.evaluate(_reader(flagged), 12, 4, SLOT)['arm'] == 'false'
    assert conditions.evaluate(_reader({}), 0, 5, SLOT)['arm'] == 'none'
    assert conditions.evaluate(_reader({}), 13, 5, SLOT)['arm'] == 'unrecovered'
    assert conditions.evaluate(_reader({}), 17, 5, SLOT)['arm'] == 'unrecovered'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.CONDITION_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.condition_plan(machine, machine.registers())
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_census
def test_unwitnessed_kinds_and_positions_are_declined():
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.CONDITION_ENTRY
        for kind, message in ((4, 'compare position not witnessed|not witnessed'), (13, 'not recovered'), (14, 'not recovered'),
                              (17, 'not recovered')):
            with pytest.raises(boundary.UnsupportedCandidate, match=message):
                boundary.condition_plan(machine, {**registers, 'd5': kind})
        # Kind 2 matching on the second marker: a compare position no recording entered.
        second = int.from_bytes(machine.peek_ram(conditions.MARKERS[1] & 0xFFFF, 2), 'big')
        first = int.from_bytes(machine.peek_ram(conditions.MARKERS[0] & 0xFFFF, 2), 'big')
        if second != first:
            with pytest.raises(boundary.UnsupportedCandidate, match='compare position not witnessed'):
                boundary.condition_plan(machine, {**registers, 'd5': 2, 'd6': second})


def test_candidate_names_are_explicit():
    assert recovery.Candidate('conditions').gate_pcs == (boundary.CONDITION_ENTRY,)
    assert boundary.CONDITION_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('conditions-mutant-outcome').mutation is recovery._mutate_outcome


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300, candidate='conditions',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] > 50 and set(report['fallback_reasons']) <= {'scheduler admission'}
    # A register mutant is blind here (the residue is dead, a non-negative slot still reads as false):
    # the control that reaches the game is a false outcome reported as true.
    flipped = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                   candidate='conditions-mutant-outcome', reference=EVIDENCE)
    assert flipped['status'] == 'DIVERGENCE', flipped
