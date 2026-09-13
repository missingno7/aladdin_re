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
COLLECTION_DISPATCH_ENTRY = 0x1ABC82
COLLECTION_DISPATCH_RETURN = 0x1ABCA0
COLLECTION_DISPATCH_TABLE = 0x1CBE
CONTACT_ENTRY = 0x1AE4F8
CONTACT_DISPATCH_ENTRY = 0x1AE9D4
CONTACT_DISPATCH_LOCAL_RETURN = 0x1AE9D8
CONTACT_SIBLING_WRAPPER = 0x1AE9C6
CONTACT_SIBLING_DIRECT = 0x1AE9DA
CONTACT_SIBLING_ENTRY = 0x1AEC00
CONTACT_SIBLING_RETIREMENT = 0x1AECD8
CONTACT_SIBLING_TAIL = 0x1AED0C
CONTACT_TYPE13_ENTRY = 0x1AF1AC
CONTACT_TYPE13_FIXED_RETURN = 0x1AF1F6
CONTACT_TYPE13_RETURN = 0x1AECEE
SPAWN_REGION_ENTRY = 0x1B524E
SPAWN_REGION_REVERSE_ENTRY = 0x1B5256
SPAWN_REGION_LOWER_ENTRY = 0x1B525E
SPAWN_REGION_UPPER_ENTRY = 0x1B5266
SPAWN_REGION_ENTRIES = (SPAWN_REGION_ENTRY, SPAWN_REGION_REVERSE_ENTRY,
                        SPAWN_REGION_LOWER_ENTRY, SPAWN_REGION_UPPER_ENTRY)
SPAWN_REGION_LAST_PC = 0x1B529E
SPAWN_REVERSE_CALLER_ENTRY = 0x1B6802
SPAWN_REVERSE_CALLER_LAST_PC = 0x1B681A
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


@dataclass(frozen=True)
class SoundSeam:
    """One admitted sound-prefix plan and its measured local return contract.

    Construction binds the concrete suffix with the stack/frame facts for the
    surrounding wrapper, so the runner never infers a route from the prefix's
    final instruction.
    """
    prefix: AtomicPlan
    stack_basis: int
    resume_pc: int
    return_slot: int
    saved_frame: int
    frame_size: int
    return_delta: int
    counts_contact: bool = False
    suffix: object | None = None


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

def _clear_objects(machine, registers, *, sp, pair=False, extra_spans=(), include_semantics=True):
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
        semantic = game.clear_pair(read, record) if include_semantics else ()
    else:
        slots = [(sp - 4, a6, 4), (sp - 6, d0, 2)]
        cycles, instructions = 96, 8
        semantic = game.release_buffer(read, record) if include_semantics else ()
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


def _object_template(machine, *, record, template, entry_sp):
    """Validate the original template/record domain and read its 19 source bytes."""
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
    return data


def _initialize_object_effects(machine, *, record, template, entry_sp):
    return tuple(game.initialize(record, _object_template(machine, record=record,
                                                         template=template, entry_sp=entry_sp)))


def initialize_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """1AE30A: initialize selected A5 record fields from the template at A6."""
    a5, a6, a7, sr = (registers[key] for key in ("a5", "a6", "a7", "sr"))
    return_pc = _read(machine, a7, 4)
    writes = _initialize_object_effects(machine, record=a5, template=a6, entry_sp=a7)
    return AtomicPlan(476, 27, writes,
                      {"a6": a6 + 19, "a7": a7 + 4, "pc": return_pc & 0xFFFFFF,
                       "sr": _logic_sr(sr, 0, 4)}, INIT_LAST_PC)


# Four adjacent entry arms select traversals of overlapping object-pool ranges
# then join at 1B526C.  The old 1AFD12 label was an interior address of an
# unrelated instruction; 1B5266 actually calls the measured 1AE262 selector.
_SPAWN_REGION_ARMS = {
    SPAWN_REGION_ENTRY: (0xFF7E82, 24, 1, 0xFF84B2, 680, 42, 44, 3, 0x1B5252),
    SPAWN_REGION_REVERSE_ENTRY: (0xFF8470, 24, -1, 0xFF7E40, 680, 42, 44, 3, 0x1B525A),
    SPAWN_REGION_LOWER_ENTRY: (0xFF8368, 20, -1, 0xFF7E40, 680, 42, 44, 3, 0x1B5262),
    SPAWN_REGION_UPPER_ENTRY: (0xFF7F06, 20, 1, 0xFF842E, 670, 41, 44, 3, 0x1B526A),
}
SPAWN_REGION_GLOBALS = (
    ('spawn position x', 0xFFF150, 2), ('spawn position x offset', 0xFF7DB0, 2),
    ('spawn position y', 0xFFF152, 2), ('spawn position y offset', 0xFF7DB2, 2),
)


