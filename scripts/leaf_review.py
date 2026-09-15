"""leaf_review: the supervision gate for one recovered leaf.

    python scripts/leaf_review.py [--artifacts DIR] [--suite MODULE ...] [--no-tests]

Runs, in order, the checks a reviewer applies to a grinder's uncommitted leaf
and prints one OK/FAIL line per check:

    diff        what changed under src and tests, and any untracked files
    guards      production lines that removed a ``raise UnsupportedCandidate``
                (an arm was widened) and test lines that removed an ``assert``
    gates       the lifecycle gate set is unchanged and within native capacity
    changed     pytest on every new or modified test module
    suites      pytest on the focused contact family suites
    verify      ``verify_status`` of --artifacts (PASS with current receipts)

It changes nothing itself.  Exit status 1 when any check fails.  The full
suite and the cold comparison are separate milestone gates.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from pathlib import Path as _Path

# Judge the checkout, never an installed wheel: the checkout's src wins.
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))

ROOT = Path(__file__).resolve().parents[1]
FOCUSED = ['tests/test_contact_family.py', 'tests/test_contact_type55.py', 'tests/test_contact_type20.py',
           'tests/test_contact_scan.py', 'tests/test_contact_step.py', 'tests/test_contact_step_sound.py',
           'tests/test_collection_dispatch.py', 'tests/test_recovery.py', 'tests/test_pathfacts.py']
PINNED_GATES = 62


def _git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout


def _environment():
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(str(ROOT / part) for part in ('src', 'scripts', 'tests'))
    env.setdefault('GENESIS_NATIVE_LIBRARY', str(ROOT / 'build' / 'libgenesis_native.dll'))
    return env


def _net_removed(diff, needle):
    """Removed lines containing needle that were not re-added elsewhere (a move is not a removal)."""
    removed, added = [], []
    for line in diff.splitlines():
        if line.startswith('---') or line.startswith('+++') or needle not in line:
            continue
        if line.startswith('-'):
            removed.append(line[1:].strip())
        elif line.startswith('+'):
            added.append(line[1:].strip())
    for text in added:
        if text in removed:
            removed.remove(text)
    return removed


def _pytest(modules):
    command = [sys.executable, '-m', 'pytest', *modules, '-q', '-p', 'no:cacheprovider']
    result = subprocess.run(command, cwd=ROOT, env=_environment(), capture_output=True, text=True, check=False)
    tail = [line for line in result.stdout.splitlines() if line.strip()][-1:] or ['(no output)']
    return result.returncode == 0, tail[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--artifacts', default=None, help='verification directory to classify')
    parser.add_argument('--suite', action='append', default=None, help='focused test modules (default: contact family)')
    parser.add_argument('--no-tests', action='store_true')
    args = parser.parse_args(argv)
    failures = []

    def report(name, ok, detail):
        print('%-8s %s  %s' % (name, 'OK  ' if ok else 'FAIL', detail))
        if not ok:
            failures.append(name)

    stat = _git('diff', '--stat', '--', 'src', 'tests').strip().splitlines()
    untracked = [line[3:] for line in _git('status', '--short').splitlines() if line.startswith('??')]
    report('diff', True, (stat[-1].strip() if stat else 'no tracked changes under src/tests')
           + ('; untracked: ' + ', '.join(untracked) if untracked else ''))

    removed_guards = _net_removed(_git('diff', '--', 'src'), 'raise UnsupportedCandidate')
    removed_asserts = _net_removed(_git('diff', '--', 'tests'), 'assert')
    report('guards', not removed_guards and not removed_asserts,
           '%d production refusals removed, %d test assertions removed' % (len(removed_guards), len(removed_asserts)))
    for line in removed_guards + removed_asserts:
        print('         - ' + line[:110])

    probe = subprocess.run([sys.executable, '-c',
                            'from aladdin_sega.recovery import Candidate; g = Candidate("lifecycle").gate_pcs; '
                            'print(len(g), len(set(g)))'],
                           cwd=ROOT, env=_environment(), capture_output=True, text=True, check=False)
    try:
        count, distinct = map(int, probe.stdout.split())
        report('gates', count == distinct == PINNED_GATES and count <= 64,
               '%d lifecycle gates (pinned %d, native limit 64)' % (count, PINNED_GATES))
    except ValueError:
        report('gates', False, 'could not import the candidate: ' + probe.stderr.strip()[-200:])

    if not args.no_tests:
        changed = sorted({line.split()[-1] for line in _git('status', '--short', 'tests').splitlines()
                          if line.split()[-1].endswith('.py')})
        if changed:
            ok, tail = _pytest(changed)
            report('changed', ok, '%s: %s' % (' '.join(changed), tail))
        else:
            report('changed', True, 'no new or modified test modules')
        suites = args.suite or [module for module in FOCUSED if (ROOT / module).exists()]
        ok, tail = _pytest(suites)
        report('suites', ok, tail)

    if args.artifacts:
        sys.path.insert(0, str(ROOT / 'scripts'))
        import verify_status
        status, reason = verify_status.classify(args.artifacts)
        report('verify', status == 'PASS', '%s: %s' % (status, reason))

    print('leaf review: %s' % ('PASS' if not failures else 'FAIL (' + ', '.join(failures) + ')'))
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
