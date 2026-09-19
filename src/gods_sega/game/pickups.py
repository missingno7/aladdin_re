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
continue into ``013316`` (``grid_inverse_award``, below), the grid inverse
and a bounded debris burst.

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
SPECIAL_TIMER = 0xFFFFF156                            # word: the special-1 pickup's own decrement (00BA8E's own tail)
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
    # -4 and below: the same cascade that tests -1/-2/-3 falls all the way through to the code's own
    # "worth nothing special" tail, which unconditionally awards BIG_VALUE (10000) before continuing
    # into 013316 (grid_inverse_award, below) -- a real, witnessed store, not a silent fall-through.
    stores[AWARD] = (BIG_VALUE, 2)
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
# to the shared pool.  ``AWARD_SCALE_LEVEL`` nonzero (00BBEA onward, formerly
# read as an unwitnessed "message" tail) is not a call into any message
# system at all: it is a second, RAM-only way to derive the SAME (box
# residue, award) pair the arms above already consume, an award shift by
# ``3 - AWARD_SCALE_LEVEL`` (or a halving correction when the shift removes
# no bits) before rejoining the shared found-sound/found-bare/found-effect
# tail at its own entry points (00BC12/00BC18) -- see ``_scaled_box_result``.
# Sub-arms this routine's own census never enters (the special-1 pickup's
# own further call, the award-zero bare exit, either jitter draw's own
# default-mask branch) are named but not modelled further: the boundary
# declines them.

CAMERA_X, CAMERA_Y = 0xFFFFF3EE, 0xFFFFF3F0
BOX_COPY_X, BOX_COPY_Y = 0xFFFFF392, 0xFFFFF394        # the working copy of HALF_WIDTH/HALF_HEIGHT
CHECK_SOUND_ON = 0xFFFFF396                            # this routine's own sound gate (distinct from SOUND_ON=EF14)
CHECK_SOUND_CUE = 0xFFFFFDF4
ZONE_CUE_SOUND_OFF, ZONE_CUE_SOUND_ON = 0x3C, 0x4F
ARRAY_GATE = 0xFFFFEF8A                                # bit15 clear appends into the array below (common: 30/33 witnessed on 7251bbd0ecf7)
ARRAY_CURSOR = 0xFFFFF1E8                              # long: the array's own write cursor, advanced by 6 (three words) per append
ARRAY_COUNT = 0xFFFFF1E2                               # word: incremented once per append
AWARD_SCALE_LEVEL = 0xFFFFEF46                         # nonzero re-derives (box_result, d3) by an award shift
RESULT_WORD = 0xFFFFF3D4
PICKUP_GRID_ROW = 0x30                                 # matches PICKUP_GRID's own 48-byte row stride
NEAR_LIMIT = 0xFFF0                                    # -16: both axes near-wrap at or below this
X_FAR_LIMIT, Y_FAR_LIMIT = 0x150, 0xD0                 # far thresholds (the X test compares the raw position,
                                                        # the Y test compares position+size -- the ROM's own asymmetry)


def _lsr_word(value, count):
    """68000 LSR.w Dx,Dy: the count register is masked to 6 bits; 16 or more zeroes a word."""
    count &= 0x3F
    value &= 0xFFFF
    if count == 0:
        return value
    if count >= 16:
        return 0
    return value >> count


def _asr_word(value, count):
    """68000 ASR.w #n,Dy: arithmetic (sign-extending) shift; n here is always the immediate 1."""
    value = _signed_word(value)
    if count >= 16:
        return 0xFFFF if value < 0 else 0
    return (value >> count) & 0xFFFF


