"""Exact Aladdin entry/seam effects over live RAM; semantic bodies are in recovered.

Only admitted RAM spans may collapse internal writes to final residue.
"""
from __future__ import annotations
from dataclasses import dataclass
from . import recovered as game


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
TRANSITION_ENTRY = 0x1AF468
SOUND_RETURN = 0x1AF498
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

def _clear_objects(machine, registers, *, sp, pair=False, extra_spans=()):
    """One RAM-domain adapter: aggregate cost and final residue, no helper plans."""
    record, a6, d0 = (registers[name] for name in ("a1", "a6", "d0"))
    read = lambda address, size: _read(machine, address, size)
    if sp & 1:
        raise UnsupportedCandidate("unaligned guest stack")
    linked = read(record + 62, 4) if pair else 0
    depth = (14 if linked else 10) if pair else 6
    spans = [("current record", record, 66 if pair else 50),
             ("object stack", sp - depth, depth + 4), *extra_spans]
    if linked:
        spans.append(("linked record", linked, 50))
    lengths = []
    for item in ((record, linked) if linked else (record,)):
        pointer = read(item + 42, 4)
        length = read(item + 41, 1) + 1 if pointer else 0
        lengths.append(length)
        if pointer:
            spans.append(("object buffer", pointer, length))
    _spans_disjoint(spans)
    if pair:
        slots = ([(sp - 4, record, 4), (sp - 8, 0x1ABE86, 4),
                  (sp - 12, a6, 4), (sp - 14, d0, 2)] if linked else
                 [(sp - 4, 0x1ABE74, 4), (sp - 8, a6, 4), (sp - 10, d0, 2)])
        cycles, instructions = (332, 26) if linked else (168, 13)
        semantic = game.clear_pair(read, record)
    else:
        slots = [(sp - 4, a6, 4), (sp - 6, d0, 2)]
        cycles, instructions = 96, 8
        semantic = game.release_buffer(read, record)
    writes = [byte for address, value, size in slots for byte in _bytes(address, value, size)]
    cycles += sum(82 + 22 * length for length in lengths if length)
    instructions += sum(5 + 2 * length for length in lengths if length)
    return cycles, instructions, (*writes, *semantic), linked

def clear_auxiliary_buffer(machine, registers: dict[str, int]) -> AtomicPlan:
    sp, d0, sr = (registers[name] for name in ("a7", "d0", "sr"))
    return_pc = _read(machine, sp, 4)
    cycles, instructions, writes, _ = _clear_objects(machine, registers, sp=sp)
    return AtomicPlan(cycles, instructions, writes,
                      {"d0": d0, "pc": return_pc & 0xFFFFFF, "a7": sp + 4, "sr": _logic_sr(sr, d0, 2)},
                      LEAF_LAST_PC)


def clear_object_pair(machine, registers: dict[str, int]) -> AtomicPlan:
    """Exact external 1ABE6E boundary; internal callers need no pair plan."""
    sp, sr, d0 = (registers[name] for name in ("a7", "sr", "d0"))
    return_pc = _read(machine, sp, 4)
    cycles, instructions, writes, linked = _clear_objects(machine, registers, sp=sp, pair=True)
    return AtomicPlan(cycles, instructions, writes,
                      {"a1": registers["a1"], "d0": d0, "a7": sp + 4, "pc": return_pc & 0xFFFFFF,
                       "sr": _logic_sr(sr, d0, 2) if linked else _logic_sr(sr, 0, 4)},
                      PAIR_LAST_PC, direct_calls=1 + bool(linked))


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
    return tuple(game.initialize(record, data))


def initialize_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """1AE30A: initialize selected A5 record fields from the template at A6."""
    a5, a6, a7, sr = (registers[key] for key in ("a5", "a6", "a7", "sr"))
    return_pc = _read(machine, a7, 4)
    writes = _initialize_object_effects(machine, record=a5, template=a6, entry_sp=a7)
    return AtomicPlan(476, 27, writes,
                      {"a6": a6 + 19, "a7": a7 + 4, "pc": return_pc & 0xFFFFFF,
                       "sr": _logic_sr(sr, 0, 4)}, INIT_LAST_PC)


