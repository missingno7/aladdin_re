"""Exact outer effects of recovered Gods regions over the live machine; semantics are in ``game``.

A planner reads the parked machine at a region's entry and returns the
``AtomicPlan`` the shared adapter admits as one operation: the RAM bytes,
the register file at the exit, and the original's instruction and cycle
cost along the executed path -- or a ``Seam`` when the region contains a
platform operation the machine must run (``genesis_re.seam``).  Anything a
recording has not witnessed is declined with ``UnsupportedCandidate`` and
the original runs it.
"""
from __future__ import annotations

from genesis_re.seam import AtomicPlan, Seam, UnsupportedCandidate  # noqa: F401  (the shared admission contract)

from .game import camera


CAMERA_FOLLOW_ENTRY, CAMERA_FOLLOW_LAST_PC = 0x002806, 0x002850

# 68000 costs of the routine's instructions along its paths, as the tracer
# measured them (artifacts/gods/evidence/census-002806*): the common trunk,
# the three x arms, the x limit and the y limit.
_TRUNK_CYCLES = (12 + 12       # move.w FOLLOW_X,d0; sub.w CAMERA_X,d0
                 + 12 + 10     # move.w CAMERA_X,d0; bpl taken
                 + 8 + 8       # asr; cmpi #$680
                 + 12          # move.w d0,SCROLL_X
                 + 12 + 10     # move.w FOLLOW_Y,d0; bpl taken
                 + 12 + 8 + 8  # move.w d0,CAMERA_Y; asr; cmpi #$100
                 + 12 + 16)    # move.w d0,SCROLL_Y; rts
_TRUNK_INSTRUCTIONS = 14
_X_ARMS = {'hold': (10, 1),               # beq taken
           'right': (8 + 10 + 16, 3),     # beq not taken, bpl taken, addq.w #4,CAMERA_X
           'left': (8 + 8 + 16 + 10, 4)}  # beq, bpl not taken, subq.w #4,CAMERA_X, bra
_LIMIT_ARMS = {False: (10, 1),            # blt taken
               True: (8 + 8, 2)}          # blt not taken, move.w #$67f,d0 / move.w #$ff,d0
WITNESSED_CLAMPS = {'x-limit', 'y-limit'}  # the negative clamps (002822, 00283A) are unwitnessed: declined


def _word_bytes(address, value):
    return ((address, (value >> 8) & 0xFF), (address + 1, value & 0xFF))


def camera_follow_plan(machine, registers):
    """002806: the camera follow step, admitted on the witnessed arms only."""
    if registers['pc'] != CAMERA_FOLLOW_ENTRY:
        raise UnsupportedCandidate('camera follow planner needs the machine parked at 002806')
    read_word = lambda address: int.from_bytes(machine.peek_ram(address & 0xFFFF, 2), 'big')
    result = camera.camera_follow(read_word)
    unwitnessed = [name for name in result['clamps'] if name not in WITNESSED_CLAMPS]
    if unwitnessed:
        raise UnsupportedCandidate('camera clamp not witnessed by a recording: ' + ', '.join(unwitnessed))
    x_cycles, x_instructions = _X_ARMS[result['branch']]
    xl_cycles, xl_instructions = _LIMIT_ARMS['x-limit' in result['clamps']]
    y_cycles, y_instructions = _LIMIT_ARMS['y-limit' in result['clamps']]
    writes = tuple(pair for address, value in result['stores'].items() for pair in _word_bytes(address, value))
    d0 = (registers['d0'] & 0xFFFF0000) | result['d0']
    # The last flag-setting instruction is move.w d0,SCROLL_Y: N/Z from the stored word, V=C=0;
    # X is the low bit of the y word the preceding asr shifted out.
    ccr = (result['x_flag'] << 4) | (0x04 if result['d0'] == 0 else 0)
    sp = registers['a7']
    return AtomicPlan(
        cycles=_TRUNK_CYCLES + x_cycles + xl_cycles + y_cycles,
        instructions=_TRUNK_INSTRUCTIONS + x_instructions + xl_instructions + y_instructions,
        writes=writes,
        registers={'d0': d0, 'a7': (sp + 4) & 0xFFFFFFFF,
                   'pc': int.from_bytes(machine.peek_ram(sp & 0xFFFF, 4), 'big') & 0xFFFFFF,
                   'sr': (registers['sr'] & ~0x1F) | ccr},
        last_pc=CAMERA_FOLLOW_LAST_PC)


