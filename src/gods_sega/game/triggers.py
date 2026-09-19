"""The trigger evaluator (ROM 00462C-004688): the disabled and non-firing arms only.

The level's trigger records (`TRIGGER_TABLE`, 0x18 bytes each) carry three
(kind, argument) condition pairs at +0/+4/+8.  For a caller-supplied record
index, the evaluator presets three result slots to true (-1), calls
`00470C` (`conditions.evaluate`) once per pair with the kind, argument and
that pair's own slot, then ANDs the three slots: if all three still read
true the record fires (message, action dispatch -- `004688` onward, not
modeled here, left for the supervisor); otherwise it does nothing more.
A global word disables the whole evaluator (no calls at all) when nonzero;
no recording has ever been seen with it set.
"""
from __future__ import annotations

from . import conditions

DISABLE_FLAG = 0xFFFFEF38                          # tst.w: nonzero skips evaluation entirely (unwitnessed)
TRIGGER_TABLE = 0xFFFFB01A                          # the level's trigger records
TRIGGER_STRIDE = 0x18
SLOT_BASE = 0xFFFFF38C                              # three consecutive words: the same slots 00470C writes
PAIR_OFFSETS = (0x00, 0x04, 0x08)                   # (kind, argument) at +0/+4/+8 inside a trigger record


def evaluate_record(read, index, disable_flag):
    """00462C: one trigger record's three conditions, by the record's own index into `TRIGGER_TABLE`.

    Returns ``{'arm': 'disabled'}`` (unwitnessed by any recording) when
    ``disable_flag`` is nonzero; otherwise ``{'arm': 'non-firing'|'firing'|
    'unrecovered', 'entry': the record's address, 'calls': one dict per pair
    (kind, argument, slot, the raw ``conditions.evaluate`` result -- 'arm'
    may itself be ``'unrecovered'``), 'stores': every slot write across the
    calls that did run}``.  Declining an unrecovered or unwitnessed kind is
    the boundary's job (as for a lone 00470C call); this just reports what
    each of the three calls found, in order, stopping at the first one
    ``conditions.evaluate`` cannot resolve (later pairs are never reached in
    the original either, since the routine has already raised by then).
    """
    if disable_flag & 0xFFFF:
        return {'arm': 'disabled'}
    entry = (TRIGGER_TABLE + TRIGGER_STRIDE * index) & 0xFFFFFFFF
    calls = []
    stores = {}
    for slot_index, offset in enumerate(PAIR_OFFSETS):
        kind = read((entry + offset) & 0xFFFFFF, 2)
        argument = read((entry + offset + 2) & 0xFFFFFF, 2)
        slot = (SLOT_BASE + 2 * slot_index) & 0xFFFFFFFF
        result = conditions.evaluate(read, kind, argument, slot)
        calls.append({'kind': kind, 'argument': argument, 'slot': slot, 'result': result})
        stores.update(result['stores'])
    if any(call['result']['arm'] == 'unrecovered' for call in calls):
        return {'arm': 'unrecovered', 'entry': entry, 'calls': calls, 'stores': stores}
    fires = all(call['result']['arm'] != 'false' for call in calls)
    return {'arm': 'firing' if fires else 'non-firing', 'entry': entry, 'calls': calls, 'stores': stores}


# --- The firing tail (00468A-0046CE): the recipe-6a family over the record's own +0x10 action word --
#
# `docs/gods/blockers/2026-09-16-00462C-firing.md`'s Split/Resolution: (1) a message-display preamble
# gated on a per-message-group flag byte in RAM, itself found through a two-step indirection table at
# work-RAM `FFFFAD0E` (`$14(a1)`, the record's own message-group index, doubled into that table, its
# own signed word offset added to the table's base, then `+0x50`); (2) two unconditional calls into
# the already-recovered `004800`/`00475E`; (3) a tail JUMP (`jmp (a5)`, `0046CE`) through the 15-entry
# action table at ROM `0046D0`, indexed by the record's own `+0x10` word doubled twice (NOT masked --
# unlike `00475E`'s own bit-7 test of the SAME word, the dispatch reads the full word; a value whose
# doubling would leave the table's own 60-byte extent is real ROM, never witnessed, declined).
MESSAGE_INDEX = 0x14
MESSAGE_TABLE_BASE = 0xFFFFAD0E
MESSAGE_FLAG_OFFSET = 0x50
MESSAGE_PRIORITY = 0x32                 # D7 into 007986: fixed, every firing activation
ACTION_INDEX = 0x10
ACTION_TABLE_BASE = 0x0046D0
ACTION_TABLE_COUNT = 15
ACTION_TABLE_ENTRY_SIZE = 4


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def firing_message_address(read, a1):
    """0046A4's own gate address: the record's own message-group index at ``a1+0x14`` through the
    work-RAM indirection table at `FFFFAD0E`, ``+0x50``.  Returns the address whose own leading byte
    IS the message text -- a zero byte there means no message this activation."""
    index = read((a1 + MESSAGE_INDEX) & 0xFFFFFF, 2)
    offset = _signed_word(read((MESSAGE_TABLE_BASE + 2 * index) & 0xFFFFFF, 2))
    address = (MESSAGE_TABLE_BASE + offset + MESSAGE_FLAG_OFFSET) & 0xFFFFFFFF
    has_message = read(address & 0xFFFFFF, 1) != 0
    return {'address': address, 'has_message': has_message}


def firing_action_target(read, a1):
    """0046C2's own dispatch: the record's own `+0x10` word, doubled twice (a plain 16-bit ADD.W,
    never masked), as a BYTE offset into the 15-entry action table.  Returns the raw word, the byte
    offset, and -- only when the offset lands inside the table's own 60 bytes -- the handler address
    the ROM would actually jump to; an offset outside that domain is real ROM, never witnessed by any
    recording, and carries no address (the boundary declines it)."""
    raw = read((a1 + ACTION_INDEX) & 0xFFFFFF, 2)
    offset = (raw * ACTION_TABLE_ENTRY_SIZE) & 0xFFFF
    in_domain = offset < ACTION_TABLE_COUNT * ACTION_TABLE_ENTRY_SIZE
    target = read((ACTION_TABLE_BASE + offset) & 0xFFFFFF, 4) if in_domain else None
    return {'raw': raw, 'offset': offset, 'in_domain': in_domain, 'target': target}
