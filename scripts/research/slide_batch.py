"""slide_batch: run vblank_slide over one fixture per census directory (an interrupted one when there is one).

    python scripts/research/slide_batch.py [--ticks 20] [--positions 4] [--out artifacts/gods/research/slide-batch]
                                           [--only 0018C8,001164,...]

Picks, for every ``artifacts/gods/evidence/census-<PC>*`` directory, the first
retained fixture whose original trace carries an interrupt and the first
that does not, and runs ``vblank_slide.main`` on each, writing one JSON per
fixture and a summary table.  Research tooling; read-only on the evidence.
"""
import argparse
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import pathfacts
from gods_sega.profile import GODS


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ticks', type=int, default=20)
    p.add_argument('--positions', type=int, default=4)
    p.add_argument('--out', default='artifacts/gods/research/slide-batch')
    p.add_argument('--only', default=None)
    p.add_argument('--per-dir', type=int, default=1, help='clean fixtures per directory (interrupted ones are always taken, up to 2)')
    a = p.parse_args(argv)
    only = set(a.only.split(',')) if a.only else None
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dirs = sorted(glob.glob('artifacts/gods/evidence/census-*'))
    chosen = []
    for d in dirs:
        m = re.match(r'.*census-([0-9A-F]{6})', d)
        if not m or (only and m.group(1) not in only):
            continue
        interrupted, clean = [], []
        for f in sorted(glob.glob(d + '/*-p*.state')):
            try:
                facts = pathfacts.trace(Path(f).read_bytes(), game=GODS, detail=False, track_ram=False)
            except Exception as error:  # noqa: BLE001 - a fixture the tracer cannot follow is reported, not fatal
                print('skip %s: %s' % (f, error))
                continue
            (interrupted if facts['interrupts_during_trace'] else clean).append(f)
            if len(interrupted) >= 2 and len(clean) >= a.per_dir:
                break
        chosen += [(m.group(1), f, 'interrupted') for f in interrupted[:2]] + [(m.group(1), f, 'clean') for f in clean[:a.per_dir]]
    summary = []
    for region, f, kind in chosen:
        js = out / (Path(f).stem + '.json')
        r = subprocess.run([sys.executable, str(ROOT / 'scripts/research/vblank_slide.py'), f, '--ticks', str(a.ticks),
                            '--positions', str(a.positions), '--json', str(js)], capture_output=True, text=True)
        if r.returncode:
            print('%s %s: ERROR %s' % (region, Path(f).name, r.stderr.strip().splitlines()[-1] if r.stderr else r.stdout))
            summary.append({'region': region, 'fixture': f, 'kind': kind, 'error': r.stderr[-400:]})
            continue
        rep = json.loads(js.read_text())
        runs = [x for x in rep['runs'] if x.get('accepted')]
        verdicts = [x['verdict'] for x in runs]
        line = {'region': region, 'fixture': Path(f).name, 'kind': kind, 'region_steps': rep['A']['region_steps'],
                'landings': [x['landing_step'] for x in runs], 'verdicts': verdicts,
                'sound_block_moved': [not x['sound_block_same'] for x in runs]}
        summary.append(line)
        print('%s %-28s %-11s steps %4d landings %-24s %s%s' % (
            region, Path(f).name, kind, rep['A']['region_steps'], line['landings'],
            'EQUIVALENT' if verdicts and all(v == 'EQUIVALENT' for v in verdicts) else 'DIFFERS' if verdicts else 'no accepted burn',
            '  [sound block differs at exit]' if any(line['sound_block_moved']) else ''))
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
