"""Run the existing no-build edit check with one explicit semantic mutation."""
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


def check_edit(witness: Path, output: Path, *, needle: str, replacement: str, description: str) -> int:
    native = ROOT / 'build/libaladdin_native.dll'
    native_hash = hashlib.sha256(native.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aladdin-spawn-edit-') as temporary:
        source = Path(temporary) / 'aladdin_sega'
        shutil.copytree(ROOT / 'src/aladdin_sega', source,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        environment = dict(os.environ, PYTHONPATH=temporary, ALADDIN_NATIVE_LIBRARY=str(native),
                           PYTHONDONTWRITEBYTECODE='1')

        def compare(label):
            started = time.perf_counter()
            result = subprocess.run([sys.executable, '-m', 'aladdin_sega', 'compare',
                                     str(witness.resolve()), '--candidate', 'lifecycle',
                                     '--diagnostics', '--output', str((output / label).resolve())],
                                    env=environment, text=True, capture_output=True, timeout=30)
            payload = json.loads(result.stdout)
            return {'returncode': result.returncode, 'status': payload['status'],
                    'wall_seconds': time.perf_counter() - started,
                    'report': str((output / label / 'comparison.json').resolve())}

        before = compare('before')
        lifecycle = source / 'game/objects/lifecycle.py'
        code = lifecycle.read_text()
        if code.count(needle) != 1:
            raise RuntimeError('semantic edit must match exactly once')
        lifecycle.write_text(code.replace(needle, replacement))
        after = compare('after')
    unchanged = hashlib.sha256(native.read_bytes()).hexdigest() == native_hash
    passed = before['status'] == 'PASS' and after['status'] in {'DIVERGENCE', 'CANDIDATE_ERROR'} and unchanged
    report = {'status': 'PASS' if passed else 'FAIL', 'before': before, 'after': after,
              'edit': description,
              'native_sha256': native_hash, 'native_unchanged': unchanged,
              'native_builds': 0, 'package_installs': 0}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if passed else 1


def edit_cli(*, needle, replacement, description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('witness', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    return check_edit(args.witness, args.output, needle=needle,
                      replacement=replacement, description=description)
