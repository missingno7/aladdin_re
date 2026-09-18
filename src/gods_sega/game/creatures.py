"""The creature attack timer (ROM 009D6C-009D6A / 009CF2-009DEA), called once per active creature per
frame from ``00A772`` (the per-creature family 00A578's own 9-slot list walk calls for each live
instance).

Two pointers, both owned by the caller and never advanced here: ``type_ptr`` (A4) is the creature
TYPE's own shared, read-only template (``00A578``'s own per-list definition table); ``instance_ptr``
(A5) is this one creature's own live 24-byte state (the record ``00A578`` itself walks in 0x18-byte
steps).  A zero attack byte, or its own low nibble zero, leaves everything alone (``'skip'``).
Otherwise the per-instance countdown at ``COUNTDOWN`` is decremented; while it stays nonzero the call
is done (``'waiting'``).  Reaching zero reloads it from the low nibble (``(16-kind)*4``) and reads the
aim quadrant from the type's own word at ``QUADRANT_WORD`` (bits 4-5): quadrant 1 draws two jitters
from the shared random table (``effects.next_random``, applied to the tracked position the same way
``projectiles.launch`` biases it) and launches through ``projectiles.launch_toward`` (ROM 0091C8 --
``launch``'s own pool body entered past its GRID_X/GRID_Y read, with the jittered target supplied
directly); quadrants 2-3 launch at the tracked position with no jitter, through ``projectiles.launch``
itself (0091BC).  Both share the launch's own ``'pool-full'`` decline (unwitnessed).

Quadrant 0 never launches a projectile: it computes a frequency word with the exact shape
``timers._frequency`` uses (``swap(power * FREQUENCY_SCALE) + 1``) but fed from the attack byte's own
high nibble (``power``) rather than a control byte, then hands off to ``timers._spawn``'s own
BACK/FORWARD hazard-pool fill.  Which variant runs is selected by whichever of two ROM tests fires
first: while the shared word ``TRACKED_SIGN`` is negative, a fixed one-byte ROM table
(``DIRECTION_BIT_TABLE``) is tested at the bit ``DIRECTION_INDEX`` selects; otherwise the instance's own
``FORWARD_BACK`` word does directly (zero declines with no effect at all, ``'skip-quadrant0'``).  Both
tests are plain mirrors of the ROM's own two branches -- not a guess -- and both reach the identical
BACK/FORWARD tail ``timers._spawn`` already proves; only the *dispatch* differs.

Pure functions of ``read(address, size)``; calls into ``game/timers.py``, ``game/effects.py`` and
``game/projectiles.py``'s own pure functions for the rest.
"""
from __future__ import annotations

from . import effects, projectiles, timers
from .grid import GRID_X, GRID_Y

ATTACK_BYTE = 0x6                  # type_ptr byte: 0 disables the creature's attack entirely
QUADRANT_WORD = 0x4                # type_ptr word: bits 4-5 (>>4 & 3) select the aim quadrant
COUNTDOWN = 0xE                    # instance_ptr word: ticks down to zero, then reloads
POSITION_X, POSITION_Y = 0x0, 0x2  # instance_ptr words: this creature's own world position
DIRECTION_INDEX = 0xA              # instance_ptr word: bit index into DIRECTION_BIT_TABLE
KIND = DIRECTION_INDEX             # the SAME field: 00A772's own kind-table dispatch and 00AA50 both
                                    # index KIND_TABLE with it (confirmed by trace, 18 Sep) -- the Q0
                                    # arm's own DIRECTION_BIT_TABLE bit index above is this same
                                    # 0-7 value read for a second purpose, not a distinct field.
FORWARD_BACK = 0x12                # instance_ptr word: sign selects BACK(<0)/skip(==0)/FORWARD(>0)
DIRECTION_BIT_TABLE = 0x009DEA     # ROM byte: bit N (mod 8) set selects BACK, clear selects FORWARD
TRACKED_SIGN = 0xFFFFF1BE          # word: negative routes through DIRECTION_BIT_TABLE, else FORWARD_BACK
LAUNCH_POSITION_BIAS = 0x10        # instance position -> the launch's own x0 (X only)
TARGET_BIAS_X, TARGET_BIAS_Y = 0x8, 0x6   # matches projectiles.TARGET_BIAS_X/Y (tracked position bias)
AIM_JITTER_MASK, AIM_JITTER_BIAS = 0x3F, 0x1F   # jitter = (next_random() & 0x3F) - 0x1F, one draw per axis
LAUNCH_FLAG = 0                    # moveq #0,d6: the launch's own flag argument, fixed (not caller-derived)