def _scaled_box_result(d2_orig, d3_orig, level):
    """00BBF0-00BC1C: the AWARD_SCALE_LEVEL-nonzero derivation of (box_result, d3), an alternate
    front end for the SAME found-sound/found-bare/found-effect tail the unscaled path reaches at
    00BC24/00BC44/00BC56.  ``d2_orig`` is the box's own D2 residue before the award subtraction
    (``d2_after_zone``), ``d3_orig`` the award ``collect()`` just stored.

    Returns the tail's own ``box_result``, the ``d3`` it should test for bare-vs-effect, which of
    the two branches back at 00BC14/00BC16 was taken, and the (op, left, right) of the last
    flag-setting instruction before that branch -- ``pickup_check`` threads this through as
    ``result['x_op']`` so the boundary derives the exit X bit from the real ROM instruction
    instead of assuming the unscaled path's own ``sub.w d3,d2``.
    """
    d2_minus_d3 = (d2_orig - d3_orig) & 0xFFFF                    # 00BBF2: sub.w d3,d2
    shift_raw = (3 - level) & 0xFFFF                              # 00BBF4/00BBF6: moveq #3,d5; sub.w level,d5
    bpl_taken = not (shift_raw & 0x8000)                          # 00BBFA: bpl.b $bbfe
    shift = shift_raw if bpl_taken else 0                         # 00BBFC: moveq #0,d5 (only when not taken)
    shifted = _lsr_word(d3_orig, shift)                           # 00BC00: lsr.w d5,d3
    same = shifted == (d3_orig & 0xFFFF)                          # 00BC02/00BC04: cmp.w (a7)+,d3; bne.b
    if same:
        half = _lsr_word(d3_orig, 1)                              # 00BC06/00BC08: move.w d3,d5; lsr.w #1,d3
        remainder = (d3_orig - half) & 0xFFFF                     # 00BC0A: sub.w d3,d5
        remainder = _asr_word(remainder, 1)                       # 00BC0C: asr.w #1,d5
        d3_final = (half + remainder) & 0xFFFF                    # 00BC0E: add.w d5,d3
    else:
        d3_final = shifted
    box_result = (d2_minus_d3 + d3_final) & 0xFFFF                # 00BC12: add.w d3,d2
    common = {'shift': shift, 'same': same, 'shift_raw': shift_raw, 'bpl_taken': bpl_taken,
              # 00BBF0/00BBFE push d2 then d3 (both words) below the routine's own live frame, popped
              # at 00BC02/00BC10 but never overwritten again: transient RAM residue the boundary must
              # write too (game.boundary._pk_scale_transient_writes).
              'd2_orig': d2_orig & 0xFFFF, 'd3_orig': d3_orig & 0xFFFF}
    if _signed_word(box_result) <= 0:                             # 00BC14/00BC16: bmi.b / beq.b -> 00BC24
        return {**common, 'box_result': box_result, 'd3': d3_final, 'branch': 'cue',
                'x_op': ('add', d2_minus_d3, d3_final), 'box_result_negative': _signed_word(box_result) < 0}
    d3_new = (d2_orig - box_result) & 0xFFFF                      # 00BC18/00BC1A: sub.w d2,d5; move.w d5,d3
    return {**common, 'box_result': box_result, 'd3': d3_new, 'branch': 'positive',
            'x_op': ('sub', d2_orig, box_result)}


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
    # 013264's own stores (AWARD, a consumed slot, a cue) already landed via the real jsr, regardless
    # of what this routine's own tail below does with the result -- apply them unconditionally, the
    # way the ROM's own control flow already has by the time it reaches the tst.w d4 that follows.
    stores.update(collected['stores'])
    d3 = collected['stores'].get(AWARD, (read(AWARD, 2), 2))[0]     # AWARD, just stored by collect()

    if collected['arm'] == 'unrecovered':
        # code -4 and below: 013264's own cascade falls straight into 013316 (grid_inverse_award)
        # before EVER reaching 00BA8E's own tst.w d4 -- one activation of the same jsr.  d3 (BIG_VALUE)
        # is already set above; only the sound-off debris burst is witnessed (013264's own gate proved
        # it), so the sound-on and pool-exhausted arms still decline.
        inverse = grid_inverse_award(read, scan['after_code'])
        result['inverse'] = inverse
        if inverse['arm'] != 'debris':
            return {**result, 'arm': 'found-code-unrecovered', 'd3': d3}
        stores.update(inverse['stores'])

    if collected['d4'] != 0:
        # special-1's own extra step (00BBDE-00BBE2): a shared timer word is decremented by the box's
        # own d2 residue; only when that goes negative does the ROM fall into a further, unrecovered
        # call (jsr 011540) instead of re-joining the common tail every other collect() result reaches.
        timer = read(SPECIAL_TIMER, 2)
        new_timer = (timer - d2_after_zone) & 0xFFFF
        stores[SPECIAL_TIMER & 0xFFFFFF] = (new_timer, 2)
        result['special_timer'] = new_timer
        if _signed_word(new_timer) < 0:
            return {**result, 'arm': 'found-special-timer', 'd3': d3}   # jsr 011540: unrecovered, unwitnessed

    scale_level = read(AWARD_SCALE_LEVEL, 2)
    if scale_level != 0:
        # 00BBEA/00BBEE: an alternate, RAM-only derivation of (box_result, d3) -- not a call into any
        # message system (the ROM here is straight-line arithmetic, no bsr/jsr at all) -- that rejoins
        # the SAME found-sound/found-bare/found-effect tail below at its own entry points.
        scaled = _scaled_box_result(d2_after_zone, d3, scale_level)
        result['scale_level'], result['scaled'] = scale_level, scaled
        box_result, d3, x_op = scaled['box_result'], scaled['d3'], scaled['x_op']
    else:
        box_result = (d2_after_zone - d3) & 0xFFFF
        x_op = ('sub', d2_after_zone, d3)
    result['x_op'] = x_op
    # bmi.b $bc24 (box_result<0), when NOT taken, falls straight into bne.b $bc4e (box_result!=0);
    # when THAT is also not taken (box_result==0) execution falls through to the very next instruction
    # in memory, which is $bc24 itself -- box_result<=0 is one arm, not two: the ROM's own fall-through
    # reaches the sound-cue code either way.  The scaled path reaches the very same 00BC24 (or 00BC44/
    # 00BC56 through 00BC4E) by its own bmi.b/beq.b pair at 00BC14/00BC16 -- same test, same targets.
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
    # mask -- so the mask comes from the HALVED value, not the size copy itself.  When the mask
    # collapses to zero (00BC66/00BC84's own andi.w result), the ROM does not use it: it reloads D4
    # with a fixed 0x10 first (moveq #$10,d4) before the same subq.w #1,d4 -- a real, bounded default,
    # not a decline (00BC6A/00BC90's own bne.b falling through instead of being taken).
    half_x = (_signed_word(size_x) >> 1) & 0xFFFF
    half_y = (_signed_word(size_y) >> 1) & 0xFFFF
    mask_x = (half_x & 0xFFF0) - 1 if (half_x & 0xFFF0) else 0xF
    mask_y = (half_y & 0xFFF0) - 1 if (half_y & 0xFFF0) else 0xF
    default_mask_x = (half_x & 0xFFF0) == 0
    default_mask_y = (half_y & 0xFFF0) == 0
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
    # The second draw's own negative branch (00BC9E) mirrors the first's exactly: subtract the jitter
    # instead of adding it -- not a decline, the same shape dx_negative already models for X.
    jitter_y = dy & mask_y
    py_base = ((d1 & 0xFFFF) + half_y) & 0xFFFF   # the add.w/sub.w's own left operand (X's own source
                                                    # when the effect pool turns out full: no addq runs)
    py = (py_base - jitter_y if dy_negative else py_base + jitter_y) & 0xFFFF

    pool_x = (px - 8 - read(CAMERA_X, 2)) & 0xFFFF
    pool_y = (py - 8 - read(CAMERA_Y, 2)) & 0xFFFF
    added = effect_pool_add(read, pool_x, pool_y, 0, 0)
    result['effect'] = added
    stores.update(added['stores'])
    return {**result, 'arm': 'found-effect', 'd3': d3, 'box_result': box_result, 'stores': stores, 'd2': box_result,
            'px': px, 'py': py, 'py_base': py_base, 'jitter_y': jitter_y, 'dx_negative': dx_negative,
            'dy_negative': dy_negative, 'default_mask_x': default_mask_x, 'default_mask_y': default_mask_y,
            'pool_x': pool_x, 'pool_y': pool_y, 'mask_x': mask_x, 'mask_y': mask_y}


# --- 013316: the grid inverse and debris burst (continuation of 013264's code -4 and below) ---
#
# Converts the pickup grid byte's own address back to a world position (the
# grid inverse: offset // 48 is the row, offset % 48 the column, each *8 for
# pixels, plus the camera), then either an immediate fixed award when sound
# is off... no: on (0x32, GRID_CODE_AWARD), rts -- or (sound off, the only
# witnessed arm) a bounded debris burst: up to DEBRIS_PARTICLES slots of a
# shared 80-slot pool (DEBRIS_POOL, the same "unrolled test count" shape
# 00932C's own pool shares, but the scan position carries over slot to slot
# instead of restarting), each filled with the position, a table-driven
# offset word (DEBRIS_TABLE, ROM, one entry per particle) and a randomised
# impact cue via the already-recovered next_random.  A rate gate
# (DEBRIS_RATE_FLAG/DEBRIS_RATE_COUNTER) can decline the whole burst before
# it starts, or (once per particle) arm a rate limit for future calls; every
# recording's own DEBRIS_RATE_FLAG is already negative at entry and none of
# them ever flips it, so only the "already limited" shape is witnessed.
DEBRIS_POOL = 0xFFFF123E
DEBRIS_POOL_STRIDE = 6
DEBRIS_POOL_COUNT = 80                   # 0x4F + 1
DEBRIS_PARTICLES = 8
DEBRIS_TABLE = 0x0134EA                  # ROM: one word per particle
DEBRIS_RATE_FLAG = 0xFFFFEF5E            # word: zero or (rare) unwitnessed-positive skip the burst outright
DEBRIS_RATE_COUNTER = 0xFFFFEF62         # word: >= DEBRIS_RATE_LIMIT also skips it
DEBRIS_RATE_LIMIT = 0xBE
DEBRIS_RATE_TIMER = 0xFFFFEF48           # word: set to -10 the first time a particle arms the rate limit
GRID_CODE_AWARD = 0x32                   # the sound-on arm's own fixed award
DEBRIS_CUE_BASE = 0x58                   # each particle's own impact cue: (draw & 7, wrapped into 0-5) + this


