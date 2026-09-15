"""The first recovered Gods region: the camera follow step (002806).

Three tiers: the pure semantics on synthetic reads; the boundary plan
against the tracer's facts on every state the census retained from the
recorded history (all six executed paths and their CCR variants); the
candidate over real frames against the reference of the last PASS cold run,
with its negative control diverging.  The evidence tiers skip when the local
census/reference artifacts are absent (`docs/gods/STATUS.md` says how they
are made); the semantics tier always runs.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import camera
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
# One census directory per recording the routine was censused on (census-002806, census-002806-<node>).
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-002806*/002806-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 002806')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not (EVIDENCE / 'boundary-6000.state').exists()
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    return lambda address: values[address]


def test_camera_x_eases_by_four_toward_the_follow_point_and_y_snaps():
    base = {camera.FOLLOW_X: 0x0070, camera.CAMERA_X: 0x0070, camera.FOLLOW_Y: 0x01B5}
    hold = camera.camera_follow(_reader(base))
    assert hold['branch'] == 'hold' and hold['clamps'] == []
    assert hold['stores'] == {camera.CAMERA_X: 0x70, camera.SCROLL_X: 0x38, camera.CAMERA_Y: 0x1B5, camera.SCROLL_Y: 0xDA}
    assert hold['d0'] == 0xDA and hold['x_flag'] == 1
    right = camera.camera_follow(_reader({**base, camera.FOLLOW_X: 0x0100}))
    assert right['branch'] == 'right' and right['stores'][camera.CAMERA_X] == 0x74 and right['stores'][camera.SCROLL_X] == 0x3A
    left = camera.camera_follow(_reader({**base, camera.FOLLOW_X: 0x0001}))
    assert left['branch'] == 'left' and left['stores'][camera.CAMERA_X] == 0x6C
    assert camera.camera_follow(_reader({**base, camera.FOLLOW_Y: 0x0340}))['x_flag'] == 0


def test_the_limit_clamps_are_witnessed_and_the_negative_clamps_are_named():
    base = {camera.FOLLOW_X: 0x0070, camera.CAMERA_X: 0x0070, camera.FOLLOW_Y: 0x0340}
    clamped = camera.camera_follow(_reader(base))
    assert clamped['clamps'] == ['y-limit'] and clamped['d0'] == 0xFF and clamped['stores'][camera.SCROLL_Y] == 0xFF
    assert clamped['stores'][camera.CAMERA_Y] == 0x340
    negative_y = camera.camera_follow(_reader({**base, camera.FOLLOW_Y: 0xFFF0}))
    assert negative_y['clamps'] == ['y-negative'] and negative_y['stores'][camera.CAMERA_Y] == 0
    low = {**base, camera.FOLLOW_Y: 0x01B5}
    wide = camera.camera_follow(_reader({**low, camera.FOLLOW_X: 0x0D10, camera.CAMERA_X: 0x0D10}))
    assert wide['clamps'] == ['x-limit'] and wide['stores'][camera.SCROLL_X] == 0x67F
    behind = camera.camera_follow(_reader({**low, camera.FOLLOW_X: 0xFFFC, camera.CAMERA_X: 0xFFFC}))
    assert behind['clamps'] == ['x-negative'] and behind['stores'][camera.SCROLL_X] == 0


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_plan_reproduces_every_fact_of_the_original_on_each_retained_path(fixture):
    state = fixture.read_bytes()
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['entry'] == boundary.CAMERA_FOLLOW_ENTRY
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        plan = boundary.camera_follow_plan(machine, machine.registers())
    facts = pathfacts.trace(state, game=GODS)
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['interrupts_during_trace'] == 0


@needs_census
def test_unwitnessed_clamps_are_declined_and_the_original_runs_them():
    state = FIXTURES[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        pc = machine.info['pc']
        assert pc == boundary.CAMERA_FOLLOW_ENTRY
        machine.gates([pc])
        assert machine.run(instructions=1) == 'gate'
        # A negative follow-point y: the 00283A arm no recording has entered.
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=pc,
                              writes=[(camera.FOLLOW_Y, 0xFF), (camera.FOLLOW_Y + 1, 0xF0)], registers=machine.registers())
        with pytest.raises(boundary.UnsupportedCandidate, match='y-negative'):
            boundary.camera_follow_plan(machine, machine.registers())
        candidate = recovery.Candidate('camera')
        candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000) is False
        assert candidate.stats['fallbacks'] == 1 and candidate.stats['candidate_hits'] == 0
        assert list(candidate.stats['fallback_reasons']) == ['unsupported domain: camera clamp not witnessed by a recording: y-negative']
        assert machine.info['pc'] == 0x00280A     # the original executed the entry instruction


def test_candidate_names_are_explicit():
    assert recovery.Candidate('camera').gate_pcs == (boundary.CAMERA_FOLLOW_ENTRY,)
    assert recovery.Candidate('camera-mutant-result').mutation is not None
    with pytest.raises(ValueError, match='Unknown Gods recovery candidate'):
        recovery.Candidate('lifecycle')
    with pytest.raises(ValueError, match='has no recovered code|Unknown Gods'):
        GODS.candidate('lifecycle')


@needs_reference
def test_candidate_matches_the_reference_over_real_frames_and_its_mutant_diverges():
    report = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120, candidate='camera',
                                  reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['candidate_hits'] == 60 and report['fallbacks'] == 0     # once per game tick, every other frame
    mutant = segment_verify.check(EVIDENCE / 'boundary-6000.state', game=GODS, frames=120,
                                  candidate='camera-mutant-result', reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE' and mutant['first_difference']['frame'] == 6001