# 00AA50: the creature's own per-kind, per-frame offset -- called both from 00A772's own $f38a.w
# "moving" arm (its own result fed straight to the next unrecovered call, 00A922) and from inside the
# ground/fall kind handlers (00ACA0/00AD88/00AE6C/00AED4, per the blocker).  RAM/ROM-read only, no
# store, one unconditional path on every one of 19,798 occurrences across four recordings that reach
# it (the fifth never does): the routine's own arithmetic is the fact, not a guess at what the result
# means.
KIND_TABLE = 0x00A538               # ROM: the SAME 8-entry, 8-byte kind table 00A772's own dispatch reads
                                     # (handler pointer at +0, a per-kind word here at +4 -- 0x800, 0,
                                     # 0x808, 8, 0x808, 8, 0x808, 8 for kinds 0-7, confirmed from the ROM)
KIND_TABLE_VALUE_OFFSET = 0x4       # the per-kind long this routine reads (upper word always 0 in the ROM)
FRAME_STEP = 0x4                    # instance_ptr word: added to the kind table's own per-kind value
TYPE_FRAME_BYTE = 0x7               # type_ptr byte: adjacent to ATTACK_BYTE; this type's own frame number
FRAME_TABLE_PTR = 0xFFFFF188        # long: a work-RAM pointer to a per-kind table, read fresh every call
                                     # (every witnessed occurrence reads the SAME pointer value, but it
                                     # is live state, not hardcoded -- a level or animation-state global)


def kind_frame_offset(read, type_ptr, instance_ptr):
    """00AA50: ``((KIND_TABLE[kind].value + instance.frame_step) << 4) + FRAME_TABLE[type.frame << 4]``,
    all 16-bit arithmetic (the kind table's own value is read as a long, but every ROM entry's upper
    word is zero, so the result -- returned as ``'d2'`` -- is exactly this word, zero-extended)."""
    type_ptr &= 0xFFFFFF
    instance_ptr &= 0xFFFFFF
    kind = read(instance_ptr + KIND, 2) & 0xFFFF
    kind_value = read(KIND_TABLE + 8 * kind + KIND_TABLE_VALUE_OFFSET, 4)
    step = read(instance_ptr + FRAME_STEP, 2) & 0xFFFF
    offset = ((kind_value + step) << 4) & 0xFFFF
    frame = read(type_ptr + TYPE_FRAME_BYTE, 1) & 0xFF
    table = read(FRAME_TABLE_PTR, 4) & 0xFFFFFF
    delta = read((table + ((frame << 4) & 0xFFFF)) & 0xFFFFFF, 2) & 0xFFFF
    return {'d2': (offset + delta) & 0xFFFF, 'kind': kind, 'frame': frame, 'offset': offset, 'delta': delta}


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _overlay(read, stores):
    """A ``read`` wrapped so an address just written (by an earlier draw in the same call) is seen with
    its new value -- real hardware, unlike this module's own ``stores`` bookkeeping, sees every write
    immediately."""
    def wrapped(address, size):
        address &= 0xFFFFFF
        if address in stores:
            value, _ = stores[address]
            return value
        return read(address, size)
    return wrapped


