"""Shared-prefix traversal and strongest cold-run verification contracts."""
import copy
import json
import os
import subprocess
import sys

import pytest

from aladdin_sega.history import HistoryStore, ROOT_ID
from aladdin_sega.profile import read_rom, DEFAULT_ROM
from aladdin_sega.history_runtime import GenesisRun
from aladdin_sega.verification import execute_history, compare_history, _validate_execution


def graph(tmp_path):
    store = HistoryStore(tmp_path / 'history')
    a = store.append(ROOT_ID, [], 2)
    b = store.append(a, [{'frame': 2, 'buttons': 128}], 4)
    c = store.append(b, [{'frame': 4, 'buttons': 0}], 6)
    x = store.append(b, [{'frame': 4, 'buttons': 8}], 7)
    store.set_main(c)
    return store, a, b, c, x


def test_tree_reuses_prefix_and_matches_each_continuous_cold_leaf(tmp_path):
    store, a, b, c, x = graph(tmp_path)
    tree = execute_history(store, read_rom(), tree=True)
    assert tree['executed_frames'] == 9  # 2+2+2+3, instead of 6+7.
    assert len(store.nodes()) == 5
    for leaf in (c, x):
        cold = execute_history(store, read_rom(), node=leaf)
        assert cold['restores'] == 0
        assert cold['endpoints'][leaf] == tree['endpoints'][leaf]


def test_fresh_worker_tree_comparison(tmp_path):
    store, *_ = graph(tmp_path)
    result = compare_history(store.path, DEFAULT_ROM, candidate='original', tree=True,
                             output=tmp_path / 'comparison')
    assert result['status'] == 'PASS', result
    assert result['reference']['executed_frames'] == 9


@pytest.mark.parametrize('field', ['state_sha256', 'pcm_sha256', 'frame_sha256', 'pc'])
def test_missing_terminal_evidence_fails_even_if_both_workers_omit_it(tmp_path, field):
    store, _, _, c, _ = graph(tmp_path)
    result = execute_history(store, read_rom(), node=c)
    del result['endpoints'][c][field]
    with pytest.raises(ValueError, match='terminal'):
        _validate_execution(result, store, c, False, 'original', result['receipt'])


def test_missing_frame_or_stale_implementation_receipt_fails(tmp_path):
    store, _, _, c, _ = graph(tmp_path)
    result = execute_history(store, read_rom(), node=c)
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
    with GenesisRun(read_rom()) as original:
        original.advance(prefix['end_frame'], prefix['events'])
        original.cache(store, b)
    results = {}
    for mode in ('cold', 'cache'):
        output = tmp_path / (mode + '.json')
        subprocess.run([sys.executable, '-m', 'aladdin_sega', 'history-run', c,
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
    env = dict(os.environ, ALADDIN_NATIVE_LIBRARY=str(tmp_path / 'absent.dll'))
    subprocess.run([sys.executable, '-m', 'aladdin_sega', 'history-export', c,
                    '--history', str(store.path), '--rom', str(tmp_path / 'absent.rom'),
                    '--output', str(output)], env=env,
                   capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(output.read_text()) == store.flatten(c)
