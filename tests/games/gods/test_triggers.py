"""The trigger evaluator (00462C): the non-firing arm, the disabled arm (declined, never witnessed),
and, since 19 September, the firing arm too -- the recipe-6a family over the record's own `+0x10`
action word (`docs/gods/blockers/2026-09-16-00462C-firing.md`'s own Resolution).

The non-firing arm composes three already-recovered 00470C calls (the shape 0049DA's calls into
001164 proved): the boundary owns the whole call, 00470C is not a separate gate at this call site.
The firing arm (004688 onward: the message preamble, the two unconditional calls, the action-table
dispatch) composes message_gate_plan/string_copy_plan/record_id_scan_plan/slot_scan_plan and the
recovered action handlers (0048E4, 004ACA, 0048EA, 004A0A, the three 00475C rts entries) by ROM
address; every other real action index, and the rare case where record id scan or slot scan itself
reaches an unmodelled achievement seam, still declines by name.  Three tiers as for the other regions.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import conditions, triggers
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-*00462C*/00462C-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00462C')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_disabled_flag_skips_evaluation_entirely():
    result = triggers.evaluate_record(_reader({}), 0, disable_flag=1)
    assert result == {'arm': 'disabled'}


def test_three_holding_pairs_fire():
    record = {}
    base = triggers.TRIGGER_TABLE & 0xFFFFFF
    for offset, (kind, argument) in zip(triggers.PAIR_OFFSETS, ((0, 0), (0, 0), (0, 0))):
        record[(base + offset, 2)] = kind
        record[(base + offset + 2, 2)] = argument
    result = triggers.evaluate_record(_reader(record), 0, disable_flag=0)
    assert result['arm'] == 'firing' and result['entry'] & 0xFFFFFF == base


def test_one_failing_pair_prevents_firing_and_clears_its_own_slot_only():
    record = {}
    base = triggers.TRIGGER_TABLE & 0xFFFFFF
    markers = {(conditions.MARKERS[i] & 0xFFFFFF, 2): v for i, v in enumerate((1, 2, 3, 4))}
    pairs = ((1, 99), (0, 0), (0, 0))               # kind 1 (any-equal) with an argument that matches nothing: false
    for offset, (kind, argument) in zip(triggers.PAIR_OFFSETS, pairs):
        record[(base + offset, 2)] = kind
        record[(base + offset + 2, 2)] = argument
    result = triggers.evaluate_record(_reader({**record, **markers}), 0, disable_flag=0)
    assert result['arm'] == 'non-firing'
    assert result['stores'] == {0xFFF38C: (0, 2)}    # only the first slot cleared


def test_an_unrecovered_kind_in_any_pair_is_reported_as_unrecovered():
    record = {}
    base = triggers.TRIGGER_TABLE & 0xFFFFFF
    for offset, (kind, argument) in zip(triggers.PAIR_OFFSETS, ((13, 5), (0, 0), (0, 0))):
        record[(base + offset, 2)] = kind
        record[(base + offset + 2, 2)] = argument
    result = triggers.evaluate_record(_reader(record), 0, disable_flag=0)
    assert result['arm'] == 'unrecovered'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_and_declines_the_rest_by_name(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.EVALUATOR_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        read = boundary._reader(machine)
        disable_flag = read(triggers.DISABLE_FLAG & 0xFFFFFF, 2)
        index = read((registers['a0'] + 2) & 0xFFFFFF, 2)
        result = triggers.evaluate_record(read, index, disable_flag)
        if result['arm'] in ('disabled', 'unrecovered'):
            with pytest.raises(boundary.UnsupportedCandidate):
                boundary.evaluator_plan(machine, registers)
            return
        try:
            plan = boundary.evaluator_plan(machine, registers)
        except boundary.UnsupportedCandidate as error:
            # Only the firing arm's own unrecovered action indices (or an achievement seam record
            # id scan/slot scan itself reaches) still decline; non-firing never does.
            assert result['arm'] == 'firing', error
            return
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['interrupts_during_trace'] == 0


@needs_census
def test_a_real_firing_activation_is_composed_not_declined():
    """At least one retained fixture must actually exercise the firing arm's own composition (a
    census-only regression could otherwise hide behind an all-decline pass)."""
    composed = 0
    for fixture in FIXTURES:
        state = fixture.read_bytes()
        with Machine(GODS.read_rom()) as machine:
            machine.restore(state)
            registers = machine.registers()
            read = boundary._reader(machine)
            disable_flag = read(triggers.DISABLE_FLAG & 0xFFFFFF, 2)
            index = read((registers['a0'] + 2) & 0xFFFFFF, 2)
            result = triggers.evaluate_record(read, index, disable_flag)
            if result['arm'] != 'firing':
                continue
            try:
                boundary.evaluator_plan(machine, registers)
            except boundary.UnsupportedCandidate:
                continue
            composed += 1
    assert composed > 0


def test_candidate_names_are_explicit():
    assert recovery.Candidate('evaluator').gate_pcs == (boundary.EVALUATOR_ENTRY,)
    assert boundary.EVALUATOR_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('evaluator-mutant-outcome').mutation is recovery._mutate_outcome


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='evaluator',
                                  reference=EVIDENCE)
    assert report['status'] in ('PASS', 'NOT_EXERCISED'), report
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                  candidate='evaluator-mutant-outcome', reference=EVIDENCE)
    assert mutant['status'] in ('PASS', 'DIVERGENCE', 'NOT_EXERCISED'), mutant
