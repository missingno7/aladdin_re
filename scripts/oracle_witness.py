"""Construct original-ROM fixtures and qualify bounded recovered regions.

The fixture is deliberately small: cold boot, ten logical frame steps, then
one native atomic setup at a selected spawn entry.  It is an oracle aid for
strict qualification, not a replay/history format or execution framework.
The same entry-to-return runner serves setup parents and contact callbacks;
game-specific fixture construction remains explicit.
"""
from __future__ import annotations

import argparse
from collections import namedtuple
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
                                   SPAWN_ROW_DISPATCH_WALKER_ENTRY,
                                   SPAWN_ROW_DISPATCH_WALKER_LAST_PC,
                                   SPAWN_SETUP_LEFT_ENTRY, SPAWN_SETUP_RIGHT_ENTRY,
                                   SPAWN_SETUP_ROW_LOW_ENTRY, SPAWN_SETUP_ROW_HIGH_ENTRY,
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
CALLER_POOLS = {0x1B6ED0: 0x1B5266, 0x1B6F0C: 0x1B525E, 0x1B6F1E: 0x1B525E}
GUARD_TARGETS = (0x1B7354, 0x1B742A, 0x1B744A)
GUARD_ADDRESSES = {0x1B7354: 0xFFF171, 0x1B742A: 0xFFF172, 0x1B744A: 0xFFF16F,
                   0x1B71A0: 0xFFF12A}
GUARD_SLOT_TYPES = {0x1B742A: 0x39}
CALLER_POOLS.update({0x1B7354: 0x1B5266, 0x1B742A: 0x1B524E, 0x1B744A: 0x1B5266})
DIRECT_CALLER_POOLS = dict(CALLER_POOLS)
PLAIN_WRAPPERS = {
    0x1B700C: (0x1B525E, 0x1B80FC),
    0x1B6D84: (0x1B5266, 0x1B7F30),
    0x1B6726: (0x1B525E, 0x1B8070),
    0x1B68CA: (0x1B5256, 0x1B7C9C),
    0x1B6C4E: (0x1B524E, 0x1B7A6C),
    0x1B65D4: (0x1B525E, 0x1B82B4),
}
OFFSET_WRAPPERS = {
    0x1B66F2: (0x1B525E, 0x1B7A1C, 8, 12),
    0x1B670C: (0x1B525E, 0x1B7E54, -8, 4),
    0x1B6870: (0x1B525E, 0x1B7B34, 9, 7),
}
CALLER_POOLS.update({entry: callee for entry, (callee, _) in PLAIN_WRAPPERS.items()})
CALLER_POOLS.update({entry: callee for entry, (callee, _, _, _) in OFFSET_WRAPPERS.items()})
# These five recorded callback rows use the same allocator planners but have
# distinct, semantic post-allocation suffixes.  Keep them out of
# DIRECT_CALLER_POOLS: production reaches them as dispatcher children, while
# the direct oracle still qualifies their concrete machine boundary.
CLOSURE_WRAPPERS = {
    0x1B723E: (0x1B525E,),  # type 0x8A, template 0x124494
    0x1B728E: (0x1B5266,),  # type 0x41, template 0x125D7E
    0x1B72AE: (0x1B5256,),  # reverse type 0x84, template 0x123E7A
    0x1B70D4: (0x1B5266,),  # upper type 0x4C, template 0x123E36
    0x1B71A0: (0x1B525E,),  # guarded lower, template 0x124318
}
CALLER_POOLS.update({entry: callee for entry, (callee,) in CLOSURE_WRAPPERS.items()})
CALLER_POOLS[SAFE_RETURN] = 0x1B5266
DISPATCH_CALLBACKS = (
    *CALLER_POOLS,
    SPAWN_REVERSE_CALLER_ENTRY, SPAWN_UPPER_VARIANT_CALLER_ENTRY,
    SPAWN_UPPER_SCRIPTED_CALLER_ENTRY, SPAWN_REVERSE_PLAIN_CALLER_ENTRY,
    SPAWN_UPPER_PLAIN_CALLER_ENTRY, SPAWN_UPPER_STANDARD_CALLER_ENTRY,
    SPAWN_UPPER_SECONDARY_CALLER_ENTRY, SPAWN_UPPER_TERTIARY_CALLER_ENTRY,
    SPAWN_UPPER_TYPED_CALLER_ENTRY, SPAWN_UPPER_CALLER_ENTRY,
    SPAWN_PRIMARY_DISPATCH_ENTRY, SPAWN_PRIMARY_DOUBLE_GUARD_ENTRY,
    SPAWN_PRIMARY_INVERSE_GUARD_ENTRY, SPAWN_PRIMARY_MIXED_GUARD_ENTRY,
    SPAWN_LOWER_DISPATCH_ENTRY, SPAWN_UPPER_DISPATCH_ENTRY,
)

