"""The proximity table search-and-add (00F828/00F86A): 014084's own 'trigger' callee.

00F828 unconditionally calls 00F86A first (the 40-entry search); the
boundary owns the whole call, 00F86A is not a separate gate.  A matching,
still-negative-timer entry (the 'trigger' arm) falls into 00F8A2 -- a
caller-record decrement of the SAME timer word, gated by which of
conditions.py's own TRACKED ids is currently selected -- and returns past
both stack frames at once (a deliberate double return, not a bug); 17
September: recovered (`game.hazard.proximity_trigger`), a bounded leaf
composed into `proximity_plan`, once real fixtures turned up (25 of them)
in a full re-census.  Otherwise 00F828's own scan adds a fresh entry into
the first free slot ('added'), or declines ('pool-full') if none of the
40 is free -- real code too, but unwitnessed.  Three tiers as for the
other regions.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import hazard
from gods_sega.game.grid import GRID_TABLE
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00F828*/00F828-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00F828')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0xFFFF if size == 2 else 0)
    return read


def _empty_table():
    values = {}
    for index in range(hazard.PROXIMITY_COUNT):
        base = (hazard.PROXIMITY_TABLE + hazard.PROXIMITY_STRIDE * index) & 0xFFFFFF
        values[(base, 2)] = 0xFFFF
        values[(base + 2, 2)] = 0
        values[(base + 4, 2)] = 0xFFFF
    return values


def test_an_empty_table_is_not_found_and_adds_into_the_first_slot():
    a1 = GRID_TABLE + 0x100
    search = hazard.proximity_search(_reader(_empty_table()), a1)
    assert search['arm'] == 'not-found'
    assert all(p == 'miss' for p in search['positions'])
    added = hazard.proximity_add(_reader(_empty_table()), search['offset'], search['d4'], search['d5'])
    assert added['arm'] == 'added' and added['index'] == 0
    base = hazard.PROXIMITY_TABLE & 0xFFFFFF
    assert added['stores'][base] == (search['d4'], 2)
    assert added['stores'][base + 4] == (0xFFFF, 2)


def test_a_matching_entry_with_a_negative_timer_is_the_trigger_arm():
    a1 = GRID_TABLE + 0x100
    values = _empty_table()
    offset, d4, d5 = hazard._proximity_key(a1)
    base = hazard.PROXIMITY_TABLE & 0xFFFFFF
    values[(base, 2)] = d4
    values[(base + 2, 2)] = d5 & 0xFFFF
    values[(base + 4, 2)] = 0x8000                  # negative: a fresh, unconsumed entry
    search = hazard.proximity_search(_reader(values), a1)
    assert search['arm'] == 'trigger' and search['index'] == 0


def test_proximity_trigger_bonus_and_floor_clamp():
    entry_base = hazard.PROXIMITY_TABLE
    timer_address = (entry_base + 4) & 0xFFFFFF
    a2 = 0xFFFFF1F8
    values = _empty_table()
    values[(hazard.TRIGGER_SELECTOR & 0xFFFFFF, 2)] = 0        # selects TRACKED[0]
    values[(0xFFEF8C, 2)] = hazard.TRIGGER_BONUS_ID             # active id 0xA: the bonus applies
    values[(timer_address, 2)] = 0xFFF0                          # the matched entry's own timer (-16)
    values[((a2 + 8) & 0xFFFFFF, 2)] = 5                         # a2+8: the caller record's own base decrement
    result = hazard.proximity_trigger(_reader(values), a2=a2, entry_base=entry_base)
    assert result['arm'] == 'trigger-decrement' and result['bonus'] and result['decrement'] == 5 + 0x32
    assert result['cleared'] is False
    assert result['stores'][timer_address] == (result['final'], 2)

    # A decrement that pushes the timer below the floor clears it to 0 instead of wrapping negative.
    values[(timer_address, 2)] = 0xFF00 & 0xFFFF     # -256: 55 more brings it well past the -200 floor
    result = hazard.proximity_trigger(_reader(values), a2=a2, entry_base=entry_base)
    assert result['cleared'] and result['final'] == 0

    # A selector outside 0/1/2 leaves the ROM's own d5 uninitialised: declined, not guessed.
    values[(hazard.TRIGGER_SELECTOR & 0xFFFFFF, 2)] = 3
    result = hazard.proximity_trigger(_reader(values), a2=a2, entry_base=entry_base)
    assert result['arm'] == 'unrecovered'


def test_a_matching_entry_with_a_non_negative_timer_is_stale_and_the_search_continues():
    a1 = GRID_TABLE + 0x100
    values = _empty_table()
    offset, d4, d5 = hazard._proximity_key(a1)
    base = hazard.PROXIMITY_TABLE & 0xFFFFFF
    values[(base, 2)] = d4
    values[(base + 2, 2)] = d5 & 0xFFFF
    values[(base + 4, 2)] = 0x0005                  # already counting down: not a fresh match
    search = hazard.proximity_search(_reader(values), a1)
    assert search['arm'] == 'not-found' and search['positions'][0] == 'stale'


def test_a_full_table_is_pool_full():
    a1 = GRID_TABLE + 0x100
    values = _empty_table()
    for index in range(hazard.PROXIMITY_COUNT):
        base = (hazard.PROXIMITY_TABLE + hazard.PROXIMITY_STRIDE * index) & 0xFFFFFF
        values[(base, 2)] = 0x0001                  # occupied: never matches d4, never free
    search = hazard.proximity_search(_reader(values), a1)
    assert search['arm'] == 'not-found'
    added = hazard.proximity_add(_reader(values), search['offset'], search['d4'], search['d5'])
    assert added['arm'] == 'pool-full'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_arm(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.PROXIMITY_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.proximity_plan(machine, registers)
        except boundary.UnsupportedCandidate:
            return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['interrupts_during_trace'] == 0


def test_candidate_names_are_explicit():
    assert recovery.Candidate('proximity').gate_pcs == (boundary.PROXIMITY_ENTRY,)
    assert boundary.PROXIMITY_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('proximity-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_candidate_matches_the_reference_over_real_frames():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300, candidate='proximity',
                                  reference=EVIDENCE)
    assert report['status'] in ('PASS', 'NOT_EXERCISED'), report