def _logic_sr(sr, value, width):
    """68000 MOVE/logic flags of ``value``: N and Z, V and C clear, X retained."""
    mask = (1 << (8 * width)) - 1
    value &= mask
    out = sr & ~0x0F
    if value == 0:
        out |= 0x04
    if value & (1 << (8 * width - 1)):
        out |= 0x08
    return out


def _cmp_sr(sr, left, right, width):
    """68000 CMP flags of ``left - right``, X retained."""
    mask, sign = (1 << (8 * width)) - 1, 1 << (8 * width - 1)
    left &= mask
    right &= mask
    result = (left - right) & mask
    out = _logic_sr(sr, result, width)
    if left < right:
        out |= 0x01
    if (left ^ right) & (left ^ result) & sign:
        out |= 0x02
    return out


def _add_sr(sr, left, right, width):
    """68000 ADD/ADDQ flags of ``left + right``, X set with C."""
    mask, sign = (1 << (8 * width)) - 1, 1 << (8 * width - 1)
    left &= mask
    right &= mask
    total = left + right
    result = total & mask
    out = _logic_sr(sr & ~0x1F, result, width)
    if total > mask:
        out |= 0x11
    if ~(left ^ right) & (left ^ result) & sign:
        out |= 0x02
    return out


def _margin_add_x(sr, operand, margin, width=2):
    """The X (=C) bit an ADD of ``margin`` into ``operand`` leaves; a later CMP does not touch X.

    Unlike ``_cmp_sr``, X here cannot be retained from the caller's SR: the
    routine's own ADD (the screen-margin test) sets it fresh from this
    addition's carry, overwriting whatever X the entry SR held.
    """
    mask = (1 << (8 * width)) - 1
    total = (operand & mask) + (margin & mask)
    return (sr & ~0x10) | (0x10 if total > mask else 0)


def _asl_sr(sr, value, shift, width=2):
    """68000 ASL flags of a left shift by a fixed, nonzero count: N/Z from the result, X=C the last bit
    shifted out, V set if any of the bits shifted past the sign (plus the sign itself) were not uniform.
    """
    bits = 8 * width
    mask, sign = (1 << bits) - 1, 1 << (bits - 1)
    value &= mask
    result = (value << shift) & mask
    out = sr & ~0x1F
    if result & sign:
        out |= 0x08
    if result == 0:
        out |= 0x04
    span = min(shift + 1, bits)
    top = (value >> (bits - span)) & ((1 << span) - 1)
    if top not in (0, (1 << span) - 1):
        out |= 0x02
    if shift and (value >> (bits - shift)) & 1:
        out |= 0x11
    return out


def _bytes(address, value, size):
    return tuple((address + index, (value >> (8 * (size - index - 1))) & 0xFF) for index in range(size))


def _ram_span(name, address, size):
    if not 0xFF0000 <= address <= 0xFFFFFF - size + 1:
        raise UnsupportedCandidate(f'{name} lies outside work RAM')
    return address


def _spans_disjoint(spans):
    checked = [(name, _ram_span(name, start, size), size) for name, start, size in spans]
    for index, (name, start, size) in enumerate(checked):
        for other, other_start, other_size in checked[index + 1:]:
            if start < other_start + other_size and other_start < start + size:
                raise UnsupportedCandidate(f'{name} overlaps {other}')


def _reader(machine):
    """``read(address, size)`` over work RAM and the cartridge, for the semantics."""
    def read(address, size):
        address &= 0xFFFFFF
        if 0xFF0000 <= address <= 0xFFFFFF - size + 1:
            return int.from_bytes(machine.peek_ram(address & 0xFFFF, size), 'big')
        try:
            return int.from_bytes(machine.peek_rom(address, size), 'big')
        except ValueError as error:
            raise UnsupportedCandidate(f'read of {address:06X} is neither work RAM nor ROM') from error
    return read


