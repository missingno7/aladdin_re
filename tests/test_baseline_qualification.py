"""The qualification launcher verifies its preserved worker before spawning it."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "qualify_baseline.py"
SPEC = importlib.util.spec_from_file_location("qualify_baseline", SCRIPT)
qualification = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualification)


def make_baseline(tmp_path):
    package = tmp_path / "aladdin_sega"
    package.mkdir()
    module = package / "machine.py"
    dll = package / "libaladdin_native.dll"
    module.write_bytes(b"preserved module")
    dll.write_bytes(b"preserved dll")
    files = {
        "aladdin_sega\\machine.py": hashlib.sha256(module.read_bytes()).hexdigest(),
        "aladdin_sega\\libaladdin_native.dll": hashlib.sha256(dll.read_bytes()).hexdigest(),
    }
    (tmp_path / "receipt.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    return package


def test_baseline_receipt_is_checked_before_child_execution(tmp_path):
    package = make_baseline(tmp_path)
    actual, receipt = qualification.validate_baseline(tmp_path)
    assert actual == package.resolve()
    assert receipt["files"]
    (package / "machine.py").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="receipt mismatch"):
        qualification.validate_baseline(tmp_path)


def test_baseline_environment_does_not_inherit_current_pythonpath(tmp_path, monkeypatch):
    package = make_baseline(tmp_path)
    monkeypatch.setenv("PYTHONPATH", "current/source/tree")
    env = qualification.baseline_environment(package)
    assert env["PYTHONPATH"] == str(package.parent)
    assert env["ALADDIN_NATIVE_LIBRARY"] == str(package / "libaladdin_native.dll")
