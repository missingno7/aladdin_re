"""Exact execution identity, separate from immutable capture provenance."""
import hashlib
import json
from pathlib import Path
import platform
import sys

from . import __version__
from .machine import library_path, load_library
from .profile import PROFILE_SHA256


def execution_receipt(*, artifact_sha256=None, capture_source=None, candidate="original"):
    lib = load_library()
    root = Path(__file__).parent
    modules = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}
    return {"native_source_id": lib.al_source_id().decode(),
            "native_binary_sha256": hashlib.sha256(library_path().read_bytes()).hexdigest(),
            "native_build": json.loads(lib.al_build_info().decode()),
            "python": platform.python_version(), "python_executable": sys.executable,
            "python_module_path": str(root.resolve()), "python_modules_sha256": modules,
            "platform": platform.platform(), "profile_sha256": PROFILE_SHA256,
            "artifact_sha256": artifact_sha256, "capture_source_id": capture_source,
            "candidate": candidate, "project_version": __version__}
