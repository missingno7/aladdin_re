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
