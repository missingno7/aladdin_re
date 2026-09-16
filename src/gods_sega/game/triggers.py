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
