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
from .camera import FOLLOW_X, FOLLOW_Y
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


# --- 00AE6C/00AED4: the fall kind handlers -- kinds 2 and 3 of 00A772's own eight-entry table, the
# targets KIND_FALL/MIRROR_KIND_FALL name above.  A distinct shape from 00ACA0/00AD88 (docs/gods/
# STATUS.md: "a distinct 'vertical fall' shape... at a DIFFERENT record offset"): no POSITION_X step at
# all; instead FRAME_STEP (0x4, the SAME field kind_frame_offset itself reads) is cleared before an
# immediate composed call into kind_frame_offset (00AA50, called by BSR here, not a tail-jump -- this
# routine returns normally, RTS, to 00A772), then FALL_VELOCITY (0x12 -- the SAME offset
# ground_contact_update's own FALL_PHASE names for a different caller, likewise not established as the
# same field) is added to POSITION_Y and incremented (capped once it reaches FALL_VELOCITY_CEILING,
# never past).  The near test (00AD46's own (d16,An) shape again, +0x100/+0x101) then gates a THIRD
# test byte-for-byte the SAME shape as ground_contact_update's own skip test (00AE6C's own probes are
# at the SAME -1/+0x7F offsets 00ACA0 uses; 00AED4's own at the SAME +1/+0x81 offsets 00AD88 uses --
# confirmed, not coincidence) -- gated by POSITION_X's own low 5 bits being zero, exactly as
# ground_contact_update's own skip test is, but AFTER the near trigger already ran, not before it.
FALL_VELOCITY = 0x12               # instance_ptr word: this creature's own fall speed, added to
                                    # POSITION_Y every tick, incremented (capped) until FALL_VELOCITY_CEILING.
                                    # The SAME offset ground_contact_update's own FALL_PHASE names.
FALL_VELOCITY_CEILING = 0x10       # FALL_VELOCITY stops incrementing once it reaches exactly this


def _fall_kind_step(read, type_ptr, instance_ptr, *, third_low_offset, third_high_offset, near_kind, third_kind):
    """The shared shape 00AE6C and 00AED4 both run, parameterised on what differs: the third test's own
    two cell-byte offsets, and which KIND the near trigger and the third trigger each hand the creature
    off to (``fall_kind_update``/``fall_kind_update_mirror``, below, supply the ROM's own real values).

    Returns the arm (``'not-triggered'`` -- the near test never matched; ``'triggered-low5nz'`` -- the
    near test matched (either probe -- the ROM only tests D1, never which of the two set it, the same
    reasoning ground_contact_update's own near test already established) but POSITION_X's own low 5 bits are nonzero,
    so the third test never runs, KIND set to ``near_kind``; ``'triggered-third-no-match'`` -- the third
    test ran and missed, KIND stays ``near_kind``; or ``'triggered-third-match'`` -- the third test hit
    (either probe: the ROM only tests whether EITHER matched, never which, the same reasoning
    ground_contact_update's own near test uses), KIND overwritten to ``third_kind``) plus every fact the
    boundary's own cost needs."""
    type_ptr &= 0xFFFFFF
    instance_ptr &= 0xFFFFFF
    stores = {(instance_ptr + FRAME_STEP) & 0xFFFFFF: (0, 2)}
    read1 = _overlay(read, stores)
    frame = kind_frame_offset(read1, type_ptr, instance_ptr)
    velocity = read(instance_ptr + FALL_VELOCITY, 2) & 0xFFFF
    incremented = velocity != FALL_VELOCITY_CEILING
    if incremented:
        stores[(instance_ptr + FALL_VELOCITY) & 0xFFFFFF] = ((velocity + 1) & 0xFFFF, 2)
    y = read(instance_ptr + POSITION_Y, 2) & 0xFFFF
    new_y = (y + velocity) & 0xFFFF
    stores[(instance_ptr + POSITION_Y) & 0xFFFFFF] = (new_y, 2)
    read2 = _overlay(read, stores)
    grid = creature_grid_cell(read2, instance_ptr)
    cell_addr = grid['a1'] & 0xFFFFFF
    x = read(instance_ptr + POSITION_X, 2) & 0xFFFF
    near = ground_edge_test(read2, cell_addr + 0x100, x)
    result = {'frame': frame, 'velocity': velocity, 'incremented': incremented, 'y': y, 'new_y': new_y,
              'grid': grid, 'near': near, 'x': x, 'stores': dict(stores)}
    if near['arm'] not in ('cell-low', 'cell-high'):
        result['arm'] = 'not-triggered'
        return result
    masked_y = new_y & 0xFFF0
    stores[(instance_ptr + POSITION_Y) & 0xFFFFFF] = (masked_y, 2)
    stores[(instance_ptr + KIND) & 0xFFFFFF] = (near_kind, 2)
    result.update(masked_y=masked_y, stores=dict(stores))
    low5 = x & 0x1F
    result['low5'] = low5
    if low5 != 0:
        result['arm'] = 'triggered-low5nz'
        return result
    read3 = _overlay(read, stores)
    grid2 = creature_grid_cell(read3, instance_ptr)
    cell2_addr = grid2['a1'] & 0xFFFFFF
    low_byte = read3((cell2_addr + third_low_offset) & 0xFFFFFF, 1) & 0xFF
    high_byte = None
    if low_byte == GROUND_EDGE_FLAG:
        third = 'cell-low'
    else:
        high_byte = read3((cell2_addr + third_high_offset) & 0xFFFFFF, 1) & 0xFF
        third = 'cell-high' if high_byte == GROUND_EDGE_FLAG else 'no-match'
    result.update(grid2=grid2, third=third, third_high=high_byte)
    if third == 'no-match':
        result['arm'] = 'triggered-third-no-match'
    else:
        stores[(instance_ptr + KIND) & 0xFFFFFF] = (third_kind, 2)
        result['arm'] = 'triggered-third-match'
    result['stores'] = stores
    return result


def fall_kind_update(read, type_ptr, instance_ptr):
    """00AE6C: kind 2's own fall tick -- the third test's own two cell probes are at -1(a1)/+0x7F(a1)
    (the SAME offsets ground_contact_update's own skip test uses), a near trigger sets KIND to 0
    (00AA76), a third-test trigger sets KIND to 1 (00AB50)."""
    return _fall_kind_step(read, type_ptr, instance_ptr, third_low_offset=GROUND_SKIP_TEST_LOW_OFFSET,
                           third_high_offset=GROUND_SKIP_TEST_HIGH_OFFSET, near_kind=0, third_kind=1)


def fall_kind_update_mirror(read, type_ptr, instance_ptr):
    """00AED4: kind 3's own fall tick -- the SAME shape as 00AE6C (``fall_kind_update``), mirrored: the
    third test's own two cell probes are at +1(a1)/+0x81(a1) (the SAME offsets
    ground_contact_update_mirror's own skip test uses), a near trigger sets KIND to 1 (00AB50), a
    third-test trigger sets KIND to 0 (00AA76) -- the OPPOSITE assignment from 00AE6C's own."""
    return _fall_kind_step(read, type_ptr, instance_ptr, third_low_offset=MIRROR_SKIP_TEST_LOW_OFFSET,
                           third_high_offset=MIRROR_SKIP_TEST_HIGH_OFFSET, near_kind=1, third_kind=0)


# --- 00B082: the aim-cue update, the second of 00AF52's own three unconditional callees
# (docs/gods/blockers/2026-09-18-00A578.md's own "Decision on 00AF52", 19 Sep).  Every single call
# first refills a fixed 400-byte work table from thirteen ROM constants (real, unconditional -- the
# table's own purpose past this routine is not established this session), then -- unless
# AIM_CUE_SKIP_FLAG is set (real ROM, never witnessed by any of the five recordings: declined) --
# draws one word from the shared random table (``effects.next_random``) and compares it against the
# type's own threshold byte to pick between the LOW and HIGH nibble of the type's own index byte as a
# 0-3 dispatch selector into one of (up to) four bodies.  Only three of the four are ever witnessed:
#
# - index 0 (``window-mark``, ROM 00B2EC): unconditional, branch-free -- one camera-relative cell
#   offset, three bytes set to 0xFF in a second sub-table (no bounds check at all, so always applied).
# - index 1 (``quadrant-mark``, ROM 00B0FE): a fixed, DATA-INDEPENDENT sweep of exactly 32 camera-
#   relative cells (two mirrored 8-step passes, twice each -- immediate values, no data-dependent trip
#   count), each tested against the shared ``_cue_mark`` window and, in bounds, marked.
# - index 2 (``event-scan``, ROM 00B15C): walks the SAME world-event list ``event_consume`` reads
#   (``EVENT_LIST``, clamped to ``EVENT_LIST_MAX``), unconditionally marking every entry (no kind
#   filter, no early exit) -- and, only when ``EVENT_COUNT`` is exactly 0, RETRIES immediately with the
#   OTHER nibble (real ROM: swap and redispatch, ``00B0E0``) before the loop ever runs, since the loop
#   never touches the sticky flag a real (nonzero-count) scan always ends up setting once at least one
#   mark hits -- every witnessed occurrence has at least one hit, so that second, post-loop retry path
#   is real code this session never saw taken.
#
# index 3 (ROM 00B1E8, a further table dispatch) is never witnessed by any recording; a retry landing
# on index 3, on index 2 again (self, real code: the pathological case both nibbles equal 2, an
# infinite retry the ROM's own data plainly never produces) or on index 1 (untested AS a retry target,
# though the code is byte-identical to a direct index-1 dispatch) are declined by the boundary too --
# not because the arithmetic would be wrong, but because no recording proves the COMBINATION.
#
# The shared "mark" leaf (ROM 00B1AC) itself declines (real ROM, never witnessed: every mark computed
# from all five recordings' own evidence lands in bounds) when its own camera-relative cell would fall
# outside the table's own window -- the boundary raises for that arm too.
AIM_CUE_FILL_SOURCE = 0x004102          # ROM: thirteen sign-extended words (d0-d7,a1-a5 load order)
AIM_CUE_TABLE_LOW, AIM_CUE_TABLE_HIGH = 0xFFC1BA, 0xFFC34A   # 400 bytes, refilled whole every call
_AIM_CUE_FILL_REGISTERS = 13            # d0-d7 (8) + a1-a5 (5)
_AIM_CUE_FILL_LAST_REGISTERS = 9        # the eighth (final) store only covers d0-d7/a1
AIM_CUE_SKIP_FLAG = 0xFFFFF388          # word: nonzero jumps straight into the event-scan arm's own
                                         # body, skipping the whole dispatch -- unwitnessed, declined
AIM_CUE_INDEX_BYTE = 0x8                # type_ptr byte: low/high nibble select the dispatch arm
AIM_CUE_THRESHOLD_BYTE = 0x9            # type_ptr byte: the draw's own comparison threshold
AIM_CUE_MARK_BASE = 0xFFC1BA            # a2: the SAME fill table's own low address
AIM_CUE_MARK_OFFSET = 0x50              # a3 = MARK_BASE + MARK_OFFSET + offset
AIM_CUE_MARK_SPAN = 0x17C               # valid iff MARK_BASE <= a3 < MARK_BASE + MARK_SPAN
AIM_CUE_MARK_STRIDE = 0x14              # the mark's own second byte, base+STRIDE
AIM_CUE_MARK_BIAS = 8                   # 00B1AC's own subq #8 pre-adjustment (window-mark has none)
AIM_CUE_STICKY_FLAG = 0xFFFFF17C        # byte: bit 3 -- set by a successful mark (event-scan clears
                                         # it first; the quadrant loop never clears it at all)
AIM_CUE_WINDOW_BASE = 0xFFFFC20A        # index 0's own sub-table base (no bounds check); the full
                                         # 32-bit register value (`lea.l $c20a.w,a0`'s own sign
                                         # extension, GRID_TABLE's own convention) -- every existing
                                         # reader of this constant only ever uses it `& 0xFFFF` or
                                         # `& 0xFFFFFF` (RAM addressing, unaffected by the top byte);
                                         # aim_target_scan (00B724) is the first caller of
                                         # aim_window_address that needs the real register value, and
                                         # the previous `0xFFC20A` literal was silently wrong in that
                                         # top byte -- never caught because 00B32E's own boundary plan
                                         # (aim_window_address_plan) reconstructs a0 independently
                                         # (`0xFFFF0000 | ...`) rather than calling this function.
AIM_CUE_WINDOW_STRIDE_1, AIM_CUE_WINDOW_STRIDE_2 = 0x14, 0x28


_AIM_CUE_FILL_ORDER = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'a1', 'a2', 'a3', 'a4', 'a5')


def _cue_fill_registers(read):
    """00B086: the thirteen ROM words at AIM_CUE_FILL_SOURCE, sign-extended to 32 bits, in
    ``movem.w`` load order -- every recording's own evidence has all thirteen at zero, but this reads
    the ROM rather than assume it."""
    words = [read((AIM_CUE_FILL_SOURCE + 2 * i) & 0xFFFFFF, 2) & 0xFFFF for i in range(_AIM_CUE_FILL_REGISTERS)]
    longs = [(w - 0x10000 if w & 0x8000 else w) & 0xFFFFFFFF for w in words]
    return dict(zip(_AIM_CUE_FILL_ORDER, longs))


def _cue_fill_stores(read):
    """00B086-00B0AE: the thirteen ROM words at AIM_CUE_FILL_SOURCE (``_cue_fill_registers``), tiled
    by seven full 13-register ``movem.l -(a0)`` stores then one 9-register (d0-d7/a1) partial store
    into AIM_CUE_TABLE_LOW..AIM_CUE_TABLE_HIGH -- the SAME 400 bytes every single call, never read
    back by this routine itself."""
    longs = [_cue_fill_registers(read)[name] for name in _AIM_CUE_FILL_ORDER]
    stores = {}
    address = AIM_CUE_TABLE_HIGH
    for block in range(8):
        count = _AIM_CUE_FILL_REGISTERS if block < 7 else _AIM_CUE_FILL_LAST_REGISTERS
        address -= 4 * count
        for slot in range(count):
            value = longs[slot]
            for byte_index in range(4):
                stores[(address + 4 * slot + byte_index) & 0xFFFFFF] = (value >> (8 * (3 - byte_index))) & 0xFF
    return stores


def _cue_offset(dx, dy, bias):
    """The shared ``(asr#5) + 5 + 20*(asr#4)`` scaling both the window-mark arm and the shared mark
    leaf use (the mark leaf biases each axis by AIM_CUE_MARK_BIAS first; the window arm does not)."""
    a = _signed_word((dx - bias) & 0xFFFF) >> 5
    b = _signed_word((dy - bias) & 0xFFFF) >> 4
    return (a + 5 + 20 * b) & 0xFFFF


