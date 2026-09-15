"""Run one test scope from the checkout against the built native library.

    python scripts/run_tests.py common            shared machine, history, replay, verification, tooling
    python scripts/run_tests.py aladdin           common + the Aladdin recovery project
    python scripts/run_tests.py gods              common + the Gods recovery project
    python scripts/run_tests.py all               everything (the broader regression run)
    python scripts/run_tests.py gods -- -k boot   extra pytest arguments after --

A grinding iteration on one game runs that game's scope; the full run is for
larger checkpoints.  Scopes are directories (tests/common, tests/games/<game>),
so the selection is structural, not runtime skips.  Parallel by default
(-n auto is not used: workers share one native library and one machine each,
eight workers is the measured sweet spot on the reference machine).
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {
    "common": ["tests/common"],
    "aladdin": ["tests/common", "tests/games/aladdin"],
    "gods": ["tests/common", "tests/games/gods"],
    "all": ["tests"],
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in SCOPES:
        print(__doc__, file=sys.stderr)
        return 2
    scope = argv.pop(0)
    if argv and argv[0] == "--":
        argv.pop(0)
    workers = [] if any(a.startswith("-n") for a in argv) else ["-n", "8"]
    env = dict(os.environ)
    env.setdefault("GENESIS_NATIVE_LIBRARY", str(ROOT / "build" / "libgenesis_native.dll"))
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *workers, *SCOPES[scope], *argv]
    print("[run_tests] " + " ".join(command[2:]), file=sys.stderr, flush=True)
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
