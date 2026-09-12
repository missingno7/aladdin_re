"""Run the source tree against an already-built native DLL.

This is deliberately a thin process launcher: it never builds, installs, or
downloads anything.  It exists so an edit below ``src`` is what a fresh Python
process imports during recovery work.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
DEFAULT_NATIVE = ROOT / "build" / "libaladdin_native.dll"


def split_native_option(argv: Sequence[str]) -> tuple[Path | None, list[str]]:
    """Remove this launcher's ``--native`` option without touching CLI options."""
    native = None
    forwarded: list[str] = []
    index = 0
    while index < len(argv):
        value = argv[index]
        if value == "--native":
            if native is not None or index + 1 == len(argv):
                raise ValueError("--native requires one path and may be supplied once")
            native = Path(argv[index + 1])
            index += 2
        elif value.startswith("--native="):
            if native is not None or value == "--native=":
                raise ValueError("--native requires one path and may be supplied once")
            native = Path(value.removeprefix("--native="))
            index += 1
        else:
            forwarded.append(value)
            index += 1
    return native, forwarded


def child_environment(native: Path, inherited: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment that makes the checkout win over an installed wheel."""
    env = dict(os.environ if inherited is None else inherited)
    source = str(SOURCE_ROOT.resolve())
    old_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = source if not old_pythonpath else source + os.pathsep + old_pythonpath
    env["ALADDIN_NATIVE_LIBRARY"] = str(native.resolve())
    return env


def run(argv: Sequence[str], *, runner=subprocess.run) -> int:
    selected, forwarded = split_native_option(argv)
    if not forwarded:
        raise ValueError("supply an aladdin-sega command, for example: doctor")
    native = (selected or DEFAULT_NATIVE).expanduser().resolve()
    if not native.is_file():
        raise FileNotFoundError(f"Native DLL not found: {native}")
    # Python timestamp caches can hide a same-size edit within one second.
    # An empty cache prefix plus no writes guarantees source imports, including
    # the comparator's child workers, without deleting checkout-owned caches.
    with tempfile.TemporaryDirectory(prefix="aladdin-import-") as cache:
        env = child_environment(native)
        env.update(PYTHONPYCACHEPREFIX=cache, PYTHONDONTWRITEBYTECODE="1")
        result = runner(
            [sys.executable, "-m", "aladdin_sega", *forwarded],
            cwd=ROOT,
            env=env,
            check=False,
        )
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except (ValueError, FileNotFoundError) as error:
        print(f"dev.py: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