def attack_update(read, type_ptr, instance_ptr):
    """009D6C: one creature's own attack-timer tick.

    Returns the arm (``'skip'``, ``'waiting'``, ``'launch-jittered'``, ``'launch-direct'`` (each with a
    ``-pool-full`` suffix if the projectile pool is exhausted -- declined, unwitnessed), ``'spawn-window'``
    /``'spawn-reject'``/``'spawn-pool-full'`` (the last declined, unwitnessed) or ``'skip-quadrant0'``
    (declined, unwitnessed as its own combination though its own effect is none) -- the countdown's value
    before/after where it changed, and the durable stores.
    """
    type_ptr &= 0xFFFFFF
    instance_ptr &= 0xFFFFFF
    attack_byte = read(type_ptr + ATTACK_BYTE, 1) & 0xFF
    if attack_byte == 0:
        return {'arm': 'skip', 'stores': {}}
    kind = attack_byte & 0xF
    if kind == 0:
        return {'arm': 'skip', 'stores': {}}
    before = read(instance_ptr + COUNTDOWN, 2) & 0xFFFF
    after = (before - 1) & 0xFFFF
    if after != 0:
        return {'arm': 'waiting', 'before': before, 'after': after,
                'stores': {(instance_ptr + COUNTDOWN) & 0xFFFFFF: (after, 2)}}
    reload = (((0x10 - kind) & 0xFF) * 4) & 0xFFFF
    stores = {(instance_ptr + COUNTDOWN) & 0xFFFFFF: (reload, 2)}
    power = (attack_byte >> 4) & 0xF
    quadrant = (read(type_ptr + QUADRANT_WORD, 2) >> 4) & 0x3
    result = {'before': before, 'after': after, 'reload': reload, 'kind': kind, 'power': power,
              'quadrant': quadrant, 'stores': stores}
    if quadrant != 0:
        x0 = (read(instance_ptr + POSITION_X, 2) + LAUNCH_POSITION_BIAS) & 0xFFFF
        y0 = read(instance_ptr + POSITION_Y, 2) & 0xFFFF
        if quadrant == 1:
            x1 = (read(GRID_X, 2) + TARGET_BIAS_X) & 0xFFFF
            y1 = (read(GRID_Y, 2) + TARGET_BIAS_Y) & 0xFFFF
            draw_x = effects.next_random(read)
            stores.update(draw_x['stores'])
            x1 = (x1 + (((draw_x['value'] & AIM_JITTER_MASK) - AIM_JITTER_BIAS) & 0xFFFF)) & 0xFFFF
            draw_y = effects.next_random(_overlay(read, draw_x['stores']))
            stores.update(draw_y['stores'])
            y1 = (y1 + (((draw_y['value'] & AIM_JITTER_MASK) - AIM_JITTER_BIAS) & 0xFFFF)) & 0xFFFF
            result['draws'] = (draw_x, draw_y)
            launch = projectiles.launch_toward(read, x0, y0, x1, y1, power, LAUNCH_FLAG)
            result['arm'] = 'launch-jittered'
        else:
            launch = projectiles.launch(read, x0, y0, power, LAUNCH_FLAG)
            result['arm'] = 'launch-direct'
        stores.update(launch['stores'])
        result['launch'] = launch
        if launch['arm'] == 'pool-full':
            result['arm'] += '-pool-full'
        return result
    # quadrant == 0: the frequency/hazard-pool arm -- timers._frequency's own shape, a local 'power' base.
    raw = (power * read(timers.FREQUENCY_SCALE, 2)) & 0xFFFFFFFF
    frequency = (((raw >> 16) & 0xFFFF) + 1) & 0xFFFF
    frequency_upper = raw & 0xFFFF   # swap's own leftover high word -- D5 keeps it until 01158C/0115D4 overwrite D5 entirely (spawn-window only)
    tracked = _signed_word(read(TRACKED_SIGN, 2))
    if tracked < 0:
        index = read(instance_ptr + DIRECTION_INDEX, 2) & 0x7
        bit = (read(DIRECTION_BIT_TABLE, 1) >> index) & 1
        variant = timers.BACK if bit else timers.FORWARD
    else:
        select = _signed_word(read(instance_ptr + FORWARD_BACK, 2))
        if select == 0:
            result['arm'] = 'skip-quadrant0'
            return result
        variant = timers.FORWARD if select > 0 else timers.BACK
    if variant is timers.BACK:
        frequency = (-frequency) & 0xFFFF
    spawn = timers._spawn(read, instance_ptr, variant, frequency)
    stores[timers.TRIGGER_FREQUENCY & 0xFFFFFF] = (frequency, 2)
    stores.update(spawn['stores'])
    result.update(frequency=frequency, frequency_upper=frequency_upper, variant=variant, spawn=spawn)
    if not spawn['windowed']:
        result['arm'] = 'spawn-reject'
    elif spawn['slot'] is not None:
        result['arm'] = 'spawn-window'
    else:
        result['arm'] = 'spawn-pool-full'
    return result


# --- 00B944: the creature update's own probe into the already-recovered pickup check ------------
#
# 00A772's own second unconditional callee (18 Sep, real-index-26 session, per
# docs/gods/blockers/2026-09-18-00A578.md's own ordering): unlike 010CD2's own camera-relative probe
# (pickups.pickup_probe), this one calls pickup_check directly over the creature's own tracked
# position (D0/D1, already read by 00A772's own head before the call), no camera add.  A single
# unconditional write (FFFFF382.l = 0x00200020, a fixed constant this session did not trace further)
# runs before the call every time.  LIFECYCLE (the creature's own +8 word, the SAME field
# docs/gods/blockers/2026-09-18-00A578.md's own recon names "the lifecycle word $8(a5)" that 00A578's
# own per-frame walk tests to decide whether to call 00A772 at all) is both the call's own D2
# argument and its own result: on a negative pickup_check result, FRAME_STEP is forced to -1 and the
# instance's own +6 word (LIFECYCLE_RESET below; what tracks it is not established this session) is
# cleared.
LIFECYCLE = 0x8                     # instance_ptr word: pickup_check's own D2 argument AND result
LIFECYCLE_RESET = 0x6               # instance_ptr word: cleared alongside FRAME_STEP=-1 on a pickup hit


def creature_pickup_check(read, x, y, lifecycle):
    """00B944: probes the already-recovered pickup check over the creature's own tracked position
    (no camera offset, unlike pickups.pickup_probe's own 010CD2).  Returns the check's own result and
    whether it came back negative (the caller then forces FRAME_STEP=-1 and clears LIFECYCLE_RESET)."""
    from . import pickups
    check = pickups.pickup_check(read, x, y, lifecycle)
    return {'check': check, 'negative': pickups._signed_word(check['d2']) < 0}


