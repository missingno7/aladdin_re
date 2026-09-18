"""State 19 (005886): a shared multi-part region with state 18, per docs/gods/blockers/
2026-09-18-005886.md's own ten real terminal shapes (all witnessed).  States 18 and 19 are "one
region, two gates" (states 4/15, 5/1, 6/0's own shape): not byte-identical heads, but branching into
the SAME physical downstream code -- the FFFFEA1E==1 small dispatch and the bsr into the achievement
highlight cycle (game.achievements.achievement_highlight_cycle, states 19/18's own 005CEE) both land
on identical addresses either way.  The scan (0058D2-005954) is a second, separately-compiled copy
of game.movement.box_overlap_scan's own algorithm (00722C), consumed here unlike its own twin's two
witnessed call sites (states 0/1).  Two seam shapes: the box-scan-consume "consumed" arm (a single
jsr 001648) and the highlight cycle (a seam over a seam, cede the whole 005CEE activation, per
achievement_slot_dispatch's own shape over 0047DA) with its own "run of platform calls" idle-cycle
arm (two chained jsr 001648, never re-gated in between).  Three tiers as for the other leaves; the
evidence tiers skip when the local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine, NativeError
from genesis_re.seam import Seam, UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import achievements, movement, player, spawns
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-005886-*/005886-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 005886')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


# --- semantics: game.player.state1918_scan_consume / state1918_dispatch / state19_head -----------

def test_scan_not_found_sets_the_empty_latch():
    values = {}
    result = player.state1918_scan_consume(_reader(values))
    assert result['arm'] == 'not-found'
    assert result['stores'] == {player.SCAN_EMPTY & 0xFFFFFF: (1, 2)}


def test_scan_found_kind_two_rearms_when_both_bits_clear():
    entry = movement.BOX_SCAN_TABLE & 0xFFFFFF
    values = {(0xFFF18C, 2): 0, (0xFFF18E, 2): 0,
              (entry + 4, 2): 2, (entry + 6, 2): 1, (entry, 2): 0x10, (entry + 2, 2): 0x28,
              ((player.PROXIMITY_KIND_TABLE + 2) & 0xFFFFFF, 1): player.PROXIMITY_KIND_CONSUME,
              (player.EA23_WORD & 0xFFFFFF, 1): 0}
    result = player.state1918_scan_consume(_reader(values))
    assert result['arm'] == 'rearmed'
    assert result['stores'] == {(entry + 4) & 0xFFFFFF: (2, 2), (entry + 6) & 0xFFFFFF: (1, 2),
                                player.SCAN_ACTIVE & 0xFFFFFF: (0, 2)}


def test_scan_found_kind_two_consumes_when_a_bit_is_set():
    entry = movement.BOX_SCAN_TABLE & 0xFFFFFF
    values = {(0xFFF18C, 2): 0, (0xFFF18E, 2): 0,
              (entry + 4, 2): 2, (entry + 6, 2): 1, (entry, 2): 0x10, (entry + 2, 2): 0x28,
              ((player.PROXIMITY_KIND_TABLE + 2) & 0xFFFFFF, 1): player.PROXIMITY_KIND_CONSUME,
              (player.EA23_WORD & 0xFFFFFF, 1): 2}
    result = player.state1918_scan_consume(_reader(values))
    assert result['arm'] == 'consumed'
    assert result['stores'] == {(entry + 4) & 0xFFFFFF: (0xFFFF, 2), (entry + 6) & 0xFFFFFF: (0, 2)}


def test_dispatch_runs_the_scan_when_inactive():
    assert player.state1918_dispatch(_reader({}))['arm'] == 'scan'


def test_dispatch_calls_highlight_when_empty_and_bits_clear():
    values = {(player.SCAN_ACTIVE & 0xFFFFFF, 2): 1, (player.SCAN_EMPTY & 0xFFFFFF, 2): 1,
              (player.EA23_WORD & 0xFFFFFF, 1): 0}
    assert player.state1918_dispatch(_reader(values))['arm'] == 'highlight'


def test_dispatch_pending_hold_declines_bit1_alone():
    values = {(player.SCAN_ACTIVE & 0xFFFFFF, 2): 1, (player.SCAN_EMPTY & 0xFFFFFF, 2): 1,
              (player.EA23_WORD & 0xFFFFFF, 1): 2, (player.PENDING_HIGHLIGHT & 0xFFFFFF, 2): 1}
    result = player.state1918_dispatch(_reader(values))
    assert result['arm'] == 'bit1-set'


def test_dispatch_pending_hold_on_bit2_alone():
    values = {(player.SCAN_ACTIVE & 0xFFFFFF, 2): 1, (player.SCAN_EMPTY & 0xFFFFFF, 2): 1,
              (player.EA23_WORD & 0xFFFFFF, 1): 4, (player.PENDING_HIGHLIGHT & 0xFFFFFF, 2): 1}
    result = player.state1918_dispatch(_reader(values))
    assert result['arm'] == 'pending-hold' and result['set_pending'] is True


def test_dispatch_idle_exit_direct_path():
    values = {(player.SCAN_ACTIVE & 0xFFFFFF, 2): 1, (player.SCAN_EMPTY & 0xFFFFFF, 2): 0,
              (player.PENDING_HIGHLIGHT & 0xFFFFFF, 2): 0, (player.EA23_WORD & 0xFFFFFF, 1): 0}
    result = player.state1918_dispatch(_reader(values))
    assert result['arm'] == 'idle-exit' and result['set_pending'] is False


def test_state19_head_dispatches_on_ea1e():
    assert player.state19_head(_reader({(player.EA1E_WORD & 0xFFFFFF, 2): 1}))['head'] == 'dispatch'
    assert player.state19_head(_reader({(player.EA1E_WORD & 0xFFFFFF, 2): 0}))['head'] == 'budget'


def test_state19_budget_tail_holds_then_resets():
    hold = player.state19_budget_tail(_reader({}), 1)
    assert hold == {'arm': 'budget-hold', 'd7': 0, 'stores': {}}
    reset = player.state19_budget_tail(_reader({}), 0)
    assert reset['arm'] == 'budget-reset' and reset['d7'] == 2
    assert reset['stores'] == {player.STATE_INDEX & 0xFFFFFF: (player.STATE19_RESET_STATE_INDEX, 2)}


# --- semantics: game.achievements.achievement_highlight_cycle / game.spawns.floating_icon_spawn --

def test_highlight_cycle_refreshes_when_slot_empty():
    values = {(achievements.HIGHLIGHT_ID & 0xFFFFFF, 2): 1, ((achievements.ACHIEVEMENT_SLOTS + 2) & 0xFFFFFF, 2): 0xFFFF}
    result = achievements.achievement_highlight_cycle(_reader(values))
    assert result['arm'] == 'refresh' and result['icon_d0'] == 1 and result['stores'] == {}


def test_highlight_cycle_spawns_when_slot_holds_a_value():
    values = {(achievements.HIGHLIGHT_ID & 0xFFFFFF, 2): 2, ((achievements.ACHIEVEMENT_SLOTS + 4) & 0xFFFFFF, 2): 0x12}
    result = achievements.achievement_highlight_cycle(_reader(values))
    assert result['arm'] == 'spawn' and result['kind'] == 0x12 + achievements.HIGHLIGHT_KIND_BIAS
    assert result['stores'] == {(achievements.ACHIEVEMENT_SLOTS + 4) & 0xFFFFFF: (0xFFFF, 2)}


def test_floating_icon_spawn_declines_special_kind_and_busy():
    assert spawns.floating_icon_spawn(_reader({}), 1, 2, spawns.SPECIAL_KIND)['arm'] == 'special'
    busy = {(spawns.SPAWN_KIND & 0xFFFFFF, 2): 5}
    assert spawns.floating_icon_spawn(_reader(busy), 1, 2, 0x10)['arm'] == 'busy'


def test_floating_icon_spawn_stores_all_four_fields_when_idle():
    idle = {(spawns.SPAWN_KIND & 0xFFFFFF, 2): 0xFFFF}
    result = spawns.floating_icon_spawn(_reader(idle), 0x100, 0x200, 0x87)
    assert result['arm'] == 'spawn'
    assert result['stores'] == {spawns.SPAWN_X & 0xFFFFFF: (0x100, 2), spawns.SPAWN_Y & 0xFFFFFF: (0x200, 2),
                                spawns.SPAWN_TIMER & 0xFFFFFF: (spawns.SPAWN_TIMER_INIT, 2),
                                spawns.SPAWN_KIND & 0xFFFFFF: (0x87, 2)}


# --- boundary: every retained fixture, both states ------------------------------------------------

def check_seam(seam, state):
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
def test_state19_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state19_plan(machine, registers)
        except UnsupportedCandidate as error:
            pytest.fail(f'unexpected decline: {error}')
    if isinstance(plan, Seam):
        check_seam(plan, state)
        return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems


STATE18_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-005834-*/005834-entry-p*.state'))
needs_state18_census = pytest.mark.skipif(not STATE18_FIXTURES or not GODS.rom_path.is_file(),
                                          reason='no local census of 005834')


@needs_state18_census
@pytest.mark.parametrize('fixture', STATE18_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_state18_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state18_plan(machine, registers)
        except UnsupportedCandidate as error:
            pytest.fail(f'unexpected decline: {error}')
    if isinstance(plan, Seam):
        check_seam(plan, state)
        return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems


def test_candidate_names_are_explicit():
    assert recovery.Candidate('state-19').gate_pcs == (boundary.STATE19_ENTRY,)
    assert recovery.Candidate('state-18').gate_pcs == (boundary.STATE18_ENTRY,)
    assert boundary.STATE19_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    # STATE18_ENTRY is deliberately NOT armed in the combined candidate: native/machine.cpp caps the
    # gate set at 64 and camera-sprites was already at 63 (state 19 takes the last slot); state 18
    # stays a fully recovered, individually verified candidate of its own, per Aladdin's own
    # precedent for exhausted native gate capacity (docs/archive/aladdin/recovery-cost-log.md).
    assert len(recovery.Candidate('camera-sprites').gate_pcs) == 64
    assert boundary.STATE18_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    # A register mutant, not the generic _mutate_outcome every other state uses: states 19/18 are
    # seam-heavy, and dropping every write corrupts a seam's own structural return-address writes,
    # faulting the M68000 rather than diverging cleanly (confirmed empirically).  D0 carries the icon
    # slot into every ceded 001648 call and is real on every admitted arm, seam or plain.
    assert recovery.Candidate('state-19-mutant-result').mutation is recovery._mutate_register
    assert recovery.Candidate('state-18-mutant-result').mutation is recovery._mutate_register


@needs_reference
@pytest.mark.parametrize('candidate,fixtures', [('state-19', FIXTURES), ('state-18', STATE18_FIXTURES)])
def test_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges(candidate, fixtures):
    for fixture in fixtures:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate=candidate, reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip(f'no retained fixture reaches {candidate} within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    try:
        mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate=f'{candidate}-mutant-result', reference=EVIDENCE)
    except NativeError:
        return   # a mutant that faults the machine is itself a finding, not a control failure
    assert mutant['status'] == 'DIVERGENCE', mutant
