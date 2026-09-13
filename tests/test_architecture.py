import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("architecture", ROOT / "scripts/check_architecture.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_current_python_boundary():
    assert guard.check() == []


def test_accidental_framework_leak_is_detected():
    assert guard.violations("from port_forge.replay import verdict_record", filename="recovery.py")
    assert guard.violations("codec = b'PFGENS02'", filename="artifacts.py")
    assert guard.violations("from .verification import Observer", filename="recovered.py")
    assert guard.violations("from .boundary import AtomicPlan", filename="recovered.py")
    assert guard.violations("plan = AtomicPlan()", filename="recovered.py")
    assert not guard.violations("from .machine import Machine", filename="recovery.py")
