"""Derive four fixed spawn allocator facts from verified USA-ROM bytes.

This recognises measured 68000 sequences only.  It is a development checker,
not a runtime recovery dependency or a generic disassembler.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from aladdin_sega.boundary import ROM_SHA256, SPAWN_REGION_ENTRIES, SPAWN_REGION_LAST_PC


SELECTORS = (0x1AE262, 0x1AE27A, 0x1AE292, 0x1AE2AA)
SITES = (0x1B524E, 0x1B5256, 0x1B525E, 0x1B5266)
TAIL = 0x1B526C

# Measured costs for these fixed instruction shapes.  The checker derives the
# count-dependent formula only after the corresponding bytes are recognised.
_SELECTOR_FREE = (54, 5)
_SELECTOR_OCCUPIED = (40, 4)
_SELECTOR_EXHAUSTED_ADJUSTMENT = (-14, -2)
_TAIL = (644, 39)
_BSR, _BNE_NOT_TAKEN, _BNE_TAKEN, _BRA, _RTS = (18, 1), (8, 1), (10, 1), (10, 1), (16, 1)
_TAIL_BYTES = bytes.fromhex(
    '6100909c3b4200321b430034303900fff150d07900ff7db03b400002'
    '303900fff152d07900ff7db23b40000442322000b1004e75')


@dataclass(frozen=True)
class AllocatorArmFacts:
    entry: int
    selector: int
    start: int
    count: int
    direction: int
    stride: int
    return_target: int
    exhausted_a5: int
    free_cycles_base: int
    free_cycles_per_occupied: int
    free_instructions_base: int
    free_instructions_per_occupied: int
    exhausted_cycles: int
    exhausted_instructions: int
    free_fixed_cycles: int
    free_fixed_instructions: int
    exhausted_fixed_cycles: int
    exhausted_fixed_instructions: int


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], 'big')


def _s16(data: bytes, offset: int) -> int:
    value = _u16(data, offset)
    return value - 0x10000 if value & 0x8000 else value


def _s8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _selector(rom: bytes, pc: int) -> dict:
    """Accept exactly LEA/MOVE/TST/BEQ/ADDA-or-SUBA/DBRA/RTS."""
    code = rom[pc:pc + 24]
    if len(code) != 24 or code[:2] != b'\x4b\xf9' or code[6:8] != b'\x30\x3c' \
            or code[10:14] != b'\x4a\x15\x67\x08' or code[18:22] != b'\x51\xc8\xff\xf6' \
            or code[22:] != b'\x4e\x75':
        raise ValueError(f'Unsupported allocator selector instructions at {pc:06X}')
    op = code[14:16]
    if op == b'\xda\xfc':
        direction = 1
    elif op == b'\x9a\xfc':
        direction = -1
    else:
        raise ValueError(f'Unsupported allocator direction opcode at {pc:06X}')
    count, stride = _u16(code, 8) + 1, _u16(code, 16)
    start = int.from_bytes(code[2:6], 'big')
    if not count or not stride or not 0xFF0000 <= start <= 0xFFFFFF:
        raise ValueError(f'Unsupported allocator operands at {pc:06X}')
    return {'pc': pc, 'start': start, 'count': count, 'direction': direction,
            'stride': stride, 'exhausted_a5': start + direction * stride * count,
            'free_cycles_base': _SELECTOR_FREE[0],
            'free_cycles_per_occupied': _SELECTOR_OCCUPIED[0],
            'free_instructions_base': _SELECTOR_FREE[1],
            'free_instructions_per_occupied': _SELECTOR_OCCUPIED[1],
            'exhausted_cycles': (_SELECTOR_OCCUPIED[0] * count + _SELECTOR_FREE[0]
                                 + _SELECTOR_EXHAUSTED_ADJUSTMENT[0]),
            'exhausted_instructions': (_SELECTOR_OCCUPIED[1] * count + _SELECTOR_FREE[1]
                                       + _SELECTOR_EXHAUSTED_ADJUSTMENT[1])}


def _site(rom: bytes, entry: int, selectors: dict[int, dict]) -> AllocatorArmFacts:
    code = rom[entry:entry + 8]
    if len(code) != 8 or code[:2] != b'\x61\x00' or code[4] != 0x66:
        raise ValueError(f'Unsupported spawn allocator call instructions at {entry:06X}')
    # 68000 word-displacement BSR is relative to the extension word address.
    selector = entry + 2 + _s16(code, 2)
    if selector not in selectors:
        raise ValueError(f'Unsupported spawn allocator callee at {entry:06X}: {selector:06X}')
    bne_target = entry + 6 + _s8(code[5])
    if bne_target != SPAWN_REGION_LAST_PC or rom[bne_target:bne_target + 2] != b'\x4e\x75':
        raise ValueError(f'Unsupported spawn allocator failure return at {entry:06X}')
    branch = (0, 0)
    fallthrough = entry + 6
    if fallthrough != TAIL:
        if rom[fallthrough] != 0x60 or fallthrough + 2 + _s8(rom[fallthrough + 1]) != TAIL:
            raise ValueError(f'Unsupported spawn allocator success branch at {entry:06X}')
        branch = _BRA
    selector_facts = selectors[selector]
    return AllocatorArmFacts(
        entry=entry, selector=selector, start=selector_facts['start'], count=selector_facts['count'],
        direction=selector_facts['direction'], stride=selector_facts['stride'], return_target=entry + 4,
        exhausted_a5=selector_facts['exhausted_a5'],
        free_cycles_base=selector_facts['free_cycles_base'],
        free_cycles_per_occupied=selector_facts['free_cycles_per_occupied'],
        free_instructions_base=selector_facts['free_instructions_base'],
        free_instructions_per_occupied=selector_facts['free_instructions_per_occupied'],
        exhausted_cycles=selector_facts['exhausted_cycles'],
        exhausted_instructions=selector_facts['exhausted_instructions'],
        free_fixed_cycles=_TAIL[0] + _BSR[0] + _BNE_NOT_TAKEN[0] + branch[0],
        free_fixed_instructions=_TAIL[1] + _BSR[1] + _BNE_NOT_TAKEN[1] + branch[1],
        exhausted_fixed_cycles=_BSR[0] + _BNE_TAKEN[0] + _RTS[0],
        exhausted_fixed_instructions=_BSR[1] + _BNE_TAKEN[1] + _RTS[1])


def decode_allocator_arms(rom: bytes) -> dict[int, AllocatorArmFacts]:
    """Decode a supplied byte image after validating its exact shared tail."""
    if rom[TAIL:TAIL + len(_TAIL_BYTES)] != _TAIL_BYTES:
        raise ValueError(f'Unsupported shared spawn tail at {TAIL:06X}')
    selectors = {pc: _selector(rom, pc) for pc in SELECTORS}
    return {entry: _site(rom, entry, selectors) for entry in SITES}


def allocator_arms(rom: bytes) -> dict[int, AllocatorArmFacts]:
    if hashlib.sha256(rom).hexdigest() != ROM_SHA256:
        raise ValueError('Expected the verified USA ROM')
    return decode_allocator_arms(rom)


def check_boundary_arms(arms: dict[int, AllocatorArmFacts]) -> None:
    """Reject handwritten boundary constants that disagree with ROM facts."""
    from aladdin_sega.boundary import _SPAWN_REGION_ARMS
    if tuple(arms) != SPAWN_REGION_ENTRIES or tuple(_SPAWN_REGION_ARMS) != SPAWN_REGION_ENTRIES:
        raise ValueError('Spawn allocator entry set differs from verified ROM')
    for entry, facts in arms.items():
        expected = (facts.start, facts.count, facts.direction, facts.exhausted_a5,
                    facts.free_fixed_cycles, facts.free_fixed_instructions,
                    facts.exhausted_fixed_cycles, facts.exhausted_fixed_instructions,
                    facts.return_target)
        if _SPAWN_REGION_ARMS[entry] != expected:
            raise ValueError(f'Boundary arm facts differ from ROM at {entry:06X}')


def report(rom: bytes) -> dict[str, object]:
    arms = allocator_arms(rom)
    check_boundary_arms(arms)
    return {'status': 'PASS', 'scope': 'four fixed allocator and spawn-call sequences',
            'arms': {f'{entry:06X}': asdict(facts) for entry, facts in arms.items()},
            'manual_timing_inputs': {'selector_free': _SELECTOR_FREE,
                                     'selector_occupied': _SELECTOR_OCCUPIED,
                                     'selector_exhausted_adjustment': _SELECTOR_EXHAUSTED_ADJUSTMENT,
                                     'tail': _TAIL, 'bsr': _BSR,
                                     'bne_not_taken': _BNE_NOT_TAKEN,
                                     'bne_taken': _BNE_TAKEN, 'bra': _BRA, 'rts': _RTS}}


if __name__ == '__main__':
    print(json.dumps(report(Path('assets/Aladdin (USA).md').read_bytes()), indent=2))
