"""A retained real state verifies a candidate over a few frames against stored reference observations."""
import copy
import json

import segment_verify
from genesis_re.history import HistoryStore, write_json
from aladdin_sega.profile import ALADDIN, ROOT_ID, read_rom
from genesis_re.history_runtime import GenesisRun
from genesis_re.verification import execute_history

EVENTS = [{'frame': 2, 'buttons': 128}]


def evidence(tmp_path):
    store = HistoryStore(tmp_path / 'history', ALADDIN.history_root)
    node = store.append(ROOT_ID, EVENTS, 6)
    store.set_main(node)
    rom = read_rom()
    reference = execute_history(ALADDIN, store, rom, node=node)
    (tmp_path / 'evidence').mkdir()
    write_json(tmp_path / 'evidence' / 'reference.json', reference)
    with GenesisRun(ALADDIN, rom) as run:
        run.advance(3, EVENTS)
        state, frame, _, _, _ = run.save()
    fixture = tmp_path / 'evidence' / 'boot-3.state'
    fixture.write_bytes(state)
    fixture.with_suffix('.json').write_text(json.dumps({'frame': frame, 'history_id': node, 'entry': 0,
                                                        'frame_boundary': True}))
    return store, node, fixture, reference


def test_segment_from_a_retained_state_matches_the_reference_every_frame(tmp_path):
    store, node, fixture, _ = evidence(tmp_path)
    for candidate in ('original', 'lifecycle'):
        report = segment_verify.check(fixture, game=ALADDIN, frames=3, candidate=candidate, history=store.path)
        assert report['status'] == 'PASS', report
        assert (report['from_frame'], report['frames'], report['oracle']) == (3, 3, 'reference observations')
        assert report['first_difference'] is None
    assert 'fallbacks_by_gate' in report and report['candidate_hits'] == 0


def test_a_tampered_or_foreign_reference_is_detected_or_replaced_by_the_original(tmp_path):
    store, node, fixture, reference = evidence(tmp_path)
    tampered = copy.deepcopy(reference)
    tampered['observations'][node][4]['state_sha256'] = '0' * 64  # frame 5
    write_json(tmp_path / 'tampered.json', tampered)
    report = segment_verify.check(fixture, game=ALADDIN, frames=3, candidate='original', reference=tmp_path / 'tampered.json',
                                  history=store.path)
    assert report['status'] == 'DIVERGENCE'
    assert report['first_difference'] == {'frame': 5, 'fields': ['state_sha256']}
    foreign = copy.deepcopy(reference)
    foreign['history_id'] = 'f' * 64
    write_json(tmp_path / 'foreign.json', foreign)
    report = segment_verify.check(fixture, game=ALADDIN, frames=3, candidate='original', reference=tmp_path / 'foreign.json',
                                  history=store.path)
    assert report['status'] == 'PASS' and report['oracle'].startswith('original run (reference is for history')
    report = segment_verify.check(fixture, game=ALADDIN, frames=3, candidate='original', reference=tmp_path / 'absent',
                                  history=store.path)
    assert report['status'] == 'PASS' and 'no reference observations' in report['oracle']


def test_parent_fixture_reports_child_ownership_and_the_cli_exit_status(tmp_path, capsys):
    store, node, fixture, _ = evidence(tmp_path)
    parent = tmp_path / 'evidence' / 'parent-boot-3.state'
    parent.write_bytes(fixture.read_bytes())
    parent.with_suffix('.json').write_text(json.dumps({'parent_frame': 3, 'child': 0x1E5800, 'history_id': node}))
    report = segment_verify.check(parent, game=ALADDIN, frames=2, history=store.path)
    assert report['status'] == 'PASS' and report['child'] == '1E5800'
    assert report['child_named_in_fallbacks'] == [] and report['ownership'].startswith('inconclusive')
    assert segment_verify.main([str(parent), '--game', 'aladdin', '--frames', '2', '--history', str(store.path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith('PASS: parent-boot-3.state from frame 3 for 2 frames against reference observations')
    assert 'child 1E5800: inconclusive' in out
    assert segment_verify.main([str(fixture), '--game', 'aladdin', '--frames', '9', '--history', str(store.path), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['frames'] == 3  # clipped to the end of the history


def test_mid_frame_state_compares_state_and_video_first_then_the_reseeded_pcm_chain(tmp_path):
    from genesis_re.machine import Machine
    store, node, fixture, _ = evidence(tmp_path)
    with Machine(read_rom()) as machine:
        machine.restore(fixture.read_bytes())
        machine.gates([])
        assert machine.run(instructions=2000) == 'limit'
        mid = tmp_path / 'evidence' / 'mid-3.state'
        mid.write_bytes(machine.snapshot())
    mid.with_suffix('.json').write_text(json.dumps({'frame': 3, 'history_id': node, 'entry': 0}))
    report = segment_verify.check(mid, game=ALADDIN, frames=3, candidate='original', history=store.path)
    assert report['status'] == 'PASS', report
    assert report['first_frame_pcm'] == 'not compared: state restored mid-frame'
    boundary = segment_verify.check(fixture, game=ALADDIN, frames=3, candidate='original', history=store.path)
    assert boundary['first_frame_pcm'] == 'compared'
