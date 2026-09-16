"""The rate-gated countdown check (010332): a control byte and a countdown record, both caller-supplied.

The dominant two arms ('idle': the control byte is zero; 'waiting': the
countdown has not reached zero) are a plain leaf, no frame, no calls.
Reaching zero reloads the countdown and a frequency word unconditionally,
then either calls the unrecovered 0091BC pool ('trigger-deep', declined)
or runs a direction-mirrored screen window test and, inside it, a bounded
pool scan+fill shaped like hazard.py's own ('trigger-reject': outside the
window; 'trigger-spawn': inside it, a free slot filled).  The pool
exhausted ('trigger-pool-full') is real ROM code but unwitnessed, so it is
declined too.  Three tiers as for the other leaves; the evidence tiers
skip when the local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import timers
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-010332*/010332-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 010332')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')

CONTROL, COUNTDOWN = 0xFF38C2, 0xFF3A2A


def _reader(values):
    def read(address, size):
        return values.get((address, size), 0)
    return read


def test_a_zero_control_byte_is_idle_and_touches_nothing():
    result = timers.countdown_check(_reader({(CONTROL + timers.RATE_ENABLE, 1): 0}), CONTROL, COUNTDOWN)
    assert result == {'arm': 'idle', 'before': None, 'after': None, 'stores': {}}


def test_a_nonzero_control_decrements_the_countdown_while_it_stays_nonzero():
    values = {(CONTROL + timers.RATE_ENABLE, 1): 1, (COUNTDOWN + timers.COUNTDOWN, 2): 0x20}
    result = timers.countdown_check(_reader(values), CONTROL, COUNTDOWN)
    assert result['arm'] == 'waiting' and result['before'] == 0x20 and result['after'] == 0x1F
    assert result['stores'] == {COUNTDOWN + timers.COUNTDOWN: (0x1F, 2)}


def _trigger_values(overrides=None):
    values = {(CONTROL + timers.RATE_ENABLE, 1): 8, (CONTROL + timers.TRIGGER_DEEP_GATE, 1): 0,
              (COUNTDOWN + timers.COUNTDOWN, 2): 1, (COUNTDOWN + timers.DIRECTION, 2): 0,
              (COUNTDOWN + timers.POSITION_X, 2): 100, (COUNTDOWN + timers.POSITION_Y, 2): 50,
              (timers.CAMERA_X, 2): 0, (timers.CAMERA_Y, 2): 0, (timers.FREQUENCY_SCALE, 2): 0x1000}
    values.update(overrides or {})
    return values


def test_the_countdown_reaching_zero_reloads_it_and_computes_the_frequency_unconditionally():
    result = timers.countdown_check(_reader(_trigger_values()), CONTROL, COUNTDOWN)
    assert result['after'] == 0 and result['reload'] == 32          # (0x10 - 8) * 4
    assert result['stores'][(COUNTDOWN + timers.COUNTDOWN) & 0xFFFFFF] == (32, 2)


def test_the_deep_gate_declines_before_touching_the_window_or_the_pool():
    result = timers.countdown_check(_reader(_trigger_values({(CONTROL + timers.TRIGGER_DEEP_GATE, 1): 1})),
                                     CONTROL, COUNTDOWN)
    assert result['arm'] == 'trigger-deep'
    assert 'frequency' not in result and 'windowed' not in result


def test_outside_the_screen_window_is_trigger_reject_with_no_pool_touch():
    # BACK (direction 0): Y in [-4, 0xC0); Y=300 is outside it.
    result = timers.countdown_check(_reader(_trigger_values({(COUNTDOWN + timers.POSITION_Y, 2): 300})),
                                     CONTROL, COUNTDOWN)
    assert result['arm'] == 'trigger-reject' and result['windowed'] is False and result['slot'] is None
    assert all(address not in result['stores'] for address in range(timers.SPAWN_POOL_BASE & 0xFFFFFF,
                                                                      (timers.SPAWN_POOL_BASE + 8) & 0xFFFFFF))


def test_inside_the_window_fills_the_first_free_pool_slot():
    values = _trigger_values()
    values[(timers.SPAWN_POOL_BASE + 6, 2)] = 0xFFFF   # slot 0's own marker word: negative means free
    result = timers.countdown_check(_reader(values), CONTROL, COUNTDOWN)
    assert result['arm'] == 'trigger-spawn' and result['windowed'] is True
    assert result['slot'] == timers.SPAWN_POOL_BASE and result['tries'] == 0
    slot = timers.SPAWN_POOL_BASE & 0xFFFFFF
    assert result['stores'][slot] == (92, 2) and result['stores'][slot + 2] == (50, 2)      # position, bias -8 in X
    assert result['stores'][slot + 4] == (0xFFFF, 2) and result['stores'][slot + 6] == (timers.BACK['marker'], 2)


def test_a_full_pool_is_trigger_pool_full_unwitnessed():
    values = _trigger_values()
    for index in range(timers.SPAWN_POOL_COUNT):
        values[(timers.SPAWN_POOL_BASE + timers.SPAWN_POOL_STRIDE * index + 6, 2)] = 0   # every slot occupied
    result = timers.countdown_check(_reader(values), CONTROL, COUNTDOWN)
    assert result['arm'] == 'trigger-pool-full' and result['windowed'] is True and result['slot'] is None


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm_and_declines_the_rest(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.COUNTDOWN_CHECK_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        control, countdown = registers['a3'] & 0xFFFFFF, registers['a5'] & 0xFFFFFF
        result = timers.countdown_check(boundary._reader(machine), control, countdown)
        if result['arm'] in ('trigger-deep', 'trigger-pool-full'):
            with pytest.raises(boundary.UnsupportedCandidate, match='trigger'):
                boundary.countdown_check_plan(machine, registers)
            return
        plan = boundary.countdown_check_plan(machine, registers)
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc']


def test_candidate_names_are_explicit():
    assert recovery.Candidate('countdown-check').gate_pcs == (boundary.COUNTDOWN_CHECK_ENTRY,)
    assert boundary.COUNTDOWN_CHECK_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('countdown-check-mutant-result').mutation is recovery._mutate_register


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='countdown-check',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    if report['candidate_hits'] == 0:
        pytest.skip('countdown-check never hits in this window')
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='countdown-check-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
