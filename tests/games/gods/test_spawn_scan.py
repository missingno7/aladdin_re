"""004926: the box-scan puff spawner (`docs/gods/blockers/2026-09-16-00462C-firing.md`'s Split part 3
first bite; `docs/gods/grinder-protocol.md`'s "where to work" order).  Reached from two real callers
(0048EA, the trigger evaluator's firing-arm action table, and a second one at 0139D2 inside the
collectible-lists subsystem) -- neither recovered, so this leaf is verified stand-alone, over every
retained fixture across all five recordings.  Three tiers as for the other leaves; the evidence tiers
skip when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import achievements, movement, spawn_queue, spawn_scan
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X004926-*/004926-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 004926')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0xFFFF if size == 2 else 0)
    return read


def _record(status):
    return {(achievements.RECORD_TABLE + 4) & 0xFFFFFF: status}


def test_find_spawn_slot_stops_at_the_first_negative_counter():
    def read(address, size):
        index = (address - spawn_queue.SLOT_BASE) // spawn_queue.SLOT_SIZE
        return (-1, 0, 0, 0)[index] & 0xFFFF
    result = spawn_scan.find_spawn_slot(read)
    assert result == {'index': 0, 'checked': 1, 'exhausted': False}

    def read_one_occupied(address, size):
        index = (address - spawn_queue.SLOT_BASE) // spawn_queue.SLOT_SIZE
        return (0, -1, 0, 0)[index] & 0xFFFF
    assert spawn_scan.find_spawn_slot(read_one_occupied) == {'index': 1, 'checked': 2, 'exhausted': False}

    def read_all_occupied(address, size):
        return 0
    assert spawn_scan.find_spawn_slot(read_all_occupied) == {'index': 3, 'checked': 4, 'exhausted': True}


def test_scan_finds_a_record_inside_the_box_and_declines_nothing_it_does_not_witness():
    values = {}

    def read(address, size):
        address &= 0xFFFFFF
        if (address, size) in values:
            return values[(address, size)]
        return 0xFFFF if size == 2 else 0

    entry_addr = movement.BOX_SCAN_TABLE & 0xFFFFFF
    values[(entry_addr, 2)] = 0x0010          # x
    values[(entry_addr + 2, 2)] = 0x0020      # y
    values[(entry_addr + 4, 2)] = 0x0005      # header (non-negative, index 5)
    record_addr = achievements._record_address(0x0005)
    values[((record_addr + 4) & 0xFFFFFF, 2)] = spawn_scan.RECORD_MATCH_STATUS
    result = spawn_scan.scan_and_spawn(read, x_min=0, y_min=0, x_max=0x100, y_max=0x100)
    assert result['end_index'] == movement.BOX_SCAN_COUNT
    assert len(result['consumed']) == 1
    match = result['consumed'][0]
    assert match['index'] == 0 and match['queued_x'] == (0x0010 - spawn_scan.X_ADJUST) & 0xFFFF
    assert match['queued_y'] == 0x0020 and match['special'] is False
    assert result['last_active'] == 0x0005
    assert result['last_status_match'] == (match['queued_x'], 0x0020)


def test_a_record_outside_the_box_is_a_miss_not_a_consume():
    values = {}

    def read(address, size):
        address &= 0xFFFFFF
        return values.get((address, size), 0xFFFF if size == 2 else 0)

    entry_addr = movement.BOX_SCAN_TABLE & 0xFFFFFF
    values[(entry_addr, 2)] = 0x0500           # x far outside the box
    values[(entry_addr + 2, 2)] = 0x0020
    values[(entry_addr + 4, 2)] = 0x0007
    record_addr = achievements._record_address(0x0007)
    values[((record_addr + 4) & 0xFFFFFF, 2)] = spawn_scan.RECORD_MATCH_STATUS
    result = spawn_scan.scan_and_spawn(read, x_min=0, y_min=0, x_max=0x100, y_max=0x100)
    assert result['consumed'] == []
    assert result['entries'][0]['arm'] == 'box-miss-x-max'
    assert result['last_status_match'] == (0x0500, 0x0020)   # raw, never adjusted on a miss


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.SPAWN_SCAN_ENTRY
        plan = boundary.spawn_scan_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_census
def test_a_second_consume_in_one_activation_is_declined():
    # None of the retained fixtures ever finds two records in the same activation (the scan's own
    # early-exit-at-two-matches path, 0049D4, is real ROM no recording has reached): confirm the
    # planner declines it by name rather than guessing the early-exit cost/registers.
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        read = boundary._reader(machine)
        result = spawn_scan.scan_and_spawn(read, registers['d0'], registers['d1'], registers['d2'], registers['d3'])
        assert len(result['consumed']) <= 1   # every witnessed fixture: 0 or 1
    # A synthetic two-consume scan (an overly generous box) is declined regardless.
    def read_two(address, size):
        address &= 0xFFFFFF
        table = {}
        # two live, matching, in-box entries at index 0 and 1
        for i, header in ((0, 1), (1, 2)):
            base = (movement.BOX_SCAN_TABLE + movement.BOX_SCAN_STRIDE * i) & 0xFFFFFF
            table[(base, 2)] = 0x10
            table[(base + 2, 2)] = 0x10
            table[(base + 4, 2)] = header
            record = achievements._record_address(header)
            table[((record + 4) & 0xFFFFFF, 2)] = spawn_scan.RECORD_MATCH_STATUS
        return table.get((address, size), 0xFFFF if size == 2 else 0)
    from gods_sega.game import spawn_queue as sq
    def read_slot_free(address, size):
        if sq.SLOT_BASE <= address < sq.SLOT_BASE + sq.SLOT_SIZE * sq.SLOT_COUNT:
            return 0xFFFF
        return read_two(address, size)
    result = spawn_scan.scan_and_spawn(read_slot_free, 0, 0, 0x100, 0x100)
    assert len(result['consumed']) == 2


def test_candidate_name_is_explicit():
    assert recovery.Candidate('spawn-scan').gate_pcs == (boundary.SPAWN_SCAN_ENTRY,)
    assert boundary.SPAWN_SCAN_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('spawn-scan-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_spawn_scan_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='spawn-scan', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 004926 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='spawn-scan-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
