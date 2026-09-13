"""Run the frozen persistent-continuation evidence at fc66041, never production.

Examples: carrier_v060.py witness --output artifacts/synchronous/reference-witness
          carrier_v060.py compare recordings/current/example.alreplay --candidate carrier
          carrier_v060.py test
"""
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

BASELINE = "fc6604131d3f03409b0a9843d75a932e43c3bc6d"
ROOT = Path(__file__).resolve().parents[1]


def main(args):
    if not args:
        raise SystemExit("Supply witness, test, or a 0.6 CLI command")
    archive = subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}",
        "archive", "--format=zip", BASELINE, "src/aladdin_sega", "scripts", "tests"], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="aladdin-v060-") as folder:
        frozen = Path(folder)
        with zipfile.ZipFile(io.BytesIO(archive)) as saved:
            saved.extractall(frozen)
        env = dict(os.environ, PYTHONPATH=str(frozen / "src"), PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPYCACHEPREFIX=str(frozen / "cache"),
                   ALADDIN_NATIVE_LIBRARY=str(ROOT / "build/libaladdin_native.dll"))
        if args[0] == "witness":
            command = [str(frozen / "scripts/carrier_witness.py"),
                       "--recording", str(ROOT / "recordings/current/20260912T210640.729016Z.alreplay"),
                       "--output", str(ROOT / "artifacts/synchronous/v060-witness"), *args[1:]]
        elif args[0] == "test":
            command = ["-m", "pytest", "--rootdir", str(frozen), "--confcutdir", str(frozen),
                       str(frozen / "tests/test_carrier.py"), "-q", *args[1:]]
        else:
            command = ["-m", "aladdin_sega", *args]
        return subprocess.call([sys.executable, *command], cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
