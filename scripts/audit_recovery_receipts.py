"""Audit completed comparison files against the current source and native binary.

Read-only: missing/incomplete/stale evidence fails; this does not poll workers or
turn a summary into qualification. Pass explicit comparison files, never a glob
that could silently omit a required replay.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = ('state_sha256', 'frame_sha256', 'pcm_sha256', 'tick', 'pc',
            'm68k_cycles', 'm68k_instructions')


def audit_comparison(report, modules, native_hash, replay_hash=None):
    errors = []
    if report.get('status') != 'PASS' or report.get('comparison', {}).get('equal') is not True:
        errors.append('comparison is not a completed PASS')
    if replay_hash is not None and report.get('replay_sha256') != replay_hash:
        errors.append('replay identity mismatch')
    original, candidate = report.get('reference', {}), report.get('candidate_receipt', {})
    for key in TERMINAL:
        if key not in original or key not in candidate or original[key] != candidate[key]:
            errors.append('missing or unequal terminal ' + key)
    for name, side in [('reference', original), ('candidate', candidate)]:
        receipt = side.get('receipt', {})
        if receipt.get('python_modules_sha256') != modules:
            errors.append(name + ' source identity mismatch')
        if receipt.get('native_binary_sha256') != native_hash:
            errors.append(name + ' native identity mismatch')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('comparisons', type=Path, nargs='+')
    parser.add_argument('--replay', type=Path, action='append', required=True,
                        help='Expected recording for each comparison, in the same order; repeat per file')
    parser.add_argument('--native', type=Path, default=ROOT / 'build/libaladdin_native.dll')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if len(args.replay) != len(args.comparisons):
        parser.error('provide exactly one --replay per comparison')
    source = ROOT / 'src/aladdin_sega'
    modules = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in source.rglob('*.py')}
    native_hash = hashlib.sha256(args.native.read_bytes()).hexdigest()
    rows = []
    for path, replay in zip(args.comparisons, args.replay):
        try:
            errors = audit_comparison(json.loads(path.read_text()), modules, native_hash,
                                      hashlib.sha256(replay.read_bytes()).hexdigest())
        except (OSError, ValueError, TypeError, AttributeError) as error:
            errors = ['unreadable or incomplete comparison: ' + str(error)]
        rows.append({'comparison': str(path), 'errors': errors})
    report = {'status': 'FAIL' if any(r['errors'] for r in rows) else 'PASS',
              'modules': modules, 'native_sha256': native_hash, 'cases': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
