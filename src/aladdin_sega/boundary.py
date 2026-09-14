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
COLLECTION_TYPE3A_ENTRY = 0x1AF228
COLLECTION_DISPATCH_ENTRY = 0x1ABC82
COLLECTION_DISPATCH_RETURN = 0x1ABCA0
CONTACT_COMPLETION_EXIT = 0x1ABD74
CONTACT_SCAN_ENTRY = 0x1ABBD6
CONTACT_SCAN_EXIT = 0x1ABD7C
CONTACT_STEP_ENTRY = 0x1ABB40
COLLECTION_DISPATCH_TABLE = 0x1CBE
CONTACT_ENTRY = 0x1AE4F8
CONTACT_DISPATCH_ENTRY = 0x1AE9D4
CONTACT_DISPATCH_LOCAL_RETURN = 0x1AE9D8
CONTACT_SIBLING_WRAPPER = 0x1AE9C6
CONTACT_SIBLING_DIRECT = 0x1AE9DA
CONTACT_SIBLING_ENTRY = 0x1AEC00
CONTACT_SIBLING_RETIREMENT = 0x1AECD8
CONTACT_SIBLING_TAIL = 0x1AED0C
CONTACT_ACTIVATION_ENTRY = 0x1AFD84
CONTACT_ACTIVATION_TAIL = 0x1AE6B4
CONTACT_FAMILY_66_ENTRY = 0x1AFBF4
CONTACT_FAMILY_MOTION_ENTRY = 0x1AF978
CONTACT_FAMILY_SECONDARY_MOTION_ENTRY = 0x1AF9F6
CONTACT_FAMILY_SOUND_ENTRY = 0x1AFC4E
CONTACT_FAMILY_TYPE79_ENTRY = 0x1AEB7C
CONTACT_FAMILY_TYPE1F_ENTRY = 0x1AE796
CONTACT_FAMILY_TYPE15_ENTRY = 0x1AE978
CONTACT_FAMILY_TYPE44_ENTRY = 0x1AEF12
CONTACT_FAMILY_TYPE03_ENTRY = 0x1AED86
CONTACT_FAMILY_TYPE46_ENTRY = 0x1AEF5C
CONTACT_FAMILY_TYPE55_ENTRY = 0x1AF590
CONTACT_FAMILY_TYPE58_ENTRY = 0x1AF5F0
CONTACT_FAMILY_TYPE63_ENTRY = 0x1AF81C
CONTACT_FAMILY_TYPE74_ENTRY = 0x1AFA84
CONTACT_TYPE74_POOL = 0xFF7F06
CONTACT_TYPE74_POOL_COUNT = 20
CONTACT_FAMILY_TYPE6E_ENTRY = 0x1AFB36
CONTACT_FAMILY_TYPE1A_ENTRY = 0x1AE9E0
CONTACT_FAMILY_TYPE23_ENTRY = 0x1AEECA
CONTACT_FAMILY_TYPE0D_ENTRY = 0x1AEB7A
CONTACT_FAMILY_TYPE14_ENTRY = 0x1AEBFE
CONTACT_FAMILY_TYPE0C_ENTRY = 0x1AE9A8
CONTACT_FAMILY_TYPE78_ENTRY = 0x1AEBDC
CONTACT_FAMILY_TYPE2C_ENTRY = 0x1AEE40
CONTACT_TYPE74_TEMPLATE = 0x1B7E7C
CONTACT_FAMILY_TYPE43_ENTRY = 0x1AE64C
CONTACT_COLLECTION_RELOCATION_ENTRY = 0x1AF516
CONTACT_TYPE7E_ENTRY = 0x1AFE1C
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
SPAWN_DISPATCH_ITERATION_ENTRY = 0x1AE468
SPAWN_DISPATCH_ITERATION_LAST_PC = 0x1AE478
SPAWN_DISPATCH_CALL_ENTRY = 0x1AE46C
SPAWN_DISPATCH_CALL_LAST_PC = 0x1AE46E
SPAWN_DISPATCH_WALKER_ENTRY = 0x1AE44A
SPAWN_DISPATCH_WALKER_LAST_PC = 0x1AE47C
SPAWN_ROW_DISPATCH_WALKER_ENTRY = 0x1AE4C6
SPAWN_ROW_DISPATCH_WALKER_LAST_PC = 0x1AE4F6
SPAWN_SETUP_LEFT_ENTRY = 0x1AE3FC
SPAWN_SETUP_RIGHT_ENTRY = 0x1AE406
SPAWN_SETUP_ROW_LOW_ENTRY = 0x1AE47E
SPAWN_SETUP_ROW_HIGH_ENTRY = 0x1AE488
SPAWN_UPPER_VARIANT_CALLER_ENTRY = 0x1B7262
SPAWN_UPPER_VARIANT_CALLER_LAST_PC = 0x1B728C
SPAWN_UPPER_SCRIPTED_CALLER_ENTRY = 0x1B72D4
SPAWN_UPPER_SCRIPTED_CALLER_LAST_PC = 0x1B72FA
SPAWN_REVERSE_PLAIN_CALLER_ENTRY = 0x1B7232
SPAWN_REVERSE_PLAIN_CALLER_LAST_PC = 0x1B723C
SPAWN_UPPER_PLAIN_CALLER_ENTRY = 0x1B6F76
SPAWN_UPPER_PLAIN_CALLER_LAST_PC = 0x1B6F80
SPAWN_UPPER_STANDARD_CALLER_ENTRY = 0x1B6E7A
SPAWN_UPPER_STANDARD_CALLER_LAST_PC = 0x1B6E84
SPAWN_UPPER_SECONDARY_CALLER_ENTRY = 0x1B6E90
SPAWN_UPPER_SECONDARY_CALLER_LAST_PC = 0x1B6E9A
SPAWN_UPPER_TERTIARY_CALLER_ENTRY = 0x1B6EA6
SPAWN_UPPER_TERTIARY_CALLER_LAST_PC = 0x1B6EB0
SPAWN_UPPER_TYPED_CALLER_ENTRY = 0x1B6EB2
SPAWN_UPPER_TYPED_CALLER_LAST_PC = 0x1B6ECE
SPAWN_UPPER_TYPED_SECONDARY_ENTRY = 0x1B6ED0
SPAWN_UPPER_TYPED_SECONDARY_LAST_PC = 0x1B6EEC
SPAWN_LOWER_RESET_ENTRY = 0x1B6F0C
SPAWN_LOWER_SCRIPTED_ENTRY = 0x1B6F1E
SPAWN_UPPER_CALLER_ENTRY = 0x1B735E
SPAWN_UPPER_CALLER_LAST_PC = 0x1B7388
SPAWN_UPPER_GUARD_ENTRY = 0x1B7354
SPAWN_UPPER_GUARD_LAST_PC = 0x1B6EB0
SPAWN_PRIMARY_DISPATCH_ENTRY = 0x1B7434
SPAWN_PRIMARY_DISPATCH_LAST_PC = 0x1B7448
SPAWN_PRIMARY_GUARD_ENTRY = 0x1B742A
SPAWN_PRIMARY_GUARD_LAST_PC = 0x1B6EB0
SPAWN_LOWER_DISPATCH_ENTRY = 0x1B74D6
SPAWN_LOWER_DISPATCH_LAST_PC = 0x1B74E0
SPAWN_PLAIN_LOWER_ONE_ENTRY = 0x1B700C
SPAWN_PLAIN_UPPER_ENTRY = 0x1B6D84
SPAWN_PLAIN_LOWER_TWO_ENTRY = 0x1B6726
SPAWN_PLAIN_REVERSE_ENTRY = 0x1B68CA
SPAWN_PLAIN_PRIMARY_ENTRY = 0x1B6C4E
SPAWN_PLAIN_LOWER_THREE_ENTRY = 0x1B65D4
SPAWN_PLAIN_REVERSE_TWO_ENTRY = 0x1B668A
SPAWN_PLAIN_REVERSE_THREE_ENTRY = 0x1B688A
SPAWN_PLAIN_LOWER_FOUR_ENTRY = 0x1B6864
SPAWN_PLAIN_LOWER_FIVE_ENTRY = 0x1B674A
SPAWN_PLAIN_UPPER_TWO_ENTRY = 0x1B7000
SPAWN_PLAIN_UPPER_THREE_ENTRY = 0x1B673E
SPAWN_OFFSET_PLUS_ENTRY = 0x1B66F2
SPAWN_OFFSET_MIXED_ENTRY = 0x1B670C
SPAWN_OFFSET_SECONDARY_ENTRY = 0x1B6870
SPAWN_CLOSURE_LOWER_ENTRY = 0x1B723E
SPAWN_CLOSURE_UPPER_ENTRY = 0x1B728E
SPAWN_CLOSURE_REVERSE_ENTRY = 0x1B72AE
SPAWN_CLOSURE_UPPER_CLEAR_ENTRY = 0x1B70D4
SPAWN_CLOSURE_GUARD_ENTRY = 0x1B71A0
SPAWN_CLOSURE_REVERSE_SCRIPT_ENTRY = 0x1B6696
SPAWN_CLOSURE_REVERSE_SCRIPT_A_ENTRY = 0x1B6F4A
SPAWN_CLOSURE_REVERSE_SCRIPT_B_ENTRY = 0x1B6F34
SPAWN_CLOSURE_SAFE_RETURN_ENTRY = 0x1B65BE
SPAWN_UPPER_DISPATCH_GUARD_ENTRY = 0x1B744A
SPAWN_UPPER_DISPATCH_GUARD_LAST_PC = 0x1B6EB0
SPAWN_PRIMARY_DOUBLE_GUARD_ENTRY = 0x1B738A
SPAWN_PRIMARY_DOUBLE_GUARD_LAST_PC = 0x1B73C0
SPAWN_PRIMARY_INVERSE_GUARD_ENTRY = 0x1B73C2
SPAWN_PRIMARY_INVERSE_GUARD_LAST_PC = 0x1B73F0
SPAWN_PRIMARY_MIXED_GUARD_ENTRY = 0x1B73F2
SPAWN_PRIMARY_MIXED_GUARD_LAST_PC = 0x1B7428
SPAWN_UPPER_DISPATCH_ENTRY = 0x1B7454
SPAWN_UPPER_DISPATCH_LAST_PC = 0x1B7472
SPAWN_UPPER_TILE_CALLER_ENTRY = 0x1B6C0E
SPAWN_UPPER_TILE_CALLER_LAST_PC = 0x1B6C2C
SPAWN_UPPER_TILE_CALLER_TEMPLATE = 0x1B7A80
SPAWN_CAP_GUARD_TWO_ENTRY = 0x1B72FC
SPAWN_CAP_GUARD_TWO_LAST_PC = 0x1B7330
SPAWN_LOWER_OFFSET_CALLER_ENTRY = 0x1B71C4
SPAWN_LOWER_OFFSET_CALLER_LAST_PC = 0x1B71DE
SPAWN_UPPER_TILE_WORD_CALLER_ENTRY = 0x1B6FAE
SPAWN_UPPER_TILE_WORD_CALLER_EARLY_PC = 0x1B6FD8
SPAWN_UPPER_TILE_WORD_CALLER_LAST_PC = 0x1B6FE0
SPAWN_UPPER_TILE_WORD_CALLER_TEMPLATE = 0x1B81EC
SPAWN_REVERSE_GUARD_CALLER_ENTRY = 0x1B6756
SPAWN_REVERSE_GUARD_CALLER_LAST_PC = 0x1B6792
SPAWN_REVERSE_GUARD_CALLER_TEMPLATE = 0x1B7DDC
SPAWN_REVERSE_Y_OFFSET_CALLER_ENTRY = 0x1B65C0
SPAWN_REVERSE_Y_OFFSET_CALLER_LAST_PC = 0x1B65D2
SPAWN_REVERSE_Y_OFFSET_CALLER_TEMPLATE = 0x1B7D14
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
    x_base, x_offset = read(0xFFF150, 2), read(0xFF7DB0, 2)
    y_base, y_offset = read(0xFFF152, 2), read(0xFF7DB2, 2)
    x = (x_base + x_offset) & 0xFFFF
    y = (y_base + y_offset) & 0xFFFF
    # The final coordinate ADD.W is the last X-writing instruction.  The
    # indexed CLR.B sets Z but preserves that arithmetic X residue.
    coordinate_sr = _logic_sr(_add_sr(sr, y_base, y_offset, 2), 0, 1)
    writes = (*_bytes(sp - 4, 0x1B5270, 4),
              *game.spawn_region(destination, template, d2, d3, x, y, clear_address))
    scan_cycles, scan_instructions = 54 + 40 * index, 5 + 4 * index
    return AtomicPlan(scan_cycles + free_fixed_cycles, scan_instructions + free_fixed_instructions,
                      tuple(dict(writes).items()),
                      {**registers, 'd0': (d0 & 0xFFFF0000) | (y & 0xFF00),
                       'a5': destination, 'a6': a6 + 19, 'a7': sp + 4,
                       'pc': return_pc & 0xFFFFFF, 'sr': coordinate_sr},
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


def spawn_upper_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover table callback 1B735E through its upper-pool creation suffix."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned upper spawn caller stack')
    _spans_disjoint([('upper spawn caller pool', 0xFF7E82, 24 * 66),
                     ('upper spawn caller frame', sp - 8, 12),
                     *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    cap = _read(machine, 0xFFEFE0, 2)
    compare_sr = (_sub_sr(registers['sr'], cap, 0x3939, 2) & ~0x10) | (registers['sr'] & 0x10)
    if compare_sr & 4:
        return AtomicPlan(46, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': compare_sr},
                          SPAWN_UPPER_CALLER_LAST_PC)
    prefix = AtomicPlan(66, 4, _bytes(sp - 4, 0x1B7374, 4),
                        {**registers, 'a6': 0x1B79B8, 'a7': sp - 4,
                         'pc': SPAWN_REGION_UPPER_ENTRY}, 0x1B7370, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_UPPER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 22,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_UPPER_CALLER_LAST_PC, prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_upper_spawn(final['a5']))
    # MOVE/CLR suffixes preserve the allocator tail's coordinate ADD.W X.
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 0, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 72,
                      prefix.instructions + selected.instructions + 5,
                      tuple(dict((*writes, *suffix)).items()), final, SPAWN_UPPER_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_upper_guard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B7354``'s observed guard and its established fallthrough.

    A zero ``FFF171`` takes the distant RTS directly.  A nonzero value only
    contributes the TST/BEQ prefix before entering the already qualified
    upper-pool caller at ``1B735E``.
    """
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned upper guard caller stack')
    outer = _read(machine, sp, 4)
    guard = _read(machine, 0xFFF171, 1)
    tested_sr = _logic_sr(registers['sr'], guard, 1)
    if guard == 0:
        return AtomicPlan(42, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': tested_sr},
                          SPAWN_UPPER_GUARD_LAST_PC)
    prefix = AtomicPlan(28, 2, (), {**registers, 'pc': SPAWN_UPPER_CALLER_ENTRY,
                                     'sr': tested_sr}, 0x1B735A)
    selected = spawn_upper_caller(dispatch_plan_view(machine, prefix), prefix.registers)
    return AtomicPlan(prefix.cycles + selected.cycles,
                      prefix.instructions + selected.instructions, selected.writes,
                      selected.registers, selected.last_pc,
                      prefix.direct_calls + selected.direct_calls)


def spawn_primary_dispatch_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B7434``'s slot predicate and primary-pool allocation."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned primary dispatch caller stack')
    outer = _read(machine, sp, 4)
    slot_type = _read(machine, 0xFF7E3C, 1)
    compare_sr = (_sub_sr(registers['sr'], slot_type, 0x39, 1) & ~0x10) | (registers['sr'] & 0x10)
    if compare_sr & 4:
        return AtomicPlan(46, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': compare_sr},
                          SPAWN_PRIMARY_DISPATCH_LAST_PC)
    prefix = AtomicPlan(58, 4, _bytes(sp - 4, 0x1B7448, 4),
                        {**registers, 'a6': 0x1B79CC, 'a7': sp - 4,
                         'pc': SPAWN_REGION_ENTRY}, 0x1B7444, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_ENTRY)
    final = dict(selected.registers)
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
    return AtomicPlan(prefix.cycles + selected.cycles + 16,
                      prefix.instructions + selected.instructions + 1,
                      tuple(dict((*prefix.writes, *selected.writes)).items()), final,
                      SPAWN_PRIMARY_DISPATCH_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_primary_guard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B742A``'s guard before the primary dispatcher callback."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned primary guard caller stack')
    outer = _read(machine, sp, 4)
    guard = _read(machine, 0xFFF172, 1)
    tested_sr = _logic_sr(registers['sr'], guard, 1)
    if guard == 0:
        return AtomicPlan(42, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': tested_sr},
                          SPAWN_PRIMARY_GUARD_LAST_PC)
    prefix = AtomicPlan(28, 2, (), {**registers, 'pc': SPAWN_PRIMARY_DISPATCH_ENTRY,
                                     'sr': tested_sr}, 0x1B7430)
    selected = spawn_primary_dispatch_caller(dispatch_plan_view(machine, prefix), prefix.registers)
    return AtomicPlan(prefix.cycles + selected.cycles,
                      prefix.instructions + selected.instructions, selected.writes,
                      selected.registers, selected.last_pc,
                      prefix.direct_calls + selected.direct_calls)


# These are concrete ROM facts, not a generic calling-convention layer. Every
# row has the same twelve-byte LEA absolute / BSR word / RTS wrapper shape.
SPAWN_PLAIN_CALLER_FACTS = {
    SPAWN_REVERSE_PLAIN_CALLER_ENTRY: (SPAWN_REGION_REVERSE_ENTRY, 0x1B79E0),
    SPAWN_UPPER_PLAIN_CALLER_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B80AC),
    SPAWN_UPPER_STANDARD_CALLER_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B7C10),
    SPAWN_UPPER_SECONDARY_CALLER_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B7C24),
    SPAWN_UPPER_TERTIARY_CALLER_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B7C38),
    SPAWN_LOWER_DISPATCH_ENTRY: (SPAWN_REGION_LOWER_ENTRY, 0x1B7A30),
    SPAWN_PLAIN_LOWER_ONE_ENTRY: (SPAWN_REGION_LOWER_ENTRY, 0x1B80FC),
    SPAWN_PLAIN_UPPER_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B7F30),
    SPAWN_PLAIN_LOWER_TWO_ENTRY: (SPAWN_REGION_LOWER_ENTRY, 0x1B8070),
    SPAWN_PLAIN_REVERSE_ENTRY: (SPAWN_REGION_REVERSE_ENTRY, 0x1B7C9C),
    SPAWN_PLAIN_PRIMARY_ENTRY: (SPAWN_REGION_ENTRY, 0x1B7A6C),
    SPAWN_PLAIN_LOWER_THREE_ENTRY: (SPAWN_REGION_LOWER_ENTRY, 0x1B82B4),
    SPAWN_PLAIN_REVERSE_TWO_ENTRY: (SPAWN_REGION_REVERSE_ENTRY, 0x1B8084),
    SPAWN_PLAIN_REVERSE_THREE_ENTRY: (SPAWN_REGION_REVERSE_ENTRY, 0x1B7B0C),
    SPAWN_PLAIN_LOWER_FOUR_ENTRY: (SPAWN_REGION_LOWER_ENTRY, 0x1B7AE4),
    SPAWN_PLAIN_LOWER_FIVE_ENTRY: (SPAWN_REGION_LOWER_ENTRY, 0x1B7E68),
    SPAWN_PLAIN_UPPER_TWO_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B8020),
    SPAWN_PLAIN_UPPER_THREE_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B7DB4),
}
SPAWN_PLAIN_CALLER_ENTRIES = tuple(SPAWN_PLAIN_CALLER_FACTS)

# Three observed lower-pool wrappers have one more position-adjustment suffix.
SPAWN_OFFSET_CALLER_FACTS = {
    SPAWN_OFFSET_PLUS_ENTRY: (0x1B7A1C, 8, 12),
    SPAWN_OFFSET_MIXED_ENTRY: (0x1B7E54, -8, 4),
    SPAWN_OFFSET_SECONDARY_ENTRY: (0x1B7B34, 9, 7),
}
SPAWN_OFFSET_CALLER_ENTRIES = tuple(SPAWN_OFFSET_CALLER_FACTS)

# The remaining dispatcher callbacks have distinct ROM suffixes.  The raw
# instruction images are part of the admission facts, rather than a decoder.
SPAWN_CLOSURE_CALLER_FACTS = {
    SPAWN_CLOSURE_LOWER_ENTRY: (SPAWN_REGION_LOWER_ENTRY, 0x1B79E0,
        bytes.fromhex('4df9001b79e06100e018660c1abc008a2b7c0012449400204e75'),
        game.finish_type_8a_spawn, 60, 4, 0x1B7256, (0x00124494, 4)),
    SPAWN_CLOSURE_UPPER_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B79B8,
        bytes.fromhex('4df9001b79b86100dfd066121abc00412b7c00125d7e00201b7c000200294e75'),
        game.finish_type_41_spawn, 76, 5, 0x1B72AC, (2, 1)),
    SPAWN_CLOSURE_REVERSE_ENTRY: (SPAWN_REGION_REVERSE_ENTRY, 0x1B79B8,
        bytes.fromhex('4df9001b79b86100dfa066181abc00841b7c002100062b7c00123e7a00201b7c000200294e75'),
        game.finish_type_84_spawn, 92, 6, 0x1B72D2, (2, 1)),
    SPAWN_CLOSURE_UPPER_CLEAR_ENTRY: (SPAWN_REGION_UPPER_ENTRY, 0x1B79B8,
        bytes.fromhex('4df9001b79b86100e18a66161abc004c2b7c00123e36002042ad000a1b7c000100294e75'),
        game.finish_type_4c_spawn, 100, 6, 0x1B70F6, (1, 1)),
    SPAWN_CLOSURE_REVERSE_SCRIPT_ENTRY: (SPAWN_REGION_REVERSE_ENTRY, 0x1B8084,
        bytes.fromhex('4df9001b80846100ebb866082b7c0012534800204e75'),
        game.finish_reverse_script_spawn, 48, 3, 0x1B66AA, (0x00125348, 4)),
    SPAWN_CLOSURE_REVERSE_SCRIPT_A_ENTRY: (SPAWN_REGION_REVERSE_ENTRY, 0x1B8264,
        bytes.fromhex('4df9001b82646100e30466082b7c00125a8800204e75'),
        game.finish_reverse_script_a_spawn, 48, 3, 0x1B6F5E, (0x00125a88, 4)),
    SPAWN_CLOSURE_REVERSE_SCRIPT_B_ENTRY: (SPAWN_REGION_REVERSE_ENTRY, 0x1B8264,
        bytes.fromhex('4df9001b82646100e31a66082b7c00125a6800204e75'),
        game.finish_reverse_script_b_spawn, 48, 3, 0x1B6F48, (0x00125a68, 4)),
}


def _plain_wrapper_shape(machine, entry, allocator, template):
    raw = machine.peek_rom(entry, 12)
    if (raw[:2] != bytes.fromhex('4df9') or
            int.from_bytes(raw[2:6], 'big') != template or raw[6:8] != bytes.fromhex('6100') or
            entry + 8 + int.from_bytes(raw[8:10], 'big', signed=True) != allocator or
            raw[10:12] != bytes.fromhex('4e75')):
        raise UnsupportedCandidate('plain spawn wrapper ROM shape')


def spawn_plain_caller(machine, registers: dict[str, int], entry: int) -> AtomicPlan:
    """Recover one ROM-validated LEA/BSR/RTS allocator wrapper."""
    try:
        allocator, template = SPAWN_PLAIN_CALLER_FACTS[entry]
    except KeyError as error:
        raise UnsupportedCandidate('unknown plain spawn caller') from error
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned plain spawn caller stack')
    _plain_wrapper_shape(machine, entry, allocator, template)
    _spans_disjoint([('plain spawn caller pool', 0xFF7E82, 24 * 66),
                     ('plain spawn caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, entry + 10, 4),
                        {**registers, 'a6': template, 'a7': sp - 4, 'pc': allocator},
                        entry + 6, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers, allocator)
    final = dict(selected.registers)
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
    return AtomicPlan(prefix.cycles + selected.cycles + 16,
                      prefix.instructions + selected.instructions + 1,
                      tuple(dict((*prefix.writes, *selected.writes)).items()), final,
                      entry + 10, prefix.direct_calls + selected.direct_calls)


def _offset_wrapper_shape(machine, entry, template, x_delta, y_delta):
    raw = machine.peek_rom(entry, 26)
    x_opcode = bytes.fromhex('046d' if x_delta < 0 else '066d')
    if (raw[:2] != bytes.fromhex('4df9') or
            int.from_bytes(raw[2:6], 'big') != template or raw[6:8] != bytes.fromhex('6100') or
            entry + 8 + int.from_bytes(raw[8:10], 'big', signed=True) != SPAWN_REGION_LOWER_ENTRY or
            raw[10:12] != bytes.fromhex('660c') or raw[12:14] != x_opcode or
            int.from_bytes(raw[14:16], 'big') != abs(x_delta) or raw[16:18] != bytes.fromhex('0002') or
            raw[18:20] != bytes.fromhex('066d') or
            int.from_bytes(raw[20:22], 'big') != y_delta or raw[22:24] != bytes.fromhex('0004') or
            raw[24:26] != bytes.fromhex('4e75')):
        raise UnsupportedCandidate('offset spawn caller ROM shape')


def spawn_offset_caller(machine, registers: dict[str, int], entry: int) -> AtomicPlan:
    """Recover an observed lower allocation followed by signed position offsets."""
    try:
        template, x_delta, y_delta = SPAWN_OFFSET_CALLER_FACTS[entry]
    except KeyError as error:
        raise UnsupportedCandidate('unknown offset spawn caller') from error
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned offset spawn caller stack')
    _offset_wrapper_shape(machine, entry, template, x_delta, y_delta)
    _spans_disjoint([('offset spawn caller pool', 0xFF7E82, 24 * 66),
                     ('offset spawn caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, entry + 10, 4),
                        {**registers, 'a6': template, 'a7': sp - 4,
                         'pc': SPAWN_REGION_LOWER_ENTRY}, entry + 6, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_LOWER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (selected.registers['sr'] & 0x04):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          entry + 24, prefix.direct_calls + selected.direct_calls)
    planned = dispatch_plan_view(machine, AtomicPlan(prefix.cycles + selected.cycles,
                                                      prefix.instructions + selected.instructions,
                                                      writes, final, selected.last_pc,
                                                      prefix.direct_calls + selected.direct_calls))
    y_before = _read(planned, final['a5'] + 4, 2)
    offsets = tuple(game.offset_spawn_position(
        lambda address, size: _read(planned, address, size), final['a5'], x_delta, y_delta))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF,
                 sr=_add_sr(selected.registers['sr'], y_before, y_delta, 2))
    return AtomicPlan(prefix.cycles + selected.cycles + 64,
                      prefix.instructions + selected.instructions + 4,
                      tuple(dict((*writes, *offsets)).items()), final, entry + 24,
                      prefix.direct_calls + selected.direct_calls + 1)


def spawn_closure_caller(machine, registers: dict[str, int], entry: int) -> AtomicPlan:
    """Recover one verified remaining allocator callback through its parent dispatcher."""
    try:
        allocator, template, shape, finish, suffix_cycles, suffix_instructions, last_pc, ccr = SPAWN_CLOSURE_CALLER_FACTS[entry]
    except KeyError as error:
        raise UnsupportedCandidate('unknown closure spawn caller') from error
    sp = registers['a7']
    if sp & 1 or machine.peek_rom(entry, len(shape)) != shape:
        raise UnsupportedCandidate('closure spawn caller ROM shape')
    _spans_disjoint([('closure spawn caller pool', 0xFF7E82, 24 * 66),
                     ('closure spawn caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, entry + 10, 4),
                        {**registers, 'a6': template, 'a7': sp - 4, 'pc': allocator},
                        entry + 6, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers, allocator)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers); final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
    if not (final['sr'] & 4):
        return AtomicPlan(prefix.cycles + selected.cycles + 26, prefix.instructions + selected.instructions + 2,
                          writes, final, last_pc, prefix.direct_calls + selected.direct_calls)
    suffix = tuple(finish(final['a5']))
    final['sr'] = _logic_sr(final['sr'], ccr[0], ccr[1])
    return AtomicPlan(prefix.cycles + selected.cycles + suffix_cycles,
                      prefix.instructions + selected.instructions + suffix_instructions,
                      tuple(dict((*writes, *suffix)).items()), final, last_pc,
                      prefix.direct_calls + selected.direct_calls + 1)


def spawn_closure_guard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover 1B71A0's FFF12A guard and its lower-pool successful suffix."""
    entry, sp = SPAWN_CLOSURE_GUARD_ENTRY, registers['a7']
    shape = bytes.fromhex('4a3900fff12a671a4df9001b78f06100e0ae660e2b7c001243180020046d000800044e75')
    if sp & 1 or machine.peek_rom(entry, len(shape)) != shape:
        raise UnsupportedCandidate('closure guarded spawn ROM shape')
    outer, guard = _read(machine, sp, 4), _read(machine, 0xFFF12A, 1)
    tested_sr = _logic_sr(registers['sr'], guard, 1)
    if guard == 0:
        return AtomicPlan(42, 3, (), {**registers, 'a7': sp + 4, 'pc': outer & 0xFFFFFF, 'sr': tested_sr}, 0x1B71C2)
    _spans_disjoint([('closure guarded spawn pool', 0xFF7E82, 24 * 66), ('closure guard frame', sp - 8, 12),
                     ('closure guard flag', 0xFFF12A, 1), *SPAWN_REGION_GLOBALS])
    prefix = AtomicPlan(54, 4, _bytes(sp - 4, 0x1B71B2, 4),
                        {**registers, 'a6': 0x1B78F0, 'a7': sp - 4, 'pc': SPAWN_REGION_LOWER_ENTRY, 'sr': tested_sr},
                        0x1B71AE, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers, SPAWN_REGION_LOWER_ENTRY)
    writes, final = tuple(dict((*prefix.writes, *selected.writes)).items()), dict(selected.registers)
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
    if not (final['sr'] & 4):
        return AtomicPlan(prefix.cycles + selected.cycles + 26, prefix.instructions + selected.instructions + 2,
                          writes, final, 0x1B71C2, prefix.direct_calls + selected.direct_calls)
    view = dispatch_plan_view(machine, AtomicPlan(prefix.cycles + selected.cycles, prefix.instructions + selected.instructions,
                              writes, final, selected.last_pc, prefix.direct_calls + selected.direct_calls))
    y = _read(view, final['a5'] + 4, 2)
    suffix = (*game.finish_guarded_lower_spawn(final['a5']),
              *game.offset_spawn_position(lambda address, size: _read(view, address, size), final['a5'], 0, -8))
    final['sr'] = _sub_sr(selected.registers['sr'], y, 8, 2)
    return AtomicPlan(prefix.cycles + selected.cycles + 68, prefix.instructions + selected.instructions + 4,
                      tuple(dict((*writes, *suffix)).items()), final, 0x1B71C2,
                      prefix.direct_calls + selected.direct_calls + 2)


def spawn_closure_safe_return(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover callback 1B65BE only when the dispatcher has selected it."""
    sp = registers['a7']
    if sp & 1 or machine.peek_rom(SPAWN_CLOSURE_SAFE_RETURN_ENTRY, 2) != bytes.fromhex('4e75'):
        raise UnsupportedCandidate('closure safe return ROM shape')
    outer = _read(machine, sp, 4)
    return AtomicPlan(16, 1, (), {**registers, 'a7': sp + 4, 'pc': outer & 0xFFFFFF},
                      SPAWN_CLOSURE_SAFE_RETURN_ENTRY)


def spawn_lower_dispatch_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B74D6``'s fixed-template lower-pool allocation."""
    return spawn_plain_caller(machine, registers, SPAWN_LOWER_DISPATCH_ENTRY)


def _upper_tile_wrapper_shape(machine):
    raw = machine.peek_rom(SPAWN_UPPER_TILE_CALLER_ENTRY, 32)
    if raw != bytes.fromhex(
            '4df9001b7a806100e65066124a3900fff175660a41f9001292b26100ba264e75'):
        raise UnsupportedCandidate('upper tile spawn caller ROM shape')


def spawn_upper_tile_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6C0E``'s upper-pool creation and its FFF175 tile-upload guard.

    A failed allocation, and a successful one with ``FFF175`` set, both
    return locally with no further writes -- the same LEA/BSR upper-pool
    prefix as ``spawn_upper_caller``, with a plain RTS tail instead of a
    coordinate-correction suffix.  A successful allocation with ``FFF175``
    clear continues into ``1B2650``'s VDP tile-data upload: a MOVE.L to the
    VDP control port ``$C00004`` followed by a 16-word transfer through the
    data port ``$C00000``, inside the ``1B263C..1B26D0`` command-stream
    engine range.  No RAM-domain recipe reaches a device port, so that arm
    declines.
    """
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned upper tile spawn caller stack')
    _upper_tile_wrapper_shape(machine)
    _spans_disjoint([('upper tile spawn caller pool', 0xFF7E82, 24 * 66),
                     ('upper tile spawn caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, SPAWN_UPPER_TILE_CALLER_ENTRY + 10, 4),
                        {**registers, 'a6': SPAWN_UPPER_TILE_CALLER_TEMPLATE, 'a7': sp - 4,
                         'pc': SPAWN_REGION_UPPER_ENTRY},
                        SPAWN_UPPER_TILE_CALLER_ENTRY + 6, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_UPPER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_UPPER_TILE_CALLER_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    planned = dispatch_plan_view(machine, AtomicPlan(
        prefix.cycles + selected.cycles, prefix.instructions + selected.instructions,
        writes, final, selected.last_pc, prefix.direct_calls + selected.direct_calls))
    guard = _read(planned, 0xFFF175, 1)
    if guard == 0:
        raise UnsupportedCandidate('upper tile spawn caller requires the 1B2650 VDP tile upload')
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], guard, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 50,
                      prefix.instructions + selected.instructions + 4, writes, final,
                      SPAWN_UPPER_TILE_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_cap_guard_two(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B72FC``'s FFEFE0 cap comparison against ``$3030``.

    A clear (mismatched) cap takes the direct RTS recovered here.  An exact
    match falls into an unrecorded four-slot allocation sequence (no
    retained fixture exercises it); that arm declines.
    """
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned spawn cap guard stack')
    outer = _read(machine, sp, 4)
    cap = _read(machine, 0xFFEFE0, 2)
    compare_sr = (_sub_sr(registers['sr'], cap, 0x3030, 2) & ~0x10) | (registers['sr'] & 0x10)
    if compare_sr & 4:
        raise UnsupportedCandidate(
            'spawn cap guard reached 0x3030: unrecorded four-slot spawn sequence')
    return AtomicPlan(46, 3, (), {**registers, 'a7': sp + 4,
                      'pc': outer & 0xFFFFFF, 'sr': compare_sr},
                      SPAWN_CAP_GUARD_TWO_LAST_PC)


def spawn_lower_offset_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B71C4``'s lower-pool creation and its script/Y-offset tail.

    The same allocator and template as ``spawn_closure_guard_caller``
    (``SPAWN_REGION_LOWER_ENTRY``, template ``0x1B78F0``) and the same
    finish-write-plus-Y-offset tail shape, just without that entry's
    ``FFF12A`` guard prefix.  Every arm is owned: allocation failure and
    success both return locally with no undeclined branch.
    """
    entry, sp = SPAWN_LOWER_OFFSET_CALLER_ENTRY, registers['a7']
    shape = bytes.fromhex('4df9001b78f06100e092660e2b7c001243320020046d000800044e75')
    if sp & 1 or machine.peek_rom(entry, len(shape)) != shape:
        raise UnsupportedCandidate('lower offset spawn caller ROM shape')
    _spans_disjoint([('lower offset spawn caller pool', 0xFF7E82, 24 * 66),
                     ('lower offset spawn caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, entry + 10, 4),
                        {**registers, 'a6': 0x1B78F0, 'a7': sp - 4, 'pc': SPAWN_REGION_LOWER_ENTRY},
                        entry + 6, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_LOWER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
    if not (final['sr'] & 4):
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_LOWER_OFFSET_CALLER_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    view = dispatch_plan_view(machine, AtomicPlan(
        prefix.cycles + selected.cycles, prefix.instructions + selected.instructions,
        writes, final, selected.last_pc, prefix.direct_calls + selected.direct_calls))
    y = _read(view, final['a5'] + 4, 2)
    suffix = (*game.finish_lower_offset_spawn(final['a5']),
              *game.offset_spawn_position(lambda address, size: _read(view, address, size),
                                          final['a5'], 0, -8))
    final['sr'] = _sub_sr(selected.registers['sr'], y, 8, 2)
    return AtomicPlan(prefix.cycles + selected.cycles + 68,
                      prefix.instructions + selected.instructions + 4,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_LOWER_OFFSET_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls + 2)


def spawn_reverse_y_offset_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B65C0``'s reverse-pool creation and its +10 Y-only offset.

    Reverse-pool allocation (template ``0x1B7D14``) then, on success only,
    an unsigned ``ADDI.W #$A`` to the record's own Y coordinate -- no
    script write, no X adjustment, unlike the closure/offset table shapes.
    Both allocation failure and success are owned.
    """
    entry, sp = SPAWN_REVERSE_Y_OFFSET_CALLER_ENTRY, registers['a7']
    shape = bytes.fromhex('4df9001b7d146100ec8e6606066d000a00044e75')
    if sp & 1 or machine.peek_rom(entry, len(shape)) != shape:
        raise UnsupportedCandidate('reverse Y-offset spawn caller ROM shape')
    _spans_disjoint([('reverse Y-offset spawn caller pool', 0xFF7E82, 24 * 66),
                     ('reverse Y-offset spawn caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, entry + 10, 4),
                        {**registers, 'a6': SPAWN_REVERSE_Y_OFFSET_CALLER_TEMPLATE, 'a7': sp - 4,
                         'pc': SPAWN_REGION_REVERSE_ENTRY}, entry + 6, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_REVERSE_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
    if not (final['sr'] & 4):
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_REVERSE_Y_OFFSET_CALLER_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    view = dispatch_plan_view(machine, AtomicPlan(
        prefix.cycles + selected.cycles, prefix.instructions + selected.instructions,
        writes, final, selected.last_pc, prefix.direct_calls + selected.direct_calls))
    y = _read(view, final['a5'] + 4, 2)
    offsets = tuple(game.offset_spawn_position(
        lambda address, size: _read(view, address, size), final['a5'], 0, 10))
    final['sr'] = _add_sr(selected.registers['sr'], y, 10, 2)
    return AtomicPlan(prefix.cycles + selected.cycles + 44,
                      prefix.instructions + selected.instructions + 3,
                      tuple(dict((*writes, *offsets)).items()), final,
                      SPAWN_REVERSE_Y_OFFSET_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls + 1)


def _upper_tile_word_wrapper_shape(machine):
    raw = machine.peek_rom(SPAWN_UPPER_TILE_WORD_CALLER_ENTRY, 52)
    if raw != bytes.fromhex(
            '4df9001b81ec6100e2b0661e4a3900fff17566160c39000500ff7e26670e'
            '41f9001294f24eb9001b26504e753b7c6000001e4e75'):
        raise UnsupportedCandidate('upper tile word spawn caller ROM shape')


def spawn_upper_tile_word_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6FAE``'s upper-pool creation, FFF175 guard and FF7E26 arm.

    The same upper-pool prefix as ``spawn_upper_tile_caller`` (``1B6C0E``),
    template ``0x1B81EC``.  A failed allocation and a successful one with
    ``FFF175`` set both return locally at the same early RTS (``0x1B6FD8``)
    with no further writes.  A successful allocation with ``FFF175`` clear
    continues into a CMPI.B FF7E26,#5 selector: a match writes one fixed
    word at record+0x1E and returns (``0x1B6FE0``, the arm every recorded
    fixture exercises); a mismatch reaches 1B2650's VDP tile-data upload
    (the same command-stream engine device port as 1B6C0E) and declines.
    """
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned upper tile word spawn caller stack')
    _upper_tile_word_wrapper_shape(machine)
    _spans_disjoint([('upper tile word spawn caller pool', 0xFF7E82, 24 * 66),
                     ('upper tile word spawn caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    entry = SPAWN_UPPER_TILE_WORD_CALLER_ENTRY
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, entry + 10, 4),
                        {**registers, 'a6': SPAWN_UPPER_TILE_WORD_CALLER_TEMPLATE, 'a7': sp - 4,
                         'pc': SPAWN_REGION_UPPER_ENTRY}, entry + 6, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_UPPER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_UPPER_TILE_WORD_CALLER_EARLY_PC,
                          prefix.direct_calls + selected.direct_calls)
    planned = dispatch_plan_view(machine, AtomicPlan(
        prefix.cycles + selected.cycles, prefix.instructions + selected.instructions,
        writes, final, selected.last_pc, prefix.direct_calls + selected.direct_calls))
    guard = _read(planned, 0xFFF175, 1)
    if guard != 0:
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], guard, 1))
        return AtomicPlan(prefix.cycles + selected.cycles + 50,
                          prefix.instructions + selected.instructions + 4, writes, final,
                          SPAWN_UPPER_TILE_WORD_CALLER_EARLY_PC,
                          prefix.direct_calls + selected.direct_calls)
    selector = _read(planned, 0xFF7E26, 1)
    if selector != 5:
        raise UnsupportedCandidate(
            'upper tile word spawn caller requires the 1B2650 VDP tile upload')
    suffix = tuple(game.finish_upper_tile_word_spawn(final['a5']))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 0x6000, 2))
    return AtomicPlan(prefix.cycles + selected.cycles + 94,
                      prefix.instructions + selected.instructions + 7,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_UPPER_TILE_WORD_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def _reverse_guard_wrapper_shape(machine):
    raw = machine.peek_rom(SPAWN_REVERSE_GUARD_CALLER_ENTRY, 22)
    if raw != bytes.fromhex('0c39000b00ff7e26670c4df9001b7ddc6100eaee6026'):
        raise UnsupportedCandidate('reverse guard spawn caller ROM shape')


def spawn_reverse_guard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6756``'s FF7E26 selector and its unconditional reverse spawn.

    A ``FF7E26 != 0x0B`` selector (every recorded fixture) allocates from
    the reverse pool (template ``0x1B7DDC``) then branches unconditionally
    to a shared RTS with no Z-flag check at all: whether the allocation
    succeeds or the pool is exhausted, the wrapper returns with no further
    writes either way, so this owns both sub-cases as one arm.  A
    ``FF7E26 == 0x0B`` selector is unobserved on the recorded history and
    nests a second guard, a second reverse-pool spawn and a second 1B2650
    VDP tile upload behind it; that arm has no retained fixture and no
    RAM-domain recipe for the VDP call, so it declines.
    """
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned reverse guard spawn caller stack')
    _reverse_guard_wrapper_shape(machine)
    selector = _read(machine, 0xFF7E26, 1)
    tested_sr = _sub_sr(registers['sr'], selector, 0x0B, 1)
    if tested_sr & 4:
        raise UnsupportedCandidate(
            'reverse guard spawn caller requires its unrecorded FF7E26==0x0B chain')
    _spans_disjoint([('reverse guard spawn caller pool', 0xFF7E82, 24 * 66),
                     ('reverse guard spawn caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    entry = SPAWN_REVERSE_GUARD_CALLER_ENTRY
    prefix = AtomicPlan(58, 4, _bytes(sp - 4, entry + 20, 4),
                        {**registers, 'a6': SPAWN_REVERSE_GUARD_CALLER_TEMPLATE, 'a7': sp - 4,
                         'pc': SPAWN_REGION_REVERSE_ENTRY}, entry + 16, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_REVERSE_ENTRY)
    final = dict(selected.registers)
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
    return AtomicPlan(prefix.cycles + selected.cycles + 26,
                      prefix.instructions + selected.instructions + 2,
                      tuple(dict((*prefix.writes, *selected.writes)).items()), final,
                      SPAWN_REVERSE_GUARD_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_reverse_plain_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B7232``'s direct reverse-pool allocator wrapper."""
    return spawn_plain_caller(machine, registers, SPAWN_REVERSE_PLAIN_CALLER_ENTRY)


def spawn_upper_plain_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6F76``'s direct upper-pool allocator wrapper."""
    return spawn_plain_caller(machine, registers, SPAWN_UPPER_PLAIN_CALLER_ENTRY)


def spawn_upper_standard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6E7A``'s direct upper-pool allocator wrapper."""
    return spawn_plain_caller(machine, registers, SPAWN_UPPER_STANDARD_CALLER_ENTRY)


def spawn_upper_secondary_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6E90``'s direct upper-pool allocator wrapper."""
    return spawn_plain_caller(machine, registers, SPAWN_UPPER_SECONDARY_CALLER_ENTRY)


def spawn_upper_tertiary_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6EA6``'s direct upper-pool allocator wrapper."""
    return spawn_plain_caller(machine, registers, SPAWN_UPPER_TERTIARY_CALLER_ENTRY)


def spawn_upper_typed_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6EB2``'s upper allocator and successful typed suffix."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned typed upper caller stack')
    _spans_disjoint([('typed upper caller pool', 0xFF7E82, 24 * 66),
                     ('typed upper caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, 0x1B6EBC, 4),
                        {**registers, 'a6': 0x1B7C10, 'a7': sp - 4,
                         'pc': SPAWN_REGION_UPPER_ENTRY}, 0x1B6EB8, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_UPPER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_UPPER_TYPED_CALLER_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_upper_typed_spawn(final['a5']))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 0x20, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 84,
                      prefix.instructions + selected.instructions + 5,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_UPPER_TYPED_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_upper_typed_secondary_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B6ED0``'s upper allocator and successful typed suffix."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned secondary typed upper caller stack')
    _spans_disjoint([('secondary typed upper caller pool', 0xFF7E82, 24 * 66),
                     ('secondary typed upper caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, 0x1B6EDA, 4),
                        {**registers, 'a6': 0x1B7C24, 'a7': sp - 4,
                         'pc': SPAWN_REGION_UPPER_ENTRY}, 0x1B6ED6, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers, SPAWN_REGION_UPPER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items()); final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26, prefix.instructions + selected.instructions + 2, writes, final, SPAWN_UPPER_TYPED_SECONDARY_LAST_PC, prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_upper_typed_spawn(final['a5'], 0x001235ac, 0x21))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 0x21, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 84, prefix.instructions + selected.instructions + 5, tuple(dict((*writes, *suffix)).items()), final, SPAWN_UPPER_TYPED_SECONDARY_LAST_PC, prefix.direct_calls + selected.direct_calls)


def spawn_lower_reset_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Clear the shared spawn flag, then allocate from the descending lower pool."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned lower reset caller stack')
    _spans_disjoint([('lower reset pool', 0xFF7E82, 24 * 66),
                     ('lower reset frame', sp - 8, 12),
                     ('lower reset flag', 0xFFF104, 1), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(50, 3, (*game.reset_lower_spawn_flag(), *_bytes(sp - 4, 0x1B6F1C, 4)),
                        {**registers, 'a6': 0x1B7C4C, 'a7': sp - 4,
                         'pc': SPAWN_REGION_LOWER_ENTRY,
                         'sr': _logic_sr(registers['sr'], 0, 1)}, 0x1B6F18, direct_calls=2)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_LOWER_ENTRY)
    return AtomicPlan(prefix.cycles + selected.cycles + 16,
                      prefix.instructions + selected.instructions + 1,
                      tuple(dict((*prefix.writes, *selected.writes)).items()),
                      {**selected.registers, 'a7': sp + 4, 'pc': outer & 0xFFFFFF},
                      0x1B6F1C, prefix.direct_calls + selected.direct_calls)


def spawn_lower_scripted_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Allocate a lower-pool object; install its script only on success."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned lower scripted caller stack')
    _spans_disjoint([('lower scripted pool', 0xFF7E82, 24 * 66),
                     ('lower scripted frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, 0x1B6F28, 4),
                        {**registers, 'a6': 0x1B8250, 'a7': sp - 4,
                         'pc': SPAWN_REGION_LOWER_ENTRY}, 0x1B6F24, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_LOWER_ENTRY)
    writes = (*prefix.writes, *selected.writes)
    final = {**selected.registers, 'a7': sp + 4, 'pc': outer & 0xFFFFFF}
    if not final['sr'] & 4:
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2,
                          tuple(dict(writes).items()), final, 0x1B6F32,
                          prefix.direct_calls + selected.direct_calls)
    suffix = game.finish_lower_scripted_spawn(final['a5'])
    final['sr'] = _logic_sr(final['sr'], 0x00125A4C, 4)
    return AtomicPlan(prefix.cycles + selected.cycles + 48,
                      prefix.instructions + selected.instructions + 3,
                      tuple(dict((*writes, *suffix)).items()), final, 0x1B6F32,
                      prefix.direct_calls + selected.direct_calls + 1)


def spawn_upper_dispatch_guard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B744A``'s guard before the upper dispatcher callback."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned upper dispatch guard caller stack')
    outer = _read(machine, sp, 4)
    guard = _read(machine, 0xFFF16F, 1)
    tested_sr = _logic_sr(registers['sr'], guard, 1)
    if guard == 0:
        return AtomicPlan(42, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': tested_sr},
                          SPAWN_UPPER_DISPATCH_GUARD_LAST_PC)
    prefix = AtomicPlan(28, 2, (), {**registers, 'pc': SPAWN_UPPER_DISPATCH_ENTRY,
                                     'sr': tested_sr}, 0x1B7450)
    selected = spawn_upper_dispatch_caller(dispatch_plan_view(machine, prefix), prefix.registers)
    return AtomicPlan(prefix.cycles + selected.cycles,
                      prefix.instructions + selected.instructions, selected.writes,
                      selected.registers, selected.last_pc,
                      prefix.direct_calls + selected.direct_calls)


def spawn_primary_double_guard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B738A``'s two guards and primary-pool success suffix."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned primary double guard caller stack')
    outer = _read(machine, sp, 4)
    first = _read(machine, 0xFFF177, 1)
    first_sr = _logic_sr(registers['sr'], first, 1)
    if first == 0:
        return AtomicPlan(42, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': first_sr},
                          SPAWN_PRIMARY_DOUBLE_GUARD_LAST_PC)
    second = _read(machine, 0xFFF178, 1)
    second_sr = _logic_sr(first_sr, second, 1)
    if second == 0:
        return AtomicPlan(66, 5, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': second_sr},
                          SPAWN_PRIMARY_DOUBLE_GUARD_LAST_PC)
    prefix = AtomicPlan(78, 6, _bytes(sp - 4, 0x1B73A4, 4),
                        {**registers, 'a6': 0x1B79B8, 'a7': sp - 4,
                         'pc': SPAWN_REGION_ENTRY, 'sr': second_sr},
                        0x1B73A0, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_PRIMARY_DOUBLE_GUARD_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_primary_double_guard_spawn(final['a5']))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 1, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 100,
                      prefix.instructions + selected.instructions + 6,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_PRIMARY_DOUBLE_GUARD_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_primary_inverse_guard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B73C2``'s inverse primary allocator guard and suffix."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned primary inverse guard caller stack')
    outer = _read(machine, sp, 4)
    first = _read(machine, 0xFFF177, 1)
    first_sr = _logic_sr(registers['sr'], first, 1)
    if first != 0:
        return AtomicPlan(42, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': first_sr},
                          0x1B73F0)
    prefix = AtomicPlan(54, 4, _bytes(sp - 4, 0x1B73D4, 4),
                        {**registers, 'a6': 0x1B79B8, 'a7': sp - 4,
                         'pc': SPAWN_REGION_ENTRY, 'sr': first_sr},
                        0x1B73D0, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          0x1B73F0,
                          prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_primary_inverse_guard_spawn(final['a5']))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 1, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 100,
                      prefix.instructions + selected.instructions + 6,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_PRIMARY_INVERSE_GUARD_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_primary_mixed_guard_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B73F2``'s opposing primary-pool guards and suffix."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned primary mixed guard caller stack')
    outer = _read(machine, sp, 4)
    first = _read(machine, 0xFFF177, 1)
    first_sr = _logic_sr(registers['sr'], first, 1)
    if first == 0:
        return AtomicPlan(42, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': first_sr},
                          SPAWN_PRIMARY_MIXED_GUARD_LAST_PC)
    second = _read(machine, 0xFFF178, 1)
    second_sr = _logic_sr(first_sr, second, 1)
    if second != 0:
        return AtomicPlan(66, 5, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': second_sr},
                          SPAWN_PRIMARY_MIXED_GUARD_LAST_PC)
    prefix = AtomicPlan(78, 6, _bytes(sp - 4, 0x1B740C, 4),
                        {**registers, 'a6': 0x1B79B8, 'a7': sp - 4,
                         'pc': SPAWN_REGION_ENTRY, 'sr': second_sr},
                        0x1B7408, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_PRIMARY_MIXED_GUARD_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_primary_mixed_guard_spawn(final['a5']))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 1, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 100,
                      prefix.instructions + selected.instructions + 6,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_PRIMARY_MIXED_GUARD_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_upper_dispatch_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover the recorded ``1B7454`` upper-pool callback.

    This callback has no cap or guard of its own: it fixes the template, uses
    the existing upper allocator, and tags a successfully allocated slot.
    The adjacent ``1B7354`` guard remains an original-only entry.
    """
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned upper dispatch caller stack')
    _spans_disjoint([('upper dispatch caller pool', 0xFF7E82, 24 * 66),
                     ('upper dispatch caller frame', sp - 4, 8),
                     *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, 0x1B745E, 4),
                        {**registers, 'a6': 0x1B79B8, 'a7': sp - 4,
                         'pc': SPAWN_REGION_UPPER_ENTRY}, 0x1B745A, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_UPPER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_UPPER_DISPATCH_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_upper_dispatch_spawn(final['a5']))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 1, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 76,
                      prefix.instructions + selected.instructions + 5,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_UPPER_DISPATCH_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)




def spawn_dispatch_call(machine, registers: dict[str, int], *, row=False) -> AtomicPlan:
    """Compose one admitted ``1AE46C`` callback and its MOVEM restore.

    Lookup and loop ownership remain native.  This narrow parent span starts
    after the dispatcher has saved D0-D7/A0-A6 and declines before JSR unless
    the observed A4 callback is one of the qualified spawn callers.
    """
    call_entry, call_last_pc, resume_pc = ((0x1AE4E8, 0x1AE4EA, 0x1AE4EE) if row else
                                           (SPAWN_DISPATCH_CALL_ENTRY, SPAWN_DISPATCH_CALL_LAST_PC, 0x1AE472))
    sp, target = registers['a7'], registers['a4'] & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned spawn dispatcher call stack')
    callbacks = {
        SPAWN_REVERSE_CALLER_ENTRY: spawn_reverse_caller,
        SPAWN_UPPER_VARIANT_CALLER_ENTRY: spawn_upper_variant_caller,
        SPAWN_UPPER_SCRIPTED_CALLER_ENTRY: spawn_upper_scripted_caller,
        SPAWN_UPPER_TYPED_CALLER_ENTRY: spawn_upper_typed_caller,
        SPAWN_UPPER_TYPED_SECONDARY_ENTRY: spawn_upper_typed_secondary_caller,
        SPAWN_LOWER_RESET_ENTRY: spawn_lower_reset_caller,
        SPAWN_LOWER_SCRIPTED_ENTRY: spawn_lower_scripted_caller,
        SPAWN_UPPER_GUARD_ENTRY: spawn_upper_guard_caller,
        SPAWN_UPPER_CALLER_ENTRY: spawn_upper_caller,
        SPAWN_PRIMARY_GUARD_ENTRY: spawn_primary_guard_caller,
        SPAWN_PRIMARY_DISPATCH_ENTRY: spawn_primary_dispatch_caller,
        SPAWN_PRIMARY_DOUBLE_GUARD_ENTRY: spawn_primary_double_guard_caller,
        SPAWN_PRIMARY_INVERSE_GUARD_ENTRY: spawn_primary_inverse_guard_caller,
        SPAWN_PRIMARY_MIXED_GUARD_ENTRY: spawn_primary_mixed_guard_caller,
        SPAWN_UPPER_DISPATCH_GUARD_ENTRY: spawn_upper_dispatch_guard_caller,
        SPAWN_UPPER_DISPATCH_ENTRY: spawn_upper_dispatch_caller,
        SPAWN_CLOSURE_GUARD_ENTRY: spawn_closure_guard_caller,
        SPAWN_CLOSURE_SAFE_RETURN_ENTRY: spawn_closure_safe_return,
        SPAWN_UPPER_TILE_CALLER_ENTRY: spawn_upper_tile_caller,
        SPAWN_CAP_GUARD_TWO_ENTRY: spawn_cap_guard_two,
        SPAWN_LOWER_OFFSET_CALLER_ENTRY: spawn_lower_offset_caller,
        SPAWN_UPPER_TILE_WORD_CALLER_ENTRY: spawn_upper_tile_word_caller,
        SPAWN_REVERSE_GUARD_CALLER_ENTRY: spawn_reverse_guard_caller,
        SPAWN_REVERSE_Y_OFFSET_CALLER_ENTRY: spawn_reverse_y_offset_caller,
    }
    callback_function = callbacks.get(target)
    if target not in SPAWN_PLAIN_CALLER_FACTS and target not in SPAWN_OFFSET_CALLER_FACTS \
            and target not in SPAWN_CLOSURE_CALLER_FACTS and callback_function is None:
        raise UnsupportedCandidate(f'spawn dispatcher target {target:06X} is not recovered')
    extra = [('lower reset flag', 0xFFF104, 1)] if target == SPAWN_LOWER_RESET_ENTRY else []
    _spans_disjoint([('spawn dispatcher MOVEM frame', sp - 4, 64),
                     ('spawn dispatcher indexed clear',
                      (registers['a2'] + _signed_word(registers['d2'])) & 0xFFFFFF, 1),
                     ('spawn dispatcher pool', 0xFF7E82, 24 * 66),
                     *SPAWN_REGION_GLOBALS, *extra])
    prefix = AtomicPlan(16, 1, _bytes(sp - 4, call_last_pc, 4),
                        {**registers, 'a7': sp - 4, 'pc': target},
                        call_entry, direct_calls=1)
    planner = dispatch_plan_view(machine, prefix)
    if target in SPAWN_PLAIN_CALLER_FACTS:
        callback = spawn_plain_caller(planner, prefix.registers, target)
    elif target in SPAWN_OFFSET_CALLER_FACTS:
        callback = spawn_offset_caller(planner, prefix.registers, target)
    elif target in SPAWN_CLOSURE_CALLER_FACTS:
        callback = spawn_closure_caller(planner, prefix.registers, target)
    else:
        callback = callback_function(planner, prefix.registers)
    restored = {name: _read(machine, sp + 4 * index, 4)
                for index, name in enumerate(('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7',
                                               'a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6'))}
    final = {**restored, 'a7': sp + 60, 'pc': resume_pc, 'sr': callback.registers['sr']}
    return AtomicPlan(prefix.cycles + callback.cycles + 132,
                      prefix.instructions + callback.instructions + 1,
                      tuple(dict((*prefix.writes, *callback.writes)).items()), final,
                      call_last_pc,
                      prefix.direct_calls + callback.direct_calls)

def spawn_upper_variant_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover table callback 1B7262 through the upper allocator and $3A suffix."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned upper variant caller stack')
    _spans_disjoint([('upper variant caller pool', 0xFF7E82, 24 * 66),
                     ('upper variant caller frame', sp - 8, 12),
                     ('upper variant cap', 0xFFEFE2, 2), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    cap = _read(machine, 0xFFEFE2, 2)
    compare_sr = (_sub_sr(registers['sr'], cap, 0x3939, 2) & ~0x10) | (registers['sr'] & 0x10)
    if compare_sr & 4:
        return AtomicPlan(46, 3, (), {**registers, 'a7': sp + 4,
                          'pc': outer & 0xFFFFFF, 'sr': compare_sr},
                          SPAWN_UPPER_VARIANT_CALLER_LAST_PC)
    prefix = AtomicPlan(66, 4, _bytes(sp - 4, 0x1B7278, 4),
                        {**registers, 'a6': 0x1B79B8, 'a7': sp - 4,
                         'pc': SPAWN_REGION_UPPER_ENTRY}, 0x1B7274, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_UPPER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 22,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_UPPER_VARIANT_CALLER_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_upper_variant_spawn(final['a5']))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 1, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 72,
                      prefix.instructions + selected.instructions + 5,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_UPPER_VARIANT_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_upper_scripted_caller(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover ``1B72D4``'s upper allocator and complete caller suffix."""
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned upper scripted caller stack')
    _spans_disjoint([('upper scripted caller pool', 0xFF7E82, 24 * 66),
                     ('upper scripted caller frame', sp - 8, 12), *SPAWN_REGION_GLOBALS])
    outer = _read(machine, sp, 4)
    prefix = AtomicPlan(30, 2, _bytes(sp - 4, 0x1B72DE, 4),
                        {**registers, 'a6': 0x1B79B8, 'a7': sp - 4,
                         'pc': SPAWN_REGION_UPPER_ENTRY}, 0x1B72DA, direct_calls=1)
    selected = spawn_region(dispatch_plan_view(machine, prefix), prefix.registers,
                            SPAWN_REGION_UPPER_ENTRY)
    writes = tuple(dict((*prefix.writes, *selected.writes)).items())
    final = dict(selected.registers)
    if not (final['sr'] & 4):
        final.update(a7=sp + 4, pc=outer & 0xFFFFFF)
        return AtomicPlan(prefix.cycles + selected.cycles + 26,
                          prefix.instructions + selected.instructions + 2, writes, final,
                          SPAWN_UPPER_SCRIPTED_CALLER_LAST_PC,
                          prefix.direct_calls + selected.direct_calls)
    suffix = tuple(game.finish_upper_scripted_spawn(final['a5']))
    final.update(a7=sp + 4, pc=outer & 0xFFFFFF, sr=_logic_sr(final['sr'], 1, 1))
    return AtomicPlan(prefix.cycles + selected.cycles + 100,
                      prefix.instructions + selected.instructions + 6,
                      tuple(dict((*writes, *suffix)).items()), final,
                      SPAWN_UPPER_SCRIPTED_CALLER_LAST_PC,
                      prefix.direct_calls + selected.direct_calls)


def spawn_dispatch_iteration(machine, registers: dict[str, int], *, row=False) -> AtomicPlan:
    """Recover one admitted ``1AE468`` callback iteration.

    The table lookup that selects ``A4`` and all later iterations remain
    native.  This owns the exact save/call/restore/update sequence only when
    that already-selected target has a recovered spawn caller.
    """
    sp = registers['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned spawn dispatcher iteration stack')
    names = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7',
             'a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6')
    saved = tuple(byte for index, name in enumerate(names)
                  for byte in _bytes(sp - 60 + 4 * index, registers[name], 4))
    iteration_entry, iteration_last_pc = ((0x1AE4E4, 0x1AE4F2) if row else
                                           (SPAWN_DISPATCH_ITERATION_ENTRY, SPAWN_DISPATCH_ITERATION_LAST_PC))
    prefix = AtomicPlan(128, 1, saved,
                        {**registers, 'a7': sp - 60,
                         'pc': 0x1AE4E8 if row else SPAWN_DISPATCH_CALL_ENTRY}, iteration_entry)
    callback = spawn_dispatch_call(dispatch_plan_view(machine, prefix), prefix.registers, row=row)
    final = dict(callback.registers)
    d4, d5, d6 = (final[name] for name in ('d4', 'd5', 'd6'))
    if not row:
        final['a0'] = (final['a0'] + _signed_word(d5)) & 0xFFFFFFFF
    final['d6'] = (d6 & 0xFFFF0000) | ((d6 + 0x10) & 0xFFFF)
    final['d4'] = (d4 & 0xFFFF0000) | ((d4 - 1) & 0xFFFF)
    final['sr'] = _add_sr(final['sr'], d6 & 0xFFFF, 0x10, 2)
    tail_cycles = (22 if (d4 & 0xFFFF) == 0 else 18) if row else (30 if (d4 & 0xFFFF) == 0 else 26)
    final['pc'] = ((SPAWN_ROW_DISPATCH_WALKER_LAST_PC if (d4 & 0xFFFF) == 0 else SPAWN_ROW_DISPATCH_WALKER_ENTRY)
                   if row else (0x1AE47C if (d4 & 0xFFFF) == 0 else 0x1AE44A))
    return AtomicPlan(prefix.cycles + callback.cycles + tail_cycles,
                      prefix.instructions + callback.instructions + (2 if row else 3),
                      tuple(dict((*prefix.writes, *callback.writes)).items()), final,
                      iteration_last_pc,
                      prefix.direct_calls + callback.direct_calls)


def spawn_dispatch_walker(machine, registers: dict[str, int], *, row=False) -> AtomicPlan:
    """Recover the bounded ``1AE44A..1AE47C`` spawn-table walker.

    Setup through ``1AE446`` remains native. Starting at the loop head, this
    owns one to sixteen slots selected by the existing D4 DBRA counter. Known
    callbacks compose through ``spawn_dispatch_iteration``; an unknown
    callback declines before the aggregate plan can be admitted, allowing the
    native instruction stream to retain that slot.
    """
    sp, a1, a2, d4, d5 = (registers[name] for name in ('a7', 'a1', 'a2', 'd4', 'd5'))
    walker_entry, walker_last_pc = ((SPAWN_ROW_DISPATCH_WALKER_ENTRY, SPAWN_ROW_DISPATCH_WALKER_LAST_PC)
                                    if row else (SPAWN_DISPATCH_WALKER_ENTRY, SPAWN_DISPATCH_WALKER_LAST_PC))
    count = (d4 & 0xFFFF) + 1
    if sp & 1:
        raise UnsupportedCandidate('unaligned spawn dispatcher walker stack')
    if count > (23 if row else 16):
        raise UnsupportedCandidate('spawn dispatcher walker count is outside one pass')
    if a1 != 0x004154 or a2 != 0xFFAE87:
        raise UnsupportedCandidate('spawn dispatcher walker table identity')

    # Validate every potential slot before planning. D5 is a signed original
    # cursor stride; the running plan supplies all later alias-visible reads.
    cursor = registers['a0'] & 0xFFFFFFFF
    stride = 2 if row else _signed_word(d5)
    for _ in range(count):
        _address(cursor, 2)
        cursor = (cursor + stride) & 0xFFFFFFFF

    current = AtomicPlan(0, 0, (), dict(registers), walker_entry)
    for _ in range(count):
        view = dispatch_plan_view(machine, current)
        state = dict(current.registers)
        cursor = state['a0'] & 0xFFFFFFFF
        flag_index, flag = game.select_spawn_dispatch_slot(
            lambda address, size: _read(view, address, size), cursor, a2)
        d2 = (state['d2'] & 0xFFFF0000) | flag_index
        d1 = (state['d1'] & 0xFFFFFF00) | flag
        remaining = state['d4'] & 0xFFFF
        final_iteration = remaining == 0

        if not flag:
            d6 = state['d6']
            final = {**state,
                     'd1': d1,
                     'd2': d2,
                     'a0': (cursor + stride) & 0xFFFFFFFF,
                     'd6': (d6 & 0xFFFF0000) | ((d6 + 0x10) & 0xFFFF),
                     'd4': (state['d4'] & 0xFFFF0000) | ((remaining - 1) & 0xFFFF),
                     'sr': _add_sr(state['sr'], d6 & 0xFFFF, 0x10, 2),
                     'pc': walker_last_pc if final_iteration else walker_entry}
            step = AtomicPlan((62 if final_iteration else 58) if row else (70 if final_iteration else 66),
                              6 if row else 7, (), final,
                              0x1AE4F2 if row else SPAWN_DISPATCH_ITERATION_LAST_PC, direct_calls=1)
        else:
            target = int.from_bytes(view.peek_rom(a1 + flag * 4, 4), 'big') & 0xFFFFFF
            d1 = (state['d1'] & 0xFFFF0000) | ((flag * 4) & 0xFFFF)
            selected = AtomicPlan(92, 10, _bytes(0xFF7DB0 if row else 0xFF7DB2, state['d6'], 2),
                                  {**state, **({'a0': (cursor + 2) & 0xFFFFFFFF} if row else {}), 'd1': d1, 'd2': d2,
                                   'd3': (state['d3'] & 0xFFFFFF00) | flag,
                                   'a4': target, 'pc': 0x1AE4E4 if row else SPAWN_DISPATCH_ITERATION_ENTRY,
                                   'sr': _logic_sr(state['sr'] & ~0x10, state['d6'], 2)},
                                  0x1AE4DE if row else 0x1AE462, direct_calls=1)
            callback = spawn_dispatch_iteration(dispatch_plan_view(view, selected),
                                                selected.registers, row=row)
            step = AtomicPlan(selected.cycles + callback.cycles,
                              selected.instructions + callback.instructions,
                              tuple(dict((*selected.writes, *callback.writes)).items()),
                              callback.registers, callback.last_pc,
                              selected.direct_calls + callback.direct_calls)

        current = AtomicPlan(current.cycles + step.cycles,
                             current.instructions + step.instructions,
                             tuple(dict((*current.writes, *step.writes)).items()),
                             step.registers, step.last_pc,
                             current.direct_calls + step.direct_calls)

    if current.registers['pc'] != walker_last_pc:
        raise UnsupportedCandidate('spawn dispatcher walker did not reach its return')
    # The bounded product boundary is the original RTS instruction. It stays
    # native so the future-continuation witness also verifies its outer return.
    return AtomicPlan(current.cycles, current.instructions, current.writes,
                      current.registers, 0x1AE4F2 if row else SPAWN_DISPATCH_ITERATION_LAST_PC,
                      current.direct_calls)


def spawn_row_dispatch_walker(machine, registers: dict[str, int]) -> AtomicPlan:
    """Recover the bounded 23-slot row dispatcher through the shared carrier."""
    return spawn_dispatch_walker(machine, registers, row=True)


# Each setup fixes placement inputs then enters one established bounded walker.
SPAWN_SETUP_FACTS = {
    SPAWN_SETUP_LEFT_ENTRY: (False, -16, 0xF0, 178, 13, 0x1AE446,
        bytes.fromhex('33fcfff000fff150600833fc015000fff15033fc00f000fff152303900ff7e06020000f033c000ff7db0207900ff7dac43f841543c3900ff7e08020600f03a3900ff7db445f900ffae87383c000f')),
    SPAWN_SETUP_RIGHT_ENTRY: (False, 0x150, 0xF0, 168, 12, 0x1AE446,
        bytes.fromhex('33fc015000fff15033fc00f000fff152303900ff7e06020000f033c000ff7db0207900ff7dac43f841543c3900ff7e08020600f03a3900ff7db445f900ffae87383c000f')),
    SPAWN_SETUP_ROW_LOW_ENTRY: (True, -16, 0xF0, 162, 12, 0x1AE4C2,
        bytes.fromhex('33fc00f000fff152600833fc01e000fff15233fcfff000fff150303900ff7e08020000f033c000ff7db2207900ff7dac43f841543c3900ff7e06020600f045f900ffae87383c0016')),
    SPAWN_SETUP_ROW_HIGH_ENTRY: (True, -16, 0x1E0, 152, 11, 0x1AE4C2,
        bytes.fromhex('33fc01e000fff15233fcfff000fff150303900ff7e08020000f033c000ff7db2207900ff7dac43f841543c3900ff7e06020600f045f900ffae87383c0016')),
}


def spawn_setup_dispatch(machine, registers: dict[str, int], entry: int) -> AtomicPlan:
    """Recover one setup prefix, its selected bounded walker, and outer RTS."""
    try:
        row, x_offset, y_offset, cycles, instructions, prefix_last_pc, shape = SPAWN_SETUP_FACTS[entry]
    except KeyError as error:
        raise UnsupportedCandidate('unknown spawn setup entry') from error
    if machine.peek_rom(entry, len(shape)) != shape:
        raise UnsupportedCandidate('spawn setup ROM shape')
    inputs = game.prepare_spawn_strip(lambda address, size: _read(machine, address, size),
                                      row=row, x_offset=x_offset, y_offset=y_offset)
    writes = (*_bytes(0xFFF150, inputs['x_offset'], 2),
              *_bytes(0xFFF152, inputs['y_offset'], 2),
              *_bytes(0xFF7DB2 if row else 0xFF7DB0, inputs['position'], 2))
    prefix_registers = {**registers,
                        'd0': (registers['d0'] & 0xFFFF0000) | inputs['position'],
                        'd6': (registers['d6'] & 0xFFFF0000) | inputs['varying'],
                        'd4': (registers['d4'] & 0xFFFF0000) | (22 if row else 15),
                        'a0': inputs['cursor'], 'a1': 0x4154, 'a2': 0xFFAE87,
                        'sr': _logic_sr(registers['sr'], 22 if row else 15, 2),
                        'pc': SPAWN_ROW_DISPATCH_WALKER_ENTRY if row else SPAWN_DISPATCH_WALKER_ENTRY}
    if not row:
        prefix_registers['d5'] = (registers['d5'] & 0xFFFF0000) | inputs['stride']
    prefix = AtomicPlan(cycles, instructions, writes, prefix_registers, prefix_last_pc,
                        direct_calls=1)
    walker = (spawn_row_dispatch_walker if row else spawn_dispatch_walker)(
        dispatch_plan_view(machine, prefix), prefix.registers)
    combined = AtomicPlan(prefix.cycles + walker.cycles, prefix.instructions + walker.instructions,
                          tuple(dict((*prefix.writes, *walker.writes)).items()), walker.registers,
                          walker.last_pc, prefix.direct_calls + walker.direct_calls)
    final = dict(walker.registers)
    planned = dispatch_plan_view(machine, combined)
    outer = _read(planned, final['a7'], 4)
    final.update(a7=final['a7'] + 4, pc=outer & 0xFFFFFF)
    return AtomicPlan(combined.cycles + 16, combined.instructions + 1, combined.writes, final,
                      SPAWN_ROW_DISPATCH_WALKER_LAST_PC if row else SPAWN_DISPATCH_WALKER_LAST_PC,
                      combined.direct_calls)

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


def begin_contact_family_type1a(machine, registers):
    """1AE9E0's FFF0D8 gate, self pair-release and 1B7940 re-template.

    An active ``FFF0D8`` gate (nonzero) is required; clear, the callback
    returns at once with no writes.  Active, it sets ``FFF10E`` then runs
    the exact external 1ABE6E pair-release (``_clear_objects``, the same
    RAM-domain adapter already proven for ``clear_object_pair``) on the
    triggering record itself -- its own type byte and attached buffer, and
    if its own ``record+62`` link is set, that linked record's type byte
    and buffer too -- then re-expands the fixed 19-byte template at
    ``1B7940`` back into the (still-linked) triggering record through the
    exact 1AE30A adapter already proven for ``initialize_object`` /
    ``finish_object``.  Neither call is a native re-entry; both are plain
    68000 subroutines this boundary already owns, so this is one RAM-only
    leaf despite its two internal BSRs.  Cost table (each row additive):

        inactive (FFF0D8 clear)                                       42 /  3
        active, no buffer, no link                                   868 / 74
        + own buffer of length L                                 82+22L / 5+2L
        + linked record (no linked buffer)                          264 / 22
        + linked record's own buffer of length M                82+22M / 5+2M

    Nothing along this path is a CMP/SUB/NEG, so X survives unchanged from
    entry throughout; the closing CLR.L at 1AE36C is unconditionally the
    last flag-setting instruction on the active arm, so every active exit
    carries N=Z=V=C from that fixed zero regardless of data (Z=1) with only
    X preserved -- the inactive arm's own TST.B FFF0D8 (value 0 by
    definition) yields the identical Z=1 residue.
    """
    sp, sr = registers['a7'], registers['sr']
    if sp & 1:
        raise UnsupportedCandidate('unaligned type1a stack')
    return_pc = _read(machine, sp, 4)
    gate = _read(machine, 0xFFF0D8, 1)
    if not gate:
        _spans_disjoint([('type1a gate', 0xFFF0D8, 1), ('type1a return', sp, 4)])
        return AtomicPlan(42, 3, (), {'a7': sp + 4, 'pc': return_pc & 0xFFFFFF,
                                      'sr': _logic_sr(sr, 0, 1)}, 0x1AE9FE)
    record = registers['a1']
    cycles, instructions, clear_writes, linked = _clear_objects(
        machine, registers, sp=sp - 4, pair=True,
        extra_spans=(('type1a return', sp, 4), ('type1a gate', 0xFFF0D8, 1), ('type1a tail', 0xFFF10E, 1)))
    init_writes = _initialize_object_effects(machine, record=record, template=0x1B7940, entry_sp=sp - 4)
    # The second BSR (to 1AE30A) reuses the same sp-4 scratch slot the first
    # BSR (to 1ABE6E) used; only its final push (the resume-at-RTS address)
    # survives as a permanent RAM diff.
    writes = (*clear_writes, (0xFFF10E, 0xFF), *_bytes(sp - 4, 0x1AE9FE, 4), *init_writes)
    return AtomicPlan(112 + cycles + 476, 8 + instructions + 27, tuple(dict(writes).items()),
                      {'a5': record, 'a6': 0x1B7940 + 19, 'a7': sp + 4,
                       'pc': return_pc & 0xFFFFFF, 'sr': _logic_sr(sr, 0, 4)},
                      0x1AE9FE, direct_calls=2 + bool(linked))


def begin_contact_family_type1a_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE1A_ENTRY,
                                    begin_contact_family_type1a)


def begin_contact_family_type23(machine, registers):
    """1AEECA's FFF0D8 gate, self-retype and double pool-slot spawn.

    An active FFF0D8 gate is required; clear, the callback returns at once
    with no writes.  Active, the triggering record retypes itself to a used
    kind-0x84 marker (``game.contact_type23_retype``) before either spawn
    attempt, then a child is sought in the FF7F06 pool exactly as
    ``begin_contact_family_type74``'s own scan (``game.free_object``, same
    20-slot pool); found, it is expanded from the fixed 1B79B8 template
    (``game.initialize``), given the triggering record's own position
    (``game.contact_type74_position``, the same primitive already proven
    for that spawn), and then retyped a second time to kind 0x3B with its
    own +0x20 long field overwritten (``game.contact_type23_override`` --
    the fresh template's own values at those offsets are discarded).  Only
    then is a second child sought in the wider 24-slot FF7E82 pool (the
    same pool the contact scan itself walks); found, it is expanded from
    the fixed 1B7CC4 template and given the same triggering-record
    position, with no further retype.  Either pool exhausted abandons only
    what follows it; the first pool's own spawn, once committed, is never
    undone.  Neither spawn is a native re-entry: both reuse the exact
    1AE262/1AE30A adapters already proven for
    ``begin_contact_family_type74``, so despite four internal BSRs this is
    one RAM-only leaf.  Cost table (``factcheck``, i and j the zero-based
    index each pool's search finds its slot at):

        inactive                                                       42 /   3
        active, primary pool exhausted                              1022 /  96
        active, primary slot at index i, secondary pool exhausted  1878+40i / 154+4i
        active, primary slot i, secondary slot j                  1476+40i+40j / 91+4i+4j

    Nothing on this path is a CMP/SUB/NEG, so X survives unchanged from
    entry throughout.  A primary-pool exhaustion's own residue is the last
    slot the scan actually tested (index 19, not the one-past address A5
    is left holding -- the same distinction ``begin_contact_family_type74``
    already documents for the identical 1AE262 scan); a secondary-pool
    exhaustion's residue is likewise its own last tested slot (index 23).
    Either pool's own successful find instead carries through to the
    closing position copy, whose final MOVE.W (the child's Y coordinate)
    is what every completed spawn's exit flags actually come from.
    """
    sp, sr = registers['a7'], registers['sr']
    if sp & 1:
        raise UnsupportedCandidate('unaligned type23 stack')
    return_pc = _read(machine, sp, 4)
    read = lambda address, size: _read(machine, address, size)
    gate = read(0xFFF0D8, 1)
    if not gate:
        _spans_disjoint([('type23 gate', 0xFFF0D8, 1), ('type23 return', sp, 4)])
        return AtomicPlan(42, 3, (), {'a7': sp + 4, 'pc': return_pc & 0xFFFFFF,
                                      'sr': _logic_sr(sr, 0, 1)}, 0x1AEEDC)
    record = registers['a1']
    a2, a6 = registers['a2'], registers['a6']
    if record & 1:
        raise UnsupportedCandidate('unaligned type23 record')
    _spans_disjoint([('type23 record', record, 66), ('type23 return', sp, 4),
                     ('type23 gate', 0xFFF0D8, 1), ('type23 frame', sp - 16, 16)])
    _spans_disjoint([('type23 primary pool', 0xFF7F06, 20 * 66), ('type23 return', sp, 4),
                     ('type23 frame', sp - 16, 16)])
    _spans_disjoint([('type23 secondary pool', 0xFF7E82, 24 * 66), ('type23 return', sp, 4),
                     ('type23 frame', sp - 16, 16)])
    retype = tuple(game.contact_type23_retype(record))
    x, y = read(record + 2, 2), read(record + 4, 2)
    # The outer two BSRs (1AEECA's own call to 1ABFFA, then 1ABFFA's first
    # call to 1AE262) always leave their resume address as a permanent
    # scratch diff -- a2's saved value at sp-4, then 0x1AC00E at sp-12,
    # both at the depth 1ABFFA's own frame runs at (its own return sits at
    # sp-8).  Whichever later BSR runs last at that same sp-12 depth
    # (1ABFFA's own frame never grows past this one nested call at a time)
    # overwrites 0x1AC00E in turn; sp-16 only ever receives a value when
    # the primary spawn's own 1AC0BA wrapper runs its nested 1AE30A call.
    base_scratch = (*_bytes(sp - 4, a2, 4), *_bytes(sp - 8, 0x1AEEDA, 4))
    slot1, index1 = game.free_object(read, 0xFF7F06, 20)
    if slot1 is None:
        last = read(0xFF7F06 + 19 * 66, 1)
        return AtomicPlan(1022, 96, (*retype, *base_scratch, *_bytes(sp - 12, 0x1AC00E, 4)),
                          {'a2': a2, 'a5': 0xFF7F06 + 20 * 66, 'a6': a6, 'd0': (registers['d0'] & 0xFFFF0000) | 0xFFFF,
                           'a7': sp + 4, 'pc': return_pc & 0xFFFFFF, 'sr': _logic_sr(sr, last, 1)},
                          0x1AEEDC)
    template1 = machine.peek_rom(0x1B79B8, 19)
    init1 = tuple(game.initialize(slot1, template1))
    position1 = tuple(game.contact_type74_position(slot1, x, y))
    override1 = tuple(game.contact_type23_override(slot1))
    a6_after_1 = 0x1B79B8 + 19
    cycles1, instructions1 = 1476 + 40 * index1, 91 + 4 * index1
    exhausted_extra_cycles, exhausted_extra_instructions = 402, 63
    # The secondary pool's own scan runs after the primary spawn's writes
    # (including its retype override) are already live in RAM; a plan view
    # exposes them to game.free_object exactly as the real 1AE27A scan
    # would see them, so a just-filled primary slot is never mistaken for
    # a free secondary one.
    committed = (*retype, *init1, *position1, *override1)
    view_read = lambda address, size: _read(dispatch_plan_view(machine, AtomicPlan(0, 0, committed, {}, 0)), address, size)
    slot2, index2 = game.free_object(view_read, 0xFF7E82, 24)
    if slot2 is None:
        last = view_read(0xFF7E82 + 23 * 66, 1)
        return AtomicPlan(cycles1 + exhausted_extra_cycles, instructions1 + exhausted_extra_instructions,
                          (*retype, *base_scratch, *_bytes(sp - 12, 0x1AC024, 4), *_bytes(sp - 16, 0x1AC0C4, 4),
                           *init1, *position1, *override1),
                          {'a2': a2, 'a5': 0xFF7E82 + 24 * 66, 'a6': a6_after_1,
                           'd0': (registers['d0'] & 0xFFFF0000) | 0xFFFF,
                           'a7': sp + 4, 'pc': return_pc & 0xFFFFFF, 'sr': _logic_sr(sr, last, 1)},
                          0x1AEEDC)
    template2 = machine.peek_rom(0x1B7CC4, 19)
    init2 = tuple(game.initialize(slot2, template2))
    position2 = tuple(game.contact_type74_position(slot2, x, y))
    return AtomicPlan(cycles1 + 40 * index2, instructions1 + 4 * index2,
                      (*retype, *base_scratch, *_bytes(sp - 12, 0x1AC030, 4), *_bytes(sp - 16, 0x1AC0C4, 4),
                       *init1, *position1, *override1, *init2, *position2),
                      {'a2': a2, 'a5': slot2, 'a6': 0x1B7CC4 + 19,
                       'd0': (registers['d0'] & 0xFFFF0000) | ((0x17 - index2) & 0xFFFF),
                       'a7': sp + 4, 'pc': return_pc & 0xFFFFFF, 'sr': _logic_sr(sr, y, 2)},
                      0x1AEEDC)


def begin_contact_family_type23_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE23_ENTRY,
                                    begin_contact_family_type23)


def _begin_contact_family_noop(machine, registers, entry_pc):
    """Shared shape for a dispatch-table slot whose whole body is an
    unconditional RTS: no gate, no write, no flag change (RTS never
    touches CCR, and nothing before it runs at all)."""
    sp, sr = registers['a7'], registers['sr']
    if sp & 1:
        raise UnsupportedCandidate('unaligned noop stack')
    return_pc = _read(machine, sp, 4)
    _spans_disjoint([('noop return', sp, 4)])
    return AtomicPlan(16, 1, (), {'a7': sp + 4, 'pc': return_pc & 0xFFFFFF, 'sr': sr}, entry_pc)


def begin_contact_family_type0d(machine, registers):
    """1AEB7A's entire body is an unconditional RTS."""
    return _begin_contact_family_noop(machine, registers, 0x1AEB7A)


def begin_contact_family_type0d_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE0D_ENTRY,
                                    begin_contact_family_type0d)


def begin_contact_family_type14(machine, registers):
    """1AEBFE's entire body is an unconditional RTS.  Reached by both the
    kind-0x14 and kind-0x2B collection-dispatch slots."""
    return _begin_contact_family_noop(machine, registers, 0x1AEBFE)


def begin_contact_family_type14_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE14_ENTRY,
                                    begin_contact_family_type14)


def begin_contact_family_type0c(machine, registers):
    """1AE9A8's FFF0D8 gate, own-buffer release and 1B7CC4 re-template.

    Same shape as ``begin_contact_family_type1a`` but simpler: no linked
    record at all, just the triggering record's own type byte and attached
    buffer (``_clear_objects`` with ``pair=False``, the same RAM-domain
    adapter already proven for ``clear_auxiliary_buffer``), then the exact
    1AE30A adapter already proven for
    ``initialize_object``/``finish_object``/``begin_contact_family_type1a``
    re-expands a different fixed 19-byte template (1B7CC4, the same one
    ``begin_contact_family_type23``'s own secondary spawn uses) into the
    same record.  Neither call is a native re-entry.  Cost table
    (``factcheck``):

        inactive (FFF0D8 clear)                                       42 /  3
        active, no buffer                                            868 / 74
        + own buffer of length L                                 82+22L / 5+2L

    Nothing on this path is a CMP/SUB/NEG, so X survives unchanged from
    entry throughout; the closing CLR.L at 1AE36C is unconditionally the
    last flag-setting instruction on the active arm (nothing follows it
    here, unlike Type-23's own trailing position copy), so every active
    exit carries the fixed Z=1 residue with only X preserved from entry --
    the inactive arm's own TST.B FFF0D8 (value 0 by definition) yields the
    identical Z=1 residue.
    """
    sp, sr = registers['a7'], registers['sr']
    if sp & 1:
        raise UnsupportedCandidate('unaligned type0c stack')
    return_pc = _read(machine, sp, 4)
    gate = _read(machine, 0xFFF0D8, 1)
    if not gate:
        _spans_disjoint([('type0c gate', 0xFFF0D8, 1), ('type0c return', sp, 4)])
        return AtomicPlan(42, 3, (), {'a7': sp + 4, 'pc': return_pc & 0xFFFFFF,
                                      'sr': _logic_sr(sr, 0, 1)}, 0x1AE9C4)
    record = registers['a1']
    cycles, instructions, clear_writes, linked = _clear_objects(
        machine, registers, sp=sp - 4, pair=False,
        extra_spans=(('type0c return', sp, 4), ('type0c gate', 0xFFF0D8, 1)))
    init_writes = _initialize_object_effects(machine, record=record, template=0x1B7CC4, entry_sp=sp - 4)
    # The second BSR (to 1AE30A) reuses the same sp-4 scratch slot the
    # first BSR (to 1AE372) used; only its final push survives.
    writes = (*clear_writes, *_bytes(sp - 4, 0x1AE9C4, 4), *init_writes)
    return AtomicPlan(108 + cycles + 476, 8 + instructions + 27, tuple(dict(writes).items()),
                      {'a5': record, 'a6': 0x1B7CC4 + 19, 'a7': sp + 4,
                       'pc': return_pc & 0xFFFFFF, 'sr': _logic_sr(sr, 0, 4)},
                      0x1AE9C4, direct_calls=2 + bool(linked))


def begin_contact_family_type0c_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE0C_ENTRY,
                                    begin_contact_family_type0c)


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


def begin_collection_type3a_dispatch(machine, registers, dispatch):
    """Compose 1AF228: the shared FFEFE2/FFEFE3 counter (1B0394), an optional
    command-0x0D sound seam, and the already-proven 1AF4C2 replace tail.

    FFEFE2 reaching the 0x3939 sentinel is not recovered here: original
    continues through 1AE6DE's own table-write arm, which is exactly the
    ``game.collection_state('secondary', ...)`` formula ``begin_collection``
    already reuses for kinds 'primary'/'secondary' -- but that arm is not
    observed on the recorded history for this entry, so it declines here.
    Short of the cap, the counter's own advance is exactly
    ``game.collection_state(..., 'secondary')`` (``game.increment_counter``
    shifted +2, to FFEFE2/FFEFE3 instead of FFEFE0/FFEFE1) -- the same
    arithmetic 1B0394 performs with raw ADDQ/CMPI rather than an
    ASCII-boundary test.  A pass always joins the already-proven
    ``replace_object(increment_total=True)`` tail (0x1AF4C2..0x1AF4D6,
    template 0x1B7ABC) after an optional command-0x0D sound seam, the same
    24-byte-saved-frame/28-byte-return-delta ABI shape as
    ``begin_object_transition``'s own command-11 seam.  Cost table
    (``factcheck``), each row exclusive of ``replace_object`` itself:

        own gate (CMPI/BNE/BSR) plus 1B0394, no rollover       48 + 94
        own gate plus 1B0394, rollover (FFEFE3 wraps to '0')  48 + 132
        no-sound suffix (TST.B/BEQ taken/BRA)                         36
        sound prefix through the native request entry (TST.B/
        BEQ not-taken/MOVEM/PEA/JSR)                                 108
    """
    callback = {**registers, **dispatch.registers}
    record, sp, sr = (callback[key] for key in ('a1', 'a7', 'sr'))
    if callback['pc'] != COLLECTION_TYPE3A_ENTRY or sp != registers['a7'] - 4:
        raise UnsupportedCandidate('type3a dispatch identity')
    view = dispatch_plan_view(machine, dispatch)
    read = lambda address, size: _read(view, address, size)
    _spans_disjoint([('type3a return', sp, 4), ('type3a counter', 0xFFEFE2, 2),
                     ('type3a sound', 0xFFF57D, 1)])
    digits = read(0xFFEFE2, 2)
    if digits == 0x3939:
        raise UnsupportedCandidate('type3a capped counter arm is not recovered')
    try:
        counter_writes = list(game.collection_state(read, record, 'secondary'))
    except ValueError as error:
        raise UnsupportedCandidate(str(error)) from error
    rollover = digits & 0xFF == 0x39
    gate_cycles = dispatch.cycles + 48 + (132 if rollover else 94)
    gate_instructions = dispatch.instructions + 3 + (8 if rollover else 6)
    sound = read(0xFFF57D, 1)
    sr = _logic_sr(sr & ~0x10, sound, 1)
    if not sound:
        tail = replace_object(view, {**callback, 'sr': sr}, increment_total=True,
                              extra_spans=(('type3a counter', 0xFFEFE2, 2),))
        writes = tuple(dict((*dispatch.writes, *counter_writes, *tail.writes)).items())
        final = {**callback, **tail.registers}
        return AtomicPlan(gate_cycles + 36 + tail.cycles, gate_instructions + 3 + tail.instructions,
                          writes, final, tail.last_pc,
                          direct_calls=dispatch.direct_calls + 2 + tail.direct_calls)
    writes = [*dispatch.writes, *counter_writes]
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        writes.extend(_bytes(sp - index * 4, callback[name], 4))
    writes.extend(_bytes(sp - 24, 0xD, 4))
    writes.extend(_bytes(sp - 28, 0x1AF252, 4))
    plan = AtomicPlan(gate_cycles + 108, gate_instructions + 5, tuple(dict(writes).items()),
                      {**callback, 'a7': sp - 28, 'pc': 0x1E58B8, 'sr': sr}, 0x1AF24C,
                      direct_calls=dispatch.direct_calls + 2)
    return SoundSeam(plan, sp, 0x1AF258, 0x1AF258, 24, 28, 28,
                     suffix=finish_collection_type3a)


def finish_collection_type3a(machine, registers):
    """Restore Type-3A's MOVEM frame, then join the 1AF4C2 replace tail."""
    sp = registers['a7'] + 24
    restored = dict(registers, a7=sp)
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        restored[name] = _read(machine, sp - index * 4, 4)
    tail = replace_object(machine, restored, increment_total=True)
    final = {name: restored[name] for name in ('d0', 'd1', 'a0', 'a1')}
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
    if target not in (*COLLECTION_ROUTES, CONTACT_DISPATCH_ENTRY, CONTACT_ACTIVATION_ENTRY,
                      CONTACT_FAMILY_66_ENTRY, CONTACT_FAMILY_MOTION_ENTRY,
                      CONTACT_FAMILY_SECONDARY_MOTION_ENTRY, CONTACT_FAMILY_SOUND_ENTRY,
                      CONTACT_FAMILY_TYPE79_ENTRY,
                      CONTACT_FAMILY_TYPE1F_ENTRY,
                      CONTACT_FAMILY_TYPE15_ENTRY,
                      CONTACT_FAMILY_TYPE44_ENTRY,
                      CONTACT_FAMILY_TYPE03_ENTRY,
                      CONTACT_FAMILY_TYPE46_ENTRY,
                      CONTACT_FAMILY_TYPE55_ENTRY,
                      CONTACT_FAMILY_TYPE58_ENTRY,
                      CONTACT_FAMILY_TYPE63_ENTRY,
                      CONTACT_FAMILY_TYPE74_ENTRY,
                      CONTACT_FAMILY_TYPE6E_ENTRY,
                      CONTACT_FAMILY_TYPE1A_ENTRY,
                      CONTACT_FAMILY_TYPE23_ENTRY,
                      CONTACT_FAMILY_TYPE0D_ENTRY,
                      CONTACT_FAMILY_TYPE14_ENTRY,
                      CONTACT_FAMILY_TYPE0C_ENTRY,
                      CONTACT_FAMILY_TYPE78_ENTRY,
                      CONTACT_FAMILY_TYPE2C_ENTRY,
                      CONTACT_FAMILY_TYPE43_ENTRY,
                      COLLECTION_TYPE3A_ENTRY,
                      CONTACT_COLLECTION_RELOCATION_ENTRY,
                      CONTACT_TYPE7E_ENTRY,
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


def _contact_completion_btst(sr, value):
    return (sr & ~0x04) | (0x04 if not (value & 0x10) else 0)


def complete_contact_plan(machine, registers):
    """Exact 1ABCA0 completion suffix through the scan advance label."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact completion record/stack')
    live = ((0xFF7DF6, 2), (0xFF7DF8, 2), (0xFF7DFA, 2), (0xFF7DFC, 2),
            (0xFF7E02, 2), (0xFF7E04, 2), (0xFF7E42, 2), (0xFF7E44, 2),
            (0xFF7E5A, 2), (0xFF7E60, 4), (0xFF7E77, 1), (0xFFF0F5, 1),
            (0xFFF0BE, 1), (0xFFF0C0, 1), (0xFFF0E7, 1), (0xFFF0C1, 1),
            (0xFFF0CC, 1), (0xFFF0CD, 1), (0xFFF0D3, 1), (0xFFF0EB, 1),
            (0xFFF173, 1), (0xFFF0B0, 2), (0xFFF101, 1))
    # The BSR slot must not alias the position stores: otherwise the original
    # helper's own RTS would consume a changed return address.
    _spans_disjoint([('contact completion record', record, 66),
                     ('contact completion return', sp - 4, 4),
                     *(('contact completion live', address, size) for address, size in live)])
    read = lambda address, size: _read(machine, address, size)
    flags = read(record + 6, 1)
    d0 = (registers['d0'] & 0xFFFFFF00) | flags
    sr = _contact_completion_btst(_logic_sr(sr, flags, 1), flags)
    final = {**registers, 'd0': d0, 'a7': sp, 'pc': CONTACT_COMPLETION_EXIT}
    if not flags & 0x10:
        return AtomicPlan(32, 3, (), {**final, 'sr': sr}, 0x1ABCA8)
    block = read(0xFFF0F5, 1)
    sr = _logic_sr(sr, block, 1)
    if block:
        return AtomicPlan(60, 5, (), {**final, 'sr': sr}, 0x1ABCB2)
    be = read(0xFFF0BE, 1)
    extra_cycles = extra_instructions = 0
    sr = _logic_sr(sr, be, 1)
    if be:
        c0 = read(0xFFF0C0, 1)
        sr = _logic_sr(sr, c0, 1)
        if not c0:
            return AtomicPlan(116, 9, (), {**final, 'sr': sr}, 0x1ABCC6)
        extra_cycles, extra_instructions = 50, 3
    writes = [(0xFFF0BE, 0)]
    e7 = read(0xFFF0E7, 1)
    sr = _logic_sr(sr, e7, 1)
    if e7:
        return AtomicPlan(114 + extra_cycles, 9 + extra_instructions,
                          tuple(writes), {**final, 'sr': sr}, 0x1ABCD6)
    vertical = read(0xFF7E5A, 2)
    sr = _logic_sr(sr, vertical, 2)
    kind = read(record, 1)
    cycles, instructions, script = 384, 25, None
    if vertical:
        script = game.contact_landing_script(read, kind)
        cycles, instructions = {0x121964: (544, 35), 0x121F74: (570, 37),
                                0x1220AA: (588, 38), 0x121F84: (644, 41),
                                0x121BB6: (670, 42)}[script]
        if kind < 0x50:
            # The first CMP/BCS reaches the common selector without the
            # second type-range CMP/BCC used by kinds >= 0x52.
            cycles -= 20
            instructions -= 2
    writes.extend(game.complete_contact_landing(kind, script))
    writes.extend(_bytes(sp - 4, CONTACT_COMPLETION_EXIT, 4))
    x, y = game.contact_position(read)
    writes.extend(game.publish_contact_position(x, y))
    final.update(d0=(registers['d0'] & 0xFFFF0000) | y,
                 sr=_logic_sr(_add_sr(sr, read(0xFF7DF8, 2), read(0xFF7DFC, 2), 2), y, 2))
    return AtomicPlan(cycles + extra_cycles, instructions + extra_instructions,
                      tuple(dict(writes).items()), final, 0x1A8E3C, direct_calls=1)


def extend_contact_completion(machine, plan):
    """Compose a completed callback's planned RAM residue with 1ABCA0."""
    if plan.registers.get('pc') != COLLECTION_DISPATCH_RETURN:
        raise UnsupportedCandidate('contact completion entry identity')
    registers = {**machine.registers(), **plan.registers}
    suffix = complete_contact_plan(dispatch_plan_view(machine, plan), registers)
    return AtomicPlan(plan.cycles + suffix.cycles, plan.instructions + suffix.instructions,
                      tuple(dict((*plan.writes, *suffix.writes)).items()), suffix.registers,
                      suffix.last_pc, plan.direct_calls + suffix.direct_calls)


_CONTACT_SCAN_COST = {
    'inactive': (18, 2, 0x1ABBE2), 'non-contact-kind': (42, 4, 0x1ABBEA),
    'no-shape': (70, 6, 0x1ABBF2), 'left': (168, 15, 0x1ABC20),
    'above': (240, 23, 0x1ABC3A), 'right': (322, 31, 0x1ABC64),
    'below': (394, 39, 0x1ABC7E), 'contact': (396, 39, 0x1ABC7E),
}


def _contact_scan_source(machine, address, size):
    if 0xff0000 <= address <= 0xffffff:
        return _read(machine, address, size)
    if 0 <= address < 0x200000 and not (size > 1 and address & 1):
        return int.from_bytes(machine.peek_rom(address, size), 'big')
    raise UnsupportedCandidate('contact scan descriptor is neither aligned ROM nor work RAM')


def _contact_scan_prefix(machine, registers):
    facts = game.contact_scan_collision(lambda address, size: _read(machine, address, size),
                                        lambda address, size: _contact_scan_source(machine, address, size),
                                        record=registers['a1'], player=registers['a2'],
                                        player_shape=registers['a3'])
    branch = facts['branch']; cycles, instructions, last_pc = _CONTACT_SCAN_COST[branch]
    sr = registers['sr']; kind = _read(machine, registers['a1'], 1)
    if branch == 'inactive':
        residue = _logic_sr(sr, kind, 1)
    else:
        residue = _cmp_sr(sr, kind, 0x7f, 1)
        if branch == 'no-shape':
            residue = _logic_sr(residue, 0, 4)
        elif branch not in ('non-contact-kind',):
            horizontal = branch in ('left', 'right')
            axis = 'horizontal' if horizontal else 'vertical'
            object_edge = facts[f'object_{axis}_edge']
            origin = _read(machine, registers['a1'] + (2 if horizontal else 4), 2)
            # The final object-edge ADD.W owns X. CMP preserves that bit;
            # subsequent rejected/inactive scan slots preserve it as well.
            residue = (residue & ~0x10) | (0x10 if object_edge < origin else 0)
            residue = _cmp_sr(residue, facts[f'player_{axis}_edge'], object_edge, 2)
            if facts.get('mirrored'):
                cycles += 12 if branch in ('left', 'above') else 24
                instructions += 2 if branch in ('left', 'above') else 4
    final = dict(registers)
    for name, fact in (('d0', 'player_horizontal_edge'), ('d1', 'player_vertical_edge'),
                       ('d2', 'object_horizontal_edge'), ('d3', 'object_vertical_edge')):
        if fact in facts:
            final[name] = (final[name] & 0xffff0000) | facts[fact]
    if 'shape' in facts:
        final['a0'] = facts['shape']
    final.update(sr=residue, pc=COLLECTION_DISPATCH_ENTRY if branch == 'contact' else CONTACT_COMPLETION_EXIT)
    return AtomicPlan(cycles, instructions, (), final, last_pc), branch


def _join_plans(first, second):
    final = dict(first.registers); final.update(second.registers)
    return AtomicPlan(first.cycles + second.cycles, first.instructions + second.instructions,
                      tuple(dict((*first.writes, *second.writes)).items()), final, second.last_pc,
                      first.direct_calls + second.direct_calls)


def _contact_type1f_ram_dispatch(machine, registers, dispatch):
    """Reuse the qualified finite type-1F paths inside the contact scan."""
    for planner in (begin_contact_family_type1f_inactive_dispatch,
                    begin_contact_family_type1f_transition_dispatch,
                    begin_contact_family_type1f_transition_soundoff_dispatch,
                    begin_contact_family_type1f_contact_dispatch):
        try:
            return planner(machine, registers, dispatch)
        except UnsupportedCandidate:
            pass
    raise UnsupportedCandidate('contact scan type1f requires original sound/device path')


def contact_scan_plan(machine, registers):
    """Exact 1ABBD6 24-record scan through the instruction before its RTS."""
    if registers.get('pc') != CONTACT_SCAN_ENTRY:
        raise UnsupportedCandidate('contact scan entry identity')
    callbacks = {
        CONTACT_FAMILY_TYPE79_ENTRY: begin_contact_family_type79_dispatch,
        CONTACT_FAMILY_TYPE1F_ENTRY: _contact_type1f_ram_dispatch,
        CONTACT_FAMILY_TYPE15_ENTRY: begin_contact_family_type15_dispatch,
        CONTACT_FAMILY_TYPE44_ENTRY: begin_contact_family_type44_dispatch,
        CONTACT_FAMILY_TYPE55_ENTRY: begin_contact_family_type55_dispatch,
        CONTACT_FAMILY_TYPE58_ENTRY: begin_contact_family_type58_dispatch,
        CONTACT_FAMILY_TYPE74_ENTRY: begin_contact_family_type74_dispatch,
        CONTACT_FAMILY_TYPE6E_ENTRY: begin_contact_family_type6e_dispatch,
        CONTACT_FAMILY_TYPE1A_ENTRY: begin_contact_family_type1a_dispatch,
        CONTACT_FAMILY_TYPE23_ENTRY: begin_contact_family_type23_dispatch,
        CONTACT_FAMILY_TYPE0D_ENTRY: begin_contact_family_type0d_dispatch,
        CONTACT_FAMILY_TYPE14_ENTRY: begin_contact_family_type14_dispatch,
        CONTACT_FAMILY_TYPE0C_ENTRY: begin_contact_family_type0c_dispatch,
        CONTACT_FAMILY_TYPE78_ENTRY: begin_contact_family_type78_dispatch,
        CONTACT_FAMILY_TYPE63_ENTRY: begin_contact_family_type63_dispatch,
        CONTACT_FAMILY_TYPE2C_ENTRY: begin_contact_family_type2c_dispatch,
        CONTACT_COLLECTION_RELOCATION_ENTRY: begin_contact_collection_relocation_dispatch,
        CONTACT_FAMILY_66_ENTRY: begin_contact_family_66_dispatch,
        CONTACT_FAMILY_MOTION_ENTRY: begin_contact_family_motion_dispatch,
        CONTACT_FAMILY_SECONDARY_MOTION_ENTRY: begin_contact_family_secondary_dispatch,
        CONTACT_TYPE7E_ENTRY: begin_contact_type7e_dispatch,
        CONTACT_ACTIVATION_ENTRY: begin_contact_activation_dispatch,
    }
    current = AtomicPlan(20, 2, (), {**registers, 'a1': 0xff7e82,
                         'd4': (registers['d4'] & 0xffff0000) | 23,
                         'pc': 0x1ABBE0, 'sr': _logic_sr(registers['sr'], 23, 2)}, 0x1ABBDC)
    for slot in range(24):
        prefix, branch = _contact_scan_prefix(dispatch_plan_view(machine, current), current.registers)
        step = prefix
        if branch == 'contact':
            view = dispatch_plan_view(machine, _join_plans(current, prefix))
            target, dispatch = begin_collection_dispatch(view, prefix.registers)
            if target in (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
                callback = begin_contact_sibling_dispatch(view, prefix.registers, dispatch, target)
            else:
                planner = callbacks.get(target)
                if planner is None:
                    raise UnsupportedCandidate(f'contact scan callback at slot {slot}: {target:06X} unresolved/device-or-sound')
                callback = planner(view, prefix.registers, dispatch)
            if callback.registers.get('pc') != COLLECTION_DISPATCH_RETURN:
                raise UnsupportedCandidate(f'contact scan callback at slot {slot}: noncompletion handoff')
            callback_registers = dict(prefix.registers)
            callback_registers.update(dispatch.registers)
            callback_registers.update(callback.registers)
            complete = complete_contact_plan(dispatch_plan_view(machine, _join_plans(_join_plans(current, prefix), callback)),
                                             callback_registers)
            step = _join_plans(prefix, _join_plans(callback, complete))
        aggregate = _join_plans(current, step)
        state = dict(aggregate.registers); remaining = state['d4'] & 0xffff
        state.update(a1=(state['a1'] + 66) & 0xffffff,
                     d4=(state['d4'] & 0xffff0000) | ((remaining - 1) & 0xffff),
                     pc=CONTACT_SCAN_EXIT if slot == 23 else 0x1ABBE0)
        current = _join_plans(aggregate, AtomicPlan(28 if slot == 23 else 24, 2, (), state, 0x1ABD78))
    return current


def _contact_scan_resume(machine, registers):
    """Continue a validated scan at 1ABD74 from live post-callback state."""
    if registers.get('pc') != CONTACT_COMPLETION_EXIT:
        raise UnsupportedCandidate('contact scan resume identity')
    remaining = registers['d4'] & 0xffff
    if remaining > 23 or registers['a1'] != 0xff7e82 + (23 - remaining) * 66:
        raise UnsupportedCandidate('contact scan resume cursor')
    current = AtomicPlan(0, 0, (), dict(registers), CONTACT_COMPLETION_EXIT)
    # Advancing from 1ABD74 is part of the resumed original loop; each later
    # iteration reuses the ordinary collision/callback recipes.
    while True:
        state = dict(current.registers); remaining = state['d4'] & 0xffff
        state.update(a1=(state['a1'] + 66) & 0xffffff,
                     d4=(state['d4'] & 0xffff0000) | ((remaining - 1) & 0xffff),
                     pc=CONTACT_SCAN_EXIT if remaining == 0 else 0x1ABBE0)
        current = _join_plans(current, AtomicPlan(28 if remaining == 0 else 24, 2, (), state, 0x1ABD78))
        if remaining == 0:
            return current
        # Re-enter the established whole-scan planner at the live cursor by
        # borrowing its one-slot body through a bounded synthetic tail.
        prefix, branch = _contact_scan_prefix(dispatch_plan_view(machine, current), current.registers)
        if branch == 'contact':
            view = dispatch_plan_view(machine, _join_plans(current, prefix))
            target, dispatch = begin_collection_dispatch(view, prefix.registers)
            planners = {CONTACT_FAMILY_TYPE79_ENTRY: begin_contact_family_type79_dispatch,
                        CONTACT_FAMILY_TYPE1F_ENTRY: _contact_type1f_ram_dispatch,
                        CONTACT_FAMILY_TYPE15_ENTRY: begin_contact_family_type15_dispatch,
                        CONTACT_FAMILY_TYPE44_ENTRY: begin_contact_family_type44_dispatch,
                        CONTACT_FAMILY_TYPE55_ENTRY: begin_contact_family_type55_dispatch,
                        CONTACT_FAMILY_TYPE58_ENTRY: begin_contact_family_type58_dispatch,
                        CONTACT_FAMILY_TYPE74_ENTRY: begin_contact_family_type74_dispatch,
        CONTACT_FAMILY_TYPE6E_ENTRY: begin_contact_family_type6e_dispatch,
        CONTACT_FAMILY_TYPE1A_ENTRY: begin_contact_family_type1a_dispatch,
        CONTACT_FAMILY_TYPE23_ENTRY: begin_contact_family_type23_dispatch,
        CONTACT_FAMILY_TYPE0D_ENTRY: begin_contact_family_type0d_dispatch,
        CONTACT_FAMILY_TYPE14_ENTRY: begin_contact_family_type14_dispatch,
        CONTACT_FAMILY_TYPE0C_ENTRY: begin_contact_family_type0c_dispatch,
        CONTACT_FAMILY_TYPE78_ENTRY: begin_contact_family_type78_dispatch,
        CONTACT_FAMILY_TYPE63_ENTRY: begin_contact_family_type63_dispatch,
        CONTACT_FAMILY_TYPE2C_ENTRY: begin_contact_family_type2c_dispatch,
                        CONTACT_COLLECTION_RELOCATION_ENTRY: begin_contact_collection_relocation_dispatch,
                        CONTACT_FAMILY_66_ENTRY: begin_contact_family_66_dispatch,
                        CONTACT_FAMILY_MOTION_ENTRY: begin_contact_family_motion_dispatch,
                        CONTACT_FAMILY_SECONDARY_MOTION_ENTRY: begin_contact_family_secondary_dispatch,
                        CONTACT_TYPE7E_ENTRY: begin_contact_type7e_dispatch,
                        CONTACT_ACTIVATION_ENTRY: begin_contact_activation_dispatch}
            if target in (TRANSITION_ENTRY, 0x1AF4D8):
                raise UnsupportedCandidate('later collection sound requires local fallback')
            if target in (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
                callback = begin_contact_sibling_dispatch(view, prefix.registers, dispatch, target)
            else:
                planner = planners.get(target)
                if planner is None:
                    raise UnsupportedCandidate(f'resumed contact scan callback {target:06X} unsupported')
                callback = planner(view, prefix.registers, dispatch)
            if callback.registers.get('pc') != COLLECTION_DISPATCH_RETURN:
                raise UnsupportedCandidate('resumed contact scan noncompletion handoff')
            overlay = dict(prefix.registers); overlay.update(dispatch.registers); overlay.update(callback.registers)
            complete = complete_contact_plan(dispatch_plan_view(machine, _join_plans(_join_plans(current, prefix), callback)), overlay)
            current = _join_plans(current, _join_plans(prefix, _join_plans(callback, complete)))
        else:
            current = _join_plans(current, prefix)


def begin_contact_step_sound(machine, registers):
    """Plan the parent prefix through its first supported callback sound call."""
    prefix = _contact_step_prefix(machine, registers)
    if prefix.registers.get('pc') != CONTACT_SCAN_ENTRY:
        raise UnsupportedCandidate('contact tick has no scan sound path')
    current = AtomicPlan(prefix.cycles + 20, prefix.instructions + 2, prefix.writes,
        {**prefix.registers, 'a1': 0xff7e82,
         'd4': (prefix.registers['d4'] & 0xffff0000) | 23,
         'pc': 0x1ABBE0, 'sr': _logic_sr(prefix.registers['sr'], 23, 2)}, 0x1ABBDC,
        prefix.direct_calls)
    for slot in range(24):
        collision, branch = _contact_scan_prefix(dispatch_plan_view(machine, current), current.registers)
        if branch == 'contact':
            view = dispatch_plan_view(machine, _join_plans(current, collision))
            target, dispatch = begin_collection_dispatch(view, collision.registers)
            callback_registers = dict(collision.registers); callback_registers.update(dispatch.registers)
            if target in (TRANSITION_ENTRY, 0x1AF4D8):
                sound, legacy = begin_collection(dispatch_plan_view(view, dispatch), callback_registers, target)
                if not legacy or sound.registers.get('pc') != 0x1E58B8:
                    raise UnsupportedCandidate('contact tick collection sound identity')
                planned = _join_plans(current, _join_plans(collision, _join_plans(dispatch, sound)))
                resume = COLLECTION_ROUTES[target][1]
                return SoundSeam(planned, callback_registers['a7'], resume, resume, 24, 28, 28,
                                 suffix=lambda live, returned: finish_contact_step_sound(live, returned, target))
            if target in (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
                sound = begin_contact_sibling_dispatch_sound_seam(
                    view, collision.registers, dispatch, target)
                planned = _join_plans(current, _join_plans(collision, sound.prefix))
                return SoundSeam(
                    planned, sound.stack_basis, sound.resume_pc, sound.return_slot,
                    sound.saved_frame, sound.frame_size, sound.return_delta,
                    sound.counts_contact,
                    suffix=lambda live, returned: finish_contact_step_sound(
                        live, returned, finisher=sound.suffix))
            raise UnsupportedCandidate(f'contact tick callback {target:06X} is not a supported sound path')
        aggregate = _join_plans(current, collision); state = dict(aggregate.registers); remaining = state['d4'] & 0xffff
        state.update(a1=(state['a1'] + 66) & 0xffffff,
                     d4=(state['d4'] & 0xffff0000) | ((remaining - 1) & 0xffff), pc=0x1ABBE0)
        current = _join_plans(aggregate, AtomicPlan(24, 2, (), state, 0x1ABD78))
    raise UnsupportedCandidate('contact tick sound callback was not reached')


def finish_contact_step_sound(machine, registers, entry=None, finisher=None):
    """Resume a callback sound from live guest state through the parent RTS."""
    if finisher is None:
        if entry is None:
            raise UnsupportedCandidate('contact tick collection sound entry')
        finish = finish_collection(machine, registers, entry)
    else:
        finish = finisher(machine, registers)
    overlay = dict(machine.registers()); overlay.update(finish.registers)
    complete = complete_contact_plan(dispatch_plan_view(machine, finish), overlay)
    combined = _join_plans(finish, complete)
    remainder = _contact_scan_resume(dispatch_plan_view(machine, combined), combined.registers)
    combined = _join_plans(combined, remainder)
    final = dict(combined.registers); sp = final['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned contact tick return stack')
    outer = _read(dispatch_plan_view(machine, combined), sp, 4) & 0xffffff
    if outer & 1:
        raise UnsupportedCandidate('unaligned contact tick return PC')
    final.update(a7=sp + 4, pc=outer)
    return AtomicPlan(combined.cycles + 16, combined.instructions + 1, combined.writes,
                      final, CONTACT_SCAN_EXIT, combined.direct_calls)


def _contact_step_prefix(machine, registers):
    if registers.get('pc') != CONTACT_STEP_ENTRY:
        raise UnsupportedCandidate('contact tick entry identity')
    read = lambda address, size=1: _read(machine, address, size)
    ee, f2 = read(0xFFF0EE), read(0xFFF0F2)
    writes = game.contact_tick_reset(read(0xFFF0D3), ee, f2)
    cycles, instructions = 210 + 18 * bool(ee) + 18 * bool(f2), 12 + bool(ee) + bool(f2)
    # SUBQ.B #1 has a known non-borrowing X result whenever either timer ran.
    sr = registers['sr'] & ~0x10 if ee or f2 else registers['sr']
    shape = read(0xFF7E54, 4)
    final = {**registers, 'pc': CONTACT_SCAN_EXIT, 'sr': _logic_sr(sr, shape, 4)}
    if not shape:
        return AtomicPlan(cycles, instructions, tuple(writes), final, 0x1ABB8A)
    player = 0xFF7E40
    active = read(player)
    cycles += 52; instructions += 4
    final.update(a2=player, a3=shape, sr=_logic_sr(final['sr'], active, 1))
    if not active:
        return AtomicPlan(cycles, instructions, tuple(writes), final, 0x1ABB9C)
    staged = dispatch_plan_view(machine, AtomicPlan(1, 1, tuple(writes), {}, CONTACT_STEP_ENTRY))
    def descriptor(offset):
        address = shape + offset
        if 0 <= address < 0x200000:
            return machine.peek_rom(address, 1)[0]
        return _read(staged, address, 1)
    mirrored = read(0xFF7E49)
    left, right = game.contact_tick_bounds(read(player + 2, 2), descriptor(2), descriptor(4), mirrored)
    writes.extend((*_bytes(0xFFF08C, left, 2), *_bytes(0xFFF08E, right, 2)))
    final.update(d0=(registers['d0'] & 0xffff0000) | left,
                 d2=(registers['d2'] & 0xffff0000) | right, pc=CONTACT_SCAN_ENTRY,
                 sr=_logic_sr(_add_sr(final['sr'], descriptor(4) if not mirrored else (-descriptor(2) & 0xff),
                                       read(player + 2, 2), 2), right, 2))
    return AtomicPlan(cycles + 116 + (16 if mirrored else 0),
                      instructions + 10 + (3 if mirrored else 0), tuple(writes), final, 0x1ABBD0)


def contact_step_plan(machine, registers):
    """Recover one 1ABB40 contact tick through its real caller return."""
    prefix = _contact_step_prefix(machine, registers)
    combined = prefix
    if prefix.registers['pc'] == CONTACT_SCAN_ENTRY:
        scan = contact_scan_plan(dispatch_plan_view(machine, prefix), prefix.registers)
        combined = _join_plans(prefix, scan)
    final = dict(combined.registers)
    sp = final['a7']
    if sp & 1:
        raise UnsupportedCandidate('unaligned contact tick return stack')
    outer = _read(dispatch_plan_view(machine, combined), sp, 4) & 0xffffff
    if outer & 1:
        raise UnsupportedCandidate('unaligned contact tick return PC')
    final.update(a7=sp + 4, pc=outer)
    return AtomicPlan(combined.cycles + 16, combined.instructions + 1, combined.writes,
                      final, CONTACT_SCAN_EXIT, combined.direct_calls)


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


def _contact_type78_prefix(machine, registers, read, record, sp, sr):
    """1AEBDC's own FFF0D8 gate/window prefix, shared by both call arms.

    Returns ``(arm, facts, callback)`` where ``callback`` is ``None`` for a
    window-rejected arm (nothing further to compose) and otherwise the
    ``AtomicPlan`` for the BSR frame into ``CONTACT_ENTRY``.
    """
    window = registers['d0'] & 0xffff
    arm, facts = game.contact_type78_route(read, record, window)
    if arm != 'call':
        return arm, facts, None
    if facts['gate']:
        cycles, instructions = 94, 10
        d2 = (registers['d2'] & 0xffff0000) | facts['lower']
        prefix_sr = _cmp_sr(sr, window, facts['lower'], 2)
        extra = {'d2': d2}
    else:
        cycles, instructions = 44, 3
        prefix_sr = _logic_sr(sr, 0, 1)
        extra = {}
    callback = AtomicPlan(cycles, instructions, _bytes(sp - 4, 0x1AEBFC, 4),
                          {**registers, **extra, 'a7': sp - 4, 'pc': CONTACT_ENTRY, 'sr': prefix_sr},
                          0x1AEBFC, direct_calls=1)
    return arm, facts, callback


def begin_contact_family_type78(machine, registers):
    """1AEBDC's FFF0D8 gate and, when active, a +/-8 window guard around a
    BSR into the shared 1AE4F8 contact root through ``begin_contact``.

    Arm selection is ``game.contact_type78_route``; this boundary owns the
    alias guards, the cost table and the CCR.  Cost table (``factcheck``),
    each call row exclusive of ``begin_contact`` itself:

        window upper fail  (FFF0D8 set, D0 >= record+2 + 8)     74 /  7
        window lower fail  (FFF0D8 set, D0 <  record+2 - 8)     94 / 10
        call, FFF0D8 clear                                      44 /  3
        call, FFF0D8 set and D0 inside the window                94 / 10

    The gate's own TST/CMP discard every incoming CCR bit they do not set;
    a window-fail's final flags are its own last CMP's, a call's final
    flags are ``begin_contact``'s.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type78 record/stack')
    _spans_disjoint([('type78 record', record, 66), ('type78 return', sp, 4),
                     ('type78 bsr return', sp - 4, 4), ('type78 gate', 0xFFF0D8, 1)])
    read = lambda address, size: _read(machine, address, size)
    return_pc = read(sp, 4) & 0xFFFFFF
    arm, facts, callback = _contact_type78_prefix(machine, registers, read, record, sp, sr)
    if arm == 'window_upper_fail':
        d2 = (registers['d2'] & 0xffff0000) | facts['upper']
        return AtomicPlan(74, 7, (), {'d2': d2, 'a7': sp + 4, 'pc': return_pc,
                                       'sr': _cmp_sr(sr, registers['d0'] & 0xffff, facts['upper'], 2)},
                          0x1AEBFC)
    if arm == 'window_lower_fail':
        d2 = (registers['d2'] & 0xffff0000) | facts['lower']
        return AtomicPlan(94, 10, (), {'d2': d2, 'a7': sp + 4, 'pc': return_pc,
                                        'sr': _cmp_sr(sr, registers['d0'] & 0xffff, facts['lower'], 2)},
                          0x1AEBFC)
    contact = begin_contact(dispatch_plan_view(machine, callback), callback.registers)
    # ``begin_contact`` accounts for exactly one RTS (landing at our own
    # local return, the BSR's return slot); a second, explicit RTS there
    # unwinds our own frame back to the true caller, exactly as
    # ``begin_contact_dispatch`` adds for its own nested BSR.
    final = dict(callback.registers)
    final.update(contact.registers)
    final.update(a7=sp + 4, pc=return_pc)
    return AtomicPlan(callback.cycles + contact.cycles + 16, callback.instructions + contact.instructions + 1,
                      tuple(dict((*callback.writes, *contact.writes)).items()), final,
                      0x1AEBFC, callback.direct_calls + contact.direct_calls)


def begin_contact_family_type78_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE78_ENTRY, begin_contact_family_type78)


def begin_contact_family_type78_sound(machine, registers):
    """Enter 1AEBDC's window-guarded contact root through command 31."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type78 sound record/stack')
    _spans_disjoint([('type78 sound record', record, 66), ('type78 sound return', sp, 4),
                     ('type78 sound bsr return', sp - 4, 4), ('type78 sound gate', 0xFFF0D8, 1)])
    read = lambda address, size: _read(machine, address, size)
    arm, facts, callback = _contact_type78_prefix(machine, registers, read, record, sp, sr)
    if arm != 'call':
        raise UnsupportedCandidate('contact type78 sound outside the window pass')
    sound = begin_contact_sound(dispatch_plan_view(machine, callback), callback.registers)
    final = dict(callback.registers)
    final.update(sound.registers)
    return AtomicPlan(callback.cycles + sound.cycles, callback.instructions + sound.instructions,
                      tuple(dict((*callback.writes, *sound.writes)).items()), final,
                      sound.last_pc, callback.direct_calls + sound.direct_calls)


def begin_contact_family_type78_dispatch_sound(machine, registers, dispatch):
    """Compose collection dispatch with type-78's sound-seam arm."""
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != CONTACT_FAMILY_TYPE78_ENTRY
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact type78 sound dispatch identity')
    sound = begin_contact_family_type78_sound(dispatch_plan_view(machine, dispatch), callback_registers)
    final = dict(callback_registers)
    final.update(sound.registers)
    return AtomicPlan(dispatch.cycles + sound.cycles, dispatch.instructions + sound.instructions,
                      tuple(dict((*dispatch.writes, *sound.writes)).items()), final,
                      sound.last_pc, dispatch.direct_calls + sound.direct_calls)


def finish_contact_family_type78_sound(machine, registers):
    """Restore command 31, then type-78's own BSR/RTS pair to the dispatcher."""
    contact = finish_contact_sound(machine, registers)
    local_sp = contact.registers['a7']
    if (contact.registers.get('pc') != 0x1AEBFC
            or _read(machine, local_sp, 4) != COLLECTION_DISPATCH_RETURN):
        raise UnsupportedCandidate('contact type78 sound local return identity')
    final = dict(contact.registers)
    final.update(a7=local_sp + 4, pc=COLLECTION_DISPATCH_RETURN)
    return AtomicPlan(contact.cycles + 16, contact.instructions + 1,
                      contact.writes, final, 0x1AEBFC, contact.direct_calls)


def _contact_family_type2c_prefix(machine, registers, record, sp, sr):
    """1AEE40's own FFF0D8-clear prefix: self-retype, the already-proven
    1AE372 buffer release, then the BSR frame into CONTACT_ENTRY."""
    clear_cycles, clear_instructions, clear_writes, linked = _clear_objects(
        machine, registers, sp=sp - 4, pair=False,
        extra_spans=(('type2c return', sp, 4), ('type2c gate', 0xFFF0D8, 1)))
    writes = (*_bytes(record, 0, 1), *clear_writes, *_bytes(sp - 4, 0x1AEEC8, 4))
    cycles = 56 + clear_cycles + 18   # TST.B/BEQ/CLR.B/BSR(1AE372) + BSR(1AE4F8)
    instructions = 4 + clear_instructions + 1
    return AtomicPlan(cycles, instructions, writes,
                      {**registers, 'a7': sp - 4, 'pc': CONTACT_ENTRY,
                       'sr': _logic_sr(sr, 0, 1)},
                      0x1AEEC8, direct_calls=2)


def begin_contact_family_type2c(machine, registers):
    """1AEE40's FFF0D8 gate: clear, self-retype plus the already-proven
    1AE372 buffer release, then a BSR into the shared 1AE4F8 contact root
    through ``begin_contact``.

    Active (FFF0D8 set) continues into a pool-scan-and-spawn arm behind a
    new subroutine 1AE2DA that is not recovered here.  Cost table
    (``factcheck``), exclusive of ``_clear_objects``/``begin_contact``
    themselves:

        own prefix (TST.B/BEQ/CLR.B/BSR to 1AE372, BSR to 1AE4F8)  74
        extra local RTS that unwinds this wrapper's own frame      16

    The extra local RTS mirrors ``begin_contact_dispatch``'s own
    adjustment for its nested BSR: ``begin_contact`` accounts for exactly
    one RTS (landing at this wrapper's own local return), so a second,
    explicit RTS here unwinds back to the true caller.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type2c record/stack')
    gate = _read(machine, 0xFFF0D8, 1)
    if gate:
        raise UnsupportedCandidate('type2c pool-scan-and-spawn arm is not recovered')
    return_pc = _read(machine, sp, 4) & 0xFFFFFF
    callback = _contact_family_type2c_prefix(machine, registers, record, sp, sr)
    contact = begin_contact(dispatch_plan_view(machine, callback), callback.registers)
    final = dict(callback.registers)
    final.update(contact.registers)
    final.update(a7=sp + 4, pc=return_pc)
    return AtomicPlan(callback.cycles + contact.cycles + 16, callback.instructions + contact.instructions + 1,
                      tuple(dict((*callback.writes, *contact.writes)).items()), final,
                      0x1AEEC8, callback.direct_calls + contact.direct_calls)


def begin_contact_family_type2c_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE2C_ENTRY, begin_contact_family_type2c)


def begin_contact_family_type2c_sound(machine, registers):
    """Enter 1AEE40's own contact root through command 31 (FFF0D8 clear only)."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type2c sound record/stack')
    gate = _read(machine, 0xFFF0D8, 1)
    if gate:
        raise UnsupportedCandidate('type2c pool-scan-and-spawn arm is not recovered')
    callback = _contact_family_type2c_prefix(machine, registers, record, sp, sr)
    sound = begin_contact_sound(dispatch_plan_view(machine, callback), callback.registers)
    final = dict(callback.registers)
    final.update(sound.registers)
    return AtomicPlan(callback.cycles + sound.cycles, callback.instructions + sound.instructions,
                      tuple(dict((*callback.writes, *sound.writes)).items()), final,
                      sound.last_pc, callback.direct_calls + sound.direct_calls)


def begin_contact_family_type2c_dispatch_sound(machine, registers, dispatch):
    """Compose collection dispatch with type-2C's sound-seam arm."""
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != CONTACT_FAMILY_TYPE2C_ENTRY
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact type2c sound dispatch identity')
    sound = begin_contact_family_type2c_sound(dispatch_plan_view(machine, dispatch), callback_registers)
    final = dict(callback_registers)
    final.update(sound.registers)
    return AtomicPlan(dispatch.cycles + sound.cycles, dispatch.instructions + sound.instructions,
                      tuple(dict((*dispatch.writes, *sound.writes)).items()), final,
                      sound.last_pc, dispatch.direct_calls + sound.direct_calls)


def finish_contact_family_type2c_sound(machine, registers):
    """Restore command 31, then type-2C's own BSR/RTS pair to the dispatcher."""
    contact = finish_contact_sound(machine, registers)
    local_sp = contact.registers['a7']
    if (contact.registers.get('pc') != 0x1AEEC8
            or _read(machine, local_sp, 4) != COLLECTION_DISPATCH_RETURN):
        raise UnsupportedCandidate('contact type2c sound local return identity')
    final = dict(contact.registers)
    final.update(a7=local_sp + 4, pc=COLLECTION_DISPATCH_RETURN)
    return AtomicPlan(contact.cycles + 16, contact.instructions + 1,
                      contact.writes, final, 0x1AEEC8, contact.direct_calls)


CONTACT_ACTIVATION_GLOBALS = tuple((name, address, size) for name, address, size in (
    ('contact activation vertical', 0xFF7E5A, 2),
    ('contact activation blocked', 0xFFF0E7, 1),
    ('contact activation motion', 0xFF7DFC, 2),
    ('contact activation base', 0xFF7DF8, 2),
    ('contact activation impulse', 0xFF7DFE, 2),
    ('contact activation script', 0xFF7E60, 4),
    ('contact activation script mode', 0xFF7E77, 1),
    ('contact activation contact', 0xFFF0BE, 1),
    ('contact activation contact mode', 0xFFF0C0, 1),
    ('contact activation player', 0xFF7E02, 2),
    ('contact activation horizontal impulse', 0xFF7E58, 1),
    ('contact activation dispatch flag', 0xFFF0F5, 1),
))


def begin_contact_activation(machine, registers):
    """Recover 1AFD84 through its guarded proximity and RTS paths."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact activation record/stack')
    _spans_disjoint([('contact activation record', record, 66),
                     ('contact activation return', sp, 4), *CONTACT_ACTIVATION_GLOBALS])
    read = lambda address, size: _read(machine, address, size)
    ret = read(sp, 4) & 0xFFFFFF
    vertical = read(0xFF7E5A, 2)
    if vertical & 0x8000:
        return AtomicPlan(42, 3, (), {'a7': sp + 4, 'pc': ret,
                                       'sr': _logic_sr(sr, vertical, 2)}, 0x1AFE1A)
    blocked = read(0xFFF0E7, 1)
    if blocked:
        return AtomicPlan(70, 5, (), {'a7': sp + 4, 'pc': ret,
                                       'sr': _logic_sr(sr, blocked, 1)}, 0x1AFE1A)
    delta = (read(record + 4, 2) - read(0xFF7DF8, 2)) & 0xFFFF
    distance = (read(0xFF7DFC, 2) - delta) & 0xFFFF
    distance_sr = _sub_sr(sr, read(0xFF7DFC, 2), delta, 2)
    borrowed_distance = bool(distance_sr & 1)
    if borrowed_distance:
        before_negate = distance
        distance = (-distance) & 0xFFFF
        distance_sr = _sub_sr(distance_sr, 0, before_negate, 2)
    if distance >= 6:
        return AtomicPlan(170 if borrowed_distance else 168, 14 if borrowed_distance else 13,
                          ((0xFFF0F5, 0xFF),),
                          {'d2': (registers['d2'] & 0xFFFF0000) | delta,
                           'd7': (registers['d7'] & 0xFFFF0000) | distance,
                           'a7': sp + 4, 'pc': ret,
                           'sr': _cmp_sr(distance_sr, distance, 6, 2)},
                          CONTACT_ACTIVATION_TAIL + 6)
    d0 = (registers['d0'] & 0xFFFF0000) | ((read(0xFF7E02, 2) - read(record + 2, 2)) & 0xFFFF)
    impulse_sr = _sub_sr(distance_sr, read(0xFF7E02, 2), read(record + 2, 2), 2)
    negative = bool(d0 & 0x8000)
    if negative:
        before_negate = d0 & 0xFFFF
        d0 = (d0 & 0xFFFF0000) | ((-d0) & 0xFFFF)
        impulse_sr = _sub_sr(impulse_sr, 0, before_negate, 2)
    shifted = d0 & 0xFF
    d0 = (d0 & 0xFFFFFF00) | (shifted >> 3)
    impulse_sr = _logic_sr(impulse_sr & ~0x1F, d0 & 0xFF, 1)
    if shifted & 4:
        impulse_sr |= 0x11
    if negative:
        shifted_word = d0 & 0xFFFF
        d0 = (d0 & 0xFFFF0000) | ((-shifted_word) & 0xFFFF)
        impulse_sr = _sub_sr(impulse_sr, 0, shifted_word, 2)
        last = 0x1AFE1A
    else:
        last = 0x1AFE0C
    # The terminal MOVE.B publishes the impulse, supplies N/Z, clears V/C,
    # and retains X from the preceding shift or negation.
    impulse_sr = _logic_sr(impulse_sr, d0 & 0xFF, 1)
    writes = game.activate_contact(record, delta, d0)
    return AtomicPlan((422 if borrowed_distance else 420) if negative else (412 if borrowed_distance else 410),
                      (30 if borrowed_distance else 29) if negative else (28 if borrowed_distance else 27), tuple(writes),
                      {'d0': d0, 'd2': (registers['d2'] & 0xFFFF0000) | delta,
                       'd7': (registers['d7'] & 0xFFFF0000) | distance,
                       'a7': sp + 4, 'pc': ret, 'sr': impulse_sr}, last, direct_calls=1)


def begin_contact_activation_dispatch(machine, registers, dispatch):
    """Compose collection dispatch type 01 and its direct activation callback."""
    sp = registers['a7']
    if dispatch.registers.get('pc') != CONTACT_ACTIVATION_ENTRY or dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('contact activation dispatch prefix identity')
    callback_registers = {**registers, **dispatch.registers}
    activation = begin_contact_activation(dispatch_plan_view(machine, dispatch), callback_registers)
    final = dict(callback_registers)
    final.update(activation.registers)
    return AtomicPlan(dispatch.cycles + activation.cycles,
                      dispatch.instructions + activation.instructions,
                      tuple(dict((*dispatch.writes, *activation.writes)).items()), final,
                      activation.last_pc, dispatch.direct_calls + activation.direct_calls)


CONTACT_FAMILY_66_GLOBALS = (
    ('contact family vertical', 0xFF7E5A, 2),
    ('contact family blocked', 0xFFF0E7, 1),
    ('contact family script', 0xFF7E60, 4),
    ('contact family script mode', 0xFF7E77, 1),
    ('contact family state', 0xFFF0BE, 1),
    ('contact family state mode', 0xFFF0C0, 1),
    ('contact family clear', 0xFFF0CC, 1),
)


def begin_contact_family_66(machine, registers):
    """Recover `1AFBF4`'s timer-gated type-66 transition."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact family-66 record/stack')
    _spans_disjoint([('contact family-66 record', record, 56),
                     ('contact family-66 return', sp, 4), *CONTACT_FAMILY_66_GLOBALS])
    read = lambda address, size: _read(machine, address, size)
    ret, vertical = read(sp, 4) & 0xFFFFFF, read(0xFF7E5A, 2)
    if vertical & 0x8000:
        return AtomicPlan(42, 3, (), {'a7': sp + 4, 'pc': ret,
                                       'sr': _logic_sr(sr, vertical, 2)}, 0x1AFC4C)
    if vertical == 0:
        return AtomicPlan(66, 5, (), {'a7': sp + 4, 'pc': ret,
                                       'sr': _logic_sr(sr, vertical, 2)}, 0x1AFC4C)
    kind = read(record, 1)
    if kind == 0x66:
        return AtomicPlan(86, 7, (), {'a7': sp + 4, 'pc': ret,
                                       'sr': _cmp_sr(sr, kind, 0x66, 1)}, 0x1AFC4C)
    blocked = read(0xFFF0E7, 1)
    writes = game.transition_contact_66(record, publish=not blocked)
    # The blocked arm ends after TST.B; the published arm ends after CLR.B.
    return AtomicPlan(162 if blocked else 288, 12 if blocked else 18, tuple(writes),
                      {'a7': sp + 4, 'pc': ret, 'sr': _logic_sr(sr, blocked, 1)},
                      0x1AFC4C, direct_calls=1)


def _contact_family_dispatch(machine, registers, dispatch, entry, planner):
    """The shared JSR frame and atomic composition for three RAM-only callbacks."""
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != entry
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact family dispatch identity')
    callback = planner(dispatch_plan_view(machine, dispatch), callback_registers)
    return AtomicPlan(dispatch.cycles + callback.cycles, dispatch.instructions + callback.instructions,
                      (*dispatch.writes, *callback.writes), {**callback_registers, **callback.registers},
                      callback.last_pc, dispatch.direct_calls + callback.direct_calls)


def begin_contact_family_66_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_66_ENTRY, begin_contact_family_66)


def begin_contact_family_type79(machine, registers):
    """Recover 1AEB7C type-79's RAM-only FFF0E7/FFF0D8 return arm."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact type79 record/stack')
    _spans_disjoint([('contact type79 record', record, 66),
                     ('contact type79 return', sp, 4),
                     ('contact type79 gates', 0xFFF0D8, 1),
                     ('contact type79 gates', 0xFFF0E7, 1),
                     ('contact type79 gate', 0xFFF0F2, 1)])
    read = lambda address, size: _read(machine, address, size)
    if read(0xFFF0E7, 1):
        raise UnsupportedCandidate('contact type79 non-return arm')
    active, sound_gate = read(0xFFF0D8, 1), read(0xFFF0F2, 1)
    if active:
        cycles, instructions, residue = 70, 5, active
    elif sound_gate:
        # The third TST/BNE takes the local RTS, preserving its CCR result.
        cycles, instructions, residue = 94, 7, sound_gate
    else:
        raise UnsupportedCandidate('contact type79 non-return arm')
    return AtomicPlan(cycles, instructions, (),
                      {'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF,
                       'sr': _logic_sr(sr, residue, 1)},
                      0x1AEBA2)


def begin_contact_family_type79_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE79_ENTRY,
                                    begin_contact_family_type79)


def begin_contact_family_type79_sound(machine, registers):
    """Enter type-79's inactive contact arm through command 31.

    This is the other fall-through from ``1AEB7C``: after both inactive
    guards and the sound guard pass, it clears the family latch and BSRs the
    ordinary contact root.  The measured wrapper through the sound-call gate
    is 118 cycles / 8 instructions before the contact prefix.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact type79 sound record/stack')
    _spans_disjoint([('contact type79 sound record', record, 66),
                     ('contact type79 sound return', sp, 4),
                     ('contact type79 sound bsr return', sp - 4, 4),
                     ('contact type79 sound gates', 0xFFF0D8, 1),
                     ('contact type79 sound gates', 0xFFF0E7, 1),
                     ('contact type79 sound gate', 0xFFF0F2, 1),
                     ('contact type79 sound clear', 0xFFF0CC, 1)])
    read = lambda address, size: _read(machine, address, size)
    if read(0xFFF0E7, 1) or read(0xFFF0D8, 1) or read(0xFFF0F2, 1):
        raise UnsupportedCandidate('contact type79 sound guard')
    callback = AtomicPlan(118, 8,
                          (*_bytes(0xFFF0CC, 0, 1), *_bytes(sp - 4, 0x1AEBA2, 4)),
                          {**registers, 'a7': sp - 4, 'pc': CONTACT_ENTRY,
                           'sr': _logic_sr(sr, 0, 1)},
                          0x1AEBA0, direct_calls=1)
    sound = begin_contact_sound(dispatch_plan_view(machine, callback), callback.registers)
    final = dict(callback.registers)
    final.update(sound.registers)
    return AtomicPlan(callback.cycles + sound.cycles,
                      callback.instructions + sound.instructions,
                      tuple(dict((*callback.writes, *sound.writes)).items()), final,
                      sound.last_pc, callback.direct_calls + sound.direct_calls)


def begin_contact_family_type79_dispatch_sound(machine, registers, dispatch):
    """Compose collection dispatch with type-79's concrete sound arm."""
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != CONTACT_FAMILY_TYPE79_ENTRY
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact type79 sound dispatch identity')
    sound = begin_contact_family_type79_sound(dispatch_plan_view(machine, dispatch), callback_registers)
    final = dict(callback_registers)
    final.update(sound.registers)
    return AtomicPlan(dispatch.cycles + sound.cycles,
                      dispatch.instructions + sound.instructions,
                      tuple(dict((*dispatch.writes, *sound.writes)).items()), final,
                      sound.last_pc, dispatch.direct_calls + sound.direct_calls)


def finish_contact_family_type79_sound(machine, registers):
    """Restore command 31, then type-79's BSR/RTS pair to the dispatcher."""
    contact = finish_contact_sound(machine, registers)
    local_sp = contact.registers['a7']
    if (contact.registers.get('pc') != 0x1AEBA2
            or _read(machine, local_sp, 4) != COLLECTION_DISPATCH_RETURN):
        raise UnsupportedCandidate('contact type79 sound local return identity')
    final = dict(contact.registers)
    final.update(a7=local_sp + 4, pc=COLLECTION_DISPATCH_RETURN)
    return AtomicPlan(contact.cycles + 16, contact.instructions + 1,
                      contact.writes, final, 0x1AEBA2, contact.direct_calls)


def begin_contact_family_type1f_inactive(machine, registers):
    """Recover 1AE796's measured bit-5-clear position/inactive RTS tails.

    Its contact, retirement, and device-helper siblings deliberately remain
    outside these leaf plans.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact type1f record/stack')
    _spans_disjoint([('contact type1f record', record, 66),
                     ('contact type1f return', sp, 4),
                     ('contact type1f player', 0xFF7E02, 2),
                     ('contact type1f direction', 0xFF7E49, 1),
                     ('contact type1f active', 0xFFF0D8, 1)])
    read = lambda address, size: _read(machine, address, size)
    player, threshold, direction = (read(0xFF7E02, 2), read(record + 2, 2),
                                    read(0xFF7E49, 1))
    if read(record + 0x3C, 1) & 0x20:
        raise UnsupportedCandidate('contact type1f non-inactive-tail-rts arm')
    position_failed = player >= threshold if not direction else player < threshold
    if position_failed:
        # CMP.W's N/V/C survive BTST; the clear bit sets Z alone.
        residue = _cmp_sr(sr, player, threshold, 2)
        residue = (residue & ~0x04) | 0x04
        cycles, instructions = (106, 8) if not direction else (104, 8)
    elif not read(0xFFF0D8, 1):
        # TST.B FFF0D8 is the immediately preceding flag producer.
        residue = _logic_sr(sr, 0, 1)
        cycles, instructions = (134, 10) if not direction else (142, 11)
    else:
        raise UnsupportedCandidate('contact type1f non-inactive-tail-rts arm')
    return AtomicPlan(cycles, instructions, (),
                      {'d7': (registers['d7'] & 0xFFFF0000) | player,
                       'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF,
                       'sr': residue},
                      0x1AE976)


def begin_contact_family_type1f_inactive_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE1F_ENTRY,
                                    begin_contact_family_type1f_inactive)


def begin_contact_family_type1f_contact(machine, registers):
    """Enter 1AE796's recorded inactive bit-5 contact BSR."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact type1f contact record/stack')
    _spans_disjoint([('contact type1f contact record', record, 66),
                     ('contact type1f contact return', sp, 4),
                     ('contact type1f contact bsr return', sp - 4, 4),
                     ('contact type1f player', 0xFF7E02, 2),
                     ('contact type1f direction', 0xFF7E49, 1),
                     ('contact type1f active', 0xFFF0D8, 1)])
    read = lambda address, size: _read(machine, address, size)
    player, threshold = read(0xFF7E02, 2), read(record + 2, 2)
    if (read(0xFF7E49, 1) != 0 or player >= threshold
            or read(0xFFF0D8, 1) != 0 or not (read(record + 0x3C, 1) & 0x20)):
        raise UnsupportedCandidate('contact type1f non-recorded contact arm')
    return AtomicPlan(138, 10, (*_bytes(sp - 4, 0x1AE870, 4),),
                      {**registers, 'd7': (registers['d7'] & 0xFFFF0000) | player,
                       'a7': sp - 4, 'pc': CONTACT_ENTRY, 'sr': sr & ~0x0F},
                      0x1AE86C, direct_calls=1)


def _finish_contact_family_type1f_contact(machine, contact):
    local_sp = contact.registers['a7']
    if (contact.registers.get('pc') != 0x1AE870
            or _read(machine, local_sp, 4) != COLLECTION_DISPATCH_RETURN):
        raise UnsupportedCandidate('contact type1f contact local return identity')
    final = dict(contact.registers)
    final.update(a7=local_sp + 4, pc=COLLECTION_DISPATCH_RETURN)
    return AtomicPlan(contact.cycles + 16, contact.instructions + 1, contact.writes,
                      final, 0x1AE870, contact.direct_calls)


def begin_contact_family_type1f_contact_dispatch(machine, registers, dispatch):
    """Compose collection dispatch and type-1F's finite contact return."""
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != CONTACT_FAMILY_TYPE1F_ENTRY
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact type1f contact dispatch identity')
    callback = begin_contact_family_type1f_contact(dispatch_plan_view(machine, dispatch), callback_registers)
    contact = begin_contact(dispatch_plan_view(machine, callback), callback.registers)
    composed = _join_plans(dispatch, _join_plans(callback, contact))
    finish = _finish_contact_family_type1f_contact(dispatch_plan_view(machine, composed), contact)
    return _join_plans(dispatch, _join_plans(callback, finish))


def begin_contact_family_type1f_contact_dispatch_sound(machine, registers, dispatch):
    """Compose collection dispatch and type-1F's command-31 contact prefix."""
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != CONTACT_FAMILY_TYPE1F_ENTRY
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact type1f contact sound dispatch identity')
    callback = begin_contact_family_type1f_contact(dispatch_plan_view(machine, dispatch), callback_registers)
    sound = begin_contact_sound(dispatch_plan_view(machine, callback), callback.registers)
    return _join_plans(dispatch, _join_plans(callback, sound))


def finish_contact_family_type1f_contact_sound(machine, registers):
    """Restore command 31 then close type-1F's local RTS."""
    return _finish_contact_family_type1f_contact(machine, finish_contact_sound(machine, registers))


def begin_contact_family_type1f_transition(machine, registers):
    """Recover type-1F's direct no-counter transition to 1AE954."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact type1f transition record/stack')
    _spans_disjoint([('contact type1f transition record', record, 66),
                     ('contact type1f transition return', sp, 4),
                     ('contact type1f player', 0xFF7E02, 2),
                     ('contact type1f direction', 0xFF7E49, 1),
                     ('contact type1f active', 0xFFF0D8, 1),
                     ('contact type1f finish gate', 0xFF7E21, 1)])
    read = lambda address, size: _read(machine, address, size)
    player, threshold = read(0xFF7E02, 2), read(record + 2, 2)
    if (read(0xFF7E49, 1) != 0 or player >= threshold
            or not read(0xFFF0D8, 1) or read(record + 0x3C, 1) & 0x20):
        raise UnsupportedCandidate('contact type1f non-direct-finish arm')
    kind, finish_gate = read(record, 1), read(0xFF7E21, 1)
    if not finish_gate:
        try:
            script, cycles, instructions = {
                0x1E: (0x1234BE, 272, 19), 0x1F: (0x12384A, 316, 23),
                0x21: (0x12350C, 294, 21), 0x22: (0x12387A, 328, 24),
            }[kind]
        except KeyError as error:
            raise UnsupportedCandidate('contact type1f direct-finish kind') from error
    elif kind == 0x1F and not read(record + 1, 1):
        script, cycles, instructions = 0x12384A, 336, 25
    else:
        raise UnsupportedCandidate('contact type1f non-direct-finish arm')
    writes = (*_bytes(record + 0x20, script, 4), *_bytes(record, 0x84, 1),
              *_bytes(record + 0x37, 0, 1), *_bytes(record + 0x0A, 0, 4),
              *_bytes(record + 0x36, 0, 1))
    return AtomicPlan(cycles, instructions, writes,
                      {**registers, 'd7': (registers['d7'] & 0xFFFF0000) | player,
                       'pc': FINISH_ENTRY, 'sr': _logic_sr(sr, 0, 1)},
                      0x1AE8FE)


def begin_contact_family_type1f_transition_dispatch(machine, registers, dispatch):
    """Compose collection dispatch, direct type-1F state change, and retirement."""
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != CONTACT_FAMILY_TYPE1F_ENTRY
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact type1f transition dispatch identity')
    prefix = begin_contact_family_type1f_transition(dispatch_plan_view(machine, dispatch), callback_registers)
    composed = _join_plans(dispatch, prefix)
    finish = finish_object(dispatch_plan_view(machine, composed), prefix.registers)
    return _join_plans(dispatch, _join_plans(prefix, finish))


def begin_contact_family_type1f_transition_sound(machine, registers):
    """Enter the recorded type-1E/1F counter transition through command 41."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact type1f command41 record/stack')
    _spans_disjoint([('contact type1f command41 record', record, 66),
                     ('contact type1f command41 frame', sp - 28, 32),
                     ('contact type1f player', 0xFF7E02, 2),
                     ('contact type1f direction', 0xFF7E49, 1),
                     ('contact type1f active', 0xFFF0D8, 1),
                     ('contact type1f finish gate', 0xFF7E21, 1),
                     ('contact type1f sound', 0xFFF57D, 1)])
    read = lambda address, size: _read(machine, address, size)
    player, threshold, kind = read(0xFF7E02, 2), read(record + 2, 2), read(record, 1)
    counter = read(record + 1, 1)
    if (read(0xFF7E49, 1) != 0 or player >= threshold
            or not read(0xFFF0D8, 1) or read(record + 0x3C, 1) & 0x20
            or kind not in (0x1E, 0x1F, 0x21, 0x22) or not read(0xFF7E21, 1)
            or not counter or not read(0xFFF57D, 1)):
        raise UnsupportedCandidate('contact type1f non-command41 arm')
    script, cycles, instructions = ({0x1E: (0x1234BE, 414, 27),
                                     0x1F: (0x12384A, 458, 31),
                                     0x21: (0x12350C, 436, 29),
                                     0x22: (0x12387A, 470, 32)}[kind])
    writes = [*_bytes(record + 0x20, script, 4), (record, 0x84),
              (record + 0x37, 0), *_bytes(record + 0x0A, 0, 4),
              (record + 0x36, 0), (record + 1, counter - 1)]
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        writes.extend(_bytes(sp - index * 4, registers[name], 4))
    writes.extend((*_bytes(sp - 24, 0x41, 4), *_bytes(sp - 28, 0x1AE91A, 4)))
    return AtomicPlan(cycles, instructions, tuple(writes),
                      {**registers, 'd7': (registers['d7'] & 0xFFFF0000) | player,
                       'a7': sp - 28, 'pc': 0x1E58B8, 'sr': sr & ~0x0F},
                      0x1AE914, direct_calls=1)


def begin_contact_family_type1f_transition_dispatch_sound(machine, registers, dispatch):
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != CONTACT_FAMILY_TYPE1F_ENTRY
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact type1f command41 dispatch identity')
    sound = begin_contact_family_type1f_transition_sound(
        dispatch_plan_view(machine, dispatch), callback_registers)
    return _join_plans(dispatch, sound)


def finish_contact_family_type1f_transition_sound(machine, registers):
    """Resume command 41 at 1AE920, select the script, and return."""
    if registers.get('pc') != 0x1AE920 or registers['a7'] & 1:
        raise UnsupportedCandidate('foreign contact type1f command41 return')
    sp = registers['a7'] + 24
    restored = dict(registers, a7=sp)
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        restored[name] = _read(machine, sp - index * 4, 4)
    record = restored['a1']
    _spans_disjoint([('contact type1f command41 record', record, 66),
                     ('contact type1f command41 frame', sp - 28, 32),
                     *CONTACT_SELECTOR_GLOBALS,
                     ('contact type1f script', 0xFF7E60, 4),
                     ('contact type1f active', 0xFFF0D8, 1)])
    local = AtomicPlan(130, 6,
                       ((0xFFF0CC, 0), *_bytes(0xFFF0B0, 0, 2),
                        *_bytes(sp - 4, restored['a2'], 4), *_bytes(sp - 8, 0x1AE938, 4)),
                       {**restored, 'a7': sp - 8, 'pc': 0x1AD150},
                       0x1AE934, direct_calls=1)
    selector = _contact_selector(dispatch_plan_view(machine, local), local.registers)
    planned = _join_plans(local, selector)
    saved_a2, outer_return = restored['a2'], _read(machine, sp, 4)
    bits = _read(dispatch_plan_view(machine, planned), record + 0x3C, 1)
    writes = (*_bytes(0xFF7E60, selector.registers['a2'], 4), (0xFF7E77, 0),
              (0xFFF0D8, 0), (record + 0x3C, bits & ~0x20))
    final = dict(restored)
    final.update(selector.registers, a2=saved_a2, a7=sp + 4,
                 pc=outer_return & 0xFFFFFF, sr=_logic_sr(selector.registers['sr'], 0, 1))
    tail = AtomicPlan(108, 6, writes, final, 0x1AE952, direct_calls=1)
    return _join_plans(planned, tail)


def begin_contact_family_type1f_transition_soundoff(machine, registers):
    """Directly compose the recorded command-41-disabled selector route."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact type1f soundoff record/stack')
    _spans_disjoint([('contact type1f soundoff record', record, 66),
                     ('contact type1f soundoff selector frame', sp - 8, 12),
                     ('contact type1f player', 0xFF7E02, 2),
                     ('contact type1f direction', 0xFF7E49, 1),
                     ('contact type1f active', 0xFFF0D8, 1),
                     ('contact type1f finish gate', 0xFF7E21, 1),
                     ('contact type1f sound', 0xFFF57D, 1),
                     *CONTACT_SELECTOR_GLOBALS,
                     ('contact type1f script', 0xFF7E60, 4)])
    read = lambda address, size: _read(machine, address, size)
    player, threshold, kind = read(0xFF7E02, 2), read(record + 2, 2), read(record, 1)
    counter = read(record + 1, 1)
    if (read(0xFF7E49, 1) != 0 or player >= threshold or not read(0xFFF0D8, 1)
            or read(record + 0x3C, 1) & 0x20 or kind not in (0x1E, 0x1F, 0x21, 0x22)
            or not read(0xFF7E21, 1) or not counter or read(0xFFF57D, 1)):
        raise UnsupportedCandidate('contact type1f non-soundoff selector arm')
    script, cycles, instructions = ({0x1E: (0x1234BE, 402, 28),
                                     0x1F: (0x12384A, 446, 32),
                                     0x21: (0x12350C, 424, 30),
                                     0x22: (0x12387A, 458, 33)}[kind])
    writes = [*_bytes(record + 0x20, script, 4), (record, 0x84),
              (record + 0x37, 0), *_bytes(record + 0x0A, 0, 4),
              (record + 0x36, 0), (record + 1, counter - 1),
              (0xFFF0CC, 0), *_bytes(0xFFF0B0, 0, 2),
              *_bytes(sp - 4, registers['a2'], 4), *_bytes(sp - 8, 0x1AE938, 4)]
    local = AtomicPlan(cycles, instructions, tuple(writes),
                       {**registers, 'd7': (registers['d7'] & 0xFFFF0000) | player,
                        'a7': sp - 8, 'pc': 0x1AD150, 'sr': _logic_sr(sr, 0, 1)},
                       0x1AE934, direct_calls=1)
    selector = _contact_selector(dispatch_plan_view(machine, local), local.registers)
    planned = _join_plans(local, selector)
    bits = _read(dispatch_plan_view(machine, planned), record + 0x3C, 1)
    tail = AtomicPlan(108, 6,
                      (*_bytes(0xFF7E60, selector.registers['a2'], 4), (0xFF7E77, 0),
                       (0xFFF0D8, 0), (record + 0x3C, bits & ~0x20)),
                      {**registers, **selector.registers, 'a2': registers['a2'], 'a7': sp + 4,
                       'pc': _read(machine, sp, 4) & 0xFFFFFF,
                       'sr': _logic_sr(selector.registers['sr'], 0, 1)},
                      0x1AE952, direct_calls=1)
    return _join_plans(planned, tail)


def begin_contact_family_type1f_transition_soundoff_dispatch(machine, registers, dispatch):
    callback_registers = {**registers, **dispatch.registers}
    if (callback_registers['pc'] != CONTACT_FAMILY_TYPE1F_ENTRY
            or callback_registers['a7'] != registers['a7'] - 4):
        raise UnsupportedCandidate('contact type1f soundoff dispatch identity')
    return _join_plans(dispatch, begin_contact_family_type1f_transition_soundoff(
        dispatch_plan_view(machine, dispatch), callback_registers))


CONTACT_FAMILY_MOTION_GLOBALS = (
    ('contact family gate', 0xFFF0BE, 1), ('contact family gate mode', 0xFFF0C0, 1),
    ('contact family motion', 0xFF7DFC, 2), ('contact family origin', 0xFF7DF8, 2),
    ('contact family dispatch flag', 0xFFF0F5, 1),
)


def begin_contact_family_motion(machine, registers):
    """Recover `1AF978`, including its bounded `1AE6DE` publication call."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact family-motion record/stack')
    _spans_disjoint([('contact family-motion record', record, 56),
                     ('contact family-motion return', sp - 10, 14),
                     *CONTACT_FAMILY_MOTION_GLOBALS])
    read = lambda address, size: _read(machine, address, size)
    ret = read(sp, 4) & 0xFFFFFF
    be = read(0xFFF0BE, 1)
    prefix_cycles = 26 if not be else 52
    prefix_instructions = 2 if not be else 4
    if be and not read(0xFFF0C0, 1):
        return AtomicPlan(86, 6, ((0xFFF0F5, 0xFF),),
                          {'a7': sp + 4, 'pc': ret, 'sr': _logic_sr(sr, 0, 1)}, 0x1AE6BA)
    flags = read(record + 6, 1)
    if not flags & 0x10:
        return AtomicPlan(prefix_cycles + 68, prefix_instructions + 5, ((0xFFF0F5, 0xFF),),
                          {'d0': (registers['d0'] & 0xFFFFFF00) | flags,
                           'a7': sp + 4, 'pc': ret, 'sr': _logic_sr(sr, flags, 1) | 4}, 0x1AE6BA)
    delta = (read(record + 4, 2) - read(0xFF7DF8, 2) - 8) & 0xFFFF
    distance = (read(0xFF7DFC, 2) - delta) & 0xFFFF
    distance_sr = _sub_sr(sr, read(0xFF7DFC, 2), delta, 2)
    borrowed = bool(distance_sr & 1)
    if borrowed:
        before = distance; distance = (-distance) & 0xFFFF
        distance_sr = _sub_sr(distance_sr, 0, before, 2)
    if distance >= 12:
        # Tail is ST.B FFF0F5; RTS after the CMP/BCC branch.
        cycles = prefix_cycles + (156 if borrowed else 154)
        instructions = prefix_instructions + (14 if borrowed else 13)
        return AtomicPlan(cycles, instructions, ((0xFFF0F5, 0xFF),),
                          {'d0': (registers['d0'] & 0xFFFFFF00) | flags,
                           'd2': (registers['d2'] & 0xFFFF0000) | delta,
                           'd7': (registers['d7'] & 0xFFFF0000) | distance,
                           'a7': sp + 4, 'pc': ret, 'sr': _cmp_sr(distance_sr, distance, 12, 2)},
                          0x1AE6BA)
    kind = read(record, 1)
    if kind not in (0x6A, 0x69):
        return AtomicPlan(prefix_cycles + (198 if borrowed else 196),
                          prefix_instructions + (18 if borrowed else 17),
                          tuple(game.transition_contact_6b(record, delta, 0x408E)[:2]),
                          {'d0': (registers['d0'] & 0xFFFFFF00) | flags,
                           'd2': (registers['d2'] & 0xFFFF0000) | delta,
                           'd7': (registers['d7'] & 0xFFFF0000) | distance,
                           'a7': sp + 4, 'pc': ret, 'sr': _cmp_sr(distance_sr, kind, 0x69, 1)},
                          0x1AF9F4, direct_calls=1)
    script, return_pc, extra = ((0x408E, 0x1AF9D8, 0) if kind == 0x6A else
                                (0x404E, 0x1AF9F4, 22))
    publication = read(record + 0x34, 1)
    writes = [*game.transition_contact_6b(record, delta, script),
              *_bytes(sp - 4, return_pc, 4)]
    d0 = (registers['d0'] & 0xFFFFFF00) | flags
    final_sr = _logic_sr(distance_sr, 0, 1)
    if publication:
        index = read(record + 0x32, 2)
        publication_address = 0xFFAE87 + _signed_word(index)
        _spans_disjoint([('contact family-motion publication', publication_address, 1),
                         ('contact family-motion record', record, 56),
                         ('contact family-motion return', sp - 10, 14), *CONTACT_FAMILY_MOTION_GLOBALS])
        writes.extend((*_bytes(sp - 8, registers['a3'], 4),
                       *_bytes(sp - 10, registers['d1'], 2),
                       *game.publish_contact_record(record, _signed_word(index), publication)))
        d0 = (registers['d0'] & 0xFFFF0000) | index
        final_sr = _logic_sr(distance_sr, registers['d1'], 2)
    return AtomicPlan(prefix_cycles + 280 + extra + 2 * borrowed + 88 * bool(publication),
                      prefix_instructions + 22 + (2 if kind == 0x69 else 0) + borrowed + 8 * bool(publication),
                      tuple(writes),
                      {'d0': d0,
                       'd2': (registers['d2'] & 0xFFFF0000) | delta,
                       'd7': (registers['d7'] & 0xFFFF0000) | distance,
                       'a7': sp + 4, 'pc': ret, 'sr': final_sr},
                      return_pc, direct_calls=1 + bool(publication))


def begin_contact_family_motion_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_MOTION_ENTRY, begin_contact_family_motion)


def begin_contact_family_secondary(machine, registers):
    """1AF9F6: contact proximity, signed-byte motion and directional scripts."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned secondary contact record/stack')
    _spans_disjoint([('secondary record', record, 56), ('secondary return', sp, 4),
                     *CONTACT_FAMILY_MOTION_GLOBALS,
                     ('secondary player', 0xFF7E02, 2), ('secondary motion', 0xFF7DFA, 2)])
    read = lambda address, size: _read(machine, address, size)
    final = {'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF}
    be = read(0xFFF0BE, 1)
    cycles, instructions = (26, 2) if not be else (52, 4)
    tail = ((0xFFF0F5, 0xFF),)
    if be and not read(0xFFF0C0, 1):
        return AtomicPlan(86, 6, tail, {**final, 'sr': _logic_sr(sr, 0, 1)}, 0x1AE6BA)
    flags = read(record + 6, 1)
    final['d0'] = (registers['d0'] & 0xFFFFFF00) | flags
    if not flags & 0x10:
        return AtomicPlan(cycles + 68, instructions + 5, tail,
                          {**final, 'sr': _logic_sr(sr, flags, 1) | 4}, 0x1AE6BA)
    player = read(0xFF7E02, 2)
    final['d0'] = (registers['d0'] & 0xFFFF0000) | player
    delta = (read(record + 4, 2) - read(0xFF7DF8, 2) - 11) & 0xFFFF
    previous = read(0xFF7DFC, 2)
    distance = (previous - delta) & 0xFFFF
    sr = _sub_sr(sr, previous, delta, 2)
    borrowed = bool(sr & 1)
    if borrowed:
        sr = _sub_sr(sr, 0, distance, 2)
        distance = (-distance) & 0xFFFF
        cycles += 2
        instructions += 1
    final.update(d2=(registers['d2'] & 0xFFFF0000) | delta,
                 d7=(registers['d7'] & 0xFFFF0000) | distance)
    if distance >= 6:
        return AtomicPlan(cycles + 170, instructions + 14, tail,
                          {**final, 'sr': _cmp_sr(sr, distance, 6, 2)}, 0x1AE6BA)
    byte = read(record + 0x1C, 1)
    signed = byte - 256 if byte & 0x80 else byte
    motion = read(0xFF7DFA, 2)
    secondary = (motion + signed) & 0xFFFF
    sr = _add_sr(sr, motion, signed & 0xFFFF, 2)
    final['d2'] = (registers['d2'] & 0xFFFF0000) | (signed & 0xFFFF)
    kind = read(record, 1)
    sr = _cmp_sr(sr, kind, 0x76, 1)
    script, last = None, 0x1AFA82
    if kind != 0x76:
        cycles += 226
        instructions += 19
    else:
        position = read(record + 2, 2)
        upper = (position + 8) & 0xFFFF
        sr = _cmp_sr(_add_sr(sr, position, 8, 2), player, upper, 2)
        final['d2'] = (registers['d2'] & 0xFFFF0000) | upper
        if player >= upper:
            script = 0x41C8
            cycles += 294
            instructions += 25
        else:
            lower = (upper - 16) & 0xFFFF
            sr = _cmp_sr(_sub_sr(sr, upper, 16, 2), player, lower, 2)
            final['d2'] = (registers['d2'] & 0xFFFF0000) | lower
            if player >= lower:
                cycles += 278
                instructions += 26
            else:
                script, last = 0x4198, 0x1AFA74
                cycles += 312
                instructions += 28
        if script is not None:
            sr = _logic_sr(sr, 0x77, 1)
    final['sr'] = sr
    return AtomicPlan(cycles, instructions,
                      tuple(game.transition_contact_77(record, delta, secondary, script)),
                      final, last, direct_calls=1)


def begin_contact_family_secondary_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_SECONDARY_MOTION_ENTRY, begin_contact_family_secondary)


def begin_contact_family_sound_dispatch(machine, registers, dispatch):
    """Compose 1AFC4E; its ordinary request/flush uses the existing sound seam."""
    callback = {**registers, **dispatch.registers}
    record, sp, sr = (callback[key] for key in ('a1', 'a7', 'sr'))
    if callback['pc'] != CONTACT_FAMILY_SOUND_ENTRY or sp != registers['a7'] - 4:
        raise UnsupportedCandidate('contact launch dispatch identity')
    view = dispatch_plan_view(machine, dispatch)
    read = lambda address, size: _read(view, address, size)
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned contact launch record/stack')
    _spans_disjoint([('launch record', record, 56), ('launch frame', sp - 28, 32),
                     ('launch vertical', 0xFF7E5A, 2), ('launch blocked', 0xFFF0E7, 1),
                     ('launch player', 0xFF7E02, 2), ('launch script', 0xFF7E60, 4),
                     ('launch mode', 0xFF7E77, 1), ('launch contact', 0xFFF0BE, 1),
                     ('launch contact mode', 0xFFF0C0, 1), ('launch sound', 0xFFF57D, 1)])
    final = {**callback, 'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF}
    vertical = read(0xFF7E5A, 2)
    writes, calls, sound = [], 0, False
    if vertical & 0x8000:
        cycles, instructions = 42, 3
        final['sr'] = _logic_sr(sr, vertical, 2)
    elif read(0xFFF0E7, 1):
        cycles, instructions = 66, 5
        final['sr'] = _logic_sr(sr, read(0xFFF0E7, 1), 1)
    else:
        position, player = read(record + 2, 2), read(0xFF7E02, 2)
        upper = (position + 24) & 0xFFFF
        sr = _cmp_sr(_add_sr(sr, position, 24, 2), upper, player, 2)
        final['d2'] = (callback['d2'] & 0xFFFF0000) | upper
        if upper < player:
            cycles, instructions = 110, 9
            final['sr'] = sr
        else:
            lower = (upper - 48) & 0xFFFF
            sr = _cmp_sr(_sub_sr(sr, upper, 48, 2), lower, player, 2)
            final['d2'] = (callback['d2'] & 0xFFFF0000) | lower
            if lower >= player:
                cycles, instructions = 142, 12
                final['sr'] = sr
            else:
                writes = game.begin_contact_launch()
                sound = bool(read(0xFFF57D, 1))
                calls = 1
                if sound:
                    cycles, instructions = 340, 21
                    for index, name in enumerate(('d0', 'd1', 'a0', 'a1', 'a6')):
                        writes.extend(_bytes(sp - 20 + index * 4, callback[name], 4))
                    writes.extend((*_bytes(sp - 24, 0x4B, 4), *_bytes(sp - 28, 0x1AFCB4, 4)))
                    final.update(a7=sp - 28, pc=0x1E58B8,
                                 sr=_logic_sr(sr, read(0xFFF57D, 1), 1))
                else:
                    cycles, instructions = 326, 22
                    writes.extend(game.finish_contact_launch(record))
                    calls += 1
                    final['sr'] = _logic_sr(sr, 0, 1)
    plan = AtomicPlan(dispatch.cycles + cycles, dispatch.instructions + instructions,
                      (*dispatch.writes, *writes), final,
                      0x1AFCAE if sound else 0x1AFCD0, dispatch.direct_calls + calls)
    return (SoundSeam(plan, sp, 0x1AFCBA, 0x1AFCBA, 24, 28, 28,
                      suffix=finish_contact_family_sound) if sound else plan)


def finish_contact_family_sound(machine, registers):
    """Restore the concrete contact sound frame, then publish the object suffix."""
    sp = registers['a7']
    restored = {name: _read(machine, sp + 4 + index * 4, 4)
                for index, name in enumerate(('d0', 'd1', 'a0', 'a1', 'a6'))}
    record = restored['a1']
    _spans_disjoint([('launch suffix record', record, 56), ('launch suffix frame', sp, 28)])
    restored.update(a7=sp + 28, pc=_read(machine, sp + 24, 4) & 0xFFFFFF,
                    sr=_logic_sr(registers['sr'], 0, 1))
    return AtomicPlan(128, 6, tuple(game.finish_contact_launch(record)), restored,
                      0x1AFCD0, direct_calls=1)


CONTACT_TYPE7E_GLOBALS = (
    ('type7E blocked', 0xFFF0E7, 1), ('type7E ready', 0xFFF07E, 1),
    ('type7E armed', 0xFFF114, 1), ('type7E motion', 0xFF7DFE, 2),
    ('type7E motion limit', 0xFF7E00, 2),
)


def begin_contact_type7e(machine, registers):
    """Own only `1AFE1C`'s finite no-callee exits.

    Ready, unarmed records enter the decimal/sound/stream handoff and are
    intentionally declined as one untouched dispatcher callback.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type7E record/stack')
    _spans_disjoint([('type7E record', record, 66), ('type7E return', sp, 4),
                     *CONTACT_TYPE7E_GLOBALS])
    read = lambda address, size: _read(machine, address, size)
    ret = read(sp, 4) & 0xFFFFFF
    blocked = read(0xFFF0E7, 1)
    if blocked:
        cycles, instructions, clear = 82, 5, False
    elif not read(0xFFF07E, 1):
        cycles, instructions, clear = 130, 8, True
    elif read(0xFFF114, 1):
        cycles, instructions, clear = 138, 9, False
    else:
        raise UnsupportedCandidate('type7E progress/stream handoff')
    return AtomicPlan(cycles, instructions, tuple(game.finish_contact_type7e(clear_armed=clear)),
                      {'a7': sp + 4, 'pc': ret, 'sr': _logic_sr(sr, 0x180, 2)},
                      0x1AFF3E, direct_calls=1)


def begin_contact_type7e_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_TYPE7E_ENTRY, begin_contact_type7e)


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


