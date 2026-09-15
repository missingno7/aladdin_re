"""Derive the repeated collection sound-frame facts from the verified USA ROM.

This recognizes one already-qualified instruction sequence, not arbitrary 68000
code. No disassembler, native rebuild or generated execution layer is required.
The independent original-machine witnesses remain the correctness oracle.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aladdin_sega.boundary import COLLECTION_ROUTES, ROM_SHA256


def sound_site(rom: bytes, resume: int) -> dict:
    """Reject any difference in the concrete TST/BEQ/MOVEM/PEA/JSR sound ABI."""
    start = resume - 28
    span = rom[start:resume + 6]
    expected = bytes.fromhex(
        '4a3900fff57d671a48e7c0c24878')
    if (len(span) != 34 or span[:14] != expected
            or span[16:] != bytes.fromhex('4eb9001e58b84eb9001e589a588f4cdf4303')):
        raise ValueError(f'Unsupported collection sound instructions at {start:06X}')
    command = int.from_bytes(span[14:16], 'big', signed=True)
    # Original M68000 timings for these fixed addressing modes:
    # TST abs.l=16, BEQ not taken=8/taken=10, MOVEM predec 5 longs=48,
    # PEA abs.w=16, JSR abs.l=20, ADDQ An=8, MOVEM postinc 5 longs=52.
    return {'test_pc': start, 'first_call': resume - 12,
            'second_call': resume - 6, 'resume': resume, 'suffix': resume + 6,
            'command': command, 'targets': [0x1E58B8, 0x1E589A],
            'saved_registers': ['d0', 'd1', 'a0', 'a1', 'a6'],
            'frame_bytes_at_callee': 28,
            'enabled_prefix': {'cycles': 16 + 8 + 48 + 16 + 20, 'instructions': 5},
            'disabled_prefix': {'cycles': 16 + 10, 'instructions': 2},
            'restore': {'cycles': 8 + 52, 'instructions': 2}}


def collection_sites(rom: bytes) -> dict:
    if hashlib.sha256(rom).hexdigest() != ROM_SHA256:
        raise ValueError('Expected the verified USA ROM')
    return {f'{entry:06X}': {'kind': route[0], **sound_site(rom, route[1])}
            for entry, route in COLLECTION_ROUTES.items()}


if __name__ == '__main__':
    print(json.dumps(collection_sites(Path('assets/Aladdin (USA).md').read_bytes()), indent=2))
