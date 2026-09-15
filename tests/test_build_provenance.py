"""A changed locked dependency must stop an incremental native build."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PORTFORGE = Path(r"D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge")
TOOLS = {
    "cmake": ROOT / ".venv" / "Scripts" / "cmake.exe",
    "ninja": ROOT / ".venv" / "Scripts" / "ninja.exe",
    "gcc": Path(r"C:/msys64/mingw64/bin/gcc.exe"),
    "g++": Path(r"C:/msys64/mingw64/bin/g++.exe"),
}


def require_local_build_tools():
    missing = [name for name, path in TOOLS.items() if not path.is_file()]
    if not PORTFORGE.is_dir():
        missing.append("pinned PortForge checkout")
    if missing:
        pytest.skip("Build provenance regression requires local Windows tools: " + ", ".join(missing))


def command(args, *, cwd):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=120, check=False)


def require_success(args, *, cwd):
    result = command(args, cwd=cwd)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_id_from_fresh_process(dll: Path) -> str:
    code = (
        "import ctypes, sys; "
        "library = ctypes.CDLL(sys.argv[1]); "
        "library.al_source_id.restype = ctypes.c_char_p; "
        "print(library.al_source_id().decode())"
    )
    return require_success([sys.executable, "-c", code, str(dll)], cwd=ROOT).stdout.strip()


def copy_disposable_project(destination: Path) -> Path:
    """Copy runtime inputs only; test framework headers must not be required."""
    upstream = json.loads((ROOT / "third_party/upstream.json").read_text())
    inputs = ["CMakeLists.txt", "native/machine.cpp", "scripts/check_sources.py",
              "third_party/sources.json", "third_party/upstream.json"]
    inputs += [name for component in upstream.values() for name in component["files"]]
    for relative in inputs:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    lock = json.loads((ROOT / "third_party/sources.json").read_text(encoding="utf-8"))
    focused = destination / "port_forge"
    for relative in lock["files"]:
        target = focused / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PORTFORGE / relative, target)
    return focused


def test_incremental_build_rechecks_dependencies_and_refreshes_identity(tmp_path):
    require_local_build_tools()
    project = tmp_path / "project"
    focused = copy_disposable_project(project)
    build = project / "build"
    configure = [
        str(TOOLS["cmake"]), "-S", str(project), "-B", str(build), "-G", "Ninja",
        f"-DPORTFORGE_ROOT={focused}",
        f"-DPython_EXECUTABLE={sys.executable}",
        f"-DCMAKE_MAKE_PROGRAM={TOOLS['ninja']}",
        f"-DCMAKE_C_COMPILER={TOOLS['gcc']}", f"-DCMAKE_CXX_COMPILER={TOOLS['g++']}",
        "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=OFF",
    ]
    require_success(configure, cwd=project)
    build_command = [str(TOOLS["cmake"]), "--build", str(build)]
    require_success(build_command, cwd=project)

    dll = build / "libgenesis_native.dll"
    assert dll.is_file()
    original_dll_hash = sha256(dll)
    initial_source_id = source_id_from_fresh_process(dll)
    receipt = json.loads((build / "native-build-receipt.json").read_text(encoding="utf-8"))
    assert receipt["source_id"] == initial_source_id
    assert receipt["dependency_commit"] == json.loads((project / "third_party/sources.json").read_text())["commit"]
    assert "CXX_COMPILER=" in receipt["build_options"]

    locked_header = focused / "src/arch/m68k/alu.hpp"
    pristine_header = locked_header.read_bytes()
    locked_header.write_bytes(pristine_header + b"\n// deliberate locked-byte mutation\n")
    refused = command(build_command, cwd=project)
    assert refused.returncode != 0
    assert "Source mismatch: src/arch/m68k/alu.hpp" in refused.stdout + refused.stderr
    assert sha256(dll) == original_dll_hash

    locked_header.write_bytes(pristine_header)
    adapter = project / "native/machine.cpp"
    adapter.write_bytes(adapter.read_bytes() + b"\n// comment-only identity regression mutation\n")
    require_success(build_command, cwd=project)
    refreshed_source_id = source_id_from_fresh_process(dll)
    assert refreshed_source_id != initial_source_id
    refreshed_receipt = json.loads((build / "native-build-receipt.json").read_text(encoding="utf-8"))
    assert refreshed_receipt["source_id"] == refreshed_source_id