def begin_contact_family_type15(machine, registers):
    """1AE978: type-15 sibling call followed by the shared D8/RTS tail."""
    record, sp = registers['a1'], registers['a7']
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type15 sibling stack')
    _spans_disjoint([('type15 sibling frame', sp - 10, 14),
                     ('type15 sibling record', record, 66),
                     *CONTACT_SIBLING_GLOBALS])
    # Although this shares 1AE9C6's post-sibling D8 tail, the BSR's durable
    # stack word is the callback's own 1AE97C return address.
    callback = AtomicPlan(18, 1, _bytes(sp - 4, 0x1AE97C, 4),
                          {**registers, 'a7': sp - 4, 'pc': CONTACT_SIBLING_ENTRY},
                          CONTACT_FAMILY_TYPE15_ENTRY, direct_calls=1)
    sibling = begin_contact_sibling(dispatch_plan_view(machine, callback),
                                    callback.registers)
    if _read(machine, 0xFFF0D8, 1) == 0:
        raise UnsupportedCandidate('type15 sibling D8 tail does not return')
    final = dict(sibling.registers)
    final.update(a7=sp + 4, pc=_read(machine, sp, 4) & 0xFFFFFF,
                 sr=_logic_sr(sibling.registers['sr'], _read(machine, 0xFFF0D8, 1), 1))
    return AtomicPlan(callback.cycles + sibling.cycles + 42,
                      callback.instructions + sibling.instructions + 3,
                      tuple(dict((*callback.writes, *sibling.writes)).items()), final,
                      0x1A91C4, callback.direct_calls + sibling.direct_calls)


