"""Fresh-process checkpoint suffix check; no reference data enters execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from . import artifacts
from .machine import Machine


def snapshot_check(rom, rom_path, recording):
    data = artifacts.read_bounded(recording)
    with Machine(rom) as machine:
        meta, initial, events = artifacts.load_replay(data, rom_sha256=machine.rom_sha256, source_id=machine.source_id)
        artifacts.restore_snapshot(machine, initial)
        # Capture after a prefix, with next-unconsumed event index separate from state.
        cursor = len(events) // 2
        checkpoint_tick = events[cursor - 1]["tick"] if cursor else machine.info["tick"]
        artifacts.play_events(machine, events[:cursor], checkpoint_tick)
        checkpoint = artifacts.snapshot_bytes(machine)
        suffix = events[cursor:]
        derived = artifacts.Recorder(machine, origin="synthetic", reset_provenance="derived-checkpoint")
        derived.events = [{**event, "seq": i} for i, event in enumerate(suffix)]
        machine.audio()
        pcm = hashlib.sha256()
        artifacts.play_events(machine, suffix, meta["terminal_tick"], audio_sink=pcm.update)
        expected = artifacts.digest(machine.snapshot())
        expected_frame = artifacts.digest(machine.frame()[2])
        expected_pcm = pcm.hexdigest()
        suffix_archive = derived.finish(machine)
    # The first worker is closed before spawning a fresh interpreter.
    with tempfile.TemporaryDirectory(prefix="aladdin-snapshot-") as tmp:
        path = Path(tmp) / "suffix.alreplay"
        path.write_bytes(suffix_archive)
        proc = subprocess.run([sys.executable, "-m", "aladdin_sega", "replay", str(path), "--rom", str(rom_path)],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode:
            raise RuntimeError(f"Fresh-process replay failed: {proc.stdout} {proc.stderr}")
        actual = json.loads(proc.stdout)
        if actual.get("state_sha256") != expected:
            raise RuntimeError("Fresh-process snapshot suffix diverged")
        if actual.get("frame_sha256") != expected_frame or actual.get("pcm_sha256") != expected_pcm:
            raise RuntimeError("Fresh-process snapshot suffix output diverged")
    return {"status": "PASS", "scope": "fresh-process original suffix: full state, final frame, all suffix PCM",
            "replay_sha256": artifacts.digest(data), "checkpoint_sha256": artifacts.digest(checkpoint),
            "next_event_index": cursor, "suffix_events": len(suffix), "state_sha256": expected,
            "pcm_sha256": expected_pcm, "frame_sha256": expected_frame, "cross_platform": "UNVERIFIED"}


def check_saved_snapshots(rom, rom_path, recording, snapshots):
    """Match separately saved live states against replay, then resume their suffixes."""
    data = artifacts.read_bounded(recording)
    matches = []
    with Machine(rom) as machine:
        meta, initial, events = artifacts.load_replay(data, rom_sha256=machine.rom_sha256, source_id=machine.source_id)
        checkpoints = []
        for path in snapshots:
            raw = artifacts.read_bounded(path)
            info, state = artifacts.load_snapshot(raw, rom_sha256=machine.rom_sha256, source_id=machine.source_id)
            checkpoints.append((info["tick"], str(path), raw, state))
        artifacts.restore_snapshot(machine, initial)
        cursor = 0
        def observe_pcm(pcm):
            for match in matches:
                match["pcm"].update(pcm)
        for tick, path, raw, state in sorted(checkpoints):
            if tick < machine.info["tick"] or tick > meta["terminal_tick"]:
                raise ValueError(f"Snapshot outside recording interval: {path}")
            end = cursor
            while end < len(events) and events[end]["tick"] < tick:
                end += 1
            artifacts.play_events(machine, events[cursor:end], tick, audio_sink=observe_pcm)
            cursor = end
            # Standalone saves can occur before, between or after equal-tick inputs.
            while machine.snapshot() != state:
                if cursor >= len(events) or events[cursor]["tick"] != tick:
                    raise RuntimeError(f"Saved snapshot does not match original replay: {path}")
                machine.pad(events[cursor]["buttons"])
                cursor += 1
            matches.append({"path": path, "tick": tick, "sha256": artifacts.digest(raw),
                            "next_event_index": cursor, "initial": raw, "pcm": hashlib.sha256()})
        artifacts.play_events(machine, events[cursor:], meta["terminal_tick"], audio_sink=observe_pcm)
        expected_state = artifacts.digest(machine.snapshot())
        expected_frame = artifacts.digest(machine.frame()[2])
    # Test each original saved file, not a substitute checkpoint from replay.
    with tempfile.TemporaryDirectory(prefix="aladdin-live-snapshots-") as tmp:
        for index, match in enumerate(matches):
            remaining = events[match["next_event_index"]:]
            expected_pcm = match.pop("pcm").hexdigest()
            with Machine(rom) as machine:
                artifacts.restore_snapshot(machine, match["initial"])
                recorder = artifacts.Recorder(machine, origin="synthetic", reset_provenance="derived-from-user-snapshot")
                recorder.events = [{**e, "seq": i} for i, e in enumerate(remaining)]
                pcm = hashlib.sha256()
                artifacts.play_events(machine, remaining, meta["terminal_tick"], audio_sink=pcm.update)
                if artifacts.digest(machine.snapshot()) != expected_state or artifacts.digest(machine.frame()[2]) != expected_frame:
                    raise RuntimeError(f"Saved snapshot continuation diverged: {match['path']}")
                suffix = recorder.finish(machine)
                if pcm.hexdigest() != expected_pcm:
                    raise RuntimeError(f"Saved snapshot PCM differs from uninterrupted replay: {match['path']}")
            path = Path(tmp) / f"suffix-{index}.alreplay"
            path.write_bytes(suffix)
            proc = subprocess.run([sys.executable, "-m", "aladdin_sega", "replay", str(path), "--rom", str(rom_path)],
                                  capture_output=True, text=True, timeout=60)
            if proc.returncode:
                raise RuntimeError(f"Fresh-process replay failed: {proc.stdout} {proc.stderr}")
            actual = json.loads(proc.stdout)
            if (actual.get("state_sha256"), actual.get("frame_sha256"), actual.get("pcm_sha256")) != (expected_state, expected_frame, expected_pcm):
                raise RuntimeError(f"Fresh-process saved snapshot diverged: {match['path']}")
            del match["initial"]
            match.update(status="PASS", suffix_events=len(remaining), pcm_sha256=expected_pcm)
    return {"status": "PASS", "scope": "live snapshots match replay; their fresh-process suffixes match full state, final frame and PCM",
            "replay_sha256": artifacts.digest(data), "snapshots": matches,
            "state_sha256": expected_state, "frame_sha256": expected_frame, "cross_platform": "UNVERIFIED"}
