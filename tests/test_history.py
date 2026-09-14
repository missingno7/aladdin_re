"""Independent contracts for cold-root frame histories and disposable caches."""
from __future__ import annotations

import pytest

from aladdin_sega.history import HistoryStore, ROOT_ID, encoded, digest, read_json, write_json
from aladdin_sega.history_runtime import GenesisRun, Session
from aladdin_sega import artifacts
from aladdin_sega.profile import FRAME_TICKS, read_rom


def synthetic_rom() -> bytes:
    rom = bytearray(1024)
    rom[0:8] = bytes.fromhex("00ff8000 00000200")
    rom[0x200:0x20A] = bytes.fromhex("33fc123400ff0010 60f6")
    return bytes(rom)


def test_history_identity_is_canonical_and_branches_by_input(tmp_path):
    store = HistoryStore(tmp_path / "history")
    events = [{"frame": 0, "buttons": 1}, {"frame": 2, "buttons": 0}]
    first = store.append(ROOT_ID, events, 4)
    same_path = store.append(ROOT_ID, events, 4)
    branch = store.append(ROOT_ID, [{"frame": 0, "buttons": 2}], 4)

    assert first == same_path
    assert branch != first
    assert store.flatten(first) == {
        "root": store.flatten(first)["root"], "history_id": first,
        "end_frame": 4, "events": events,
    }
    assert [key for key, _ in store.ancestry(first)] == [ROOT_ID, first]
    assert [key for key, _ in store.ancestry(branch)] == [ROOT_ID, branch]


def test_history_rejects_noncanonical_segment_events(tmp_path):
    store = HistoryStore(tmp_path / "history")
    with pytest.raises(ValueError, match="ordered"):
        store.append(ROOT_ID, [{"frame": 3, "buttons": 1}], 3)
    with pytest.raises(ValueError, match="Redundant"):
        store.append(ROOT_ID, [{"frame": 0, "buttons": 0}], 1)
    with pytest.raises(ValueError, match="ordered"):
        store.append(ROOT_ID, [{"frame": 1, "buttons": 1}, {"frame": 1, "buttons": 2}], 3)


def test_history_presentation_is_metadata_only(tmp_path):
    store = HistoryStore(tmp_path / "history")
    node = store.append(ROOT_ID, [{"frame": 0, "buttons": 4}], 1)
    rgb = bytes([17, 34, 51]) * (2 * 1)
    store.present(node, rgb=rgb, width=2, height=1, reason="manual", label="frame-1")

    metadata = store.metadata(node)
    assert metadata["reason"] == "manual"
    assert metadata["label"] == "frame-1"
    assert metadata["screenshot"] == f"screenshots/{node}.ppm"
    assert (tmp_path / "history" / metadata["screenshot"]).read_bytes().endswith(rgb)


def test_genesis_run_counts_logical_frames_despite_native_tick_overshoot():
    with GenesisRun(synthetic_rom()) as run:
        run.step(1)
        assert run.frame == 1
        assert run.machine.info["tick"] >= FRAME_TICKS
        assert run.machine.info["tick"] != FRAME_TICKS


def test_cold_and_cache_continuations_match_full_state_frame_and_pcm(tmp_path):
    store = HistoryStore(tmp_path / "history")
    rom = read_rom()
    prefix = [{"frame": 0, "buttons": 1}]
    suffix = [{"frame": 3, "buttons": 3}]
    node = store.append(ROOT_ID, prefix, 3)

    with GenesisRun(rom) as cold:
        cold.advance(3, prefix)
        cold.cache(store, node)
        cold.advance(5, suffix)
        expected = cold.observable()

    with GenesisRun(rom) as restored:
        assert restored.restore_cache(store, node)
        restored.advance(5, suffix)
        actual = restored.observable()

    assert actual == expected
    assert actual["frame"] == 5
    assert actual["state_sha256"] == expected["state_sha256"]
    assert actual["frame_sha256"] == expected["frame_sha256"]
    assert actual["pcm_sha256"] == expected["pcm_sha256"]
    assert actual["pcm_bytes"] == expected["pcm_bytes"]