def begin_contact_family_type15_dispatch(machine, registers, dispatch):
    """Compose the table dispatcher with the 1AE978 type-15 wrapper."""
    sp = registers['a7']
    if dispatch.registers.get('pc') != CONTACT_FAMILY_TYPE15_ENTRY or \
            dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('type15 sibling dispatch prefix identity')
    callback = begin_contact_family_type15(dispatch_plan_view(machine, dispatch),
                                           {**registers, **dispatch.registers})
    final = dict(dispatch.registers); final.update(callback.registers)
    return AtomicPlan(dispatch.cycles + callback.cycles,
                      dispatch.instructions + callback.instructions,
                      tuple(dict((*dispatch.writes, *callback.writes)).items()), final,
                      callback.last_pc, dispatch.direct_calls + callback.direct_calls)


def begin_contact_family_type03_sound_seam(machine, registers):
    """1AED86's D8-zero branch joined to C6's measured contact sound seam.

    Type 03 does no durable work before entering the wrapper: TST.B FFF0D8
    followed by the taken BEQ.W.  Its non-zero arm mutates the record and is
    deliberately outside this candidate.  The zero arm preserves the caller's
    stack exactly, so C6 owns the only local BSR and sound frame.
    """
    record, sp = registers['a1'], registers['a7']
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type03 record/stack')
    _spans_disjoint([('type03 record', record, 66),
                     ('type03 frame', sp - 10, 14),
                     *CONTACT_SIBLING_GLOBALS])
    d8 = _read(machine, 0xFFF0D8, 1)
    if d8:
        raise UnsupportedCandidate('type03 D8 mutation arm is not recovered')
    prefix = AtomicPlan(26, 2, (),
                        {**registers, 'pc': CONTACT_SIBLING_WRAPPER,
                         'sr': _logic_sr(registers['sr'], d8, 1)},
                        CONTACT_FAMILY_TYPE03_ENTRY)
    sound = begin_contact_sibling_wrapper_sound_seam(
        dispatch_plan_view(machine, prefix), prefix.registers, CONTACT_SIBLING_WRAPPER)
    combined = AtomicPlan(prefix.cycles + sound.prefix.cycles,
                          prefix.instructions + sound.prefix.instructions,
                          tuple(dict((*prefix.writes, *sound.prefix.writes)).items()),
                          sound.prefix.registers, sound.prefix.last_pc,
                          prefix.direct_calls + sound.prefix.direct_calls)
    return SoundSeam(combined, sound.stack_basis, sound.resume_pc, sound.return_slot,
                     sound.saved_frame, sound.frame_size, sound.return_delta,
                     sound.counts_contact, sound.suffix)


