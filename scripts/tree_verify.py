"""tree_verify: every leaf of a game's history tree verified cold, concurrently.

    python scripts/tree_verify.py --game GAME --candidate NAME --output DIR [--timeout-seconds 3000] [--jobs N]

The single-process ``history-verify --tree`` walks the tree once, restoring
at branch points, with one reference and one candidate worker: two
processes for the whole tree.  This driver makes the same claim as a set of
independent claims: one ``history-verify`` per leaf, each a cold run from
power-on under that leaf's inputs (no restore anywhere), launched
concurrently.  Every leaf gets its own directory ``DIR/<leaf12>`` with the
usual ``comparison.json``/``reference.json``/``candidate.json`` and the
usual receipts; ``DIR/tree.json`` records the set and the verdict; the
verdict is PASS only when every leaf is PASS.  The frame total equals the
tree walk's (the leaves cover every node); the wall time is the longest
leaf's instead of the sum.  ``verify_status.py`` reads a leaf directory as
it reads any run; ``tree.json`` names them.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from genesis_re.games import game as select_game        # noqa: E402
from genesis_re.history import HistoryStore              # noqa: E402


def leaves_of(store):
    nodes = store.nodes()
    parents = {node.get("parent") for node in nodes.values()}
    return sorted((key for key in nodes if key not in parents), key=lambda key: -nodes[key]["end_frame"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=3000)
    parser.add_argument("--jobs", type=int, default=0, help="leaves verified at once (default: all)")
    args = parser.parse_args(argv)
    game = select_game(args.game)
    store = HistoryStore(args.history or game.history_path(), game.history_root)
    leaves = leaves_of(store)
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    def verify(leaf):
        out = args.output / leaf[:12]
        command = [sys.executable, str(ROOT / "scripts" / "dev.py"), "history-verify", leaf, "--game", game.id,
                   "--candidate", args.candidate, "--timeout-seconds", str(args.timeout_seconds), "--output", str(out)]
        if args.history:
            command += ["--history", str(args.history)]
        log = out.with_suffix(".log")
        out.mkdir(parents=True, exist_ok=True)
        with open(log, "w", encoding="utf-8") as handle:
            code = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, check=False).returncode
        try:
            status = json.loads((out / "comparison.json").read_text(encoding="utf-8")).get("status")
        except (OSError, ValueError):
            status = "ERROR"
        return leaf, code, status

    with ThreadPoolExecutor(max_workers=args.jobs or len(leaves)) as pool:
        results = list(pool.map(verify, leaves))
    verdict = "PASS" if all(status == "PASS" for _, _, status in results) else \
        next(status for _, _, status in results if status != "PASS")
    summary = {"game": game.id, "candidate": args.candidate, "verdict": verdict, "seconds": round(time.perf_counter() - started, 1),
               "leaves": [{"leaf": leaf, "directory": str(args.output / leaf[:12]), "status": status, "returncode": code}
                          for leaf, code, status in results],
               "executed_frames": sum(store.nodes()[leaf]["end_frame"] for leaf in leaves)}
    (args.output / "tree.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for leaf, code, status in results:
        print(f"  {leaf[:12]}  {status}")
    print(f"{verdict}: {len(leaves)} leaves, {summary['executed_frames']} frames, {summary['seconds']} s")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