# --- 00A922: the creature's own world-event consume, the third of 00A772's own unconditional
# callees (18 Sep, real-index-26 session).  No calls; a bounded loop over the world update's own
# per-tick event list (EVENT_LIST, new -- unreferenced anywhere else in src/gods_sega), then, on a
# match, a SECOND bounded loop backwards over the already-recovered game.movement.BOX_SCAN_TABLE
# looking for the object the event refers to.
EVENT_MODE = 0xFFFFF1E6              # word: only mode 2 permits a scan; 0/1 are the world update's
                                      # own earlier phases (order 11, docs/gods/tick-map.md)
EVENT_COUNT = 0xFFFFF260              # word: this tick's own appended-event count (0030CC's own tail);
                                       # clamped to EVENT_LIST_MAX before the search loop even starts
EVENT_LIST = 0xFFFF0BF8               # 6-byte (X, Y, kind) triples, appended by the world update
EVENT_LIST_STRIDE = 6
EVENT_LIST_MAX = 0x14                 # never witnessed exceeded by any recording; declined, not guessed
EVENT_KIND = 0x10                     # instance_ptr word: gate ('already has an event' when >= 0);
                                       # the found event's own kind, once one is consumed
EVENT_X, EVENT_Y = 0x14, 0x16         # instance_ptr words: the found event's own position
EVENT_KIND_OTHER_GATE = 0xC0          # a slot kind >= this shifts QUADRANT_WORD by 2 instead of 0
EVENT_KIND_EXCLUDED = 0x45            # a slot of exactly this kind is always skipped
EVENT_BOX_NEAR, EVENT_BOX_FAR = -0x28, 0x8    # instanceX - slotX (and instanceY - slotY) must fall
                                               # in this range for the slot to match (00A980/00A982
                                               # addq.w #8 sets the far bound; 00A98C/00A990 subi.w
                                               # #$30 from that same +8 value nets -0x28 for the near
                                               # bound -- not the state-26 box margins, which are a
                                               # different region's own constants)


