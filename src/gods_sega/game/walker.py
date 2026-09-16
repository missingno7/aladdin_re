"""The line walker: Gods' Bresenham stepper with a persistent record, in two ROM copies.

A walker record (18 bytes, live in the owner's object) holds where a
straight-line walk stands: the phase (which of four loop bodies the walk
is in: toward +x or −x, shallow or steep), the current position, the sign
of the minor-axis step, the line's |dx| and |dy|, the Bresenham error
accumulator and the walk's own step counter.  A call gives the walker a
budget of steps (the shared word ``FFF1FE``, set by the caller just
before) and the walker takes steps until the budget is spent, then writes
its state back and returns; the next call resumes from the record.  This
is game state — the solids' movement along their waypoints and the
projectiles' flight persist in these records across ticks — not a
recovery mechanism.

Two copies of the stepper exist in the ROM with one difference in how a
walk ends.  The **object copy** (``00FFF0``/``010002``, used by the
animation step ``00FE08`` for the solids, whose record is at ``+6`` of the
solid's live record): the loop is a ``dbra`` on the step counter, so a walk
whose major axis is exhausted stops inside the call, and the counter goes
negative — the completion the caller tests (``tst.w d7; bpl``) to load the
next waypoint.  The **projectile copy** (``0093D2``/``0093E4``, used by
``0091BC`` on the 20-entry pool at ``FFE19E``, 22 bytes each, the walker
record first): the loop is unconditional, the counter is decremented once
per call after the budget is spent, and completion is the driver's
(``009210``), not the walker's.  The projectile copy also re-arms its
"toward −x, steep" body as the "toward +x, steep" body (``0094BC`` stores
``009436``): a walk that ran that body once continues in the other
direction on its next call.  That is what the ROM does; it is kept.

Pure functions; no cycles, CCR, stack or registers.  A phase is named by
its body's address in the copy it belongs to, and by what it does.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

BUDGET = 0xFFF1FE                                     # word: steps the current call may take, set by the caller
RECORD_SIZE = 18

# Phases: (toward, slope).  The body addresses are the continuation the record stores.
OBJECT_BODIES = {('+x', 'shallow'): 0x010022, ('+x', 'steep'): 0x010052, ('-x', 'shallow'): 0x010098, ('-x', 'steep'): 0x0100C8}
PROJECTILE_BODIES = {('+x', 'shallow'): 0x009408, ('+x', 'steep'): 0x009436, ('-x', 'shallow'): 0x00947A, ('-x', 'steep'): 0x0094A8}
# What each body re-arms the record with when it yields (the projectile copy's -x steep body re-arms +x steep).
OBJECT_REARM = {phase: address for phase, address in OBJECT_BODIES.items()}
PROJECTILE_REARM = {('+x', 'shallow'): 0x009408, ('+x', 'steep'): 0x009436, ('-x', 'shallow'): 0x00947A, ('-x', 'steep'): 0x009436}
COPIES = {'object': (OBJECT_BODIES, OBJECT_REARM, True), 'projectile': (PROJECTILE_BODIES, PROJECTILE_REARM, False)}


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


@dataclass(frozen=True)
class Walk:
    """A walker record's content.  Words are kept as the 16-bit values the record holds."""
    phase: tuple                 # (toward, slope)
    x: int                       # current position (the record's D4 word)
    y: int                       # (D6)
    y_sign: int                  # +1 / -1 as a word (D0): the minor-axis step for shallow walks, the y step for steep ones
    dx: int                      # |dx| (D2)
    dy: int                      # |dy| (D3)
    error: int                   # the Bresenham accumulator (D5)
    counter: int                 # the walk's own step counter (D7): the major axis length, counted down by the object copy

    def as_words(self):
        return (self.x, self.y, self.y_sign, self.dx, self.dy, self.error, self.counter)


