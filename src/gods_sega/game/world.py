"""The object post-process kind dispatch (``0036E2``), reached from ``003284``'s own body (the
achievements-record status ``> 4`` arm, ``docs/gods/blockers/2026-09-19-003480.md``'s own
reconnaissance) with the entry's own template kind word already in a live register.

A 13-entry ``(kind: word, handler: long)`` function-pointer table at ROM ``0x00370E``: most handlers
are the already-recovered dynamic sprite emitter (``0018C8``) or its sibling tile painter (``001810``,
directly or through a small per-frame index adjustment); a literal kind (``0x71``) short-circuits with
no call at all; an unmatched kind falls back to ``001810`` directly.  Every one of these dispatched
handlers is real ROM code this module does not reproduce -- the boundary cedes to it as one opaque
block (the same shape ``achievement_slot_dispatch_plan`` already proved for ``0047DA``), so only the
table lookup itself is named here as a pure function of ``read(address, size)``.

The dispatch's own EXIT is not an RTS: ``bra.w $3158``, back into ``0030CC``'s own 200-entry object
scan loop.  That address, and everything past it, belongs to the scan, not this dispatch.
"""
from __future__ import annotations

KIND_TABLE = 0x00370E
KIND_TABLE_COUNT = 13
NOOP_KIND = 0x0071
FALLBACK_HANDLER = 0x001810                 # the table's own exhaustion arm: a plain bsr into the tile painter


def classify_object_kind(read, kind):
    """What ``0036E2`` does with the template's own kind word.

    Returns the arm (``'noop'``: no call at all; ``'dispatch'``: the matched
    table entry's own handler, with ``mismatches`` the number of entries
    skipped before it, for the boundary's own cost formula; ``'fallback'``:
    every entry mismatched, `FALLBACK_HANDLER` runs instead) and, for
    ``'dispatch'``, the handler address read directly from the table.
    """
    if kind == NOOP_KIND:
        return {'arm': 'noop'}
    address = KIND_TABLE
    for index in range(KIND_TABLE_COUNT):
        entry_kind = read(address, 2)
        if entry_kind == kind:
            handler = read(address + 2, 4) & 0xFFFFFF
            return {'arm': 'dispatch', 'mismatches': index, 'handler': handler}
        address += 6
    return {'arm': 'fallback', 'mismatches': KIND_TABLE_COUNT, 'handler': FALLBACK_HANDLER}


