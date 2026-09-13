"""Player and developer commands share one cold-start history model."""
import argparse
import json
from pathlib import Path

from .history import HistoryStore, write_json
from .history_runtime import Session
from .machine import load_library, library_path
from .profile import DEFAULT_ROM, read_rom
from .receipt import execution_receipt
from .verification import execute_history, compare_history


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aladdin-sega")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "play", "history-run", "history-verify", "history-validate",
                 "history-export", "history-capture"):
        p = sub.add_parser(name)
        p.add_argument("--rom", type=Path, default=DEFAULT_ROM)
        p.add_argument("--history", type=Path, default=Path("history"))
        if name in {"history-run", "history-verify", "history-export"}:
            p.add_argument("node", nargs="?", default="main")
        if name in {"history-run", "history-verify"}:
            p.add_argument("--candidate", default="original" if name == "history-run" else "lifecycle")
            p.add_argument("--tree", action="store_true")
            p.add_argument("--output", type=Path, default=Path("artifacts/comparison") if name == "history-verify" else None)
        if name == "history-run":
            mode = p.add_mutually_exclusive_group()
            mode.add_argument("--cold", action="store_true", help="Run continuously from reset; this is the default")
            mode.add_argument("--cache", action="store_true", help="Allow compatible player caches")
        if name == "history-verify":
            p.add_argument("--timeout-seconds", type=float, default=120)
        if name == "history-export":
            p.add_argument("--output", type=Path, required=True)
        if name == "history-capture":
            p.add_argument("--frames", type=int, required=True)
            p.add_argument("--input", action="append", default=[], metavar="FRAME:MASK")
            p.add_argument("--checkpoint", type=int, action="append", default=[])
        if name == "play":
            p.add_argument("--frames", type=int, default=0)
            p.add_argument("--mute", action="store_true")
            p.add_argument("--new", action="store_true")
            p.add_argument("--node", help="Checkpoint ID or main; omit to open history panel")
            p.add_argument("--audio-report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            lib = load_library()
            result = {"status": "PASS", "source_id": lib.al_source_id().decode(),
                      "native_library": str(library_path()), "receipt": execution_receipt()}
        elif args.command == "play":
            from .frontend import play
            if args.new and args.node:
                raise ValueError("Choose either --new or --node")
            play(read_rom(args.rom), frames=args.frames, mute=args.mute, history_path=args.history,
                 node=args.node, new=args.new, audio_report=args.audio_report)
            return 0
        else:
            store = HistoryStore(args.history)
            if args.command == "history-validate":
                result = {"status": "PASS", "nodes": len(store.nodes()), "main": store.resolve()}
            elif args.command == "history-export":
                result = store.flatten(store.resolve(args.node))
                write_json(args.output, result)
            elif args.command == "history-capture":
                if args.frames <= 0:
                    raise ValueError("--frames must be positive")
                changes = {}
                for item in args.input:
                    frame, buttons = map(lambda v:int(v, 0), item.split(":"))
                    if not 0 <= frame < args.frames or not 0 <= buttons <= 255 or frame in changes:
                        raise ValueError("Invalid or repeated frame input")
                    changes[frame] = buttons
                held = 0
                with Session(store, read_rom(args.rom)) as session:
                    for frame in range(args.frames):
                        held = changes.get(frame, held)
                        session.step(held)
                        if session.frame in args.checkpoint:
                            session.checkpoint(reason="constructed")
                result = {"status": "PASS", "history_id": store.resolve(), "frames": args.frames,
                          "provenance": "constructed input scenario"}
            elif args.command == "history-run":
                if args.tree and args.cache:
                    raise ValueError("Tree verification uses only its own freshly computed prefix states")
                result = execute_history(store, read_rom(args.rom), node=args.node,
                                         candidate=args.candidate, tree=args.tree, use_cache=args.cache)
                if args.output:
                    write_json(args.output, result)
                    result = {k:v for k,v in result.items() if k not in {"observations", "endpoints"}}
            else:
                result = compare_history(args.history, args.rom, node=args.node, candidate=args.candidate,
                                         tree=args.tree, output=args.output, timeout_seconds=args.timeout_seconds)
        print(json.dumps(result))
        return 0 if result.get("status", "PASS") in {"PASS", "COMPLETED"} else 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError) as error:
        print(json.dumps({"status": "ERROR", "detail": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
