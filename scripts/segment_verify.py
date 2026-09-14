"""segment_verify: verify a candidate over a few frames from a retained real state.

    python scripts/segment_verify.py FIXTURE.state [--frames 120] [--candidate lifecycle]
                                     [--reference DIR-or-reference.json] [--history history] [--json]

Restores a census fixture (a complete machine state captured on the canonical
replay at a known frame) into a fresh candidate run, advances it ``--frames``
frames with the canonical input events, and compares every frame's state,
video and PCM observation with the reference cold run's observations for the
same frames.  The reference is the ``reference.json`` a ``history-verify``
run wrote (by default the one next to the fixture); it must come from the
same history and the same native binary.  Without a reference the original
is executed first over the same segment.

This is the constant-time integration check between a fixture qualification
and the full cold comparison: it runs the leaf under real frame deadlines in
the frames around a recorded occurrence, and for a ``parent-*`` fixture it
reports whether the child was declined (named in a fallback reason) or owned.
It never replaces the every-frame cold comparison from power-on.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from pathlib import Path as _Path

# Judge the checkout, never an installed wheel: the checkout's src wins.
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))

FIELDS = ('state_sha256', 'frame_sha256', 'pcm_sha256', 'pcm_bytes')


def _load_reference(reference, history_id):
    from aladdin_sega.receipt import execution_receipt
    path = Path(reference)
    if path.is_dir():
        path = path / 'reference.json'
    if not path.exists():
        return None, 'no reference observations at %s' % path
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('history_id') != history_id:
        return None, 'reference is for history %s, fixture is from %s' % (str(data.get('history_id'))[:12], history_id[:12])
    native = data.get('implementation', {}).get('native')
    if native != execution_receipt()['native_binary_sha256']:
        return None, 'reference was produced by a different native binary'
    observations = data.get('observations', {}).get(history_id)
    if not observations:
        return None, 'reference has no observations for this history'
    return observations, None


def _segment(rom, candidate, state, frame, buttons, events, frames, pcm_seed, pcm_bytes, reseed=None):
    """Advance a restored state; ``reseed`` re-anchors the PCM chain after the first frame.

    A machine snapshot does not carry the audio samples produced since the
    last frame drain, so a state captured inside a frame (every census
    fixture) cannot reproduce that frame's PCM; the chain is re-anchored to
    the reference after the first frame and compared from the next one on.
    Only a state saved at a frame boundary right after the drain (marked
    ``frame_boundary`` in its metadata) has its first frame's PCM compared.
    """
    from aladdin_sega.history_runtime import GenesisRun
    observations = []
    with GenesisRun(rom, candidate) as run:
        run.restore((state, frame, buttons, pcm_seed, pcm_bytes))

        def observe(r):
            observations.append(r.observable())
            if reseed is not None and len(observations) == 1:
                r.pcm_digest, r.pcm_bytes = reseed
        run.advance(frame + frames, events, observe)
        stats = dict(run.candidate.stats) if run.candidate else {}
    return observations, stats


def check(fixture, *, frames=120, candidate='lifecycle', reference=None, history='history'):
    """Return a report dict; ``status`` is PASS, DIVERGENCE or ERROR."""
    from aladdin_sega.history import HistoryStore
    from aladdin_sega.history_runtime import EMPTY_PCM
    from aladdin_sega.profile import read_rom
    fixture = Path(fixture)
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    frame = meta['parent_frame'] if 'parent_frame' in meta else meta['frame']
    history_id = meta['history_id']
    store = HistoryStore(history)
    path = store.flatten(store.resolve(history_id))
    if frame + frames > path['end_frame']:
        frames = path['end_frame'] - frame
    if frames <= 0:
        return {'status': 'ERROR', 'detail': 'fixture frame %d is at the end of the history' % frame}
    buttons = 0
    for event in path['events']:
        if event['frame'] <= frame:
            buttons = event['buttons']
    events = [event for event in path['events'] if event['frame'] > frame]
    state = fixture.read_bytes()
    rom = read_rom()
    reference_observations, problem = (None, None)
    if reference is None:
        reference = fixture.parent
    reference_observations, problem = _load_reference(reference, history_id)
    started = time.perf_counter()
    mid_frame = not meta.get('frame_boundary', False)
    if reference_observations is not None:
        if frame >= 1:
            seed = reference_observations[frame - 1]
            pcm_seed, pcm_bytes = seed['pcm_sha256'], seed['pcm_bytes']
        else:
            pcm_seed, pcm_bytes = EMPTY_PCM, 0
        expected = reference_observations[frame:frame + frames]
        reseed = (expected[0]['pcm_sha256'], expected[0]['pcm_bytes']) if mid_frame else None
        oracle = 'reference observations'
    else:
        pcm_seed, pcm_bytes = EMPTY_PCM, 0
        expected, _ = _segment(rom, 'original', state, frame, buttons, events, frames, pcm_seed, pcm_bytes)
        reseed = None
        oracle = 'original run (%s)' % problem
    actual, stats = _segment(rom, candidate, state, frame, buttons, events, frames, pcm_seed, pcm_bytes, reseed)
    first = None
    for index, (got, want) in enumerate(zip(actual, expected)):
        fields = FIELDS
        if index == 0 and reseed is not None:
            fields = ('state_sha256', 'frame_sha256')
        differences = [field for field in fields if got[field] != want[field]]
        if differences or got['frame'] != want['frame']:
            first = {'frame': got['frame'], 'fields': differences or ['frame']}
            break
    if first is None and len(actual) != len(expected):
        first = {'frame': frame + min(len(actual), len(expected)), 'fields': ['count']}
    reasons = stats.get('fallback_reasons', {})
    report = {
        'status': 'PASS' if first is None else 'DIVERGENCE', 'fixture': fixture.name, 'candidate': candidate,
        'history_id': history_id, 'from_frame': frame, 'frames': frames, 'oracle': oracle,
        'seconds': round(time.perf_counter() - started, 2), 'first_difference': first,
        'first_frame_pcm': 'not compared: state restored mid-frame' if reseed is not None else 'compared',
        'candidate_hits': stats.get('candidate_hits'), 'fallbacks': stats.get('fallbacks'),
        'fallback_reasons': dict(sorted(reasons.items(), key=lambda kv: -kv[1])[:8]),
        'fallbacks_by_gate': dict(sorted(stats.get('fallbacks_by_gate', {}).items(), key=lambda kv: -kv[1])[:6]),
    }
    child = meta.get('child')
    if child is not None:
        named = [reason for reason in reasons if '%06X' % child in reason]
        parent_gate = '%06X' % meta['parent'] if 'parent' in meta else None
        parent_hits = stats.get('contact_step_hits', 0) + stats.get('contact_scan_hits', 0)
        report['child'] = '%06X' % child
        report['child_named_in_fallbacks'] = named
        if named:
            report['ownership'] = 'declined'
        elif parent_hits:
            report['ownership'] = 'owned'
        else:
            refused = stats.get('fallbacks_by_gate', {}).get(parent_gate, 0) if parent_gate else 0
            report['ownership'] = 'inconclusive: parent plan not admitted (%d fallbacks at %s)' % (refused, parent_gate)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('fixture')
    parser.add_argument('--frames', type=int, default=120)
    parser.add_argument('--candidate', default='lifecycle')
    parser.add_argument('--reference', default=None, help='history-verify output directory or its reference.json')
    parser.add_argument('--history', default='history')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    report = check(args.fixture, frames=args.frames, candidate=args.candidate, reference=args.reference,
                   history=args.history)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print('%s: %s from frame %d for %d frames against %s in %.2f s' % (
            report['status'], report['fixture'], report.get('from_frame', -1), report.get('frames', 0),
            report.get('oracle', '?'), report.get('seconds', 0)))
        if report.get('first_difference'):
            print('  first difference at frame %(frame)d: %(fields)s' % report['first_difference'])
        if report.get('detail'):
            print('  ' + report['detail'])
        if report.get('candidate_hits') is not None:
            print('  candidate hits %s, fallbacks %s' % (report['candidate_hits'], report['fallbacks']))
            for reason, count in report['fallback_reasons'].items():
                print('    %6d  %s' % (count, reason))
        if 'ownership' in report:
            print('  child %s: %s' % (report['child'], report['ownership']))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
