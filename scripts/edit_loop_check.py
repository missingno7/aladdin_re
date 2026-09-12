"""Prove a Python source edit changes the focused verdict without a native build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("witness", type=Path)
    parser.add_argument("--rom", type=Path, default=ROOT / "assets/Aladdin (USA).md")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/review/edit-loop")
    args = parser.parse_args()
    native = ROOT / "build/libaladdin_native.dll"
    native_hash = hashlib.sha256(native.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aladdin-python-edit-") as temporary:
        source = Path(temporary) / "aladdin_sega"
        source.mkdir()
        for path in (ROOT / "src/aladdin_sega").glob("*.py"):
            shutil.copyfile(path, source / path.name)
        env = dict(os.environ, PYTHONPATH=temporary, ALADDIN_NATIVE_LIBRARY=str(native))
        def compare(label):
            command = [sys.executable, "-m", "aladdin_sega", "compare", str(args.witness.resolve()),
                       "--rom", str(args.rom.resolve()), "--candidate", "leaf", "--output", str((args.output / label).resolve())]
            started = time.perf_counter()
            result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=30)
            payload = json.loads(result.stdout)
            return {"returncode": result.returncode, "wall_seconds": time.perf_counter() - started,
                    "status": payload["status"], "report": str((args.output / label / "comparison.json").resolve())}
        before = compare("before")
        function = source / "recovery.py"
        code = function.read_text()
        expression = "writes.extend((pointer + offset, 0) for offset in range(length))"
        if code.count(expression) != 1:
            raise RuntimeError("Recovery edit witness no longer identifies exactly one clear loop")
        function.write_text(code.replace(expression, "writes.extend((pointer + offset, 1) for offset in range(length))"))
        # No stale timestamp/size bytecode cache may hide a same-length edit.
        for cached in (source / "__pycache__").glob("recovery.*.pyc"):
            cached.unlink()
        after = compare("after")
    same_native = hashlib.sha256(native.read_bytes()).hexdigest() == native_hash
    passed = before["status"] == "PASS" and after["status"] in {"DIVERGENCE", "CANDIDATE_ERROR"} and same_native
    report = {"status": "PASS" if passed else "FAIL", "before": before, "after": after,
              "edit": "Python buffer clear value 0 -> 1 in a disposable source copy", "native_sha256": native_hash,
              "native_unchanged": same_native, "native_builds": 0, "package_installs": 0}
    (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