# --- 0018C8: the dynamic sprite emitter (game/sprites.py) --------------------
#
# Cost table from the tracer (artifacts/gods/evidence/census-0018C8-*), per
# path fragment: (cycles, instructions).
SPRITE_EMIT_ENTRY, SPRITE_EMIT_UPLOAD, SPRITE_EMIT_RESUME, SPRITE_EMIT_LAST_PC = 0x0018C8, 0x001974, 0x00198C, 0x001990
SPRITE_EMIT_PREFIX_LAST_PC = 0x00196E  # ori.l #$40000000,d0: the last instruction before the VDP control write
SPRITE_EMIT_FRAME = 36                 # movem.l d0-d5/a0-a2,-(a7)
_SPRITE_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'a0', 'a1', 'a2')
_SE_HEAD = (168, 12)                   # movem, move.w #$2000, the two camera subtractions, both bounds tests not taken
_SE_OFFSCREEN_X = (138, 8)             # ... the x test taken (bhi 10)
_SE_OFFSCREEN_Y = (166, 12)            # ... the y test taken
_SE_SETUP = (66, 8)                    # move.w d2,d3; lea; lea; add.w; adda.w; lea; lea; moveq #7
_SE_SCAN_MISMATCH = (50, 6)            # tst; bmi not taken; cmp (a1)+; beq not taken; addq a2; dbra taken
_SE_SCAN_HIT = (34, 4)                 # tst; bmi not taken; cmp; beq taken
_SE_SCAN_EMPTY = (18, 2)               # tst; bmi taken
_SE_SCAN_EXHAUSTED = (54, 6)           # the eighth mismatch with dbra falling through
_SE_HIT_TAIL = (192, 19)               # 001992..0019D0, no flip
_SE_MISS_TAIL = (276, 27)              # 00191C..00196E, no flip: the prefix ends at the VDP control write
_SE_RESTORE = (100, 2)                 # movem.l (a7)+; rts
_SPRITE_GLOBALS = (('sprite list head', 0xFFEBF8, 4), ('sprite list last', 0xFFEBFC, 4),
                   ('sprite count', 0xFFEBF6, 2), ('tile cursor', 0xFFEE84, 2), ('camera', 0xFFEA38, 4))


def _frame_writes(sp, registers):
    return tuple(pair for index, name in enumerate(_SPRITE_FRAME_REGISTERS)
                 for pair in _bytes(sp - SPRITE_EMIT_FRAME + 4 * index, registers[name], 4))


def _return(machine, sp):
    return int.from_bytes(machine.peek_ram(sp & 0xFFFF, 4), 'big') & 0xFFFFFF


