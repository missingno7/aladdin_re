"""The trigger conditions (``00470C``): one predicate per kind, each clearing the caller's result slot when false.

The level's trigger records (``FFB01A``, 0x18 bytes each; the evaluator
``00462C``) carry three (kind, argument) pairs.  For each pair the evaluator
calls ``00470C`` with the kind in D5, the argument in D6 and a result slot
in A3 (``FFF38C``/``FFF38E``/``FFF390``, preset to -1); the kind selects a
predicate through the ROM table at ``004718``, and the predicate clears the
slot when its condition does not hold.  A record whose three slots stay
negative fires its action.

Pure functions of ``read(address, size)``; no cycles, CCR, stack or
registers.  What each predicate compares is named for what the arithmetic
supports, not more: the four words at ``FFF22E`` are "the current markers"
(kinds 1/2 test membership), the three at ``FFEF8C``/``FFF01E``/``FFF0B0``
"the tracked ids" (3/4), the table at ``FF502A`` "the status words" (5/6),
``FFEF3E`` and ``FFF1CC`` "the two progress words" (7/8, 15/16), the
elapsed count ``FFF2AA`` over the rate ``FFEEC0`` "the elapsed seconds"
(9/10), the records at ``FF62F6`` (six bytes each) "the flagged entries"
(11/12).  Kinds 13/14 compare the score through ``00364C`` and are not
recovered.
"""
from __future__ import annotations

KIND_TABLE = 0x004718                                 # ROM: one long per kind, the predicate's address
KINDS = 17                                            # the table's extent (0..16)
HANDLERS = (0x00475C, 0x004AF8, 0x004B14, 0x004B30, 0x004B46, 0x004B5C, 0x004B74, 0x004B8C, 0x004B96,
            0x004BA0, 0x004BB8, 0x004BD0, 0x004BEA, 0x004C18, 0x004C5C, 0x004C04, 0x004C0E)
MARKERS = (0xFFF22E, 0xFFF230, 0xFFF232, 0xFFF234)    # kinds 1 (any equal) and 2 (none equal)
TRACKED = (0xFFEF8C, 0xFFF01E, 0xFFF0B0)              # kinds 3 (any equal) and 4 (none equal)
STATUS_WORDS = 0xFFFF502A                             # kinds 5 (negative) and 6 (not negative): word at base + 4 * (argument - 1)
PROGRESS_A, PROGRESS_B = 0xFFEF3E, 0xFFF1CC           # kinds 7/8 (argument below / above A), 15/16 (below / above B)
ELAPSED, RATE = 0xFFF2AA, 0xFFEEC0                    # kinds 9/10: 5 * argument below / above elapsed // rate
FLAGGED = 0xFFFF62F6                                  # kinds 11 (bit 0 of byte +5 set) and 12 (clear): entries of six bytes
FLAGGED_STRIDE, FLAGGED_FLAG_BYTE = 6, 5
SECONDS_PER_ARGUMENT = 5
TRUE, FALSE = 0xFFFF, 0x0000                          # the slot's value: preset -1, cleared when the predicate fails


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _signed_long(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _membership(read, addresses, argument):
    """Which of ``addresses`` holds ``argument`` first (0-based), or None."""
    for index, address in enumerate(addresses):
        if read(address, 2) == argument:
            return index
    return None


def evaluate(read, kind, argument, slot):
    """What ``00470C`` does for ``kind`` (D5) and ``argument`` (D6) with the result slot ``slot`` (A3).

    Returns the kind, the predicate's address, the arm (``'true'`` leaves
    the slot alone, ``'false'`` clears it, ``'none'`` for kind 0,
    ``'unrecovered'`` for the score kinds and any kind outside the table),
    the stores, and the facts the boundary turns into cost and register
    residue: for the membership kinds the index of the first match
    (``matched``), for the table kinds the entry address (``entry``), for
    the elapsed kinds the quotient and the scaled argument, for the
    flagged kinds the entry address and the doubled argument.
    """
    argument &= 0xFFFF
    result = {'kind': kind, 'handler': HANDLERS[kind] if kind < KINDS else None, 'stores': {}, 'matched': None,
              'entry': None, 'quotient': None, 'scaled': None}
    if kind >= KINDS or kind in (13, 14):
        return {**result, 'arm': 'unrecovered'}
    if kind == 0:
        return {**result, 'arm': 'none'}
    if kind in (1, 2):
        matched = _membership(read, MARKERS, argument)
        holds = (matched is not None) if kind == 1 else (matched is None)
        result['matched'] = matched
    elif kind in (3, 4):
        matched = _membership(read, TRACKED, argument)
        holds = (matched is not None) if kind == 3 else (matched is None)
        result['matched'] = matched
    elif kind in (5, 6):
        offset = ((argument - 1) & 0xFFFF) * 4 & 0xFFFF            # subq.w; add.w; add.w: a word index
        entry = (STATUS_WORDS + _signed_word(offset)) & 0xFFFFFFFF
        negative = bool(read(entry & 0xFFFFFF, 2) & 0x8000)
        holds = negative if kind == 5 else not negative
        result['entry'] = entry
    elif kind in (7, 8, 15, 16):
        word = _signed_word(read(PROGRESS_A if kind in (7, 8) else PROGRESS_B, 2))
        value = _signed_word(argument)
        holds = value < word if kind in (7, 15) else value > word
    elif kind in (9, 10):
        rate = _signed_word(read(RATE, 2))
        if rate == 0:
            return {**result, 'arm': 'unrecovered'}                 # divs by zero traps; never witnessed
        elapsed = _signed_long(read(ELAPSED, 4))
        quotient = int(elapsed / rate)                                # divs truncates toward zero
        if not -0x8000 <= quotient <= 0x7FFF:
            return {**result, 'arm': 'unrecovered'}                 # divs overflow leaves D0 alone; never witnessed
        scaled = (SECONDS_PER_ARGUMENT * argument) & 0xFFFF
        holds = _signed_word(scaled) < quotient if kind == 9 else _signed_word(scaled) > quotient
        result.update(quotient=quotient, scaled=scaled, remainder=elapsed - quotient * rate)
    else:                                                             # 11, 12
        doubled = (2 * argument) & 0xFFFF
        entry = (FLAGGED + _signed_word(doubled) + _signed_word((2 * doubled) & 0xFFFF)) & 0xFFFFFFFF
        flag = read((entry + FLAGGED_FLAG_BYTE) & 0xFFFFFF, 1) & 1
        holds = bool(flag) if kind == 11 else not flag
        result.update(entry=entry, scaled=(2 * doubled) & 0xFFFF)
    if not holds:
        result['stores'][slot & 0xFFFFFF] = (FALSE, 2)
    return {**result, 'arm': 'true' if holds else 'false'}