def begin_contact_family_type03_dispatch_sound_seam(machine, registers, dispatch):
    """Compose the table callback prefix with Type 03's bounded sound seam."""
    sp = registers['a7']
    if dispatch.registers.get('pc') != CONTACT_FAMILY_TYPE03_ENTRY or \
            dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('type03 dispatch prefix identity')
    callback_registers = {**registers, **dispatch.registers}
    sound = begin_contact_family_type03_sound_seam(dispatch_plan_view(machine, dispatch),
                                                    callback_registers)
    final = dict(dispatch.registers)
    final.update(sound.prefix.registers)
    combined = AtomicPlan(dispatch.cycles + sound.prefix.cycles,
                          dispatch.instructions + sound.prefix.instructions,
                          tuple(dict((*dispatch.writes, *sound.prefix.writes)).items()),
                          final, sound.prefix.last_pc,
                          dispatch.direct_calls + sound.prefix.direct_calls)
    return SoundSeam(combined, sound.stack_basis, sound.resume_pc, sound.return_slot,
                     sound.saved_frame, sound.frame_size, sound.return_delta,
                     sound.counts_contact, sound.suffix)


def begin_contact_family_type46_sound_seam(machine, registers):
    """1AEF5C's bounded command-66 prefix and counted-replacement seam."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type46 record/stack')
    _spans_disjoint([('type46 record', record, 66),
                     ('type46 sound frame', sp - 34, 38),
                     ('type46 counter', 0xFF7E3C, 1),
                     ('type46 sound', 0xFFF57D, 1),
                     ('type46 total', 0xFFF14E, 2)])
    read = lambda address, size: _read(machine, address, size)
    request, facts = game.contact_type46_request(read)
    if facts['capped']:
        raise UnsupportedCandidate('type46 capped return arm is not recovered')
    if not facts['sound']:
        raise UnsupportedCandidate('type46 sound-off replacement arm is not recovered')
    old, value = facts['old'], facts['value']
    # Machine side: the local BSR frame, the five-register MOVEM save, the
    # request argument and command words, and the JSR return to 1AEFA0.
    # Cost table (original machine): 220 cycles / 14 instructions below the
    # clamp, 238 / 15 when the increment is clamped at 0x39.
    writes = (*_bytes(sp - 4, 0x1AEF6C, 4), *_bytes(sp - 6, registers['d0'], 2),
              *_bytes(sp - 10, registers['a6'], 4), *_bytes(sp - 14, registers['a1'], 4),
              *_bytes(sp - 18, registers['a0'], 4), *_bytes(sp - 22, registers['d1'], 4),
              *_bytes(sp - 26, (registers['d0'] & 0xFFFFFF00) | value, 4),
              *_bytes(sp - 30, facts['command'], 4),
              *_bytes(sp - 34, 0x1AEFA0, 4), *request)
    prefix = AtomicPlan(220 if old < 0x38 else 238, 14 if old < 0x38 else 15, writes,
                        {**registers, 'd0': (registers['d0'] & 0xFFFFFF00) | value,
                         'a7': sp - 34, 'pc': 0x1E58B8,
                         'sr': _logic_sr(sr, facts['sound'], 1)}, 0x1AEF9A, direct_calls=2)
    return SoundSeam(prefix, sp - 6, 0x1AEFA6, 0x1AEFA6, 24, 28, 28,
                     suffix=finish_contact_family_type46_sound)


def begin_contact_family_type46_dispatch_sound_seam(machine, registers, dispatch):
    """Compose the table prefix with Type 46's exact command-66 seam."""
    sp = registers['a7']
    if dispatch.registers.get('pc') != CONTACT_FAMILY_TYPE46_ENTRY or \
            dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('type46 dispatch prefix identity')
    callback_registers = {**registers, **dispatch.registers}
    sound = begin_contact_family_type46_sound_seam(dispatch_plan_view(machine, dispatch),
                                                    callback_registers)
    final = dict(dispatch.registers)
    final.update(sound.prefix.registers)
    prefix = AtomicPlan(dispatch.cycles + sound.prefix.cycles,
                        dispatch.instructions + sound.prefix.instructions,
                        tuple(dict((*dispatch.writes, *sound.prefix.writes)).items()),
                        final, sound.prefix.last_pc,
                        dispatch.direct_calls + sound.prefix.direct_calls)
    return SoundSeam(prefix, sound.stack_basis, sound.resume_pc, sound.return_slot,
                     sound.saved_frame, sound.frame_size, sound.return_delta,
                     sound.counts_contact, sound.suffix)


