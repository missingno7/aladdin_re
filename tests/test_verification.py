"""Verification observations and worker watchdogs need no ROM or native DLL."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from aladdin_sega import verification as v


class FakeMachine:
    def __init__(self, tick=0, state=b"state", frame=b"frame"):
        self.info = {"tick": tick}
        self._state, self._frame = state, frame

    def snapshot(self):
        return self._state

    def frame(self):
        return 1, 1, self._frame


def observation(tick, *, marker="same"):
    return {"id": f"frame-{tick}", "requested_tick": tick, "actual_tick": tick,
            "state_sha256": marker, "frame_sha256": marker, "pcm_sha256": marker, "pcm_bytes": 0}


def test_observer_records_isolated_pcm_chunks_and_terminal():
    observer = v.Observer()
    observer.pcm(b"first")
    observer.checkpoint(FakeMachine(10), 0, 10)
    observer.pcm(b"second")
    values = observer.finish(FakeMachine(12), 12)
    assert values[0]["pcm_bytes"] == 5
    assert values[0]["pcm_sha256"] == hashlib.sha256(b"first").hexdigest()
    assert values[1]["id"] == "terminal"
    assert values[1]["pcm_sha256"] == hashlib.sha256(b"second").hexdigest()


def test_worker_timeout_is_structured_and_watchdog_is_configurable():
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["worker"], 0.25, output="partial", stderr="still running")

    with pytest.raises(v.WorkerTimeout) as raised:
        v.run_worker("candidate", ["worker"], timeout_seconds=0.25, runner=timeout)
    assert raised.value.kind == "TIMEOUT"
    assert raised.value.report()["worker"] == "candidate"
    assert raised.value.stdout == "partial"


def test_nonmonotonic_or_different_observations_produce_bounded_failure_interval():
    empty = v.compare_observations([], [])
    assert not empty["equal"]
    assert "empty" in empty["first_failing_interval"]["reason"]

    invalid = v.compare_observations([observation(10)], [observation(10), observation(9)])
    assert not invalid["equal"]
    assert "nonmonotonic" in invalid["first_failing_interval"]["reason"]

    divergent = v.compare_observations([observation(10), observation(20)], [observation(10), observation(20, marker="changed")])
    assert not divergent["equal"]
    assert divergent["last_matching_checkpoint"]["id"] == "frame-10"
    assert divergent["first_failing_interval"]["to"]["candidate"]["id"] == "frame-20"


def test_compare_requires_candidate_hit_and_validates_terminal_worker_payload(tmp_path, monkeypatch):
    recording, rom = tmp_path / "capture.alreplay", tmp_path / "rom.md"
    recording.write_bytes(b"opaque capture")
    rom.write_bytes(b"rom")
    base = {"status": "COMPLETED", "compared": False, "state_sha256": "state", "frame_sha256": "frame",
            "pcm_sha256": "pcm", "pcm_bytes": 12, "candidate_stats": {"candidate_hits": 0}}

    def worker(role, command, **_kwargs):
        path = command[command.index("--observations") + 1]
        Path(path).write_text(json.dumps([observation(1)]), encoding="utf-8")
        return v.WorkerResult(role, command, dict(base), "", "")

    monkeypatch.setattr(v, "run_worker", worker)
    result = v.compare_replay(rom, recording, candidate="leaf", output=tmp_path / "out")
    assert result["status"] == "NOT_EXERCISED"
    assert result["compared"] is True

    def different_terminal(role, command, **_kwargs):
        path = command[command.index("--observations") + 1]
        Path(path).write_text(json.dumps([observation(1)]), encoding="utf-8")
        payload = dict(base)
        payload["candidate_stats"] = {"candidate_hits": 1}
        if role == "candidate":
            payload["state_sha256"] = "wrong"
        return v.WorkerResult(role, command, payload, "", "")

    monkeypatch.setattr(v, "run_worker", different_terminal)
    result = v.compare_replay(rom, recording, candidate="leaf", output=tmp_path / "terminal")
    assert result["status"] == "DIVERGENCE"
    assert result["comparison"]["terminal_payload"]["differences"]["state_sha256"]