def event_consume(read, type_ptr, instance_ptr):
    """00A922: real, witnessed, fully modelled arms -- 'mode-inactive' (EVENT_MODE != 2, the world
    update's own earlier phases), 'no-events' (EVENT_COUNT == 0), 'already-has-event' (EVENT_KIND >=
    0), 'no-match' (the event-list scan exhausts).  'found' composes both loops: the first slot inside
    the creature's own box around (POSITION_X-8, POSITION_Y-8) whose own kind passes the
    QUADRANT_WORD mask (and isn't EVENT_KIND_EXCLUDED) selects an (x, y, kind) triple; the SAME triple
    is then searched for, walking game.movement.BOX_SCAN_TABLE BACKWARDS from its own last slot, in
    the object table -- the entries dicts (both 'entries' and 'obj_entries') carry every step's own
    per-slot facts for the boundary's own costing.  'count-clamped' (EVENT_COUNT > EVENT_LIST_MAX) and
    the object search's own 'skip-negative'/'skip-y'/exhausted ('no-object-match') arms are real ROM,
    never witnessed by any recording -- the caller declines them."""
    type_ptr &= 0xFFFFFF
    instance_ptr &= 0xFFFFFF
    mode = read(EVENT_MODE, 2) & 0xFFFF
    if mode != 2:
        return {'arm': 'mode-inactive'}
    count = read(EVENT_COUNT, 2) & 0xFFFF
    if count == 0:
        return {'arm': 'no-events'}
    if _signed_word(read(instance_ptr + EVENT_KIND, 2)) >= 0:
        return {'arm': 'already-has-event'}
    if count > EVENT_LIST_MAX:
        return {'arm': 'count-clamped'}
    d7 = count - 1
    cx = _signed_word((read(instance_ptr + POSITION_X, 2) - 8) & 0xFFFF)
    cy = _signed_word((read(instance_ptr + POSITION_Y, 2) - 8) & 0xFFFF)
    quadrant_word = read(type_ptr + QUADRANT_WORD, 2) & 0xFFFF
    entries = []
    found = None
    entry_addr = EVENT_LIST
    for index in range(d7 + 1):
        slot_kind = read((entry_addr + 4) & 0xFFFFFF, 2) & 0xFFFF
        shift = 2 if _signed_word(slot_kind) >= EVENT_KIND_OTHER_GATE else 0
        mask = (quadrant_word >> shift) & 3
        if mask == 0:
            entries.append({'index': index, 'arm': 'skip-mask', 'entry': entry_addr, 'slot_kind': slot_kind,
                           'mask': mask})
        elif slot_kind == EVENT_KIND_EXCLUDED:
            entries.append({'index': index, 'arm': 'skip-excluded', 'entry': entry_addr, 'slot_kind': slot_kind,
                           'mask': mask})
        else:
            slot_x = read(entry_addr & 0xFFFFFF, 2) & 0xFFFF
            slot_y = read((entry_addr + 2) & 0xFFFFFF, 2) & 0xFFFF
            dx = cx - _signed_word(slot_x)
            dy = cy - _signed_word(slot_y)
            pass_far_x = dx <= EVENT_BOX_FAR
            pass_far_y = pass_far_x and dy <= EVENT_BOX_FAR
            pass_near_x = pass_far_y and dx >= EVENT_BOX_NEAR
            pass_near_y = pass_near_x and dy >= EVENT_BOX_NEAR
            step = {'index': index, 'entry': entry_addr, 'slot_kind': slot_kind, 'mask': mask,
                    'pass_far_x': pass_far_x, 'pass_far_y': pass_far_y, 'pass_near_x': pass_near_x}
            if pass_near_y:
                step['arm'] = 'found'
                entries.append(step)
                found = step
                break
            step['arm'] = 'tested'
            entries.append(step)
        entry_addr = (entry_addr + EVENT_LIST_STRIDE) & 0xFFFFFFFF
    if found is None:
        return {'arm': 'no-match', 'entries': entries, 'd0': cx & 0xFFFF, 'd1': cy & 0xFFFF}

    from .movement import BOX_SCAN_TABLE, BOX_SCAN_COUNT, BOX_SCAN_STRIDE, BOX_SCAN_STATUS_A, BOX_SCAN_STATUS_B
    ex = read(found['entry'] & 0xFFFFFF, 2) & 0xFFFF
    ey = read((found['entry'] + 2) & 0xFFFFFF, 2) & 0xFFFF
    ekind = found['slot_kind']
    obj_entries = []
    obj_found = None
    obj_addr = (BOX_SCAN_TABLE + BOX_SCAN_STRIDE * BOX_SCAN_COUNT) & 0xFFFFFFFF
    declined_arm = None
    for oindex in range(BOX_SCAN_COUNT):
        obj_addr = (obj_addr - BOX_SCAN_STRIDE) & 0xFFFFFFFF
        status_b = read((obj_addr + BOX_SCAN_STATUS_B) & 0xFFFFFF, 2)
        if status_b == 0:
            obj_entries.append({'index': oindex, 'arm': 'skip-inactive', 'entry': obj_addr})
            continue
        status_a = read((obj_addr + BOX_SCAN_STATUS_A) & 0xFFFFFF, 2)
        if _signed_word(status_a) < 0:
            obj_entries.append({'index': oindex, 'arm': 'skip-negative', 'entry': obj_addr})
            declined_arm = 'skip-negative'
            break
        if (status_a & 0xFFFF) != ekind:
            obj_entries.append({'index': oindex, 'arm': 'skip-kind', 'entry': obj_addr})
            continue
        ox = read(obj_addr & 0xFFFFFF, 2) & 0xFFFF
        if ox != ex:
            obj_entries.append({'index': oindex, 'arm': 'skip-x', 'entry': obj_addr})
            continue
        oy = read((obj_addr + 2) & 0xFFFFFF, 2) & 0xFFFF
        if oy != ey:
            obj_entries.append({'index': oindex, 'arm': 'skip-y', 'entry': obj_addr})
            declined_arm = 'skip-y'
            break
        obj_entries.append({'index': oindex, 'arm': 'found', 'entry': obj_addr})
        obj_found = obj_addr
        break
    base = {'entries': entries, 'obj_entries': obj_entries, 'd0': cx & 0xFFFF, 'd1': cy & 0xFFFF,
            'd2': ex, 'd3': ey, 'd4': ekind}
    if declined_arm is not None:
        return {**base, 'arm': declined_arm}
    if obj_found is None:
        return {**base, 'arm': 'no-object-match'}
    stores = {(instance_ptr + EVENT_X) & 0xFFFFFF: (ex, 2), (instance_ptr + EVENT_Y) & 0xFFFFFF: (ey, 2),
              (instance_ptr + EVENT_KIND) & 0xFFFFFF: (ekind, 2), (obj_found + 4) & 0xFFFFFF: (0xFFFF, 2),
              (obj_found + 6) & 0xFFFFFF: (0, 2)}
    return {**base, 'arm': 'found', 'stores': stores, 'obj_found': obj_found}


# --- 00AA38: the creature's own grid-cell lookup, one of the six further callees the ground/fall kind
# handlers need (docs/gods/blockers/2026-09-18-00A578.md's own recon: "00AA38, a grid/position-to-tile-
# address computation, structurally similar to game.grid.grid_cell_at").  Confirmed identical, not
# merely similar: byte-for-byte 0063FA/010CBC's own shared arithmetic (game.grid.grid_cell_at), read
# from the creature's own tracked position (POSITION_X/POSITION_Y) instead of a caller-supplied D0/D1
# or the fixed GRID_X/GRID_Y -- a third call site of the same shape, the record convention the
# grinder-protocol names as no reason to defer.  RAM/ROM-read only, no store, ONE unconditional path
# on every one of 1,283 occurrences across the four recordings that reach it (census-00AA38-*,
# `ca2b703b6fd5` never reaches 00A578's own creature slots at all, matching the other creature-family
# leaves).  Only its own output register differs from 010CBC's (A1 here, A0 there).

