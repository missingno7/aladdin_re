"""Export the pinned PortForge dependency closure as a local source bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "third_party" / "sources.json"
PROJECT_NOTICE = ROOT / "third_party" / "README.md"
SAFE_TOP_LEVELS = {"src", "tests", "third_party"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def read_lock(lock_path: Path, *, tests=False) -> dict[str, Any]:
    """Read and validate the small, explicit dependency manifest."""
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if tests:
            lock["files"] = {**lock["files"], **lock.get("test_files", {})}
        files = lock["files"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"Invalid source lock {lock_path}: {error}") from error
    if not isinstance(lock.get("repository"), str) or not isinstance(lock.get("commit"), str):
        raise ValueError("Source lock requires repository and commit strings")
    if not isinstance(files, dict) or not files:
        raise ValueError("Source lock requires a non-empty files map")
    for name, digest in files.items():
        path = PurePosixPath(name) if isinstance(name, str) else None
        if (path is None or path.is_absolute() or ".." in path.parts or len(path.parts) < 2
                or path.parts[0] not in SAFE_TOP_LEVELS or not isinstance(digest, str)
                or not SHA256.fullmatch(digest)):
            raise ValueError(f"Unsafe or invalid locked path: {name!r}")
    return lock


def verified_files(source: Path, lock: dict[str, Any]) -> list[tuple[PurePosixPath, bytes, str]]:
    """Read every selected file once and verify its bytes before any output write."""
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Source checkout not found: {source}")
    checked = []
    for name, expected in sorted(lock["files"].items()):
        relative = PurePosixPath(name)
        candidate = (source / Path(*relative.parts)).resolve()
        try:
            candidate.relative_to(source)
        except ValueError as error:
            raise ValueError(f"Locked path escapes source checkout: {name}") from error
        if not candidate.is_file():
            raise ValueError(f"Source mismatch: {name}")
        data = candidate.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Source mismatch: {name}")
        checked.append((relative, data, expected))
    return checked


def export_bundle(source: Path, output: Path, *, lock_path: Path = DEFAULT_LOCK, tests=False) -> Path:
    """Create a new bundle; existing paths are deliberately never reused."""
    lock_path = lock_path.resolve()
    lock_bytes = lock_path.read_bytes()
    lock = read_lock(lock_path, tests=tests)
    files = verified_files(source, lock)

    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()

    source_dir = output / "source"
    for relative, data, expected in files:
        destination = source_dir.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Byte-exact export failed: {relative.as_posix()}")

    metadata = output / "metadata"
    metadata.mkdir()
    (metadata / "sources.json").write_bytes(lock_bytes)
    notice = PROJECT_NOTICE.read_text(encoding="utf-8") if PROJECT_NOTICE.is_file() else ""
    (metadata / "THIRD_PARTY_NOTICES.md").write_text(
        "# Selected third-party notices\n\n"
        "The original relative paths are retained under `source/`. Selected "
        "license and README files are included when they appear in the lock.\n\n"
        + notice,
        encoding="utf-8",
    )
    provenance = {
        "format": "aladdin-re-source-bundle/v1",
        "upstream": {"repository": lock["repository"], "commit": lock["commit"]},
        "file_count": len(files),
        "scope": "runtime-and-tests" if tests else "runtime",
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "layout": {
            "sources": "source/<original-relative-path>",
            "lock": "metadata/sources.json",
            "notices": "metadata/THIRD_PARTY_NOTICES.md",
        },
        "files": lock["files"],
    }
    (metadata / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Pinned local PortForge checkout")
    parser.add_argument("--output", type=Path, required=True, help="New local directory for the source bundle")
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK, help="Dependency lock (mainly for controlled tests)")
    parser.add_argument("--tests", action="store_true", help="Also export the separately locked native test dependencies")
    args = parser.parse_args(argv)
    try:
        output = export_bundle(args.source, args.output, lock_path=args.lock, tests=args.tests)
    except (FileNotFoundError, FileExistsError, ValueError, OSError) as error:
        print(f"export_sources.py: {error}", file=sys.stderr)
        return 2
    print(f"Exported {len(read_lock(args.lock, tests=args.tests)['files'])} pinned files to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