# --- 002F2E: the effect queue append (reached from 003480's own body; the DRAIN half, 0x2F68 --
# pulling the queue's own head, decrementing a per-entry lifetime, calling the already-recovered
# 001164 -- is a separate, still-unrecovered caller, not modelled here) -------------------------
#
# A 10-slot, 10-byte-stride queue at QUEUE_BASE: the first word negative marks a slot free.  QUEUE_GATE
# (FFFFF240), when already zero, skips the scan entirely and writes straight into slot 0 (real ROM
# guarantees slot 0 is free whenever the gate reads zero -- the gate is exactly "the queue has never
# been appended to" as far as this routine's own logic assumes, never independently verified here);
# otherwise the ten slots are scanned in order for the first free one.  A found slot gets the caller's
# own D0/D1/D2 (position and a caller-chosen word) plus two fixed words (LIFETIME, START_FLAG) and the
# gate is set to 1.  Exhausting every slot with none free is real ROM (a silent drop, no store at all)
# no recording enters: declined.
QUEUE_BASE = 0xFFFF09FE
QUEUE_GATE = 0xFFFFF240
QUEUE_SLOT_STRIDE = 0xA
QUEUE_SLOT_COUNT = 10
QUEUE_LIFETIME = 0x0006     # the fixed word every append writes at the entry's own +6
QUEUE_START_FLAG = 0xFFF4   # the fixed word every append writes at the entry's own +8
QUEUE_WITNESSED_SCAN_DEPTH = range(0, 7)   # 0-6 occupied slots checked before a free one, all witnessed


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def queue_append(read, d0, d1, d2):
    """002F2E: append (d0, d1, d2) to the effect queue.

    Returns the arm (``'direct'``: QUEUE_GATE was zero, slot 0 used with no scan at all; ``'found'``:
    the scan found a free slot after ``depth`` occupied ones; ``'full'``: every slot occupied, a real,
    unwitnessed silent drop), the chosen slot's own address (``None`` for ``'full'``) and the stores.
    """
    if read(QUEUE_GATE, 2) == 0:
        slot = QUEUE_BASE
        arm, depth = 'direct', None
    else:
        slot, depth = None, None
        for index in range(QUEUE_SLOT_COUNT):
            candidate = (QUEUE_BASE + QUEUE_SLOT_STRIDE * index) & 0xFFFFFFFF
            if _signed_word(read(candidate & 0xFFFFFF, 2)) < 0:
                slot, depth = candidate, index
                break
        if slot is None:
            return {'arm': 'full', 'slot': None, 'depth': QUEUE_SLOT_COUNT, 'stores': {}}
        arm = 'found'
    address = slot & 0xFFFFFF
    # QUEUE_GATE is ordered first, not last: every future append sets it back to exactly 1 regardless
    # of what it held, so a generic "flip the last write" negative control on it would self-heal on
    # the very next append, before the drain half could ever observe the corruption.  The slot's own
    # fields persist until THIS slot is next reused, which is far less frequent.
    stores = {QUEUE_GATE & 0xFFFFFF: (1, 2), (address + 8) & 0xFFFFFF: (QUEUE_START_FLAG, 2),
             (address + 6) & 0xFFFFFF: (QUEUE_LIFETIME, 2), (address + 4) & 0xFFFFFF: (d2 & 0xFFFF, 2),
             (address + 2) & 0xFFFFFF: (d1 & 0xFFFF, 2), address: (d0 & 0xFFFF, 2)}
    return {'arm': arm, 'slot': slot, 'depth': depth, 'stores': stores}


# --- the 005958 table's own witnessed handlers (jsr'd from 00352C, inside 003480's own still-
# unrecovered body -- docs/gods/blockers/2026-09-19-003480.md) -----------------------------------
#
# A ROM-constant scan over a 192-byte table (SOUND_SCAN_TABLE) counts zero bytes among the caller's
# own status-many entries (status is SIGNED: a subq.w #1/bmi test, not a plain count -- status <= 0
# scans nothing), doubled twice into a real 23-entry (not 16: the prior reconnaissance's own read
# stopped at the first table-shaped run of bytes, but table-shaped code follows -- confirmed by this
# session's own full-tree trace of every occurrence, and by reading the ROM past entry 15 directly)
# function-pointer table at KIND_DISPATCH_TABLE.  Fifteen of the twenty-three are witnessed; seven are
# recovered here as their own leaves (indices 0, 3, 10, 14, 15, 16, 21); the rest (1, 2, 4, 6, 17, 18,
# 19, 22 -- witnessed but not yet recovered; and every unwitnessed index) decline by name.  Each
# handler ends in a plain rts (no seam, no tail branch): 003480's own body resumes at 003532 either
# way, and at least one of them (index 10, ROM 0x5A48) has a second, independent real caller elsewhere
# (exit 008616 in this session's own census) -- the leaf does not assume which caller it serves.
SOUND_SCAN_TABLE = 0x00014B42
SOUND_SCAN_TABLE_SIZE = 192
KIND_DISPATCH_TABLE = 0x00005958
KIND_DISPATCH_COUNT = 23
KIND_DISPATCH_WITNESSED = frozenset({0, 1, 2, 3, 4, 6, 10, 14, 15, 16, 17, 18, 19, 21, 22})
KIND_DISPATCH_ADMITTED = frozenset({0, 3, 10, 14, 15, 16, 21})


def kind_table_count(read, status):
    """0x3502-351E: the zero-byte count over SOUND_SCAN_TABLE's own first max(status, 0) bytes."""
    limit = status if status > 0 else 0
    return sum(1 for i in range(limit) if read((SOUND_SCAN_TABLE + i) & 0xFFFFFF, 1) == 0)


