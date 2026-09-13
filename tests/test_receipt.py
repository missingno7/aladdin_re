"""Source provenance must follow semantic code into nested packages."""
import hashlib
from types import SimpleNamespace

from aladdin_sega import receipt


def test_receipt_detects_nested_semantic_edits_and_new_modules(tmp_path, monkeypatch):
    package = tmp_path / "aladdin_sega"
    objects = package / "game" / "objects"
    objects.mkdir(parents=True)
    facade = package / "recovered.py"
    facade.write_text("from .game.objects.lifecycle import clear_pair\n")
    semantic = objects / "lifecycle.py"
    semantic.write_text("def clear_pair(): return 0\n")
    binary = tmp_path / "native.dll"
    binary.write_bytes(b"test native identity")
    monkeypatch.setattr(receipt, "__file__", str(package / "receipt.py"))
    monkeypatch.setattr(receipt, "library_path", lambda: binary)
    monkeypatch.setattr(receipt, "load_library", lambda: SimpleNamespace(
        al_source_id=lambda: b"test-source", al_build_info=lambda: b"{}"))

    before = receipt.execution_receipt()["python_modules_sha256"]
    assert before["game/objects/lifecycle.py"] == hashlib.sha256(semantic.read_bytes()).hexdigest()
    semantic.write_text("def clear_pair(): return 1\n")
    after = receipt.execution_receipt()["python_modules_sha256"]
    assert after["recovered.py"] == before["recovered.py"]
    assert after["game/objects/lifecycle.py"] != before["game/objects/lifecycle.py"]

    (objects / "contact.py").write_text("def react(): return 2\n")
    expanded = receipt.execution_receipt()["python_modules_sha256"]
    assert "game/objects/contact.py" in expanded
    assert expanded != after
