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
    parser.add_argument('--game', required=True)
    parser.add_argument('--history', type=Path, default=None, help='history store; default history/<game>')
    parser.add_argument('--node', default='main')
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--source', required=True, help="module path below the game's package, e.g. game/objects/lifecycle.py")
    parser.add_argument('--needle', required=True)
    parser.add_argument('--replacement', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    native = ROOT / 'build/libgenesis_native.dll'
    before_hash = hashlib.sha256(native.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    sys.path.insert(0, str(ROOT / 'src'))
    from genesis_re.games import game as select_game
    game = select_game(args.game)
    history = (args.history or ROOT / game.history_path()).resolve()
    with tempfile.TemporaryDirectory(prefix='genesis-re-history-edit-') as temporary:
        # The whole source tree, so the mutated game package and the shared layer are what the workers import.
        for package in sorted(p.name for p in (ROOT / 'src').iterdir() if p.is_dir() and not p.name.startswith('__')):
            shutil.copytree(ROOT / 'src' / package, Path(temporary) / package, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        source = Path(temporary) / game.package
        target = (source / args.source).resolve()
        target.relative_to(source.resolve())
        env = dict(os.environ, PYTHONPATH=temporary, PYTHONDONTWRITEBYTECODE='1', GENESIS_NATIVE_LIBRARY=str(native))
        for label in ('baseline', 'mutated'):
            if label == 'mutated':
                text = target.read_text()
                if text.count(args.needle) != 1:
                    raise ValueError('Mutation must match exactly once')
                target.write_text(text.replace(args.needle, args.replacement))
            start = time.perf_counter()
            out = (args.output / label).resolve()
            result = subprocess.run([sys.executable, '-m', 'genesis_re', 'history-verify', args.node, '--game', game.id,
                                     '--history', str(history), '--candidate', args.candidate,
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
