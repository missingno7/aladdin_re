"""Verify the exact dependency closure without writing into the source checkout."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = Path(sys.argv[1])
    lock = json.loads((ROOT / "third_party/sources.json").read_text())
    failures = []
    for name, expected in lock["files"].items():
        path = source / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(name)
    if failures:
        raise SystemExit("Source mismatch: " + ", ".join(failures))
    print(f"Verified {len(lock['files'])} dependency files at {lock['commit']}")


if __name__ == "__main__":
    main()
