"""State 22 (0062B0): state 21's own FFFFF1BA-gated head in front of state 12's own ENTIRE
oscillation body and BOTH block tests, reused verbatim (byte-for-byte the same masks, offsets and
immediates as state 12's own). A genuine ground-found jump lands on the SAME PHYSICAL ground-tail
code state 12's own uses (006134-006160, not a relocated copy). One real, confirmed difference from
state 12's own: the ALT ground test's own mask is FFFFF18C & 0x1F here, not state 12's own 0x1C.
The tail (once neither ground test finds anything) is D7-based: exactly 3 transitions to state 12
(d7 forced to 0); exactly 1 calls the already-recovered movement-cluster consumer 012DA0 before
exiting unchanged; any other value exits unchanged directly. Three tiers as for the other leaves;
the evidence tiers skip when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-0062B0*/0062B0-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 0062B0')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_head_bumps_d7_when_f1ba_clear():
    new_d7, f1ba_was_set = player._state22_head(_reader({}), 2)
    assert new_d7 == 3
    assert f1ba_was_set is False


def test_head_decrements_d7_when_f1ba_set():
    values = {(player.F1BA & 0xFFFFFF, 2): 1}
    new_d7, f1ba_was_set = player._state22_head(_reader(values), 2)
    assert new_d7 == 1
    assert f1ba_was_set is True


def test_tail_reaches_trigger_at_exactly_3():
    values = {(player.EA20_WORD & 0xFFFFFF, 2): 0, (player.F1BA & 0xFFFFFF, 2): 1, (0xFFFFF1A0 & 0xFFFFFF, 2): 2}
    result = player.state22_step(_reader(values), 4)
    assert result['arm'] == 'trigger'
    assert result['d7'] == 3


def test_tail_reaches_consume_at_exactly_1():
    result = player.state22_step(_reader({}), 0)
    assert result['arm'] == 'consume'
    assert result['d7'] == 1


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_witnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.state22_plan(machine, registers)
        except UnsupportedCandidate as error:
            assert 'not witnessed' in str(error), error
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_name_is_explicit():
    assert recovery.Candidate('state-22').gate_pcs == (boundary.STATE22_ENTRY,)
    # Retired 18 September: player_state_plan (005700) now owns the jump into state 22's
    # own handler; this candidate's own hits replace the direct gate's.
    assert boundary.STATE22_ENTRY not in recovery.Candidate('camera-sprites').gate_pcs
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('state-22-mutant-result').mutation is recovery._mutate_outcome


@needs_reference
def test_state_22_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-22', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches state 22 within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    from genesis_re.machine import NativeError
    try:
        mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='state-22-mutant-result', reference=EVIDENCE)
    except NativeError:
        # The mutant drops contact_consume's own writes wholesale (`_mutate_outcome`), which on
        # this fixture's own "consume" arm corrupts a linked-list-style record 012DA0 would
        # otherwise have updated; the real game dereferences it a few frames later and the native
        # machine raises an M68000 address error instead of a clean value mismatch -- the SAME
        # divergence `scripts/dev.py history-verify --candidate state-22-mutant-result --expect
        # divergence` already reports cleanly as DIVERGENCE at frame 5,605 (its own crash-tolerant
        # comparison catches this; segment_verify's own lighter-weight check does not), confirming
        # this is the mutant doing its job, not a bug.
        return
    assert mutant['status'] == 'DIVERGENCE'
