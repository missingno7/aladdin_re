"""verify_status reads verifier state without inferring PASS from silence."""
import json
import os

import verify_status
from aladdin_sega.receipt import execution_receipt


def write(tmp_path, report):
    (tmp_path / 'comparison.json').write_text(json.dumps(report), encoding='utf-8')
    return tmp_path


def test_no_receipt_is_no_evidence_unless_a_process_is_alive(tmp_path):
    assert verify_status.classify(tmp_path)[0] == 'NO_EVIDENCE'
    assert verify_status.classify(tmp_path, pid=os.getpid())[0] == 'RUNNING'
    (tmp_path / 'launcher.pid').write_text(str(os.getpid()))
    assert verify_status.classify(tmp_path)[0] == 'RUNNING'
    (tmp_path / 'launcher.pid').write_text('999999999')
    assert verify_status.classify(tmp_path)[0] == 'NO_EVIDENCE'


def test_worker_timeouts_are_timeouts_even_in_the_old_candidate_error_form(tmp_path):
    status, reason = verify_status.classify(write(tmp_path, {
        'status': 'TIMEOUT', 'error': {'worker': 'candidate', 'detail': 'worker exceeded 120 seconds'}}))
    assert status == 'TIMEOUT' and 'candidate worker' in reason
    status, reason = verify_status.classify(write(tmp_path, {
        'status': 'CANDIDATE_ERROR', 'error': {'worker': 'candidate', 'detail': 'worker exceeded 120 seconds'}}))
    assert status == 'TIMEOUT'
    status, _ = verify_status.classify(write(tmp_path, {
        'status': 'CANDIDATE_ERROR', 'error': {'worker': 'candidate', 'detail': "No module named 'x'"}}))
    assert status == 'DEPENDENCY_FAILURE'
    status, reason = verify_status.classify(write(tmp_path, {
        'status': 'CANDIDATE_ERROR', 'error': {'worker': 'candidate', 'detail': 'worker returned a nonzero exit status'}}))
    assert status == 'ERROR' and 'nonzero' in reason


def test_divergence_and_not_exercised_are_named(tmp_path):
    status, reason = verify_status.classify(write(tmp_path, {
        'status': 'DIVERGENCE', 'comparison': {'equal': False, 'first_difference': {
            'node': 'n', 'reference': {'frame': 4019, 'state_sha256': 'a'}, 'candidate': {'frame': 4019, 'state_sha256': 'b'}}}}))
    assert status == 'DIVERGENCE' and 'frame 4019' in reason
    assert verify_status.classify(write(tmp_path, {'status': 'NOT_EXERCISED'}))[0] == 'NOT_EXERCISED'


def test_pass_requires_current_source_and_native_receipts(tmp_path):
    receipt = execution_receipt()
    report = {'status': 'PASS', 'workers': 'parallel',
              'candidate_receipt': {'receipt': receipt, 'executed_frames': 10, 'restores': 0,
                                    'candidate_stats': {'fallbacks': 3}}}
    status, reason = verify_status.classify(write(tmp_path, report))
    assert status == 'PASS' and 'parallel workers' in reason and 'fallbacks 3' in reason
    stale = json.loads(json.dumps(report))
    module = next(iter(stale['candidate_receipt']['receipt']['python_modules_sha256']))
    stale['candidate_receipt']['receipt']['python_modules_sha256'][module] = '0' * 64
    status, reason = verify_status.classify(write(tmp_path, stale))
    assert status == 'STALE_EVIDENCE' and module in reason
    stale = json.loads(json.dumps(report))
    stale['candidate_receipt']['receipt']['native_binary_sha256'] = '0' * 64
    assert verify_status.classify(write(tmp_path, stale)) == (
        'STALE_EVIDENCE', 'PASS was recorded for different source/native: changed [] native')


def test_cli_exit_status_only_accepts_pass_or_running(tmp_path, capsys):
    assert verify_status.main([str(tmp_path)]) == 1
    assert capsys.readouterr().out.startswith('NO_EVIDENCE: ')
    assert verify_status.main([str(tmp_path), '--pid', str(os.getpid())]) == 0
