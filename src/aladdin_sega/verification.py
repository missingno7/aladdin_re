"""Strict Genesis comparisons over cold-start input histories."""
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
from .history import HistoryStore, ROOT_ID, digest, encoded, write_json
from .history_runtime import GenesisRun
from .profile import read_rom
from .receipt import execution_receipt


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




def execute_history(store, rom, *, node=None, candidate="original", tree=False, use_cache=False):
    """Execute logical paths; traversal caches belong to this implementation only.

    Tree verification starts cold and caches only states just computed in that
    traversal. Persistent player caches are used only when explicitly requested.
    """
    nodes = store.nodes() if tree else None
    selected = store.resolve(node or "main")
    start = execution_receipt(candidate=candidate)
    observations, endpoints = {}, {}
    executed_frames = restores = 0
    with GenesisRun(rom, candidate) as run:
        if tree:
            children = {key: [] for key in nodes}
            for key, value in nodes.items():
                if value["parent"] is not None:
                    children[value["parent"]].append(key)
            # An explicit traversal stack avoids a Python recursion limit on
            # a long playthrough with many manual checkpoints.
            stack = [(ROOT_ID, run.save())]
            while stack:
                key, saved = stack.pop()
                run.restore(saved)
                if key != ROOT_ID:
                    restores += 1
                    branch = nodes[key]
                    edge = []
                    before = run.frame
                    run.advance(branch["end_frame"], branch["events"], lambda r: edge.append(r.observable()))
                    executed_frames += run.frame - before
                    observations[key] = edge
                endpoints[key] = run.observable()
                checkpoint = run.save()
                for child in sorted(children[key], reverse=True):
                    stack.append((child, checkpoint))
        else:
            path = store.flatten(selected)
            restored = False
            if use_cache:
                for key, _ in reversed(store.ancestry(selected)):
                    if key != ROOT_ID and run.restore_cache(store, key):
                        restored = True
                        restores = 1
                        break
            before = run.frame
            edge = []
            events = [event for event in path["events"] if event["frame"] >= run.frame]
            run.advance(path["end_frame"], events, lambda r: edge.append(r.observable()))
            executed_frames = run.frame - before
            observations[selected] = edge
            endpoints[selected] = run.observable()
        stats = dict(run.candidate.stats) if run.candidate else {}
        implementation = run.implementation
    end = execution_receipt(candidate=candidate)
    if any(start[k] != end[k] for k in ("python_modules_sha256", "native_binary_sha256")):
        raise RuntimeError("Implementation changed during history execution")
    return {"status": "COMPLETED", "compared": False, "root": ROOT_ID,
            "history_id": selected, "mode": "tree" if tree else "cached" if use_cache else "cold",
            "observations": observations, "endpoints": endpoints,
            "executed_frames": executed_frames, "restores": restores,
            "candidate_stats": stats, "implementation": implementation, "receipt": end}


def _validate_execution(payload, store, selected, tree, candidate, receipt):
    if (payload.get("status"), payload.get("compared"), payload.get("root"),
            payload.get("history_id"), payload.get("mode")) != (
            "COMPLETED", False, ROOT_ID, selected, "tree" if tree else "cold"):
        raise ValueError("Worker history/execution contract mismatch")
    actual_receipt = payload.get("receipt", {})
    for key in ("python_modules_sha256", "native_binary_sha256"):
        if actual_receipt.get(key) != receipt[key]:
            raise ValueError("Worker implementation receipt mismatch: " + key)
    if payload.get("implementation", {}).get("candidate") != candidate:
        raise ValueError("Worker candidate identity mismatch")
    nodes = store.nodes() if tree else {selected: store.node(selected)}
    if set(payload.get("endpoints", {})) != set(nodes):
        raise ValueError("Worker omitted a history endpoint")
    observed = set(nodes) - {ROOT_ID} if tree else set(nodes)
    if set(payload.get("observations", {})) != observed:
        raise ValueError("Worker omitted a history input segment")
    required = {"frame", "buttons", "state_sha256", "frame_sha256", "pcm_sha256", "pcm_bytes",
                "tick", "pc", "sr", "m68k_cycles", "m68k_instructions", "z80_instructions", "vblanks"}
    for key, node in nodes.items():
        endpoint = payload["endpoints"][key]
        if set(endpoint) != required or endpoint["frame"] != node["end_frame"] or endpoint["buttons"] != node["buttons"]:
            raise ValueError("Incomplete or misplaced terminal machine observation")
        if key in observed:
            start = store.node(node["parent"])["end_frame"] if tree else 0
            values = payload["observations"][key]
            if len(values) != node["end_frame"] - start:
                raise ValueError("Worker did not observe every canonical frame")
            for frame, value in enumerate(values, start + 1):
                if set(value) != required or value["frame"] != frame:
                    raise ValueError("Incomplete or unordered frame observation")
            if values and values[-1] != endpoint:
                raise ValueError("Worker terminal disagrees with final frame")


def compare_history(store_path, rom_path, *, node=None, candidate="lifecycle", tree=False,
                    output=Path("artifacts/comparison"), timeout_seconds=120):
    """Separate fresh workers, strict per-frame state/video/PCM and final equality."""
    store = HistoryStore(store_path)
    selected = store.resolve(node or "main")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    identities = {key: store.flatten(key) for key in store.nodes()} if tree else store.flatten(selected)
    payloads = {}
    receipt = execution_receipt()
    report = {"history_id": selected, "tree": tree, "candidate": candidate,
              "contract": "strict-genesis-every-canonical-frame", "status": "ERROR"}
    try:
        for role, choice in (("reference", "original"), ("candidate", candidate)):
            result_path = output / (role + ".json")
            command = [sys.executable, "-m", "aladdin_sega", "history-run", selected,
                       "--history", str(Path(store_path).resolve()), "--rom", str(Path(rom_path).resolve()),
                       "--candidate", choice, "--output", str(result_path.resolve())]
            if tree:
                command.append("--tree")
            run_worker(role, command, timeout_seconds=timeout_seconds)
            payloads[role] = json.loads(result_path.read_text())
            _validate_execution(payloads[role], store, selected, tree, choice, receipt)
        left, right = payloads["reference"], payloads["candidate"]
        equal = left["observations"] == right["observations"] and left["endpoints"] == right["endpoints"]
        first = None
        for key in left["observations"]:
            a, b = left["observations"][key], right["observations"].get(key, [])
            if a != b:
                for i in range(max(len(a), len(b))):
                    av, bv = a[i] if i < len(a) else None, b[i] if i < len(b) else None
                    if av != bv:
                        first = {"node": key, "reference": av, "candidate": bv}
                        break
                break
        current = {key: store.flatten(key) for key in store.nodes()} if tree else store.flatten(selected)
        if current != identities:
            raise ValueError("History graph changed during comparison")
        exercised = right["candidate_stats"].get("candidate_hits", 0)
        report.update(status=("PASS" if candidate == "original" or exercised else "NOT_EXERCISED") if equal else "DIVERGENCE",
                      comparison={"equal": equal, "first_difference": first},
                      reference={k:v for k,v in left.items() if k != "observations"},
                      candidate_receipt={k:v for k,v in right.items() if k != "observations"})
    except WorkerError as error:
        report.update(status="CANDIDATE_ERROR" if error.role == "candidate" else error.kind, error=error.report())
    except (OSError, ValueError, KeyError) as error:
        report.update(status="ERROR", error=str(error))
    write_json(output / "comparison.json", report)
    return report