def _cue_mark(dx, dy):
    """00B1AC: the shared 'mark' leaf both the quadrant loop and the event scan call -- a camera-
    relative cell test against AIM_CUE_MARK_BASE's own [OFFSET, OFFSET+SPAN) window; in bounds, two
    bytes are set to 0xFF (a read-modify-write bit, not shown here -- the caller ORs it once per
    successful mark) at ``address``/``address+STRIDE``.  Returns ``None`` on a miss (real ROM, never
    witnessed by any recording)."""
    offset = _signed_word(_cue_offset(dx, dy, AIM_CUE_MARK_BIAS))
    address = (AIM_CUE_MARK_BASE + AIM_CUE_MARK_OFFSET + offset) & 0xFFFFFFFF
    if address < AIM_CUE_MARK_BASE or address >= AIM_CUE_MARK_BASE + AIM_CUE_MARK_SPAN:
        return None
    return (address & 0xFFFFFF, (address + AIM_CUE_MARK_STRIDE) & 0xFFFFFF)


def _cue_window_mark(read):
    """00B2EC: dispatch index 0 -- unconditional, branch-free; the SAME scaling as ``_cue_mark`` but
    with no bias and no bounds check, so always applied."""
    dx = (read(GRID_X, 2) - read(FOLLOW_X, 2)) & 0xFFFF
    dy = (read(GRID_Y, 2) - read(FOLLOW_Y, 2)) & 0xFFFF
    offset = _signed_word(_cue_offset(dx, dy, 0))
    base = (AIM_CUE_WINDOW_BASE + offset) & 0xFFFFFFFF
    addresses = (base & 0xFFFFFF, (base + AIM_CUE_WINDOW_STRIDE_1) & 0xFFFFFF,
                (base + AIM_CUE_WINDOW_STRIDE_2) & 0xFFFFFF)
    return {'offset': offset, 'addresses': addresses}


def _cue_quadrant_marks(read):
    """00B0FE: dispatch index 1 -- two mirrored 8-step passes (d0 stepping while d1 stays fixed, then
    d1 stepping while d0 stays fixed), each pass run twice (the second with its own fixed value
    negated -- ALWAYS, since the first pass's own fixed value is always negative on entry): exactly 32
    calls into the shared mark leaf, immediate values only, no data dependence in the trip count."""
    dx0 = (read(GRID_X, 2) - read(FOLLOW_X, 2)) & 0xFFFF
    dy0 = (read(GRID_Y, 2) - read(FOLLOW_Y, 2)) & 0xFFFF
    marks = []
    for d1_fixed in (-64, 64):
        d0 = -64
        for _ in range(8):
            marks.append(_cue_mark((d0 + dx0) & 0xFFFF, (d1_fixed + dy0) & 0xFFFF))
            d0 += 0x10
    for d0_fixed in (-64, 64):
        d1 = -64
        for _ in range(8):
            marks.append(_cue_mark((d0_fixed + dx0) & 0xFFFF, (d1 + dy0) & 0xFFFF))
            d1 += 0x10
    return marks


def _cue_event_scan(read):
    """00B15C: dispatch index 2 -- walks EVENT_LIST (clamped to EVENT_LIST_MAX, the SAME shared list
    and clamp event_consume reads), camera-relative, marking every entry; unlike event_consume this
    never inspects an entry's own kind and never stops early.  ``'count-clamped'`` (EVENT_COUNT >
    EVENT_LIST_MAX) declines, unwitnessed.  On EVENT_COUNT == 0 the loop never runs at all -- the
    caller retries with the OTHER dispatch nibble (see ``aim_cue_update``)."""
    count = read(EVENT_COUNT, 2) & 0xFFFF
    if count == 0:
        return {'arm': 'empty', 'count': 0}
    if count > EVENT_LIST_MAX:
        return {'arm': 'count-clamped', 'count': count}
    marks = []
    address = EVENT_LIST
    for _ in range(count):
        dx = (read(address & 0xFFFFFF, 2) - read(FOLLOW_X, 2)) & 0xFFFF
        dy = (read((address + 2) & 0xFFFFFF, 2) - read(FOLLOW_Y, 2)) & 0xFFFF
        marks.append(_cue_mark(dx, dy))
        address = (address + EVENT_LIST_STRIDE) & 0xFFFFFFFF
    return {'arm': 'scanned', 'count': count, 'marks': marks}


def aim_cue_update(read, type_ptr):
    """00B082: the whole aim-cue update -- the fill, the skip-flag gate, the draw-gated dispatch, and
    (index 2 only) the empty-count retry.  Returns the fill's own stores plus an ``'arm'`` tag:
    ``'skip-flag'`` (declined), ``'window-mark'``, ``'quadrant-mark'``, ``'event-scan'`` (with its own
    ``scan['arm']`` of ``'scanned'`` or ``'count-clamped'``, declined), or ``'retry'`` (the empty-count
    redispatch, itself ``'window-mark'``-shaped, ``'quadrant-mark'``-shaped, or declined when the
    retried index is 2 or 3)."""
    type_ptr &= 0xFFFFFF
    fill = _cue_fill_stores(read)
    if read(AIM_CUE_SKIP_FLAG, 2) & 0xFFFF:
        return {'arm': 'skip-flag', 'fill': fill}
    index_byte = read((type_ptr + AIM_CUE_INDEX_BYTE) & 0xFFFFFF, 1) & 0xFF
    low, high = index_byte & 0xF, (index_byte >> 4) & 0xF
    threshold = read((type_ptr + AIM_CUE_THRESHOLD_BYTE) & 0xFFFFFF, 1) & 0xFF
    draw = effects.next_random(read)
    masked = draw['value'] & 0x7F
    swap = masked > threshold
    index = high if swap else low
    base = {'fill': fill, 'draw': draw, 'masked': masked, 'threshold': threshold, 'low': low,
            'high': high, 'swap': swap, 'index': index}
    if index == 0:
        return {**base, 'arm': 'window-mark', 'window': _cue_window_mark(read)}
    if index == 1:
        return {**base, 'arm': 'quadrant-mark', 'marks': _cue_quadrant_marks(read)}
    if index == 2:
        scan = _cue_event_scan(read)
        if scan['arm'] != 'empty':
            return {**base, 'arm': 'event-scan', 'scan': scan}
        retry_index = low if swap else high
        result = {**base, 'arm': 'retry', 'retry_index': retry_index}
        if retry_index == 0:
            result['retry'] = {'arm': 'window-mark', 'window': _cue_window_mark(read)}
        elif retry_index == 1:
            result['retry'] = {'arm': 'quadrant-mark', 'marks': _cue_quadrant_marks(read)}
        else:
            result['retry'] = {'arm': 'undispatched'}   # index 2 (self) or 3: never witnessed
        return result
    return {**base, 'arm': 'undispatched'}


# --- 00B02A / 00B05A: the aim pool reset and add (docs/gods/blockers/2026-09-18-00A578.md's own
# "Decision on 00AF52", 19 Sep -- the first of 00AF52's own three further calls, per the supervisor's
# own order).  One 256-byte, 32-slot (8 bytes each) work-RAM table, two entries: 00B02A is an
# unconditional register-save, refill-from-ROM-constants (the SAME AIM_CUE_FILL_SOURCE 00B082 already
# reads, a different tiling -- four full 13-register blocks then one 12-register block, dropping A5)
# and a counter clear, then a full register restore -- a plain reset, no branch at all.  00B05A is the
# ADD: gated on the counter (AIM_POOL_COUNT) not yet at AIM_POOL_SLOTS, it scans the table for the
# first slot whose own leading long is zero and writes four caller words there (D0, D1, D7, D2),
# incrementing the counter -- the SAME "scan a fixed-stride table for a free long-tested slot, write
# four words, bump a counter" shape ``hazard.effect_pool_add``/``timers._spawn`` already prove.  Every
# witnessed occurrence (across all five recordings) finds a free slot within the first four positions;
# the counter-gate ('pool-full-by-count') and a fully exhausted scan ('pool-full-scanned') are real
# ROM, never witnessed: the boundary declines both.
AIM_POOL_LOW, AIM_POOL_HIGH = 0xFFFF40B2, 0xFFFF41B2   # 256 bytes, 32 slots of 8
AIM_POOL_STRIDE = 8
AIM_POOL_SLOTS = 32
AIM_POOL_COUNT = 0xFFFFF2AE            # word: this pool's own occupancy counter
_AIM_POOL_FILL_ORDER = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'a1', 'a2', 'a3', 'a4', 'a5')
_AIM_POOL_FILL_LAST_REGISTERS = 12     # the final (5th) store drops A5 (d0-d7/a1-a4 only)


def _aim_pool_fill_stores(read):
    """00B02E-00B04C: the SAME thirteen ROM words AIM_CUE_FILL_SOURCE names (``_cue_fill_registers``),
    tiled by four full 13-register ``movem.l -(a0)`` stores then one 12-register (d0-d7/a1-a4) partial
    store into AIM_POOL_LOW..AIM_POOL_HIGH -- 256 bytes, every single call."""
    longs = [_cue_fill_registers(read)[name] for name in _AIM_POOL_FILL_ORDER]
    stores = {}
    address = AIM_POOL_HIGH
    for block in range(5):
        count = _AIM_CUE_FILL_REGISTERS if block < 4 else _AIM_POOL_FILL_LAST_REGISTERS
        address -= 4 * count
        for slot in range(count):
            value = longs[slot]
            for byte_index in range(4):
                stores[(address + 4 * slot + byte_index) & 0xFFFFFF] = (value >> (8 * (3 - byte_index))) & 0xFF
    return stores


def aim_pool_reset(read):
    """00B02A: refill the 256-byte pool from ROM constants and clear AIM_POOL_COUNT -- unconditional,
    no branch."""
    stores = _aim_pool_fill_stores(read)
    stores[AIM_POOL_COUNT & 0xFFFFFF] = 0
    stores[(AIM_POOL_COUNT + 1) & 0xFFFFFF] = 0
    return {'stores': stores}


def aim_window_address(read, d0, d1):
    """00B32E: the SAME camera-relative scaling ``aim_cue_update``'s own window-mark arm uses (bias
    0), but the caller supplies the raw position directly (D0/D1) instead of this routine reading
    GRID_X/GRID_Y itself -- a pure address computation into the AIM_CUE_WINDOW_BASE sub-table, no
    store, called (with 00AF3C, the shared grid-cell lookup) from every one of 00AF52's own further
    creature-targeting callees (00B724, 00B7DA, 00B6AE, ...)."""
    dx = (d0 - read(FOLLOW_X, 2)) & 0xFFFF
    dy = (d1 - read(FOLLOW_Y, 2)) & 0xFFFF
    offset = _signed_word(_cue_offset(dx, dy, 0))
    return (AIM_CUE_WINDOW_BASE + offset) & 0xFFFFFFFF


def aim_pool_add(read, d0, d1, d7, d2):
    """00B05A: scan AIM_POOL_LOW.. for the first slot whose own leading long (its own first two words)
    is zero, and write ``d0, d1, d7, d2`` there (in that order), incrementing AIM_POOL_COUNT.  Returns
    ``'arm'``: ``'found'`` (with the slot index and address), ``'pool-full-by-count'`` (the counter
    already at AIM_POOL_SLOTS, unwitnessed) or ``'pool-full-scanned'`` (every slot occupied,
    unwitnessed)."""
    count = read(AIM_POOL_COUNT, 2) & 0xFFFF
    if count >= AIM_POOL_SLOTS:
        return {'arm': 'pool-full-by-count', 'count': count}
    address = AIM_POOL_LOW
    skipped = 0
    for index in range(AIM_POOL_SLOTS):
        leading = read(address & 0xFFFFFF, 4)
        if leading == 0:
            stores = {}
            for offset, value in ((0, d0), (2, d1), (4, d7), (6, d2)):
                stores[(address + offset) & 0xFFFFFF] = (value >> 8) & 0xFF
                stores[(address + offset + 1) & 0xFFFFFF] = value & 0xFF
            stores[AIM_POOL_COUNT & 0xFFFFFF] = ((count + 1) >> 8) & 0xFF
            stores[(AIM_POOL_COUNT + 1) & 0xFFFFFF] = (count + 1) & 0xFF
            return {'arm': 'found', 'index': index, 'address': address, 'skipped': skipped,
                    'count': count, 'stores': stores}
        skipped += 1
        address = (address + AIM_POOL_STRIDE) & 0xFFFFFFFF
    return {'arm': 'pool-full-scanned', 'count': count, 'skipped': skipped}


# --- 00B524 / 00B62A: the aim ray probe and mark-store (docs/gods/blockers/2026-09-18-00A578.md's own
# "Decision on 00B588", 19 Sep) -- the found-only probe and the store-capable evaluator 00B354/00B440's
# own ray-march (each its own bounded walk along the eight-entry 00AE4C table) calls at specific steps,
# and 00B588's own outer loop calls directly after each ray pass.  Both run the SAME step-limit test,
# the SAME camera-relative box test, and the SAME window-mark tile read as 00B6AE's own inner loop
# (_resolve_slot, above) -- the shape the Decision named "byte-for-byte the same bounding-box +
# window-mark tile logic" -- but each derives its own step index (D7) from a different source: 00B524's
# own D4 (a local step accumulator the ray march itself threads) versus 00B62A's own AIM_RAY_STEP_INDEX
# (F2D4, written by the ray march's own tail).  A3 is the current AIM_POOL entry (00B588's own outer
# loop variable: +4 a per-entry base index folded into D7, +6 a per-entry flag word); A4 is the
# creature TYPE pointer (+0xD the walk's own per-type step limit, the SAME AIM_SEARCH_STEP_LIMIT_OFFSET
# byte aim_target_scan's own walk reads).  00B62A alone stores (through the already-recovered
# aim_pool_add) and alone runs a dedup guard against A5 (bounds-tested against (a5)/2(a5) -- this
# session's own recovery does not confirm which caller sets A5, the same fact the escalation itself
# left open); 00B524 only ever reports a found-tail update.
AIM_RAY_STEP_INDEX = 0xFFFFF2D4      # word: written by 00B354/00B440's own tail (D4, the ray's own
                                      # local step count) -- 00B62A's own D7 base
AIM_RAY_CONTEXT_FLAG = 0xFFFFF2D2    # word: the pass's own fallback flag (00B588's own move.w #n,f2d2
                                      # before each of its four ray-march + 00B62A passes) -- the
                                      # found/store tail's own flag source when A3+4 is zero
AIM_PROBE_LOW_BIAS = -0x40           # camera-relative low bound, both axes (signed; ble, strict)
AIM_PROBE_Y_HIGH = 0xE0              # camera-relative Y high bound (signed; bge, strict) -- X reuses
                                      # AIM_SEARCH_X_LIMIT (the SAME 0x160 aim_target_scan's own walk
                                      # bounds against)


