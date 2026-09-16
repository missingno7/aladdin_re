"""vp_refusal_report: the refusal breakdown of a classified vp_tree_run (candidate run with --classify).

    python scripts/research/vp_refusal_report.py DIR [DIR2 ...]
"""
import json
import sys
from collections import Counter
from pathlib import Path


def main(dirs):
    for d in dirs:
        run = json.loads((Path(d) / 'run.json').read_text())
        refusals = json.loads((Path(d) / 'refusals.json').read_text())
        stats = run['candidate_stats']
        print('== %s: candidate %s, observation offset %d (%.4f frame), %d frames, %.0f s' % (
            d, run['candidate'], run['observation_offset_ticks'], run['observation_offset_ticks'] / 896040, run['executed_frames'], run['seconds']))
        print('   hits %d, fallbacks %d, seam entries %d completions %d seam-deadlines %d' % (
            stats['candidate_hits'], stats['fallbacks'], stats['seam_entries'], stats['seam_completions'], stats['seam_deadline_fallbacks']))
        reasons = stats['fallback_reasons']
        unsupported = sum(v for k, v in reasons.items() if k.startswith('unsupported'))
        print('   fallback reasons: scheduler admission %d, seam deadline %d, unsupported domain %d, other %d' % (
            reasons.get('scheduler admission', 0), reasons.get('seam deadline', 0), unsupported,
            sum(v for k, v in reasons.items() if k not in ('scheduler admission', 'seam deadline') and not k.startswith('unsupported'))))
        causes = Counter(r['cause'] for r in refusals)
        print('   atomic refusals classified: %s (sum %d)' % (dict(causes), sum(causes.values())))
        seam = Counter((r['cause'], r['in_seam']) for r in refusals)
        print('   by (cause, inside a seam suffix): %s' % {('%s%s' % (c, ' [seam suffix]' if s else '')): n for (c, s), n in seam.items()})
        by_gate = {}
        for r in refusals:
            by_gate.setdefault(r['gate'], Counter())[r['cause']] += 1
        print('   by gate:')
        for g, c in sorted(by_gate.items(), key=lambda kv: -sum(kv[1].values())):
            print('      %s: %s' % (g, dict(c)))
        for cause in ('deadline', 'vblank-in-span', 'engine-other'):
            offs = sorted(r['offset'] for r in refusals if r['cause'] == cause)
            if offs:
                hist = Counter(round(o, 1) for o in offs)
                print('   %s frame-offset histogram (0.1 bins): %s' % (cause, dict(sorted(hist.items()))))
        margins = sorted(r['margin_cycles'] for r in refusals if r['cause'] == 'engine-other')
        if margins:
            print('   engine-other: cycles from plan end to the next VBlank IRQ: min %d, p10 %d, median %d, max %d' % (
                margins[0], margins[len(margins) // 10], margins[len(margins) // 2], margins[-1]))
        vb = sorted(r['margin_cycles'] for r in refusals if r['cause'] == 'vblank-in-span')
        if vb:
            print('   vblank-in-span: margin min %d max %d (<= 64 by definition); plan cycles min %d max %d' % (
                vb[0], vb[-1], min(r['cycles'] for r in refusals if r['cause'] == 'vblank-in-span'), max(r['cycles'] for r in refusals if r['cause'] == 'vblank-in-span')))
        dl = [r for r in refusals if r['cause'] == 'deadline']
        if dl:
            print('   deadline: plan cycles min %d median %d max %d; deadline distance min %d median %d max %d' % (
                min(r['cycles'] for r in dl), sorted(r['cycles'] for r in dl)[len(dl) // 2], max(r['cycles'] for r in dl),
                min(r['deadline_cycles'] for r in dl), sorted(r['deadline_cycles'] for r in dl)[len(dl) // 2], max(r['deadline_cycles'] for r in dl)))
        nodes = Counter(r['node'] for r in refusals)
        print('   refusals by recording: %s' % dict(nodes))


if __name__ == '__main__':
    main(sys.argv[1:])
