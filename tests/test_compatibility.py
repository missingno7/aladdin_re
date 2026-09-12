"""Capture identity is exact by default and exceptions are named-directional."""
import pytest

from aladdin_sega import artifacts, compatibility
from aladdin_sega.profile import PROFILE_SHA256


def test_exact_identity_is_default_and_named_transition_is_directional(monkeypatch):
    captured, runtime, other = "captured", "runtime", "other-native"
    monkeypatch.setattr(compatibility, "TRANSITIONS", {
        "test-pair": (captured, runtime, PROFILE_SHA256),
    })

    compatibility.check_source(captured, captured)
    compatibility.check_source(captured, runtime, policy="test-pair")
    with pytest.raises(ValueError, match="Unknown compatibility transition"):
        compatibility.check_source(captured, runtime, policy="missing")
    with pytest.raises(ValueError, match="source identity mismatch"):
        compatibility.check_source(captured, runtime)
    with pytest.raises(ValueError, match="source identity mismatch"):
        compatibility.check_source(runtime, captured, policy="test-pair")
    with pytest.raises(ValueError, match="source identity mismatch"):
        compatibility.check_source(other, runtime, policy="test-pair")


def test_transition_requires_the_current_profile(monkeypatch):
    monkeypatch.setattr(compatibility, "TRANSITIONS", {
        "wrong-profile": ("captured", "runtime", "not-the-current-profile"),
    })
    with pytest.raises(ValueError, match="source identity mismatch"):
        compatibility.check_source("captured", "runtime", policy="wrong-profile")


def test_restore_checks_manifest_tick_against_native_state_before_import():
    from tests.test_machine import synthetic_rom
    from aladdin_sega.machine import Machine

    with Machine(synthetic_rom()) as machine:
        machine.run(instructions=1)
        saved = artifacts.snapshot_bytes(machine)
        before = machine.snapshot()
        parts = artifacts.unpack(saved, {"manifest.json", "machine.bin"}, {"manifest.json", "machine.bin"})
        manifest = artifacts.decode_json(parts["manifest.json"])
        manifest["tick"] += 1
        parts["manifest.json"] = artifacts.json_bytes(manifest)
        forged = artifacts.pack(parts)
        with pytest.raises(ValueError, match="timestamp disagrees"):
            artifacts.restore_snapshot(machine, forged)
        assert machine.snapshot() == before