def creature_grid_cell(read, instance_ptr):
    """00AA38: grid.grid_cell_at's own arithmetic, over this creature's own POSITION_X/POSITION_Y."""
    from .grid import grid_cell_at
    instance_ptr &= 0xFFFFFF
    x = read(instance_ptr + POSITION_X, 2) & 0xFFFF
    y = read(instance_ptr + POSITION_Y, 2) & 0xFFFF
    result = grid_cell_at(x, y)
    return {'a1': result['address'] & 0xFFFFFFFF, 'd0': result['column'] & 0xFFFF,
            'd1': result['row'] & 0xFFFF, 'row_source': result['row_source']}


# --- 00AD68: the second of the six further callees -- a two-cell test over the grid table's own bytes
# at the address 00AA38/creature_grid_cell leaves in A1, gated by the SAME creature's own POSITION_X
# low 5 bits (docs/gods/blockers/2026-09-18-00A578.md's own recon: "00AD68, a small collision-adjacent
# leaf").  What the flag byte itself means is not established this session -- the name is what the
# arithmetic supports (a per-cell marker the ground/fall kind handlers test), not more.  Census over
# all four exercising recordings (census-00AD68-*) retains exactly two real path classes, both ending
# with the result 0: the routine's own two "found" arms (the cell's low byte itself is 1, or -- past
# the low-5 gate -- its neighbour is) are real ROM, declined, unwitnessed by any recording.
GROUND_EDGE_LOW_BYTE = 0                # cell_addr byte: tested unconditionally first
GROUND_EDGE_HIGH_BYTE = 1               # cell_addr+1 byte: tested only when x's own low 5 bits are >= 8
GROUND_EDGE_X_GATE = 0x8                # the low-5-bits threshold that admits the second test
GROUND_EDGE_FLAG = 1                    # the byte value either test matches


def ground_edge_test(read, cell_addr, x):
    """00AD68: tests the grid cell's own low byte, then -- only when ``x``'s own low 5 bits are >= 8 --
    its neighbour, for ``GROUND_EDGE_FLAG``.  Returns the arm and ``d1`` (0 or 1, the routine's only
    real output); 'cell-low' and 'cell-high' (the flag actually found) are real ROM, unwitnessed."""
    cell_addr &= 0xFFFFFF
    low = read(cell_addr, 1) & 0xFF
    if low == GROUND_EDGE_FLAG:
        return {'arm': 'cell-low', 'd1': 1}
    x_low5 = x & 0x1F
    if x_low5 < GROUND_EDGE_X_GATE:
        return {'arm': 'no-match-near-edge', 'd1': 0, 'x_low5': x_low5}
    high = read((cell_addr + GROUND_EDGE_HIGH_BYTE) & 0xFFFFFF, 1) & 0xFF
    if high == GROUND_EDGE_FLAG:
        return {'arm': 'cell-high', 'd1': 1}
    return {'arm': 'no-match', 'd1': 0, 'x_low5': x_low5, 'high': high}


# --- 00ACA0: the ground-contact kind handler -- kind 4 of 00A772's own eight-entry table (00A538),
# the most frequent witnessed kind handler (docs/gods/blockers/2026-09-18-00A578.md's own Decision:
# "the six witnessed kind handlers are leaves or small families over the creature record").  Composes
# the already-recovered creature_grid_cell (00AA38, called twice: once before the settle test, again
# after the table-driven POSITION_Y step, over the record's OWN pending write -- an overlay reader,
# the same shape attack_update's own chained next_random draws already use) and ground_edge_test
# (00AD68) TWICE over: once directly (00AD68 itself, the far test, offsets 0/1) and once through a
# sibling entry point (00AD46) that tests the SAME two grid-cell bytes through the (d16,An) addressing
# mode instead ($100/$101(a1) -- confirmed identical arithmetic to ground_edge_test's own 0/1(a1), just
# fed cell_addr+0x100, a real cross-reference finding, 19 Sep) -- the near test, gating whether the
# table step runs at all.  Never returns to its own caller: the ROM's own tail is always
# ``bra.w $aa50`` (kind_frame_offset, its own separately-armed gate, per docs/gods/grinder-protocol.md
# section 6a's family-hand-off shape -- 00AA50's own effects are NOT inlined here, exactly as
# ``player_state_plan``'s own states hand off to ``player-tail``'s gate rather than compose it).
GROUND_HOLD_TIMER = 0x6            # instance_ptr word: ticks down each activation; negative reloads it.
                                    # The SAME offset LIFECYCLE_RESET (00B944, above) names for a
                                    # different caller -- not established as the same field this session.
