"""The trigger evaluator's own action table (ROM 0046D0, fifteen entries; `docs/gods/blockers/
2026-09-16-00462C-firing.md`'s Split, part 3): one module per admissible handler, named for what it
does, not for its table index.  Three of fifteen entries collapse to the same bare `rts` at `00475C`
(no semantics needed).  Handlers that call an unrecovered routine, or that touch the level grid /
solid tables in ways not yet modelled, stay out of this module until their own callees are recovered.

Every handler here is reached by the evaluator's own firing tail through a tail JUMP (`jmp (a5)`,
0046CE) with no frame of its own: its own `rts` returns straight to the evaluator's own caller, the
same "opaque tail" shape `0048B4`'s own jump into `0047DA` already proved -- gating a handler's own
entry PC needs no seam at all, since nothing is ceded to the platform.
"""
from __future__ import annotations

from . import pickups
from .conditions import ELAPSED


# --- 004ACA: clear a matched pickup group's own active-id word ------------------------------------
#
# The pickup groups' own three "active id" words (`pickups.py`'s own `GROUP_TABLES`, already read
# there): a caller-supplied record's own word at `+0x12` is compared against each of the three in
# turn, and whichever one matches is cleared to 0.  A miss against all three is a no-op.
def clear_matched_group(read, argument):
    """004ACA: the (at most one) matched group active-id word to clear, or None on a miss."""
    for address in pickups.GROUP_TABLES:
        if (read(address, 2) & 0xFFFF) == (argument & 0xFFFF):
            return address
    return None


# --- 0048E4: unconditionally clear the elapsed-seconds counter -------------------------------------
#
# The whole body is `clr.l $f2aa.w; rts` -- no branch, no caller input at all; the SAME longword
# `conditions.py`'s own kinds 9/10 read as `ELAPSED` (the elapsed-seconds counter `00470C` consults).
def reset_elapsed(_read):
    """0048E4: always clears `ELAPSED` to 0."""
    return ELAPSED