def finish_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """1AE954: accumulate, clear the pair, and install template 1B7940."""
    a1, a6, sp, d0, d7, sr = (registers[key] for key in ("a1", "a6", "a7", "d0", "d7", "sr"))
    return_pc = _read(machine, sp, 4)
    value = _read(machine, a1 + 8, 1)
    total = _read(machine, 0xFFF14E, 2) + value
    carry_sr = (sr & ~0x10) | (0x10 if total > 0xFFFF else 0)
    cycles, instructions, writes, linked = _clear_objects(machine, registers, sp=sp - 4, pair=True,
        extra_spans=(("outer return", sp, 4), ("object total", 0xFFF14E, 2)))
    initialized = _initialize_object_effects(machine, record=a1, template=0x1B7940, entry_sp=sp - 4)
    # The repeated buffer clear sees a null pointer. Only its final stack
    # residue survives; no second semantic clear or saved-register bridge.
    writes = (*writes, *_bytes(0xFFF14E, total, 2), *_bytes(sp - 8, a6, 4),
              *_bytes(sp - 10, d0, 2), *_bytes(sp - 4, 0x1AE976, 4), *initialized)
    return AtomicPlan(706 + cycles, 45 + instructions, tuple(dict(writes).items()),
                      {"d7": (d7 & 0xFFFF0000) | value, "a5": a1, "a6": 0x1B7953,
                       "a7": sp + 4, "pc": return_pc & 0xFFFFFF, "sr": _logic_sr(carry_sr, 0, 4)},
                      FINISH_LAST_PC, direct_calls=3 + bool(linked))


def replace_object(machine, registers: dict[str, int], *, increment_total=False, extra_spans=()) -> AtomicPlan:
    """1AF4C6 replacement boundary, optionally including the 1AF4C2 +15 call."""
    a1, sp, sr = (registers[key] for key in ("a1", "a7", "sr"))
    return_pc = _read(machine, sp, 4)
    spans = [("outer return", sp, 4), *extra_spans]
    writes = []
    if increment_total:
        total = _read(machine, 0xFFF14E, 2) + 15
        sr = (sr & ~0x10) | (0x10 if total > 0xFFFF else 0)
        spans.append(("object total", 0xFFF14E, 2))
        writes.extend(_bytes(0xFFF14E, total, 2))
    cycles, instructions, cleared, linked = _clear_objects(machine, registers, sp=sp - 4,
                                                          pair=True, extra_spans=spans)
    initialized = _initialize_object_effects(machine, record=a1, template=0x1B7ABC, entry_sp=sp - 4)
    writes.extend((*cleared, *_bytes(sp - 4, 0x1AF4D6, 4), *initialized))
    return AtomicPlan(544 + cycles + 58 * increment_total, 32 + instructions + 3 * increment_total,
                      tuple(dict(writes).items()),
                      {"a5": a1, "a6": 0x1B7ACF, "a7": sp + 4,
                       "pc": return_pc & 0xFFFFFF, "sr": _logic_sr(sr, 0, 4)},
                      REPLACE_LAST_PC, direct_calls=3 + bool(linked) + int(increment_total))


def increment_decimal_counter(machine):
    digits = _read(machine, 0xFFEFE0, 2)
    try:
        writes = game.increment_counter(digits)
    except ValueError as error:
        raise UnsupportedCandidate(str(error)) from error
    return writes, 132 if digits & 255 == 0x39 else 94, 8 if digits & 255 == 0x39 else 6