def finish_contact_family_type46_sound(machine, registers):
    """Restore Type 46's local word/frame and join 1AF4C2 replacement."""
    sp = registers['a7'] + 24
    restored = dict(registers)
    for index, name in enumerate(('a6', 'a1', 'a0', 'd1', 'd0'), 1):
        restored[name] = _read(machine, sp - index * 4, 4)
    restored['d0'] = (restored['d0'] & 0xFFFF0000) | _read(machine, sp, 2)
    restored.update(a7=sp + 6, pc=_read(machine, sp + 2, 4) & 0xFFFFFF)
    if restored['pc'] != 0x1AEF6C:
        raise UnsupportedCandidate('type46 local BSR return identity')
    tail = replace_object(machine, restored, increment_total=True,
                          extra_spans=(('type46 counter', 0xFF7E3C, 1),))
    final = dict(restored); final.update(tail.registers)
    return AtomicPlan(94 + tail.cycles, 5 + tail.instructions, tail.writes, final,
                      tail.last_pc, tail.direct_calls)


def begin_contact_family_type43_sound_seam(machine, registers):
    """1AE64C's motion/template update and its command-63 sound request.

    The publication itself is ``game.contact_type43_update``.  This boundary
    owns the saved secondary-motion word at ``sp-2``, the five-register MOVEM
    frame, the request argument/command words and the JSR return to 1AE6A0,
    then hands the original machine the request at 1E58B8.  The resume point
    1AE6A6 lies past a second native call (JSR 1E589A) that the free-running
    original executes inside the same seam.  Cost table (original machine):
    510 cycles / 32 instructions for the active, sound-on arm.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type43 record/stack')
    _spans_disjoint([('type43 record', record, 66),
                     ('type43 sound frame', sp - 30, 30),
                     ('type43 active', 0xFFF0C1, 1),
                     ('type43 sound', 0xFFF57D, 1),
                     ('type43 motion', 0xFF7DF6, 8),
                     ('type43 span', 0xFF7E0A, 8),
                     ('type43 latch', 0xFFF154, 1)])
    read = lambda address, size: _read(machine, address, size)
    update, facts = game.contact_type43_update(read, record)
    if not facts['active']:
        raise UnsupportedCandidate('type43 inactive early return is not recovered')
    if not facts['sound']:
        raise UnsupportedCandidate('type43 sound-off request arm is not recovered')
    vertical_span = facts['vertical_span']
    writes = (*_bytes(sp - 2, facts['old_secondary'], 2),
              *update,
              *_bytes(sp - 22, (registers['d0'] & 0xFFFF0000) | vertical_span, 4),
              *_bytes(sp - 18, registers['d1'], 4),
              *_bytes(sp - 14, registers['a0'], 4),
              *_bytes(sp - 10, registers['a1'], 4),
              *_bytes(sp - 6, registers['a6'], 4),
              *_bytes(sp - 26, facts['command'], 4),
              *_bytes(sp - 30, 0x1AE6A0, 4))
    prefix = AtomicPlan(510, 32, writes,
                        {**registers,
                         'd0': (registers['d0'] & 0xFFFF0000) | vertical_span,
                         'd7': (registers['d7'] & 0xFFFF0000) | facts['new_secondary'],
                         'a7': sp - 30, 'pc': 0x1E58B8,
                         'sr': _logic_sr(sr, facts['sound'], 1)}, 0x1AE69A, direct_calls=2)
    return SoundSeam(prefix, sp, 0x1AE6A6, 0x1AE6A6, 26, 26, 30,
                     suffix=finish_contact_family_type43_sound)


def begin_contact_family_type43_dispatch_sound_seam(machine, registers, dispatch):
    """Compose the table prefix with Type 43's exact command-63 seam."""
    sp = registers['a7']
    if (dispatch.registers.get('pc') != CONTACT_FAMILY_TYPE43_ENTRY
            or dispatch.registers.get('a7') != sp - 4):
        raise UnsupportedCandidate('type43 dispatch prefix identity')
    callback_registers = {**registers, **dispatch.registers}
    sound = begin_contact_family_type43_sound_seam(dispatch_plan_view(machine, dispatch),
                                                    callback_registers)
    final = dict(dispatch.registers)
    final.update(sound.prefix.registers)
    prefix = AtomicPlan(dispatch.cycles + sound.prefix.cycles,
                        dispatch.instructions + sound.prefix.instructions,
                        tuple(dict((*dispatch.writes, *sound.prefix.writes)).items()),
                        final, sound.prefix.last_pc,
                        dispatch.direct_calls + sound.prefix.direct_calls)
    return SoundSeam(prefix, sound.stack_basis, sound.resume_pc, sound.return_slot,
                     sound.saved_frame, sound.frame_size, sound.return_delta,
                     sound.counts_contact, sound.suffix)


