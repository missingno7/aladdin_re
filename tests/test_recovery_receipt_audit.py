"""Reject stale and incomplete evidence without needing ROM/local recordings."""
import copy
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('receipt_audit', Path(__file__).parents[1] / 'scripts/audit_recovery_receipts.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def valid():
    side = {key: 'same' for key in audit.TERMINAL}
    side['receipt'] = {'python_modules_sha256': {'game.py': 'source'},
                       'native_binary_sha256': 'native'}
    return {'status': 'PASS', 'comparison': {'equal': True}, 'replay_sha256': 'replay',
            'reference': copy.deepcopy(side), 'candidate_receipt': copy.deepcopy(side)}


def check(report):
    return audit.audit_comparison(report, {'game.py': 'source'}, 'native', 'replay')


def test_complete_receipt_passes():
    assert not check(valid())


@pytest.mark.parametrize('key', audit.TERMINAL)
def test_missing_on_both_sides_is_not_equality(key):
    report = valid()
    for side in ['reference', 'candidate_receipt']:
        del report[side][key]
    assert check(report)


@pytest.mark.parametrize('side', ['reference', 'candidate_receipt'])
@pytest.mark.parametrize('field', ['python_modules_sha256', 'native_binary_sha256'])
def test_stale_identity_rejected(side, field):
    report = valid(); report[side]['receipt'][field] = 'stale'
    assert check(report)


def test_summary_pass_does_not_override_divergence():
    report = valid(); report['comparison']['equal'] = False
    assert check(report)


def test_wrong_replay_rejected():
    report = valid(); report['replay_sha256'] = 'other'
    assert check(report)


@pytest.mark.parametrize('wrong_replay', [False, True])
def test_cli_enforces_supplied_replay(tmp_path, monkeypatch, wrong_replay):
    import hashlib
    import json
    root = tmp_path / 'repo'
    (root / 'src/aladdin_sega').mkdir(parents=True)
    (root / 'src/aladdin_sega/game.py').write_bytes(b'source')
    native = tmp_path / 'native.dll'; native.write_bytes(b'native')
    replay = tmp_path / 'input.alreplay'; replay.write_bytes(b'input')
    report = valid()
    report['replay_sha256'] = hashlib.sha256(b'wrong' if wrong_replay else b'input').hexdigest()
    for side in ['reference', 'candidate_receipt']:
        report[side]['receipt'] = {
            'python_modules_sha256': {'game.py': hashlib.sha256(b'source').hexdigest()},
            'native_binary_sha256': hashlib.sha256(b'native').hexdigest()}
    comparison = tmp_path / 'comparison.json'; comparison.write_text(json.dumps(report))
    monkeypatch.setattr(audit, 'ROOT', root)
    monkeypatch.setattr('sys.argv', ['audit', str(comparison), '--replay', str(replay),
                                    '--native', str(native), '--output', str(tmp_path / 'audit.json')])
    assert audit.main() == int(wrong_replay)