WALKER_ENTRY = 0x1AE44A
WALKER_EXIT = 0x1AE47C


def write_word(address: int, value: int) -> tuple[tuple[int, int], ...]:
    return tuple((address + i, (value >> (8 * (1 - i))) & 0xFF) for i in range(2))


def write_long(address: int, value: int) -> tuple[tuple[int, int], ...]:
    return tuple((address + i, (value >> (8 * (3 - i))) & 0xFF) for i in range(4))


def cold_fixture(entry: int, *, free: int | None = 0, incoming_x: bool = False,
                 pc_entry: int | None = None, guard_entry: int | None = None,
                 guard_value: int | None = None, slot_type: int | None = None,
                 stack: int = STACK, initial_d0: int = 0):
    if entry not in ENTRY_BASES:
        raise ValueError(f"unsupported spawn entry {entry:06X}")
    rom = read_rom(DEFAULT_ROM)
    machine = Machine(rom)
    for frame in range(1, 11):
        machine.run(target=FRAME_TICKS * frame)
        machine.audio()
    registers = machine.registers()
    registers.update({"a2": 0xFF6000, "a6": TEMPLATE, "a7": stack,
                      "d0": initial_d0, "d2": 3, "d3": 1, "pc": entry if pc_entry is None else pc_entry,
                      "sr": (registers["sr"] & ~0x1F) | (0x10 if incoming_x else 0)})
    base, count, direction = ENTRY_BASES[entry]
    writes = list(write_long(stack + 4 * i, SAFE_RETURN) for i in range(-16, 151))
    flat = [byte for group in writes for byte in group]
    flat.append((0xFFF104, 0xA5))
    if guard_value is not None:
        if guard_entry not in GUARD_ADDRESSES:
            raise ValueError(f"unsupported guard entry {guard_entry!r}")
        flat.append((GUARD_ADDRESSES[guard_entry], guard_value & 0xFF))
    if slot_type is not None:
        flat.append((0xFF7E3C, slot_type & 0xFF))
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


def dispatcher_fixture(target: int, *, free: int | None = 0, incoming_x: bool = False,
                       guard_value: int | None = None, stack: int = STACK,
                       initial_d0: int = 0):
    if target not in DISPATCH_CALLBACKS and target != SAFE_RETURN:
        raise ValueError(f"unsupported dispatcher callback {target:06X}")
    machine = cold_fixture(CALLER_POOLS.get(target, 0x1B5266), free=free, incoming_x=incoming_x,
                           pc_entry=SPAWN_DISPATCH_ITERATION_ENTRY,
                           guard_entry=target if target in GUARD_ADDRESSES else None,
                           guard_value=guard_value,
                           slot_type=GUARD_SLOT_TYPES.get(target) if guard_value else None,
                           stack=stack, initial_d0=initial_d0)
    machine.gates([SPAWN_DISPATCH_ITERATION_ENTRY])
    assert machine.run(instructions=1) == "gate"
    registers = machine.registers()
    registers.update({"a0": 0xFF6000, "a4": target, "d0": initial_d0,
                      "d4": 2, "d5": 0, "d6": 0})
    assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                          cycles=1, instructions=1, last_pc=SPAWN_DISPATCH_ITERATION_ENTRY,
                          writes=[], registers=registers)
    return machine