def test_corrupt_cache_is_ignored_and_can_be_regenerated(tmp_path):
    store = HistoryStore(tmp_path / "history")
    node = store.append(ROOT_ID, [{"frame": 0, "buttons": 1}], 2)
    with GenesisRun(read_rom()) as writer:
        writer.advance(2, [{"frame": 0, "buttons": 1}])
        writer.cache(store, node)
        cache_path = next((tmp_path / "history" / "caches").rglob("*.cache"))

    cache_path.write_bytes(b"corrupt cache")

    with GenesisRun(read_rom()) as reader:
        assert reader.restore_cache(store, node) is False
        path = store.flatten(node)
        reader.advance(path["end_frame"], path["events"])
        reader.cache(store, node)

    with GenesisRun(read_rom()) as restored:
        assert restored.restore_cache(store, node) is True


def test_tampered_cache_pcm_accounting_is_ignored(tmp_path):
    store = HistoryStore(tmp_path / "history")
    node = store.append(ROOT_ID, [{"frame": 0, "buttons": 1}], 2)
    with GenesisRun(read_rom()) as writer:
        writer.advance(2, [{"frame": 0, "buttons": 1}])
        writer.cache(store, node)
        cache_path = next((tmp_path / "history" / "caches").rglob("*.cache"))

    parts = artifacts.unpack(cache_path.read_bytes(), {"cache.json", "state.bin"}, {"cache.json", "state.bin"})
    metadata = artifacts.decode_json(parts["cache.json"])
    metadata["pcm_bytes"] += 4
    cache_path.write_bytes(artifacts.pack({"cache.json": encoded(metadata), "state.bin": parts["state.bin"]}))

    with GenesisRun(read_rom()) as reader:
        assert reader.restore_cache(store, node) is False


def test_session_resume_records_input_release_at_next_frame(tmp_path):
    store = HistoryStore(tmp_path / "history")
    with Session(store, read_rom()) as session:
        session.step(8)
        session.step(8)
        node = session.checkpoint(reason="pause")

    with Session(store, read_rom(), node=node) as resumed:
        assert resumed.frame == 2
        assert resumed.run.buttons == 8
        resumed.step(0)
        assert resumed.events == [{"frame": 2, "buttons": 0}]
        resumed_node = resumed.checkpoint(reason="resume")

    assert store.flatten(resumed_node)["events"] == [
        {"frame": 0, "buttons": 8}, {"frame": 2, "buttons": 0}
    ]


def test_checkpoint_placement_and_presentation_cannot_change_path_identity(tmp_path):
    left, right = HistoryStore(tmp_path / 'left'), HistoryStore(tmp_path / 'right')
    events = [{'frame': 0, 'buttons': 8}, {'frame': 4, 'buttons': 0}]
    whole = left.append(ROOT_ID, events, 8)
    middle = right.append(ROOT_ID, events[:1], 3)
    split = right.append(middle, events[1:], 8)
    assert whole == split
    assert left.flatten(whole) == right.flatten(split)
    right.present(split, rgb=bytes(3), width=1, height=1, reason='manual', label='test')
    image = right.path / right.metadata(split)['screenshot']
    image.write_bytes(b'arbitrary presentation change')
    assert right.flatten(split) == left.flatten(whole)
    image.unlink()
    assert right.flatten(split) == left.flatten(whole)


def test_resume_branch_autosave_and_cache_deletion_preserve_ancestry(tmp_path):
    store = HistoryStore(tmp_path / 'history')
    with Session(store, read_rom()) as first:
        first.step(8)
        a = first.checkpoint()
        first.step(0)
        b = first.checkpoint()
        first.step(16)
    c = store.resolve()
    original_path = store.flatten(c)
    with Session(store, read_rom(), node=b) as resumed:
        assert resumed.used_cache
        resumed.step(32)
    x = store.resolve()
    assert x != c
    assert len(store.nodes()) == 5  # implicit root + A/B/C/X
    assert store.node(c)['parent'] == store.node(x)['parent'] == b
    assert store.node(b)['parent'] == a
    assert store.flatten(c) == original_path
    assert store.metadata(x)['reason'] == 'session_exit'
    assert (store.path / store.metadata(x)['screenshot']).exists()
    with GenesisRun(read_rom()) as cold:
        path = store.flatten(x)
        cold.advance(path['end_frame'], path['events'])
        expected = cold.observable()
        cold._cache_path(store, x).unlink()
    with Session(store, read_rom(), node=x) as regenerated:
        assert not regenerated.used_cache
        assert regenerated.run.observable() == expected
    assert store.flatten(x) == path