def finish_contact_family_type43_sound(machine, registers):
    """Restore Type 43's saved registers and secondary-motion word, then return.

    ``registers`` stands at the local resume 1AE6A6, past both native sound
    calls; its A7 is the command-word slot.  The MOVEM frame, the saved
    FF7DFA word and the caller's return slot sit at fixed offsets above it,
    exactly as 1AE6A6..1AE6B2 reads them back: 96 cycles / 4 instructions.
    """
    base = registers['a7']
    restored = dict(registers)
    for name, offset in (('d0', 4), ('d1', 8), ('a0', 12), ('a1', 16), ('a6', 20)):
        restored[name] = _read(machine, base + offset, 4)
    old_secondary = _read(machine, base + 24, 2)
    restored.update(a7=base + 30, pc=_read(machine, base + 26, 4) & 0xFFFFFF)
    return AtomicPlan(96, 4, _bytes(0xFF7DFA, old_secondary, 2), restored, 0x1AE6B2)


def begin_contact_family_type55(machine, registers):
    """1AF590's bit-4 bounded-distance and direct flag returns through 1AE6B4.

    Arm selection and the distance arithmetic are ``game.contact_type55_guard``;
    this boundary owns the alias guards, the cost table, the register residue
    and the CCR.  Cost table from the original machine (``factcheck``):

        direct return  (FFF0BE set, FFF0C0 clear)          86 cycles /  6 instructions
        guard, no borrow                                   180 / 15
        guard, borrowed and negated                        182 / 16
        guard reached through FFF0BE and FFF0C0 both set   +26 / +2

    The guard's own SUB/NEG/CMP discards every incoming CCR bit it does not
    set, so its residue is the same however it is reached.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type55 record/stack')
    _spans_disjoint([('type55 record', record, 66), ('type55 return', sp, 4),
                     ('type55 flags', 0xFFF0BE, 1), ('type55 mode', 0xFFF0C0, 1),
                     ('type55 motion', 0xFF7DFC, 2), ('type55 player', 0xFF7DF8, 2),
                     ('type55 tail', 0xFFF0F5, 1)])
    read = lambda address, size: _read(machine, address, size)
    arm, facts = game.contact_type55_guard(read, record)
    writes = tuple(game.contact_type55_return())
    if arm == 'direct':
        return AtomicPlan(86, 6, writes,
                          {'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF,
                           'sr': _logic_sr(sr, 0, 1)},
                          0x1AE6BA)
    if arm == 'inactive':
        raise UnsupportedCandidate('type55 observed guard arm is not active')
    if arm == 'transition':
        raise UnsupportedCandidate('type55 transition arm is not recovered')
    delta, previous, distance, borrowed = (facts[key] for key in ('delta', 'previous', 'distance', 'borrowed'))
    residue = _sub_sr(sr, previous, delta, 2)
    if borrowed:
        residue = _sub_sr(residue, 0, facts['difference'], 2)
    cycles, instructions = (182, 16) if borrowed else (180, 15)
    if facts['selector']:
        cycles, instructions = cycles + 26, instructions + 2
    return AtomicPlan(cycles, instructions, writes,
                      {'d0': (registers['d0'] & 0xFFFFFF00) | facts['flags'],
                       'd2': (registers['d2'] & 0xFFFF0000) | delta,
                       'd7': (registers['d7'] & 0xFFFF0000) | distance,
                       'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF,
                       'sr': _cmp_sr(residue, distance, 6, 2)},
                      0x1AE6BA)


def begin_contact_family_type55_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE55_ENTRY,
                                    begin_contact_family_type55)


def begin_contact_family_type58(machine, registers):
    """1AF5F0's bit-4 bounded-distance guard, both arms owned.

    Same shape as ``begin_contact_family_type55`` (same ``FFF0BE`` selector,
    same record-plus-6 bit-4 activity test, same shared 1AE6B4 tail), but
    this entry's own guard adds 2 to the delta rather than subtracting 18,
    its limit is 0xC rather than 6, and both sides of the comparison are
    recovered on the recorded history: a pass rewrites FF7DFC with the delta
    and returns locally at 1AF636; a fail publishes the same FFF0F5 tail flag
    as the direct and inactive arms through 1AE6B4.  Cost table
    (``factcheck``):

        direct return  (FFF0BE set, FFF0C0 clear)                    86 /  6
        guard fail,  no borrow, reached via FFF0BE clear             180 / 15
        guard fail,  borrowed and negated, via FFF0BE clear          182 / 16
        guard pass,  no borrow, reached via FFF0BE clear             178 / 15
        guard pass,  borrowed and negated, via FFF0BE clear          180 / 16
        every guard arm reached through FFF0BE and FFF0C0 both set  +26 /  +2

    The guard's own SUB/NEG discards every incoming CCR bit it does not set;
    a fail's final flags are the CMPI's own (ST never touches CCR), while a
    pass's final flags come from the local MOVE.W that publishes delta.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type58 record/stack')
    _spans_disjoint([('type58 record', record, 66), ('type58 return', sp, 4),
                     ('type58 flags', 0xFFF0BE, 1), ('type58 mode', 0xFFF0C0, 1),
                     ('type58 motion', 0xFF7DFC, 2), ('type58 player', 0xFF7DF8, 2),
                     ('type58 tail', 0xFFF0F5, 1)])
    read = lambda address, size: _read(machine, address, size)
    arm, facts = game.contact_type58_guard(read, record)
    fail_writes = tuple(game.contact_type58_fail())
    if arm == 'direct':
        return AtomicPlan(86, 6, fail_writes,
                          {'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF,
                           'sr': _logic_sr(sr, 0, 1)},
                          0x1AE6BA)
    if arm == 'inactive':
        raise UnsupportedCandidate('type58 observed guard arm is not active')
    delta, previous, distance, borrowed = (facts[key] for key in ('delta', 'previous', 'distance', 'borrowed'))
    residue = _sub_sr(sr, previous, delta, 2)
    if borrowed:
        residue = _sub_sr(residue, 0, facts['difference'], 2)
    extra_cycles, extra_instructions = (26, 2) if facts['selector'] else (0, 0)
    base_registers = {'d0': (registers['d0'] & 0xFFFFFF00) | facts['flags'],
                      'd2': (registers['d2'] & 0xFFFF0000) | delta,
                      'd7': (registers['d7'] & 0xFFFF0000) | distance,
                      'a7': sp + 4, 'pc': read(sp, 4) & 0xFFFFFF}
    if arm == 'guard_fail':
        # The CMPI's own flags stand: ST never touches CCR.
        base_cycles, base_instructions = (182, 16) if borrowed else (180, 15)
        return AtomicPlan(base_cycles + extra_cycles, base_instructions + extra_instructions, fail_writes,
                          {**base_registers, 'sr': _cmp_sr(residue, distance, 0xC, 2)},
                          0x1AE6BA)
    # The CMPI's flags are overwritten by the local MOVE.W that publishes
    # delta to FF7DFC: N/Z from delta, V/C cleared, X carried from the SUB/NEG.
    base_cycles, base_instructions = (180, 16) if borrowed else (178, 15)
    writes = tuple(game.contact_type58_pass(delta))
    return AtomicPlan(base_cycles + extra_cycles, base_instructions + extra_instructions, writes,
                      {**base_registers, 'sr': _logic_sr(residue, delta, 2)},
                      0x1AF636)