EF3C_BYPASS = 0xFFFFEF3C
EF3E_COUNTER = 0xFFFFEF3E
EF3E_CAP = 0x18
ACCUM_CUE_ADDRESS = 0xFFFFFDF6
ACCUM_CUE = 0x52
SPECIAL_TIMER = 0xFFFFF156   # the SAME SPECIAL_TIMER game.pickups already names
# (increment, has its own sound cue) per handler index; index 20 (increment 4) is real ROM, witnessed
# by no recording, and stays undescribed here on purpose -- only the four this session found in the
# ROM at all are named, and only three of those (0, 3, 21) are witnessed.
ACCUMULATOR_PARAMS = {0: (0xC, True), 3: (0x18, True), 19: (2, False), 21: (3, False)}


def accumulator_step(read, index):
    """Indices 0, 3, 21: EF3C negative bypasses entirely; otherwise EF3E is incremented by the
    index's own amount (always stored, even when the cap check below fails), and indices 0/3 ALSO
    write a fixed sound cue (0x52) unconditionally before the cap check.  Once EF3E exceeds EF3E_CAP
    it is reset to the cap and the excess, scaled by 32, is folded into SPECIAL_TIMER when
    SPECIAL_TIMER is not itself negative."""
    increment, has_cue = ACCUMULATOR_PARAMS[index]
    if _signed_word(read(EF3C_BYPASS, 2)) < 0:
        return {'arm': 'bypass', 'stores': {}}
    stores = {}
    if has_cue:
        stores[ACCUM_CUE_ADDRESS & 0xFFFFFF] = (ACCUM_CUE, 2)
    counter = (read(EF3E_COUNTER, 2) + increment) & 0xFFFF
    stores[EF3E_COUNTER & 0xFFFFFF] = (counter, 2)
    if _signed_word(counter) <= EF3E_CAP:
        return {'arm': 'below-cap', 'stores': stores}
    stores[EF3E_COUNTER & 0xFFFFFF] = (EF3E_CAP, 2)
    d0 = ((counter - EF3E_CAP) << 5) & 0xFFFF
    timer = read(SPECIAL_TIMER, 2)
    if _signed_word(timer) < 0:
        return {'arm': 'accumulate-skip', 'stores': stores, 'd0': d0}
    stores[SPECIAL_TIMER & 0xFFFFFF] = ((timer + d0) & 0xFFFF, 2)
    return {'arm': 'accumulate', 'stores': stores, 'd0': d0}


SOUND_CUE_PAIR_FDF4 = 0xFFFFFDF4
SOUND_CUE_PAIR_FDF6 = 0xFFFFFDF6
SOUND_CUE_PAIR_COUNTER = 0xFFFFF1CC


def sound_cue_pair(read):
    """Index 10 (ROM 0x5A48): two fixed sound cues and a shared counter incremented by one."""
    value = (read(SOUND_CUE_PAIR_COUNTER, 2) + 1) & 0xFFFF
    return {'stores': {SOUND_CUE_PAIR_FDF4 & 0xFFFFFF: (0x4C, 2), SOUND_CUE_PAIR_FDF6 & 0xFFFFFF: (0x4D, 2),
                       SOUND_CUE_PAIR_COUNTER & 0xFFFFFF: (value, 2)}}


COPY_TABLE_DEST = 0xFFFFF53A
COPY_TABLE_LONGS = 6
COPY_SOURCE = {14: 0x0142BC, 15: 0x0142D4, 16: 0x0142EC}


def copy_table(read, index):
    """Indices 14/15/16 (ROM 0x142A6/0x14292/0x1429C): the shared 24-byte (six-long) ROM-to-RAM copy
    (0x142AA) each feeds with its own fixed source block.  Index 14 reaches the copy by falling
    through with no store of its own D3 (whatever the caller's D3 already held survives, a real
    difference from 15/16's own explicit ``moveq #1,d3``, which the boundary's own register file
    must reproduce, not this pure function)."""
    source = COPY_SOURCE[index]
    stores = {(COPY_TABLE_DEST + 4 * i) & 0xFFFFFF: (read((source + 4 * i) & 0xFFFFFF, 4), 4)
             for i in range(COPY_TABLE_LONGS)}
    return {'stores': stores}


