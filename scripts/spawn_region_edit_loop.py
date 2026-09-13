"""Verify a disposable spawn-region semantic edit changes a focused verdict."""
from __future__ import annotations

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('witness', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    native = ROOT / 'build/libaladdin_native.dll'
    native_hash = hashlib.sha256(native.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aladdin-spawn-edit-') as temporary:
        source = Path(temporary) / 'aladdin_sega'
        shutil.copytree(ROOT / 'src/aladdin_sega', source,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        environment = dict(os.environ, PYTHONPATH=temporary, ALADDIN_NATIVE_LIBRARY=str(native))

        def compare(label):
            started = time.perf_counter()
            result = subprocess.run([sys.executable, '-m', 'aladdin_sega', 'compare',
                                     str(args.witness.resolve()), '--candidate', 'lifecycle',
                                     '--diagnostics', '--output', str((args.output / label).resolve())],
                                    env=environment, text=True, capture_output=True, timeout=30)
            payload = json.loads(result.stdout)
            return {'returncode': result.returncode, 'status': payload['status'],
                    'wall_seconds': time.perf_counter() - started,
                    'report': str((args.output / label / 'comparison.json').resolve())}

        before = compare('before')
        lifecycle = source / 'game/objects/lifecycle.py'
        code = lifecycle.read_text()
        needle = '(clear_address, 0)]'
        if code.count(needle) != 1:
            raise RuntimeError('spawn edit loop no longer identifies the indexed-clear effect')
        lifecycle.write_text(code.replace(needle, '(clear_address, 1)]'))
        after = compare('after')
    unchanged = hashlib.sha256(native.read_bytes()).hexdigest() == native_hash
    passed = before['status'] == 'PASS' and after['status'] in {'DIVERGENCE', 'CANDIDATE_ERROR'} and unchanged
    report = {'status': 'PASS' if passed else 'FAIL', 'before': before, 'after': after,
              'edit': 'spawn-region indexed clear byte 0 -> 1 in a disposable source copy',
              'native_sha256': native_hash, 'native_unchanged': unchanged,
              'native_builds': 0, 'package_installs': 0}
    (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