def begin_contact_family_type58_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE58_ENTRY,
                                    begin_contact_family_type58)


def begin_contact_family_type63(machine, registers):
    """1AF81C's bit-4 bounded-distance guard (limit 0xA) plus a self-kind check.

    Same shape as ``begin_contact_family_type58`` (the same ``FFF0BE``/
    ``FFF0C0`` family selector, the same record-plus-6 bit-4 activity
    test, the same shared 1AE6B4 tail), but this entry's own guard adds
    nothing to the delta and its limit is 0xA rather than 0xC.  A guard
    pass publishes the delta through FF7DFC exactly as Type-58's own pass
    does, then continues into a kind check: a match against the fixed
    0x63 constant returns locally at once; a mismatch retypes the record
    to 0x63 (``game.contact_type63_retype``) and, when ``FFF57D`` is
    clear, also returns locally -- when it is set the mismatch instead
    continues into a command-0x45 sound seam, recovered separately by
    ``begin_contact_family_type63_sound_seam``.  Cost table
    (``factcheck``):

        direct return  (FFF0BE set, FFF0C0 clear)                    86 /  6
        guard fail,  no borrow, reached via FFF0BE clear             172 / 14
        guard fail,  borrowed and negated, via FFF0BE clear          174 / 15
        kind match,  no borrow, reached via FFF0BE clear             192 / 16
        kind match,  borrowed and negated, via FFF0BE clear          194 / 17
        kind mismatch, no sound, no borrow, via FFF0BE clear         252 / 20
        kind mismatch, no sound, borrowed and negated, via FFF0BE clear  254 / 21
        every guard arm reached through FFF0BE and FFF0C0 both set  +26 /  +2

    The guard's own SUB/NEG discards every incoming CCR bit it does not
    set; a guard fail's final flags are the CMPI's own (ST never touches
    CCR).  A kind check's final flags are its own CMPI.B's (0x63), fed by
    the local MOVE.W that publishes delta (N/Z/V/C from delta, X carried
    from the SUB/NEG); a no-sound mismatch's final flags are instead the
    trailing TST.B FFF57D's own (clear, since this arm requires it clear).
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type63 record/stack')
    _spans_disjoint([('type63 record', record, 66), ('type63 return', sp, 4),
                     ('type63 flags', 0xFFF0BE, 1), ('type63 mode', 0xFFF0C0, 1),
                     ('type63 motion', 0xFF7DFC, 2), ('type63 player', 0xFF7DF8, 2),
                     ('type63 tail', 0xFFF0F5, 1), ('type63 sound', 0xFFF57D, 1)])
    read = lambda address, size: _read(machine, address, size)
    arm, facts = game.contact_type63_guard(read, record)
    return_pc = read(sp, 4) & 0xFFFFFF
    fail_writes = tuple(game.contact_type63_fail())
    if arm == 'direct':
        return AtomicPlan(86, 6, fail_writes,
                          {'a7': sp + 4, 'pc': return_pc, 'sr': _logic_sr(sr, 0, 1)},
                          0x1AE6BA)
    if arm == 'inactive':
        raise UnsupportedCandidate('type63 observed guard arm is not active')
    if arm == 'kind_mismatch_sound':
        raise UnsupportedCandidate('type63 kind-mismatch sound arm is not recovered here')
    delta, previous, distance, borrowed = (facts[key] for key in ('delta', 'previous', 'distance', 'borrowed'))
    residue = _sub_sr(sr, previous, delta, 2)
    if borrowed:
        residue = _sub_sr(residue, 0, facts['difference'], 2)
    extra_cycles, extra_instructions = (26, 2) if facts['selector'] else (0, 0)
    base_registers = {'d0': (registers['d0'] & 0xFFFFFF00) | facts['flags'],
                      'd2': (registers['d2'] & 0xFFFF0000) | delta,
                      'd7': (registers['d7'] & 0xFFFF0000) | distance,
                      'a7': sp + 4, 'pc': return_pc}
    if arm == 'guard_fail':
        base_cycles, base_instructions = (174, 15) if borrowed else (172, 14)
        return AtomicPlan(base_cycles + extra_cycles, base_instructions + extra_instructions, fail_writes,
                          {**base_registers, 'sr': _cmp_sr(residue, distance, 0xA, 2)},
                          0x1AE6BA)
    # kind_match or kind_mismatch (no sound): both first publish the delta
    # locally exactly as a Type-58 guard pass does, then run their own
    # CMPI.B #$63 against the record's own kind byte.
    pass_writes = tuple(game.contact_type63_pass(delta))
    stage_sr = _logic_sr(residue, delta, 2)
    kind_sr = _cmp_sr(stage_sr, facts['kind'], 0x63, 1)
    if arm == 'kind_match':
        base_cycles, base_instructions = (194, 17) if borrowed else (192, 16)
        return AtomicPlan(base_cycles + extra_cycles, base_instructions + extra_instructions, pass_writes,
                          {**base_registers, 'sr': kind_sr}, 0x1AF892)
    # kind_mismatch, no sound: also retype the record, then TST.B FFF57D
    # (clear, since this arm requires it clear) sets the truly final flags.
    retype_writes = tuple(game.contact_type63_retype(record))
    base_cycles, base_instructions = (254, 21) if borrowed else (252, 20)
    return AtomicPlan(base_cycles + extra_cycles, base_instructions + extra_instructions,
                      pass_writes + retype_writes,
                      {**base_registers, 'sr': _logic_sr(kind_sr, facts['sound'], 1)}, 0x1AF892)


def begin_contact_family_type63_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE63_ENTRY,
                                    begin_contact_family_type63)


def begin_contact_family_type63_sound_seam(machine, registers):
    """1AF81C's kind-mismatch arm, continued into its own command-0x45 seam.

    Reached only when ``game.contact_type63_guard`` names
    ``kind_mismatch_sound`` (the guard passed, the record's own kind byte
    did not match 0x63, and FFF57D is set).  The delta publish and the
    retype (``game.contact_type63_pass``/``game.contact_type63_retype``)
    are the same writes the RAM-only mismatch arm makes; here they are
    followed by a MOVEM.L d0-d1/a0-a1/a6 save, a fixed command-0x45 word
    and a JSR into the shared request entry -- a private 24-byte saved
    frame plus a 4-byte return slot, the same ABI shape as Type-46's own
    seam.  Cost table (``factcheck``): relative to the RAM-only no-sound
    mismatch arm's own total (252/20 no borrow, 254/21 borrowed, +26/+2
    when the selector is set), swap its closing TST.B/BEQ(taken)/RTS (42
    cycles / 3 instructions) for the MOVEM/PEA/JSR frame that instead
    lands at the native request entry (108 cycles / 5 instructions) -- a
    net +66 cycles / +2 instructions (318/22 no borrow, 320/23 borrowed,
    before the native sound-request entry).
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type63 sound record/stack')
    _spans_disjoint([('type63 sound record', record, 66),
                     ('type63 sound frame', sp - 28, 28),
                     ('type63 sound flags', 0xFFF0BE, 1), ('type63 sound mode', 0xFFF0C0, 1),
                     ('type63 sound motion', 0xFF7DFC, 2), ('type63 sound player', 0xFF7DF8, 2),
                     ('type63 sound gate', 0xFFF57D, 1)])
    read = lambda address, size: _read(machine, address, size)
    arm, facts = game.contact_type63_guard(read, record)
    if arm != 'kind_mismatch_sound':
        raise UnsupportedCandidate('type63 sound seam outside the kind-mismatch sound arm')
    delta, previous, distance, borrowed = (facts[key] for key in ('delta', 'previous', 'distance', 'borrowed'))
    residue = _sub_sr(sr, previous, delta, 2)
    if borrowed:
        residue = _sub_sr(residue, 0, facts['difference'], 2)
    extra_cycles, extra_instructions = (26, 2) if facts['selector'] else (0, 0)
    base_cycles, base_instructions = (254, 21) if borrowed else (252, 20)
    # Relative to the RAM-only no-sound-mismatch arm's own total: swap its
    # closing TST.B/BEQ(taken)/RTS (42 cycles / 3 instructions) for the
    # MOVEM/PEA/JSR frame that instead lands at the native request entry
    # (108 cycles / 5 instructions) -- a net +66 cycles / +2 instructions.
    prefix_cycles = base_cycles + extra_cycles + 66
    prefix_instructions = base_instructions + extra_instructions + 2
    saved_d0 = (registers['d0'] & 0xFFFFFF00) | facts['flags']
    writes = (*game.contact_type63_pass(delta), *game.contact_type63_retype(record),
              *_bytes(sp - 4, registers['a6'], 4), *_bytes(sp - 8, registers['a1'], 4),
              *_bytes(sp - 12, registers['a0'], 4), *_bytes(sp - 16, registers['d1'], 4),
              *_bytes(sp - 20, saved_d0, 4),
              *_bytes(sp - 24, 0x45, 4), *_bytes(sp - 28, 0x1AF886, 4))
    return AtomicPlan(prefix_cycles, prefix_instructions, writes,
                      {**registers, 'd0': saved_d0,
                       'd2': (registers['d2'] & 0xFFFF0000) | delta,
                       'd7': (registers['d7'] & 0xFFFF0000) | distance,
                       'a7': sp - 28, 'pc': 0x1E58B8,
                       'sr': _logic_sr(residue, facts['sound'], 1)}, 0x1AF880, direct_calls=1)


