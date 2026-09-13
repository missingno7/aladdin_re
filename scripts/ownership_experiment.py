"""Compare frozen 0.7 and two object-boundary prototypes without production modes.

Only disposable Python source is changed. All workers use the existing DLL,
ordinary comparator and the frozen 0.6 witness; no builds or package installs.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "a72ed9e00fa8f24000e4df9fe4e3a29d4c7a68cc"


def prepare(folder, variant):
    archive = subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}",
        "archive", "--format=zip", BASELINE, "src/aladdin_sega", "tests"], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as saved:
        saved.extractall(folder)
    package = folder / "src/aladdin_sega"
    if variant != "v070":
        source = package / "recovered.py"
        code = source.read_text()
        node = next(n for n in ast.parse(code).body if isinstance(n, ast.FunctionDef) and n.name == "replace_object")
        lines = code.splitlines(keepends=True)
        source.write_text("".join(lines[:node.lineno - 1] + lines[node.end_lineno:]) +
                          "\nfrom .ownership_boundary import replace_object\n")
        for name in ("ownership_boundary.py", "ownership_semantics.py"):
            shutil.copyfile(ROOT / "scripts" / name, package / name)
        if variant == "no-residue":
            boundary = package / "ownership_boundary.py"
            code = boundary.read_text()
            start = code.index("    residue = ")
            end = code.index("    # No callback", start)
            boundary.write_text(code[:start] + code[end:])
    return package


def run(output, full):
    output.mkdir(parents=True, exist_ok=True)
    native = ROOT / "build/libaladdin_native.dll"
    native_hash = hashlib.sha256(native.read_bytes()).hexdigest()
    report = {"baseline": BASELINE, "native_sha256": native_hash, "runs": {}, "source": {},
              "method": "Serial fresh workers; source preparation excluded. Normal stdlib cache; copied project source has no cache and bytecode writes disabled. Single latency samples."}
    with tempfile.TemporaryDirectory(prefix="aladdin-ownership-") as temporary:
        for variant in ("v070", "hybrid", "no-residue"):
            package = prepare(Path(temporary) / variant, variant)
            env = dict(os.environ, PYTHONPATH=str(package.parent), PYTHONDONTWRITEBYTECODE="1",
                       ALADDIN_NATIVE_LIBRARY=str(native))
            env.pop("PYTHONPYCACHEPREFIX", None)
            report["source"][variant] = {p.name: {"loc": len(p.read_text().splitlines()),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in package.glob("*.py")}
            evidence = output / variant
            evidence.mkdir(exist_ok=True)
            def invoke(label, args, timeout=180):
                start = time.perf_counter()
                result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, text=True,
                                        capture_output=True, timeout=timeout)
                elapsed = time.perf_counter() - start
                (evidence / f"{label}.stdout.txt").write_text(result.stdout)
                (evidence / f"{label}.stderr.txt").write_text(result.stderr)
                print(json.dumps({"variant": variant, "run": label, "returncode": result.returncode,
                                  "seconds": elapsed}), flush=True)
                return result, elapsed
            result, _ = invoke("effects", [str(ROOT / "scripts/ownership_witness.py"),
                                           "--output", str(evidence / "effects.json")])
            assert result.returncode == 0, result.stderr
            effects = json.loads(result.stdout)
            assert effects["exit_state_equal"] == (variant != "no-residue"), effects
            if variant == "hybrid":
                frozen = package.parents[1]
                result, elapsed = invoke("tests", ["-m", "pytest", "-q", "--rootdir", str(frozen),
                    "--confcutdir", str(frozen), *[str(frozen / "tests" / name) for name in
                    ("test_recovery.py", "test_carrier.py", "test_atomic.py", "test_atomic_sound_guard.py")]])
                assert result.returncode == 0, result.stdout + result.stderr
                report["hybrid_tests"] = {"output": result.stdout, "seconds": elapsed}
                result, _ = invoke("safe-boundaries", [str(ROOT / "scripts/synchronous_witness.py"),
                    "--output", str(evidence / "safe-boundaries")])
                assert result.returncode == 0, result.stdout + result.stderr
            scopes = [("short", ROOT / "artifacts/carrier/witness-v060/witness.alreplay")]
            if full:
                scopes.append(("full", ROOT / "recordings/current/20260912T210640.729016Z.alreplay"))
            for scope, replay in scopes:
                def compare(label):
                    done, elapsed = invoke(label, ["-m", "aladdin_sega", "compare", str(replay),
                        "--rom", str(ROOT / "assets/Aladdin (USA).md"), "--candidate", "carrier",
                        "--diagnostics", "--output", str(evidence / label)])
                    payload = json.loads(done.stdout)
                    receipt = payload.get("candidate_receipt") or {}
                    calls = receipt.get("machine_api_calls", {})
                    return {"status": payload["status"], "seconds": elapsed,
                            "stats": receipt.get("candidate_stats"), "api_calls": calls,
                            "execution_crossings": 2 * (calls.get("run", 0) + calls.get("atomic", 0)),
                            "all_api_crossings": 2 * sum(calls.values())}
                measured = compare(scope)
                report["runs"][f"{variant}-{scope}"] = measured
                if variant != "no-residue":
                    assert measured["status"] == "PASS", measured
                if variant == "hybrid" and scope == "short":
                    source = package / "ownership_semantics.py"
                    correct = source.read_text()
                    assert correct.count("(pointer + offset, 0)") == 1
                    source.write_text(correct.replace("(pointer + offset, 0)", "(pointer + offset, 1)"))
                    try:
                        mutant = compare("semantic-edit")
                    finally:
                        source.write_text(correct)
                    assert mutant["status"] == "DIVERGENCE", mutant
                    report["semantic_edit"] = mutant
        assert hashlib.sha256(native.read_bytes()).hexdigest() == native_hash
    report.update(native_builds=0, package_installs=0)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/ownership")
    parser.add_argument("--quick", action="store_true", help="Skip only the full replay comparisons")
    args = parser.parse_args()
    run(args.output.resolve(), not args.quick)