def walker_fixture(fixture: str | Path | bytes, *, registers: dict[str, int] | None = None,
                   writes: tuple[tuple[int, int], ...] = (),
                   entry: int = WALKER_ENTRY):
    """Restore a captured walker entry, with optional test-only overrides."""
    machine = Machine(read_rom(DEFAULT_ROM))
    if isinstance(fixture, (bytes, bytearray)):
        machine.restore(bytes(fixture))
    else:
        path = Path(fixture)
        if path.suffix != ".state":
            path = path.with_suffix(".state")
        machine.restore(path.read_bytes())
    if machine.info["pc"] != entry:
        machine.close()
        raise ValueError(f"walker fixture is not parked at {entry:06X}")
    if registers or writes:
        machine.gates([entry])
        if machine.run(instructions=1) != "gate":
            machine.close()
            raise RuntimeError("could not park walker fixture for override")
        updated = machine.registers()
        if registers:
            updated.update(registers)
        if not machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=1, instructions=1, last_pc=entry,
                              writes=list(writes), registers=updated):
            machine.close()
            raise RuntimeError("walker fixture override was not accepted")
    return machine


def _callback_flag(callback: int) -> int:
    rom = read_rom(DEFAULT_ROM)
    for flag in range(256):
        address = 0x004154 + flag * 4
        if int.from_bytes(rom[address:address + 4], "big") & 0xFFFFFF == callback:
            return flag
    raise ValueError(f"callback {callback:06X} is absent from the fixed ROM table")


def constructed_walker_state(*, count: int = 16,
                             callbacks: tuple[int | None, ...] | None = None,
                             stride: int = 0x258, incoming_x: bool = False,
                             exhausted: bool = False, cursor: int = 0xFF6000,
                             slot_indices: tuple[int, ...] | None = None,
                             initial_d0: int = 0, row: bool = False) -> bytes:
    """Build a small walker state from the normal cold oracle setup.

    The table identity remains the real ROM table (A1=4154, A2=FFAE87). Every
    cursor word and flag byte is explicit RAM fixture input, and callback
    addresses are resolved from that fixed ROM table. This keeps qualification
    independent of recorded artifact files while retaining the normal cold
    setup path used by the other oracles.
    """
    maximum = 23 if row else 16
    if not 1 <= count <= maximum:
        raise ValueError(f"walker count must be in one..{maximum}")
    if callbacks is None:
        callbacks = (None,) * count
    if len(callbacks) < count:
        raise ValueError("callback sequence is shorter than walker count")
    if slot_indices is None:
        slot_indices = tuple(0x100 + index for index in range(count))
    if len(slot_indices) < count:
        raise ValueError("slot index sequence is shorter than walker count")
    entry = SPAWN_ROW_DISPATCH_WALKER_ENTRY if row else WALKER_ENTRY
    machine = cold_fixture(0x1B5266, free=0, pc_entry=entry)
    try:
        machine.gates([entry])
        if machine.run(instructions=1) != "gate":
            raise RuntimeError("could not park constructed walker")
        registers = machine.registers()
        registers.update({"a0": cursor, "a1": 0x004154, "a2": 0xFFAE87,
                          "d4": count - 1, "d5": stride & 0xFFFFFFFF,
                          "d0": initial_d0 & 0xFFFFFFFF,
                          "d6": 0, "sr": (registers["sr"] & ~0x1F) |
                          (0x10 if incoming_x else 0)})
        writes_list = []
        for index in range(count):
            slot_address = (cursor + (2 if row else stride) * index) & 0xFFFFFFFF
            slot_index = slot_indices[index]
            writes_list.extend(write_word(slot_address, slot_index << 1))
            callback = callbacks[index]
            flag = 0 if callback is None else _callback_flag(callback)
            writes_list.append((0xFFAE87 + slot_index, flag))
        # Seed every known 24-slot object pool as free. The callback itself
        # can still be made exhausted explicitly without changing the walker
        # selection inputs.
        for base, pool_count, direction in ENTRY_BASES.values():
            for index in range(pool_count):
                writes_list.append(((base + direction * 0x42 * index) & 0xFFFFFF,
                                    1 if exhausted else 0))
        writes = tuple(writes_list)
        if not machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=1, instructions=1, last_pc=entry,
                              writes=list(writes), registers=registers):
            raise RuntimeError("constructed walker setup was not accepted")
        return machine.snapshot()
    finally:
        machine.close()


