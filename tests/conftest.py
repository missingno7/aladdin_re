"""Test scopes and the checkout's import paths.

    tests/common/          shared machine, history, replay, verification, tooling
    tests/games/aladdin/   the Aladdin recovery project
    tests/games/gods/      the Gods recovery project

Run a scope by path (``pytest tests/common tests/games/gods``) or by marker
(``pytest -m "common or gods"``); ``scripts/run_tests.py SCOPE`` composes both
with the checkout's native library.  The paths below make the checkout's
``src``, ``scripts`` and each game's script directory importable, for this
process and for the fresh workers the verification tests spawn, so no
PYTHONPATH is needed to run the suite from the checkout.
"""
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMPORT_PATHS = [ROOT / "src", ROOT / "scripts", ROOT / "scripts" / "aladdin", ROOT / "scripts" / "gods", ROOT / "tests"]
SCOPES = {"common": "common", "games/aladdin": "aladdin", "games/gods": "gods"}


def _prepend_paths():
    for path in reversed(IMPORT_PATHS):
        text = str(path)
        if text in sys.path:
            sys.path.remove(text)
        sys.path.insert(0, text)
    inherited = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    os.environ["PYTHONPATH"] = os.pathsep.join([str(p) for p in IMPORT_PATHS] + [p for p in inherited if p not in map(str, IMPORT_PATHS)])
    native = ROOT / "build" / "libgenesis_native.dll"
    if "GENESIS_NATIVE_LIBRARY" not in os.environ and native.is_file():
        os.environ["GENESIS_NATIVE_LIBRARY"] = str(native)


_prepend_paths()


def pytest_configure(config):
    for marker in SCOPES.values():
        config.addinivalue_line("markers", f"{marker}: tests of the {marker} scope (by directory)")


def pytest_collection_modifyitems(config, items):
    for item in items:
        relative = Path(str(item.fspath)).resolve().relative_to(ROOT / "tests").as_posix()
        for prefix, marker in SCOPES.items():
            if relative.startswith(prefix + "/"):
                item.add_marker(getattr(pytest.mark, marker))