# --- indices 1/2 (ROM 0x5B5E/0x5B5C): bump every active group's own record, then recompute TIME_MARK
BUMP_CUE = 0x53


def _with_stores(read, stores):
    def wrapped(address, size):
        entry = stores.get(address & 0xFFFFFF)
        if entry is not None and entry[1] == size:
            return entry[0]
        return read(address, size)
    return wrapped


def bump_active_records(read):
    """0x5B70: for each of the three GROUP_TABLES whose own active id is non-negative, increment
    that item's own contact record ITEM_VALUE (+8) by one -- the SAME per-item record
    ``pickups.contact_search``/``award_group_dispatch`` already use, indexed here through a ROM
    lookup table (0x5BA6) confirmed byte-identical to ``active_id * CONTACT_ITEM_RECORD_STRIDE``."""
    from .pickups import GROUP_TABLES, CONTACT_ITEM_RECORDS_BASE, CONTACT_ITEM_RECORD_STRIDE, ITEM_VALUE
    stores = {}
    live = read
    for table in GROUP_TABLES:
        active = live(table, 2) & 0xFFFF
        if active & 0x8000:
            continue
        record = (CONTACT_ITEM_RECORDS_BASE + active * CONTACT_ITEM_RECORD_STRIDE) & 0xFFFFFFFF
        value_key = (record + ITEM_VALUE) & 0xFFFFFF
        value = (live(value_key, 2) + 1) & 0xFFFF
        stores[value_key] = (value, 2)
        live = _with_stores(read, stores)
    return {'stores': stores}


def bump_and_tally(read, times):
    """Indices 1 (times=1) and 2 (times=2): ``bump_active_records`` run ``times`` times (a real,
    witnessed double application for index 2 -- not special-cased, each run sees the previous run's
    own increments), then ``time_mark_cascade``, then a fixed sound cue.  The cue is ordered before
    the bump's own stores in the returned dict (the boundary places it first in ``writes``): the cue
    is rewritten by many other handlers regardless, but the SAME item record a caller might re-check
    persists until that item is next collected -- the durable effect belongs last, matching
    ``award_group_dispatch``'s own TIME_MARK-reordering fix."""
    from .pickups import time_mark_cascade
    bump_stores = {}
    live = read
    for _ in range(times):
        step = bump_active_records(live)
        bump_stores.update(step['stores'])
        live = _with_stores(read, bump_stores)
    tally = time_mark_cascade(live)
    stores = dict(tally['stores'])
    stores[0xFFFFFDF6 & 0xFFFFFF] = (BUMP_CUE, 2)
    stores.update(bump_stores)   # the bump's own record increments last: the durable effect
    return {'stores': stores, 'tally': tally, 'bump_stores': bump_stores, 'live_after_bump': live}


# --- index 22 (ROM 0x59C2): halve a shared frame counter into a second field ---------------------
def half_frame_counter(read):
    """0x59C2: F210 = EEC0 >> 1 (a plain LSR.w #1, no rounding); D3 = 2 on return."""
    value = (read(0xFFFFEEC0, 2) & 0xFFFF) >> 1
    return {'stores': {0xFFFFF210 & 0xFFFFFF: (value, 2)}}


