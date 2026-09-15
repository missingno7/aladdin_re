"""Small terminal/failure witness captures using public machine inspection only."""
import json
from pathlib import Path

from . import artifacts


def capture(machine, directory, *, execution_error=None, receipt=None):
    """Never advance time or drain PCM; a failed run may not permit a snapshot."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    meta = {"scope": "terminal state" if execution_error is None else "execution failure state",
            "execution_error": execution_error, "capture_errors": {}}
    if receipt is not None:
        meta["receipt"] = receipt
    for key, read in (("info", lambda: machine.info), ("registers", machine.registers)):
        try:
            meta[key] = read()
        except Exception as error:
            meta["capture_errors"][key] = str(error)
    for name, read in (("ram.bin", lambda: machine.peek_ram(0, 65536)),
                       ("oracle-state.bin", machine.snapshot)):
        try:
            data = read()
            (directory / name).write_bytes(data)
            meta[name] = {"sha256": artifacts.digest(data), "size": len(data)}
        except Exception as error:
            meta["capture_errors"][name] = str(error)
    (directory / "machine.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compare(directory):
    """Differences at the captured stops, not a claim about the first bad opcode."""
    directory = Path(directory)
    result = {"directory": str(directory.resolve()),
              "scope": "terminal/failure stops; not the first differing instruction"}
    captures, ram = {}, {}
    for role in ("reference", "candidate"):
        try:
            captures[role] = artifacts.decode_json(artifacts.read_bounded(directory / role / "machine.json"))
            path = directory / role / "ram.bin"
            if "ram.bin" in captures[role]:
                data = artifacts.read_bounded(path)
                if len(data) != 65536 or captures[role]["ram.bin"] != {"size": len(data), "sha256": artifacts.digest(data)}:
                    raise ValueError("Work RAM capture integrity mismatch")
                ram[role] = data
        except (OSError, ValueError, KeyError, TypeError) as error:
            result.setdefault("unavailable", {})[role] = str(error)
    result["captures"] = captures
    if len(captures) != 2:
        return result
    left, right = captures["reference"], captures["candidate"]
    ticks = [item.get("info", {}).get("tick") for item in (left, right)]
    result["same_tick"] = ticks[0] is not None and ticks[0] == ticks[1]
    if "registers" in left and "registers" in right:
        result["register_differences"] = {
            key: {"reference": left["registers"].get(key), "candidate": right["registers"].get(key)}
            for key in sorted(left["registers"].keys() | right["registers"].keys())
            if left["registers"].get(key) != right["registers"].get(key)}
    if len(ram) == 2:
        changed = [i for i, (a, b) in enumerate(zip(ram["reference"], ram["candidate"])) if a != b]
        result["ram"] = {"changed_bytes": len(changed), "truncated": len(changed) > 32,
                         "first_changes": [{"address": f"0x{0xff0000 + i:06X}",
                                            "reference": ram["reference"][i], "candidate": ram["candidate"][i]}
                                           for i in changed[:32]]}
    result["device_state"] = "Not decoded; snapshots remain opaque. Equal registers/RAM do not imply equal machine state."
    return result