def _signed_word(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def spawn_region(machine, registers: dict[str, int], entry: int) -> AtomicPlan:
    """Recover one allocation-backed ``1B524E..1B529E`` entry arm.

    All four observed allocation arms share the initializer and coordinate
    tail.  The selected pool remains live RAM; only the final residue is
    staged after the full pool, frame, template, globals, and indexed-clear
    spans are proved disjoint.
    """
    if entry not in _SPAWN_REGION_ARMS:
        raise UnsupportedCandidate('unknown spawn region entry')
    a2, a6, sp, d0, d2, d3, sr = (registers[name] for name in
                                  ('a2', 'a6', 'a7', 'd0', 'd2', 'd3', 'sr'))
    if sp & 1:
        raise UnsupportedCandidate('unaligned spawn region stack')
    base, count, direction, exhausted, free_fixed_cycles, free_fixed_instructions, \
        exhausted_fixed_cycles, exhausted_fixed_instructions, selector_return = _SPAWN_REGION_ARMS[entry]
    clear_address = (a2 + _signed_word(d2)) & 0xFFFFFF
    _address(clear_address, 1)
    spans = [('spawn allocator pool', 0xFF7E82, 24 * 66),
             ('spawn region frame', sp - 4, 8), ('spawn indexed clear', clear_address, 1),
             *SPAWN_REGION_GLOBALS]
    if 0xFF0000 <= a6 <= 0xFFFFFF:
        spans.append(('spawn template', a6, 19))
    _spans_disjoint(spans)
    return_pc = _read(machine, sp, 4)
    read = lambda address, size: _read(machine, address, size)
    addresses = tuple(base + direction * 66 * index for index in range(count))
    destination, index = (game.free_object(read, base, count) if direction > 0 else
                          game.free_object_reverse(read, base, count))
    if destination is None:
        selected_type = read(addresses[-1], 1)
        scan_cycles, scan_instructions = ((1000, 99) if count == 24 else (840, 83))
        return AtomicPlan(scan_cycles + exhausted_fixed_cycles,
                          scan_instructions + exhausted_fixed_instructions,
                          _bytes(sp - 4, selector_return, 4),
                          {**registers, 'd0': (d0 & 0xFFFF0000) | 0xFFFF,
                           'a5': exhausted, 'a7': sp + 4, 'pc': return_pc & 0xFFFFFF,
                           'sr': _logic_sr(sr, selected_type, 1)},
                          SPAWN_REGION_LAST_PC,
                          direct_calls=1)
    template = _object_template(machine, record=destination, template=a6, entry_sp=sp - 4)
    # The full shared pool was guarded above; this exact selection is only for
    # the initializer's template/record contract and the semantic writes.
    x = (read(0xFFF150, 2) + read(0xFF7DB0, 2)) & 0xFFFF
    y = (read(0xFFF152, 2) + read(0xFF7DB2, 2)) & 0xFFFF
    writes = (*_bytes(sp - 4, 0x1B5270, 4),
              *game.spawn_region(destination, template, d2, d3, x, y, clear_address))
    scan_cycles, scan_instructions = 54 + 40 * index, 5 + 4 * index
    return AtomicPlan(scan_cycles + free_fixed_cycles, scan_instructions + free_fixed_instructions,
                      tuple(dict(writes).items()),
                      {**registers, 'd0': (d0 & 0xFFFF0000) | (y & 0xFF00),
                       'a5': destination, 'a6': a6 + 19, 'a7': sp + 4,
                       'pc': return_pc & 0xFFFFFF, 'sr': _logic_sr(sr, 0, 1)},
                      SPAWN_REGION_LAST_PC, direct_calls=2)


def _sub_sr(sr, left, right, width):
    """68000 SUBI status residue, including its X/C borrow result."""
    mask, sign = (1 << (8 * width)) - 1, 1 << (8 * width - 1)
    left &= mask; right &= mask
    result = (left - right) & mask
    out = _logic_sr(sr & ~0x1F, result, width)
    if left < right:
        out |= 0x11
    if ((left ^ right) & (left ^ result) & sign):
        out |= 2
    return out


def spawn_reverse_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover recorded 1B6802's B5256 creation and successful-slot correction."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned reverse spawn caller stack')
    _spans_disjoint([('reverse spawn caller pool', 0xFF7E82, 24 * 66),
                     ('reverse spawn caller frame', sp - 8, 12),
                     *SPAWN_REGION_GLOBALS])
    outer_return = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, 0x1B680C, 4),
                        {**registers, 'a6': 0x1B7D8C, 'a7': sp - 4,
                         'pc': SPAWN_REGION_REVERSE_ENTRY},
                        0x1B6808, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_REVERSE_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (selected.registers['sr'] & 0x04):
        # BNE 1B681A then RTS: the allocator left Z clear and no slot exists.
        final.update(a7=sp + 4, pc=outer_return & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2,
                          writes, final, SPAWN_REVERSE_CALLER_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    planned = dispatch_plan_view(machine, AtomicPlan(prefix.cycles + selected.cycles,
                                                      prefix.instructions + selected.instructions,
                                                      writes, final, selected.last_pc,
                                                      prefix.direct_calls + selected.direct_calls))
    record = selected.registers['a5']
    read = lambda address, size: _read(planned, address, size)
    correction = tuple(game.finish_reverse_spawn(read, record))
    y = read(record + 4, 2)
    final.update(a7=sp + 4, pc=outer_return & 0xFFFFFF,
                 sr=_sub_sr(selected.registers['sr'], y, 1, 2))
    return AtomicPlan(prefix.cycles + selected.cycles + 64,
                      prefix.instructions + selected.instructions + 4,
                      tuple(dict((*writes, *correction)).items()), final,
                      SPAWN_REVERSE_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)

def _finish_object_plan(machine, registers, *, static_cycles, static_instructions,
                        return_site, last_pc, extra_writes=(), extra_spans=(),
                        accumulate=True, final_d7=None):
    """Build the shared pair-release/template-install tail without a new seam."""
    a1, a6, sp, d0, d7, sr = (registers[key] for key in ("a1", "a6", "a7", "d0", "d7", "sr"))
    return_pc = _read(machine, sp, 4)
    value = _read(machine, a1 + 8, 1) if accumulate else None
    total = _read(machine, 0xFFF14E, 2) + value if accumulate else None
    carry_sr = ((sr & ~0x10) | (0x10 if total > 0xFFFF else 0)) if accumulate else sr
    spans = (("object total", 0xFFF14E, 2),) if accumulate else ()
    cycles, instructions, writes, linked = _clear_objects(machine, registers, sp=sp - 4, pair=True,
        extra_spans=(("outer return", sp, 4), *spans, *extra_spans))
    initialized = _initialize_object_effects(machine, record=a1, template=0x1B7940, entry_sp=sp - 4)
    # The repeated buffer clear sees a null pointer. Only its final stack
    # residue survives; no second semantic clear or saved-register bridge.
    accumulated = _bytes(0xFFF14E, total, 2) if accumulate else ()
    writes = (*writes, *accumulated, *_bytes(sp - 8, a6, 4),
              *_bytes(sp - 10, d0, 2), *_bytes(sp - 4, return_site, 4), *extra_writes, *initialized)
    return AtomicPlan(static_cycles + cycles, static_instructions + instructions, tuple(dict(writes).items()),
                      {"d7": (d7 & 0xFFFF0000) | (value if final_d7 is None else final_d7), "a5": a1, "a6": 0x1B7953,
                       "a7": sp + 4, "pc": return_pc & 0xFFFFFF, "sr": _logic_sr(carry_sr, 0, 4)},
                      last_pc, direct_calls=3 + bool(linked))


def finish_object(machine, registers: dict[str, int]) -> AtomicPlan:
    """1AE954: accumulate, clear the pair, and install template 1B7940."""
    return _finish_object_plan(machine, registers, static_cycles=706, static_instructions=45,
                               return_site=0x1AE976, last_pc=FINISH_LAST_PC)


def replace_object(machine, registers: dict[str, int], *, increment_total=False, extra_spans=(),
                   template=0x1B7ABC, return_site=REPLACE_LAST_PC, amount=0) -> AtomicPlan:
    """1AF4C6 replacement boundary, optionally including the 1AF4C2 +15 call."""
    a1, sp, sr = (registers[key] for key in ("a1", "a7", "sr"))
    return_pc = _read(machine, sp, 4)
    spans = [("outer return", sp, 4), *extra_spans]
    writes = []
    amount = 15 if increment_total else amount
    if amount:
        total = _read(machine, 0xFFF14E, 2) + amount
        sr = (sr & ~0x10) | (0x10 if total > 0xFFFF else 0)
        if not any(start <= 0xFFF14E and start + size >= 0xFFF150 for _, start, size in extra_spans):
            spans.append(("object total", 0xFFF14E, 2))
    cycles, instructions, cleared, linked = _clear_objects(machine, registers, sp=sp - 4,
                                                          pair=True, extra_spans=spans, include_semantics=False)
    data = _object_template(machine, record=a1, template=template, entry_sp=sp - 4)
    semantic = game.retire_collected_object(lambda address, size: _read(machine, address, size), a1, data, amount)
    writes.extend((*cleared, *_bytes(sp - 4, return_site, 4), *semantic))
    return AtomicPlan(544 + cycles + 58 * bool(amount), 32 + instructions + 3 * bool(amount),
                      tuple(dict(writes).items()),
                      {"a5": a1, "a6": template + 19, "a7": sp + 4,
                       "pc": return_pc & 0xFFFFFF, "sr": _logic_sr(sr, 0, 4)},
                      return_site, direct_calls=4 + bool(linked) + bool(amount))


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


# Same concrete two-call sound ABI at ten collection sites. These are ROM facts,
# not resume IDs: the Python activation retains its entry while sound runs.
# kind, return after second JSR, final RTS, amount, replacement template
COLLECTION_ROUTES = {
    0x1AF008: ('flag128', 0x1AF02A, 0x1AF4D6, 15, 0x1B7ABC),
    0x1AF034: ('flag129', 0x1AF056, 0x1AF4D6, 15, 0x1B7ABC),
    0x1AF060: ('flag116', 0x1AF082, 0x1AF4D6, 15, 0x1B7ABC),
    0x1AF08C: ('flag12a', 0x1AF0AE, 0x1AF4D6, 15, 0x1B7ABC),
    TRANSITION_ENTRY: ('primary', SOUND_RETURN, REPLACE_LAST_PC, 0, 0x1B7ABC),
    0x1AF21E: ('secondary', 0x1AF258, 0x1AF4D6, 15, 0x1B7ABC),
    0x1AF264: ('quarter', 0x1AF2A6, 0x1AF4D6, 15, 0x1B7ABC),
    0x1AF2B0: ('flag177', 0x1AF2F2, 0x1AF2F8, 0, 0),
    0x1AF2FA: ('flag178', 0x1AF33C, 0x1AF342, 0, 0),
    0x1AF344: ('timer100', 0x1AF378, 0x1AF382, 100, 0x1B7ABC),
    0x1AF384: ('flag100', 0x1AF3B0, 0x1AF3C0, 100, 0x1B7ABC),
    0x1AF3C2: ('flag25', 0x1AF3E4, 0x1AF3FE, 25, 0x1B7CD8),
    0x1AF400: ('spawn', 0x1AF422, 0x1AF466, 0, 0x1B7CC4),
    0x1AF4A0: ('plain15', 0x1AF4BC, 0x1AF4D6, 15, 0x1B7ABC),
    0x1AF4D8: ('count25', 0x1AF4FA, 0x1AF514, 25, 0x1B7CD8),
    0x1AF53E: ('reset15', 0x1AF4BC, 0x1AF4D6, 15, 0x1B7ABC),
}
COLLECTION_GLOBALS = tuple(('collection input/effect', address, size) for address, size in (
    (0xFFEFE0, 4), (0xFFF003, 1), (0xFFF0A4, 2), (0xFFF0D8, 1),
    (0xFFF0E9, 1), (0xFFF10A, 1), (0xFFF11C, 1), (0xFFF14E, 2), (0xFFF176, 4),
    (0xFFF116, 1), (0xFFF128, 2), (0xFFF12A, 1), (0xFFF57D, 1), (0xFF7DFE, 4)))


def begin_collection_dispatch(machine, registers):
    """1ABC82: dispatch one known collection callback without a native re-entry.

    The original table has 256 immutable four-byte callback slots. This owner
    accepts only already-qualified collection entries. Its JSR frame becomes
    the callback's outer return. Planning refusals fall back from the untouched
    dispatcher; after an admitted prefix, a sound-suffix refusal hands back at
    the existing callback boundary with that prefix retained.
    """
    record, sp, d1, sr = (registers[key] for key in ('a1', 'a7', 'd1', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned collection dispatch record/stack')
    _spans_disjoint([('collection dispatch record', record, 66),
                     ('collection dispatch frame', sp - 4, 8),
                     ('collection dispatch globals', 0xFFF0F5, 2)])
    kind = _read(machine, record, 1)
    target = int.from_bytes(machine.peek_rom(COLLECTION_DISPATCH_TABLE + 4 * kind, 4), 'big') & 0xFFFFFF
    if target not in (*COLLECTION_ROUTES, CONTACT_DISPATCH_ENTRY,
                      CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
        raise UnsupportedCandidate(f'collection dispatch target {target:06X} is not recovered')
    dispatch_sr = sr & ~0x1F
    if kind == 0:
        dispatch_sr |= 0x04
    writes = ((0xFFF0F5, 0), (0xFFF0F6, kind),
              *_bytes(sp - 4, COLLECTION_DISPATCH_RETURN, 4))
    return target, AtomicPlan(98, 9, writes,
                              {'d1': (d1 & 0xFFFF0000) | (kind * 4), 'a4': target,
                               'a7': sp - 4, 'pc': target, 'sr': dispatch_sr},
                              0x1ABC9E, direct_calls=1)


class _DispatchPlanView:
    """Read planned prefix bytes while deriving its direct callback plan."""
    def __init__(self, machine, writes):
        self._machine = machine
        self._writes = {address & 0xFFFF: value for address, value in writes}

    def peek_ram(self, offset, size):
        data = bytearray(self._machine.peek_ram(offset, size))
        for index in range(size):
            value = self._writes.get(offset + index)
            if value is not None:
                data[index] = value
        return bytes(data)

    def peek_rom(self, offset, size):
        return self._machine.peek_rom(offset, size)


def dispatch_plan_view(machine, prefix):
    """Expose planned prefix bytes needed by the immediate callback plan."""
    return _DispatchPlanView(machine, prefix.writes)


def begin_contact_dispatch(machine, registers, dispatch):
    """Compose dispatcher type 7B's BSR/RTS around a direct contact plan."""
    sp = registers['a7']
    if dispatch.registers.get('pc') != CONTACT_DISPATCH_ENTRY or dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('contact dispatch prefix identity')
    callback_writes = (*dispatch.writes, *_bytes(sp - 8, CONTACT_DISPATCH_LOCAL_RETURN, 4))
    callback = AtomicPlan(dispatch.cycles + 18, dispatch.instructions + 1, callback_writes,
                          {**registers, **dispatch.registers, 'a7': sp - 8, 'pc': CONTACT_ENTRY},
                          CONTACT_DISPATCH_ENTRY, dispatch.direct_calls + 1)
    contact = begin_contact(dispatch_plan_view(machine, callback), callback.registers)
    final = dict(dispatch.registers)
    final.update(contact.registers)
    final.update(a7=sp, pc=COLLECTION_DISPATCH_RETURN)
    return AtomicPlan(callback.cycles + contact.cycles + 16,
                      callback.instructions + contact.instructions + 1,
                      tuple(dict((*callback.writes, *contact.writes)).items()), final,
                      CONTACT_DISPATCH_LOCAL_RETURN, callback.direct_calls + contact.direct_calls)


def begin_contact_dispatch_sound(machine, registers, dispatch):
    """Enter type 7B's contact callback through the existing command-31 seam."""
    sp = registers['a7']
    if dispatch.registers.get('pc') != CONTACT_DISPATCH_ENTRY or dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('contact dispatch prefix identity')
    callback_writes = (*dispatch.writes, *_bytes(sp - 8, CONTACT_DISPATCH_LOCAL_RETURN, 4))
    callback = AtomicPlan(dispatch.cycles + 18, dispatch.instructions + 1, callback_writes,
                          {**registers, **dispatch.registers, 'a7': sp - 8, 'pc': CONTACT_ENTRY},
                          CONTACT_DISPATCH_ENTRY, dispatch.direct_calls + 1)
    sound = begin_contact_sound(dispatch_plan_view(machine, callback), callback.registers)
    final = dict(callback.registers)
    final.update(sound.registers)
    return AtomicPlan(callback.cycles + sound.cycles, callback.instructions + sound.instructions,
                      tuple(dict((*callback.writes, *sound.writes)).items()), final,
                      sound.last_pc, callback.direct_calls + sound.direct_calls)


def finish_contact_dispatch_sound(machine, registers):
    """Complete the contact suffix, then type 7B's local RTS to 1ABCA0."""
    contact = finish_contact_sound(machine, registers)
    local_sp = contact.registers['a7']
    if (contact.registers.get('pc') != CONTACT_DISPATCH_LOCAL_RETURN
            or _read(machine, local_sp, 4) != COLLECTION_DISPATCH_RETURN):
        raise UnsupportedCandidate('contact dispatch local return identity')
    final = dict(contact.registers)
    final.update(a7=local_sp + 4, pc=COLLECTION_DISPATCH_RETURN)
    return AtomicPlan(contact.cycles + 16, contact.instructions + 1, contact.writes, final,
                      CONTACT_DISPATCH_LOCAL_RETURN, contact.direct_calls)


CONTACT_GLOBALS = tuple(('contact state', address, 1) for address in (
    0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2, 0xFFF0BE, 0xFFF0C1,
    0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4, 0xFFF173, 0xFFF0CC,
    0xFFEFFF, 0xFFF11F, 0xFFF0D8, 0xFFF57D, 0xFF7E21,
    0xFF7E20, 0xFFEFFA, 0xFF7E77)) + (
    ('contact state', 0xFFF0B0, 2), ('contact state', 0xFF7E60, 4))

CONTACT_SIBLING_GLOBALS = (
    ('contact sibling state', 0xFFF0D8, 1), ('contact sibling state', 0xFFF0E9, 1),
    ('contact sibling state', 0xFF7E02, 2), ('contact sibling state', 0xFF7E49, 1),
)

# 1AF1AC allocates from the same 24-record primary pool that can also hold
# its source.  The source may overlap one *whole* slot (the first template
# makes it active before the reverse scan); partial overlap has no measured
# meaning and is refused.
CONTACT_TYPE13_GLOBALS = (
    ('type13 transition', 0xFFF124, 1), ('type13 sound flag', 0xFFF57F, 1),
    ('type13 total', 0xFFF14E, 2),
)
_TYPE13_POOL_START = 0xFF7E82
_TYPE13_POOL_HIGH = 0xFF8470
_TYPE13_POOL_COUNT = 24
_TYPE13_POOL_SIZE = _TYPE13_POOL_COUNT * 66


def _contact_type13_guard(machine, registers):
    """Validate the concrete record/pool/frame ownership for 1AF1AC."""
    record, sp = registers['a1'], registers['a7']
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type13 record or stack')
    pool_end = _TYPE13_POOL_START + _TYPE13_POOL_SIZE
    overlaps_pool = record < pool_end and record + 66 > _TYPE13_POOL_START
    if overlaps_pool and (record < _TYPE13_POOL_START or record + 66 > pool_end or
                          (record - _TYPE13_POOL_START) % 66):
        raise UnsupportedCandidate('type13 source partially overlaps allocator pool')
    spans = [('type13 allocator pool', _TYPE13_POOL_START, _TYPE13_POOL_SIZE),
             ('type13 frame', sp - 24, 28), *CONTACT_TYPE13_GLOBALS]
    if not overlaps_pool:
        spans.append(('type13 source record', record, 66))
    pointer = _read(machine, record + 42, 4)
    if pointer:
        spans.append(('type13 source buffer', pointer, _read(machine, record + 41, 1) + 1))
    _spans_disjoint(spans)
    _read(machine, sp, 4)
    return lambda address, size: _read(machine, address, size)


def _contact_type13(machine, registers):
    """Plan 1AF1AC up to its fixed native helper, or its exhausted RTS.

    The shared release and template semantics are reused directly here.  The
    helper's device effects stay native; its return is admitted separately.
    """
    record, sp, sr = (registers[name] for name in ('a1', 'a7', 'sr'))
    read = _contact_type13_guard(machine, registers)
    if read(record, 1) != 0x13 or read(record + 1, 1):
        raise UnsupportedCandidate('type13 callee record state')

    # CLR.B + BSR 1AE372.  The callee writes transient save slots below the
    # caller frame; later MOVEM overwrites them on the free-slot arm.
    clear_registers = dict(registers, a7=sp - 4)
    clear_cycles, clear_instructions, clear_writes, _ = _clear_objects(
        machine, clear_registers, sp=sp - 4,
        extra_spans=(('type13 return', sp, 4),))
    first = _initialize_object_effects(machine, record=record, template=0x1B7CC4,
                                       entry_sp=sp - 4)
    prefix_writes = [
        (record, 0), *_bytes(sp - 4, 0x1AF1B2, 4), *clear_writes,
        *_bytes(sp - 4, 0x1AF1BE, 4), *first,
    ]
    after_first = AtomicPlan(30 + clear_cycles + 34 + 476,
                             2 + clear_instructions + 3 + 27,
                             tuple(dict(prefix_writes).items()),
                             {**registers, 'a5': record, 'a6': 0x1B7CD7,
                              'a7': sp, 'sr': _logic_sr(sr, 0, 4)},
                             0x1AF1BE, direct_calls=2)
    planner = dispatch_plan_view(machine, after_first)
    plan_read = lambda address, size: _read(planner, address, size)
    destination, index = game.free_object_reverse(plan_read, _TYPE13_POOL_HIGH,
                                                   _TYPE13_POOL_COUNT)
    # BSR plus 1AE292's LEA/MOVE/DBRA/RTS scan.  A found slot leaves D0 as
    # 23-index; exhaustion leaves the DBRA low word at FFFF and A5 just below
    # the pool.  TST.B supplies NZVC on both arms.
    scan_cycles = 54 + 40 * index if destination is not None else 1000
    scan_instructions = 5 + 4 * index if destination is not None else 99
    d0 = (registers['d0'] & 0xFFFF0000) | (23 - index if destination is not None else 0xFFFF)
    selected = destination if destination is not None else _TYPE13_POOL_START - 66
    selected_type = 0 if destination is not None else plan_read(_TYPE13_POOL_START, 1)
    scanned_sr = _logic_sr(after_first.registers['sr'], selected_type, 1)
    scan_writes = (*after_first.writes, *_bytes(sp - 4, 0x1AF1C2, 4))
    if destination is None:
        return AtomicPlan(after_first.cycles + 18 + scan_cycles + 26,
                          after_first.instructions + 1 + scan_instructions + 2,
                          tuple(dict(scan_writes).items()),
                          {**registers, 'd0': d0, 'a5': selected, 'a6': 0x1B7CD7,
                           'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF, 'sr': scanned_sr},
                          0x1AF21C, direct_calls=after_first.direct_calls + 1), False

    second = _initialize_object_effects(planner, record=destination, template=0x1B8368,
                                        entry_sp=sp - 4)
    staged_writes = [*scan_writes, *_bytes(sp - 4, 0x1AF1CE, 4), *second]
    staged = AtomicPlan(after_first.cycles + 18 + scan_cycles + 8 + 30 + 476,
                        after_first.instructions + 1 + scan_instructions + 1 + 2 + 27,
                        tuple(dict(staged_writes).items()),
                        {**registers, 'd0': d0, 'a5': destination, 'a6': 0x1B837B,
                         'a7': sp, 'sr': scanned_sr},
                        0x1AF1CE, direct_calls=after_first.direct_calls + 2)
    staged_machine = dispatch_plan_view(machine, staged)
    position_x = _read(staged_machine, record + 2, 2)
    position_y = _read(staged_machine, record + 4, 2)
    saves = []
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        saves.extend(_bytes(sp - index * 4, staged.registers[name], 4))
    writes = (*staged.writes, *_bytes(destination + 2, position_x, 2),
              *_bytes(destination + 4, (position_y - 0x20) & 0xFFFF, 2),
              (destination + 9, 0xFF), (0xFFF124, 8), *saves,
              *_bytes(sp - 24, CONTACT_TYPE13_FIXED_RETURN, 4))
    return AtomicPlan(staged.cycles + 164, staged.instructions + 7,
                      tuple(dict(writes).items()),
                      {**staged.registers, 'a7': sp - 24, 'pc': 0x1E58F4,
                       'sr': _logic_sr(scanned_sr, 8, 1)},
                      0x1AF1F0, direct_calls=staged.direct_calls), True


def _finish_contact_type13(machine, registers):
    """Restore 1E58F4's fixed 20-byte frame and return through 1AECEE."""
    if registers.get('pc') != CONTACT_TYPE13_FIXED_RETURN or registers['a7'] & 1:
        raise UnsupportedCandidate('foreign type13 fixed-helper return')
    sp = registers['a7'] + 20
    restored = dict(registers, a7=sp)
    for index, name in enumerate(('d0', 'd1', 'a0', 'a1', 'a6')):
        restored[name] = _read(machine, registers['a7'] + index * 4, 4)
    _contact_type13_guard(machine, restored)
    if _read(machine, 0xFFF57F, 1):
        # The 0x14 request has a distinct second synchronous call.  The fixed
        # helper is already committed and original code owns that local tail.
        raise UnsupportedCandidate('type13 optional command14 suffix')
    return AtomicPlan(94, 4, (),
                      {**restored, 'a7': sp + 4, 'pc': _read(machine, sp, 4) & 0xFFFFFF,
                       'sr': _logic_sr(restored['sr'], 0, 1)},
                      0x1AF21C)


def _contact_type13_outer(machine, registers, *, require_fixed):
    """Compose 1AEC00's direction/counter prefix with the 1AF1AC callee."""
    record, sp, sr = (registers[name] for name in ('a1', 'a7', 'sr'))
    read = lambda address, size: _read(machine, address, size)
    direction, distance, value = read(0xFF7E49, 1), read(0xFF7E02, 2), read(record + 8, 1)
    total = read(0xFFF14E, 2) + value
    outer_cycles, outer_instructions = (124, 10) if direction else (116, 9)
    enter = AtomicPlan(outer_cycles + 74, outer_instructions + 6,
                       (*_bytes(0xFFF14E, total, 2), *_bytes(sp - 4, CONTACT_TYPE13_RETURN, 4)),
                       {**registers, 'd7': (registers['d7'] & 0xFFFF0000) | value,
                        'a7': sp - 4, 'pc': CONTACT_TYPE13_ENTRY,
                        'sr': _add_sr(sr, read(0xFFF14E, 2), value, 2)},
                       CONTACT_SIBLING_RETIREMENT, direct_calls=1)
    inner, needs_fixed = _contact_type13(dispatch_plan_view(machine, enter), enter.registers)
    if require_fixed:
        if not needs_fixed:
            raise UnsupportedCandidate('type13 allocator exhausted without fixed helper')
        final = dict(enter.registers); final.update(inner.registers)
        return AtomicPlan(enter.cycles + inner.cycles, enter.instructions + inner.instructions,
                          tuple(dict((*enter.writes, *inner.writes)).items()), final,
                          inner.last_pc, enter.direct_calls + inner.direct_calls)
    if needs_fixed:
        raise UnsupportedCandidate('type13 requires fixed native helper')
    # 1AF1AC returns to 1AECEE, whose RTS returns the surrounding callback.
    final = dict(inner.registers)
    final.update(a7=sp + 4, pc=read(sp, 4) & 0xFFFFFF)
    return AtomicPlan(enter.cycles + inner.cycles + 16, enter.instructions + inner.instructions + 1,
                      tuple(dict((*enter.writes, *inner.writes)).items()), final,
                      CONTACT_TYPE13_RETURN, enter.direct_calls + inner.direct_calls)


def begin_contact_sibling_type13_sound(machine, registers):
    """Enter 1AEC00's free-slot type-13 fixed-helper seam."""
    return _contact_type13_outer(machine, registers, require_fixed=True)


def finish_contact_sibling_type13_sound(machine, registers):
    """Finish the fixed helper then the caller RTS at 1AECEE."""
    inner = _finish_contact_type13(machine, registers)
    sp = inner.registers['a7']
    final = dict(inner.registers)
    final.update(a7=sp + 4, pc=_read(machine, sp, 4) & 0xFFFFFF)
    return AtomicPlan(inner.cycles + 16, inner.instructions + 1, inner.writes, final,
                      CONTACT_TYPE13_RETURN, inner.direct_calls)

# 1AD150's priority inputs are live RAM.  The sole table arm reads immutable
# cartridge data at 121828; the boundary reads that data only after this guard
# has admitted the full mutable selector domain.
CONTACT_SELECTOR_GLOBALS = tuple(('contact selector state', address, 1) for address in (
    0xFFF0D7, 0xFFF173, 0xFFF115, 0xFFF0CD, 0xFFF0D3, 0xFFF0DB,
    0xFFF0D0, 0xFFF0D2, 0xFFF0C1, 0xFFF0DE, 0xFFF0DF, 0xFFF0ED,
    0xFFF0E7, 0xFF7E77, 0xFFF0CC,
)) + (('contact selector state', 0xFFF0B0, 2),
      ('contact selector state', 0xFF7E04, 2))


def _cmp_sr(sr, left, right, width):
    """68000 CMP flags for ``left - right`` while retaining X."""
    mask, sign = (1 << (8 * width)) - 1, 1 << (8 * width - 1)
    left &= mask; right &= mask
    result = (left - right) & mask
    out = _logic_sr(sr, result, width)
    if left < right:
        out |= 1
    if ((left ^ right) & (left ^ result) & sign):
        out |= 2
    return out


def _subq_byte_sr(sr, value):
    """The decrement's SUBQ.B #1 residue, including its X/C result."""
    value &= 0xFF
    result = (value - 1) & 0xFF
    out = _logic_sr(sr & ~0x10, result, 1)
    if value == 0:
        out |= 0x11
    if value == 0x80:
        out |= 2
    return out


def _contact_selector(machine, registers):
    """Plan the pure 1AD150 selector through its BSR return at 1AEC64."""
    sp, sr = registers['a7'], registers['sr']
    read = lambda address, size: _read(machine, address, size)
    key, selected, table_index, clears_cc = game.contact_script_selector(read)
    writes = []
    if key != 'd7':
        writes.extend(((0xFF7E77, 0), (0xFFF0E7, 0)))
    if clears_cc:
        writes.append((0xFFF0CC, 0))
    costs = {
        'd7': (52, 4), 'f173-c1zero': (146, 10),
        'f173-b0-1': (178, 12), 'f173-b0-2': (206, 14),
        'f173-default': (236, 16), 'f115': (166, 11),
        'cd-50-51': (248, 17), 'cd-60': (278, 19),
        'db': (228, 16), 'd0-table': (316, 23), 'd2': (280, 20),
        'normal': (308, 22), 'de': (334, 24), 'df': (360, 26),
        'ed': (386, 28), 'b0-1': (418, 30), 'b0-2': (462, 33),
        'c1-default': (476, 34),
    }
    # CD's fall-through costs depend on the two earlier comparisons.  The
    # selector semantic identifies the final arm; the boundary retains this
    # instruction-level distinction without retaining mutable state.
    cd, d3 = read(0xFFF0CD, 1), read(0xFFF0D3, 1)
    if key == 'cd-5e':
        cycles, instructions = (308, 21) if cd else (222, 15)
    else:
        cycles, instructions = costs[key]
        if cd and key in ('normal', 'db', 'd0-table', 'd2', 'de', 'df', 'ed',
                          'b0-1', 'b0-2', 'c1-default'):
            extra_cycles, extra_instructions = (58, 4) if d3 < 0x50 else (86, 6)
            cycles += extra_cycles; instructions += extra_instructions
    if key == 'd0-table':
        selected = int.from_bytes(machine.peek_rom(0x121828 + table_index * 4, 4), 'big')
        final_sr = _logic_sr(sr & ~0x10, table_index << 2, 2)
        d0 = (registers['d0'] & 0xFFFF0000) | (table_index << 2)
    elif key == 'd7':
        final_sr = _logic_sr(sr, read(0xFFF0D7, 1), 1)
    elif key == 'f115':
        # The terminal CLR.B 7E77 follows the LEA and therefore supplies Z.
        final_sr = _logic_sr(sr, 0, 1)
    elif key == 'db':
        final_sr = _logic_sr(sr, read(0xFFF0DB, 1), 1)
    elif key == 'd2':
        final_sr = _logic_sr(sr, read(0xFFF0D2, 1), 1)
    elif key in ('de', 'df', 'ed'):
        address = {'de': 0xFFF0DE, 'df': 0xFFF0DF, 'ed': 0xFFF0ED}[key]
        final_sr = _logic_sr(sr, read(address, 1), 1)
    elif key == 'c1-default':
        final_sr = _cmp_sr(sr, read(0xFFF0B0, 2), 2, 2)
    else:
        # The remaining arms terminate in a CLR/TST or equality comparison.
        final_sr = _logic_sr(sr, 0, 1)
    last = {'d7': 0x1AD15E, 'f115': 0x1AD18A, 'cd-50-51': 0x1AD1B4,
            'cd-60': 0x1AD1CC, 'cd-5e': 0x1AD1E4, 'db': 0x1AD1F4,
            'd0-table': 0x1AD216, 'd2': 0x1AD226, 'normal': 0x1AD294,
            'de': 0x1AD240, 'df': 0x1AD250, 'ed': 0x1AD260,
            'b0-1': 0x1AD294, 'b0-2': 0x1AD294, 'c1-default': 0x1AD28C,
            'f173-c1zero': 0x1AD2DA, 'f173-b0-1': 0x1AD294,
            'f173-b0-2': 0x1AD294, 'f173-default': 0x1AD2D2}[key]
    final = {**registers, 'a2': selected, 'a7': sp + 4,
             'pc': _read(machine, sp, 4) & 0xFFFFFF, 'sr': final_sr}
    if key == 'd0-table':
        final['d0'] = d0
    return AtomicPlan(cycles, instructions, tuple(writes), final, last, direct_calls=1)


def _contact_sibling_decrement_suffix(machine, registers):
    """1AEC64: install the selected script and finish the non-13 arm."""
    record, sp = registers['a1'], registers['a7']
    read = lambda address, size: _read(machine, address, size)
    kind = read(record, 1)
    if kind == 0x13:
        raise UnsupportedCandidate('contact sibling decrement type13 is not recovered')
    saved_a2, outer_return = read(sp, 4), read(sp + 4, 4)
    writes = [*_bytes(0xFF7E60, registers['a2'], 4), (0xFF7E77, 0),
              *_bytes(0xFFF0B0, 0, 2), (0xFFF0CC, 0)]
    cycles, instructions = 152, 10
    final_sr = _cmp_sr(registers['sr'], kind, 0x18, 1)
    if kind == 0x18:
        writes.extend(((record, 0x84), *_bytes(record + 0x20, 0x1248B6, 4), (record + 0x37, 0)))
        cycles, instructions = 202, 13
        final_sr = _logic_sr(final_sr, 0, 1)
    return AtomicPlan(cycles, instructions, tuple(writes),
                      {'a2': saved_a2, 'a7': sp + 8, 'pc': outer_return & 0xFFFFFF,
                       'sr': final_sr}, 0x1AED22, direct_calls=1)


def _contact_sibling_decrement(machine, registers):
    """1AEC32 sound-off counter decrement, BSR selector, and local suffix."""
    record, sp = registers['a1'], registers['a7']
    read = lambda address, size: _read(machine, address, size)
    counter = read(record + 1, 1)
    if not counter:
        raise UnsupportedCandidate('contact sibling counter wraps')
    if read(record, 1) == 0x13:
        raise UnsupportedCandidate('contact sibling decrement type13 is not recovered')
    prefix_sr = _logic_sr(_subq_byte_sr(registers['sr'], counter), read(0xFFF57D, 1), 1)
    prefix = AtomicPlan(92, 6,
                        (*_bytes(record + 1, counter - 1, 1), *_bytes(sp - 4, registers['a2'], 4),
                         *_bytes(sp - 8, 0x1AEC64, 4)),
                        {**registers, 'a7': sp - 8, 'pc': 0x1AD150, 'sr': prefix_sr},
                        0x1AEC60, direct_calls=1)
    selector = _contact_selector(dispatch_plan_view(machine, prefix), prefix.registers)
    planned = AtomicPlan(prefix.cycles + selector.cycles, prefix.instructions + selector.instructions,
                         tuple(dict((*prefix.writes, *selector.writes)).items()), selector.registers,
                         selector.last_pc, prefix.direct_calls + selector.direct_calls)
    suffix = _contact_sibling_decrement_suffix(dispatch_plan_view(machine, planned), selector.registers)
    final = dict(registers); final.update(selector.registers); final.update(suffix.registers)
    return AtomicPlan(prefix.cycles + selector.cycles + suffix.cycles,
                      prefix.instructions + selector.instructions + suffix.instructions,
                      tuple(dict((*prefix.writes, *selector.writes, *suffix.writes)).items()), final,
                      suffix.last_pc, prefix.direct_calls + selector.direct_calls + suffix.direct_calls)


def _contact_sibling_decrement_sound(machine, registers):
    """1AEC32 through its command-8 request, before native sound executes."""
    record, sp = registers['a1'], registers['a7']
    read = lambda address, size: _read(machine, address, size)
    counter = read(record + 1, 1)
    if not counter or read(record, 1) == 0x13:
        raise UnsupportedCandidate('contact sibling command8 decrement domain')
    if not read(0xFFF57D, 1):
        raise UnsupportedCandidate('contact sibling command8 is sound-disabled')
    sr = _logic_sr(_subq_byte_sr(registers['sr'], counter), read(0xFFF57D, 1), 1)
    writes = [*_bytes(record + 1, counter - 1, 1)]
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        writes.extend(_bytes(sp - index * 4, registers[name], 4))
    writes.extend((*_bytes(sp - 24, 8, 4), *_bytes(sp - 28, 0x1AEC4C, 4)))
    return AtomicPlan(124, 6, tuple(writes),
                      {**registers, 'a7': sp - 28, 'pc': 0x1E58B8, 'sr': sr},
                      0x1AEC46, direct_calls=1)


def begin_contact_sibling_sound_seam(machine, registers):
    """Construct 1AEC00's measured decrement or type-13 sound seam."""
    record, sp = registers['a1'], registers['a7']
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact sibling sound record/stack')
    _spans_disjoint([('contact sibling sound record', record, 66),
                     ('contact sibling sound frame', sp - 28, 32), *CONTACT_SIBLING_GLOBALS,
                     *CONTACT_SELECTOR_GLOBALS, ('contact sibling sound state', 0xFFF57D, 1),
                     ('contact sibling script', 0xFF7E60, 4)])
    read = lambda address, size: _read(machine, address, size)
    route = game.contact_sibling_route(read, record)[0]
    if route == 'type13':
        return SoundSeam(begin_contact_sibling_type13_sound(machine, registers), sp - 4,
                         CONTACT_TYPE13_FIXED_RETURN, CONTACT_TYPE13_FIXED_RETURN,
                         20, 20, 24, suffix=finish_contact_sibling_sound)
    if route != 'decrement':
        raise UnsupportedCandidate('contact sibling is not on its decrement arm')
    direction, distance = read(0xFF7E49, 1), read(0xFF7E02, 2)
    outer_cycles, outer_instructions = (126, 10) if direction else (118, 9)
    outer = AtomicPlan(outer_cycles, outer_instructions, (),
                       {**registers, 'd7': (registers['d7'] & 0xFFFF0000) | distance,
                        'pc': 0x1AEC32}, 0x1AEC2E)
    sound = _contact_sibling_decrement_sound(dispatch_plan_view(machine, outer), outer.registers)
    prefix = AtomicPlan(outer.cycles + sound.cycles, outer.instructions + sound.instructions,
                        tuple(dict((*outer.writes, *sound.writes)).items()), sound.registers,
                        sound.last_pc, outer.direct_calls + sound.direct_calls)
    return SoundSeam(prefix, sp, 0x1AEC52, 0x1AEC52, 24, 28, 28,
                     suffix=finish_contact_sibling_sound)


def begin_contact_sibling_sound(machine, registers):
    """1AEC00's admitted decrement or type-13 native helper prefix."""
    return begin_contact_sibling_sound_seam(machine, registers).prefix

def finish_contact_sibling_sound(machine, registers):
    """Resume command 8 or the type-13 fixed helper at its local return."""
    if registers.get('pc') == CONTACT_TYPE13_FIXED_RETURN:
        return finish_contact_sibling_type13_sound(machine, registers)
    if registers['pc'] != 0x1AEC52 or registers['a7'] & 1:
        raise UnsupportedCandidate('foreign contact sibling command8 return')
    sp = registers['a7'] + 24
    restored = dict(registers, a7=sp)
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        restored[name] = _read(machine, sp - index * 4, 4)
    record = restored['a1']
    _spans_disjoint([('contact sibling sound record', record, 66),
                     ('contact sibling sound frame', sp - 28, 32), *CONTACT_SIBLING_GLOBALS,
                     *CONTACT_SELECTOR_GLOBALS, ('contact sibling sound state', 0xFFF57D, 1),
                     ('contact sibling script', 0xFF7E60, 4)])
    local = AtomicPlan(110, 5, (*_bytes(sp - 4, restored['a2'], 4),
                                *_bytes(sp - 8, 0x1AEC64, 4)),
                       {**restored, 'a7': sp - 8, 'pc': 0x1AD150}, 0x1AEC60, direct_calls=1)
    selector = _contact_selector(dispatch_plan_view(machine, local), local.registers)
    planned = AtomicPlan(local.cycles + selector.cycles, local.instructions + selector.instructions,
                         tuple(dict((*local.writes, *selector.writes)).items()), selector.registers,
                         selector.last_pc, local.direct_calls + selector.direct_calls)
    suffix = _contact_sibling_decrement_suffix(dispatch_plan_view(machine, planned), selector.registers)
    final = dict(restored); final.update(selector.registers); final.update(suffix.registers)
    return AtomicPlan(planned.cycles + suffix.cycles, planned.instructions + suffix.instructions,
                      tuple(dict((*planned.writes, *suffix.writes)).items()), final,
                      suffix.last_pc, planned.direct_calls + suffix.direct_calls)

_CONTACT_SIBLING_RETIRE = {
    # Cost from 1AECD8 to the 1AED0C tail, after the latter's own RTS body.
    'retire18': (88, 8, ()),
    'retire10': (122, 10, ((0xFFF0E9, 0x20),)),
    'retire11': (140, 12, ((0xFFF0E9, 0x20),)),
    'retire': (122, 11, ()),
}


def _contact_sibling_tail(machine, registers, *, extra_spans=()):
    """1AED0C's shared pair-release/template-install tail alone."""
    return _finish_object_plan(machine, registers, static_cycles=670, static_instructions=42,
                               return_site=0x1AED22, last_pc=0x1AED22,
                               extra_spans=extra_spans, accumulate=False,
                               final_d7=registers['d7'] & 0xFFFF)


def begin_contact_sibling_tail(machine, registers):
    """Exact external 1AED0C tail; it has no direction or counter precondition."""
    record, sp = registers['a1'], registers['a7']
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact sibling record/stack')
    _spans_disjoint([('contact sibling record', record, 66),
                     ('contact sibling tail return', sp - 10, 14)])
    return _contact_sibling_tail(machine, registers)


def begin_contact_sibling_retirement(machine, registers):
    """1AECD8 retirement; type-13's exhausted allocator arm is oracle-only."""
    record, sp = registers['a1'], registers['a7']
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact sibling record/stack')
    _spans_disjoint([('contact sibling record', record, 66),
                     ('contact sibling return', sp - 10, 14),
                     ('contact sibling total', 0xFFF14E, 2),
                     ('contact sibling mode', 0xFFF0E9, 1)])
    read = lambda address, size: _read(machine, address, size)
    kind = read(record, 1)
    if kind == 0x13:
        value = read(record + 8, 1)
        total = read(0xFFF14E, 2) + value
        enter = AtomicPlan(74, 6,
                           (*_bytes(0xFFF14E, total, 2),
                            *_bytes(sp - 4, CONTACT_TYPE13_RETURN, 4)),
                           {**registers, 'd7': (registers['d7'] & 0xFFFF0000) | value,
                            'a7': sp - 4, 'pc': CONTACT_TYPE13_ENTRY,
                            'sr': _add_sr(registers['sr'], read(0xFFF14E, 2), value, 2)},
                           CONTACT_SIBLING_RETIREMENT, direct_calls=1)
        inner, needs_fixed = _contact_type13(dispatch_plan_view(machine, enter), enter.registers)
        if needs_fixed:
            raise UnsupportedCandidate('type13 direct retirement requires fixed helper seam')
        final = dict(inner.registers)
        final.update(a7=sp + 4, pc=read(sp, 4) & 0xFFFFFF)
        return AtomicPlan(enter.cycles + inner.cycles + 16,
                          enter.instructions + inner.instructions + 1,
                          tuple(dict((*enter.writes, *inner.writes)).items()), final,
                          CONTACT_TYPE13_RETURN, enter.direct_calls + inner.direct_calls)
    route = 'retire18' if kind == 0x18 else 'retire10' if kind == 0x10 else \
            'retire11' if kind == 0x11 else 'retire'
    cycles, instructions, extra_writes = _CONTACT_SIBLING_RETIRE[route]
    value = read(record + 8, 1)
    total = read(0xFFF14E, 2) + value
    add_sr = (registers['sr'] & ~0x10) | (0x10 if total > 0xFFFF else 0)
    tail = _contact_sibling_tail(machine, dict(registers, sr=add_sr),
                                 extra_spans=(('contact sibling total', 0xFFF14E, 2),
                                              ('contact sibling mode', 0xFFF0E9, 1)))
    final = dict(tail.registers)
    final['d7'] = (registers['d7'] & 0xFFFF0000) | value
    writes = (*_bytes(0xFFF14E, total, 2), *extra_writes, *tail.writes)
    return AtomicPlan(cycles + tail.cycles, instructions + tail.instructions,
                      tuple(dict(writes).items()), final, tail.last_pc, tail.direct_calls)


def begin_contact_sibling(machine, registers):
    """1AEC00 through the accepted counter-retirement branch and its RTS."""
    record, sp = registers['a1'], registers['a7']
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact sibling record/stack')
    _spans_disjoint([('contact sibling record', record, 66),
                     ('contact sibling return', sp - 10, 14), *CONTACT_SIBLING_GLOBALS,
                     *CONTACT_SELECTOR_GLOBALS, ('contact sibling sound', 0xFFF57D, 1),
                     ('contact sibling script', 0xFF7E60, 4), ('contact sibling total', 0xFFF14E, 2)])
    read = lambda address, size: _read(machine, address, size)
    route, _ = game.contact_sibling_route(read, record)
    if route == 'decrement':
        if read(0xFFF57D, 1):
            raise UnsupportedCandidate('contact sibling decrement requires command8 seam')
        direction, distance = read(0xFF7E49, 1), read(0xFF7E02, 2)
        prefix_cycles, prefix_instructions = (126, 10) if direction else (118, 9)
        prefix = AtomicPlan(prefix_cycles, prefix_instructions, (),
                            {**registers, 'd7': (registers['d7'] & 0xFFFF0000) | distance,
                             'pc': 0x1AEC32}, 0x1AEC2E)
        decrement = _contact_sibling_decrement(dispatch_plan_view(machine, prefix), prefix.registers)
        final = dict(prefix.registers); final.update(decrement.registers)
        return AtomicPlan(prefix.cycles + decrement.cycles,
                          prefix.instructions + decrement.instructions,
                          tuple(dict((*prefix.writes, *decrement.writes)).items()), final,
                          decrement.last_pc, prefix.direct_calls + decrement.direct_calls)
    if route == 'type13':
        return _contact_type13_outer(machine, registers, require_fixed=False)
    if route in _CONTACT_SIBLING_RETIRE:
        # The outer route reads all sibling inputs before entering the tail.
        kind = read(record, 1)
        cycles, instructions, extra_writes = _CONTACT_SIBLING_RETIRE[route]
        value = read(record + 8, 1)
        total = read(0xFFF14E, 2) + value
        add_sr = (registers['sr'] & ~0x10) | (0x10 if total > 0xFFFF else 0)
        tail = _contact_sibling_tail(machine, dict(registers, sr=add_sr), extra_spans=(
            *CONTACT_SIBLING_GLOBALS, ('contact sibling total', 0xFFF14E, 2)))
        final = dict(tail.registers)
        final['d7'] = (registers['d7'] & 0xFFFF0000) | value
        prefix_cycles, prefix_instructions = (124, 10) if read(0xFF7E49, 1) else (116, 9)
        writes = (*_bytes(0xFFF14E, total, 2), *extra_writes, *tail.writes)
        return AtomicPlan(prefix_cycles + cycles + tail.cycles,
                          prefix_instructions + instructions + tail.instructions,
                          tuple(dict(writes).items()), final, tail.last_pc, tail.direct_calls)
    if route == 'contact':
        return AtomicPlan(42, 3, (),
                          {'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF,
                           'sr': _logic_sr(registers['sr'], 0, 1)}, 0x1AED22)
    if route == 'early':
        direction, distance, limit = read(0xFF7E49, 1), read(0xFF7E02, 2), read(record + 2, 2)
        # MOVE.W FF7E02,D7 then CMP.W 2(A1),D7.  Taken direction arms
        # differ only in the branch timing; CMP preserves X and writes NZVC.
        result = (distance - limit) & 0xFFFF
        sr = _logic_sr(registers['sr'], result, 2)
        if distance < limit:
            sr |= 1
        if ((distance ^ limit) & (distance ^ result) & 0x8000):
            sr |= 2
        return AtomicPlan(106 if direction else 108, 8, (),
                          {'d7': (registers['d7'] & 0xFFFF0000) | distance,
                           'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF, 'sr': sr},
                          0x1AED22)
    raise UnsupportedCandidate(f'contact sibling {route} is not recovered')


def begin_contact_sibling_wrapper(machine, registers, entry):
    """Compose 1AE9C6/1AE9DA around an admitted sibling or direct contact."""
    if entry not in (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
        raise UnsupportedCandidate('unknown contact sibling wrapper')
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned contact sibling wrapper stack')
    _spans_disjoint([('contact sibling wrapper frame', sp - 10, 14),
                     ('contact sibling wrapper record', registers['a1'], 66),
                     *CONTACT_SIBLING_GLOBALS])
    # The first BSR's residue is retained only when 1AEC00 returns directly;
    # the C6 contact arm overwrites it with its second BSR return.
    sibling_return = 0x1AE9CA if entry == CONTACT_SIBLING_WRAPPER else 0x1AE9DE
    callback = AtomicPlan(18, 1, _bytes(sp - 4, sibling_return, 4),
                          {**registers, 'a7': sp - 4, 'pc': CONTACT_SIBLING_ENTRY},
                          entry, direct_calls=1)
    planner = dispatch_plan_view(machine, callback)
    read = lambda address, size: _read(planner, address, size)
    route, _ = game.contact_sibling_route(read, registers['a1'])
    if entry == CONTACT_SIBLING_WRAPPER and route == 'contact':
        contact_return = 0x1AE9D8
        contact_callback = AtomicPlan(106, 7, _bytes(sp - 4, contact_return, 4),
                                      {**registers, 'a7': sp - 4, 'pc': CONTACT_ENTRY},
                                      CONTACT_SIBLING_WRAPPER, direct_calls=2)
        contact = begin_contact(dispatch_plan_view(machine, contact_callback), contact_callback.registers)
        final = dict(contact.registers)
        final.update(a7=sp + 4, pc=read(sp, 4) & 0xFFFFFF)
        return AtomicPlan(contact_callback.cycles + contact.cycles + 16,
                          contact_callback.instructions + contact.instructions + 1,
                          tuple(dict((*contact_callback.writes, *contact.writes)).items()), final,
                          CONTACT_DISPATCH_LOCAL_RETURN,
                          contact_callback.direct_calls + contact.direct_calls)
    sibling = begin_contact_sibling(planner, callback.registers)
    if entry == CONTACT_SIBLING_DIRECT:
        final = dict(sibling.registers)
        final.update(a7=sp + 4, pc=read(sp, 4) & 0xFFFFFF)
        return AtomicPlan(callback.cycles + sibling.cycles + 16,
                          callback.instructions + sibling.instructions + 1,
                          tuple(dict((*callback.writes, *sibling.writes)).items()), final,
                          0x1AE9DE, callback.direct_calls + sibling.direct_calls)
    # 1AE9CA tests D8 and its taken BNE targets the single RTS at 1A91C4.
    if not read(0xFFF0D8, 1):
        raise UnsupportedCandidate('contact sibling wrapper contact arm did not compose')
    final = dict(sibling.registers)
    final.update(a7=sp + 4, pc=read(sp, 4) & 0xFFFFFF,
                 sr=_logic_sr(sibling.registers['sr'], read(0xFFF0D8, 1), 1))
    return AtomicPlan(callback.cycles + sibling.cycles + 42,
                      callback.instructions + sibling.instructions + 3,
                      tuple(dict((*callback.writes, *sibling.writes)).items()), final,
                      0x1A91C4, callback.direct_calls + sibling.direct_calls)


def begin_contact_sibling_dispatch(machine, registers, dispatch, entry):
    """Compose the recorded table prefix with one bounded sibling wrapper."""
    sp = registers['a7']
    if entry not in (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
        raise UnsupportedCandidate('unknown dispatched contact sibling wrapper')
    if dispatch.registers.get('pc') != entry or dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('contact sibling dispatch prefix identity')
    callback_registers = {**registers, **dispatch.registers}
    wrapper = begin_contact_sibling_wrapper(dispatch_plan_view(machine, dispatch), callback_registers, entry)
    final = dict(dispatch.registers)
    final.update(wrapper.registers)
    return AtomicPlan(dispatch.cycles + wrapper.cycles, dispatch.instructions + wrapper.instructions,
                      tuple(dict((*dispatch.writes, *wrapper.writes)).items()), final,
                      wrapper.last_pc, dispatch.direct_calls + wrapper.direct_calls)


def begin_contact_sibling_wrapper_sound_seam(machine, registers, entry):
    """Construct a wrapper sound prefix with its exact local return facts."""
    if entry not in (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
        raise UnsupportedCandidate('unknown contact sibling sound wrapper')
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned contact sibling wrapper stack')
    _spans_disjoint([('contact sibling wrapper frame', sp - 10, 14),
                     ('contact sibling wrapper record', registers['a1'], 66),
                     *CONTACT_SIBLING_GLOBALS])
    read = lambda address, size: _read(machine, address, size)
    route = game.contact_sibling_route(read, registers['a1'])[0]
    if route in ('decrement', 'type13'):
        sibling_return = 0x1AE9CA if entry == CONTACT_SIBLING_WRAPPER else 0x1AE9DE
        callback = AtomicPlan(18, 1, _bytes(sp - 4, sibling_return, 4),
                              {**registers, 'a7': sp - 4, 'pc': CONTACT_SIBLING_ENTRY},
                              entry, direct_calls=1)
        sound = begin_contact_sibling_sound_seam(dispatch_plan_view(machine, callback), callback.registers)
        prefix = AtomicPlan(callback.cycles + sound.prefix.cycles,
                            callback.instructions + sound.prefix.instructions,
                            tuple(dict((*callback.writes, *sound.prefix.writes)).items()),
                            sound.prefix.registers, sound.prefix.last_pc,
                            callback.direct_calls + sound.prefix.direct_calls)
        return SoundSeam(prefix, sound.stack_basis, sound.resume_pc, sound.return_slot,
                         sound.saved_frame, sound.frame_size, sound.return_delta, sound.counts_contact,
                         finish_contact_sibling_wrapper_sound)
    if entry != CONTACT_SIBLING_WRAPPER or route != 'contact':
        raise UnsupportedCandidate('contact sibling wrapper is not on its contact arm')
    # BSR sibling + D8-zero return + TST/BNE + BSR contact.  The contact BSR
    # overwrites the earlier sibling return slot before the sound frame starts.
    contact_callback = AtomicPlan(106, 7, _bytes(sp - 4, CONTACT_DISPATCH_LOCAL_RETURN, 4),
                                  {**registers, 'a7': sp - 4, 'pc': CONTACT_ENTRY},
                                  CONTACT_SIBLING_WRAPPER, direct_calls=2)
    sound = begin_contact_sound(dispatch_plan_view(machine, contact_callback), contact_callback.registers)
    prefix = AtomicPlan(contact_callback.cycles + sound.cycles,
                        contact_callback.instructions + sound.instructions,
                        tuple(dict((*contact_callback.writes, *sound.writes)).items()), sound.registers,
                        sound.last_pc, contact_callback.direct_calls + sound.direct_calls)
    return SoundSeam(prefix, sp - 4, 0x1AE5B6, 0x1AE5B6, 24, 28, 28, True,
                     finish_contact_sibling_wrapper_sound)


def begin_contact_sibling_wrapper_sound(machine, registers, entry):
    """Enter a sibling wrapper's admitted command-31 or command-8 sound arm."""
    return begin_contact_sibling_wrapper_sound_seam(machine, registers, entry).prefix

def finish_contact_sibling_wrapper_sound(machine, registers):
    """Finish C6/DA's admitted contact or decrement sound suffix and RTS."""
    if registers['pc'] in (0x1AEC52, CONTACT_TYPE13_FIXED_RETURN):
        sibling = finish_contact_sibling_sound(machine, registers)
        local_sp, local_pc = sibling.registers['a7'], sibling.registers['pc']
        if local_pc == 0x1AE9CA:
            if _read(machine, 0xFFF0D8, 1) == 0:
                raise UnsupportedCandidate('contact sibling command8 wrapper D8 return')
            final = dict(sibling.registers)
            final.update(a7=local_sp + 4, pc=_read(machine, local_sp, 4) & 0xFFFFFF,
                         sr=_logic_sr(sibling.registers['sr'], _read(machine, 0xFFF0D8, 1), 1))
            return AtomicPlan(sibling.cycles + 42, sibling.instructions + 3, sibling.writes, final,
                              0x1A91C4, sibling.direct_calls)
        if local_pc == 0x1AE9DE:
            final = dict(sibling.registers)
            final.update(a7=local_sp + 4, pc=_read(machine, local_sp, 4) & 0xFFFFFF)
            return AtomicPlan(sibling.cycles + 16, sibling.instructions + 1, sibling.writes, final,
                              0x1AE9DE, sibling.direct_calls)
        raise UnsupportedCandidate('contact sibling command8 wrapper return identity')
    contact = finish_contact_sound(machine, registers)
    local_sp = contact.registers['a7']
    if contact.registers.get('pc') != CONTACT_DISPATCH_LOCAL_RETURN:
        raise UnsupportedCandidate('contact sibling wrapper local contact return')
    final = dict(contact.registers)
    final.update(a7=local_sp + 4, pc=_read(machine, local_sp, 4) & 0xFFFFFF)
    return AtomicPlan(contact.cycles + 16, contact.instructions + 1, contact.writes, final,
                      CONTACT_DISPATCH_LOCAL_RETURN, contact.direct_calls)


def begin_contact_sibling_dispatch_sound_seam(machine, registers, dispatch, entry):
    """Construct the table prefix and its measured sibling sound seam."""
    sp = registers['a7']
    if entry not in (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
        raise UnsupportedCandidate('unknown dispatched sibling sound wrapper')
    if dispatch.registers.get('pc') != entry or dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('contact sibling dispatch sound prefix identity')
    callback_registers = {**registers, **dispatch.registers}
    sound = begin_contact_sibling_wrapper_sound_seam(dispatch_plan_view(machine, dispatch),
                                                      callback_registers, entry)
    final = dict(dispatch.registers)
    final.update(sound.prefix.registers)
    prefix = AtomicPlan(dispatch.cycles + sound.prefix.cycles,
                        dispatch.instructions + sound.prefix.instructions,
                        tuple(dict((*dispatch.writes, *sound.prefix.writes)).items()), final,
                        sound.prefix.last_pc, dispatch.direct_calls + sound.prefix.direct_calls)
    return SoundSeam(prefix, sound.stack_basis, sound.resume_pc, sound.return_slot,
                     sound.saved_frame, sound.frame_size, sound.return_delta, sound.counts_contact,
                     sound.suffix)


def begin_contact_sibling_dispatch_sound(machine, registers, dispatch, entry):
    """Compose the table prefix with an admitted sibling sound prefix."""
    return begin_contact_sibling_dispatch_sound_seam(machine, registers, dispatch, entry).prefix

_CONTACT_RESET_BASE = {
    'be': (470, 33), 'd0': (526, 37), 'd7': (554, 39),
    'cd': (582, 41), 'd4': (610, 43), 'c1zero': (498, 35),
    'cc': (640, 45), 'efff': (690, 49), 'f11f': (714, 51),
    'pointer': (734, 51),
}
_CONTACT_REACTION_BASE = {
    'be': (310, 20), 'd0': (366, 24), 'd7': (394, 26),
    'cd': (422, 28), 'd4': (450, 30), 'c1zero': (338, 22),
    'direct': (454, 30),
}
_CONTACT_SOUND_PREFIX = {
    'be': (312, 19), 'd0': (368, 23), 'd7': (396, 25),
    'cd': (424, 27), 'd4': (452, 29), 'c1zero': (340, 21),
    'cc': (482, 31), 'efff': (532, 35), 'f11f': (556, 37),
    'pointer': (576, 37),
}


def _contact_decay_accounting(read, sr):
    """Return the exact aggregate cost and residue of reset's 1B03F2 calls."""
    count, counter = read(0xFF7E21, 1), read(0xFFEFFA, 1)
    calls = 1 + min(count, 2)
    residue = 0x1AE5C0 if count == 0 else 0x1AE5D0 if count == 1 else 0x1AE5E0
    blocker = read(0xFF7E20, 1)
    if blocker:
        # Calls reach 1B03F2's FF7E20 TST/RTS short path, with the caller's
        # intervening FF7E21 comparisons accounting for the later deltas.
        cycles, instructions = 214, 13
        if count:
            cycles += 140; instructions += 10
        if count > 1:
            cycles += 110; instructions += 8
        # The first and second exits follow CMP #0/#1, while a third returns
        # directly from 1B03F2 with the blocker's TST CCR.
        final_value = 0 if count <= 1 else blocker
        return cycles, instructions, residue, _logic_sr(sr, final_value, 1), calls
    cycles, instructions = (258, 16) if counter == 0 else (300, 19)
    if count:
        cycles += 116 if counter == 0 else 184 if counter == 1 else 188
        instructions += 8 if counter == 0 else 13 if counter == 1 else 14
    if count > 1:
        cycles += 86 if counter < 2 else 158
        instructions += 6 if counter < 2 else 12
    final_value = 0 if count <= 1 else 10 if counter == 0 else 0x28
    # SUBQ.B in the positive-counter path writes X; its following CMP leaves
    # that X result intact.  The zero-counter MOVE path does not alter X.
    final_sr = _logic_sr(sr & ~0x10 if counter else sr, final_value, 1)
    return cycles, instructions, residue, final_sr, calls


def _contact_guard(machine, registers, *, sound_frame=False):
    """Validate the caller frame before reading the contact live-RAM domain."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned contact stack')
    # A direct reset leaves a BSR return residue at SP-4 before its final RTS.
    # Guard it with the caller return rather than accepting a live-RAM alias.
    frame = ('contact sound frame', sp - 28, 32) if sound_frame else ('contact direct frame', sp - 4, 8)
    _spans_disjoint([frame, *CONTACT_GLOBALS])
    return lambda address, size: _read(machine, address, size)


def begin_contact(machine, registers):
    """Recover direct, non-sound 1AE4F8 contact gates through their RTS."""
    sp, sr = registers['a7'], registers['sr']
    read = _contact_guard(machine, registers)
    path, route = game.contact_route(read)
    if path == 'early':
        index = (0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2).index(route)
        return AtomicPlan(42 + 28 * index, 3 + 2 * index, (),
                          {'a7': sp + 4, 'pc': read(sp, 4) & 0xffffff,
                           'sr': _logic_sr(sr, read(route, 1), 1)},
                          CONTACT_ENTRY + 6 * index)
    if path == 'reaction':
        if route not in _CONTACT_REACTION_BASE:
            raise UnsupportedCandidate('contact reaction route')
        writes = game.contact_reaction(read)
        d8 = read(0xFFF0D8, 1)
        cycles, instructions = _CONTACT_REACTION_BASE[route]
        return AtomicPlan(cycles - 18 * bool(d8), instructions - bool(d8), tuple(writes),
                          {'a7': sp + 4, 'pc': read(sp, 4) & 0xffffff,
                           'sr': _logic_sr(sr, 1 if not d8 else d8, 1)},
                          0x1AE618 if not d8 else 0x1AE616)
    if path in ('reset', 'pointer_reset') and not read(0xFFF57D, 1):
        if route not in _CONTACT_RESET_BASE:
            raise UnsupportedCandidate('contact reset route')
        cycles, instructions = _CONTACT_RESET_BASE[route]
        decay_cycles, decay_instructions, bsr_return, final_sr, calls = _contact_decay_accounting(read, sr)
        cycles += decay_cycles - 300; instructions += decay_instructions - 19
        writes = (*game.contact_reset(read, pointer_reset=path == 'pointer_reset'),
                  *_bytes(sp - 4, bsr_return, 4))
        return AtomicPlan(cycles, instructions, tuple(writes),
                          {'a7': sp + 4, 'pc': read(sp, 4) & 0xffffff,
                           'sr': final_sr}, 0x1AE5E0,
                          direct_calls=calls)
    raise UnsupportedCandidate(f'contact {path} requires the synchronous reset seam')


def begin_contact_sound(machine, registers):
    """The recorded reset path through its existing command ``0x31`` seam."""
    sp, sr = registers['a7'], registers['sr']
    # This path constructs a full MOVEM/argument/JSR frame.  It must be safe
    # on its own because begin_contact deliberately declines this reset path.
    read = _contact_guard(machine, registers, sound_frame=True)
    path, route = game.contact_route(read)
    if path not in ('reset', 'pointer_reset') or not read(0xFFF57D, 1):
        raise UnsupportedCandidate('contact reset is outside the recorded sound seam')
    if route not in _CONTACT_SOUND_PREFIX:
        raise UnsupportedCandidate('contact sound route')
    writes = list(game.contact_reset(read, pointer_reset=path == 'pointer_reset', decay=False))
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        writes.extend(_bytes(sp - index * 4, registers[name], 4))
    writes.extend((*_bytes(sp - 24, 0x31, 4), *_bytes(sp - 28, 0x1AE5B0, 4)))
    cycles, instructions = _CONTACT_SOUND_PREFIX[route]
    return AtomicPlan(cycles, instructions, tuple(writes),
                      # The original MOVE-to-CCR clears N/Z/V/C but leaves X.
                      {'a7': sp - 28, 'pc': 0x1E58B8, 'sr': sr & ~0x0F}, 0x1AE5AA, direct_calls=1)


def finish_contact_sound(machine, registers):
    """1AE5B6: restore the command-31 frame, decay once, and return."""
    sp = registers['a7'] + 24
    if registers['pc'] != 0x1AE5B6:
        raise UnsupportedCandidate('foreign contact sound return')
    restored_frame = dict(registers, a7=sp)
    read = _contact_guard(machine, restored_frame, sound_frame=True)
    if read(sp - 28, 4) != 0x1AE5B6:
        raise UnsupportedCandidate('contact sound return slot')
    if read(0xFFF0E9, 1) or read(0xFFF0E6, 1) or read(0xFFF0F2, 1):
        raise UnsupportedCandidate('contact sound return domain')
    restored = dict(registers, a7=sp)
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        restored[name] = read(sp - index * 4, 4)
    cycles, instructions, bsr_return, final_sr, calls = _contact_decay_accounting(read, restored['sr'])
    writes = (*game.contact_repeated_decay(read), *_bytes(sp - 4, bsr_return, 4))
    return AtomicPlan(cycles, instructions, tuple(writes),
                      {**{name: restored[name] for name in ('d0', 'd1', 'a0', 'a1', 'a6')},
                       'a7': sp + 4, 'pc': read(sp, 4) & 0xffffff,
                       'sr': final_sr}, 0x1AE5DC,
                      direct_calls=calls)


def _add_sr(sr, left, right, width):
    mask, sign = (1 << (8 * width)) - 1, 1 << (8 * width - 1)
    total = left + right; result = total & mask
    out = _logic_sr(sr & ~0x1F, result, width)
    if total > mask: out |= 0x11
    if (~(left ^ right) & (left ^ result)) & sign: out |= 2
    return out


def _collection_guard(machine, registers):
    record, sp = registers['a1'], registers['a7']
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned collection record/stack')
    _spans_disjoint([('collection record', record, 66), ('collection frame', sp - 28, 32),
                     *COLLECTION_GLOBALS])
    return lambda address, size: _read(machine, address, size)


def _collection_suffix(machine, registers, entry):
    kind, resume, last, amount, template = COLLECTION_ROUTES[entry]
    sp, sr = registers['a7'], registers['sr']
    if kind == 'spawn':
        return _spawn_collection(machine, registers)
    if kind in ('timer100', 'flag100'):
        value = _read(machine, 0xFFF14E, 2)
        writes = (*_bytes(0xFFF14E, value + amount, 2),
                  *_bytes(sp - 4, 0x1AF382 if kind == 'timer100' else 0x1AF3BA, 4))
        if kind == 'flag100': writes += ((0xFFF179, 255),)
        return AtomicPlan(74 + 20 * (kind == 'flag100'), 4 + (kind == 'flag100'), writes,
            {'a7': sp+4, 'pc': _read(machine, sp, 4) & 0xFFFFFF,
             'sr': _add_sr(sr, value, amount, 2)}, last, direct_calls=1)
    if not template:
        return AtomicPlan(16, 1, (), {'a7': sp+4, 'pc': _read(machine, sp, 4) & 0xFFFFFF}, last)
    tail = replace_object(machine, registers, template=template, return_site=last,
                          amount=amount, extra_spans=COLLECTION_GLOBALS)
    branch = kind in ('primary', 'secondary', 'quarter', 'flag128', 'flag129', 'flag116', 'flag12a')
    return AtomicPlan(tail.cycles + 10 * branch, tail.instructions + branch,
                      tail.writes, tail.registers, tail.last_pc, tail.direct_calls)


def begin_collection(machine, registers, entry):
    """One collection entry: accepted state changes, optional original sound, retirement.

    Aggregate recipes cover actual straight-line paths. Internal clear/init/total
    calls compose through existing adapters; no per-instruction executor is used.
    """
    kind, resume, last, amount, template = COLLECTION_ROUTES[entry]
    read = _collection_guard(machine, registers)
    sp, sr, record = registers['a7'], registers['sr'], registers['a1']
    if kind == 'secondary' and read(0xFFF0D8, 1):
        return AtomicPlan(42, 3, (), {'sr': _logic_sr(sr, read(0xFFF0D8, 1), 1),
            'a7': sp+4, 'pc': read(sp, 4) & 0xFFFFFF}, 0x1A91C4), False
    if kind == 'quarter' and read(0xFFEFE0, 2) == 0x3939:
        return AtomicPlan(46, 3, (), {'sr': _logic_sr(sr, 0, 2),
            'a7': sp+4, 'pc': read(sp, 4) & 0xFFFFFF}, 0x1A91C4), False
    try:
        writes = game.collection_state(read, record, kind)
    except ValueError as error:
        raise UnsupportedCandidate(str(error)) from error
    # Before-sound instruction sums; variable decimal path uses its established recipe.
    cycles, instructions = {'flag25': (20, 1), 'flag128': (20, 1), 'flag129': (20, 1),
        'flag116': (20, 1), 'flag12a': (20, 1), 'count25': (20, 1), 'plain15': (0, 0),
        'reset15': (30, 2), 'flag177': (112, 6), 'flag178': (112, 6), 'spawn': (20, 1),
        'timer100': (20, 1), 'flag100': (0, 0), 'secondary': (76, 5),
        'quarter': (82, 5), 'primary': (48, 3)}[kind]
    direct = 1
    sound = read(0xFFF57D, 1)
    wants_sound = True
    if kind == 'count25': sr = _add_sr(sr, read(0xFFF003, 1), 1, 1)
    restored = dict(registers)
    if kind in ('primary', 'secondary', 'quarter'):
        wants_sound = kind != 'quarter' or ((read(0xFFF10A, 1) + 1) & 255) >= 4
        if kind == 'quarter': sr = _add_sr(sr, read(0xFFF10A, 1), 1, 1)
        if wants_sound:
            digits = read(0xFFEFE2 if kind == 'secondary' else 0xFFEFE0, 2)
            if digits == 0x3939:
                flag = read(record+52, 1)
                cycles = (152 if kind == 'primary' else 180) + (88 if flag else 0)
                instructions = (10 if kind == 'primary' else 12) + (8 if flag else 0)
                if flag:
                    table = (('object state table byte', writes[0][0], 1),)
                    _spans_disjoint([('sound frame', sp-28, 32), *COLLECTION_GLOBALS, *table])
                    _clear_objects(machine, registers, sp=sp-4, pair=True,
                                   extra_spans=(*COLLECTION_GLOBALS, *table), include_semantics=False)
                    restored['d0'] = (registers['d0'] & 0xFFFF0000) | read(record+50, 2)
                direct += 2
            else:
                cycles += 132 if digits & 255 == 0x39 else 94
                instructions += 8 if digits & 255 == 0x39 else 6
                if kind == 'quarter': cycles += 36; instructions += 2
                sr &= ~0x10
                direct += 1
    restored['sr'] = sr
    if kind in ('timer100', 'flag100'):
        init_return = 0x1AF35C if kind == 'timer100' else 0x1AF394
        retired = replace_object(machine, restored, return_site=init_return,
                                 extra_spans=COLLECTION_GLOBALS)
        cycles += retired.cycles - 16; instructions += retired.instructions - 1
        writes.extend(retired.writes); direct += retired.direct_calls
        restored.update(retired.registers, a7=sp)
        sr = restored['sr']
    if wants_sound:
        sr = _logic_sr(sr, sound, 1)
        cycles += 24 if sound else 26; instructions += 2
    if not (wants_sound and sound):
        suffix = _collection_suffix(machine, dict(restored, sr=sr), entry)
        final = dict(restored, sr=sr); final.update(suffix.registers)
        return AtomicPlan(cycles + suffix.cycles, instructions + suffix.instructions,
            tuple(dict((*writes, *suffix.writes)).items()), final, suffix.last_pc,
            direct + suffix.direct_calls), False
    sound_id = 13 if kind == 'secondary' else 12 if kind == 'quarter' else 103 if kind in (
        'flag128', 'flag129', 'flag116', 'flag12a') else (
        105 if kind in ('count25', 'flag25') else 11 if kind in ('primary', 'plain15', 'reset15') else 93 if kind == 'spawn' else 100)
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        writes.extend(_bytes(sp - index*4, restored[name], 4))
    writes.extend((*_bytes(sp-24, sound_id, 4), *_bytes(sp-28, resume-6, 4)))
    final = dict(restored, a7=sp-28, pc=0x1E58B8, sr=sr)
    return AtomicPlan(cycles+84, instructions+3, tuple(dict(writes).items()), final,
                      resume-12, direct), True


def finish_collection(machine, registers, entry):
    sp = registers['a7'] + 24
    restored = dict(registers, a7=sp)
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        restored[name] = _read(machine, sp-index*4, 4)
    _collection_guard(machine, restored)
    suffix = _collection_suffix(machine, restored, entry)
    final = {name: restored[name] for name in ('d0', 'd1', 'a0', 'a1', 'a6')}
    final.update(suffix.registers)
    return AtomicPlan(60+suffix.cycles, 2+suffix.instructions, suffix.writes, final,
                      suffix.last_pc, suffix.direct_calls)


def relocate_collection(machine, registers):
    """1AF516: search six secondary slots, then move the complete object record."""
    record, sp, sr, d0 = (registers[k] for k in ('a1', 'a7', 'sr', 'd0'))
    read = _collection_guard(machine, registers)
    _spans_disjoint([('source object', record, 66), ('secondary pool', 0xFF84B2, 396),
                     ('relocation frame', sp-4, 8)])
    destination, index = game.free_object(read, 0xFF84B2, 6)
    writes = list(_bytes(sp-4, 0x1AF51A, 4))
    if destination is None:
        return AtomicPlan(324, 30, tuple(writes),
            {'d0': (d0 & 0xFFFF0000) | 0xFFFF, 'a5': 0xFF863E,
             'sr': _logic_sr(sr, read(0xFF85FC, 1), 1),
             'a7': sp+4, 'pc': read(sp, 4) & 0xFFFFFF}, 0x1AF53C, direct_calls=1)
    writes = (*writes, *_bytes(sp-4, record, 4), *game.relocate_object(read, record, destination))
    return AtomicPlan(922+40*index, 81+4*index, tuple(dict(writes).items()),
        {'d0': (d0 & 0xFFFF0000) | (5-index), 'd7': registers['d7'] | 0xFFFF,
         'a5': destination+66, 'sr': _logic_sr(sr, 0, 1),
                      'a7': sp+4, 'pc': read(sp, 4) & 0xFFFFFF}, 0x1AF53C, direct_calls=2)


def _spawn_collection(machine, registers):
    record, sp, sr, d0 = (registers[k] for k in ('a1', 'a7', 'sr', 'd0'))
    read = _collection_guard(machine, registers)
    _spans_disjoint([('primary pool', 0xFF7E82, 24*66), ('spawn frame', sp-4, 8), *COLLECTION_GLOBALS])
    if record < 0xFF84B2 and record+66 > 0xFF7E82 and (record-0xFF7E82) % 66:
        raise UnsupportedCandidate('source partially overlaps primary pool slots')
    # The preceding activation makes the source occupied before searching.
    # No mutable mirror: this one known read dependency is explicit in the search.
    destination, index = game.free_object(read, 0xFF7E82, 24, occupied=record)
    writes = [*game.activate_collection(record), *_bytes(sp-4, 0x1AF44E, 4)]
    if destination is None:
        value = 0x84 if record == 0xFF8470 else read(0xFF8470, 1)
        return AtomicPlan(1152, 108, tuple(writes),
            {'d0': (d0 & 0xFFFF0000) | 0xFFFF, 'a5': 0xFF84B2,
             'sr': _logic_sr(sr, value, 1), 'a7': sp+4, 'pc': read(sp, 4) & 0xFFFFFF},
            0x1AF466, direct_calls=2)
    _spans_disjoint([('source record', record, 66), ('spawned record', destination, 66)])
    template = machine.peek_rom(0x1B7CC4, 19)
    writes.extend((*game.spawn_collection(read, record, destination, template), *_bytes(sp-4, 0x1AF45A, 4)))
    return AtomicPlan(750+40*index, 45+4*index, tuple(dict(writes).items()),
        {'d0': (d0 & 0xFFFF0000) | (23-index), 'a5': destination, 'a6': 0x1B7CD7,
         'sr': _logic_sr(sr, read(record+4, 2), 2), 'a7': sp+4, 'pc': read(sp, 4) & 0xFFFFFF},
        0x1AF466, direct_calls=4)
