"""Pickups: the award for a collected item (``013264``).

The level keeps a byte grid at ``FFBBDE`` (8x8-pixel cells, 48 bytes per
row) whose non-zero bytes are pickup codes; the player's box is scanned
against it every tick by the pickup check ``00BA8E``, and a hit calls
``013264`` with A0 just past the found byte.  A positive code names one of
27 item slots in three groups of nine (the groups' tables at ``FFEF8C``,
``FFF01E``, ``FFF0B0``: an active-id word, then nine 8-byte slots); the
active id selects the group's item record through the ROM table at
``012D04`` (eleven work-RAM records of 0x50 bytes at ``FFF552``), whose
word at ``+8`` is the item's value.  The value goes to ``FFF35A`` (plus a
time bonus, an eighth of ``FFF362 - FFF36C`` when positive), a cue is
requested when sound is on (``FFEF14``), and the slot is consumed when the
record's byte at ``+0x49`` says so.  Negative codes are the special
pickups: -1 takes the value from ``FFF158`` and reports 1 in D4, -2 is
worth 10,000 (nothing when sound is on), -3 is worth nothing; -4 and below
continue into the routine that follows and are not recovered.

Pure functions of ``read(address, size)``; no cycles, CCR, stack or
registers.  The names are what the arithmetic supports, not more.
"""
from __future__ import annotations

from .effects import RANDOM_CURSOR, next_random
from .hazard import effect_pool_add
from .zones import HALF_HEIGHT, HALF_WIDTH, zone_check

PICKUP_GRID = 0xFFFFBBDE                              # bytes, 8x8-pixel cells, 48 per row (00BA8E's scan, 013316's inverse)
GROUP_TABLES = (0xFFFFEF8C, 0xFFFFF01E, 0xFFFFF0B0)   # per group: the active id word, then nine 8-byte slots
GROUP_SIZE, SLOT_SIZE, SLOT_BASE = 9, 8, 2
ITEM_RECORDS = 0x012D04                               # ROM: eleven longs, the work-RAM record of each item id
ITEM_RECORD_COUNT = 11
ITEM_VALUE, ITEM_CONSUMES_SLOT = 0x8, 0x49            # record fields: the value word, the consume flag byte
AWARD = 0xFFF35A                                      # word: the value awarded by the last pickup
TIME_NOW, TIME_MARK = 0xFFF362, 0xFFF36C              # words: the bonus is an eighth of their difference when positive
SOUND_ON, SOUND_CUE = 0xFFEF14, 0xFFFDF4              # the cue word of the sound command block
PICKUP_CUE = 0x38
SPECIAL_VALUE = 0xFFF158                              # the -1 pickup's value
BIG_VALUE = 0x2710


