"""Exact execution identity, separate from immutable capture provenance."""
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys

from . import __version__
from .machine import library_path, load_library


def _package_root(name):
    return Path(importlib.import_module(name).__file__).resolve().parent


def source_modules(game=None):
    """SHA-256 of every Python module that can execute: the shared package and the game's own.

    Keys are package-relative (``genesis_re/machine.py``, ``aladdin_sega/game/objects/lifecycle.py``),
    so a game's receipt never depends on another game's recovered code.
    """
    packages = [__name__.split(".")[0]] + ([game.package] if game is not None else [])
    modules = {}
    for name in packages:
        root = _package_root(name)
        for path in sorted(root.rglob("*.py")):
            modules[f"{name}/{path.relative_to(root).as_posix()}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return modules


def execution_receipt(game=None, *, artifact_sha256=None, capture_source=None, candidate="original"):
    lib = load_library()
    return {"native_source_id": lib.al_source_id().decode(),
            "native_binary_sha256": hashlib.sha256(library_path().read_bytes()).hexdigest(),
            "native_build": json.loads(lib.al_build_info().decode()),
            "python": platform.python_version(), "python_executable": sys.executable,
            "python_module_path": str(_package_root(__name__.split(".")[0]).parent),
            "python_modules_sha256": source_modules(game),
            "platform": platform.platform(),
            "game": None if game is None else game.id,
            "profile_sha256": None if game is None else game.profile_sha256,
            "artifact_sha256": artifact_sha256, "capture_source_id": capture_source,
            "candidate": candidate, "project_version": __version__}
