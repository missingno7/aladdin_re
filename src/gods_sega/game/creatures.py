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
