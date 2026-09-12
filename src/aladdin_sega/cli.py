"""User launch and headless diagnostics use the same machine and artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

from . import artifacts
from .machine import Machine, NativeError, library_path, load_library
from .profile import DEFAULT_ROM, FRAME_TICKS, MASTER_HZ, PROFILE_SHA256, read_rom


def emit(value):
    print(json.dumps(value, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aladdin-sega")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "boot-check", "play", "replay", "snapshot-check", "resume-check"):
        p = sub.add_parser(name)
        p.add_argument("--rom", type=Path, default=DEFAULT_ROM)
        if name in {"replay", "snapshot-check", "resume-check"}:
            p.add_argument("artifact", type=Path)
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
        if name == "snapshot-check":
            p.add_argument("--fresh-process", action="store_true", default=True)
            p.add_argument("--snapshot", type=Path, action="append", default=[],
                           help="Also match a separately saved live snapshot against this recording (repeatable)")
    args = parser.parse_args(argv)
    try:
        rom = read_rom(args.rom)
        if args.command == "doctor":
            lib = load_library()
            emit({"status": "PASS", "scope": "ROM and native ABI availability", "python": platform.python_version(),
                  "host": platform.platform(), "native_library": str(library_path()),
                  "source_id": lib.al_source_id().decode(), "profile_sha256": PROFILE_SHA256})
        elif args.command == "play":
            from .frontend import play
            play(rom, frames=args.frames, mute=args.mute, record_from_start=args.record_from_start,
                 snapshot=args.snapshot, audio_report=args.audio_report)
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
                emit(check_saved_snapshots(rom, args.rom.resolve(), args.artifact, args.snapshot))
            else:
                emit(snapshot_check(rom, args.rom.resolve(), args.artifact))
        else:
            with Machine(rom) as machine:
                data = artifacts.read_bounded(args.artifact)
                pcm = hashlib.sha256()
                if args.command == "replay":
                    meta, initial, events = artifacts.load_replay(data, rom_sha256=machine.rom_sha256, source_id=machine.source_id)
                    artifacts.restore_snapshot(machine, initial)
                    artifacts.play_events(machine, events, meta["terminal_tick"], audio_sink=pcm.update)
                else:
                    artifacts.restore_snapshot(machine, data)
                    artifacts.play_events(machine, [], args.target, audio_sink=pcm.update)
                emit({"status": "PASS", "scope": "original deterministic execution", **machine.info,
                      "state_sha256": artifacts.digest(machine.snapshot()), "source_id": machine.source_id,
                      "frame_sha256": artifacts.digest(machine.frame()[2]), "pcm_sha256": pcm.hexdigest()})
        return 0
    except FileNotFoundError as e:
        emit({"status": "MISSING_INPUT", "detail": str(e)})
        return 2
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, ImportError) as e:
        emit({"status": "ERROR", "detail": str(e)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