def constructed_row_walker_state(*, count: int = 23,
                                 callbacks: tuple[int | None, ...] | None = None,
                                 incoming_x: bool = False, exhausted: bool = False,
                                 cursor: int = 0xFF6000,
                                 slot_indices: tuple[int, ...] | None = None,
                                 initial_d0: int = 0) -> bytes:
    """Build a portable 23-slot row-walker fixture from explicit RAM inputs."""
    return constructed_walker_state(count=count, callbacks=callbacks,
                                    stride=2, incoming_x=incoming_x,
                                    exhausted=exhausted, cursor=cursor,
                                    slot_indices=slot_indices,
                                    initial_d0=initial_d0, row=True)


def constructed_setup_state(entry: int, *, callbacks: tuple[int | None, ...] | None = None,
                            incoming_x: bool = False, exhausted: bool = False,
                            cursor: int = 0xFF6000, stride: int = 0x258,
                            position: int = 0x1237, varying: int = 0x245F,
                            slot_indices: tuple[int, ...] | None = None,
                            initial_d0: int = 0xABCD0000,
                            initial_d4: int = 0x13570000,
                            initial_d5: int = 0x24680000,
                            initial_d6: int = 0xFACE0000,
                            stack: int = STACK) -> bytes:
    """Build a portable full setup-to-RTS fixture.

    The setup prefix is real ROM input: it masks the two coordinate words,
    installs its offsets, then enters the existing column or row walker.  All
    walker slots and callback flags are explicit, so this fixture is suitable
    for default tests without relying on ignored captured states.
    """
    if entry not in SETUP_ENTRIES:
        raise ValueError(f"unsupported spawn setup entry {entry:06X}")
    row = entry in (SPAWN_SETUP_ROW_LOW_ENTRY, SPAWN_SETUP_ROW_HIGH_ENTRY)
    count = 23 if row else 16
    if callbacks is None:
        callbacks = (None,) * count
    if len(callbacks) < count:
        raise ValueError("callback sequence is shorter than setup walker count")
    if slot_indices is None:
        slot_indices = tuple(0x100 + index for index in range(count))
    if len(slot_indices) < count:
        raise ValueError("slot index sequence is shorter than setup walker count")
    machine = cold_fixture(0x1B5266, free=0, incoming_x=incoming_x,
                           pc_entry=entry, stack=stack,
                           initial_d0=initial_d0)
    try:
        machine.gates([entry])
        if machine.run(instructions=1) != "gate":
            raise RuntimeError("could not park constructed setup")
        registers = machine.registers()
        registers.update({"d0": initial_d0 & 0xFFFFFFFF,
                          "d4": initial_d4 & 0xFFFFFFFF,
                          "d5": initial_d5 & 0xFFFFFFFF,
                          "d6": initial_d6 & 0xFFFFFFFF,
                          "a0": cursor & 0xFFFFFFFF,
                          "sr": (registers["sr"] & ~0x1F) |
                                (0x10 if incoming_x else 0)})
        writes_list = [*write_word(0xFF7E06, position),
                       *write_word(0xFF7E08, varying),
                       *write_long(0xFF7DAC, cursor),
                       *write_word(0xFF7DB4, stride)]
        stride_word = stride & 0xFFFF
        signed_stride = stride_word if stride_word < 0x8000 else stride_word - 0x10000
        step = 2 if row else signed_stride
        for index in range(count):
            slot_address = (cursor + step * index) & 0xFFFFFFFF
            slot_index = slot_indices[index]
            writes_list.extend(write_word(slot_address, slot_index << 1))
            callback = callbacks[index]
            flag = 0 if callback is None else _callback_flag(callback)
            writes_list.append((0xFFAE87 + slot_index, flag))
        for base, pool_count, direction in ENTRY_BASES.values():
            for index in range(pool_count):
                writes_list.append(((base + direction * 0x42 * index) & 0xFFFFFF,
                                    1 if exhausted else 0))
        if not machine.atomic(target=machine.info["tick"] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=entry, writes=writes_list,
                              registers=registers):
            raise RuntimeError("constructed setup was not accepted")
        return machine.snapshot()
    finally:
        machine.close()