def begin_contact_family_type63_dispatch_sound_seam(machine, registers, dispatch):
    """Compose collection dispatch with Type-63's exact command-0x45 seam."""
    sp = registers['a7']
    if dispatch.registers.get('pc') != CONTACT_FAMILY_TYPE63_ENTRY or \
            dispatch.registers.get('a7') != sp - 4:
        raise UnsupportedCandidate('type63 dispatch prefix identity')
    callback_registers = {**registers, **dispatch.registers}
    sound = begin_contact_family_type63_sound_seam(dispatch_plan_view(machine, dispatch),
                                                    callback_registers)
    final = dict(dispatch.registers)
    final.update(sound.registers)
    prefix = AtomicPlan(dispatch.cycles + sound.cycles, dispatch.instructions + sound.instructions,
                        tuple(dict((*dispatch.writes, *sound.writes)).items()),
                        final, sound.last_pc, dispatch.direct_calls + sound.direct_calls)
    # The MOVEM/PEA/JSR frame is built relative to the callback's own SP
    # (post the outer collection-dispatch JSR), not the true caller's SP:
    # the seam's stack_basis must match that same frame of reference.
    return SoundSeam(prefix, callback_registers['a7'], 0x1AF88C, 0x1AF88C, 24, 28, 28,
                     suffix=finish_contact_family_type63_sound)


def finish_contact_family_type63_sound(machine, registers):
    """Restore Type-63's local MOVEM frame, then its own RTS to the dispatcher.

    ``registers`` stands at the local resume 0x1AF88C, past both native
    sound calls; A7 is the pushed command-word slot (the pea already
    consumed by the pair of JSRs' own matched pops).  ADDQ.L #4,A7 then
    the MOVEM.L restore sit at fixed offsets above it, exactly as
    1AF88C..1AF892 reads them back.
    """
    if registers.get('pc') != 0x1AF88C:
        raise UnsupportedCandidate('foreign type63 sound return')
    base = registers['a7'] + 4
    restored = dict(registers)
    for name, offset in (('d0', 0), ('d1', 4), ('a0', 8), ('a1', 12), ('a6', 16)):
        restored[name] = _read(machine, base + offset, 4)
    local_sp = base + 20
    ret = _read(machine, local_sp, 4) & 0xFFFFFF
    if ret != COLLECTION_DISPATCH_RETURN:
        raise UnsupportedCandidate('type63 sound local return identity')
    restored.update(a7=local_sp + 4, pc=ret)
    return AtomicPlan(76, 3, (), restored, 0x1AF892)


def begin_contact_family_type74(machine, registers):
    """1AFA84's bounded-distance guard, window/kind/state gate and child spawn.

    Same FFF0BE/FFF0C0 family selector as Type-55/58's own guard (no bit-4
    test here), reached by both the kind-0x74 and kind-0x75 collection
    dispatch slots -- kind 0x75 is what a triggering record becomes after it
    spawns, so a kind-0x75 re-entry always fails the kind recheck below.  A
    guard pass rewrites FF7DFC and continues into a horizontal-window, kind
    and state gate (``game.contact_type74_target``); any one of those checks
    that fails returns locally at 1AFB34 with only the FF7DFC rewrite
    already published.  Passing every check retypes the triggering record
    to a used kind-0x75 marker and spawns a child from the fixed 1B7E7C
    template into the first free FF7F06 pool slot -- ``game.free_object``
    and ``game.initialize`` are the same primitives already proven for the
    spawn-region callers, so only the surrounding gate and the self-retype
    are new semantics.  A guard fail publishes the same FFF0F5 tail flag as
    the direct arm through the shared 1AE6B4 tail.  Cost table
    (``factcheck``), each row additive to the selector-route prefix (26/2
    short: FFF0BE clear; 52/4 full: FFF0BE and FFF0C0 both set):

        direct return    (FFF0BE set, FFF0C0 clear)                    86 /  6
        guard fail,  no borrow                                        136 / 11
        guard fail,  borrowed and negated                             138 / 12
        window upper fail   (player x >= record x + 0x10)             168 / 15  (after a guard pass)
        window lower fail   (player x <  record x - 0x10)              38 /  4
        kind mismatch        (record kind != 0x74)                     38 /  3
        state gate            (FFF0D8 != 0)                            42 /  3
        negative state        (FF7E5A < 0)                             42 /  3
        zero state            (FF7E5A == 0)                            42 /  3
        spawn, pool exhausted                                         976 / 91
        spawn, pool slot at index i                          734 + 40*i / 44 + 4*i

    (the window-upper row already folds in the fixed run from the guard
    pass through its own branch; every later row is additive to the row
    above it, in source order.)  The gate's own TST/CMP/SUBI/ADDI discard
    every incoming CCR bit they do not set; a bail's final flags are its own
    last comparison's, a spawn's final flags come from the local MOVE.W
    that publishes the child's Y position, and the pool scan's own exit
    flags (found or exhausted) sit between -- exactly as they do inside the
    already-proven ``spawn_region``.
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type74 record/stack')
    # The triggering record is itself one member of the same 66-byte-stride
    # object space the FF7F06 pool scans, so it is deliberately not checked
    # disjoint from the pool here: its own kind byte is nonzero (0x74 or
    # 0x75) both before and after the retype below, so ``game.free_object``
    # never selects it regardless of read order.
    _spans_disjoint([
        ('type74 record', record, 66), ('type74 return', sp, 4),
        ('type74 flags', 0xFFF0BE, 1), ('type74 mode', 0xFFF0C0, 1),
        ('type74 motion', 0xFF7DFC, 2), ('type74 player', 0xFF7DF8, 2),
        ('type74 screen x', 0xFF7E02, 2), ('type74 gate', 0xFFF0D8, 1),
        ('type74 state', 0xFF7E5A, 2), ('type74 tail', 0xFFF0F5, 1),
        ('type74 retype latch', 0xFFF0CC, 1), ('type74 retype counter', 0xFFF0B0, 2),
    ])
    _spans_disjoint([
        ('type74 pool', CONTACT_TYPE74_POOL, CONTACT_TYPE74_POOL_COUNT * 66),
        ('type74 return', sp, 4),
        ('type74 flags', 0xFFF0BE, 1), ('type74 mode', 0xFFF0C0, 1),
        ('type74 motion', 0xFF7DFC, 2), ('type74 player', 0xFF7DF8, 2),
        ('type74 screen x', 0xFF7E02, 2), ('type74 gate', 0xFFF0D8, 1),
        ('type74 state', 0xFF7E5A, 2), ('type74 tail', 0xFFF0F5, 1),
        ('type74 retype latch', 0xFFF0CC, 1), ('type74 retype counter', 0xFFF0B0, 2),
    ])
    read = lambda address, size: _read(machine, address, size)
    arm, facts = game.contact_type74_guard(read, record)
    fail_writes = tuple(game.contact_type74_fail())
    return_pc = read(sp, 4) & 0xFFFFFF
    if arm == 'direct':
        return AtomicPlan(86, 6, fail_writes,
                          {'a7': sp + 4, 'pc': return_pc, 'sr': _logic_sr(sr, 0, 1)},
                          0x1AE6BA)

    delta, previous, distance, borrowed = (facts[key] for key in ('delta', 'previous', 'distance', 'borrowed'))
    residue = _sub_sr(sr, previous, delta, 2)
    if borrowed:
        residue = _sub_sr(residue, 0, facts['difference'], 2)
    route_cycles, route_instructions = (52, 4) if facts['selector'] else (26, 2)
    player_x = read(0xFF7E02, 2)
    d0 = (registers['d0'] & 0xFFFF0000) | player_x
    d2_delta = (registers['d2'] & 0xFFFF0000) | delta
    d7 = (registers['d7'] & 0xFFFF0000) | distance

    if arm == 'guard_fail':
        base_cycles, base_instructions = (102, 10) if borrowed else (100, 9)
        return AtomicPlan(route_cycles + base_cycles + 36, route_instructions + base_instructions + 2,
                          fail_writes,
                          {'d0': d0, 'd2': d2_delta, 'd7': d7, 'a7': sp + 4, 'pc': return_pc,
                           'sr': _cmp_sr(residue, distance, 0xA, 2)},
                          0x1AE6BA)

    # guard_pass: publish the motion word, then walk the window/kind/state gate.
    pass_writes = tuple(game.contact_type74_pass(delta))
    base_cycles, base_instructions = (104, 10) if borrowed else (102, 9)
    cycles = route_cycles + base_cycles + 16   # + the local FF7DFC MOVE.W
    instructions = route_instructions + base_instructions + 1
    stage_sr = _logic_sr(residue, delta, 2)

    stage, target_facts = game.contact_type74_target(read, record, player_x)
    record_x, upper = target_facts['record_x'], target_facts['upper']
    stage_sr = _logic_sr(stage_sr, record_x, 2)              # move.w record+2,d2
    stage_sr = _add_sr(stage_sr, record_x, 0x10, 2)           # addi.w #$10,d2
    cycles += 20; instructions += 2
    d2_upper = (registers['d2'] & 0xFFFF0000) | upper
    stage_sr = _cmp_sr(stage_sr, player_x, upper, 2)          # cmp.w d2,d0
    if stage == 'window_upper':
        return AtomicPlan(cycles + 30, instructions + 3, pass_writes,
                          {'d0': d0, 'd2': d2_upper, 'd7': d7, 'a7': sp + 4, 'pc': return_pc,
                           'sr': stage_sr},
                          0x1AFB34)
    cycles += 12; instructions += 2

    lower = target_facts['lower']
    stage_sr = _sub_sr(stage_sr, upper, 0x20, 2)              # subi.w #$20,d2
    d2_lower = (registers['d2'] & 0xFFFF0000) | lower
    stage_sr = _cmp_sr(stage_sr, player_x, lower, 2)          # cmp.w d2,d0
    if stage == 'window_lower':
        return AtomicPlan(cycles + 38, instructions + 4, pass_writes,
                          {'d0': d0, 'd2': d2_lower, 'd7': d7, 'a7': sp + 4, 'pc': return_pc,
                           'sr': stage_sr},
                          0x1AFB34)
    cycles += 20; instructions += 3

    kind = target_facts['kind']
    stage_sr = _cmp_sr(stage_sr, kind, 0x74, 1)               # cmpi.b #$74,(a1)
    if stage == 'kind_mismatch':
        return AtomicPlan(cycles + 38, instructions + 3, pass_writes,
                          {'d0': d0, 'd2': d2_lower, 'd7': d7, 'a7': sp + 4, 'pc': return_pc,
                           'sr': stage_sr},
                          0x1AFB34)
    cycles += 20; instructions += 2

    gate = target_facts['gate']
    stage_sr = _logic_sr(stage_sr, gate, 1)                   # tst.b fff0d8
    if stage == 'state_gate':
        return AtomicPlan(cycles + 42, instructions + 3, pass_writes,
                          {'d0': d0, 'd2': d2_lower, 'd7': d7, 'a7': sp + 4, 'pc': return_pc,
                           'sr': stage_sr},
                          0x1AFB34)
    cycles += 28; instructions += 2

    state = target_facts['state']
    stage_sr = _logic_sr(stage_sr, state, 2)                  # tst.w ff7e5a
    if stage == 'negative_state':
        return AtomicPlan(cycles + 42, instructions + 3, pass_writes,
                          {'d0': d0, 'd2': d2_lower, 'd7': d7, 'a7': sp + 4, 'pc': return_pc,
                           'sr': stage_sr},
                          0x1AFB34)
    cycles += 28; instructions += 2
    # The re-test 1AFAF2 reads the same word, so it yields identical flags.
    if stage == 'zero_state':
        return AtomicPlan(cycles + 42, instructions + 3, pass_writes,
                          {'d0': d0, 'd2': d2_lower, 'd7': d7, 'a7': sp + 4, 'pc': return_pc,
                           'sr': stage_sr},
                          0x1AFB34)
    cycles += 28; instructions += 2

    # Every gate cleared: retype the trigger to a used kind-0x75 marker and
    # spawn a child from the fixed template into the first free pool slot.
    retype_writes = tuple(game.contact_type74_retype(record))
    stage_sr = _logic_sr(stage_sr, 0, 1)          # clr.b fff0cc
    stage_sr = _logic_sr(stage_sr, 0, 2)          # clr.w fff0b0
    stage_sr = _logic_sr(stage_sr, 0x120A42, 4)   # move.l #$120a42,$a(a1)
    stage_sr = _logic_sr(stage_sr, 0, 1)          # clr.b $36(a1)
    stage_sr = _logic_sr(stage_sr, 0x75, 1)       # move.b #$75,(a1)
    cycles += 92; instructions += 5

    destination, index = game.free_object(read, CONTACT_TYPE74_POOL, CONTACT_TYPE74_POOL_COUNT)
    cycles += 18; instructions += 1               # bsr.w 1AE262
    if destination is None:
        last_kind = read(CONTACT_TYPE74_POOL + (CONTACT_TYPE74_POOL_COUNT - 1) * 66, 1)
        stage_sr = _logic_sr(stage_sr, last_kind, 1)
        # The 1AE262 call's own return address is the only stack scratch a
        # single BSR/RTS pair leaves behind (nothing pushes over it again).
        scan_return = _bytes(sp - 4, 0x1AFB1C, 4)
        return AtomicPlan(cycles + 840 + 10 + 16, instructions + 83 + 1 + 1,
                          (*pass_writes, *retype_writes, *scan_return),
                          {'d0': (registers['d0'] & 0xFFFF0000) | 0xFFFF,
                           'd2': d2_lower, 'd7': d7,
                           'a5': CONTACT_TYPE74_POOL + CONTACT_TYPE74_POOL_COUNT * 66,
                           'a7': sp + 4, 'pc': return_pc, 'sr': stage_sr},
                          0x1AFB34)
    stage_sr = _logic_sr(stage_sr, 0, 1)           # the found slot's own tst.b
    cycles += 54 + 40 * index + 8
    instructions += (5 + 4 * index) + 1

    template = machine.peek_rom(CONTACT_TYPE74_TEMPLATE, 19)
    init_writes = tuple(game.initialize(destination, template))
    stage_sr = _logic_sr(stage_sr, 0, 4)           # 1AE30A's own closing clr.l
    cycles += 30 + 476; instructions += 2 + 27

    x, y = read(record + 2, 2), read(record + 4, 2)
    position_writes = tuple(game.contact_type74_position(destination, x, y))
    stage_sr = _logic_sr(stage_sr, x, 2)
    stage_sr = _logic_sr(stage_sr, y, 2)
    cycles += 40; instructions += 2

    d0_found = (registers['d0'] & 0xFFFF0000) | (0x13 - index)
    # The 1AE30A call's return address overwrites the same stack slot the
    # 1AE262 call's own return address left behind; only this final value
    # of that scratch slot survives.
    call_return = _bytes(sp - 4, 0x1AFB28, 4)
    return AtomicPlan(cycles + 16, instructions + 1,
                      (*pass_writes, *retype_writes, *init_writes, *position_writes, *call_return),
                      {'d0': d0_found, 'd2': d2_lower, 'd7': d7, 'a5': destination,
                       'a6': CONTACT_TYPE74_TEMPLATE + 19, 'a7': sp + 4, 'pc': return_pc,
                       'sr': stage_sr},
                      0x1AFB34)


def begin_contact_family_type74_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE74_ENTRY,
                                    begin_contact_family_type74)


def begin_contact_family_type6e(machine, registers):
    """1AFB36's gate cascade and dual-axis distance guard, both arms owned.

    Reached by six adjacent collection-dispatch kinds (0x6E-0x73) that share
    this one entry.  ``game.contact_type6e_guard`` selects the arm; this
    boundary owns the alias guards, the cost table and the CCR.  Cost table
    (``factcheck``), each row additive to the row above it in source order
    (26/2 route: FFF0BE and FFF0C0 both set; 1/2 borrow: previous < delta;
    166/8 reinit: FFF103 was zero on entry):

        inactive          (FFF0E7 set)                                42 /  3
        negative state    (FF7E5A < 0)                                90 /  6
        direct return     (FFF0BE set, FFF0C0 clear)                 142 / 10
        bit4 inactive     (record+6 bit4 clear)                      144 / 10
        guard fail,  no borrow                                       222 / 17
        guard pass,  no borrow, FFF103 nonzero (immediate tail)      358 / 26
        guard pass,  no borrow, FFF103 zero (reinit tail)            524 / 34

    Every TST/BTST/SUB/NEG/CMP/MOVE/ADDI/CLR along the way sets its own
    flags in source order; ST never touches CCR and the tail's final
    MOVE.B #4,FFF103 is a fixed positive nonzero constant, so every arm
    that reaches it exits with N=Z=V=C=0 and only X survives from whichever
    SUB/ADD last set it (the distance SUB/NEG chain for a fail, the
    Y-delta SUBI/ADDI chain for a pass -- the pass path's own SUB/ADDI
    overwrite whatever the distance chain left, exactly as the pool scan
    overwrites its own predecessor in ``begin_contact_family_type74``).
    """
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type6e record/stack')
    _spans_disjoint([
        ('type6e record', record, 66), ('type6e return', sp, 4),
        ('type6e gate', 0xFFF0E7, 1), ('type6e state', 0xFF7E5A, 2),
        ('type6e flags', 0xFFF0BE, 1), ('type6e mode', 0xFFF0C0, 1),
        ('type6e player x', 0xFF7DF6, 2), ('type6e motion x', 0xFF7DFA, 2),
        ('type6e player y', 0xFF7DF8, 2), ('type6e motion y', 0xFF7DFC, 2),
        ('type6e machine state', 0xFFF103, 1),
        ('type6e tail a', 0xFFF0D7, 1), ('type6e tail b', 0xFFF0D0, 1),
        ('type6e fail tail', 0xFFF0F5, 1),
        ('type6e reinit script', 0xFF7E60, 4), ('type6e reinit stream', 0xFF7E77, 1),
        ('type6e reinit window x', 0xFF7DFE, 2), ('type6e reinit window y', 0xFF7E00, 2),
        ('type6e reinit counter', 0xFFF0B0, 2), ('type6e reinit latch', 0xFFF0CC, 1),
        ('type6e reinit timer', 0xFF7E58, 2),
    ])
    read = lambda address, size: _read(machine, address, size)
    arm, facts = game.contact_type6e_guard(read, record)
    return_pc = read(sp, 4) & 0xFFFFFF
    residue = _logic_sr(sr, facts['gate'], 1)
    if arm == 'inactive':
        return AtomicPlan(42, 3, (), {'a7': sp + 4, 'pc': return_pc, 'sr': residue}, 0x1AFBF2)

    fail_writes = tuple(game.contact_type6e_fail())
    residue = _logic_sr(residue, facts['state'], 2)
    if arm == 'negative':
        return AtomicPlan(90, 6, fail_writes, {'a7': sp + 4, 'pc': return_pc, 'sr': residue}, 0x1AE6BA)

    residue = _logic_sr(residue, facts['selector'], 1)
    if facts['selector']:
        residue = _logic_sr(residue, facts['mode'], 1)
    if arm == 'direct':
        return AtomicPlan(142, 10, fail_writes, {'a7': sp + 4, 'pc': return_pc, 'sr': residue}, 0x1AE6BA)

    residue = _contact_completion_btst(residue, facts['flags'])
    route_cycles, route_instructions = (26, 2) if facts['selector'] else (0, 0)
    if arm == 'bit4_inactive':
        return AtomicPlan(144 + route_cycles, 10 + route_instructions, fail_writes,
                          {'a7': sp + 4, 'pc': return_pc, 'sr': residue}, 0x1AE6BA)

    delta, previous, distance, borrowed = (facts[key] for key in ('delta', 'previous', 'distance', 'borrowed'))
    record_x = read(record + 2, 2)
    residue = _sub_sr(residue, record_x, read(0xFF7DF6, 2), 2)
    residue = _sub_sr(residue, previous, delta, 2)
    if borrowed:
        residue = _sub_sr(residue, 0, facts['difference'], 2)
    residue = _cmp_sr(residue, distance, 0xC, 2)
    borrow_cycles, borrow_instructions = (2, 1) if borrowed else (0, 0)
    if arm == 'guard_fail':
        return AtomicPlan(222 + route_cycles + borrow_cycles, 17 + route_instructions + borrow_instructions,
                          fail_writes,
                          {'d5': (registers['d5'] & 0xFFFF0000) | delta,
                           'd6': (registers['d6'] & 0xFFFF0000) | distance,
                           'a7': sp + 4, 'pc': return_pc, 'sr': residue},
                          0x1AE6BA)

    # guard_pass: the X delta publishes as-is; the Y delta always recomputes.
    pass_writes, reinit = game.contact_type6e_pass(read, record, delta)
    pass_writes = tuple(pass_writes)
    record_y, player_y = read(record + 4, 2), read(0xFF7DF8, 2)
    y_partial = (record_y - player_y) & 0xFFFF
    y_delta = (y_partial + 0x10) & 0xFFFF
    residue = _logic_sr(residue, delta, 2)          # move.w d5,$ff7dfa.l
    residue = _logic_sr(residue, record_y, 2)        # move.w $4(a1),d5
    residue = _sub_sr(residue, record_y, player_y, 2)  # sub.w $ff7df8.l,d5
    residue = _add_sr(residue, y_partial, 0x10, 2)     # addi.w #$10,d5
    residue = _logic_sr(residue, y_delta, 2)           # move.w d5,$ff7dfc.l
    residue = _logic_sr(residue, read(0xFFF103, 1), 1)  # tst.b $fff103.l
    reinit_cycles, reinit_instructions = (166, 8) if reinit else (0, 0)
    # ST never touches CCR; the tail's own MOVE.B #4,$fff103.l is a fixed
    # positive nonzero byte, so every guard-pass arm exits N=Z=V=C=0 with
    # only X surviving from the Y-delta SUBI/ADDI chain just above.
    residue = _logic_sr(residue, 4, 1)
    return AtomicPlan(358 + route_cycles + borrow_cycles + reinit_cycles,
                      26 + route_instructions + borrow_instructions + reinit_instructions,
                      pass_writes,
                      {'d5': (registers['d5'] & 0xFFFF0000) | y_delta,
                       'd6': (registers['d6'] & 0xFFFF0000) | distance,
                       'a7': sp + 4, 'pc': return_pc, 'sr': residue},
                      0x1AFBF2)


def begin_contact_family_type6e_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE6E_ENTRY,
                                    begin_contact_family_type6e)


def begin_contact_family_type44(machine, registers):
    """1AEF12's no-sound counter clamp and counted replacement tail."""
    record, sp, sr = (registers[key] for key in ('a1', 'a7', 'sr'))
    if (record | sp) & 1:
        raise UnsupportedCandidate('unaligned type44 record/stack')
    _spans_disjoint([('type44 record', record, 66),
                     ('type44 frame', sp - 4, 8),
                     ('type44 sound', 0xFFF57D, 1),
                     ('type44 finish gate', 0xFF7E21, 1),
                     ('type44 counter', 0xFFEFFA, 2)])
    read = lambda address, size: _read(machine, address, size)
    if read(0xFFF57D, 1):
        raise UnsupportedCandidate('type44 requires command98 sound seam')
    candidate = (3 - read(0xFF7E21, 1) + read(0xFFEFFA, 1)) & 0xff
    limit = read(0xFFEFFB, 1)
    value = candidate if candidate < limit else limit
    # TST/BEQ, arithmetic, compare, optional clamp move, byte store, BRA.
    prefix = AtomicPlan(118 if candidate < limit else 132,
                        9 if candidate < limit else 10,
                        _bytes(0xFFEFFA, value, 1),
                        {**registers,
                         'd0': (registers['d0'] & 0xffffff00) | value,
                         'sr': _logic_sr(sr, value, 1)},
                        0x1AEF58)
    tail = replace_object(dispatch_plan_view(machine, prefix), prefix.registers,
                          increment_total=True,
                          extra_spans=(('type44 counter', 0xFFEFFA, 2),))
    final = dict(prefix.registers); final.update(tail.registers)
    return AtomicPlan(prefix.cycles + tail.cycles,
                      prefix.instructions + tail.instructions,
                      tuple(dict((*prefix.writes, *tail.writes)).items()), final,
                      tail.last_pc, prefix.direct_calls + tail.direct_calls)


def begin_contact_family_type44_dispatch(machine, registers, dispatch):
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_FAMILY_TYPE44_ENTRY,
                                    begin_contact_family_type44)


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


def begin_contact_collection_relocation_dispatch(machine, registers, dispatch):
    """Compose Type20's callback JSR with the existing secondary relocation."""
    return _contact_family_dispatch(machine, registers, dispatch,
                                    CONTACT_COLLECTION_RELOCATION_ENTRY,
                                    relocate_collection)


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
