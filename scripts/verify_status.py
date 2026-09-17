"""verify_status: one word about a cold-history verification directory.

    python scripts/verify_status.py ARTIFACT_DIR [--pid PID]

Prints exactly one classification and a short reason:

    RUNNING             a launcher/worker PID is alive and no receipt exists yet
    PASS                comparison.json says PASS and its receipts match current source and native binary
    STALE_EVIDENCE      comparison.json exists but its source/native receipts differ from the checkout now
    DIVERGENCE          comparison.json says DIVERGENCE (first failing frame printed)
    TIMEOUT             a worker exceeded its watchdog (not a divergence; rerun with a longer --timeout-seconds)
    DEPENDENCY_FAILURE  a worker could not start (missing DLL/ROM/module)
    NOT_EXERCISED       equal, but the candidate never admitted a plan
    ERROR               the comparator or a worker failed; detail printed
    NO_EVIDENCE         no comparison.json and no live process: nothing has been verified here

Exit status is 0 for PASS and RUNNING, 1 otherwise.  This is read-only: it
never restarts, kills or launches a verifier.  It is the only way a grinder
should read verifier state; do not infer PASS from a quiet process.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from pathlib import Path as _Path

# Judge the checkout, never an installed wheel: the checkout's src wins.
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))

_DEPENDENCY_TOKENS = ('Native library', 'DLL load', 'ImportError', 'No module named', 'MISSING_INPUT')


def pid_alive(pid):
    if not pid:
        return False
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            kernel32.CloseHandle(handle)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def current_receipt(game_id):
    """The receipt a PASS must still match: the shared modules and, when the report names a game, its own."""
    from genesis_re.games import game as select_game
    from genesis_re.receipt import execution_receipt
    receipt = execution_receipt(None if game_id is None else select_game(game_id))
    return receipt['python_modules_sha256'], receipt['native_binary_sha256']


def _worker_error(report):
    error = report.get('error') or {}
    if isinstance(error, dict):
        return error.get('worker', '?'), str(error.get('detail', ''))
    return '?', str(error)


def classify(directory, pid=None):
    """Return ``(status, reason)`` for one verification output directory.

    A ``tree.json`` (scripts/tree_verify.py: one cold run per leaf, concurrently)
    is the set of its leaf directories: PASS only when every leaf classifies as
    PASS with current receipts; otherwise the first leaf's other status.
    """
    directory = Path(directory)
    tree = directory / 'tree.json'
    if tree.exists() and not (directory / 'comparison.json').exists():
        summary = json.loads(tree.read_text(encoding='utf-8'))
        statuses = [(leaf['leaf'][:12], classify(leaf['directory'])) for leaf in summary['leaves']]
        failing = [(leaf, status, reason) for leaf, (status, reason) in statuses if status != 'PASS']
        if failing:
            leaf, status, reason = failing[0]
            return status, 'leaf %s: %s' % (leaf, reason)
        fallbacks = 0
        for leaf in summary['leaves']:
            report = json.loads((Path(leaf['directory']) / 'comparison.json').read_text(encoding='utf-8'))
            stats = (report.get('candidate_receipt') or {}).get('candidate_stats') or {}
            fallbacks += stats.get('fallbacks', 0) or 0
        return 'PASS', 'frames %s, %d leaves cold, fallbacks %d, %s s, current receipts' % (
            summary.get('executed_frames'), len(summary['leaves']), fallbacks, summary.get('seconds'))
    comparison = directory / 'comparison.json'
    if not comparison.exists():
        if pid_alive(pid):
            return 'RUNNING', 'pid %s is alive; comparison.json is written only at completion' % pid
        pid_file = directory / 'launcher.pid'
        if pid_file.exists():
            launcher = pid_file.read_text().strip()
            if pid_alive(launcher):
                return 'RUNNING', 'launcher pid %s is alive; comparison.json is written only at completion' % launcher
        return 'NO_EVIDENCE', 'no comparison.json in %s and no live process' % directory
    report = json.loads(comparison.read_text(encoding='utf-8'))
    status = report.get('status')
    workers = report.get('workers', 'sequential')
    if status in ('TIMEOUT', 'DEPENDENCY_FAILURE'):
        worker, detail = _worker_error(report)
        return status, '%s worker: %s' % (worker, detail[:200])
    if status in ('ERROR', 'CANDIDATE_ERROR'):
        worker, detail = _worker_error(report)
        # Older comparators reported a candidate watchdog expiry as
        # CANDIDATE_ERROR; keep the distinction the grinder needs.
        if 'exceeded' in detail and 'seconds' in detail:
            return 'TIMEOUT', '%s worker: %s' % (worker, detail[:160])
        if any(token in detail for token in _DEPENDENCY_TOKENS):
            return 'DEPENDENCY_FAILURE', '%s worker: %s' % (worker, detail[:200])
        if 'Implementation changed' in detail or 'receipt mismatch' in detail:
            return 'STALE_EVIDENCE', detail[:200]
        return 'ERROR', '%s worker: %s' % (worker, detail[:300]) if worker != '?' else detail[:300]
    if status == 'DIVERGENCE':
        first = report.get('comparison', {}).get('first_difference') or {}
        reference = first.get('reference') or {}
        return 'DIVERGENCE', 'first difference at frame %s: %s' % (
            reference.get('frame', '?'), json.dumps(first)[:300])
    if status == 'NOT_EXERCISED':
        return 'NOT_EXERCISED', 'streams equal but the candidate admitted nothing'
    if status == 'PASS':
        receipt = report.get('candidate_receipt', {}).get('receipt', {})
        modules, native = current_receipt(report.get('game', receipt.get('game')))
        recorded = receipt.get('python_modules_sha256', {})
        changed = sorted(k for k in set(modules) | set(recorded) if modules.get(k) != recorded.get(k))
        native_changed = receipt.get('native_binary_sha256') != native
        if changed or native_changed:
            return 'STALE_EVIDENCE', 'PASS was recorded for different source/native: changed %s%s' % (
                changed[:6], ' native' if native_changed else '')
        candidate = report.get('candidate_receipt', {})
        stats = candidate.get('candidate_stats', {})
        return 'PASS', 'frames %s, restores %s, fallbacks %s, %s workers, current receipts' % (
            candidate.get('executed_frames'), candidate.get('restores'), stats.get('fallbacks'), workers)
    return 'ERROR', 'unknown status %r' % status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('directory')
    parser.add_argument('--pid', default=None)
    args = parser.parse_args(argv)
    status, reason = classify(args.directory, args.pid)
    print('%s: %s' % (status, reason))
    return 0 if status in ('PASS', 'RUNNING') else 1


if __name__ == '__main__':
    sys.exit(main())