def sprite_emit_plan(machine, registers):
    """0018C8: an off-screen or cached sprite as one plan; an uploaded one as a ``Seam``."""
    from .game import sprites
    if registers['pc'] != SPRITE_EMIT_ENTRY:
        raise UnsupportedCandidate('sprite emit planner needs the machine parked at 0018C8')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    frame = ('sprite frame', sp - SPRITE_EMIT_FRAME, SPRITE_EMIT_FRAME + 4)
    _ram_span(*frame)
    result = sprites.emit_sprite(_reader(machine), registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF,
                                 registers['d2'] & 0xFFFF)
    arm = result['arm']
    screen_x, screen_y = result['screen']
    if arm == 'offscreen-x':
        cost = (_SE_OFFSCREEN_X[0] + _SE_RESTORE[0], _SE_OFFSCREEN_X[1] + _SE_RESTORE[1])
        exit_sr = _cmp_sr(sr, (screen_x + sprites.SCREEN_MARGIN) & 0xFFFF, sprites.SCREEN_X_LIMIT, 2)
    elif arm == 'offscreen-y':
        cost = (_SE_OFFSCREEN_Y[0] + _SE_RESTORE[0], _SE_OFFSCREEN_Y[1] + _SE_RESTORE[1])
        exit_sr = _cmp_sr(sr, (screen_y + sprites.SCREEN_MARGIN) & 0xFFFF, sprites.SCREEN_Y_LIMIT, 2)
    if arm.startswith('offscreen'):
        return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=_frame_writes(sp, registers),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=SPRITE_EMIT_LAST_PC)
    if result['flip']:
        raise UnsupportedCandidate('flipped sprite arm not witnessed by a recording')
    record, slot = result['record'], result['inserted']
    spans = [frame, ('sprite record', record, sprites.RECORD_SIZE), *_SPRITE_GLOBALS]
    if slot is None:
        spans.append(('cache tables', sprites.CACHE_IDS, 4 * (sprites.CACHE_SCANNED + 1)))
    else:
        spans += [('cache id slot', sprites.CACHE_IDS + 2 * slot, 2),
                  ('cache tile slot', sprites.CACHE_TILES + 2 * slot, 2)]
    _spans_disjoint(spans)
    exhausted = slot == sprites.CACHE_SCANNED
    mismatches = result['scan'] - 1                 # slots tested before the decisive one (the eighth, when exhausted)
    decisive = _SE_SCAN_HIT if arm == 'hit' else (_SE_SCAN_EXHAUSTED if exhausted else _SE_SCAN_EMPTY)
    tail = _SE_HIT_TAIL if arm == 'hit' else _SE_MISS_TAIL
    cycles = _SE_HEAD[0] + _SE_SETUP[0] + mismatches * _SE_SCAN_MISMATCH[0] + decisive[0] + tail[0]
    instructions = _SE_HEAD[1] + _SE_SETUP[1] + mismatches * _SE_SCAN_MISMATCH[1] + decisive[1] + tail[1]
    writes = _frame_writes(sp, registers) + tuple(
        pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    if arm == 'hit':
        # The last flag-setting instruction is addq.w #1,LIST_COUNT; the registers come back from the frame.
        return AtomicPlan(cycles=cycles + _SE_RESTORE[0], instructions=instructions + _SE_RESTORE[1],
                          writes=writes,
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp),
                                     'sr': _add_sr(sr, result['count'], 1, 2)},
                          last_pc=SPRITE_EMIT_LAST_PC)
    # A miss: the prefix leaves the machine at the VDP control write with the
    # upload's registers in place; the last flag-setter is ori.l #$40000000,d0.
    upload = result['upload']
    high = lambda name: registers[name] & 0xFFFF0000
    prefix = AtomicPlan(
        cycles=cycles, instructions=instructions, writes=writes,
        registers={'d0': upload['command'],
                   'd1': high('d1') | (upload['cursor'] >> 5) | sprites.PRIORITY_ATTRIBUTE,
                   'd2': high('d2') | result['stores'][record + 2][0],
                   'd3': high('d3'),
                   'd4': (7 - mismatches - exhausted) & 0xFFFF,   # moveq #7 counted down by every dbra
                   'd5': high('d5') | sprites.PRIORITY_ATTRIBUTE,   # move.w #$2000,d5 keeps the upper word
                   'a0': result['descriptor'],
                   'a1': result['stores'][sprites.LIST_HEAD][0],
                   'a2': (0xFFFF0000 | (sprites.CACHE_TILES + 2 * slot + 2)) & 0xFFFFFFFF,
                   'a7': (sp32 - SPRITE_EMIT_FRAME) & 0xFFFFFFFF,
                   'pc': SPRITE_EMIT_UPLOAD,
                   'sr': _logic_sr(sr, upload['command'], 4)},
        last_pc=SPRITE_EMIT_PREFIX_LAST_PC)
    return Seam(prefix=prefix, resume_pc=SPRITE_EMIT_RESUME,
                stack_basis=(sp32 - SPRITE_EMIT_FRAME) & 0xFFFFFFFF,
                guards=((sp - SPRITE_EMIT_FRAME, SPRITE_EMIT_FRAME + 4),), suffix=sprite_emit_suffix)