TYPE_GROUND_RELOAD_BYTE = 0xB      # type_ptr byte: (byte>>2), the reload is 2 - that shift (word wrap)
GROUND_SKIP_TEST_LOW_OFFSET = -1   # cell_addr byte: the "hold position" cell test's own first probe
GROUND_SKIP_TEST_HIGH_OFFSET = 0x7F  # cell_addr byte: its own second probe (low5==0 gates both)
FALL_PHASE = 0x12                  # instance_ptr word: an index into GROUND_STATE_TABLE, 0 at rest,
                                    # set to 2/8 by this routine's own settle tail, decremented once
                                    # past the near-test guard.  The SAME offset FORWARD_BACK
                                    # (attack_update, above) names for a different caller -- likewise
                                    # not established as the same field.
GROUND_STATE_TABLE = 0x00AE4C      # ROM: 13 signed words (0, -1, -1, -2, -4, -8 x8), a POSITION_Y delta
GROUND_SETTLE_FLOOR = -5           # FALL_PHASE, after its own decrement, resets below this (signed)
GROUND_SETTLE_RESET = 8            # the reset value for FALL_PHASE
KIND_FALL = 2                      # KIND_TABLE index 2 == 00AE6C, the fall kind handler (the far-edge
                                    # trigger and the settle-reset tail both hand the creature off to it
                                    # by overwriting its own KIND field -- 00A772's own dispatch re-reads
                                    # KIND every activation, so this is a real state transition, not a
                                    # renamed record field: confirmed against docs/gods/blockers/
                                    # 2026-09-18-00A578.md's own eight-entry table order)

# --- 00AD88: kind 5's own ground-contact tick, the SAME shape as 00ACA0 mirrored (ground_contact_update_mirror,
# below) -- its own skip-test offsets and KIND transition targets.
MIRROR_SKIP_TEST_LOW_OFFSET = 1    # cell_addr byte: the mirror's own first probe (00ACA0's own is -1)
MIRROR_SKIP_TEST_HIGH_OFFSET = 0x81  # cell_addr byte: its own second probe (00ACA0's own is +0x7F)
MIRROR_KIND_FALL = 3               # KIND_TABLE index 3 == 00AED4, the SECOND fall kind handler --
                                    # distinct from KIND_FALL (2, 00AE6C), 00ACA0's own target