def _aim_probe_bound(read, d0, d1):
    """The camera-relative box test 00B524 and 00B62A both run right after their own step-limit test:
    returns (dx, dy, arm) where arm names WHICH of the four sequential ROM compares rejects the point
    (``'bound-x-low'``, ``'bound-x-high'``, ``'bound-y-low'``, ``'bound-y-high'``) or is ``None`` when
    all four pass.  Both D2 (dx) and D3 (dy) are computed by the ROM UNCONDITIONALLY before any of the
    four compares (two move.w/sub.w pairs back to back) -- dy is real and returned even when an x
    bound already rejects the point, since it is still the exact register value the routine exits
    with on every 'bound-x-*' arm."""
    dx = _signed_word((d0 - read(FOLLOW_X, 2)) & 0xFFFF)
    dy = _signed_word((d1 - read(FOLLOW_Y, 2)) & 0xFFFF)
    if dx <= AIM_PROBE_LOW_BIAS:
        return dx, dy, 'bound-x-low'
    if dx >= AIM_SEARCH_X_LIMIT:
        return dx, dy, 'bound-x-high'
    if dy <= AIM_PROBE_LOW_BIAS:
        return dx, dy, 'bound-y-low'
    if dy >= AIM_PROBE_Y_HIGH:
        return dx, dy, 'bound-y-high'
    return dx, dy, None


def _aim_found_update(read, d7, entry_ptr):
    """The found-tail shared, byte-for-byte, by 00B524's own probe (B566-B57E) and 00B62A's own
    evaluator (B690-B6AC): D7 admitted only when it is <= the running AIM_SEARCH_BEST_INDEX (unsigned
    cmp.w/bhi); on admission AIM_SEARCH_BEST_FLAG is set from ``entry_ptr + 6`` when the word at
    ``entry_ptr + 4`` is nonzero, else from AIM_RAY_CONTEXT_FLAG, and AIM_SEARCH_BEST_INDEX from D7.
    A worse D7 (real ROM, never witnessed by any recording) is declined by the boundary."""
    entry_ptr &= 0xFFFFFF
    best_index_before = read(AIM_SEARCH_BEST_INDEX & 0xFFFFFF, 2) & 0xFFFF
    if (d7 & 0xFFFF) > best_index_before:
        return {'arm': 'no-improvement', 'best_index_before': best_index_before}
    if read((entry_ptr + 4) & 0xFFFFFF, 2) & 0xFFFF:
        flag = read((entry_ptr + 6) & 0xFFFFFF, 2) & 0xFFFF
    else:
        flag = read(AIM_RAY_CONTEXT_FLAG & 0xFFFFFF, 2) & 0xFFFF
    return {'arm': 'found', 'flag': flag}


def aim_probe_mark(read, d0, d1, d4, a3, a4):
    """00B524: a found-only probe over one ray-march step.  D7 = (signed D4 >> 1) + word(A3 + 4), word
    arithmetic (D4 the ray's own local step accumulator).  ``'step-limit'`` when D7's own low byte
    exceeds the type's own limit byte (A4 + AIM_SEARCH_STEP_LIMIT_OFFSET, signed cmp.b); a
    ``'bound-*'`` arm when the camera-relative box around (d0, d1) rejects the point
    (_aim_probe_bound); ``'clear'`` when the window-mark tile at
    ``aim_window_address(d0, d1) + AIM_CUE_WINDOW_STRIDE_1`` is not negative (tile >= 0, no update);
    otherwise the found-tail (_aim_found_update) against A3 -- ``'found'`` or ``'no-improvement'``."""
    from .grid import _signed_byte
    a3 &= 0xFFFFFF
    a4 &= 0xFFFFFF
    d7 = ((_signed_word(d4) >> 1) + read((a3 + 4) & 0xFFFFFF, 2)) & 0xFFFF
    limit = read((a4 + AIM_SEARCH_STEP_LIMIT_OFFSET) & 0xFFFFFF, 1) & 0xFF
    if _signed_byte(d7 & 0xFF) > _signed_byte(limit):
        return {'arm': 'step-limit', 'd7': d7}
    dx, dy, bound_arm = _aim_probe_bound(read, d0, d1)
    if bound_arm is not None:
        return {'arm': bound_arm, 'd7': d7, 'dx': dx, 'dy': dy}
    a0 = (aim_window_address(read, d0, d1) + AIM_CUE_WINDOW_STRIDE_1) & 0xFFFFFFFF
    tile = read(a0 & 0xFFFFFF, 1) & 0xFF
    if _signed_byte(tile) >= 0:
        return {'arm': 'clear', 'd7': d7, 'dx': dx, 'dy': dy, 'a0': a0, 'tile': tile}
    result = _aim_found_update(read, d7, a3)
    result.update(d7=d7, dx=dx, dy=dy, a0=a0, tile=tile)
    return result


def aim_probe_mark_store(read, d0, d1, a3, a4, a5):
    """00B62A: the STORE-capable evaluator 00B588 calls directly after each ray pass.  D7 = (signed
    AIM_RAY_STEP_INDEX >> 2) + word(A3 + 4) -- the SAME step-limit and camera-relative box tests as
    aim_probe_mark, and the SAME found-tail on a negative tile (no store).  On a non-negative tile that
    is not pruned (tile == 0, or tile > 0 and D7 < tile, both signed byte) a dedup guard against A5
    skips the store when (d0, d1) already equals (a5)/2(a5); otherwise the tile byte is set to D7 and
    aim_pool_add(d0, d1, d7, flag) runs, flag the SAME tst.w-A3+4 selection aim_probe_mark's own
    found-tail uses.  ``'pruned'`` (tile > 0 and D7 >= tile, signed) declines nothing -- it is a real,
    witnessed miss with no update at all."""
    from .grid import _signed_byte
    a3 &= 0xFFFFFF
    a4 &= 0xFFFFFF
    a5 &= 0xFFFFFF
    d7 = ((_signed_word(read(AIM_RAY_STEP_INDEX & 0xFFFFFF, 2)) >> 2) + read((a3 + 4) & 0xFFFFFF, 2)) & 0xFFFF
    limit = read((a4 + AIM_SEARCH_STEP_LIMIT_OFFSET) & 0xFFFFFF, 1) & 0xFF
    if _signed_byte(d7 & 0xFF) > _signed_byte(limit):
        return {'arm': 'step-limit', 'd7': d7}
    dx, dy, bound_arm = _aim_probe_bound(read, d0, d1)
    if bound_arm is not None:
        return {'arm': bound_arm, 'd7': d7, 'dx': dx, 'dy': dy}
    a0 = (aim_window_address(read, d0, d1) + AIM_CUE_WINDOW_STRIDE_1) & 0xFFFFFFFF
    tile = read(a0 & 0xFFFFFF, 1) & 0xFF
    stile = _signed_byte(tile)
    if stile < 0:
        result = _aim_found_update(read, d7, a3)
        result.update(d7=d7, dx=dx, dy=dy, a0=a0, tile=tile)
        return result
    if stile > 0 and _signed_byte(d7 & 0xFF) >= stile:
        return {'arm': 'pruned', 'd7': d7, 'dx': dx, 'dy': dy, 'a0': a0, 'tile': tile}
    if (d0 & 0xFFFF) == (read(a5, 2) & 0xFFFF) and (d1 & 0xFFFF) == (read((a5 + 2) & 0xFFFFFF, 2) & 0xFFFF):
        return {'arm': 'dedup', 'd7': d7, 'dx': dx, 'dy': dy, 'a0': a0, 'tile': tile}
    if read((a3 + 4) & 0xFFFFFF, 2) & 0xFFFF:
        flag = read((a3 + 6) & 0xFFFFFF, 2) & 0xFFFF
    else:
        flag = read(AIM_RAY_CONTEXT_FLAG & 0xFFFFFF, 2) & 0xFFFF
    add_result = aim_pool_add(read, d0 & 0xFFFF, d1 & 0xFFFF, d7, flag)
    return {'arm': 'store', 'd7': d7, 'dx': dx, 'dy': dy, 'a0': a0, 'tile': tile, 'flag': flag,
            'add_result': add_result}


# --- 00B354 / 00B440: the directional ray march (docs/gods/blockers/2026-09-18-00A578.md's own
# "Decision on 00B588", 19 Sep) -- 00B588's own outer loop runs each of these, one per AIM_POOL entry,
# for a caller-supplied starting D5 (7 or 13, doubled here to 14 or 26) over the SAME eleven-word table
# at 00AE4C the Decision itself read (eight real (dx, dy) steps, an upward arc; what follows is other
# ROM data).  Neither routine has a save/restore frame of its own: A3 (the current AIM_POOL entry) and
# A4 (the creature TYPE pointer) pass straight through to every aim_probe_mark call, and the two probe
# calls' own internal CCR and stack residue persist into the caller exactly as the machine leaves them
# -- a real internal call composition, the same class of fact 00B082's own session first found.
#
# This is a literal transcription of the ROM's own block structure (the census showed 200+ real path
# classes per direction on four recordings -- an outer loop that revisits its own table-lookup block
# from two different entry points, not a simple bounded count), not a shape this module tries to
# summarize: each named block below is one ROM label, walked exactly as 00B354/00B440 walk it, so that
# every real occurrence the tracer replays is also a real path through this function.  Grid solid tests
# read the SAME FOOTPRINT_GRID layer 0063FA/00FDB8/aim_target_scan already prove.
AIM_RAY_TABLE = 0x00AE4C                # ROM: eight real (dx, dy) word-pair steps, then other data;
                                         # read at a SIGNED word offset (D5), so entries at and before
                                         # the label are real too (the routine's own D5 walk goes
                                         # negative before it stops)
AIM_RAY_ROW_STRIDE = 0x80               # == grid.GRID_ROW_BYTES
AIM_RAY_TAIL_OFFSET = 0x100             # two rows down -- the SAME footing aim_target_scan's own walk
                                         # gates on
AIM_RAY_NEAR_STEP = 4                   # the per-outer-step micro x-nudge (phase A), 1/8 of a cell
AIM_RAY_SENTINEL = -0xA                 # moveq #$f6 -- forced on a wall hit, and once more at natural
                                         # exhaustion
AIM_RAY_SENTINEL_STOP = -0xC            # the value that ends the outer loop (sentinel - 2)


