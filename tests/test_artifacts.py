import json
from pathlib import Path

import pytest

from aladdin_sega import artifacts as a
from aladdin_sega.machine import Machine
from test_machine import synthetic_rom


def test_mid_session_input_capture_and_terminal():
    with Machine(synthetic_rom()) as m:
        m.run(instructions=7)
        m.pad(16)
        recorder = a.Recorder(m, origin="synthetic")
        m.run(instructions=10)
        recorder.apply_pad(m, 0)
        recorder.apply_pad(m, 128)  # equal timestamp ordering
        m.run(instructions=21)
        recorder.apply_pad(m, 0)
        m.run(instructions=4)  # terminal time extends beyond last input
        data = recorder.finish(m)
        expected = m.snapshot()
        meta, initial, events = a.load_replay(data, rom_sha256=m.rom_sha256, source_id=m.source_id)
        a.restore_snapshot(m, initial)
        assert m.info["buttons"] == 16
        a.play_events(m, events, meta["terminal_tick"])
        assert m.snapshot() == expected


def test_archive_validation_and_exclusive_save(tmp_path):
    with pytest.raises(ValueError):
        a.unpack(a.pack({"../bad": b"x"}), {"manifest.json"}, {"manifest.json"})
    with pytest.raises(ValueError):
        a.decode_json(b'{"tick":1,"tick":2}')
    with pytest.raises(ValueError):
        a.uint(True)
    path = tmp_path / "recording.alreplay"
    a.write_new(path, b"original")
    with pytest.raises(FileExistsError):
        a.write_new(path, b"replacement")
    assert path.read_bytes() == b"original"


def test_wrong_identity_corrupt_and_manifest_time():
    with Machine(synthetic_rom()) as m:
        m.run(instructions=9)
        snap = a.snapshot_bytes(m)
        before = m.snapshot()
        with pytest.raises(ValueError, match="identity"):
            a.load_snapshot(snap, rom_sha256="0" * 64, source_id=m.source_id)
        parts = a.unpack(snap, {"manifest.json", "machine.bin"}, {"manifest.json", "machine.bin"})
        meta = json.loads(parts["manifest.json"])
        meta["tick"] += 1
        parts["manifest.json"] = a.json_bytes(meta)
        with pytest.raises(ValueError, match="timestamp"):
            a.restore_snapshot(m, a.pack(parts))
        assert m.snapshot() == before
        with pytest.raises(ValueError):
            a.restore_snapshot(m, snap[:-30])


@pytest.mark.parametrize("change", ["terminal", "order", "mask", "port", "profile"])
def test_replay_rejects_invalid_events(change):
    with Machine(synthetic_rom()) as m:
        recorder = a.Recorder(m, origin="synthetic")
        m.run(instructions=2)
        recorder.apply_pad(m, 1)
        data = recorder.finish(m)
        parts = a.unpack(data, {"manifest.json", "initial.alsnap", "events.jsonl", "bookmarks.json"}, set())
        meta = json.loads(parts["manifest.json"])
        event = json.loads(parts["events.jsonl"])
        if change == "terminal": meta["terminal_tick"] = 0
        if change == "order": event["seq"] = 1
        if change == "mask": event["buttons"] = 256
        if change == "port": event["port"] = 1
        if change == "profile": meta["profile_sha256"] = "0" * 64
        parts["events.jsonl"] = a.json_bytes(event) + b"\n"
        meta["events_sha256"] = a.digest(parts["events.jsonl"])
        parts["manifest.json"] = a.json_bytes(meta)
        with pytest.raises(ValueError):
            a.load_replay(a.pack(parts), rom_sha256=m.rom_sha256, source_id=m.source_id)