def _signed_byte(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def collect(read, after_code):
    """What ``013264`` does with A0 just past the pickup code byte.

    Returns the arm (``'item'``, ``'special-1'``, ``'special-2'``,
    ``'special-3'``, ``'unrecovered'`` for codes of -4 and below), the
    code, the stores as ``{address: (value, size)}``, D4's result, and for
    an item: the group table, the slot index (0-based), the active id, the
    record, the time difference and whether the bonus arm ran, whether the
    cue was requested and whether the slot was consumed.
    """
    code = _signed_byte(read((after_code - 1) & 0xFFFFFF, 1))
    result = {'code': code, 'stores': {}, 'd4': 0, 'group': None, 'slot': None, 'record': None,
              'time_difference': None, 'bonus': False, 'cue': False, 'consumed': False}
    stores = result['stores']
    if code >= 0:
        group = 0 if code <= GROUP_SIZE else (1 if code - GROUP_SIZE <= GROUP_SIZE else 2)
        in_group = code - GROUP_SIZE * group
        table = GROUP_TABLES[group]
        slot = in_group - 1                              # code 0 gives slot -1: the word before the slots
        active = read(table & 0xFFFFFF, 2)
        record = read(ITEM_RECORDS + _signed_word(4 * active), 4) & 0xFFFFFFFF   # (a1,d4.w): a signed index
        value = read((record + ITEM_VALUE) & 0xFFFFFF, 2)
        difference = _signed_word(read(TIME_NOW, 2) - read(TIME_MARK, 2))
        if difference > 0:
            value = (value + (difference >> 3)) & 0xFFFF
        stores[AWARD] = (value, 2)
        if read(SOUND_ON, 2):
            stores[SOUND_CUE] = (PICKUP_CUE, 2)
            result['cue'] = True
        if read((record + ITEM_CONSUMES_SLOT) & 0xFFFFFF, 1):
            stores[(table + SLOT_BASE + SLOT_SIZE * slot) & 0xFFFFFF] = (0, 2)
            result['consumed'] = True
        result.update(arm='item', group=group, slot=slot, active=active, record=record,
                      time_difference=difference, bonus=difference > 0, table=table)
        return result
    if code == -1:
        stores[AWARD] = (read(SPECIAL_VALUE, 2), 2)
        return {**result, 'arm': 'special-1', 'd4': 1}
    if code == -2:
        stores[AWARD] = (0, 2) if read(SOUND_ON, 2) else (BIG_VALUE, 2)
        return {**result, 'arm': 'special-2'}
    if code == -3:
        stores[AWARD] = (0, 2)
        return {**result, 'arm': 'special-3'}
    return {**result, 'arm': 'unrecovered'}


# --- 00BA8E: the pickup check (a caller-supplied position, D0/D1/D2) --------
#
# Calls the already-recovered zone check first (``zone_check``, ``00BCCE``):
# a forced-negative result there is an immediate sound cue and nothing else
# (the ``'zone-cue'`` arm).  Otherwise a box is built around (D0,D1) from
# ``HALF_WIDTH``/``HALF_HEIGHT`` (copied to ``BOX_COPY_X``/``BOX_COPY_Y``
# first, unconditionally): each axis independently near-wraps (very
# negative: the size word gets the residue added back and the position is
# pinned to ``-0x10``) or far-clamps (past a fixed threshold: the size word
# shrinks by the excess) -- either clamp can itself bail the whole routine
# when the size collapses to zero or negative (``'clean'`` arm, no pickup
# grid access at all).  Otherwise an append gate (``ARRAY_GATE``) decides
# whether the box's own position and D2 are appended into a growing array
# (``ARRAY_CURSOR``/``ARRAY_COUNT``; common on some recordings) before the
# pickup grid (``PICKUP_GRID``) is scanned in the box's own (rows, cols) bounds (a
# formula in the clamped size words, the same "unrolled test count" shape
# ``00FDB8``'s row scan and ``0018C8``'s cache scan share).  A nonzero byte
# is a hit: ``collect`` (``013264``) awards it, and when the box's own D2
# residue exceeds the award and the award is nonzero, an effect is queued:
# two draws from the random table (``next_random``, ``014A3C``) jitter the
# spawn position on each axis, then ``effect_pool_add`` (``00932C``) adds it
# to the shared pool.  Sub-arms this routine's own census never enters
# (the special-1 pickup's own further call, the message/digit-split tail,
# the award-zero bare exit, either jitter draw's own default-mask branch)
# are named but not modelled further: the boundary declines them.

CAMERA_X, CAMERA_Y = 0xFFFFF3EE, 0xFFFFF3F0
BOX_COPY_X, BOX_COPY_Y = 0xFFFFF392, 0xFFFFF394        # the working copy of HALF_WIDTH/HALF_HEIGHT
CHECK_SOUND_ON = 0xFFFFF396                            # this routine's own sound gate (distinct from SOUND_ON=EF14)
CHECK_SOUND_CUE = 0xFFFFFDF4
ZONE_CUE_SOUND_OFF, ZONE_CUE_SOUND_ON = 0x3C, 0x4F
ARRAY_GATE = 0xFFFFEF8A                                # bit15 clear appends into the array below (common: 30/33 witnessed on 7251bbd0ecf7)
ARRAY_CURSOR = 0xFFFFF1E8                              # long: the array's own write cursor, advanced by 6 (three words) per append
ARRAY_COUNT = 0xFFFFF1E2                               # word: incremented once per append
MESSAGE_FLAG = 0xFFFFEF46                              # nonzero selects the unwitnessed digit-split tail
RESULT_WORD = 0xFFFFF3D4
PICKUP_GRID_ROW = 0x30                                 # matches PICKUP_GRID's own 48-byte row stride
NEAR_LIMIT = 0xFFF0                                    # -16: both axes near-wrap at or below this
X_FAR_LIMIT, Y_FAR_LIMIT = 0x150, 0xD0                 # far thresholds (the X test compares the raw position,
                                                        # the Y test compares position+size -- the ROM's own asymmetry)


def _axis_clamp(read, size_address, raw, far_limit, far_uses_combined):
    """One axis of 00BA8E's own box clamp; ``raw`` is the position already rounded to a multiple of 8.

    Returns the sub-arm (``'none'``, ``'near'``, ``'far'``), whether it
    bails the whole routine, the size word's new value (``None`` if
    unwritten) and the value used for the grid scan going forward.
    """
    size = read(size_address, 2)
    if _signed_word(raw) <= _signed_word(NEAR_LIMIT):
        adjusted = (raw + 0x10) & 0xFFFF
        new_size = (size + adjusted) & 0xFFFF
        # The last flag-setting instruction on this sub-arm is the ADD itself (add.w Dn,size): its
        # own operands, so the boundary can derive X/C exactly rather than guess from a stale SR.
        return {'arm': 'near', 'bail': _signed_word(new_size) <= 0, 'new_size': new_size, 'value': NEAR_LIMIT,
                'op': 'add', 'left': size, 'right': adjusted}
    combined = (size + raw) & 0xFFFF
    tested = combined if far_uses_combined else raw
    if _signed_word(tested) < _signed_word(far_limit):
        return {'arm': 'none', 'bail': False, 'new_size': None, 'value': raw, 'op': None}
    excess = (combined - far_limit) & 0xFFFF
    new_size = (size - excess) & 0xFFFF
    # Here the last flag-setter is the SUB (sub.w d4,size).
    return {'arm': 'far', 'bail': _signed_word(new_size) <= 0, 'new_size': new_size, 'value': raw,
            'op': 'sub', 'left': size, 'right': excess}


def _scan(read, base, rows, cols):
    """The bounded grid scan: up to ``rows`` rows of ``cols`` consecutive bytes each."""
    last_address, last_value = None, None
    for row in range(rows):
        row_base = (base + row * PICKUP_GRID_ROW) & 0xFFFFFFFF
        for col in range(cols):
            last_address = (row_base + col) & 0xFFFFFF
            last_value = read(last_address, 1)
            if last_value != 0:
                return {'found': True, 'row': row, 'col': col, 'after_code': (row_base + col + 1) & 0xFFFFFFFF,
                        'last_address': last_address, 'last_value': last_value}
    return {'found': False, 'row': rows, 'col': None, 'after_code': None,
            'last_address': last_address, 'last_value': last_value}


def pickup_check(read, d0, d1, d2):
    """00BA8E: the pickup check over the player's own box (D0/D1 position, D2 the zone check's own argument)."""
    zone = zone_check(read, d0 & 0xFFFF, d1 & 0xFFFF, d2 & 0xFFFF)
    zd2 = zone.get('new_d2')
    d2_after_zone = zd2 if zd2 is not None else d2 & 0xFFFF
    stores = dict(zone['stores'])
    if _signed_word(d2_after_zone) < 0:
        cue = ZONE_CUE_SOUND_OFF if read(CHECK_SOUND_ON, 2) == 0 else ZONE_CUE_SOUND_ON
        stores[CHECK_SOUND_CUE & 0xFFFFFF] = (cue, 2)
        return {'arm': 'zone-cue', 'zone': zone, 'stores': stores, 'd2': 0xFFFF}

    size_x, size_y = read(HALF_WIDTH, 2), read(HALF_HEIGHT, 2)
    stores[BOX_COPY_X & 0xFFFFFF] = (size_x, 2)
    stores[BOX_COPY_Y & 0xFFFFFF] = (size_y, 2)
    raw_x = (d0 - read(CAMERA_X, 2) + 4) & 0xFFF8
    raw_y = (d1 - read(CAMERA_Y, 2) + 4) & 0xFFF8
    # The Y clamp runs first in the ROM (00BAA0 onward); a Y bail jumps straight to the clean exit
    # without ever reaching X's own clamp code at all -- X is only computed when Y did not bail.
    y_clamp = _axis_clamp(read, HALF_HEIGHT, raw_y, Y_FAR_LIMIT, True)
    if y_clamp['new_size'] is not None:
        stores[HALF_HEIGHT & 0xFFFFFF] = (y_clamp['new_size'], 2)
    if y_clamp['bail']:
        x_clamp = {'arm': 'not-reached', 'bail': False, 'new_size': None, 'value': None, 'op': None}
        result = {'zone': zone, 'x_clamp': x_clamp, 'y_clamp': y_clamp, 'stores': stores, 'd2': d2_after_zone}
        return {**result, 'arm': 'clean', 'scan': None}
    x_clamp = _axis_clamp(read, HALF_WIDTH, raw_x, X_FAR_LIMIT, False)
    if x_clamp['new_size'] is not None:
        stores[HALF_WIDTH & 0xFFFFFF] = (x_clamp['new_size'], 2)
    result = {'zone': zone, 'x_clamp': x_clamp, 'y_clamp': y_clamp, 'stores': stores, 'd2': d2_after_zone}
    if x_clamp['bail']:
        return {**result, 'arm': 'clean', 'scan': None}

    x_final, y_final = x_clamp['value'], y_clamp['value']
    appended = read(ARRAY_GATE, 2) & 0x8000 == 0
    result['appended'] = appended
    if appended:
        cursor = read(ARRAY_CURSOR, 4)
        count = read(ARRAY_COUNT, 2)
        stores[(cursor + 0) & 0xFFFFFF] = (x_final, 2)
        stores[(cursor + 2) & 0xFFFFFF] = (y_final, 2)
        stores[(cursor + 4) & 0xFFFFFF] = (d2_after_zone, 2)
        stores[ARRAY_CURSOR & 0xFFFFFF] = ((cursor + 6) & 0xFFFFFFFF, 4)
        stores[ARRAY_COUNT & 0xFFFFFF] = ((count + 1) & 0xFFFF, 2)
        result['array_cursor'] = cursor

    # The scan's own base address comes from the clamp's position value (x_clamp/y_clamp['value']);
    # its bounds (rows, cols) come from the CURRENT size words instead -- F382/F384 read fresh, which
    # is the clamp's own new_size when it wrote one, or the original (BOX_COPY) size otherwise.
    size_x_now = x_clamp['new_size'] if x_clamp['new_size'] is not None else size_x
    size_y_now = y_clamp['new_size'] if y_clamp['new_size'] is not None else size_y
    cell_x = _signed_word(x_final) >> 3
    y_rounded = y_final & 0xFFF8
    cell_y6 = _signed_word((y_rounded * 6) & 0xFFFF)   # the two doublings (d1*2, then *2 again): a net *6
    base = (PICKUP_GRID + cell_x + cell_y6) & 0xFFFFFFFF
    cols_shifted = _signed_word(size_x_now) >> 3
    rows_shifted = _signed_word(size_y_now) >> 3
    cols = max(1, cols_shifted - 1)
    rows = max(1, rows_shifted)
    scan = _scan(read, base, rows, cols)
    result.update(scan=scan, rows=rows, cols=cols, cols_shifted=cols_shifted, rows_shifted=rows_shifted)
    if not scan['found']:
        return {**result, 'arm': 'clean'}

    collected = collect(read, scan['after_code'])
    result['collect'] = collected
    if collected['d4'] != 0:
        return {**result, 'arm': 'found-special'}          # the special-1 timer/011540 continuation: unwitnessed
    if read(MESSAGE_FLAG, 2) != 0:
        return {**result, 'arm': 'found-message'}           # the digit-split tail: unwitnessed
    stores.update(collected['stores'])
    result['d2_before_award'] = d2_after_zone   # the sub.w d3,d2 left operand, for the boundary's own X/C
    d3 = collected['stores'].get(AWARD, (read(AWARD, 2), 2))[0]     # AWARD, just stored by collect()
    box_result = (d2_after_zone - d3) & 0xFFFF
    if _signed_word(box_result) <= 0:
        cue = ZONE_CUE_SOUND_OFF if read(CHECK_SOUND_ON, 2) == 0 else ZONE_CUE_SOUND_ON
        stores[CHECK_SOUND_CUE & 0xFFFFFF] = (cue, 2)
        return {**result, 'arm': 'found-sound', 'd3': d3, 'box_result': box_result, 'stores': stores, 'd2': 0xFFFF}

    stores[RESULT_WORD & 0xFFFFFF] = (box_result, 2)
    if d3 == 0:
        return {**result, 'arm': 'found-bare', 'd3': d3, 'box_result': box_result, 'stores': stores, 'd2': box_result}

    # The effect chain: the box's own size copy (BOX_COPY_X/Y, made at entry, not the clamped current size)
    # jittered by two random draws, offset from the ORIGINAL (unrounded) D0/D1 the caller passed -- the
    # caller's own d0/d1 are re-read from the routine's own saved frame at this point in the ROM, which
    # is exactly the untouched arguments this function was called with.
    # D4 is reused: loaded with the size copy, halved (asr.w #1, the "half" used to offset the
    # position), and the SAME register then masked (andi.w #$fff0) and decremented for the jitter
    # mask -- so the mask comes from the HALVED value, not the size copy itself.
    half_x = (_signed_word(size_x) >> 1) & 0xFFFF
    half_y = (_signed_word(size_y) >> 1) & 0xFFFF
    if (half_x & 0xFFF0) == 0:
        return {**result, 'arm': 'found-jitter-x-default', 'd3': d3}   # half_x<0x10's default mask: unwitnessed
    if (half_y & 0xFFF0) == 0:
        return {**result, 'arm': 'found-jitter-y-default', 'd3': d3}   # half_y<0x10's default mask: unwitnessed
    mask_x = (half_x & 0xFFF0) - 1
    mask_y = (half_y & 0xFFF0) - 1
    draw_x = next_random(read)
    stores.update(draw_x['stores'])
    dx, dx_negative = draw_x['value'], bool(draw_x['value'] & 0x8000)
    jitter_x = dx & mask_x
    px = ((d0 & 0xFFFF) + half_x - jitter_x if dx_negative else (d0 & 0xFFFF) + half_x + jitter_x) & 0xFFFF

    # The cursor RANDOM_CURSOR advanced with the first draw: read it back through that store so the
    # second draw sees the same table position the machine's own second call would.
    advanced_cursor = draw_x['stores'][RANDOM_CURSOR & 0xFFFFFF][0]
    read_after_x = lambda address, size, _base=read, _addr=RANDOM_CURSOR & 0xFFFFFF, _val=advanced_cursor: (
        _val if (address & 0xFFFFFF) == _addr and size == 2 else _base(address, size))
    draw_y = next_random(read_after_x)
    stores.update(draw_y['stores'])
    dy, dy_negative = draw_y['value'], bool(draw_y['value'] & 0x8000)
    if dy_negative:
        return {**result, 'arm': 'found-jitter-y-negative', 'd3': d3, 'draw_x': draw_x, 'px': px,
                'dx_negative': dx_negative}   # the second draw's negative branch: unwitnessed
    jitter_y = dy & mask_y
    py = ((d1 & 0xFFFF) + half_y + jitter_y) & 0xFFFF

    pool_x = (px - 8 - read(CAMERA_X, 2)) & 0xFFFF
    pool_y = (py - 8 - read(CAMERA_Y, 2)) & 0xFFFF
    added = effect_pool_add(read, pool_x, pool_y, 0, 0)
    result['effect'] = added
    stores.update(added['stores'])
    return {**result, 'arm': 'found-effect', 'd3': d3, 'box_result': box_result, 'stores': stores, 'd2': box_result,
            'px': px, 'py': py, 'dx_negative': dx_negative, 'dy_negative': dy_negative,
            'pool_x': pool_x, 'pool_y': pool_y, 'mask_y': mask_y}
