"""Editable Aladdin game behavior over live machine storage.

No registration, oracle, mutant, replay or backend-framework policy belongs here.
Effects are staged until the machine admits their bounded atomic span.
"""
from __future__ import annotations
from dataclasses import dataclass


LEAF_ENTRY = 0x1AE372
LEAF_LAST_PC = 0x1AE39E
PAIR_ENTRY = 0x1ABE6E
PAIR_LAST_PC = 0x1ABE88
CALLER_ENTRY = 0x1AD0FC
CALLER_LAST_PC = 0x1AD136
INIT_ENTRY = 0x1AE30A
INIT_LAST_PC = 0x1AE370
FINISH_ENTRY = 0x1AE954
FINISH_LAST_PC = 0x1AE976
COUNTED_REPLACE_ENTRY = 0x1AF4C2
REPLACE_ENTRY = 0x1AF4C6
REPLACE_LAST_PC = 0x1AF4D6
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
    direct_calls: int = 0


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
    if size > 1 and address & 1:
        raise UnsupportedCandidate("unaligned word/long operand")
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
    """Return cycle/instruction/write/buffer-pointer facts for 1AE372.

    ``entry_sp`` is the A7 value visible to the leaf.  It may be the
    caller's freshly pushed BSR frame rather than the outer activation's
    original A7.
    """
    a1, a6, d0 = registers["a1"], registers["a6"], registers["d0"]
    if entry_sp & 1:
        raise UnsupportedCandidate("unaligned guest stack")
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
        registers={"d0": d0, "pc": return_pc & 0xFFFFFF, "a7": a7 + 4, "sr": _logic_sr(sr, d0, 2)},
        last_pc=LEAF_LAST_PC,
    )

def _clear_pair_effects(machine, registers, *, entry_sp, return_pc, extra_spans=()) -> AtomicPlan:
    """Clear the current and optional linked object, including both BSR frames."""
    a1, d0, sr = (registers[key] for key in ("a1", "d0", "sr"))
    link = _read(machine, a1 + 62, 4)
    spans = [("current record", a1, 66),
             ("pair stack", entry_sp - (14 if link else 10), 18 if link else 14), *extra_spans]
    first_cycles, first_instructions, first_writes, buffer = _clear_buffer_effects(
        machine, registers, entry_sp=entry_sp - 4)
    if buffer:
        spans.append(("current buffer", buffer, _read(machine, a1 + 41, 1) + 1))
    writes = [(a1, 0), *_bytes(entry_sp - 4, 0x1ABE74, 4), *first_writes]
    if link:
        linked_registers = {**registers, "a1": link}
        second_cycles, second_instructions, second_writes, linked_buffer = _clear_buffer_effects(
            machine, linked_registers, entry_sp=entry_sp - 8)
        spans.append(("linked record", link, 50))
        if linked_buffer:
            spans.append(("linked buffer", linked_buffer, _read(machine, link + 41, 1) + 1))
        writes.extend(_bytes(entry_sp - 4, a1, 4))
        writes.append((link, 0))
        writes.extend(_bytes(entry_sp - 8, 0x1ABE86, 4))
        writes.extend(second_writes)
        cycles, instructions = 140 + first_cycles + second_cycles, 10 + first_instructions + second_instructions
        final_sr = _logic_sr(sr, d0, 2)
    else:
        cycles, instructions = 72 + first_cycles, 5 + first_instructions
        final_sr = _logic_sr(sr, 0, 4)  # TST.L of the null link survives RTS.
    _spans_disjoint(spans)
    return AtomicPlan(cycles, instructions, tuple(writes),
                      {"a1": a1, "d0": d0, "a7": entry_sp + 4,
                       "pc": return_pc & 0xFFFFFF, "sr": final_sr},
                      PAIR_LAST_PC, direct_calls=1 + bool(link))


def clear_object_pair(machine, registers: dict[str, int]) -> AtomicPlan:
    """1ABE6E: deactivate one or two objects and release their auxiliary buffers."""
    a7 = registers["a7"]
    return _clear_pair_effects(machine, registers, entry_sp=a7, return_pc=_read(machine, a7, 4))


