"""005700: the player state machine's own dispatch, composed as the family over FFFFF192.

The dispatcher's own prefix (d7 <- STATE_COUNTER FFFFF190, d0 <- STATE_INDEX FFFFF192, the
FROZEN_FLAG/ACTIVE_GATE inactive arm falling straight into the already-armed player-tail gate
(`0075D6`), the STATE_TABLE lookup at 005618 otherwise) owns the jump into each recovered state's
own planner -- the same "call the callee's own planner from a machine parked at its own entry,
prepend this region's own cost" composition `achievement_slot_dispatch_plan` already draws over
`achievement_slot_reset_plan`, one level up: no device access sits in the dispatcher's own head, so
the callee's own AtomicPlan/Seam is reused directly, never ceded to the machine.  This turns the 25
individual player-state gates `camera-sprites` used to arm (0-6, 8-14, 16-28 except 18, and the
movement-cluster pair 24/25) into this one gate: their own hits are replaced by this candidate's.

One real gap remains, declined by name, not guessed: states 7 and 15 (`game.player.
UNWITNESSED_STATES`, never FFFFF192's own value on any of the eight recordings).  Real STATE_TABLE
index 26 (ROM 005724) -- the coordinator's own seventh most frequent state, the tree's largest single
decline before its own recovery session (1,975 of 8,857 fallbacks) -- is now recovered
(`game.player.state_26_step` and friends, `boundary.state_26_plan`, candidate `'state-26'`); the
candidate PREVIOUSLY named 'state-26' targeted index 20 (ROM 0069AC) and is renamed 'state-20'
(`test_state26.py`), a misnomer `docs/gods/STATUS.md`'s own 18 September entry first recorded.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from genesis_re.seam import Seam, UnsupportedCandidate
from gods_sega import boundary, recovery
from gods_sega.game import player
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = (sorted(Path('artifacts/gods/evidence').glob('census-005700-fb408bc75597/005700-entry-p*.state'))
           + sorted(Path('artifacts/gods/evidence').glob('census-005700-plain/005700-entry-*.state')))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 005700')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


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
def test_player_state_plan_reproduces_every_witnessed_state(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.player_state_plan(machine, registers)
        except UnsupportedCandidate as error:
            # The two real remaining gaps: states 7/15 (never FFFFF192's own value on any recording),
            # plus real STATE_TABLE index 26's (005724) own narrow unwitnessed sub-arms (recovered 18
            # Sep) -- see game/player.py's own module note above state_26_step.
            assert 'not witnessed by a recording' in str(error) or 'outside the 29-entry STATE_TABLE' in str(error), error
            return
    if isinstance(plan, Seam):
        check_seam(plan, state)
        return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems


def test_state_26_is_recovered_not_declined():
    """18 September (real-index-26 recovery session): the census over fb408bc75597 retains real
    occurrences of STATE_TABLE index 26 (005724) -- the coordinator's own frequency tally named it
    634 of 13,488 activations, the tree's largest single decline (1,975 of 8,857 fallbacks) before
    this session.  Every one of those occurrences now MATCHes through player_state_plan; not the
    'state-26' candidate's own former misnomer for index 20 (0069AC), renamed 'state-20'."""
    fixtures = [f for f in FIXTURES if f.parent.name == 'census-005700-fb408bc75597']
    plans = []
    with Machine(GODS.read_rom()) as machine:
        for fixture in fixtures:
            state = fixture.read_bytes()
            machine.restore(state)
            registers = machine.registers()
            index = int.from_bytes(machine.peek_ram(player.STATE_INDEX & 0xFFFF, 2), 'big')
            if index != 26:
                continue
            plans.append((state, boundary.player_state_plan(machine, registers)))
    assert plans, 'no retained fixture reached real STATE_TABLE index 26; the census may have changed'
    for state, plan in plans:
        facts = pathfacts.region_only(pathfacts.trace(state, game=GODS, stop_pc=plan.registers['pc']))
        problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
        assert problems == [], problems


def test_candidate_names_are_explicit():
    assert recovery.Candidate('player-state').gate_pcs == (boundary.PLAYER_STATE_ENTRY,)
    assert boundary.PLAYER_STATE_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    # The 25 individual player-state gates are retired from the combined candidate: their own hits
    # are replaced by the dispatcher's.  Their own standalone candidates (state-0 etc.) are untouched.
    for entry in (boundary.STATE0_ENTRY, boundary.STATE1_ENTRY, boundary.STATE2_ENTRY, boundary.STATE3_ENTRY,
                  boundary.STATE4_ENTRY, boundary.STATE5_ENTRY, boundary.STATE6_ENTRY, boundary.STATE8_ENTRY,
                  boundary.STATE9_ENTRY, boundary.STATE10_ENTRY, boundary.STATE11_ENTRY, boundary.STATE12_ENTRY,
                  boundary.STATE13_ENTRY, boundary.STATE14_ENTRY, boundary.STATE16_ENTRY, boundary.STATE17_ENTRY,
                  boundary.STATE19_ENTRY, boundary.STATE21_ENTRY, boundary.STATE22_ENTRY, boundary.STATE23_ENTRY,
                  boundary.STATE26_ENTRY, boundary.STATE27_ENTRY, boundary.STATE28_ENTRY, boundary.STATE24_ENTRY,
                  boundary.STATE25_ENTRY, boundary.STATE_26_ENTRY):
        assert entry not in recovery.Candidate('camera-sprites').gate_pcs
    assert len(recovery.Candidate('camera-sprites').gate_pcs) <= 64     # the adapter's gate capacity
    assert recovery.Candidate('state-26').gate_pcs == (boundary.STATE_26_ENTRY,)
    # A d7 (STATE_COUNTER) mutant, the same shape states 0/1/14's own already draw: every witnessed
    # activation (100% of the coordinator's own tally is the active dispatch arm) hands d7 on to the
    # separately-armed player-tail gate one step later, whose own first instruction stores it into
    # FFFFF190 unconditionally.
    assert recovery.Candidate('player-state-mutant-result').mutation is recovery._mutate_player_state_counter


@needs_reference
def test_player_state_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='player-state', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches player-state within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='player-state-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE', mutant
