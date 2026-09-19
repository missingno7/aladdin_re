"""The object-kind dispatch (0036E2): a seam opaque over its own table-matched handler.

Reached from inside 003284's own body (the achievements-record status > 4
arm) by a plain branch, not a bsr, and exits via `bra.w $3158` back into
0030CC's own 200-entry scan loop, not an rts -- verified directly
(`factcheck facts --park 0x36E2 --stop 0x3158`) since the standard census
tooling cannot classify this gate (it is not itself a call boundary).  Of
the thirteen `0x00370E` table entries, only kind 0x51 (-> 0037A0) is
witnessed reaching this gate; everything else declines by name.  Three
tiers as for the other leaves; the fixtures here are materialized by
advancing retained `003186` census fixtures to `0x36E2` (`pathfacts.park`),
since `recovery_census.py`'s own default classifier cannot itself retain a
fixture at a mid-function jump target.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import world
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0X0036E2-*/0036E2-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0036E2')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values[(address, size)]
    return read


def test_noop_kind_makes_no_call_at_all():
    values = {(world.KIND_TABLE, 2): 0x51}
    result = world.classify_object_kind(_reader(values), world.NOOP_KIND)
    assert result['arm'] == 'noop'


def test_a_matched_kind_reads_its_own_handler_from_the_table_directly():
    values = {}
    for index in range(world.KIND_TABLE_COUNT):
        base = world.KIND_TABLE + 6 * index
        values[(base, 2)] = 0x1000 + index
        values[(base + 2, 4)] = 0x100000 + index
    result = world.classify_object_kind(_reader(values), 0x1005)
    assert result['arm'] == 'dispatch' and result['mismatches'] == 5 and result['handler'] == 0x100005


def test_an_unmatched_kind_falls_back_to_the_tile_painter():
    values = {}
    for index in range(world.KIND_TABLE_COUNT):
        base = world.KIND_TABLE + 6 * index
        values[(base, 2)] = 0x2000 + index
        values[(base + 2, 4)] = 0
    result = world.classify_object_kind(_reader(values), 0x9999)
    assert result['arm'] == 'fallback' and result['handler'] == world.FALLBACK_HANDLER == boundary.OBJECT_TILE_ENTRY


def _check_seam(seam, state):
    """The strict witness of a seam: the prefix up to the ceded handler, the suffix from the resume."""
    facts = pathfacts.trace(state, game=GODS, stop_pc=seam.prefix.registers['pc'])
    problems = [p for p in pathfacts.check_plan(seam.prefix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('prefix', problems)
    resumed = pathfacts.park(state, seam.resume_pc, game=GODS)
    with Machine(GODS.read_rom()) as machine:
        machine.restore(resumed)
        registers = machine.registers()
        assert registers['a7'] == seam.stack_basis
        suffix = seam.suffix(machine, registers)
    facts = pathfacts.trace(resumed, game=GODS, stop_pc=boundary.OBJECT_KIND_SCAN_LOOP)
    problems = [p for p in pathfacts.check_plan(suffix, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], ('suffix', problems)


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.OBJECT_KIND_DISPATCH_ENTRY
        plan = boundary.object_kind_dispatch_plan(machine, registers)
    if isinstance(plan, boundary.Seam):
        _check_seam(plan, state)
        return
    facts = pathfacts.trace(state, game=GODS, stop_pc=boundary.OBJECT_KIND_SCAN_LOOP)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems


def test_candidate_names_are_explicit():
    assert recovery.Candidate('object-kind-dispatch').gate_pcs == (boundary.OBJECT_KIND_DISPATCH_ENTRY,)
    assert boundary.OBJECT_KIND_DISPATCH_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('object-kind-dispatch-mutant-register').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                  candidate='object-kind-dispatch', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('object-kind-dispatch never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                  candidate='object-kind-dispatch-mutant-register', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
