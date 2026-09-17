"""The message display gate and string copy (ROM 007986/0079DC).

Shared utilities, not trigger-specific: `007986` is called from many sites
(the trigger evaluator's own firing arm, `0046AA`, is only one of them) to
ask whether a message of a given priority may claim the display buffer, and
`0079DC` is the plain byte copy that follows when it may.  Pure functions of
`read(address, size)`; no cycles, CCR, stack or registers.
"""
from __future__ import annotations

MESSAGE_BOUND = 0xFFFFF164        # word: the currently displayed message's own priority (0 = none)
MESSAGE_PENDING = 0xFFFFF16E      # word: cleared alongside MESSAGE_BOUND when the caller's own d7 is negative
MESSAGE_BUFFER = 0xFFFFF166       # long: the primary destination buffer's own pointer
MESSAGE_BUFFER_ALT = 0xFFFFF16A   # long: the alternate buffer, used when the primary is already occupied


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def message_gate(read, d7):
    """007986: gate a message of priority ``d7`` against the display buffer.

    A negative ``d7`` is negated first (and clears MESSAGE_BOUND/PENDING,
    the "start fresh" arm).  The primary buffer (MESSAGE_BUFFER) already
    empty is the common ``'ready'`` arm (A1 left at that buffer).  A buffer
    already holding a message compares ``d7`` against the stored
    MESSAGE_BOUND: a sufficient priority (bound <= the stored one) is
    ALSO ``'ready'``, but through MESSAGE_BUFFER_ALT instead; either way
    MESSAGE_BOUND is (re)stored and D0 is 0.  An insufficient priority is
    the real ``'blocked'`` arm (D0 -1, no stores).  A stored bound of
    exactly 0 while the buffer is still occupied skips the compare
    entirely (the ROM's own beq) -- real code, but a state no recording
    has ever produced: the ``'unrecovered'`` arm.
    """
    negated = _signed_word(d7) < 0
    bound = ((-d7) if negated else d7) & 0xFFFF
    stores = {}
    if negated:
        stores[MESSAGE_BOUND & 0xFFFFFF] = (0, 2)
        stores[MESSAGE_PENDING & 0xFFFFFF] = (0, 2)
    primary = read(MESSAGE_BUFFER, 4) & 0xFFFFFFFF
    if read(primary & 0xFFFFFF, 1) == 0:
        buffer = primary
    else:
        stored = read(MESSAGE_BOUND, 2)
        if stored == 0:
            return {'arm': 'unrecovered', 'negated': negated, 'bound': bound, 'stores': stores}
        if _signed_word(bound) > _signed_word(stored):
            return {'arm': 'blocked', 'negated': negated, 'bound': bound, 'stored': stored, 'stores': stores}
        buffer = read(MESSAGE_BUFFER_ALT, 4) & 0xFFFFFFFF
    stores[MESSAGE_BOUND & 0xFFFFFF] = (bound, 2)
    return {'arm': 'ready', 'negated': negated, 'bound': bound, 'buffer': buffer, 'stores': stores, 'd0': 0}


def copy_message(read, source):
    """0079DC: copy bytes from ``source`` to the destination the caller supplies (A1, from
    ``message_gate``'s own ``'buffer'``) until a NUL, which is itself copied.  Returns the copied
    bytes (NUL included) and the stores; the caller's own A1/A2 both end one past the NUL.
    """
    copied = bytearray()
    offset = 0
    while True:
        value = read((source + offset) & 0xFFFFFF, 1) & 0xFF
        copied.append(value)
        offset += 1
        if value == 0:
            break
    return {'length': len(copied), 'bytes': bytes(copied)}