def observable(machine):
    return {"state": artifacts.digest(machine.snapshot()), "info": machine.info,
            "registers": machine.registers(), "ram": artifacts.digest(machine.peek_ram(0, 65536)),
            "frame": artifacts.digest(machine.frame()[2]), "pcm": artifacts.digest(machine.audio())}


class ExecutionResult(namedtuple("ExecutionResultBase", (
        "outer", "future", "stats", "outer_state", "future_state", "iterations"))):
    """Named result shared by every oracle execution shape.

    Raw states and walker iteration counts are opt-in evidence fields; normal
    qualification only consumes the outer state, future state, and stats.
    """

    __slots__ = ()

    def __new__(cls, outer, future, stats, outer_state=None,
                future_state=None, iterations=None):
        return super().__new__(cls, outer, future, stats, outer_state,
                               future_state, iterations)


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


def execute(entry: int, *, free: int | None, candidate: str | None, incoming_x: bool,
            guard_value: int | None = None):
    machine = cold_fixture(CALLER_POOLS.get(entry, entry), free=free, incoming_x=incoming_x,
                           pc_entry=entry, guard_entry=entry if entry in GUARD_ADDRESSES else None,
                           guard_value=guard_value,
                           slot_type=GUARD_SLOT_TYPES.get(entry) if guard_value else None)
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
        return ExecutionResult(at_outer, observable(machine),
                                recovery.stats if recovery else None)
    finally:
        machine.close()


def execute_dispatch(target: int, *, free: int | None, candidate: str | None, incoming_x: bool,
                     include_raw: bool = False, guard_value: int | None = None,
                     stack: int = STACK, initial_d0: int = 0):
    machine = dispatcher_fixture(target, free=free, incoming_x=incoming_x,
                                 guard_value=guard_value, stack=stack,
                                 initial_d0=initial_d0)
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
        return ExecutionResult(at_outer, future, recovery.stats if recovery else None,
                               outer_state if include_raw else None,
                               future_state if include_raw else None)
    finally:
        machine.close()


SETUP_ENTRIES = (SPAWN_SETUP_LEFT_ENTRY, SPAWN_SETUP_RIGHT_ENTRY,
                 SPAWN_SETUP_ROW_LOW_ENTRY, SPAWN_SETUP_ROW_HIGH_ENTRY)


def setup_fixture(fixture: str | Path | bytes, entry: int):
    """Restore a captured region entry parked before its first instruction."""
    return walker_fixture(fixture, entry=entry)


def execute_region(fixture: str | Path | bytes, *, entry: int,
                   candidate: str | None, register_overrides: dict[str, int] | None = None,
                   future_instructions: int = 150, include_raw: bool = False,
                   stop_after_first: bool = False, expected_return: int | None = None):
    """Qualify an entry fixture through its explicit outer return boundary."""
    machine = setup_fixture(fixture, entry)
    try:
        if register_overrides:
            machine.gates([entry])
            assert machine.run(instructions=1) == "gate"
            registers = machine.registers()
            registers.update(register_overrides)
            assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                                  cycles=1, instructions=1, last_pc=entry,
                                  writes=[], registers=registers)
        outer = int.from_bytes(machine.peek_ram(machine.registers()["a7"] & 0xFFFF, 4), "big") & 0xFFFFFF
        if expected_return is not None:
            # Explicit oracle boundary for fixtures whose callback overwrites
            # the caller's return slot. Both executions must actually reach it.
            outer = expected_return
        machine.gates([entry, outer])
        assert machine.run(instructions=1) == "gate"
        recovery = Candidate(candidate) if candidate else None
        if recovery:
            recovery.arm(machine)
            machine.gates(list(dict.fromkeys((*recovery.gate_pcs, entry, outer))))
            handled = None
            for _ in range(32):
                if machine.run(instructions=100_000) != "gate":
                    raise RuntimeError("setup candidate did not reach its outer return")
                if machine.info["pc"] == outer:
                    break
                if machine.info["pc"] not in recovery.gate_pcs and machine.info["pc"] != entry:
                    raise RuntimeError(f"setup stopped at unexpected PC {machine.info['pc']:06X}")
                handled = recovery.on_gate(machine, machine.info["tick"] + 1_000_000)
                if stop_after_first:
                    if not handled:
                        raise AssertionError("setup negative witness did not admit its first plan")
                    return ExecutionResult(observable(machine), None, recovery.stats,
                                           machine.snapshot() if include_raw else None)
                if not handled:
                    # _fallback has already retired the one native instruction;
                    # retain the complete production gate set for a local seam
                    # or a later retry at the walker head.
                    machine.gates(list(dict.fromkeys((*recovery.gate_pcs, entry, outer))))
            else:
                raise RuntimeError("setup candidate exceeded gate budget")
        else:
            machine.gate(entry, bypass_once=True)
            if machine.run(instructions=100_000) != "gate":
                raise RuntimeError("setup original did not reach its outer return")
        if machine.info["pc"] != outer:
            raise RuntimeError(f"setup did not return to {outer:06X}")
        outer_state = machine.snapshot()
        at_outer = observable(machine)
        machine.gates([])
        if machine.run(instructions=future_instructions) != "limit":
            raise RuntimeError("setup future did not reach instruction limit")
        future_state = machine.snapshot()
        future = observable(machine)
        stats = recovery.stats if recovery else None
        if include_raw:
            return ExecutionResult(at_outer, future, stats, outer_state, future_state)
        return ExecutionResult(at_outer, future, stats)
    finally:
        machine.close()