# --- 001164: the sibling without a cache (game/sprites.py: emit_static_sprite) ---------------
#
# Cost table from the tracer (artifacts/gods/evidence/census-001164*), per
# path fragment: (cycles, instructions).  No platform operation: a plain plan.
STATIC_EMIT_ENTRY, STATIC_EMIT_LAST_PC = 0x001164, 0x0011E4
STATIC_EMIT_FRAME = 24                              # movem.l d0-d3/a0-a1,-(a7)
_STATIC_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'a0', 'a1')
_SK_HEAD = (80, 3)                     # movem, sub.w CAMERA_X,d0; sub.w CAMERA_Y,d1
_SK_X_TEST = (16, 3)                   # moveq #$20,d3; add.w d0,d3; cmpi.w #$160,d3
_SK_Y_TEST = (16, 3)                   # moveq #$20,d3; add.w d1,d3; cmpi.w #$e0,d3
_SK_TAKEN, _SK_NOT_TAKEN = (10, 1), (8, 1)             # a Bcc.b outcome
_SK_SETUP_NOFLIP = (76, 8)             # move d2,d3; lea; lea; add d2,d2; adda; move 6(a0),d2; andi; beq (taken)
_SK_SETUP_FLIP = (94, 10)              # ... beq (not taken); move #$800,d3; move 8(a0),d2
_SK_POSITION = (46, 4)                 # add d2,d0; add $a(a0),d1; movea LIST_HEAD,a1; cmpa #LIST_FULL,a1
_SK_WRITE = (128, 12)                  # the four record words, the list pointers, addq LIST_COUNT
_SK_RESTORE = (76, 2)                  # movem.l (a7)+; rts
WITNESSED_STATIC_ARMS = {'offscreen-x', 'offscreen-y', 'placed'}   # 'full' (the list-full guard): unwitnessed


def _static_frame_writes(sp, registers):
    return tuple(pair for index, name in enumerate(_STATIC_FRAME_REGISTERS)
                 for pair in _bytes(sp - STATIC_EMIT_FRAME + 4 * index, registers[name], 4))


def _static_emit_cost(arm, flip):
    """001164's own cost (cycles, instructions) for one call, by arm -- shared with a caller composing several calls."""
    if arm == 'offscreen-x':
        return (_SK_HEAD[0] + _SK_X_TEST[0] + _SK_TAKEN[0] + _SK_RESTORE[0],
                _SK_HEAD[1] + _SK_X_TEST[1] + _SK_TAKEN[1] + _SK_RESTORE[1])
    if arm == 'offscreen-y':
        return (_SK_HEAD[0] + _SK_X_TEST[0] + _SK_NOT_TAKEN[0] + _SK_Y_TEST[0] + _SK_TAKEN[0] + _SK_RESTORE[0],
                _SK_HEAD[1] + _SK_X_TEST[1] + _SK_NOT_TAKEN[1] + _SK_Y_TEST[1] + _SK_TAKEN[1] + _SK_RESTORE[1])
    setup = _SK_SETUP_FLIP if flip else _SK_SETUP_NOFLIP
    return (_SK_HEAD[0] + _SK_X_TEST[0] + _SK_NOT_TAKEN[0] + _SK_Y_TEST[0] + _SK_NOT_TAKEN[0]
           + setup[0] + _SK_POSITION[0] + _SK_NOT_TAKEN[0] + _SK_WRITE[0] + _SK_RESTORE[0],
            _SK_HEAD[1] + _SK_X_TEST[1] + _SK_NOT_TAKEN[1] + _SK_Y_TEST[1] + _SK_NOT_TAKEN[1]
           + setup[1] + _SK_POSITION[1] + _SK_NOT_TAKEN[1] + _SK_WRITE[1] + _SK_RESTORE[1])


