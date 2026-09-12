"""User launch and headless diagnostics use the same machine and artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from . import artifacts
from .machine import Machine, NativeError, library_path, load_library
from .profile import DEFAULT_ROM, FRAME_TICKS, MASTER_HZ, PROFILE_SHA256, read_rom
from .receipt import execution_receipt
from .verification import WorkerError


def emit(value):
    print(json.dumps(value, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aladdin-sega")
    sub = parser.add_subparsers(dest="command", required=True)
    candidates = ["original", "leaf", "composed", "mutant-result", "mutant-continuation", "mutant-timing"]
    for name in ("doctor", "boot-check", "play", "replay", "snapshot-check", "resume-check", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--rom", type=Path, default=DEFAULT_ROM)
        p.add_argument("--compatibility", help="Explicit named capture-to-runtime qualification (default: exact source identity)")
        if name in {"replay", "snapshot-check", "resume-check", "compare"}:
            p.add_argument("artifact", type=Path)
        if name in {"snapshot-check", "compare"}:
            p.add_argument("--timeout-seconds", type=float, default=120)
        if name in {"replay", "compare"}:
            p.add_argument("--candidate", choices=candidates, default="original" if name == "replay" else "leaf")
        if name == "compare":
            p.add_argument("--output", type=Path, default=Path("artifacts/comparison"))
        if name in {"boot-check", "play"}:
            p.add_argument("--frames", type=int, default=300 if name == "boot-check" else 0)
        if name == "play":
            p.add_argument("--mode", choices=["original"], default="original")
            p.add_argument("--mute", action="store_true")
            p.add_argument("--record-from-start", action="store_true",
                           help="Record immediately from reset or --snapshot; F5 stops and saves")
            p.add_argument("--snapshot", type=Path, help="Continue playing from a saved .alsnap")
            p.add_argument("--audio-report", type=Path, help="Write host audio buffer diagnostics on exit")
        if name == "boot-check":
            p.add_argument("--output", type=Path, default=Path("artifacts/boot"))
        if name == "resume-check":
            p.add_argument("--target", type=int, required=True)
        if name == "replay":
            p.add_argument("--headless", action="store_true", default=True)
            p.add_argument("--mode", choices=["original"], default="original")
            p.add_argument("--observations", type=Path, help="Write ordered derived state/frame/PCM checkpoints")
        if name == "snapshot-check":
            p.add_argument("--fresh-process", action="store_true", default=True)
            p.add_argument("--snapshot", type=Path, action="append", default=[],
                           help="Also match a separately saved live snapshot against this recording (repeatable)")
    args = parser.parse_args(argv)
    try:
        rom = read_rom(args.rom)
        start_receipt = execution_receipt(compatibility=args.compatibility) if args.command in {"replay", "resume-check"} else None
        if args.command == "doctor":
            lib = load_library()
            emit({"status": "PASS", "scope": "ROM and native ABI availability", "python": platform.python_version(),
                  "host": platform.platform(), "native_library": str(library_path()),
                  "source_id": lib.al_source_id().decode(), "profile_sha256": PROFILE_SHA256,
                  "receipt": execution_receipt(compatibility=args.compatibility)})
        elif args.command == "play":
            from .frontend import play
            play(rom, frames=args.frames, mute=args.mute, record_from_start=args.record_from_start,
                 snapshot=args.snapshot, audio_report=args.audio_report, compatibility=args.compatibility)
        elif args.command == "compare":
            from .verification import compare_replay
            result = compare_replay(args.rom.resolve(), args.artifact.resolve(), candidate=args.candidate,
                                    compatibility=args.compatibility, timeout_seconds=args.timeout_seconds, output=args.output)
            emit(result)
            return 0 if result["status"] == "PASS" else 1
        elif args.command == "boot-check":
            if args.frames <= 0:
                raise ValueError("--frames must be positive")
            with Machine(rom) as machine:
                begin = time.perf_counter()
                # Drain each frame, as playback does, so all generated PCM is hashed.
                pcm = hashlib.sha256()
                pcm_bytes = 0
                for frame in range(1, args.frames + 1):
                    machine.run(target=frame * FRAME_TICKS)
                    sound = machine.audio()
                    pcm.update(sound)
                    pcm_bytes += len(sound)
                wall = time.perf_counter() - begin
                width, height, rgb = machine.frame()
                snap = artifacts.snapshot_bytes(machine)
                original = machine.snapshot()
                artifacts.restore_snapshot(machine, snap)
                if machine.snapshot() != original:
                    raise NativeError("Immediate snapshot round trip diverged")
                args.output.mkdir(parents=True, exist_ok=True)
                (args.output / "frame.ppm").write_bytes(f"P6\n{width} {height}\n255\n".encode() + rgb)
                (args.output / "state.alsnap").write_bytes(snap)
                result = {"status": "PASS", "scope": "cold boot; immediate same-process snapshot round trip",
                          **machine.info, "source_id": machine.source_id, "host": platform.platform(),
                          "profile_sha256": PROFILE_SHA256, "frames": args.frames,
                          "emulated_seconds": machine.info["tick"] / MASTER_HZ, "wall_seconds": wall,
                          "realtime_ratio": machine.info["tick"] / MASTER_HZ / wall,
                          "audio_emulated": True, "pcm_bytes": pcm_bytes, "pcm_sha256": pcm.hexdigest(),
                          "frame_sha256": artifacts.digest(rgb), "state_sha256": artifacts.digest(original),
                          "instrumentation": "per-frame PCM drain; component timings unmeasured"}
                (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
                emit(result)
        elif args.command == "snapshot-check":
            from .verification import snapshot_check, check_saved_snapshots
            if args.snapshot:
                emit(check_saved_snapshots(rom, args.rom.resolve(), args.artifact, args.snapshot,
                                          compatibility=args.compatibility, timeout_seconds=args.timeout_seconds))
            else:
                emit(snapshot_check(rom, args.rom.resolve(), args.artifact,
                                    compatibility=args.compatibility, timeout_seconds=args.timeout_seconds))
        else:
            with Machine(rom, compatibility=args.compatibility) as machine:
                data = artifacts.read_bounded(args.artifact)
                pcm = hashlib.sha256()
                candidate = observer = None
                pcm_bytes = 0
                def audio_sink(sound):
                    nonlocal pcm_bytes
                    pcm.update(sound)
                    pcm_bytes += len(sound)
                    if observer:
                        observer.pcm(sound)
                if args.command == "replay":
                    meta, initial, events = artifacts.load_replay(data, rom_sha256=machine.rom_sha256, source_id=machine.source_id,
                                                               compatibility=args.compatibility)
                    artifacts.restore_snapshot(machine, initial)
                    if args.candidate != "original":
                        from .recovery import Candidate
                        candidate = Candidate(args.candidate)
                        candidate.arm(machine)
                    if args.observations:
                        from .verification import Observer
                        observer = Observer()
                    try:
                        artifacts.play_events(machine, events, meta["terminal_tick"], audio_sink=audio_sink,
                                              on_gate=candidate.on_gate if candidate else None,
                                              on_checkpoint=observer.checkpoint if observer else None)
                    except BaseException:
                        if observer:
                            args.observations.parent.mkdir(parents=True, exist_ok=True)
                            observer.write(args.observations)  # completed checkpoints only
                        raise
                    if observer:
                        observer.finish(machine, meta["terminal_tick"])
                        args.observations.parent.mkdir(parents=True, exist_ok=True)
                        observer.write(args.observations)
                else:
                    artifacts.restore_snapshot(machine, data)
                    artifacts.play_events(machine, [], args.target, audio_sink=audio_sink)
                receipt = execution_receipt(artifact_sha256=artifacts.digest(data),
                           capture_source=meta["source_id"] if args.command == "replay" else None,
                           candidate=args.candidate if args.command == "replay" else "original", compatibility=args.compatibility)
                if any(start_receipt[key] != receipt[key] for key in ("python_modules_sha256", "native_binary_sha256")):
                    raise RuntimeError("Implementation files changed during execution; rerun in a fresh process for a valid receipt")
                emit({"status": "COMPLETED", "compared": False, "scope": "successful execution; no equivalence verdict", **machine.info,
                      "candidate_stats": candidate.stats if candidate else {}, "pcm_bytes": pcm_bytes,
                      "interpreted_m68k_instructions": machine.info["m68k_instructions"] - (candidate.stats.get("replaced_m68k_instructions", 0) if candidate else 0),
                      "receipt": receipt,
                      "state_sha256": artifacts.digest(machine.snapshot()), "source_id": machine.source_id,
                      "frame_sha256": artifacts.digest(machine.frame()[2]), "pcm_sha256": pcm.hexdigest()})
        return 0
    except FileNotFoundError as e:
        emit({"status": "MISSING_INPUT", "detail": str(e)})
        return 2
    except subprocess.TimeoutExpired as e:
        emit({"status": "TIMEOUT", "detail": str(e), "timeout_seconds": e.timeout})
        return 3
    except WorkerError as e:
        emit({"status": e.kind, **e.report()})
        return 3 if e.kind == "TIMEOUT" else 1
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, ImportError) as e:
        emit({"status": "ERROR", "detail": str(e)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