def _aim_ray_march(read, d0, d1, d5_in, a2, a3, a4, forward):
    """00B354 (``forward=True``) / 00B440 (``forward=False``): see the module note above.  Returns a
    dict with the exit register values (``d0``..``d5``, ``a0``, ``a2``), ``events`` (every ROM
    instruction executed, as ``(symbolic_name, taken_or_None, sr_op)`` in order -- the boundary's own
    cost and CCR bookkeeping replays this list against a cost table the tracer itself derived; `sr_op`
    is ``None`` for an instruction that does not touch the CCR, ``('probe', index)`` for a call whose
    own exit CCR becomes the running one, or a ``(kind, ...)`` tuple ('cmp'/'add'/'sub'/'logic'/'asr1')
    naming the exact flags the boundary's own helpers already compute for every other Gods region) and
    ``probes`` (the aim_probe_mark calls made, in order, each ``(symbolic_name, d0, d1, d2, d3, d4,
    result)`` -- the caller's own register file AT the call, needed to reproduce the callee's own exit
    CCR and stack residue exactly, plus its already-computed `result`)."""
    d0 &= 0xFFFF
    d1 &= 0xFFFF
    a2 &= 0xFFFFFFFF
    events = []

    def emit(name, taken=None, sr=None):
        events.append((name, taken, sr))

    d2 = d0 & 0x1F
    emit('MOVEQ_D2', sr=('logic', 0x1F, 2))
    d3 = d1 & 0xF
    emit('MOVEQ_D3', sr=('logic', 0xF, 2))
    emit('AND_D2', sr=('logic', d2, 2))
    emit('AND_D3', sr=('logic', d3, 2))
    d5 = (d5_in + d5_in) & 0xFFFF
    emit('ADD_D5D5', sr=('add', d5_in & 0xFFFF, d5_in & 0xFFFF, 2))
    d4 = 0
    emit('MOVEQ_D4', sr=('logic', 0, 2))

    probes = []
    d5_upper_reset = False   # moveq #$f6,d5 (a wall hit, or the never-witnessed d5-underflow fallback)
                              # sign-extends -- the ONLY thing that ever changes D5's own upper half
                              # away from the caller's own entry value (add.w/subq.w never touch it)
    a0 = AIM_RAY_TABLE & 0xFFFFFFFF   # only meaningful once TABLE runs at least once -- always does
    block = 'HEAD'
    steps = 0
    while True:
        steps += 1
        if steps > 5000:
            raise RuntimeError('aim ray march: block dispatch did not terminate (a real translation bug)')

        if block == 'HEAD':
            d4_before = d4
            d4 = (d4 + 1) & 0xFFFF
            emit('ADDQ_D4', sr=('add', d4_before, 1, 2))
            emit('CMP_NEAR', sr=('cmp', d5, AIM_RAY_SENTINEL & 0xFFFF, 2))
            near_skip = _signed_word(d5) < AIM_RAY_SENTINEL
            emit('BLT_NEAR', near_skip)
            block = 'DISPATCH' if near_skip else 'PHASE_A'
            continue

        if block == 'PHASE_A':
            emit('TST_D2', sr=('logic', d2, 2))
            has_nudge = d2 != 0
            emit('BNE_NUDGE', has_nudge)
            blocked = False
            if not has_nudge:
                if forward:
                    solid_addrs = ((a2 + 1) & 0xFFFFFF, (a2 + 1 + AIM_RAY_ROW_STRIDE) & 0xFFFFFF)
                else:
                    solid_addrs = ((a2 - 1) & 0xFFFFFF, (a2 - 1 + AIM_RAY_ROW_STRIDE) & 0xFFFFFF)
                s1 = read(solid_addrs[0], 1) & 0xFF
                emit('CMP_SOLID1', sr=('cmp', s1, 1, 1))
                t1 = s1 == 1
                emit('BEQ_SOLID1', t1)
                if t1:
                    blocked = True
                else:
                    s2 = read(solid_addrs[1], 1) & 0xFF
                    emit('CMP_SOLID2', sr=('cmp', s2, 1, 1))
                    t2 = s2 == 1
                    emit('BEQ_SOLID2', t2)
                    if t2:
                        blocked = True
            if not blocked:
                if forward:
                    d0_before = d0
                    d0 = (d0 + AIM_RAY_NEAR_STEP) & 0xFFFF
                    emit('ADDQ_D0', sr=('add', d0_before, AIM_RAY_NEAR_STEP, 2))
                    d2_before = d2
                    d2raw = (d2 + AIM_RAY_NEAR_STEP) & 0xFFFF
                    emit('ADDQ_D2', sr=('add', d2_before, AIM_RAY_NEAR_STEP, 2))
                    d2 = d2raw & 0x1F
                    emit('ANDI_D2', sr=('logic', d2, 2))
                    wrapped = d2 == 0
                    emit('BNE_WRAP', not wrapped)
                    if wrapped:
                        emit('ADDQ_A2')
                        a2 = (a2 + 1) & 0xFFFFFFFF
                else:
                    d0_before = d0
                    d0 = (d0 - AIM_RAY_NEAR_STEP) & 0xFFFF
                    emit('SUBQ_D0', sr=('sub', d0_before, AIM_RAY_NEAR_STEP, 2))
                    d2_before = d2
                    d2raw = (d2 - AIM_RAY_NEAR_STEP) & 0xFFFF
                    emit('SUBQ_D2', sr=('sub', d2_before, AIM_RAY_NEAR_STEP, 2))
                    wrapped = bool(d2raw & 0x8000)
                    emit('BPL_NOWRAP', not wrapped)
                    if wrapped:
                        emit('SUBQ_A2')
                        a2 = (a2 - 1) & 0xFFFFFFFF
                        emit('MOVEQ_D2B', sr=('logic', 0x1C, 2))
                        d2 = 0x1C
                    else:
                        d2 = d2raw
            block = 'DISPATCH'
            continue

        if block == 'DISPATCH':
            emit('TST_D5', sr=('logic', d5, 2))
            gt = _signed_word(d5) > 0
            emit('BGT_TABLE', gt)
            if gt:
                block = 'TABLE'
                continue
            lt = _signed_word(d5) < 0
            emit('BLT_TAIL', lt)
            if lt:
                block = 'TAIL'
                continue
            emit('BSR_PROBE1', True)
            result = aim_probe_mark(read, d0, d1, d4, a3, a4)
            probes.append(('PROBE1', d0, d1, d2, d3, d4, result))
            emit('_PROBE_SR', sr=('probe', len(probes) - 1))
            if 'a0' in result:
                a0 = result['a0'] & 0xFFFFFFFF
            read = _overlay(read, _aim_probe_overlay_stores(result))
            block = 'TAIL'
            continue

        if block == 'TABLE':
            emit('LEA_TABLE')
            a0 = AIM_RAY_TABLE & 0xFFFFFFFF
            table_addr = (AIM_RAY_TABLE + _signed_word(d5)) & 0xFFFFFF
            table_val = read(table_addr, 2)
            table_val = table_val - 0x10000 if table_val & 0x8000 else table_val
            d1_before = d1
            d1 = (d1 + table_val) & 0xFFFF
            emit('ADD_D1TAB', sr=('add', d1_before, table_val & 0xFFFF, 2))
            d3_before = d3
            d3 = (d3 + table_val) & 0xFFFF
            emit('ADD_D3TAB', sr=('add', d3_before, table_val & 0xFFFF, 2))
            up = bool(d3 & 0x8000)
            emit('BPL_ROWX', not up)
            if up:
                d3_before2 = d3
                d3 = (d3 + 0x10) & 0xFFFF
                emit('ADDI_D3A', sr=('add', d3_before2, 0x10, 2))
                a2 = (a2 - AIM_RAY_ROW_STRIDE) & 0xFFFFFFFF
                emit('LEA_ROWUP')
                emit('BRA_MERGE', True)
            else:
                emit('CMP_D3_F', sr=('cmp', d3, 0xF, 2))
                down = _signed_word(d3) > 0xF
                emit('BLE_MERGE', not down)
                if down:
                    d3_before2 = d3
                    d3 = (d3 - 0x10) & 0xFFFF
                    emit('SUBI_D3', sr=('sub', d3_before2, 0x10, 2))
                    a2 = (a2 + AIM_RAY_ROW_STRIDE) & 0xFFFFFFFF
                    emit('LEA_ROWDN')
            block = 'WALL'
            continue

        if block == 'WALL':
            solid_here = read(a2, 1) & 0xFF
            emit('CMP_WALL', sr=('cmp', solid_here, 1, 1))
            hit = solid_here == 1
            emit('BEQ_WALL', hit)
            if not hit:
                low = _signed_word(d2) < 8
                emit('CMP_D2_8B', sr=('cmp', d2, 8, 2))
                emit('BLT_CONT', low)
                if low:
                    block = 'LOOPBACK'
                    continue
                adj = read((a2 + 1) & 0xFFFFFF, 1) & 0xFF
                emit('CMP_WALL2', sr=('cmp', adj, 1, 1))
                hit = adj == 1
                emit('BNE_CONT', not hit)
                if not hit:
                    block = 'LOOPBACK'
                    continue
            d1 = d1 & 0xFFF0
            emit('ANDI_D1B', sr=('logic', d1, 2))
            d3 = 0
            emit('CLR_D3', sr=('logic', 0, 2))
            d1_before = d1
            d1 = (d1 + 0x10) & 0xFFFF
            emit('ADDI_D1B', sr=('add', d1_before, 0x10, 2))
            a2 = (a2 + AIM_RAY_ROW_STRIDE) & 0xFFFFFFFF
            emit('LEA_ROWB')
            emit('PUSH_D4', sr=('logic', d4, 2))
            d4_saved = d4
            d4_new = 0xC
            emit('MOVEQ_D4C', sr=('logic', 0xC, 2))
            d4_new_before = d4_new
            d4_new = (d4_new + d5) & 0xFFFF
            emit('ADD_D5D4', sr=('add', d4_new_before, d5, 2))
            d4_shift_before = d4_new
            d4_new = _signed_word(d4_new) >> 1
            emit('ASR_D4', sr=('asr1', d4_shift_before, 2))
            d4_new &= 0xFFFF
            d4 = (d4_new + d4_saved) & 0xFFFF
            emit('POP_D4', sr=('add', d4_new, d4_saved, 2))
            d5 = AIM_RAY_SENTINEL & 0xFFFF
            d5_upper_reset = True
            emit('RESET_D5', sr=('logic', d5, 2))
            block = 'LOOPBACK'
            continue

        if block == 'LOOPBACK':
            d5_before = d5
            d5 = (d5 - 2) & 0xFFFF
            emit('SUBQ_D5', sr=('sub', d5_before, 2, 2))
            emit('CMP_D5END', sr=('cmp', d5, AIM_RAY_SENTINEL_STOP & 0xFFFF, 2))
            cont = _signed_word(d5) >= AIM_RAY_SENTINEL_STOP
            emit('BGE_LOOP', cont)
            if not cont:
                d5 = AIM_RAY_SENTINEL & 0xFFFF
                d5_upper_reset = True
                emit('RESET_D5B', sr=('logic', d5, 2))
                emit('BRA_LOOPB', True)
            block = 'HEAD'
            continue

        if block == 'TAIL':
            solid_100 = read((a2 + AIM_RAY_TAIL_OFFSET) & 0xFFFFFF, 1) & 0xFF
            emit('CMP_TAIL100', sr=('cmp', solid_100, 1, 1))
            setup = solid_100 == 1
            emit('BEQ_TAIL100', setup)
            if not setup:
                low = _signed_word(d2) < 8
                emit('CMP_D2_8', sr=('cmp', d2, 8, 2))
                emit('BLT_TABLE2', low)
                if low:
                    block = 'TABLE'
                    continue
                solid_101 = read((a2 + AIM_RAY_TAIL_OFFSET + 1) & 0xFFFFFF, 1) & 0xFF
                emit('CMP_TAIL101', sr=('cmp', solid_101, 1, 1))
                setup = solid_101 == 1
                emit('BNE_TABLE2', not setup)
                if not setup:
                    block = 'TABLE'
                    continue
            d1 = d1 & 0xFFF0
            emit('ANDI_D1', sr=('logic', d1, 2))
            skip_align = d2 == 0
            emit('TST_D2B', sr=('logic', d2, 2))
            emit('BEQ_SKIP_ALIGN', skip_align)
            if not skip_align:
                d0 = d0 & 0xFFE0
                emit('ANDI_D0', sr=('logic', d0, 2))
                if forward:
                    d0_before = d0
                    d0 = (d0 + 0x20) & 0xFFFF
                    emit('ADDI_D0', sr=('add', d0_before, 0x20, 2))
                    a2 = (a2 + 1) & 0xFFFFFFFF
                    emit('ADDQ_A2B')
            emit('BSR_PROBE2', True)
            result = aim_probe_mark(read, d0, d1, d4, a3, a4)
            probes.append(('PROBE2', d0, d1, d2, d3, d4, result))
            emit('_PROBE_SR', sr=('probe', len(probes) - 1))
            if 'a0' in result:
                a0 = result['a0'] & 0xFFFFFFFF
            read = _overlay(read, _aim_probe_overlay_stores(result))
            block = 'ROWLOOP'
            continue

        if block == 'ROWLOOP':
            solid = read((a2 + AIM_RAY_TAIL_OFFSET) & 0xFFFFFF, 1) & 0xFF
            emit('CMP_ROWEXIT', sr=('cmp', solid, 1, 1))
            done = solid == 1
            emit('BEQ_ROWEXIT', done)
            if done:
                emit('MOVE_F2D4', sr=('logic', d4, 2))
                emit('RTS')
                break
            emit('LEA_ROW')
            a2 = (a2 + AIM_RAY_ROW_STRIDE) & 0xFFFFFFFF
            d1_before = d1
            d1 = (d1 + 0x10) & 0xFFFF
            emit('ADDI_D1', sr=('add', d1_before, 0x10, 2))
            d4_before = d4
            d4 = (d4 + 8) & 0xFFFF
            emit('ADDQ_D4_ROW', sr=('add', d4_before, 8, 2))
            emit('BRA_ROWLOOP', True)
            continue

        raise RuntimeError(f'aim ray march: unknown block {block!r}')

    return {'d0': d0, 'd1': d1, 'd2': d2, 'd3': d3, 'd4': d4, 'd5': d5, 'a0': a0, 'a2': a2,
            'd5_upper_reset': d5_upper_reset, 'events': events, 'probes': probes}


def _aim_probe_overlay_stores(result):
    """The RAM an earlier aim_probe_mark call inside the SAME ray march wrote (AIM_SEARCH_BEST_FLAG/
    INDEX on 'found'), in ``_overlay``'s own {address: (value, size)} form, so a SECOND probe call in
    the same activation sees it -- real hardware, not this module's own bookkeeping."""
    if result['arm'] != 'found':
        return {}
    return {AIM_SEARCH_BEST_FLAG & 0xFFFFFF: (result['flag'] & 0xFFFF, 2),
            AIM_SEARCH_BEST_INDEX & 0xFFFFFF: (result['d7'] & 0xFFFF, 2)}


def aim_ray_march_forward(read, d0, d1, d5, a2, a3, a4):
    """00B354: see the module note above _aim_ray_march."""
    return _aim_ray_march(read, d0, d1, d5, a2, a3, a4, forward=True)


def aim_ray_march_backward(read, d0, d1, d5, a2, a3, a4):
    """00B440: 00B354's own mirror -- NOT byte-identical: phase A's own cell-boundary wrap is computed
    the same way (word SUBQ's own sign, not an AND mask) but the near-check reads the column already
    behind the ray (A2 - 1 / A2 - 1 + 0x80, not + 1), and the second probe's own setup skips the extra
    32-pixel alignment nudge and grid-pointer advance 00B354's own forward setup makes (real ROM: two
    fewer instructions, not a guess)."""
    return _aim_ray_march(read, d0, d1, d5, a2, a3, a4, forward=False)


# --- 00B724: the aim target scan (docs/gods/blockers/2026-09-18-00A578.md's own "Decision on
# 00AF52", 19 Sep -- the first of the three further callees, 00B002's own reconnaissance found bounded
# over {00AF3C, 00B32E} on every one of 1,772 witnessed occurrences across four recordings).  A
# horizontal raycast, rightward one grid column at a time from ``(x0, y0)``'s own cell (Y never
# changes), gated at each column on a two-rows-down footing -- the SAME FOOTPRINT_GRID layer
# 0063FA/00FDB8 read (a cell holds 1 while a solid stands there; ``GRID_ROW_BYTES`` separates rows) --
# and not itself, nor the row beneath it, blocked by a solid.  Each visited column is marked with a
# running step index in the SAME work-RAM cell ``aim_cue_update``'s own window-mark arm (``00B2EC``)
# writes 0xFF into (``AIM_CUE_WINDOW_STRIDE_1`` past ``aim_window_address``'s own base) -- so an
# EARLIER scan's own 0xFF mark short-circuits a later one as 'found', and an earlier scan's own
# (smaller-or-equal) step index at a column prunes a later, worse pass through it.  Each visited
# column's own position is also appended to a second, per-call work-RAM table
# (``AIM_SEARCH_POOL_LOW``, restarting from slot 0 on every single call -- NOT an occupancy pool like
# AIM_POOL, whose own 256 bytes sit immediately below it).
AIM_SEARCH_STEP_LIMIT_OFFSET = 0xD      # type_ptr byte: the walk's own max step count
AIM_SEARCH_START_INDEX = 0xFFFFF2CA     # word: the walk's own starting step index (a byte-wise prune
                                         # gate at the very first column, then the first stored index)
AIM_SEARCH_FLAG_SOURCE = 0xFFFFF2CC     # word: the search's own flag value, substituted by 1 for every
                                         # store when AIM_SEARCH_START_INDEX's own value is 0
AIM_SEARCH_COUNT = 0xFFFFF2B0           # word: this call's own store counter -- READ, not reset, at
                                         # entry (carries over calls that do not end in 'found'); the
                                         # 'found' arm alone clears it back to 0
AIM_SEARCH_SNAPSHOT = 0xFFFFF2B2        # three words (D0, D1, D7): the 'exhausted' arm's own snapshot
AIM_SEARCH_SNAPSHOT_FLAG = 0xFFFFF2B8   # word: AIM_SEARCH_FLAG_SOURCE's own value, forced to 1 when
                                         # AIM_SEARCH_START_INDEX is 0 -- 'exhausted' only
AIM_SEARCH_BEST_FLAG = 0xFFFFF2CE       # word: the running best flag -- 'found' only, and then only
AIM_SEARCH_BEST_INDEX = 0xFFFFF2D0      #   when the step index is (unsigned) less than this word's
                                         #   own current value; a 'found' where it is not is real ROM,
                                         #   never witnessed by any recording (declined)
AIM_SEARCH_STEP = 0x20                  # pixels per walk step (world X; the grid column stride)
AIM_SEARCH_X_LIMIT = 0x160              # camera-relative X must stay below this (signed)
AIM_SEARCH_POOL_LOW = 0xFFFF41B2        # 32 slots, 8 bytes each: D0, D1, D7, D5 per visited column
AIM_SEARCH_POOL_STRIDE = 8
AIM_SEARCH_MARK_OFFSET = AIM_CUE_WINDOW_STRIDE_1   # a0 = aim_window_address(...) + this