def _signed_long(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _truncating_divmod(dividend, divisor):
    """DIVS.W: signed division truncating toward zero (Python's // floors instead)."""
    quotient = abs(dividend) // divisor
    if (dividend < 0) != (divisor < 0):
        quotient = -quotient
    return quotient, dividend - quotient * divisor


def grid_inverse_position(read, a0):
    """013316's own head: the grid byte's address, inverted back to a world position."""
    offset = _signed_long((a0 - PICKUP_GRID) & 0xFFFFFFFF)
    row, col = _truncating_divmod(offset, PICKUP_GRID_ROW)
    x = (((col << 3) & 0xFFFF) + read(CAMERA_X, 2)) & 0xFFFF
    y = (((row << 3) & 0xFFFF) + read(CAMERA_Y, 2)) & 0xFFFF
    return x, y


def _debris_scan(read, start_index):
    """One slot of the shared, carrying-over pool scan; ``None`` if the pool is exhausted."""
    for index in range(start_index, DEBRIS_POOL_COUNT):
        address = (DEBRIS_POOL + DEBRIS_POOL_STRIDE * index) & 0xFFFFFFFF
        if _signed_word(read(address & 0xFFFFFF, 2)) < 0:
            return index, address
    return None, None


def grid_inverse_award(read, after_code):
    """013316: the grid inverse and (sound off) the debris burst; the sound-on arm is unwitnessed."""
    x, y = grid_inverse_position(read, after_code)
    if read(SOUND_ON, 2):
        return {'arm': 'grid-code', 'x': x, 'y': y, 'stores': {AWARD: (GRID_CODE_AWARD, 2)}, 'd4': 0}

    rate_flag = read(DEBRIS_RATE_FLAG, 2)
    if rate_flag != 0 and read(DEBRIS_RATE_COUNTER, 2) >= DEBRIS_RATE_LIMIT:
        return {'arm': 'debris-limited', 'x': x, 'y': y, 'stores': {}, 'd4': 0}

    stores, cursor, particles = {}, 0, []
    live_cursor = read(RANDOM_CURSOR & 0xFFFFFF, 2)

    def draw(address):
        nonlocal live_cursor
        result = next_random(lambda a, s: live_cursor if (a & 0xFFFFFF) == (address & 0xFFFFFF) else read(a, s))
        live_cursor = result['stores'][RANDOM_CURSOR & 0xFFFFFF][0]
        return result['value']

    for slot in range(DEBRIS_PARTICLES):
        index, address = _debris_scan(read, cursor)
        if index is None:
            stores[RANDOM_CURSOR & 0xFFFFFF] = (live_cursor, 2)
            return {'arm': 'debris-exhausted', 'x': x, 'y': y, 'stores': stores, 'd4': 0, 'particles': particles,
                    'skipped': index}   # a bounded pool with no free slot left: not witnessed by any recording
        skipped = index - cursor
        table_value = read(DEBRIS_TABLE + 2 * slot, 2)
        drawn = draw(RANDOM_CURSOR)
        masked = drawn & 7
        cue = (((masked - 6) if masked >= 6 else masked) + DEBRIS_CUE_BASE) & 0xFFFF
        stores[address & 0xFFFFFF] = (x, 2)
        stores[(address + 2) & 0xFFFFFF] = (y, 2)
        stores[(address + 4) & 0xFFFFFF] = (table_value, 2)
        stores[SOUND_CUE] = (cue, 2)
        particles.append({'index': index, 'address': address, 'skipped': skipped, 'table_value': table_value,
                          'drawn': drawn, 'masked': masked, 'high_range': masked >= 6, 'cue': cue})
        cursor = index + 1
        if rate_flag == 0:
            # The rate gate arms itself the first time it is found clear -- unwitnessed by every
            # recording (DEBRIS_RATE_FLAG is already nonzero at entry on all of them).
            stores[RANDOM_CURSOR & 0xFFFFFF] = (live_cursor, 2)
            return {'arm': 'debris-arms-rate-limit', 'x': x, 'y': y, 'stores': stores, 'd4': 0,
                    'particles': particles}
    stores[RANDOM_CURSOR & 0xFFFFFF] = (live_cursor, 2)
    return {'arm': 'debris', 'x': x, 'y': y, 'stores': stores, 'd4': 0, 'particles': particles}


# --- 010CD2: the pickup probe (a caller-supplied record's own camera-relative call) ---
#
# Adds the camera to (D0,D1), calls the already-recovered pickup_check with the record's own D2 (at
# A5+8), writes the result back to A5+8, and marks A5+4 (-1) when it came back negative.  The camera
# add here and pickup_check's own subtract of the same words cancel exactly (mod 0x10000): the net
# position pickup_check computes from is D0/D1 exactly as passed in here.
def pickup_probe(read, d0, d1, record_d2):
    """010CD2: a caller-supplied record's own probe into the pickup check."""
    x = (d0 + read(CAMERA_X, 2)) & 0xFFFF
    y = (d1 + read(CAMERA_Y, 2)) & 0xFFFF
    check = pickup_check(read, x, y, record_d2)
    return {'x': x, 'y': y, 'check': check, 'negative': _signed_word(check['d2']) < 0}


# --- 008222/00837E: the movement-cluster contact search over the three collectible lists -----
#
# The blocker docs/gods/blockers/2026-09-17-008222.md (Decision, 18 September): reached from
# inside the player state machine's own movement-cluster handlers (state 1, state 0, state 24 and
# others), a reentrancy-guarded search over the SAME three collectible lists ``GROUP_TABLES`` names
# above (their own leading count word, entries starting two bytes later) -- but read here as up to
# three consecutive 0x18-byte "hit records" per list, each carrying three status words (offsets
# 0/8/0x10) rather than the 8-byte item slots ``collect`` above reads from the identical bytes; the
# two views coexist because 008222 only ever looks at the first three records of a list, well inside
# ``collect``'s own nine-slot span.  Each of the three independent sub-passes is gated by its own
# list's count word (negative skips the sub-pass outright) and looks up one item record's own word at
# ``+0xA`` (``ITEM_VALUE``'s neighbour, named ``ITEM_CONTACT_WORD`` here): sub-pass 1 indexes the flat
# item-record array directly (``count * 0x50`` bytes past ``ITEM_RECORDS_BASE``, the same address
# ``pickups.ITEM_RECORDS`` -- the ROM pointer table -- points its own first entry at); sub-passes 2
# and 3 go through that pointer table instead (``ITEM_RECORDS[count]``) and additionally abandon the
# whole sub-pass when the word comes back negative.  ITEM_CONTACT_WORD then doubles as a retry budget
# (decremented after each occupied entry; hitting exactly zero abandons the sub-pass before its own
# third, unrolled attempt) and, on a match, a latch selector: sub-pass 1 sets ``CONTACT_LATCH``
# unconditionally when its own ITEM_CONTACT_WORD is 1 (never reads the latch first, since nothing
# could have set it yet); sub-passes 2 and 3 do the mirror image -- when THEIR OWN ITEM_CONTACT_WORD
# is 1, they read the latch first and discard the match entirely (no store, no "found" contribution)
# if it is already set, and never set it themselves either way.  A found-and-stored entry's own
# address and the attempt's own index constant (1/4/7 for sub-pass 1, 0xA/0xD/0x10 for sub-pass 2,
# 0x13/0x16/0x19 for sub-pass 3 -- a fixed per-sub-pass base plus 3 per retry, not the attempt's own
# 0-based position) land in one of the three slot pairs.  The overall result (D0/D3) is 0 ("found")
# if ANY sub-pass stored a match, 1 otherwise -- a sub-pass finding but being latch-discarded does
# NOT count.  All three sub-passes always run (a match in an earlier one does not skip a later one).
REENTRANCY_GUARD = 0xFFFFF1A2                          # word: nonzero while a search is already in progress
CONTACT_LATCH = 0xFFFFF23C                              # word: cleared at entry; set once, by sub-pass 1 only
CONTACT_SLOTS = (0xFFFFF374, 0xFFFFF378, 0xFFFFF37C)    # per sub-pass: the found entry's own address (long)
CONTACT_INDEX_WORDS = (0xFFFFF36E, 0xFFFFF370, 0xFFFFF372)   # per sub-pass: the found attempt's own index
CONTACT_ENTRY_BASE_OFFSET = 2                           # entries start two bytes past the list's count word
CONTACT_ENTRY_STRIDE = 0x18                             # bytes between consecutive attempts in one sub-pass
CONTACT_STATUS_OFFSETS = (0, 8, 0x10)                   # an entry's own three status words, tested in order
CONTACT_ITEM_RECORDS_BASE = 0xFFFFF552                  # sub-pass 1's own direct arithmetic (== ITEM_RECORDS[0])
CONTACT_ITEM_RECORD_STRIDE = 0x50                       # matches ITEM_RECORD_COUNT's own 0x50-byte records
CONTACT_WORD_OFFSET = 0xA                               # ITEM_VALUE's neighbour: retry budget and latch selector
CONTACT_INITIAL_INDEX = (1, 0xA, 0x13)                  # each sub-pass's own first-attempt index constant
CONTACT_INDEX_STEP = 3                                  # added to the index per retry
CONTACT_MAX_ATTEMPTS = 3


def _contact_probe(read, entry_addr):
    """00837E: an entry's own three status words (offsets 0/8/0x10), tested in ROM order; the first
    nonzero one stops the check short ('occupied', naming which offset stopped it -- the boundary's
    own cost varies with it); all three zero is a match ('free')."""
    for offset in CONTACT_STATUS_OFFSETS:
        if read((entry_addr + offset) & 0xFFFFFF, 2) != 0:
            return {'result': 'occupied', 'stop_offset': offset}
    return {'result': 'free', 'stop_offset': None}


def _contact_subpass(read, sub_index, list_table, latch_set):
    """One of 008222's own three sub-passes over ``list_table`` (one of ``GROUP_TABLES``).

    ``sub_index`` (0/1/2) selects sub-pass 1's own direct item-record arithmetic versus sub-passes
    2/3's indirect read through ``ITEM_RECORDS``; ``latch_set`` is ``CONTACT_LATCH``'s value as of
    entering this sub-pass (only sub-pass 1 ever writes it, so 2 and 3 only ever read it).

    Returns the sub-pass's own arm (``'skip'``: the count word was negative; ``'skip-negative'``:
    sub-pass 2/3 only, ITEM_CONTACT_WORD was negative; ``'not-found'``: every attempt was occupied,
    or the retry budget ran out; ``'found'``: a match was stored; ``'gated'``: a match was found but
    discarded by the latch), the attempts made (each a probe result), the stores, whether this
    sub-pass's own find (if any) was stored, and whether it set the latch (sub-pass 1 only).

    Also carries what the boundary needs for the exit register file and CCR, since this sub-pass is
    the only place that knows which of its own instructions ran: ``a2_exit``/``d4_exit``/
    ``d5_exit``/``d6_exit`` (``None`` when this sub-pass left that register untouched -- the 'skip'
    arm touches none of them) and ``last_x``, the ``(op, left, right)`` of the last ADD/ADDQ/SUB/
    SUBQ/ASL this sub-pass executed (also ``None`` on 'skip'; every other instruction in the routine,
    including every one inside the shared probe ``00837E``, leaves X alone).
    """
    # 008230 (HEAD) and each sub-pass's own setup (SP23_SETUP) clear this sub-pass's own slot
    # unconditionally, BEFORE the count test -- a later find overwrites it, but every other arm
    # (including 'skip') leaves the clear as the slot's own final value.
    base_stores = {CONTACT_SLOTS[sub_index] & 0xFFFFFF: (0, 4)}
    count = read(list_table & 0xFFFFFF, 2)
    entries_base = (list_table + CONTACT_ENTRY_BASE_OFFSET) & 0xFFFFFFFF
    if _signed_word(count) < 0:
        return {'arm': 'skip', 'attempts': [], 'stores': base_stores, 'stored': False, 'sets_latch': False,
                'count': count, 'a2_exit': None, 'd4_exit': None, 'd5_exit': None, 'd6_exit': None,
                'last_x': None}

    count16 = count & 0xFFFF
    if sub_index == 0:
        # d4 = count<<4, doubled twice more (<<6), then added to its own pre-doubled copy (d6, <<4):
        # d4 = count<<6 + count<<4 = count*0x50; a2 itself stays CONTACT_ITEM_RECORDS_BASE throughout
        # (d4 is only ever an INDEX register in the "$a(a2,d4.w)" read, never added into a2 itself).
        shifted = (count16 << 4) & 0xFFFF
        doubled = (shifted << 2) & 0xFFFF
        lookup_x = ('add', doubled, shifted)
        record_addr = (CONTACT_ITEM_RECORDS_BASE + _signed_word((count16 * CONTACT_ITEM_RECORD_STRIDE) & 0xFFFF)) & 0xFFFFFFFF
        a2_lookup = CONTACT_ITEM_RECORDS_BASE
    else:
        # d5 = count, doubled twice (<<2) as the pointer table's own byte index; a2 becomes the
        # record's own address once the indirection (movea.l) runs.
        doubled_once = (count16 << 1) & 0xFFFF
        lookup_x = ('add', doubled_once, doubled_once)
        pointer_addr = (ITEM_RECORDS + _signed_word((count16 * 4) & 0xFFFF)) & 0xFFFFFF
        record_addr = read(pointer_addr, 4) & 0xFFFFFFFF
        a2_lookup = record_addr
    contact_word = read((record_addr + CONTACT_WORD_OFFSET) & 0xFFFFFF, 2)
    word16 = contact_word & 0xFFFF

    if sub_index != 0 and _signed_word(contact_word) < 0:
        return {'arm': 'skip-negative', 'attempts': [], 'stores': base_stores, 'stored': False, 'sets_latch': False,
                'count': count, 'record_addr': record_addr, 'contact_word': contact_word,
                'a2_exit': a2_lookup, 'd4_exit': word16, 'd5_exit': doubled_once, 'd6_exit': word16,
                'last_x': lookup_x}

    d4_track, d5_track, last_x = word16, CONTACT_INITIAL_INDEX[sub_index], lookup_x
    attempts = []
    found_attempt = None
    for attempt in range(CONTACT_MAX_ATTEMPTS):
        entry_addr = (entries_base + CONTACT_ENTRY_STRIDE * attempt) & 0xFFFFFFFF
        index_value = d5_track & 0xFFFF
        probe = _contact_probe(read, entry_addr)
        step = {'attempt': attempt, 'entry': entry_addr, 'index': index_value, **probe}
        attempts.append(step)
        if probe['result'] == 'free':
            found_attempt = step
            break
        if attempt < CONTACT_MAX_ATTEMPTS - 1:
            pre_d4 = d4_track
            d4_track = (d4_track - 1) & 0xFFFF
            last_x = ('sub', pre_d4, 1)
            step['budget_after'] = d4_track
            if d4_track == 0:
                break   # the retry budget ran out before the last unrolled attempt
            pre_d5 = d5_track
            d5_track = (d5_track + CONTACT_INDEX_STEP) & 0xFFFF
            last_x = ('add', pre_d5, CONTACT_INDEX_STEP)

    stores, stored, sets_latch, gated = dict(base_stores), False, False, False
    if found_attempt is not None:
        if sub_index == 0:
            stores[CONTACT_SLOTS[0] & 0xFFFFFF] = (found_attempt['entry'], 4)
            stores[CONTACT_INDEX_WORDS[0] & 0xFFFFFF] = (found_attempt['index'], 2)
            stored = True
            if word16 == 1:
                stores[CONTACT_LATCH & 0xFFFFFF] = (1, 2)
                sets_latch = True
        elif word16 == 1 and latch_set:
            gated = True
        else:
            stores[CONTACT_SLOTS[sub_index] & 0xFFFFFF] = (found_attempt['entry'], 4)
            stores[CONTACT_INDEX_WORDS[sub_index] & 0xFFFFFF] = (found_attempt['index'], 2)
            stored = True

    arm = 'found' if stored else ('gated' if gated else 'not-found')
    return {'arm': arm, 'attempts': attempts, 'stores': stores, 'stored': stored, 'sets_latch': sets_latch,
            'count': count, 'record_addr': record_addr, 'contact_word': contact_word,
            'found_attempt': found_attempt, 'a2_exit': a2_lookup, 'd4_exit': d4_track,
            'd5_exit': d5_track & 0xFFFF, 'd6_exit': word16, 'last_x': last_x}


def contact_search(read):
    """008222 (with its helper 00837E): the movement-cluster hit-list search.

    Returns the reentrancy arm (``'busy'`` when the guard was already set: no RAM touched but the
    guard), or ``'ran'`` with the three sub-passes' own results, the combined stores, and D0/D3
    (0 if any sub-pass stored a match, 1 otherwise).
    """
    if read(REENTRANCY_GUARD, 2) != 0:
        return {'arm': 'busy', 'd0': 1, 'stores': {}, 'subpasses': None}

    stores = {REENTRANCY_GUARD & 0xFFFFFF: (1, 2), CONTACT_LATCH & 0xFFFFFF: (0, 2)}
    latch_set = False
    subpasses = []
    any_stored = False
    # HEAD's own "moveq #1,d5" (the reentrancy guard just cleared) leaves d5=1 even if every
    # sub-pass below is 'skip' and never touches it again; a2/d4/d6 have no such HEAD setter.
    a2_exit = d4_exit = d6_exit = last_x = None
    d5_exit = CONTACT_INITIAL_INDEX[0]
    for sub_index, list_table in enumerate(GROUP_TABLES):
        result = _contact_subpass(read, sub_index, list_table, latch_set)
        subpasses.append(result)
        stores.update(result['stores'])
        if result['sets_latch']:
            latch_set = True
        if result['stored']:
            any_stored = True
        # Each sub-pass always runs, so whichever most recently touched a register is what is live
        # at the end -- sub-pass 3's own value wins if it ran at all, sub-pass 2's if 3 was 'skip', etc.
        if result['a2_exit'] is not None:
            a2_exit = result['a2_exit']
        if result['d4_exit'] is not None:
            d4_exit = result['d4_exit']
        if result['d5_exit'] is not None:
            d5_exit = result['d5_exit']
        if result['d6_exit'] is not None:
            d6_exit = result['d6_exit']
        if result['last_x'] is not None:
            last_x = result['last_x']
    d0 = 0 if any_stored else 1
    return {'arm': 'ran', 'd0': d0, 'stores': stores, 'subpasses': subpasses, 'found': any_stored,
            'a2_exit': a2_exit, 'd4_exit': d4_exit, 'd5_exit': d5_exit, 'd6_exit': d6_exit, 'last_x': last_x}


# --- 012DA0/012E5A: the movement-cluster contact consumers (the item type dispatch) -------------
#
# Once contact_search has populated up to three of its own CONTACT_SLOTS, these two near-identical
# siblings consume them, one call per movement-cluster state activation (not necessarily the SAME
# tick contact_search ran: a slot's own value persists in FFFFF374/F378/F37C until overwritten by
# a later search or consumed here -- an ordering fact, not modelled further).  For each populated
# slot, in order: re-read the SAME list's own count word (it may have changed since the search
# ran), look up the item record it names (through ITEM_RECORDS, exactly as contact_search's own
# sub-passes 2/3 do) and its own type field -- offset 0x14 for 012DA0 (ITEM_TYPE_PRIMARY), 0x10 for
# 012E5A (ITEM_TYPE_SECONDARY) -- then jump through a second ROM table (012C3E) into a per-type
# handler.  Slots 1 and 2 (FFFFF374/F378) are reached by ``bsr``: the handler's own `rts` lands back
# after it, continuing to the next slot.  Slot 3 (FFFFF37C) is reached by a tail JUMP with no bsr,
# so the handler's own `rts` ends the WHOLE activation directly (0048B4's shape, one level further
# removed) -- a clean 'skip3' arm (rts immediately) only when slot 3 is itself empty.
#
# Every witnessed type handler (012DA0: 1, 3, 7, 9; 012E5A: 0, 2 -- census over fb408bc75597,
# --classifier entry, no overflow at 10/8 real path classes) reduces to a common position
# computation (the slot's own default grid-relative pair, or a caller-tracked one when
# CONTACT_ACTIVE_SELECTOR names this slot) plus one of two small bodies: the ordinary bounded
# append (up to three (d4,d3,d5,const) quadruples into the hit record's own three status groups --
# the SAME offsets contact_search's own probe tested -- plus the item record's own claim flag), or
# the SAME append with an extra per-attempt write into CONTACT_POOL_TABLE; 012DA0's own bodies
# always use the constants (1, 0, 2) and claim flag 1, 012E5A's own always (4, 3, 5) and -1 --
# a fact of which ORIGINAL routine reached the body, not of the type value.  Type 9 (012DA0 only)
# is a wholly separate single-write handler, its own small state block armed once.  Every OTHER
# type (real ROM code behind the same 012C3E table) is unwitnessed by any recording and declines
# by its own numeric type value.
ITEM_RANGE_LOW = 0x6                                     # record field: the group count's low end (ITEM_VALUE, +8, is the high end)
ITEM_TYPE_PRIMARY, ITEM_TYPE_SECONDARY = 0x14, 0x10       # record fields: 012DA0's own and 012E5A's own dispatch selector
ITEM_CLAIM_FLAG = 0xE                                     # record field: set to the body's own claim value once appended
CONTACT_ACTIVE_SELECTOR = 0xFFFFF154                      # word: 0/1/2 -- which slot gets the tracked position instead of the grid one
CONTACT_TRACK_X, CONTACT_TRACK_Y = 0xFFFFF148, 0xFFFFF14A  # words: the tracked position the active slot uses instead of the grid one
CONTACT_POOL_INDEX_BASE = 0xFFFFF380                      # word: subtracted from the contact index (FFFF36E et al) for the pool table slot
CONTACT_POOL_TABLE = 0xFFFF0436                           # words: one sentinel (0xFFFA) per append, the pool body's own arm
MOVEMENT_SOUND_CUE = 0xFFFFFDF6                            # word: two bytes past SOUND_COMMAND/SOUND_CUE -- a separate field of the same block
CONTACT_BODY_CUE = 0x35                                    # the ordinary bodies' own sound cue
TYPE9_CUE = 0x5F                                           # type 9's own sound cue
TYPE9_FLAG, TYPE9_COUNT, TYPE9_CURSOR = 0xFFFFF35E, 0xFFFFF35C, 0xFFFFF360  # type 9's own small state block

# Per originating routine (0 = 012DA0, 1 = 012E5A): the bounded body's own three group constants
# and the claim value written to the matched item record's own ITEM_CLAIM_FLAG.
_BODY_CONSTS = {0: (1, 0, 2), 1: (4, 3, 5)}
_BODY_CLAIM = {0: 1, 1: 0xFFFF}

# (type value -> (d3_delta, d5_delta, pooled)) for each originating routine's own witnessed types;
# d3_delta/d5_delta are the type's own header adjustment (the shared body itself always subtracts 6
# from d5 first when pooled=True, on top of these).  Type 9 (routine 0 only) is not in this table:
# it is a standalone shape, handled separately.
TYPE_HEADERS = {
    0: {1: (0x10, -0xC, False), 7: (0, -4, False), 3: (0, 0, True)},
    1: {0: (0, -0xC, False), 2: (0x10, 0, True), 6: (-0x18, -4, False)},
}


def _consume_position(read, active_index):
    """012DA0/012E5A's own shared per-slot head: the default is a fixed grid-relative pair
    (GRID_X, GRID_Y + 0x18); when CONTACT_ACTIVE_SELECTOR names this slot (0/1/2), it is the
    tracked position instead (8 + CONTACT_TRACK_X, 0x10 + CONTACT_TRACK_Y)."""
    from .grid import GRID_X, GRID_Y
    default_x = read(GRID_X, 2)
    default_y = (read(GRID_Y, 2) + 0x18) & 0xFFFF
    if read(CONTACT_ACTIVE_SELECTOR, 2) == active_index:
        return (8 + read(CONTACT_TRACK_X, 2)) & 0xFFFF, (0x10 + read(CONTACT_TRACK_Y, 2)) & 0xFFFF
    return default_x, default_y


def _item_lookup(read, list_table):
    """Both consumers' own shared head, per populated slot: re-read the list's own count word and
    look the item record up through ITEM_RECORDS -- exactly contact_search's own sub-passes 2/3."""
    count = read(list_table & 0xFFFFFF, 2)
    pointer_addr = (ITEM_RECORDS + _signed_word((count * 4) & 0xFFFF)) & 0xFFFFFF
    record = read(pointer_addr, 4) & 0xFFFFFFFF
    return count, record


def _append_groups(read, a3, d3, d5, d4, record, consts, claim, pooled):
    """The shared bounded body (012DA0: 0131D2/012F0E; 012E5A: 013222/012F6E): up to three
    (d4, d3, d5, const) quadruples into the hit record's own three status groups (offsets 0/8/0x10,
    contact_search's own probe offsets), the item record's own claim flag set once, and -- pooled
    bodies only -- one CONTACT_POOL_TABLE sentinel write per group, indexed by (d4 - the group's own
    running index) relative to CONTACT_POOL_INDEX_BASE.

    Returns the stores, the groups actually written (1-3) and the final d4/d6 (for cost/registers).
    """
    stores = {MOVEMENT_SOUND_CUE & 0xFFFFFF: (CONTACT_BODY_CUE, 2)}
    count = (read((record + ITEM_VALUE) & 0xFFFFFF, 2) - read((record + ITEM_RANGE_LOW) & 0xFFFFFF, 2) + 1) & 0xFFFF
    groups = []
    d6 = count
    for index, const in enumerate(consts):
        entry = (a3 + 8 * index) & 0xFFFFFFFF
        stores[entry & 0xFFFFFF] = (d4 & 0xFFFF, 2)
        stores[(entry + 2) & 0xFFFFFF] = (d3 & 0xFFFF, 2)
        stores[(entry + 4) & 0xFFFFFF] = (d5 & 0xFFFF, 2)
        stores[(entry + 6) & 0xFFFFFF] = (const & 0xFFFF, 2)
        pool_addr = None
        if pooled:
            pool_index = ((d4 - read(CONTACT_POOL_INDEX_BASE, 2) - 1) & 0xFFFF) * 2
            pool_addr = (CONTACT_POOL_TABLE + _signed_word(pool_index)) & 0xFFFFFF
            stores[pool_addr] = (0xFFFA, 2)
        groups.append({'entry': entry, 'd4': d4 & 0xFFFF, 'const': const, 'pool_addr': pool_addr})
        if index == 0:
            stores[(record + ITEM_CLAIM_FLAG) & 0xFFFFFF] = (claim & 0xFFFF, 2)
        if index == len(consts) - 1:
            break   # the ROM's own last unrolled group has no decrement/test after it at all
        d6 = (d6 - 1) & 0xFFFF
        if d6 == 0:
            break
        d4 = (d4 + 1) & 0xFFFF
    return stores, groups, d4 & 0xFFFF, d6


def _type9_handler(read, a3, d3, d5, d4):
    """012DA0's own type 9 (013194): a standalone single write, no loop, no claim flag -- its own
    small state block (TYPE9_FLAG cleared, TYPE9_COUNT set to 4, TYPE9_CURSOR set to -1) armed
    unconditionally first."""
    d3 = (d3 + 0x10) & 0xFFFF
    d5 = ((d5 - 0x20) & 0xFFFF) & 0xFFFC
    stores = {TYPE9_FLAG & 0xFFFFFF: (0, 2), TYPE9_COUNT & 0xFFFFFF: (4, 2), TYPE9_CURSOR & 0xFFFFFF: (0xFFFF, 2),
              MOVEMENT_SOUND_CUE & 0xFFFFFF: (TYPE9_CUE, 2),
              a3 & 0xFFFFFF: (d4 & 0xFFFF, 2), (a3 + 2) & 0xFFFFFF: (d3, 2), (a3 + 4) & 0xFFFFFF: (d5, 2),
              (a3 + 6) & 0xFFFFFF: (0x2F, 2)}
    return stores, d3, d5


def _consume_slot(read, routine, slot_index, list_table, slot_addr, index_word, type_field):
    """One of the up to three slots either consumer's own head processes.  Returns the arm
    ('empty', 'found' or 'unrecovered'), the type dispatched (when found) and the stores."""
    entry = read(slot_addr & 0xFFFFFF, 4) & 0xFFFFFFFF
    if entry == 0:
        return {'arm': 'empty', 'stores': {}, 'type': None}
    d4 = read(index_word & 0xFFFFFF, 2)
    d3, d5 = _consume_position(read, slot_index)
    count, record = _item_lookup(read, list_table)
    type_value = read((record + type_field) & 0xFFFFFF, 4) & 0xFFFFFFFF
    if routine == 0 and type_value == 9:
        stores, d3, d5 = _type9_handler(read, entry, d3, d5, d4)
        return {'arm': 'found', 'type': 9, 'stores': stores, 'entry': entry, 'record': record,
                'd3': d3, 'd5': d5, 'd4': d4, 'pooled': False, 'groups': None, 'cue': TYPE9_CUE}
    header = TYPE_HEADERS.get(routine, {}).get(type_value)
    if header is None:
        return {'arm': 'unrecovered', 'stores': {}, 'type': type_value}
    d3_delta, d5_delta, pooled = header
    d3 = (d3 + d3_delta) & 0xFFFF
    d5 = (d5 + d5_delta) & 0xFFFF
    if pooled:
        d5 = (d5 - 6) & 0xFFFF
    consts, claim = _BODY_CONSTS[routine], _BODY_CLAIM[routine]
    stores, groups, d4_final, d6_final = _append_groups(read, entry, d3, d5, d4, record, consts, claim, pooled)
    return {'arm': 'found', 'type': type_value, 'stores': stores, 'entry': entry, 'record': record,
            'd3': d3, 'd5': d5, 'd4': d4_final, 'pooled': pooled, 'groups': groups, 'cue': CONTACT_BODY_CUE,
            'd6': d6_final}


def contact_consume(read, routine):
    """012DA0 (routine 0) / 012E5A (routine 1): the movement-cluster contact consumer.

    Processes CONTACT_SLOTS 1 and 2 (returning normally after each) then slot 3 (ending the whole
    activation, a tail jump with no bsr).  Returns the three slots' own results and which one (if
    any) ended the activation via the tail jump.
    """
    lists = (GROUP_TABLES[0], GROUP_TABLES[1], GROUP_TABLES[2])
    slots = (CONTACT_SLOTS[0], CONTACT_SLOTS[1], CONTACT_SLOTS[2])
    indices = (CONTACT_INDEX_WORDS[0], CONTACT_INDEX_WORDS[1], CONTACT_INDEX_WORDS[2])
    type_field = ITEM_TYPE_PRIMARY if routine == 0 else ITEM_TYPE_SECONDARY
    results = []
    for slot_index in range(3):
        result = _consume_slot(read, routine, slot_index, lists[slot_index], slots[slot_index],
                                indices[slot_index], type_field)
        results.append(result)
        if slot_index == 2:
            break
        if result['arm'] == 'unrecovered':
            break
    return {'slots': results, 'tail_slot': len(results) - 1}


# --- 012C80: the pickup award group dispatch (with its own chain, 012D30/012A3E/012A34/011468) -----
#
# Reached from 003480's own '>= 0xC0' arm (`docs/gods/blockers/2026-09-19-003480.md`) and from a
# second, still-unrecovered caller this session's own census found (return site 00874E, distinct from
# 003480's own 003638) -- D2 is an item id, the SAME 0-10 domain `collect`/`contact_search` already
# use (`ITEM_RECORDS`).  Two top-level arms, both ending by recomputing TIME_MARK:
#
#  'already-active': D2 already names one of the three GROUP_TABLES' own active-id words (a plain
#    cmp.w against each, in order) -- the item's own per-item RAM record (`ITEM_RECORDS[d2]`, the SAME
#    record `contact_search`/`contact_consume` already use) has its own ITEM_VALUE (+8) incremented by
#    one, then `time_mark_cascade` recomputes TIME_MARK and the routine returns directly.
#  'register': D2 names an item not currently tracked by any group -- `select_group_slot` (012D30)
#    picks a group (declining a real 'contested' evict-the-lower-value tie-break arm, and a real
#    generic "GROUP_TABLES[2] empty" arm, that no recording enters), the chosen table's own active-id
#    word is set to D2, `register_item` (012A3E) re-arms the item's own record (ITEM_VALUE reset to
#    ITEM_RANGE_LOW), the chosen table's own extended slot area is cleared (`group_extended_clear`,
#    012A34), `time_mark_cascade` recomputes TIME_MARK, and `leading_group_recheck` (011468) re-tests
#    SPECIAL_TIMER -- negative on every witnessed occurrence; its own non-negative arm (a further
#    TIME_MARK/FFFFF154 derivation over the active groups) is real ROM no recording enters.
#
# Pure functions of `read(address, size)`; no cycles, CCR, stack or registers.
GROUP_OVERRIDE_ID = 2                  # item id 2 always hard-codes group 2 (012D3E's own d3==2 test)
GROUP_OVERRIDE_POOL_BASE = 0x12        # written to CONTACT_POOL_INDEX_BASE (FFFFF380) on the override arm
ITEM_REGISTER_RESET = 0x4              # record field: cleared by register_item; no further evidence of its own role
ITEM_FIELD_TEST = 0x2                  # record field: compared to 3 by register_item; never witnessed equal (the clear declines)
GROUP_SLOT_CLEAR_WORDS = 0x48          # 012A34's own dbra count: 72 words (0x90 bytes) cleared from the chosen table's own +2,
                                        # well past the nine 8-byte slots (0x48 bytes) GROUP_SIZE/SLOT_SIZE name -- the further
                                        # 0x48 bytes are real, traced, unexplained by any field this module names; for group 2
                                        # this clear runs past the table array's own end into whatever RAM follows, every time.
GROUP_EIGHT_TEST = 8                   # register_item's own triple compare (EF8C/F01E/F0B0 == 8): never witnessed true


def select_group_slot(read, item_id):
    """012D30: choose which GROUP_TABLES slot registers ``item_id`` (only called once the caller has
    already confirmed ``item_id`` matches none of the three groups' own current active ids).

    ``item_id == GROUP_OVERRIDE_ID`` (2) always hard-codes group 2 and arms CONTACT_POOL_INDEX_BASE --
    a real, witnessed ROM special case.  Otherwise: group 0 is chosen when the item's own contact
    record's first word (``ITEM_RECORDS[item_id]``) is zero; group 1 when GROUP_TABLES[1]'s own
    active-id word is negative (empty) -- both witnessed.  Group 2 by the SAME "negative active id"
    test, and the further "both occupied: evict whichever of GROUP_TABLES[1]/[2]'s own item records
    has the lower ITEM_VALUE" tie-break (0x12D58-0x12D82), are real ROM code no recording enters:
    returned as their own arms so the boundary can decline them by name, not modelled further.
    """
    record = read(ITEM_RECORDS + _signed_word(4 * item_id), 4) & 0xFFFFFFFF
    if item_id == GROUP_OVERRIDE_ID:
        return {'arm': 'override', 'group': 2, 'table': GROUP_TABLES[2], 'record': record,
                'stores': {CONTACT_POOL_INDEX_BASE & 0xFFFFFF: (GROUP_OVERRIDE_POOL_BASE, 2)}}
    if (read(record & 0xFFFFFF, 2) & 0xFFFF) == 0:
        return {'arm': 'group0', 'group': 0, 'table': GROUP_TABLES[0], 'record': record, 'stores': {}}
    if _signed_word(read(GROUP_TABLES[1], 2)) < 0:
        return {'arm': 'group1', 'group': 1, 'table': GROUP_TABLES[1], 'record': record, 'stores': {}}
    if _signed_word(read(GROUP_TABLES[2], 2)) < 0:
        return {'arm': 'group2-empty', 'group': 2, 'table': GROUP_TABLES[2], 'record': record, 'stores': {}}
    return {'arm': 'contested', 'group': None, 'table': None, 'record': record, 'stores': {}}


def register_item(read, item_id):
    """012A3E: (re)arm ``item_id``'s own per-item RAM record for tracking -- ITEM_VALUE (+8) reset to
    ITEM_RANGE_LOW (+6), ITEM_REGISTER_RESET (+4) cleared, then ARRAY_GATE (FFFFEF8A) is raised
    (0xFFFF) and either left set (SPECIAL_TIMER negative AND none of the three groups' own active id
    is GROUP_EIGHT_TEST (8) -- the 'left-set' arm) or immediately cleared back to 0 (SPECIAL_TIMER
    non-negative, or one of the three DOES equal 8 -- the 'cleared' arm; both real and witnessed).
    Neither arm stops the registration itself -- ``award_group_dispatch``'s own ``leading_group_recheck``
    (011468), re-testing the SAME SPECIAL_TIMER unchanged since this read, decides whether the whole
    activation completes.
    """
    record = (CONTACT_ITEM_RECORDS_BASE + item_id * CONTACT_ITEM_RECORD_STRIDE) & 0xFFFFFFFF
    field2 = read((record + ITEM_FIELD_TEST) & 0xFFFFFF, 2) & 0xFFFF
    if field2 == 3:
        return {'arm': 'unrecovered-field2', 'record': record, 'stores': {}}
    range_low = read((record + ITEM_RANGE_LOW) & 0xFFFFFF, 2) & 0xFFFF
    stores = {(record + ITEM_REGISTER_RESET) & 0xFFFFFF: (0, 2),
              (record + ITEM_VALUE) & 0xFFFFFF: (range_low, 2)}
    timer_negative = _signed_word(read(SPECIAL_TIMER, 2)) < 0
    ids = tuple(read(table, 2) & 0xFFFF for table in GROUP_TABLES) if timer_negative else None
    cleared = (not timer_negative) or (GROUP_EIGHT_TEST in ids)
    stores[ARRAY_GATE & 0xFFFFFF] = (0, 2) if cleared else (0xFFFF, 2)
    return {'arm': 'cleared' if cleared else 'left-set', 'record': record, 'stores': stores,
            'timer_negative': timer_negative, 'ids': ids}


def group_extended_clear(table):
    """012A34: clear GROUP_SLOT_CLEAR_WORDS (0x48) words starting at ``table + SLOT_BASE`` (+2)."""
    base = (table + SLOT_BASE) & 0xFFFFFFFF
    return {(base + 2 * index) & 0xFFFFFF: (0, 2) for index in range(GROUP_SLOT_CLEAR_WORDS)}


def _tally_group(read, active_id):
    """012CD6: one group's own contribution to TIME_MARK (an unrolled, up-to-three-step accumulation
    of ITEM_RANGE_LOW, the last step carrying whatever remains of ITEM_VALUE-ITEM_RANGE_LOW
    unconditionally), or none at all when the group's own active id is negative (empty).

    Returns the amount added to TIME_MARK and ``steps`` (0 for an empty group, else 1/2/3 -- the
    boundary's own cost varies with it) for the boundary's own per-step cost table.
    """
    doubled = _signed_word((active_id & 0xFFFF) * 4)
    if doubled < 0:
        return 0, 0
    record = read(ITEM_RECORDS + doubled, 4) & 0xFFFFFFFF
    range_low = read((record + ITEM_RANGE_LOW) & 0xFFFFFF, 2) & 0xFFFF
    value = read((record + ITEM_VALUE) & 0xFFFFFF, 2) & 0xFFFF
    added = range_low
    remaining = (value - range_low) & 0xFFFF
    if remaining == 0:
        return added, 1
    added = (added + range_low) & 0xFFFF
    remaining = (remaining - 1) & 0xFFFF
    if remaining == 0:
        return added, 2
    added = (added + range_low) & 0xFFFF
    remaining = (remaining - 1) & 0xFFFF
    added = (added + remaining) & 0xFFFF
    return added, 3


def time_mark_cascade(read):
    """012CC2: clear TIME_MARK, then fold in each of the three groups' own contribution in order."""
    f36c = 0
    steps = []
    for table in GROUP_TABLES:
        active_id = read(table, 2) & 0xFFFF
        added, step = _tally_group(read, active_id)
        f36c = (f36c + added) & 0xFFFF
        steps.append(step)
    return {'value': f36c, 'stores': {TIME_MARK & 0xFFFFFF: (f36c, 2)}, 'steps': tuple(steps)}


def leading_group_recheck(read):
    """011468: SPECIAL_TIMER re-tested once registration is complete; negative on every witnessed
    occurrence.  The non-negative arm (a further count-active-groups/TIME_MARK derivation into
    FFFFF154) is real ROM no recording enters: declined, not modelled."""
    return {'negative': _signed_word(read(SPECIAL_TIMER, 2)) < 0}


def _with_stores(read, stores):
    """A reader that sees ``stores`` (an ``{address: (value, size)}`` map, exact address+size match
    only) as if they had already landed -- the real CPU sees its own earlier stores in this same
    activation before the tally cascade re-reads GROUP_TABLES/ITEM_RECORDS; a plain ``read`` would
    not."""
    def wrapped(address, size):
        entry = stores.get(address & 0xFFFFFF)
        if entry is not None and entry[1] == size:
            return entry[0]
        return read(address, size)
    return wrapped


def award_group_dispatch(read, item_id):
    """012C80: register ``item_id`` into one of the three GROUP_TABLES, or bump its own contact
    record's own ITEM_VALUE if it is already tracked -- either way TIME_MARK is recomputed.

    ``stores`` is ordered so its own last entry is the one durable effect (ITEM_VALUE, or the
    GROUP_TABLES active-id word), not TIME_MARK: TIME_MARK is rebuilt from scratch by every future
    call to this same routine (``time_mark_cascade``'s own ``clr.w f36c.w``), so a negative control
    that flips only it self-heals the next time an item is collected nearby, before ``collect``'s own
    read of it as the time-bonus baseline could ever observe the corruption.
    """
    item_id &= 0xFFFF
    ids = tuple(read(table, 2) & 0xFFFF for table in GROUP_TABLES)
    if item_id in ids:
        matched = ids.index(item_id)
        record = read(ITEM_RECORDS + _signed_word(4 * item_id), 4) & 0xFFFFFFFF
        value = read((record + ITEM_VALUE) & 0xFFFFFF, 2) & 0xFFFF
        new_value = (value + 1) & 0xFFFF
        value_key = (record + ITEM_VALUE) & 0xFFFFFF
        tally = time_mark_cascade(_with_stores(read, {value_key: (new_value, 2)}))
        stores = dict(tally['stores'])
        stores[value_key] = (new_value, 2)
        return {'arm': 'already-active', 'item_id': item_id, 'matched': matched, 'record': record,
                'stores': stores, 'tally': tally}

    selection = select_group_slot(read, item_id)
    if selection['arm'] not in ('override', 'group0', 'group1'):
        return {'arm': 'unrecovered-' + selection['arm'], 'item_id': item_id, 'stores': {}, 'selection': selection}

    table_key = selection['table'] & 0xFFFFFF
    overlay = dict(selection['stores'])
    overlay[table_key] = (item_id, 2)
    registration = register_item(_with_stores(read, overlay), item_id)
    overlay.update(registration['stores'])
    if registration['arm'] == 'unrecovered-field2':
        stores = dict(overlay)
        return {'arm': registration['arm'], 'item_id': item_id, 'stores': stores,
                'selection': selection, 'registration': registration}
    overlay.update(group_extended_clear(selection['table']))
    live_read = _with_stores(read, overlay)
    tally = time_mark_cascade(live_read)
    recheck = leading_group_recheck(live_read)
    if not recheck['negative']:
        stores = dict(overlay)
        stores.update(tally['stores'])
        return {'arm': 'unrecovered-leading-group', 'item_id': item_id, 'stores': stores,
                'selection': selection, 'registration': registration, 'tally': tally}
    stores = dict(selection['stores'])
    stores.update(registration['stores'])
    stores.update(group_extended_clear(selection['table']))
    stores.update(tally['stores'])
    stores[table_key] = (item_id, 2)
    return {'arm': 'register', 'item_id': item_id, 'group': selection['group'], 'group_arm': selection['arm'],
            'stores': stores, 'selection': selection, 'registration': registration, 'tally': tally}
