"""Disposable Python edit -> strict cold-history verdict, without rebuilding."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, required=True)
    parser.add_argument('--node', default='main')
    parser.add_argument('--candidate', default='lifecycle')
    parser.add_argument('--source', default='game/objects/lifecycle.py')
    parser.add_argument('--needle', required=True)
    parser.add_argument('--replacement', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    native = ROOT / 'build/libaladdin_native.dll'
    before_hash = hashlib.sha256(native.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix='aladdin-history-edit-') as temporary:
        source = Path(temporary) / 'aladdin_sega'
        shutil.copytree(ROOT / 'src/aladdin_sega', source, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        target = (source / args.source).resolve()
        target.relative_to(source.resolve())
        env = dict(os.environ, PYTHONPATH=temporary, PYTHONDONTWRITEBYTECODE='1', ALADDIN_NATIVE_LIBRARY=str(native))
        for label in ('baseline', 'mutated'):
            if label == 'mutated':
                text = target.read_text()
                if text.count(args.needle) != 1:
                    raise ValueError('Mutation must match exactly once')
                target.write_text(text.replace(args.needle, args.replacement))
            start = time.perf_counter()
            out = (args.output / label).resolve()
            result = subprocess.run([sys.executable, '-m', 'aladdin_sega', 'history-verify', args.node,
                                     '--history', str(args.history.resolve()), '--candidate', args.candidate,
                                     '--output', str(out)], env=env, capture_output=True, text=True, timeout=180)
            report = json.loads((out / 'comparison.json').read_text())
            rows.append({'case': label, 'status': report['status'], 'seconds': time.perf_counter()-start,
                         'returncode': result.returncode})
    unchanged = hashlib.sha256(native.read_bytes()).hexdigest() == before_hash
    passed = rows[0]['status'] == 'PASS' and rows[1]['status'] in {'DIVERGENCE', 'CANDIDATE_ERROR'} and unchanged
    report = {'status': 'PASS' if passed else 'FAIL', 'cases': rows, 'native_unchanged': unchanged,
              'native_builds': 0, 'package_installs': 0}
    (args.output / 'result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
