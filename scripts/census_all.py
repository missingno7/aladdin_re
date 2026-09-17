"""census_all: one recovery census per leaf of the history tree, all leaves at once.

    python scripts/census_all.py --game GAME --entry PC [--classifier entry] [--max-classes 400] [--prefix census-PC]
                                 [extra recovery_census arguments after --]

A census over one recording retains the path classes that recording
reaches; a region planned from those alone can MATCH every fixture and still
diverge on another recording (state 14 on 18 September: five real defects
on a recording never censused, found by the tree).  The cheap instrument is
the fixture set over every recording, so this driver runs
``recovery_census.py`` for every leaf concurrently into
``artifacts/<game>/evidence/<prefix>-<leaf12>`` and prints each summary; the
region's test module then globs ``<prefix>*`` and ``factcheck check`` sees
every witnessed class on every recording before any seal runs.  The census
tool changes nothing; this only launches it.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from genesis_re.games import game as select_game        # noqa: E402
from genesis_re.history import HistoryStore              # noqa: E402


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    extra = []
    if "--" in argv:
        extra = argv[argv.index("--") + 1:]
        argv = argv[:argv.index("--")]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", required=True)
    parser.add_argument("--entry", action="append", required=True)
    parser.add_argument("--classifier", default="entry")
    parser.add_argument("--max-classes", type=int, default=400)
    parser.add_argument("--prefix", default=None, help="output directory prefix; default census-<first entry>")
    parser.add_argument("--history", default=None)
    args = parser.parse_args(argv)
    game = select_game(args.game)
    store = HistoryStore(Path(args.history) if args.history else game.history_path(), game.history_root)
    nodes = store.nodes()
    parents = {node.get("parent") for node in nodes.values()}
    leaves = sorted((key for key in nodes if key not in parents), key=lambda key: -nodes[key]["end_frame"])
    prefix = args.prefix or f"census-{args.entry[0].upper()}"
    evidence = Path("artifacts") / game.id / "evidence"

    def census(leaf):
        out = evidence / f"{prefix}-{leaf[:12]}"
        command = [sys.executable, str(ROOT / "scripts" / "recovery_census.py"), str(out), "--game", game.id,
                   "--classifier", args.classifier, "--node", leaf, "--max-classes", str(args.max_classes)]
        for entry in args.entry:
            command += ["--entry", entry]
        if args.history:
            command += ["--history", args.history]
        command += extra
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        return leaf, result.returncode, (result.stdout + result.stderr).strip().splitlines()[-6:]

    with ThreadPoolExecutor(max_workers=len(leaves)) as pool:
        for leaf, code, tail in pool.map(census, leaves):
            print(f"== {leaf[:12]} ({nodes[leaf]['end_frame']} frames){'' if code == 0 else f'  EXIT {code}'}")
            for line in tail:
                print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