def static_emit_plan(machine, registers):
    """001164: the RAM-only sprite emitter sibling; the list-full guard is declined (unwitnessed)."""
    from .game import sprites
    if registers['pc'] != STATIC_EMIT_ENTRY:
        raise UnsupportedCandidate('static sprite emit planner needs the machine parked at 001164')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    frame = ('static sprite frame', sp - STATIC_EMIT_FRAME, STATIC_EMIT_FRAME + 4)
    _ram_span(*frame)
    result = sprites.emit_static_sprite(_reader(machine), registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF,
                                        registers['d2'] & 0xFFFF)
    arm = result['arm']
    if arm not in WITNESSED_STATIC_ARMS:
        raise UnsupportedCandidate(f'static sprite arm not witnessed by a recording: {arm}')
    screen_x, screen_y = result['screen']
    writes = _static_frame_writes(sp, registers)
    cost = _static_emit_cost(arm, result['flip'])
    if arm == 'offscreen-x':
        exit_sr = _cmp_sr(_margin_add_x(sr, screen_x, sprites.SCREEN_MARGIN),
                          (screen_x + sprites.SCREEN_MARGIN) & 0xFFFF, sprites.SCREEN_X_LIMIT, 2)
    elif arm == 'offscreen-y':
        exit_sr = _cmp_sr(_margin_add_x(sr, screen_y, sprites.SCREEN_MARGIN),
                          (screen_y + sprites.SCREEN_MARGIN) & 0xFFFF, sprites.SCREEN_Y_LIMIT, 2)
    if arm.startswith('offscreen'):
        return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes,
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=STATIC_EMIT_LAST_PC)
    # 'placed': the descriptor lookup, the list-full guard (not taken), the record append.
    record, count = result['record'], result['count']
    spans = [frame, ('static sprite record', record, sprites.RECORD_SIZE), *_SPRITE_GLOBALS]
    _spans_disjoint(spans)
    writes += tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    # The last flag-setting instruction is addq.w #1,LIST_COUNT; the registers come back from the frame.
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes,
                      registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp),
                                 'sr': _add_sr(sr, count, 1, 2)},
                      last_pc=STATIC_EMIT_LAST_PC)


# --- 0049DA: the spawn queue (game/spawn_queue.py: scan_spawn_queue) ---------
#
# A RAM-only leaf that calls the already-recovered 001164 once per active
# slot (0-2 witnessed at once); its own cost fragments, from the tracer
# (artifacts/gods/evidence/census-0049DA*).  001164 pushes and pops its own
# frame at the current stack pointer, which 0049DA itself never moves, so
# every call's frame lands at the same 28 bytes below entry a7 -- only the
# last call's frame write need be declared (the rest are overwritten before
# the routine returns).
SPAWN_QUEUE_ENTRY, SPAWN_QUEUE_LAST_PC = 0x0049DA, 0x004A08
SPAWN_CALL_RETURN = 0x0049F6                        # the PC bsr.w 001164 pushes and returns to
SPAWN_CALL_FRAME = STATIC_EMIT_FRAME + 4            # the callee's frame plus the pushed return address
_SQ_HEAD = (16, 2)                     # lea.l SLOT_BASE,a4; moveq #3,d7
_SQ_SKIP_BASE = (22, 3)                # tst.w (a4); bmi.b taken; addq.w #6,a4
_SQ_ACTIVE_PRE = (70, 7)               # tst; bmi not taken; move.w x2; moveq; add.w (a4),d2; bsr.w 001164
_SQ_POST_CONTINUE_BASE = (38, 4)       # addq.w #1,(a4); cmpi.w #7,(a4); blt.b taken; addq.w #6,a4
_SQ_POST_RETIRE_BASE = (48, 5)         # addq.w #1,(a4); cmpi.w #7,(a4); blt.b not taken; move.w #-1,(a4); addq.w #6,a4
_SQ_DBRA_TAKEN, _SQ_DBRA_LAST = 10, 14                # dbra d7: mid-loop vs the final (4th) iteration
_SQ_RETURN = (16, 1)                   # rts


