"""The admission contract of recovered code and the seam: pause, let the machine run a platform operation, resume.

A recovered region is admitted as one ``AtomicPlan`` through
``Machine.atomic``: the RAM bytes, the register file at the exit and the
original's cost along the executed path.  When a region contains a bounded
platform operation (a sound request, a VDP upload) the recovered code stops
at its first instruction with everything the operation reads in place, the
original machine runs it, and the recovered code resumes: that is a
``Seam``, and ``run_seam`` is the mechanism that pauses and resumes.  This
module holds no game fact: which regions exist, where they resume, what
their frames look like and what the suffix means belong to the game's
``boundary``; how the game counts and reports belongs to its dispatcher.

Aladdin proved the shape on its sound requests (a JSR to a native helper,
the seam resuming after it) and its platform tails (a run of platform
calls bridged to the caller's own RTS); Gods reproduced it on an inline
VDP upload.  The runner is theirs in common.
"""
from __future__ import annotations

from dataclasses import dataclass


class UnsupportedCandidate(RuntimeError):
    """A supported refusal: the region's state is outside what the recovered code has been verified on."""


@dataclass(frozen=True)
class AtomicPlan:
    """One admitted operation: what ``Machine.atomic`` needs and nothing else."""
    cycles: int
    instructions: int
    writes: tuple[tuple[int, int], ...]
    registers: dict[str, int]
    last_pc: int
    direct_calls: int = 0


@dataclass(frozen=True)
class Seam:
    """A recovered prefix, a bounded platform operation the machine runs, a recovered suffix.

    ``prefix`` ends with the PC at the operation's first instruction (a
    callee's entry with its frame pushed, or an inline device block) and
    every register the operation reads in place.  The machine runs from
    there to ``resume_pc``.  The activation's identity at the resume is
    ``stack_basis`` (the expected ``a7``), the ``guards`` (spans of work RAM
    read after the prefix that must be unchanged at the resume: the saved
    frame, a return slot the operation never touches) and ``expect`` (slots
    that must hold a known value at the resume: the return slot of the last
    call the operation itself made).  ``suffix(machine, registers)`` plans
    the rest from the live state at the resume.
    """
    prefix: AtomicPlan
    resume_pc: int
    stack_basis: int
    guards: tuple[tuple[int, int], ...]
    suffix: object
    expect: tuple[tuple[int, int, int], ...] = ()


@dataclass(frozen=True)
class SeamOutcome:
    """What happened after the prefix: ``completed``, ``declined`` (the suffix planner refused),
    ``refused`` (the scheduler would not admit the suffix) or ``deadline`` (the frame's observation
    instant fell inside the platform operation; the original owns the rest of the activation)."""
    status: str
    reason: str | None
    stops: int
    foreign_returns: int


def run_seam(machine, deadline, seam, *, admit, gates):
    """Run one seam whose prefix the caller has already admitted.

    Only ``resume_pc`` is gated while the machine runs the platform
    operation; a stop there with another ``a7`` belongs to another
    activation (an interrupt, a nested call) and is bypassed once.  At the
    activation's own return the guards are compared byte for byte, the
    suffix is planned from the live state and handed to ``admit`` (the
    game's admission: its mutation, its counters).  Whatever happens the
    machine leaves with ``in_seam`` clear and ``gates`` armed again; the
    caller records the outcome and, for a declined or refused suffix, lets
    the original run it from the resume.  A guard that changed is a
    contract violation, not a fallback: it raises.
    """
    guarded = [(address, machine.peek_ram(address & 0xFFFF, size)) for address, size in seam.guards]
    stops = foreign = 0
    machine.in_seam = True
    try:
        machine.gates([seam.resume_pc])
        while machine.run(target=deadline) == 'gate':
            stops += 1
            returned = machine.registers()
            if returned['a7'] != seam.stack_basis:
                foreign += 1
                machine.gate(seam.resume_pc, bypass_once=True)
                continue
            if returned['pc'] != seam.resume_pc or any(
                    machine.peek_ram(address & 0xFFFF, len(expected)) != expected for address, expected in guarded) or any(
                    int.from_bytes(machine.peek_ram(address & 0xFFFF, size), 'big') != value
                    for address, size, value in seam.expect):
                raise ValueError('Seam return/frame mismatch: the activation changed under the platform operation')
            try:
                plan = seam.suffix(machine, returned)
            except UnsupportedCandidate as error:
                return SeamOutcome('declined', f'unsupported domain: {error}', stops, foreign)
            if not admit(plan):
                return SeamOutcome('refused', 'scheduler admission', stops, foreign)
            return SeamOutcome('completed', None, stops, foreign)
        return SeamOutcome('deadline', 'seam deadline', stops, foreign)
    finally:
        machine.in_seam = False
        machine.gates(list(gates))