# --- 003480: the object activity gate (`docs/gods/blockers/2026-09-19-003480.md`) ----------------
#
# Reached from 003284's own body with the entry's own object record in A0 (its own X/Y in D0/D1);
# EF3C negative bypasses entirely.  Otherwise a camera-relative box test (X: camera_x-4..camera_x+
# 0x24; Y: camera_y-4..camera_y+0x34, both against D0/D1+8) gates the whole rest of the routine --
# every exit (bypass, box miss, or the body's own completion) shares the SAME "rtr" tail (0x34B6/
# 0x34B8: clr.w -(a7); rtr -- SR wholesale 0) except one real, witnessed fail arm (0x34BE/0x34C2:
# move.w #8,-(a7); rtr -- SR wholesale N=1) reached only from inside the status dispatch below.
#
# In bounds, the object's own record status (+4(a0)) selects one of three real arms: >= 0xC0 hands
# off to the pickup-award group dispatch (012C80, already recovered) plus the queue append (002F2E,
# already recovered); otherwise the SAME status indexes achievements.RECORD_TABLE (0xFFFFF8C2, the
# SAME 10-byte-stride arithmetic achievements._record_address already models) for a second status
# word at +4: > 1 is the real fail exit named above; == 1 reaches a second real sub-dispatch, modelled
# below as `record_status_one_dispatch` (0x354C, over a further 4-entry FFFFF22E table); <= 0 reaches
# the SAME 005958 handler dispatch this session already recovered eleven of fifteen witnessed entries
# for (composing whichever handler the
# SAME SOUND_SCAN_TABLE zero-byte count selects, keyed here by the achievements record's own template
# status word, not the object's own +4 status), then the queue append again.
CAMERA_GATE_BYPASS = 0xFFFFEF3C
CAMERA_GATE_X, CAMERA_GATE_Y = 0xFFFFF18C, 0xFFFFF18E
CAMERA_GATE_X_LOW, CAMERA_GATE_X_HIGH = -4, 0x24
CAMERA_GATE_Y_LOW, CAMERA_GATE_Y_HIGH = -4, 0x34
OBJECT_STATUS_OFFSET = 4
OBJECT_TEMPLATE_OFFSET = 6
PICKUP_AWARD_GROUP_THRESHOLD = 0xC0
GATE_SOUND_CUE = 0x34
GATE_FIELD_WORD = 0xFFFFF3F2


def _signed_word16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def object_activity_gate(read, a0, d0, d1):
    """003480: the object activity gate.  ``a0`` is the object's own record; ``d0``/``d1`` its own
    X/Y (already the values 003284's own body passes, before this routine's own +8 offset)."""
    from .achievements import _record_address
    if _signed_word16(read(CAMERA_GATE_BYPASS, 2)) < 0:
        return {'arm': 'bypass', 'stores': {}}
    x, y = (d0 + 8) & 0xFFFF, (d1 + 8) & 0xFFFF
    camera_x, camera_y = read(CAMERA_GATE_X, 2) & 0xFFFF, read(CAMERA_GATE_Y, 2) & 0xFFFF
    x_low = (camera_x + CAMERA_GATE_X_LOW) & 0xFFFF
    x_high = (camera_x + CAMERA_GATE_X_HIGH) & 0xFFFF
    if _signed_word16(x) < _signed_word16(x_low) or _signed_word16(x) > _signed_word16(x_high):
        return {'arm': 'box-miss', 'stores': {}}
    y_low = (camera_y + CAMERA_GATE_Y_LOW) & 0xFFFF
    y_high = (camera_y + CAMERA_GATE_Y_HIGH) & 0xFFFF
    if _signed_word16(y) < _signed_word16(y_low) or _signed_word16(y) > _signed_word16(y_high):
        return {'arm': 'box-miss', 'stores': {}}

    status = read((a0 + OBJECT_STATUS_OFFSET) & 0xFFFFFF, 2) & 0xFFFF
    if status >= PICKUP_AWARD_GROUP_THRESHOLD:
        item_id = (status - PICKUP_AWARD_GROUP_THRESHOLD) & 0xFFFF
        return {'arm': 'pickup-award', 'item_id': item_id, 'x': d0 & 0xFFFF, 'y': d1 & 0xFFFF,
                'stores': {(a0 + OBJECT_STATUS_OFFSET) & 0xFFFFFF: (0xFFFF, 2),
                          (a0 + OBJECT_TEMPLATE_OFFSET) & 0xFFFFFF: (0, 2),
                          GATE_FIELD_WORD & 0xFFFFFF: (item_id, 2),
                          0xFFFFFDF6 & 0xFFFFFF: (GATE_SOUND_CUE, 2)}}

    record = _record_address(status)
    record_status = read((record + OBJECT_STATUS_OFFSET) & 0xFFFFFF, 2) & 0xFFFF
    # F3F2 is stored unconditionally once status < 0xC0 (0x34D0), before the record-status test.
    status_store = {GATE_FIELD_WORD & 0xFFFFFF: (status, 2)}
    if record_status > 1:
        return {'arm': 'record-status-fail', 'stores': status_store}
    if record_status == 1:
        return {'arm': 'record-status-one', 'stores': status_store}

    # FDF6 is written 0x34 twice here (both before the matched 005958 handler runs) -- left out of
    # this arm's own stores since the handler itself may write FDF6 again afterward (the accumulator
    # family's own cue, bump_tally's 0x53): the boundary composes the correct final order.
    return {'arm': 'sound-request', 'kind_count_status': status, 'x': d0 & 0xFFFF, 'y': d1 & 0xFFFF,
            'stores': {(a0 + OBJECT_STATUS_OFFSET) & 0xFFFFFF: (0xFFFF, 2),
                      (a0 + OBJECT_TEMPLATE_OFFSET) & 0xFFFFFF: (0, 2),
                      GATE_FIELD_WORD & 0xFFFFFF: (status, 2)}}


