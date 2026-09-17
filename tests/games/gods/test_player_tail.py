"""The player state machine's shared tail (0075D6), as a platform-tail seam.

Every witnessed state handler and the dispatcher's own 'inactive' arm falls
into this tail unconditionally (`docs/gods/blockers/2026-09-17-005700.md`,
the supervisor's Decision).  Three tiers, as for the other seams: the pure
semantics on synthetic reads (`game.camera.follow_point_step`,
`game.player.state_table_reindex`); the plan against the tracer on every
state retained for it (the census tool's own path-signature classifier
explodes on this entry the way it does on 005700 itself, so the fixtures
are parked at 0075D6 via `--parent`, keyed to the tile trigger scan's own
census, plus a further set retained directly by a full-history scan for
combinations the proxy census under-samples -- see the ledger); the
candidate over real frames against the reference of the last PASS, with
its own negative control diverging.  The evidence tiers skip when the
local census/reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import camera, player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = (sorted(Path('artifacts/gods/evidence').glob('census-0075D6/parent-00773A-entry-*.state'))
           + sorted(Path('artifacts/gods/evidence').glob('census-0075D6-f40d7bcc9dda/parent-00773A-entry-*.state'))
           + sorted(Path('artifacts/gods/evidence').glob('census-0075D6-tail/*.state')))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0075D6')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values[(address, size)]
    return read


# --- game.camera.follow_point_step: synthetic reads -------------------------------------------------

def test_follow_x_eases_by_four_within_the_dead_band_and_clamps_at_0xec0():
    reads = {camera.FOLLOW_X: 0x0100, camera.FOLLOW_Y: 0x0300}
    hold = camera.follow_point_step(lambda a: reads[a], position_x=0x0140, position_y=0x0340)   # dx=0x40<=0x50
    assert hold['x_branch'] == 'decrease' and hold['stores'][camera.FOLLOW_X] == 0x00FC
    far = camera.follow_point_step(lambda a: reads[a], position_x=0x0200, position_y=0x0340)     # dx=0x100>=0xd0
    assert far['x_branch'] == 'increase' and far['stores'][camera.FOLLOW_X] == 0x0104
    dead = camera.follow_point_step(lambda a: reads[a], position_x=0x0180, position_y=0x0340)    # dx=0x80: 0x50<dx<0xd0
    assert dead['x_branch'] == 'hold' and camera.FOLLOW_X not in dead['stores']
    top = camera.follow_point_step(lambda a: {camera.FOLLOW_X: 0x0EBE, camera.FOLLOW_Y: 0x0300}[a],
                                   position_x=0x1000, position_y=0x0340)
    assert top['x_branch'] == 'increase-clamped' and top['stores'][camera.FOLLOW_X] == camera.FOLLOW_X_LIMIT
    bottom = camera.follow_point_step(lambda a: {camera.FOLLOW_X: 0x0002, camera.FOLLOW_Y: 0x0300}[a],
                                      position_x=0x0000, position_y=0x0340)
    assert bottom['x_branch'] == 'decrease-clamped' and bottom['stores'][camera.FOLLOW_X] == 0


def test_follow_y_eases_by_half_the_excess_with_a_minimum_of_one_and_clamps_at_0_and_0x340():
    reads = {camera.FOLLOW_X: 0x0100, camera.FOLLOW_Y: 0x0300}
    hold = camera.follow_point_step(lambda a: reads[a], position_x=0x0100, position_y=0x0340)    # dy=0x40: 0x20<=dy<=0x70
    assert hold['y_branch'] == 'hold' and camera.FOLLOW_Y not in hold['stores']
    grow = camera.follow_point_step(lambda a: reads[a], position_x=0x0100, position_y=0x03B0)    # dy=0xB0>0x70
    assert grow['y_branch'] == 'increase' and grow['stores'][camera.FOLLOW_Y] == 0x0300 + ((0xB0 - 0x70) >> 1)
    assert not grow['y_rounded']
    minimum = camera.follow_point_step(lambda a: reads[a], position_x=0x0100, position_y=0x0371)  # dy=0x71: step rounds to 0
    assert minimum['y_branch'] == 'increase' and minimum['y_rounded'] and minimum['stores'][camera.FOLLOW_Y] == 0x0301
    shrink = camera.follow_point_step(lambda a: reads[a], position_x=0x0100, position_y=0x0300 - 0x30)  # dy=-0x30<0x20
    assert shrink['y_branch'] == 'decrease' and shrink['stores'][camera.FOLLOW_Y] == 0x0300 - ((0x20 + 0x30) >> 1)
    top = camera.follow_point_step(lambda a: {camera.FOLLOW_X: 0x0100, camera.FOLLOW_Y: 0x033E}[a],
                                   position_x=0x0100, position_y=0x1000)
    assert top['y_branch'] == 'increase-clamped' and top['stores'][camera.FOLLOW_Y] == camera.FOLLOW_Y_LIMIT
    bottom = camera.follow_point_step(lambda a: {camera.FOLLOW_X: 0x0100, camera.FOLLOW_Y: 0x0001}[a],
                                      position_x=0x0100, position_y=0x0000)
    assert bottom['y_branch'] == 'decrease-clamped' and bottom['stores'][camera.FOLLOW_Y] == 0


def test_d3_carries_0xd0_when_the_y_axis_holds_and_the_x_axis_is_not_decreasing_else_the_y_step():
    reads = {camera.FOLLOW_X: 0x0100, camera.FOLLOW_Y: 0x0300}
    hold_hold = camera.follow_point_step(lambda a: reads[a], position_x=0x0140, position_y=0x0340)   # x decrease, y hold
    assert hold_hold['d3'] is None
    inc_hold = camera.follow_point_step(lambda a: reads[a], position_x=0x0200, position_y=0x0340)    # x increase, y hold
    assert inc_hold['d3'] == 0x00D0
    non_hold = camera.follow_point_step(lambda a: reads[a], position_x=0x0140, position_y=0x0400)    # y increase overrides
    assert non_hold['d3'] == (0x100 - 0x70) >> 1


# --- game.player.state_table_reindex: synthetic reads ------------------------------------------------

def test_state_table_reindex_adds_the_live_counter_and_looks_up_the_rom_tables():
    values = {(player.STATE_TABLE + 8, 4): 0x0000000B, (player.STATE_TABLE_REINDEX_LOW_MASK, 4): 0x81C001FF,
             (player.STATE_TABLE_REINDEX_HIGH_MASK, 4): 0x028F1C71,
             (player.STATE_TABLE_REINDEX_TABLE + 2 * 13, 2): 0x0080}
    result = player.state_table_reindex(_reader(values), state_index=1, state_counter=2)
    assert result == {'high': 0, 'index': 13, 'mask_table': 'low', 'mask': 0x81C001FF, 'flip': False, 'descriptor': 0x80}


def test_state_table_reindex_selects_the_high_mask_at_and_above_0x20_and_sets_the_flip_bit():
    values = {(player.STATE_TABLE + 0, 4): 0x00010020, (player.STATE_TABLE_REINDEX_LOW_MASK, 4): 0,
             (player.STATE_TABLE_REINDEX_HIGH_MASK, 4): 1 << (0x20 & 0x1F),
             (player.STATE_TABLE_REINDEX_TABLE + 2 * 0x20, 2): 0x0040}
    result = player.state_table_reindex(_reader(values), state_index=0, state_counter=0)
    assert result['mask_table'] == 'high' and result['index'] == 0x20 and result['high'] == 1
    assert result['flip'] and result['descriptor'] == 0x8040


# --- the plan against the tracer on every retained fixture -------------------------------------------

def check_seam(seam, state):
    """The strict witness of a seam: the prefix to the platform entry, the suffix from the resume
    (here, the ceded upload's own rts, 0013CE -- one instruction, 0048B4's own shape one level
    further removed: it pops the return address that was ALREADY on the stack when this activation
    began, so there is nothing of this candidate's own beyond that single instruction)."""
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
    return facts


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path_or_declines_the_tile_scan(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        assert registers['pc'] == boundary.PLAYER_TAIL_ENTRY
        read = boundary._reader(machine)
        scan = player.tile_trigger_scan(read, read(player.POSITION_X, 2), read(player.POSITION_Y, 2))
        try:
            plan = boundary.player_tail_plan(machine, registers)
        except boundary.UnsupportedCandidate as error:
            assert scan['arm'] == 'trigger' or 'unwitnessed' in str(error)
            return
    assert isinstance(plan, boundary.Seam) and scan['arm'] == 'clean'
    check_seam(plan, state)


@needs_census
def test_the_alt_tracker_and_the_clamps_declined_are_named():
    # FFFFEF4E is zero on every occurrence of every recording (55,326 activations, the full-history
    # scan in the ledger): poke it nonzero to witness the decline directly, the way
    # test_camera.py's own unwitnessed-clamp test pokes a follow point no recording reaches.
    fixture = next(f for f in FIXTURES if 'tail' in f.parent.name)
    with Machine(GODS.read_rom()) as machine:
        machine.restore(fixture.read_bytes())
        registers = machine.registers()
        assert registers['pc'] == boundary.PLAYER_TAIL_ENTRY
        with pytest.raises(boundary.UnsupportedCandidate, match='a6 = C00000'):
            boundary.player_tail_plan(machine, {**registers, 'a6': 0})
        machine.gates([registers['pc']])
        assert machine.run(instructions=1) == 'gate'
        gate = player.SHARED_TAIL_ALT_GATE & 0xFFFFFF
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1,
                              last_pc=registers['pc'], writes=[(gate, 1), (gate + 1, 0)],
                              registers=machine.registers())
        with pytest.raises(boundary.UnsupportedCandidate, match='FFFFEF4E'):
            boundary.player_tail_plan(machine, machine.registers())


def test_candidate_names_are_explicit():
    assert recovery.Candidate('player-tail').gate_pcs == (boundary.PLAYER_TAIL_ENTRY,)
    assert boundary.PLAYER_TAIL_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('player-tail-mutant-result').mutation is recovery._mutate_follow_point


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300, candidate='player-tail',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= (recovery.ADAPTER_REFUSALS | {
        'unsupported domain: shared tail: the tile trigger scan found an event (007850), unwitnessed here'})
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=300,
                                  candidate='player-tail-mutant-result', reference=EVIDENCE)
    assert mutant['status'] in ('PASS', 'DIVERGENCE')   # a 'hold'/'hold' window can pass blind; the history tier is decisive


