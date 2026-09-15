"""Experimental exact outer adapter for 1AF4C2/1AF4C6, not a new runtime.

Installed only into disposable source copies by ownership_experiment.py.
The same synchronous 0.7 caller and original sound span remain in charge.
"""
from aladdin_sega.recovered import (
    AtomicPlan, UnsupportedCandidate, _read, _address, _spans_disjoint, _bytes, _logic_sr,
    REPLACE_LAST_PC,
)
from aladdin_sega import ownership_semantics as game


def replace_object(machine, registers, *, increment_total=False, extra_spans=()):
    record, sp, sr = (registers[name] for name in ("a1", "a7", "sr"))
    read = lambda address, size: _read(machine, address, size)
    return_pc = read(sp, 4)
    linked = read(record + 62, 4)
    if (record | sp) & 1:
        raise UnsupportedCandidate("unaligned object record or stack")
    spans = [("current record", record, 66),
             ("replacement stack", sp - (18 if linked else 14), 22 if linked else 18),
             *extra_spans]
    if linked:
        spans.append(("linked record", linked, 50))
    lengths = []
    for item in ((record, linked) if linked else (record,)):
        pointer = read(item + 42, 4)
        length = read(item + 41, 1) + 1 if pointer else 0
        lengths.append(length)
        if pointer:
            spans.append(("object buffer", _address(pointer, length), length))
    writes = []
    if increment_total:
        total = read(0xFFF14E, 2) + 15
        sr = (sr & ~0x10) | (0x10 if total > 65535 else 0)
        spans.append(("object total", 0xFFF14E, 2))
        writes.extend(_bytes(0xFFF14E, total, 2))
    _spans_disjoint(spans)
    writes.extend(game.clear_pair(read, record))
    writes.extend(game.initialize(record, machine.peek_rom(0x1B7ABC, 19)))
    # Final residue only. No internal guest call, saved-register restoration,
    # pair AtomicPlan, or intermediate CCR/PC/register dictionary is built.
    residue = [(sp - 4, 0x1AF4D6, 4)]
    if linked:
        residue += [(sp - 8, record, 4), (sp - 12, 0x1ABE86, 4),
                    (sp - 16, registers["a6"], 4), (sp - 18, registers["d0"], 2)]
    else:
        residue += [(sp - 8, 0x1ABE74, 4), (sp - 12, registers["a6"], 4),
                    (sp - 14, registers["d0"], 2)]
    for address, value, width in residue:
        writes.extend(_bytes(address, value, width))
    # No callback can observe intermediate effects of an ADMITTED RAM-only
    # plan. Last-writer wins is local to this guarded region, not a bus rule.
    writes = tuple(dict(writes).items())
    cycles = 876 if linked else 712
    instructions = 58 if linked else 45
    cycles += sum(82 + 22 * length for length in lengths if length) + 58 * increment_total
    instructions += sum(5 + 2 * length for length in lengths if length) + 3 * increment_total
    return AtomicPlan(cycles, instructions, writes,
                      {"a5": record, "a6": 0x1B7ACF, "a7": sp + 4,
                       "pc": return_pc & 0xFFFFFF, "sr": _logic_sr(sr, 0, 4)},
                      REPLACE_LAST_PC, direct_calls=3 + bool(linked) + int(increment_total))
