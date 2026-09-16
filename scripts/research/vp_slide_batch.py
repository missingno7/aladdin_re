"""vp_slide_batch: run vp_slide over the regions the first report left "not established" (and any others named).

    python scripts/research/vp_slide_batch.py --only 002806,004150,00364C,010A14,010332,00BA8E,00932C,014A3C
                                              [--per-dir 2] [--ticks 20] [--positions 4] [--out artifacts/gods/research/slide-vp]

For every ``artifacts/gods/evidence/census-<PC>*`` directory of a named region, takes up to
``--per-dir`` fixtures (the first path classes, `-p0`, `-p1`, ...) and runs ``vp_slide.main`` on
each in its own process (one Machine per process).  Writes one JSON per fixture and summary.txt/json.
Research tooling; read-only on the evidence.
"""
import argparse
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--only', required=True)
    p.add_argument('--per-dir', type=int, default=2)
    p.add_argument('--ticks', type=int, default=20)
    p.add_argument('--positions', type=int, default=4)
    p.add_argument('--out', default='artifacts/gods/research/slide-vp')
    a = p.parse_args(argv)
    only = set(a.only.split(','))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for d in sorted(glob.glob('artifacts/gods/evidence/census-*')):
        m = re.match(r'.*census-([0-9A-F]{6})', d)
        if not m or m.group(1) not in only:
            continue
        fixtures = sorted(glob.glob(d + '/*-p*.state'), key=lambda f: (len(Path(f).stem), Path(f).stem))[:a.per_dir]
        for f in fixtures:
            js = out / (Path(d).name + '--' + Path(f).stem + '.json')
            r = subprocess.run([sys.executable, str(ROOT / 'scripts/research/vp_slide.py'), f, '--ticks', str(a.ticks), '--positions', str(a.positions), '--json', str(js)],
                               capture_output=True, text=True)
            if r.returncode:
                err = (r.stderr.strip().splitlines() or [r.stdout[-300:]])[-1]
                print('%s %s: ERROR %s' % (m.group(1), Path(f).name, err))
                summary.append({'region': m.group(1), 'dir': Path(d).name, 'fixture': Path(f).name, 'error': err})
                continue
            rep = json.loads(js.read_text())
            runs = [x for x in rep['runs'] if x.get('accepted')]
            verdicts = [x['verdict'] for x in runs]
            line = {'region': m.group(1), 'dir': Path(d).name, 'fixture': Path(f).name, 'region_steps': rep['A']['region_steps'],
                    'entry_offset': round(rep['entry_offset'], 4), 'cycles_to_vblank': rep['cycles_to_vblank'],
                    'landings': [x['landing_step'] for x in runs], 'verdicts': verdicts, 'refused': sum(1 for x in rep['runs'] if not x.get('accepted')),
                    'sound_block_moved': [not x['sound_block_same'] for x in runs],
                    'first_diffs': [x['first_future_diff'] for x in runs if x['first_future_diff']],
                    'exit_live_diffs': [x['exit_live_diff'] for x in runs if x['exit_live_diff']]}
            summary.append(line)
            print('%s %-34s %-28s steps %4d entry@%.3f vblank in %6d cyc landings %-22s %s%s' % (
                m.group(1), Path(d).name, Path(f).name, rep['A']['region_steps'], rep['entry_offset'], rep['cycles_to_vblank'], line['landings'],
                'EQUIVALENT' if verdicts and all(v == 'EQUIVALENT' for v in verdicts) else 'DIFFERS' if verdicts else 'no accepted burn',
                '  [sound block differs at exit]' if any(line['sound_block_moved']) else ''), flush=True)
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))
    with (out / 'summary.txt').open('w') as fh:
        for s in summary:
            if 'error' in s:
                fh.write('%s %s %s ERROR %s\n' % (s['region'], s['dir'], s['fixture'], s['error']))
            else:
                fh.write('%s %s %s steps %d entry@%.3f landings %s %s%s\n' % (
                    s['region'], s['dir'], s['fixture'], s['region_steps'], s['entry_offset'], s['landings'],
                    'EQUIVALENT' if s['verdicts'] and all(v == 'EQUIVALENT' for v in s['verdicts']) else 'DIFFERS' if s['verdicts'] else 'no accepted burn',
                    ' [sound block differs at exit]' if any(s['sound_block_moved']) else ''))


if __name__ == '__main__':
    main()
