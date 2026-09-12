"""Editable Aladdin game behavior over live machine storage.

No registration, oracle, mutant, replay or backend-framework policy belongs here.
Effects are staged until the machine admits their bounded atomic span.
"""
from __future__ import annotations
from dataclasses import dataclass


LEAF_ENTRY = 0x1AE372
LEAF_LAST_PC = 0x1AE39E
CALLER_ENTRY = 0x1AD0FC
CALLER_LAST_PC = 0x1AD136
ROM_SHA256 = "a3779fc77994780e80d05bb557f800110d0398d34b951baa8c0a14910014ded3"


class UnsupportedCandidate(RuntimeError):
    """The current stopped machine is outside this small candidate domain."""


@dataclass(frozen=True)
class AtomicPlan:
    cycles: int
    instructions: int
    writes: tuple[tuple[int, int], ...]
    registers: dict[str, int]
    last_pc: int


def _logic_sr(sr: int, value: int, width: int) -> int:
    """68000 MOVE/CLR logic flags, preserving X and the non-CCR bits."""
    mask = (1 << (width * 8)) - 1
    value &= mask
    out = sr & ~0x0F  # X is bit 4 and is deliberately retained.
    if value == 0:
        out |= 0x04
    if value & (1 << (width * 8 - 1)):
        out |= 0x08
    return out


class LegacyExit(UnsupportedCandidate):
    """Unrecovered dependency: dispatch original from the unchanged entry."""
    def __init__(self, target, reason):
        self.target = target
        super().__init__(f"{reason}: legacy call {target:06X}")


def _address(value: int, size: int) -> int:
    if type(value) is not int or type(size) is not int or size <= 0:
        raise UnsupportedCandidate("invalid candidate address span")
    if not 0xFF0000 <= value <= 0xFFFFFF or value + size - 1 > 0xFFFFFF:
        raise UnsupportedCandidate("candidate touches noncanonical work RAM")
    return value

def _spans_disjoint(spans: list[tuple[str, int, int]]) -> None:
    checked = [(name, _address(start, size), size) for name, start, size in spans]
    for index, (name, start, size) in enumerate(checked):
        for other_name, other_start, other_size in checked[index + 1:]:
            if start < other_start + other_size and other_start < start + size:
                raise UnsupportedCandidate(f"candidate aliases {name} and {other_name}")

def _bytes(address: int, value: int, size: int) -> tuple[tuple[int, int], ...]:
    return tuple((address + index, (value >> (8 * (size - index - 1))) & 0xFF)
                 for index in range(size))

def _read(machine, address: int, size: int) -> int:
    address = _address(address, size)
    return int.from_bytes(machine.peek_ram(address & 0xFFFF, size), "big")

def _read_source_byte(machine, address: int) -> tuple[int, bool]:
    """Read caller script input from immutable ROM or guarded work RAM."""
    if type(address) is not int:
        raise UnsupportedCandidate("invalid script source address")
    if 0 <= address <= 0x3fffff:
        try:
            return machine.peek_rom(address, 1)[0], False
        except ValueError as error:
            raise UnsupportedCandidate("script source lies beyond the cartridge") from error
    if 0xff0000 <= address <= 0xffffff:
        return _read(machine, address, 1), True
    raise UnsupportedCandidate("script source is neither immutable ROM nor work RAM")

def _clear_buffer_effects(machine, registers: dict[str, int], *, entry_sp: int) -> tuple[int, int, tuple[tuple[int, int], ...], int]:
    """Return cycle/instruction/write/return-PC facts for 1AE372.

    ``entry_sp`` is the A7 value visible to the leaf.  It may be the
    caller's freshly pushed BSR frame rather than the outer activation's
    original A7.
    """
    a1, a6, d0 = registers["a1"], registers["a6"], registers["d0"]
    count_address, pointer_address = _address(a1 + 41, 1), _address(a1 + 42, 4)
    count = _read(machine, count_address, 1)
    pointer = _read(machine, pointer_address, 4)
    stack_base = _address(entry_sp - 6, 10)
    if pointer:
        length = count + 1
        _spans_disjoint([
            ("record", a1, 50), ("buffer", pointer, length), ("leaf stack", stack_base, 10),
        ])
    else:
        length = 0
        _spans_disjoint([("record", a1, 50), ("leaf stack", stack_base, 10)])
    writes = list(_bytes(entry_sp - 4, a6, 4))
    writes.extend(_bytes(entry_sp - 6, d0, 2))
    if pointer:
        writes.extend(_bytes(a1 + 42, 0, 4))
        writes.extend(_bytes(a1 + 46, 0, 4))
        writes.extend(_bytes(a1 + 41, 0, 1))
        writes.extend((pointer + offset, 0) for offset in range(length))
        return 178 + 22 * length, 13 + 2 * length, tuple(writes), pointer
    return 96, 8, tuple(writes), pointer

