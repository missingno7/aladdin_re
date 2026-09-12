"""Fresh-worker replay comparisons and snapshot continuation checks."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from . import artifacts
from .machine import Machine


class WorkerError(RuntimeError):
    kind = "ERROR"

    def __init__(self, role, command, detail, *, stdout="", stderr="", returncode=None):
        super().__init__(detail)
        self.role, self.command, self.detail = role, command, detail
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode

    def report(self):
        return {"worker": self.role, "detail": self.detail, "returncode": self.returncode,
                "command": self.command, "stdout": self.stdout, "stderr": self.stderr}


class WorkerTimeout(WorkerError):
    kind = "TIMEOUT"


class WorkerFailure(WorkerError):
    kind = "ERROR"


class WorkerDependencyFailure(WorkerFailure):
    kind = "DEPENDENCY_FAILURE"


@dataclass
class WorkerResult:
    role: str
    command: list[str]
    payload: dict[str, Any]
    stdout: str
    stderr: str


def _last_json(stdout):
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("worker did not emit a JSON result")


def run_worker(role, command, *, timeout_seconds, env=None, runner=None):
    """Run one child; watchdog expiry is reported separately from execution failure."""
    if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    invoke = subprocess.run if runner is None else runner
    try:
        completed = invoke(command, capture_output=True, text=True, timeout=timeout_seconds, env=env, check=False)
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or "", error.stderr or ""
        if isinstance(stdout, bytes): stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes): stderr = stderr.decode(errors="replace")
        raise WorkerTimeout(role, command, f"worker exceeded {timeout_seconds:g} seconds", stdout=stdout, stderr=stderr) from error
    if completed.returncode:
        try:
            failed = _last_json(completed.stdout)
        except ValueError:
            failed = {}
        detail = str(failed.get("detail", ""))
        if failed.get("status") == "TIMEOUT":
            raise WorkerTimeout(role, command, detail or "worker reported timeout", stdout=completed.stdout,
                                stderr=completed.stderr, returncode=completed.returncode)
        dependency = failed.get("status") == "MISSING_INPUT" or any(token in detail for token in
            ("Native library", "DLL load", "ImportError", "No module named"))
        error_type = WorkerDependencyFailure if dependency else WorkerFailure
        raise error_type(role, command, "worker returned a nonzero exit status", stdout=completed.stdout,
                         stderr=completed.stderr, returncode=completed.returncode)
    try:
        payload = _last_json(completed.stdout)
    except ValueError as error:
        raise WorkerFailure(role, command, str(error), stdout=completed.stdout, stderr=completed.stderr) from error
    if payload.get("status") != "COMPLETED" or payload.get("compared") is not False:
        raise WorkerFailure(role, command, "worker did not report successful un-compared execution",
                            stdout=completed.stdout, stderr=completed.stderr)
    return WorkerResult(role, command, payload, completed.stdout, completed.stderr)


class Observer:
    """A small ordered observation stream that never feeds data to a candidate."""
    def __init__(self, machine=None):
        self.machine = machine
        self._pcm, self._pcm_bytes, self.observations = hashlib.sha256(), 0, []

    def pcm(self, data):
        self._pcm.update(data)
        self._pcm_bytes += len(data)

    def checkpoint(self, machine, checkpoint_id, requested_tick):
        info = machine.info
        _, _, frame = machine.frame()
        self.observations.append({
            "id": str(checkpoint_id), "requested_tick": requested_tick, "actual_tick": info["tick"],
            "state_sha256": artifacts.digest(machine.snapshot()), "frame_sha256": artifacts.digest(frame),
            "pcm_sha256": self._pcm.hexdigest(), "pcm_bytes": self._pcm_bytes,
        })
        self._pcm, self._pcm_bytes = hashlib.sha256(), 0

    def finish(self, machine=None, terminal_tick=None):
        machine = machine or self.machine
        if machine is None:
            raise ValueError("Observer.finish requires a machine")
        if terminal_tick is None:
            terminal_tick = machine.info["tick"]
        self.checkpoint(machine, "terminal", terminal_tick)
        return self.observations

    def write(self, path):
        Path(path).write_text(json.dumps(self.observations, indent=2, sort_keys=True) + "\n", encoding="utf-8")


_OBSERVATION_FIELDS = {"id", "requested_tick", "actual_tick", "state_sha256", "frame_sha256", "pcm_sha256", "pcm_bytes"}


def _observation_error(stream):
    if not isinstance(stream, list): return "observations are not a list"
    if not stream: return "observations are empty"
    previous = -1
    for index, value in enumerate(stream):
        if not isinstance(value, dict) or set(value) != _OBSERVATION_FIELDS:
            return f"invalid observation fields at index {index}"
        if type(value["actual_tick"]) is not int or value["actual_tick"] < previous:
            return f"nonmonotonic actual_tick at index {index}"
        if type(value["requested_tick"]) is not int or type(value["pcm_bytes"]) is not int or value["pcm_bytes"] < 0:
            return f"invalid observation values at index {index}"
        previous = value["actual_tick"]
    return None


def _anchor(value):
    return None if value is None else {key: value[key] for key in ("id", "requested_tick", "actual_tick")}


def compare_observations(reference, candidate):
    """Compare two streams with an anchor and first bounded failing interval."""
    for role, stream in (("reference", reference), ("candidate", candidate)):
        problem = _observation_error(stream)
        if problem:
            return {"equal": False, "last_matching_checkpoint": None,
                    "first_failing_interval": {"reason": f"{role}: {problem}"}}
    last = None
    fields = ("id", "requested_tick", "actual_tick", "state_sha256", "frame_sha256", "pcm_sha256", "pcm_bytes")
    for index in range(max(len(reference), len(candidate))):
        left = reference[index] if index < len(reference) else None
        right = candidate[index] if index < len(candidate) else None
        if left is None or right is None:
            return {"equal": False, "last_matching_checkpoint": _anchor(last), "first_failing_interval": {
                "from": _anchor(last), "to": {"reference": _anchor(left), "candidate": _anchor(right)},
                "reason": "observation count differs"}}
        changed = {field: {"reference": left[field], "candidate": right[field]}
                   for field in fields if left[field] != right[field]}
        if changed:
            return {"equal": False, "last_matching_checkpoint": _anchor(last), "first_failing_interval": {
                "from": _anchor(last), "to": {"reference": _anchor(left), "candidate": _anchor(right)},
                "differences": changed}}
        last = left
    return {"equal": True, "last_matching_checkpoint": _anchor(last), "first_failing_interval": None}


def _worker_command(recording, rom_path, candidate, observations, diagnostics=None):
    command = [sys.executable, "-m", "aladdin_sega", "replay", str(recording), "--rom", str(rom_path),
               "--candidate", candidate, "--observations", str(observations)]
    if diagnostics is not None:
        command.extend(("--diagnostics", str(diagnostics)))
    return command


def _write_report(output, report):
    if output is not None:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _comparison_paths(output, temporary):
    """Keep derived observations beside the report when the caller requested output."""
    if output is None:
        return None, temporary / "reference.observations.json", temporary / "candidate.observations.json"
    output = Path(output)
    if output.suffix:
        output.parent.mkdir(parents=True, exist_ok=True)
        stem = output.with_suffix("")
        return output, stem.with_name(stem.name + ".reference.observations.json"), stem.with_name(stem.name + ".candidate.observations.json")
    output.mkdir(parents=True, exist_ok=True)
    return output / "comparison.json", output / "reference.observations.json", output / "candidate.observations.json"


def compare_replay(rom_path, recording, *, candidate, timeout_seconds=120, output=None, diagnostics=False):
    """Run original and candidate independently, then compare only their outputs."""
    rom_path, recording = Path(rom_path).resolve(), Path(recording).resolve()
    if diagnostics and output is None:
        raise ValueError("Diagnostic captures require an output path")
    recording_data = artifacts.read_bounded(recording)
    report = {"candidate": candidate,
              "replay_sha256": artifacts.digest(recording_data), "timeout_seconds": timeout_seconds,
              "contract": "full-machine-frame-pcm-60frames-v1", "evidence_level": "integrated-same-model",
              "compared": False}
    with tempfile.TemporaryDirectory(prefix="aladdin-compare-") as temporary:
        temporary = Path(temporary)
        report_path, reference_file, candidate_file = _comparison_paths(output, temporary)
        diagnostic_dir = None
        worker_recording = recording
        if diagnostics:
            diagnostic_dir = Path(tempfile.mkdtemp(prefix="diagnostics-", dir=report_path.parent)).resolve()
            worker_recording = diagnostic_dir / "reproducer.alreplay"
            worker_recording.write_bytes(recording_data)
        def save_report():
            if diagnostic_dir is not None:
                from .diagnostics import compare
                report["diagnostics"] = compare(diagnostic_dir)
                report["diagnostics"]["replay_sha256"] = report["replay_sha256"]
            _write_report(report_path, report)
        reference_command = _worker_command(worker_recording, rom_path, "original", reference_file,
                                             diagnostic_dir / "reference" if diagnostics else None)
        candidate_command = _worker_command(worker_recording, rom_path, candidate, candidate_file,
                                             diagnostic_dir / "candidate" if diagnostics else None)
        report["reproducer"] = {"reference": reference_command, "candidate": candidate_command}
        try:
            reference = run_worker("reference", reference_command, timeout_seconds=timeout_seconds)
            candidate_result = run_worker("candidate", candidate_command, timeout_seconds=timeout_seconds)
        except WorkerError as error:
            status = "CANDIDATE_ERROR" if type(error) is WorkerFailure and error.role == "candidate" else error.kind
            report.update(status=status, worker=error.report())
            if error.role == "candidate":
                report["reference"] = reference.payload
                if candidate_file.exists() and reference_file.exists():
                    left = json.loads(reference_file.read_text(encoding="utf-8"))
                    right = json.loads(candidate_file.read_text(encoding="utf-8"))
                    partial = compare_observations(left, right)
                    partial["execution_failure"] = error.report()
                    report["comparison"] = partial
            save_report()
            return report
        try:
            reference_observations = json.loads(reference_file.read_text(encoding="utf-8"))
            candidate_observations = json.loads(candidate_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            report.update(status="ERROR", detail=f"invalid worker observation file: {error}")
            save_report()
            return report
        comparison = compare_observations(reference_observations, candidate_observations)
        payload_fields = ("state_sha256", "frame_sha256", "pcm_sha256", "pcm_bytes")
        payload_differences = {field: {"reference": reference.payload.get(field), "candidate": candidate_result.payload.get(field)}
                               for field in payload_fields if reference.payload.get(field) != candidate_result.payload.get(field)}
        comparison["terminal_payload"] = {"equal": not payload_differences, "differences": payload_differences}
        comparison["equal"] = comparison["equal"] and not payload_differences
        report["compared"] = True
        report["observations"] = {
            "reference": {"path": str(reference_file), "sha256": artifacts.digest(reference_file.read_bytes()),
                          "count": len(reference_observations)},
            "candidate": {"path": str(candidate_file), "sha256": artifacts.digest(candidate_file.read_bytes()),
                          "count": len(candidate_observations)},
        }
        if candidate != "original" and candidate_result.payload.get("candidate_stats", {}).get("candidate_hits", 0) <= 0:
            report.update(reference=reference.payload, candidate_receipt=candidate_result.payload, comparison=comparison,
                          status="NOT_EXERCISED")
            save_report()
            return report
        report.update(reference=reference.payload, candidate_receipt=candidate_result.payload, comparison=comparison,
                      status="PASS" if comparison["equal"] else "DIVERGENCE")
        save_report()
        return report


def _load_replay(data, machine):
    kwargs = {"rom_sha256": machine.rom_sha256, "state_version": machine.state_version}
    return artifacts.load_replay(data, **kwargs)


def _load_snapshot(data, machine):
    kwargs = {"rom_sha256": machine.rom_sha256, "state_version": machine.state_version}
    return artifacts.load_snapshot(data, **kwargs)


def _fresh_replay(path, rom_path, *, timeout_seconds):
    command = [sys.executable, "-m", "aladdin_sega", "replay", str(path), "--rom", str(rom_path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as error:
        raise WorkerTimeout("fresh-process", command, f"worker exceeded {timeout_seconds:g} seconds") from error
    if result.returncode:
        raise WorkerFailure("fresh-process", command, "Fresh-process replay failed", stdout=result.stdout,
                            stderr=result.stderr, returncode=result.returncode)
    return _last_json(result.stdout)


def snapshot_check(rom, rom_path, recording, *, timeout_seconds=60):
    data = artifacts.read_bounded(recording)
    with Machine(rom) as machine:
        meta, initial, events = _load_replay(data, machine)
        artifacts.restore_snapshot(machine, initial)
        cursor = len(events) // 2
        checkpoint_tick = events[cursor - 1]["tick"] if cursor else machine.info["tick"]
        artifacts.play_events(machine, events[:cursor], checkpoint_tick)
        checkpoint = artifacts.snapshot_bytes(machine)
        suffix = events[cursor:]
        derived = artifacts.Recorder(machine, origin="synthetic", reset_provenance="derived-checkpoint")
        derived.events = [{**event, "seq": i} for i, event in enumerate(suffix)]
        machine.audio(); pcm = hashlib.sha256()
        artifacts.play_events(machine, suffix, meta["terminal_tick"], audio_sink=pcm.update)
        expected, expected_frame, expected_pcm = artifacts.digest(machine.snapshot()), artifacts.digest(machine.frame()[2]), pcm.hexdigest()
        suffix_archive = derived.finish(machine)
    with tempfile.TemporaryDirectory(prefix="aladdin-snapshot-") as tmp:
        path = Path(tmp) / "suffix.alreplay"; path.write_bytes(suffix_archive)
        actual = _fresh_replay(path, rom_path, timeout_seconds=timeout_seconds)
        if actual.get("state_sha256") != expected: raise RuntimeError("Fresh-process snapshot suffix diverged")
        if actual.get("frame_sha256") != expected_frame or actual.get("pcm_sha256") != expected_pcm:
            raise RuntimeError("Fresh-process snapshot suffix output diverged")
    return {"status": "PASS", "scope": "fresh-process original suffix: full state, final frame, all suffix PCM",
            "replay_sha256": artifacts.digest(data), "checkpoint_sha256": artifacts.digest(checkpoint),
            "next_event_index": cursor, "suffix_events": len(suffix), "state_sha256": expected,
            "pcm_sha256": expected_pcm, "frame_sha256": expected_frame, "cross_platform": "UNVERIFIED"}


def check_saved_snapshots(rom, rom_path, recording, snapshots, *, timeout_seconds=60):
    """Match separately saved live states against replay, then resume their suffixes."""
    data, matches = artifacts.read_bounded(recording), []
    with Machine(rom) as machine:
        meta, initial, events = _load_replay(data, machine)
        checkpoints = []
        for path in snapshots:
            raw = artifacts.read_bounded(path); info, state = _load_snapshot(raw, machine)
            checkpoints.append((info["tick"], str(path), raw, state))
        artifacts.restore_snapshot(machine, initial); cursor = 0
        def observe_pcm(pcm):
            for match in matches: match["pcm"].update(pcm)
        for tick, path, raw, state in sorted(checkpoints):
            if tick < machine.info["tick"] or tick > meta["terminal_tick"]: raise ValueError(f"Snapshot outside recording interval: {path}")
            end = cursor
            while end < len(events) and events[end]["tick"] < tick: end += 1
            artifacts.play_events(machine, events[cursor:end], tick, audio_sink=observe_pcm); cursor = end
            while machine.snapshot() != state:
                if cursor >= len(events) or events[cursor]["tick"] != tick: raise RuntimeError(f"Saved snapshot does not match original replay: {path}")
                machine.pad(events[cursor]["buttons"]); cursor += 1
            matches.append({"path": path, "tick": tick, "sha256": artifacts.digest(raw), "next_event_index": cursor, "initial": raw, "pcm": hashlib.sha256()})
        artifacts.play_events(machine, events[cursor:], meta["terminal_tick"], audio_sink=observe_pcm)
        expected_state, expected_frame = artifacts.digest(machine.snapshot()), artifacts.digest(machine.frame()[2])
    with tempfile.TemporaryDirectory(prefix="aladdin-live-snapshots-") as tmp:
        for index, match in enumerate(matches):
            remaining, expected_pcm = events[match["next_event_index"]:], match.pop("pcm").hexdigest()
            with Machine(rom) as machine:
                artifacts.restore_snapshot(machine, match["initial"])
                recorder = artifacts.Recorder(machine, origin="synthetic", reset_provenance="derived-from-user-snapshot")
                recorder.events = [{**e, "seq": i} for i, e in enumerate(remaining)]
                pcm = hashlib.sha256(); artifacts.play_events(machine, remaining, meta["terminal_tick"], audio_sink=pcm.update)
                if artifacts.digest(machine.snapshot()) != expected_state or artifacts.digest(machine.frame()[2]) != expected_frame: raise RuntimeError(f"Saved snapshot continuation diverged: {match['path']}")
                suffix = recorder.finish(machine)
                if pcm.hexdigest() != expected_pcm: raise RuntimeError(f"Saved snapshot PCM differs from uninterrupted replay: {match['path']}")
            path = Path(tmp) / f"suffix-{index}.alreplay"; path.write_bytes(suffix)
            actual = _fresh_replay(path, rom_path, timeout_seconds=timeout_seconds)
            if (actual.get("state_sha256"), actual.get("frame_sha256"), actual.get("pcm_sha256")) != (expected_state, expected_frame, expected_pcm): raise RuntimeError(f"Fresh-process saved snapshot diverged: {match['path']}")
            del match["initial"]; match.update(status="PASS", suffix_events=len(remaining), pcm_sha256=expected_pcm)
    return {"status": "PASS", "scope": "live snapshots match replay; their fresh-process suffixes match full state, final frame and PCM",
            "replay_sha256": artifacts.digest(data), "snapshots": matches, "state_sha256": expected_state,
            "frame_sha256": expected_frame, "cross_platform": "UNVERIFIED"}
