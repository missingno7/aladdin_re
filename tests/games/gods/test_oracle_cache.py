"""The oracle cache: the original's stream of a history is executed once per oracle key and reused.

`compare_history` runs the reference worker only when no validated stream
exists under the key (shared modules, native binary, profile, observation
instant, cache contract, ROM, the history's inputs, the mode); a later
comparison of any candidate runs only its own worker and validates the
cached stream's shared-module and native receipts.  The candidate's
receipt is always fresh.  A fake runner stands in for the workers so the
test needs no replay; the real store, ROM hash and receipt are used.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from genesis_re import verification as v
from genesis_re.history import HistoryStore
from genesis_re.receipt import execution_receipt
from gods_sega.profile import GODS

ROOT = Path(__file__).resolve().parents[3]
needs_history = pytest.mark.skipif(not GODS.history_path().is_dir() or not GODS.rom_path.is_file(),
                                   reason='no local Gods history or ROM')
REQUIRED = ('frame', 'buttons', 'state_sha256', 'frame_sha256', 'pcm_sha256', 'pcm_bytes',
            'tick', 'pc', 'sr', 'm68k_cycles', 'm68k_instructions', 'z80_instructions', 'vblanks')


def _fake_worker(store, node, receipt, candidate):
    """A COMPLETED payload for a cold run of ``node``: one observation per frame, all alike."""
    record = store.node(node)
    frames = record['end_frame']

    def observation(frame):
        return {key: frame if key == 'frame' else (record['buttons'] if key == 'buttons' else 'x') for key in REQUIRED}
    return {'status': 'COMPLETED', 'compared': False, 'root': store.root_id, 'game': 'gods', 'history_id': node,
            'mode': 'cold', 'receipt': receipt, 'implementation': {'candidate': candidate},
            'endpoints': {node: observation(frames)}, 'observations': {node: [observation(f) for f in range(1, frames + 1)]},
            'candidate_stats': {'candidate_hits': 1, 'fallbacks': 0}, 'executed_frames': frames}


@needs_history
def test_the_reference_stream_is_executed_once_per_key_and_reused_by_later_candidates(tmp_path, monkeypatch):
    store_path = (ROOT / GODS.history_path()).resolve()
    rom_path = (ROOT / GODS.rom_path).resolve()
    store = HistoryStore(store_path, GODS.history_root)
    node = store.resolve('f0ac19738f19')
    receipt = execution_receipt(GODS)
    monkeypatch.chdir(tmp_path)                       # artifacts/gods/oracle lands here
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        candidate = command[command.index('--candidate') + 1]
        output = Path(command[command.index('--output') + 1])
        payload = _fake_worker(store, node, receipt, candidate)
        output.write_text(json.dumps(payload))
        summary = {k: v for k, v in payload.items() if k not in ('observations', 'endpoints')}
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(summary), stderr='')

    first = v.compare_history(GODS, store_path, rom_path, node=node, candidate='camera', output=tmp_path / 'one',
                              runner=runner)
    assert first['status'] == 'PASS' and first['oracle']['cached'] is False
    assert sorted(c[c.index('--candidate') + 1] for c in calls) == ['camera', 'original']
    cache = Path(first['oracle']['path'])
    assert cache.is_file() and json.loads(cache.read_text())['oracle_key'] == first['oracle']['key']

    calls.clear()
    second = v.compare_history(GODS, store_path, rom_path, node=node, candidate='walker', output=tmp_path / 'two',
                               runner=runner)
    assert second['status'] == 'PASS' and second['oracle']['cached'] is True
    assert [c[c.index('--candidate') + 1] for c in calls] == ['walker']          # only the candidate ran
    assert second['oracle']['key'] == first['oracle']['key']
    assert second['candidate_receipt']['receipt']['python_modules_sha256'] == receipt['python_modules_sha256']

    calls.clear()
    third = v.compare_history(GODS, store_path, rom_path, node=node, candidate='walker', output=tmp_path / 'three',
                              runner=runner, use_oracle_cache=False)
    assert third['status'] == 'PASS' and third['oracle']['cached'] is False and len(calls) == 2


@needs_history
def test_the_key_changes_with_the_shared_package_the_instant_and_the_inputs():
    store_path = (ROOT / GODS.history_path()).resolve()
    store = HistoryStore(store_path, GODS.history_root)
    receipt = execution_receipt(GODS)
    identities = store.flatten(store.resolve('f0ac19738f19'))
    rom = hashlib.sha256(b'rom').hexdigest()
    key = v.oracle_key(GODS, receipt, identities, rom, False)
    changed = dict(receipt, python_modules_sha256=dict(receipt['python_modules_sha256'], **{'genesis_re/machine.py': '0' * 64}))
    assert v.oracle_key(GODS, changed, identities, rom, False) != key
    game_only = dict(receipt, python_modules_sha256=dict(receipt['python_modules_sha256'], **{'gods_sega/boundary.py': '0' * 64}))
    assert v.oracle_key(GODS, game_only, identities, rom, False) == key          # recovered code is not the oracle's
    assert v.oracle_key(GODS, receipt, identities, rom, True) != key
    assert v.oracle_key(GODS, receipt, store.flatten(store.resolve('ca2b703b6fd5')), rom, False) != key
    import dataclasses
    moved = dataclasses.replace(GODS, observation_offset_ticks=GODS.observation_offset_ticks + 1)
    assert v.oracle_key(moved, receipt, identities, rom, False) != key