def test_implementation_change_invalidates_only_cache(tmp_path):
    store = HistoryStore(tmp_path / 'history')
    with Session(store, read_rom()) as session:
        session.step(0)
    node = store.resolve()
    path = store.flatten(node)
    with GenesisRun(read_rom()) as changed:
        changed.implementation['source'] = {'changed.py': '0' * 64}
        changed.implementation_id = digest(encoded(changed.implementation))
        assert not changed.restore_cache(store, node)
        changed.advance(path['end_frame'], path['events'])
        changed.cache(store, node)
    assert store.flatten(node) == path
    assert len(list((store.path / 'caches').rglob('*.cache'))) == 2


def test_valid_cache_envelope_with_invalid_native_state_cannot_move_logical_clock(tmp_path):
    store = HistoryStore(tmp_path / 'history')
    with Session(store, read_rom()) as session:
        session.step(8)
        session.step(0)
    node = store.resolve()
    with GenesisRun(read_rom()) as reader:
        cache = reader._cache_path(store, node)
        parts = artifacts.unpack(cache.read_bytes(), {'cache.json', 'state.bin'}, {'cache.json', 'state.bin'})
        meta = artifacts.decode_json(parts['cache.json'])
        del meta['checksum']
        meta['state_sha256'] = digest(b'invalid native state')
        meta['checksum'] = digest(encoded(meta))
        cache.write_bytes(artifacts.pack({'cache.json': encoded(meta), 'state.bin': b'invalid native state'}))
        before = reader.save()
        assert not reader.restore_cache(store, node)
        assert reader.save() == before
    with Session(store, read_rom(), node=node) as recovered:
        assert not recovered.used_cache
        assert recovered.frame == 2


@pytest.mark.parametrize('damage', ['cycle', 'missing', 'input'])
def test_graph_validation_rejects_broken_ancestry(tmp_path, damage):
    store = HistoryStore(tmp_path / 'history')
    a = store.append(ROOT_ID, [], 2)
    b = store.append(a, [{'frame': 2, 'buttons': 1}], 4)
    path = store.path / 'nodes' / (a + '.json')
    value = read_json(path)
    if damage == 'missing':
        path.unlink()
    else:
        if damage == 'cycle':
            value['parent'] = b
        else:
            value['events'] = [{'frame': 0, 'buttons': 16}]
        write_json(path, value)
    with pytest.raises((ValueError, FileNotFoundError)):
        store.flatten(b)


def test_original_caches_survive_a_python_source_edit_but_candidate_caches_do_not(tmp_path, monkeypatch):
    from aladdin_sega import history_runtime
    store = HistoryStore(tmp_path / 'history')
    with Session(store, read_rom()) as session:
        session.step(0)
    node = store.resolve()
    path = store.flatten(node)
    with GenesisRun(read_rom(), 'lifecycle') as candidate:
        candidate.advance(path['end_frame'], path['events'])
        candidate.cache(store, node)
    real = history_runtime.execution_receipt

    def edited(candidate='original'):
        receipt = dict(real(candidate=candidate))
        receipt['python_modules_sha256'] = {**receipt['python_modules_sha256'], 'boundary.py': '0' * 64}
        return receipt

    monkeypatch.setattr(history_runtime, 'execution_receipt', edited)
    with GenesisRun(read_rom()) as original:
        assert 'source' in original.implementation and 'source' not in original.cache_implementation
        assert original.restore_cache(store, node)
        assert original.frame == path['end_frame']
    with GenesisRun(read_rom(), 'lifecycle') as changed:
        assert 'source' in changed.cache_implementation
        assert not changed.restore_cache(store, node)