def clear_auxiliary_buffer(machine, registers: dict[str, int]) -> AtomicPlan:
    a7, d0, sr = registers["a7"], registers["d0"], registers["sr"]
    _address(a7, 4)
    cycles, instructions, writes, _ = _clear_buffer_effects(machine, registers, entry_sp=a7)
    return_pc = _read(machine, a7, 4)
    return AtomicPlan(
        cycles=cycles,
        instructions=instructions,
        writes=writes,
        registers={"d0": d0, "pc": return_pc, "a7": a7 + 4, "sr": _logic_sr(sr, d0, 2)},
        last_pc=LEAF_LAST_PC,
    )

def detach_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """The observed direct 1AD0FC -> 1AE372 path, with a direct Python call."""
    a0, a1, a2, a7, d0, sr = (registers[key] for key in ("a0", "a1", "a2", "a7", "d0", "sr"))
    source_address = a2 + 1
    source_byte, source_is_ram = _read_source_byte(machine, source_address)
    if source_byte:
        raise LegacyExit(0x1ABE6E, "nonzero script path")
    if _read(machine, _address(a1 + 60, 1), 1) & 0x04:
        raise LegacyExit(0x1ABE6E, "bit-two script path")
    outer_return = _read(machine, _address(a7, 4), 4)
    return_override = _read(machine, 0xFF7D9E, 4)
    leaf_registers = dict(registers)
    leaf_registers["d0"] = (d0 & 0xFFFFFF00) | source_byte
    leaf_cycles, leaf_instructions, leaf_writes, buffer = _clear_buffer_effects(
        machine, leaf_registers, entry_sp=a7 - 4)
    count = _read(machine, _address(a1 + 41, 1), 1)
    link = _read(machine, _address(a1 + 62, 4), 4)
    spans = [
        ("caller record", a1, 66), ("leaf stack and outer return", a7 - 10, 14),
        ("return override", 0xFF7D9E, 4),
    ]
    if source_is_ram:
        spans.append(("script byte", source_address, 1))
    if link:
        spans.append(("linked record", link + 60, 6))
    if buffer:
        spans.append(("leaf buffer", buffer, count + 1))
    _spans_disjoint(spans)
    writes = [(a1, 0)]
    writes.extend(_bytes(a7 - 4, 0x1AD118, 4))
    writes.extend(leaf_writes)
    if link:
        linked_flag = _read(machine, link + 60, 1)
        writes.extend(_bytes(a7 - 4, a0, 4))
        writes.extend(_bytes(link + 62, 0, 4))
        writes.append((link + 60, linked_flag & ~0x04))
        post_cycles, post_instructions = 152, 9
    else:
        post_cycles, post_instructions = 70, 4
    writes.extend(_bytes(a7, return_override, 4))
    # Keep the read visible in the plan: an odd/unmapped stack pointer is
    # rejected above, but the source return is intentionally overwritten.
    del outer_return
    return AtomicPlan(
        cycles=80 + leaf_cycles + post_cycles,
        instructions=7 + leaf_instructions + post_instructions,
        writes=tuple(writes),
        registers={
            "d0": leaf_registers["d0"], "a2": a2 + 2,
            "a7": a7 + 4, "pc": return_override,
            "sr": _logic_sr(sr, return_override, 4),
        },
        last_pc=CALLER_LAST_PC,
    )
