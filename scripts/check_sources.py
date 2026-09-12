"""Verify the exact dependency closure without writing into the source checkout."""
import hashlib
import json
import argparse
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--identity-header", type=Path)
    parser.add_argument("--tests", action="store_true")
    parser.add_argument("--build-options", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    source = args.source
    lock = json.loads((ROOT / "third_party/sources.json").read_text())
    failures = []
    selected = dict(lock["files"])
    if args.tests:
        selected.update(lock["test_files"])
    for name, expected in selected.items():
        path = source / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(name)
    upstream_file = ROOT / "third_party/upstream.json"
    upstream = json.loads(upstream_file.read_text())
    for component in upstream.values():
        for name, expected in component["files"].items():
            path = ROOT / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                failures.append(name)
            # Borrowed board wrappers still include donor declarations. Until
            # those wrappers are absorbed, both header copies must be identical.
            if name.endswith(".h") and lock["files"].get(name) != expected:
                failures.append(name + " (donor wrapper header differs from direct upstream)")
    if failures:
        raise SystemExit("Source mismatch: " + ", ".join(failures))
    if args.identity_header:
        adapter = hashlib.sha256((ROOT / "native/machine.cpp").read_bytes()).hexdigest()
        dependency = hashlib.sha256((ROOT / "third_party/sources.json").read_bytes() + upstream_file.read_bytes()).hexdigest()
        source_id = hashlib.sha256(f"{adapter}:{dependency}".encode()).hexdigest()
        options = args.build_options.read_text() if args.build_options else ""
        receipt = {"source_id": source_id, "adapter_sha256": adapter, "dependency_lock_sha256": dependency,
                   "dependency_commit": lock["commit"], "upstream_revisions": {k:v["revision"] for k,v in upstream.items()}, "build_options": options,
                   "build_python": platform.python_version(), "build_platform": platform.platform()}
        payload = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        header = '#pragma once\n#define AL_SOURCE_ID ' + json.dumps(source_id) + '\n#define AL_BUILD_INFO ' + json.dumps(payload) + '\n'
        args.identity_header.parent.mkdir(parents=True, exist_ok=True)
        if not args.identity_header.exists() or args.identity_header.read_text() != header:
            args.identity_header.write_text(header)
        if args.receipt:
            args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Verified {len(selected)} dependency files at {lock['commit']}")


if __name__ == "__main__":
    main()