def aim_target_scan(read, type_ptr, x0, y0):
    """00B724: see the module note above.  'blocked-start' (the starting cell's own two-rows-down
    footing is not 1) is real ROM, never witnessed: declined.  'pruned-start' (the starting
    window-mark cell already holds a step index greater than the walk's own starting index) IS
    witnessed (census-00B724-*, three recordings) and is admitted (boundary.aim_target_scan_plan).
    Past those two guards the routine ALWAYS stores at least once (unconditionally, before the first per-step
    continuation test), then at each subsequent column: 'step-limit' (the step index reaches
    AIM_SEARCH_STEP_LIMIT_OFFSET's own value), 'x-bound' (the camera-relative X leaves
    [0, AIM_SEARCH_X_LIMIT)), 'blocked' / 'blocked-below' (the next column's own layer 0 / layer 1 is
    occupied), 'found' (the next column's own window-mark cell already holds a negative signed byte,
    i.e. 0xFF -- an earlier pass fully marked it), 'pruned' (the next column's own window-mark cell
    already holds a step index at or past this one) or 'exhausted' (the next column's own two-rows-
    down footing is not 1) -- the walk continues instead when it is."""
    from .grid import grid_cell_at, GRID_ROW_BYTES, _signed_byte, _signed_word
    type_ptr &= 0xFFFFFF
    x0 &= 0xFFFF
    y0 &= 0xFFFF
    cell = grid_cell_at(x0, y0)
    a2 = cell['address'] & 0xFFFFFFFF
    a0 = (aim_window_address(read, x0, y0) + AIM_SEARCH_MARK_OFFSET) & 0xFFFFFFFF

    if (read((a2 + 2 * GRID_ROW_BYTES) & 0xFFFFFF, 1) & 0xFF) != 1:
        return {'arm': 'blocked-start', 'a2': a2, 'a0': a0}

    d7 = read(AIM_SEARCH_START_INDEX, 2) & 0xFFFF
    tile0 = read(a0, 1) & 0xFF
    if _signed_byte(d7 & 0xFF) > _signed_byte(tile0):
        return {'arm': 'pruned-start', 'a2': a2, 'a0': a0, 'd7_start': d7, 'tile0': tile0}

    d7_start_word = d7                # AIM_SEARCH_START_INDEX itself (F2CA) is never written by this
                                       # routine, so this stays its own (fresh) value for both the
                                       # 'found' and 'exhausted' tails' own re-reads of it, below
    start_index_zero = d7_start_word == 0
    flag_source = read(AIM_SEARCH_FLAG_SOURCE, 2) & 0xFFFF
    d5 = 1 if d7 == 0 else flag_source
    limit = read((type_ptr + AIM_SEARCH_STEP_LIMIT_OFFSET) & 0xFFFFFF, 1) & 0xFF
    count = read(AIM_SEARCH_COUNT, 2) & 0xFFFF

    d0 = x0
    d2 = (x0 - read(FOLLOW_X, 2)) & 0xFFFF
    stores = []
    checks = []          # one entry per store, above: the transition test that followed it
    index = 0
    while True:
        stores.append({'index': index,
                        'address': (AIM_SEARCH_POOL_LOW + AIM_SEARCH_POOL_STRIDE * index) & 0xFFFFFFFF,
                        'd0': d0 & 0xFFFF, 'd1': y0 & 0xFFFF, 'd7': d7 & 0xFFFF, 'd5': d5 & 0xFFFF,
                        'mark_address': a0, 'mark_value': d7 & 0xFF})
        d7_before_incr = d7
        d7 = (d7 + 1) & 0xFFFF
        if _signed_byte(d7 & 0xFF) >= _signed_byte(limit):
            checks.append({'arm': 'step-limit', 'd7_before': d7_before_incr})
            return {'arm': 'step-limit', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0,
                    'd7': d7, 'limit': limit, 'count_before': count}
        a0 = (a0 + 1) & 0xFFFFFFFF
        d0 = (d0 + AIM_SEARCH_STEP) & 0xFFFF
        d2_before = d2
        d2 = (d2 + AIM_SEARCH_STEP) & 0xFFFF
        if _signed_word(d2) >= AIM_SEARCH_X_LIMIT:
            checks.append({'arm': 'x-bound', 'd7_before': d7_before_incr, 'd2_before': d2_before})
            return {'arm': 'x-bound', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'count_before': count}
        a2 = (a2 + 1) & 0xFFFFFFFF
        layer0 = read(a2, 1) & 0xFF
        if layer0 == 1:
            checks.append({'arm': 'blocked', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0})
            return {'arm': 'blocked', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'count_before': count}
        layer1 = read((a2 + GRID_ROW_BYTES) & 0xFFFFFF, 1) & 0xFF
        if layer1 == 1:
            checks.append({'arm': 'blocked-below', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0, 'layer1': layer1})
            return {'arm': 'blocked-below', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0,
                    'd0': d0, 'd2': d2, 'd7': d7, 'count_before': count}
        tile = read(a0, 1) & 0xFF
        stile = _signed_byte(tile)
        if stile < 0:
            best_index_before = read(AIM_SEARCH_BEST_INDEX, 2) & 0xFFFF
            update_best = d7 < best_index_before
            best_flag = 1 if start_index_zero else flag_source
            checks.append({'arm': 'found', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0, 'layer1': layer1, 'tile': tile})
            return {'arm': 'found', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'tile': tile, 'count_before': count,
                    'best_index_before': best_index_before, 'update_best': update_best,
                    'best_flag': best_flag & 0xFFFF, 'flag_source': flag_source,
                    'd7_start_word': d7_start_word}
        pruned = stile > 0 and _signed_byte(d7 & 0xFF) >= _signed_byte(tile)
        if pruned:
            checks.append({'arm': 'pruned', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0, 'layer1': layer1, 'tile': tile})
            return {'arm': 'pruned', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'tile': tile, 'count_before': count}
        header = read((a2 + 2 * GRID_ROW_BYTES) & 0xFFFFFF, 1) & 0xFF
        if header != 1:
            checks.append({'arm': 'exhausted', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0, 'layer1': layer1, 'tile': tile, 'header': header})
            return {'arm': 'exhausted', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'count_before': count, 'flag_source': flag_source,
                    'force_flag': start_index_zero, 'd7_start_word': d7_start_word}
        checks.append({'arm': 'continue', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                        'layer0': layer0, 'layer1': layer1, 'tile': tile, 'header': header})
        index += 1


# --- 00B7DA: the aim target scan, backward (docs/gods/blockers/2026-09-18-00A578.md's own "Decision
# on 00AF52", 19 Sep -- the second of the three further callees 00B002's own reconnaissance found
# bounded over {00AF3C, 00B32E}).  The disassembly reads as 00B724's own mirror (the SAME two initial
# guards, the SAME per-column footing/blocking/marking tests, stepping left instead of right) but two
# real differences the tracer found, not assumed by symmetry: it never stores the starting column at
# all (00B724's own first store is unconditional; here the very first probe is a bare advance, and a
# column is only stored once a LATER probe's own header test re-validates it -- so a call can produce
# zero stores where 00B724 always produces at least one), and it has no step-count limit whatsoever
# (00B724's own `cmp.b $d(a4),d7` has no counterpart here: only the X bound ever stops the walk).  The
# 'found' tail is also a real superset of 00B724's own: AIM_SEARCH_BEST_FLAG's own word is read first
# and, only when it is already negative (never yet set), the new best is stored unconditionally --
# otherwise AIM_SEARCH_BEST_INDEX is compared SIGNED (00B724's own comparison is unsigned) and only
# the 'skip' sub-arm (this step is not an improvement) is witnessed.  A3 (the pool cursor) is NOT
# reloaded from a fixed address the way 00B724's own `lea.l $ffff41b2.l,a3` is -- it is the caller's
# own register, continuing wherever an earlier call (00B724's, on every witnessed occurrence) left it.
AIM_SEARCH_BACKWARD_SNAPSHOT = 0xFFFFF2BA      # three words (D0, D1, D7): the 'exhausted' arm's own
                                                # snapshot -- its own work-RAM span, not 00B724's
AIM_SEARCH_BACKWARD_SNAPSHOT_FLAG = 0xFFFFF2C0  # word: AIM_SEARCH_FLAG_SOURCE's own value, forced to
                                                 # 0 (not 00B724's own 1) when the start index is 0
AIM_SEARCH_BACKWARD_X_LIMIT = -0x40             # camera-relative X must stay above this (signed)


def aim_target_scan_backward(read, type_ptr, x0, y0, a3):
    """00B7DA: see the module note above.  'blocked-start' is real ROM, never witnessed, exactly as
    00B724's own.  'pruned-start' IS witnessed (census-00B7DA-*, three recordings) and is admitted
    (boundary.aim_target_scan_backward_plan).  Past those two guards the FIRST probe is a bare advance (no
    store): at each column, 'x-bound' (the camera-relative X leaves (AIM_SEARCH_BACKWARD_X_LIMIT, 0]),
    'blocked' / 'blocked-below' (layer 0 / layer 1 occupied), 'found' (the column's own window-mark
    cell already holds a negative signed byte), 'pruned' (it already holds a step index at or past this
    one) or 'exhausted' (its own two-rows-down footing is not 1) end the walk; otherwise the column is
    stored (at ``a3``, the caller's own cursor) and the walk continues from it."""
    from .grid import grid_cell_at, GRID_ROW_BYTES, _signed_byte, _signed_word
    type_ptr &= 0xFFFFFF
    x0 &= 0xFFFF
    y0 &= 0xFFFF
    a3 &= 0xFFFFFFFF
    cell = grid_cell_at(x0, y0)
    a2 = cell['address'] & 0xFFFFFFFF
    a0 = (aim_window_address(read, x0, y0) + AIM_SEARCH_MARK_OFFSET) & 0xFFFFFFFF

    if (read((a2 + 2 * GRID_ROW_BYTES) & 0xFFFFFF, 1) & 0xFF) != 1:
        return {'arm': 'blocked-start', 'a2': a2, 'a0': a0}

    d7_start_word = read(AIM_SEARCH_START_INDEX, 2) & 0xFFFF
    tile0 = read(a0, 1) & 0xFF
    if _signed_byte(d7_start_word & 0xFF) > _signed_byte(tile0):
        return {'arm': 'pruned-start', 'a2': a2, 'a0': a0, 'd7_start': d7_start_word, 'tile0': tile0}

    start_index_zero = d7_start_word == 0
    flag_source = read(AIM_SEARCH_FLAG_SOURCE, 2) & 0xFFFF
    d5 = 0 if start_index_zero else flag_source
    count = read(AIM_SEARCH_COUNT, 2) & 0xFFFF

    d7 = d7_start_word
    d0 = x0
    d2 = (x0 - read(FOLLOW_X, 2)) & 0xFFFF
    stores = []
    checks = []
    index = 0
    while True:
        d7_before_incr = d7
        d7 = (d7 + 1) & 0xFFFF
        a0 = (a0 - 1) & 0xFFFFFFFF
        d0 = (d0 - AIM_SEARCH_STEP) & 0xFFFF
        d2_before = d2
        d2 = (d2 - AIM_SEARCH_STEP) & 0xFFFF
        if _signed_word(d2) <= AIM_SEARCH_BACKWARD_X_LIMIT:
            checks.append({'arm': 'x-bound', 'd7_before': d7_before_incr, 'd2_before': d2_before})
            return {'arm': 'x-bound', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'count_before': count, 'a3': a3, 'd7_start_word': d7_start_word}
        a2 = (a2 - 1) & 0xFFFFFFFF
        layer0 = read(a2, 1) & 0xFF
        if layer0 == 1:
            checks.append({'arm': 'blocked', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0})
            return {'arm': 'blocked', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'count_before': count, 'a3': a3, 'd7_start_word': d7_start_word}
        layer1 = read((a2 + GRID_ROW_BYTES) & 0xFFFFFF, 1) & 0xFF
        if layer1 == 1:
            checks.append({'arm': 'blocked-below', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0, 'layer1': layer1})
            return {'arm': 'blocked-below', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0,
                    'd0': d0, 'd2': d2, 'd7': d7, 'count_before': count, 'a3': a3, 'd7_start_word': d7_start_word}
        tile = read(a0, 1) & 0xFF
        stile = _signed_byte(tile)
        if stile < 0:
            best_flag_before = read(AIM_SEARCH_BEST_FLAG, 2) & 0xFFFF
            no_prior_best = _signed_word(best_flag_before) < 0
            if no_prior_best:
                # 00B878's own bmi taken: no comparison at all, always a new best.
                update_best = True
                best_index_before = None
            else:
                # 00B87A-880: SIGNED cmp.w d1,d7 (d1 = AIM_SEARCH_BEST_INDEX); bge skips the store.
                # Only the skip (d7 >= best_index_before) sub-arm is witnessed by any recording.
                best_index_before = read(AIM_SEARCH_BEST_INDEX, 2) & 0xFFFF
                skip = _signed_word(d7) >= _signed_word(best_index_before)
                update_best = not skip
            best_flag = 0 if start_index_zero else flag_source
            checks.append({'arm': 'found', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0, 'layer1': layer1, 'tile': tile})
            return {'arm': 'found', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'tile': tile, 'count_before': count, 'a3': a3,
                    'best_flag_before': best_flag_before, 'no_prior_best': no_prior_best,
                    'best_index_before': best_index_before, 'update_best': update_best,
                    'best_flag': best_flag & 0xFFFF, 'flag_source': flag_source,
                    'd7_start_word': d7_start_word}
        pruned = stile > 0 and _signed_byte(d7 & 0xFF) >= _signed_byte(tile)
        if pruned:
            checks.append({'arm': 'pruned', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0, 'layer1': layer1, 'tile': tile})
            return {'arm': 'pruned', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0, 'd0': d0,
                    'd2': d2, 'd7': d7, 'tile': tile, 'count_before': count, 'a3': a3, 'd7_start_word': d7_start_word}
        header = read((a2 + 2 * GRID_ROW_BYTES) & 0xFFFFFF, 1) & 0xFF
        if header != 1:
            checks.append({'arm': 'exhausted', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                            'layer0': layer0, 'layer1': layer1, 'tile': tile, 'header': header})
            return {'arm': 'exhausted', 'stores': stores, 'checks': checks, 'a2': a2, 'a0': a0,
                    'd0': d0, 'd2': d2, 'd7': d7, 'count_before': count, 'flag_source': flag_source,
                    'force_flag': start_index_zero, 'd7_start_word': d7_start_word, 'a3': a3}
        stores.append({'index': index, 'address': (a3 + AIM_SEARCH_POOL_STRIDE * index) & 0xFFFFFFFF,
                        'd0': d0 & 0xFFFF, 'd1': y0 & 0xFFFF, 'd7': d7 & 0xFFFF, 'd5': d5 & 0xFFFF,
                        'mark_address': a0, 'mark_value': d7 & 0xFF})
        checks.append({'arm': 'continue', 'd7_before': d7_before_incr, 'd2_before': d2_before,
                        'layer0': layer0, 'layer1': layer1, 'tile': tile, 'header': header})
        index += 1