def phase_of(copy, continuation):
    """The phase a stored continuation address names in ``copy``, or None if it is not one of the four bodies."""
    bodies = COPIES[copy][0]
    for phase, address in bodies.items():
        if address == continuation:
            return phase
    return None


def load(read, record, copy):
    """The walk a record holds, or None when its continuation is not one of the copy's bodies."""
    phase = phase_of(copy, read(record, 4) & 0xFFFFFF)
    if phase is None:
        return None
    words = [read(record + 4 + 2 * index, 2) for index in range(7)]
    return Walk(phase, *words)


def start(x0, y0, x1, y1):
    """The cold start (``010002`` / ``0093E4``): the walk from (x0, y0) toward (x1, y1), before any step.

    Returns the walk as the code sets it up: the phase from the sign of the
    x span and the shallow/steep comparison, |dx|, |dy|, the y step sign,
    the accumulator at half the major axis, the counter at the major axis.
    """
    x0, y0, x1, y1 = (v & 0xFFFF for v in (x0, y0, x1, y1))
    toward = '-x' if _signed_word(x0) > _signed_word(x1) else '+x'      # cmp.w d2,d0; bgt: the start lies right of the end
    dx = (x0 - x1) & 0xFFFF if toward == '-x' else (x1 - x0) & 0xFFFF
    dy = (y1 - y0) & 0xFFFF
    y_sign = 1
    if dy & 0x8000:                                                         # sub.w d1,d3; bpl / neg.w; moveq #-1
        dy = (-dy) & 0xFFFF
        y_sign = 0xFFFF
    slope = 'steep' if dx < dy else 'shallow'                               # cmp.w d3,d2; bcs (unsigned)
    major = dx if slope == 'shallow' else dy
    return Walk((toward, slope), x0, y0, y_sign, dx, dy, major >> 1, major)


def run(walk, budget, copy):
    """Steps the walk with ``budget`` steps to spend, the way the copy's loop body does.

    Returns the walk as the record is re-armed (phase per the copy's
    re-arm table, counter as saved), the budget left (0 when spent), the
    number of steps taken, and whether the object copy's counter ran out
    (the walk completed inside this call).  The budget word is decremented
    before the exit test, so a call with budget 0 takes 65,535 steps of
    the object copy at most — the caller never does that; it is not
    modelled and raises.
    """
    bodies, rearm, counted = COPIES[copy]
    if budget == 0:
        raise ValueError('a zero budget wraps the budget word: not a walk the game makes')
    toward, slope = walk.phase
    x, y, y_sign, dx, dy, error, counter = walk.as_words()
    x_step = 1 if toward == '+x' else 0xFFFF
    steps, completed = 0, False
    while True:
        if slope == 'shallow':
            error = (error - dy) & 0xFFFF
            if error & 0x8000:
                error = (error + dx) & 0xFFFF
                y = (y + y_sign) & 0xFFFF
            x = (x + x_step) & 0xFFFF
        else:
            y = (y + y_sign) & 0xFFFF
            error = (error - dx) & 0xFFFF
            if error & 0x8000:
                error = (error + dy) & 0xFFFF
                x = (x + x_step) & 0xFFFF
        steps += 1
        budget = (budget - 1) & 0xFFFF
        if budget == 0:
            break
        if counted:
            counter = (counter - 1) & 0xFFFF                                # dbra: count down, stop on -1
            if counter == 0xFFFF:
                completed = True
                break
    counter = (counter - 1) & 0xFFFF                                        # subq.w #1,d7 after either exit
    return replace(walk, phase=phase_of(copy, rearm[walk.phase]) or walk.phase, x=x, y=y, error=error,
                   counter=counter), budget, steps, completed


def stores(walk, record, copy):
    """The record bytes a yield writes: the re-armed continuation and the seven words, as {address: (value, size)}."""
    bodies = COPIES[copy][0]
    words = walk.as_words()
    out = {record: (bodies[walk.phase], 4)}
    for index, word in enumerate(words):
        out[record + 4 + 2 * index] = (word, 2)
    return out