def execute_setup(fixture: str | Path | bytes, *, entry: int,
                  candidate: str | None, register_overrides: dict[str, int] | None = None,
                  future_instructions: int = 150, include_raw: bool = False,
                  stop_after_first: bool = False, expected_return: int | None = None):
    """Compatibility name for the original setup-to-walker region witness."""
    return execute_region(fixture, entry=entry, candidate=candidate,
                          register_overrides=register_overrides,
                          future_instructions=future_instructions,
                          include_raw=include_raw,
                          stop_after_first=stop_after_first,
                          expected_return=expected_return)


def execute_wrapper(entry: int, *, free: int | None, candidate: str | None,
                    incoming_x: bool, setup_writes: tuple[tuple[int, int], ...] = (),
                    include_raw: bool = False):
    """Qualify one concrete spawn wrapper at its direct original entry."""
    if entry in PLAIN_WRAPPERS:
        callee, template = PLAIN_WRAPPERS[entry]
    elif entry in OFFSET_WRAPPERS:
        callee, template, _, _ = OFFSET_WRAPPERS[entry]
    elif entry in CLOSURE_WRAPPERS:
        callee = CLOSURE_WRAPPERS[entry][0]
    else:
        raise ValueError(f"unsupported spawn wrapper {entry:06X}")
    machine = cold_fixture(callee, free=free, incoming_x=incoming_x, pc_entry=entry)
    try:
        if setup_writes:
            machine.gates([entry])
            assert machine.run(instructions=1) == "gate"
            registers = machine.registers()
            assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                                  cycles=1, instructions=1, last_pc=entry,
                                  writes=list(setup_writes), registers=registers)
        outer = int.from_bytes(machine.peek_ram(STACK & 0xFFFF, 4), "big") & 0xFFFFFF
        machine.gates([entry, outer])
        assert machine.run(instructions=1) == "gate"
        stats = None
        if candidate:
            from aladdin_sega.boundary import (spawn_offset_caller, spawn_plain_caller,
                                               spawn_closure_caller, spawn_closure_guard_caller)
            if entry in OFFSET_WRAPPERS:
                plan = spawn_offset_caller(machine, machine.registers(), entry)
            elif entry in PLAIN_WRAPPERS:
                plan = spawn_plain_caller(machine, machine.registers(), entry)
            elif entry == 0x1B71A0:
                plan = spawn_closure_guard_caller(machine, machine.registers())
            else:
                plan = spawn_closure_caller(machine, machine.registers(), entry)
            assert machine.atomic(target=machine.info["tick"] + 1_000_000,
                                  cycles=plan.cycles, instructions=plan.instructions,
                                  writes=list(plan.writes), registers=plan.registers,
                                  last_pc=plan.last_pc)
            stats = {"candidate_hits": 1, "fallbacks": 0,
                     "direct_python_calls": plan.direct_calls}
        else:
            machine.gate(entry, bypass_once=True)
            assert machine.run(instructions=20_000) == "gate"
        outer_state = machine.snapshot()
        at_outer = observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        future_state = machine.snapshot()
        future = observable(machine)
        if include_raw:
            return ExecutionResult(at_outer, future, stats, outer_state, future_state)
        return ExecutionResult(at_outer, future, stats)
    finally:
        machine.close()


