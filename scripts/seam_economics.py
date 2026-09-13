"""Measure frozen 0.6 versus synchronous carrier on the same short/full replays."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

from carrier_v060 import BASELINE, ROOT


def run(output, witness, replay):
    output.mkdir(parents=True, exist_ok=True)
    archive = subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}",
        "archive", "--format=zip", BASELINE, "src/aladdin_sega"], cwd=ROOT)
    report = {"baseline_commit": BASELINE, "method": "Serial fresh processes; source extraction excluded; identical DLL, empty bytecode cache, diagnostics and observation settings. Single timing samples, not a speedup claim.",
              "runs": {}, "loc": {}}
    with tempfile.TemporaryDirectory(prefix="aladdin-seam-cost-") as folder:
        frozen = Path(folder)
        with zipfile.ZipFile(io.BytesIO(archive)) as saved:
            saved.extractall(frozen)
        sources = {"v060": frozen / "src", "synchronous": ROOT / "src"}
        for scope, artifact in (("short", witness), ("full", replay)):
            for name, source in sources.items():
                label = f"{scope}-{name}"
                env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1",
                           PYTHONPYCACHEPREFIX=str(frozen / "empty-cache"),
                           ALADDIN_NATIVE_LIBRARY=str(ROOT / "build/libaladdin_native.dll"))
                command = [sys.executable, "-m", "aladdin_sega", "compare", str(artifact),
                           "--rom", str(ROOT / "assets/Aladdin (USA).md"), "--candidate", "carrier",
                           "--diagnostics", "--output", str(output / label)]
                start = time.perf_counter()
                done = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
                elapsed = time.perf_counter() - start
                if done.returncode:
                    raise RuntimeError(f"{label}: {done.stdout}\n{done.stderr}")
                result = json.loads(done.stdout)
                assert result["status"] == "PASS", result
                receipt = result["candidate_receipt"]
                calls = receipt["machine_api_calls"]
                report["runs"][label] = {"status": result["status"], "seconds": elapsed,
                    "replay_sha256": result["replay_sha256"], "stats": receipt["candidate_stats"],
                    "observations": result["observations"]["candidate"]["count"], "api_calls": calls,
                    "execution_crossings": 2 * (calls["run"] + calls["atomic"]),
                    "all_api_crossings": 2 * sum(calls.values()),
                    "native_sha256": receipt["receipt"]["native_binary_sha256"]}
                print(json.dumps({"run": label, "status": "PASS", "seconds": elapsed}), flush=True)
        for file in ("recovery.py", "machine.py", "artifacts.py", "cli.py", "frontend.py", "recovered.py"):
            report["loc"][file] = {name: len((source / "aladdin_sega" / file).read_text().splitlines())
                                   for name, source in sources.items()}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/synchronous/economics")
    parser.add_argument("--witness", type=Path, default=ROOT / "artifacts/carrier/witness-v060/witness.alreplay")
    parser.add_argument("--replay", type=Path, default=ROOT / "recordings/current/20260912T210640.729016Z.alreplay")
    args = parser.parse_args()
    run(args.output.resolve(), args.witness.resolve(), args.replay.resolve())