# --- 00B6AE: the aim target resolve (docs/gods/blockers/2026-09-18-00A578.md's own "Decision on
# 00AF52", 19 Sep -- the third of the three further callees 00B002's own reconnaissance found bounded
# over {00AF3C, 00B32E, 00B05A}).  Consumes the two 'exhausted' snapshots 00B724 and 00B7DA's own
# calls, earlier in the SAME activation, leave (AIM_SEARCH_SNAPSHOT/AIM_SEARCH_BACKWARD_SNAPSHOT): a
# two-slot outer loop, one slot per snapshot, each an independent VERTICAL scan downward (Y steps by
# 0x10, half 00B724/00B7DA's own horizontal 0x20 -- the row stride GRID_ROW_BYTES and the window
# table's own row-to-row stride AIM_CUE_WINDOW_STRIDE_1 advance the grid/mark pointers together) until
# a row's own two-rows-down footing IS 1 (the opposite polarity from 00B724/00B7DA's own per-step
# test: there, header==1 means keep going; here, header==1 means STOP scanning and evaluate this row).
# An empty snapshot (both its own position words zero) skips the slot outright.  Evaluating a found
# row reuses the shape 00B724/00B7DA's own do: 'found' (the window-mark cell already negative -- update
# the shared best registry AIM_SEARCH_BEST_FLAG/AIM_SEARCH_BEST_INDEX, this time compared UNSIGNED
# STRICT, a third convention distinct from both 00B724's own unsigned>= and 00B7DA's own signed>=),
# 'pruned' (a step index already at or past this one) or a STORE (the window-mark cell zero, or
# positive but this step is an improvement) that reuses the already-recovered aim_pool_add (00B05A)
# verbatim over the ORIGINAL AIM_POOL, not AIM_SEARCH_POOL -- the snapshot's own flag word (its own
# +6 offset: AIM_SEARCH_SNAPSHOT_FLAG / AIM_SEARCH_BACKWARD_SNAPSHOT_FLAG) is threaded through as the
# pool entry's own fourth word.  'step-limit' (the SAME type_ptr+0xD field 00B724 reads) and 'y-bound'
# (the scan's own vertical extent, AIM_TARGET_RESOLVE_Y_LIMIT) end a slot without a header==1 row ever
# found.
AIM_TARGET_RESOLVE_SLOTS = ((AIM_SEARCH_SNAPSHOT, AIM_SEARCH_SNAPSHOT_FLAG),
                            (AIM_SEARCH_BACKWARD_SNAPSHOT, AIM_SEARCH_BACKWARD_SNAPSHOT_FLAG))
AIM_TARGET_RESOLVE_Y_STEP = 0x10
AIM_TARGET_RESOLVE_Y_LIMIT = 0xC0               # signed: the scan's own vertical extent
AIM_TARGET_RESOLVE_ROW_STRIDE = 0x80            # == grid.GRID_ROW_BYTES
AIM_TARGET_RESOLVE_MARK_STRIDE = AIM_CUE_WINDOW_STRIDE_1


def _resolve_slot(read, type_ptr, limit, snapshot_addr, flag_addr):
    from .grid import grid_cell_at, _signed_byte, _signed_word
    d0 = read(snapshot_addr & 0xFFFFFF, 2) & 0xFFFF
    d1 = read((snapshot_addr + 2) & 0xFFFFFF, 2) & 0xFFFF
    d7 = read((snapshot_addr + 4) & 0xFFFFFF, 2) & 0xFFFF
    cell = grid_cell_at(d0, d1)
    a2 = cell['address'] & 0xFFFFFFFF
    a0 = (aim_window_address(read, d0, d1) + AIM_SEARCH_MARK_OFFSET) & 0xFFFFFFFF
    d3 = (d1 - read(FOLLOW_Y, 2)) & 0xFFFF
    steps = []
    while True:
        d3_before = d3
        d3 = (d3 + AIM_TARGET_RESOLVE_Y_STEP) & 0xFFFF
        if _signed_word(d3) >= AIM_TARGET_RESOLVE_Y_LIMIT:
            return {'arm': 'y-bound', 'steps': steps, 'd0': d0, 'd1': d1, 'd7': d7, 'a2': a2, 'a0': a0,
                    'd3': d3, 'd3_before': d3_before}
        d1_before = d1
        d1 = (d1 + AIM_TARGET_RESOLVE_Y_STEP) & 0xFFFF
        d7 = (d7 + 1) & 0xFFFF
        a2 = (a2 + AIM_TARGET_RESOLVE_ROW_STRIDE) & 0xFFFFFFFF
        a0 = (a0 + AIM_TARGET_RESOLVE_MARK_STRIDE) & 0xFFFFFFFF
        header = read((a2 + 0x100) & 0xFFFFFF, 1) & 0xFF
        if header != 1:
            steps.append({'header': header, 'continue': True, 'd1_before': d1_before})
            continue
        steps.append({'header': header, 'continue': False, 'd1_before': d1_before})
        if _signed_byte(d7 & 0xFF) > _signed_byte(limit):
            return {'arm': 'step-limit', 'steps': steps, 'd0': d0, 'd1': d1, 'd7': d7, 'a2': a2, 'a0': a0, 'd3': d3}
        tile = read(a0 & 0xFFFFFF, 1) & 0xFF
        stile = _signed_byte(tile)
        if stile < 0:
            best_index_before = read(AIM_SEARCH_BEST_INDEX, 2) & 0xFFFF
            skip = d7 > best_index_before          # cmp.w f2d0,d7; bhi -- unsigned, STRICT
            flag = read(flag_addr & 0xFFFFFF, 2) & 0xFFFF
            return {'arm': 'found', 'steps': steps, 'd0': d0, 'd1': d1, 'd7': d7, 'a2': a2, 'a0': a0,
                    'd3': d3, 'tile': tile, 'best_index_before': best_index_before, 'update_best': not skip,
                    'flag': flag}
        if stile > 0 and _signed_byte(d7 & 0xFF) >= _signed_byte(tile):
            return {'arm': 'pruned', 'steps': steps, 'd0': d0, 'd1': d1, 'd7': d7, 'a2': a2, 'a0': a0, 'd3': d3,
                    'tile': tile}
        # tile == 0, or (tile > 0 and d7 < tile): store.
        flag = read(flag_addr & 0xFFFFFF, 2) & 0xFFFF
        add_result = aim_pool_add(read, d0, d1, d7, flag)
        return {'arm': 'store', 'steps': steps, 'd0': d0, 'd1': d1, 'd7': d7, 'a2': a2, 'a0': a0, 'd3': d3,
                'tile': tile, 'flag': flag, 'add_result': add_result}


def aim_target_resolve(read, type_ptr):
    """00B6AE: see the module note above.  Returns ``{'slots': [slot0, slot1]}``, one dict per outer
    slot (in AIM_TARGET_RESOLVE_SLOTS order): ``{'arm': 'empty'}`` (the snapshot's own leading long is
    zero) or the result of ``_resolve_slot`` -- ``'y-bound'`` / ``'step-limit'`` / ``'pruned'`` (no
    match; a real recording witnesses each), ``'found'`` (with ``'update_best'``: only the True case --
    every witnessed occurrence -- is admitted, the False case is real ROM never witnessed) or
    ``'store'`` (with the already-recovered ``aim_pool_add``'s own result nested in -- only its own
    ``'found'`` arm is witnessed here, matching aim_pool_add's own recovery)."""
    type_ptr &= 0xFFFFFF
    limit = read((type_ptr + AIM_SEARCH_STEP_LIMIT_OFFSET) & 0xFFFFFF, 1) & 0xFF
    slots = []
    for snapshot_addr, flag_addr in AIM_TARGET_RESOLVE_SLOTS:
        if read(snapshot_addr & 0xFFFFFF, 4) == 0:
            slots.append({'arm': 'empty'})
            continue
        slots.append(_resolve_slot(read, type_ptr, limit, snapshot_addr, flag_addr))
    return {'slots': slots}


# --- 00B8C2 / 00B920: the creature spawn-init's own icon-cue add (docs/gods/blockers/2026-09-18-
# 00A578.md's own original scope -- 00A578's own spawn-init body's own unconditional `bsr $b920`,
# independent of the whole 00AF52/00B588 chain escalated the same session).  A 10-slot, 6-byte table
# (`FFFF0EF0`; reset by 00B88C, not itself needed here -- every witnessed occurrence finds a free slot
# without ever seeing the table freshly reset) -- each slot a position long (offset 0) and a state word
# (offset 4, negative meaning free, matching the table's own reset value 0xFFFF). 00B8C2 is the scan
# (RTR is how the ROM returns its own CCR-only 'found'/'not found' result -- a plain register/CCR
# contract from this recovery's own side, not a new mechanism); 00B920 is the ADD, storing the
# creature's own tracked position (POSITION_X:POSITION_Y as one long) and two more fields on the
# creature record itself (`$6(a5)`, `$8(a5)`) whose own downstream consumer this session did not
# trace -- named minimally, the way `aim_cue_update`'s own 400-byte table was.
SPAWN_TABLE_LOW = 0xFFFF0EF0
SPAWN_TABLE_SLOTS = 10
SPAWN_TABLE_STRIDE = 6
SPAWN_TABLE_STATE_OFFSET = 4          # word: negative (the table's own reset value) means free
SPAWN_TRIGGER_MARKER = 0xFFFFFDF4     # word: unconditional 0x36 on every 00B920 call, real purpose
                                       # not traced this session (kept a fact, not a guess)
SPAWN_TRIGGER_STATE_WORD = 7          # the state word 00B920 itself writes on a successful add
SPAWN_ICON_STATE_OFFSET = 0x6         # instance_ptr word: written 5 -- the SAME offset LIFECYCLE_RESET
                                       # and GROUND_HOLD_TIMER already name for other kind-contexts
SPAWN_ICON_TIMER_OFFSET = 0x8         # instance_ptr word: written -3 -- the SAME offset LIFECYCLE
                                       # already names for the pickup-check kind-context
SPAWN_ICON_STATE_VALUE = 5
SPAWN_ICON_TIMER_VALUE = 0xFFFFFFFD & 0xFFFF
SPAWN_TABLE_BUSY_FLAG = 0xFFFFF292    # word: cleared alongside the table itself (00B88C's own reset),
                                       # set to 1 by every witnessed 00B920 add


def spawn_table_find_free(read):
    """00B8C2: the first of SPAWN_TABLE_SLOTS whose own state word (offset SPAWN_TABLE_STATE_OFFSET)
    is negative.  Returns ``'found'`` (every witnessed occurrence, all five recordings) or ``'full'``
    (every slot occupied -- real ROM, never witnessed: declined)."""
    from .grid import _signed_word
    address = SPAWN_TABLE_LOW
    skipped = 0
    for index in range(SPAWN_TABLE_SLOTS):
        state = read((address + SPAWN_TABLE_STATE_OFFSET) & 0xFFFFFF, 2) & 0xFFFF
        if _signed_word(state) < 0:
            return {'arm': 'found', 'index': index, 'address': address, 'skipped': skipped}
        skipped += 1
        address = (address + SPAWN_TABLE_STRIDE) & 0xFFFFFFFF
    return {'arm': 'full', 'skipped': skipped}


def spawn_table_add(read, instance_ptr):
    """00B920: SPAWN_TRIGGER_MARKER is set unconditionally, then spawn_table_find_free's own 'found'
    arm (the only one witnessed) stores the creature's own tracked position and SPAWN_TRIGGER_STATE_WORD
    into the free slot, and two more fields onto the creature record itself.  'full' (spawn_table_find_
    free's own decline) is real ROM, never witnessed: declined."""
    instance_ptr &= 0xFFFFFF
    scan = spawn_table_find_free(read)
    if scan['arm'] != 'found':
        return {'arm': scan['arm'], 'scan': scan}
    position = read(instance_ptr, 4)
    slot_addr = scan['address'] & 0xFFFFFF
    stores = {SPAWN_TRIGGER_MARKER & 0xFFFFFF: (0x36, 2), slot_addr: (position, 4),
             (slot_addr + 4) & 0xFFFFFF: (SPAWN_TRIGGER_STATE_WORD, 2),
             (instance_ptr + SPAWN_ICON_STATE_OFFSET) & 0xFFFFFF: (SPAWN_ICON_STATE_VALUE, 2),
             SPAWN_TABLE_BUSY_FLAG & 0xFFFFFF: (1, 2),
             (instance_ptr + SPAWN_ICON_TIMER_OFFSET) & 0xFFFFFF: (SPAWN_ICON_TIMER_VALUE, 2)}
    return {'arm': 'found', 'scan': scan, 'position': position, 'stores': stores}


# --- 00AC36: the aim-search-flag kind dispatch (00AA76's own third call) --------------------------
#
# A small, bounded, callee-free dispatcher docs/gods/blockers/2026-09-18-00A578.md's own reconnaissance
# already named -- read fresh once 00AF52's own AIM_SEARCH_BEST_FLAG contract was understood
# (census-0XAC36-*, four recordings, 3 real path classes, all callee-free).  `f2ce.w`
# (AIM_SEARCH_BEST_FLAG) is read into a local value once, never re-read:
#   f2ce <= 1 (signed): KIND (DIRECTION_INDEX, $a) := f2ce itself, unconditional; FALL_PHASE and
#     FRAME_STEP untouched (real: 00AF52's own head sets f2ce to -1 whenever the whole aim-search
#     dispatch found nothing, and this is the SAME arm that reaches here with f2ce still 0 or 1 too).
#   f2ce > 1: x = f2ce - 2; KIND := (x & 1) + 4 (an even/odd split over four/five); then, over x with
#     its own low bit cleared: x == 0 -> FALL_PHASE := 7; x == 2 (after one more -2) -> FALL_PHASE := 9
#     (real ROM, never witnessed -- declined); anything past that (x >= 4, i.e. f2ce >= 6) ->
#     FALL_PHASE := 13.  FRAME_STEP is cleared whenever f2ce > 1, regardless of which FALL_PHASE arm.

def aim_search_flag_dispatch(f2ce):
    """00AC36: see the module note above.  Returns {'arm', 'kind', 'fall_phase' (only for 'extended')} --
    'fall-phase-9' is real ROM, never witnessed by a recording; the caller declines it by name."""
    f2ce = _signed_word(f2ce & 0xFFFF)
    if f2ce <= 1:
        return {'arm': 'direct', 'kind': f2ce & 0xFFFF}
    x = (f2ce - 2) & 0xFFFF
    kind = (x & 1) + 4
    x &= 0xFFFE
    if x == 0:
        return {'arm': 'extended', 'kind': kind, 'fall_phase': 7}
    x = (x - 2) & 0xFFFF
    if x == 0:
        return {'arm': 'fall-phase-9', 'kind': kind}
    return {'arm': 'extended', 'kind': kind, 'fall_phase': 13}


# --- 00AA76 / 00AB50: the two most-witnessed kind handlers (docs/gods/blockers/2026-09-18-00A578.md's
# own 19 September Progress) -- each a real ~70-instruction body composing 00AF3C (twice), 00AF52 and
# 00AC36 before a hand-off to kind_frame_offset's own separately-armed gate (00AA50), the SAME "one
# gate hands off to a separately-armed gate" shape ground_contact_update's own trigger arms already
# use.  NOT a byte-identical pair (confirmed by direct disassembly, not assumed by mirror symmetry):
# 00AB50's own shared-exit test is `f2ce == 1`, not `f2ce == 0`; its own arm-2 sets KIND 3 (00AA76's
# own sets KIND 2); and its own two neighbor cascades run in the OPPOSITE order.  Both helpers below
# are shared, parameterised on what differs.

AIM_RETRY_COUNTER = 0x6            # instance_ptr word: the SAME offset LIFECYCLE_RESET/GROUND_HOLD_TIMER
                                    # name for other callers -- here a per-instance search-retry
                                    # countdown, decremented once per activation and reseeded (below)
                                    # when it goes negative.
TYPE_RETRY_SEED_BYTE = 0xB         # type_ptr byte: the retry counter's own reseed source -- the SAME
                                    # offset TYPE_GROUND_RELOAD_BYTE names for a different caller.