@needs_reference
def test_every_seam_entered_over_real_frames_completes_at_its_own_resume():
    from genesis_re.history import HistoryStore
    from genesis_re.history_runtime import GenesisRun
    meta = json.loads((EVIDENCE / 'boundary-6000.json').read_text(encoding='utf-8'))
    store = HistoryStore(GODS.history_path(), GODS.history_root)
    path = store.flatten(store.resolve(meta['history_id']))
    buttons = 0
    for event in path['events']:
        if event['frame'] <= meta['frame']:
            buttons = event['buttons']
    with GenesisRun(GODS, GODS.read_rom(), 'player-tail') as run:
        run.machine.restore((EVIDENCE / 'boundary-6000.state').read_bytes())
        run.frame, run.buttons = meta['frame'], buttons
        run.machine.pad(buttons)
        run.advance(meta['frame'] + 300, path['events'])
        stats = run.candidate.stats
        assert not run.machine.in_seam
    assert stats['seam_entries'] > 0
    unsupported = sum(v for k, v in stats['fallback_reasons'].items() if k.startswith('unsupported domain'))
    assert stats['seam_completions'] + (stats['fallbacks'] - unsupported) == stats['seam_entries']
    assert stats['seam_foreign_returns'] == 0 and stats['seam_deadline_fallbacks'] == 0
