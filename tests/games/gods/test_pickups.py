"""The pickup award (013264): the value of a collected item, its cue and the consumed slot.

The blocker package of 16 September read this routine as a per-type
dispatch; the table at 012D04 is a table of item *records*, not handlers,
and the routine is a RAM-only leaf over the pickup code A0 points past.
Three tiers as for the other regions; the evidence tiers skip when the
local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import pickups
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-013264*/013264-*-p*.state'))
REFERENCE_FIXTURES = sorted(Path('artifacts/gods/evidence/census-013264-f0ac19738f19').glob('013264-*-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 013264')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not REFERENCE_FIXTURES
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

GRID_CELL = 0xFFBCDA
RECORD = 0xFFF5F2


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def _world(code, active=2, value=6, now=0x22, mark=0x17, sound=0, consume=1):
    return {(GRID_CELL - 1, 1): code & 0xFF, (pickups.GROUP_TABLES[2] & 0xFFFFFF, 2): active,
            (pickups.ITEM_RECORDS + 4 * active, 4): 0xFFFF0000 | RECORD, (RECORD + pickups.ITEM_VALUE, 2): value,
            (RECORD + pickups.ITEM_CONSUMES_SLOT, 1): consume, (pickups.TIME_NOW, 2): now, (pickups.TIME_MARK, 2): mark,
            (pickups.SOUND_ON, 2): sound, (pickups.SPECIAL_VALUE, 2): 0x0123}


def test_an_item_code_ranges_into_its_group_awards_the_record_value_with_the_time_bonus_and_consumes_the_slot():
    result = pickups.collect(_reader(_world(19)), GRID_CELL)
    assert (result['arm'], result['code'], result['group'], result['slot'], result['active']) == ('item', 19, 2, 0, 2)
    assert result['record'] == 0xFFFFF5F2 and result['time_difference'] == 0xB and result['bonus']
    assert result['stores'] == {pickups.AWARD: (7, 2), 0xFFF0B2: (0, 2)} and result['consumed'] and not result['cue']
    plain = pickups.collect(_reader(_world(19, now=5, mark=9, sound=1, consume=0)), GRID_CELL)
    assert plain['stores'] == {pickups.AWARD: (6, 2), pickups.SOUND_CUE: (pickups.PICKUP_CUE, 2)}
    assert plain['cue'] and not plain['bonus'] and not plain['consumed'] and plain['time_difference'] == -4
    assert pickups.collect(_reader(_world(1)), GRID_CELL)['group'] == 0
    assert pickups.collect(_reader(_world(10)), GRID_CELL)['group'] == 1 and pickups.collect(_reader(_world(10)), GRID_CELL)['slot'] == 0


def test_the_special_codes_and_the_unrecovered_continuation():
    minus_one = pickups.collect(_reader(_world(-1)), GRID_CELL)
    assert (minus_one['arm'], minus_one['d4'], minus_one['stores']) == ('special-1', 1, {pickups.AWARD: (0x0123, 2)})
    assert pickups.collect(_reader(_world(-2)), GRID_CELL)['stores'] == {pickups.AWARD: (pickups.BIG_VALUE, 2)}
    assert pickups.collect(_reader(_world(-2, sound=1)), GRID_CELL)['stores'] == {pickups.AWARD: (0, 2)}
    assert pickups.collect(_reader(_world(-3)), GRID_CELL)['stores'] == {pickups.AWARD: (0, 2)}
    assert pickups.collect(_reader(_world(-4)), GRID_CELL)['arm'] == 'unrecovered'
    assert pickups.collect(_reader(_world(-100)), GRID_CELL)['arm'] == 'unrecovered'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path_or_declines_the_continuation(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.PICKUP_AWARD_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        code = machine.peek_ram((registers['a0'] - 1) & 0xFFFF, 1)[0]
        try:
            plan = boundary.pickup_award_plan(machine, registers)
        except boundary.UnsupportedCandidate as declined:
            assert code >= 0x80 and code - 0x100 <= -4, (code, str(declined))
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_census
def test_the_continuation_code_is_now_admitted_via_the_grid_inverse_composition():
    # 013316 (the grid inverse + debris burst 013264's own -4-and-below cascade falls into) is
    # recovered: every retained code -4 fixture reaches its witnessed 'debris' arm and is admitted,
    # not declined -- see tests/games/gods/test_pickup_check.py for 013316's own coverage.
    found = False
    for fixture in FIXTURES:
        with Machine(GODS.read_rom()) as machine:
            machine.restore(fixture.read_bytes())
            registers = machine.registers()
            code = machine.peek_ram((registers['a0'] - 1) & 0xFFFF, 1)[0]
            if code < 0x80 or code - 0x100 > -4:
                continue
            found = True
            machine.gates([registers['pc']])
            candidate = recovery.Candidate('pickups')
            candidate.arm(machine)
            assert machine.run(instructions=1) == 'gate'
            # A long activation (up to ~370 instructions) can straddle an interrupt boundary: the
            # scheduler's own admission refusal is exact (the original runs it), not a decline.
            admitted = candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
            if not admitted:
                assert set(candidate.stats['fallback_reasons']) <= {'scheduler admission'}
                continue
            assert candidate.stats['candidate_hits'] == 1 and candidate.stats['fallbacks'] == 0
    if not found:
        pytest.skip('no retained fixture carries a continuation code')


def test_candidate_names_are_explicit():
    assert recovery.Candidate('pickups').gate_pcs == (boundary.PICKUP_AWARD_ENTRY,)
    assert boundary.PICKUP_AWARD_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('pickups-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_from_a_retained_pickup_and_its_mutant_diverges():
    fixture = REFERENCE_FIXTURES[0]
    report = segment_verify.check(fixture, game=GODS, frames=120, candidate='pickups', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] >= 1 and set(report['fallback_reasons']) <= {'scheduler admission'}
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='pickups-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE' and mutant['first_difference']['frame'] == report['from_frame'] + 1