def spawn_queue_plan(machine, registers):
    """0049DA: up to four calls to the static sprite emitter, one per active slot."""
    from .game import sprites, spawn_queue
    if registers['pc'] != SPAWN_QUEUE_ENTRY:
        raise UnsupportedCandidate('spawn queue planner needs the machine parked at 0049DA')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    frame = ('spawn queue call frame', sp - SPAWN_CALL_FRAME, SPAWN_CALL_FRAME)
    _ram_span(*frame)
    slots = spawn_queue.scan_spawn_queue(_reader(machine))
    cycles, instructions = _SQ_HEAD
    writes, last_call_writes, last_active_registers = (), (), None
    for index, slot in enumerate(slots):
        last = index == len(slots) - 1
        dbra = _SQ_DBRA_LAST if last else _SQ_DBRA_TAKEN
        if not slot['active']:
            sr = _logic_sr(sr, slot['counter'], 2)
            cycles += _SQ_SKIP_BASE[0] + dbra
            instructions += _SQ_SKIP_BASE[1] + 1
            continue
        emitted = slot['emitted']
        arm = emitted['arm']
        if arm not in WITNESSED_STATIC_ARMS:
            raise UnsupportedCandidate(f'spawn queue slot {index}: static sprite arm not witnessed: {arm}')
        call_cost = _static_emit_cost(arm, emitted['flip'])
        base = _SQ_POST_RETIRE_BASE if slot['retire'] else _SQ_POST_CONTINUE_BASE
        cycles += _SQ_ACTIVE_PRE[0] + call_cost[0] + base[0] + dbra
        instructions += _SQ_ACTIVE_PRE[1] + call_cost[1] + base[1] + 1
        sr = _add_sr(sr, slot['counter'], 1, 2)
        sr = _logic_sr(sr, 0xFFFF, 2) if slot['retire'] else _cmp_sr(sr, slot['counter_store'], 7, 2)
        slot_base = spawn_queue.SLOT_BASE + spawn_queue.SLOT_SIZE * index
        writes += ((slot_base, (slot['counter_store'] >> 8) & 0xFF), (slot_base + 1, slot['counter_store'] & 0xFF))
        writes += tuple(pair for address, (value, size) in emitted['stores'].items() for pair in _bytes(address, value, size))
        registers_at_call = {'d0': slot['x'], 'd1': slot['y'], 'd2': slot['sprite'],
                             'd3': registers['d3'], 'a0': registers['a0'], 'a1': registers['a1']}
        last_call_writes = (_static_frame_writes(sp - 4, registers_at_call)
                            + tuple(_bytes(sp - 4, SPAWN_CALL_RETURN, 4)))
        last_active_registers = registers_at_call
    cycles += _SQ_RETURN[0]
    instructions += _SQ_RETURN[1]
    final_a4 = 0xFFFF0000 | ((spawn_queue.SLOT_BASE + spawn_queue.SLOT_SIZE * spawn_queue.SLOT_COUNT) & 0xFFFFFF)
    exit_registers = {'a4': final_a4, 'd7': 0xFFFF, 'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': sr}
    if last_active_registers is not None:
        # d0-d2 carry the last active slot's x/y/sprite (the pushed-and-popped frame restores them
        # unchanged across every call); d3/a0/a1 are never touched by 0049DA itself.
        exit_registers.update(d0=last_active_registers['d0'] & 0xFFFF | (registers['d0'] & 0xFFFF0000),
                              d1=last_active_registers['d1'] & 0xFFFF | (registers['d1'] & 0xFFFF0000),
                              d2=last_active_registers['d2'] & 0xFFFF | (registers['d2'] & 0xFFFF0000))
    # The frame/return-address bytes lead: they are dead scratch by the time the routine returns
    # (each call's own RTS already consumed its return address), so the negative control's generic
    # "flip the last write" must land on the last slot's own durable store, not that scratch.
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=last_call_writes + writes,
                      registers=exit_registers, last_pc=SPAWN_QUEUE_LAST_PC)


# --- 004150: the work-table reset (game/tables.py: reset_table) --------------
#
# Cost from the tracer (artifacts/gods/evidence/census-004150*): fully
# unrolled, so cost is constant per arm (no data-dependent loop count).
TABLE_RESET_ENTRY, TABLE_RESET_LAST_PC = 0x004150, 0x0041EE
TABLE_RESET_FRAME = 56                              # movem.l d0-d7/a0-a5,-(a7)
_TR_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'a0', 'a1', 'a2', 'a3', 'a4', 'a5')
_TR_ZERO_COST = (3806, 38)       # tst.w RESET_FLAG negative: bmi taken straight into the fill bursts
_TR_POISON_COST = (3940, 40)     # not negative: the extra reload and clr.w $ef5c.w before the same bursts