def aim_retry_counter_step(read, type_ptr, counter_before):
    """`$AB1A`/`$AB06` (00AA76) and their own mirror in 00AB50: `subq.w #1,$6(a5); bpl.w $aa50` -- the
    non-negative arm hands off with no further effect.  The negative arm (`$AB2A`) reseeds the counter
    from a per-type byte and the shared random-table multiplier (`timers.FREQUENCY_SCALE`, the SAME RAM
    word `mulu.w $eebe.w` always resolves to): `moveq #$a,d0; sub.b $b(a4),d0; ext.w d0; mulu.w
    $eebe.w,d0; add.l d0,d0; swap d0; addq.w #1,d0` -- MULU treats the sign-extended word as UNSIGNED (a
    byte subtraction that goes negative becomes a LARGE multiplier, not a small negative one), and the
    doubling before the SWAP can carry past 32 bits (dropped, real 68000 wraparound)."""
    counter_after = (counter_before - 1) & 0xFFFF
    if not (counter_after & 0x8000):
        return {'arm': 'positive', 'counter': counter_after}
    from .grid import _signed_byte
    byte = read((type_ptr + TYPE_RETRY_SEED_BYTE) & 0xFFFFFF, 1) & 0xFF
    diff = (0xA - byte) & 0xFF                       # sub.b: byte subtraction, upper bits stay 0 (moveq)
    word = _signed_byte(diff) & 0xFFFF               # ext.w: sign-extend the byte into the word
    freq = read(timers.FREQUENCY_SCALE, 2) & 0xFFFF
    product = (word * freq) & 0xFFFFFFFF             # mulu.w: both operands unsigned
    doubled = (product * 2) & 0xFFFFFFFF             # add.l d0,d0
    swapped_low = (doubled >> 16) & 0xFFFF           # swap d0 -- becomes D0's new low word
    swapped_high = doubled & 0xFFFF                  # swap d0 -- becomes D0's new UPPER word, and
                                                      # survives the following addq.w (a word op, the
                                                      # LAST write to D0 in this routine): D0's exit
                                                      # value is this residue, not the caller's own
                                                      # entry upper half.
    reseeded = (swapped_low + 1) & 0xFFFF            # addq.w #1,d0
    d0_exit = (swapped_high << 16) | reseeded
    return {'arm': 'reseed', 'counter': reseeded, 'd0': d0_exit, 'byte': byte, 'diff': diff,
            'product': product}


def aim_kind_handler_search(read, cell_addr, *, offsets):
    """The neighbor cascade 00AA76 (`$AAC2`-`$AAFC`, `offsets=(-1, 0x7F, 0xFF, 0x1, 0x81, 0x101)`) and
    00AB50 (`$ABA6`-`$ABE8`, `offsets=(0x1, 0x81, 0x101, -1, 0x7F, 0xFF)` -- the opposite cascade order)
    both run on 00AF52's own 'nothing found' result (`f2ce < 0`): up to six byte compares against
    `cell_addr`'s neighbors in ROM order with real short-circuiting.  `probe_c` alone (the THIRD test
    of the first group) exits straight to the shared retry-counter reset; the first two probes of that
    group instead jump into the second group on a match (`route`), which the routine also falls into
    when none of the first three match.  Returns every probe outcome (for the boundary's own
    per-instruction cost) plus `route` ('a' -- probe_a matched; 'fallthrough' -- none of the first
    three did; 'b' -- probe_b alone, real ROM, never witnessed by any recording) and, from the second
    group, `outcome` ('kind' -- the third probe of the second group matches, the real KIND store;
    'reset-d'/'reset-e' -- the first two probes of the second group, real ROM never witnessed;
    'reset-no-f' -- neither the first two nor the third probe of the second group matches)."""
    off_a, off_b, off_c, off_d, off_e, off_f = offsets
    # Real short-circuiting: probe_b is read only when probe_a misses, probe_c only when both miss --
    # the ROM never re-reads a neighbor byte it already branched away on.
    probe_a = (read((cell_addr + off_a) & 0xFFFFFF, 1) & 0xFF) == 1
    probe_b = False if probe_a else (read((cell_addr + off_b) & 0xFFFFFF, 1) & 0xFF) == 1
    probe_c = False if (probe_a or probe_b) else (read((cell_addr + off_c) & 0xFFFFFF, 1) & 0xFF) == 1
    if probe_c:
        return {'route': 'c', 'probe_a': probe_a, 'probe_b': probe_b, 'probe_c': probe_c}
    route = 'a' if probe_a else ('b' if probe_b else 'fallthrough')
    probe_d = (read((cell_addr + off_d) & 0xFFFFFF, 1) & 0xFF) == 1
    probe_e = (read((cell_addr + off_e) & 0xFFFFFF, 1) & 0xFF) == 1
    probe_f = (read((cell_addr + off_f) & 0xFFFFFF, 1) & 0xFF) == 1
    if probe_d:
        outcome = 'reset-d'
    elif probe_e:
        outcome = 'reset-e'
    elif not probe_f:
        outcome = 'reset-no-f'
    else:
        outcome = 'kind'
    return {'route': route, 'probe_a': probe_a, 'probe_b': probe_b, 'probe_c': probe_c,
            'probe_d': probe_d, 'probe_e': probe_e, 'probe_f': probe_f, 'outcome': outcome}


AIM_KIND_HANDLER_76_SEARCH_OFFSETS = (-1, 0x7F, 0xFF, 0x1, 0x81, 0x101)


# --- 00004AAA: the creature effect-slot pool scan (00A772's own further tail, called from 00010E28)
# -- a 200-slot, 8-byte pool distinct from every spawn/hazard/aim pool already named (game/timers.py,
# game/hazard.py, game/creatures.py's own AIM_POOL).  A free slot's own word at +4 holds a negative
# value; the 74 retained fixtures over all five recordings all find one within the first 176 of 200
# slots -- full exhaustion is real ROM, never witnessed, declined.
EFFECT_SLOT_POOL = 0xFFFF4342
EFFECT_SLOT_STRIDE = 8
EFFECT_SLOT_COUNT = 0xC8            # 200
EFFECT_SLOT_ACTIVE_OFFSET = 4       # word: negative selects this slot as free


def effect_slot_find_free(read):
    """00004AAA: `lea.l EFFECT_SLOT_POOL,a5; move.w #$c7,d6` then, for each of 200 slots in order,
    `tst.w $4(a5)` (free iff negative) -- on a match, D5 becomes the slot's own 0-based index (`$c7 -
    d6`), D6 the remaining count from there, A5 the slot's own address; the CCR is `tst.w d6`'s own
    (Z only when the match falls on the very last slot).  Exhausting all 200 slots without a match is
    real ROM, never witnessed: declined."""
    for index in range(EFFECT_SLOT_COUNT):
        address = (EFFECT_SLOT_POOL + index * EFFECT_SLOT_STRIDE) & 0xFFFFFFFF
        active = read(address + EFFECT_SLOT_ACTIVE_OFFSET, 2) & 0xFFFF
        if _signed_word(active) < 0:
            remaining = (EFFECT_SLOT_COUNT - 1 - index) & 0xFFFF
            return {'arm': 'found', 'address': address, 'index': index, 'remaining': remaining}
    return {'arm': 'exhausted'}


# --- 00010E28: the creature effect-slot add (game/creatures.py: effect_slot_add) -- composes
# effect_slot_find_free (00004AAA) over a full movem.l register frame: on 'found', stores the caller's
# own D0/D1 (a world position), an adjusted D2 (a frame/type index wrapped modulo
# EFFECT_SLOT_INDEX_MOD, both directions real and witnessed) and the literal 1 into the slot, advances
# the slot cursor (EFFECT_SLOT_CURSOR) past it, and marks the SAME slot's own index in a parallel
# 200-byte flag table (EFFECT_SLOT_FLAG_TABLE).  'exhausted' (real ROM, never witnessed) skips the
# slot entirely.  Called from more than one place (00A772's own tail is only one caller); every
# register this routine touches besides A7 is saved on entry and restored before its own rts, so
# nothing but the writes and A7/PC/SR survive into its caller.
EFFECT_SLOT_INDEX_MOD = 0xB          # d2 wrap threshold
EFFECT_SLOT_INDEX_WRAP = 0xC0        # added when d2 is below the threshold
EFFECT_SLOT_CURSOR = 0xFFFFF2A6      # long: the slot's own address, advanced past the stored fields
EFFECT_SLOT_FLAG_TABLE = 0xFFFF3FEA  # byte per slot (EFFECT_SLOT_STRIDE-independent index), set to $FF


def effect_slot_add(read, d0, d1, d2):
    """00010E28: see the module note above."""
    scan = effect_slot_find_free(read)
    if scan['arm'] != 'found':
        return {'arm': 'exhausted'}
    wrap = d2 >= EFFECT_SLOT_INDEX_MOD
    d2_adjusted = ((d2 - EFFECT_SLOT_INDEX_MOD) if wrap else (d2 + EFFECT_SLOT_INDEX_WRAP)) & 0xFFFF
    return {'arm': 'found', 'address': scan['address'], 'index': scan['index'], 'wrap': wrap,
            'd0': d0 & 0xFFFF, 'd1': d1 & 0xFFFF, 'd2': d2_adjusted}


# --- 00003F0C: a shared packed-BCD counter increment (called from 00009A9F2 -- 00A772's own
# LIFECYCLE-negative arm -- and, far more often, from places this session did not trace) -- a
# six-digit packed-BCD counter at BCD_COUNTER_BASE, read/written as three words (d1/d2/d3, the low
# digit pair added the caller's own D7 amount, the other two propagating its own decimal carry only),
# unconditionally marking BCD_COUNTER_DIRTY for a separate, VBlank-driven display flush this session
# does not chase (it never touches a device itself).
BCD_COUNTER_BASE = 0xFFFFEF80        # four words read/written (d0-d3 via movem.w); d0 is untouched
                                      # scratch, d1/d2/d3 the counter's own three digit-pairs
BCD_COUNTER_DIRTY = 0xFFFFF1CE       # word: unconditionally set to 1


def _bcd_byte_add(a, b, carry_in):
    """68000 ABCD.b Dy,Dx: two packed-BCD bytes plus a carry-in, decimal digit by digit."""
    lo = (a & 0xF) + (b & 0xF) + carry_in
    carry = 0
    if lo > 9:
        lo -= 10
        carry = 1
    hi = (a >> 4 & 0xF) + (b >> 4 & 0xF) + carry
    carry_out = 0
    if hi > 9:
        hi -= 10
        carry_out = 1
    return ((hi & 0xF) << 4) | (lo & 0xF), carry_out


def bcd_counter_add(read, amount):
    """00003F0C: see the module note above.  Returns the three updated digit-pair bytes (the low byte
    of each of D1/D2/D3) and each ABCD's own carry-out (for the boundary's own CCR)."""
    # movem.w loads d1/d2/d3 from the words at +2/+4/+6; abcd.b only ever touches a register's own low
    # BYTE, which is the word's own SECOND (low) byte in memory -- +3/+5/+7, not +2/+4/+6.
    d1 = read((BCD_COUNTER_BASE + 3) & 0xFFFFFF, 1) & 0xFF
    d2 = read((BCD_COUNTER_BASE + 5) & 0xFFFFFF, 1) & 0xFF
    d3 = read((BCD_COUNTER_BASE + 7) & 0xFFFFFF, 1) & 0xFF
    d1_new, carry1 = _bcd_byte_add(d1, amount & 0xFF, 0)
    d2_new, carry2 = _bcd_byte_add(d2, 0, carry1)
    d3_new, carry3 = _bcd_byte_add(d3, 0, carry2)
    return {'d1': d1_new, 'd2': d2_new, 'd3': d3_new, 'carry1': carry1, 'carry2': carry2, 'carry3': carry3}


# --- 00009A9F2: the creature death BCD-amount split (00A772's own LIFECYCLE-negative arm, composing
# 00003F0C up to twice) -- derives up to two ABCD 'amount' bytes from the creature's own type-template
# byte (D5 on entry, `move.b $1(a4),d5` in 00A772's own caller): `((d5&0xff)>>1)+1`, divided by 10
# (unsigned): the quotient and remainder pack into the first amount as `(quotient<<4)|remainder`, fed
# to 00003F0C's own ABCD chain UNMODIFIED -- a quotient above 9 packs a genuinely non-BCD nibble
# there, which 00003F0C's own digit-carry arithmetic still resolves correctly, exactly as real ABCD
# hardware does on any byte.  When the quotient exceeds 9, a second amount, `(quotient-9)<<4`, corrects
# the overflow with its own second 00003F0C call.
def creature_death_bcd_amounts(d5_entry):
    """00009A9F2: see the module note above."""
    value = (((d5_entry & 0xFF) >> 1) + 1) & 0xFFFF
    quotient, remainder = divmod(value, 10)
    tens_overflow = max(0, quotient - 9)
    first = ((quotient & 0xFF) << 4 | (remainder & 0xFF)) & 0xFF
    second = ((tens_overflow & 0xFF) << 4) & 0xFF
    return {'quotient': quotient, 'remainder': remainder, 'first': first,
            'has_second': tens_overflow != 0, 'second': second}


# --- 00A578: the 9-slot creature list walk (docs/gods/blockers/2026-09-18-00A578.md's own "not just
# a walk") -- called once per tick, gated by WALK_GATE.  A fixed 9-slot list at CREATURE_LIST_BASE
# (CREATURE_LIST_STRIDE bytes each: a header word, a type-template pointer long, and, at +0x10, a
# byte this module calls WAVE_TRIGGERED) walks a shared instance array at CREATURE_INSTANCE_BASE
# (CREATURE_INSTANCE_STRIDE bytes per instance, CREATURE_SLOT_BLOCK reserved per slot so a slot's own
# instances never spill into the next slot's own reserved block).  A zero header skips the slot
# outright.  A header of exactly 1 selects the PER-FRAME UPDATE body: walk `(type_ptr)+1` live
# instances, and for each one whose own LIFECYCLE word is positive, call the family (00A772);
# LIFECYCLE == 0 is a plain skip, LIFECYCLE < 0 is the ICON-SPAWN sub-machine below.  Any OTHER
# nonzero header selects the SPAWN-INIT body: initialise `(type_ptr)+1` brand-new instances (position,
# LIFECYCLE = -2, a per-type attack countdown, DIRECTION_INDEX, a fresh DISPLAY_TIMER/AIM_WINDOW_STATE,
# and a staggered "spawn frequency" reload timer accumulated across the new instances) and decrement
# the slot's own header, so a header > 1 spreads its own new-instance batch over several ticks.
WALK_GATE = 0xFFFFEED1                 # byte: 0 skips the whole walk for this tick
CREATURE_LIST_BASE = 0xFFFF1496        # 9 real slots, CREATURE_LIST_STRIDE bytes each
CREATURE_LIST_STRIDE = 0x12
# The loop counter is pushed as 9 and tested AFTER each decrement (`subq.w #1,(a7); bpl.w`, not a
# DBRA), so the loop body actually runs TEN times (9, 8, ..., 0 are all still >= 0) -- confirmed
# directly against the tracer (`0xA596` visited exactly 10 times on every retained fixture) and
# against RAM: the tenth slot's own header (`CREATURE_LIST_BASE + 9*CREATURE_LIST_STRIDE`) is 0 on
# all 1,283 retained fixtures across all five recordings, so this real off-by-one always lands on a
# harmless 'skip' -- modelled here as a real 10th iteration, not assumed away.
CREATURE_LIST_COUNT = 10
CREATURE_LIST_TYPE_PTR = 0x2           # slot word+2: the type template pointer (a4)
CREATURE_LIST_WAVE_TRIGGERED = 0x10    # slot byte: this slot's own "icon wave already cued" latch
CREATURE_INSTANCE_BASE = 0xFFFF2602    # the shared instance array a slot's own instances walk
CREATURE_INSTANCE_STRIDE = 0x18        # 24 bytes per instance (creatures.py's own established stride)
CREATURE_SLOT_BLOCK = 0xF0             # 240 bytes = 10 instances reserved per slot, used or not
AIM_WINDOW_STATE = 0xC                 # instance_ptr word: reset to -1 by spawn-init; its own aim-
                                        # subsystem consumer is outside this session's scope
