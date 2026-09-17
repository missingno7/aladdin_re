"""perf_snapshot: the cost of the native snapshot round trip (read-only research tooling).

    python scripts/research/perf_snapshot.py --game gods [--fixture artifacts/gods/evidence/main/boundary-6000.state] [--repeat 200]

Splits ``Machine.snapshot()`` (native ``al_export``: the PortForge field codec
plus two native SHA-256 passes, then a Python copy) from the pure native hash
work (``al_snapshot_tick`` validates a snapshot by recomputing both SHA-256
digests and nothing else), and times ``restore`` (``al_import``: the same two
hash passes plus the decoder), ``registers()``, ``info``, ``peek_ram`` and
``gates`` -- the crossings a gate handler and a planner make.  Reports
microseconds per call so the per-gate and per-frame budgets can be added up.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("GENESIS_NATIVE_LIBRARY", str(ROOT / "build" / "libgenesis_native.dll"))

from genesis_re.games import game as select_game   # noqa: E402
from genesis_re.machine import Machine              # noqa: E402


def timed(fn, repeat):
    t = time.perf_counter()
    for _ in range(repeat):
        fn()
    return (time.perf_counter() - t) / repeat


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", default="gods")
    parser.add_argument("--fixture", default=str(ROOT / "artifacts/gods/evidence/main/boundary-6000.state"))
    parser.add_argument("--repeat", type=int, default=200)
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)
    game = select_game(args.game)
    rom = game.read_rom()
    state = Path(args.fixture).read_bytes()
    report = {"fixture": Path(args.fixture).name, "snapshot_bytes": len(state), "repeat": args.repeat}
    t = time.perf_counter()
    lib_machine = Machine(rom, game)
    report["machine_create_seconds"] = round(time.perf_counter() - t, 4)
    with lib_machine as m:
        m.restore(state)
        us = lambda s: round(1e6 * s, 1)
        report["us_per_call"] = {
            "snapshot (al_export + copy)": us(timed(m.snapshot, args.repeat)),
            "snapshot_tick (two native SHA-256 passes only)": us(timed(lambda: m.snapshot_tick(state), args.repeat)),
            "python sha256 of snapshot": us(timed(lambda: hashlib.sha256(state).hexdigest(), args.repeat)),
            "restore (al_import: hashes + decode)": us(timed(lambda: m.restore(state), args.repeat)),
            "frame (render + rgb copy)": us(timed(m.frame, args.repeat)),
            "registers": us(timed(m.registers, args.repeat * 10)),
            "info": us(timed(lambda: m.info, args.repeat * 10)),
            "peek_ram 2 bytes": us(timed(lambda: m.peek_ram(0x1000, 2), args.repeat * 10)),
            "peek_ram 64 KiB": us(timed(lambda: m.peek_ram(0, 65536), args.repeat)),
            "gates (44 pcs)": us(timed(lambda: m.gates(list(range(0x1000, 0x1000 + 88, 2))), args.repeat)),
            "run 1 instruction": us(timed(lambda: m.run(instructions=1), args.repeat * 10)),
        }
        export = report["us_per_call"]["snapshot (al_export + copy)"]
        hashes = report["us_per_call"]["snapshot_tick (two native SHA-256 passes only)"]
        report["derived"] = {
            "native_sha256_MB_per_s": round(2 * len(state) / (hashes * 1e-6) / 1e6, 1),
            "python_sha256_MB_per_s": round(len(state) / (report["us_per_call"]["python sha256 of snapshot"] * 1e-6) / 1e6, 1),
            "export_minus_hashes_us (codec + copy)": round(export - hashes, 1),
            "hash_share_of_export": round(hashes / export, 2),
        }
    print(json.dumps(report, indent=1))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
