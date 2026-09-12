"""Compare an immutable b3c78ac replay worker with the current qualified build.

The baseline child intentionally imports only the preserved package.  The
parent delays every current-package import until that process has exited, so a
new Python wrapper cannot accidentally become the reference implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "artifacts" / "baseline-b3c78ac"
DEFAULT_CURRENT_NATIVE = ROOT / "build" / "libaladdin_native.dll"
CHECKPOINT_FRAMES = 60


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def validate_baseline(directory: Path) -> tuple[Path, dict[str, Any]]:
    """Verify the preserved package against its receipt before executing it."""
    directory = directory.resolve()
    receipt_path = directory / "receipt.json"
    package = directory / "aladdin_sega"
    dll = package / "libaladdin_native.dll"
    if not receipt_path.is_file() or not package.is_dir() or not dll.is_file():
        raise FileNotFoundError("Baseline requires receipt.json and aladdin_sega/libaladdin_native.dll")
    receipt = read_json(receipt_path)
    expected = receipt.get("files")
    if not isinstance(expected, dict):
        raise ValueError("Baseline receipt has no file hashes")
    mismatches = []
    for relative, expected_hash in expected.items():
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise ValueError("Baseline receipt has invalid file hashes")
        actual_path = directory / Path(relative.replace("\\", "/"))
        if not actual_path.is_file() or sha256(actual_path) != expected_hash:
            mismatches.append(relative)
    if mismatches:
        raise ValueError("Baseline receipt mismatch: " + ", ".join(mismatches))
    return package, receipt


def baseline_environment(package: Path) -> dict[str, str]:
    """Do not inherit a current source-tree PYTHONPATH into the old worker."""
    dll = package / "libaladdin_native.dll"
    if not dll.is_file():
        raise FileNotFoundError(f"Baseline DLL not found: {dll}")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(package.parent)
    env["ALADDIN_NATIVE_LIBRARY"] = str(dll)
    return env


def current_environment(native: Path) -> dict[str, str]:
    native = native.resolve()
    if not native.is_file():
        raise FileNotFoundError(f"Current native DLL not found: {native}")
    env = dict(os.environ)
    source = str((ROOT / "src").resolve())
    env["PYTHONPATH"] = source
    env["ALADDIN_NATIVE_LIBRARY"] = str(native)
    return env


def _last_json(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("worker did not emit a JSON object")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _receipt_fingerprint(package: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    files = receipt["files"]
    return {
        "receipt_sha256": sha256(package.parent / "receipt.json"),
        "native_source_id": receipt.get("native_source_id"),
        "native_binary_sha256": files.get("aladdin_sega\\libaladdin_native.dll"),
        "python_modules_sha256": {name: value for name, value in files.items() if name.endswith(".py")},
        "python_module_path": str(package),
    }


def _baseline_worker_main(args: argparse.Namespace) -> int:
    """Wrapper with total PCM accounting; split keeps baseline imports local."""
    package, receipt = validate_baseline(Path(args.baseline_dir))
    sys.path.insert(0, str(package.parent))
    from aladdin_sega import artifacts
    from aladdin_sega.machine import Machine
    from aladdin_sega.profile import FRAME_TICKS

    recording, rom, output = Path(args.recording).resolve(), Path(args.rom).resolve(), Path(args.observations).resolve()
    with Machine(rom.read_bytes()) as machine:
        data = artifacts.read_bounded(recording)
        meta, initial, events = artifacts.load_replay(data, rom_sha256=machine.rom_sha256, source_id=machine.source_id)
        artifacts.restore_snapshot(machine, initial)
        total_pcm, total_bytes = hashlib.sha256(), 0
        chunk_pcm, chunk_bytes, records = hashlib.sha256(), 0, []
        period = FRAME_TICKS * CHECKPOINT_FRAMES
        next_checkpoint = (machine.info["tick"] // period + 1) * period

        def drain():
            nonlocal chunk_bytes, total_bytes
            sound = machine.audio()
            chunk_pcm.update(sound); total_pcm.update(sound)
            chunk_bytes += len(sound); total_bytes += len(sound)

        def checkpoint(identifier, requested_tick):
            nonlocal chunk_pcm, chunk_bytes
            info = machine.info
            _, _, frame = machine.frame()
            records.append({
                "id": str(identifier), "requested_tick": requested_tick, "actual_tick": info["tick"],
                "state_sha256": artifacts.digest(machine.snapshot()), "frame_sha256": artifacts.digest(frame),
                "pcm_sha256": chunk_pcm.hexdigest(), "pcm_bytes": chunk_bytes,
            })
            chunk_pcm, chunk_bytes = hashlib.sha256(), 0

        def advance(target):
            nonlocal next_checkpoint
            while machine.info["tick"] < target:
                current = machine.info["tick"]
                deadline = min(target, (current // FRAME_TICKS + 1) * FRAME_TICKS)
                reason = machine.run(target=deadline)
                info = machine.info
                if reason != "limit" or info["tick"] <= current:
                    raise RuntimeError(f"Baseline replay made no progress: reason={reason} tick={info['tick']} target={deadline}")
                drain()
                if machine.info["tick"] >= next_checkpoint:
                    checkpoint(next_checkpoint // period, next_checkpoint)
                    next_checkpoint += period

        for item in events:
            tick = item["tick"]
            if machine.info["tick"] < tick:
                advance(tick)
            if machine.info["tick"] != tick:
                raise ValueError("Recorded input tick is not reachable at this instruction boundary")
            machine.pad(item["buttons"])
        if machine.info["tick"] < meta["terminal_tick"]:
            advance(meta["terminal_tick"])
        if machine.info["tick"] != meta["terminal_tick"]:
            raise ValueError("Replay terminal tick is not reachable")
        checkpoint("terminal", meta["terminal_tick"])
        _write_json(output, records)
        print(json.dumps({
            "status": "COMPLETED", "compared": False, "scope": "preserved b3c78ac original execution",
            "source_id": machine.source_id, "state_sha256": artifacts.digest(machine.snapshot()),
            "frame_sha256": artifacts.digest(machine.frame()[2]), "pcm_sha256": total_pcm.hexdigest(),
            "pcm_bytes": total_bytes, "observation_count": len(records),
            "baseline_receipt": _receipt_fingerprint(package, receipt),
        }, sort_keys=True))
    return 0


def qualify(args: argparse.Namespace) -> dict[str, Any]:
    baseline_dir = Path(args.baseline_dir).resolve()
    package, baseline_receipt = validate_baseline(baseline_dir)
    recording, rom = Path(args.recording).resolve(), Path(args.rom).resolve()
    if not recording.is_file() or not rom.is_file():
        raise FileNotFoundError("Recording and ROM must both exist")
    input_hashes = {"recording_sha256": sha256(recording), "rom_sha256": sha256(rom)}
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    baseline_observations = output / "baseline.observations.json"
    current_observations = output / "current.observations.json"
    baseline_command = [sys.executable, str(Path(__file__).resolve()), "--baseline-worker",
                        "--baseline-dir", str(baseline_dir), "--recording", str(recording), "--rom", str(rom),
                        "--observations", str(baseline_observations)]
    baseline = subprocess.run(baseline_command, cwd=package.parent, env=baseline_environment(package),
                              capture_output=True, text=True, timeout=args.timeout_seconds, check=False)
    if baseline.returncode:
        raise RuntimeError("Baseline worker failed: " + baseline.stdout + baseline.stderr)
    baseline_payload = _last_json(baseline.stdout)
    if baseline_payload.get("status") != "COMPLETED" or baseline_payload.get("compared") is not False:
        raise RuntimeError("Baseline worker did not report successful execution")
    if input_hashes != {"recording_sha256": sha256(recording), "rom_sha256": sha256(rom)}:
        raise RuntimeError("Baseline worker mutated an immutable input")
    if baseline_payload.get("source_id") != baseline_receipt.get("native_source_id"):
        raise RuntimeError("Baseline worker source identity differs from its receipt")

    # Current imports begin only after the baseline process is completely done.
    sys.path.insert(0, str((ROOT / "src").resolve()))
    from aladdin_sega import verification
    current_native = Path(args.current_native).resolve()
    current_command = [sys.executable, "-m", "aladdin_sega", "replay", str(recording), "--rom", str(rom),
                       "--compatibility", "review-baseline-v1", "--observations", str(current_observations)]
    current = verification.run_worker("current", current_command, timeout_seconds=args.timeout_seconds,
                                      env=current_environment(current_native))
    if input_hashes != {"recording_sha256": sha256(recording), "rom_sha256": sha256(rom)}:
        raise RuntimeError("Current worker mutated an immutable input")
    reference = json.loads(baseline_observations.read_text(encoding="utf-8"))
    candidate = json.loads(current_observations.read_text(encoding="utf-8"))
    comparison = verification.compare_observations(reference, candidate)
    terminal_fields = ("state_sha256", "frame_sha256", "pcm_sha256", "pcm_bytes")
    terminal_differences = {field: {"baseline": baseline_payload.get(field), "current": current.payload.get(field)}
                            for field in terminal_fields if baseline_payload.get(field) != current.payload.get(field)}
    comparison["terminal_payload"] = {"equal": not terminal_differences, "differences": terminal_differences}
    comparison["equal"] = comparison["equal"] and not terminal_differences
    report = {
        "status": "PASS" if comparison["equal"] else "DIVERGENCE", "compared": True,
        "contract": "full-machine-frame-pcm-60frames-v1", "timeout_seconds": args.timeout_seconds,
        "inputs": input_hashes, "compatibility": "review-baseline-v1",
        "baseline": {"payload": baseline_payload, "receipt": _receipt_fingerprint(package, baseline_receipt),
                     "observations": {"path": str(baseline_observations), "sha256": sha256(baseline_observations), "count": len(reference)}},
        "current": {"payload": current.payload, "receipt": current.payload.get("receipt"),
                    "observations": {"path": str(current_observations), "sha256": sha256(current_observations), "count": len(candidate)}},
        "comparison": comparison,
        "reproducer": {"baseline": baseline_command, "current": current_command},
    }
    _write_json(output / "qualification.json", report)
    return report


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE)
    value.add_argument("--recording", type=Path)
    value.add_argument("--rom", type=Path)
    value.add_argument("--output", type=Path)
    value.add_argument("--current-native", type=Path, default=DEFAULT_CURRENT_NATIVE)
    value.add_argument("--timeout-seconds", type=float, default=120)
    value.add_argument("--baseline-worker", action="store_true", help=argparse.SUPPRESS)
    value.add_argument("--observations", type=Path, help=argparse.SUPPRESS)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.baseline_worker:
            if not all((args.recording, args.rom, args.observations)):
                raise ValueError("Baseline worker requires recording, ROM and observations")
            return _baseline_worker_main(args)
        if not all((args.recording, args.rom, args.output)):
            raise ValueError("--recording, --rom and --output are required")
        print(json.dumps(qualify(args), sort_keys=True))
        return 0
    except subprocess.TimeoutExpired as error:
        print(json.dumps({"status": "TIMEOUT", "detail": str(error), "timeout_seconds": args.timeout_seconds}, sort_keys=True))
        return 3
    except (FileNotFoundError, ValueError, OSError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "ERROR", "detail": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