DISPLAY_TIMER = 0x10                   # instance_ptr word: 00A772's own DISPLAY_TIMER, reset to -1 here
TYPE_INSTANCE_COUNT = 0x0              # type_ptr byte: `(type_ptr)+1` instances this activation walks
TYPE_SPAWN_X, TYPE_SPAWN_Y = 0x12, 0x13    # type_ptr bytes: the spawn-init position, <<5/<<4
TYPE_ATTACK_KIND_BYTE = 0x6            # type_ptr byte: low nibble reloads COUNTDOWN, 0 skips it
TYPE_ZONE_BIT_BYTE = 0x4               # type_ptr byte: bit 1 folds into DIRECTION_INDEX
TYPE_FREQUENCY_BYTE = 0x14             # type_ptr byte: unsigned, the spawn-stagger frequency's own scale
TYPE_ICON_KIND_BYTE = 0x1              # type_ptr byte: the icon-spawn 'other negative' arm's new LIFECYCLE
TYPE_GROUND_RELOAD_BYTE = 0xB          # type_ptr byte: the SAME offset TYPE_RETRY_SEED_BYTE names for
                                        # 00AA76/00AB50's own retry reseed -- the icon-spawn -3 arm's
                                        # own reseed uses it identically (`10 - byte`)
ZONE_MODE_FLAG = 0x100                 # a1-relative byte (the caller's own live zone/tile-map pointer,
                                        # not traced further this session): ==1 selects zone bit 0,
                                        # anything else selects zone bit 2
WALK_A5_SAVE = 0xFFFFF2C2              # long: this slot's own starting instance base, saved/restored
                                        # around the per-frame-update body's own internal a5 advance
                                        # (purely a register-spill; nothing else reads it back)
WALK_SETTLED_COUNT = 0xFFFFF2C6        # word: per-slot tally of 'settled' (LIFECYCLE == 0) instances
WALK_DISPLAY_COUNT = 0xFFFFF2C8        # word: per-slot tally of icon-spawn 'display' instances
WALK_CACHED_POSITION = 0xFFFFF26C      # long (two words): the LAST icon-spawn 'display' instance's
                                        # own position this tick, read back by the wave-complete check


def creature_walk_gate(read):
    """WALK_GATE == 0 skips the ENTIRE 9-slot walk for this tick (`tst.b $eed1.w; beq.w $a662`)."""
    return (read(WALK_GATE, 1) & 0xFF) != 0


def creature_walk_slot_dispatch(read, slot_addr):
    """One slot's own header dispatch (`move.w (a3),d0; beq...; subq.w#1,d0; beq...`): 'skip' (header
    was 0), 'per-frame' (header was 1) or 'spawn-init' (header was anything else, decremented)."""
    header = read(slot_addr & 0xFFFFFF, 2) & 0xFFFF
    if header == 0:
        return {'arm': 'skip', 'header': header}
    type_ptr = read((slot_addr + CREATURE_LIST_TYPE_PTR) & 0xFFFFFF, 4) & 0xFFFFFFFF
    after = (header - 1) & 0xFFFF
    if after == 0:
        return {'arm': 'per-frame', 'header': header, 'type_ptr': type_ptr}
    return {'arm': 'spawn-init', 'header': header, 'header_after': after, 'type_ptr': type_ptr}


def creature_spawn_init_instance(read, type_ptr, a1, d6_before):
    """00A5AA-00A644: one new instance's own init, and the running spawn-stagger accumulator (`d6`)
    the WHOLE spawn-init body threads across every new instance in this activation.  `bsr $b920`
    (the icon-cue add) fires only for the very FIRST new instance (`d6` still 0 at that point)."""
    x_byte = read((type_ptr + TYPE_SPAWN_X) & 0xFFFFFF, 1) & 0xFF
    y_byte = read((type_ptr + TYPE_SPAWN_Y) & 0xFFFFFF, 1) & 0xFF
    position_x = (x_byte << 5) & 0xFFFF
    position_y = (y_byte << 4) & 0xFFFF
    add_icon_cue = d6_before == 0
    kind_field = (read((type_ptr + TYPE_ATTACK_KIND_BYTE) & 0xFFFFFF, 1)) & 0xF
    countdown = None if kind_field == 0 else (((0x10 - kind_field) & 0xFFFF) << 2) & 0xFFFF
    zone_byte = read((a1 + ZONE_MODE_FLAG) & 0xFFFFFF, 1) & 0xFF
    zone_bit = 0 if zone_byte == 1 else 2
    type_bit4 = read((type_ptr + TYPE_ZONE_BIT_BYTE) & 0xFFFFFF, 1) & 0xFF
    direction_index = (((type_bit4 >> 1) & 1) + zone_bit) & 0xFFFF
    freq_byte = read((type_ptr + TYPE_FREQUENCY_BYTE) & 0xFFFFFF, 1) & 0xFF
    freq_scale = read(timers.FREQUENCY_SCALE, 2) & 0xFFFF
    product = (freq_byte * freq_scale) & 0xFFFFFFFF
    doubled = (product * 2) & 0xFFFFFFFF
    reload_low = (doubled >> 16) & 0xFFFF          # swap d0's own new low word
    reload_high = doubled & 0xFFFF                 # swap d0's own new upper word (D0's exit residue)
    reload = (reload_low + 1) & 0xFFFF             # addq.w #1,d0
    d6_after = (d6_before + reload) & 0xFFFF
    return {'position_x': position_x, 'position_y': position_y, 'lifecycle_reset': d6_before,
            'add_icon_cue': add_icon_cue, 'countdown': countdown, 'direction_index': direction_index,
            'reload': reload, 'reload_d0_exit': (reload_high << 16) | reload, 'd6_after': d6_after}


def creature_per_frame_instance_dispatch(read, instance_ptr):
    """00A678-00A682: one live instance's own top-level dispatch inside the per-frame update body.
    LIFECYCLE < 0 is the icon-spawn sub-machine (below); == 0 a plain skip (bumps the "settled" tally
    the wave-complete check below reads); > 0 calls the family (00A772)."""
    lifecycle = read((instance_ptr + LIFECYCLE) & 0xFFFFFF, 2) & 0xFFFF
    signed = lifecycle - 0x10000 if lifecycle & 0x8000 else lifecycle
    if signed < 0:
        return {'arm': 'icon-spawn', 'lifecycle': lifecycle}
    if signed == 0:
        return {'arm': 'settled', 'lifecycle': lifecycle}
    return {'arm': 'family', 'lifecycle': lifecycle}


ICON_SPAWN_ARMED = 0xFFFE              # LIFECYCLE value fresh off creature_death_bcd's own store (-2)
ICON_SPAWN_COUNTING = 0xFFFD           # LIFECYCLE value once the reload timer starts running (-3)


def creature_icon_spawn_step(read, type_ptr, instance_ptr):
    """00A6C8-00A76E: the icon-spawn sub-machine one live instance with LIFECYCLE < 0 runs, once per
    per-frame-update activation.  Three LIFECYCLE bands: exactly -2 (`'reload-wait'`, the icon-cue's
    own second add.w, `bsr $b920`, on its own reload's own expiry), exactly -3 (`'seed-wait'`, the
    per-instance reload's own expiry reseeds LIFECYCLE from the type's own icon-kind byte and reseeds
    the SAME reload timer, the SAME `10 - byte` shape 00AA76/00AB50's own retry reseed uses), and any
    other negative value (`'display'`, a small state machine over FRAME_STEP driving a floating-icon
    spawn through the already-recovered 010D7C on its own first frame -- when DISPLAY_TIMER is still
    live and under 0xC0 -- then the already-recovered static sprite emitter (001164) every frame after,
    until FRAME_STEP reaches 7 and LIFECYCLE/LIFECYCLE_RESET both clear, settling the instance)."""
    lifecycle = read((instance_ptr + LIFECYCLE) & 0xFFFFFF, 2) & 0xFFFF
    if lifecycle == ICON_SPAWN_ARMED:
        reload_before = read((instance_ptr + LIFECYCLE_RESET) & 0xFFFFFF, 2) & 0xFFFF
        reload_after = (reload_before - 1) & 0xFFFF
        if reload_after != 0:
            return {'arm': 'reload-wait', 'fired': False, 'reload_before': reload_before, 'reload_after': reload_after}
        return {'arm': 'reload-wait', 'fired': True, 'reload_before': reload_before, 'reload_after': reload_after}
    if lifecycle == ICON_SPAWN_COUNTING:
        reload_before = read((instance_ptr + LIFECYCLE_RESET) & 0xFFFFFF, 2) & 0xFFFF
        reload_after = (reload_before - 1) & 0xFFFF
        if reload_after != 0:
            return {'arm': 'seed-wait', 'fired': False, 'reload_before': reload_before, 'reload_after': reload_after}
        icon_kind = read((type_ptr + TYPE_ICON_KIND_BYTE) & 0xFFFFFF, 1) & 0xFF
        byte = read((type_ptr + TYPE_GROUND_RELOAD_BYTE) & 0xFFFFFF, 1) & 0xFF
        diff = (0xA - byte) & 0xFF
        from .grid import _signed_byte
        word = _signed_byte(diff) & 0xFFFF
        freq = read(timers.FREQUENCY_SCALE, 2) & 0xFFFF
        product = (word * freq) & 0xFFFFFFFF
        doubled = (product * 2) & 0xFFFFFFFF
        swapped_low = (doubled >> 16) & 0xFFFF
        swapped_high = doubled & 0xFFFF
        reseeded = (swapped_low + 1) & 0xFFFF
        return {'arm': 'seed-wait', 'fired': True, 'reload_before': reload_before, 'reload_after': reload_after,
                'new_lifecycle': icon_kind, 'byte': byte, 'diff': diff, 'reseed': reseeded,
                'reseed_d0_exit': (swapped_high << 16) | reseeded}
    # 'display': any other negative LIFECYCLE.  FRAME_STEP >= 0 skips straight to the frame-step
    # advance below (00A744); FRAME_STEP < 0 (only the icon's own first frame) additionally spawns
    # the floating icon through 010D7C, but only while DISPLAY_TIMER is still live (>= 0).
    frame_step = read((instance_ptr + FRAME_STEP) & 0xFFFFFF, 2) & 0xFFFF
    frame_step_signed = frame_step - 0x10000 if frame_step & 0x8000 else frame_step
    result = {'arm': 'display', 'lifecycle': lifecycle, 'frame_step': frame_step, 'spawn_icon': False}
    if frame_step_signed < 0:
        display_timer = read((instance_ptr + DISPLAY_TIMER) & 0xFFFFFF, 2) & 0xFFFF
        display_signed = display_timer - 0x10000 if display_timer & 0x8000 else display_timer
        if display_signed >= 0:
            # cmpi.w #$c0,d2; bge.b (>= 0xc0: subi.w #$c0,d2); else (< 0xc0: addi.w #$b,d2) -- two
            # DISTINCT ROM arms, not the same arithmetic: the icon "kind" 010D7C's own D2 argument
            # becomes is display_timer - 0xc0 when display_timer is at or past 0xc0, else
            # display_timer + 0xb below it.
            icon_kind = (display_signed - 0xC0) & 0xFFFF if display_signed >= 0xC0 else (display_signed + 0xB) & 0xFFFF
            result['spawn_icon'] = True
            result['icon_kind'] = icon_kind
            result['icon_kind_high_arm'] = display_signed >= 0xC0
            result['position'] = (read(instance_ptr & 0xFFFFFF, 2) & 0xFFFF, read((instance_ptr + 2) & 0xFFFFFF, 2) & 0xFFFF)
            result['display_timer'] = display_timer
    return result


TYPE_WAVE_ICON_KIND = 0x10             # type_ptr word: negative skips the wave-complete icon spawn


def creature_wave_complete_check(read, type_ptr, slot_addr, settled_count, other_negative_count, cached_position):
    """00A68E-00A6BC: once every live instance in this slot's own per-frame-update batch is either
    'settled' (LIFECYCLE == 0) or in the icon-spawn sub-machine's own 'display' arm, and the slot's
    own WAVE_TRIGGERED latch is not yet set, cue one more floating icon (010D7C) at the LAST 'display'
    instance's own cached position (F26C/F26E, only ever written by that arm) -- unless the type's own
    TYPE_WAVE_ICON_KIND word is negative, which still sets the latch but skips the call."""
    type_count = read(type_ptr & 0xFFFFFF, 1) & 0xFF
    if (settled_count + other_negative_count) & 0xFF != type_count:
        return {'arm': 'not-yet', 'settled_count': settled_count, 'other_negative_count': other_negative_count}
    if read((slot_addr + CREATURE_LIST_WAVE_TRIGGERED) & 0xFFFFFF, 1) & 0xFF:
        return {'arm': 'already-triggered'}
    wave_icon = read((type_ptr + TYPE_WAVE_ICON_KIND) & 0xFFFFFF, 2) & 0xFFFF
    wave_icon_signed = wave_icon - 0x10000 if wave_icon & 0x8000 else wave_icon
    if wave_icon_signed < 0:
        return {'arm': 'skip-negative', 'wave_icon': wave_icon}
    x, y = cached_position
    return {'arm': 'trigger', 'wave_icon': wave_icon, 'x': (x + 8) & 0xFFFF, 'y': y & 0xFFFF}


def _signed_byte(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def creature_slot_deactivate_check(read, type_ptr, settled_count):
    """00A6BC-00A6C6: `cmp.b (a4),d6; blt.b $a64e` -- a BYTE, signed comparison (only d6's own low byte
    participates).  Once EVERY instance in this slot's own per-frame batch is 'settled' (not merely
    displaying an icon), the slot itself deactivates (its own header clears to 0, freeing the slot for
    a future spawn-init header)."""
    type_count = _signed_byte(read(type_ptr & 0xFFFFFF, 1))
    return not (_signed_byte(settled_count) < type_count)
