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
import time
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
DEFAULT_NATIVE = ROOT / "build" / "libgenesis_native.dll"


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
    env["GENESIS_NATIVE_LIBRARY"] = str(native.resolve())
    return env


def _visible_verification(command, *, cwd, env, check=False):
    """Observe one verifier without mistaking a quiet worker for failure.

    The verifier owns worker timeouts and the qualification receipt. This
    launcher only reports process liveness; it neither restarts nor qualifies.
    """
    started = time.monotonic()
    pid_file = None
    if "--output" in command:
        # verify_status reads this while comparison.json does not exist yet.
        output = Path(command[command.index("--output") + 1])
        output.mkdir(parents=True, exist_ok=True)
        pid_file = output / "launcher.pid"
    with subprocess.Popen(command, cwd=cwd, env=env) as process:
        if pid_file is not None:
            pid_file.write_text(str(process.pid), encoding="utf-8")
        print(f"[verification] started pid={process.pid}; two fresh workers "
              "(parallel unless --sequential); comparison.json is written at completion",
              file=sys.stderr, flush=True)
        while True:
            try:
                code = process.wait(timeout=30)
                break
            except subprocess.TimeoutExpired:
                print(f"[verification] RUNNING pid={process.pid} "
                      f"elapsed={time.monotonic() - started:.0f}s; "
                      "no final receipt yet is not a failure", file=sys.stderr, flush=True)
        print(f"[verification] EXIT pid={process.pid} code={code} "
              f"elapsed={time.monotonic() - started:.1f}s; inspect comparison.json",
              file=sys.stderr, flush=True)
    if pid_file is not None and pid_file.exists():
        pid_file.unlink()
    return subprocess.CompletedProcess(command, code)


def run(argv: Sequence[str], *, runner=None) -> int:
    selected, forwarded = split_native_option(argv)
    if not forwarded:
        raise ValueError("supply a genesis-re command, for example: doctor, or play --game gods")
    native = (selected or DEFAULT_NATIVE).expanduser().resolve()
    if not native.is_file():
        raise FileNotFoundError(f"Native DLL not found: {native}")
    # Python timestamp caches can hide a same-size edit within one second.
    # An empty cache prefix plus no writes guarantees source imports, including
    # the comparator's child workers, without deleting checkout-owned caches.
    with tempfile.TemporaryDirectory(prefix="genesis-re-import-") as cache:
        env = child_environment(native)
        env.update(PYTHONPYCACHEPREFIX=cache, PYTHONDONTWRITEBYTECODE="1")
        invoke = runner or (_visible_verification if forwarded[0] == "history-verify" else subprocess.run)
        result = invoke(
            [sys.executable, "-m", "genesis_re", *forwarded],
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
