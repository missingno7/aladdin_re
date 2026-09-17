"""perf_concurrency: replay throughput per worker as concurrent workers are added (read-only research tooling).

    python scripts/research/perf_concurrency.py --game gods --node fb408bc75597 --frames 1500 --workers 1,2,4,8,16
                                                [--json artifacts/gods/research/perf/concurrency.json]

For each worker count K, launches K fresh Python processes at once, each
loading the native library, creating its own machine, and replaying the
first ``--frames`` frames of the node with a per-frame observation (exactly
the verification worker's inner loop, ``GenesisRun.advance`` with
``observable``); reports each process's startup time (import + DLL load +
ROM + machine create + receipt), its replay fps, and the aggregate frames per
second, so the scaling of per-leaf / per-recording / per-fixture
concurrency on this machine is measured, not assumed.  Runs the counts one
after the other; the whole sweep with the defaults is under a minute.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

WORKER = r'''
import json, os, sys, time
t0 = time.perf_counter()
sys.path.insert(0, r"%(src)s")
os.environ.setdefault("GENESIS_NATIVE_LIBRARY", r"%(dll)s")
from genesis_re.games import game as select_game
from genesis_re.history import HistoryStore
from genesis_re.history_runtime import GenesisRun
game = select_game(%(game)r)
rom = game.read_rom()
store = HistoryStore(game.history_path(), game.history_root)
path = store.flatten(store.resolve(%(node)r))
t1 = time.perf_counter()
run = GenesisRun(game, rom, %(candidate)r)
t2 = time.perf_counter()
n = 0
with run:
    run.advance(1, path["events"], lambda r: r.observable())
    t3 = time.perf_counter()
    run.advance(%(frames)d, path["events"], lambda r: r.observable())
    t4 = time.perf_counter()
    n = run.frame
print(json.dumps({"import_seconds": round(t1 - t0, 3), "genesis_run_seconds": round(t2 - t1, 3),
                  "first_frame_seconds": round(t3 - t2, 3), "fps": round((n - 1) / (t4 - t3), 1),
                  "frames": n, "replay_seconds": round(t4 - t3, 3), "total_seconds": round(t4 - t0, 3)}))
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", default="gods")
    parser.add_argument("--node", default="main")
    parser.add_argument("--frames", type=int, default=1500)
    parser.add_argument("--candidate", default="original")
    parser.add_argument("--workers", default="1,2,4,8,16")
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)
    code = WORKER % {"src": str(ROOT / "src"), "dll": str(ROOT / "build" / "libgenesis_native.dll"),
                     "game": args.game, "node": args.node, "candidate": args.candidate, "frames": args.frames}
    results = []
    for count in [int(x) for x in args.workers.split(",")]:
        started = time.perf_counter()
        procs = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
                 for _ in range(count)]
        outs = [p.communicate() for p in procs]
        wall = time.perf_counter() - started
        rows = []
        for out, err in outs:
            try:
                rows.append(json.loads(out.strip().splitlines()[-1]))
            except (ValueError, IndexError):
                rows.append({"error": err[-400:]})
        good = [r for r in rows if "fps" in r]
        results.append({"workers": count, "wall_seconds": round(wall, 2),
                        "fps_per_worker_mean": round(sum(r["fps"] for r in good) / max(1, len(good)), 1),
                        "fps_per_worker_min": min((r["fps"] for r in good), default=None),
                        "aggregate_fps": round(sum(r["fps"] for r in good), 1),
                        "startup_seconds_mean": round(sum(r["import_seconds"] + r["genesis_run_seconds"] for r in good) / max(1, len(good)), 3),
                        "first_frame_seconds_mean": round(sum(r["first_frame_seconds"] for r in good) / max(1, len(good)), 3),
                        "rows": rows})
        print(json.dumps({k: v for k, v in results[-1].items() if k != "rows"}), flush=True)
    report = {"game": args.game, "node": args.node, "frames": args.frames, "candidate": args.candidate,
              "cpu_count": os.cpu_count(), "results": results}
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