# --- 00354C: the object activity gate's own record-status-1 sub-dispatch --------------------------
#
# Reached from object_activity_gate's own body by a plain branch (0034EC `beq.w $354c`, the SAME
# non-call-boundary shape `classify_object_kind`'s own 0036E2 already proved) when the matched
# `achievements.RECORD_TABLE` entry's own status field is exactly 1.  D2 at this point is still the
# OBJECT's own status word (0034C4's own `move.w 4(a0),d2`, never overwritten before the branch) --
# the SAME value `object_activity_gate`'s own caller already computed and passed here as `status`.
# Every arm rejoins the gate's own shared "pass" exit (`bra.w $34b2`), never returning on its own.
RECORD_ONE_RANGE_LOW, RECORD_ONE_RANGE_HIGH = 0x000C, 0x0012      # [LOW, HIGH): the table-lookup range
RECORD_ONE_TABLE = 0xFFFFF22E
RECORD_ONE_TABLE_COUNT = 4
RECORD_ONE_ACCUM = 0xFFFFF296             # a long accumulator this arm folds the record's own +6 field into
RECORD_ONE_SCORE_BUFFER = 0xFFFFEF80      # score_convert's own destination base for this call site


def _signed_word_asr(value, count):
    """asr.w #count,d -- an arithmetic shift confined to the low 16 bits, as the ROM's own `asr.w`
    leaves the untouched upper word (the caller re-extends with `ext.l` afterward, modelled by the
    caller of this helper, not here)."""
    value &= 0xFFFF
    signed = value - 0x10000 if value & 0x8000 else value
    return (signed >> count) & 0xFFFF


def record_status_one_dispatch(read, status, record):
    """00354C: ``status`` is the object's own status word (D2, unchanged since 0034C4); ``record`` is
    ``achievements._record_address(status)``, already computed by the caller.  Returns the arm --
    'award' (status outside [0xC, 0x12): a sound cue, then the record's own +6 field folded into
    RECORD_ONE_ACCUM and converted through the already-recovered score conversion, then queued);
    'odd' (status inside the range, odd: a plain store, no calls); 'found'/'not-found' (status inside
    the range, even: a derived index looked up against the 4-entry RECORD_ONE_TABLE) -- and, for
    'award', the accumulator delta and the value score_convert itself receives; for 'found'/'not-found',
    the derived index and, for 'found', which of the four slots matched."""
    if status < RECORD_ONE_RANGE_LOW or status >= RECORD_ONE_RANGE_HIGH:
        raw = read((record + 6) & 0xFFFFFF, 2) & 0xFFFF
        accum_delta = raw - 0x10000 if raw & 0x8000 else raw
        shifted = _signed_word_asr(raw, 3)
        value = shifted - 0x10000 if shifted & 0x8000 else shifted
        return {'arm': 'award', 'accum_delta': accum_delta, 'value': value}
    if status & 1:
        return {'arm': 'odd'}
    index = ((status - RECORD_ONE_RANGE_LOW) >> 1) + 0x15
    for slot in range(RECORD_ONE_TABLE_COUNT):
        entry = read((RECORD_ONE_TABLE + 2 * slot) & 0xFFFFFF, 2) & 0xFFFF
        if entry == index:
            return {'arm': 'found', 'slot': slot, 'index': index}
    return {'arm': 'not-found', 'index': index}