def _initialize_object_effects(machine, *, record, template, entry_sp):
    """Expand the 19-byte object template into selected fields of a 66-byte record."""
    if (record | template | entry_sp) & 1:
        raise UnsupportedCandidate("unaligned object template, record or stack")
    spans = [("initialized record", record, 66), ("initializer return", entry_sp, 4)]
    if 0 <= template <= 0x3FFFFF:
        try:
            data = machine.peek_rom(template, 19)
        except ValueError as error:
            raise UnsupportedCandidate("object template lies beyond the cartridge") from error
    elif 0xFF0000 <= template <= 0xFFFFFF:
        spans.append(("object template", template, 19))
        _address(template, 19)
        data = machine.peek_ram(template & 0xFFFF, 19)
    else:
        raise UnsupportedCandidate("object template is neither immutable ROM nor work RAM")
    _spans_disjoint(spans)
    writes = [(record + offset, data[index]) for index, offset in enumerate((0, 1, 6, 7, 8, 9))]
    writes.extend((record + 10 + index, value) for index, value in enumerate(data[6:10]))
    for offset, size in ((19, 1), (20, 4), (24, 2), (26, 2), (28, 1), (29, 1)):
        writes.extend(_bytes(record + offset, 0, size))
    writes.extend((record + 30 + index, value) for index, value in enumerate(data[10:16]))
    writes.append((record + 41, data[16]))
    for offset, size in ((42, 4), (46, 4), (50, 2), (52, 1)):
        writes.extend(_bytes(record + offset, 0, size))
    writes.extend(((record + 53, data[17]), (record + 54, 0), (record + 55, 0),
                   (record + 60, data[18]), (record + 61, 0)))
    writes.extend(_bytes(record + 62, 0, 4))
    return tuple(writes)


def initialize_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """1AE30A: initialize selected A5 record fields from the template at A6."""
    a5, a6, a7, sr = (registers[key] for key in ("a5", "a6", "a7", "sr"))
    return_pc = _read(machine, a7, 4)
    writes = _initialize_object_effects(machine, record=a5, template=a6, entry_sp=a7)
    return AtomicPlan(476, 27, writes,
                      {"a6": a6 + 19, "a7": a7 + 4, "pc": return_pc & 0xFFFFFF,
                       "sr": _logic_sr(sr, 0, 4)}, INIT_LAST_PC)


def finish_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """1AE954: accumulate the object's byte value, clear it, and install template 1B7940."""
    a1, a6, a7, d0, d7, sr = (registers[key] for key in ("a1", "a6", "a7", "d0", "d7", "sr"))
    return_pc = _read(machine, a7, 4)
    value = _read(machine, a1 + 8, 1)
    total = _read(machine, 0xFFF14E, 2) + value
    # ADD.W sets X as well as NZVC. Subsequent logic instructions retain X.
    carry_sr = (sr & ~0x10) | (0x10 if total > 0xFFFF else 0)
    pair = _clear_pair_effects(machine, {**registers, "sr": carry_sr},
                               entry_sp=a7 - 4, return_pc=0x1AE964,
                               extra_spans=(("outer return", a7, 4), ("object total", 0xFFF14E, 2)))
    initialized = _initialize_object_effects(machine, record=a1, template=0x1B7940, entry_sp=a7 - 4)
    writes = [*_bytes(0xFFF14E, total, 2), *_bytes(a7 - 4, 0x1AE964, 4), *pair.writes]
    # The pair has cleared the current buffer pointer. The repeated leaf is
    # therefore its null path: retain its BSR and saved A6/D0 stack writes,
    # without reading the old pointer from the still-unmodified live machine.
    writes.extend(((a1, 0), *_bytes(a7 - 4, 0x1AE96A, 4),
                   *_bytes(a7 - 8, a6, 4), *_bytes(a7 - 10, d0, 2)))
    writes.extend(_bytes(a7 - 4, 0x1AE976, 4))
    writes.extend(initialized)
    return AtomicPlan(706 + pair.cycles, 45 + pair.instructions, tuple(writes),
                      {"d7": (d7 & 0xFFFF0000) | value, "a5": a1, "a6": 0x1B7953,
                       "a7": a7 + 4, "pc": return_pc & 0xFFFFFF, "sr": _logic_sr(carry_sr, 0, 4)},
                      FINISH_LAST_PC, direct_calls=3 + pair.direct_calls)