def execute_walker(fixture: str | Path | bytes, *, candidate: str | None,
                   register_overrides: dict[str, int] | None = None,
                   writes: tuple[tuple[int, int], ...] = (),
                   future_instructions: int = 150, include_raw: bool = False,
                   stop_after_first: bool = False, row: bool = False):
    """Run a complete captured walker through its outer exit boundary."""
    entry = SPAWN_ROW_DISPATCH_WALKER_ENTRY if row else WALKER_ENTRY
    exit_pc = SPAWN_ROW_DISPATCH_WALKER_LAST_PC if row else WALKER_EXIT
    machine = walker_fixture(fixture, registers=register_overrides, writes=writes,
                             entry=entry)
    try:
        if isinstance(fixture, (bytes, bytearray)):
            metadata = {}
        else:
            metadata_path = Path(fixture)
            if metadata_path.suffix != ".json":
                metadata_path = metadata_path.with_suffix(".json")
            metadata = json.loads(metadata_path.read_text())
            if metadata.get("entry") != entry or metadata.get("exit") != exit_pc:
                raise ValueError("walker fixture metadata has an unexpected boundary")
        machine.gates([entry, exit_pc])
        recovery = Candidate(candidate) if candidate else None
        if recovery:
            recovery.arm(machine)
            machine.gates(list(dict.fromkeys((*recovery.gate_pcs, entry, exit_pc))))
        iterations = 0
        # The native row performs one entry per slot and reaches the outer RTS
        # only on the following stop; allow that final exit observation.
        while iterations < (24 if row else 32):
            if machine.run(instructions=100_000) != "gate":
                break
            pc = machine.info["pc"]
            if pc == exit_pc:
                break
            if pc != entry:
                if recovery:
                    recovery.on_gate(machine, machine.info["tick"] + 1_000_000)
                else:
                    machine.gate(pc, bypass_once=True)
                    machine.run(instructions=1)
                continue
            iterations += 1
            if recovery:
                handled = recovery.on_gate(machine, machine.info["tick"] + 1_000_000)
                if stop_after_first:
                    if not handled:
                        raise AssertionError("negative witness did not admit its first plan")
                    at_outer = observable(machine)
                    outer_state = machine.snapshot()
                    stats = recovery.stats
                    return ExecutionResult(at_outer, None, stats,
                                           outer_state if include_raw else None,
                                           iterations=iterations)
                if not handled:
                    # Keep the actual production gates: after one native
                    # fallback instruction, later loop heads may retry.
                    machine.gates(list(dict.fromkeys(
                        (*recovery.gate_pcs, entry, exit_pc))))
            else:
                machine.gate(entry, bypass_once=True)
                machine.run(instructions=1)
        reached_exit = machine.info["pc"] == exit_pc
        if not reached_exit:
            raise RuntimeError("walker did not reach its qualified outer exit")
        at_outer = observable(machine) if reached_exit else None
        outer_state = machine.snapshot() if reached_exit else None
        if reached_exit:
            machine.gates([])
            if machine.run(instructions=future_instructions) != "limit":
                raise RuntimeError("walker future did not reach instruction limit")
            future_state = machine.snapshot()
            future = observable(machine)
        else:
            future_state = None
            future = None
        stats = recovery.stats if recovery else None
        return ExecutionResult(at_outer, future, stats,
                               outer_state if include_raw else None,
                               future_state if include_raw else None,
                               iterations)
    finally:
        machine.close()