def begin_object_transition(machine, registers: dict[str, int]) -> tuple[AtomicPlan, bool]:
    """Increment the displayed decimal counter, optionally play sound 11, then replace.

    The boolean requests the original sound request/flush operation. The two
    adjacent legacy calls share one guest save frame and one Python resume.
    """
    sp, sr = registers["a7"], registers["sr"]
    writes, counter_cycles, counter_instructions = increment_decimal_counter(machine)
    sound = _read(machine, 0xFFF57D, 1)
    _read(machine, sp, 4)
    _spans_disjoint([("sound stack", sp - 28, 32), ("decimal counter", 0xFFEFE0, 2),
                     ("sound flag", 0xFFF57D, 1)])
    sr = _logic_sr(sr & ~0x10, sound, 1)  # ASCII ADDQ clears X; TST supplies NZVC.
    if not sound:
        tail = replace_object(machine, {**registers, "sr": sr},
                              extra_spans=(("decimal counter", 0xFFEFE0, 2),))
        return AtomicPlan(84 + counter_cycles + tail.cycles, 6 + counter_instructions + tail.instructions,
                          (*writes, *tail.writes), tail.registers, tail.last_pc,
                          direct_calls=2 + tail.direct_calls), False
    # MOVEM.L D0/D1/A0/A1/A6,-(SP), PEA 11, JSR 1E58B8.
    # The earlier counter-call return slot is overwritten by MOVEM: no need
    # to reconstruct that intermediate frame or the transient ASCII ':'.
    for index, name in enumerate(("a6", "a1", "a0", "d1", "d0"), 1):
        writes.extend(_bytes(sp - index * 4, registers[name], 4))
    writes.extend(_bytes(sp - 24, 11, 4))
    writes.extend(_bytes(sp - 28, 0x1AF492, 4))
    return AtomicPlan(156 + counter_cycles, 8 + counter_instructions, tuple(writes),
                      {"a7": sp - 28, "pc": 0x1E58B8, "sr": sr}, 0x1AF48C,
                      direct_calls=1), True


def finish_object_transition(machine, registers: dict[str, int]) -> AtomicPlan:
    """Resume after original sound request/flush, restore its frame, and replace."""
    sp = registers["a7"] + 24
    restored = dict(registers, a7=sp)
    for index, name in enumerate(("a6", "a1", "a0", "d1", "d0"), 1):
        restored[name] = _read(machine, sp - index * 4, 4)
    tail = replace_object(machine, restored)
    # ADDQ SP, MOVEM restoration and BRA are absorbed into the owned suffix.
    final = {name: restored[name] for name in ("d0", "d1", "a0", "a1")}
    final.update(tail.registers)
    return AtomicPlan(70 + tail.cycles, 3 + tail.instructions, tail.writes, final,
                      tail.last_pc, direct_calls=1 + tail.direct_calls)


def detach_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """1AD0FC: script detach and exact overridden-return boundary."""
    a0, a1, a2, sp, d0, sr = (registers[key] for key in ("a0", "a1", "a2", "a7", "d0", "sr"))
    source, source_is_ram = _read_source_byte(machine, a2 + 1)
    use_pair = bool(source or (_read(machine, a1 + 60, 1) & 0x04))
    _read(machine, sp, 4)
    return_override = _read(machine, 0xFF7D9E, 4)
    d0 = (d0 & 0xFFFFFF00) | source
    spans = [("outer return", sp, 4), ("return override", 0xFF7D9E, 4)]
    if source_is_ram:
        spans.append(("script byte", a2 + 1, 1))
    if not use_pair:
        # The leaf sees 50 bytes; this caller additionally reads the link/flag.
        spans.append(("caller record extension", a1 + 50, 16))
        linked = _read(machine, a1 + 62, 4)
        if linked:
            spans.append(("linked flags", linked + 60, 6))
    cycles, instructions, writes, _ = _clear_objects(machine, dict(registers, d0=d0),
                                                    sp=sp - 4, pair=use_pair, extra_spans=spans)
    if use_pair:
        before_cycles, before_instructions = (46, 4) if source else (70, 6)
        cycles, instructions = cycles + before_cycles + 54, instructions + before_instructions + 3
        writes = (*_bytes(sp - 4, 0x1AD108, 4), *writes)
        direct_calls = 2 + bool(_read(machine, a1 + 62, 4))
    else:
        cycles += 80 + (152 if linked else 70)
        instructions += 7 + (9 if linked else 4)
        writes = ((a1, 0), *_bytes(sp - 4, a0 if linked else 0x1AD118, 4), *writes,
                  *game.unlink(lambda address, size: _read(machine, address, size), linked))
        direct_calls = 2  # buffer release and semantic unlink (including its null case)
    return AtomicPlan(cycles, instructions, (*writes, *_bytes(sp, return_override, 4)),
                      {"d0": d0, "a2": a2 + 2, "a7": sp + 4,
                       "pc": return_override & 0xFFFFFF, "sr": _logic_sr(sr, return_override, 4)},
                      CALLER_LAST_PC, direct_calls=direct_calls)
