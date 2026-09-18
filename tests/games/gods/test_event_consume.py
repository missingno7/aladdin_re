"""00A922: the creature update's own third unconditional callee (00A772's own tail's tail), the
world-event consume.  Two loops: the first walks the event list (EVENT_LIST, stride 6) looking for
a slot whose own kind passes the type's own QUADRANT_WORD mask, isn't EVENT_KIND_EXCLUDED, and whose
own (x, y) falls inside the creature's own box; the second, on a match, walks
game.movement.BOX_SCAN_TABLE backwards for an active object of the SAME (x, y, kind), and on a match
stores the event into the instance and marks both slots consumed.  Every register the routine ever
writes is a WORD op (d2/d6/d7's own upper halves all survive from entry; d3/d4 are freshly loaded
each time they're written).  See game/creatures.py's own module note above event_consume and
boundary.py's own note above event_consume_plan/_ec_walk_loop1/_ec_loop2_entry_cost.  Three tiers as
for the other leaves; the evidence tiers skip when the local census or reference artifacts are
absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import creatures
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00A922-*/00A922-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00A922')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_mode_inactive_is_declined_by_semantics():
    values = {(creatures.EVENT_MODE & 0xFFFFFF, 2): 0}
    result = creatures.event_consume(_reader(values), 0x100, 0x200)
    assert result['arm'] == 'mode-inactive'


def test_no_events_is_declined_by_semantics():
    values = {(creatures.EVENT_MODE & 0xFFFFFF, 2): 2, (creatures.EVENT_COUNT & 0xFFFFFF, 2): 0}
    result = creatures.event_consume(_reader(values), 0x100, 0x200)
    assert result['arm'] == 'no-events'


def test_already_has_event_is_declined_by_semantics():
    values = {(creatures.EVENT_MODE & 0xFFFFFF, 2): 2, (creatures.EVENT_COUNT & 0xFFFFFF, 2): 3,
              ((0x200 + creatures.EVENT_KIND) & 0xFFFFFF, 2): 5}
    result = creatures.event_consume(_reader(values), 0x100, 0x200)
    assert result['arm'] == 'already-has-event'


def test_count_clamped_is_declined_by_semantics():
    values = {(creatures.EVENT_MODE & 0xFFFFFF, 2): 2, (creatures.EVENT_COUNT & 0xFFFFFF, 2): 0x15,
              ((0x200 + creatures.EVENT_KIND) & 0xFFFFFF, 2): 0xFFFF}
    result = creatures.event_consume(_reader(values), 0x100, 0x200)
    assert result['arm'] == 'count-clamped'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.event_consume_plan(machine, registers)
        except UnsupportedCandidate as error:
            # the count-clamp and object-search-exhaustion/skip-negative/skip-y arms are real ROM,
            # never witnessed by any recording -- the caller declines them, per game/creatures.py's
            # own module note above event_consume.
            assert 'event consume' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('event-consume').gate_pcs == (boundary.EVENT_CONSUME_ENTRY,)
    assert boundary.EVENT_CONSUME_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('event-consume-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_event_consume_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    # most fixtures only ever exercise a decline arm (no stores), where _mutate_result is a no-op
    # (nothing to corrupt) and the mutant trivially PASSes; the search wants one that reaches the
    # 'found' arm's own stores within the window, so the mutant's corrupted byte is actually read
    # back and diverges.
    match = None
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='event-consume', reference=EVIDENCE)
        if report['candidate_hits'] < 1:
            continue
        mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='event-consume-mutant-result',
                                      reference=EVIDENCE)
        if mutant['status'] == 'DIVERGENCE':
            match = (report, mutant)
            break
    if match is None:
        pytest.skip('no retained fixture reaches 00A922\'s own found arm within 120 frames')
    report, mutant = match
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    assert mutant['status'] == 'DIVERGENCE'