def _table_reset_frame_writes(sp, registers):
    return tuple(pair for index, name in enumerate(_TR_FRAME_REGISTERS)
                 for pair in _bytes(sp - TABLE_RESET_FRAME + 4 * index, registers[name], 4))


def table_reset_plan(machine, registers):
    """004150: an unconditional table fill, one of two constant fill bytes."""
    from .game import tables
    if registers['pc'] != TABLE_RESET_ENTRY:
        raise UnsupportedCandidate('table reset planner needs the machine parked at 004150')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    read_word = lambda address: int.from_bytes(machine.peek_ram(address & 0xFFFF, 2), 'big')
    result = tables.reset_table(read_word)
    cost = _TR_POISON_COST if result['poisoned'] else _TR_ZERO_COST
    # tst.w (the zero-fill arm) or clr.w $ef5c.w (the poison-fill arm) is the last flag-setter; X is retained
    # unchanged from entry by every instruction on either path (movem/lea/tst/bmi/clr do not touch X).
    exit_value = read_word(tables.RESET_FLAG) if not result['poisoned'] else 0
    exit_sr = _logic_sr(sr, exit_value, 2)
    writes = _table_reset_frame_writes(sp, registers) + tuple(result['stores'].items())
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes,
                      registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                      last_pc=TABLE_RESET_LAST_PC)


# --- 0063FA: the grid cell lookup (game/grid.py: grid_cell) -------------------
#
# A straight-line leaf: one path, no writes, no branch.  Cost from the
# tracer (artifacts/gods/evidence/census-0063FA*).
GRID_CELL_ENTRY, GRID_CELL_LAST_PC = 0x0063FA, 0x006412
GRID_CELL_COST = (100, 9)


def grid_cell_plan(machine, registers):
    """0063FA: the grid cell address; the last flag-setter is asl.w #3,d1 (adda/lea/rts do not touch CCR)."""
    from .game import grid
    if registers['pc'] != GRID_CELL_ENTRY:
        raise UnsupportedCandidate('grid cell planner needs the machine parked at 0063FA')
    sr = registers['sr']
    result = grid.grid_cell(_reader(machine))
    exit_sr = _asl_sr(sr, result['row_source'], 3, 2)
    d0 = (registers['d0'] & 0xFFFF0000) | result['d0']
    d1 = (registers['d1'] & 0xFFFF0000) | result['d1']
    sp = registers['a7']
    return AtomicPlan(cycles=GRID_CELL_COST[0], instructions=GRID_CELL_COST[1], writes=(),
                      registers={'d0': d0, 'd1': d1, 'a0': result['address'] & 0xFFFFFFFF,
                                 'a7': (sp + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp & 0xFFFFFF), 'sr': exit_sr},
                      last_pc=GRID_CELL_LAST_PC)


def sprite_emit_suffix(machine, registers):
    """00198C after the upload: the frame back into the registers, the RTS; the CCR is the machine's."""
    if registers['pc'] != SPRITE_EMIT_RESUME:
        raise UnsupportedCandidate('sprite emit suffix needs the machine parked at 00198C')
    base = registers['a7']
    restored = {name: int.from_bytes(machine.peek_ram((base + 4 * index) & 0xFFFF, 4), 'big')
                for index, name in enumerate(_SPRITE_FRAME_REGISTERS)}
    sp = (base + SPRITE_EMIT_FRAME) & 0xFFFFFFFF
    restored.update(a7=(sp + 4) & 0xFFFFFFFF, pc=_return(machine, sp))
    return AtomicPlan(cycles=_SE_RESTORE[0], instructions=_SE_RESTORE[1], writes=(), registers=restored,
                      last_pc=SPRITE_EMIT_LAST_PC)
