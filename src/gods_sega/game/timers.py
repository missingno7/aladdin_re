"""The rate-gated countdown check (ROM 010332-0103xx), called 412 times / 600 frames from ``0101FA``.

Called with a control byte (A3) and a per-slot countdown word (A5), both
passed by the caller (they vary call to call, not fixed globals): a control
byte of zero disables the slot entirely (the ``'idle'`` arm, no effect); a
nonzero control decrements the countdown, and while it stays nonzero the
call is done (the ``'waiting'`` arm, the decremented word its only durable
effect).  Reaching zero (the ``'trigger'`` arm) calls one of two unrecovered
routines (``01158C``/``0115D4``, chosen by a further byte and a position
compare) to do the actual work the countdown was gating; what that work is
is not known, and the arm is declined -- not for lack of a recording (both
the routines it calls run in every recording), but because the boundary
cannot reproduce a call into code that is not itself recovered.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

RATE_ENABLE = 0x13     # control byte (A3): zero disables the check for this call
COUNTDOWN = 0xC         # countdown word (A5): decremented once per enabled call


def countdown_check(read, control, countdown):
    """What ``010332`` does for one call with control struct ``control`` (A3) and countdown struct ``countdown`` (A5).

    Returns the arm (``'idle'``, ``'waiting'`` or ``'trigger'``), the
    countdown's value before and after (``'idle'`` leaves it untouched:
    ``before == after``), and the durable stores.
    """
    if read(control + RATE_ENABLE, 1) == 0:
        return {'arm': 'idle', 'before': None, 'after': None, 'stores': {}}
    before = read(countdown + COUNTDOWN, 2)
    after = (before - 1) & 0xFFFF
    if after != 0:
        return {'arm': 'waiting', 'before': before, 'after': after, 'stores': {countdown + COUNTDOWN: (after, 2)}}
    return {'arm': 'trigger', 'before': before, 'after': after, 'stores': {}}
