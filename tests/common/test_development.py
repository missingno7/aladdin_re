"""Development runner and dependency-bundle behavior stay independent of the ROM."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dev_uses_fresh_source_tree_process_and_preserves_cli_arguments(tmp_path):
    dev = load_script("dev")
    native = tmp_path / "native.dll"
    native.write_bytes(b"native")
    calls = []

    class Result:
        returncode = 17

    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        return Result()

    assert dev.run(["history-run", "main", "--output", "result.json", "--native", str(native)], runner=runner) == 17
    assert len(calls) == 1
    (command,), options = calls[0]
    assert command == [sys.executable, "-m", "genesis_re", "history-run", "main", "--output", "result.json"]
    assert options["cwd"] == ROOT
    assert options["check"] is False
    assert options["env"]["GENESIS_NATIVE_LIBRARY"] == str(native.resolve())
    assert options["env"]["PYTHONPATH"].split(";")[0] == str((ROOT / "src").resolve())


def test_export_is_byte_exact_and_refuses_tampering_or_overwrite(tmp_path):
    exporter = load_script("export_sources")
    source = tmp_path / "upstream"
    content = b"first\r\nsecond\r\n"
    selected = source / "src" / "component.hpp"
    selected.parent.mkdir(parents=True)
    selected.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    lock = tmp_path / "sources.json"
    lock.write_text(json.dumps({"repository": "local", "commit": "abc", "files": {"src/component.hpp": digest}}), encoding="utf-8")

    output = exporter.export_bundle(source, tmp_path / "bundle", lock_path=lock)
    assert (output / "source" / "src" / "component.hpp").read_bytes() == content
    metadata = json.loads((output / "metadata" / "provenance.json").read_text(encoding="utf-8"))
    assert metadata["file_count"] == 1
    assert metadata["files"]["src/component.hpp"] == digest
    with pytest.raises(FileExistsError):
        exporter.export_bundle(source, output, lock_path=lock)

    selected.write_bytes(b"modified")
    with pytest.raises(ValueError, match="Source mismatch"):
        exporter.export_bundle(source, tmp_path / "tampered", lock_path=lock)
    assert not (tmp_path / "tampered").exists()


def test_export_rejects_rom_like_roots_even_if_a_lock_names_them(tmp_path):
    exporter = load_script("export_sources")
    lock = tmp_path / "unsafe.json"
    lock.write_text(json.dumps({"repository": "local", "commit": "abc", "files": {"assets/game.md": "0" * 64}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe"):
        exporter.read_lock(lock)


def test_dev_does_not_load_timestamp_cache_after_same_size_same_second_edit(tmp_path, monkeypatch):
    dev = load_script("dev")
    package = tmp_path / "src/genesis_re"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    entry = package / "__main__.py"
    entry.write_text("print('before')")
    stamp = entry.stat().st_mtime
    py_compile.compile(str(entry), doraise=True)
    entry.write_text("print('edited')")  # Identical byte count and timestamp.
    os.utime(entry, (stamp, stamp))
    native = tmp_path / "native.dll"
    native.write_bytes(b"unused by this source-loading witness")
    monkeypatch.setattr(dev, "SOURCE_ROOT", package.parent)
    outputs = []
    def runner(*args, **kwargs):
        result = subprocess.run(*args, **kwargs, capture_output=True, text=True)
        outputs.append(result.stdout.strip())
        return result
    assert dev.run(["doctor", "--native", str(native)], runner=runner) == 0
    assert outputs == ["edited"]


@pytest.mark.parametrize('exit_code', (0, 7))
def test_verifier_wait_timeout_is_observation_not_restart(monkeypatch, capsys, exit_code):
    dev = load_script('dev')
    calls = []
    class Process:
        pid = 123
        waits = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def wait(self, timeout):
            assert timeout == 30
            self.waits += 1
            if self.waits <= 2:
                raise subprocess.TimeoutExpired('verifier', timeout)
            return exit_code
    def start(*args, **kwargs):
        calls.append((args, kwargs))
        return Process()
    monkeypatch.setattr(dev.subprocess, 'Popen', start)
    result = dev._visible_verification(['verifier'], cwd=ROOT, env={})
    assert result.returncode == exit_code
    assert len(calls) == 1
    output = capsys.readouterr()
    assert not output.out
    assert output.err.count('RUNNING') == 2
    assert f'code={exit_code}' in output.err
    assert 'PASS' not in output.err


def test_history_verification_uses_visible_launcher(tmp_path, monkeypatch):
    dev = load_script('dev')
    native = tmp_path / 'native.dll'; native.write_bytes(b'test')
    calls = []
    def visible(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(dev, '_visible_verification', visible)
    assert dev.run(['history-verify', '--native', str(native)]) == 0
    assert calls[0][-1] == 'history-verify'
