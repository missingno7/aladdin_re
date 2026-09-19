"""002F2E: the effect queue append (`docs/gods/blockers/2026-09-19-003480.md`'s own "pool shape" bite,
recovered independently of 003480 -- still unrecovered). A 10-slot, 10-byte-stride queue: QUEUE_GATE
zero skips the scan and writes slot 0 directly; otherwise the ten slots are scanned in order for the
first free one (negative first word). Three tiers as for the other leaves; the evidence tiers skip
when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import world
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X002F2E-*/002F2E-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 002F2E')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_a_zero_gate_writes_slot_zero_with_no_scan():
    result = world.queue_append(_reader({(world.QUEUE_GATE & 0xFFFFFF, 2): 0}), 0x50, 0x80, 3)
    assert result['arm'] == 'direct' and result['slot'] == world.QUEUE_BASE
    base = world.QUEUE_BASE & 0xFFFFFF
    assert result['stores'][base] == (0x50, 2) and result['stores'][(base + 4) & 0xFFFFFF] == (3, 2)
    assert result['stores'][(base + 6) & 0xFFFFFF] == (world.QUEUE_LIFETIME, 2)
    assert result['stores'][world.QUEUE_GATE & 0xFFFFFF] == (1, 2)


def test_a_nonzero_gate_scans_for_the_first_free_slot():
    values = {(world.QUEUE_GATE & 0xFFFFFF, 2): 1}
    base = world.QUEUE_BASE & 0xFFFFFF
    for index in range(world.QUEUE_SLOT_COUNT):
        values[(base + world.QUEUE_SLOT_STRIDE * index, 2)] = 5 if index < 3 else 0xFFFF   # occupied, then free
    result = world.queue_append(_reader(values), 1, 2, 3)
    assert result['arm'] == 'found' and result['depth'] == 3
    assert result['slot'] == world.QUEUE_BASE + world.QUEUE_SLOT_STRIDE * 3


def test_every_slot_occupied_is_declined_not_guessed():
    values = {(world.QUEUE_GATE & 0xFFFFFF, 2): 1}
    base = world.QUEUE_BASE & 0xFFFFFF
    for index in range(world.QUEUE_SLOT_COUNT):
        values[(base + world.QUEUE_SLOT_STRIDE * index, 2)] = 5
    result = world.queue_append(_reader(values), 1, 2, 3)
    assert result['arm'] == 'full' and result['slot'] is None


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.QUEUE_APPEND_ENTRY
        plan = boundary.queue_append_plan(machine, registers)
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_a_full_queue_declines_when_synthesized():
    # None of the retained fixtures ever exhausts the queue; confirm the planner declines rather than
    # guesses if the machine were ever parked with every slot occupied -- the same RAM-poke technique
    # test_spawn_puff_box.py's own unwitnessed-substitution test uses.
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        pc = registers['pc']
        assert pc == boundary.QUEUE_APPEND_ENTRY
        machine.gates([pc])
        assert machine.run(instructions=1) == 'gate'
        writes = []
        for index in range(world.QUEUE_SLOT_COUNT):
            writes.extend(boundary._bytes((world.QUEUE_BASE + world.QUEUE_SLOT_STRIDE * index) & 0xFFFFFF, 5, 2))
        writes.extend(boundary._bytes(world.QUEUE_GATE & 0xFFFFFF, 1, 2))
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=pc,
                              writes=writes, registers=machine.registers())
        with pytest.raises(UnsupportedCandidate, match='occupied'):
            boundary.queue_append_plan(machine, machine.registers())


def test_candidate_name_is_explicit():
    assert recovery.Candidate('queue-append').gate_pcs == (boundary.QUEUE_APPEND_ENTRY,)
    assert boundary.QUEUE_APPEND_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('queue-append-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_queue_append_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='queue-append', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches 002F2E within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='queue-append-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
