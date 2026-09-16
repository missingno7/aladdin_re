"""The rate-gated countdown check (010332): a control byte and a countdown word, both caller-supplied.

The dominant two arms ('idle': the control byte is zero; 'waiting': the
countdown has not reached zero) are a plain leaf, no frame, no calls.  The
'trigger' arm (the countdown reaches zero) calls one of two unrecovered
routines and is declined, even though it is witnessed -- the boundary
cannot reproduce a call into code that is not itself recovered.  Three
tiers as for the other leaves; the evidence tiers skip when the local
census or reference artifacts are absent.
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


def test_the_countdown_reaching_zero_is_the_trigger_arm():
    values = {(CONTROL + timers.RATE_ENABLE, 1): 1, (COUNTDOWN + timers.COUNTDOWN, 2): 1}
    result = timers.countdown_check(_reader(values), CONTROL, COUNTDOWN)
    assert result['arm'] == 'trigger' and result['after'] == 0


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_the_idle_and_waiting_arms_and_declines_the_trigger_one(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.COUNTDOWN_CHECK_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        control, countdown = registers['a3'] & 0xFFFFFF, registers['a5'] & 0xFFFFFF
        control_byte = machine.peek_ram(control & 0xFFFF, 0x14)[timers.RATE_ENABLE]
        if control_byte != 0:
            before = int.from_bytes(machine.peek_ram((countdown + timers.COUNTDOWN) & 0xFFFF, 2), 'big')
            if (before - 1) & 0xFFFF == 0:
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
