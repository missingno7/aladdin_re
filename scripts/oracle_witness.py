"""Construct raw original-ROM spawn fixtures without legacy archives.

The fixture is deliberately small: cold boot, ten logical frame steps, then
one native atomic setup at a selected spawn entry.  It is an oracle aid for
strict qualification, not a replay/history format or execution framework.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine, library_path
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import Candidate
from aladdin_sega.receipt import execution_receipt
from aladdin_sega.boundary import (SPAWN_REGION_ENTRIES, SPAWN_DISPATCH_ITERATION_ENTRY,
                                   SPAWN_REVERSE_CALLER_ENTRY, SPAWN_UPPER_VARIANT_CALLER_ENTRY,
                                   SPAWN_UPPER_SCRIPTED_CALLER_ENTRY, SPAWN_REVERSE_PLAIN_CALLER_ENTRY,
                                   SPAWN_UPPER_PLAIN_CALLER_ENTRY, SPAWN_UPPER_STANDARD_CALLER_ENTRY,
                                   SPAWN_UPPER_SECONDARY_CALLER_ENTRY, SPAWN_UPPER_TERTIARY_CALLER_ENTRY,
                                   SPAWN_UPPER_TYPED_CALLER_ENTRY, SPAWN_UPPER_CALLER_ENTRY,
                                   SPAWN_PRIMARY_DISPATCH_ENTRY, SPAWN_PRIMARY_DOUBLE_GUARD_ENTRY,
                                   SPAWN_PRIMARY_INVERSE_GUARD_ENTRY, SPAWN_PRIMARY_MIXED_GUARD_ENTRY,
                                   SPAWN_LOWER_DISPATCH_ENTRY, SPAWN_UPPER_DISPATCH_ENTRY,
                                   spawn_dispatch_iteration)


SAFE_RETURN = 0x1B65BE
STACK = 0xFFEC00
TEMPLATE = 0x1B79B8
ENTRY_BASES = {
    0x1B524E: (0xFF7E82, 24, 1),
    0x1B5256: (0xFF8470, 24, -1),
    0x1B525E: (0xFF8368, 20, -1),
    0x1B5266: (0xFF7F06, 20, 1),
}
DISPATCH_CALLBACKS = (
    SPAWN_REVERSE_CALLER_ENTRY, SPAWN_UPPER_VARIANT_CALLER_ENTRY,
    SPAWN_UPPER_SCRIPTED_CALLER_ENTRY, SPAWN_REVERSE_PLAIN_CALLER_ENTRY,
    SPAWN_UPPER_PLAIN_CALLER_ENTRY, SPAWN_UPPER_STANDARD_CALLER_ENTRY,
    SPAWN_UPPER_SECONDARY_CALLER_ENTRY, SPAWN_UPPER_TERTIARY_CALLER_ENTRY,
    SPAWN_UPPER_TYPED_CALLER_ENTRY, SPAWN_UPPER_CALLER_ENTRY,
    SPAWN_PRIMARY_DISPATCH_ENTRY, SPAWN_PRIMARY_DOUBLE_GUARD_ENTRY,
    SPAWN_PRIMARY_INVERSE_GUARD_ENTRY, SPAWN_PRIMARY_MIXED_GUARD_ENTRY,
    SPAWN_LOWER_DISPATCH_ENTRY, SPAWN_UPPER_DISPATCH_ENTRY,
)


def write_word(address: int, value: int) -> tuple[tuple[int, int], ...]:
    return tuple((address + i, (value >> (8 * (1 - i))) & 0xFF) for i in range(2))


def write_long(address: int, value: int) -> tuple[tuple[int, int], ...]:
    return tuple((address + i, (value >> (8 * (3 - i))) & 0xFF) for i in range(4))


def cold_fixture(entry: int, *, free: int | None = 0, incoming_x: bool = False,
                 pc_entry: int | None = None):
    if entry not in ENTRY_BASES:
        raise ValueError(f"unsupported spawn entry {entry:06X}")
    rom = read_rom(DEFAULT_ROM)
    machine = Machine(rom)
    for frame in range(1, 11):
        machine.run(target=FRAME_TICKS * frame)
        machine.audio()
    registers = machine.registers()
    registers.update({"a2": 0xFF6000, "a6": TEMPLATE, "a7": STACK,
                      "d0": 0, "d2": 3, "d3": 1, "pc": entry if pc_entry is None else pc_entry,
                      "sr": (registers["sr"] & ~0x1F) | (0x10 if incoming_x else 0)})
    base, count, direction = ENTRY_BASES[entry]
    writes = list(write_long(STACK + 4 * i, SAFE_RETURN) for i in range(-16, 151))
    flat = [byte for group in writes for byte in group]
    flat += list(write_word(0xFFF150, 1) + write_word(0xFF7DB0, 1))
    flat += list(write_word(0xFFF152, 1) + write_word(0xFF7DB2, 1))
    if free is not None and not 0 <= free < count:
        raise ValueError("free slot outside selected pool")
    for index in range(count):
        address = (base + direction * 0x42 * index) & 0xFFFFFF
        flat.append((address, 0 if free == index else 1))
    # Native atomic replacement is only legal at a parked instruction.
    current_pc = machine.info["pc"]
    machine.gates([current_pc])
    if machine.run(instructions=1) != "gate":
        machine.close()
        raise RuntimeError("could not park cold fixture at current PC")
    accepted = machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=4, instructions=1, last_pc=entry,
                              writes=flat, registers=registers)
    if not accepted:
        machine.close()
        raise RuntimeError("native fixture setup was not accepted")
    return machine


def dispatcher_fixture(target: int, *, free: int | None = 0, incoming_x: bool = False):
    if target not in DISPATCH_CALLBACKS:
        raise ValueError(f"unsupported dispatcher callback {target:06X}")
    machine = cold_fixture(0x1B5266, free=free, incoming_x=incoming_x,
                           pc_entry=SPAWN_DISPATCH_ITERATION_ENTRY)
    machine.gates([SPAWN_DISPATCH_ITERATION_ENTRY])
    assert machine.run(instructions=1) == "gate"
    registers = machine.registers()
    registers.update({"a0": 0xFF6000, "a4": target, "d4": 2, "d5": 0, "d6": 0})
    assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                          cycles=1, instructions=1, last_pc=SPAWN_DISPATCH_ITERATION_ENTRY,
                          writes=[], registers=registers)
    return machine


def observable(machine):
    return {"state": artifacts.digest(machine.snapshot()), "info": machine.info,
            "registers": machine.registers(), "ram": artifacts.digest(machine.peek_ram(0, 65536)),
            "frame": artifacts.digest(machine.frame()[2]), "pcm": artifacts.digest(machine.audio())}


def fresh_process_future(state: bytes) -> dict:
    """Restore one raw post-outer state in a new Python/native process."""
    with tempfile.TemporaryDirectory(prefix="aladdin-oracle-") as directory:
        path = Path(directory) / "outer.state"
        path.write_bytes(state)
        command = [sys.executable, str(Path(__file__).resolve()), "--fresh-child", str(path)]
        result = subprocess.run(command, capture_output=True, text=True, check=False,
                                env={**__import__("os").environ,
                                     "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
        if result.returncode:
            raise RuntimeError(f"fresh oracle child failed: {result.stderr or result.stdout}")
        return json.loads(result.stdout)


def execute(entry: int, *, free: int | None, candidate: str | None, incoming_x: bool):
    machine = cold_fixture(entry, free=free, incoming_x=incoming_x)
    try:
        outer = int.from_bytes(machine.peek_ram(STACK & 0xFFFF, 4), "big") & 0xFFFFFF
        machine.gates([entry, outer])
        assert machine.run(instructions=1) == "gate"
        recovery = Candidate(candidate) if candidate else None
        if recovery:
            recovery.arm(machine)
            assert machine.run(instructions=1) == "gate"
            assert recovery.on_gate(machine, machine.info["tick"] + 1_000_000)
        else:
            machine.gate(entry, bypass_once=True)
            assert machine.run(instructions=20_000) == "gate"
        at_outer = observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        return at_outer, observable(machine), recovery.stats if recovery else None
    finally:
        machine.close()


def execute_dispatch(target: int, *, free: int | None, candidate: str | None, incoming_x: bool,
                     include_raw: bool = False):
    machine = dispatcher_fixture(target, free=free, incoming_x=incoming_x)
    try:
        machine.gates([SPAWN_DISPATCH_ITERATION_ENTRY, 0x1AE44A, 0x1AE47C])
        assert machine.run(instructions=1) == "gate"
        recovery = Candidate(candidate) if candidate else None
        if recovery:
            recovery.arm(machine)
            assert machine.run(instructions=1) == "gate"
            assert recovery.on_gate(machine, machine.info["tick"] + 1_000_000)
        else:
            machine.gate(SPAWN_DISPATCH_ITERATION_ENTRY, bypass_once=True)
            assert machine.run(instructions=20_000) == "gate"
        outer_state = machine.snapshot()
        at_outer = observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        future_state = machine.snapshot()
        future = observable(machine)
        result = (at_outer, future, recovery.stats if recovery else None)
        if include_raw:
            return at_outer, outer_state, future, future_state, recovery.stats if recovery else None
        return result
    finally:
        machine.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry", action="append", type=lambda value: int(value, 0), default=None)
    parser.add_argument("--callback", action="append", type=lambda value: int(value, 0),
                        default=[])
    parser.add_argument("--all-callbacks", action="store_true")
    parser.add_argument("--fresh-process", action="store_true")
    parser.add_argument("--fresh-child", type=Path)
    parser.add_argument("--free", type=int, default=0)
    parser.add_argument("--exhausted", action="store_true")
    parser.add_argument("--incoming-x", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.fresh_child:
        machine = Machine(read_rom(DEFAULT_ROM))
        try:
            machine.restore(args.fresh_child.read_bytes())
            assert machine.run(instructions=150) == "limit"
            print(json.dumps(observable(machine), sort_keys=True))
            return 0
        finally:
            machine.close()
    free = None if args.exhausted else args.free
    rows = []
    for entry in (list(SPAWN_REGION_ENTRIES) if args.entry is None else args.entry):
        expected, expected_future, _ = execute(entry, free=free, candidate=None, incoming_x=args.incoming_x)
        actual, actual_future, stats = execute(entry, free=free, candidate="lifecycle", incoming_x=args.incoming_x)
        rows.append({"entry": f"{entry:06X}", "provenance": "constructed original-ROM cold-root fixture",
                     "free": free, "incoming_x": args.incoming_x, "equal_outer": actual == expected,
                     "equal_future": actual_future == expected_future, "stats": stats})
    callbacks = list(DISPATCH_CALLBACKS) if args.all_callbacks else args.callback
    for target in callbacks:
        expected, expected_future, _ = execute_dispatch(target, free=free, candidate=None,
                                                        incoming_x=args.incoming_x)
        actual, actual_future, stats = execute_dispatch(target, free=free, candidate="lifecycle",
                                                        incoming_x=args.incoming_x)
        fresh = None
        if args.fresh_process:
            _, outer_state, _, _, _ = execute_dispatch(target, free=free, candidate="lifecycle",
                                                       incoming_x=args.incoming_x, include_raw=True)
            fresh = fresh_process_future(outer_state) == actual_future
        rows.append({"callback": f"{target:06X}", "provenance": "constructed original-ROM dispatcher fixture",
                     "free": free, "incoming_x": args.incoming_x, "equal_outer": actual == expected,
                     "equal_future": actual_future == expected_future, "fresh_process_150": fresh,
                     "stats": stats})
    result = {"status": "PASS" if all(row["equal_outer"] and row["equal_future"]
                                        and row.get("fresh_process_150") is not False for row in rows) else "FAIL",
              "native_library": str(library_path()), "frame_ticks": FRAME_TICKS,
              "receipt": execution_receipt(candidate="lifecycle"), "rows": rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