def replace_object(machine, registers: dict[str, int], *, increment_total=False) -> AtomicPlan:
    """1AF4C6 cleanup/template tail, optionally including the 1AF4C2 +15 call."""
    a1, a7, sr = (registers[key] for key in ("a1", "a7", "sr"))
    return_pc = _read(machine, a7, 4)
    spans = [("outer return", a7, 4)]
    writes = []
    if increment_total:
        total = _read(machine, 0xFFF14E, 2) + 15
        # ADDI.W's X survives both the pair clear and initialization.
        sr = (sr & ~0x10) | (0x10 if total > 0xFFFF else 0)
        spans.append(("object total", 0xFFF14E, 2))
        writes.extend(_bytes(a7 - 4, 0x1AF4C6, 4))
        writes.extend(_bytes(0xFFF14E, total, 2))
    pair = _clear_pair_effects(machine, {**registers, "sr": sr}, entry_sp=a7 - 4,
                               return_pc=0x1AF4CA, extra_spans=spans)
    initialized = _initialize_object_effects(machine, record=a1, template=0x1B7ABC, entry_sp=a7 - 4)
    writes.extend(_bytes(a7 - 4, 0x1AF4CA, 4))
    writes.extend(pair.writes)
    writes.extend(_bytes(a7 - 4, 0x1AF4D6, 4))
    writes.extend(initialized)
    return AtomicPlan(544 + pair.cycles + (58 if increment_total else 0),
                      32 + pair.instructions + (3 if increment_total else 0), tuple(writes),
                      {"a5": a1, "a6": 0x1B7ACF, "a7": a7 + 4,
                       "pc": return_pc & 0xFFFFFF, "sr": _logic_sr(sr, 0, 4)},
                      REPLACE_LAST_PC, direct_calls=2 + pair.direct_calls + int(increment_total))


def detach_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """1AD0FC: consume a script byte, detach objects, and replace the outer return."""
    a0, a1, a2, a7, d0, sr = (registers[key] for key in ("a0", "a1", "a2", "a7", "d0", "sr"))
    source_address = a2 + 1
    source_byte, source_is_ram = _read_source_byte(machine, source_address)
    use_pair = source_byte or (_read(machine, a1 + 60, 1) & 0x04)
    _read(machine, a7, 4)  # Validate the outer return operand, which is overwritten.
    return_override = _read(machine, 0xFF7D9E, 4)
    leaf_registers = dict(registers)
    leaf_registers["d0"] = (d0 & 0xFFFFFF00) | source_byte
    if use_pair:
        extra_spans = [("outer return", a7, 4), ("return override", 0xFF7D9E, 4)]
        if source_is_ram:
            extra_spans.append(("script byte", source_address, 1))
        pair = _clear_pair_effects(machine, leaf_registers, entry_sp=a7 - 4,
                                   return_pc=0x1AD108, extra_spans=extra_spans)
        # Nonzero: ADDQ, MOVE.B, BEQ.W (not taken), BSR.
        # Zero/set bit adds BTST and the taken BNE.S, with BEQ.W taken.
        before_cycles, before_instructions = (46, 4) if source_byte else (70, 6)
        return AtomicPlan(
            before_cycles + pair.cycles + 54, before_instructions + pair.instructions + 3,
            (*_bytes(a7 - 4, 0x1AD108, 4), *pair.writes, *_bytes(a7, return_override, 4)),
            {"d0": leaf_registers["d0"], "a2": a2 + 2, "a7": a7 + 4,
             "pc": return_override & 0xFFFFFF, "sr": _logic_sr(sr, return_override, 4)},
            CALLER_LAST_PC, direct_calls=1 + pair.direct_calls)
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
    return AtomicPlan(
        cycles=80 + leaf_cycles + post_cycles,
        instructions=7 + leaf_instructions + post_instructions,
        writes=tuple(writes),
        registers={
            "d0": leaf_registers["d0"], "a2": a2 + 2,
            "a7": a7 + 4, "pc": return_override & 0xFFFFFF,
            "sr": _logic_sr(sr, return_override, 4),
        },
        last_pc=CALLER_LAST_PC,
        direct_calls=1,
    )
