"""The score conversion (ROM 00364C-0036E0): called from the score-update sites (0035B2, 003604)
and, unwitnessed, from the trigger conditions' score kinds (13/14, through 004C4E's tail jump).

Packs a non-negative value into four caller-supplied words as eight packed-BCD
digits (two per word, low nibble first then high), adding on top of whatever
those four words already hold rather than overwriting them: each digit is a
68000 ``abcd`` (extended-precision decimal add) into the target word's low
byte, so the routine also threads the caller's ``X`` flag in as the first
digit's carry-in and BCD-carries out of a full word into the next one.  The
loop divides by ten and stops as soon as the quotient is zero (``divs.w
#$a,d6`` then ``ext.l d6; beq``); the recordings only ever witness 1, 2 or 3
divisions (``value`` 0-9, 10-99, 100-999) -- four or more digits is real ROM
code but no recording enters it, so it stays declined.  ``d7`` always ends
the routine at zero (the chain's own ``clr.w d7`` between digits).
"""
from __future__ import annotations

WORD_COUNT = 4                          # d0..d3: four packed-BCD words, low byte the meaningful one
WITNESSED_DIGITS = (1, 2, 3)            # divisions performed before the quotient hits zero


def _bcd_add(existing_byte, digit, carry_in):
    """One 68000 ``abcd.b`` on the low byte: existing_byte + digit (both BCD) + carry_in.

    Returns ``(result_byte, carry_out)``; the result's high nibble is BCD-adjusted
    independently of the low nibble, matching the real instruction (not a plain
    binary add mod 100).
    """
    lo = (existing_byte & 0x0F) + (digit & 0x0F) + carry_in
    hi = (existing_byte >> 4) + (digit >> 4)
    if lo > 9:
        lo -= 10
        hi += 1
    carry_out = 0
    if hi > 9:
        hi -= 10
        carry_out = 1
    return ((hi << 4) | lo) & 0xFF, carry_out


def convert_score(read, value, base, entry_x):
    """00364C: pack ``value`` (D6) as BCD digits on top of the four words at ``base`` (A0).

    ``read(address, size)`` supplies the four words' current content (each
    loaded once, at entry, the way ``movem.w (a0)+,d0-d3`` does); ``entry_x``
    is the caller's X flag (the first digit's carry-in).  Returns the digit
    count (``None`` when the value needs a fourth division, unwitnessed), the
    four result words (``words``, high byte kept, low byte the packed BCD
    pair), the ``stores`` (only the words whose value actually changed) and
    the exit ``x`` flag (the last ``abcd`` in the final digit's own chain --
    N/Z/V/C are fixed at the exit: 0/1/0/0, the flags of the zero quotient
    ``ext.l`` leaves, C cleared again by the routine's own ``move.w
    #$1,$f1ce.w``).
    """
    if value < 0:
        return {'digits': None}
    original = [read(base + 2 * index, 2) for index in range(WORD_COUNT)]
    words = list(original)
    x = 1 if entry_x else 0
    remaining = value
    digits = 0
    for slot in range(8):
        quotient, remainder = divmod(remaining, 10)
        register = slot // 2
        shifted = slot % 2 == 1
        digit = (remainder << 4) & 0xFF if shifted else remainder & 0xFF
        if shifted:
            x = 0                                   # the lsl.w #4 shifting a value 0-9 always shifts out 0
        for index in range(register, WORD_COUNT):
            contribution = digit if index == register else 0
            low_byte, x = _bcd_add(words[index] & 0xFF, contribution, x)
            words[index] = (words[index] & 0xFF00) | low_byte
        digits += 1
        remaining = quotient
        if quotient == 0:
            break
    else:
        return {'digits': None}                     # an eighth digit was needed: real code, never witnessed
    if digits not in WITNESSED_DIGITS:
        return {'digits': None}
    stores = {base + 2 * index: (words[index], 2) for index in range(WORD_COUNT) if words[index] != original[index]}
    return {'digits': digits, 'words': tuple(words), 'original': tuple(original), 'stores': stores, 'x': bool(x)}
