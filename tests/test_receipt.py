"""Source provenance must follow semantic code into nested packages, per game."""
import hashlib
from types import SimpleNamespace

from genesis_re import receipt


def _profile(package):
    return SimpleNamespace(package=package, id=package, profile_sha256="p" * 64)


def test_receipt_detects_nested_semantic_edits_and_new_modules(tmp_path, monkeypatch):
    shared = tmp_path / "genesis_re"
    shared.mkdir()
    (shared / "machine.py").write_text("ABI = 2\n")
    package = tmp_path / "some_game"
    objects = package / "game" / "objects"
    objects.mkdir(parents=True)
    facade = package / "recovered.py"
    facade.write_text("from .game.objects.lifecycle import clear_pair\n")
    semantic = objects / "lifecycle.py"
    semantic.write_text("def clear_pair(): return 0\n")
    binary = tmp_path / "native.dll"
    binary.write_bytes(b"test native identity")
    roots = {"genesis_re": shared, "some_game": package, "other_game": tmp_path / "other_game"}
    (tmp_path / "other_game").mkdir()
    (tmp_path / "other_game" / "profile.py").write_text("OTHER = 1\n")
    monkeypatch.setattr(receipt, "_package_root", lambda name: roots[name])
    monkeypatch.setattr(receipt, "library_path", lambda: binary)
    monkeypatch.setattr(receipt, "load_library", lambda: SimpleNamespace(
        al_source_id=lambda: b"test-source", al_build_info=lambda: b"{}"))
    game = _profile("some_game")

    before = receipt.execution_receipt(game)["python_modules_sha256"]
    assert before["some_game/game/objects/lifecycle.py"] == hashlib.sha256(semantic.read_bytes()).hexdigest()
    assert "genesis_re/machine.py" in before
    assert not any(key.startswith("other_game/") for key in before)
    semantic.write_text("def clear_pair(): return 1\n")
    after = receipt.execution_receipt(game)["python_modules_sha256"]
    assert after["some_game/recovered.py"] == before["some_game/recovered.py"]
    assert after["some_game/game/objects/lifecycle.py"] != before["some_game/game/objects/lifecycle.py"]

    (objects / "contact.py").write_text("def react(): return 2\n")
    expanded = receipt.execution_receipt(game)["python_modules_sha256"]
    assert "some_game/game/objects/contact.py" in expanded
    assert expanded != after

    # Another game's receipt never moves when this game's recovered code changes.
    other = receipt.execution_receipt(_profile("other_game"))["python_modules_sha256"]
    assert set(other) == {"genesis_re/machine.py", "other_game/profile.py"}
    shared_only = receipt.execution_receipt()
    assert set(shared_only["python_modules_sha256"]) == {"genesis_re/machine.py"}
    assert shared_only["game"] is None and shared_only["profile_sha256"] is None