def recorded_walker_rows(directory: str | Path, *, row: bool = False) -> list[dict]:
    """Qualify explicitly supplied captured walkers for an evidence report."""
    directory = Path(directory)
    paths = tuple(sorted(directory.glob("walker-*.state")))
    if not paths:
        raise ValueError(f"walker directory has no walker-*.state files: {directory}")
    rows = []
    for path in paths:
        metadata = json.loads(path.with_suffix(".json").read_text())
        expected = execute_walker(path, candidate=None, row=row)
        actual = execute_walker(path, candidate="lifecycle", include_raw=True, row=row)
        rows.append({"fixture": path.name, "provenance": "recorded walker state",
                     "state_sha256": artifacts.digest(path.read_bytes()),
                     "history_id": metadata.get("history_id"),
                     "frame": metadata.get("frame"),
                     "callbacks": metadata.get("callbacks"),
                     "entry": metadata.get("entry"), "exit": metadata.get("exit"),
                     "native_iterations": expected.iterations,
                     "candidate_iterations": actual.iterations,
                     "equal_outer": actual.outer == expected.outer,
                     "equal_future": actual.future == expected.future,
                     "fresh_process_150": fresh_process_future(actual.outer_state) == actual.future,
                     "stats": actual.stats})
    return rows


def recorded_setup_rows(directory: str | Path) -> list[dict]:
    """Qualify explicitly supplied full setup-to-RTS captures.

    These captures are evidence rows, not default fixtures: callers must opt
    into the directory so ordinary qualification remains portable.
    """
    directory = Path(directory)
    paths = tuple(sorted(path for path in directory.glob("setup-*.state")
                         if not path.stem.endswith("-outer")))
    if not paths:
        raise ValueError(f"setup directory has no setup-*.state files: {directory}")
    rows = []
    for path in paths:
        metadata = json.loads(path.with_suffix(".json").read_text())
        entry = int(metadata["entry"])
        if entry not in SETUP_ENTRIES:
            raise ValueError(f"setup fixture has an unexpected entry: {entry:06X}")
        expected = execute_setup(path, entry=entry, candidate=None)
        actual = execute_setup(path, entry=entry, candidate="lifecycle",
                               include_raw=True)
        rows.append({"fixture": path.name, "provenance": "recorded full setup state",
                     "state_sha256": artifacts.digest(path.read_bytes()),
                     "history_id": metadata.get("history_id"),
                     "frame": metadata.get("frame"), "entry": entry,
                     "walker_exit": metadata.get("exit"),
                     "equal_outer": actual.outer == expected.outer,
                     "equal_future": actual.future == expected.future,
                     "fresh_process_150": fresh_process_future(actual.outer_state) == actual.future,
                     "stats": actual.stats})
    return rows


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
    parser.add_argument("--walker-directory", type=Path,
                        help="explicit directory of captured walker .state/.json evidence")
    parser.add_argument("--setup-directory", type=Path,
                        help="explicit directory of captured full setup .state/.json evidence")
    parser.add_argument("--row", action="store_true",
                        help="use the recorded 23-slot row walker boundary")
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
        expected = execute(entry, free=free, candidate=None, incoming_x=args.incoming_x)
        actual = execute(entry, free=free, candidate="lifecycle", incoming_x=args.incoming_x)
        rows.append({"entry": f"{entry:06X}", "provenance": "constructed original-ROM cold-root fixture",
                     "free": free, "incoming_x": args.incoming_x,
                     "equal_outer": actual.outer == expected.outer,
                     "equal_future": actual.future == expected.future,
                     "stats": actual.stats})
    callbacks = list(DISPATCH_CALLBACKS) if args.all_callbacks else args.callback
    for target in callbacks:
        expected = execute_dispatch(target, free=free, candidate=None,
                                    incoming_x=args.incoming_x)
        actual = execute_dispatch(target, free=free, candidate="lifecycle",
                                  incoming_x=args.incoming_x)
        fresh = None
        if args.fresh_process:
            raw = execute_dispatch(target, free=free, candidate="lifecycle",
                                   incoming_x=args.incoming_x, include_raw=True)
            fresh = fresh_process_future(raw.outer_state) == actual.future
        rows.append({"callback": f"{target:06X}", "provenance": "constructed original-ROM dispatcher fixture",
                     "free": free, "incoming_x": args.incoming_x,
                     "equal_outer": actual.outer == expected.outer,
                     "equal_future": actual.future == expected.future, "fresh_process_150": fresh,
                     "stats": actual.stats})
    if args.walker_directory is not None:
        rows.extend(recorded_walker_rows(args.walker_directory, row=args.row))
    if args.setup_directory is not None:
        rows.extend(recorded_setup_rows(args.setup_directory))
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
