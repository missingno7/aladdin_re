"""Shared-prefix traversal and strongest cold-run verification contracts."""
import copy
import json
import os
import subprocess
import sys
import threading

import pytest

from genesis_re.history import HistoryStore, digest, encoded
from genesis_re.games import GAMES

from genesis_re.history_runtime import GenesisRun
from genesis_re.verification import execute_history, compare_history, _validate_execution

GAME = GAMES["aladdin"]   # the common suite exercises real-cartridge mechanisms on this registered game
ROOT_ID = digest(encoded(GAME.history_root))
DEFAULT_ROM = GAME.rom_path


def graph(tmp_path):
    store = HistoryStore(tmp_path / 'history', GAME.history_root)
    a = store.append(ROOT_ID, [], 2)
    b = store.append(a, [{'frame': 2, 'buttons': 128}], 4)
    c = store.append(b, [{'frame': 4, 'buttons': 0}], 6)
    x = store.append(b, [{'frame': 4, 'buttons': 8}], 7)
    store.set_main(c)
    return store, a, b, c, x


def test_tree_reuses_prefix_and_matches_each_continuous_cold_leaf(tmp_path):
    store, a, b, c, x = graph(tmp_path)
    tree = execute_history(GAME, store, GAME.read_rom(), tree=True)
    assert tree['executed_frames'] == 9  # 2+2+2+3, instead of 6+7.
    assert len(store.nodes()) == 5
    for leaf in (c, x):
        cold = execute_history(GAME, store, GAME.read_rom(), node=leaf)
        assert cold['restores'] == 0
        assert cold['endpoints'][leaf] == tree['endpoints'][leaf]


def test_fresh_worker_tree_comparison(tmp_path):
    store, *_ = graph(tmp_path)
    result = compare_history(GAME, store.path, DEFAULT_ROM, candidate='original', tree=True,
                             output=tmp_path / 'comparison')
    assert result['status'] == 'PASS', result
    assert result['reference']['executed_frames'] == 9


@pytest.mark.parametrize('field', ['state_sha256', 'pcm_sha256', 'frame_sha256', 'pc'])
def test_missing_terminal_evidence_fails_even_if_both_workers_omit_it(tmp_path, field):
    store, _, _, c, _ = graph(tmp_path)
    result = execute_history(GAME, store, GAME.read_rom(), node=c)
    del result['endpoints'][c][field]
    with pytest.raises(ValueError, match='terminal'):
        _validate_execution(result, store, c, False, 'original', result['receipt'])


def test_missing_frame_or_stale_implementation_receipt_fails(tmp_path):
    store, _, _, c, _ = graph(tmp_path)
    result = execute_history(GAME, store, GAME.read_rom(), node=c)
    incomplete = copy.deepcopy(result)
    incomplete['observations'][c].pop()
    with pytest.raises(ValueError, match='every canonical frame'):
        _validate_execution(incomplete, store, c, False, 'original', result['receipt'])
    stale = copy.deepcopy(result)
    stale['receipt']['native_binary_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='receipt'):
        _validate_execution(stale, store, c, False, 'original', result['receipt'])


def test_fresh_process_cache_prefix_and_continuous_cold_are_strictly_equal(tmp_path):
    store, _, b, c, _ = graph(tmp_path)
    prefix = store.flatten(b)
    with GenesisRun(GAME, GAME.read_rom()) as original:
        original.advance(prefix['end_frame'], prefix['events'])
        original.cache(store, b)
    results = {}
    for mode in ('cold', 'cache'):
        output = tmp_path / (mode + '.json')
        subprocess.run([sys.executable, '-m', 'genesis_re', 'history-run', c, '--game', 'aladdin',
                        '--history', str(store.path), '--rom', str(DEFAULT_ROM.resolve()),
                        '--' + mode, '--output', str(output)],
                       capture_output=True, text=True, check=True, timeout=30)
        results[mode] = json.loads(output.read_text())
    assert results['cold']['restores'] == 0
    assert results['cold']['executed_frames'] == 6
    assert results['cache']['restores'] == 1
    assert results['cache']['executed_frames'] == 2
    assert results['cold']['endpoints'] == results['cache']['endpoints']


def test_portable_export_needs_neither_rom_nor_native_library(tmp_path):
    store, _, _, c, _ = graph(tmp_path)
    output = tmp_path / 'portable.json'
    env = dict(os.environ, GENESIS_NATIVE_LIBRARY=str(tmp_path / 'absent.dll'))
    subprocess.run([sys.executable, '-m', 'genesis_re', 'history-export', c, '--game', 'aladdin',
                    '--history', str(store.path), '--rom', str(tmp_path / 'absent.rom'),
                    '--output', str(output)], env=env,
                   capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(output.read_text()) == store.flatten(c)


def test_reference_and_candidate_workers_run_at_the_same_time(tmp_path):
    store, *_ = graph(tmp_path)
    barrier = threading.Barrier(2, timeout=10)

    def runner(command, **kwargs):
        barrier.wait()  # only passes when both workers are in flight together
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])

    result = compare_history(GAME, store.path, DEFAULT_ROM, candidate='original', output=tmp_path / 'c',
                             timeout_seconds=1, runner=runner)
    assert result['status'] == 'TIMEOUT'
    assert result['error']['worker'] == 'reference'
    assert result['workers'] == 'parallel'


def test_sequential_mode_stops_at_the_first_failed_worker(tmp_path):
    store, *_ = graph(tmp_path)
    started = []

    def runner(command, **kwargs):
        started.append(command[command.index('--candidate') + 1])
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])

    result = compare_history(GAME, store.path, DEFAULT_ROM, candidate='lifecycle', output=tmp_path / 'c',
                             timeout_seconds=1, runner=runner, parallel=False)
    assert result['status'] == 'TIMEOUT' and result['workers'] == 'sequential'
    assert started == ['original']


def test_candidate_watchdog_expiry_is_a_timeout_not_a_candidate_error(tmp_path):
    store, *_ = graph(tmp_path)

    def runner(command, **kwargs):
        if command[command.index('--candidate') + 1] == 'original':
            return subprocess.run(command, **kwargs)
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])

    result = compare_history(GAME, store.path, DEFAULT_ROM, candidate='lifecycle', output=tmp_path / 'c',
                             timeout_seconds=60, runner=runner)
    assert result['status'] == 'TIMEOUT'
    assert result['error']['worker'] == 'candidate'
    assert 'exceeded 60 seconds' in result['error']['detail']


def test_parallel_cold_comparison_of_a_real_branch_passes(tmp_path):
    store, _, _, c, _ = graph(tmp_path)
    result = compare_history(GAME, store.path, DEFAULT_ROM, node=c, candidate='original', output=tmp_path / 'c')
    assert result['status'] == 'PASS', result
    assert result['workers'] == 'parallel'
    assert result['reference']['executed_frames'] == 6
