"""Strict Genesis comparisons over cold-start input histories."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from . import artifacts
from .history import HistoryStore, write_json
from .history_runtime import GenesisRun
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
    if payload.get("status") not in ("COMPLETED", "DIVERGED") or payload.get("compared") is not False:
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




def _executing_modules(receipt, candidate):
    """The modules whose edit during a run would change what ran: all of them for a candidate, the shared
    package's for the original (a game's recovered code is not executed by it, and another agent editing
    that code while an oracle run is in flight must not invalidate the oracle)."""
    modules = receipt["python_modules_sha256"]
    if candidate == "original":
        return {k: v for k, v in modules.items() if k.startswith("genesis_re/")}
    return modules


class _StopAtDivergence(Exception):
    def __init__(self, frame):
        super().__init__(frame)
        self.frame = frame


def execute_history(game, store, rom, *, node=None, candidate="original", tree=False, use_cache=False,
                    expected=None):
    """Execute logical paths; traversal caches belong to this implementation only.

    Tree verification starts cold and caches only states just computed in that
    traversal. Persistent player caches are used only when explicitly requested.
    ``expected`` (a cold run only) is the oracle's observation list for the
    selected history: execution stops at the first frame whose observation
    differs from it and the payload says ``DIVERGED`` with the frames observed
    so far -- what a negative control needs, which is the first difference,
    not the rest of the history.
    """
    if store.root != game.history_root:
        raise ValueError(f"History store {store.path} is not a {game.title} original-machine history")
    nodes = store.nodes() if tree else None
    selected = store.resolve(node or "main")
    start = execution_receipt(game, candidate=candidate)
    observations, endpoints = {}, {}
    executed_frames = restores = 0
    stopped = None
    if expected is not None and tree:
        raise ValueError("Stopping at a divergence needs a cold run of one history")
    with GenesisRun(game, rom, candidate) as run:
        if tree:
            children = {key: [] for key in nodes}
            for key, value in nodes.items():
                if value["parent"] is not None:
                    children[value["parent"]].append(key)
            # An explicit traversal stack avoids a Python recursion limit on
            # a long playthrough with many manual checkpoints.
            stack = [(store.root_id, run.save())]
            while stack:
                key, saved = stack.pop()
                run.restore(saved)
                if key != store.root_id:
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
                    if key != store.root_id and run.restore_cache(store, key):
                        restored = True
                        restores = 1
                        break
            before = run.frame
            edge = []
            events = [event for event in path["events"] if event["frame"] >= run.frame]

            def observe(r):
                value = r.observable()
                edge.append(value)
                if expected is not None:
                    index = len(edge) - 1
                    if index >= len(expected) or expected[index] != value:
                        raise _StopAtDivergence(value["frame"])
            try:
                run.advance(path["end_frame"], events, observe)
            except _StopAtDivergence as stop:
                stopped = stop.frame
            executed_frames = run.frame - before
            observations[selected] = edge
            if stopped is None:
                endpoints[selected] = run.observable()
        stats = dict(run.candidate.stats) if run.candidate else {}
        implementation = run.implementation
    end = execution_receipt(game, candidate=candidate)
    if _executing_modules(start, candidate) != _executing_modules(end, candidate) or             start["native_binary_sha256"] != end["native_binary_sha256"]:
        raise RuntimeError("Implementation changed during history execution")
    return {"status": "COMPLETED" if stopped is None else "DIVERGED", "compared": False, "root": store.root_id,
            "game": game.id, "history_id": selected, "mode": "tree" if tree else "cached" if use_cache else "cold",
            "observations": observations, "endpoints": endpoints, "stopped_frame": stopped,
            "executed_frames": executed_frames, "restores": restores,
            "candidate_stats": stats, "implementation": implementation, "receipt": end}


def _validate_execution(payload, store, selected, tree, candidate, receipt, shared_only=False, may_stop=False):
    diverged = may_stop and payload.get("status") == "DIVERGED" and not tree
    if (("DIVERGED" if diverged else payload.get("status")), payload.get("compared"), payload.get("root"),
            payload.get("game"), payload.get("history_id"), payload.get("mode")) != (
            "DIVERGED" if diverged else "COMPLETED", False, store.root_id, receipt["game"], selected,
            "tree" if tree else "cold"):
        raise ValueError("Worker history/execution contract mismatch")
    actual_receipt = payload.get("receipt", {})
    if actual_receipt.get("native_binary_sha256") != receipt["native_binary_sha256"]:
        raise ValueError("Worker implementation receipt mismatch: native_binary_sha256")
    recorded, current = actual_receipt.get("python_modules_sha256", {}), receipt["python_modules_sha256"]
    if shared_only:
        # A cached original stream: the game's recovered code never ran in it, so only the
        # shared package must still be what executed (the rest of its identity is the oracle key).
        recorded = {k: v for k, v in recorded.items() if k.startswith("genesis_re/")}
        current = {k: v for k, v in current.items() if k.startswith("genesis_re/")}
    if recorded != current:
        raise ValueError("Worker implementation receipt mismatch: python_modules_sha256")
    if payload.get("implementation", {}).get("candidate") != candidate:
        raise ValueError("Worker candidate identity mismatch")
    nodes = store.nodes() if tree else {selected: store.node(selected)}
    if diverged:
        # Stopped at the first differing frame: every observation before it is a full one.
        values = payload.get("observations", {}).get(selected)
        if not values or values[-1]["frame"] != payload.get("stopped_frame"):
            raise ValueError("Worker stopped without the differing observation")
        for frame, value in enumerate(values, 1):
            if set(value) != _REQUIRED or value["frame"] != frame:
                raise ValueError("Incomplete or unordered frame observation")
        return
    if set(payload.get("endpoints", {})) != set(nodes):
        raise ValueError("Worker omitted a history endpoint")
    observed = set(nodes) - {store.root_id} if tree else set(nodes)
    if set(payload.get("observations", {})) != observed:
        raise ValueError("Worker omitted a history input segment")
    required = _REQUIRED
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


def _run_workers(roles, commands, *, timeout_seconds, parallel, runner=None):
    """Run the reference and candidate workers; report the first failure in role order.

    The two workers share nothing but the read-only history and ROM, so they
    may run at the same time.  Each keeps its own watchdog; the report names
    the worker whose watchdog expired.
    """
    if not parallel:
        for role in roles:
            run_worker(role, commands[role], timeout_seconds=timeout_seconds, runner=runner)
        return
    errors = {}
    with ThreadPoolExecutor(max_workers=len(roles)) as pool:
        futures = {role: pool.submit(run_worker, role, commands[role],
                                     timeout_seconds=timeout_seconds, runner=runner) for role in roles}
        for role in roles:
            try:
                futures[role].result()
            except WorkerError as error:
                errors[role] = error
    for role in roles:
        if role in errors:
            raise errors[role]


_REQUIRED = {"frame", "buttons", "state_sha256", "frame_sha256", "pcm_sha256", "pcm_bytes",
             "tick", "pc", "sr", "m68k_cycles", "m68k_instructions", "z80_instructions", "vblanks"}


def oracle_key(game, receipt, identities, rom_sha256, tree):
    """What the original's observation stream of a history depends on, hashed.

    The shared package's modules, the native binary and source, the cartridge
    profile, the observation instant and the cache contract, the ROM, the
    history's flattened inputs and the mode -- and not the game's own
    recovered code, which the original never executes.  Two runs with the
    same key observe the same stream (the original is deterministic: checked
    run-against-run on every recording before the cache existed), so the
    reference worker's stream is stored under it and reused by every later
    comparison of any candidate until one of those inputs changes.
    """
    from .history_runtime import CACHE_CONTRACT
    shared = {k: v for k, v in receipt["python_modules_sha256"].items() if k.startswith("genesis_re/")}
    record = {"shared_modules": shared, "native_binary_sha256": receipt["native_binary_sha256"],
              "native_source_id": receipt["native_source_id"], "profile_sha256": game.profile_sha256,
              "observation_offset_ticks": game.observation_offset_ticks, "cache_contract": CACHE_CONTRACT,
              "rom_sha256": rom_sha256, "inputs": identities, "mode": "tree" if tree else "cold"}
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def oracle_cache_path(game, key):
    root = os.environ.get("GENESIS_ORACLE_CACHE")
    return (Path(root) / game.id if root else Path("artifacts") / game.id / "oracle") / (key + ".json")


def compare_history(game, store_path, rom_path, *, node=None, candidate="lifecycle", tree=False,
                    output=Path("artifacts/comparison"), timeout_seconds=120, parallel=True,
                    runner=None, use_oracle_cache=True, expect="pass"):
    """Separate fresh workers, strict per-frame state/video/PCM and final equality.

    The original's stream is the oracle: once a comparison has executed and
    validated it for a history under an ``oracle_key``, later comparisons of
    any candidate reuse that stream (``artifacts/<game>/oracle/<key>.json``)
    and run only the candidate worker; ``use_oracle_cache=False`` executes the
    original again and refreshes the entry.  The report says which
    (``oracle``), and the candidate's receipt -- the one evidence is judged by
    -- is always fresh.  ``expect="divergence"`` (a negative control) lets the
    candidate worker stop at the first frame that differs from the cached
    stream instead of finishing the history; the verdict is the same
    DIVERGENCE with the same first difference, and a control that never
    differs still runs to the end and reports PASS.
    """
    store = HistoryStore(store_path, game.history_root)
    selected = store.resolve(node or "main")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    identities = {key: store.flatten(key) for key in store.nodes()} if tree else store.flatten(selected)
    payloads = {}
    receipt = execution_receipt(game)
    rom_sha256 = hashlib.sha256(Path(rom_path).read_bytes()).hexdigest()
    key = oracle_key(game, receipt, identities, rom_sha256, tree)
    cache = oracle_cache_path(game, key)
    cached = use_oracle_cache and cache.is_file()
    report = {"game": game.id, "history_id": selected, "tree": tree, "candidate": candidate,
              "contract": "strict-genesis-every-canonical-frame", "status": "ERROR",
              "workers": "parallel" if parallel else "sequential", "expect": expect,
              "oracle": {"key": key, "cached": cached, "path": str(cache)}}
    stop_early = expect == "divergence" and cached and not tree
    try:
        roles = (("reference", "original"), ("candidate", candidate))
        commands = {}
        for role, choice in roles:
            result_path = output / (role + ".json")
            command = [sys.executable, "-m", "genesis_re", "history-run", selected, "--game", game.id,
                       "--history", str(Path(store_path).resolve()), "--rom", str(Path(rom_path).resolve()),
                       "--candidate", choice, "--output", str(result_path.resolve())]
            if tree:
                command.append("--tree")
            if role == "candidate" and stop_early:
                command += ["--stop-at-divergence-from", str(cache.resolve())]
            commands[role] = command
        if cached:
            payloads["reference"] = json.loads(cache.read_text())
            if payloads["reference"].get("oracle_key") != key:
                raise ValueError("Oracle cache entry does not carry its own key")
            _validate_execution(payloads["reference"], store, selected, tree, "original", receipt, shared_only=True)
            del commands["reference"]
        _run_workers(list(commands), commands, timeout_seconds=timeout_seconds, parallel=parallel, runner=runner)
        for role, choice in roles:
            if role in commands:
                payloads[role] = json.loads((output / (role + ".json")).read_text())
                _validate_execution(payloads[role], store, selected, tree, choice, receipt,
                                    may_stop=(role == "candidate" and stop_early))
        if not cached and use_oracle_cache:
            entry = dict(payloads["reference"], oracle_key=key, oracle_from=str(output.resolve()))
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_suffix(".tmp")
            temporary.write_text(json.dumps(entry))
            temporary.replace(cache)
        left, right = payloads["reference"], payloads["candidate"]
        equal = left["observations"] == right["observations"] and left["endpoints"] == right["endpoints"]
        if right.get("status") == "DIVERGED":
            equal = False
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
        # A watchdog expiry or a missing dependency is reported by its own
        # class for either worker; only an execution failure of the candidate
        # keeps the CANDIDATE_ERROR name.  ``error.worker`` names the role.
        if error.kind == "ERROR":
            status = "CANDIDATE_ERROR" if error.role == "candidate" else "ERROR"
        else:
            status = error.kind
        report.update(status=status, error=error.report())
    except (OSError, ValueError, KeyError) as error:
        report.update(status="ERROR", error=str(error))
    write_json(output / "comparison.json", report)
    return report