def _ground_contact_step(read, type_ptr, instance_ptr, *, x_delta, skip_low_offset, skip_high_offset,
                         near_kind, far_kind):
    """The shared shape 00ACA0 and 00AD88 both run, parameterised on what differs between them: the
    sign of the POSITION_X step, the skip-test's own two cell-byte offsets, and the KIND value a
    trigger hands the creature off to (``ground_contact_update``/``ground_contact_update_mirror``, both
    below, supply the ROM's own real constants -- nothing here is guessed).

    Returns the arm (``'idle'`` -- the hold timer stayed non-negative; ``'near-trigger'`` -- the
    (d16,An) edge test's own match (either probe: the ROM only tests the routine's own D1 result, never
    which byte set it), KIND set to ``near_kind`` and POSITION_Y masked; the DECLINED, unwitnessed
    ``'far-trigger-cell-low'``/``'far-trigger-cell-high'``; or ``'settle-continue'``/``'settle-reset'``
    -- the table-driven POSITION_Y step, the far edge test (0/1(a1)) not triggering, and FALL_PHASE's
    own decrement landing at or above / below GROUND_SETTLE_FLOOR) plus every intermediate fact the
    boundary's own cost needs (whether POSITION_X's own step applied or which cell test skipped it, the
    near/far ground_edge_test results, the table read)."""
    type_ptr &= 0xFFFFFF
    instance_ptr &= 0xFFFFFF
    timer_before = read(instance_ptr + GROUND_HOLD_TIMER, 2) & 0xFFFF
    timer_after = (timer_before - 1) & 0xFFFF
    if _signed_word(timer_after) >= 0:
        return {'arm': 'idle', 'timer_before': timer_before, 'timer_after': timer_after,
                'stores': {(instance_ptr + GROUND_HOLD_TIMER) & 0xFFFFFF: (timer_after, 2)}}
    reload_byte = read(type_ptr + TYPE_GROUND_RELOAD_BYTE, 1) & 0xFF
    reload = (2 - ((reload_byte >> 2) & 0xFFFF)) & 0xFFFF
    stores = {(instance_ptr + GROUND_HOLD_TIMER) & 0xFFFFFF: (reload, 2)}
    grid = creature_grid_cell(read, instance_ptr)
    cell_addr = grid['a1'] & 0xFFFFFF
    x = read(instance_ptr + POSITION_X, 2) & 0xFFFF
    low5 = x & 0x1F
    step_applied, skip_test = True, None
    if low5 == 0:
        low_byte = read((cell_addr + skip_low_offset) & 0xFFFFFF, 1) & 0xFF
        if low_byte == GROUND_EDGE_FLAG:
            step_applied, skip_test = False, 'cell-low'
        else:
            high_byte = read((cell_addr + skip_high_offset) & 0xFFFFFF, 1) & 0xFF
            if high_byte == GROUND_EDGE_FLAG:
                step_applied, skip_test = False, 'cell-high'
    x_before = x
    if step_applied:
        x = (x + x_delta) & 0xFFFF
        stores[(instance_ptr + POSITION_X) & 0xFFFFFF] = (x, 2)
    result = {'timer_before': timer_before, 'reload': reload, 'low5': low5, 'grid': grid,
              'subq_applied': step_applied, 'skip_test': skip_test, 'x': x, 'x_before': x_before}
    fall_phase = _signed_word(read(instance_ptr + FALL_PHASE, 2))
    result['fall_phase'] = fall_phase
    if fall_phase <= 0:
        near = ground_edge_test(read, cell_addr + 0x100, x)
        result['near'] = near
        if near['arm'] in ('cell-low', 'cell-high'):
            # The ROM only tests D1 (0 or 1) after the call, never which of the two probes set it: a
            # 'cell-low' and a 'cell-high' match run the SAME two stores below -- confirmed from the
            # disassembly, not merely unwitnessed for one of the two callers (00ACA0 witnesses only
            # 'cell-low' here, 00AD88 only 'cell-high'; together they witness both real arms of
            # ground_edge_test's own d1==1 outcome, so neither declines).
            y = read(instance_ptr + POSITION_Y, 2) & 0xFFFF
            new_y = y & 0xFFF0
            stores[(instance_ptr + KIND) & 0xFFFFFF] = (near_kind, 2)
            stores[(instance_ptr + POSITION_Y) & 0xFFFFFF] = (new_y, 2)
            result.update(arm='near-trigger', y=y, new_y=new_y, stores=stores)
            return result
    delta = _signed_word(read((GROUND_STATE_TABLE + 2 * fall_phase) & 0xFFFFFF, 2))
    y = read(instance_ptr + POSITION_Y, 2) & 0xFFFF
    new_y = (y + delta) & 0xFFFF
    stores[(instance_ptr + POSITION_Y) & 0xFFFFFF] = (new_y, 2)
    read2 = _overlay(read, stores)
    grid2 = creature_grid_cell(read2, instance_ptr)
    cell2_addr = grid2['a1'] & 0xFFFFFF
    x2 = read2(instance_ptr + POSITION_X, 2) & 0xFFFF
    far = ground_edge_test(read2, cell2_addr, x2)
    result.update(delta=delta, y=y, new_y=new_y, grid2=grid2, far=far)
    if far['arm'] in ('cell-low', 'cell-high'):
        result['arm'] = 'far-trigger-' + far['arm']
        result['stores'] = stores
        return result
    new_fall_phase = (fall_phase - 1) & 0xFFFF
    stores[(instance_ptr + FALL_PHASE) & 0xFFFFFF] = (new_fall_phase, 2)
    if _signed_word(new_fall_phase) < GROUND_SETTLE_FLOOR:
        stores[(instance_ptr + KIND) & 0xFFFFFF] = (far_kind, 2)
        stores[(instance_ptr + FALL_PHASE) & 0xFFFFFF] = (GROUND_SETTLE_RESET, 2)
        result['arm'] = 'settle-reset'
    else:
        result['arm'] = 'settle-continue'
    result['new_fall_phase'] = new_fall_phase
    result['stores'] = stores
    return result


def ground_contact_update(read, type_ptr, instance_ptr):
    """00ACA0: kind 4's own ground-contact tick -- POSITION_X steps by -4, the skip test's own two
    cell probes are at -1(a1)/+0x7F(a1), a near trigger sets KIND to 0 (00AA76), a far trigger or a
    settled fall sets KIND to KIND_FALL (2, 00AE6C)."""
    return _ground_contact_step(read, type_ptr, instance_ptr, x_delta=-4,
                                skip_low_offset=GROUND_SKIP_TEST_LOW_OFFSET,
                                skip_high_offset=GROUND_SKIP_TEST_HIGH_OFFSET,
                                near_kind=0, far_kind=KIND_FALL)


def ground_contact_update_mirror(read, type_ptr, instance_ptr):
    """00AD88: kind 5's own ground-contact tick -- the SAME shape as 00ACA0 (``ground_contact_update``),
    mirrored: POSITION_X steps by +4, the skip test's own two cell probes are at +1(a1)/+0x81(a1)
    (MIRROR_SKIP_TEST_LOW_OFFSET/MIRROR_SKIP_TEST_HIGH_OFFSET), a near trigger sets KIND to 1 (00AB50),
    a far trigger or a settled fall sets KIND to MIRROR_KIND_FALL (3, 00AED4) -- a second, distinct fall
    kind handler from 00ACA0's own (docs/gods/STATUS.md's own creature-family notes: "00AE6C and
    00AED4... at a DIFFERENT record offset")."""
    return _ground_contact_step(read, type_ptr, instance_ptr, x_delta=4,
                                skip_low_offset=MIRROR_SKIP_TEST_LOW_OFFSET,
                                skip_high_offset=MIRROR_SKIP_TEST_HIGH_OFFSET,
                                near_kind=1, far_kind=MIRROR_KIND_FALL)
