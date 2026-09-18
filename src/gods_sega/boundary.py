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


def _sub_sr(sr, left, right, width):
    """68000 SUB/SUBQ flags of ``left - right``: N/Z/V/C as CMP, but X set with C (CMP leaves X alone)."""
    out = _cmp_sr(sr, left, right, width)
    return (out & ~0x10) | (0x10 if out & 0x01 else 0)


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


# --- 00FDB8: the footprint stamp (game/grid.py: stamp_footprint) --------------
#
# Cost from the tracer (artifacts/gods/evidence/census-00FDB8*): the head
# through the height read, then per row the width reload, the row push,
# the cells and the row pop; loop counts are the definition's own bytes,
# so the cost is a formula in (rows, cells) verified on four (rows, cells)
# combinations.
FOOTPRINT_STAMP_ENTRY, FOOTPRINT_STAMP_LAST_PC = 0x00FDB8, 0x00FE06
_FS_HEAD = (140, 15)                   # btst not taken ... movem.l d6-d7,-(a7); move.b $1b(a2),d7; ext.w
_FS_ROW = (62, 5)                      # move.b $1a(a2),d6; andi; pea $80(a0); movea.l (a7)+,a0; dbra d7 taken; the cells' last dbra +4
_FS_CELL = (58, 5)                     # move.l a0,(a5)+; clr.b; move.b (a0),(a5)+; move.b #1,(a0)+; dbra d6 (taken)
_FS_LAST = 4                           # the rows' dbra falling through costs 14, not 10
_FS_TAIL = (44, 2)                     # movem.l (a7)+,d6-d7; rts
FOOTPRINT_FRAME = 8                    # d6, d7
FOOTPRINT_MAX_CELLS = 64               # the verified domain (and well inside the atomic write limit)


def footprint_stamp_plan(machine, registers):
    """00FDB8: the solid's cells set and their old bytes queued for undo; the no-footprint arm is declined."""
    from .game import grid
    if registers['pc'] != FOOTPRINT_STAMP_ENTRY:
        raise UnsupportedCandidate('footprint stamp planner needs the machine parked at 00FDB8')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    definition, cursor = registers['a2'] & 0xFFFFFF, registers['a5']
    if (sp | definition | cursor) & 1:
        raise UnsupportedCandidate('unaligned stack, definition or undo cursor')
    result = grid.stamp_footprint(_reader(machine), registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF,
                                  definition, cursor)
    if result['arm'] == 'none':
        raise UnsupportedCandidate('no-footprint arm (width bit 7) not witnessed by a recording')
    rows, cells = result['rows'], result['cells']
    if result['height'] < 0:
        raise UnsupportedCandidate('negative footprint height wraps the row count')
    if rows * cells > FOOTPRINT_MAX_CELLS:
        raise UnsupportedCandidate('footprint larger than the verified domain')
    total = rows * cells
    spans = [('footprint frame', sp - FOOTPRINT_FRAME - 4, FOOTPRINT_FRAME + 4 + 4),
             ('footprint definition', definition, 0x1C),
             ('footprint undo entries', cursor & 0xFFFFFF, grid.UNDO_ENTRY * total)]
    first_row = result['first_row'] & 0xFFFFFF
    spans += [('footprint row %d' % index, (first_row + grid.GRID_ROW_BYTES * index) & 0xFFFFFF, cells)
              for index in range(rows)]
    _spans_disjoint(spans)
    cycles = _FS_HEAD[0] + rows * (_FS_ROW[0] + cells * _FS_CELL[0]) + _FS_LAST + _FS_TAIL[0]
    instructions = _FS_HEAD[1] + rows * (_FS_ROW[1] + cells * _FS_CELL[1]) + _FS_TAIL[1]
    # The frame: d6/d7 saved below the stack pointer, and the last row's pushed row-after value beneath them.
    writes = (_bytes(sp - FOOTPRINT_FRAME, registers['d6'], 4) + _bytes(sp - FOOTPRINT_FRAME + 4, registers['d7'], 4)
              + _bytes(sp - FOOTPRINT_FRAME - 4, result['row_after'], 4)
              + tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size)))
    # N/Z/V/C from the last move.b #1,(a0)+ (a positive, nonzero byte: all clear); X from asl.w #3,d3.
    exit_sr = (_asl_sr(sr, result['row_source'], 3, 2) & 0x10) | (sr & ~0x1F)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes,
                      registers={'d2': result['column'],
                                 'd3': (registers['d3'] & 0xFFFF0000) | result['row'],
                                 'a0': result['row_after'], 'a5': result['cursor'],
                                 'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                      last_pc=FOOTPRINT_STAMP_LAST_PC)


# --- 00FC8E: the solid drawer (game/solids.py: draw_solid) --------------------
#
# Cost from the tracer (artifacts/gods/evidence/census-00FC8E*): the head
# through the table scan and the tile lookup, then per row a reload of the
# column count, and per cell the two screen-bound tests, a skip or a
# four-word record write, and the loop bookkeeping; the negative (inline
# VDP upload) arm and an unmatched-and-unterminated table scan are declined
# -- no recording enters either.  Everything else (rows, cells, the visible
# count) is bounded by the same definition bytes 00FDB8 already reads.
SOLID_DRAW_ENTRY, SOLID_DRAW_LAST_PC = 0x00FC8E, 0x00FD26
SOLID_DRAW_FRAME = 36                                  # movem.l d0-d4/d6-d7/a0-a1,-(a7)
_SOLID_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'd4', 'd6', 'd7', 'a0', 'a1')
SOLID_DRAW_CELL_FRAME = 8                              # the per-cell movem.l d0-d1,-(a7): the last one is never popped by hand
SOLID_DRAW_MAX_CELLS = 64                              # the verified domain (rows x cells; witnessed up to 1x3 and 3x1)
_SD_HEAD = (12 + 4 + 80, 3)                            # move.b $4(a2),d2; ext.w; movem push
_SD_LOOKUP = (16, 1)                                   # movea.l $f2d6.w,a0
_SD_SCAN_MISMATCH = (8 + 4 + 8 + 4 + 10, 5)            # move.w (a0)+,d6; cmp.b; beq not taken; tst; bne taken
_SD_SCAN_MATCH = (8 + 4 + 10, 3)                       # move.w (a0)+,d6; cmp.b; beq taken
_SD_POST_MATCH = (4 + 12, 2)                           # tst.w d6; bmi.w not taken
_SD_TILE = (22 + 4, 2)                                 # lsr.w #8,d6; move.w d6,d2
_SD_PRELOOP = (12 + 12 + 16 + 12 + 4 + 4, 6)           # sub.w x2; movea.l LIST_HEAD,a0; move.b height,d7; ext.w; move.w d0,d3
_SD_ROW_HEAD = (12 + 8, 2)                             # move.b width,d6; andi.w #7,d6
_SD_ROW_TAIL = (4 + 8, 2)                              # move.w d3,d0; addi.w #$10,d1
_SD_CELL_HEAD = (24 + 4 + 4 + 8, 4)                    # movem.l d0-d1,-(a7); moveq #$20,d4; add.w d0,d4; cmpi.w #$160,d4
_SD_X_TAKEN = (10, 1)                                  # bhi.b taken: off the left/right edge, cell skipped
_SD_Y_TEST = (4 + 4 + 8, 3)                            # moveq #$10,d4; add.w d1,d4; cmpi.w #$e0,d4
_SD_Y_TAKEN = (10, 1)                                  # bhi.b taken: off the top/bottom edge, cell skipped
_SD_X_NOT_TAKEN, _SD_Y_NOT_TAKEN = 8, 8                # the same bhi.b, on-screen
_SD_VISIBLE_BODY = (16 + 8 + 8 + 12 + 8 + 8 + 8 + 8 + 8 + 16, 10)   # the four-word record write and the count bump
_SD_REJOIN = (28 + 8, 2)                               # movem.l (a7)+,d0-d1; addi.w #$20,d0
_SD_DBRA_TAKEN, _SD_DBRA_LAST = 10, 14                 # dbra: mid-loop vs. the count's final (not-taken) iteration
_SD_TAIL = (16 + 84 + 16, 3)                           # move.l a0,LIST_HEAD; movem pop (9 regs); rts
_SD_X_SKIP = (_SD_CELL_HEAD[0] + _SD_X_TAKEN[0], _SD_CELL_HEAD[1] + _SD_X_TAKEN[1])
_SD_Y_SKIP = (_SD_CELL_HEAD[0] + _SD_X_NOT_TAKEN + _SD_Y_TEST[0] + _SD_Y_TAKEN[0],
              _SD_CELL_HEAD[1] + 1 + _SD_Y_TEST[1] + _SD_Y_TAKEN[1])
_SD_VISIBLE = (_SD_CELL_HEAD[0] + _SD_X_NOT_TAKEN + _SD_Y_TEST[0] + _SD_Y_NOT_TAKEN + _SD_VISIBLE_BODY[0],
               _SD_CELL_HEAD[1] + 1 + _SD_Y_TEST[1] + 1 + _SD_VISIBLE_BODY[1])


def _solid_frame_writes(sp, registers, d2):
    values = {**{name: registers[name] for name in _SOLID_FRAME_REGISTERS}, 'd2': d2}
    return tuple(pair for index, name in enumerate(_SOLID_FRAME_REGISTERS)
                 for pair in _bytes(sp - SOLID_DRAW_FRAME + 4 * index, values[name], 4))


def draw_solid_plan(machine, registers):
    """00FC8E: sprite records for one active solid's rows x cells grid; the upload arm is declined."""
    from .game import solids
    if registers['pc'] != SOLID_DRAW_ENTRY:
        raise UnsupportedCandidate('solid draw planner needs the machine parked at 00FC8E')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    definition = registers['a2'] & 0xFFFFFF
    if (sp | definition) & 1:
        raise UnsupportedCandidate('unaligned stack or definition')
    result = solids.draw_solid(_reader(machine), registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF, definition)
    arm = result['arm']
    if arm != 'sprite':
        raise UnsupportedCandidate(f'solid draw arm not witnessed by a recording: {arm}')
    rows, cells, visible = result['rows'], result['cells'], result['visible']
    if rows * cells > SOLID_DRAW_MAX_CELLS:
        raise UnsupportedCandidate('solid grid larger than the verified domain')
    scanned, mismatches = result['scanned'], result['scanned'] - 1
    frame = ('solid draw frame', sp - SOLID_DRAW_FRAME - SOLID_DRAW_CELL_FRAME, SOLID_DRAW_FRAME + SOLID_DRAW_CELL_FRAME)
    initial_head = (result['final_head'] - visible * solids.RECORD_SIZE) & 0xFFFFFF
    spans = [frame, ('solid definition', definition, 0x1C), *_SPRITE_GLOBALS]
    if visible:
        spans.append(('solid sprite records', initial_head, visible * solids.RECORD_SIZE))
    _spans_disjoint(spans)
    # d2's pushed (and later restored) value is the sign-extended type-id byte the routine read for
    # itself at entry, not the tile index move.w d6,d2 leaves live during the routine's own body.
    type_byte = machine.peek_ram((definition + solids.SOLID_TYPE) & 0xFFFF, 1)[0]
    signed_type = type_byte - 0x100 if type_byte & 0x80 else type_byte
    d2 = (registers['d2'] & 0xFFFF0000) | (signed_type & 0xFFFF)

    x_skips, y_skips = result['x_skips'], result['y_skips']
    cycles = (_SD_HEAD[0] + _SD_LOOKUP[0] + mismatches * _SD_SCAN_MISMATCH[0] + _SD_SCAN_MATCH[0]
              + _SD_POST_MATCH[0] + _SD_TILE[0] + _SD_PRELOOP[0]
              + rows * (_SD_ROW_HEAD[0] + _SD_ROW_TAIL[0])
              + x_skips * _SD_X_SKIP[0] + y_skips * _SD_Y_SKIP[0] + visible * _SD_VISIBLE[0]
              + rows * cells * _SD_REJOIN[0]
              + rows * (cells - 1) * _SD_DBRA_TAKEN + rows * _SD_DBRA_LAST
              + (rows - 1) * _SD_DBRA_TAKEN + _SD_DBRA_LAST
              + _SD_TAIL[0])
    instructions = (_SD_HEAD[1] + _SD_LOOKUP[1] + mismatches * _SD_SCAN_MISMATCH[1] + _SD_SCAN_MATCH[1]
                    + _SD_POST_MATCH[1] + _SD_TILE[1] + _SD_PRELOOP[1]
                    + rows * (_SD_ROW_HEAD[1] + _SD_ROW_TAIL[1])
                    + x_skips * _SD_X_SKIP[1] + y_skips * _SD_Y_SKIP[1] + visible * _SD_VISIBLE[1]
                    + rows * cells * _SD_REJOIN[1]
                    + rows * (cells - 1) * 1 + rows * 1
                    + (rows - 1) * 1 + 1
                    + _SD_TAIL[1])
    # The transient per-cell frame (movem.l d0-d1,-(a7)) is popped every iteration but never
    # cleared: at RTS it still holds the last row's y and the last column's x, pre-POSITION_BIAS,
    # from whichever cell (visible or skipped) the loop reached last.
    cell_writes = (_bytes(sp - SOLID_DRAW_FRAME - SOLID_DRAW_CELL_FRAME,
                          (registers['d0'] & 0xFFFF0000) | result['last_col_x'], 4)
                   + _bytes(sp - SOLID_DRAW_FRAME - SOLID_DRAW_CELL_FRAME + 4,
                           (registers['d1'] & 0xFFFF0000) | result['last_row_y'], 4))
    writes = (_solid_frame_writes(sp, registers, d2) + cell_writes
              + tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size)))
    # The last flag-setting instruction is addi.w #$10,d1 (the final row's own height advance,
    # which runs even on the routine's last row); N/Z come from the unconditional final
    # move.l a0,LIST_HEAD, which does not touch X.
    exit_sr = (_logic_sr(sr, result['final_head'], 4) & ~0x10) | (_add_sr(sr, result['last_row_y'], solids.ROW_HEIGHT, 2) & 0x10)
    exit_registers = {name: registers[name] for name in ('d0', 'd1', 'd3', 'd4', 'd6', 'd7', 'a0', 'a1')}
    exit_registers.update(d2=d2, a7=(sp32 + 4) & 0xFFFFFFFF, pc=_return(machine, sp), sr=exit_sr)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                      last_pc=SOLID_DRAW_LAST_PC)


# --- 00FE08: the animation step (game/animation.py: animation_step) ----------
#
# Cost from the tracer (artifacts/gods/evidence/census-00FE08*): the 'idle'
# arm (a plain leaf, constant cost) and, since 16 Sep, the 'moving' arm's own
# head (up to and including the bsr into the walker resume WALKER_RESUME_ENTRY,
# below) and tail (the position store, the completion test on d7, and on
# completion the next-waypoint load and remaining-count test).  The call
# itself costs exactly WALKER_RESUME_ENTRY's own cost fragments
# (_WR_HEAD/_WR_STEP/_WR_TAIL), reused here the way 0049DA reuses 001164's
# own cost table -- 00FFF0 *is* this bsr's target, not a twin.
# 'moving-coldstart' (the walk completes with at most one waypoint left)
# falls into the per-object-type waypoint dispatch 00FEC0/00FF54: censused
# fresh over all eight recordings (16 Sep) and unwitnessed on every one, so
# it stays declined, along with a zero budget and a record whose stored
# continuation is not one of the walker's own four bodies.
ANIMATION_STEP_ENTRY = 0x00FE08
ANIMATION_STEP_IDLE_LAST_PC = 0x00FE5A
ANIMATION_STEP_CONTINUE_LAST_PC = 0x00FE5A
ANIMATION_STEP_COMPLETE_LAST_PC = 0x00FE54
ANIMATION_STEP_FRAME = 24                              # movem.l d0-d3/a1-a2,-(a7)
ANIMATION_STEP_CALL_FRAME = ANIMATION_STEP_FRAME + 4    # + the bsr 00FFF0 return address
ANIMATION_STEP_CALL_RETURN = 0x00FE26                   # the PC bsr.w 00FFF0 pushes and returns to
_AS_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'a1', 'a2')
ANIMATION_STEP_IDLE_COST = (194, 10)
_AS_MOVING_HEAD = (134, 9)      # 00FE08..00FE22: the frame, the budget refresh, tst.b/bmi not taken, bsr taken
_AS_POST_CALL = (88, 5)         # 00FE26..00FE32: d5=d6, the frame restore, the position store, tst.w d7
_AS_TAIL_CONTINUE = (26, 2)     # bpl taken; rts (00FE5A)
_AS_TAIL_COMPLETE = (118, 11)   # bpl not taken; the waypoint load, the remaining-count test, -1 store; rts (00FE54)
_AS_DECLINED_ARMS = {'moving-coldstart', 'moving-zero-budget', 'moving-unrecovered-record'}


def _animation_frame_writes(sp, registers):
    return tuple(pair for index, name in enumerate(_AS_FRAME_REGISTERS)
                 for pair in _bytes(sp - ANIMATION_STEP_FRAME + 4 * index, registers[name], 4))


def _animation_idle_plan(machine, registers, result, sp32, sp, sr, record):
    from .game import animation
    _spans_disjoint([('animation step frame', sp - ANIMATION_STEP_FRAME, ANIMATION_STEP_FRAME),
                     ('animation frame budget', animation.FRAME_BUDGET & 0xFFFFFF, 2)])
    moving_flag = machine.peek_ram((record + animation.LIVE_MOVING_FLAG) & 0xFFFF, 1)[0]
    # N/Z/V/C are tst.b $5(a1)'s own (the last flag-setter before the rts); X is the earlier
    # addq.w #1,d4's own carry (tst does not touch X, so it survives from there to the exit).
    exit_sr = (_logic_sr(sr, moving_flag, 1) & ~0x10) | (_add_sr(sr, result['budget_before'], 1, 2) & 0x10)
    d4 = (registers['d4'] & 0xFFFF0000) | result['budget']
    writes = (_animation_frame_writes(sp, registers)
              + tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size)))
    return AtomicPlan(cycles=ANIMATION_STEP_IDLE_COST[0], instructions=ANIMATION_STEP_IDLE_COST[1], writes=writes,
                      registers={'d4': d4, 'a3': (registers['a1'] + 6) & 0xFFFFFFFF,
                                 'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                      last_pc=ANIMATION_STEP_IDLE_LAST_PC)


def _animation_moving_plan(machine, registers, result, sp32, sp, sr, record):
    from .game import animation, walker
    arm = result['arm']
    walker_record = (record + animation.WALKER_RECORD_OFFSET) & 0xFFFFFF
    if (walker_record | (sp - ANIMATION_STEP_CALL_FRAME)) & 1:
        raise UnsupportedCandidate('unaligned walker record or call frame')
    _spans_disjoint([('animation step call frame', sp - ANIMATION_STEP_CALL_FRAME, ANIMATION_STEP_CALL_FRAME),
                     ('animation frame budget', animation.FRAME_BUDGET & 0xFFFFFF, 2),
                     ('animation record header', record, 6),
                     ('walker record', walker_record, walker.RECORD_SIZE)])
    walk, after = result['walk'], result['after']
    steps, counter_before_subq = _walk_steps(walk, result['budget'], 'object')
    call_cost = _add(_WR_HEAD, *(_WR_STEP[step] for step in steps), _WR_TAIL)
    high = lambda name: registers[name] & 0xFFFF0000
    loaded = lambda word: 0xFFFF0000 if word & 0x8000 else 0
    walker_record32 = (registers['a1'] + animation.WALKER_RECORD_OFFSET) & 0xFFFFFFFF
    # The walker's own residue, the same formulas WALKER_RESUME_ENTRY's own plan uses: d0/d4/d6 keep this
    # call's own upper word (never touched going in), d2/d3/d5/d7 are movem.w's own sign extension, a0/a3/a5
    # the walker's own.  d5 is the walker's own d5 (the error word's own sign extension) with its low word
    # replaced by d6's (00FE26: move.w d6,d5).  The frame restore (d0-d3/a1-a2) brings d0-d2 and a1/a2
    # straight back to their entry values, so only d3 (on 'moving-complete': the waypoint index), d4, d5,
    # d6, d7, a0, a3, a5 differ from entry.
    d4 = high('d4') | after.x
    d5 = loaded(walk.error) | after.y
    d6 = high('d6') | after.y
    d7 = loaded(walk.counter) | after.counter
    a0 = walker.OBJECT_BODIES[walk.phase]
    a5 = walker_record32
    a3 = (walker_record32 + 10) & 0xFFFFFFFF
    call_return_writes = (_animation_frame_writes(sp, registers)
                          + _bytes(sp - ANIMATION_STEP_CALL_FRAME, ANIMATION_STEP_CALL_RETURN, 4))
    stores_writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    writes = call_return_writes + stores_writes
    exit_registers = {'d4': d4, 'd5': d5, 'd6': d6, 'd7': d7, 'a0': a0, 'a3': a3, 'a5': a5,
                      'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp)}
    if arm == 'moving-continue':
        cost = _add(_AS_MOVING_HEAD, call_cost, _AS_POST_CALL, _AS_TAIL_CONTINUE)
        # tst.w d7 is the last flag-setter (N/Z from the final counter, V=C=0); X is the walker's own
        # residue (its final subq.w #1,d7's borrow), unaffected by every instruction since.
        x = 0x10 if counter_before_subq == 0 else 0
        nz = 0x08 if after.counter & 0x8000 else (0x04 if after.counter == 0 else 0)
        exit_registers['sr'] = (sr & ~0x1F) | x | nz
        return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers,
                          last_pc=ANIMATION_STEP_CONTINUE_LAST_PC)
    # 'moving-complete': the waypoint load and remaining-count test add their own fixed cost; d3 becomes
    # the waypoint index (the +5 byte re-read, sign-extended, minus one, times four -- two SUBQ/ADD pairs
    # that overwrite the walker's own X residue); the last flag-setter is move.b #$ff,$5(a1) (N=1,Z=0
    # always -- storing -1); X is the second ADD's own carry (doubling the post-SUBQ word).
    cost = _add(_AS_MOVING_HEAD, call_cost, _AS_POST_CALL, _AS_TAIL_COMPLETE)
    doubled_once = (((result['slot'] - 1) & 0xFFFF) * 2) & 0xFFFF
    x = 0x10 if doubled_once & 0x8000 else 0
    exit_registers['d3'] = high('d3') | (result['index'] & 0xFFFF)
    exit_registers['sr'] = (sr & ~0x1F) | x | 0x08
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers,
                      last_pc=ANIMATION_STEP_COMPLETE_LAST_PC)


def animation_step_plan(machine, registers):
    """00FE08: the frame-budget refresh, the idle return, and the 'moving' arm's own walker call plus
    its own tail; the walk-completes-with-no-waypoints-left arm ('moving-coldstart') is declined, along
    with a zero budget and a record whose continuation is not one of the walker's own bodies."""
    from .game import animation
    if registers['pc'] != ANIMATION_STEP_ENTRY:
        raise UnsupportedCandidate('animation step planner needs the machine parked at 00FE08')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    record, definition = registers['a1'] & 0xFFFFFF, registers['a2'] & 0xFFFFFF
    if (sp | record | definition) & 1:
        raise UnsupportedCandidate('unaligned stack, record or definition')
    result = animation.animation_step(_reader(machine), record, definition)
    arm = result['arm']
    if arm in _AS_DECLINED_ARMS:
        raise UnsupportedCandidate('animation step arm calls unrecovered 00FEC0/00FF54: ' + arm) \
            if arm == 'moving-coldstart' else UnsupportedCandidate('animation step arm not witnessed: ' + arm)
    if arm == 'idle':
        return _animation_idle_plan(machine, registers, result, sp32, sp, sr, record)
    return _animation_moving_plan(machine, registers, result, sp32, sp, sr, record)


# --- 010332: the rate-gated countdown check (game/timers.py: countdown_check) --
#
# Cost from the tracer (artifacts/gods/evidence/census-010332{,-7251bbd0ecf7,-f0ac19738f19,-f40d7bcc9dda}):
# 'idle'/'waiting' are the original two-instruction-tail leaf; a residue of
# zero reloads the countdown and the frequency word unconditionally, then
# either calls the unrecovered 0091BC pool ('trigger-deep', declined) or
# runs the near-identical 01158C/0115D4 window test and bounded pool scan
# ('trigger-reject': outside the screen window, no pool touch;
# 'trigger-spawn': inside it, a free slot found and filled).  The pool
# exhausted ('trigger-pool-full') is real ROM code -- the same bounded
# dbra shape as hazard.py's own pool -- but no recording exhausts it, so
# it is declined as unwitnessed.
COUNTDOWN_CHECK_ENTRY, COUNTDOWN_CHECK_LAST_PC = 0x010332, 0x010386
COUNTDOWN_CHECK_DEEP_LAST_PC = 0x0103C8          # the deep gate's own tail rts (past COUNTDOWN_CHECK_LAST_PC)
_CC_IDLE_COST = (38, 3)                # tst.b not zero-taken? no: tst.b; beq taken; rts
_CC_WAITING_COST = (62, 5)             # tst.b; beq not taken; subq.w; bne taken; rts
_CC_TRIGGER_HEAD = (12 + 8 + 16 + 8, 4)          # tst.b; beq not taken; subq.w; bne not taken (falls into trigger)
_CC_PUSH = (24, 1)                               # movem.l d0-d1,-(a7)
_CC_RELOAD = (4 + 12 + 4 + 4 + 4 + 12, 6)        # moveq; sub.b; ext.w; add.w; add.w; move.w -> store
_CC_DEEP_TEST, _CC_DEEP_NOT_TAKEN = (12, 1), (8, 1)   # tst.b $12(a3); bne not taken (proceeds)
_CC_FREQUENCY = (12 + 4 + 10 + 4 + 62 + 4 + 4, 7)     # move.b; ext.w; asr.w#2; addq.w#4; mulu.w; swap; addq.w#1
_CC_DIR_TEST = (12, 1)                           # tst.w $a(a5)
_CC_DIR_BACK, _CC_DIR_FWD = (8, 1), (10, 1)      # bne not taken (BACK) / taken (FORWARD)
_CC_NEG = (4, 1)                                 # BACK only: neg.w d3
_CC_STORE_AND_LOAD = (12 + 8 + 12, 3)            # move.w d3,f1c2.w; move.w (a5),d0; move.w 2(a5),d1
_CC_BIAS_BACK, _CC_BIAS_FWD = (4, 1), (8, 1)     # subq.w #8,d0 / addi.w #$20,d0
_CC_CALL = (18, 1)                               # bsr.w $1158c / $115d4
_CC_CALLEE_HEAD = (12 + 4 + 4 + 12 + 12, 5)      # move.l a0,-(a7); move.w d0,d2; move.w d1,d3; sub.w f3ee,d2; sub.w f3f0,d3
_CC_WINDOW_TEST, _CC_WINDOW_PASS, _CC_WINDOW_REJECT = (8, 1), (8, 1), (10, 1)   # cmpi.w; branch not taken / taken
_CC_POOL_SETUP = (8 + 4, 2)                      # lea.l $db74.w,a0; moveq #$13,d5
_CC_POOL_ITER = (12 + 10 + 4 + 10, 4)            # a slot occupied: tst.w; bpl TAKEN (skip); addq.w #8,a0; dbra taken
_CC_POOL_FOUND = (12 + 8, 2)                     # a free slot: tst.w; bpl NOT taken (falls into the stores)
_CC_POOL_STORE = (8 + 8 + 16 + 12, 4)            # move.w d0,(a0)+; move.w d1,(a0)+; move.w f1c2,(a0)+; the marker store
_CC_POOL_EXIT_BRA = (10, 1)                      # bra.b $115d0 (the found path's own; a reject already took its branch)
_CC_POP_A0, _CC_RTS_INNER = (12, 1), (16, 1)     # movea.l (a7)+,a0; rts (01158C/0115D4's own)
_CC_POP_D0D1, _CC_RTS_OUTER = (28, 1), (16, 1)   # movem.l (a7)+,d0-d1; rts (010332's own)
_CC_DEEP_TAKEN = (10, 1)                         # bne.b $103a0 taken (the deep gate itself)
_CC_DEEP_POSITION = (8 + 12 + 8, 3)              # move.w (a5),d0; move.w 2(a5),d1; addi.w #$10,d0
_CC_DEEP_BUDGET = (12 + 4 + 8 + 4, 4)            # move.b $13(a3),d4; ext.w; asr.w #1; addq.w #2
_CC_DEEP_FRAME = (120, 1)                        # movem.l d0-d7/a0-a5,-(a7)
_CC_DEEP_FLAG = (4, 1)                           # moveq #$1,d6
_CC_DEEP_CALL = (20, 1)                          # jsr $91bc.l
_CC_DEEP_RESTORE = (124, 1)                      # movem.l (a7)+,d0-d7/a0-a5
_CC_DEEP_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'a0', 'a1', 'a2', 'a3', 'a4', 'a5')
_CC_DEEP_INTERNAL_RETURN = 0x0103C0              # the jsr $91bc's own return address
_CC_DEEP_LAUNCH_RETURN = 0x0091F0                # 0091BC's own internal bsr $93e4's own return address


def _cc_deep_writes(sp, registers, x0, y0, budget_full, reload, launch):
    """The deep gate's own two nested frames (the outer d0-d1 push already accounted for by the caller),
    0091BC's own internal call return, and the launch's own durable stores.  D3 already holds the
    reload value by this point (the shared head's own moveq/sub.b/ext.w/add.w/add.w, common to every
    'trigger' arm); D4 holds the budget (a byte move only, so its own upper word survives from entry)."""
    inner_sp = sp - 8                                                    # below the outer d0-d1 frame
    frame_values = dict(registers)
    frame_values['d0'], frame_values['d1'], frame_values['d3'], frame_values['d4'] = x0, y0, reload, budget_full
    frame = tuple(pair for index, name in enumerate(_CC_DEEP_FRAME_REGISTERS)
                 for pair in _bytes(inner_sp - len(_CC_DEEP_FRAME_REGISTERS) * 4 + 4 * index, frame_values[name] & 0xFFFFFFFF, 4))
    call_sp = inner_sp - len(_CC_DEEP_FRAME_REGISTERS) * 4
    jsr_return = _bytes(call_sp - 4, _CC_DEEP_INTERNAL_RETURN, 4)
    launch_return = _bytes(call_sp - 8, _CC_DEEP_LAUNCH_RETURN, 4)
    stores_writes = tuple(pair for address, (value, size) in launch['stores'].items() for pair in _bytes(address, value, size))
    return frame + jsr_return + launch_return + stores_writes


def _cc_frame_writes(sp, registers):
    """movem.l d0-d1,-(a7): D0 at sp-8, D1 at sp-4 (ascending register order at ascending addresses)."""
    return _bytes((sp - 8) & 0xFFFFFF, registers['d0'] & 0xFFFFFFFF, 4) + \
           _bytes((sp - 4) & 0xFFFFFF, registers['d1'] & 0xFFFFFFFF, 4)


def _cc_call_writes(sp, resume_pc, a0_value):
    """The bsr's own return address, then the callee's own move.l a0,-(a7): both durable stack residue."""
    call_sp = sp - 8
    return _bytes((call_sp - 4) & 0xFFFFFF, resume_pc, 4) + _bytes((call_sp - 8) & 0xFFFFFF, a0_value & 0xFFFFFFFF, 4)


def _cc_window_cost_and_ccr(sr, result, variant):
    # BACK (01158C) tests the X lower bound before the upper; FORWARD (0115D4) tests the upper bound first --
    # the two routines are mirrors of each other in more than just the thresholds.
    from .game import timers
    x_lo, x_hi = variant['x_window']
    x_lo_stage = (result['screen_x'], x_lo & 0xFFFF, result['screen_x'] < x_lo)
    x_hi_stage = (result['screen_x'], x_hi & 0xFFFF, result['screen_x'] > x_hi)
    x_stages = (x_hi_stage, x_lo_stage) if variant is timers.FORWARD else (x_lo_stage, x_hi_stage)
    stages = ((result['screen_y'], 0xC0, result['screen_y'] >= 0xC0),
              (result['screen_y'], 0xFFFC, result['screen_y'] < -4)) + x_stages
    cycles, instructions = 0, 0
    for left, right, taken in stages:
        cycles, instructions = cycles + _CC_WINDOW_TEST[0], instructions + _CC_WINDOW_TEST[1]
        if taken:
            return cycles + _CC_WINDOW_REJECT[0], instructions + _CC_WINDOW_REJECT[1], _cmp_sr(sr, left, right, 2)
        cycles, instructions = cycles + _CC_WINDOW_PASS[0], instructions + _CC_WINDOW_PASS[1]
    return cycles, instructions, None


def _countdown_check_deep_plan(machine, registers, result, sp32, sp, sr):
    """The 'trigger-deep-launch' arm: the record's own position and a rate-derived budget straight into
    the already-recovered projectile launch, inside two nested save/restore frames that leave every
    register at its entry value -- only the launch's own RAM effects and CCR residue survive."""
    launch = result['launch']
    walk, after, budget = launch['walk'], launch['after'], launch['budget']
    steps, counter_before_subq = _walk_steps(walk, budget, 'projectile')
    toward, slope = walk.phase
    setup_cost = _add(_PL_OUTER[toward], _PL_XSETUP[toward], _PL_YSIGN[(toward, walk.y_sign == 0xFFFF)],
                      _PL_SLOPE_TEST[slope], _PL_PRELOOP)
    call_cost = _add(setup_cost, *(_WR_STEP[step] for step in steps), _WR_TAIL)
    launch_cost = _add(_PL_HEAD, *([_PL_SKIP] * launch['tries']), _PL_FOUND, _PL_STORE_AND_CALL, call_cost, _PL_TAIL)
    head_cost = (_CC_TRIGGER_HEAD[0] + _CC_PUSH[0] + _CC_RELOAD[0] + _CC_DEEP_TEST[0] + _CC_DEEP_TAKEN[0]
                + _CC_DEEP_POSITION[0] + _CC_DEEP_BUDGET[0] + _CC_DEEP_FRAME[0] + _CC_DEEP_FLAG[0] + _CC_DEEP_CALL[0],
                 _CC_TRIGGER_HEAD[1] + _CC_PUSH[1] + _CC_RELOAD[1] + _CC_DEEP_TEST[1] + _CC_DEEP_TAKEN[1]
                + _CC_DEEP_POSITION[1] + _CC_DEEP_BUDGET[1] + _CC_DEEP_FRAME[1] + _CC_DEEP_FLAG[1] + _CC_DEEP_CALL[1])
    cost = _add(head_cost, launch_cost, _CC_DEEP_RESTORE, _CC_POP_D0D1, _CC_RTS_OUTER)
    reload = result['reload']
    budget_full = (registers['d4'] & 0xFFFF0000) | budget      # move.b only: D4's own upper word survives from entry
    # walk.x/walk.y are the launch's own (x0, y0) argument, exactly what D0/D1 held at the inner frame's
    # own push (before any step ran); D2/D5/D6/D7/A0-A2/A4 in that frame are this activation's own entry
    # value, untouched by anything before the push; D3 already holds the reload (the shared head's own
    # moveq #$10,d3 resets the whole register, so no upper word survives); the outer D0-D1 frame (pushed
    # before either was touched) restores those two to their true entry values on the way out.
    reload_writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    writes = reload_writes + _cc_frame_writes(sp, registers) + _cc_deep_writes(sp, registers, walk.x, walk.y, budget_full, reload, launch)
    # Only D3 (the reload) and D4 (the budget) differ from entry once both frames unwind; movem/rts never
    # touch flags, so the exit CCR is exactly what 0091BC's own tail leaves: N=Z=V=C=0
    # (move.w #1,$f386.w), X its residue.
    x = 0x10 if counter_before_subq == 0 else 0
    exit_registers = {'d3': reload, 'd4': budget_full, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                      'pc': _return(machine, sp), 'sr': (sr & ~0x1F) | x}
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers,
                      last_pc=COUNTDOWN_CHECK_DEEP_LAST_PC)


def countdown_check_plan(machine, registers):
    """010332: the countdown reload/reset, the direction-mirrored screen window test and pool fill."""
    from .game import timers
    if registers['pc'] != COUNTDOWN_CHECK_ENTRY:
        raise UnsupportedCandidate('countdown check planner needs the machine parked at 010332')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    control, countdown = registers['a3'] & 0xFFFFFF, registers['a5'] & 0xFFFFFF
    result = timers.countdown_check(_reader(machine), control, countdown)
    arm = result['arm']
    if arm == 'trigger-deep-pool-full':
        raise UnsupportedCandidate('countdown check trigger-deep arm: projectile pool exhausted, not witnessed')
    if arm == 'trigger-pool-full':
        raise UnsupportedCandidate('countdown check trigger arm: spawn pool exhausted, not witnessed')
    if arm == 'idle':
        # The control byte itself is the last (and only) flag-setter: tst.b $13(a3).
        control_byte = machine.peek_ram((control + timers.RATE_ENABLE) & 0xFFFF, 1)[0]
        exit_sr = _logic_sr(sr, control_byte, 1)
        return AtomicPlan(cycles=_CC_IDLE_COST[0], instructions=_CC_IDLE_COST[1], writes=(),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=COUNTDOWN_CHECK_LAST_PC)
    if arm == 'waiting':
        # The last flag-setter is subq.w #1,$c(a5), which also sets X (unlike a plain CMP).
        exit_sr = _sub_sr(sr, result['before'], 1, 2)
        writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
        return AtomicPlan(cycles=_CC_WAITING_COST[0], instructions=_CC_WAITING_COST[1], writes=writes,
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=COUNTDOWN_CHECK_LAST_PC)
    if arm == 'trigger-deep-launch':
        return _countdown_check_deep_plan(machine, registers, result, sp32, sp, sr)
    # 'trigger-reject' or 'trigger-spawn': both run the full head, the window test, and (spawn only) the pool scan.
    variant = result['variant']
    back = variant is timers.BACK
    cycles, instructions = _CC_TRIGGER_HEAD[0] + _CC_PUSH[0] + _CC_RELOAD[0] + _CC_DEEP_TEST[0] + _CC_DEEP_NOT_TAKEN[0], \
                            _CC_TRIGGER_HEAD[1] + _CC_PUSH[1] + _CC_RELOAD[1] + _CC_DEEP_TEST[1] + _CC_DEEP_NOT_TAKEN[1]
    cycles, instructions = cycles + _CC_FREQUENCY[0] + _CC_DIR_TEST[0], instructions + _CC_FREQUENCY[1] + _CC_DIR_TEST[1]
    dir_step = _CC_DIR_BACK if back else _CC_DIR_FWD
    cycles, instructions = cycles + dir_step[0], instructions + dir_step[1]
    if back:
        cycles, instructions = cycles + _CC_NEG[0], instructions + _CC_NEG[1]
    cycles, instructions = cycles + _CC_STORE_AND_LOAD[0], instructions + _CC_STORE_AND_LOAD[1]
    bias = _CC_BIAS_BACK if back else _CC_BIAS_FWD
    cycles, instructions = cycles + bias[0], instructions + bias[1]
    cycles, instructions = cycles + _CC_CALL[0] + _CC_CALLEE_HEAD[0], instructions + _CC_CALL[1] + _CC_CALLEE_HEAD[1]
    # sub.w $f3f0.w,d3 (the Y subtraction, the callee's own last instruction before the window test) is a SUB: it
    # sets X (unlike the CMPs that follow, which retain it), and nothing after this point ever sets X again.
    camera_y = int.from_bytes(machine.peek_ram(timers.CAMERA_Y & 0xFFFF, 2), 'big')
    sr_x = _sub_sr(sr, result['pos_y'], camera_y, 2)
    window_cycles, window_instructions, reject_ccr = _cc_window_cost_and_ccr(sr_x, result, variant)
    cycles, instructions = cycles + window_cycles, instructions + window_instructions
    if arm == 'trigger-spawn':
        cycles, instructions = cycles + _CC_POOL_SETUP[0], instructions + _CC_POOL_SETUP[1]
        cycles, instructions = cycles + result['tries'] * _CC_POOL_ITER[0], instructions + result['tries'] * _CC_POOL_ITER[1]
        cycles, instructions = cycles + _CC_POOL_FOUND[0] + _CC_POOL_STORE[0] + _CC_POOL_EXIT_BRA[0], \
                                instructions + _CC_POOL_FOUND[1] + _CC_POOL_STORE[1] + _CC_POOL_EXIT_BRA[1]
        # move.w #marker,(a0)+ (or clr.w) is the pool store's own last flag-setter: N/Z/V=0/C=0 from the marker.
        exit_ccr = _logic_sr(sr_x, variant['marker'], 2)
    else:
        exit_ccr = reject_ccr
    cycles, instructions = cycles + _CC_POP_A0[0] + _CC_RTS_INNER[0], instructions + _CC_POP_A0[1] + _CC_RTS_INNER[1]
    cycles, instructions = cycles + _CC_POP_D0D1[0] + _CC_RTS_OUTER[0], instructions + _CC_POP_D0D1[1] + _CC_RTS_OUTER[1]
    d2 = (registers['d2'] & 0xFFFF0000) | (result['screen_x'] & 0xFFFF)
    d3 = ((result['frequency_upper'] & 0xFFFF) << 16) | (result['screen_y'] & 0xFFFF)
    exit_registers = {'d0': registers['d0'], 'd1': registers['d1'], 'd2': d2, 'd3': d3,
                       'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_ccr}
    if arm == 'trigger-spawn':
        exit_registers['d5'] = (0x13 - result['tries']) & 0xFFFFFFFF
    writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    writes += _cc_frame_writes(sp, registers) + _cc_call_writes(sp, variant['resume'], registers['a0'])
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                      last_pc=variant['resume'] + 4)


# --- 010A14: the collision gate (game/movement.py: collision_gate) -----------
#
# Cost from the tracer (artifacts/gods/evidence/census-010A14{,-f0ac19738f19}):
# every arm shares a head and a tail; 'held' and 'gated' need only the head
# and the tail.  A residue of zero calls 010CBC (game/grid.py:
# grid_cell_at, a straight-line 9-instruction body, 84cy) and runs a bounded
# near/mid/far grid test in the direction 'moving' selects: a match on near
# or mid, or a miss on far, ends in 'collision-clear' (the moving-state word
# toggled); a match on far alone reaches a further gate byte in A3 -- zero
# on every witnessed occurrence ('collision-held', the tail runs untouched)
# -- or, unwitnessed, an unbounded grid search this module does not model
# ('collision-deep', declined).  The phase>7 arm ('over') is real ROM code,
# but no recording on either history that reaches this entry takes it.
COLLISION_GATE_ENTRY, COLLISION_GATE_LAST_PC = 0x010A14, 0x010AAC
_CG_HEAD_TAKEN, _CG_HEAD_NOT_TAKEN = (50, 5), (48, 5)      # ble taken (phase<=7) vs not (phase>7, declined)
_CG_FLAG_TAKEN, _CG_FLAG_NOT_TAKEN = (22, 2), (20, 2)      # tst.w GLOBAL_GATE; bne
_CG_ADVANCE_TAKEN, _CG_ADVANCE_NOT_TAKEN = (46, 5), (44, 5)  # addq/andi/move/tst(a5+0xA)/bne
_CG_DIR_TAKEN, _CG_DIR_NOT_TAKEN = (26, 4), (24, 4)        # addq-or-subq #4,d0; move; andi; bne
_CG_TAIL_TAKEN, _CG_TAIL_NOT_TAKEN = (64, 5), (70, 6)      # asl/add/tst/bne[/ori]/rts
_CG_CALL = (18 + 84, 1 + 9)                                # bsr.w $10cbc (18cy) + 010CBC's own body (84cy, 9 instr)
_CG_NEAR_TEST = _CG_MID_TEST = _CG_FAR_TEST = (16, 1)      # cmpi.b #1,(offset)(a0)
_CG_NEAR_TAKEN = _CG_MID_TAKEN = (10, 1)                   # beq.b taken -> collision-clear
_CG_NEAR_NOT_TAKEN = _CG_MID_NOT_TAKEN = (8, 1)            # beq.b not taken
_CG_FAR_TAKEN_BACK, _CG_FAR_NOT_TAKEN_BACK = (10, 1), (12, 1)          # moving==0: beq.w $10afc taken / not
_CG_FAR_TAKEN_FWD = (8 + 10, 1 + 1)                        # moving!=0: bne.b not taken (8) + bra.b taken (10)
_CG_FAR_NOT_TAKEN_FWD = (10, 1)                            # moving!=0: bne.b taken -> straight to eori
_CG_EORI, _CG_EORI_BRA = (20, 1), (10, 1)                  # eori.w #1,$a(a5); bra.b $10a9c
_CG_DEEP_GATE_TEST, _CG_DEEP_GATE_CLEAR = (12, 1), (10, 1)  # tst.b $12(a3); beq.b taken (gate zero) -> tail
# bsr.w $10cbc's own return address, pushed at (entry a7 - 4) and popped by 010CBC's rts: the four bytes
# are durable stack residue (net a7 unchanged, but nothing else overwrites them before this activation's own rts).
_CG_COLLISION_RETURN_BACK, _CG_COLLISION_RETURN_FWD = 0x010A52, 0x010A82


def _collision_test_cost(result, moving):
    """The near/mid/far grid test's own cost and which shared tail it reaches ('clear' or 'deep')."""
    cycles, instructions = _CG_CALL
    cycles, instructions = cycles + _CG_NEAR_TEST[0], instructions + _CG_NEAR_TEST[1]
    if result['near'] == 1:
        return cycles + _CG_NEAR_TAKEN[0], instructions + _CG_NEAR_TAKEN[1], 'clear'
    cycles, instructions = cycles + _CG_NEAR_NOT_TAKEN[0], instructions + _CG_NEAR_NOT_TAKEN[1]
    cycles, instructions = cycles + _CG_MID_TEST[0], instructions + _CG_MID_TEST[1]
    if result['mid'] == 1:
        return cycles + _CG_MID_TAKEN[0], instructions + _CG_MID_TAKEN[1], 'clear'
    cycles, instructions = cycles + _CG_MID_NOT_TAKEN[0], instructions + _CG_MID_NOT_TAKEN[1]
    cycles, instructions = cycles + _CG_FAR_TEST[0], instructions + _CG_FAR_TEST[1]
    far_taken = _CG_FAR_TAKEN_FWD if moving != 0 else _CG_FAR_TAKEN_BACK
    far_not_taken = _CG_FAR_NOT_TAKEN_FWD if moving != 0 else _CG_FAR_NOT_TAKEN_BACK
    if result['far'] == 1:
        return cycles + far_taken[0], instructions + far_taken[1], 'deep'
    return cycles + far_not_taken[0], instructions + far_not_taken[1], 'clear'


def collision_gate_plan(machine, registers):
    """010A14: phase advance, +-4 residue gate and (residue zero) the near/mid/far grid test."""
    from .game import movement
    if registers['pc'] != COLLISION_GATE_ENTRY:
        raise UnsupportedCandidate('collision gate planner needs the machine parked at 010A14')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    state = registers['a5'] & 0xFFFFFF
    a3 = registers['a3'] & 0xFFFFFF
    result = movement.collision_gate(_reader(machine), state, a3, registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF)
    arm = result['arm']
    if arm == 'over':
        raise UnsupportedCandidate('collision gate phase>7 arm not witnessed by a recording')
    if arm == 'collision-deep':
        raise UnsupportedCandidate('collision gate deep arm (A3 gate nonzero) not witnessed by a recording')
    cycles, instructions = _CG_HEAD_TAKEN
    if arm == 'held':
        cycles, instructions = cycles + _CG_FLAG_TAKEN[0], instructions + _CG_FLAG_TAKEN[1]
    else:
        cycles, instructions = cycles + _CG_FLAG_NOT_TAKEN[0], instructions + _CG_FLAG_NOT_TAKEN[1]
        moving = machine.peek_ram((state + movement.MOVING_STATE) & 0xFFFF, 2)
        moving = int.from_bytes(moving, 'big')
        advance = _CG_ADVANCE_TAKEN if moving != 0 else _CG_ADVANCE_NOT_TAKEN
        cycles, instructions = cycles + advance[0], instructions + advance[1]
        gated = _CG_DIR_TAKEN if arm == 'gated' else _CG_DIR_NOT_TAKEN
        cycles, instructions = cycles + gated[0], instructions + gated[1]
        if arm in ('collision-clear', 'collision-held'):
            test_cycles, test_instructions, outcome = _collision_test_cost(result, moving)
            cycles, instructions = cycles + test_cycles, instructions + test_instructions
            if outcome == 'clear':
                cycles, instructions = cycles + _CG_EORI[0] + _CG_EORI_BRA[0], instructions + _CG_EORI[1] + _CG_EORI_BRA[1]
            else:
                cycles, instructions = cycles + _CG_DEEP_GATE_TEST[0], instructions + _CG_DEEP_GATE_TEST[1]
                cycles, instructions = cycles + _CG_DEEP_GATE_CLEAR[0], instructions + _CG_DEEP_GATE_CLEAR[1]
    if 'moving_after' in result:
        moving_now = result['moving_after']
    else:
        moving_now = machine.peek_ram((state + movement.MOVING_STATE) & 0xFFFF, 2)
        moving_now = int.from_bytes(moving_now, 'big')
    tail = _CG_TAIL_TAKEN if moving_now != 0 else _CG_TAIL_NOT_TAKEN
    cycles, instructions = cycles + tail[0], instructions + tail[1]
    tail_d2_before_add = (result['tail_d2'] << 4) & 0xFFFF
    final_d2 = (tail_d2_before_add + movement.TAIL_BASE_VALUE) & 0xFFFF
    if moving_now == 0:
        final_d2 |= movement.RESULT_TAG
    x_bit = _add_sr(sr, tail_d2_before_add, movement.TAIL_BASE_VALUE, 2) & 0x10
    exit_sr = (_logic_sr(sr, moving_now if moving_now != 0 else final_d2, 2) & ~0x10) | x_bit
    d0 = (registers['d0'] & 0xFFFF0000) | result['d0']
    d2 = (registers['d2'] & 0xFFFF0000) | final_d2
    exit_registers = {'d0': d0, 'd2': d2, 'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr}
    if arm == 'gated':
        # d3 = d0 & 0x1F survives (no frame restores it): the residue that gated this arm.
        exit_registers['d3'] = (registers['d3'] & 0xFFFF0000) | (result['d0'] & movement.RESIDUE_MASK)
    elif arm in ('collision-clear', 'collision-held'):
        # 010CBC's own results survive to the RTS: A0 the grid address, D3 the column, D4 the row.
        cell = result['cell']
        exit_registers['a0'] = cell['address'] & 0xFFFFFFFF
        exit_registers['d3'] = (registers['d3'] & 0xFFFF0000) | cell['column']
        exit_registers['d4'] = (registers['d4'] & 0xFFFF0000) | cell['row']
    writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    if arm in ('collision-clear', 'collision-held'):
        return_pc = _CG_COLLISION_RETURN_FWD if moving != 0 else _CG_COLLISION_RETURN_BACK
        writes += _bytes((sp32 - 4) & 0xFFFFFF, return_pc, 4)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                      last_pc=COLLISION_GATE_LAST_PC)


# --- 00BCCE: the zone check (game/zones.py: zone_check) ----------------------
#
# Cost from the tracer (artifacts/gods/evidence/census-00BCCE-fresh): every
# arm shares a head, an 8-register save/restore frame the routine never
# writes back through (the whole box arithmetic is scratch), and up to
# four sequential box tests.  Fully witnessed: no declines.  (The stale
# pre-staged census-00BCCE directory showed calls to 0F4472, but those were
# an interrupt landing mid-activation misattributed to the region's own
# signature by an older tracer; re-censused, every occurrence is RAM-only.)
ZONE_CHECK_ENTRY, ZONE_CHECK_HELD_LAST_PC, ZONE_CHECK_INSIDE_LAST_PC = 0x00BCCE, 0x00BD30, 0x00BD50
ZONE_CHECK_FRAME = 32                                  # movem.l d0-d7,-(a7)
_ZC_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7')
_ZC_HELD_COST = (38, 3)                                # tst.w; bmi.w taken; rts
_ZC_HEAD = (12 + 12, 2)                                # tst.w; bmi.w not taken (word branch: 12cy not taken, not 8)
_ZC_PUSH = (72, 1)                                     # movem.l d0-d7,-(a7)
_ZC_CAMERA_SETUP = (52, 8)
_ZC_LEVEL_NARROW_LOW = (16 + 10, 2)                    # cmpi; blt taken
_ZC_LEVEL_NARROW_HIGH = (16 + 8 + 16 + 10, 4)          # cmpi; blt not taken; cmpi; bgt taken
_ZC_LEVEL_WIDE = (16 + 8 + 16 + 8 + 8, 5)              # cmpi; blt nt; cmpi; bgt nt; addi
_ZC_HALF = (12 + 8 + 4 + 4 + 4, 5)                     # move; asr; add; sub; add (HALF_X and HALF_Y alike)
_ZC_BCC_TAKEN = (4 + 10, 2)                            # cmp; Bcc taken -- a failing test 1-3, or test 4's success
_ZC_BCC_NOT_TAKEN = (4 + 8, 2)                         # cmp; Bcc not taken -- a passing test 1-3, or test 4's failure
_ZC_TAIL_OUTSIDE = (76 + 16, 2)                        # movem pop; rts
_ZC_INSIDE_HEAD = (4 + 4 + 16 + 4 + 12, 5)             # move; addq; asr; addq; tst.w SUPPRESS_COOLDOWN
_ZC_SUPPRESS_TAKEN = (10, 1)                           # bne taken: no cooldown decrement
_ZC_SUPPRESS_NOT_TAKEN = (8 + 16, 2)                   # bne not taken: sub.w
_ZC_INSIDE_POP = (76, 1)
_ZC_RESULT_TST = (12, 1)
_ZC_RESULT_TAKEN = (10, 1)                             # bne taken: d2 unchanged
_ZC_RESULT_NOT_TAKEN = (8 + 4, 2)                      # bne not taken: moveq #-1,d2
_ZC_RTS = (16, 1)


def _zone_frame_writes(sp, registers):
    return tuple(pair for index, name in enumerate(_ZC_FRAME_REGISTERS)
                 for pair in _bytes(sp - ZONE_CHECK_FRAME + 4 * index, registers[name], 4))


def _zone_check_cost(machine, result):
    """00BCCE's own (cycles, instructions) for one call -- shared with a caller (00BA8E) composing the call."""
    from .game import zones
    if result['arm'] == 'held':
        return _ZC_HELD_COST
    cycles, instructions = _ZC_HEAD[0] + _ZC_PUSH[0] + _ZC_CAMERA_SETUP[0], _ZC_HEAD[1] + _ZC_PUSH[1] + _ZC_CAMERA_SETUP[1]
    # The level shape (narrow-low / narrow-high / wide) only needs the level number itself.
    level_value = machine.peek_ram(zones.LEVEL_NUMBER & 0xFFFF, 2)
    level_value = zones._signed_word(int.from_bytes(level_value, 'big'))
    if level_value < zones.WIDE_LEVEL_LOW:
        level_cost = _ZC_LEVEL_NARROW_LOW
    elif level_value > zones.WIDE_LEVEL_HIGH:
        level_cost = _ZC_LEVEL_NARROW_HIGH
    else:
        level_cost = _ZC_LEVEL_WIDE
    cycles, instructions = cycles + level_cost[0], instructions + level_cost[1]
    cycles, instructions = cycles + 2 * _ZC_HALF[0], instructions + 2 * _ZC_HALF[1]
    order = ('x_near', 'x_far', 'y_near', 'y_far')
    fail = result['fail']
    fail_index = order.index(fail) if fail else 4
    for index in range(min(fail_index, 3)):
        # Tests 1-3 passing (not taken) to get this far.
        cycles, instructions = cycles + _ZC_BCC_NOT_TAKEN[0], instructions + _ZC_BCC_NOT_TAKEN[1]
    if fail_index < 3:
        cycles, instructions = cycles + _ZC_BCC_TAKEN[0], instructions + _ZC_BCC_TAKEN[1]     # tests 1-3: taken = fail
    elif fail_index == 3:
        cycles, instructions = cycles + _ZC_BCC_NOT_TAKEN[0], instructions + _ZC_BCC_NOT_TAKEN[1]  # test 4: not taken = fail
    else:
        cycles, instructions = cycles + _ZC_BCC_TAKEN[0], instructions + _ZC_BCC_TAKEN[1]      # test 4: taken = success
    if result['arm'] == 'outside':
        cycles, instructions = cycles + _ZC_TAIL_OUTSIDE[0], instructions + _ZC_TAIL_OUTSIDE[1]
        return cycles, instructions
    # 'inside'
    cycles, instructions = cycles + _ZC_INSIDE_HEAD[0], instructions + _ZC_INSIDE_HEAD[1]
    if result['suppressed']:
        cycles, instructions = cycles + _ZC_SUPPRESS_TAKEN[0], instructions + _ZC_SUPPRESS_TAKEN[1]
    else:
        cycles, instructions = cycles + _ZC_SUPPRESS_NOT_TAKEN[0], instructions + _ZC_SUPPRESS_NOT_TAKEN[1]
    cycles, instructions = (cycles + _ZC_INSIDE_POP[0] + _ZC_RESULT_TST[0],
                            instructions + _ZC_INSIDE_POP[1] + _ZC_RESULT_TST[1])
    if result['result_flag'] != 0:
        cycles, instructions = cycles + _ZC_RESULT_TAKEN[0], instructions + _ZC_RESULT_TAKEN[1]
    else:
        cycles, instructions = cycles + _ZC_RESULT_NOT_TAKEN[0], instructions + _ZC_RESULT_NOT_TAKEN[1]
    cycles, instructions = cycles + _ZC_RTS[0], instructions + _ZC_RTS[1]
    return cycles, instructions


def _zone_check_exit_x(sr, result):
    """00BCCE's own exit X bit for the 'inside' arm -- shared with a caller composing the call, since
    nothing in the caller's own code between the call and its next flag-setter touches X either."""
    if result['suppressed']:
        return _add_sr(sr, result['shifted'], 5, 2) & 0x10
    return _sub_sr(sr, result['cooldown_before'], result['scale'], 2) & 0x10


def zone_check_plan(machine, registers):
    """00BCCE: the box test over the player's own position; every witnessed arm is admitted."""
    from .game import zones
    if registers['pc'] != ZONE_CHECK_ENTRY:
        raise UnsupportedCandidate('zone check planner needs the machine parked at 00BCCE')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    result = zones.zone_check(_reader(machine), registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF,
                              registers['d2'] & 0xFFFF)
    arm = result['arm']
    if arm == 'held':
        hold_flag = machine.peek_ram(zones.HOLD_FLAG & 0xFFFF, 2)
        exit_sr = _logic_sr(sr, int.from_bytes(hold_flag, 'big'), 2)
        cycles, instructions = _zone_check_cost(machine, result)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=(),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=ZONE_CHECK_HELD_LAST_PC)
    frame = ('zone check frame', sp - ZONE_CHECK_FRAME, ZONE_CHECK_FRAME)
    _spans_disjoint([frame, ('zone check cooldown', zones.COOLDOWN & 0xFFFFFF, 2)])
    cycles, instructions = _zone_check_cost(machine, result)
    x_left, x_right = result['x_operands']
    x_bit = _add_sr(sr, x_left, x_right, 2) & 0x10
    if arm == 'outside':
        left, right = result['test_operands']
        exit_sr = (_cmp_sr(sr, left, right, 2) & ~0x10) | x_bit
        writes = _zone_frame_writes(sp, registers)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes,
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=ZONE_CHECK_HELD_LAST_PC)
    # 'inside'
    x_bit = _zone_check_exit_x(sr, result)
    result_flag = result['result_flag']
    exit_registers = {'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp)}
    if result_flag != 0:
        exit_sr = (_logic_sr(sr, result_flag, 2) & ~0x10) | x_bit
    else:
        exit_registers['d2'] = 0xFFFFFFFF
        exit_sr = (0x08 & ~0x10) | x_bit          # moveq #$ff,d2: N=1, Z=V=C=0
    exit_registers['sr'] = exit_sr
    writes = (_zone_frame_writes(sp, registers)
              + tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size)))
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                      last_pc=ZONE_CHECK_INSIDE_LAST_PC)


# --- 00126A: the particle drawer's own emitter (game/sprites.py: emit_particle_sprite) ---
#
# Cost from the tracer (artifacts/gods/evidence/census-00126A-fresh): no
# cache, so every on-screen call is a seam (Aladdin recipe 2/3, the same
# shape as 0018C8's own cache-miss upload).  The ceded block's own length
# (the data-loop trip count) varies with the descriptor's tile size, but
# that cost is the machine's own -- charged for real, never modeled here.
PARTICLE_EMIT_ENTRY, PARTICLE_EMIT_UPLOAD = 0x00126A, 0x0012F4
PARTICLE_EMIT_RESUME, PARTICLE_EMIT_LAST_PC = 0x00130C, 0x001310
PARTICLE_EMIT_PREFIX_LAST_PC = 0x0012EE          # ori.l #$40000000,d0: the last instruction before the VDP control write
PARTICLE_EMIT_FRAME = 28                          # movem.l d0-d4/a0-a1,-(a7)
_PARTICLE_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'd4', 'a0', 'a1')
_PE_HEAD = (64 + 8 + 12 + 12 + 4 + 12 + 8 + 8, 8)      # movem push; move#4000,d4; sub x2; move d2,d3; lea; andi; adda
_PE_X_TEST_PASS, _PE_X_TEST_FAIL = (4 + 4 + 8 + 12, 4), (4 + 4 + 8 + 10, 4)      # moveq;add;cmpi;bhi.w
_PE_Y_TEST_PASS, _PE_Y_TEST_FAIL = (4 + 4 + 8 + 12, 4), (4 + 4 + 8 + 10, 4)
_PE_RECORD_NOFLIP = (12 + 8 + 10, 3)                   # move $6(a0),d2; andi #$8000,d3; beq taken
_PE_RECORD_FLIP = (12 + 8 + 8 + 8 + 12, 5)             # beq not taken; move #$800,d3; move $8(a0),d2
_PE_RECORD_BODY = (4 + 4 + 12 + 16 + 16 + 8 + 12 + 12 + 8 + 12 + 16 + 4 + 8 + 8 + 16 + 16, 16)
_PE_UPLOAD_SETUP = (4 + 12 + 12 + 10 + 4 + 16, 6)      # moveq#0,d0; move ee84->d0; rol.l#2; lsr.w#2; swap; ori.l
_PE_RESTORE = (68 + 16, 2)                             # movem.l (a7)+; rts


def _particle_frame_writes(sp, registers):
    return tuple(pair for index, name in enumerate(_PARTICLE_FRAME_REGISTERS)
                 for pair in _bytes(sp - PARTICLE_EMIT_FRAME + 4 * index, registers[name], 4))


def particle_emit_plan(machine, registers):
    """00126A: an off-screen particle as one plan; an on-screen one as a ``Seam`` (no cache, always a miss)."""
    from .game import sprites
    if registers['pc'] != PARTICLE_EMIT_ENTRY:
        raise UnsupportedCandidate('particle emit planner needs the machine parked at 00126A')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    frame = ('particle frame', sp - PARTICLE_EMIT_FRAME, PARTICLE_EMIT_FRAME + 4)
    _ram_span(*frame)
    result = sprites.emit_particle_sprite(_reader(machine), registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF,
                                          registers['d2'] & 0xFFFF)
    arm = result['arm']
    writes = _particle_frame_writes(sp, registers)
    if arm == 'offscreen-x':
        cost = (_PE_HEAD[0] + _PE_X_TEST_FAIL[0] + _PE_RESTORE[0], _PE_HEAD[1] + _PE_X_TEST_FAIL[1] + _PE_RESTORE[1])
        # The margin add (moveq #$20,d2; add.w d0,d2) is the last X-setter; the cmpi does not touch X.
        x_bit = _add_sr(sr, result['screen'][0], sprites.SCREEN_MARGIN, 2) & 0x10
        exit_sr = (_cmp_sr(sr, (result['screen'][0] + sprites.SCREEN_MARGIN) & 0xFFFF, sprites.SCREEN_X_LIMIT, 2)
                   & ~0x10) | x_bit
        return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes,
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=PARTICLE_EMIT_LAST_PC)
    if arm == 'offscreen-y':
        cost = (_PE_HEAD[0] + _PE_X_TEST_PASS[0] + _PE_Y_TEST_FAIL[0] + _PE_RESTORE[0],
                _PE_HEAD[1] + _PE_X_TEST_PASS[1] + _PE_Y_TEST_FAIL[1] + _PE_RESTORE[1])
        # The Y test's own margin add is the last X-setter (it runs after the X test's own).
        x_bit = _add_sr(sr, result['screen'][1], sprites.SCREEN_MARGIN, 2) & 0x10
        exit_sr = (_cmp_sr(sr, (result['screen'][1] + sprites.SCREEN_MARGIN) & 0xFFFF, sprites.SCREEN_Y_LIMIT, 2)
                   & ~0x10) | x_bit
        return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes,
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=PARTICLE_EMIT_LAST_PC)
    # 'upload': the prefix ends at the VDP control write with the upload's registers in place.
    # The descriptor lives in ROM (066794-relative), read-only and out of the RAM aliasing check.
    record = result['record']
    spans = [frame, ('particle record', record, sprites.RECORD_SIZE), *_SPRITE_GLOBALS]
    _spans_disjoint(spans)
    record_flip = _PE_RECORD_FLIP if result['flip'] else _PE_RECORD_NOFLIP
    cycles = (_PE_HEAD[0] + _PE_X_TEST_PASS[0] + _PE_Y_TEST_PASS[0] + record_flip[0]
              + _PE_RECORD_BODY[0] + _PE_UPLOAD_SETUP[0])
    instructions = (_PE_HEAD[1] + _PE_X_TEST_PASS[1] + _PE_Y_TEST_PASS[1] + record_flip[1]
                    + _PE_RECORD_BODY[1] + _PE_UPLOAD_SETUP[1])
    writes = writes + tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    upload = result['upload']
    stores = result['stores']
    high = lambda name: registers[name] & 0xFFFF0000
    attribute = (sprites.FLIP_ATTRIBUTE if result['flip'] else 0) | sprites.PARTICLE_PRIORITY_ATTRIBUTE
    # The ceded block (0012F4-001308) reads only D0 (the VDP command) and A0 (the descriptor,
    # to fetch the tile pointer at its own +0); the strict witness still checks every register
    # the prefix's own path (0012BA-0012EE) actually changes, dead to the ceded block or not.
    # D1-D3 are the record's own words (already computed for the stores); D4 never moves past
    # its entry move.w #$4000; A0 stays the descriptor; A1 ends at the advanced list head.
    # rol.l #2 always clears bits 0-1 of the low word (a left shift by 2), and lsr.w #2 then
    # shifts those same two zero bits into the carry/X position last: X is always 0 here.
    prefix = AtomicPlan(
        cycles=cycles, instructions=instructions, writes=writes,
        registers={'d0': upload['command'], 'd1': high('d1') | stores[record + 4][0],
                   # D2's upper word is gone by here: moveq #$20,d2 (the X and Y screen tests, both taken
                   # before any record work) sign-extends the whole 32-bit register, and nothing after
                   # that touches more than D2's low word.
                   'd2': stores[record + 2][0], 'd3': high('d3') | attribute,
                   'd4': high('d4') | 0x4000, 'a0': result['descriptor'], 'a1': stores[sprites.LIST_HEAD][0],
                   'a7': (sp32 - PARTICLE_EMIT_FRAME) & 0xFFFFFFFF,
                   'pc': PARTICLE_EMIT_UPLOAD,
                   'sr': _logic_sr(sr, upload['command'], 4) & ~0x10},
        last_pc=PARTICLE_EMIT_PREFIX_LAST_PC)
    return Seam(prefix=prefix, resume_pc=PARTICLE_EMIT_RESUME,
                stack_basis=(sp32 - PARTICLE_EMIT_FRAME) & 0xFFFFFFFF,
                guards=((sp - PARTICLE_EMIT_FRAME, PARTICLE_EMIT_FRAME + 4),), suffix=particle_emit_suffix)


def particle_emit_suffix(machine, registers):
    """00130C after the upload: the frame back into the registers, the RTS; the CCR is the machine's."""
    if registers['pc'] != PARTICLE_EMIT_RESUME:
        raise UnsupportedCandidate('particle emit suffix needs the machine parked at 00130C')
    base = registers['a7']
    restored = {name: int.from_bytes(machine.peek_ram((base + 4 * index) & 0xFFFF, 4), 'big')
                for index, name in enumerate(_PARTICLE_FRAME_REGISTERS)}
    sp = (base + PARTICLE_EMIT_FRAME) & 0xFFFFFFFF
    restored.update(a7=(sp + 4) & 0xFFFFFFFF, pc=_return(machine, sp))
    return AtomicPlan(cycles=_PE_RESTORE[0], instructions=_PE_RESTORE[1], writes=(), registers=restored,
                      last_pc=PARTICLE_EMIT_LAST_PC)


# --- 014084: the hazard tick (game/hazard.py: hazard_tick) -------------------
#
# Cost from the tracer (artifacts/gods/evidence/census-014084-fresh): no
# frame at all (D4/D5/A0/A1/A2 are live scratch, never saved).  The
# 'trigger' arm (rare: 8 of 26,293 occurrences on the longest recording)
# calls an unrecovered routine and is declined; 'paint' and 'spawn' (found
# or the pool exhausted) are admitted.
HAZARD_TICK_ENTRY = 0x014084
HAZARD_TICK_PAINT_WRITE_LAST_PC, HAZARD_TICK_PAINT_SKIP_LAST_PC = 0x01415C, 0x01414A
HAZARD_TICK_SPAWN_LAST_PC = 0x014106
_HZ_HEAD_ACTIVE, _HZ_HEAD_INACTIVE = (12 + 12, 2), (12 + 10, 2)          # tst.b; beq.w not taken / taken
_HZ_GRID_SETUP = (4 + 4 + 4 + 12 + 12 + 4 + 4 + 8 + 16 + 12 + 8 + 8 + 8, 13)
_HZ_GRID_MISMATCH, _HZ_GRID_MATCH = (12 + 10, 2), (12 + 12, 2)           # cmpi.b; bne.w taken / not taken
_HZ_SOUND_WRITE = (16, 1)
_HZ_TYPE_MISMATCH, _HZ_TYPE_MATCH = (16 + 10, 2), (16 + 8, 2)            # cmpi.b d(a1); bne.b taken / not taken
_HZ_COUNTER_LOW, _HZ_COUNTER_HIGH = (16 + 10, 2), (16 + 8, 2)            # cmpi.w abs; blt.b taken(skip) / not taken(trigger)
_HZ_POOL_SETUP = (12 + 4, 2)                                             # lea; moveq #$13,d4
_HZ_POOL_ITER = (8 + 8 + 8 + 10, 4)                                      # tst.w; bmi not taken; lea $c(a1),a1; dbra taken
_HZ_POOL_EXHAUSTED_TAIL = (8 + 8 + 8 + 14 + 10, 5)                       # ... dbra not taken; bra.b $14104
_HZ_POOL_FOUND = (8 + 10, 2)                                             # tst.w; bmi taken
_HZ_FILL = (12 + 4 + 4 + 12 + 12 + 8 + 8 + 20 + 12 + 16, 10)
_HZ_TAIL_SPAWN = (12 + 16, 2)                                            # clr.w (a3); rts
_HZ_TILE_SETUP = (8 + 8 + 4 + 4 + 12 + 8 + 8 + 4 + 8 + 4 + 8, 11)
_HZ_BOUNDS_LOW_FAIL, _HZ_BOUNDS_LOW_PASS = (6 + 10, 2), (6 + 8, 2)       # cmpa.l; blt.b taken / not taken
_HZ_BOUNDS_HIGH_FAIL = (8 + 6 + 10, 3)                                   # lea; cmpa.l; bge.b taken
_HZ_BOUNDS_HIGH_PASS = (8 + 6 + 8, 3)                                    # lea; cmpa.l; bge.b not taken
_HZ_PAINT_HEAD_ODD, _HZ_PAINT_HEAD_EVEN = (12 + 4 + 8 + 10, 4), (12 + 4 + 8 + 8, 4)  # move.b; move.w; andi; bne
_HZ_PAINT_WRITE_ODD = (12 * 4, 4)          # move.b d5,$30(a0)/$60(a0)/$31(a0)/$61(a0): all displaced
_HZ_PAINT_WRITE_EVEN = (8 + 12 + 12 + 12, 4)   # move.b d5,(a0) is bare -- 8cy, not 12
_HZ_RTS = (16, 1)
_HZ_JSR_PROXIMITY = (20, 1)              # jsr $f828.l (00F828's own cost added separately, via _proximity_resolve)


def hazard_tick_plan(machine, registers):
    """014084: the grid-gated pool spawn (including its own call into the already-recovered proximity
    table, 00F828) or the tile-array paint; only the type-match-but-counter-low gate, a proximity
    search selector outside 0/1/2, and the proximity table's own pool-full arm still decline as
    'trigger', unwitnessed by any recording."""
    from .game import hazard
    if registers['pc'] != HAZARD_TICK_ENTRY:
        raise UnsupportedCandidate('hazard tick planner needs the machine parked at 014084')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    a1, a3 = registers['a1'] & 0xFFFFFF, registers['a3'] & 0xFFFFFF
    d0, d1 = registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF
    read = _reader(machine)
    active = read(a1 + hazard.ACTIVE_FLAG, 1) != 0
    result = hazard.hazard_tick(read, a1, a3, d0, d1)
    arm = result['arm']
    if arm == 'trigger':
        raise UnsupportedCandidate(f"hazard tick trigger arm {result.get('reason', 'unwitnessed')}")
    high = lambda name: registers[name] & 0xFFFF0000
    if arm == 'spawn':
        _spans_disjoint([('hazard pool entry', hazard.POOL_BASE & 0xFFFFFF, hazard.POOL_STRIDE * hazard.POOL_COUNT),
                         ('hazard pending flag', a3, 2)])
        proximity = result.get('proximity')
        proximity_writes = ()
        proximity_a0 = proximity_d6 = None
        if proximity is None:
            # A type mismatch (the parallel table byte isn't TRIGGER_TYPE): 00F828 is never called,
            # regardless of the trigger counter (the ROM's own bne skips both the counter test and
            # the call at once).
            cycles = (_HZ_HEAD_ACTIVE[0] + _HZ_GRID_SETUP[0] + _HZ_GRID_MATCH[0] + _HZ_SOUND_WRITE[0]
                      + _HZ_TYPE_MISMATCH[0] + _HZ_POOL_SETUP[0])
            instructions = (_HZ_HEAD_ACTIVE[1] + _HZ_GRID_SETUP[1] + _HZ_GRID_MATCH[1] + _HZ_SOUND_WRITE[1]
                            + _HZ_TYPE_MISMATCH[1] + _HZ_POOL_SETUP[1])
        else:
            # A type match with the trigger counter already at 2: 0140CC's own jsr into the
            # already-recovered proximity table (game.hazard.proximity_search/add/trigger), landing
            # back here (0140D2) either way -- the SAME shared pool fill runs next regardless of
            # which of 00F828's own outcomes this call reached.
            cycles = (_HZ_HEAD_ACTIVE[0] + _HZ_GRID_SETUP[0] + _HZ_GRID_MATCH[0] + _HZ_SOUND_WRITE[0]
                      + _HZ_TYPE_MATCH[0] + _HZ_COUNTER_HIGH[0] + _HZ_JSR_PROXIMITY[0])
            instructions = (_HZ_HEAD_ACTIVE[1] + _HZ_GRID_SETUP[1] + _HZ_GRID_MATCH[1] + _HZ_SOUND_WRITE[1]
                            + _HZ_TYPE_MATCH[1] + _HZ_COUNTER_HIGH[1] + _HZ_JSR_PROXIMITY[1])
            cell, _row = hazard._cell_address(read, d0, d1)
            c, i, prox_writes, prox_kind, prox_search, prox_resolved = _proximity_resolve(
                read, (sp - 4) & 0xFFFFFF, cell, registers['a1'] & 0xFFFFFFFF)
            cycles += c
            instructions += i
            # 0140CC's own return address, pushed by the jsr itself, one level above 00F828's own
            # internal frame (_proximity_resolve's own writes are relative to THAT, sp-4 here).
            proximity_writes = list(_bytes((sp - 4) & 0xFFFFFF, 0x0140D2, 4)) + prox_writes
            # 00F828/00F86A's own exit leaves A0 at the table entry it last touched (the matched
            # entry's own address for 'trigger', the newly-added free slot's own +4 for 'added') --
            # neither this routine's own tail (0140D2 onward: A1, not A0) nor the jsr itself touches
            # A0 again, so it survives all the way to hazard_tick's own exit.
            if prox_kind == 'trigger':
                proximity_a0 = (hazard.PROXIMITY_TABLE + hazard.PROXIMITY_STRIDE * prox_search['index']) & 0xFFFFFFFF
                # moveq #$27,d6 (00F888, unconditional) then one dbra per examined-but-mismatched
                # position before the match ends the search early -- never reaches 0xFFFF here.
                proximity_d6 = (0x27 - (len(prox_search['positions']) - 1)) & 0xFFFF
            else:
                proximity_a0 = (hazard.PROXIMITY_TABLE
                                + hazard.PROXIMITY_STRIDE * prox_resolved['index'] + 4) & 0xFFFFFFFF
                # The 'not-found' search always runs all 40 iterations (dbra expires): d6 = -1.
                proximity_d6 = 0xFFFF
            cycles += _HZ_POOL_SETUP[0]
            instructions += _HZ_POOL_SETUP[1]
        y_pre_addq = (d1 + read(hazard.OBJECT_Y, 2)) & 0xFFFF
        if result['slot'] is not None:
            tries = (result['slot'] - hazard.POOL_BASE) // hazard.POOL_STRIDE
            cycles += tries * _HZ_POOL_ITER[0] + _HZ_POOL_FOUND[0] + _HZ_FILL[0] + _HZ_TAIL_SPAWN[0]
            instructions += tries * _HZ_POOL_ITER[1] + _HZ_POOL_FOUND[1] + _HZ_FILL[1] + _HZ_TAIL_SPAWN[1]
            x_bit = _add_sr(sr, result['counter_before'], 1, 2) & 0x10
        else:
            cycles += (hazard.POOL_COUNT - 1) * _HZ_POOL_ITER[0] + _HZ_POOL_EXHAUSTED_TAIL[0] + _HZ_TAIL_SPAWN[0]
            instructions += (hazard.POOL_COUNT - 1) * _HZ_POOL_ITER[1] + _HZ_POOL_EXHAUSTED_TAIL[1] + _HZ_TAIL_SPAWN[1]
            x_bit = _add_sr(sr, y_pre_addq, 8, 2) & 0x10
        exit_sr = (0x04 & ~0x10) | x_bit          # clr.w (a3) is the last flag-setter: N=0,Z=1,V=C=0 always
        # D4's upper word is gone here regardless of arm: moveq #$13,d4 (the pool loop's own
        # counter) clears it, and nothing after ever restores the caller's own upper half.  D5's own
        # upper half survives from entry UNLESS the proximity call ran first: 00F86A's own move.l
        # d4,d5 sets the WHOLE register from the grid-cell key (always upper 0 by construction, the
        # same reason search['offset']'s upper half is always 0), wiping any caller upper half.
        d5_high = 0 if proximity is not None else high('d5')
        exit_registers = {'d4': result['d4'], 'd5': d5_high | result['d5'],
                          'a1': result['a1'], 'a2': registers['a1'],
                          'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr}
        if proximity_a0 is not None:
            exit_registers['a0'] = proximity_a0
            # moveq #$27,d6 sign-extends the whole register: no entry-value preservation, the same
            # rule the standalone 00F828 gate's own exit already applies.
            exit_registers['d6'] = proximity_d6
        writes = tuple(proximity_writes) + tuple(
            pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                          last_pc=HAZARD_TICK_SPAWN_LAST_PC)
    # 'paint': reached whether inactive, or active with a grid mismatch.
    head = _HZ_HEAD_ACTIVE if active else _HZ_HEAD_INACTIVE
    cycles, instructions = head[0] + _HZ_TILE_SETUP[0], head[1] + _HZ_TILE_SETUP[1]
    if active:
        cycles += _HZ_GRID_SETUP[0] + _HZ_GRID_MISMATCH[0]
        instructions += _HZ_GRID_SETUP[1] + _HZ_GRID_MISMATCH[1]
    x_bit = _add_sr(sr, result['doubled1'], result['doubled1'], 2) & 0x10   # the tile-setup's own second doubling
    # movea.l a1,a2 only runs on the active path (0x01408C); when inactive, A2 is never touched.
    exit_registers = {'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp)}
    if active:
        exit_registers['a2'] = registers['a1']
    if not result['painted']:
        # Which bound failed determines the CMPA operands (and hence N/Z/V/C) and the cost.
        if result['a0'] < hazard.TILE_LOW:
            cycles += _HZ_BOUNDS_LOW_FAIL[0] + _HZ_RTS[0]
            instructions += _HZ_BOUNDS_LOW_FAIL[1] + _HZ_RTS[1]
            exit_sr = (_cmp_sr(sr, result['a0'], hazard.TILE_LOW, 4) & ~0x10) | x_bit
            last_pc = HAZARD_TICK_PAINT_SKIP_LAST_PC
        else:
            cycles += _HZ_BOUNDS_LOW_PASS[0] + _HZ_BOUNDS_HIGH_FAIL[0] + _HZ_RTS[0]
            instructions += _HZ_BOUNDS_LOW_PASS[1] + _HZ_BOUNDS_HIGH_FAIL[1] + _HZ_RTS[1]
            exit_sr = (_cmp_sr(sr, result['a0'], hazard.TILE_HIGH, 4) & ~0x10) | x_bit
            last_pc = HAZARD_TICK_PAINT_SKIP_LAST_PC
        exit_registers.update(a0=result['a0'], a1=hazard.TILE_LOW if result['a0'] < hazard.TILE_LOW else hazard.TILE_HIGH,
                              d4=high('d4') | result['x_shift'], d5=high('d5') | result['doubled2'], sr=exit_sr)
        writes = ()
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                          last_pc=last_pc)
    cycles += _HZ_BOUNDS_LOW_PASS[0] + _HZ_BOUNDS_HIGH_PASS[0]
    instructions += _HZ_BOUNDS_LOW_PASS[1] + _HZ_BOUNDS_HIGH_PASS[1]
    paint_head = _HZ_PAINT_HEAD_ODD if result['d4'] else _HZ_PAINT_HEAD_EVEN
    paint_write = _HZ_PAINT_WRITE_ODD if result['d4'] else _HZ_PAINT_WRITE_EVEN
    cycles += paint_head[0] + paint_write[0] + _HZ_RTS[0]
    instructions += paint_head[1] + paint_write[1] + _HZ_RTS[1]
    # The last flag-setter is the fourth move.b (a positive, nonzero byte unless the value itself is
    # zero): N/Z/V/C from that byte; X is still the tile-setup's own second doubling.
    exit_sr = (_logic_sr(sr, result['value'], 1) & ~0x10) | x_bit
    exit_registers.update(a0=result['a0'], a1=hazard.TILE_HIGH, d4=high('d4') | result['d4'],
                          d5=(high('d5') | (result['doubled2'] & 0xFF00) | result['value']) & 0xFFFFFFFF, sr=exit_sr)
    writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    # D1&4 not only picks the four offsets but also which of the two RTS instructions falls
    # through to: the not-taken (even) tail shares 01414A with the bounds-skip exit above.
    last_pc = HAZARD_TICK_PAINT_WRITE_LAST_PC if result['d4'] else HAZARD_TICK_PAINT_SKIP_LAST_PC
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                      last_pc=last_pc)



# --- 00470C: the trigger conditions (game/conditions.py) -----------------------
#
# The first Gods dispatcher: the head selects a predicate by kind (D5)
# through the ROM table at 004718, each predicate is a small RAM-only leaf.
# One gate, one planner, the kinds as arms; a kind or a compare position
# no recording entered is declined.  Cost from the tracer
# (artifacts/gods/evidence/census-00470C-*): the head (move.w d5,d0; add;
# add; movea.l (pc,d0); jmp (a5)) is 38 cycles / 5 instructions, rts 16 / 1.
CONDITION_ENTRY = 0x00470C
_CD_HEAD = (38, 5)
_CD_RTS = (16, 1)
_CD_CLEAR = (12, 1)                    # clr.w (a3)
_CD_COMPARE_NEXT = (20, 2)             # cmp.w abs.w,d6; branch not taken
_CD_COMPARE_LAST = (22, 2)             # cmp.w abs.w,d6; branch taken
_CD_STATUS = (42, 6)                   # move; subq; add; add; lea.l; tst.w (a4,d0.w)
_CD_PROGRESS = (12, 1)                 # cmp.w abs.w,d6
_CD_ELAPSED = (16 + 166 + 4 + 4 + 4 + 4 + 4, 7)   # move.l; divs.w abs.w (the engine's fixed cost); move; add; add; add; cmp
_CD_FLAGGED = (12 + 4 + 8 + 4 + 8 + 16, 6)        # lea.l; add; adda; add; adda; btst.b #0,d16(a4)
_CD_BRANCH_TAKEN, _CD_BRANCH_NOT = (10, 1), (8, 1)
# Witnessed arms: (kind, 'match', position) / (kind, 'none', None) for the membership kinds, (kind, holds) for
# the rest.  Everything else is declined.
CONDITION_WITNESSED = {
    (1, 'match', 0), (1, 'match', 1), (1, 'match', 2), (1, 'match', 3), (1, 'none', None),
    (2, 'match', 0), (2, 'match', 3), (2, 'none', None),
    (3, 'match', 0), (3, 'match', 1), (3, 'none', None),
    (5, True), (5, False), (6, True), (6, False), (7, True), (7, False), (8, True), (8, False),
    (9, True), (9, False), (10, True), (10, False), (11, True), (11, False), (12, True), (12, False),
    (15, True), (15, False), (16, True), (16, False)}
_CONDITION_LAST_PCS = {0: 0x00475C, 1: 0x004B12, 2: 0x004B2E, 3: 0x004B44, 4: 0x004B5A, 5: 0x004B72, 6: 0x004B8A,
                       7: 0x004B94, 8: 0x004B9E, 9: 0x004BB6, 10: 0x004BCE, 11: 0x004BE8, 12: 0x004C02,
                       15: 0x004C0C, 16: 0x004C16}


def _add(*costs):
    return sum(c[0] for c in costs), sum(c[1] for c in costs)


def _condition_call(read, sr, d0_in, kind, argument, slot):
    """The exact effects of one call into 00470C (head dispatch through rts): cost, stores, the register
    residue the predicate itself leaves (not A7/PC -- a caller's own bsr/rts, or an internal one a
    composing region owns, pops those) and the exit SR.  Shared by ``condition_plan`` (the machine
    parked at 00470C) and a composing region that calls 00470C internally, the way ``spawn_queue_plan``
    reuses ``_static_emit_cost`` for its own calls into 001164.  Raises ``UnsupportedCandidate`` for an
    unrecovered kind or an unwitnessed compare position/arm -- identically for either caller.
    """
    from .game import conditions
    result = conditions.evaluate(read, kind, argument, slot)
    arm = result['arm']
    if arm == 'unrecovered':
        raise UnsupportedCandidate(f'condition kind {kind} not recovered')
    # The dispatcher's residue: D0 = 4 * kind (word, the upper half kept), A5 = the predicate's address;
    # add.w d0,d0 is the last flag-setter when the predicate sets none (kind 0).
    doubled = (2 * kind) & 0xFFFF
    extra = {'d0': (d0_in & 0xFFFF0000) | ((4 * kind) & 0xFFFF), 'a5': result['handler']}
    head_sr = _add_sr(sr, doubled, doubled, 2)
    cost = _add(_CD_HEAD, _CD_RTS)
    holds = arm == 'true'
    if kind == 0:
        exit_sr = head_sr
    elif kind in (1, 2, 3, 4):
        addresses = conditions.MARKERS if kind in (1, 2) else conditions.TRACKED
        matched = result['matched']
        key = (kind, 'match', matched) if matched is not None else (kind, 'none', None)
        if key not in CONDITION_WITNESSED:
            raise UnsupportedCandidate(f'condition kind {kind} compare position not witnessed by a recording')
        compared = matched + 1 if matched is not None else len(addresses)
        exit_sr = _cmp_sr(head_sr, argument, read(addresses[compared - 1], 2), 2)
        # Every compare but the decisive one falls through; the decisive one branches (over the clear for
        # any-equal, to the clear for none-equal) unless it is the last compare of a none-equal chain,
        # whose bne falls into the clear on a match and branches past it otherwise.
        final = compared == len(addresses)
        if kind in (1, 3):
            decisive = _CD_COMPARE_LAST if matched is not None else _CD_COMPARE_NEXT
        else:
            decisive = _CD_COMPARE_LAST if (matched is None if final else matched is not None) else _CD_COMPARE_NEXT
        cost = _add(cost, *([_CD_COMPARE_NEXT] * (compared - 1)), decisive)
    elif kind in (5, 6):
        entry = result['entry']
        exit_sr = _logic_sr(head_sr, read(entry & 0xFFFFFF, 2), 2)
        extra.update(d0=(d0_in & 0xFFFF0000) | (((argument - 1) & 0xFFFF) * 4 & 0xFFFF),
                     a4=conditions.STATUS_WORDS)   # the index rides in the addressing mode, a4 is the base
        cost = _add(cost, _CD_STATUS, _CD_BRANCH_TAKEN if holds else _CD_BRANCH_NOT)
    elif kind in (7, 8, 15, 16):
        word = read(conditions.PROGRESS_A if kind in (7, 8) else conditions.PROGRESS_B, 2)
        exit_sr = _cmp_sr(head_sr, argument, word, 2)
        cost = _add(cost, _CD_PROGRESS, _CD_BRANCH_TAKEN if holds else _CD_BRANCH_NOT)
    elif kind in (9, 10):
        quotient, scaled = result['quotient'] & 0xFFFF, result['scaled']
        # divs leaves the remainder in the upper word; the adds then the cmp set the flags (X from the last add).
        d0 = ((result['remainder'] & 0xFFFF) << 16) | quotient
        add_sr = _add_sr(head_sr, (4 * argument) & 0xFFFF, argument, 2)
        exit_sr = _cmp_sr(add_sr, scaled, quotient, 2)
        extra.update(d0=d0, d1=argument, d6=scaled)     # 9/10 overwrite d0 fully; d1/d6 keep their own upper half in the caller
        cost = _add(cost, _CD_ELAPSED, _CD_BRANCH_TAKEN if holds else _CD_BRANCH_NOT)
    else:                                                             # 11, 12
        entry, quadrupled = result['entry'], result['scaled']
        flag = read((entry + conditions.FLAGGED_FLAG_BYTE) & 0xFFFFFF, 1) & 1
        add_sr = _add_sr(head_sr, (2 * argument) & 0xFFFF, (2 * argument) & 0xFFFF, 2)
        exit_sr = (add_sr & ~0x04) | (0x00 if flag else 0x04)        # btst: Z only
        extra.update(d6=quadrupled, a4=entry)            # d6 keeps its own upper half in the caller
        cost = _add(cost, _CD_FLAGGED, _CD_BRANCH_TAKEN if holds else _CD_BRANCH_NOT)
    if kind not in (0, 1, 2, 3, 4) and (kind, holds) not in CONDITION_WITNESSED:
        raise UnsupportedCandidate(f'condition kind {kind} arm not witnessed by a recording')
    if arm == 'false':
        exit_sr = _logic_sr(exit_sr, 0, 2)                            # clr.w (a3): Z set, N/V/C clear, X kept
        cost = _add(cost, _CD_CLEAR)
    extra['sr'] = exit_sr
    return {'cost': cost, 'extra': extra, 'stores': result['stores'], 'holds': holds,
           'last_pc': _CONDITION_LAST_PCS[kind]}


def condition_plan(machine, registers):
    """00470C: one trigger predicate by kind; unwitnessed kinds and compare positions are declined."""
    if registers['pc'] != CONDITION_ENTRY:
        raise UnsupportedCandidate('condition planner needs the machine parked at 00470C')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    kind, argument, slot = registers['d5'] & 0xFFFF, registers['d6'] & 0xFFFF, registers['a3']
    if (sp | slot) & 1:
        raise UnsupportedCandidate('unaligned stack or result slot')
    _spans_disjoint([('condition frame', sp, 4), ('condition slot', slot & 0xFFFFFF, 2)])
    effects = _condition_call(_reader(machine), sr, registers['d0'], kind, argument, slot)
    extra = effects['extra']
    if 'd1' in extra:
        extra['d1'] = (registers['d1'] & 0xFFFF0000) | (extra['d1'] & 0xFFFF)
    if 'd6' in extra:
        extra['d6'] = (registers['d6'] & 0xFFFF0000) | (extra['d6'] & 0xFFFF)
    exit_registers = {**extra, 'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp)}
    writes = tuple(pair for address, (value, size) in effects['stores'].items() for pair in _bytes(address, value, size))
    return AtomicPlan(cycles=effects['cost'][0], instructions=effects['cost'][1], writes=writes,
                      registers=exit_registers, last_pc=effects['last_pc'])


# --- 00364C: the score conversion (game/score.py) -------------------------
#
# Called from the score-update sites (0035B2, 003604) and, unwitnessed, from
# the trigger conditions' score kinds through 004C4E's tail jump. Cost from
# the tracer (artifacts/gods/evidence/census-00364C*): the per-digit head
# (divs.w #$a,d6; move.l d6,d7; swap d7) is constant, the internal call chain
# (abcd/clr.w through to d3, then the movem/flag/addq/rts tail) depends only
# on which of d0..d3 the digit enters at.  Only 1-3 digit values (0-999) are
# witnessed; a fourth division is real ROM code no recording enters.
SCORE_CONVERT_ENTRY = 0x00364C
SCORE_CONVERT_LAST_PC = 0x0036C4                # the outer rts once the quotient is zero
_SC_INITIAL_LOAD = (28, 1)                      # movem.w (a0)+,d0-d3: once, at the very start
_SC_HEAD = (162 + 4 + 4, 3)                     # divs.w #$a,d6; move.l d6,d7; swap d7
_SC_SHIFT = (14, 1)                             # lsl.w #4,d7: the pair's second (odd) digit only
_SC_BSR = (18, 1)                               # bsr.b to the internal chain
# abcd.b/clr.w from the entry register through d3, plus the chain's own
# common tail (movem.w d0-d3,-(a0); move.w #$1,$f1ce.w; addq.w #$8,a0; rts).
_SC_TAIL = (24 + 16 + 4 + 16, 4)
_SC_CHAIN = {0: (6 + 4 + 6 + 4 + 6 + 4 + 6, 7), 1: (6 + 4 + 6 + 4 + 6, 5), 2: (6 + 4 + 6, 3), 3: (6, 1)}
_SC_EXT = (4, 1)                                # ext.l d6
_SC_BEQ_TAKEN, _SC_BEQ_NOT = (10, 1), (8, 1)     # beq.b $36c4
_SC_FLAG_WORD = 0xFFF1CE                        # move.w #$1,$f1ce.w: every internal call, unconditional
# The internal bsr's own return address (right after the bsr in the ROM, one per digit slot); only the
# LAST slot's push survives in final RAM -- each later slot's internal bsr overwrites the same stack slot.
_SC_RETURN_PC = {0: 0x00365A, 1: 0x00366A, 2: 0x003678, 3: 0x003688,
                 4: 0x003696, 5: 0x0036A6, 6: 0x0036B4, 7: 0x0036C4}


def _sign_extend_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def score_convert_plan(machine, registers):
    """00364C: the score digit conversion, admitted for the witnessed 1-3 digit (0-999) values only."""
    from .game import score
    if registers['pc'] != SCORE_CONVERT_ENTRY:
        raise UnsupportedCandidate('score convert planner needs the machine parked at 00364C')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    base32 = registers['a0'] & 0xFFFFFFFF
    base = base32 & 0xFFFFFF
    _ram_span('score convert buffer', base, 2 * score.WORD_COUNT)
    value = registers['d6'] & 0xFFFFFFFF
    if value & 0x80000000:
        raise UnsupportedCandidate('score convert value is negative: not witnessed')
    read = _reader(machine)
    result = score.convert_score(read, value, base, bool(sr & 0x10))
    if result['digits'] is None:
        raise UnsupportedCandidate('score convert value needs an unwitnessed digit count (0-999 only)')
    digits = result['digits']
    cycles, instructions = _SC_INITIAL_LOAD
    for slot in range(digits):
        register, shifted = slot // 2, slot % 2 == 1
        for part in (_SC_HEAD, _SC_SHIFT if shifted else (0, 0), _SC_BSR, _SC_CHAIN[register], _SC_TAIL, _SC_EXT,
                     _SC_BEQ_TAKEN if slot == digits - 1 else _SC_BEQ_NOT):
            cycles += part[0]
            instructions += part[1]
    cycles += 16                                    # the outer rts (0036C4)
    instructions += 1
    exit_registers = {'d6': 0, 'd7': 0, 'a0': (base32 + 2 * score.WORD_COUNT) & 0xFFFFFFFF,
                      'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp),
                      'sr': (sr & ~0x1F) | 0x04 | (0x10 if result['x'] else 0)}
    for index, name in enumerate(('d0', 'd1', 'd2', 'd3')):
        upper = _sign_extend_word(result['original'][index]) & 0xFFFFFF00 & 0xFFFFFFFF
        exit_registers[name] = (upper | (result['words'][index] & 0xFF)) & 0xFFFFFFFF
    # The digit stores are ordered last: they are the routine's durable, later-read effect (the packed
    # score display, and what the trigger conditions' score kinds will compare), unlike the flag word
    # and the internal bsr's own dead stack scratch above -- _mutate_result flips the last write.
    writes = list(_bytes(_SC_FLAG_WORD, 0x0001, 2))                        # every internal call: move.w #$1,$f1ce.w
    writes.extend(_bytes((sp - 4) & 0xFFFFFF, _SC_RETURN_PC[digits - 1], 4))  # the last internal bsr's push
    writes.extend(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(writes), registers=exit_registers,
                      last_pc=SCORE_CONVERT_LAST_PC)


# --- 00462C: the trigger evaluator (game/triggers.py) -----------------------
#
# A composition of three internal calls into the already-recovered 00470C,
# the shape 0049DA's calls into 001164 proved: the boundary owns the whole
# call, 00470C is not a separate gate at this call site.  Only the
# non-firing arm is admitted; the firing arm (004688 onward: the message,
# the per-action dispatch table) is a second dispatcher, left for the
# supervisor.  The disabled arm (FFEF38 nonzero, no calls at all) is real
# ROM code no recording has ever entered: declined too.  Cost from the
# tracer (artifacts/gods/evidence/census-00462C*): the head through the
# first pair's own setup, the per-call bsr overhead, the two between-call
# setups, the AND tail and the outer rts.
EVALUATOR_ENTRY, EVALUATOR_LAST_PC = 0x00462C, 0x004688
_TE_HEAD = (12 + 8 + 4 + 12 + 8 + 44 + 6 + 24 + 16 + 8 + 12 + 8, 12)
# tst.w EF38; bne.b (not taken); movea.l a0,a2; move.w 2(a0),d0; lea.l TRIGGER_TABLE,a1; muls.w #$18,d0;
# adda.l d0,a1; move.l #-1,SLOT_BASE; move.w #-1,SLOT_BASE+4; move.w (a1),d5; move.w 2(a1),d6; lea.l SLOT_BASE,a3
_TE_BSR = (18, 1)                       # bsr.w $470c
_TE_SETUP = (12 + 12 + 4, 3)            # move.w n(a1),d5; move.w n+2(a1),d6; addq.w #2,a3 -- between calls only
_TE_TAIL = (12 + 12 + 12 + 8, 4)        # move.w SLOT_BASE,d0; and.w +2,d0; and.w +4,d0; bmi.b (not taken)
_TE_OUTER_RTS = (16, 1)
_TE_RETURN_PC = (0x00465E, 0x00466C, 0x00467A)   # the internal bsr's own return address, one per pair


def _evaluator_resolve(read, sr, a0, entry_d1, entry_d5, entry_d6, entry_a4, entry_a5):
    """00462C's own non-firing arm, from the disabled-flag test through the AND tail, shared by
    ``evaluator_plan`` (parked directly at 00462C, ``a0`` its own caller-supplied status-table address)
    and ``player_tail_plan``'s own composed raise (0075D6's tile scan, ``a0`` the STATUS_WORDS entry
    ``event_status`` already read the status word from -- the SAME convention: 00462C's own head reads
    ``2(a0)`` as the trigger-record index either way).  Raises ``UnsupportedCandidate`` for the disabled
    arm (unwitnessed), an unrecovered condition kind, or the firing arm (all three conditions hold --
    left for the supervisor, docs/gods/blockers/2026-09-16-00462C-firing.md).  Returns the cost, every
    RAM store (the two preset slot writes, then whichever the three condition calls clear -- NOT the
    caller-specific return-address residue, added by each caller separately), the register residue
    (d0/d1/d5/d6/a1/a2/a3/a4/a5) and the exit SR chained from ``sr``.  ``entry_d1``/``entry_d5``/
    ``entry_d6``/``entry_a4``/``entry_a5`` are the caller's own values at the point 00462C is entered --
    only their UPPER halves (d1/d5/d6) or their whole value when no condition call ever touches them
    (a4; a5 is always set, by every pair's own dispatch) survive into the result.
    """
    from .game import triggers
    disable_flag = read(triggers.DISABLE_FLAG & 0xFFFFFF, 2)
    if disable_flag & 0xFFFF:
        raise UnsupportedCandidate('trigger evaluator disabled arm not witnessed by a recording')
    index = read((a0 + 2) & 0xFFFFFF, 2)
    result = triggers.evaluate_record(read, index, disable_flag)
    if result['arm'] == 'unrecovered':
        raise UnsupportedCandidate('trigger evaluator: a condition kind in this record is not recovered')
    if result['arm'] == 'firing':
        raise UnsupportedCandidate('trigger evaluator firing arm is not recovered (left for the supervisor)')
    entry = result['entry']
    cycles, instructions = _TE_HEAD
    # muls.w #$18,d0 (the head's own index-to-entry-offset multiply) leaves the full 32-bit signed
    # product in d0 before the first internal call -- the caller's own entering d0 is gone by then.
    index_signed = index - 0x10000 if index & 0x8000 else index
    regs = {'d0': (index_signed * triggers.TRIGGER_STRIDE) & 0xFFFFFFFF, 'd1': entry_d1,
           'd5': entry_d5, 'd6': entry_d6, 'a4': entry_a4, 'a5': entry_a5}
    call_sr = sr
    slot_values = []
    for pair_index, call in enumerate(result['calls']):
        kind, argument, slot = call['kind'], call['argument'], call['slot']
        regs['d5'] = (regs['d5'] & 0xFFFF0000) | (kind & 0xFFFF)
        regs['d6'] = (regs['d6'] & 0xFFFF0000) | (argument & 0xFFFF)
        effects = _condition_call(read, call_sr, regs['d0'], kind, argument, slot)
        extra = dict(effects['extra'])
        if 'd1' in extra:
            extra['d1'] = (regs['d1'] & 0xFFFF0000) | (extra['d1'] & 0xFFFF)
        if 'd6' in extra:
            extra['d6'] = (regs['d6'] & 0xFFFF0000) | (extra['d6'] & 0xFFFF)
        call_sr = extra.pop('sr')
        regs.update(extra)
        cycles += _TE_BSR[0] + effects['cost'][0]
        instructions += _TE_BSR[1] + effects['cost'][1]
        slot_values.append(call['result']['arm'] != 'false')
        if pair_index < len(result['calls']) - 1:
            cycles += _TE_SETUP[0]
            instructions += _TE_SETUP[1]
    cycles += _TE_TAIL[0] + _TE_OUTER_RTS[0]
    instructions += _TE_TAIL[1] + _TE_OUTER_RTS[1]
    final = 0xFFFF if all(slot_values) else 0x0000
    exit_sr = _logic_sr(call_sr, final, 2)
    exit_registers = {'d0': (regs['d0'] & 0xFFFF0000) | final, 'a2': a0,
                      'a1': (triggers.TRIGGER_TABLE + triggers.TRIGGER_STRIDE * index) & 0xFFFFFFFF,
                      'a3': (triggers.SLOT_BASE + 4) & 0xFFFFFFFF, 'a4': regs['a4'], 'a5': regs['a5'],
                      'd1': regs['d1'], 'd5': regs['d5'], 'd6': regs['d6']}
    writes = {}
    for a, b in _bytes(triggers.SLOT_BASE & 0xFFFFFF, 0xFFFFFFFF, 4):
        writes[a] = b
    for a, b in _bytes((triggers.SLOT_BASE + 4) & 0xFFFFFF, 0xFFFF, 2):
        writes[a] = b
    for call in result['calls']:
        for address, (value, size) in call['result']['stores'].items():
            for a, b in _bytes(address, value, size):
                writes[a] = b
    return {'cycles': cycles, 'instructions': instructions, 'writes': writes, 'registers': exit_registers,
           'sr': exit_sr, 'entry': entry, 'pair_count': len(result['calls'])}


def evaluator_plan(machine, registers):
    """00462C: the trigger evaluator's non-firing arm, three composed calls into 00470C."""
    from .game import triggers
    if registers['pc'] != EVALUATOR_ENTRY:
        raise UnsupportedCandidate('trigger evaluator planner needs the machine parked at 00462C')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    a0 = registers['a0'] & 0xFFFFFFFF
    read = _reader(machine)
    resolved = _evaluator_resolve(read, sr, a0, registers['d1'], registers['d5'], registers['d6'],
                                  registers['a4'], registers['a5'])
    _spans_disjoint([('trigger frame', sp, 4),
                     ('trigger record', resolved['entry'] & 0xFFFFFF, triggers.TRIGGER_STRIDE)])
    exit_registers = dict(resolved['registers'])
    exit_registers.update(a7=(sp32 + 4) & 0xFFFFFFFF, pc=_return(machine, sp), sr=resolved['sr'])
    writes = dict(resolved['writes'])
    for a, b in _bytes((sp - 4) & 0xFFFFFF, _TE_RETURN_PC[resolved['pair_count'] - 1], 4):
        writes[a] = b
    return AtomicPlan(cycles=resolved['cycles'], instructions=resolved['instructions'],
                      writes=tuple(writes.items()), registers=exit_registers, last_pc=EVALUATOR_LAST_PC)


# --- 007986/0079DC: the message display gate and string copy (game/messages.py) ---------------------
#
# Shared utilities (007986 has real callers well outside the trigger firing
# arm this session was asked to compose, e.g. 005BC6 and 0086B6); recovered
# on their own merits, each its own gate.  A fresh census of 007986 over all
# eight recordings (--max-classes 100) found only two real path classes,
# both reaching the SAME "buffer already empty" tail -- the only difference
# is whether the caller's own D7 needed negating first (which also clears
# MESSAGE_BOUND/PENDING).  The "buffer occupied" arm (a stored-priority
# compare, then MESSAGE_BUFFER_ALT or failure) is real code no recording
# has ever entered.
MESSAGE_GATE_ENTRY, MESSAGE_GATE_READY_LAST_PC = 0x007986, 0x0079B0
_MG_TST_D7 = (4, 1)                     # tst.w d7
_MG_BPL_TAKEN, _MG_BPL_NOTTAKEN = (10, 1), (8, 1)       # bpl.b $7994
_MG_NEGATE = (4 + 16 + 16, 3)           # neg.w d7; clr.w MESSAGE_BOUND; clr.w MESSAGE_PENDING
_MG_BUFFER = (16, 1)                    # movea.l MESSAGE_BUFFER,a1
_MG_TST_BUFFER = (8, 1)                 # tst.b (a1)
_MG_BEQ_TAKEN, _MG_BEQ_NOTTAKEN = (10, 1), (8, 1)       # beq.b $79aa (the primary buffer's own test)
_MG_READ_STORED = (12, 1)               # move.w MESSAGE_BOUND,d0 (the buffer's own occupant)
_MG_BEQ_STORED_NOTTAKEN = (8, 1)        # beq.b $79a6, not taken (stored bound != 0, the only witnessed case)
_MG_CMP = (4, 1)                        # cmp.w d0,d7
_MG_BGT_TAKEN, _MG_BGT_NOTTAKEN = (10, 1), (8, 1)       # bgt.b $79b2 (insufficient priority: 'blocked')
_MG_ALT_BUFFER = (16, 1)                # movea.l MESSAGE_BUFFER_ALT,a1
_MG_STORE_BOUND = (12, 1)               # move.w d7,MESSAGE_BOUND
_MG_MOVEQ_D0 = (4, 1)                   # moveq #$0,d0
_MG_FAIL_MOVEQ = (4, 1)                 # moveq #$ff,d0
_MG_RTS = (16, 1)
MESSAGE_GATE_BLOCKED_LAST_PC = 0x0079B4


def message_gate_plan(machine, registers):
    """007986: gate a message of priority D7 against the display buffer -- the primary buffer
    already empty, or occupied with a sufficient stored priority (MESSAGE_BUFFER_ALT instead), are
    both 'ready'; an occupied buffer with a stored bound of exactly 0 (skips the compare outright) is
    not witnessed by any recording."""
    from .game import messages
    if registers['pc'] != MESSAGE_GATE_ENTRY:
        raise UnsupportedCandidate('message gate planner needs the machine parked at 007986')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    d7 = registers['d7'] & 0xFFFF
    read = _reader(machine)
    result = messages.message_gate(read, d7)
    if result['arm'] == 'unrecovered':
        raise UnsupportedCandidate(
            'message gate: an occupied buffer with a zero stored bound is not witnessed by a recording')
    cycles, instructions = _add(_MG_TST_D7, _MG_BPL_NOTTAKEN if result['negated'] else _MG_BPL_TAKEN)
    if result['negated']:
        c, i = _MG_NEGATE
        cycles += c
        instructions += i
    c, i = _add(_MG_BUFFER, _MG_TST_BUFFER)
    cycles += c
    instructions += i
    # A 'ready' result can be reached with the primary buffer either empty or occupied (then via
    # MESSAGE_BUFFER_ALT): distinguish them by re-reading the same byte the semantics already checked.
    primary_empty = read(messages.MESSAGE_BUFFER, 4) & 0xFFFFFFFF
    primary_empty = read(primary_empty & 0xFFFFFF, 1) == 0
    if primary_empty:
        c, i = _add(_MG_BEQ_TAKEN, _MG_STORE_BOUND, _MG_MOVEQ_D0, _MG_RTS)
        cycles += c
        instructions += i
    else:
        c, i = _add(_MG_BEQ_NOTTAKEN, _MG_READ_STORED, _MG_BEQ_STORED_NOTTAKEN, _MG_CMP)
        cycles += c
        instructions += i
        if result['arm'] == 'blocked':
            c, i = _add(_MG_BGT_TAKEN, _MG_FAIL_MOVEQ, _MG_RTS)
            cycles += c
            instructions += i
            writes = tuple(pair for address, (value, size) in result['stores'].items()
                          for pair in _bytes(address, value, size))
            # moveq #$ff,d0 is the last flag-setter (N=1 always); X survives as for the 'ready' arm.
            x_bit = 0x10 if result['negated'] else (sr & 0x10)
            exit_sr = (_logic_sr(sr, 0xFFFFFFFF, 4) & ~0x10) | x_bit
            exit_registers = {'d0': 0xFFFFFFFF, 'd7': (registers['d7'] & 0xFFFF0000) | result['bound'],
                              'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr}
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                              last_pc=MESSAGE_GATE_BLOCKED_LAST_PC)
        c, i = _add(_MG_BGT_NOTTAKEN, _MG_ALT_BUFFER, _MG_STORE_BOUND, _MG_MOVEQ_D0, _MG_RTS)
        cycles += c
        instructions += i
    writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    # moveq #$0,d0 is the last flag-setter (Z=1 always); X survives from neg.w d7 when negated
    # (a nonzero operand always borrows: X=1) or is untouched otherwise.
    x_bit = 0x10 if result['negated'] else (sr & 0x10)
    exit_sr = (_logic_sr(sr, 0, 2) & ~0x10) | x_bit
    # moveq #$0,d0 sign-extends into the WHOLE register: no entry-value preservation.
    exit_registers = {'d0': 0, 'd7': (registers['d7'] & 0xFFFF0000) | result['bound'],
                      'a1': result['buffer'], 'a7': (sp32 + 4) & 0xFFFFFFFF,
                      'pc': _return(machine, sp), 'sr': exit_sr}
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                      last_pc=MESSAGE_GATE_READY_LAST_PC)


STRING_COPY_ENTRY, STRING_COPY_LAST_PC = 0x0079DC, 0x0079E4
_STRCPY_BYTE = (8 + 8 + 8 + 10, 4)      # move.b (a2)+,d1; beq nottaken; move.b d1,(a1)+; bra taken -- per copied byte
_STRCPY_TAIL = (8 + 10 + 16, 3)         # move.b (a2)+,d1; beq taken; rts -- the terminating NUL


def string_copy_plan(machine, registers):
    """0079DC: copy bytes from A2 to A1 until a NUL (itself read but not written -- the caller's own
    clr.b (a1)+ supplies the terminator); the loop is bounded by the string's own length."""
    if registers['pc'] != STRING_COPY_ENTRY:
        raise UnsupportedCandidate('string copy planner needs the machine parked at 0079DC')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    a1, a2 = registers['a1'] & 0xFFFFFFFF, registers['a2'] & 0xFFFFFFFF
    from .game import messages
    read = _reader(machine)
    result = messages.copy_message(read, a2)
    copied = result['bytes'][:-1]              # every byte but the trailing NUL: what actually gets written
    _ram_span('string copy destination', a1 & 0xFFFFFF, len(copied))
    writes = tuple(pair for index, value in enumerate(copied) for pair in _bytes((a1 + index) & 0xFFFFFF, value, 1))
    c, i = _add(*([_STRCPY_BYTE] * len(copied)), _STRCPY_TAIL)
    exit_registers = {'d1': registers['d1'] & 0xFFFFFF00, 'a1': (a1 + len(copied)) & 0xFFFFFFFF,
                      'a2': (a2 + result['length']) & 0xFFFFFFFF, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                      'pc': _return(machine, sp), 'sr': _logic_sr(sr, 0, 1)}
    return AtomicPlan(cycles=c, instructions=i, writes=writes, registers=exit_registers, last_pc=STRING_COPY_LAST_PC)


# --- 0047DA: the achievement slot reset (game/achievements.py) -- a platform tail via bsr --------
#
# Aladdin's "one native call inside the branch" shape (recipe 6b's platform
# tail), reproduced with Gods' own device convention: the prefix is 0047DA's
# own RAM-only head (its d1/d2/a0 frame, the slot store, the D1 derivation),
# ending at the bsr itself with the return address pushed and every register
# 001648 reads in place; the ceded block is all of 001648 (whichever of its
# own two fill arms the ROM takes); the resume is 0047FA, and the suffix is
# 0047DA's own frame restore + rts, entirely RAM-only.  Cost from the tracer
# (artifacts/gods/evidence/census-0047DA-fresh-*).
ACHIEVEMENT_SLOT_RESET_ENTRY = 0x0047DA
ACHIEVEMENT_SLOT_RESET_CALL_LAST_PC = 0x0047F6    # the bsr instruction itself: the prefix's own last_pc
ACHIEVEMENT_SLOT_RESET_RESUME = 0x0047FA          # right after the bsr returns
ACHIEVEMENT_SLOT_RESET_LAST_PC = 0x0047FE         # the routine's own rts
ACHIEVEMENT_ICON_UPLOAD_ENTRY = 0x001648
ACHIEVEMENT_SLOT_RESET_FRAME = 12                 # movem.l d1-d2/a0,-(a7)
_ASR_FRAME_PUSH = (32, 1)               # movem.l d1-d2/a0,-(a7)
_ASR_MOVE_D0_D1 = (4, 1)                # move.w d0,d1
_ASR_DOUBLE_D1 = (4, 1)                 # add.w d1,d1
_ASR_LEA = (8, 1)                       # lea.l $f22e.w,a0
_ASR_MOVEQ_FF = (4, 1)                  # moveq #$ff,d2
_ASR_STORE_SLOT = (14, 1)               # move.w d2,(a0,d1.w)
_ASR_MOVEQ_0 = (4, 1)                   # moveq #0,d1
_ASR_CMP_HIGHLIGHT = (12, 1)            # cmp.w HIGHLIGHT_ID,d0
_ASR_BNE_TAKEN, _ASR_BNE_NOTTAKEN = (10, 1), (8, 1)
_ASR_MOVEQ_1 = (4, 1)                   # moveq #1,d1 (only when bne not taken, i.e. highlighted)
_ASR_BSR = (18, 1)                      # bsr.w $1648
_ASR_RESTORE = (36, 1)                  # movem.l (a7)+,d1-d2/a0 (the suffix)
_ASR_RTS = (16, 1)


def achievement_slot_reset_plan(machine, registers):
    """0047DA: mark a tracked-id slot empty, then call 001648 (the icon upload) as a seam -- D2 is
    fixed at -1 on every path through this routine, so only 001648's own 'clear' arm is ever reached
    from here (its real-descriptor upload belongs to a different, unidentified caller)."""
    from .game import achievements
    if registers['pc'] != ACHIEVEMENT_SLOT_RESET_ENTRY:
        raise UnsupportedCandidate('achievement slot reset planner needs the machine parked at 0047DA')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    if registers['a6'] != 0xC00000:
        raise UnsupportedCandidate('achievement slot reset planner needs a6 = C00000 (the VDP data port)')
    d0 = registers['d0'] & 0xFFFF
    if d0 not in achievements.WITNESSED_ICON_SLOTS:
        raise UnsupportedCandidate(f'achievement icon slot {d0} not witnessed by a recording')
    read = _reader(machine)
    result = achievements.achievement_slot_reset(read, d0)
    # The return-address write goes into `order` FIRST and the semantic slot store LAST, so a generic
    # "flip the last write" mutant (_mutate_result) corrupts an observable game byte, never the return
    # address 001648's own rts reads (a one-off return address is an odd fetch, an M68000 address
    # error, not a clean divergence).
    order = {}
    frame = ('achievement slot reset frame', sp - ACHIEVEMENT_SLOT_RESET_FRAME, ACHIEVEMENT_SLOT_RESET_FRAME + 4)
    _ram_span(*frame)
    for index, name in enumerate(('d1', 'd2', 'a0')):
        for a, b in _bytes((sp - ACHIEVEMENT_SLOT_RESET_FRAME + 4 * index) & 0xFFFFFF, registers[name], 4):
            order[a] = b
    return_slot = (sp - ACHIEVEMENT_SLOT_RESET_FRAME - 4) & 0xFFFFFF
    for a, b in _bytes(return_slot, ACHIEVEMENT_SLOT_RESET_RESUME, 4):
        order[a] = b
    for address, (value, size) in result['stores'].items():
        for a, b in _bytes(address, value, size):
            order[a] = b
    if result['highlighted']:
        c, i = _add(_ASR_FRAME_PUSH, _ASR_MOVE_D0_D1, _ASR_DOUBLE_D1, _ASR_LEA, _ASR_MOVEQ_FF, _ASR_STORE_SLOT,
                   _ASR_MOVEQ_0, _ASR_CMP_HIGHLIGHT, _ASR_BNE_NOTTAKEN, _ASR_MOVEQ_1, _ASR_BSR)
    else:
        c, i = _add(_ASR_FRAME_PUSH, _ASR_MOVE_D0_D1, _ASR_DOUBLE_D1, _ASR_LEA, _ASR_MOVEQ_FF, _ASR_STORE_SLOT,
                   _ASR_MOVEQ_0, _ASR_CMP_HIGHLIGHT, _ASR_BNE_TAKEN, _ASR_BSR)
    # cmp.w HIGHLIGHT_ID,d0 is the last flag-setter on the not-highlighted path (bne taken skips
    # moveq #1,d1 entirely); on the highlighted path moveq #1,d1 runs AFTER it and -- unlike a MOVE.w
    # into a scratch register elsewhere in this file -- MOVEQ does set N/Z/V/C (X only is unaffected),
    # so it is the real last flag-setter there, not the cmp.
    exit_sr = _logic_sr(sr, 1, 4) if result['highlighted'] else _cmp_sr(sr, d0, read(achievements.HIGHLIGHT_ID, 2), 2)
    prefix = AtomicPlan(
        cycles=c, instructions=i, writes=tuple(order.items()),
        # moveq sign-extends to the full 32-bit register (D1 <- 0 or 1, D2 <- -1): neither of the two
        # entry values' own upper halves survives, unlike a .w move.
        registers={'d1': result['icon_d1'], 'd2': 0xFFFFFFFF,
                   'a0': 0xFFFFF22E, 'a7': (sp32 - ACHIEVEMENT_SLOT_RESET_FRAME - 4) & 0xFFFFFFFF,
                   'pc': ACHIEVEMENT_ICON_UPLOAD_ENTRY, 'sr': exit_sr},
        last_pc=ACHIEVEMENT_SLOT_RESET_CALL_LAST_PC)
    return Seam(prefix=prefix, resume_pc=ACHIEVEMENT_SLOT_RESET_RESUME,
                stack_basis=(sp32 - ACHIEVEMENT_SLOT_RESET_FRAME) & 0xFFFFFFFF,
                # the frame plus the 4 bytes just above it: 0047DA's OWN return address (pushed by its
                # caller before this activation began, still unreturned -- 0018C8's own guard shape).
                guards=((sp - ACHIEVEMENT_SLOT_RESET_FRAME, ACHIEVEMENT_SLOT_RESET_FRAME + 4),),
                suffix=achievement_slot_reset_suffix)


def achievement_slot_reset_suffix(machine, registers):
    """0047FA after the icon upload returns: the d1/d2/a0 frame back into the registers, then rts."""
    if registers['pc'] != ACHIEVEMENT_SLOT_RESET_RESUME:
        raise UnsupportedCandidate('achievement slot reset suffix needs the machine parked at 0047FA')
    base = registers['a7']
    restored = {name: int.from_bytes(machine.peek_ram((base + 4 * index) & 0xFFFF, 4), 'big')
                for index, name in enumerate(('d1', 'd2', 'a0'))}
    sp = (base + ACHIEVEMENT_SLOT_RESET_FRAME) & 0xFFFFFFFF
    restored.update(a7=(sp + 4) & 0xFFFFFFFF, pc=_return(machine, sp))
    c, i = _add(_ASR_RESTORE, _ASR_RTS)
    return AtomicPlan(cycles=c, instructions=i, writes=(), registers=restored,
                      last_pc=ACHIEVEMENT_SLOT_RESET_LAST_PC)


# --- 004790: the slot dispatch (game/achievements.py: achievement_slot_dispatch) -----------------
#
# A caller-supplied record's own tracked id, checked against 0047DA's own four ids; at most one can
# match (the ids are distinct).  A miss is a plain RAM-only leaf (four redundant compares, no calls).
# A match is a platform tail one level UP from achievement_slot_reset_plan: the whole of 0047DA
# (including ITS OWN nested call into 001648) is one opaque ceded block -- during a seam only its own
# resume_pc is gated (genesis_re.seam.run_seam narrows the gate array for the span), so 0047DA's own
# separate gate never fires inside it, and this composition need not know anything about 0047DA's own
# internals beyond what achievement_slot_reset_plan already proved.  The resume is 004790's own
# continuation after the ONE bsr that ran (0047BA/0047C4/0047CE/0047D8, one per matched slot), and the
# suffix is whichever later comparisons the ROM still runs (all misses, since the ids are distinct)
# plus 004790's own final rts.
ACHIEVEMENT_DISPATCH_ENTRY, ACHIEVEMENT_DISPATCH_LAST_PC = 0x004790, 0x0047D8
_AD_BSR_ADDRESSES = (0x0047B8, 0x0047C2, 0x0047CC, 0x0047D6)     # the bsr.b $47da instruction, per matched slot
_AD_RESUME_ADDRESSES = (0x0047BA, 0x0047C4, 0x0047CE, 0x0047D8)  # right after that bsr, per matched slot
_AD_LOAD_D5 = (8, 1)                     # move.w (a2),d5                                (004790/0047AE)
_AD_LEA_TABLE = (8, 1)                   # lea.l $f8c2.w,a3                              (004792)
_AD_DOUBLE = (4, 1)                      # add.w d5,d5
_AD_ADDA = (8, 1)                        # adda.w d5,a3
_AD_CMP_STATUS = (16, 1)                 # cmpi.w #2,4(a3)                               (0047A0)
_AD_BEQ_STATUS_TAKEN = (10, 1)           # beq.b (status==2, the only witnessed continuation) (0047A6)
_AD_CMP_ID = (12, 1)                     # cmp.w idN,d5
_AD_BNE_TAKEN, _AD_BNE_NOTTAKEN = (10, 1), (8, 1)
_AD_MOVEQ = (4, 1)                       # moveq #n,d0
_AD_BSR = (18, 1)                        # bsr.b $47da
_AD_RTS = (16, 1)
_AD_HEAD = _add(_AD_LOAD_D5, _AD_LEA_TABLE, _AD_DOUBLE, _AD_ADDA, _AD_DOUBLE, _AD_DOUBLE, _AD_ADDA,
               _AD_CMP_STATUS, _AD_BEQ_STATUS_TAKEN, _AD_LOAD_D5)


def achievement_slot_dispatch_plan(machine, registers):
    """004790: the slot dispatch; a miss is a plain leaf, a match is a seam over 0047DA (itself a
    seam over 001648) -- the whole of 0047DA is opaque to this composition."""
    from .game import achievements
    if registers['pc'] != ACHIEVEMENT_DISPATCH_ENTRY:
        raise UnsupportedCandidate('achievement slot dispatch planner needs the machine parked at 004790')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    a2 = registers['a2'] & 0xFFFFFFFF
    read = _reader(machine)
    result = achievements.achievement_slot_dispatch(read, a2)
    if result['arm'] == 'blocked':
        raise UnsupportedCandidate(f"achievement slot dispatch status {result['status']} not witnessed by a recording")
    tracked = result['tracked']
    d5 = (registers['d5'] & 0xFFFF0000) | tracked
    if result['arm'] == 'no-match':
        c, i = _add(_AD_HEAD, *(_add(_AD_CMP_ID, _AD_BNE_TAKEN) for _ in range(4)), _AD_RTS)
        exit_sr = _cmp_sr(sr, tracked, read(achievements.TRACKED_IDS[3], 2), 2)
        return AtomicPlan(cycles=c, instructions=i, writes=(),
                          registers={'d5': d5, 'a3': result['record'] & 0xFFFFFFFF,
                                     'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp),
                                     'sr': exit_sr},
                          last_pc=ACHIEVEMENT_DISPATCH_LAST_PC)
    slot = result['match']
    c, i = _add(_AD_HEAD, *(_add(_AD_CMP_ID, _AD_BNE_TAKEN) for _ in range(slot)), _AD_CMP_ID, _AD_BNE_NOTTAKEN,
               _AD_MOVEQ, _AD_BSR)
    a3 = result['record'] & 0xFFFFFFFF
    # moveq #n,d0 is the LAST flag-setter before the bsr, not the cmp before it (achievement_slot_reset_plan's
    # own lesson: MOVEQ sets N/Z/V/C, only X unaffected) -- nothing between the moveq and the bsr touches CCR.
    exit_sr = _logic_sr(sr, slot, 4)
    return_slot = (sp - 4) & 0xFFFFFF
    _ram_span('achievement slot dispatch return slot', return_slot, 4)
    writes = _bytes(return_slot, _AD_RESUME_ADDRESSES[slot], 4)
    prefix = AtomicPlan(cycles=c, instructions=i, writes=writes,
                        registers={'d0': slot, 'd5': d5, 'a3': a3, 'a7': (sp32 - 4) & 0xFFFFFFFF,
                                   'pc': ACHIEVEMENT_SLOT_RESET_ENTRY, 'sr': exit_sr},
                        last_pc=_AD_BSR_ADDRESSES[slot])
    return Seam(prefix=prefix, resume_pc=_AD_RESUME_ADDRESSES[slot], stack_basis=sp32 & 0xFFFFFFFF,
               guards=((sp, 4),), suffix=achievement_slot_dispatch_suffix)


def achievement_slot_dispatch_suffix(machine, registers):
    """The resume after the ONE matched bsr into 0047DA (itself already back from its own seam over
    001648): whichever later comparisons the ROM still runs (always misses), then 004790's own rts."""
    pc = registers['pc']
    if pc not in _AD_RESUME_ADDRESSES:
        raise UnsupportedCandidate('achievement slot dispatch suffix needs the machine parked at its own resume')
    slot = _AD_RESUME_ADDRESSES.index(pc)
    from .game import achievements
    read = _reader(machine)
    d5 = registers['d5']
    tracked = d5 & 0xFFFF
    remaining = range(slot + 1, 4)
    c, i = _add(*(_add(_AD_CMP_ID, _AD_BNE_TAKEN) for _ in remaining), _AD_RTS)
    sp = registers['a7'] & 0xFFFFFF
    exit_registers = {'a7': (registers['a7'] + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp)}
    if slot < 3:
        # A later comparison ran, and cmp (unlike moveq or bne) always sets the flags: the exit SR is
        # exactly that comparison's, independent of anything the ceded 0047DA/001648 block left behind.
        exit_registers['sr'] = _cmp_sr(registers['sr'], tracked, read(achievements.TRACKED_IDS[3], 2), 2)
    # slot == 3: resume_pc IS 0047D8 itself, the rts with nothing in between -- the machine's own live
    # SR already holds whatever the ceded block left (no Python-side override needed or possible).
    return AtomicPlan(cycles=c, instructions=i, writes=(), registers=exit_registers,
                      last_pc=ACHIEVEMENT_DISPATCH_LAST_PC)


# --- 00475E: the slot scan (game/achievements.py) -- up to three independent calls into 004790 ----
#
# Gates on bit 7 of the caller's own record ($10(a1)); when set, checks three independent flag
# words in turn ((a1), $4(a1), $8(a1), each tested against 1) and, for whichever is 1, calls the
# already-recovered achievement_slot_dispatch (004790) with a pointer two bytes past the flag --
# 0049DA's own "calls to already-recovered code" shape, up to three times in one activation.  Every
# witnessed occurrence across all eight recordings has at most one flag true; the third (0x08) is
# real ROM code no recording ever sets, and only the first position's call is ever witnessed to
# match a tracked id (the second, when true, is always a plain miss).  A match composes one level up
# from achievement_slot_dispatch_plan exactly as that planner composes one level up from
# achievement_slot_reset_plan (the whole of 0047DA/001648 stays one opaque ceded block; only the
# resume PC -- already one of 004790's own _AD_RESUME_ADDRESSES -- is gated).  genesis_re.seam
# cannot express a second independent seam inside the same activation's suffix, so a witnessed match
# followed by another independent match later in the same activation (never seen) declines there --
# an honest, safe fallback, not a guess.
SLOT_SCAN_ENTRY, SLOT_SCAN_LAST_PC = 0x00475E, 0x00478E
_SS_CHECKS = (
    (0x00, 0x02, (12, 1), 0x004772),   # (a1) == 1   -> a1+2,    resumes at 004772
    (0x04, 0x06, (16, 1), 0x004780),   # $4(a1) == 1 -> a1+6,    resumes at 004780
    (0x08, 0x0A, (16, 1), 0x00478E),   # $8(a1) == 1 -> a1+0xA,  resumes at 00478E (the rts itself)
)
_SS_BTST = (16, 1)                      # btst.b #7, $10(a1)
_SS_GATE_TAKEN, _SS_GATE_NOTTAKEN = (10, 1), (8, 1)
_SS_BNE_TAKEN, _SS_BNE_NOTTAKEN = (10, 1), (8, 1)
_SS_LEA = (8, 1)
_SS_BSR = (18, 1)
_SS_RTS = (16, 1)


def _slot_scan_tail(read, a1, start):
    """The cost of the checks from ``start`` to the end (2) that the ROM always still runs, on the
    witnessed assumption that none of them are true -- the only shape any recording exercises past a
    first true check; a true flag here is declined, not guessed."""
    cycles = instructions = 0
    for j in range(start, 3):
        _, _, cmp_cost, _ = _SS_CHECKS[j]
        if read((a1 + _SS_CHECKS[j][0]) & 0xFFFFFF, 2) & 0xFFFF == 1:
            raise UnsupportedCandidate(
                f'slot scan: a second independent check (position {j}) true in one activation, unwitnessed')
        c, i = _add(cmp_cost, _SS_BNE_TAKEN)
        cycles += c
        instructions += i
    return cycles, instructions


def slot_scan_plan(machine, registers):
    """00475E: the slot scan, up to three independent calls into 004790."""
    from .game import achievements
    if registers['pc'] != SLOT_SCAN_ENTRY:
        raise UnsupportedCandidate('slot scan planner needs the machine parked at 00475E')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    read = _reader(machine)
    a1 = registers['a1'] & 0xFFFFFFFF
    exit_pc = _return(machine, sp)
    if not (read((a1 + 0x10) & 0xFFFFFF, 1) & 0x80):
        c, i = _add(_SS_BTST, _SS_GATE_TAKEN, _SS_RTS)
        # btst sets only Z (the tested bit was clear); N/V/C/X are retained from the entry SR.
        return AtomicPlan(cycles=c, instructions=i, writes=(),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': exit_pc, 'sr': sr | 0x04},
                          last_pc=SLOT_SCAN_LAST_PC)
    cycles, instructions = _add(_SS_BTST, _SS_GATE_NOTTAKEN)
    index = None
    for j in range(3):
        offset, id_offset, cmp_cost, resume_after = _SS_CHECKS[j]
        c, i = cmp_cost
        cycles += c
        instructions += i
        if read((a1 + offset) & 0xFFFFFF, 2) & 0xFFFF == 1:
            index = j
            break
        c, i = _SS_BNE_TAKEN
        cycles += c
        instructions += i
    if index is None:
        # all three flags false: the routine's own straight-line bare exit
        c, i = _SS_RTS
        cycles += c
        instructions += i
        exit_sr = _cmp_sr(sr, read((a1 + _SS_CHECKS[2][0]) & 0xFFFFFF, 2) & 0xFFFF, 1, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=(),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': exit_pc, 'sr': exit_sr},
                          last_pc=SLOT_SCAN_LAST_PC)
    if index not in achievements.WITNESSED_SLOT_SCAN_CALLS:
        raise UnsupportedCandidate(f'slot scan call position {index} not witnessed by a recording')
    offset, id_offset, cmp_cost, resume_after = _SS_CHECKS[index]
    c, i = _add(_SS_BNE_NOTTAKEN, _SS_LEA, _SS_BSR)
    cycles += c
    instructions += i
    order = {}
    return_slot = (sp - 4) & 0xFFFFFF
    _ram_span('slot scan return slot', return_slot, 4)
    for a, b in _bytes(return_slot, resume_after, 4):
        order[a] = b
    virtual = dict(registers)
    virtual.update(pc=ACHIEVEMENT_DISPATCH_ENTRY, a2=(a1 + id_offset) & 0xFFFFFFFF,
                   a7=(sp32 - 4) & 0xFFFFFFFF, sr=_cmp_sr(sr, 1, 1, 2))
    inner = achievement_slot_dispatch_plan(machine, virtual)
    if isinstance(inner, Seam):
        if index not in achievements.WITNESSED_SLOT_SCAN_MATCHES:
            raise UnsupportedCandidate(f'slot scan match at position {index} not witnessed by a recording')
        for a, b in inner.prefix.writes:
            order[a] = b
        prefix_registers = dict(inner.prefix.registers)
        prefix_registers['a2'] = (a1 + id_offset) & 0xFFFFFFFF
        prefix = AtomicPlan(cycles=cycles + inner.prefix.cycles, instructions=instructions + inner.prefix.instructions,
                            writes=tuple(order.items()), registers=prefix_registers,
                            last_pc=inner.prefix.last_pc)
        matched_index = index

        def suffix(machine, live_registers):
            tail = achievement_slot_dispatch_suffix(machine, live_registers)
            read2 = _reader(machine)
            tail_cycles, tail_instructions = _slot_scan_tail(read2, a1, matched_index + 1)
            base_sr = tail.registers['sr'] if 'sr' in tail.registers else live_registers['sr']
            exit_registers = dict(tail.registers)
            if matched_index < 2:
                exit_registers['sr'] = _cmp_sr(base_sr, read2((a1 + _SS_CHECKS[2][0]) & 0xFFFFFF, 2) & 0xFFFF, 1, 2)
            else:
                exit_registers['sr'] = base_sr
            exit_registers['pc'] = _return(machine, sp)
            exit_registers['a7'] = (tail.registers['a7'] + 4) & 0xFFFFFFFF
            rc, ri = _SS_RTS
            return AtomicPlan(cycles=tail.cycles + tail_cycles + rc, instructions=tail.instructions + tail_instructions + ri,
                              writes=(), registers=exit_registers, last_pc=SLOT_SCAN_LAST_PC)

        return Seam(prefix=prefix, resume_pc=inner.resume_pc, stack_basis=inner.stack_basis,
                   guards=inner.guards, suffix=suffix, expect=inner.expect)
    # no-match: fold the call's own cost/writes/registers, then the remaining checks (witnessed false)
    for a, b in inner.writes:
        order[a] = b
    tail_cycles, tail_instructions = _slot_scan_tail(read, a1, index + 1)
    exit_sr = inner.registers.get('sr', sr)
    if index < 2:
        exit_sr = _cmp_sr(exit_sr, read((a1 + _SS_CHECKS[2][0]) & 0xFFFFFF, 2) & 0xFFFF, 1, 2)
    rc, ri = _SS_RTS
    registers = dict(inner.registers)
    registers.update(a2=(a1 + id_offset) & 0xFFFFFFFF, a7=(sp32 + 4) & 0xFFFFFFFF, pc=exit_pc, sr=exit_sr)
    return AtomicPlan(cycles=cycles + inner.cycles + tail_cycles + rc,
                      instructions=instructions + inner.instructions + tail_instructions + ri,
                      writes=tuple(order.items()), registers=registers, last_pc=SLOT_SCAN_LAST_PC)


# --- 004800: the record id scan (game/achievements.py) -- the trigger firing subsystem blocker's ---
# own part 2, last caller: up to three independent calls into 0048B4 (achievement_slot_dispatch's own
# id-compare tail, reached without a status gate) ---------------------------------------------------
#
# Gates on d5 = ($10(a1)) & 0x7fff being one of {2,3,4,7,8}; when it is, checks the same three (flag,
# id) field pairs 00475E's own slot scan does, but a witnessed pair calls 0048B4 through a tail JUMP
# straight into 0047DA (D0 the matched slot).  A bra.w pushes nothing, so 0047DA's own rts returns
# directly to whichever of 004800's own bsr sites made the call: the composition reuses
# achievement_slot_reset_plan/_suffix exactly as if 0048B4's own match were 0047DA's own direct
# caller, needing no 004790-style resume-and-continue layer of its own -- only 0048B4's own id-compare
# body (identical in shape to achievement_slot_dispatch's own tail, but ending in a bra.w, not a bsr)
# has to be charged explicitly before reaching 0047DA.  Every witnessed call (either the first or
# second position) is a match; the third position, and a miss from either witnessed one, are both
# real ROM code no recording enters -- declined, not guessed, exactly as 00475E's own unwitnessed
# combinations are.
RECORD_ID_SCAN_ENTRY, RECORD_ID_SCAN_LAST_PC = 0x004800, 0x0048B2
RECORD_ID_SCAN_GATE_LAST_PC = 0x004820   # the gate's own separate rts (d5 outside {2,3,4,7,8})
_RIS_MOVE_D5 = (12, 1)                  # move.w $10(a1), d5
_RIS_ANDI = (8, 1)                      # andi.w #$7fff, d5
_RIS_CMP = (8, 1)                       # cmpi.w #n, d5
_RIS_BCC_TAKEN, _RIS_BCC_NOTTAKEN = (10, 1), (8, 1)
_RIS_RTS = (16, 1)
_RIS_FLAG_MOVE = ((8, 1), (12, 1), (12, 1))    # move.w (a1)/$4(a1)/$8(a1), d5 -- per position
_RIS_FLAG_CMP = (8, 1)                         # cmpi.w #1, d5
_RIS_FLAG_BNE_TAKEN, _RIS_FLAG_BNE_NOTTAKEN = (10, 1), (8, 1)
_RIS_RANGE_CMP = (16, 1)                       # cmpi.w #n, N(a1) -- same cost for all four bounds
_RIS_RANGE_BCC_TAKEN, _RIS_RANGE_BCC_NOTTAKEN = (10, 1), (8, 1)
_RIS_MOVE_D6 = (12, 1)                         # move.w N(a1), d6
_RIS_BSR = (18, 1)
_RIT_CMP_ID = (12, 1)                          # 0048B4's own cmp.w idN, d6
_RIT_BNE_TAKEN, _RIT_BNE_NOTTAKEN = (10, 1), (8, 1)
_RIT_MOVEQ = (4, 1)                            # moveq #slot, d0
_RIT_BRA = (10, 1)                             # bra.w $47da (a tail jump, not a bsr)
_RIS_RESUME = (0x004852, 0x004882, 0x0048B2)   # 004800's own three continuation addresses, per position


def _record_id_scan_gate_cost(d5):
    """004800's own gate walk (0x4800-0x4820): accepted or not, its cost, and the value the LAST
    comparison it made (on a reject) compares d5 against -- the exit SR's own source."""
    cycles, instructions = _add(_RIS_MOVE_D5, _RIS_ANDI, _RIS_CMP)
    if d5 < 2:
        c, i = _add(_RIS_BCC_TAKEN, _RIS_RTS)
        return False, cycles + c, instructions + i, 2
    c, i = _add(_RIS_BCC_NOTTAKEN, _RIS_CMP)
    cycles, instructions = cycles + c, instructions + i
    if d5 <= 4:
        c, i = _RIS_BCC_TAKEN
        return True, cycles + c, instructions + i, 4
    c, i = _add(_RIS_BCC_NOTTAKEN, _RIS_CMP)
    cycles, instructions = cycles + c, instructions + i
    if d5 == 7:
        c, i = _RIS_BCC_TAKEN
        return True, cycles + c, instructions + i, 7
    c, i = _add(_RIS_BCC_NOTTAKEN, _RIS_CMP)
    cycles, instructions = cycles + c, instructions + i
    if d5 == 8:
        c, i = _RIS_BCC_TAKEN
        return True, cycles + c, instructions + i, 8
    c, i = _add(_RIS_BCC_NOTTAKEN, _RIS_RTS)
    return False, cycles + c, instructions + i, 8


def _record_id_scan_range_cost(value, sr):
    """0048B4's own two id ranges (0x12-0x17, then 0x7f-0x81): accepted or not, cost, exit SR."""
    cycles, instructions = _RIS_RANGE_CMP
    if value < 0x12:
        c, i = _RIS_RANGE_BCC_TAKEN
        return False, cycles + c, instructions + i, _cmp_sr(sr, value, 0x12, 2)
    c, i = _add(_RIS_RANGE_BCC_NOTTAKEN, _RIS_RANGE_CMP)
    cycles, instructions = cycles + c, instructions + i
    if value <= 0x17:
        c, i = _RIS_RANGE_BCC_TAKEN
        return True, cycles + c, instructions + i, _cmp_sr(sr, value, 0x17, 2)
    c, i = _add(_RIS_RANGE_BCC_NOTTAKEN, _RIS_RANGE_CMP)
    cycles, instructions = cycles + c, instructions + i
    if value < 0x7F:
        c, i = _RIS_RANGE_BCC_TAKEN
        return False, cycles + c, instructions + i, _cmp_sr(sr, value, 0x7F, 2)
    c, i = _add(_RIS_RANGE_BCC_NOTTAKEN, _RIS_RANGE_CMP)
    cycles, instructions = cycles + c, instructions + i
    if value > 0x81:
        c, i = _RIS_RANGE_BCC_TAKEN
        return False, cycles + c, instructions + i, _cmp_sr(sr, value, 0x81, 2)
    c, i = _RIS_RANGE_BCC_NOTTAKEN
    return True, cycles + c, instructions + i, _cmp_sr(sr, value, 0x81, 2)


def _record_id_scan_check(read, a1, position, sr):
    """One of the three independent (flag, id) checks: whether it calls 0048B4, the id value if so,
    the cost along whichever branch the ROM took, its own exit SR, and the flag word itself (d5's own
    final value comes from whichever position last ran -- always the third, since all three always
    run regardless of an earlier match)."""
    from .game import achievements
    flag_offset, id_offset = achievements.SLOT_SCAN_CHECKS[position]
    cycles, instructions = _RIS_FLAG_MOVE[position]
    c, i = _RIS_FLAG_CMP
    cycles, instructions = cycles + c, instructions + i
    flag_value = read((a1 + flag_offset) & 0xFFFFFF, 2) & 0xFFFF
    if flag_value != 1:
        c, i = _RIS_FLAG_BNE_TAKEN
        return False, None, cycles + c, instructions + i, _cmp_sr(sr, flag_value, 1, 2), flag_value
    c, i = _RIS_FLAG_BNE_NOTTAKEN
    cycles, instructions = cycles + c, instructions + i
    value = read((a1 + id_offset) & 0xFFFFFF, 2) & 0xFFFF
    accepted, rc, ri, range_sr = _record_id_scan_range_cost(value, sr)
    cycles, instructions = cycles + rc, instructions + ri
    if not accepted:
        return False, None, cycles, instructions, range_sr, flag_value
    c, i = _add(_RIS_MOVE_D6, _RIS_BSR)
    return True, value, cycles + c, instructions + i, range_sr, flag_value


def _id_tail_cost(slot):
    """0048B4's own body: up to four id compares against 0047DA's own tracked ids, then moveq #slot,d0
    and a tail bra.w straight into 0047DA (no bsr, no rts of 0048B4's own)."""
    cycles = instructions = 0
    for _ in range(slot):
        c, i = _add(_RIT_CMP_ID, _RIT_BNE_TAKEN)
        cycles, instructions = cycles + c, instructions + i
    c, i = _add(_RIT_CMP_ID, _RIT_BNE_NOTTAKEN, _RIT_MOVEQ, _RIT_BRA)
    return cycles + c, instructions + i


def _record_id_scan_tail(read, a1, sr, start):
    """The checks from ``start`` to the end (2) the ROM always still runs, on the witnessed
    assumption that none of them call 0048B4 -- the only shape any recording exercises past a first
    match; a call here is declined, not guessed (genesis_re.seam cannot chain a second seam)."""
    cycles = instructions = 0
    exit_sr = sr
    flag_value = 0
    for j in range(start, 3):
        matched, _, c, i, exit_sr, flag_value = _record_id_scan_check(read, a1, j, sr)
        cycles += c
        instructions += i
        if matched:
            raise UnsupportedCandidate(
                f'record id scan: a second independent check (position {j}) true in one activation, unwitnessed')
    return cycles, instructions, exit_sr, flag_value


def record_id_scan_plan(machine, registers):
    """004800: the record id scan, up to three independent calls into 0048B4."""
    from .game import achievements
    if registers['pc'] != RECORD_ID_SCAN_ENTRY:
        raise UnsupportedCandidate('record id scan planner needs the machine parked at 004800')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    read = _reader(machine)
    a1 = registers['a1'] & 0xFFFFFFFF
    exit_pc = _return(machine, sp)
    # 004800's own first instruction loads d5 fresh from the record ($10(a1)) -- the entry register is
    # scratch, exactly as 00475E's own checks always read their fields from (a1), never from a register.
    d5_masked = read((a1 + 0x10) & 0xFFFFFF, 2) & 0x7FFF
    accepted, cycles, instructions, last_cmp = _record_id_scan_gate_cost(d5_masked)
    if not accepted:
        exit_sr = _cmp_sr(sr, d5_masked, last_cmp, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=(),
                          registers={'d5': (registers['d5'] & 0xFFFF0000) | d5_masked,
                                     'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': exit_pc, 'sr': exit_sr},
                          last_pc=RECORD_ID_SCAN_GATE_LAST_PC)
    index = match_value = None
    last_flag_value = 0
    last_check_sr = sr
    for j in range(3):
        matched, value, c, i, check_sr, flag_value = _record_id_scan_check(read, a1, j, sr)
        cycles += c
        instructions += i
        last_flag_value, last_check_sr = flag_value, check_sr
        if matched:
            index, match_value = j, value
            break
    if index is None:
        c, i = _RIS_RTS
        registers_out = {'d5': (registers['d5'] & 0xFFFF0000) | last_flag_value,
                         'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': exit_pc, 'sr': last_check_sr}
        return AtomicPlan(cycles=cycles + c, instructions=instructions + i, writes=(),
                          registers=registers_out, last_pc=RECORD_ID_SCAN_LAST_PC)
    if index not in achievements.WITNESSED_RECORD_ID_SCAN_CALLS:
        raise UnsupportedCandidate(f'record id scan call position {index} not witnessed by a recording')
    match = achievements.match_tracked_id(read, match_value)
    if match is None:
        raise UnsupportedCandidate('record id scan: a miss from 0048B4 is not witnessed by a recording')
    tail_c, tail_i = _id_tail_cost(match)
    cycles += tail_c
    instructions += tail_i
    resume_after = _RIS_RESUME[index]
    order = {}
    return_slot = (sp - 4) & 0xFFFFFF
    _ram_span('record id scan return slot', return_slot, 4)
    for a, b in _bytes(return_slot, resume_after, 4):
        order[a] = b
    virtual = dict(registers)
    virtual.update(pc=ACHIEVEMENT_SLOT_RESET_ENTRY, d0=match, a7=(sp32 - 4) & 0xFFFFFFFF, sr=last_check_sr)
    inner = achievement_slot_reset_plan(machine, virtual)
    for a, b in inner.prefix.writes:
        order[a] = b
    prefix_registers = dict(inner.prefix.registers)
    prefix_registers['d0'] = match           # moveq sign-extends to the full 32-bit register (0047DA's own lesson)
    prefix_registers['d6'] = (registers['d6'] & 0xFFFF0000) | match_value   # move.w only touches the low word
    prefix_registers['d5'] = (registers['d5'] & 0xFFFF0000) | 1   # the checked flag word itself, still 1 at this point
    prefix = AtomicPlan(cycles=cycles + inner.prefix.cycles, instructions=instructions + inner.prefix.instructions,
                        writes=tuple(order.items()), registers=prefix_registers, last_pc=inner.prefix.last_pc)
    matched_index = index

    def suffix(machine, live_registers):
        tail = achievement_slot_reset_suffix(machine, live_registers)
        read2 = _reader(machine)
        tail_cycles, tail_instructions, tail_sr, tail_flag = _record_id_scan_tail(
            read2, a1, live_registers['sr'], matched_index + 1)
        exit_registers = dict(tail.registers)
        exit_registers['d5'] = (registers['d5'] & 0xFFFF0000) | tail_flag
        exit_registers['sr'] = tail_sr
        exit_registers['pc'] = _return(machine, sp)
        exit_registers['a7'] = (tail.registers['a7'] + 4) & 0xFFFFFFFF
        rc, ri = _RIS_RTS
        return AtomicPlan(cycles=tail.cycles + tail_cycles + rc, instructions=tail.instructions + tail_instructions + ri,
                          writes=(), registers=exit_registers, last_pc=RECORD_ID_SCAN_LAST_PC)

    return Seam(prefix=prefix, resume_pc=inner.resume_pc, stack_basis=inner.stack_basis,
               guards=inner.guards, suffix=suffix, expect=inner.expect)


# --- The trigger evaluator's action table (game/actions.py) -- part 3 of the trigger firing --------
# subsystem blocker's Split: two admissible handlers, reached by 00462C's own firing tail through a
# tail JUMP (jmp (a5), 0046CE) with no frame of its own -- exactly 0048B4's own shape, so a handler's
# own entry PC needs no seam at all: its own rts returns straight past the whole evaluator activation
# to whoever called it. The other action-table entries (004A0A, 004D04, 004E1C, 004E74, 0048EA,
# 005024, 00772E; 004A74/005074 unwitnessed) call still-unrecovered helper routines (004AAA, 004926,
# 004ECE/004D7E, 0050A4, 0077A8, 004F16) or write the level grid across several blocks, and stay
# unrecovered until those callees are -- an ordinary decline, not a new mechanism.

# --- 0048E4: reset the elapsed-seconds counter (ACTION_RESET_ELAPSED) ------------------------------
ACTION_RESET_ELAPSED_ENTRY, ACTION_RESET_ELAPSED_LAST_PC = 0x0048E4, 0x0048E8
_ARE_CLR = (24, 1)   # clr.l $f2aa.w
_ARE_RTS = (16, 1)


def action_reset_elapsed_plan(machine, registers):
    """0048E4: clr.l ELAPSED; rts -- no branch, no caller input, no frame of its own."""
    from .game import actions
    if registers['pc'] != ACTION_RESET_ELAPSED_ENTRY:
        raise UnsupportedCandidate('action reset elapsed planner needs the machine parked at 0048E4')
    sp = registers['a7'] & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    address = actions.reset_elapsed(_reader(machine))
    exit_pc = _return(machine, sp)
    c, i = _add(_ARE_CLR, _ARE_RTS)
    exit_sr = _logic_sr(registers['sr'], 0, 4)   # clr.l always sets Z, clears N/V/C; X retained
    return AtomicPlan(cycles=c, instructions=i, writes=_bytes(address & 0xFFFFFF, 0, 4),
                      registers={'a7': (registers['a7'] + 4) & 0xFFFFFFFF, 'pc': exit_pc, 'sr': exit_sr},
                      last_pc=ACTION_RESET_ELAPSED_LAST_PC)


# --- 004ACA: clear a matched pickup group's own active-id word (ACTION_CLEAR_GROUP) ----------------
#
# Each of the three (kind, argument) comparisons has ITS OWN rts (004ADA, 004AE8, 004AF6 -- not one
# shared exit): a match against the first or second group stops there; a match against the third, or
# a miss against all three, both end at 004AF6.
ACTION_CLEAR_GROUP_ENTRY = 0x004ACA
_ACTION_CLEAR_GROUP_LAST_PC = (0x004ADA, 0x004AE8, 0x004AF6)   # per matched index; a miss also ends at 004AF6
WITNESSED_ACTION_CLEAR_GROUP_ARMS = (1,)   # which of the three group words has been witnessed to match; None (no match) is also witnessed
_AC_MOVE_D2 = (12, 1)     # move.w $12(a1), d2
_AC_CMP = (12, 1)         # cmp.w idN.w, d2
_AC_BNE_TAKEN, _AC_BNE_NOTTAKEN = (10, 1), (8, 1)
_AC_STORE = (16, 1)       # move.w #$ffff, idN.w
_AC_RTS = (16, 1)


def _action_clear_group_cost(read, a1, value, sr):
    """004ACA: the (at most one) matched group's own index/address, cost, its own last_pc, and exit
    SR along the branch the ROM actually takes (None, None on a miss against all three)."""
    from .game import pickups
    cycles, instructions = _AC_MOVE_D2
    stored = None
    for index, address in enumerate(pickups.GROUP_TABLES):
        stored = read(address & 0xFFFFFF, 2) & 0xFFFF
        c, i = _AC_CMP
        cycles, instructions = cycles + c, instructions + i
        if value == stored:
            c, i = _AC_BNE_NOTTAKEN
            cycles, instructions = cycles + c, instructions + i
            c, i = _add(_AC_STORE, _AC_RTS)
            return (index, address, cycles + c, instructions + i, _logic_sr(sr, 0xFFFF, 2),
                    _ACTION_CLEAR_GROUP_LAST_PC[index])
        c, i = _AC_BNE_TAKEN
        cycles, instructions = cycles + c, instructions + i
    c, i = _AC_RTS
    return (None, None, cycles + c, instructions + i, _cmp_sr(sr, value, stored, 2),
            _ACTION_CLEAR_GROUP_LAST_PC[-1])


def action_clear_group_plan(machine, registers):
    """004ACA: clear whichever of the three pickup groups' own active-id words matches $12(a1)."""
    if registers['pc'] != ACTION_CLEAR_GROUP_ENTRY:
        raise UnsupportedCandidate('action clear group planner needs the machine parked at 004ACA')
    sp = registers['a7'] & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    read = _reader(machine)
    a1 = registers['a1'] & 0xFFFFFFFF
    sr = registers['sr']
    value = read((a1 + 0x12) & 0xFFFFFF, 2) & 0xFFFF
    index, address, cycles, instructions, exit_sr, last_pc = _action_clear_group_cost(read, a1, value, sr)
    if index not in WITNESSED_ACTION_CLEAR_GROUP_ARMS:
        raise UnsupportedCandidate(f'action clear group arm {index} not witnessed by a recording')
    d2 = (registers['d2'] & 0xFFFF0000) | value
    exit_pc = _return(machine, sp)
    writes = _bytes(address & 0xFFFFFF, 0xFFFF, 2) if address is not None else ()
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes,
                      registers={'d2': d2, 'a7': (registers['a7'] + 4) & 0xFFFFFFFF, 'pc': exit_pc, 'sr': exit_sr},
                      last_pc=last_pc)


# --- 00F828: the proximity table search-and-add (game/hazard.py: proximity_search/proximity_add) ---
#
# Owns its own internal call into 00F86A the way 0049DA owns its calls into
# 001164: no separate gate for 00F86A, the whole activation planned as one.
# Cost from the tracer (artifacts/gods/evidence/census-00F828*): the head
# (both the search's own hash and the outer routine's), the search's four
# per-position shapes (miss/close/stale/trigger), the free-slot scan's two
# (free/occupied), and the add body (a redundant recompute of the same key).
PROXIMITY_ENTRY, PROXIMITY_ADD_LAST_PC = 0x00F828, 0x00F868
PROXIMITY_TRIGGER_LAST_PC = 0x00F8E4
_PX_BSR = (18, 1)                       # bsr.w $f86a
_PX_HASH_HEAD = (4 + 16 + 4 + 14 + 8 + 16 + 14 + 12 + 4, 9)     # 00F86A's own head through moveq #$27,d6
_PX_MISS_MID, _PX_MISS_LAST = (8 + 10 + 4 + 10, 4), (8 + 10 + 4 + 14, 4)
_PX_CLOSE_MID, _PX_CLOSE_LAST = (8 + 8 + 12 + 10 + 4 + 10, 6), (8 + 8 + 12 + 10 + 4 + 14, 6)
_PX_STALE_MID, _PX_STALE_LAST = (8 + 8 + 12 + 8 + 12 + 8 + 4 + 10, 8), (8 + 8 + 12 + 8 + 12 + 8 + 4 + 14, 8)
_PX_SEARCH_RTS = (16, 1)                # 00F8A0: rts, once the search exhausts all 40 unmatched
_PX_OWN_HEAD = (12 + 4, 2)              # 00F82C: lea.l PROXIMITY_TABLE,a0; moveq #$27,d4
_PX_FREE = (8 + 10, 2)                  # tst.w (a0); bmi.b (taken)
_PX_OCC_MID, _PX_OCC_LAST = (8 + 8 + 4 + 10, 4), (8 + 8 + 4 + 14, 4)
_PX_ADD_KEY = (4 + 16 + 4 + 14 + 8 + 16 + 14, 7)      # the redundant key recompute: move.l a1,d4 .. lsr.l #3,d5
_PX_ADD_WRITE = (8 + 8, 2)              # move.w d4,(a0)+; move.w d5,(a0)+
_PX_ADD_TIMER = (12, 1)                 # move.w #$ffff,(a0)
_PX_ADD_COUNTER = (16, 1)               # addq.w #1,PROXIMITY_COUNTER -- the last flag-setter
_PX_ADD_FLAG = (16, 1)                  # st.b PROXIMITY_FLAG
_PX_ADD_RTS = (16, 1)
# 00F8A2 onward, the search's own 'trigger' continuation (game/hazard.py: proximity_trigger): the
# matched entry's own tst.w/bmi (bmi TAKEN this time, jumping away instead of falling into addq/dbra)
# replaces the 'stale' shape's own tail.
_PX_TRIGGER_FOUND = (8 + 8 + 12 + 8 + 12 + 10, 6)   # cmp.w(a0),d4; bne nottaken; cmp.w 2(a0),d5; bne nottaken; tst.w 4(a0); bmi taken
_PX_TRIGGER_HEAD = (12, 1)              # move.w 8(a2),d4
# The three (tst-or-cmpi, bne, [store]) checks always run all three regardless of which one matches
# (the ROM's own three independent tests, not a mutually-exclusive dispatch): their total cost is the
# same whichever of 0/1/2 TRIGGER_SELECTOR holds, so one constant covers every witnessed selector.
_PX_TRIGGER_SELECTOR = (12 + 8 + 12 + 16 + 10 + 16 + 10, 7)
_PX_TRIGGER_CMP_D5 = (8, 1)             # cmpi.w #$a,d5
_PX_TRIGGER_BONUS_TAKEN, _PX_TRIGGER_BONUS_NOTTAKEN = (10, 1), (8, 1)   # bne.b $f8d2 (taken: no bonus)
_PX_TRIGGER_ADDI = (8, 1)               # addi.w #$32,d4 (bonus only)
_PX_TRIGGER_SUB = (16, 1)               # sub.w d4,4(a0)
_PX_TRIGGER_CMP_FLOOR = (16, 1)         # cmpi.w #$ff38,4(a0)
_PX_TRIGGER_BGE_TAKEN, _PX_TRIGGER_BGE_NOTTAKEN = (10, 1), (8, 1)       # bge.b $f8e2 (taken: not cleared)
_PX_TRIGGER_CLR = (16, 1)               # clr.w 4(a0) (cleared only)
_PX_TRIGGER_ADDQ_A7 = (4, 1)            # addq.w #4,a7 -- the double return's own extra pop
_PX_TRIGGER_RTS = (16, 1)


def _proximity_resolve(read, sp, a1, a2):
    """Everything 00F828 does once entered -- the internal bsr into 00F86A, the 40-entry search, and
    either the matched entry's own continuation at 00F8A2 or the free-slot add -- relative to 00F828's
    OWN entry sp (``sp``, the value of a7 the instant its first instruction runs): a plain jsr from
    014084 and a direct gate at 00F828 itself look identical from here on.  Returns (cycles,
    instructions, writes, kind, search, resolved); kind is 'trigger' or 'added' -- 'pool-full' raises
    here, the one sub-arm no recording has reached through either caller.  ``a2`` is 00F8A2's own
    caller-record pointer (the standalone gate's own entry a2; hazard_tick's own a1, since it copies
    a1 into a2 at its own head before ever reaching this call).
    """
    from .game import hazard
    search = hazard.proximity_search(read, a1)
    cycles, instructions = _PX_BSR
    c, i = _PX_HASH_HEAD
    cycles += c
    instructions += i
    positions = search['positions']
    costs = {'miss': (_PX_MISS_MID, _PX_MISS_LAST), 'close': (_PX_CLOSE_MID, _PX_CLOSE_LAST),
            'stale': (_PX_STALE_MID, _PX_STALE_LAST)}
    # The internal bsr.w $f86a's own return address, pushed once and never popped by anything else on
    # the 'added' path (dead stack scratch by the time 00F828 itself returns) but overwritten by the
    # trigger continuation's own movem-equivalent word stores on that path -- a real write either way.
    writes = list(_bytes((sp - 4) & 0xFFFFFF, 0x00F82C, 4))

    if search['arm'] == 'trigger':
        # 00F8A2 onward: the matched entry's own continuation, returning past BOTH this activation's
        # own frame and 00F828's (a deliberate double return, docs/gods/STATUS.md); every position
        # before the match costs the same as 'stale' (matched neither the key nor an earlier one, or
        # matched the key but was still stale) -- MID never LAST, since the match itself ends the
        # search early rather than the loop's own dbra expiring.
        for kind in positions[:-1]:
            c, i = costs[kind][0]
            cycles += c
            instructions += i
        c, i = _PX_TRIGGER_FOUND
        cycles += c
        instructions += i
        entry_base = (hazard.PROXIMITY_TABLE + hazard.PROXIMITY_STRIDE * search['index']) & 0xFFFFFFFF
        trigger = hazard.proximity_trigger(read, a2, entry_base)
        if trigger['arm'] == 'unrecovered':
            raise UnsupportedCandidate(
                f"proximity trigger selector {trigger['selector']} not witnessed by a recording")
        c, i = _add(_PX_TRIGGER_HEAD, _PX_TRIGGER_SELECTOR, _PX_TRIGGER_CMP_D5)
        cycles += c
        instructions += i
        c, i = _PX_TRIGGER_BONUS_NOTTAKEN if trigger['bonus'] else _PX_TRIGGER_BONUS_TAKEN
        cycles += c
        instructions += i
        if trigger['bonus']:
            c, i = _PX_TRIGGER_ADDI
            cycles += c
            instructions += i
        c, i = _add(_PX_TRIGGER_SUB, _PX_TRIGGER_CMP_FLOOR)
        cycles += c
        instructions += i
        c, i = _PX_TRIGGER_BGE_NOTTAKEN if trigger['cleared'] else _PX_TRIGGER_BGE_TAKEN
        cycles += c
        instructions += i
        if trigger['cleared']:
            c, i = _PX_TRIGGER_CLR
            cycles += c
            instructions += i
        c, i = _add(_PX_TRIGGER_ADDQ_A7, _PX_TRIGGER_RTS)
        cycles += c
        instructions += i
        writes.extend(pair for address, (value, size) in trigger['stores'].items() for pair in _bytes(address, value, size))
        return cycles, instructions, writes, 'trigger', search, trigger

    for index, kind in enumerate(positions):
        mid, last = costs[kind]
        c, i = last if index == len(positions) - 1 else mid
        cycles += c
        instructions += i
    c, i = _PX_SEARCH_RTS
    cycles += c
    instructions += i
    c, i = _PX_OWN_HEAD
    cycles += c
    instructions += i
    added = hazard.proximity_add(read, search['offset'], search['d4'], search['d5'])
    add_positions = added['positions']
    for index, kind in enumerate(add_positions):
        if kind == 'free':
            c, i = _PX_FREE
        else:
            c, i = _PX_OCC_LAST if index == len(add_positions) - 1 else _PX_OCC_MID
        cycles += c
        instructions += i
    if added['arm'] == 'pool-full':
        raise UnsupportedCandidate('proximity pool-full arm is not witnessed by a recording')
    for c, i in (_PX_ADD_KEY, _PX_ADD_WRITE, _PX_ADD_TIMER, _PX_ADD_COUNTER, _PX_ADD_FLAG, _PX_ADD_RTS):
        cycles += c
        instructions += i
    writes.extend(pair for address, (value, size) in added['stores'].items() for pair in _bytes(address, value, size))
    return cycles, instructions, writes, 'added', search, added


def proximity_plan(machine, registers):
    """00F828: the proximity table search-and-add, including its own 'trigger' continuation
    (00F8A2 onward, game.hazard.proximity_trigger); only 'pool-full' still declines, unwitnessed."""
    from .game import hazard
    if registers['pc'] != PROXIMITY_ENTRY:
        raise UnsupportedCandidate('proximity planner needs the machine parked at 00F828')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    a1 = registers['a1'] & 0xFFFFFFFF
    a2 = registers['a2'] & 0xFFFFFFFF
    read = _reader(machine)
    cycles, instructions, writes, kind, search, resolved = _proximity_resolve(read, sp, a1, a2)

    if kind == 'trigger':
        trigger = resolved
        entry_base = (hazard.PROXIMITY_TABLE + hazard.PROXIMITY_STRIDE * search['index']) & 0xFFFFFFFF
        # cmpi.w #$ff38,4(a0) is the last N/Z/V/C setter (CMP, X unaffected); ADDQ to An and RTS
        # never touch flags at all, so X survives from the search's OWN head instead -- the last
        # X-affecting instruction on every path into this arm is 00F86A's own lsr.l #3,d5 (the key's
        # own row half), unconditional and before any branch, so it does not depend on the arm at all.
        timer_before = read((entry_base + 4) & 0xFFFFFF, 2)
        pre_shift_d5 = (a1 - hazard.GRID_TABLE) & 0x00FFFF80
        x_bit = 0x10 if (pre_shift_d5 >> 2) & 1 else 0
        floor_word = hazard.TRIGGER_FLOOR & 0xFFFF
        if trigger['cleared']:
            # clr.w 4(a0) is the LAST flag-setter when the decrement clears: N=0/Z=1/V=0/C=0 always
            # (CLR never depends on the value it clears), X unaffected.
            exit_sr = 0x04 | x_bit
        else:
            exit_sr = (_cmp_sr(sr, timer_before, floor_word, 2) & ~0x10) | x_bit
        d6_final = (0x27 - (len(search['positions']) - 1)) & 0xFFFF
        # move.l a1,d4 then subi.l #$ffff885e,d4 (00F86A's own head, unconditional) sets d4 to the
        # key's own long OFFSET, not the caller's own d4 -- and since a1 and GRID_TABLE share the same
        # 0xFFFFxxxx convention, that subtraction's own upper half is always 0 by construction (the
        # same reason search['offset']'s upper half is always 0), not a per-fixture coincidence; only
        # 00F8A2's own word move (00F8A6-C4) and this arm's own decrement ever touch the low half again.
        exit_registers = {'d4': (search['offset'] & 0xFFFF0000) | trigger['decrement'],
                          'd5': (search['d5'] & 0xFFFF0000) | trigger['active'],
                          # moveq #$27,d6 (00F888, unconditional) sign-extends into the WHOLE register,
                          # wiping any upper half the caller left: no entry-value preservation here.
                          'd6': d6_final,
                          'a0': entry_base, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                          'pc': _return(machine, sp), 'sr': exit_sr}
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(writes),
                          registers=exit_registers, last_pc=PROXIMITY_TRIGGER_LAST_PC)

    added = resolved
    slot_base = (hazard.PROXIMITY_TABLE + hazard.PROXIMITY_STRIDE * added['index']) & 0xFFFFFFFF
    counter_before = added['counter_before']
    exit_sr = _add_sr(sr, counter_before, 1, 2)
    # d4's word ops (andi.w/lsl.w) preserve whatever upper half the long subtract left; d5 is all
    # long ops (andi.l/lsr.l), so its exit value is the full 32-bit result, no upper half to keep.
    exit_registers = {'d4': (search['offset'] & 0xFFFF0000) | search['d4'], 'd5': search['d5'] & 0xFFFFFFFF,
                      'd6': (registers['d6'] & 0xFFFF0000) | 0xFFFF,
                      'a0': (slot_base + 4) & 0xFFFFFFFF, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                      'pc': _return(machine, sp), 'sr': exit_sr}
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(writes), registers=exit_registers,
                      last_pc=PROXIMITY_ADD_LAST_PC)


# --- 013264: the pickup award (game/pickups.py: collect) -----------------------
#
# A leaf over the pickup grid byte A0 points past: the code ranges into a
# group table, the group's active id selects an item record through the ROM
# table at 012D04, and the record's value is awarded.  Cost from the tracer
# (artifacts/gods/evidence/census-013264-*), per fragment (cycles,
# instructions); the fragments (group, bonus, cue, consume) are independent
# straight-line pieces, each witnessed, and compose.
PICKUP_AWARD_ENTRY = 0x013264
_PA_HEAD = (36, 4)                                    # move.l a1,-(a7); move.b -1(a0),d3; ext.w; bmi not taken
_PA_GROUP = {0: (26, 3), 1: (58, 7), 2: (72, 9)}      # lea/cmpi/ble chains selecting the group table
_PA_COMMON = (102, 10)                                # subq; asl; move.w (a0),d4; add; add; lea; movea.l (a1,d4.w); move.w 8(a1),AWARD; move.w NOW,d5; sub.w MARK,d5
_PA_BONUS = {True: (48, 4), False: (8, 1)}            # bgt taken; asr.w #3,d5; add.w d5,AWARD; bra  /  bgt not taken
_PA_CUE = {True: (36, 3), False: (22, 2)}             # tst.w SOUND_ON; beq not taken; move.w #$38,CUE  /  beq taken
_PA_CONSUME = {True: (38, 3), False: (22, 2)}         # tst.b $49(a1); beq not taken; clr.w 2(a0,d3.w)  /  beq taken
_PA_TAIL = (32, 3)                                    # moveq #0,d4; movea.l (a7)+,a1; rts
_PA_SPECIAL = {-1: (102, 10), -2: (134, 14), -3: (126, 14)}   # the whole path for each special code (-2: sound off)
_PA_SPECIAL_SOUND_ON = (144, 15)                      # -2 with sound on: beq not taken, clr.w AWARD
_PA_LAST_PC = {'item': 0x0132CA, 'special-1': 0x0132DA, 'special-2': 0x0132FC, 'special-3': 0x01330A}


def pickup_award_plan(machine, registers):
    """013264: the award for the pickup code before A0; codes of -4 and below (and 0, beyond the slots) are declined."""
    from .game import pickups
    if registers['pc'] != PICKUP_AWARD_ENTRY:
        raise UnsupportedCandidate('pickup award planner needs the machine parked at 013264')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    read = _reader(machine)
    result = pickups.collect(read, registers['a0'] & 0xFFFFFF)
    arm, code = result['arm'], result['code']
    if arm == 'unrecovered':
        return _grid_inverse_award_plan(machine, registers, result, sp32, sr, sp)
    frame = ('pickup frame', sp - 4, 8)                                # the saved a1 and the caller's return slot
    high = lambda name: registers[name] & 0xFFFF0000
    exit_registers = {'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'd4': result['d4']}
    if arm == 'item':
        slot, table = result['slot'], result['table']
        if not 0 <= slot < pickups.GROUP_SIZE:
            raise UnsupportedCandidate(f'pickup code {code} addresses no slot of its group: not witnessed')
        spans = [frame, ('pickup award', pickups.AWARD, 2), ('pickup group table', table & 0xFFFFFF,
                                                               pickups.SLOT_BASE + pickups.SLOT_SIZE * pickups.GROUP_SIZE),
                 ('pickup item record', result['record'] & 0xFFFFFF, 0x50), ('pickup cue', pickups.SOUND_CUE, 2)]
        _spans_disjoint(spans)
        bonus, cue, consumed = result['bonus'], result['cue'], result['consumed']
        cost = _add(_PA_HEAD, _PA_GROUP[result['group']], _PA_COMMON, _PA_BONUS[bonus], _PA_CUE[cue],
                    _PA_CONSUME[consumed], _PA_TAIL)
        difference = result['time_difference'] & 0xFFFF
        if bonus:
            # X from add.w d5,AWARD (the carry of value + bonus); the asr before it set X too, the add wins.
            base = read((result['record'] + pickups.ITEM_VALUE) & 0xFFFFFF, 2)
            x = _add_sr(sr, base, (result['time_difference'] >> 3) & 0xFFFF, 2) & 0x10
            d5 = high('d5') | ((result['time_difference'] >> 3) & 0xFFFF)
        else:
            # X from sub.w MARK,d5: the borrow of NOW - MARK.
            x = _cmp_sr(sr, read(pickups.TIME_NOW, 2), read(pickups.TIME_MARK, 2), 2) & 0x01
            x = 0x10 if x else 0
            d5 = high('d5') | difference
        exit_registers.update(d3=high('d3') | ((slot * pickups.SLOT_SIZE) & 0xFFFF), d5=d5, a0=table)
    else:
        _spans_disjoint([frame, ('pickup award', pickups.AWARD, 2)])
        sound_on = bool(read(pickups.SOUND_ON, 2))
        cost = _PA_SPECIAL_SOUND_ON if (arm == 'special-2' and sound_on) else _PA_SPECIAL[code]
        # The addq.w #1,d3 chain ends with -1 + 1: X (and C) set by that last carry.
        x = 0x10
        exit_registers.update(d3=high('d3'))
    # moveq #n,d4 is the last N/Z/V/C setter: Z for 0, nothing for 1; X as derived.
    exit_registers['sr'] = (sr & ~0x1F) | x | (0x04 if result['d4'] == 0 else 0)
    writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    writes = _bytes(sp - 4, registers['a1'], 4) + writes
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers,
                      last_pc=_PA_LAST_PC[arm])


# --- 013316: the grid inverse and debris burst (game/pickups.py: grid_inverse_award) ---
#
# 013264's own code -4-and-below cascade (BIG_VALUE awarded, matching special-2/-3's own shape)
# falls straight through into 013316 -- no separate call, so no separate gate (013316 has no other
# caller): the composition owns it the way 00BA8E owns its own callees.  Cost fragments from the
# tracer (artifacts/gods/evidence/census-013264-* for the cascade prefix, census-013316 for the rest).
GRID_INVERSE_LAST_PC = 0x0134A8
_GI_CASCADE = (80, 10)                  # push a1; ext.w/bmi taken; three (addq;bmi taken) tests
_GI_AWARD = (16 + 4, 2)                 # move.w #$2710,AWARD; moveq #0,d4
_GI_POP_A1 = (12, 1)                    # movea.l (a7)+,a1 (013264's own frame; a1 is reused right after)
_GI_HEAD = (4 + 16 + 162 + 4 + 12 + 4 + 12 + 12 + 12, 9)   # move.l a0,d0; subi.l; divs.w; move.w; asl.w;
                                                            # swap; asl.w; add.w x2
_GI_TST_SOUND = (12, 1)
_GI_BEQ_SOUND_TAKEN = (10, 1)           # word branch: sound off, the only witnessed arm
_GI_RATE_TST = (12, 1)                  # tst.w DEBRIS_RATE_FLAG
_GI_RATE_BEQ_NOTTAKEN = (8, 1)          # byte: EF5E != 0 (always, in every recording)
_GI_RATE_CMPI = (16, 1)                 # cmpi.w #$be,DEBRIS_RATE_COUNTER
_GI_RATE_BGE_NOTTAKEN = (8, 1)          # byte: under the limit (always, in every recording)
_GI_POOL_SETUP = (12 + 8 + 32 + 4 + 4, 5)   # lea a0; lea a1; movem push d2-d3/d7; moveq #7,d7; moveq #$4f,d2
_GI_SKIP = (8 + 8 + 4 + 10, 4)          # tst.w (a0); bmi.b not taken; addq.w #6,a0; dbra taken
_GI_FOUND_TEST = (8 + 10, 2)            # tst.w (a0); bmi.b taken
_GI_FILL_HEAD = (8 + 8 + 4, 3)          # move.w d0,(a0)+; move.w d1,(a0)+; move.w d0,d3
_GI_JSR_RANDOM = (20, 1)                # jsr $14a3c.l (014A3C's own cost added separately, via _NR_COST)
_GI_MASK = (8, 1)                       # andi.w #7,d0
_GI_RANGE_LOW = (8 + 10, 2)             # cmpi.w #6,d0; blt.b taken (0-5)
_GI_RANGE_HIGH = (8 + 8 + 4, 3)         # cmpi.w #6,d0; blt.b not taken; subq.w #6,d0 (6-7)
_GI_CUE = (8 + 12, 2)                   # addi.w #$58,d0; move.w d0,SOUND_CUE
_GI_RESTORE_X = (4, 1)                  # move.w d3,d0
_GI_TABLE_COPY = (12, 1)                # move.w (a1)+,(a0)+
_GI_RATE_ARM_TST = (12, 1)              # tst.w DEBRIS_RATE_FLAG (per particle)
_GI_RATE_ARM_SKIP = (10, 1)             # bmi.b taken (always, in every recording: EF5E stays negative)
_GI_DBRA_TAKEN = (10, 1)
_GI_DBRA_LAST = (14, 1)
_GI_BRA_LAST = (10, 1)
_GI_TAIL = (36 + 16, 2)                 # movem.l (a7)+,d2-d3/d7; rts


def _grid_inverse_award_plan(machine, registers, result, sp32, sr, sp):
    """013316: the grid inverse and (sound off) debris burst 013264's own -4-and-below cascade falls into."""
    from .game import pickups
    read = _reader(machine)
    # grid_inverse_position does the ROM's own full 32-bit subtraction (move.l a0,d0; subi.l), so this
    # needs A0's own full register form (0xFFFFxxxx), not the 24-bit address a plain RAM read would use.
    inverse = pickups.grid_inverse_award(read, registers['a0'] & 0xFFFFFFFF)
    arm = inverse['arm']
    cycles, instructions = _add(_GI_CASCADE, _GI_AWARD, _GI_POP_A1, _GI_HEAD, _GI_TST_SOUND)
    order = {}
    for address, (value, size) in result['stores'].items():
        for a, b in _bytes(address, value, size):
            order[a] = b
    _ram_span('pickup award frame (the -4-and-below cascade)', sp - 4, 4)
    _pk_push(order, sp, [registers['a1']])

    if arm == 'grid-code':
        raise UnsupportedCandidate('grid inverse award grid-code (sound-on) arm not witnessed by a recording')
    if arm != 'debris':
        raise UnsupportedCandidate(f'grid inverse award {arm} arm not witnessed by a recording')

    c, i = _add(_GI_BEQ_SOUND_TAKEN, _GI_RATE_TST, _GI_RATE_BEQ_NOTTAKEN, _GI_RATE_CMPI, _GI_RATE_BGE_NOTTAKEN,
               _GI_POOL_SETUP)
    cycles += c
    instructions += i
    _ram_span('grid inverse debris frame', sp - 12, 12)
    # d3 here is 013264's own cascade-modified value (ext.w then three addq.w #1 = code+3), not the
    # caller's own entry d3: the movem push happens after the cascade already overwrote it.
    cascade_d3 = (registers['d3'] & 0xFFFF0000) | ((result['code'] + 3) & 0xFFFF)
    _pk_push(order, sp, [registers['d2'], cascade_d3, registers['d7']])

    particles = inverse['particles']
    for slot, particle in enumerate(particles):
        c, i = _add(*([_GI_SKIP] * particle['skipped']))
        cycles += c
        instructions += i
        c, i = _add(_GI_FOUND_TEST, _GI_FILL_HEAD, _GI_JSR_RANDOM)
        cycles += c
        instructions += i
        # jsr 014a3c's own return address, then its own move.l a0,-(a7) -- a0 has already advanced by
        # 4 (the two word writes just above) by the time of this call.  The stack depth is the same
        # every iteration, so each particle's push overwrites the previous one's, exactly as real
        # memory ends the activation with only the LAST particle's values here.
        _pk_push(order, sp - 12, [0x0134B6])
        _pk_push(order, sp - 16, [(particle['address'] + 4) & 0xFFFFFFFF])
        cycles, instructions = cycles + _NR_COST[0], instructions + _NR_COST[1]
        c, i = _add(_GI_MASK, _GI_RANGE_HIGH if particle['high_range'] else _GI_RANGE_LOW, _GI_CUE, _GI_RESTORE_X,
                   _GI_TABLE_COPY, _GI_RATE_ARM_TST, _GI_RATE_ARM_SKIP)
        cycles += c
        instructions += i
        last = slot == len(particles) - 1
        # Continuing (not the last particle): dbra d7 (outer, taken) falls into 0134A0, which is
        # ALSO the inner scan's own dbra d2 -- a second, separate dbra before the next slot's test.
        c, i = _add(_GI_DBRA_LAST, _GI_BRA_LAST) if last else _add(_GI_DBRA_TAKEN, _GI_DBRA_TAKEN)
        cycles += c
        instructions += i
    c, i = _GI_TAIL
    cycles += c
    instructions += i

    for address, (value, size) in inverse['stores'].items():
        for a, b in _bytes(address, value, size):
            order[a] = b
    last_particle = particles[-1]
    x_bit = _add_sr(sr, last_particle['masked'] - (6 if last_particle['high_range'] else 0), 0x58, 2) & 0x10
    ef5e = read(pickups.DEBRIS_RATE_FLAG, 2)
    exit_sr = (_logic_sr(sr, ef5e, 2) & ~0x10) | x_bit
    # d0's own upper half never gets touched by any .W op after the divs.w/swap that first placed the
    # (unshifted) row quotient there; it is d0's own state all the way to the exit.
    offset = pickups._signed_long((registers['a0'] - pickups.PICKUP_GRID) & 0xFFFFFFFF)
    row_quotient, _ = pickups._truncating_divmod(offset, pickups.PICKUP_GRID_ROW)
    # d3: the cascade's own ext.w (byte-to-word only: the upper half survives from entry) then three
    # addq.w #1 -- code+3, which for every witnessed code (-4) is -1.  d4 is the cascade's own moveq #0.
    exit_registers = {'d0': ((row_quotient & 0xFFFF) << 16) | inverse['x'],
                      'd1': (registers['d1'] & 0xFFFF0000) | inverse['y'],
                      'd3': (registers['d3'] & 0xFFFF0000) | ((result['code'] + 3) & 0xFFFF), 'd4': 0,
                      'a0': (last_particle['address'] + 6) & 0xFFFFFFFF,
                      'a1': (pickups.DEBRIS_TABLE + 2 * pickups.DEBRIS_PARTICLES) & 0xFFFFFFFF,
                      'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr}
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()), registers=exit_registers,
                      last_pc=GRID_INVERSE_LAST_PC)


def _grid_inverse_debris_cost(inverse):
    """013316's own cost only (013264's own cascade-to-BIG_VALUE prefix is _pickup_award_cost's own,
    added separately): reused by pickup_check_plan's own composition, where 013316 has no separate
    call site of its own (013264's own cascade falls straight through, the way it does when 013264
    is gated directly)."""
    if inverse['arm'] != 'debris':
        raise UnsupportedCandidate(f"grid inverse award {inverse['arm']} arm not witnessed by a recording")
    cycles, instructions = _add(_GI_HEAD, _GI_TST_SOUND, _GI_BEQ_SOUND_TAKEN, _GI_RATE_TST, _GI_RATE_BEQ_NOTTAKEN,
                                _GI_RATE_CMPI, _GI_RATE_BGE_NOTTAKEN, _GI_POOL_SETUP)
    particles = inverse['particles']
    for slot, particle in enumerate(particles):
        c, i = _add(*([_GI_SKIP] * particle['skipped']))
        cycles += c
        instructions += i
        c, i = _add(_GI_FOUND_TEST, _GI_FILL_HEAD, _GI_JSR_RANDOM)
        cycles += c
        instructions += i
        cycles, instructions = cycles + _NR_COST[0], instructions + _NR_COST[1]
        c, i = _add(_GI_MASK, _GI_RANGE_HIGH if particle['high_range'] else _GI_RANGE_LOW, _GI_CUE, _GI_RESTORE_X,
                   _GI_TABLE_COPY, _GI_RATE_ARM_TST, _GI_RATE_ARM_SKIP)
        cycles += c
        instructions += i
        last = slot == len(particles) - 1
        c, i = _add(_GI_DBRA_LAST, _GI_BRA_LAST) if last else _add(_GI_DBRA_TAKEN, _GI_DBRA_TAKEN)
        cycles += c
        instructions += i
    c, i = _GI_TAIL
    cycles += c
    instructions += i
    return cycles, instructions


# --- 014A3C: the next-random draw (game/effects.py: next_random) ------------
#
# A trivial RAM-only leaf, no branch: called 3,971 times / 34,904 frames from
# many sites (only two of them the pickup check's own found-effect
# composition, game/pickups.py: pickup_check).  Cost from the tracer
# (artifacts/gods/evidence/census-014A3C): fixed, since there is no branch.
NEXT_RANDOM_ENTRY, NEXT_RANDOM_LAST_PC = 0x014A3C, 0x014A56
_NR_COST = (110, 8)


def next_random_plan(machine, registers):
    """014A3C: draw one word from the wrapping random table and advance the cursor."""
    from .game import effects
    if registers['pc'] != NEXT_RANDOM_ENTRY:
        raise UnsupportedCandidate('next random planner needs the machine parked at 014A3C')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    result = effects.next_random(_reader(machine))
    new_cursor = result['stores'][effects.RANDOM_CURSOR & 0xFFFFFF][0]
    writes = _bytes(sp - 4, registers['a0'], 4)
    writes += tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    # andi.w #$1ff,RANDOM_CURSOR is the last flag-setter: the cursor's own new value, not the drawn word.
    return AtomicPlan(cycles=_NR_COST[0], instructions=_NR_COST[1], writes=writes,
                      registers={'d0': (registers['d0'] & 0xFFFF0000) | result['value'], 'a0': registers['a0'],
                                 'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp),
                                 'sr': _logic_sr(sr, new_cursor, 2)},
                      last_pc=NEXT_RANDOM_LAST_PC)


# --- 00932C: the effect pool add (game/hazard.py: effect_pool_add) ----------
#
# The general form of the pool fill hazard.py's own '_spawn' inlines with
# d2=d3=0; called 452 times / 34,904 frames over this history, almost all
# from the hazard tick's own spawn arm (013F3A's own bsr, already owned
# inline by hazard_tick_plan) and twice from the pickup check's own
# found-effect composition (00BA8E, game/pickups.py: pickup_check).  Cost
# from the tracer (artifacts/gods/evidence/census-00932C), per fragment:
# the scan is bounded by the pool's own 20 slots (the same shape 0018C8's
# cache scan and 00F828's table search share), and the pool-full arm (all
# 20 occupied) is itself witnessed (46/452 occurrences).
EFFECT_POOL_ADD_ENTRY, EFFECT_POOL_ADD_LAST_PC = 0x00932C, 0x009368
EFFECT_POOL_ADD_FULL_LAST_PC = 0x009348   # the pool-full arm has its own separate tail/rts, not shared
_EP_HEAD = (56, 3)                      # movem.l d0-d1/d4/a0,-(a7); lea.l POOL_BASE,a0; moveq #$13,d4
_EP_SKIP = (34, 4)                      # tst.w (a0); bmi.b not taken; lea.l $c(a0),a0; dbra taken
_EP_SKIP_LAST = (38, 4)                 # ... dbra not taken (expired): DBcc's own 14cy, not 10
_EP_FOUND_TEST = (18, 2)                # tst.w (a0); bmi.b taken
_EP_FILL = (96, 9)                      # clr.w; add.w x2; move.w x4; move.w #0; addq.w #1,POOL_COUNTER
_EP_TAIL = (60, 2)                      # movem.l (a7)+,d0-d1/d4/a0; rts


def effect_pool_add_plan(machine, registers):
    """00932C: fill the first free slot of the 20-entry effect pool; the pool-full arm is witnessed too."""
    from .game import hazard
    if registers['pc'] != EFFECT_POOL_ADD_ENTRY:
        raise UnsupportedCandidate('effect pool add planner needs the machine parked at 00932C')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    read = _reader(machine)
    result = hazard.effect_pool_add(read, registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF,
                                    registers['d2'] & 0xFFFF, registers['d3'] & 0xFFFF)
    frame = ('effect pool frame', sp - 16, 16)
    _ram_span(*frame)
    # d0/d1/d4/a0 are pushed then popped from this same frame, unconditionally: pure scratch.
    writes = (_bytes(sp - 16, registers['d0'], 4) + _bytes(sp - 12, registers['d1'], 4)
             + _bytes(sp - 8, registers['d4'], 4) + _bytes(sp - 4, registers['a0'], 4))
    exit_registers = {'d0': registers['d0'], 'd1': registers['d1'], 'd4': registers['d4'], 'a0': registers['a0'],
                      'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp)}
    if result['arm'] == 'full':
        last_index = hazard.POOL_COUNT - 1
        cycles, instructions = _add(_EP_HEAD, *([_EP_SKIP] * last_index), _EP_SKIP_LAST, _EP_TAIL)
        # The dbra chain sets no flags at all: the last flag-setter is the final slot's own tst.w.
        last_value = read(hazard.POOL_BASE + hazard.POOL_STRIDE * last_index, 2)
        exit_registers['sr'] = _logic_sr(sr, last_value, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                          last_pc=EFFECT_POOL_ADD_FULL_LAST_PC)
    index = result['index']
    _spans_disjoint([frame, ('effect pool slot', result['slot'] & 0xFFFFFF, hazard.POOL_STRIDE)])
    cycles, instructions = _add(_EP_HEAD, *([_EP_SKIP] * index), _EP_FOUND_TEST, _EP_FILL, _EP_TAIL)
    exit_registers['sr'] = _add_sr(sr, result['counter_before'], 1, 2)
    writes += tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes, registers=exit_registers,
                      last_pc=EFFECT_POOL_ADD_LAST_PC)


# --- 00BA8E: the pickup check (game/pickups.py: pickup_check) ---------------
#
# A composition: the already-recovered zone check (00BCCE) owned as a call
# (the shape 00462C's evaluator proved), then a two-axis box clamp bounding
# a scan of the pickup grid (the same "unrolled test count" shape 00FDB8's
# row scan and 0018C8's cache scan share), and on a hit the already-recovered
# pickup award (013264) owned as a call, then -- when the box's own residue
# exceeds a nonzero award -- an effect queued through two calls to the
# already-recovered random draw (014A3C) and one to the already-recovered
# effect pool add (00932C).  Cost fragments from the tracer
# (artifacts/gods/evidence/census-00BA8E-fresh), byte/word-branch timing
# confirmed on real fixtures throughout (68000 Bcc.b: taken 10, not taken 8;
# Bcc.w: taken 10, not taken 12; DBcc: taken 10, expired 14).
PICKUP_CHECK_ENTRY = 0x00BA8E
# AWARD_SCALE_LEVEL (00BBEA onward, game.pickups._scaled_box_result): every real occurrence across all
# eight recordings reads 1 (104 occurrences on 7251bbd0ecf7 alone, 0 on the other seven) -- a fresh gate
# scan at the tst.w instruction itself, not the 32/400-class census (the arm's own path signature never
# survived the box/scan diversity's own class budget on any node).  Any other level declines.
WITNESSED_SCALE_LEVELS = {1}
PICKUP_CHECK_ZONE_CUE_LAST_PC = 0x00BAE2      # the sound-off arm's own rts
PICKUP_CHECK_ZONE_CUE_SOUND_ON_LAST_PC = 0x00BADA   # the sound-on arm has its OWN separate rts
PICKUP_CHECK_CLEAN_LAST_PC = 0x00BBCA
PICKUP_CHECK_SOUND_LAST_PC = 0x00BC42
PICKUP_CHECK_BARE_LAST_PC = 0x00BC4C
PICKUP_CHECK_EFFECT_LAST_PC = 0x00BCCC

_PK_ZONE_CALL = (18, 1)                 # bsr.w $bcce (00BCCE's own cost is added separately, via _zone_check_cost)
_PK_TST_D2 = (4, 1)                     # tst.w d2
_PK_BMI_D2_TAKEN, _PK_BMI_D2_NOTTAKEN = (10, 1), (8, 1)      # bmi.b $bace

_PK_CUE_TST = (12, 1)                   # tst.w CHECK_SOUND_ON
_PK_CUE_BEQ_TAKEN, _PK_CUE_BEQ_NOTTAKEN = (10, 1), (8, 1)    # beq.b (sound-off arm taken)
_PK_CUE_STORE = (16, 1)                 # move.w #imm,CHECK_SOUND_CUE
_PK_CUE_RTS = (16, 1)
_PK_CUE_BRA = (10, 1)                   # bra.b $bc38 (the sound-on arm's own skip past the sound-off store)
_PK_CUE_MOVEQ = (4, 1)                  # moveq #$ff,d2 (found-sound's own tail; N=1, but never touches X)

_PK_BOX_COPY = (28, 1)                  # move.l HALF_WIDTH,BOX_COPY_X (both words at once)
_PK_PUSH_FRAME = (72, 1)                # movem.l d0-d7,-(a7)
_PK_ROUND_BOTH = (48, 6)                # sub/addq/andi for both d0 and d1, interleaved

_AC_TEST = (8, 1)                       # cmpi.w #$fff0,Dn
_AC_BGT_TAKEN, _AC_BGT_NOTTAKEN = (10, 1), (8, 1)            # bgt.b (byte: near test)
_AC_NEAR_HEAD = (24, 2)                 # addi.w #$10,Dn; add.w Dn,size
_AC_NEAR_TAIL = (14, 2)                 # moveq #$f0,Dn; bra.b (continuing only)
_AC_FAR_HEAD = (24, 3)                  # move.w size,d4; add.w Dn,d4; cmpi.w #imm,(d4 or Dn)
_AC_FAR_BLT_TAKEN, _AC_FAR_BLT_NOTTAKEN = (10, 1), (8, 1)    # blt.b (byte: in-range arm taken)
_AC_FARCLAMP_HEAD = (24, 2)             # subi.w #imm,d4; sub.w d4,size
_AC_BMI_TAKEN, _AC_BMI_NOTTAKEN = (10, 1), (12, 1)           # bmi.w $bbc6 (word: far target)
_AC_BEQ_TAKEN, _AC_BEQ_NOTTAKEN = (10, 1), (12, 1)           # beq.w $bbc6

_PK_BAIL_TAIL = (76 + 16, 2)            # movem.l (a7)+,d0-d7; rts (no a0-a2 frame: the scan was never entered)

_PK_APPEND_TST = (12, 1)                # tst.w ARRAY_GATE
_PK_APPEND_SKIP = (10, 1)               # bmi.b taken (append skipped)
_PK_APPEND_NOTTAKEN = (8, 1)            # bmi.b not taken (appending)
_PK_APPEND_MOVEA = (16, 1)              # movea.l ARRAY_CURSOR,a4
_PK_APPEND_MOVE_W = (24, 3)             # move.w Dn,(a4)+ x3 (d0, d1, d2): 8cy each
_PK_APPEND_ADDQ_L = (24, 1)             # addq.l #6,ARRAY_CURSOR
_PK_APPEND_ADDQ_W = (16, 1)             # addq.w #1,ARRAY_COUNT

_PK_SCAN_PUSH = (32, 1)                 # movem.l a0-a2,-(a7)
_PK_SCAN_BASE = (8 + 8 + 12 + 8 + 8 + 4 + 8 + 4 + 8, 9)      # lea a2; lea a0; asr d0; adda d0; andi d1; add d1,d1;
                                                              # adda d1; add d1,d1; adda d1
_PK_SCAN_ROWS_HEAD = (12 + 12 + 4, 3)   # move.w size_y,d7; asr.w #3,d7; subq.w #1,d7
_PK_SCAN_BPL_TAKEN, _PK_SCAN_BPL_NOTTAKEN = (10, 1), (8, 1)  # bpl.b (byte)
_PK_SCAN_ROWS_FORCE = (4, 1)            # moveq #0,d7 (only when forced)
_PK_SCAN_COLS_HEAD = (12 + 12 + 4, 3)   # move.w size_x,d6; asr.w #3,d6; subq.w #1,d6
_PK_SCAN_BMI_TAKEN, _PK_SCAN_BMI_NOTTAKEN = (10, 1), (8, 1)  # bmi.b (byte)
_PK_SCAN_BNE_TAKEN, _PK_SCAN_BNE_NOTTAKEN = (10, 1), (8, 1)  # bne.b (byte)
_PK_SCAN_COLS_FORCE = (4, 1)            # moveq #1,d6 (only when forced)
_PK_SCAN_TABLE = (8 + 4 + 4 + 4 + 4 + 8, 6)   # lea a1; moveq #$30,d5; sub d6,d5; add d6,d6 x2; suba d6,a1

_PK_ROW_JMP = (8, 1)                    # jmp (a1)
_PK_TEST_NOTFOUND = (16, 2)             # tst.b (a0)+; bne.b not taken
_PK_TEST_FOUND = (18, 2)                # tst.b (a0)+; bne.b taken
_PK_ROW_ADVANCE = (8, 1)                # adda.w d5,a0
_PK_DBRA_TAKEN, _PK_DBRA_LAST = (10, 1), (14, 1)

_PK_EXHAUSTED_TAIL = (36 + 76 + 16, 3)  # movem.l (a7)+,a0-a2; movem.l (a7)+,d0-d7; rts

_PK_PUSH_D2 = (12, 1)                   # move.l d2,-(a7)
_PK_JSR_AWARD = (20, 1)                 # jsr $13264.l (013264's own cost added separately, via _pickup_award_cost)
_PK_POP_D2 = (12, 1)                    # move.l (a7)+,d2
_PK_READ_AWARD = (12, 1)                # move.w AWARD,d3
_PK_TST_D4 = (4, 1)                     # tst.w d4
_PK_BEQ_D4_TAKEN, _PK_BEQ_D4_NOTTAKEN = (10, 1), (8, 1)             # beq.b $bbea (d4==0 vs the special-1 arm)
_PK_SPECIAL_TIMER_SUB = (16, 1)         # sub.w d2, SPECIAL_TIMER (special-1's own extra decrement, 00BBDE)
_PK_BPL_TIMER_TAKEN, _PK_BPL_TIMER_NOTTAKEN = (10, 1), (8, 1)       # bpl.b $bbea (00BBE2)
_PK_TST_EF46 = (12, 1)                  # tst.w AWARD_SCALE_LEVEL
_PK_BEQ_EF46_TAKEN = (10, 1)            # beq.b (level==0: the unscaled sub.w d3,d2 tail)
_PK_BEQ_EF46_NOTTAKEN = (8, 1)          # beq.b not taken (level!=0: the scaled tail, 00BBF0 onward)
_PK_SUB_D3_D2 = (4, 1)                  # sub.w d3,d2

# --- the AWARD_SCALE_LEVEL != 0 tail (00BBF0-00BC1C), game.pickups._scaled_box_result -------------
_PK_SCALE_PUSH_D2 = (8, 1)              # move.w d2,-(a7)                              (00BBF0)
_PK_SCALE_SUB_D3_D2 = (4, 1)            # sub.w d3,d2                                  (00BBF2)
_PK_SCALE_MOVEQ3 = (4, 1)               # moveq #3,d5                                  (00BBF4)
_PK_SCALE_SUB_LEVEL = (12, 1)           # sub.w AWARD_SCALE_LEVEL,d5                   (00BBF6)
_PK_SCALE_BPL_TAKEN, _PK_SCALE_BPL_NOTTAKEN = (10, 1), (8, 1)   # bpl.b                (00BBFA)
_PK_SCALE_MOVEQ0 = (4, 1)               # moveq #0,d5 (only when bpl not taken)        (00BBFC)
_PK_SCALE_PUSH_D3 = (8, 1)              # move.w d3,-(a7)                              (00BBFE)
_PK_SCALE_CMP_POP = (8, 1)              # cmp.w (a7)+,d3                               (00BC02)
_PK_SCALE_BNE_TAKEN, _PK_SCALE_BNE_NOTTAKEN = (10, 1), (8, 1)   # bne.b                (00BC04)
# move.w d3,d5; lsr.w #1,d3; sub.w d3,d5; asr.w #1,d5; add.w d5,d3 (only when bne not taken)
_PK_SCALE_CORRECT = (4 + 8 + 4 + 8 + 4, 5)                                            # (00BC06-00BC0E)
_PK_SCALE_POP_D5 = (8, 1)               # move.w (a7)+,d5                              (00BC10)
_PK_SCALE_ADD_D3_D2 = (4, 1)            # add.w d3,d2                                  (00BC12)
_PK_SCALE_BMI_TAKEN, _PK_SCALE_BMI_NOTTAKEN = (10, 1), (8, 1)   # bmi.b                (00BC14)
_PK_SCALE_BEQ_TAKEN, _PK_SCALE_BEQ_NOTTAKEN = (10, 1), (8, 1)   # beq.b                (00BC16)
_PK_SCALE_SUB_D2_D5 = (4, 1)            # sub.w d2,d5 (positive branch only)           (00BC18)
_PK_SCALE_MOVE_D5_D3 = (4, 1)           # move.w d5,d3                                 (00BC1A)
_PK_SCALE_BRA = (10, 1)                 # bra.b $bc4e                                  (00BC1C)


def _pk_scale_lsr_cost(count):
    """68000 LSR.w Dx,Dy register-shift timing: 6+2n, n the count actually used (masked to 6 bits,
    as game.pickups._lsr_word applies it)."""
    return (6 + 2 * (count & 0x3F), 1)


def _pk_scale_cost(scaled):
    """The AWARD_SCALE_LEVEL != 0 tail's own cost (00BBEA-00BC1C), from ``scaled``
    (``game.pickups._scaled_box_result``'s own result: which branches were taken)."""
    cycles, instructions = _add(_PK_TST_EF46, _PK_BEQ_EF46_NOTTAKEN, _PK_SCALE_PUSH_D2, _PK_SCALE_SUB_D3_D2,
                                _PK_SCALE_MOVEQ3, _PK_SCALE_SUB_LEVEL)
    if scaled['bpl_taken']:
        c, i = _PK_SCALE_BPL_TAKEN
    else:
        c, i = _add(_PK_SCALE_BPL_NOTTAKEN, _PK_SCALE_MOVEQ0)
    cycles += c
    instructions += i
    c, i = _add(_PK_SCALE_PUSH_D3, _pk_scale_lsr_cost(scaled['shift']), _PK_SCALE_CMP_POP)
    cycles += c
    instructions += i
    if scaled['same']:
        c, i = _add(_PK_SCALE_BNE_NOTTAKEN, _PK_SCALE_CORRECT)
    else:
        c, i = _PK_SCALE_BNE_TAKEN
    cycles += c
    instructions += i
    c, i = _add(_PK_SCALE_POP_D5, _PK_SCALE_ADD_D3_D2)
    cycles += c
    instructions += i
    if scaled['branch'] == 'cue':
        if scaled['box_result_negative']:
            c, i = _PK_SCALE_BMI_TAKEN
        else:
            c, i = _add(_PK_SCALE_BMI_NOTTAKEN, _PK_SCALE_BEQ_TAKEN)
        return cycles + c, instructions + i
    c, i = _add(_PK_SCALE_BMI_NOTTAKEN, _PK_SCALE_BEQ_NOTTAKEN, _PK_SCALE_SUB_D2_D5, _PK_SCALE_MOVE_D5_D3,
               _PK_SCALE_BRA)
    return cycles + c, instructions + i
_PK_BMI_RESULT_TAKEN, _PK_BMI_RESULT_NOTTAKEN = (10, 1), (8, 1)     # bmi.b $bc24
_PK_BNE_RESULT_TAKEN, _PK_BNE_RESULT_NOTTAKEN = (10, 1), (8, 1)     # bne.b $bc4e
_PK_STORE_F3D4 = (12, 1)                # move.w d2,RESULT_WORD
_PK_TST_D3 = (4, 1)                     # tst.w d3
_PK_BEQ_D3_TAKEN, _PK_BEQ_D3_NOTTAKEN = (10, 1), (8, 1)             # beq.b $bc44 (d3==0: found-bare vs the effect chain)

_PK_EFFECT_RESTORE_A0A2 = (36, 1)       # movem.l (a7)+,a0-a2
_PK_EFFECT_PEEK_D2D3 = (28, 1)          # movem.l (a7),d2-d3 (peek, not pop)
_PK_EFFECT_HALF = (12 + 8 + 4, 3)       # move.w size,d4; asr.w #1,d4; add.w d4,Dn
_PK_EFFECT_MASK = (8, 1)                # andi.w #$fff0,d4
_PK_EFFECT_MASK_BNE, _PK_EFFECT_MASK_BNE_NOTTAKEN = (10, 1), (8, 1)  # bne.b (mask nonzero vs the default arm)
_PK_EFFECT_MASK_DEFAULT = (4, 1)        # moveq #$10,d4 (only when the mask collapsed to zero)
_PK_EFFECT_MASK_SUBQ = (4, 1)           # subq.w #1,d4
_PK_JSR_RANDOM = (20, 1)                # jsr $14a3c.l (014A3C's own cost added separately, via _NR_COST)
_PK_TST_DRAW = (4, 1)                   # tst.w d0
_PK_BMI_DRAW_TAKEN, _PK_BMI_DRAW_NOTTAKEN = (10, 1), (8, 1)  # bmi.b
_PK_DRAW_AND = (4, 1)                   # and.w d4,d0
_PK_DRAW_ADD = (4, 1)                   # add.w d0,Dn (positive arm)
_PK_DRAW_SUB = (4, 1)                   # sub.w d0,Dn (negative arm)
_PK_DRAW_BRA = (10, 1)                  # bra.b (positive arm only, skipping the negative arm's own code)
_PK_EFFECT_TAIL = (4 + 4 + 4 + 4 + 4 + 4 + 12 + 12, 8)       # subq d2 x2; move d2,d0; move d3,d1; clr d2; clr d3;
                                                              # sub F3EE,d0; sub F3F0,d1
_PK_JSR_POOL = (20, 1)                  # jsr $932c.l (00932C's own cost added separately, via _effect_pool_add_cost)
_PK_EFFECT_RESTORE_D0D7 = (76, 1)       # movem.l (a7)+,d0-d7
_PK_LOAD_D2 = (12, 1)                   # move.w RESULT_WORD,d2
_PK_RTS = (16, 1)


def _pk_axis_cost(clamp):
    """One axis's own (cycles, instructions), the cost twin of pickups._axis_clamp."""
    cycles, instructions = _add(_AC_TEST)
    if clamp['arm'] == 'near':
        c, i = _add(_AC_BGT_NOTTAKEN, _AC_NEAR_HEAD)
        cycles += c
        instructions += i
        if clamp['bail']:
            c, i = _AC_BMI_TAKEN if clamp['new_size'] & 0x8000 else _add(_AC_BMI_NOTTAKEN, _AC_BEQ_TAKEN)
            return cycles + c, instructions + i
        c, i = _add(_AC_BMI_NOTTAKEN, _AC_BEQ_NOTTAKEN, _AC_NEAR_TAIL)
        return cycles + c, instructions + i
    c, i = _add(_AC_BGT_TAKEN, _AC_FAR_HEAD)
    cycles += c
    instructions += i
    if clamp['arm'] == 'none':
        c, i = _AC_FAR_BLT_TAKEN
        return cycles + c, instructions + i
    c, i = _add(_AC_FAR_BLT_NOTTAKEN, _AC_FARCLAMP_HEAD)
    cycles += c
    instructions += i
    if clamp['bail']:
        c, i = _AC_BMI_TAKEN if clamp['new_size'] & 0x8000 else _add(_AC_BMI_NOTTAKEN, _AC_BEQ_TAKEN)
        return cycles + c, instructions + i
    c, i = _add(_AC_BMI_NOTTAKEN, _AC_BEQ_NOTTAKEN)
    return cycles + c, instructions + i


def _pk_scan_setup_cost(rows_shifted, cols_shifted):
    cycles, instructions = _add(_PK_SCAN_PUSH, _PK_SCAN_BASE, _PK_SCAN_ROWS_HEAD)
    rows_after_subq = rows_shifted - 1
    if rows_after_subq >= 0:
        c, i = _PK_SCAN_BPL_TAKEN
    else:
        c, i = _add(_PK_SCAN_BPL_NOTTAKEN, _PK_SCAN_ROWS_FORCE)
    cycles += c
    instructions += i
    c, i = _PK_SCAN_COLS_HEAD
    cycles += c
    instructions += i
    cols_after_subq = cols_shifted - 1
    if cols_after_subq < 0:
        c, i = _add(_PK_SCAN_BMI_TAKEN, _PK_SCAN_COLS_FORCE)
    elif cols_after_subq == 0:
        c, i = _add(_PK_SCAN_BMI_NOTTAKEN, _PK_SCAN_BNE_NOTTAKEN, _PK_SCAN_COLS_FORCE)
    else:
        c, i = _add(_PK_SCAN_BMI_NOTTAKEN, _PK_SCAN_BNE_TAKEN)
    cycles += c
    instructions += i
    c, i = _PK_SCAN_TABLE
    return cycles + c, instructions + i


def _pk_scan_walk_cost(rows, cols, scan):
    cycles, instructions = 0, 0
    complete_rows = scan['row'] if scan['found'] else rows
    for row in range(complete_rows):
        c, i = _PK_ROW_JMP
        cycles += c
        instructions += i
        c, i = _add(*([_PK_TEST_NOTFOUND] * cols))
        cycles += c
        instructions += i
        c, i = _PK_ROW_ADVANCE
        cycles += c
        instructions += i
        c, i = _PK_DBRA_TAKEN if row < rows - 1 else _PK_DBRA_LAST
        cycles += c
        instructions += i
    if scan['found']:
        c, i = _PK_ROW_JMP
        cycles += c
        instructions += i
        c, i = _add(*([_PK_TEST_NOTFOUND] * scan['col']), _PK_TEST_FOUND)
        cycles += c
        instructions += i
    return cycles, instructions


def _pickup_award_cost(read, collected):
    if collected['arm'] == 'item':
        return _add(_PA_HEAD, _PA_GROUP[collected['group']], _PA_COMMON, _PA_BONUS[collected['bonus']],
                   _PA_CUE[collected['cue']], _PA_CONSUME[collected['consumed']], _PA_TAIL)
    if collected['arm'] == 'unrecovered':
        # code -4 and below: 013264's own cascade to BIG_VALUE only -- the composition that calls this
        # (pickup_check_plan) adds 013316's own cost separately, via _grid_inverse_debris_cost, once it
        # knows whether the debris burst itself is witnessed for this occurrence.
        return _add(_GI_CASCADE, _GI_AWARD, _GI_POP_A1)
    from .game import pickups
    sound_on = bool(read(pickups.SOUND_ON, 2))
    if collected['arm'] == 'special-2' and sound_on:
        return _PA_SPECIAL_SOUND_ON
    return _PA_SPECIAL[collected['code']]


def _effect_pool_add_cost(added):
    from .game import hazard
    if added['arm'] == 'full':
        last_index = hazard.POOL_COUNT - 1
        return _add(_EP_HEAD, *([_EP_SKIP] * last_index), _EP_SKIP_LAST, _EP_TAIL)
    return _add(_EP_HEAD, *([_EP_SKIP] * added['index']), _EP_FOUND_TEST, _EP_FILL, _EP_TAIL)


def _pk_push(order, sp_top, values, size=4):
    """Write a movem-style push of ``values`` (a list of ints, one per pushed register) below
    ``sp_top``: the FIRST value lands at the lowest address of the frame (movem's own
    register-ascending order for ``-(An)``), matching ``_zone_frame_writes``'s convention.
    Last-write-wins per byte (later pushes at the same stack depth overwrite earlier ones, exactly
    as real memory ends this activation)."""
    span = size * len(values)
    for index, value in enumerate(values):
        for address, byte in _bytes(sp_top - span + size * index, value, size):
            order[address] = byte


def pickup_check_plan(machine, registers):
    """00BA8E: the pickup check; a composition over the already-recovered zone check, award, random draw and pool add.

    Every internal call (00BCCE, 013264, 014A3C x2, 00932C) pushes its own transient frame on the
    SAME stack the caller is using; later pushes at a stack depth a later call also uses overwrite
    the earlier one's bytes for good (nothing pops the ORIGINAL value back in) -- ``order`` accumulates
    every write in execution order so the last one at each address wins, matching the machine exactly.
    """
    from .game import pickups
    if registers['pc'] != PICKUP_CHECK_ENTRY:
        raise UnsupportedCandidate('pickup check planner needs the machine parked at 00BA8E')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    read = _reader(machine)
    result = pickups.pickup_check(read, registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF, registers['d2'] & 0xFFFF)
    arm = result['arm']
    zone_cost = _zone_check_cost(machine, result['zone'])
    cycles, instructions = _add(_PK_ZONE_CALL, zone_cost, _PK_TST_D2)
    order = {}
    for address, (value, size) in result['stores'].items():
        for a, b in _bytes(address, value, size):
            order[a] = b
    _ram_span('pickup check bsr return slot', sp - 4, 4)
    _pk_push(order, sp, [0x00BA92])
    _AXES = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7')
    if result['zone']['arm'] != 'held':
        _ram_span('zone check frame (inside the composition)', sp - 4 - 32, 32)
        _pk_push(order, sp - 4, [registers[name] for name in _AXES])

    if arm == 'zone-cue':
        c, i = _add(_PK_BMI_D2_TAKEN, _PK_CUE_TST)
        cycles += c
        instructions += i
        sound_on = read(pickups.CHECK_SOUND_ON, 2) != 0
        cue_value = pickups.ZONE_CUE_SOUND_ON if sound_on else pickups.ZONE_CUE_SOUND_OFF
        c, i = _PK_CUE_BEQ_NOTTAKEN if sound_on else _PK_CUE_BEQ_TAKEN
        cycles += c
        instructions += i
        c, i = _add(_PK_CUE_STORE, _PK_CUE_RTS)
        cycles += c
        instructions += i
        # D2 is already -1 here (zone_check's own moveq set it); the last flag-setter in THIS routine's
        # own code is move.w #imm,CHECK_SOUND_CUE (a positive constant: N=Z=V=C=0); X survives from
        # 00BCCE's own exit (nothing between the call and here touches it).
        x_bit = _zone_check_exit_x(sr, result['zone'])
        exit_sr = (_logic_sr(sr, cue_value, 2) & ~0x10) | x_bit
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'d2': 0xFFFFFFFF, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                                     'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=(PICKUP_CHECK_ZONE_CUE_SOUND_ON_LAST_PC if sound_on
                                   else PICKUP_CHECK_ZONE_CUE_LAST_PC))

    c, i = _add(_PK_BMI_D2_NOTTAKEN, _PK_BOX_COPY, _PK_PUSH_FRAME, _PK_ROUND_BOTH)
    cycles += c
    instructions += i
    y_cost = _pk_axis_cost(result['y_clamp'])
    cycles += y_cost[0]
    instructions += y_cost[1]
    _ram_span('pickup check frame', sp - 32, 32)
    _pk_push(order, sp, [registers[name] for name in _AXES])

    if result['y_clamp']['bail']:
        c, i = _PK_BAIL_TAIL
        cycles += c
        instructions += i
        clamp = result['y_clamp']
        exit_sr = (_add_sr if clamp['op'] == 'add' else _sub_sr)(sr, clamp['left'], clamp['right'], 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=PICKUP_CHECK_CLEAN_LAST_PC)

    # X's own clamp code (00BB00 onward) is only reached when Y did not bail.
    x_cost = _pk_axis_cost(result['x_clamp'])
    cycles += x_cost[0]
    instructions += x_cost[1]

    if result['x_clamp']['bail']:
        c, i = _PK_BAIL_TAIL
        cycles += c
        instructions += i
        clamp = result['x_clamp']
        exit_sr = (_add_sr if clamp['op'] == 'add' else _sub_sr)(sr, clamp['left'], clamp['right'], 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=PICKUP_CHECK_CLEAN_LAST_PC)

    if result['appended']:
        c, i = _add(_PK_APPEND_TST, _PK_APPEND_NOTTAKEN, _PK_APPEND_MOVEA, _PK_APPEND_MOVE_W,
                   _PK_APPEND_ADDQ_L, _PK_APPEND_ADDQ_W)
        # a4 is never touched again after this (the a0-a2 restores below don't include it).
        a4_exit = {'a4': (result['array_cursor'] + 6) & 0xFFFFFFFF}
    else:
        c, i = _add(_PK_APPEND_TST, _PK_APPEND_SKIP)
        a4_exit = {}
    cycles += c
    instructions += i

    # From here on (BB4E) the routine also pushes a0-a2 in their own 12-byte frame, just below the
    # d0-d7 frame; they are pure scratch too, restored (via movem pop) on every arm reached from here.
    _ram_span('pickup check scan frame', sp - 44, 12)
    _pk_push(order, sp - 32, [registers['a0'], registers['a1'], registers['a2']])

    c, i = _pk_scan_setup_cost(result['rows_shifted'], result['cols_shifted'])
    cycles += c
    instructions += i
    c, i = _pk_scan_walk_cost(result['rows'], result['cols'], result['scan'])
    cycles += c
    instructions += i

    # The scan table setup's own last flag-setter is "add.w d6,d6" (the second doubling, always run):
    # N/Z/V/C from that alone; X follows the same instruction (ADD sets X=C), so it flows unchanged
    # through every tst.b/bne/adda/dbra of the walk itself (none of which touch X).
    scan_x_bit = _add_sr(sr, result['cols'], result['cols'], 2) & 0x10

    if not result['scan']['found']:
        c, i = _PK_EXHAUSTED_TAIL
        cycles += c
        instructions += i
        last_value = result['scan']['last_value'] or 0
        exit_sr = (_logic_sr(sr, last_value, 1) & ~0x10) | scan_x_bit
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr,
                                     **a4_exit},
                          last_pc=PICKUP_CHECK_CLEAN_LAST_PC)

    if arm in ('found-special-timer', 'found-code-unrecovered'):
        raise UnsupportedCandidate(f'pickup check {arm} arm not witnessed by a recording')
    scaled = result.get('scaled')
    if scaled is not None and result['scale_level'] not in WITNESSED_SCALE_LEVELS:
        raise UnsupportedCandidate(
            f"pickup check award-scale level {result['scale_level']} not witnessed by a recording")

    collect_result = result['collect']
    c, i = _add(_PK_PUSH_D2, _PK_JSR_AWARD, _pickup_award_cost(read, collect_result), _PK_POP_D2, _PK_READ_AWARD,
               _PK_TST_D4)
    cycles += c
    instructions += i
    if collect_result['arm'] == 'unrecovered':
        c, i = _grid_inverse_debris_cost(result['inverse'])
        cycles += c
        instructions += i
    if collect_result['d4'] == 0:
        c, i = _PK_BEQ_D4_TAKEN
    else:
        # special-1's own extra step (00BBDE-00BBE2): SPECIAL_TIMER's own decrement already landed in
        # result['stores'] (seeded into order at the top of this function); only its cost and the two
        # branches belong here.  A negative result declines above (result['arm'] would be
        # 'found-special-timer'), so reaching this point means bpl.b was taken.
        c, i = _add(_PK_BEQ_D4_NOTTAKEN, _PK_SPECIAL_TIMER_SUB, _PK_BPL_TIMER_TAKEN)
    cycles += c
    instructions += i
    if scaled is None:
        c, i = _add(_PK_TST_EF46, _PK_BEQ_EF46_TAKEN, _PK_SUB_D3_D2)
    else:
        c, i = _pk_scale_cost(scaled)
    cycles += c
    instructions += i
    # a1 at this point is the SCAN's own jump-table entry address (set at 00BB84-00BB90), not the
    # caller's original a1: the scan overwrote it, and nothing restores it before this push.
    scan_a1 = (0x00BBBC - 4 * result['cols']) & 0xFFFFFFFF
    _ram_span('pickup check award call frame', sp - 56, 12)
    _pk_push(order, sp - 44, [registers['d2']])          # move.l d2,-(a7)
    _pk_push(order, sp - 48, [0x00BBD4])                 # jsr $13264.l's own return address
    _pk_push(order, sp - 52, [scan_a1])                  # 013264's own move.l a1,-(a7)
    if scaled is not None:
        # 00BBF0/00BBFE push d2 then d3 (both words), CHRONOLOGICALLY AFTER 013264's own call above
        # (whose "move.l d2,-(a7)" already wrote the same two addresses, sp-48..45, as one long): both
        # are popped again (00BC02/00BC10) but nothing overwrites the bytes afterward, so these two
        # later, real word writes are the ones that survive to the final RAM residue.
        _ram_span('pickup check award-scale transient frame', sp - 48, 4)
        for a, b in _bytes((sp - 46) & 0xFFFFFF, scaled['d2_orig'], 2):
            order[a] = b
        for a, b in _bytes((sp - 48) & 0xFFFFFF, scaled['d3_orig'], 2):
            order[a] = b
    # collect_result['stores'] is NOT re-applied here: result['stores'] (seeded into order at the top
    # of this function) already carries it, merged by pickup_check() in the ROM's own order -- 013264's
    # own award cue (SOUND_CUE=0x38) first, then this routine's own cue store (0x3C/0x4F) overwriting
    # it on the found-sound arm.  Re-applying it here would undo that overwrite (the bug the tree
    # divergence at fb408bc75597 frame 6840 traced to: FFFDF5 left 0x38 instead of 0x3C).

    if collect_result['arm'] == 'unrecovered':
        # A grid code of -4 or below: 013264's own cascade to BIG_VALUE (013314's own movea.l
        # (a7)+,a1 already popped the scan_a1 slot above) falls straight into 013316's own debris
        # burst (result['inverse'], already witnessed on its own merits through the direct 013264
        # gate) before this activation ever reaches tst.w d4 -- one activation of the same jsr.  Its
        # own transient frame (movem.l d2-d3/d7,-(a7), 12 bytes) lands at 013264's own entry sp
        # (AWARD_SP = sp-52: the fixed 32+12+4+4-byte frame this composition always has by the jsr),
        # reusing (and overwriting, exactly as the real stack does) the scan_a1 slot just pushed.
        # d2/d3 survive unchanged from 00BA8E's own entry to this point (confirmed on every witnessed
        # fixture), but d7 is the SCAN's own residual row counter (rows-1-row: the scan's own dbra,
        # not restored until 013316's own tail pops this same frame back).
        inverse = result['inverse']
        award_sp = sp - 52
        cascade_d3 = (registers['d3'] & 0xFFFF0000) | ((collect_result['code'] + 3) & 0xFFFF)
        scan_d7 = (registers['d7'] & 0xFFFF0000) | ((result['rows'] - 1 - result['scan']['row']) & 0xFFFF)
        _ram_span('pickup check code-unrecovered debris frame', award_sp - 12, 12)
        _pk_push(order, award_sp, [registers['d2'], cascade_d3, scan_d7])
        for particle in inverse['particles']:
            _ram_span('pickup check code-unrecovered debris random-call frame', award_sp - 20, 8)
            _pk_push(order, award_sp - 12, [0x0134B6])
            _pk_push(order, award_sp - 16, [(particle['address'] + 4) & 0xFFFFFFFF])
        # inverse['stores'] (the particle fills, the pool cursor) is already in order: game.pickups
        # merges it into result['stores'] (seeded into order at the top of this function).

    if arm == 'found-sound':
        box_result = result['box_result']
        if scaled is not None:
            # The scaled path's own bmi.b/beq.b pair (00BC14/00BC16) already reached 00BC24 directly;
            # its cost is inside _pk_scale_cost above. The unscaled bmi.b/bne.b pair (00BC20/00BC22)
            # never executes on this path.
            c, i = _PK_CUE_TST
        elif pickups._signed_word(box_result) < 0:
            c, i = _add(_PK_BMI_RESULT_TAKEN, _PK_CUE_TST)
        else:
            c, i = _add(_PK_BMI_RESULT_NOTTAKEN, _PK_BNE_RESULT_NOTTAKEN, _PK_CUE_TST)
        cycles += c
        instructions += i
        sound_on = read(pickups.CHECK_SOUND_ON, 2) != 0
        c, i = _PK_CUE_BEQ_NOTTAKEN if sound_on else _PK_CUE_BEQ_TAKEN
        cycles += c
        instructions += i
        # The sound-on arm has its own bra.b $bc38 after the store (the sound-off arm falls straight
        # through instead); then 00BC38/BC3C: two movem restores (a0-a2, then d0-d7, neither touching
        # CCR) and the tail's own moveq #$ff,d2 (N=1, but MOVEQ never touches X).
        pieces = [_PK_CUE_STORE] + ([_PK_CUE_BRA] if sound_on else []) + [
            _PK_EFFECT_RESTORE_A0A2, _PK_EFFECT_RESTORE_D0D7, _PK_CUE_MOVEQ, _PK_RTS]
        c, i = _add(*pieces)
        cycles += c
        instructions += i
        # moveq #$ff,d2 sets N=1/Z=V=C=0 but never touches X: X survives from the last flag-setting
        # instruction that produced box_result -- sub.w d3,d2 (00BC1E) on the unscaled path, or
        # add.w d3,d2 (00BC12) on the scaled one -- result['x_op'] names which, from game.pickups.
        op, left, right = result['x_op']
        x_bit = (_add_sr if op == 'add' else _sub_sr)(sr, left, right, 2) & 0x10
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'d2': 0xFFFFFFFF, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                                     'pc': _return(machine, sp), 'sr': 0x08 | x_bit, **a4_exit},
                          last_pc=PICKUP_CHECK_SOUND_LAST_PC)

    if arm == 'found-bare':
        # box_result != 0 (bne taken, RESULT_WORD already stored) but the award itself is zero
        # (beq.b $bc44 taken): a bare restore-and-return, no further calls.  The scaled path's own
        # bra.b $bc4e (00BC1C) already reached here without the unscaled bmi.b/bne.b pair (00BC20/
        # 00BC22) running at all -- its cost is inside _pk_scale_cost above.
        head = () if scaled is not None else (_PK_BMI_RESULT_NOTTAKEN, _PK_BNE_RESULT_TAKEN)
        c, i = _add(*head, _PK_STORE_F3D4, _PK_TST_D3, _PK_BEQ_D3_TAKEN,
                   _PK_EFFECT_RESTORE_A0A2, _PK_EFFECT_RESTORE_D0D7, _PK_RTS)
        cycles += c
        instructions += i
        for a, b in _bytes(pickups.RESULT_WORD & 0xFFFFFF, result['box_result'], 2):
            order[a] = b
        # tst.w d3 (d3=0) is the last flag-setter: N=0/Z=1/V=C=0; X survives from the last flag-setting
        # instruction that produced box_result (sub.w d3,d2 at 00BC1E, or add.w d3,d2 at 00BC12 on the
        # scaled path -- result['x_op'] names which), untouched by every MOVE/TST/movem since.
        op, left, right = result['x_op']
        x_bit = (_add_sr if op == 'add' else _sub_sr)(sr, left, right, 2) & 0x10
        exit_sr = (_logic_sr(sr, result['d3'], 2) & ~0x10) | x_bit
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr,
                                     **a4_exit},
                          last_pc=PICKUP_CHECK_BARE_LAST_PC)
    if arm != 'found-effect':
        raise UnsupportedCandidate(f'pickup check unknown arm {arm}')

    # As in found-bare: the scaled path's own bra.b $bc4e already reached here, its cost already
    # inside _pk_scale_cost above; the unscaled bmi.b/bne.b pair (00BC20/00BC22) never runs on it.
    head = () if scaled is not None else (_PK_BMI_RESULT_NOTTAKEN, _PK_BNE_RESULT_TAKEN)
    c, i = _add(*head, _PK_STORE_F3D4, _PK_TST_D3, _PK_BEQ_D3_NOTTAKEN)
    cycles += c
    instructions += i
    for a, b in _bytes(pickups.RESULT_WORD & 0xFFFFFF, result['box_result'], 2):
        order[a] = b

    mask_x_pieces = [_PK_EFFECT_MASK_BNE_NOTTAKEN, _PK_EFFECT_MASK_DEFAULT] if result['default_mask_x'] \
        else [_PK_EFFECT_MASK_BNE]
    c, i = _add(_PK_EFFECT_RESTORE_A0A2, _PK_EFFECT_PEEK_D2D3, _PK_EFFECT_HALF, _PK_EFFECT_MASK, *mask_x_pieces,
               _PK_EFFECT_MASK_SUBQ, _PK_JSR_RANDOM)
    cycles += c
    instructions += i
    cycles, instructions = cycles + _NR_COST[0], instructions + _NR_COST[1]
    c, i = _PK_TST_DRAW
    cycles += c
    instructions += i
    if result['dx_negative']:
        c, i = _add(_PK_BMI_DRAW_TAKEN, _PK_DRAW_AND, _PK_DRAW_SUB)
    else:
        c, i = _add(_PK_BMI_DRAW_NOTTAKEN, _PK_DRAW_AND, _PK_DRAW_ADD, _PK_DRAW_BRA)
    cycles += c
    instructions += i
    # jsr 014a3c (first draw): return address, then 014A3C's own move.l a0,-(a7) -- both at sp-32's
    # own two slots; a0 is still the entry value (the scan's own a0-a2 frame was just restored above).
    _ram_span('pickup check first random call frame', sp - 40, 8)
    _pk_push(order, sp - 32, [0x00BC76])
    _pk_push(order, sp - 36, [registers['a0']])

    mask_y_pieces = [_PK_EFFECT_MASK_BNE_NOTTAKEN, _PK_EFFECT_MASK_DEFAULT] if result['default_mask_y'] \
        else [_PK_EFFECT_MASK_BNE]
    c, i = _add(_PK_EFFECT_HALF, _PK_EFFECT_MASK, *mask_y_pieces, _PK_EFFECT_MASK_SUBQ, _PK_JSR_RANDOM)
    cycles += c
    instructions += i
    cycles, instructions = cycles + _NR_COST[0], instructions + _NR_COST[1]
    c, i = _PK_TST_DRAW
    cycles += c
    instructions += i
    # The second draw's own negative branch (00BC9E) mirrors the first's: subtract instead of add.
    if result['dy_negative']:
        c, i = _add(_PK_BMI_DRAW_TAKEN, _PK_DRAW_AND, _PK_DRAW_SUB)
    else:
        c, i = _add(_PK_BMI_DRAW_NOTTAKEN, _PK_DRAW_AND, _PK_DRAW_ADD, _PK_DRAW_BRA)
    cycles += c
    instructions += i
    # jsr 014a3c (second draw): the identical two stack slots as the first call, overwritten again.
    _pk_push(order, sp - 32, [0x00BC9C])
    _pk_push(order, sp - 36, [registers['a0']])

    c, i = _add(_PK_EFFECT_TAIL, _PK_JSR_POOL)
    cycles += c
    instructions += i
    added = result['effect']
    pool_cost = _effect_pool_add_cost(added)
    cycles += pool_cost[0]
    instructions += pool_cost[1]
    # jsr 00932c: its own return address, then its own movem.l d0-d1/d4/a0,-(a7) (16 bytes) --
    # d0/d1 are the computed pool position, d4 the second jitter's own mask-minus-one, a0 unchanged.
    _ram_span('pickup check pool call frame', sp - 52, 20)
    _pk_push(order, sp - 32, [0x00BCC4])
    # D0/D1's own upper 16 bits are never cleared anywhere in this whole chain (every touch is a
    # .W op): they still carry whatever was in the entry registers, UNLESS the axis's own clamp used
    # moveq (the 'near' arm sets the WHOLE 32-bit register to -16).
    d0_high = 0xFFFF0000 if result['x_clamp']['arm'] == 'near' else registers['d0'] & 0xFFFF0000
    d1_high = 0xFFFF0000 if result['y_clamp']['arm'] == 'near' else registers['d1'] & 0xFFFF0000
    _pk_push(order, sp - 36, [d0_high | result['pool_x'], d1_high | result['pool_y'],
                              result['mask_y'], registers['a0']])
    for address, (value, size) in added['stores'].items():
        for a, b in _bytes(address, value, size):
            order[a] = b

    c, i = _add(_PK_EFFECT_RESTORE_D0D7, _PK_LOAD_D2, _PK_RTS)
    cycles += c
    instructions += i
    # move.w RESULT_WORD,d2 is the last N/Z/V/C setter (MOVE never touches X).  X instead survives
    # from whichever instruction last touched it: 00932C's OWN addq.w #1,POOL_COUNTER when a slot was
    # found, or -- when the pool is full and that addq never runs -- the second draw's own add.w/sub.w
    # (py_base +/- jitter_y) that produced py, the last X-affecting instruction before the jsr.
    if added['arm'] == 'full':
        x_bit = (_sub_sr if result['dy_negative'] else _add_sr)(sr, result['py_base'], result['jitter_y'], 2) & 0x10
    else:
        x_bit = _add_sr(sr, added['counter_before'], 1, 2) & 0x10
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers={'d2': (registers['d2'] & 0xFFFF0000) | result['box_result'],
                                 'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp),
                                 'sr': (_logic_sr(sr, result['box_result'], 2) & ~0x10) | x_bit, **a4_exit},
                      last_pc=PICKUP_CHECK_EFFECT_LAST_PC)


# --- 010CD2: the pickup probe (game/pickups.py: pickup_probe) ---------------
#
# A caller-supplied record's own camera-relative call into the already-recovered pickup check: owns
# the call the way 00BA8E owns its own callees, composed by calling pickup_check_plan itself with a
# synthetic register file for the point 00BA8E is entered (the shape 0049DA-calls-001164 proved, one
# level deeper).  pickup_check_plan's own internal exit "pc" is meaningless here (nothing was really
# pushed for it to read back: this composition never executes the real bsr), so it is discarded --
# every OTHER fact it computes (cycles, instructions, writes, and every register except pc/a7) does
# not depend on that read and is exact.
PICKUP_PROBE_ENTRY, PICKUP_PROBE_LAST_PC = 0x010CD2, 0x010CF6
PICKUP_PROBE_BSR_RETURN = 0x010CE6
_PP_PUSH = (32, 1)               # movem.l d0-d2,-(a7)
_PP_ADD_X = (12, 1)              # add.w F3EE,d0
_PP_ADD_Y = (12, 1)              # add.w F3F0,d1
_PP_READ_D2 = (12, 1)            # move.w 8(a5),d2
_PP_BSR = (18, 1)                # bsr.w $ba8e (00BA8E's own cost comes from the composed sub-plan)
_PP_WRITEBACK = (12, 1)          # move.w d2,8(a5)
_PP_BPL_TAKEN, _PP_BPL_NOTTAKEN = (10, 1), (8, 1)     # byte branch: taken skips the -1 store
_PP_STORE_NEGATIVE = (16, 1)     # move.w #$ffff,4(a5)
_PP_TAIL = (36 + 16, 2)          # movem.l (a7)+,d0-d2; rts


def pickup_probe_plan(machine, registers):
    """010CD2: a caller-supplied record's own probe into the already-recovered pickup check."""
    from .game import pickups
    if registers['pc'] != PICKUP_PROBE_ENTRY:
        raise UnsupportedCandidate('pickup probe planner needs the machine parked at 010CD2')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    read = _reader(machine)
    a5 = registers['a5'] & 0xFFFFFFFF
    _ram_span('pickup probe record', a5 & 0xFFFFFF, 10)
    record_d2 = read((a5 + 8) & 0xFFFFFF, 2)
    d0_entry, d1_entry = registers['d0'], registers['d1']
    camera_x = read(pickups.CAMERA_X & 0xFFFFFF, 2)
    camera_y = read(pickups.CAMERA_Y & 0xFFFFFF, 2)
    x_full = (d0_entry & 0xFFFF0000) | ((d0_entry + camera_x) & 0xFFFF)
    y_full = (d1_entry & 0xFFFF0000) | ((d1_entry + camera_y) & 0xFFFF)
    # add.w F3F0,d1 is the last flag-setter before the call: X for whatever 00BA8E's own first
    # flag-setter (inside the composed sub-plan) does not itself override before this routine's own
    # next flag-setting instruction (move.w d2,8(a5) is a MOVE: N/Z/V/C only, X unaffected either).
    x_bit = _add_sr(sr, d1_entry & 0xFFFF, camera_y, 2) & 0x10

    _ram_span('pickup probe frame', sp - 12, 12)
    order = {}
    _pk_push(order, sp, [registers['d0'], registers['d1'], registers['d2']])
    _pk_push(order, sp - 12, [PICKUP_PROBE_BSR_RETURN])

    virtual = dict(registers)
    virtual.update(pc=PICKUP_CHECK_ENTRY, a7=(sp - 16) & 0xFFFFFFFF, d0=x_full, d1=y_full,
                   d2=(registers['d2'] & 0xFFFF0000) | (record_d2 & 0xFFFF), sr=(sr & ~0x10) | x_bit)
    inner = pickup_check_plan(machine, virtual)

    for address, value in inner.writes:
        order[address] = value
    result_d2 = pickups._signed_word(inner.registers.get('d2', virtual['d2']))

    cycles = (_PP_PUSH[0] + _PP_ADD_X[0] + _PP_ADD_Y[0] + _PP_READ_D2[0] + _PP_BSR[0] + inner.cycles
             + _PP_WRITEBACK[0])
    instructions = (_PP_PUSH[1] + _PP_ADD_X[1] + _PP_ADD_Y[1] + _PP_READ_D2[1] + _PP_BSR[1] + inner.instructions
                    + _PP_WRITEBACK[1])
    for a, b in _bytes((a5 + 8) & 0xFFFFFF, result_d2, 2):
        order[a] = b
    if result_d2 < 0:
        c, i = _PP_BPL_NOTTAKEN
        cycles += c
        instructions += i
        c, i = _PP_STORE_NEGATIVE
        cycles += c
        instructions += i
        for a, b in _bytes((a5 + 4) & 0xFFFFFF, 0xFFFF, 2):
            order[a] = b
    else:
        c, i = _PP_BPL_TAKEN
        cycles += c
        instructions += i
    c, i = _PP_TAIL
    cycles += c
    instructions += i

    exit_sr = _logic_sr(inner.registers.get('sr', virtual['sr']), result_d2, 2)
    exit_registers = {'d0': registers['d0'], 'd1': registers['d1'], 'd2': registers['d2'],
                      'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr}
    for name in ('a0', 'a1', 'a2', 'a3', 'a4', 'a6', 'd3', 'd4', 'd5', 'd6', 'd7'):
        if name in inner.registers:
            exit_registers[name] = inner.registers[name]
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=PICKUP_PROBE_LAST_PC)


# --- 00B944: the creature update's own probe into the already-recovered pickup check ------------
#
# The SAME "push scratch, call 00BA8E, write D2 back, force -1 on a negative result" shape
# pickup_probe_plan already proves over 010CD2, but with no camera add (D0/D1 are the creature's own
# tracked position, unchanged) and one extra unconditional write before the call: FFFFF382.l =
# 0x00200020, i.e. zones.HALF_WIDTH = zones.HALF_HEIGHT = 0x20 -- pickup_check's own caller-supplied
# box half-extents (010CD2's own call trusts whatever an EARLIER, unrelated part of the frame already
# left there instead).  Since this composition calls pickup_check_plan on the SAME live `machine`
# (never literally applying its own prior writes to it -- an AtomicPlan is a description, not a
# mutation), zone_check's own read of HALF_WIDTH/HALF_HEIGHT would otherwise see whatever was ACTUALLY
# in RAM at the retained fixture's own entry, not the 0x20/0x20 this instruction really seeds on real
# hardware; `_ConstMachine` below overrides exactly those two words for the composed sub-plan's own
# reads, the same "read the value my own head just wrote, not the parked machine's" problem sprite_
# emit_plan's own seam suffix and player_state_plan's own head-into-callee handoff both had to solve
# in their own ways (a register overlay there; a RAM overlay here, since HALF_WIDTH/HEIGHT are read
# by a callee two levels down, not by pickup_check_plan itself).  A second store
# (creatures.LIFECYCLE_RESET) alongside FRAME_STEP on the negative arm is 00B944's own only other
# difference from 010CD2.  Cost from the tracer (artifacts/gods/evidence/census-00B944-*, all five
# recordings).
CREATURE_PICKUP_CHECK_ENTRY, CREATURE_PICKUP_CHECK_LAST_PC = 0x00B944, 0x00B96C
CREATURE_PICKUP_CHECK_BSR_RETURN = 0x00B958
CREATURE_PICKUP_CHECK_HALF_EXTENT = 0x20   # both zones.HALF_WIDTH and zones.HALF_HEIGHT, seeded fixed
_CPC_PUSH = (32, 1)                # movem.l d0-d2,-(a7)
_CPC_STORE_CONST = (24, 1)         # move.l #$200020,f382.w
_CPC_READ_D2 = (12, 1)             # move.w 8(a5),d2
_CPC_BSR = (18, 1)                 # bsr.w $ba8e (00BA8E's own cost comes from the composed sub-plan)
_CPC_WRITEBACK = (12, 1)           # move.w d2,8(a5)
_CPC_BPL_TAKEN, _CPC_BPL_NOTTAKEN = (10, 1), (8, 1)     # byte branch: taken skips the -1/reset stores
_CPC_STORE_NEGATIVE = (16, 1)      # move.w #$ffff,4(a5)
_CPC_CLR_RESET = (16, 1)           # clr.w 6(a5)
_CPC_TAIL = (36 + 16, 2)           # movem.l (a7)+,d0-d2; rts


class _ConstMachine:
    """A read-only view of `machine` with a few RAM bytes overridden -- for composing a callee's own
    boundary plan when THIS region's own prior write (never literally applied to the live machine
    during planning) feeds the callee's own read.  Only `peek_ram`/`peek_rom` are used by `_reader`
    and the cost helpers this composes with; nothing here is ever written to."""
    def __init__(self, machine, overrides):
        self._machine = machine
        self._overrides = overrides   # {address & 0xFFFF: byte_value}

    def peek_ram(self, offset, size=1):
        data = bytearray(self._machine.peek_ram(offset, size))
        for i in range(size):
            value = self._overrides.get(offset + i)
            if value is not None:
                data[i] = value
        return bytes(data)

    def peek_rom(self, offset, size=1):
        return self._machine.peek_rom(offset, size)


def creature_pickup_check_plan(machine, registers):
    """00B944: 00A772's own second unconditional callee.  See game/creatures.py's own module note
    above creature_pickup_check."""
    from .game import creatures, pickups
    if registers['pc'] != CREATURE_PICKUP_CHECK_ENTRY:
        raise UnsupportedCandidate('creature pickup check planner needs the machine parked at 00B944')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    read = _reader(machine)
    a5 = registers['a5'] & 0xFFFFFFFF
    _ram_span('creature pickup check record', a5 & 0xFFFFFF, 9)
    lifecycle = read((a5 + creatures.LIFECYCLE) & 0xFFFFFF, 2)
    d0_entry, d1_entry = registers['d0'], registers['d1']
    x, y = d0_entry & 0xFFFF, d1_entry & 0xFFFF

    _ram_span('creature pickup check frame', sp - 12, 12)
    order = {}
    _pk_push(order, sp, [registers['d0'], registers['d1'], registers['d2']])
    order.update(_bytes(0xFFF382, 0x00200020, 4))
    _pk_push(order, sp - 12, [CREATURE_PICKUP_CHECK_BSR_RETURN])

    virtual = dict(registers)
    virtual.update(pc=PICKUP_CHECK_ENTRY, a7=(sp - 16) & 0xFFFFFFFF, d0=(registers['d0'] & 0xFFFF0000) | x,
                   d1=(registers['d1'] & 0xFFFF0000) | y, d2=(registers['d2'] & 0xFFFF0000) | (lifecycle & 0xFFFF),
                   sr=_logic_sr(sr, lifecycle, 2))
    from .game import zones
    seeded = _ConstMachine(machine, {
        zones.HALF_WIDTH & 0xFFFF: (CREATURE_PICKUP_CHECK_HALF_EXTENT >> 8) & 0xFF,
        (zones.HALF_WIDTH + 1) & 0xFFFF: CREATURE_PICKUP_CHECK_HALF_EXTENT & 0xFF,
        zones.HALF_HEIGHT & 0xFFFF: (CREATURE_PICKUP_CHECK_HALF_EXTENT >> 8) & 0xFF,
        (zones.HALF_HEIGHT + 1) & 0xFFFF: CREATURE_PICKUP_CHECK_HALF_EXTENT & 0xFF})
    inner = pickup_check_plan(seeded, virtual)

    for address, value in inner.writes:
        order[address] = value
    result_d2 = pickups._signed_word(inner.registers.get('d2', virtual['d2']))

    cycles = (_CPC_PUSH[0] + _CPC_STORE_CONST[0] + _CPC_READ_D2[0] + _CPC_BSR[0] + inner.cycles + _CPC_WRITEBACK[0])
    instructions = (_CPC_PUSH[1] + _CPC_STORE_CONST[1] + _CPC_READ_D2[1] + _CPC_BSR[1] + inner.instructions
                    + _CPC_WRITEBACK[1])
    for a, b in _bytes((a5 + creatures.LIFECYCLE) & 0xFFFFFF, result_d2, 2):
        order[a] = b
    base_sr = inner.registers.get('sr', virtual['sr'])
    if result_d2 < 0:
        c, i = _CPC_BPL_NOTTAKEN
        cycles += c
        instructions += i
        c, i = _CPC_STORE_NEGATIVE
        cycles += c
        instructions += i
        for a, b in _bytes((a5 + creatures.FRAME_STEP) & 0xFFFFFF, 0xFFFF, 2):
            order[a] = b
        c, i = _CPC_CLR_RESET
        cycles += c
        instructions += i
        for a, b in _bytes((a5 + creatures.LIFECYCLE_RESET) & 0xFFFFFF, 0, 2):
            order[a] = b
        # clr.w 6(a5) is the LAST flag-setter on this arm (Z=1, N=V=C=0), not the writeback.
        exit_sr = _logic_sr(base_sr, 0, 2)
    else:
        c, i = _CPC_BPL_TAKEN
        cycles += c
        instructions += i
        # the writeback (move.w d2,8(a5)) is the LAST flag-setter on this arm.
        exit_sr = _logic_sr(base_sr, result_d2, 2)
    c, i = _CPC_TAIL
    cycles += c
    instructions += i
    exit_registers = {'d0': registers['d0'], 'd1': registers['d1'], 'd2': registers['d2'],
                      'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr}
    for name in ('a0', 'a1', 'a2', 'a3', 'a4', 'a6', 'd3', 'd4', 'd5', 'd6', 'd7'):
        if name in inner.registers:
            exit_registers[name] = inner.registers[name]
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=CREATURE_PICKUP_CHECK_LAST_PC)


# --- 00A922: the creature's own world-event consume, the third of 00A772's own unconditional
# callees.  No calls of its own; a bounded loop over the world update's own per-tick event list, then
# (on a match) a second bounded loop backwards over the already-recovered game.movement.BOX_SCAN_TABLE.
# Cost from the tracer (artifacts/gods/evidence/census-00A922-*, all five recordings).
EVENT_CONSUME_ENTRY, EVENT_CONSUME_DECLINE_PC = 0x00A922, 0x00A9AA
EVENT_CONSUME_FOUND_PC = 0x00A9F0

_EC_CMP_MODE = (16, 1)                      # 00A922 cmpi.w #2,f1e6.w
_EC_BNE_MODE = {True: (10, 1), False: (12, 1)}      # 00A928 bne.w (word)
_EC_TST_COUNT = (12, 1)                     # 00A92C tst.w f260.w
_EC_BEQ_COUNT = {True: (10, 1), False: (12, 1)}     # 00A930 beq.w (word)
_EC_TST_KIND = (12, 1)                      # 00A934 tst.w $10(a5)
_EC_BPL_KIND = {True: (10, 1), False: (12, 1)}      # 00A938 bpl.w (word) -- taken: already has an event
_EC_LOAD_D7 = (12, 1)                       # 00A93C move.w f260.w,d7
_EC_CMP_CLAMP = (8, 1)                      # 00A940 cmpi.w #$14,d7
_EC_BLE_CLAMP = {True: (10, 1), False: (8, 1)}      # 00A944 ble.b (byte) -- taken: no clamp needed
_EC_SUBQ_D7 = (4, 1)                        # 00A948 subq.w #1,d7
_EC_LOAD_D0 = (8, 1)                        # 00A94A move.w (a5),d0
_EC_LOAD_D1 = (12, 1)                       # 00A94C move.w $2(a5),d1
_EC_SUBQ_D0 = (4, 1)                        # 00A950 subq.w #8,d0
_EC_SUBQ_D1 = (4, 1)                        # 00A952 subq.w #8,d1
_EC_LEA_LIST = (12, 1)                      # 00A954 lea.l $ffff0bf8.l,a0

_EC_LOAD_QUAD = (12, 1)                     # 00A95A move.w $4(a4),d2
_EC_MOVEQ_D3 = (4, 1)                       # 00A95E moveq #0,d3
_EC_CMP_OTHER = (16, 1)                     # 00A960 cmpi.w #$c0,$4(a0)
_EC_BLT_OTHER = {True: (10, 1), False: (8, 1)}      # 00A966 blt.b (byte)
_EC_MOVEQ_D3_2 = (4, 1)                     # 00A968 moveq #2,d3 (only kind >= 0xc0)
_EC_LSR = {0: (6, 1), 2: (10, 1)}           # 00A96A lsr.w d3,d2 (shift is d3: 0 or 2)
_EC_ANDI_MASK = (8, 1)                      # 00A96C andi.w #3,d2
_EC_BEQ_MASK = {True: (10, 1), False: (8, 1)}       # 00A970 beq.b (byte)
_EC_CMP_EXCLUDED = (16, 1)                  # 00A972 cmpi.w #$45,$4(a0)
_EC_BEQ_EXCLUDED = {True: (10, 1), False: (8, 1)}   # 00A978 beq.b (byte)
_EC_LOAD_SLOT_X = (8, 1)                    # 00A97A move.w (a0),d2
_EC_LOAD_SLOT_Y = (12, 1)                   # 00A97C move.w $2(a0),d3
_EC_ADDQ_D2 = (4, 1)                        # 00A980 addq.w #8,d2
_EC_ADDQ_D3 = (4, 1)                        # 00A982 addq.w #8,d3
_EC_CMP1 = (4, 1)                           # 00A984 cmp.w d2,d0
_EC_BGT1 = {True: (10, 1), False: (8, 1)}           # 00A986 bgt.b (byte)
_EC_CMP2 = (4, 1)                           # 00A988 cmp.w d3,d1
_EC_BGT2 = {True: (10, 1), False: (8, 1)}           # 00A98A bgt.b (byte)
_EC_SUBI_D2 = (8, 1)                        # 00A98C subi.w #$30,d2
_EC_SUBI_D3 = (8, 1)                        # 00A990 subi.w #$30,d3
_EC_CMP3 = (4, 1)                           # 00A994 cmp.w d2,d0
_EC_BLT1 = {True: (10, 1), False: (8, 1)}           # 00A996 blt.b (byte)
_EC_CMP4 = (4, 1)                           # 00A998 cmp.w d3,d1
_EC_BLT2 = {True: (10, 1), False: (8, 1)}           # 00A99A blt.b (byte)
_EC_MOVEM_FOUND = (24, 1)                   # 00A99C movem.w (a0),d2-d4
_EC_BRA_LOOP2 = (10, 1)                     # 00A9A0 bra.b $a9ac
_EC_LEA_NEXT = (8, 1)                       # 00A9A2 lea.l $6(a0),a0
_EC_DBRA_TAKEN, _EC_DBRA_LAST = (10, 1), (14, 1)     # 00A9A6 dbra
_EC_RTS = (16, 1)                           # 00A9AA / 00A9F0 rts

_EC_LEA_OBJ_END = (12, 1)                   # 00A9AC lea.l $ffff4982.l,a0
_EC_LOAD_D6 = (8, 1)                        # 00A9B2 move.w #$c7,d6
_EC_SUBQ_A0 = (8, 1)                        # 00A9B6 subq.w #8,a0 (address register: no flags)
_EC_TST_STATUS_B = (12, 1)                  # 00A9B8 tst.w $6(a0)
_EC_BEQ_STATUS_B = {True: (10, 1), False: (8, 1)}   # 00A9BC beq.b (byte)
_EC_TST_STATUS_A = (12, 1)                  # 00A9BE tst.w $4(a0)
_EC_BPL_STATUS_A = {True: (10, 1), False: (8, 1)}   # 00A9C2 bpl.b (byte) -- taken: non-negative, proceed
_EC_CMP_KIND2 = (12, 1)                     # 00A9CA cmp.w $4(a0),d4
_EC_BNE_KIND2 = {True: (10, 1), False: (8, 1)}      # 00A9CE bne.b (byte)
_EC_CMP_X2 = (8, 1)                         # 00A9D0 cmp.w (a0),d2
_EC_BNE_X2 = {True: (10, 1), False: (8, 1)}         # 00A9D2 bne.b (byte)
_EC_CMP_Y2 = (12, 1)                        # 00A9D4 cmp.w $2(a0),d3
_EC_BNE_Y2 = {True: (10, 1), False: (8, 1)}         # 00A9D8 bne.b (byte)
_EC_STORE_EVENT_X = (12, 1)                 # 00A9DA move.w d2,$14(a5)
_EC_STORE_EVENT_Y = (12, 1)                 # 00A9DE move.w d3,$16(a5)
_EC_STORE_EVENT_KIND = (12, 1)              # 00A9E2 move.w d4,$10(a5)
_EC_STORE_NEG = (16, 1)                     # 00A9E6 move.w #$ffff,$4(a0)
_EC_CLR_ACTIVE = (16, 1)                    # 00A9EC clr.w $6(a0)

def _ec_walk_loop1(read, sr, entries, cx, cy, is_last_index):
    """Simulates the WHOLE event-list scan, entry by entry in real execution order (needed to track
    X correctly: ADDQ/SUBI on d2/d3 set it, CMP/ANDI/TST never do, so X can survive from an EARLIER
    entry's own box test into a LATER entry that never reaches one).  Returns (cycles, instructions,
    d2, d3, sr) as of the LAST entry processed; d2/d3 are low words only, the caller merges d2's own
    upper half (never touched here -- only word ops ever reach it) back in.  cx/cy are the creature's
    own tracked box origin (d0/d1, POSITION_X/Y - 8)."""
    from .game import creatures
    cycles = instructions = 0
    d2 = d3 = 0
    for index, step in enumerate(entries):
        is_last = is_last_index(index)
        c, i = _add(_EC_LOAD_QUAD, _EC_MOVEQ_D3)
        cycles += c
        instructions += i
        kind = step['slot_kind']
        is_other = kind >= creatures.EVENT_KIND_OTHER_GATE
        d3 = 2 if is_other else 0
        c, i = _EC_CMP_OTHER
        cycles += c
        instructions += i
        c, i = _EC_BLT_OTHER[not is_other]
        cycles += c
        instructions += i
        if is_other:
            c, i = _EC_MOVEQ_D3_2
            cycles += c
            instructions += i
        c, i = _EC_LSR[d3]
        cycles += c
        instructions += i
        c, i = _EC_ANDI_MASK
        cycles += c
        instructions += i
        d2 = step['mask']
        sr = _logic_sr(sr, d2, 2)
        if step['arm'] == 'skip-mask':
            c, i = _EC_BEQ_MASK[True]
            cycles += c
            instructions += i
            c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
            cycles, instructions = cycles + _EC_LEA_NEXT[0] + c, instructions + _EC_LEA_NEXT[1] + i
            continue
        c, i = _EC_BEQ_MASK[False]
        cycles += c
        instructions += i
        c, i = _EC_CMP_EXCLUDED
        cycles += c
        instructions += i
        # cmpi.w does not write its own destination: d2 stays the earlier andi.w result (the mask).
        sr = _cmp_sr(sr, kind, creatures.EVENT_KIND_EXCLUDED, 2)
        if step['arm'] == 'skip-excluded':
            c, i = _EC_BEQ_EXCLUDED[True]
            cycles += c
            instructions += i
            c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
            cycles, instructions = cycles + _EC_LEA_NEXT[0] + c, instructions + _EC_LEA_NEXT[1] + i
            continue
        c, i = _add(_EC_BEQ_EXCLUDED[False], _EC_LOAD_SLOT_X, _EC_LOAD_SLOT_Y, _EC_ADDQ_D2, _EC_ADDQ_D3, _EC_CMP1)
        cycles += c
        instructions += i
        slot_x = read(step['entry'] & 0xFFFFFF, 2)
        slot_y = read((step['entry'] + 2) & 0xFFFFFF, 2)
        d2, d3 = (slot_x + 8) & 0xFFFF, (slot_y + 8) & 0xFFFF   # ADDQ.w: sets X too
        sr = _add_sr(sr, slot_x, 8, 2)
        sr = _cmp_sr(sr, cx, d2, 2)
        if not step['pass_far_x']:
            c, i = _EC_BGT1[True]
            cycles += c
            instructions += i
            c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
            cycles, instructions = cycles + _EC_LEA_NEXT[0] + c, instructions + _EC_LEA_NEXT[1] + i
            continue
        c, i = _add(_EC_BGT1[False], _EC_CMP2)
        cycles += c
        instructions += i
        sr = _cmp_sr(sr, cy, d3, 2)
        if not step['pass_far_y']:
            c, i = _EC_BGT2[True]
            cycles += c
            instructions += i
            c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
            cycles, instructions = cycles + _EC_LEA_NEXT[0] + c, instructions + _EC_LEA_NEXT[1] + i
            continue
        c, i = _add(_EC_BGT2[False], _EC_SUBI_D2, _EC_SUBI_D3, _EC_CMP3)
        cycles += c
        instructions += i
        far_x = d2
        d2, d3 = (d2 - 0x30) & 0xFFFF, (d3 - 0x30) & 0xFFFF     # SUBI.w: sets X too
        sr = _sub_sr(sr, far_x, 0x30, 2)   # d2's own subi (d3's own runs right after, unconditionally)
        sr_after_d3_subi = _sub_sr(sr, (d3 + 0x30) & 0xFFFF, 0x30, 2)
        sr = _cmp_sr(sr_after_d3_subi, cx, d2, 2)
        if not step['pass_near_x']:
            c, i = _EC_BLT1[True]
            cycles += c
            instructions += i
            c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
            cycles, instructions = cycles + _EC_LEA_NEXT[0] + c, instructions + _EC_LEA_NEXT[1] + i
            continue
        c, i = _add(_EC_BLT1[False], _EC_CMP4)
        cycles += c
        instructions += i
        sr = _cmp_sr(sr, cy, d3, 2)
        if step['arm'] != 'found':
            c, i = _EC_BLT2[True]
            cycles += c
            instructions += i
            c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
            cycles, instructions = cycles + _EC_LEA_NEXT[0] + c, instructions + _EC_LEA_NEXT[1] + i
            continue
        c, i = _add(_EC_BLT2[False], _EC_MOVEM_FOUND, _EC_BRA_LOOP2)
        cycles += c
        instructions += i
    return cycles, instructions, d2, d3, sr


def _ec_loop2_entry_cost(step, is_last):
    """One game.movement.BOX_SCAN_TABLE entry's own cost through the object search, from its own
    subq.w #8,a0 through whichever tail it reaches.  Every 'continue' arm (skip-inactive, skip-kind,
    skip-x) jumps to the shared 00A9C4 dbra, which this folds in (DBRA_LAST only for the table's own
    last slot, i.e. full exhaustion -- 'no-object-match', which the caller already declines, so
    DBRA_TAKEN is the only cost ever actually charged here in practice).  'skip-negative'/'skip-y'
    break the loop without ever reaching the dbra.  Returns (cycles, instructions, continues)."""
    cycles, instructions = _add(_EC_SUBQ_A0, _EC_TST_STATUS_B)
    if step['arm'] == 'skip-inactive':
        c, i = _EC_BEQ_STATUS_B[True]
        cycles += c
        instructions += i
        c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
        return cycles + c, instructions + i, True
    c, i = _add(_EC_BEQ_STATUS_B[False], _EC_TST_STATUS_A)
    cycles += c
    instructions += i
    if step['arm'] == 'skip-negative':
        c, i = _EC_BPL_STATUS_A[False]
        return cycles + c, instructions + i, False
    c, i = _add(_EC_BPL_STATUS_A[True], _EC_CMP_KIND2)
    cycles += c
    instructions += i
    if step['arm'] == 'skip-kind':
        c, i = _EC_BNE_KIND2[True]
        cycles += c
        instructions += i
        c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
        return cycles + c, instructions + i, True
    c, i = _add(_EC_BNE_KIND2[False], _EC_CMP_X2)
    cycles += c
    instructions += i
    if step['arm'] == 'skip-x':
        c, i = _EC_BNE_X2[True]
        cycles += c
        instructions += i
        c, i = _EC_DBRA_LAST if is_last else _EC_DBRA_TAKEN
        return cycles + c, instructions + i, True
    c, i = _add(_EC_BNE_X2[False], _EC_CMP_Y2)
    cycles += c
    instructions += i
    if step['arm'] == 'skip-y':
        c, i = _EC_BNE_Y2[True]
        return cycles + c, instructions + i, False
    c, i = _add(_EC_BNE_Y2[False], _EC_STORE_EVENT_X, _EC_STORE_EVENT_Y, _EC_STORE_EVENT_KIND,
               _EC_STORE_NEG, _EC_CLR_ACTIVE)
    return cycles + c, instructions + i, False


def event_consume_plan(machine, registers):
    """00A922: the creature's own world-event consume.  See game/creatures.py's own module note
    above event_consume for the full arm breakdown."""
    from .game import creatures
    if registers['pc'] != EVENT_CONSUME_ENTRY:
        raise UnsupportedCandidate('event consume planner needs the machine parked at 00A922')
    sr = registers['sr']
    read = _reader(machine)
    a4, a5 = registers['a4'] & 0xFFFFFFFF, registers['a5'] & 0xFFFFFFFF
    order = {}
    exit_registers = {}
    # no push of its own anywhere in this routine (stack_delta is +4 on every exit): the caller's own
    # return address sits at the entry a7 throughout, popped by whichever rts actually runs.
    return_pc = _return(machine, registers['a7'] & 0xFFFFFF)
    exit_registers['a7'] = (registers['a7'] + 4) & 0xFFFFFFFF

    mode = read(creatures.EVENT_MODE, 2)
    cycles, instructions = _EC_CMP_MODE
    sr = _cmp_sr(sr, mode, 2, 2)
    inactive = mode != 2
    c, i = _EC_BNE_MODE[inactive]
    cycles += c
    instructions += i
    if inactive:
        exit_registers['pc'] = return_pc
        exit_registers['sr'] = sr
        c, i = _EC_RTS
        return AtomicPlan(cycles=cycles + c, instructions=instructions + i, writes=(),
                          registers=exit_registers, last_pc=EVENT_CONSUME_DECLINE_PC)

    count = read(creatures.EVENT_COUNT, 2)
    c, i = _EC_TST_COUNT
    cycles += c
    instructions += i
    sr = _logic_sr(sr, count, 2)
    no_events = count == 0
    c, i = _EC_BEQ_COUNT[no_events]
    cycles += c
    instructions += i
    if no_events:
        exit_registers['pc'] = return_pc
        exit_registers['sr'] = sr
        c, i = _EC_RTS
        return AtomicPlan(cycles=cycles + c, instructions=instructions + i, writes=(),
                          registers=exit_registers, last_pc=EVENT_CONSUME_DECLINE_PC)

    event_kind_field = read((a5 + creatures.EVENT_KIND) & 0xFFFFFF, 2)
    c, i = _EC_TST_KIND
    cycles += c
    instructions += i
    sr = _logic_sr(sr, event_kind_field, 2)
    has_event = creatures._signed_word(event_kind_field) >= 0
    c, i = _EC_BPL_KIND[has_event]
    cycles += c
    instructions += i
    if has_event:
        exit_registers['pc'] = return_pc
        exit_registers['sr'] = sr
        c, i = _EC_RTS
        return AtomicPlan(cycles=cycles + c, instructions=instructions + i, writes=(),
                          registers=exit_registers, last_pc=EVENT_CONSUME_DECLINE_PC)

    result = creatures.event_consume(read, a4, a5)
    if result['arm'] == 'count-clamped':
        raise UnsupportedCandidate('event consume: EVENT_COUNT clamp arm not witnessed by a recording')

    c, i = _EC_LOAD_D7
    cycles += c
    instructions += i
    sr = _logic_sr(sr, count, 2)
    c, i = _EC_CMP_CLAMP
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, count, 0x14, 2)
    c, i = _EC_BLE_CLAMP[True]
    cycles += c
    instructions += i
    c, i = _EC_SUBQ_D7
    cycles += c
    instructions += i
    d7 = (count - 1) & 0xFFFF
    sr = _sub_sr(sr, count, 1, 2)
    position_x = read(a5 & 0xFFFFFF, 2)
    position_y = read((a5 + 2) & 0xFFFFFF, 2)
    c, i = _EC_LOAD_D0
    cycles += c
    instructions += i
    c, i = _EC_LOAD_D1
    cycles += c
    instructions += i
    cx = (position_x - 8) & 0xFFFF
    cy = (position_y - 8) & 0xFFFF
    c, i = _EC_SUBQ_D0
    cycles += c
    instructions += i
    sr = _sub_sr(sr, position_x, 8, 2)
    c, i = _EC_SUBQ_D1
    cycles += c
    instructions += i
    sr = _sub_sr(sr, position_y, 8, 2)
    c, i = _EC_LEA_LIST
    cycles += c
    instructions += i
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cx
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cy
    exit_registers['a0'] = creatures.EVENT_LIST & 0xFFFFFFFF

    entries = result['entries']
    is_last_index = lambda index: index == len(entries) - 1
    c, i, d2_low, d3_low, sr = _ec_walk_loop1(read, sr, entries, cx, cy, is_last_index)
    cycles += c
    instructions += i
    last_entry_addr = (creatures.EVENT_LIST + creatures.EVENT_LIST_STRIDE * len(entries)) & 0xFFFFFFFF
    exit_registers['a0'] = last_entry_addr if result['arm'] != 'found' else entries[-1]['entry'] & 0xFFFFFFFF
    # d7 starts at (count-1); a 'no-match' scan always runs it down to exhaustion (-1) by construction
    # (exactly `count` entries, one dbra each); a 'found' entry never reaches its own dbra, so d7 stays
    # at (count-1) minus however many PRIOR entries already decremented it.
    # move.w $f260.w,d7 (00A93C) is the only writer of d7 before the loop; subq.w/dbra are also word
    # ops, so d7's own upper half survives from ENTRY throughout.
    if result['arm'] == 'found':
        exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | ((count - 1 - entries[-1]['index']) & 0xFFFF)
    else:
        exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | 0xFFFF
    # d2: only ever touched by word ops here (move.w/andi.w/addq.w/subi.w), so its own upper half
    # survives from ENTRY throughout; d3 is fully re-cleared by its own moveq #0/2 every iteration.
    exit_registers['d2'] = (registers['d2'] & 0xFFFF0000) | d2_low
    exit_registers['d3'] = d3_low

    if result['arm'] == 'no-match':
        exit_registers['pc'] = return_pc
        exit_registers['sr'] = sr
        c, i = _EC_RTS
        return AtomicPlan(cycles=cycles + c, instructions=instructions + i, writes=(),
                          registers=exit_registers, last_pc=EVENT_CONSUME_DECLINE_PC)
    exit_registers['d2'] = result['d2']
    exit_registers['d3'] = result['d3']

    # 'found' at loop 1: d2/d3/d4 sign-extended by movem.w; loop 2 walks game.movement.BOX_SCAN_TABLE.
    from .game import movement
    exit_registers['d4'] = result['d4'] & 0xFFFF
    c, i = _EC_LEA_OBJ_END
    cycles += c
    instructions += i
    c, i = _EC_LOAD_D6
    cycles += c
    instructions += i
    obj_entries = result['obj_entries']
    for oindex, step in enumerate(obj_entries):
        is_last_obj = oindex == len(obj_entries) - 1
        c, i, _continues = _ec_loop2_entry_cost(step, is_last_obj)
        cycles += c
        instructions += i
    last_obj = obj_entries[-1]
    if last_obj['arm'] in ('skip-negative', 'skip-y'):
        raise UnsupportedCandidate(f"event consume: object search arm not witnessed by a recording: {last_obj['arm']}")
    obj_dbra_count = len(obj_entries) - (1 if last_obj['arm'] == 'found' else 0)
    # move.w #$c7,d6 (00A9B2) is a word op: d6's own upper half survives from ENTRY.
    exit_registers['d6'] = (registers['d6'] & 0xFFFF0000) | ((0xC7 - obj_dbra_count) & 0xFFFF)
    exit_registers['a0'] = last_obj['entry'] & 0xFFFFFFFF
    if result['arm'] == 'no-object-match':
        raise UnsupportedCandidate('event consume: object search exhausted, not witnessed by a recording')

    for address, (value, size) in result['stores'].items():
        for a, b in _bytes(address, value, size):
            order[a] = b
    # clr.w 6(a0) is the last flag-setter for N/Z/V/C (Z=1, rest 0) but does not touch X; nothing in
    # loop 2 (all cmp/tst/move/clr) ever sets X either, so it survives from loop 1's own walk.
    exit_registers['sr'] = _logic_sr(sr, 0, 2)
    exit_registers['pc'] = return_pc
    c, i = _EC_RTS
    return AtomicPlan(cycles=cycles + c, instructions=instructions + i, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=EVENT_CONSUME_FOUND_PC)


# --- 00FFF0: the line walker's resume, object copy (game/walker.py) ----------
#
# The animation step resumes a solid's walk: the record at A3 is loaded, the
# stored body runs steps until the budget word FFF1FE reaches zero or the
# walk's own counter runs out, and the record is written back re-armed.
# Cost from the tracer (artifacts/gods/evidence/census-00FFF0*), per
# fragment (cycles, instructions): the resume head, one step (with or
# without the minor-axis wrap) that continues, that ends on the budget, or
# that ends on the counter, and the yield tail.  The step costs are the same
# in the shallow and the steep bodies.
WALKER_RESUME_ENTRY, WALKER_RESUME_LAST_PC = 0x00FFF0, None   # each body has its own rts
_WR_HEAD = (80, 8)                     # movea; movea (a3)+; move.w x3; movem.w (a3)+; movea; jmp (a0)
_WR_STEP = {                           # (wrapped, how the step ended) -> cost
    (False, 'continue'): (52, 6), (True, 'continue'): (58, 8),
    (False, 'budget'): (44, 5), (True, 'budget'): (50, 7),
    (False, 'counter'): (56, 6), (True, 'counter'): (62, 8)}
_WR_TAIL = (92, 8)                     # subq d7; move.l #body,(a3)+; move.w x3; addq #8,a3; movem.w -(a3); rts
_WR_RTS = {('+x', 'shallow'): 0x01004A, ('+x', 'steep'): 0x01007A, ('-x', 'shallow'): 0x0100C0, ('-x', 'steep'): 0x0100F0}


def _walk_steps(walk, budget, copy):
    """The per-step facts the cost table needs: whether the minor axis wrapped and how the step ended."""
    from .game import walker
    bodies, rearm, counted = walker.COPIES[copy]
    toward, slope = walk.phase
    error, counter = walk.error, walk.counter
    minor, major = (walk.dy, walk.dx) if slope == 'shallow' else (walk.dx, walk.dy)
    steps = []
    while True:
        error = (error - minor) & 0xFFFF
        wrapped = bool(error & 0x8000)
        if wrapped:
            error = (error + major) & 0xFFFF
        budget = (budget - 1) & 0xFFFF
        if budget == 0:
            steps.append((wrapped, 'budget'))
            break
        if counted:
            counter = (counter - 1) & 0xFFFF
            if counter == 0xFFFF:
                steps.append((wrapped, 'counter'))
                break
        steps.append((wrapped, 'continue'))
    return steps, counter


def walker_resume_plan(machine, registers):
    """00FFF0: resume the walk in the record at A3 with the budget in FFF1FE; not-a-walk records decline."""
    from .game import walker
    if registers['pc'] != WALKER_RESUME_ENTRY:
        raise UnsupportedCandidate('walker resume planner needs the machine parked at 00FFF0')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    record32 = registers['a3']
    record = record32 & 0xFFFFFF
    if (sp | record) & 1:
        raise UnsupportedCandidate('unaligned stack or walker record')
    read = _reader(machine)
    _spans_disjoint([('walker frame', sp, 4), ('walker record', record, walker.RECORD_SIZE), ('walker budget', walker.BUDGET, 2)])
    walk = walker.load(read, record, 'object')
    if walk is None:
        raise UnsupportedCandidate('record continuation is not one of the object walker bodies')
    budget = read(walker.BUDGET, 2)
    if budget == 0:
        raise UnsupportedCandidate('a zero budget wraps the budget word: not witnessed')
    after, left, count, completed = walker.run(walk, budget, 'object')
    steps, counter_before_subq = _walk_steps(walk, budget, 'object')
    assert len(steps) == count
    cost = _add(_WR_HEAD, *(_WR_STEP[step] for step in steps), _WR_TAIL)
    high = lambda name: registers[name] & 0xFFFF0000
    # The last X-setter is subq.w #1,d7 after the loop (a borrow when the counter was zero); N/Z from the
    # last move.w d0,(a3)+, the y step sign; V and C clear.
    x = 0x10 if counter_before_subq == 0 else 0
    nz = 0x08 if after.y_sign & 0x8000 else (0x04 if after.y_sign == 0 else 0)
    # movem.w into data registers sign-extends the loaded words (d2, d3, d5, d7); the word arithmetic that
    # follows leaves that upper half alone (d5, d7); move.w keeps the entry's upper word (d0, d4, d6).
    loaded = lambda word: 0xFFFF0000 if word & 0x8000 else 0
    exit_registers = {
        'd0': high('d0') | after.y_sign, 'd2': loaded(walk.dx) | after.dx, 'd3': loaded(walk.dy) | after.dy,
        'd4': high('d4') | after.x, 'd5': loaded(walk.error) | after.error, 'd6': high('d6') | after.y,
        'd7': loaded(walk.counter) | after.counter,
        'a0': walker.OBJECT_BODIES[walk.phase], 'a3': (record32 + 10) & 0xFFFFFFFF, 'a5': record32,
        'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': (sr & ~0x1F) | x | nz}
    # The budget first, the record last: the record's counter is the last written byte, so the result
    # mutant (a stored byte off) alters what the next invocation reads instead of a word the caller resets.
    stores = {walker.BUDGET: (left, 2), **walker.stores(after, record, 'object')}
    writes = tuple(pair for address, (value, size) in stores.items() for pair in _bytes(address, value, size))
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers,
                      last_pc=_WR_RTS[walk.phase])


# --- 0093D2: the line walker's resume, projectile copy (game/walker.py) -----
#
# A byte-for-byte duplicate of WALKER_RESUME_ENTRY's own body at a second ROM
# address, over the projectile pool's own records (game/projectiles.py) --
# same cost fragments (_WR_HEAD/_WR_STEP/_WR_TAIL, confirmed identical), the
# projectile's own re-arm table and RTS addresses, and no `dbra`-driven
# completion (the loop only ever ends on the budget: `_walk_steps`'s own
# 'projectile' copy never emits a 'counter' step).
PROJECTILE_RESUME_ENTRY = 0x0093D2
_WR_PROJECTILE_RTS = {('+x', 'shallow'): 0x00942E, ('+x', 'steep'): 0x00945C,
                      ('-x', 'shallow'): 0x0094A0, ('-x', 'steep'): 0x0094CE}


def walker_resume_projectile_plan(machine, registers):
    """0093D2: resume the projectile walk in the record at A3 with the budget in FFF1FE."""
    from .game import walker
    if registers['pc'] != PROJECTILE_RESUME_ENTRY:
        raise UnsupportedCandidate('projectile resume planner needs the machine parked at 0093D2')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    record32 = registers['a3']
    record = record32 & 0xFFFFFF
    if (sp | record) & 1:
        raise UnsupportedCandidate('unaligned stack or walker record')
    read = _reader(machine)
    _spans_disjoint([('walker frame', sp, 4), ('walker record', record, walker.RECORD_SIZE), ('walker budget', walker.BUDGET, 2)])
    walk = walker.load(read, record, 'projectile')
    if walk is None:
        raise UnsupportedCandidate('record continuation is not one of the projectile walker bodies')
    budget = read(walker.BUDGET, 2)
    if budget == 0:
        raise UnsupportedCandidate('a zero budget wraps the budget word: not witnessed')
    after, left, count, completed = walker.run(walk, budget, 'projectile')
    steps, counter_before_subq = _walk_steps(walk, budget, 'projectile')
    assert len(steps) == count
    cost = _add(_WR_HEAD, *(_WR_STEP[step] for step in steps), _WR_TAIL)
    high = lambda name: registers[name] & 0xFFFF0000
    x = 0x10 if counter_before_subq == 0 else 0
    nz = 0x08 if after.y_sign & 0x8000 else (0x04 if after.y_sign == 0 else 0)
    loaded = lambda word: 0xFFFF0000 if word & 0x8000 else 0
    exit_registers = {
        'd0': high('d0') | after.y_sign, 'd2': loaded(walk.dx) | after.dx, 'd3': loaded(walk.dy) | after.dy,
        'd4': high('d4') | after.x, 'd5': loaded(walk.error) | after.error, 'd6': high('d6') | after.y,
        'd7': loaded(walk.counter) | after.counter,
        'a0': walker.PROJECTILE_BODIES[walk.phase], 'a3': (record32 + 10) & 0xFFFFFFFF, 'a5': record32,
        'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': (sr & ~0x1F) | x | nz}
    stores = {walker.BUDGET: (left, 2), **walker.stores(after, record, 'projectile')}
    writes = tuple(pair for address, (value, size) in stores.items() for pair in _bytes(address, value, size))
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers,
                      last_pc=_WR_PROJECTILE_RTS[walk.phase])


# --- 0091BC: the projectile launch (game/projectiles.py: launch) ------------
#
# No save/restore frame at all: D0-D7/A3 are live scratch, exactly the
# hazard tick's own shape.  Cost from the tracer (artifacts/gods/evidence/
# census-0091BC*): the pool scan's own head/skip/found fragments, then the
# projectile cold start's own quadrant-dependent setup (before the per-step
# loop) -- WALKER_RESUME_ENTRY's own _WR_STEP/_WR_TAIL are reused directly
# for the loop and the re-arm tail, the shape this routine's own body
# proves cost-identical to 00FFF0's (the loop bodies are the same
# instructions; the projectile's own unconditional `bra.b` costs exactly
# what the object copy's `dbra` costs on every witnessed step, so the same
# per-step table serves both copies).  The pool exhausted (`0091DE`) is
# real ROM code no recording enters: declined.
LAUNCH_ENTRY, LAUNCH_LAST_PC = 0x0091BC, 0x0091F6
_PL_HEAD = (56, 7)                        # the two FFF18C/8E reads and biases, the budget store, the pool setup
_PL_SKIP = (38, 4)                        # tst.l; bmi not taken; lea.l +0x16,a3; dbra taken
_PL_FOUND = (22, 2)                       # tst.l; bmi taken
_PL_STORE_AND_CALL = (50, 4)              # the two aux-word stores; bsr.w
_PL_TAIL = (32, 2)                        # move.w #1,$f386.w; rts (the last flag-setter: N=Z=V=C=0, always)
_PL_OUTER = {'+x': (16, 2), '-x': (14, 2)}                     # cmp.w d2,d0; bgt.w (word branch)
_PL_XSETUP = {'+x': (12, 3), '-x': (18, 4)}                    # position + dx, the '-x' arm's own extra exg.l
_PL_YSIGN = {('+x', False): (22, 3), ('+x', True): (32, 5),    # y_sign setup: move.w #imm,d0 ('+x') vs moveq ('-x')
             ('-x', False): (18, 3), ('-x', True): (24, 5)}
_PL_SLOPE_TEST = {'shallow': (12, 2), 'steep': (14, 2)}        # cmp.w d3,d2; bcs.b (not-taken=shallow/taken=steep)
_PL_PRELOOP = (16, 3)                                          # move.w major,d7; move.w major,d5; lsr.w #1,d5


def launch_plan(machine, registers):
    """0091BC: scan the 20-entry pool for a free slot and start a projectile walk toward the tracked
    position; the pool exhausted (0091DE) is declined, unwitnessed by any recording."""
    from .game import projectiles, walker
    if registers['pc'] != LAUNCH_ENTRY:
        raise UnsupportedCandidate('launch planner needs the machine parked at 0091BC')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    budget, flag = registers['d4'] & 0xFFFF, registers['d6'] & 0xFFFF
    result = projectiles.launch(_reader(machine), registers['d0'] & 0xFFFF, registers['d1'] & 0xFFFF, budget, flag)
    if result['arm'] != 'launched':
        raise UnsupportedCandidate('projectile pool exhausted: not witnessed by a recording')
    _spans_disjoint([('projectile pool', projectiles.POOL_BASE & 0xFFFFFF, projectiles.POOL_STRIDE * projectiles.POOL_COUNT),
                     ('projectile budget', projectiles.BUDGET_WORD & 0xFFFFFF, 2),
                     ('projectile launched flag', projectiles.LAUNCHED_FLAG & 0xFFFFFF, 2),
                     ('launch call return', sp - 4, 4)])
    walk, after = result['walk'], result['after']
    steps, counter_before_subq = _walk_steps(walk, budget, 'projectile')
    toward, slope = walk.phase
    y_negative = walk.y_sign == 0xFFFF
    setup_cost = _add(_PL_OUTER[toward], _PL_XSETUP[toward], _PL_YSIGN[(toward, y_negative)],
                      _PL_SLOPE_TEST[slope], _PL_PRELOOP)
    call_cost = _add(setup_cost, *(_WR_STEP[step] for step in steps), _WR_TAIL)
    tries_cost = _add(*([_PL_SKIP] * result['tries']))
    cost = _add(_PL_HEAD, tries_cost, _PL_FOUND, _PL_STORE_AND_CALL, call_cost, _PL_TAIL)
    high = lambda name: registers[name] & 0xFFFF0000
    sign32 = lambda word: 0xFFFFFFFF if word & 0x8000 else word
    # Every register here is scratch from the caller's own entry, threaded through plain word ops (which
    # preserve the upper word from whatever this call's own entry held) except: d0's upper word survives
    # only on the '+x' arm (move.w #imm,d0); the '-x' arm's moveq sign-extends the whole register, losing
    # it; d2 inherits d0's own upper word on '-x' (the exg.l swap) and its own otherwise; d5 is always
    # freshly zeroed (moveq #$13,d5 in this routine's own head, never widened again).
    d0 = sign32(after.y_sign) if toward == '-x' else (high('d0') | after.y_sign)
    d2 = (high('d0') | after.dx) if toward == '-x' else (high('d2') | after.dx)
    d3 = high('d3') | after.dy
    d4 = high('d4') | after.x
    d6 = high('d6') | after.y
    d7 = high('d7') | after.counter
    a3 = (result['slot'] + 10) & 0xFFFFFFFF
    writes = (_bytes(sp - 4, 0x0091F0, 4)
              + tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size)))
    # The last flag-setting instruction is move.w #1,$f386.w (a positive constant: N=Z=V=C=0, always); X
    # is the walk's own residue (the final subq.w #1,d7's borrow -- for the projectile copy this is
    # always the walk's own untouched counter, never decremented mid-loop).
    x = 0x10 if counter_before_subq == 0 else 0
    exit_registers = {'d0': d0 & 0xFFFFFFFF, 'd2': d2 & 0xFFFFFFFF, 'd3': d3, 'd4': d4, 'd5': after.error,
                      'd6': d6, 'd7': d7, 'a3': a3, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                      'pc': _return(machine, sp), 'sr': (sr & ~0x1F) | x}
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers,
                      last_pc=LAUNCH_LAST_PC)


# --- 009D6C: the creature attack update (game/creatures.py: attack_update) --
#
# Cost from the tracer (artifacts/gods/evidence/census-009D6C*, the full-tree census over all five
# recordings, 273 retained fixtures, 18 Sep): every arm shares a head (the attack-byte read, the two
# early 'skip' exits, the countdown decrement/'waiting' exit, and -- past that -- the reload and
# quadrant read).  Quadrants 1-3 launch a projectile: both share the identical setup/frame/restore
# instructions (a movem.l d0-d7/a0-a5 SAVE shields every register the caller owns from whatever the
# launch call itself does internally, so the RESTORE afterward makes every register but d0-d5 an exact
# entry passthrough -- d0/d1 the launch's own x0/y0, d2/d3 quadrant 1's own jittered target (unchanged
# from entry on quadrants 2-3, where d2/d3 are never touched before the save except d3's own kind
# residue), d4/d5 the attack byte's own high nibble); the launch itself (0091BC direct, or 0091C8 with
# quadrant 1's own jittered target already loaded into D2/D3) is ``launch_plan``'s own body, reused
# verbatim including its 'pool-full' decline.  Quadrant 0 never launches: it hands off to
# ``timers._spawn``'s own already-recovered BACK/FORWARD hazard-pool fill (0115x8C/0115D4, the shape
# ``countdown_check_plan`` prices as ``_CC_CALLEE_HEAD``/``_CC_WINDOW_*``/``_CC_POOL_*``, reused here
# too) through a tail-JUMP (not a call): 009D6C's own frame never unwinds an extra level, so 01158C's
# own inner rts returns straight past 009D6C to 00A772.  The window-reject and hazard-pool-exhausted
# arms are ``_CC_*``'s own shapes; the pool-exhausted one is unwitnessed and declined, matching
# ``countdown_check_plan``.  ``'skip-quadrant0'`` (TRACKED_SIGN non-negative and the instance's own
# FORWARD_BACK word exactly zero) is real ROM code no recording reaches: declined.
ATTACK_UPDATE_ENTRY = 0x009D6C
ATTACK_UPDATE_SKIP_LAST_PC = 0x009DCC
ATTACK_UPDATE_JITTERED_JSR_RETURN = 0x009D66         # jsr $91c8.l's own return address (pushed on the stack)
ATTACK_UPDATE_DIRECT_JSR_RETURN = 0x009D16           # jsr $91bc.l's own return address
# Two near-identical but DISTINCT ROM copies of "movem.l (a7)+,d0-d7/a0-a5; rts" -- not a shared tail:
ATTACK_UPDATE_JITTERED_LAST_PC = 0x009D6A            # the jittered arm's own copy, right after ATTACK_UPDATE_JITTERED_JSR_RETURN
ATTACK_UPDATE_DIRECT_LAST_PC = 0x009D1A              # the direct arm's own copy, right after ATTACK_UPDATE_DIRECT_JSR_RETURN
ATTACK_UPDATE_SPAWN_BACK_LAST_PC = 0x0115D2          # tail-jump into 01158C
ATTACK_UPDATE_SPAWN_FORWARD_LAST_PC = 0x01161C       # tail-jump into 0115D4
_CU_ATTACK_READ = (12, 1)                     # move.b $6(a4),d3
_CU_ATTACK_ZERO_TAKEN, _CU_ATTACK_ZERO_NOT = (10, 1), (8, 1)     # beq.b $9dcc (byte==0)
_CU_SAVE_BYTE = (4, 1)                         # move.b d3,d5
_CU_MASK_KIND = (8, 1)                         # andi.w #$f,d3
_CU_KIND_ZERO_TAKEN, _CU_KIND_ZERO_NOT = (10, 1), (8, 1)         # beq.b $9dcc (kind==0)
_CU_COUNTDOWN_DEC = (16, 1)                    # subq.w #1,$e(a5)
_CU_WAITING_TAKEN, _CU_WAITING_NOT = (10, 1), (8, 1)             # bne.b $9dcc (still counting)
_CU_RTS = (16, 1)
_CU_RELOAD = (4 + 4 + 4 + 4 + 4 + 12, 6)       # moveq #$10,d4; sub.b d3,d4; ext.w; add.w x2; move.w d4,$e(a5)
_CU_QUADRANT_READ = (12 + 14 + 8, 3)           # move.w $4(a4),d4; lsr.w #4,d4; andi.w #3,d4
_CU_HEAD_TO_RELOAD = _add(_CU_ATTACK_READ, _CU_ATTACK_ZERO_NOT, _CU_SAVE_BYTE, _CU_MASK_KIND,
                          _CU_KIND_ZERO_NOT, _CU_COUNTDOWN_DEC, _CU_WAITING_NOT)
_CU_HEAD_TO_QUADRANT = _add(_CU_HEAD_TO_RELOAD, _CU_RELOAD, _CU_QUADRANT_READ)
_CU_Q_TAKEN, _CU_Q_NOT_TAKEN = (10, 1), (12, 1)                  # bne.w $9cf2 (quadrant!=0 / ==0)
_CU_SUBDISPATCH = (8, 1)                       # cmpi.w #1,d4 (at 9cf2)
_CU_SUBDISPATCH_TAKEN, _CU_SUBDISPATCH_NOT = (10, 1), (8, 1)     # beq.b $9d1c (quadrant==1 / 2-3)
_CU_Q1_TARGET_HEAD = (12 + 12 + 4 + 4, 4)      # move.w f18c,d2; move.w f18e,d3; addq#8,d2; addq#6,d3
_CU_Q1_JITTER_JSR = (20, 1)                    # jsr $14a3c.l (014A3C's own body cost via _NR_COST)
_CU_Q1_JITTER_APPLY = (8 + 8 + 4, 3)           # andi.w #$3f,d0; subi.w #$1f,d0; add.w d0,d2-or-d3
_CU_LAUNCH_SETUP = (8 + 12 + 8 + 8 + 14 + 4 + 120 + 4, 8)        # position+bias, power, the movem save, moveq #0,d6
_CU_LAUNCH_JSR = (20, 1)                       # jsr $91bc.l / $91c8.l
_CU_LAUNCH_RESTORE = (124 + 16, 2)             # movem.l (a7)+,d0-d7/a0-a5; rts
_CU_LAUNCH_TOWARD_HEAD = (12 + 4 + 8, 3)       # 0091C8's own remaining head: move.w d4,f1fe; moveq d5; lea a3
_CU_Q0_FREQUENCY = (8 + 14 + 62 + 4 + 4, 5)    # andi.w #$f0,d5; lsr.w #4,d5; mulu.w $eebe.w,d5; swap; addq.w #1,d5
_CU_Q0_TRACKED_TEST = (12, 1)                  # tst.w $f1be.w
_CU_Q0_TRACKED_TAKEN, _CU_Q0_TRACKED_NOT = (10, 1), (8, 1)       # bmi.b $9dce
_CU_Q0_TABLE_READ = (12, 1)                    # move.w $a(a5),d0 (F1BE<0 arm)
_CU_Q0_TABLE_BTST = (12, 1)                    # btst.l d0,$9dea(pc)
_CU_Q0_TABLE_TAKEN, _CU_Q0_TABLE_NOT = (10, 1), (8, 1)           # bne.b $9db8
_CU_Q0_SELECT_TEST = (12, 1)                   # tst.w $12(a5) (F1BE>=0 arm)
_CU_Q0_SELECT_ZERO_TAKEN = (10, 1)             # beq.b $9dcc ($12(a5)==0, declined)
_CU_Q0_SELECT_ZERO_NOT = (8, 1)
_CU_Q0_SELECT_TAKEN, _CU_Q0_SELECT_NOT = (10, 1), (8, 1)         # bpl.b $9dd8
_CU_Q0_NEG = (4, 1)                            # neg.w d5 (BACK only)
_CU_Q0_STORE_AND_BIAS_FWD = (12 + 4 + 8 + 12, 4)      # move.w d5,f1c2; moveq #$20,d0; add.w (a5),d0; move.w 2(a5),d1
_CU_Q0_STORE_AND_BIAS_BACK = (12 + 8 + 12, 3)         # move.w d5,f1c2; move.w (a5),d0; move.w 2(a5),d1 (bias is a subq below)
_CU_Q0_BIAS_BACK = (4, 1)                      # subq.w #8,d0
_CU_Q0_JMP = (12, 1)                           # jmp $1158c.l / $115d4.l


def _cu_frame_writes(sp, values):
    """movem.l d0-d7/a0-a5,-(a7): fourteen longs, ascending register order at ascending addresses."""
    names = ('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'a0', 'a1', 'a2', 'a3', 'a4', 'a5')
    base = sp - len(names) * 4
    return tuple(pair for index, name in enumerate(names)
                 for pair in _bytes((base + 4 * index) & 0xFFFFFF, values[name] & 0xFFFFFFFF, 4))


def _cu_launch_writes(sp, jsr_return):
    """The jsr's own return address, then (inside 0091BC/0091C8 itself) the bsr $93e4's own -- the same
    single extra write ``launch_plan`` adds on top of the semantics' own ``stores``."""
    jsr_sp = sp - len(('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'a0', 'a1', 'a2', 'a3', 'a4', 'a5')) * 4 - 4
    return _bytes(jsr_sp & 0xFFFFFF, jsr_return, 4) + _bytes((jsr_sp - 4) & 0xFFFFFF, _CC_DEEP_LAUNCH_RETURN, 4)


def _cu_launch_cost(launch_result, budget):
    """The pool scan, the walk's own steps and the tail -- ``launch_plan``'s own composition, reused."""
    if launch_result['arm'] != 'launched':
        return None
    steps, counter_before_subq = _walk_steps(launch_result['walk'], budget, 'projectile')
    toward, slope = launch_result['walk'].phase
    y_negative = launch_result['walk'].y_sign == 0xFFFF
    setup_cost = _add(_PL_OUTER[toward], _PL_XSETUP[toward], _PL_YSIGN[(toward, y_negative)],
                      _PL_SLOPE_TEST[slope], _PL_PRELOOP)
    call_cost = _add(setup_cost, *(_WR_STEP[step] for step in steps), _WR_TAIL)
    tries_cost = _add(*([_PL_SKIP] * launch_result['tries']))
    cost = _add(_PL_FOUND, tries_cost, _PL_STORE_AND_CALL, call_cost, _PL_TAIL)
    x = 0x10 if counter_before_subq == 0 else 0
    return cost, x


def attack_update_plan(machine, registers):
    """009D6C: one creature's own attack-timer tick (called from 00A772, itself 00A578's own per-slot
    walk)."""
    from .game import creatures, timers
    if registers['pc'] != ATTACK_UPDATE_ENTRY:
        raise UnsupportedCandidate('attack update planner needs the machine parked at 009D6C')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    type_ptr, instance_ptr = registers['a4'] & 0xFFFFFF, registers['a5'] & 0xFFFFFF
    read = _reader(machine)
    result = creatures.attack_update(read, type_ptr, instance_ptr)
    arm = result['arm']
    exit_pc = _return(machine, sp)
    base_registers = {'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': exit_pc}

    if arm == 'skip':
        attack_byte = read(type_ptr + creatures.ATTACK_BYTE, 1)
        if attack_byte == 0:
            cost = _add(_CU_ATTACK_READ, _CU_ATTACK_ZERO_TAKEN, _CU_RTS)
            d3 = (registers['d3'] & 0xFFFFFF00) | attack_byte
            exit_sr = _logic_sr(sr, attack_byte, 1)
            registers_out = dict(base_registers, d3=d3, sr=exit_sr)
        else:
            kind = attack_byte & 0xF
            cost = _add(_CU_ATTACK_READ, _CU_ATTACK_ZERO_NOT, _CU_SAVE_BYTE, _CU_MASK_KIND,
                       _CU_KIND_ZERO_TAKEN, _CU_RTS)
            d3 = (registers['d3'] & 0xFFFF0000) | kind
            d5 = (registers['d5'] & 0xFFFFFF00) | attack_byte
            exit_sr = _logic_sr(sr, kind, 2)
            registers_out = dict(base_registers, d3=d3, d5=d5, sr=exit_sr)
        return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=(), registers=registers_out,
                          last_pc=ATTACK_UPDATE_SKIP_LAST_PC)

    if arm == 'waiting':
        attack_byte = read(type_ptr + creatures.ATTACK_BYTE, 1)
        kind = attack_byte & 0xF
        cost = _add(_CU_ATTACK_READ, _CU_ATTACK_ZERO_NOT, _CU_SAVE_BYTE, _CU_MASK_KIND, _CU_KIND_ZERO_NOT,
                   _CU_COUNTDOWN_DEC, _CU_WAITING_TAKEN, _CU_RTS)
        d3 = (registers['d3'] & 0xFFFF0000) | kind
        d5 = (registers['d5'] & 0xFFFFFF00) | attack_byte
        exit_sr = _sub_sr(sr, result['before'], 1, 2)
        writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
        return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes,
                          registers=dict(base_registers, d3=d3, d5=d5, sr=exit_sr),
                          last_pc=ATTACK_UPDATE_SKIP_LAST_PC)

    if arm == 'skip-quadrant0':
        raise UnsupportedCandidate('attack update quadrant-0 arm: FORWARD_BACK==0 not witnessed by a recording')
    if arm.endswith('pool-full'):
        raise UnsupportedCandidate(f'attack update {arm} arm: pool exhausted, not witnessed by a recording')

    reload_writes = tuple(pair for address, (value, size) in result['stores'].items() if address == (instance_ptr + creatures.COUNTDOWN) & 0xFFFFFF
                          for pair in _bytes(address, value, size))

    if arm in ('launch-jittered', 'launch-direct'):
        jittered = arm == 'launch-jittered'
        x0 = (read(instance_ptr + creatures.POSITION_X, 2) + creatures.LAUNCH_POSITION_BIAS) & 0xFFFF
        y0 = read(instance_ptr + creatures.POSITION_Y, 2) & 0xFFFF
        power = result['power']
        cost = _add(_CU_HEAD_TO_QUADRANT, _CU_Q_TAKEN, _CU_SUBDISPATCH)
        if jittered:
            cost = _add(cost, _CU_SUBDISPATCH_TAKEN, _CU_Q1_TARGET_HEAD,
                       _CU_Q1_JITTER_JSR, _NR_COST, _CU_Q1_JITTER_APPLY,
                       _CU_Q1_JITTER_JSR, _NR_COST, _CU_Q1_JITTER_APPLY)
        else:
            cost = _add(cost, _CU_SUBDISPATCH_NOT)
        cost = _add(cost, _CU_LAUNCH_SETUP, _CU_LAUNCH_JSR)
        cost = _add(cost, _CU_LAUNCH_TOWARD_HEAD if jittered else _PL_HEAD)
        launch_cost = _cu_launch_cost(result['launch'], power)
        launch_body, x_flag = launch_cost
        cost = _add(cost, launch_body, _CU_LAUNCH_RESTORE)

        entry_a0 = registers['a0']
        movem_values = dict(registers)
        movem_values['d0'] = (registers['d0'] & 0xFFFF0000) | x0
        movem_values['d1'] = (registers['d1'] & 0xFFFF0000) | y0
        if jittered:
            x1, y1 = result['launch']['target']
            movem_values['d2'] = (registers['d2'] & 0xFFFF0000) | x1
            movem_values['d3'] = (registers['d3'] & 0xFFFF0000) | y1
            jsr_return = ATTACK_UPDATE_JITTERED_JSR_RETURN
        else:
            movem_values['d3'] = (registers['d3'] & 0xFFFF0000) | result['kind']
            jsr_return = ATTACK_UPDATE_DIRECT_JSR_RETURN
        movem_values['d4'] = power              # moveq #$10,d4 (the reload's own head) already zeroed d4's upper word
        movem_values['d5'] = (registers['d5'] & 0xFFFF0000) | power
        movem_values['d6'] = registers['d6']   # moveq #0,d6 runs AFTER this movem save
        writes = reload_writes + _cu_frame_writes(sp, movem_values) + _cu_launch_writes(sp, jsr_return)
        writes += tuple(pair for address, (value, size) in result['launch']['stores'].items() for pair in _bytes(address, value, size))
        if jittered:
            for draw in result['draws']:
                writes += tuple(pair for address, (value, size) in draw['stores'].items() for pair in _bytes(address, value, size))
        exit_registers = dict(base_registers)
        for name in ('d0', 'd1', 'd2', 'd3', 'd4', 'd5'):
            exit_registers[name] = movem_values.get(name, registers[name]) & 0xFFFFFFFF
        exit_registers['a0'] = entry_a0
        exit_registers['sr'] = (sr & ~0x1F) | x_flag
        last_pc = ATTACK_UPDATE_JITTERED_LAST_PC if jittered else ATTACK_UPDATE_DIRECT_LAST_PC
        return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers, last_pc=last_pc)

    # 'spawn-window' or 'spawn-reject': the quadrant-0 hazard-pool tail-jump into 01158C/0115D4.
    from .game import timers as _timers
    variant = result['variant']
    back = variant is _timers.BACK
    tracked = read(creatures.TRACKED_SIGN, 2)
    tracked_negative = creatures._signed_word(tracked) < 0
    cost = _add(_CU_HEAD_TO_QUADRANT, _CU_Q_NOT_TAKEN, _CU_Q0_FREQUENCY, _CU_Q0_TRACKED_TEST)
    if tracked_negative:
        table_taken = _CU_Q0_TABLE_TAKEN if back else _CU_Q0_TABLE_NOT
        cost = _add(cost, _CU_Q0_TRACKED_TAKEN, _CU_Q0_TABLE_READ, _CU_Q0_TABLE_BTST, table_taken)
    else:
        select_taken = _CU_Q0_SELECT_NOT if back else _CU_Q0_SELECT_TAKEN
        cost = _add(cost, _CU_Q0_TRACKED_NOT, _CU_Q0_SELECT_TEST, _CU_Q0_SELECT_ZERO_NOT, select_taken)
    if back:
        cost = _add(cost, _CU_Q0_NEG, _CU_Q0_STORE_AND_BIAS_BACK, _CU_Q0_BIAS_BACK, _CU_Q0_JMP)
    else:
        cost = _add(cost, _CU_Q0_STORE_AND_BIAS_FWD, _CU_Q0_JMP)
    cost = _add(cost, _CC_CALLEE_HEAD)
    camera_y = int.from_bytes(machine.peek_ram(_timers.CAMERA_Y & 0xFFFF, 2), 'big')
    sr_x = _sub_sr(sr, result['spawn']['pos_y'], camera_y, 2)
    window_cycles, window_instructions, reject_ccr = _cc_window_cost_and_ccr(sr_x, result['spawn'], variant)
    cost = _add(cost, (window_cycles, window_instructions))
    if arm == 'spawn-window':
        cost = _add(cost, _CC_POOL_SETUP)
        cost = _add(cost, (result['spawn']['tries'] * _CC_POOL_ITER[0], result['spawn']['tries'] * _CC_POOL_ITER[1]))
        cost = _add(cost, _CC_POOL_FOUND, _CC_POOL_STORE, _CC_POOL_EXIT_BRA)
        exit_ccr = _logic_sr(sr_x, variant['marker'], 2)
    else:
        exit_ccr = reject_ccr
    cost = _add(cost, _CC_POP_A0, _CC_RTS_INNER)
    # The jmp itself pushes nothing; 01158C/0115D4's own frame is the ONLY nested call (move.l a0,-(a7),
    # popped by movea.l before its own rts) -- the same durable residue _cc_call_writes prices, but with
    # 009D6C's own caller-return slot (never a fresh bsr here) as the resume value.  Ordered first (the
    # structural residue), with the real gameplay-visible stores last -- a mutant flipping the LAST
    # write must corrupt something the oracle can actually see, not dead stack residue.
    writes = reload_writes + _bytes((sp - 4) & 0xFFFFFF, registers['a0'] & 0xFFFFFFFF, 4)
    writes += tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
    spawn = result['spawn']
    # 01158C/0115D4's own head copies D0/D1 (the biased position, already loaded before the jmp) into
    # D2/D3 without touching D0/D1 themselves; D4 stays at the reload's own moveq-cleared 0 throughout
    # (nothing here ever writes it again); D5 keeps FREQUENCY_UPPER in its own upper word until the pool
    # scan's own ``moveq #$13,d5`` replaces it entirely (spawn-window only) -- reject leaves D5 exactly
    # as the jmp found it (negated for BACK, untouched for FORWARD).
    frequency_signed = result['frequency']   # already negated for BACK by creatures.attack_update itself
    # D3 never carries the frequency here (unlike countdown_check_plan's own D3): the creature code's
    # own D5 does, and D3 still holds "kind" (an earlier word-op residue) right up to the jmp, so 01158C's
    # word-only touches (move.w d1,d3; sub.w f3f0,d3) preserve D3's own entry upper word throughout.
    # D0's own upper word survives only on the BACK tail (move.w (a5),d0); FORWARD's own head is
    # moveq #$20,d0 -- a full 32-bit replacement -- so D0 loses it there (confirmed via
    # --perturb-upper-halves, 18 Sep).
    d0 = (registers['d0'] & 0xFFFF0000) | spawn['pos_x'] if back else spawn['pos_x']
    exit_registers = dict(base_registers, sr=exit_ccr,
                          d0=d0 & 0xFFFFFFFF,
                          d1=(registers['d1'] & 0xFFFF0000) | spawn['pos_y'],
                          d2=(registers['d2'] & 0xFFFF0000) | (spawn['screen_x'] & 0xFFFF),
                          d3=(registers['d3'] & 0xFFFF0000) | (spawn['screen_y'] & 0xFFFF),
                          d4=0)
    if arm == 'spawn-window':
        exit_registers['d5'] = (0x13 - spawn['tries']) & 0xFFFFFFFF
    else:
        exit_registers['d5'] = ((result['frequency_upper'] & 0xFFFF) << 16) | frequency_signed
    last_pc = ATTACK_UPDATE_SPAWN_BACK_LAST_PC if back else ATTACK_UPDATE_SPAWN_FORWARD_LAST_PC
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=writes, registers=exit_registers, last_pc=last_pc)


# --- 00AA50: the creature's own per-kind, per-frame offset (game/creatures.py: kind_frame_offset) --
#
# One of 00A772's own unconditional callees (docs/gods/blockers/2026-09-18-00A578.md's own "Next
# question"): reached both from 00A772's own $f38a.w "moving" arm (its own result fed straight to
# the next unrecovered call, 00A922) and from inside the ground/fall kind handlers.  RAM/ROM-read
# only, no store, one unconditional path -- confirmed across four recordings (19,798 real
# occurrences, `census-00AA50-*`), not merely unexercised by branches: the ROM has none here.
KIND_FRAME_OFFSET_ENTRY, KIND_FRAME_OFFSET_LAST_PC = 0x00AA50, 0x00AA74
_KF_LEA = (8, 1)              # lea.l $a538(pc),a0
_KF_LOAD_KIND = (12, 1)       # move.w $a(a5),d0
_KF_DOUBLE = (12, 1)          # asl.w #3,d0
_KF_LOAD_VALUE = (18, 1)      # move.l $4(a0,d0.w),d2
_KF_ADD_STEP = (12, 1)        # add.w $4(a5),d2
_KF_SHIFT_VALUE = (14, 1)     # asl.w #4,d2
_KF_CLEAR_D0 = (4, 1)         # moveq #0,d0
_KF_LOAD_FRAME = (12, 1)      # move.b $7(a4),d0
_KF_SHIFT_FRAME = (14, 1)     # asl.w #4,d0
_KF_LOAD_TABLE = (16, 1)      # movea.l $f188.w,a0
_KF_ADD_DELTA = (14, 1)       # add.w (a0,d0.w),d2
_KF_RTS = (16, 1)
_KF_COST = _add(_KF_LEA, _KF_LOAD_KIND, _KF_DOUBLE, _KF_LOAD_VALUE, _KF_ADD_STEP, _KF_SHIFT_VALUE,
               _KF_CLEAR_D0, _KF_LOAD_FRAME, _KF_SHIFT_FRAME, _KF_LOAD_TABLE, _KF_ADD_DELTA, _KF_RTS)


def kind_frame_offset_plan(machine, registers):
    """00AA50: pure RAM/ROM reads, one unconditional path, no store -- the plan is just the exit
    register file (d0, d2, a0) and the cost; nothing else changes."""
    from .game import creatures
    if registers['pc'] != KIND_FRAME_OFFSET_ENTRY:
        raise UnsupportedCandidate('kind frame offset planner needs the machine parked at 00AA50')
    sr = registers['sr']
    read = _reader(machine)
    type_ptr, instance_ptr = registers['a4'] & 0xFFFFFF, registers['a5'] & 0xFFFFFF
    result = creatures.kind_frame_offset(read, type_ptr, instance_ptr)
    cycles, instructions = _KF_COST
    # add.w (a0,d0.w),d2 (the final instruction before rts) is the last flag-setter; X is set with C.
    exit_sr = _add_sr(sr, result['offset'], result['delta'], 2)
    frame_table = read(creatures.FRAME_TABLE_PTR, 4) & 0xFFFFFFFF
    exit_registers = {
        'd0': ((result['frame'] << 4) & 0xFFFF),                      # moveq #0,d0 clears the upper half fully
        'd2': result['d2'] & 0xFFFFFFFF,                               # the ROM kind table's own +4 long is
                                                                        # always upper-zero (confirmed from the
                                                                        # ROM, all eight entries), so the full
                                                                        # 32-bit exit equals the 16-bit result
        'a0': frame_table,
        'a7': (registers['a7'] + 4) & 0xFFFFFFFF,
        'pc': _return(machine, registers['a7'] & 0xFFFFFF),
        'sr': exit_sr,
    }
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=(), registers=exit_registers,
                      last_pc=KIND_FRAME_OFFSET_LAST_PC)


# --- 00AA38: the creature's own grid-cell lookup (game/creatures.py: creature_grid_cell) -------------
#
# Byte-for-byte 0063FA's own arithmetic (game.grid.grid_cell_at), parameterised on the creature's own
# POSITION_X/POSITION_Y instead of the fixed GRID_X/GRID_Y (0063FA) or a caller's D0/D1 (010CBC).  One
# of the six further callees the ground/fall kind handlers need
# (docs/gods/blockers/2026-09-18-00A578.md).  RAM/ROM-read only, one unconditional path, no store; cost
# from the tracer (artifacts/gods/evidence/census-00AA38-*).
CREATURE_GRID_CELL_ENTRY, CREATURE_GRID_CELL_LAST_PC = 0x00AA38, 0x00AA4E
_CGC_LEA = (8, 1)             # lea.l $885e.w,a1
_CGC_LOAD_X = (8, 1)          # move.w (a5),d0
_CGC_LOAD_Y = (12, 1)         # move.w $2(a5),d1
_CGC_MASK_Y = (8, 1)          # andi.w #$fff0,d1
_CGC_ASR_X = (16, 1)          # asr.w #5,d0
_CGC_ASL_Y = (12, 1)          # asl.w #3,d1
_CGC_ADD_X = (8, 1)           # adda.w d0,a1 (address register: no flags)
_CGC_ADD_Y = (8, 1)           # adda.w d1,a1 (address register: no flags)
_CGC_RTS = (16, 1)
_CGC_COST = _add(_CGC_LEA, _CGC_LOAD_X, _CGC_LOAD_Y, _CGC_MASK_Y, _CGC_ASR_X, _CGC_ASL_Y,
                _CGC_ADD_X, _CGC_ADD_Y, _CGC_RTS)


def creature_grid_cell_plan(machine, registers):
    """00AA38: pure RAM/ROM reads, one unconditional path, no store; the last flag-setter is
    asl.w #3,d1 (both adda.w that follow leave CCR untouched, same as grid_cell_plan's own asl)."""
    from .game import creatures
    if registers['pc'] != CREATURE_GRID_CELL_ENTRY:
        raise UnsupportedCandidate('creature grid cell planner needs the machine parked at 00AA38')
    sr = registers['sr']
    read = _reader(machine)
    instance_ptr = registers['a5'] & 0xFFFFFF
    result = creatures.creature_grid_cell(read, instance_ptr)
    exit_sr = _asl_sr(sr, result['row_source'], 3, 2)
    d0 = (registers['d0'] & 0xFFFF0000) | result['d0']
    d1 = (registers['d1'] & 0xFFFF0000) | result['d1']
    sp = registers['a7']
    return AtomicPlan(cycles=_CGC_COST[0], instructions=_CGC_COST[1], writes=(),
                      registers={'d0': d0, 'd1': d1, 'a1': result['a1'],
                                 'a7': (sp + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp & 0xFFFFFF), 'sr': exit_sr},
                      last_pc=CREATURE_GRID_CELL_LAST_PC)


# --- 00AD68: the ground-edge test (game/creatures.py: ground_edge_test) ------------------------------
#
# The second of the six further callees.  Cost per witnessed arm from the tracer
# (artifacts/gods/evidence/census-00AD68-*); 'cell-low' and 'cell-high' (the flag actually matches) are
# real ROM, declined, unwitnessed by any of the four recordings that reach this leaf.
GROUND_EDGE_TEST_ENTRY, GROUND_EDGE_TEST_LAST_PC = 0x00AD68, 0x00AD86
_GET_MOVEQ_D1 = (4, 1)            # moveq #0,d1
_GET_CMP_LOW = (12, 1)            # cmpi.b #1,(a1)
_GET_BEQ_LOW = {True: (10, 1), False: (8, 1)}     # beq.b $ad84 -- taken: 'cell-low', unwitnessed
_GET_LOAD_X = (8, 1)              # move.w (a5),d0
_GET_MASK_X = (8, 1)              # andi.w #$1f,d0
_GET_CMP_EDGE = (8, 1)            # cmpi.w #8,d0
_GET_BLT_EDGE = {True: (10, 1), False: (8, 1)}    # blt.b $ad86 -- taken: 'no-match-near-edge'
_GET_CMP_HIGH = (16, 1)           # cmpi.b #1,$1(a1)
_GET_BNE_HIGH = {True: (10, 1), False: (8, 1)}    # bne.b $ad86 -- taken: 'no-match'; not taken: 'cell-high', unwitnessed
_GET_RTS = (16, 1)
_GET_NEAR_EDGE_COST = _add(_GET_MOVEQ_D1, _GET_CMP_LOW, _GET_BEQ_LOW[False], _GET_LOAD_X, _GET_MASK_X,
                          _GET_CMP_EDGE, _GET_BLT_EDGE[True], _GET_RTS)
_GET_NO_MATCH_COST = _add(_GET_MOVEQ_D1, _GET_CMP_LOW, _GET_BEQ_LOW[False], _GET_LOAD_X, _GET_MASK_X,
                         _GET_CMP_EDGE, _GET_BLT_EDGE[False], _GET_CMP_HIGH, _GET_BNE_HIGH[True], _GET_RTS)


def ground_edge_test_plan(machine, registers):
    """00AD68: the witnessed arms only ('cell-low'/'cell-high' -- the flag itself found -- decline).

    'no-match-near-edge': the last flag-setter is cmpi.w #8,d0 (the low-5-bits test).
    'no-match': the last flag-setter is cmpi.b #1,$1(a1) (the second cell byte test).
    """
    from .game import creatures
    if registers['pc'] != GROUND_EDGE_TEST_ENTRY:
        raise UnsupportedCandidate('ground edge test planner needs the machine parked at 00AD68')
    sr = registers['sr']
    read = _reader(machine)
    cell_addr = registers['a1'] & 0xFFFFFF
    x = read(registers['a5'] & 0xFFFFFF, 2) & 0xFFFF
    result = creatures.ground_edge_test(read, cell_addr, x)
    if result['arm'] in ('cell-low', 'cell-high'):
        raise UnsupportedCandidate(f"ground edge test arm not witnessed by a recording: {result['arm']}")
    d0 = (registers['d0'] & 0xFFFF0000) | result['x_low5']
    # moveq #0,d1 (the routine's own first instruction, unconditional) clears the WHOLE 32-bit
    # register, and the only other write to it (moveq #1,d1, the declined 'found' arms) does too --
    # unlike the word-only ops in this routine's own D0, D1's own upper half is never preserved from
    # entry (--perturb-upper-halves caught this: 18 Sep, real defect, not a guess).
    d1 = result['d1'] & 0xFFFFFFFF
    sp = registers['a7']
    if result['arm'] == 'no-match-near-edge':
        cost = _GET_NEAR_EDGE_COST
        exit_sr = _cmp_sr(sr, result['x_low5'], 8, 2)
    else:
        cost = _GET_NO_MATCH_COST
        exit_sr = _cmp_sr(sr, result['high'], 1, 1)
    return AtomicPlan(cycles=cost[0], instructions=cost[1], writes=(),
                      registers={'d0': d0, 'd1': d1, 'a7': (sp + 4) & 0xFFFFFFFF,
                                 'pc': _return(machine, sp & 0xFFFFFF), 'sr': exit_sr},
                      last_pc=GROUND_EDGE_TEST_LAST_PC)


# --- 0044C0/004550: the trail check (game/trail.py) -- event kind 6 ---------------------------------
#
# Raised the same way kind 3 (00462C) is: the tile scan's own preamble (0077BE-007876) jsr's straight
# into this routine's own head.  A caller-register-free leaf (every input is a fixed work-RAM address)
# that saves and restores all eight data registers around the whole call.  'found' (a recorded slot's
# own box contains the current position) stops the scan of the six-slot ring immediately with no RAM
# effect beyond the unconditional scratch copy at TRAIL_LAST_POSITION; 'exhausted' (no slot matches)
# is real ROM code this module does not model (the ring shift, the counter, the 007B4C call) and
# declines -- rare (13 of 903 occurrences on the main history alone, `--classifier entry`, 18 Sep).
# Costs from artifacts/gods/evidence/census-0044C0/0044C0-entry-p0.state (the exhaustion trace) and
# -p1.state (a single-slot 'found', matching this model's own total exactly: 382 cycles, 26 instructions).
TRAIL_CHECK_ENTRY, TRAIL_CHECK_LAST_PC = 0x0044C0, 0x00454E
_TR_HEAD = (72 + 28 + 12 + 12, 4)          # movem.l d0-d7,-(a7); move.l F18C,F1EC; move.w F18C,d0; move.w F18E,d1
_TR_SLOT_LOAD = (12 + 12, 2)               # move.w sx,d2; move.w sy,d3 -- the SAME cost for every slot (0-5)
_TR_BSR = (18, 1)                          # bsr.b $4550
_TR_BOX_COMMON = (4 + 4 + 4 + 4 + 8 + 8, 6)   # moveq;moveq;add;add;subi;subi (004550's own head)
_TR_CMP_PASS = (4 + 8, 2)                  # cmp.w;Bcc.b not taken -- one of the four chained comparisons
_TR_CMP_FAIL = (4 + 10, 2)                 # cmp.w;Bcc.b taken -- the one that actually fails
_TR_SUCCESS_EXIT = (14 + 20, 2)            # clr.w -(a7); rtr (all four comparisons passed: 'found')
_TR_FAIL_EXIT = (12 + 20, 2)               # move.w #$8,-(a7); rtr (one comparison failed: try the next slot)
_TR_BPL_TAKEN = (10, 1)                    # bpl.b taken: 'found', stop scanning
_TR_BPL_NOT = (8, 1)                       # bpl.b not taken: continue to the next slot
_TR_RESTORE_TAIL = (76 + 16, 2)            # movem.l (a7)+,d0-d7; rts
# Each slot's own bsr into 004550 (sp-36 relative to 0044C0's own entry a7, one level below the
# movem.l frame at sp-32) and the RTR trick's own transient CCR push (sp-38) reuse the SAME two stack
# slots every time -- only the FOUND slot's own residue survives (0044DC/E8/F4/004500/0C/18, one per
# slot, and the CCR word 0x0000 clr.w always writes for a 'found' outcome).
_TR_SLOT_RETURN = (0x0044DC, 0x0044E8, 0x0044F4, 0x004500, 0x00450C, 0x004518)


def _trail_check_resolve(read):
    """0044C0's own 'found' arm: the whole scan, from the head through whichever slot matches.
    Raises ``UnsupportedCandidate`` for 'exhausted' (real code this module does not model).  Returns
    the cost, ``writes`` (TRAIL_LAST_POSITION only -- the caller adds its own sp-relative residue) and
    ``found_slot`` (which of the six slots stopped the scan)."""
    from .game import player, trail
    x, y = read(player.POSITION_X, 2), read(player.POSITION_Y, 2)
    result = trail.trail_check(read, x, y)
    cycles, instructions = _TR_HEAD
    writes = dict(_bytes(trail.TRAIL_LAST_POSITION & 0xFFFFFF, ((x << 16) | y) & 0xFFFFFFFF, 4))
    for check in result['checks']:
        sl_c, sl_i = _TR_SLOT_LOAD
        cycles, instructions = cycles + sl_c, instructions + sl_i
        bsr_c, bsr_i = _TR_BSR
        cycles, instructions = cycles + bsr_c, instructions + bsr_i
        bh_c, bh_i = _TR_BOX_COMMON
        cycles, instructions = cycles + bh_c, instructions + bh_i
        if check['hit']:
            passes = 4
        else:
            passes = check['fail_at']
        pass_c, pass_i = _TR_CMP_PASS
        cycles, instructions = cycles + passes * pass_c, instructions + passes * pass_i
        if check['hit']:
            exit_c, exit_i = _TR_SUCCESS_EXIT
            cycles, instructions = cycles + exit_c, instructions + exit_i
            bpl_c, bpl_i = _TR_BPL_TAKEN
            cycles, instructions = cycles + bpl_c, instructions + bpl_i
            break
        fail_c, fail_i = _TR_CMP_FAIL
        cycles, instructions = cycles + fail_c, instructions + fail_i
        exit_c, exit_i = _TR_FAIL_EXIT
        cycles, instructions = cycles + exit_c, instructions + exit_i
        bpl_c, bpl_i = _TR_BPL_NOT
        cycles, instructions = cycles + bpl_c, instructions + bpl_i
    else:
        raise UnsupportedCandidate('trail check: the exhaustion arm (007B4C) is not recovered')
    rt_c, rt_i = _TR_RESTORE_TAIL
    cycles, instructions = cycles + rt_c, instructions + rt_i
    # movem.l (a7)+,d0-d7 restores every data register to its OWN entry value (the whole frame was
    # pushed unconditionally at the head, and nothing inside the 'found' arm touches the stack again
    # beyond the RTR trick's own transient push/pop) -- so the caller's entry d0-d7 survive untouched;
    # only a7/pc/sr change, exactly like the clean tail arm's own registers this composes into.
    return {'cycles': cycles, 'instructions': instructions, 'writes': writes, 'found_slot': check['index']}


def _trail_check_frame_writes(sp, entry_registers, found_slot):
    """The transient stack residue any caller of ``_trail_check_resolve`` must add on top of its own
    writes: the movem.l frame (sp-32..sp-1, the entry d0-d7 values) and the found slot's own bsr
    return address / clr.w CCR word (sp-36/sp-38, one level below the frame -- see the module note)."""
    writes = {}
    for index, name in enumerate(('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7')):
        for a, b in _bytes((sp - 32 + 4 * index) & 0xFFFFFF, entry_registers[name] & 0xFFFFFFFF, 4):
            writes[a] = b
    for a, b in _bytes((sp - 36) & 0xFFFFFF, _TR_SLOT_RETURN[found_slot], 4):
        writes[a] = b
    for a, b in _bytes((sp - 38) & 0xFFFFFF, 0, 2):
        writes[a] = b
    return writes


def trail_check_plan(machine, registers):
    """0044C0: the trail check, parked directly at its own entry (a standalone gate, `evaluator_plan`'s
    own shape: no caller-register inputs at all, every fact read from fixed work RAM)."""
    if registers['pc'] != TRAIL_CHECK_ENTRY:
        raise UnsupportedCandidate('trail check planner needs the machine parked at 0044C0')
    sp32 = registers['a7']
    sp = sp32 & 0xFFFFFF
    resolved = _trail_check_resolve(_reader(machine))
    writes = dict(resolved['writes'])
    writes.update(_trail_check_frame_writes(sp, registers, resolved['found_slot']))
    exit_registers = {'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp)}
    return AtomicPlan(cycles=resolved['cycles'], instructions=resolved['instructions'],
                      writes=tuple(writes.items()), registers=exit_registers,
                      last_pc=TRAIL_CHECK_LAST_PC)


# --- 0075D6: the player state machine's shared tail (game/player.py, game/camera.py) ---------------
#
# A platform-tail seam (recipe 6b, 0018C8's and 0047DA's own shape), per the supervisor's Decision
# (``docs/gods/blockers/2026-09-17-005700.md``).  Reached by a plain ``bra.w`` from every witnessed
# state handler and the dispatcher's own 'inactive' arm, so there is no frame of its own on the
# stack: the top of stack, throughout, is whatever 005700's own true caller's ``jsr`` left there.
# The prefix, in ROM order: the tile trigger scan (``game.player.tile_trigger_scan``), composed with
# its own found-tile arm (``event_status``, a strictly positive status raising one of EVENT_HANDLERS
# through the shared preamble 0077BE-007876): kind 3 (00462C, the trigger evaluator)'s own non-firing
# outcome is admitted and the scan continues, up to six raises per activation; every other kind, the
# evaluator's own firing arm, its disabled arm and a zero status all DECLINE BY NAME (real code this
# module does not model -- docs/gods/blockers/2026-09-16-00462C-firing.md); the follow-point step
# (``game.camera.follow_point_step``, the FFFFEF4E == 0 arm only -- the
# sibling cutscene-style tracker at 00755A is unwitnessed on the full tree of all eight recordings,
# 55,326 activations, and DECLINES BY NAME); and the state-table re-index
# (``game.player.state_table_reindex``).  The ceded operation is the tail's own ``jmp 001312``
# through that second inline upload's own ``rts`` -- 0048B4's own "no intermediate resume layer"
# shape, one level further removed: that ``rts`` pops the return address that was ALREADY on the
# stack when this activation began, so there is no suffix at all, because nothing of this
# candidate's own remains once the ceded block returns.  ``resume_pc`` is that return address
# itself, read live off the stack (never a fixed ROM constant: the tail returns to different true
# callers depending on what raised it -- the main loop's own per-tick dispatch, or a nested
# reentry the tile scan's own 'trigger' cascade can reach before falling back here, witnessed as
# 001FD6 and 012BA0 on the very same history).
PLAYER_TAIL_ENTRY = 0x0075D6
PLAYER_TAIL_UPLOAD_ENTRY = 0x001312
PLAYER_TAIL_UPLOAD_RTS = 0x0013CE       # the ceded upload's own rts: the seam's resume gate (see the suffix)
PLAYER_TAIL_LAST_PC = 0x0076AA          # jmp $1312.l: the prefix's own last instruction

_PT_HEAD = _add((12, 1), (12, 1), (18, 1), (12, 1))     # 0075D6 store; 0075DA push d7; 0075DC bsr; 0075E0 pop d7

# 00773A's own cost, generalised (18 Sep) from the two fixed clean-arm constants it replaces
# (224,22 narrow / 312,31 wide, still exactly reproduced by _tile_scan_cost when scan['checks'] is
# empty -- see test_player_tail.py) to every triggered cell whose own event_status declines: each
# such cell adds 0077A8's own call overhead (bsr, or bra for the scan's absolute last position, only
# reachable when widen) and its decline body (0077A8's head through its own bmi/beq-taken rts --
# game.player.event_status arm == 'declined').  An admitted event (arm == 'event', kind 3) adds the
# raiser's own preamble and _trigger_evaluate_resolve's own cost instead -- see _tc_position below.
_TC_TEST = (12, 1)                      # cmpi.b #2,(a0)
_TC_SKIP = (10, 1)                      # bls.b taken: not triggered
_TC_CALL_MID = (8 + 18, 1 + 1)          # bls.b not taken (8,1) + bsr.b $77a8 (18,1)
_TC_CALL_LAST = (8 + 10, 1 + 1)         # bls.b not taken (8,1) + bra.b $77a8 (10,1) -- position 5 only
_TC_ADV = (8, 1)                        # lea.l $80(a0),a0
_TC_ADV3 = (8, 1)                       # lea.l -$101(a0),a0 (the column switch, position 2->3)
_TC_WIDEN_NARROW = (12 + 8 + 8 + 10, 4)    # move.w;andi;cmpi;blt TAKEN (not widen: ends at position 2)
_TC_WIDEN_WIDE = (12 + 8 + 8 + 8, 4)       # move.w;andi;cmpi;blt NOT taken (widen: continues to position 3)
_TC_FINAL_RTS = (16, 1)                 # 0077A6 rts
_TC_POSITION_RETURN = (0x00775C, 0x007768, 0x007774, 0x00778E, 0x00779A)   # positions 0-4's own bsr
_TC_HEAD = _add((4, 1), (12, 1), (12, 1), (8, 1), (16, 1), (12, 1), (8, 1), (8, 1), (8, 1))
# 00773A..007752: moveq; add.w F18C; move.w F18E; andi; asr; asl; lea 885E; adda d0; adda d1

# 0077A8's own head (move.l a0,-(a7) through move.w (a0),d0 -- the status word read) plus its
# WITNESSED decline tail (bmi taken: status < 0; 517 of 654 retained fixtures, 0 mismatches), ending
# at 00787A's own rts.  The status == 0 tail (bmi not taken -- 12cy, not 8: a real defect caught 18
# Sep by cross-checking against a status > 0 trace before any fixture exercised it -- then beq taken)
# is a DIFFERENT, unwitnessed cost (game.player.event_status arm == 'declined-zero'), declined by name
# in _tc_position below the moment the scan actually reaches it.
_ES_HEAD = _add((12, 1), (4, 1), (8, 1), (4, 1), (12, 1), (4, 1), (4, 1), (8, 1), (8, 1))
_ES_DECLINE_NEG = _add((10, 1), (12, 1), (16, 1))          # bmi taken; movea (a7)+,a0; rts

# A STRICTLY POSITIVE status (arm == 'event') raises one of EVENT_HANDLERS through a shared preamble
# (0077BE-007876): both branches of _ES_HEAD's own status test fall through (not taken), then ten
# unconditional flag-word checks (real code, no recording has ever been seen with any of them set --
# game.player's own docstring) and the table dispatch itself.  Only kind 3 (00462C, the trigger
# evaluator) is modelled past this point -- every other kind is declined by name -- and only 00462C's
# own non-firing arm (at least one of a record's three conditions false) is admitted; the firing arm
# (all three hold) stands declined, docs/gods/blockers/2026-09-16-00462C-firing.md's own
# NEW_GODS_SUBSYSTEM.  Costs from artifacts/gods/evidence/census-0075D6/parent-00773A-entry-p4/p15.state.
_ES_EVENT_BRANCHES = _add((12, 1), (12, 1))                # 0077BE bmi.w / 0077C2 beq.w, both NOT taken
_ES_EVENT_FLAGS = _add(*([(20, 1), (10, 1)] * 10))          # 0077C6-00785E: ten (cmpi.b; bne.b not taken)
_ES_EVENT_DISPATCH = _add((4, 1), (4, 1), (4, 1), (12, 1), (18, 1), (16, 1))
# 007866-007876: subq.w #1,d0; add.w d0,d0 (x2); lea.l 4494,a1; movea.l (a1,d0.w),a1; jsr (a1)
_ES_EVENT_HEAD = _add(_ES_EVENT_BRANCHES, _ES_EVENT_FLAGS, _ES_EVENT_DISPATCH)
_ES_EVENT_CLOSE = _add((12, 1), (16, 1))    # 007878 movea.l (a7)+,a0; 00787A rts -- 00462C's own rts (004688)
                                             # pops straight back into THIS same exit, same as a decline's own
_ES_EVENT_JSR_RETURN = 0x007878             # the raiser's own return address (jsr (a1), fixed)
# 00462C's own three internal bsr's into 00470C (_TE_RETURN_PC above) always run, in order, on any
# non-firing raise -- only the LAST one's own return address survives (the reused stack slot).
_ES_EVENT_PAIR_RETURN = _TE_RETURN_PC[-1]


def _trigger_evaluate_resolve(read, status_address, *, entry_a4, entry_d1):
    """The raise dispatch's own call into 00462C (jsr (a1), a0 = ``status_address``): a thin wrapper
    over ``_evaluator_resolve`` (the SAME cost/register model ``evaluator_plan`` uses standalone -- the
    trigger evaluator's own shape does not change with who calls it, the way ``achievement_slot_
    dispatch`` reuses ``achievement_slot_reset_plan``); 00462C's own head re-reads the record index from
    ``2(a0)`` itself (``game.player.event_status`` already read the SAME word as ``record_index``, kept
    there for its own report, not needed again here).  d0/d1/d5/d6's own upper half and a5 are
    recombined by ``player_tail_plan`` itself the same way for every raise (only their low words --
    and a1/a2/a3/a4 in full -- are exposed here); ``entry_a4``/``entry_d1`` (low word only: 00470C
    never depends on entry d1, only threads its OWN low word through, the way a kind 5/6/11/12
    condition threads a4) are the only inputs, carried across however many raises one activation
    makes since nothing else ever touches either.  Raises ``UnsupportedCandidate`` for the disabled
    arm, an unrecovered/unwitnessed condition kind, or the firing arm (both left to
    ``_evaluator_resolve`` -- docs/gods/blockers/2026-09-16-00462C-firing.md).
    """
    resolved = _evaluator_resolve(read, 0, status_address & 0xFFFFFFFF, entry_d1 & 0xFFFF, 0, 0, entry_a4, 0)
    registers = dict(resolved['registers'])
    registers['d0'] = registers['d0'] & 0xFFFF0000
    registers['d1'] = registers['d1'] & 0xFFFF
    return {'cycles': resolved['cycles'], 'instructions': resolved['instructions'],
           'writes': resolved['writes'], 'registers': registers}


def _tc_position(read, check, raise_sp, entry_a4, entry_d1, entry_regs, *, bra=False):
    """One of 00773A's own six candidate positions: the test, then a skip (not triggered) or a call
    into 0077A8 (``check``, the corresponding entry of ``scan['checks']``, or ``None``) -- ``bra`` for
    the scan's own absolute last position (widen only), which tail-branches instead of calling, so a
    triggered position 5 leaves control in 0077A8's own rts rather than returning here at all.  A
    'declined' check costs only.  An admitted 'event' also returns a dict as the fourth element
    (``None`` otherwise): kind 3 (00462C's own non-firing arm, ``_trigger_evaluate_resolve``) carries
    a ``'registers'`` key (the caller threads a1/a2/a3/a4/a5/d0/d1/d5/d6 forward); kind 6 (0044C0's
    own 'found' arm, ``_trail_check_resolve``) carries none at all -- its own register frame is pushed
    and fully restored, so nothing survives past its own rts, and its own dict carries ``'writes'``
    only.  ``raise_sp`` is this position's own a7 right after the raiser's ``jsr (a1)`` (the SAME
    depth for every kind, one call below the tile scan's own residue slot at ``raise_sp + 4``);
    ``entry_regs`` is the WHOLE tail activation's own entry registers (d2/d3/d4/d7 never change
    before any raise, so a kind-6 raise's own transient register-frame push reads them straight)."""
    cycles, instructions = _TC_TEST
    if check is None:
        c, i = _TC_SKIP
        return cycles + c, instructions + i, False, None
    c, i = _TC_CALL_LAST if bra else _TC_CALL_MID
    cycles, instructions = cycles + c, instructions + i
    arm = check['arm']
    if arm == 'declined':
        cycles += _ES_HEAD[0] + _ES_DECLINE_NEG[0]
        instructions += _ES_HEAD[1] + _ES_DECLINE_NEG[1]
        return cycles, instructions, bra, None
    if arm == 'declined-zero':
        raise UnsupportedCandidate('shared tail: the tile trigger scan found a zero-status cell (0077A8), '
                                   'unwitnessed by any of the eight recordings')
    assert arm == 'event', check
    cycles += _ES_HEAD[0]
    instructions += _ES_HEAD[1]
    eh_c, eh_i = _ES_EVENT_HEAD
    cycles, instructions = cycles + eh_c, instructions + eh_i
    if check['handler'] == 0x00462C:
        resolve = _trigger_evaluate_resolve(read, check['status_address'], entry_a4=entry_a4, entry_d1=entry_d1)
        resolve = dict(resolve, writes=dict(resolve['writes']))
        for a, b in _bytes((raise_sp - 4) & 0xFFFFFF, _ES_EVENT_PAIR_RETURN, 4):
            resolve['writes'][a] = b
    elif check['handler'] == 0x0044C0:
        trail = _trail_check_resolve(read)
        # The raiser's own dispatch computes d0 = (status - 1) * 4 (007866-00786A: subq #1; add d0,d0
        # (x2)) as the table OFFSET, not the status itself -- for kind 6 that is (6-1)*4 = 0x14, and
        # 0044C0 never touches d0 again before its own movem push, so THAT value (not the raw status
        # word) is what its own transient frame residue must carry.
        dispatch_d0 = ((check['kind'] - 1) * 4) & 0xFFFF
        frame_regs = {'d0': dispatch_d0, 'd1': (entry_regs['d1'] & 0xFFFF0000) | (entry_d1 & 0xFFFF),
                     'd2': entry_regs['d2'], 'd3': entry_regs['d3'], 'd4': entry_regs['d4'],
                     'd5': entry_regs['d5'], 'd6': entry_regs['d6'], 'd7': entry_regs['d7']}
        writes = dict(trail['writes'])
        writes.update(_trail_check_frame_writes(raise_sp, frame_regs, trail['found_slot']))
        # The raiser's own dispatch (007872 movea.l (a1,d0.w),a1) leaves a1 = the handler's own
        # address before the jsr; 00462C immediately overwrites it (lea.l TRIGGER_TABLE,a1) but
        # 0044C0 never touches a1 at all (only absolute addressing throughout), so it rides through
        # to the tail's own final exit exactly as the dispatch left it -- 0x0044C0 itself.
        resolve = {'cycles': trail['cycles'], 'instructions': trail['instructions'], 'writes': writes,
                  'registers': {'a1': 0x0044C0}}
    else:
        raise UnsupportedCandidate(f"shared tail: the tile trigger scan found an event (0077A8), kind "
                                   f"{check['kind']}, unwitnessed here")
    cycles, instructions = cycles + resolve['cycles'], instructions + resolve['instructions']
    close_c, close_i = _ES_EVENT_CLOSE
    cycles, instructions = cycles + close_c, instructions + close_i
    return cycles, instructions, bra, resolve


def _tile_scan_cost(read, scan, sp, entry_a4, entry_registers, tile_row_d1):
    """00773A's own total cost (cycles, instructions), every RAM write the scan itself abandons (the
    per-position stack residue at sp-12/sp-16, generalised below to the deeper residue an admitted
    event's own nested calls leave below that, or, past widen's last (bra) position, sp-12/sp-16 --
    ``sp`` is THIS activation's own entry a7, matching ``player_tail_plan``'s own ``order`` dict
    convention: 'the tracer only sees the bytes that changed', so a write that matches stale RAM is
    harmless) and the LAST admitted KIND-3 event's own register residue (``None`` if the scan raised
    no kind-3 event a raise could resolve -- a kind-6 'found' leaves nothing at the outer level: its
    own frame is pushed and fully restored).  ``entry_a4`` is this ACTIVATION's own entry a4 (before
    the scan even starts), the value the first raise's own possibly-untouched a4 falls back to.
    Reduces to the two constants this once was when ``scan['checks']`` is empty (the fully clean arm)."""
    by_index = {c['index']: c for c in scan['checks']}
    widen = scan['widen']
    cycles, instructions = _TC_HEAD
    writes = {}
    registers = None
    a4_carry = entry_a4   # a4 changes only on a condition kind that sets it (5/6/11/12); once set, later
                       # raises whose own three pairs never touch it again leave it exactly as the last
                       # raise that did -- 68000 registers only change when something writes them.
    d1_carry = tile_row_d1 & 0xFFFF   # d1's own low word: NOT the activation's own entry d1 -- 00773A's
                       # own head (moveq..asl.w #3,d1) sets it to the tile row unconditionally, before
                       # any position is even tested, and nothing after that touches it again except a
                       # kind 9/10 condition (the SAME carry shape as a4) -- needed live (not just for
                       # the final exit) by a later kind-6 raise's own register-frame push.
    d5_carry = entry_registers['d5'] & 0xFFFF   # d5/d6's own low words: unlike d1, 00773A's own head
    d6_carry = entry_registers['d6'] & 0xFFFF   # never touches them, so they start at the activation's
                       # own entry value -- but a PRECEDING kind-3 raise's own last pair always sets
                       # both fresh (every pair does, kind 0 included), so a later kind-6 raise's own
                       # register-frame push must see whatever that raise left them as, not the
                       # activation's own original entry (the SAME carry shape as a4/d1).
    d0_upper = None    # 0077A8's own `moveq #0,d0` (0077AA) resets d0's upper half on EVERY call, an
                       # event's own condition calls aside -- unlike a1/a2/a3/a4/a5/d1/d5/d6, a PLAIN
                       # decline touches this too, so it is tracked across every check, not only events.

    def _position(index, *, bra=False):
        nonlocal cycles, instructions, registers, a4_carry, d1_carry, d5_carry, d6_carry, d0_upper
        check = by_index.get(index)
        cell_slot = (sp - 12) if index == 5 else (sp - 16)
        raise_regs = dict(entry_registers, d5=(entry_registers['d5'] & 0xFFFF0000) | d5_carry,
                          d6=(entry_registers['d6'] & 0xFFFF0000) | d6_carry)
        c, i, ended, resolve = _tc_position(read, check, cell_slot - 4, a4_carry, d1_carry, raise_regs, bra=bra)
        cycles, instructions = cycles + c, instructions + i
        if check is not None:
            d0_upper = 0
            if index != 5:
                for a, b in _bytes((sp - 12) & 0xFFFFFF, _TC_POSITION_RETURN[index], 4):
                    writes[a] = b
            for a, b in _bytes(cell_slot & 0xFFFFFF, scan['cells'][index] & 0xFFFFFFFF, 4):
                writes[a] = b
            if resolve is not None:
                for a, b in _bytes((cell_slot - 4) & 0xFFFFFF, _ES_EVENT_JSR_RETURN, 4):
                    writes[a] = b
                writes.update(resolve['writes'])
                if 'registers' in resolve:
                    # MERGE, never replace: a kind-6 raise's own dict carries only 'a1' (0044C0 never
                    # touches a2/a3/a4/a5/d0/d1/d5/d6, so whatever an EARLIER raise in this same
                    # activation left them as -- or the original caller's own entry, if none -- must
                    # keep riding through); a kind-3 raise's own dict always carries all of them fresh.
                    registers = {**(registers or {}), **resolve['registers']}
                    if 'd0' in resolve['registers']:
                        d0_upper = resolve['registers']['d0']
                    if 'd1' in resolve['registers']:
                        d1_carry = resolve['registers']['d1']
                    if 'd5' in resolve['registers']:
                        d5_carry = resolve['registers']['d5'] & 0xFFFF
                    if 'd6' in resolve['registers']:
                        d6_carry = resolve['registers']['d6'] & 0xFFFF
                    if 'a4' in resolve['registers']:
                        a4_carry = resolve['registers']['a4']   # falls back to entry_a4 (this closure's
                                                  # a4_carry) when nothing in this particular raise
                                                  # touches it, so this is a no-op unless a kind
                                                  # 5/6/11/12 condition just set a NEW value.
        return ended

    for position in (0, 1):
        _position(position)
        cycles, instructions = cycles + _TC_ADV[0], instructions + _TC_ADV[1]
    _position(2)
    widen_cost = _TC_WIDEN_WIDE if widen else _TC_WIDEN_NARROW
    cycles, instructions = cycles + widen_cost[0], instructions + widen_cost[1]
    if not widen:
        return cycles + _TC_FINAL_RTS[0], instructions + _TC_FINAL_RTS[1], writes, registers, d0_upper
    cycles, instructions = cycles + _TC_ADV3[0], instructions + _TC_ADV3[1]
    for position in (3, 4):
        _position(position)
        cycles, instructions = cycles + _TC_ADV[0], instructions + _TC_ADV[1]
    ended = _position(5, bra=True)
    if not ended:
        cycles, instructions = cycles + _TC_FINAL_RTS[0], instructions + _TC_FINAL_RTS[1]
    return cycles, instructions, writes, registers, d0_upper


_PT_FOLLOW_HEAD = _add((12, 1), (12, 1), (12, 1), (12, 1), (12, 1), (10, 1))   # 0075E2..0075F6 (taken: EF4E==0)

# The x band (007600-00762B): a fixed step of four, clamped to 0/0xEC0.
_PT_X_TEST = (8, 1)                                            # 007600 cmpi.w #$50,d0
_PT_X_DEC_NOTTAKEN = (8, 1)                                     # 007604 bgt (not taken: dx<=0x50)
_PT_X_DEC_BODY = (16, 1)                                        # 007606 subq.w #4,FOLLOW_X
_PT_X_DEC_CHECK_HOLD, _PT_X_DEC_CHECK_CLAMP = (10, 1), (8, 1)   # 00760A bpl
_PT_X_DEC_CLAMP = (16, 1)                                       # 00760C clr.w FOLLOW_X
_PT_X_DEC_CLAMP_BRA = (10, 1)                                   # 007610 bra.b (taken)
_PT_X_INC_TAKEN = (10, 1)                                       # 007604 bgt (taken: dx>0x50)
_PT_X_INC_SETUP = _add((8, 1), (4, 1))                          # 007612 move #$d0,d3; 007616 cmp.w d3,d0
_PT_X_INC_CHECK_HOLD, _PT_X_INC_CHECK_INCREASE = (10, 1), (8, 1)   # 007618 blt
_PT_X_INC_BODY = _add((16, 1), (16, 1))                         # 00761A addq.w #4,FOLLOW_X; 00761E cmpi #$ec0
_PT_X_INC_CLAMP_CHECK_OK, _PT_X_INC_CLAMP_CHECK_CLAMP = (10, 1), (8, 1)   # 007624 blt
_PT_X_INC_CLAMP = (16, 1)                                       # 007626 move.w #$ec0,FOLLOW_X
_PT_X_COST = {
    'decrease': _add(_PT_X_TEST, _PT_X_DEC_NOTTAKEN, _PT_X_DEC_BODY, _PT_X_DEC_CHECK_HOLD),
    'decrease-clamped': _add(_PT_X_TEST, _PT_X_DEC_NOTTAKEN, _PT_X_DEC_BODY, _PT_X_DEC_CHECK_CLAMP,
                             _PT_X_DEC_CLAMP, _PT_X_DEC_CLAMP_BRA),
    'hold': _add(_PT_X_TEST, _PT_X_INC_TAKEN, _PT_X_INC_SETUP, _PT_X_INC_CHECK_HOLD),
    'increase': _add(_PT_X_TEST, _PT_X_INC_TAKEN, _PT_X_INC_SETUP, _PT_X_INC_CHECK_INCREASE,
                     _PT_X_INC_BODY, _PT_X_INC_CLAMP_CHECK_OK),
    # 'increase-clamped' (FOLLOW_X reaching 0xEC0): unwitnessed by any of the eight recordings -- declined.
}

# The y band (00762C-00766C): half the distance beyond the band (minimum one), clamped to 0/0x340.
_PT_Y_TEST = (8, 1)                                             # 00762C cmpi.w #$70,d1
_PT_Y_CHECK1_LOW, _PT_Y_CHECK1_HIGH = (10, 1), (8, 1)           # 007630 ble (taken: dy<=0x70)
_PT_Y_INC_SETUP = _add((4, 1), (8, 1), (8, 1))                  # 007632 move; 007634 subi #$70; 007638 asr #1
_PT_Y_INC_ROUND_OK = (10, 1)                                    # 00763A bne (taken: the raw step is nonzero) --
                                                                 # the not-taken arm (the minimum-of-one override,
                                                                 # 00763C addq) is unwitnessed by any recording.
_PT_Y_INC_ADD = (16, 1)                                         # 007640 add.w d3,FOLLOW_Y
_PT_Y_INC_TEST2 = (16, 1)                                       # 007644 cmpi.w #$340,FOLLOW_Y
_PT_Y_INC_CLAMP_CHECK_OK, _PT_Y_INC_CLAMP_CHECK_CLAMP = (10, 1), (8, 1)   # 00764A blt
_PT_Y_INC_CLAMP = (16, 1)                                       # 00764C move.w #$340,FOLLOW_Y
_PT_Y_INC_CLAMP_BRA = (10, 1)                                   # 007652 bra.b (taken)
_PT_Y_TEST3 = (8, 1)                                            # 007654 cmpi.w #$20,d1
_PT_Y_CHECK2_HOLD, _PT_Y_CHECK2_DECREASE = (10, 1), (8, 1)      # 007658 bge (taken: dy>=0x20)
_PT_Y_DEC_SETUP = _add((4, 1), (4, 1), (8, 1))                  # 00765A moveq #$20; 00765C sub.w d1; 00765E asr #1
_PT_Y_DEC_ROUND_OK, _PT_Y_DEC_ROUND_MIN = (10, 1), (8, 1)       # 007660 bne
_PT_Y_DEC_MIN = (16, 1)                                         # 007662 subq.w #1,FOLLOW_Y (the minimum override)
_PT_Y_DEC_SUB = (16, 1)                                         # 007666 sub.w d3,FOLLOW_Y
_PT_Y_DEC_CLAMP_CHECK_OK = (10, 1)                              # 00766A bpl (taken: not clamped) -- the not-taken
                                                                 # arm (the clamp to 0, 00766C clr.w) is
                                                                 # unwitnessed by any recording.
_PT_Y_HOLD_COST = _add(_PT_Y_TEST, _PT_Y_CHECK1_LOW, _PT_Y_TEST3, _PT_Y_CHECK2_HOLD)
_PT_Y_INCREASE_COST = _add(_PT_Y_TEST, _PT_Y_CHECK1_HIGH, _PT_Y_INC_SETUP, _PT_Y_INC_ROUND_OK,
                           _PT_Y_INC_ADD, _PT_Y_INC_TEST2, _PT_Y_INC_CLAMP_CHECK_OK)
_PT_Y_INCREASE_CLAMPED_COST = _add(_PT_Y_TEST, _PT_Y_CHECK1_HIGH, _PT_Y_INC_SETUP, _PT_Y_INC_ROUND_OK,
                                   _PT_Y_INC_ADD, _PT_Y_INC_TEST2, _PT_Y_INC_CLAMP_CHECK_CLAMP,
                                   _PT_Y_INC_CLAMP, _PT_Y_INC_CLAMP_BRA)
_PT_Y_DECREASE_COST_OK = _add(_PT_Y_TEST, _PT_Y_CHECK1_LOW, _PT_Y_TEST3, _PT_Y_CHECK2_DECREASE,
                              _PT_Y_DEC_SETUP, _PT_Y_DEC_ROUND_OK, _PT_Y_DEC_SUB, _PT_Y_DEC_CLAMP_CHECK_OK)
_PT_Y_DECREASE_COST_MIN = _add(_PT_Y_TEST, _PT_Y_CHECK1_LOW, _PT_Y_TEST3, _PT_Y_CHECK2_DECREASE,
                               _PT_Y_DEC_SETUP, _PT_Y_DEC_ROUND_MIN, _PT_Y_DEC_MIN, _PT_Y_DEC_SUB,
                               _PT_Y_DEC_CLAMP_CHECK_OK)
# 'decrease-clamped' (FOLLOW_Y reaching 0): unwitnessed by any of the eight recordings -- declined.

# The state-table re-index (007670-0076AA): fully witnessed, every branch (both mask tables, both
# flip outcomes -- 5,137 clean activations of the whole tail checked on the main history alone).
_PT_RE_HEAD = _add((12, 1), (12, 1), (8, 1), (18, 1), (4, 1), (16, 1))   # 007670..007680
_PT_RE_SPLIT_TEST = (8, 1)                                      # 007684 cmpi.w #$20,d2
_PT_RE_SPLIT_LOW, _PT_RE_SPLIT_HIGH = (10, 1), (8, 1)           # 007688 blt
_PT_RE_HIGH_LOAD = (16, 1)                                      # 00768A move.l (the high mask, d2>=0x20)
_PT_RE_TAIL = _add((4, 1), (8, 1), (4, 1), (14, 1))             # 00768E..007696
_PT_RE_BTST = (6, 1)                                            # 00769A btst.l d0,d1
_PT_RE_FLIP_CHECK_NONE, _PT_RE_FLIP_CHECK_FLIP = (10, 1), (8, 1)   # 00769C beq
_PT_RE_FLIP = (8, 1)                                            # 00769E ori.w #$8000,d2
_PT_RE_FINAL = _add((12, 1), (12, 1), (12, 1))                  # 0076A2, 0076A6, 0076AA (this prefix's last_pc)
_PT_REINDEX_COST = {}
for _mask_table, _mask_cost in (('low', _add(_PT_RE_SPLIT_TEST, _PT_RE_SPLIT_LOW)),
                                ('high', _add(_PT_RE_SPLIT_TEST, _PT_RE_SPLIT_HIGH, _PT_RE_HIGH_LOAD))):
    for _flip, _flip_cost in ((False, _PT_RE_FLIP_CHECK_NONE),
                              (True, _add(_PT_RE_FLIP_CHECK_FLIP, _PT_RE_FLIP))):
        _PT_REINDEX_COST[(_mask_table, _flip)] = _add(
            _PT_RE_HEAD, _mask_cost, _PT_RE_TAIL, _PT_RE_BTST, _flip_cost, _PT_RE_FINAL)
del _mask_table, _mask_cost, _flip, _flip_cost


def player_tail_plan(machine, registers):
    """0075D6: the player state machine's shared tail, as a platform-tail seam over the second inline
    upload (001312).  See the module note above; the game facts are ``game.player``/``game.camera``."""
    from .game import camera, player
    if registers['pc'] != PLAYER_TAIL_ENTRY:
        raise UnsupportedCandidate('player tail planner needs the machine parked at 0075D6')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    if registers['a6'] != 0xC00000:
        raise UnsupportedCandidate('player tail planner needs a6 = C00000 (the VDP data port)')
    read = _reader(machine)
    d7 = registers['d7'] & 0xFFFF
    position_x, position_y = read(player.POSITION_X, 2), read(player.POSITION_Y, 2)
    scan = player.tile_trigger_scan(read, position_x, position_y)
    if read(player.SHARED_TAIL_ALT_GATE, 2) & 0xFFFF:
        raise UnsupportedCandidate('shared tail: the FFFFEF4E cutscene-tracker arm (00755A) is unwitnessed '
                                   'by any of the eight recordings')
    follow = camera.follow_point_step(lambda address: read(address, 2), position_x, position_y)
    x_branch, y_branch = follow['x_branch'], follow['y_branch']
    if x_branch == 'increase-clamped':
        raise UnsupportedCandidate("shared tail: the follow point's own x clamp at 0xEC0 is unwitnessed "
                                   "by any of the eight recordings")
    if y_branch == 'decrease-clamped':
        raise UnsupportedCandidate("shared tail: the follow point's own y clamp at 0 is unwitnessed "
                                   "by any of the eight recordings")
    if y_branch in ('increase', 'increase-clamped') and follow['y_rounded']:
        raise UnsupportedCandidate("shared tail: the follow point's own y minimum step on the increase "
                                   "side (dy=0x71) is unwitnessed by any of the eight recordings")

    state_index = read(player.STATE_INDEX, 2)
    reindex = player.state_table_reindex(read, state_index, d7)

    cycles, instructions = _PT_HEAD
    tile_cycles, tile_instructions, tile_writes, event_registers, d0_upper = _tile_scan_cost(
        read, scan, sp, registers['a4'], registers, player.tile_row(position_y))
    cycles, instructions = cycles + tile_cycles, instructions + tile_instructions
    fh_c, fh_i = _PT_FOLLOW_HEAD
    cycles, instructions = cycles + fh_c, instructions + fh_i
    x_c, x_i = _PT_X_COST[x_branch]
    cycles, instructions = cycles + x_c, instructions + x_i
    if y_branch == 'hold':
        y_c, y_i = _PT_Y_HOLD_COST
    elif y_branch == 'increase':
        y_c, y_i = _PT_Y_INCREASE_COST
    elif y_branch == 'increase-clamped':
        y_c, y_i = _PT_Y_INCREASE_CLAMPED_COST
    elif y_branch == 'decrease':
        y_c, y_i = _PT_Y_DECREASE_COST_MIN if follow['y_rounded'] else _PT_Y_DECREASE_COST_OK
    else:
        raise UnsupportedCandidate(f'shared tail: follow point y branch {y_branch!r} not modelled')
    cycles, instructions = cycles + y_c, instructions + y_i
    re_c, re_i = _PT_REINDEX_COST[(reindex['mask_table'], reindex['flip'])]
    cycles, instructions = cycles + re_c, instructions + re_i

    order = {}
    # 0075DA/0075DC push D7, then the bsr's own return address, both popped again by the time the
    # tail's own tile scan returns (0075E0) -- the stack pointer ends up unchanged, but the tracer's
    # diff-based writes still show these bytes (whichever of them differ from what RAM already held),
    # and the strict check compares the prefix's own final RAM values, abandoned stack scratch
    # included: the plan must write them too (a plan write that happens to match what RAM already
    # held is harmless, `pathfacts.check_plan`'s own "redundant" note).
    for a, b in _bytes((sp - 4) & 0xFFFFFF, registers['d7'] & 0xFFFFFFFF, 4):
        order[a] = b
    for a, b in _bytes((sp - 8) & 0xFFFFFF, 0x0075E0, 4):
        order[a] = b
    # Every triggered cell's own 0077A8 call (bsr for positions 0-4, bra for the scan's absolute last
    # position, 5, which pushes no return address of its own) nets the stack pointer back to its own
    # entry depth by the time it returns -- but each one's own push abandons residue at sp-12 (the
    # bsr's return address, or position 5's own pushed a0, since a bra pushes nothing of its own) and
    # sp-16 (the pushed a0 of a bsr call only); an admitted event's own nested calls (the jsr into
    # 00462C, then its own three bsr's into 00470C, the last one's return address surviving) go deeper
    # still, four and eight bytes below wherever THAT position's own cell address landed.  Positions
    # 0-4 share the sp-12/sp-16 pair (only the LAST one among them survives); position 5 (bra, only
    # reachable when widen) touches only its own cell slot (sp-12) -- _tile_scan_cost computes all of
    # this in scan order, so the last write per address is whichever position actually made it last.
    order.update(tile_writes)
    for a, b in _bytes(player.STATE_COUNTER & 0xFFFFFF, d7, 2):
        order[a] = b
    for address, value in follow['stores'].items():
        for a, b in _bytes(address & 0xFFFFFF, value, 2):
            order[a] = b

    # d0's own upper half is zero from the tile scan's own head onward (00773A: moveq #$10,d0 sign-
    # extends a positive immediate to the full 32 bits) UNLESS an admitted event's own last condition
    # call (a kind 9/10 predicate's own divs remainder) left it nonzero -- every other write to d0 in
    # this whole region, on every branch, is a plain .w move or arithmetic op that leaves the upper
    # half alone from there to the tail's own final "move.w f18c,d0" (0076A2) -- not the caller's own
    # entry upper half either way, unlike every other register this planner touches.
    d0_upper = 0 if d0_upper is None else d0_upper
    high = lambda name: 0 if name == 'd0' else registers[name] & 0xFFFF0000
    d2 = ((reindex['high'] << 16) | reindex['descriptor']) & 0xFFFFFFFF
    # move.w $f18e.w,d1 (0076A6) is the last N/Z/V/C setter before the jmp on every branch (the
    # window-clamp code and 00755A's own sibling both merge back into the re-index at 007670, and
    # nothing between there and the jmp sets N/Z/V/C except the two final moves themselves) -- but X
    # is untouched by MOVE, so it survives from the LAST arithmetic instruction that does set it,
    # which is the SAME on every branch too: 007694's own add.w d2,d2 (the re-index's own doubling,
    # always executed, always after every X/Y band arithmetic and the tile scan's own): X is the
    # carry out of doubling a 16-bit value, i.e. the re-index's own index bit 15.
    exit_sr = _logic_sr(sr, position_y, 2)
    exit_sr = (exit_sr & ~0x10) | (0x10 if (reindex['index'] >> 15) & 1 else 0)
    exit_registers = {'d0': d0_upper | position_x, 'd1': (reindex['mask'] & 0xFFFF0000) | position_y,
                      'd2': d2, 'a0': 0x00005618, 'a7': sp32, 'pc': PLAYER_TAIL_UPLOAD_ENTRY, 'sr': exit_sr}
    if follow['d3'] is not None:
        # The y-decrease band's own d3 setter is `moveq #$20,d3` (007654-0076
        # 5A) -- MOVEQ sign-extends to the FULL 32-bit register, clearing d3's
        # own upper half, unlike the increase band's `move.w #$d0,d3` (007612)
        # or `move.w d1,d3` (007632), both plain .w moves that leave it alone.
        # Found 18 Sep on a fixture the original 'clean'-only admission never
        # exercised (a nonzero d3 upper half at entry, decrease/decrease): the
        # candidate wrote 0x4B460004 where the original left 0x00000004.
        d3_high = 0 if follow['y_branch'] in ('decrease', 'decrease-clamped') else high('d3')
        exit_registers['d3'] = d3_high | follow['d3']
    if event_registers is not None:
        # The LAST raise to touch each register (kind 3 and kind 6 touch different subsets -- kind 6
        # only ever changes a1, the dispatch's own handler-address residue, since 0044C0 never writes
        # it itself and its movem restore leaves d0-d7 exactly as they were; kind 3 always refreshes
        # a1/a2/a3/a5/d0/d1/d5/d6 and a4 when a condition sets it) leaves it live all the way to the
        # ceded upload -- nothing after the tile scan (the follow-point step, the re-index) touches
        # any of them again, and the clean arm never sets any of them at all (the caller's own entry
        # values ride through untouched, the existing 'clean'-arm tests already prove it).  a1/a2/a3/a5
        # (and a4, when present) are already full 32-bit addresses; d5/d6 are only ever touched by .w
        # moves anywhere in this whole region, so the caller's own entry upper half survives exactly
        # like d0-d3 above -- each is only set here when SOME raise in this activation actually did.
        exit_registers.update({name: value for name, value in event_registers.items()
                               if name in ('a1', 'a2', 'a3', 'a4', 'a5')})
        if 'd5' in event_registers:
            exit_registers['d5'] = high('d5') | (event_registers['d5'] & 0xFFFF)
        if 'd6' in event_registers:
            exit_registers['d6'] = high('d6') | (event_registers['d6'] & 0xFFFF)
    prefix = AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                        registers=exit_registers, last_pc=PLAYER_TAIL_LAST_PC)

    def player_tail_suffix(machine, live_registers):
        # Gated at the ceded upload's own rts (0013CE) rather than after it: the native adapter
        # refuses a zero-cost atomic, and there is exactly one instruction of this candidate's own
        # left to admit -- the rts itself, which pops the return address that was ALREADY on the
        # stack when this activation began (0048B4's own shape, one level further removed).  0013CE
        # sets no flag of its own; the ceded block's own residue SR is already live and correct.
        return AtomicPlan(cycles=16, instructions=1, writes=(),
                          registers={'a7': (live_registers['a7'] + 4) & 0xFFFFFFFF,
                                     'pc': _return(machine, live_registers['a7'] & 0xFFFFFF)},
                          last_pc=PLAYER_TAIL_UPLOAD_RTS)

    return Seam(prefix=prefix, resume_pc=PLAYER_TAIL_UPLOAD_RTS, stack_basis=sp32,
               guards=((sp, 4),), suffix=player_tail_suffix)


# --- 008222/00837E: the movement-cluster contact search (game/pickups.py: contact_search) -------
#
# No save/restore frame at all (hazard_tick's own shape): only d0/d3/d4/d5/d6/a2/a3 are live
# scratch, and a2 only changes once some sub-pass reaches its own item-record lookup.  Every
# instruction's own cost is constant regardless of the data it operates on (confirmed across every
# retained fixture, artifacts/gods/evidence/census-008222-entry*), so the routine is costed one
# instruction-block at a time; the docstring on ``game.pickups.contact_search`` and its own helpers
# name the shape these blocks follow.
CONTACT_SEARCH_ENTRY, CONTACT_SEARCH_LAST_PC = 0x008222, 0x00837C

_CS_BUSY = (12 + 10 + 4 + 16, 4)                     # tst f1a2 (taken); moveq #1,d0; rts
_CS_HEAD = (12 + 12 + 16 + 16 + 8 + 24 + 4 + 4 + 4, 9)     # tst f1a2 (not taken) .. moveq #0,d0
_CS_COUNT_SKIP = (12 + 10, 2)                        # tst.w -2(a3); bmi.b taken
_CS_COUNT_CONTINUE = (12 + 8, 2)                     # tst.w -2(a3); bmi.b not taken
_CS_SP1_LOOKUP = (12 + 14 + 4 + 4 + 4 + 4 + 8 + 14 + 4, 9)   # move.w -2(a3),d4 .. move.w d4,d6
_CS_SP23_SETUP = (8 + 24 + 4, 3)                     # lea list,a3; clr.l slot; moveq #0,d0
_CS_SP23_LOOKUP = (12 + 4 + 4 + 12 + 18 + 12 + 4, 7)         # move.w -2(a3),d5 .. move.w d4,d6
_CS_SP23_BMI_SKIP = (10, 1)
_CS_SP23_BMI_CONTINUE = (8, 1)
_CS_SP23_INITIAL_INDEX = (4, 1)                      # moveq #imm,d5
_CS_BSR = (18, 1)
_CS_PROBE_OCC = {0: (8 + 10 + 4 + 16, 4), 8: (8 + 8 + 12 + 10 + 4 + 16, 6),
                 0x10: (8 + 8 + 12 + 8 + 12 + 8 + 4 + 16, 8)}
_CS_PROBE_FREE = (8 + 8 + 12 + 8 + 12 + 10 + 16, 7)
_CS_CALLER_BEQ_MISS = (8, 1)
_CS_CALLER_BEQ_FOUND = (10, 1)
_CS_BUDGET_DEC_CONTINUE = (4 + 8, 2)                 # subq.w #1,d4; beq.b not taken
_CS_BUDGET_DEC_ABORT = (4 + 10, 2)                   # subq.w #1,d4; beq.b taken
_CS_RETRY_SETUP = (8 + 4 + 4, 3)                     # lea $18(a3),a3; moveq #0,d0; addq.w #3,d5
_CS_LAST_MISS_BRA = (10, 1)                          # bra.b, unconditional, after the third unrolled attempt
_CS_SP1_STORE_BASE = (16 + 12 + 4 + 8, 4)            # move.l a3,slot; move.w d5,index; clr.w d3; cmpi.w #1,d6
_CS_SP1_STORE_NOLATCH = (10, 1)                      # bne.b taken (ITEM_CONTACT_WORD != 1)
_CS_SP1_STORE_LATCH = (8 + 16, 2)                    # bne.b not taken; move.w #1,CONTACT_LATCH
_CS_SP23_GATE_HEAD = (8, 1)                          # cmpi.w #1,d6
_CS_SP23_STORE_IMMEDIATE = (10 + 16 + 12 + 4, 4)     # bne.b taken (!=1); move.l a3,slot; move.w d5,index; moveq #0,d3
_CS_SP23_LATCH_TEST = (8 + 12, 2)                    # bne.b not taken (==1); tst.w CONTACT_LATCH
_CS_SP23_LATCH_DISCARD = (10, 1)                     # bne.b taken: latch already set, no store
_CS_SP23_LATCH_STORE = (8 + 16 + 12 + 4, 4)          # bne.b not taken: move.l a3,slot; move.w d5,index; moveq #0,d3
_CS_TAIL = (4 + 16, 2)                               # move.w d3,d0; rts
# Each bsr.w/bsr.b into 00837E pushes its own return address at (entry_sp - 4); 00837E's own rts
# pops it straight back before the next one runs, so only the LAST call's own return address is
# live there when the whole routine returns -- real stack residue, not dead scratch (docs/gods/
# grinder-protocol.md's own "a routine that saves registers writes its whole frame" rule, one word).
_CS_RETURN_ADDRESSES = ((0x008264, 0x008276, 0x008288), (0x0082D2, 0x0082E4, 0x0082F6), (0x008340, 0x008350, 0x008360))


def _cs_attempts_cost(attempts):
    """The bsr+probe+caller-beq for every attempt a sub-pass made, plus the retry setup or the
    budget decrement between attempts (and the unconditional bra after the third, if reached)."""
    cycles = instructions = 0
    for index, step in enumerate(attempts):
        c, i = _add(_CS_BSR, _CS_PROBE_OCC[step['stop_offset']] if step['result'] == 'occupied' else _CS_PROBE_FREE)
        cycles += c
        instructions += i
        found = step['result'] == 'free'
        c, i = _CS_CALLER_BEQ_FOUND if found else _CS_CALLER_BEQ_MISS
        cycles += c
        instructions += i
        if found:
            break
        if index == 2:   # the third, unrolled attempt: a miss falls straight to the unconditional bra
            c, i = _CS_LAST_MISS_BRA
            cycles += c
            instructions += i
            break
        c, i = _CS_BUDGET_DEC_ABORT if step['budget_after'] == 0 else _CS_BUDGET_DEC_CONTINUE
        cycles += c
        instructions += i
        if step['budget_after'] == 0:
            break
        c, i = _CS_RETRY_SETUP
        cycles += c
        instructions += i
    return cycles, instructions


def _cs_subpass_cost(sub_index, result):
    """The full cost of one of 008222's own three sub-passes, from its own count test to whichever
    tail (skip / abandon / store / latch-gate) it reaches."""
    cycles = instructions = 0
    if sub_index != 0:
        c, i = _CS_SP23_SETUP
        cycles += c
        instructions += i
    if result['arm'] == 'skip':
        c, i = _CS_COUNT_SKIP
        cycles += c
        instructions += i
        return cycles, instructions
    c, i = _CS_COUNT_CONTINUE
    cycles += c
    instructions += i
    c, i = _CS_SP1_LOOKUP if sub_index == 0 else _CS_SP23_LOOKUP
    cycles += c
    instructions += i
    if sub_index != 0:
        c, i = _CS_SP23_BMI_SKIP if result['arm'] == 'skip-negative' else _CS_SP23_BMI_CONTINUE
        cycles += c
        instructions += i
        if result['arm'] == 'skip-negative':
            return cycles, instructions
        c, i = _CS_SP23_INITIAL_INDEX
        cycles += c
        instructions += i
    c, i = _cs_attempts_cost(result['attempts'])
    cycles += c
    instructions += i
    if result['arm'] == 'not-found':
        return cycles, instructions
    if sub_index == 0:
        c, i = _add(_CS_SP1_STORE_BASE, _CS_SP1_STORE_LATCH if result['sets_latch'] else _CS_SP1_STORE_NOLATCH)
    else:
        c, i = _CS_SP23_GATE_HEAD
        if result['contact_word'] & 0xFFFF != 1:
            ci, ii = _CS_SP23_STORE_IMMEDIATE
        elif result['arm'] == 'gated':
            ci, ii = _add(_CS_SP23_LATCH_TEST, _CS_SP23_LATCH_DISCARD)
        else:
            ci, ii = _add(_CS_SP23_LATCH_TEST, _CS_SP23_LATCH_STORE)
        c, i = c + ci, i + ii
    cycles += c
    instructions += i
    return cycles, instructions


def _contact_search_resolve(machine, read, registers, entry_sp):
    """Everything 008222 (with 00837E) does once entered, relative to its OWN entry a7 (``entry_sp``)
    -- shared by the standalone gate (``entry_sp = registers['a7']``) and a composing caller's own
    BSR (``entry_sp = registers['a7'] - 4``, the BSR's own push already accounted for by the caller,
    the shape `_cc_resolve` proved for the contact-consume family).  Returns (cycles, instructions,
    order, exit_registers, result) where ``exit_registers`` carries every register this routine's
    own code touches except a7/pc (the caller's own concern) and ``result`` is
    ``game.pickups.contact_search``'s own return, for the caller's own further branching (state 1's
    own `0073DC tst.w d0` reads exactly ``result['d0']``).  Raises UnsupportedCandidate exactly as
    the standalone planner already did.
    """
    from .game import pickups
    sr = registers['sr']
    result = pickups.contact_search(read)
    if result['arm'] != 'busy':
        for sub_index, sub_result in enumerate(result['subpasses']):
            if sub_result['arm'] == 'skip-negative':
                raise UnsupportedCandidate(f'contact search sub-pass {sub_index} negative ITEM_CONTACT_WORD not witnessed by a recording')
            if sub_result['arm'] == 'gated':
                raise UnsupportedCandidate(f'contact search sub-pass {sub_index} latch-gated find not witnessed by a recording')
            if sub_index == 0 and sub_result['sets_latch']:
                raise UnsupportedCandidate('contact search sub-pass 0 ITEM_CONTACT_WORD == 1 (the latch set) not witnessed by a recording')
    order = {}
    for address, (value, size) in result['stores'].items():
        for a, b in _bytes(address, value, size):
            order[a] = b

    if result['arm'] == 'busy':
        cycles, instructions = _CS_BUSY
        # moveq #1,d0 sets N=0/Z=0/V=0/C=0 (a positive one-word value); tst/bne/rts touch no flag at
        # all, and MOVEQ itself never touches X, so X survives from entry unchanged.  MOVEQ is a FULL
        # 32-bit register write (sign-extends the 8-bit immediate) -- d0's own upper half is always 0
        # here, never the caller's own entry upper half (caught by `factcheck.py check
        # --perturb-upper-halves` on a state 5 fixture whose contact-search call hit this arm, 18
        # September; every witnessed real fixture's own upper half already happened to be 0, so no
        # retained fixture had ever exposed it).
        exit_sr = sr & ~0x0F
        exit_registers = {'d0': 1, 'sr': exit_sr}
        return cycles, instructions, order, exit_registers, result

    cycles, instructions = _CS_HEAD
    last_return = None
    for sub_index, sub_result in enumerate(result['subpasses']):
        c, i = _cs_subpass_cost(sub_index, sub_result)
        cycles += c
        instructions += i
        if sub_result['attempts']:
            last_return = _CS_RETURN_ADDRESSES[sub_index][len(sub_result['attempts']) - 1]
    c, i = _CS_TAIL
    cycles += c
    instructions += i
    if last_return is not None:
        sp = entry_sp & 0xFFFFFF
        for a, b in _bytes((sp - 4) & 0xFFFFFF, last_return, 4):
            order[a] = b

    # move.w d3,d0 is the last N/Z/V/C setter on every non-busy path: d3 (0 found / 1 not found)
    # gives N=0 always, Z from whether it is 0; V=C=0 (MOVE always clears them).  X is untouched by
    # MOVE: it survives from the last ADD/ADDQ/SUB/SUBQ/ASL any sub-pass executed (game.pickups
    # already names it, 'last_x'), or from entry if none did (every sub-pass 'skip').
    exit_sr = (sr & ~0x1F) | (0x04 if result['d0'] == 0 else 0)
    if result['last_x'] is not None:
        op, left, right = result['last_x']
        exit_sr = (exit_sr & ~0x10) | ((_add_sr if op == 'add' else _sub_sr)(sr, left, right, 2) & 0x10)

    # HEAD's own "moveq #0,d0" / "moveq #1,d3" / "moveq #1,d5" -- and, for d0, every RETRY_SETUP's
    # own "moveq #0,d0" between attempts -- are full 32-bit clears; nothing after them ever restores
    # a nonzero upper half, so d0/d3/d5 always exit with upper=0, never the caller's own entry value
    # (found on fixture p34, whose caller's own d0 upper half was 0xFFFF, exposing the earlier bug).
    # d4/d6 have no such MOVEQ of their own: their upper half genuinely survives from entry.
    exit_registers = {'d0': result['d0'], 'd3': result['d0'], 'sr': exit_sr}
    if result['a2_exit'] is not None:
        exit_registers['a2'] = result['a2_exit'] & 0xFFFFFFFF
    if result['d4_exit'] is not None:
        exit_registers['d4'] = (registers['d4'] & 0xFFFF0000) | result['d4_exit']
    if result['d5_exit'] is not None:
        exit_registers['d5'] = result['d5_exit']
    if result['d6_exit'] is not None:
        exit_registers['d6'] = (registers['d6'] & 0xFFFF0000) | result['d6_exit']
    # a3 ends the routine at sub-pass 3's own list base (FFFFF0B2, unconditionally leaded before its
    # own count test), advanced by 0x18 per retry ("lea $18(a3),a3") sub-pass 3's own attempts made.
    sp3_attempts = result['subpasses'][2]['attempts']
    exit_registers['a3'] = (pickups.GROUP_TABLES[2] + pickups.CONTACT_ENTRY_BASE_OFFSET
                            + 0x18 * max(0, len(sp3_attempts) - 1)) & 0xFFFFFFFF

    return cycles, instructions, order, exit_registers, result


def contact_search_plan(machine, registers):
    """008222 (with its helper 00837E): the movement-cluster contact search.

    Witnessed across all eight recordings (271 retained path classes, `--max-classes 400`): the
    guard busy; each sub-pass's own 'skip' (count negative), 'not-found' (every attempt occupied,
    or the retry budget ran out) and 'found'; and, on sub-pass 2 only, ITEM_CONTACT_WORD == 1 on a
    find (96 of the 271 fixtures) -- the latch-test code runs, but the latch is always still clear
    at that point (sub-pass 1's own item never has ITEM_CONTACT_WORD == 1, so it never sets the
    latch), so the store always goes through.  Declined, unwitnessed by any recording: a sub-pass
    2/3 whose own ITEM_CONTACT_WORD comes back negative ('skip-negative'), sub-pass 1 itself ever
    having ITEM_CONTACT_WORD == 1 (its own latch-set arm), and the latch actually being set when a
    sub-pass 2/3 find tests it (the 'gated' arm) -- the second half of the whole latch mechanism.
    """
    if registers['pc'] != CONTACT_SEARCH_ENTRY:
        raise UnsupportedCandidate('contact search planner needs the machine parked at 008222')
    read = _reader(machine)
    sp32 = registers['a7']
    cycles, instructions, order, exit_registers, result = _contact_search_resolve(machine, read, registers, sp32)
    exit_registers['a7'] = (sp32 + 4) & 0xFFFFFFFF
    exit_registers['pc'] = _return(machine, sp32 & 0xFFFFFF)
    last_pc = 0x008390 if result['arm'] == 'busy' else CONTACT_SEARCH_LAST_PC
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=last_pc)


# --- 007282: state 1 (game.player.state1_step / state1_cascade / state1_handoff) -----------------
#
# Costed one instruction-block at a time from the tracer, the way 008222 and the contact-consume
# family already are: `docs/gods/blockers/2026-09-17-008222.md`'s "18 September (continued)"
# addendum transcribes the whole decision tree and the traces each block below comes from (eleven
# `factcheck.py facts --path` traces plus targeted `branches --vary` sweeps, all on
# `census-007282/007282-entry-p0.state` and `-p245.state`).  The plan ends with `pc = 0x0075D6` on
# every arm but the contact-search-found hand-off, which ends at `pc = 0x0075DA` (skipping the
# tail's own first instruction, already done) -- the same "one gate hands off to a separately-armed
# gate" shape `movement_hit_state`'s own states 24/25 already use for the SAME tail
# (`recovery.Candidate` arms `0x0075D6` as its own gate, 'player-tail').  One arm declines by name:
# the box-overlap scan (`0072D8`, `FFFFEA1E == 1`, 7 of 3,181 occurrences on the main history --
# `game.movement.box_overlap_scan` is recovered but not yet composed here).
STATE1_ENTRY = 0x007282

_S1_BSR_GRID = (18, 1)                    # 007282 bsr.w $63fa
_S1_GATE_TEST = (16, 1)                   # 007286 cmpi.b #1,$180(a0)
_S1_GATE_BEQ = {True: (10, 1), False: (8, 1)}        # 00728C beq.b -- taken: arm A; not taken: the low-bits test
_S1_LOW_HEAD = (12 + 8 + 8, 3)            # 00728E move.w f18c,d0; 007292 andi #$1e; 007296 cmpi #8
_S1_LOW_BLT = {True: (10, 1), False: (8, 1)}         # 00729A blt.b -- taken: wall directly
_S1_WALL_TEST2 = (16, 1)                  # 00729C cmpi.b #1,$181(a0)
_S1_WALL_BEQ = {True: (10, 1), False: (8, 1)}        # 0072A2 beq.b -- taken: arm A; not taken: wall
_S1_WALL_TAIL = (16 + 4 + 16 + 16 + 16 + 10, 6)      # 0072A4..0072B8: state=$c, d7=0, f194/f1a0/f198=0
_S1_EA20_TEST = (12, 1)                   # 0072BC tst.w ea20
_S1_EA20_BPL = {True: (10, 1), False: (8, 1)}        # 0072C0 bpl.b -- taken: arm A2; not taken: negative
_S1_NEG_TAIL = (16 + 4 + 10, 3)           # 0072C2..0072CA: state=3, d7=2
_S1_EA1E_TEST = (16, 1)                   # 0072CE cmpi.w #1,ea1e
_S1_EA1E_BNE = {True: (10, 1), False: (12, 1)}       # 0072D4 bne.w -- taken: arm A3; not taken: box-overlap
_S1_BIT0_TEST = (16, 1)                   # 00734C btst.b #0,ea23
_S1_BIT0_BEQ = {True: (10, 1), False: (12, 1)}       # 007352 beq.w -- taken: arm A4; not taken: jump-start
_S1_JS_TEST = (12, 1)                     # 007356 tst.w ea20 (>= 0 already established; zero or positive)
_S1_JS_BEQ = {True: (10, 1), False: (8, 1)}          # 00735A beq.b -- taken: f196=0; not taken: f196=4
_S1_JS_ZERO_HEAD = (16 + 10, 2)           # 007380 clr.w f196; 007384 bra.b (taken)
_S1_JS_NONZERO_HEAD = _add((8, 1), (16, 1))          # 00735C bmi.b (not taken, ea20 already >= 0); 00735E move.w #4,f196
_S1_JS_TAIL = (16 + 20 + 4 + 16 + 16 + 10, 6)        # 007364..00737C: state=9, f19a=x, d7=0, f19c=0, fdf6=$30
_S1_BIT2_TEST = (16, 1)                   # 0073D0 btst.b #2,ea23
_S1_BIT2_BEQ = {True: (10, 1), False: (8, 1)}        # 0073D6 beq.b -- taken: cascade directly; not taken: bsr 8222
_S1_SEARCH_BSR = (18, 1)                  # 0073D8 bsr.w $8222
_S1_SEARCH_TST = (4, 1)                   # 0073DC tst.w d0
_S1_SEARCH_BNE = {True: (10, 1), False: (8, 1)}      # 0073DE bne.b -- taken (not found): cascade; not taken (found): hand-off
_S1_HANDOFF_BRA = (10, 1)                 # 0073E0 bra.w $749a

_S1_CASCADE_TEST = (12, 1)                # 0073E4 tst.w f182
_S1_CASCADE_BNE = {True: (10, 1), False: (12, 1)}    # 0073E8 bne.w -- taken: f182-set; not taken: continue
_S1_F182_TAIL = (16 + 16 + 4 + 8 + 10, 5)            # 007458..007466: f182=0, x+=4, d7=(d7+1)&7
_S1_EA20ONE_TEST = (16, 1)                # 0073EC cmpi.w #1,ea20
_S1_EA20ONE_BNE = {True: (10, 1), False: (12, 1)}    # 0073F2 bne.w -- taken: shared sub-body; not taken: grid tests
_S1_GRIDHEAD = (12 + 8 + 8, 3)            # 0073F6 move.w f18c,d0; 0073FA andi #$1f; 0073FE cmpi #8
_S1_GRID_BGE = {True: (10, 1), False: (8, 1)}        # 007402 bge.b -- taken: low5 >= 8 (skip grid tests)
_S1_GRID_TEST = (16, 1)                   # cmpi.b #1,offset(a0), each of the three positions
_S1_GRID_BEQ = {True: (10, 1), False: (12, 1)}       # beq.w -- taken: immediate exit; not taken: next test / advance
_S1_ADVANCE_HEAD = (16, 1)                # 007422 addq.w #4,f18c
_S1_D7_2_TEST = (8, 1)                    # 007426 cmpi.w #2,d7
_S1_D7_2_BNE = {True: (10, 1), False: (8, 1)}        # 00742A bne.b -- not taken (d7==2): write sound $48 first
_S1_SOUND_WRITE = (16, 1)                 # move.w #imm,fdf6.w ($48 at 00742C or $49 at 007438)
_S1_D7_6_TEST = (8, 1)                    # 007432 cmpi.w #6,d7
_S1_D7_6_BNE = {True: (10, 1), False: (8, 1)}        # 007436 bne.b -- not taken (d7==6): write sound $49
_S1_ADVANCE_MID = (16, 1)                 # 00743E clr.w f182
_S1_D7_7_TEST = (8, 1)                    # 007442 cmpi.w #7,d7
_S1_D7_7_BLE = {True: (10, 1), False: (8, 1)}        # 007446 ble.b -- taken (d7<=7); not taken: overflow reset
_S1_OVERFLOW_RESET = (4 + 16, 2)          # 007448 moveq #7,d7; 00744A subq.w #4,f18c (undoes the +4 above)
_S1_ADVANCE_TAIL = (4 + 8 + 10, 3)        # 00744E addq.w #1,d7; 007450 andi.w #7,d7; 007454 bra.w

_S1_SHARED_TEST = (12, 1)                 # 007208 tst.w ea1e
_S1_SHARED_BPL = {True: (10, 1), False: (12, 1)}     # 00720C bpl.w -- taken: d7 test; not taken: negative tail
_S1_SHARED_NEG_TAIL = (4 + 16 + 16 + 10, 4)          # 007210..00721C: d7=1, state=$1a, f24a=0
_S1_SHARED_D7_TEST = (4, 1)               # 007220 tst.w d7
_S1_SHARED_D7_BEQ = {True: (10, 1), False: (12, 1)}  # 007222 beq.w -- taken: unchanged; not taken: reset tail
_S1_SHARED_RESET_TAIL = (4 + 10, 2)       # 007226 moveq #$2d,d7; 007228 bra.w

_S1_HANDOFF_HEAD = (16 + 10, 2)           # 00749A move.w #5,f192; 0074A0 bra.b (taken)
_S1_HANDOFF_TAIL = (4 + 12 + 4 + 14 + 10, 5)         # 0074A8..0074B4: d7=0, f190=0, table read, bra.w


def _state1_grid_cost(result):
    """0073F6-007422: the low-bits gate (0073FE/007402) then, when `low5 < 8`, `result['checked']`
    row-stride grid tests in program order (`+1`/`+0x81`/`+0x101`) -- the LAST one only 'taken' (a
    match) on the `'grid-block'` arm, every earlier one and a `low5 >= 8` skip 'not taken'.  Uses
    `game.player.state1_cascade`'s own `low5`/`checked` rather than re-reading the grid bytes."""
    cycles, instructions = _S1_GRIDHEAD
    c, i = _S1_GRID_BGE[result['low5'] >= 8]
    cycles += c
    instructions += i
    blocked = result['arm'] == 'grid-block'
    for index in range(result['checked']):
        c, i = _S1_GRID_TEST
        cycles += c
        instructions += i
        matched = blocked and index == result['checked'] - 1
        c, i = _S1_GRID_BEQ[matched]
        cycles += c
        instructions += i
    return cycles, instructions


# The cascade's own 'f182-set', 'position-advance' (without 'overflow') and 'shared-unchanged' arms
# store D7 through an ADDQ/ANDI/TST -- word ops that leave the entry's own upper half untouched --
# while 'ea1e-negative', 'shared-reset' and 'position-advance' WITH 'overflow' go through a MOVEQ
# (a full 32-bit clear) first, so `result['d7']` there is already the caller's own complete register.
# `factcheck.py check --perturb-upper-halves` found the boundary merging neither case correctly (a
# blanket plain assignment truncated the first group's own upper half), 18 September; shared between
# state 0's and state 1's own cascades, whose arm names and shapes agree here.
_CASCADE_D7_MERGE_ARMS = frozenset({'f182-set', 'shared-unchanged'})


def _cascade_exit_d7(entry_d7_register, result):
    """The correct D7 for a cascade result's own 'd7' entry (or `None` if it has none at all)."""
    if 'd7' not in result:
        return None
    if result['arm'] in _CASCADE_D7_MERGE_ARMS or (result['arm'] == 'position-advance' and not result.get('overflow')):
        return (entry_d7_register & 0xFFFF0000) | (result['d7'] & 0xFFFF)
    return result['d7']


def _state1_cascade_cost(read, sr, d7, position_x, address):
    """0073E4-0075D6: the cascade's own cost and exit facts, shared by `state1_plan`'s own
    `EA23` bit-2-clear arm and its contact-search 'not found' continuation."""
    from .game import player
    result = player.state1_cascade(read, d7, position_x, address)
    cycles, instructions = _S1_CASCADE_TEST
    if result['arm'] == 'f182-set':
        c, i = _add(_S1_CASCADE_BNE[True], _S1_F182_TAIL)
        cycles += c
        instructions += i
        last_pc = 0x007466
        # 007462 andi.w #7,d7 is the last N/Z/V/C setter (X untouched by ANDI); X itself is whatever
        # 007460's own addq.w #1,d7 left (the entry d7 is at most 7 here, so the add never carries).
        add_x_sr = _add_sr(sr, d7, 1, 2)
        exit_sr = (_logic_sr(sr, result['d7'], 2) & ~0x10) | (add_x_sr & 0x10)
        return cycles, instructions, result, last_pc, exit_sr
    c, i = _S1_CASCADE_BNE[False]
    cycles += c
    instructions += i
    c, i = _S1_EA20ONE_TEST
    cycles += c
    instructions += i
    if result['arm'] not in ('grid-block', 'position-advance'):
        c, i = _S1_EA20ONE_BNE[True]
        cycles += c
        instructions += i
        c, i = _S1_SHARED_TEST
        cycles += c
        instructions += i
        if result['arm'] == 'ea1e-negative':
            c, i = _add(_S1_SHARED_BPL[False], _S1_SHARED_NEG_TAIL)
            cycles += c
            instructions += i
            last_pc = 0x00721C
            exit_sr = _logic_sr(sr, 0, 2)            # 007218 clr.w f24a is the last flag-setter (Z=1)
            return cycles, instructions, result, last_pc, exit_sr
        c, i = _S1_SHARED_BPL[True]
        cycles += c
        instructions += i
        c, i = _S1_SHARED_D7_TEST
        cycles += c
        instructions += i
        if result['arm'] == 'shared-unchanged':
            c, i = _S1_SHARED_D7_BEQ[True]
            cycles += c
            instructions += i
            last_pc = 0x007222
            exit_sr = _cmp_sr(sr, d7, 0, 2)        # 007220 tst.w d7 is the last (and only) flag-setter
            return cycles, instructions, result, last_pc, exit_sr
        c, i = _add(_S1_SHARED_D7_BEQ[False], _S1_SHARED_RESET_TAIL)
        cycles += c
        instructions += i
        last_pc = 0x007228
        exit_sr = _cmp_sr(sr, d7, 0, 2)            # moveq/bra set nothing; tst.w d7 (not-equal) stands
        return cycles, instructions, result, last_pc, exit_sr
    c, i = _S1_EA20ONE_BNE[False]
    cycles += c
    instructions += i
    grid_cycles, grid_instructions = _state1_grid_cost(result)
    if result['arm'] == 'grid-block':
        cycles += grid_cycles
        instructions += grid_instructions
        # The matching cmpi.b #1,offset(a0) is the last (and only) flag-setter on this arm: the byte
        # equals 1, so the compare's own result is 0 (Z=1, N=V=C=0); X is untouched by CMP.  D0 holds
        # POSITION_X's own low 5 bits (0073F6/0073FA), read regardless of which position matched.
        exit_sr = _cmp_sr(sr, 1, 1, 1)
        return cycles, instructions, result, result['last_pc'], exit_sr
    cycles += grid_cycles
    instructions += grid_instructions
    c, i = _S1_ADVANCE_HEAD
    cycles += c
    instructions += i
    c, i = _S1_D7_2_TEST
    cycles += c
    instructions += i
    c, i = _S1_D7_2_BNE[d7 != 2]
    cycles += c
    instructions += i
    if d7 == 2:
        c, i = _S1_SOUND_WRITE
        cycles += c
        instructions += i
    c, i = _S1_D7_6_TEST
    cycles += c
    instructions += i
    c, i = _S1_D7_6_BNE[d7 != 6]
    cycles += c
    instructions += i
    if d7 == 6:
        c, i = _S1_SOUND_WRITE
        cycles += c
        instructions += i
    c, i = _add(_S1_ADVANCE_MID, _S1_D7_7_TEST)
    cycles += c
    instructions += i
    if result.get('overflow'):
        c, i = _add(_S1_D7_7_BLE[False], _S1_OVERFLOW_RESET, _S1_ADVANCE_TAIL)
    else:
        c, i = _add(_S1_D7_7_BLE[True], _S1_ADVANCE_TAIL)
    cycles += c
    instructions += i
    last_pc = 0x007454
    # 007450 andi.w #7,d7 is the last flag-setter (N/Z from the masked result, V=C=0, X untouched);
    # X itself is whatever 00744E's own addq.w #1,d7 left (the entry d7 is at most 7 here, so the
    # add never carries: X=0 always on this arm).
    add_x_sr = _add_sr(sr, d7, 1, 2)
    exit_sr = (_logic_sr(sr, result['d7'], 2) & ~0x10) | (add_x_sr & 0x10)
    return cycles, instructions, result, last_pc, exit_sr


def _s1_gate_cost(head):
    """007286-0072A2: the cost to reach either 'wall' (0072A4) or arm A (0072BC), covering all three
    routes `state1_step` can take there -- `$180(a0) == 1` directly, or `$180(a0) != 1` and then
    either the low-bits test alone (`low < 8`, always wall) or both it and `$181(a0)`'s own compare
    (`low >= 8`: wall when `$181(a0) != 1`, arm A when it is 1)."""
    if head['gate_direct']:
        return _S1_GATE_BEQ[True]
    cycles, instructions = _add(_S1_GATE_BEQ[False], _S1_LOW_HEAD)
    if head['low_lt_8']:
        c, i = _S1_LOW_BLT[True]
        return cycles + c, instructions + i
    c, i = _add(_S1_LOW_BLT[False], _S1_WALL_TEST2, _S1_WALL_BEQ[head['arm'] != 'wall'])
    return cycles + c, instructions + i


def state1_plan(machine, registers):
    """007282 (state 1): the player state machine's own dispatch table entry 1, composed over the
    already-recovered grid cell (`0063FA`), contact search (`008222`) and the shared tail (`0075D6`,
    a separately-armed gate this plan hands off to by ending at `pc = 0x0075D6`).  See the module
    note above for the shape and where every block's cost comes from."""
    from .game import player
    if registers['pc'] != STATE1_ENTRY:
        raise UnsupportedCandidate('state 1 planner needs the machine parked at 007282')
    sr = registers['sr']
    read = _reader(machine)
    d7 = registers['d7'] & 0xFFFF
    head = player.state1_step(read, d7)
    # 006408 asl.w #3,d1 (inside the composed grid_cell call) is the last flag-setter before 007286's
    # own cmpi.b -- X survives from here through every later instruction that does not itself touch
    # it, exactly as grid_cell_plan's own exit_sr threads it for a standalone caller.
    sr = _asl_sr(sr, head['row_source'], 3, 2)
    order = {}
    for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x007286, 4):
        order[a] = b
    cycles, instructions = _add(_S1_BSR_GRID, GRID_CELL_COST, _S1_GATE_TEST)
    # 00728E move.w f18c,d0; 007292 andi.w #$1e,d0 -- when $180(a0) != 1, the low-bits test overwrites
    # grid_cell's own d0 (the column) with POSITION_X & 0x1E permanently; the ea20==1 grid-test block
    # further down (0073F6, mask 0x1F) overwrites it again on the arms that reach it -- handled where
    # `_state1_cascade_cost` returns its own 'd0'.
    d0 = head['d0'] if head['gate_direct'] else (head['position_x'] & 0x1E)
    exit_registers = {'d0': (registers['d0'] & 0xFFFF0000) | d0,
                      'd1': (registers['d1'] & 0xFFFF0000) | head['d1'],
                      'a0': head['address'] & 0xFFFFFFFF}

    if head['arm'] == 'wall':
        c, i = _add(_s1_gate_cost(head), _S1_WALL_TAIL)
        cycles += c
        instructions += i
        for a, b in head['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = head['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 0072B4 clr.w f198 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0072B8)

    if head['arm'] == 'negative':
        c, i = _add(_s1_gate_cost(head), _S1_EA20_TEST, _S1_EA20_BPL[False], _S1_NEG_TAIL)
        cycles += c
        instructions += i
        for a, b in head['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = head['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 3, 2)   # 0072C2 move.w #3,f192 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0072CA)

    if head['arm'] == 'box-overlap':
        raise UnsupportedCandidate('state 1: the box-overlap scan (0072D8, FFFFEA1E == 1) is not composed here yet')

    if head['arm'] == 'jump-start':
        c, i = _add(_s1_gate_cost(head), _S1_EA20_TEST, _S1_EA20_BPL[True], _S1_EA1E_TEST, _S1_EA1E_BNE[True],
                    _S1_BIT0_TEST, _S1_BIT0_BEQ[False], _S1_JS_TEST)
        if head['f196'] == 0:
            c2, i2 = _add(_S1_JS_BEQ[True], _S1_JS_ZERO_HEAD)
        else:
            c2, i2 = _add(_S1_JS_BEQ[False], _S1_JS_NONZERO_HEAD)
        c3, i3 = _S1_JS_TAIL
        cycles += c + c2 + c3
        instructions += i + i2 + i3
        for a, b in head['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = head['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x30, 2)   # 007376 move.w #$30,fdf6 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00737C)

    # head['arm'] == 'gate': the shared cascade, directly (EA23 bit 2 clear) or after a contact-search call.
    c, i = _add(_s1_gate_cost(head), _S1_EA20_TEST, _S1_EA20_BPL[True], _S1_EA1E_TEST, _S1_EA1E_BNE[True],
                _S1_BIT0_TEST, _S1_BIT0_BEQ[True], _S1_BIT2_TEST)
    cycles += c
    instructions += i
    position_x = head['position_x']
    address = head['address']

    if not head['needs_search']:
        c, i = _S1_BIT2_BEQ[True]
        cycles += c
        instructions += i
        cc, ci, result, last_pc, exit_sr = _state1_cascade_cost(read, sr, d7, position_x, address)
        cycles += cc
        instructions += ci
        if 'stores' in result:
            for a, b in result['stores'].items():
                for aa, bb in _bytes(a, b[0], b[1]):
                    order[aa] = bb
        if 'd7' in result:
            exit_registers['d7'] = _cascade_exit_d7(registers['d7'], result)
        if 'd0' in result:
            exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | result['d0']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = exit_sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    # EA23 bit 2 set: call the already-recovered contact search (008222) internally, exactly the
    # shape `_movement_hit_plan` already proved for a nested BSR into recovered code.
    c, i = _S1_BIT2_BEQ[False]
    cycles += c
    instructions += i
    sp32 = registers['a7']
    c, i = _S1_SEARCH_BSR
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x0073DC, 4):
        order[a] = b
    cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
        machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4}, sp32 - 4)
    cycles += cs_cycles
    instructions += cs_instructions
    order.update(cs_order)
    exit_registers.update(cs_registers)
    exit_registers['d0'] = cs_registers['d0']
    c, i = _S1_SEARCH_TST
    cycles += c
    instructions += i
    found = cs_result['d0'] == 0
    c, i = _S1_SEARCH_BNE[not found]
    cycles += c
    instructions += i

    if found:
        c, i = _S1_HANDOFF_BRA
        cycles += c
        instructions += i
        handoff = player.state1_handoff(read)
        c, i = _add(_S1_HANDOFF_HEAD, _S1_HANDOFF_TAIL)
        cycles += c
        instructions += i
        for a, b in handoff['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = handoff['d7']
        exit_registers['pc'] = 0x0075DA
        # 0074AA move.w d7,f190 is a plain MOVE (N/Z from the value, V=C=0), the last flag-setter; X is
        # untouched by MOVE and by the PC-relative-indexed read after it, so it survives from whatever
        # contact_search's own found-arm exit left (a MOVE too -- 00837E's own "move.l a3,slot").
        exit_registers['sr'] = _logic_sr(cs_registers['sr'], handoff['d7'], 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0074B4)

    cc, ci, result, last_pc, exit_sr = _state1_cascade_cost(read, cs_registers['sr'], d7, position_x, address)
    cycles += cc
    instructions += ci
    if 'stores' in result:
        for a, b in result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
    if 'd7' in result:
        exit_registers['d7'] = _cascade_exit_d7(registers['d7'], result)
    if 'd0' in result:
        # The ea20==1 grid tests re-read POSITION_X into d0 (0073F6/0073FA), overwriting
        # contact_search's own d0=1 (not found) residue; every other cascade arm leaves it.  The
        # upper half comes from contact_search's OWN exit (already cleared there), not state 1's
        # entry: `andi.w #$1f,d0` at 0073FA is a .w op, preserving whatever d0's upper half already
        # was at that point in the SAME activation.
        exit_registers['d0'] = (cs_registers['d0'] & 0xFFFF0000) | result['d0']
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = exit_sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=last_pc)


# --- 00746A: state 5 (game.player.state5_step / state5_handoff / state5_fallback_stores) -----------
#
# "One region, two gates, one planner" (`docs/gods/blockers/2026-09-17-005700.md`'s Decision):
# state 5's own 'fallback' arm ends at state 1's own gate (STATE1_ENTRY, a SEPARATELY ARMED candidate
# this plan hands off to, not inlined here), so this planner never re-derives state 1's own body.
# Costed one instruction-block at a time from a fresh disassembly (00746A-0074C2) cross-checked
# against `factcheck.py facts --path` on four real fixtures over `census-00746A-fb408bc75597`
# (entry d7 = 0, 2, 4-with-a-search-find, 4-with-a-search-miss), 18 September.
STATE5_ENTRY = 0x00746A
STATE5_CONSUME_RETURN_PC = 0x007478     # jsr 12da0.l's own return site (cmpi.w #5,d7)
STATE5_SEARCH_RETURN_PC = 0x00748A      # bsr.w 8222's own return site (tst.w d0)

_S5_ADDQ = (4, 1)                           # 00746A addq.w #1,d7
_S5_CMPI3 = (8, 1)                          # 00746C cmpi.w #3,d7
_S5_BNE3 = {True: (10, 1), False: (8, 1)}   # 007470 bne.b -- taken (!=3): skip the call; not taken (==3): the jsr
_S5_JSR_CONSUME = (20, 1)                   # 007472 jsr $12da0.l
_S5_CMPI5 = (8, 1)                          # 007478 cmpi.w #5,d7
_S5_BLT5 = {True: (10, 1), False: (8, 1)}   # 00747C blt.b -- taken (<5): the table hand-off; not taken: the search gate
_S5_BTST2 = (16, 1)                         # 00747E btst.b #2,ea23
_S5_BEQ_BIT2 = {True: (10, 1), False: (8, 1)}   # 007484 beq.b -- taken (bit2 clear): fallback directly; not taken: bsr 8222
_S5_BSR_SEARCH = (18, 1)                    # 007486 bsr.w $8222
_S5_TST_D0 = (4, 1)                         # 00748A tst.w d0
_S5_BEQ_FOUND = {True: (10, 1), False: (8, 1)}  # 00748C beq.b -- taken (found): the handoff's own moveq path; not taken: fallback
_S5_FALLBACK_TAIL = (4 + 16 + 10, 3)        # 00748E moveq #2,d7; 007490 move.w #1,f192.w; 007496 bra.w $7282
_S5_HANDOFF_MOVEQ = (4, 1)                  # 0074A8 moveq #0,d7 (the search-found continuation only)
_S5_HANDOFF_STORE = (12, 1)                 # 0074AA move.w d7,f190.w
_S5_HANDOFF_DOUBLE = (4, 1)                 # 0074AE add.w d7,d7
_S5_HANDOFF_TABLE_READ = (14, 1)            # 0074B0 move.w 74b8(pc,d7.w),d7
_S5_HANDOFF_BRA = (10, 1)                   # 0074B4 bra.w $75da


def _state56_handoff_stores_and_cost(read, order, index, with_moveq):
    """The `0074A8`/`0074AA`-`0074B4` table hand-off: SHARED ROM code state 5's own entry (`00746A`)
    and state 6's own entry (`0074C2`) both reach (confirmed byte-identical by a fresh disassembly of
    each), so `player.state5_handoff` -- despite its name, nothing in it is state-5-specific -- is
    reused verbatim rather than duplicated as `state6_handoff`."""
    from .game import player
    handoff = player.state5_handoff(read, index)
    for a, b in _bytes(player.STATE_COUNTER, handoff['stores'][player.STATE_COUNTER][0], 2):
        order[a] = b
    parts = (_S5_HANDOFF_MOVEQ,) if with_moveq else ()
    cycles, instructions = _add(*parts, _S5_HANDOFF_STORE, _S5_HANDOFF_DOUBLE, _S5_HANDOFF_TABLE_READ, _S5_HANDOFF_BRA)
    return cycles, instructions, handoff['d7']


def state5_plan(machine, registers):
    """00746A (state 5): the player state machine's own dispatch table entry 5, ALSO reached by a
    `bra.w` fallthrough from inside state 1's own body (`0073E0`).  Composed over the already-
    recovered contact-consume primary (`012DA0`) and contact search (`008222`); its own 'fallback' arm
    ends at state 1's own gate (`pc = 0x007282`) instead of inlining state 1's body -- see the module
    note above."""
    from .game import player
    if registers['pc'] != STATE5_ENTRY:
        raise UnsupportedCandidate('state 5 planner needs the machine parked at 00746A')
    read = _reader(machine)
    d7 = registers['d7'] & 0xFFFF
    head = player.state5_step(read, d7)
    order = {}
    sp32 = registers['a7']
    # 00746A addq.w #1,d7 is the first X-setter in this plan; nothing before it.
    sr = _add_sr(registers['sr'], d7, 1, 2)
    cycles, instructions = _add(_S5_ADDQ, _S5_CMPI3)
    exit_registers = {}

    if head['calls_consumer']:
        c, i = _S5_BNE3[False]
        cycles += c
        instructions += i
        c, i = _S5_JSR_CONSUME
        cycles += c
        instructions += i
        for a, b in _bytes((sp32 - 4) & 0xFFFFFF, STATE5_CONSUME_RETURN_PC, 4):
            order[a] = b
        cc_cycles, cc_instructions, cc_order, cc_registers, _ = _cc_resolve(machine, read, registers, 0, sp32 - 4)
        cycles += cc_cycles
        instructions += cc_instructions
        order.update(cc_order)
        exit_registers.update(cc_registers)
    else:
        c, i = _S5_BNE3[True]
        cycles += c
        instructions += i
    c, i = _S5_CMPI5
    cycles += c
    instructions += i

    if head['arm'] == 'handoff':
        c, i = _S5_BLT5[True]
        cycles += c
        instructions += i
        hc, hi, new_d7 = _state56_handoff_stores_and_cost(read, order, head['counter'], with_moveq=False)
        cycles += hc
        instructions += hi
        exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | new_d7
        exit_registers['pc'] = 0x0075DA
        add_sr = _add_sr(sr, head['counter'], head['counter'], 2)   # 0074AE add.w d7,d7
        exit_registers['sr'] = _logic_sr(add_sr, new_d7, 2)         # 0074B0 move.w ...,d7 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0074B4)

    # head['arm'] in ('fallback', 'gate'): counter >= 5.
    c, i = _S5_BLT5[False]
    cycles += c
    instructions += i
    c, i = _S5_BTST2
    cycles += c
    instructions += i

    if head['arm'] == 'fallback':
        c, i = _S5_BEQ_BIT2[True]
        cycles += c
        instructions += i
        c, i = _S5_FALLBACK_TAIL
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, player.STATE5_FALLBACK_STATE_INDEX, 2):
            order[a] = b
        exit_registers['d7'] = player.STATE5_FALLBACK_COUNTER   # moveq #2,d7: a full 32-bit clear, not a .w merge
        exit_registers['pc'] = player.STATE5_FALLBACK_PC
        exit_registers['sr'] = _logic_sr(sr, player.STATE5_FALLBACK_STATE_INDEX, 2)   # 007490's own move.w is last
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x007496)

    # head['arm'] == 'gate': call the already-recovered contact search internally, exactly the shape
    # state1_plan already proved for a nested BSR into recovered code.
    c, i = _S5_BEQ_BIT2[False]
    cycles += c
    instructions += i
    c, i = _S5_BSR_SEARCH
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, STATE5_SEARCH_RETURN_PC, 4):
        order[a] = b
    cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
        machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4, 'sr': sr}, sp32 - 4)
    cycles += cs_cycles
    instructions += cs_instructions
    order.update(cs_order)
    exit_registers.update(cs_registers)
    c, i = _S5_TST_D0
    cycles += c
    instructions += i
    found = cs_result['d0'] == 0
    c, i = _S5_BEQ_FOUND[found]
    cycles += c
    instructions += i

    if found:
        hc, hi, new_d7 = _state56_handoff_stores_and_cost(read, order, 0, with_moveq=True)
        cycles += hc
        instructions += hi
        # 0074A8's own moveq #0,d7 is a FULL 32-bit clear -- the entry's own upper half does NOT
        # survive here (unlike the plain 'handoff' arm below, which never executes that moveq); caught
        # by `factcheck.py check --perturb-upper-halves`, 18 September.
        exit_registers['d7'] = new_d7
        exit_registers['pc'] = 0x0075DA
        add_sr = _add_sr(cs_registers['sr'], 0, 0, 2)   # 0074AE add.w d7,d7 with d7 forced to 0 by 0074A8's moveq
        exit_registers['sr'] = _logic_sr(add_sr, new_d7, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0074B4)

    c, i = _S5_FALLBACK_TAIL
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, player.STATE5_FALLBACK_STATE_INDEX, 2):
        order[a] = b
    exit_registers['d7'] = player.STATE5_FALLBACK_COUNTER   # moveq #2,d7: a full 32-bit clear
    exit_registers['pc'] = player.STATE5_FALLBACK_PC
    exit_registers['sr'] = _logic_sr(cs_registers['sr'], player.STATE5_FALLBACK_STATE_INDEX, 2)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x007496)


# --- 0074C2: state 6 -- a byte-for-byte MIRROR of state 5's own shape (game.player.state6_step),
# confirmed by a fresh disassembly AND by `factcheck.py facts --path` on all five of state 6's own
# arms over `census-0074C2-fb408bc75597` (not assumed by symmetry: every one of the eleven costed
# instruction blocks below matched state 5's own `_S5_*` constants exactly, addq/cmpi/bne/jsr/cmpi/
# blt/btst/beq/bsr/tst/beq all identical shapes and cycle counts regardless of the different absolute
# targets `012E5A`/`0x006FFE` bake into two of them -- so this planner reuses `_S5_*` directly rather
# than a renamed duplicate).  Only the consumer routine (`012E5A`, secondary) and the fallback's own
# STATE_INDEX/target gate (`0`/`STATE6_FALLBACK_PC`) differ; the handoff and contact-search-gate arms
# are the exact SAME shared code state 5's own entry reaches (`_state56_handoff_stores_and_cost`).
STATE6_ENTRY = 0x0074C2
STATE6_CONSUME_RETURN_PC = 0x0074D0     # jsr 12e5a.l's own return site (cmpi.w #5,d7)
STATE6_SEARCH_RETURN_PC = 0x0074E2      # bsr.w 8222's own return site (tst.w d0)
STATE6_FALLBACK_BRA_PC = 0x0074EC       # 0074E6-0074EC: moveq #2,d7; clr.w f192.w; bra.w $6ffe


def state6_plan(machine, registers):
    """0074C2 (state 6): the player state machine's own dispatch table entry 6, ALSO reached by a
    `bra.w` fallthrough from inside state 0's own body (`state0_handoff`, `0074A2`).  See the module
    note above -- structurally state 5's own planner with the consumer routine and the fallback's own
    target swapped."""
    from .game import player
    if registers['pc'] != STATE6_ENTRY:
        raise UnsupportedCandidate('state 6 planner needs the machine parked at 0074C2')
    read = _reader(machine)
    d7 = registers['d7'] & 0xFFFF
    head = player.state6_step(read, d7)
    order = {}
    sp32 = registers['a7']
    sr = _add_sr(registers['sr'], d7, 1, 2)   # 0074C2 addq.w #1,d7 is the first X-setter
    cycles, instructions = _add(_S5_ADDQ, _S5_CMPI3)
    exit_registers = {}

    if head['calls_consumer']:
        c, i = _S5_BNE3[False]
        cycles += c
        instructions += i
        c, i = _S5_JSR_CONSUME
        cycles += c
        instructions += i
        for a, b in _bytes((sp32 - 4) & 0xFFFFFF, STATE6_CONSUME_RETURN_PC, 4):
            order[a] = b
        cc_cycles, cc_instructions, cc_order, cc_registers, _ = _cc_resolve(machine, read, registers, 1, sp32 - 4)
        cycles += cc_cycles
        instructions += cc_instructions
        order.update(cc_order)
        exit_registers.update(cc_registers)
    else:
        c, i = _S5_BNE3[True]
        cycles += c
        instructions += i
    c, i = _S5_CMPI5
    cycles += c
    instructions += i

    if head['arm'] == 'handoff':
        c, i = _S5_BLT5[True]
        cycles += c
        instructions += i
        hc, hi, new_d7 = _state56_handoff_stores_and_cost(read, order, head['counter'], with_moveq=False)
        cycles += hc
        instructions += hi
        exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | new_d7
        exit_registers['pc'] = 0x0075DA
        add_sr = _add_sr(sr, head['counter'], head['counter'], 2)
        exit_registers['sr'] = _logic_sr(add_sr, new_d7, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0074B4)

    c, i = _S5_BLT5[False]
    cycles += c
    instructions += i
    c, i = _S5_BTST2
    cycles += c
    instructions += i

    if head['arm'] == 'fallback':
        c, i = _S5_BEQ_BIT2[True]
        cycles += c
        instructions += i
        c, i = _S5_FALLBACK_TAIL
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, player.STATE6_FALLBACK_STATE_INDEX, 2):
            order[a] = b
        exit_registers['d7'] = player.STATE6_FALLBACK_COUNTER
        exit_registers['pc'] = player.STATE6_FALLBACK_PC
        exit_registers['sr'] = _logic_sr(sr, player.STATE6_FALLBACK_STATE_INDEX, 2)   # clr.w is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=STATE6_FALLBACK_BRA_PC)

    c, i = _S5_BEQ_BIT2[False]
    cycles += c
    instructions += i
    c, i = _S5_BSR_SEARCH
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, STATE6_SEARCH_RETURN_PC, 4):
        order[a] = b
    cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
        machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4, 'sr': sr}, sp32 - 4)
    cycles += cs_cycles
    instructions += cs_instructions
    order.update(cs_order)
    exit_registers.update(cs_registers)
    c, i = _S5_TST_D0
    cycles += c
    instructions += i
    found = cs_result['d0'] == 0
    c, i = _S5_BEQ_FOUND[found]
    cycles += c
    instructions += i

    if found:
        hc, hi, new_d7 = _state56_handoff_stores_and_cost(read, order, 0, with_moveq=True)
        cycles += hc
        instructions += hi
        # 0074A8's own moveq #0,d7 is a FULL 32-bit clear -- see state 5's own planner above.
        exit_registers['d7'] = new_d7
        exit_registers['pc'] = 0x0075DA
        add_sr = _add_sr(cs_registers['sr'], 0, 0, 2)
        exit_registers['sr'] = _logic_sr(add_sr, new_d7, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0074B4)

    c, i = _S5_FALLBACK_TAIL
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, player.STATE6_FALLBACK_STATE_INDEX, 2):
        order[a] = b
    exit_registers['d7'] = player.STATE6_FALLBACK_COUNTER
    exit_registers['pc'] = player.STATE6_FALLBACK_PC
    exit_registers['sr'] = _logic_sr(cs_registers['sr'], player.STATE6_FALLBACK_STATE_INDEX, 2)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=STATE6_FALLBACK_BRA_PC)


# --- 006FFE: state 0 (game.player.state0_step / state0_cascade / state0_shared_sub) ---------------
#
# Costed one instruction-block at a time from the tracer the same way state 1 is; every block below
# comes from a fresh set of `factcheck.py facts --path` traces and `branches --vary` sweeps on
# `census-006FFE/006FFE-entry-p0.state` (plus real fixtures for the arms a single parked state
# cannot reach: p1/p2/p100/p183/p276).  `game.player`'s own module note transcribes every real
# difference from state 1's shape; this file does not assume symmetry either -- every block here has
# its own tracer evidence, not a renamed copy of state 1's constants.
STATE0_ENTRY = 0x006FFE

_S0_BSR_GRID = (18, 1)                       # 006FFE bsr.w $63fa
_S0_GATE_TEST = (16, 1)                      # 007002 cmpi.b #1,$180(a0)
_S0_GATE_BEQ = {True: (10, 1), False: (8, 1)}           # 007008 beq.b -- taken: arm A; not taken: low-bits test
_S0_LOW_HEAD = (12 + 8 + 8, 3)               # 00700A move.w f18c,d0; 00700E andi #$1e; 007012 cmpi #8
_S0_LOW_BLT = {True: (10, 1), False: (8, 1)}            # 007016 blt.b -- taken: wall directly
_S0_WALL_TEST2 = (16, 1)                     # 007018 cmpi.b #1,$181(a0)
_S0_WALL_BEQ = {True: (10, 1), False: (8, 1)}           # 00701E beq.b -- taken: arm A; not taken: wall
_S0_WALL_TAIL = (16 + 16 + 16 + 16 + 4 + 10, 6)         # 007020..007034: state=$b, f194/f1a0/f198=0, d7=0
_S0_ARMA_TEST = (16, 1)                      # 007038 cmpi.w #1,ea20 -- the LITERAL compare, not a sign test
_S0_ARMA_BNE = {True: (10, 1), False: (8, 1)}           # 00703E bne.b -- taken(!=1): arm A2; not taken(==1): transition-2
_S0_TRANS2_TAIL = (16 + 4 + 10, 3)           # 007040..007048: state=2, d7=0
_S0_EA1E_TEST = (16, 1)                      # 00704C cmpi.w #1,ea1e
_S0_EA1E_BNE = {True: (10, 1), False: (12, 1)}          # 007052 bne.w -- taken: arm A3; not taken: box-overlap
_S0_BIT0_TEST = (16, 1)                      # 0070D0 btst.b #0,ea23
_S0_BIT0_BEQ = {True: (10, 1), False: (12, 1)}          # 0070D6 beq.w -- taken: arm A4; not taken: arm A3b
_S0_A3B_TEST = (12, 1)                       # 0070DA tst.w ea20
_S0_A3B_BEQ = {True: (10, 1), False: (8, 1)}            # 0070DE beq.b -- taken(==0): the zero route
_S0_A3B_BPL = {True: (10, 1), False: (8, 1)}            # 0070E0 bpl.b -- taken(>0): positive tree; not taken(<0): state 8
_S0_A3B_ZERO_HEAD = (16 + 10, 2)             # 007104 clr.w f196; 007108 bra.b (taken)
_S0_A3B_NEG_HEAD = (16, 1)                   # 0070E2 move.w #$fffc,f196
_S0_STATE8_TAIL = (16 + 20 + 4 + 16 + 16 + 10, 6)       # 0070E8..007100: state=8, f19a=x, d7=0, f19c=0, fdf6=$30
_S0_POS_HEAD = (12 + 8 + 8, 3)               # 00710A move.w f18c,d0; 00710E andi #$1f; 007112 cmpi #$14
_S0_POS_BGT = {True: (10, 1), False: (8, 1)}            # 007116 bgt.b -- taken(low5>0x14)
_S0_POS_TEST_1 = (16, 1)                     # 007124 cmpi.b #2,$1(a0)
_S0_POS_BNE_1 = {True: (10, 1), False: (8, 1)}          # 00712A bne.b -- taken(!=2): decline into arm A4; not taken: state 14
_S0_POS_STATE14_ADDI = (20, 1)               # 00712C addi.w #$20,f18c (the low5>0x14, matched route only)
_S0_POS_TEST_0 = (12, 1)                     # 007118 cmpi.b #2,(a0)
_S0_POS_BEQ_0 = {True: (10, 1), False: (8, 1)}          # 00711C beq.b -- taken(==2): state 14 directly
_S0_POS_TEST_C = (8, 1)                      # 00711E cmpi.w #$c,d0
_S0_POS_BLT_C = {True: (10, 1), False: (8, 1)}          # 007122 blt.b -- taken(low5<0xc): decline into arm A4
_S0_POS_STATE14_TAIL = (20 + 16 + 16 + 4 + 16 + 16 + 16 + 10, 7)  # 007132..007150: andi f18c, f1a8=0, state=e, d7=0x1a, f1ae/f1a4/f1a6=0
_S0_BIT2_TEST = (16, 1)                      # 007154 btst.b #2,ea23
_S0_BIT2_BEQ = {True: (10, 1), False: (8, 1)}           # 00715A beq.b -- taken: cascade directly; not taken: bsr 8222
_S0_SEARCH_BSR = (18, 1)                     # 00715C bsr.w $8222
_S0_SEARCH_TST = (4, 1)                      # 007160 tst.w d0
_S0_SEARCH_BEQ = {True: (10, 1), False: (12, 1)}        # 007162 beq.w -- taken(found): hand-off; not taken: cascade

_S0_CASCADE_TEST = (12, 1)                   # 007166 tst.w f182
_S0_CASCADE_BNE = {True: (12, 1), False: (12, 1)}       # 00716A bne.w -- taken: f182-set; not taken: continue (both 12cy)
_S0_F182_TAIL = (4 + 8 + 16 + 16 + 10, 5)    # 0071D4..0071E2: d7=(d7+1)&7, f182=0, x-=4
_S0_EA20_SIGN_TEST = (12, 1)                 # 00716E tst.w ea20 (the cascade's own sign test, before the branch)
_S0_SHARED_BPL = {True: (10, 1), False: (12, 1)}        # 007172 bpl.w -- taken(ea20>=0): shared sub; not taken: grid tests
_S0_GRIDHEAD = (12 + 8, 2)                   # 007176 move.w f18c,d0; 00717A andi #$1f
_S0_GRID_BNE = {True: (10, 1), False: (8, 1)}           # 00717E bne.b -- taken(low5!=0): skip grid tests
_S0_GRID_TEST = (16, 1)                      # cmpi.b #1,offset(a0), each of the three positions
_S0_GRID_BEQ = {True: (10, 1), False: (12, 1)}          # beq.w -- taken: immediate exit; not taken: next test / advance
_S0_D7_2_TEST = (8, 1)                       # 0071A2 cmpi.w #2,d7
_S0_D7_2_BNE = {True: (10, 1), False: (8, 1)}           # 0071A6 bne.b -- not taken(d7==2): write sound $48 first
_S0_SOUND_WRITE = (16, 1)                    # move.w #imm,fdf6.w ($48 at 0071A8 or $49 at 0071B4)
_S0_D7_6_TEST = (8, 1)                       # 0071AE cmpi.w #6,d7
_S0_D7_6_BNE = {True: (10, 1), False: (8, 1)}           # 0071B2 bne.b -- not taken(d7==6): write sound $49
_S0_ADVANCE_MID = (16, 1)                    # 0071BA clr.w f182
_S0_D7_7_TEST = (8, 1)                       # 0071BE cmpi.w #7,d7
_S0_D7_7_BLE = {True: (10, 1), False: (8, 1)}           # 0071C2 ble.b -- taken(d7<=7); not taken: overflow reset
_S0_OVERFLOW_RESET = (4 + 16, 2)             # 0071C4 moveq #7,d7; 0071C6 addq.w #4,f18c (undoes the -4 above)
_S0_ADVANCE_TAIL = (4 + 8 + 10, 3)           # 0071CA addq.w #1,d7; 0071CC andi.w #7,d7; 0071D0 bra.w
_S0_POSITION_DECREMENT = (16, 1)             # 00719E subq.w #4,f18c (the position step itself, before the d7 tests)

_S0_SHARED_TEST = (12, 1)                    # 0071E6 tst.w ea1e
_S0_SHARED_BPL2 = {True: (10, 1), False: (8, 1)}        # 0071EA bpl.b -- taken: d7 test; not taken: negative tail
_S0_SHARED_NEG_TAIL = (4 + 16 + 16 + 10, 4)  # 0071EC..0071F8: d7=0xffffffff (moveq #$ff), state=$1a, f24a=0
_S0_SHARED_D7_TEST = (4, 1)                  # 0071FC tst.w d7
_S0_SHARED_D7_BEQ = {True: (10, 1), False: (12, 1)}     # 0071FE beq.w -- taken: unchanged; not taken: reset tail
_S0_SHARED_RESET_TAIL = (4 + 10, 2)          # 007202 moveq #$39,d7; 007204 bra.w

_S0_HANDOFF_HEAD = (16, 1)                   # 0074A2 move.w #6,f192; falls straight into 0074A8 (no bra, unlike state 1's own 00749A)
_S0_HANDOFF_TAIL = (4 + 12 + 4 + 14 + 10, 5)            # 0074A8..0074B4: d7=0, f190=0, table read, bra.w


def _s0_gate_cost(head):
    """007002-00701E: the cost to reach either 'wall' (007020) or arm A (007038), covering all three
    routes `state0_step` can take there -- the SAME shape `_s1_gate_cost` already names, state 0's
    own addresses and constants."""
    if head['gate_direct']:
        return _S0_GATE_BEQ[True]
    cycles, instructions = _add(_S0_GATE_BEQ[False], _S0_LOW_HEAD)
    if head['low_lt_8']:
        c, i = _S0_LOW_BLT[True]
        return cycles + c, instructions + i
    c, i = _add(_S0_LOW_BLT[False], _S0_WALL_TEST2, _S0_WALL_BEQ[head['arm'] != 'wall'])
    return cycles + c, instructions + i


def _state0_grid_cost(result):
    """0071A2-0071DE: the low-bits gate (0071A6... actually 00717E) then, when `low5 == 0`,
    `result['checked']` row-stride grid tests in program order (-1/+0x7F/+0xFF) -- the LAST one only
    'taken' (a match) on the `'grid-block'` arm.  Mirrors `_state1_grid_cost`."""
    cycles, instructions = _S0_GRIDHEAD
    c, i = _S0_GRID_BNE[result['low5'] != 0]
    cycles += c
    instructions += i
    blocked = result['arm'] == 'grid-block'
    for index in range(result['checked']):
        c, i = _S0_GRID_TEST
        cycles += c
        instructions += i
        matched = blocked and index == result['checked'] - 1
        c, i = _S0_GRID_BEQ[matched]
        cycles += c
        instructions += i
    return cycles, instructions


def _state0_cascade_cost(read, sr, d7, position_x, address):
    """007166-0075D6: state 0's own cascade cost and exit facts, the mirror of `_state1_cascade_cost`
    over state 0's own shape (see `game.player`'s module note for what genuinely differs)."""
    from .game import player
    result = player.state0_cascade(read, d7, position_x, address)
    cycles, instructions = _S0_CASCADE_TEST
    if result['arm'] == 'f182-set':
        c, i = _add(_S0_CASCADE_BNE[True], _S0_F182_TAIL)
        cycles += c
        instructions += i
        last_pc = 0x0071E2
        # 0071DE subq.w #4,f18c is the last flag-setter (SUBQ, unlike state 1's own ANDI-last shape):
        # N/Z/V/C from POSITION_X's own new value, X from the same instruction's own borrow.
        exit_sr = _sub_sr(sr, position_x, 4, 2)
        return cycles, instructions, result, last_pc, exit_sr
    c, i = _add(_S0_CASCADE_BNE[False], _S0_EA20_SIGN_TEST)
    cycles += c
    instructions += i
    c, i = _S0_SHARED_BPL[player._signed_word(read(EA20_WORD_S0, 2)) >= 0]
    cycles += c
    instructions += i
    if result['arm'] == 'shared-sub-gate':
        # 0071E6-007204: state 0's own inline copy of the shared sub-body -- resolve it for real now
        # that the cascade's own EA20 sign test proved it is reached.
        result = player.state0_shared_sub(read, d7)
    if result['arm'] not in ('grid-block', 'position-advance'):
        c, i = _S0_SHARED_TEST
        cycles += c
        instructions += i
        if result['arm'] == 'ea1e-negative':
            c, i = _add(_S0_SHARED_BPL2[False], _S0_SHARED_NEG_TAIL)
            cycles += c
            instructions += i
            last_pc = 0x0071F8
            exit_sr = _logic_sr(sr, 0, 2)          # 0071F4 clr.w f24a is the last flag-setter
            return cycles, instructions, result, last_pc, exit_sr
        c, i = _S0_SHARED_BPL2[True]
        cycles += c
        instructions += i
        c, i = _S0_SHARED_D7_TEST
        cycles += c
        instructions += i
        if result['arm'] == 'shared-unchanged':
            c, i = _S0_SHARED_D7_BEQ[True]
            cycles += c
            instructions += i
            last_pc = 0x0071FE
            exit_sr = _cmp_sr(sr, d7, 0, 2)        # 0071FC tst.w d7 is the last (and only) flag-setter
            return cycles, instructions, result, last_pc, exit_sr
        c, i = _add(_S0_SHARED_D7_BEQ[False], _S0_SHARED_RESET_TAIL)
        cycles += c
        instructions += i
        last_pc = 0x007204
        exit_sr = _cmp_sr(sr, d7, 0, 2)
        return cycles, instructions, result, last_pc, exit_sr
    grid_cycles, grid_instructions = _state0_grid_cost(result)
    if result['arm'] == 'grid-block':
        cycles += grid_cycles
        instructions += grid_instructions
        exit_sr = _cmp_sr(sr, 1, 1, 1)
        return cycles, instructions, result, result['last_pc'], exit_sr
    cycles += grid_cycles
    instructions += grid_instructions
    c, i = _S0_POSITION_DECREMENT
    cycles += c
    instructions += i
    c, i = _S0_D7_2_TEST
    cycles += c
    instructions += i
    c, i = _S0_D7_2_BNE[d7 != 2]
    cycles += c
    instructions += i
    if d7 == 2:
        c, i = _S0_SOUND_WRITE
        cycles += c
        instructions += i
    c, i = _S0_D7_6_TEST
    cycles += c
    instructions += i
    c, i = _S0_D7_6_BNE[d7 != 6]
    cycles += c
    instructions += i
    if d7 == 6:
        c, i = _S0_SOUND_WRITE
        cycles += c
        instructions += i
    c, i = _add(_S0_ADVANCE_MID, _S0_D7_7_TEST)
    cycles += c
    instructions += i
    if result.get('overflow'):
        c, i = _add(_S0_D7_7_BLE[False], _S0_OVERFLOW_RESET, _S0_ADVANCE_TAIL)
    else:
        c, i = _add(_S0_D7_7_BLE[True], _S0_ADVANCE_TAIL)
    cycles += c
    instructions += i
    last_pc = 0x0071D0
    add_x_sr = _add_sr(sr, d7, 1, 2)
    exit_sr = (_logic_sr(sr, result['d7'], 2) & ~0x10) | (add_x_sr & 0x10)
    return cycles, instructions, result, last_pc, exit_sr


EA20_WORD_S0 = 0xFFFFEA20   # the same word game.player.EA20_WORD names; a local alias to keep this
                            # section self-contained the way state 1's own block above is.


def state0_plan(machine, registers):
    """006FFE (state 0): the player state machine's own dispatch table entry 0, composed over the
    already-recovered grid cell (0063FA), contact search (008222) and the shared tail (0075D6), the
    mirror of `state1_plan`'s own shape -- but see `game.player`'s module note for the real
    differences state 0's own tracer evidence found, not assumed by symmetry."""
    from .game import player
    if registers['pc'] != STATE0_ENTRY:
        raise UnsupportedCandidate('state 0 planner needs the machine parked at 006FFE')
    sr = registers['sr']
    read = _reader(machine)
    d7 = registers['d7'] & 0xFFFF
    head = player.state0_step(read, d7)
    sr = _asl_sr(sr, head['row_source'], 3, 2)
    order = {}
    for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x007002, 4):
        order[a] = b
    cycles, instructions = _add(_S0_BSR_GRID, GRID_CELL_COST, _S0_GATE_TEST)
    d0 = head['d0'] if head['gate_direct'] else (head['position_x'] & 0x1E)
    exit_registers = {'d0': (registers['d0'] & 0xFFFF0000) | d0,
                      'd1': (registers['d1'] & 0xFFFF0000) | head['d1'],
                      'a0': head['address'] & 0xFFFFFFFF}

    if head['arm'] == 'wall':
        c, i = _add(_s0_gate_cost(head), _S0_WALL_TAIL)
        cycles += c
        instructions += i
        for a, b in head['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = head['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 00702E clr.w f198 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x007034)

    if head['arm'] == 'transition-2':
        c, i = _add(_s0_gate_cost(head), _S0_ARMA_TEST, _S0_ARMA_BNE[False], _S0_TRANS2_TAIL)
        cycles += c
        instructions += i
        for a, b in head['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = head['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 007046 moveq #0,d7 is the last flag-setter, not the move.w before it
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x007048)

    if head['arm'] == 'box-overlap':
        raise UnsupportedCandidate('state 0: the box-overlap scan (007056, FFFFEA1E == 1) is not composed here yet')

    gate_cost = _add(_s0_gate_cost(head), _S0_ARMA_TEST, _S0_ARMA_BNE[True], _S0_EA1E_TEST, _S0_EA1E_BNE[True],
                     _S0_BIT0_TEST)

    if head['arm'] == 'jump-start':
        if head['f196'] == 0:
            # 0070DE beq.b taken (EA20 == 0): the zero route, 0070E0's own bpl.b never runs.
            c, i = _add(gate_cost, _S0_BIT0_BEQ[False], _S0_A3B_TEST, _S0_A3B_BEQ[True], _S0_A3B_ZERO_HEAD)
        else:
            # 0070DE beq.b not taken, 0070E0 bpl.b not taken (EA20 < 0): both run before the negative head.
            c, i = _add(gate_cost, _S0_BIT0_BEQ[False], _S0_A3B_TEST, _S0_A3B_BEQ[False], _S0_A3B_BPL[False],
                        _S0_A3B_NEG_HEAD)
        c3, i3 = _S0_STATE8_TAIL
        cycles += c + c3
        instructions += i + i3
        for a, b in head['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = head['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x30, 2)   # 0070FA move.w #$30,fdf6 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x007100)

    if head['arm'] == 'transition-14':
        c, i = _add(gate_cost, _S0_BIT0_BEQ[False], _S0_A3B_TEST, _S0_A3B_BEQ[False], _S0_A3B_BPL[True],
                    _S0_POS_HEAD)
        low5 = head['low5']
        if low5 <= 0x14:
            c2, i2 = _add(_S0_POS_BGT[False], _S0_POS_TEST_0, _S0_POS_BEQ_0[True], _S0_POS_STATE14_TAIL)
        else:
            c2, i2 = _add(_S0_POS_BGT[True], _S0_POS_TEST_1, _S0_POS_BNE_1[False], _S0_POS_STATE14_ADDI,
                          _S0_POS_STATE14_TAIL)
        cycles += c + c2
        instructions += i + i2
        for a, b in head['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = head['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 00714C clr.w f1a6 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x007150)

    # head['arm'] == 'gate': the shared cascade, directly (EA23 bit 2 clear) or after a contact-search
    # call -- reached either straight from arm A3 (bit0 clear) or from the positive-EA20 tree's own
    # decline (low5 < 0xc, or a grid byte that did not match).
    if head.get('position_positive'):
        low5 = head['low5']
        if low5 > 0x14:
            c, i = _add(gate_cost, _S0_BIT0_BEQ[False], _S0_A3B_TEST, _S0_A3B_BEQ[False], _S0_A3B_BPL[True],
                        _S0_POS_HEAD, _S0_POS_BGT[True], _S0_POS_TEST_1, _S0_POS_BNE_1[True])
        else:
            c, i = _add(gate_cost, _S0_BIT0_BEQ[False], _S0_A3B_TEST, _S0_A3B_BEQ[False], _S0_A3B_BPL[True],
                        _S0_POS_HEAD, _S0_POS_BGT[False], _S0_POS_TEST_0, _S0_POS_BEQ_0[False], _S0_POS_TEST_C,
                        _S0_POS_BLT_C[low5 < 0xC])
            if low5 >= 0xC:
                c, i = _add((c, i), _S0_POS_TEST_1, _S0_POS_BNE_1[True])
    else:
        c, i = _add(gate_cost, _S0_BIT0_BEQ[True], _S0_BIT2_TEST)
    cycles += c
    instructions += i
    position_x = head['position_x']
    address = head['address']

    if not head['needs_search']:
        c, i = _S0_BIT2_BEQ[True]
        cycles += c
        instructions += i
        cc, ci, result, last_pc, exit_sr = _state0_cascade_cost(read, sr, d7, position_x, address)
        cycles += cc
        instructions += ci
        if 'stores' in result:
            for a, b in result['stores'].items():
                for aa, bb in _bytes(a, b[0], b[1]):
                    order[aa] = bb
        if 'd7_full' in result:
            exit_registers['d7'] = result['d7_full']
        elif 'd7' in result:
            exit_registers['d7'] = _cascade_exit_d7(registers['d7'], result)
        if 'd0' in result:
            exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | result['d0']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = exit_sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    c, i = _S0_BIT2_BEQ[False]
    cycles += c
    instructions += i
    sp32 = registers['a7']
    c, i = _S0_SEARCH_BSR
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x007160, 4):
        order[a] = b
    cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
        machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4}, sp32 - 4)
    cycles += cs_cycles
    instructions += cs_instructions
    order.update(cs_order)
    exit_registers.update(cs_registers)
    exit_registers['d0'] = cs_registers['d0']
    c, i = _S0_SEARCH_TST
    cycles += c
    instructions += i
    found = cs_result['d0'] == 0
    c, i = _S0_SEARCH_BEQ[found]
    cycles += c
    instructions += i

    if found:
        handoff = player.state0_handoff(read)
        c, i = _add(_S0_HANDOFF_HEAD, _S0_HANDOFF_TAIL)
        cycles += c
        instructions += i
        for a, b in handoff['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = handoff['d7']
        exit_registers['pc'] = 0x0075DA
        exit_registers['sr'] = _logic_sr(cs_registers['sr'], handoff['d7'], 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0074B4)

    cc, ci, result, last_pc, exit_sr = _state0_cascade_cost(read, cs_registers['sr'], d7, position_x, address)
    cycles += cc
    instructions += ci
    if 'stores' in result:
        for a, b in result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
    if 'd7_full' in result:
        exit_registers['d7'] = result['d7_full']
    elif 'd7' in result:
        exit_registers['d7'] = _cascade_exit_d7(registers['d7'], result)
    if 'd0' in result:
        exit_registers['d0'] = (cs_registers['d0'] & 0xFFFF0000) | result['d0']
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = exit_sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=last_pc)


# --- 006DA6: state 14 (game.player.state14_step / state14_arm_a / state14_arm_b /
# state14_contact / state14_arm_d / state14_settle / state14_settle_probe) ------------------------
#
# Costed one instruction-block at a time from the tracer, the shape states 0/1 already established
# for a branchy dispatcher; every block's own evidence is `census-006DA6/006DA6-entry-p*.state`
# (204 `factcheck.py facts --path` traces, 183 real path classes) plus one `branches --vary` sweep
# for the head's own EA20==0 clear.  `game.player`'s own module note transcribes the shape.  The
# settle tail's own `FFFFF1AE != 0` continuation (`006F84` onward) IS witnessed -- a real fraction of
# activations carry an odd prior sound-trigger count into settle -- and is fully composed as the
# `'probe-f1ae'`/`'loopback'` arms (`_state14_settle_cost`'s own bounded, provably-at-most-two-pass
# loop); an earlier survey wrongly declined this fork by misapplying state 1's own `007386` dead-code
# argument to it (docs/gods/blockers/2026-09-17-008222.md's addendum records the error).  The settle
# tail's own `FFFFEA20 != 0` fork (also witnessed, ~7% of the census) hands off to `state14_step`'s
# own ARMSEL test at `006DD4` -- composed via the shared `_state14_main_dispatch` helper, reused
# verbatim by both this handoff and the top-level 'main' path, rather than a second copy.  No arm
# declines by name any more: arm B's own `+0x17F` nibble sub-test (once thought unwitnessed, a
# `'nibble-declined'` stub) turns out to mirror arm A's own `+0x181` test exactly -- a matched byte
# reaches `'contact-gate-nibble'`, anything else (including the low nibble already zero) falls
# through to `'transition-0'` directly, exactly like arm A's `'transition-1'` -- the original survey
# misread the disassembly; a tree recording outside the single-history census exercised the
# fallthrough and caught it (`game.player.state14_arm_b`'s own module note records the fix).  Three
# more real bugs the tree caught the same way, all fixed the same way (a real trace outside the
# single-history census, never guessed): `FFFFF1A4`'s own unconditional clear in arm A (`006DFA`, it
# runs before the retry-budget compare looks at its own result) was missing from three of arm A's own
# downstream stores; arm B has NO such re-clear past its own retry budget (`FFFFF1A4` only ever
# increments there, `006E78`, never re-zeroed the way arm A re-zeros `FFFFF1A6` at `006E0A`) -- three
# of arm B's own downstream stores wrongly hardcoded zero instead of carrying the incremented value
# forward; `006E2A`/`006EA0`'s own `move.w f18e,d0;andi.w #$f,d0` overwrites D0 with the low nibble
# before EITHER arm's own nibble-tested exit, missed on `'contact-gate-nibble'` (both arms) the first
# time; and `_S14B_NIBBLE_BEQ`'s own taken/not-taken costs were transcribed backwards.  The ARM
# 8222-found continuation's own choice of which contact-search body ran is exact (no extra decline:
# `state14_contact`'s own `negative` flag selects it, matching `pickups.contact_consume`'s own
# routine convention).
STATE14_ENTRY = 0x006DA6

_S14_FROZEN_TEST = (12, 1)                   # 006DA6 tst.w ef4a
_S14_FROZEN_BEQ = {True: (10, 1), False: (12, 1)}       # 006DAA beq.w -- taken: exit unchanged
_S14_WRAP_TEST = (8, 1)                      # 006DAE cmpi.w #$14,d7
_S14_WRAP_BLT = {True: (10, 1), False: (8, 1)}          # 006DB2 blt.b -- taken(d7<20): main path
_S14_WRAP_RESET = (4 + 10, 2)                # 006DB4 moveq #0,d7; 006DB6 bra.w 6f48
_S14_STORE_F1B0 = (12, 1)                    # 006DBA move.w d7,f1b0
_S14_EA1E_TEST = (12, 1)                     # 006DBE tst.w ea1e
_S14_EA1E_BMI = {True: (10, 1), False: (12, 1)}         # 006DC2 bmi.w -- taken: settle (carry d7)
_S14_EA20_TEST0 = (12, 1)                    # 006DC6 tst.w ea20
_S14_EA20_BNE0 = {True: (10, 1), False: (8, 1)}         # 006DCA bne.b -- taken(!=0): skip the clear
_S14_CLEAR = (16 + 16, 2)                    # 006DCC clr f1a4; 006DD0 clr f1a6
_S14_ARMSEL_TEST = (16, 1)                   # 006DD4 cmpi.w #1,ea20
_S14_ARMSEL_BNE = {True: (10, 1), False: (12, 1)}       # 006DDA bne.w -- taken(!=1): arm B

_S14A_BIT2 = (16, 1)                         # 006DDE btst #2,ea23
_S14A_BIT2_BEQ = {True: (10, 1), False: (8, 1)}         # 006DE4 beq.b -- taken(clear): 6DF0
_S14A_SET_F1A8 = (16, 1)                     # 006DE6 move.w #1,f1a8
_S14A_BRA_C = (10, 1)                        # 006DEC bra.w 6ec4
_S14A_BIT0 = (16, 1)                         # 006DF0 btst #0,ea23
_S14A_BIT0_BNE = {True: (10, 1), False: (12, 1)}        # 006DF6 bne.w -- taken(set): transition-9
_S14_TRANS_9_OR_8 = (16 + 16 + 4 + 20 + 16 + 16 + 10, 7)   # move state; f196; d7; f19a; f19c; fdf6; bra
_S14A_HEAD2 = (16 + 16 + 16, 3)              # 006DFA clr f1a4; 006DFE addq.w #1,f1a6 (mem); 006E02 cmpi.w #5,f1a6 (mem)
_S14A_F1A6_BLE = {True: (10, 1), False: (8, 1)}         # 006E08 ble.b -- taken(<=5): contact-gate-plain
_S14A_GRIDSETUP = (16 + 18, 2)               # 006E0A clr f1a6; 006E0E bsr 63fa
_S14_GRID_TEST = (16, 1)                     # cmpi.b #1,offset(a0)
_S14_GRID_BEQ = {True: (10, 1), False: (8, 1)}          # beq.b -- taken: matched (detour/direct per arm)
_S14_NIBBLE_HEAD = (12 + 8, 2)                # move f18e,d0; andi #$f,d0
_S14A_NIBBLE_BEQ = {True: (10, 1), False: (8, 1)}       # 006E32 beq.b -- taken(==0): transition-1 directly
_S14A_NIBBLE_TEST = (16, 1)                  # 006E34 cmpi.b #1,$181(a0)
_S14A_NIBBLE_BEQ2 = {True: (10, 1), False: (8, 1)}      # 006E3A beq.b -- taken: detour to 6E50
_S14_TRANS_1_OR_0 = (16 + 4 + 16 + 16 + 10, 5)   # move state; d7; position step x/y; bra
_S14A_DETOUR = (12 + 10, 2)                  # 006E50 tst ea20; 006E54 bpl.w (always taken here: ea20==1)

_S14B_EA20_TEST = (12, 1)                    # 006E50 tst.w ea20 (arm B's own entry)
_S14B_EA20_BPL = {True: (10, 1), False: (12, 1)}        # 006E54 bpl.w -- taken(>=0): contact-gate-plain
_S14B_BIT2 = (16, 1)                         # 006E58 btst #2,ea23
_S14B_BIT2_BEQ = {True: (10, 1), False: (8, 1)}         # 006E5E beq.b -- taken(clear): 6E6A
_S14B_SET_F1A8 = (16, 1)                     # 006E60 move.w #$ffff,f1a8
_S14B_BRA_C = (10, 1)                        # 006E66 bra.w 6ec4
_S14B_BIT0 = (16, 1)                         # 006E6A btst #0,ea23
_S14B_BIT0_BNE = {True: (10, 1), False: (12, 1)}        # 006E70 bne.w -- taken(set): transition-8
_S14B_HEAD2 = (16 + 16 + 16, 3)              # 006E74 clr f1a6; 006E78 addq.w #1,f1a4 (mem); 006E7C cmpi.w #5,f1a4 (mem)
_S14B_F1A4_BLE = {True: (10, 1), False: (8, 1)}         # 006E82 ble.b -- taken(<=5): contact-gate-plain
_S14B_GRIDSETUP = (18, 1)                    # 006E84 bsr 63fa (no extra clear -- head2 already cleared f1a6)
_S14B_NIBBLE_BEQ = {True: (10, 1), False: (8, 1)}       # 006EA8 beq.b -- taken(==0): transition-0 directly
_S14B_NIBBLE_TEST = (16, 1)                  # 006EAA cmpi.b #1,$17f(a0)
_S14B_NIBBLE_BEQ2 = {True: (10, 1), False: (8, 1)}      # 006EB0 beq.b -- taken: contact-gate-nibble (lands on 006EC4 directly)

_S14C_BIT2 = (16, 1)                         # 006EC4 btst #2,ea23
_S14C_BIT2_BEQ = {True: (10, 1), False: (8, 1)}         # 006ECA beq.b -- taken(clear): arm D
_S14C_F1A8_TEST = (12, 1)                    # 006ECC tst.w f1a8
_S14C_F1A8_BEQ = {True: (10, 1), False: (8, 1)}         # 006ED0 beq.b -- taken(==0): arm D
_S14C_F1A8_BMI = {True: (10, 1), False: (8, 1)}         # 006ED2 bmi.b -- taken(negative): the 25-body bsr
_S14C_BSR = (18, 1)                          # bsr.w 8222
_S14C_TST_D0 = (4, 1)                        # tst.w d0
_S14C_BNE_D0 = {True: (10, 1), False: (12, 1)}          # bne.w -- taken(!=0, NOT FOUND): arm D
_S14C_FOUND_HEAD = (20 + 12, 2)              # move f18e,f1aa; move d7,f1ac
_S14C_FOUND_BTST = (10, 1)                   # btst #0,d7
_S14C_FOUND_BNE = {True: (10, 1), False: (8, 1)}        # bne.b -- taken(odd, skip the subq)
_S14C_FOUND_SUBQ = (16, 1)                   # subq.w #4,f18e (even d7 only)
_S14C_FOUND_TAIL = (16 + 4 + 10, 3)          # move.w #imm,f192; moveq #0,d7; bra

_S14D_EA1E_TEST = (16, 1)                    # 006F28 cmpi.w #1,ea1e
_S14D_EA1E_BNE = {True: (10, 1), False: (12, 1)}        # 006F2E bne.w -- taken(!=1): exit unchanged
_S14D_TRANS13 = (16 + 16 + 16 + 16 + 10, 5)  # not f1ae; state=d; clr f1a4; clr f1a6; bra

_S14S_EA20_TEST = (12, 1)                    # 006F48 tst.w ea20
_S14S_EA20_BNE = {True: (10, 1), False: (12, 1)}        # 006F4C bne.w -- taken(!=0): rejoin main at 6DD4
_S14S_CLEAR = (16 + 16, 2)                   # 006F50 clr f1a4; 006F54 clr f1a6
_S14S_F1AE_TEST = (12, 1)                    # 006F58 tst.w f1ae
_S14S_F1AE_BNE = {True: (10, 1), False: (8, 1)}         # 006F5C bne.b -- taken(!=0): the F1AE fork
_S14S_F1AE_SUBQ = (4, 1)                     # 006F84 subq.w #1,d7 (register form, the F1AE fork's own single decrement)
_S14S_F1AE_BNE2 = {True: (10, 1), False: (8, 1)}        # 006F86 bne.b -- taken(!=0): probe; not taken(==0): loopback tail
_S14S_LOOPBACK_TAIL = (16 + 4 + 16 + 10, 4)  # 006F88 fdf6=$6a; 006F8E addq #1,d7; 006F90 not f1ae; 006F94 bra.b 6f48
_S14S_BUMP = (4 + 8, 2)                      # 006F5E addq #1,d7; 006F60 cmpi #3,d7
_S14S_BUMP_BGT = {True: (10, 1), False: (8, 1)}         # 006F64 bgt.b -- taken(>3): sound route
_S14S_SOUND = (16 + 16 + 4 + 4, 4)           # fdf6=$6a; not f1ae; subq #1,d7 (twice)
_S14S_SOUND_BNE = (10, 1)                    # 006F86 bne.b -- always taken (d7 > 3 entering makes d7-1 >= 2)
_S14S_PROBE_HEAD = (20 + 16 + 18, 3)         # move f18e,f1b2; subq #6,f18e; bsr 63fa
_S14S_PROBE_BRA = (10, 1)                    # 006F74 bra.w 6f96
_S14S_TEST1 = (16, 1)                        # 006F96 cmpi.b #2,$80(a0)
_S14S_TEST1_BEQ = {True: (10, 1), False: (12, 1)}       # 006F9C beq.w -- taken: blocked, exit
_S14S_TEST2 = (16, 1)                        # 006FA0 cmpi.b #2,-$80(a0)
_S14S_TEST2_BEQ = {True: (10, 1), False: (12, 1)}       # 006FA6 beq.w -- taken: blocked, exit
_S14S_EXHAUST_TAIL = (12 + 20 + 10, 3)       # move f1b0,d7; move f1b2,f18e; bra


def _state14_contact_cost(read, sr, gate_result):
    """006EC4-006F44: the contact-search gate both arm A and arm B's own `'contact-gate'`/
    `'contact-gate-plain'` results reach, plus arm D's own fall-through -- shared cost logic since
    both arms leave the SAME instructions to run from here."""
    from .game import player
    cycles, instructions = _S14C_BIT2
    contact = player.state14_contact(read, 0, gate_result.get('d7', 0), gate_result.get('f1a8_forced'))
    if contact['arm'] == 'arm-d':
        # Either 006ECA's own beq (bit 2 clear) or 006ED0's own beq (f1a8 == 0) reached here; the
        # semantics does not distinguish which test fired since both cost the SAME (16, 1) + a taken
        # beq.b -- read which one directly to keep the cost exact.
        bit2 = read(player.EA23_WORD, 1) & 4
        if not bit2:
            c, i = _S14C_BIT2_BEQ[True]
        else:
            c, i = _add(_S14C_BIT2_BEQ[False], _S14C_F1A8_TEST, _S14C_F1A8_BEQ[True])
        cycles += c
        instructions += i
        return cycles, instructions, {'arm': 'arm-d'}, False
    c, i = _add(_S14C_BIT2_BEQ[False], _S14C_F1A8_TEST, _S14C_F1A8_BEQ[False], _S14C_F1A8_BMI[contact['negative']],
                _S14C_BSR)
    cycles += c
    instructions += i
    return cycles, instructions, contact, True


def _state14_arm_d_cost(read, sr):
    """006F28-006F44: state 14's own arm D."""
    from .game import player
    result = player.state14_arm_d(read)
    if result['arm'] == 'unchanged':
        c, i = _add(_S14D_EA1E_TEST, _S14D_EA1E_BNE[True])
        # 006F28 cmpi.w #1,ea1e is the last (and only) flag-setter; bne itself touches nothing.
        exit_sr = _cmp_sr(sr, read(player.EA1E_WORD, 2), 1, 2)
        return c, i, result, 0x006F2E, exit_sr
    c, i = _add(_S14D_EA1E_TEST, _S14D_EA1E_BNE[False], _S14D_TRANS13)
    # 006F32 not.w f1ae is NOT the last flag-setter here: 006F36's own move.w #$d,f192.w and then
    # 006F3C/006F40's own clr.w f1a4.w / clr.w f1a6.w all run afterwards, and CLR unconditionally
    # sets Z=1, N=V=C=0 (X untouched) -- 006F40 (the LAST of the two CLRs) is the true last setter.
    exit_sr = _logic_sr(sr, 0, 2)
    return c, i, result, 0x006F44, exit_sr


def _state14_settle_cost(read, sr, settle_d7, sp32, f1b0_value, d7_register):
    """006F48-006FB4: state 14's own "settle" tail, reached from `state14_plan`'s own head with
    `settle_d7` either freshly reset to 0 or carrying the caller's own STATE_COUNTER.  Almost always
    one pass through `player.state14_settle`; the `'loopback'` arm (`FFFFF1AE != 0` on entry, the
    caller's own counter exactly 1) takes a second pass with `FFFFF1AE` now clear -- provably the
    only possible extra pass (`player.state14_settle`'s own module note), so the loop below is
    capped at three passes purely as a defensive check, not a modelling choice.  `d7_register` is
    the FULL 32-bit register this tail starts with (0 on a fresh reset -- its own `moveq #0,d7` --
    or the outer entry's own value, upper half included, when carried): every store here is an
    ADDQ/SUBQ/AND on the low word only (`state14_settle`'s own bump/subq, the loopback's own second
    pass), so this upper half survives unchanged through every exit below, merged back in rather
    than truncated the way a plain low-16 return once was (`factcheck.py check
    --perturb-upper-halves`, 18 September)."""
    from .game import player

    def high_d7(low):
        return (d7_register & 0xFFFF0000) | (low & 0xFFFF)

    order = {}
    cycles, instructions = (0, 0)
    current_d7 = settle_d7
    f1ae_override = None
    for _ in range(3):
        result = player.state14_settle(read, current_d7, f1ae_override)
        for a, b in result.get('stores', {}).items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        c, i = _S14S_EA20_TEST
        cycles += c
        instructions += i
        if result['arm'] == 'rejoin-main':
            c, i = _S14S_EA20_BNE[True]
            cycles += c
            instructions += i
            return cycles, instructions, order, None, None, None, 'rejoin-main', None
        c, i = _add(_S14S_EA20_BNE[False], _S14S_CLEAR, _S14S_F1AE_TEST)
        cycles += c
        instructions += i
        if result['arm'] == 'loopback':
            c, i = _add(_S14S_F1AE_BNE[True], _S14S_F1AE_SUBQ, _S14S_F1AE_BNE2[False], _S14S_LOOPBACK_TAIL)
            cycles += c
            instructions += i
            current_d7 = result['next_d7']
            f1ae_override = result['next_f1ae']
            continue
        if result['arm'] == 'probe-f1ae':
            # 006F84's own single subq.w #1,d7 (the caller's own UNMODIFIED counter) then 006F86's
            # own bne.b TAKEN (the result is nonzero): straight to the probe, no bump, no sound.
            c, i = _add(_S14S_F1AE_BNE[True], _S14S_F1AE_SUBQ, _S14S_F1AE_BNE2[True])
            cycles += c
            instructions += i
            break
        c, i = _add(_S14S_F1AE_BNE[False], _S14S_BUMP)
        cycles += c
        instructions += i
        sound = result['sound']
        c, i = _S14S_BUMP_BGT[sound]
        cycles += c
        instructions += i
        if sound:
            c, i = _add(_S14S_SOUND, _S14S_SOUND_BNE)
            cycles += c
            instructions += i
        break
    else:
        raise UnsupportedCandidate('state 14 settle: more than two passes through 006F48 not witnessed by a recording')

    settle_d7_final = result['settle_d7']
    probe = player.state14_settle_probe(read, settle_d7_final, f1b0_value)
    for a, b in probe.get('stores', {}).items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb
    c, i = _S14S_PROBE_HEAD
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x006F74, 4):
        order[a] = b
    c, i = GRID_CELL_COST
    cycles += c
    instructions += i
    c, i = _S14S_PROBE_BRA
    cycles += c
    instructions += i
    c, i = _S14S_TEST1
    cycles += c
    instructions += i
    if probe['arm'] == 'blocked':
        first_match = read((probe['cell']['address'] + 0x80) & 0xFFFFFF, 1) == 2
        c, i = _S14S_TEST1_BEQ[first_match]
        cycles += c
        instructions += i
        if first_match:
            exit_sr = _cmp_sr(sr, 2, 2, 1)   # the matching cmpi.b #2,offset(a0): result 0, Z=1
            return cycles, instructions, order, high_d7(settle_d7_final), exit_sr, 0x006F9C, 'blocked', probe['cell']
        c, i = _add(_S14S_TEST2, _S14S_TEST2_BEQ[True])
        cycles += c
        instructions += i
        exit_sr = _cmp_sr(sr, 2, 2, 1)
        return cycles, instructions, order, high_d7(settle_d7_final), exit_sr, 0x006FA6, 'blocked', probe['cell']
    c, i = _add(_S14S_TEST1_BEQ[False], _S14S_TEST2, _S14S_TEST2_BEQ[False], _S14S_EXHAUST_TAIL)
    cycles += c
    instructions += i
    # _S14S_EXHAUST_TAIL is THREE instructions, not one: "move f1b0,d7; move f1b2,f18e; bra" -- the
    # grid_cell call's own asl.w (inside PROBE_HEAD's own bsr) is long overwritten by the time this
    # tail runs.  The LAST flag-setter is the SECOND move (f1b2,f18e), restoring the ORIGINAL
    # (pre-probe) POSITION_Y that PROBE_HEAD's own "move f18e,f1b2" saved before the -6 step and
    # grid_cell call -- caught by a real trace outside the single-history census (SR left unchanged
    # at 0, not the asl.w's own nonzero result).
    exit_sr = _logic_sr(sr, read(player.POSITION_Y, 2), 2)
    return cycles, instructions, order, high_d7(probe['d7']), exit_sr, 0x006FB4, 'exhausted', probe['cell']


def _state14_main_dispatch(machine, read, registers, sr, order, exit_registers, cycles, instructions,
                            ea20_one, d7, d7_register):
    """006DDE onward: state 14's own EA20-based arm dispatch (arm A/B, the shared contact-search
    gate, arm D, and the contact-search 'found' continuation) -- shared between the top-level
    'main' path (`state14_plan`'s own head) and the settle tail's own `'rejoin-main'` handoff
    (`006F4C bne.w $6dd4` lands exactly at this dispatch's own ARMSEL test, `_S14_ARMSEL_TEST`,
    already accounted for by each caller before this function is entered).  `d7` is the LOW 16 BITS
    of the machine's own live D7 at the moment this dispatch starts (the outer entry D7 for the
    top-level path, `head['settle_d7']` for the rejoin), used only for the odd/even test inside the
    contact-search 'found' continuation below.  `d7_register` is the FULL 32-bit register this
    dispatch starts with -- the outer entry's own `registers['d7']` for the top-level path (nothing
    before it touches D7 at all, upper half included) or, for the rejoin, EITHER that same entry
    value (settle carried the counter forward untouched) OR exactly 0 (a fresh-reset settle entry's
    own `moveq #0,d7`, a FULL clear, not just the low 16 bits it forces to 0) -- the caller decides
    which.  Set as the baseline exit register here (every later arm that DOES change D7 -- the
    transitions, the found continuation -- overwrites it below): arm D's own `'unchanged'` result
    leaves it unset, relying on D7 already equalling this baseline (caught twice on a tree recording
    outside the single-history census: first that the reset case needs 0, not the plan's own OUTER
    entry value; then, under `factcheck.py check --perturb-upper-halves`, that neither case may
    truncate the register's own upper half the way a plain `d7 & 0xFFFF` did)."""
    from .game import player
    exit_registers['d7'] = d7_register
    if ea20_one:
        arm_result = player.state14_arm_a(read)
    else:
        arm_result = player.state14_arm_b(read)

    if 'cell' in arm_result:
        exit_registers['a0'] = arm_result['cell']['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | arm_result['cell']['d0']
        exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | arm_result['cell']['d1']
    if 'd0' in arm_result:
        # 006E2A/006EA0's own "move.w f18e,d0; andi.w #$f,d0" overwrites grid_cell's own d0 (the
        # column) with POSITION_Y's own low nibble on the transition-1/0 arms.
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | arm_result['d0']

    if arm_result['arm'] in ('transition-9', 'transition-8'):
        if ea20_one:
            c, i = _add(_S14A_BIT2, _S14A_BIT2_BEQ[True], _S14A_BIT0, _S14A_BIT0_BNE[True], _S14_TRANS_9_OR_8)
        else:
            c, i = _add(_S14B_EA20_TEST, _S14B_EA20_BPL[False], _S14B_BIT2, _S14B_BIT2_BEQ[True], _S14B_BIT0,
                        _S14B_BIT0_BNE[True], _S14_TRANS_9_OR_8)
        cycles += c
        instructions += i
        for a, b in arm_result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = arm_result['d7']
        exit_registers['pc'] = 0x0075D6
        # move.w #$30,fdf6 is the last flag-setter on both transitions (value 0x30, N=0, Z=0).
        exit_registers['sr'] = _logic_sr(sr, 0x30, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006FF8 if ea20_one else 0x006FD6)

    if arm_result['arm'] in ('transition-1', 'transition-0'):
        if ea20_one:
            for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x006E12, 4):
                order[a] = b
            c, i = _add(_S14A_BIT2, _S14A_BIT2_BEQ[True], _S14A_BIT0, _S14A_BIT0_BNE[False], _S14A_HEAD2,
                        _S14A_F1A6_BLE[False], _S14A_GRIDSETUP, GRID_CELL_COST)
            for offset in (1, 0x81, 0x101):
                c, i = _add((c, i), _S14_GRID_TEST, _S14_GRID_BEQ[False])
            c, i = _add((c, i), _S14_NIBBLE_HEAD, _S14A_NIBBLE_BEQ[not arm_result['nibble_tested']])
            if arm_result['nibble_tested']:
                c, i = _add((c, i), _S14A_NIBBLE_TEST, _S14A_NIBBLE_BEQ2[False])
            c, i = _add((c, i), _S14_TRANS_1_OR_0)
        else:
            for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x006E88, 4):
                order[a] = b
            c, i = _add(_S14B_EA20_TEST, _S14B_EA20_BPL[False], _S14B_BIT2, _S14B_BIT2_BEQ[True], _S14B_BIT0,
                        _S14B_BIT0_BNE[False], _S14B_HEAD2, _S14B_F1A4_BLE[False], _S14B_GRIDSETUP, GRID_CELL_COST)
            for offset in (-1, 0x7F, 0xFF):
                c, i = _add((c, i), _S14_GRID_TEST, _S14_GRID_BEQ[False])
            c, i = _add((c, i), _S14_NIBBLE_HEAD, _S14B_NIBBLE_BEQ[not arm_result['nibble_tested']])
            if arm_result['nibble_tested']:
                c, i = _add((c, i), _S14B_NIBBLE_TEST, _S14B_NIBBLE_BEQ2[False])
            c, i = _add((c, i), _S14_TRANS_1_OR_0)
        cycles += c
        instructions += i
        for a, b in arm_result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = arm_result['d7']
        exit_registers['pc'] = 0x0075D6
        # 006E48/006EBC's own subq.w #4,POSITION_Y is the last flag-setter on both transitions.
        exit_sr = _sub_sr(sr, read(player.POSITION_Y, 2), 4, 2)
        exit_registers['sr'] = exit_sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006E4C if ea20_one else 0x006EC0)

    # every remaining arm reaches the shared contact-search gate (006EC4); each name below is one
    # exact ROM path (`game.player`'s own return contract names each one distinctly for this reason).
    arm_name = arm_result['arm']
    if ea20_one:
        if arm_name == 'contact-gate':
            c, i = _add(_S14A_BIT2, _S14A_BIT2_BEQ[False], _S14A_SET_F1A8, _S14A_BRA_C)
        elif arm_name == 'contact-gate-f1a6':
            c, i = _add(_S14A_BIT2, _S14A_BIT2_BEQ[True], _S14A_BIT0, _S14A_BIT0_BNE[False], _S14A_HEAD2,
                        _S14A_F1A6_BLE[True], _S14A_DETOUR)
        else:
            # 'contact-gate-grid' (a grid byte matched) or 'contact-gate-nibble' (the +0x181 match):
            # both run the full grid setup and at least the first grid test; 006E50's own tst+bpl
            # re-fires (always taken here, EA20 == 1) before 006EC4 either way.
            for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x006E12, 4):
                order[a] = b
            c, i = _add(_S14A_BIT2, _S14A_BIT2_BEQ[True], _S14A_BIT0, _S14A_BIT0_BNE[False], _S14A_HEAD2,
                        _S14A_F1A6_BLE[False], _S14A_GRIDSETUP, GRID_CELL_COST)
            if arm_name == 'contact-gate-grid':
                address = arm_result['cell']['address']
                matched_offset = next(o for o in (1, 0x81, 0x101) if read((address + o) & 0xFFFFFF, 1) == 1)
                for offset in (1, 0x81, 0x101):
                    c, i = _add((c, i), _S14_GRID_TEST, _S14_GRID_BEQ[offset == matched_offset])
                    if offset == matched_offset:
                        break
            else:
                for offset in (1, 0x81, 0x101):
                    c, i = _add((c, i), _S14_GRID_TEST, _S14_GRID_BEQ[False])
                c, i = _add((c, i), _S14_NIBBLE_HEAD, _S14A_NIBBLE_BEQ[False], _S14A_NIBBLE_TEST,
                            _S14A_NIBBLE_BEQ2[True])
            c, i = _add((c, i), _S14A_DETOUR)
    else:
        if arm_name == 'contact-gate-immediate':
            c, i = _add(_S14B_EA20_TEST, _S14B_EA20_BPL[True])
        elif arm_name == 'contact-gate':
            c, i = _add(_S14B_EA20_TEST, _S14B_EA20_BPL[False], _S14B_BIT2, _S14B_BIT2_BEQ[False], _S14B_SET_F1A8,
                        _S14B_BRA_C)
        elif arm_name == 'contact-gate-f1a4':
            c, i = _add(_S14B_EA20_TEST, _S14B_EA20_BPL[False], _S14B_BIT2, _S14B_BIT2_BEQ[True], _S14B_BIT0,
                        _S14B_BIT0_BNE[False], _S14B_HEAD2, _S14B_F1A4_BLE[True])
        else:
            # 'contact-gate-grid' (a grid byte matched, -1/+0x7F/+0xFF) or 'contact-gate-nibble' (the
            # +0x17F match): both run the full grid setup; either lands directly on 006EC4, no extra
            # detour needed (unlike arm A's own mirror, arm B's own grid/nibble tests already target
            # 006EC4 directly).
            for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x006E88, 4):
                order[a] = b
            c, i = _add(_S14B_EA20_TEST, _S14B_EA20_BPL[False], _S14B_BIT2, _S14B_BIT2_BEQ[True], _S14B_BIT0,
                        _S14B_BIT0_BNE[False], _S14B_HEAD2, _S14B_F1A4_BLE[False], _S14B_GRIDSETUP, GRID_CELL_COST)
            if arm_name == 'contact-gate-grid':
                address = arm_result['cell']['address']
                matched_offset = next(o for o in (-1, 0x7F, 0xFF) if read((address + o) & 0xFFFFFF, 1) == 1)
                for offset in (-1, 0x7F, 0xFF):
                    c, i = _add((c, i), _S14_GRID_TEST, _S14_GRID_BEQ[offset == matched_offset])
                    if offset == matched_offset:
                        break
            else:
                for offset in (-1, 0x7F, 0xFF):
                    c, i = _add((c, i), _S14_GRID_TEST, _S14_GRID_BEQ[False])
                c, i = _add((c, i), _S14_NIBBLE_HEAD, _S14B_NIBBLE_BEQ[False], _S14B_NIBBLE_TEST,
                            _S14B_NIBBLE_BEQ2[True])
    cycles += c
    instructions += i
    for a, b in arm_result.get('stores', {}).items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb

    gc, gi, contact, has_contact = _state14_contact_cost(read, sr, arm_result)
    cycles += gc
    instructions += gi

    if not has_contact:
        arm_d_c, arm_d_i, arm_d_result, arm_d_last_pc, arm_d_sr = _state14_arm_d_cost(read, sr)
        cycles += arm_d_c
        instructions += arm_d_i
        for a, b in arm_d_result.get('stores', {}).items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = arm_d_sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=arm_d_last_pc)

    sp32 = registers['a7']
    return_pc = 0x006F02 if contact['negative'] else 0x006ED8
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, return_pc, 4):
        order[a] = b
    cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
        machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4}, sp32 - 4)
    cycles += cs_cycles
    instructions += cs_instructions
    order.update(cs_order)
    exit_registers.update(cs_registers)
    exit_registers['d0'] = cs_registers['d0']
    c, i = _S14C_TST_D0
    cycles += c
    instructions += i
    found = cs_result['d0'] == 0
    c, i = _S14C_BNE_D0[not found]
    cycles += c
    instructions += i

    if not found:
        arm_d_c, arm_d_i, arm_d_result, arm_d_last_pc, arm_d_sr = _state14_arm_d_cost(read, cs_registers['sr'])
        cycles += arm_d_c
        instructions += arm_d_i
        for a, b in arm_d_result.get('stores', {}).items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = arm_d_sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=arm_d_last_pc)

    found_result = player.state14_contact_found(read, d7, contact['negative'])
    c, i = _add(_S14C_FOUND_HEAD, _S14C_FOUND_BTST)
    cycles += c
    instructions += i
    even = d7 & 1 == 0
    c, i = _S14C_FOUND_BNE[not even]
    cycles += c
    instructions += i
    if even:
        c, i = _S14C_FOUND_SUBQ
        cycles += c
        instructions += i
    c, i = _S14C_FOUND_TAIL
    cycles += c
    instructions += i
    for a, b in found_result['stores'].items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb
    exit_registers['d7'] = found_result['d7']
    exit_registers['pc'] = 0x0075D6
    # 006EF8/006F22's own moveq #0,d7 is the last flag-setter (Z=1, N=0, V=0, C=0; MOVEQ clears X's
    # own bearing on later reads but does not itself touch X -- surviving from whatever the last
    # arithmetic before it left, here the found-continuation's own conditional subq.w #4 or nothing).
    exit_registers['sr'] = _logic_sr(cs_registers['sr'], 0, 2)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x006EFA if not contact['negative'] else 0x006F24)


def state14_plan(machine, registers):
    """006DA6 (state 14): the player state machine's own dispatch table entry 14, a vertical-
    movement dispatcher composed over the already-recovered grid cell (0063FA) and contact search
    (008222).  See `game.player`'s own module note above `state14_step` for the shape."""
    from .game import player
    if registers['pc'] != STATE14_ENTRY:
        raise UnsupportedCandidate('state 14 planner needs the machine parked at 006DA6')
    sr = registers['sr']
    read = _reader(machine)
    d7 = registers['d7'] & 0xFFFF
    head = player.state14_step(read, d7)
    order = {}
    exit_registers = {}

    if head['arm'] == 'frozen':
        cycles, instructions = _add(_S14_FROZEN_TEST, _S14_FROZEN_BEQ[True])
        exit_sr = _logic_sr(sr, 0, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=(),
                          registers={'pc': 0x0075D6, 'sr': exit_sr}, last_pc=0x006DAA)

    cycles, instructions = _add(_S14_FROZEN_TEST, _S14_FROZEN_BEQ[False], _S14_WRAP_TEST)

    if head['arm'] == 'settle':
        c, i = _S14_WRAP_BLT[not head['reset']]
        cycles += c
        instructions += i
        if head['reset']:
            c, i = _S14_WRAP_RESET
            cycles += c
            instructions += i
        else:
            for a, b in head['stores'].items():
                for aa, bb in _bytes(a, b[0], b[1]):
                    order[aa] = bb
            c, i = _add(_S14_STORE_F1B0, _S14_EA1E_TEST, _S14_EA1E_BMI[True])
            cycles += c
            instructions += i
        settle_d7_register = 0 if head['reset'] else registers['d7']
        sc, si, sorder, exit_d7, exit_sr, last_pc, arm, cell = _state14_settle_cost(
            read, sr, head['settle_d7'], registers['a7'], None if head['reset'] else head['settle_d7'], settle_d7_register)
        cycles += sc
        instructions += si
        order.update(sorder)
        if arm == 'rejoin-main':
            # 006F4C's own bne.w lands exactly on 006DD4 (the ARMSEL test this dispatcher's own
            # top-level 'main' path also uses) -- FFFFEA20 is unchanged by anything settle did (only
            # F1A4/F1A6/F1AE/D7 are ever written there), so the live read below is exact, and the
            # caller's own D7 at this point is `head['settle_d7']` (settle's own EA20 test runs
            # before any bump/subq, per `game.player.state14_settle`'s own module note).
            c, i = _S14_ARMSEL_TEST
            cycles += c
            instructions += i
            ea20_one = read(player.EA20_WORD, 2) & 0xFFFF == 1
            c, i = _S14_ARMSEL_BNE[not ea20_one]
            cycles += c
            instructions += i
            # settle_d7_register (above) is exactly the "unchanged so far" D7 this rejoin needs too:
            # a fresh-reset entry's own moveq #0,d7 clears the FULL register, and a carried entry
            # never touches D7 before this rejoin at all (settle's own EA20 test runs before any
            # bump/subq), so its own outer entry value (upper half included) survives untouched.
            return _state14_main_dispatch(machine, read, registers, sr, order, exit_registers, cycles,
                                           instructions, ea20_one, head['settle_d7'], settle_d7_register)
        if cell is not None:
            exit_registers['a0'] = cell['address'] & 0xFFFFFFFF
            exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell['d0']
            exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell['d1']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = exit_sr
        if exit_d7 is not None:
            exit_registers['d7'] = exit_d7
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    # head['arm'] == 'main'
    c, i = _add(_S14_WRAP_BLT[True], _S14_STORE_F1B0, _S14_EA1E_TEST, _S14_EA1E_BMI[False], _S14_EA20_TEST0)
    cycles += c
    instructions += i
    for a, b in head['stores'].items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb
    cleared = (0xFFFFF1A4 & 0xFFFFFF) in head['stores']
    c, i = _S14_EA20_BNE0[not cleared]
    cycles += c
    instructions += i
    if cleared:
        c, i = _S14_CLEAR
        cycles += c
        instructions += i
    c, i = _S14_ARMSEL_TEST
    cycles += c
    instructions += i
    ea20_one = head['ea20_one']
    c, i = _S14_ARMSEL_BNE[not ea20_one]
    cycles += c
    instructions += i

    # Nothing before this dispatch touches D7 at all on the top-level 'main' path: the outer entry's
    # own register (upper half included) is the correct "unchanged" baseline.
    return _state14_main_dispatch(machine, read, registers, sr, order, exit_registers, cycles,
                                   instructions, ea20_one, d7, registers['d7'])


# --- 012DA0/012E5A: the movement-cluster contact consumers (game/pickups.py: contact_consume) ---
#
# Costed the same way as 008222: one instruction-block at a time (every instruction's own cost
# confirmed data-independent against the tracer, artifacts/gods/evidence/census-012DA0-entry,
# census-012E5A-entry).  Slot 3's own tail jump ends the whole activation with no bsr; slots 1/2
# return normally (the shared body's own `rts` lands back after the bsr).  The active-selector
# override (CONTACT_ACTIVE_SELECTOR naming this slot) is unwitnessed by every one of the 18
# retained fixtures across both routines -- declined, alongside any type outside
# ``pickups.TYPE_HEADERS`` (and 9, for 012DA0 only).
CONTACT_CONSUME_PRIMARY_ENTRY = 0x012DA0      # last_pc varies by which slot ends the activation
CONTACT_CONSUME_SECONDARY_ENTRY = 0x012E5A
_CC_SLOT_TEST_SKIP = (16 + 10, 2)                # tst.l slot; beq taken
_CC_SLOT_TEST_CONTINUE = (16 + 8, 2)             # tst.l slot; beq not taken
_CC_SLOT_HEAD = (16 + 12 + 8 + 12 + 4 + 12, 6)   # movea a3; move d4; lea a1; move d3; moveq d5; add d5
_CC_SELECTOR_TEST_WORD = (12, 1)                 # tst.w f154 (slot 1 only)
_CC_SELECTOR_TEST_CMPI = (16, 1)                 # cmpi.w #imm,f154 (slots 2/3)
_CC_SELECTOR_SKIP = (10, 1)                      # bne taken -- the only witnessed outcome (keep the default position)
_CC_BSR = (18, 1)                                # bsr.b into 012E32/012EE6 (slots 1/2 only)
_CC_LOOKUP = (16 + 8 + 4 + 4 + 8 + 18 + 16 + 8 + 4 + 4 + 18 + 8, 12)   # move#$35,fdf6 .. jmp (a0)
_CC_TAIL_RTS = (16, 1)                           # the clean rts (012E58/012F0C) when slot 3 is empty
_CC_TYPE1_HEADER = (8 + 8, 2)                    # addi d3,#$10; subi d5,#$c
_CC_TYPE7_HEADER = (4 + 10, 2)                   # subq d5,#4; bra taken
_CC_TYPE0_HEADER = (8, 1)                        # subi d5,#$c
_CC_TYPE2_HEADER = (8, 1)                        # addi d3,#$10 (baked into the body's own start)
_CC_TYPE6_HEADER = (8 + 4 + 10, 3)               # subi d3,#$18; subq d5,#4; bra taken
_CC_TYPE9_FULL = (8 + 16 + 16 + 16 + 16 + 8 + 8 + 8 + 8 + 8 + 12 + 16, 12)   # the whole standalone body
_CC_BODY_SOUND = (16, 1)                         # move.w #$35,fdf6.w
_CC_BODY_POOL_SETUP = (4 + 4 + 12 + 4 + 4 + 12 + 8, 7)   # subq d5,#6 .. adda d6,a5 (pooled bodies only)
_CC_BODY_COUNT = (12 + 12 + 4, 3)                # move $8(a1),d6; sub $6(a1),d6; addq d6,#1
_CC_BODY_GROUP = (8 + 8 + 8 + 12, 4)             # move d4,(a3)+; d3,(a3)+; d5,(a3)+; #const,(a3)+  (clr costs the same as move#imm)
_CC_BODY_POOL_WRITE = (12, 1)                    # move.w #$fffa,(a5)+  (pooled bodies only, once per group)
_CC_BODY_CLAIM = (16, 1)                         # move.w #imm,$e(a1)  (once, after group 0)
_CC_BODY_DEC_STOP = (4 + 10, 2)                  # subq d6,#1; beq taken (this group was the last one written)
_CC_BODY_DEC_CONTINUE = (4 + 8, 2)               # subq d6,#1; beq not taken
_CC_BODY_ADVANCE = (4, 1)                        # addq d4,#1  (before group 2/3)
_CC_BODY_RTS = (16, 1)
# Slot 0's and slot 1's own bsr return addresses, per routine (0 = 012DA0, 1 = 012E5A) -- the
# instruction right after each bsr.b, exactly as game.pickups.CONTACT_SLOTS orders the slots.
_CC_RETURN_ADDRESSES = {0: (0x012DD0, 0x012E02), 1: (0x012E88, 0x012EB8)}
_CC_GROUP2_CONST = {0: 2, 1: 5}   # the third, unrolled group's own constant, per routine


def _cc_body_cost(pooled, num_groups):
    cycles, instructions = _add(_CC_BODY_SOUND, _CC_BODY_POOL_SETUP if pooled else (0, 0), _CC_BODY_COUNT)
    for index in range(num_groups):
        c, i = _CC_BODY_GROUP
        cycles += c
        instructions += i
        if pooled:
            c, i = _CC_BODY_POOL_WRITE
            cycles += c
            instructions += i
        if index == 0:
            c, i = _CC_BODY_CLAIM
            cycles += c
            instructions += i
        if index < num_groups - 1:
            c, i = _add(_CC_BODY_DEC_CONTINUE, _CC_BODY_ADVANCE)
        elif index < 2:
            c, i = _CC_BODY_DEC_STOP
        else:
            c, i = (0, 0)
        cycles += c
        instructions += i
    c, i = _CC_BODY_RTS
    return cycles + c, instructions + i


_TYPE_HEADER_COST = {(0, 1): _CC_TYPE1_HEADER, (0, 7): _CC_TYPE7_HEADER, (0, 3): (0, 0),
                     (1, 0): _CC_TYPE0_HEADER, (1, 2): _CC_TYPE2_HEADER, (1, 6): _CC_TYPE6_HEADER}


def _cc_slot_cost(routine, slot_index, result, is_bsr):
    """One slot's own cost, from its own tst.l test through whichever tail (skip / rts-after-bsr /
    the handler's own rts) it reaches.  ``is_bsr`` is true for slots 0/1 (the caller-side bsr and
    the selector test are part of THIS slot's own cost); slot 2 has neither -- the selector test
    still runs, but the call is a tail jmp already inside ``_CC_LOOKUP``, and no bsr precedes it."""
    cycles, instructions = 0, 0
    if result['arm'] == 'empty':
        c, i = _CC_SLOT_TEST_SKIP
        return c, i
    c, i = _CC_SLOT_TEST_CONTINUE
    cycles += c
    instructions += i
    c, i = _CC_SLOT_HEAD
    cycles += c
    instructions += i
    c, i = _CC_SELECTOR_TEST_WORD if slot_index == 0 else _CC_SELECTOR_TEST_CMPI
    cycles += c
    instructions += i
    c, i = _CC_SELECTOR_SKIP
    cycles += c
    instructions += i
    if is_bsr:
        c, i = _CC_BSR
        cycles += c
        instructions += i
    c, i = _CC_LOOKUP
    cycles += c
    instructions += i
    type_value = result['type']
    if routine == 0 and type_value == 9:
        c, i = _CC_TYPE9_FULL
        cycles += c
        instructions += i
        return cycles, instructions
    c, i = _TYPE_HEADER_COST[(routine, type_value)]
    cycles += c
    instructions += i
    c, i = _cc_body_cost(result['pooled'], len(result['groups']))
    cycles += c
    instructions += i
    return cycles, instructions


def _cc_resolve(machine, read, registers, routine, entry_sp):
    """Everything 012DA0/012E5A do once entered, relative to their OWN entry a7 (``entry_sp``) --
    shared by the standalone gate (``entry_sp = registers['a7']``) and a composing caller's own JSR
    (``entry_sp = registers['a7'] - 4``, the JSR's own push already accounted for by the caller).
    Returns (cycles, instructions, order, exit_registers) where ``exit_registers`` carries every
    register THIS routine's own code touches except a7/pc (the caller's own concern -- a plain rts
    for the standalone gate, nothing at all for a composing caller's own JSR/rts pair, which is net
    neutral on a7 and leaves pc for the caller's own next instruction).  Raises UnsupportedCandidate
    exactly as the standalone planners already did.
    """
    from .game import pickups
    # The active-selector override is unwitnessed on every retained fixture of either routine; a
    # slot whose own index matches it must decline before any of its own cost or stores are trusted.
    for slot_index, slot_addr in enumerate(pickups.CONTACT_SLOTS):
        if read(slot_addr, 4) != 0 and read(pickups.CONTACT_ACTIVE_SELECTOR, 2) == slot_index:
            raise UnsupportedCandidate(f'contact consume slot {slot_index} active-selector override not witnessed by a recording')
    result = pickups.contact_consume(read, routine)
    slots = result['slots']
    last_slot = slots[-1]
    if last_slot['arm'] == 'unrecovered':
        raise UnsupportedCandidate(f"contact consume type {last_slot['type']} not witnessed by a recording")

    order = {}
    cycles = instructions = 0
    exit_a1 = exit_a0 = exit_d0 = exit_a5 = None
    exit_d3 = exit_d4 = exit_d5 = exit_d6 = None
    exit_a3 = registers['a3'] & 0xFFFFFFFF
    for slot_index, slot_result in enumerate(slots):
        is_bsr = slot_index < 2
        c, i = _cc_slot_cost(routine, slot_index, slot_result, is_bsr)
        cycles += c
        instructions += i
        for address, (value, size) in slot_result['stores'].items():
            for a, b in _bytes(address, value, size):
                order[a] = b
        if slot_result['arm'] != 'found':
            continue
        record = slot_result['record']
        type_value = slot_result['type']
        exit_a1 = record & 0xFFFFFFFF
        # "move.l $14(a1),d0" (012DA0) / "$10(a1),d0" (012E5A) is a LONGWORD read of the type
        # field into d0 -- it clears d0's own upper half on every found slot (every witnessed
        # type value's own record field has a zero upper half too), unlike every register whose
        # own upper half survives untouched here (d3/d4/d6, word ops throughout).
        exit_d0 = (type_value * 4) & 0xFFFF
        num_groups = 1 if type_value == 9 else len(slot_result['groups'])
        exit_a3 = (slot_result['entry'] + 8 * num_groups) & 0xFFFFFFFF
        exit_d3, exit_d4, exit_d5 = slot_result['d3'], slot_result['d4'], slot_result['d5']
        if routine == 0 and type_value == 9:
            exit_a0 = 0x013194
            # type 9 never touches d6 -- leave `exit_d6` exactly as an EARLIER found slot left it
            # (still `None`, the caller's own entry value, if this is the only found slot so far;
            # a real defect, caught on state 5's own fixtures, once reset this to `None`
            # unconditionally and discarded an earlier slot's own real d6 whenever a later slot's own
            # type happened to be 9 -- witnessed when slot 0 is found (its own `_append_groups` sets
            # d6) and slot 1 is ALSO found as type 9).
        else:
            exit_a0 = int.from_bytes(machine.peek_rom((0x012C3E + 4 * type_value) & 0xFFFFFF, 4), 'big')
            exit_d6 = slot_result.get('d6')
            if slot_result['pooled']:
                # a5 is computed once (lea + adda) from the FIRST group's own d4, then merely
                # post-incremented by 2 per pool write; the last group's own pool_addr + 2 is
                # exactly that running value (pickups._append_groups already derives it per group).
                exit_a5 = 0xFFFF0000 | ((slot_result['groups'][-1]['pool_addr'] + 2) & 0xFFFF)

    if last_slot['arm'] == 'empty':
        # Slot 3 empty after an earlier slot's own bsr already returned: 012E58/012F0C's own bare
        # rts is one more instruction no per-slot cost above accounts for.
        c, i = _CC_TAIL_RTS
        cycles += c
        instructions += i
    # Slots 0/1's own bsr pushes a return address at (entry_sp - 4); the callee's own rts pops it
    # straight back before the caller continues, so only the LAST bsr actually made (slot 1's own,
    # if it ran at all; otherwise slot 0's) leaves residue there -- neither ran at all if both are
    # empty, and slot 2's own tail jump never pushes anything.
    if slots[1]['arm'] == 'found':
        last_return = _CC_RETURN_ADDRESSES[routine][1]
    elif slots[0]['arm'] == 'found':
        last_return = _CC_RETURN_ADDRESSES[routine][0]
    else:
        last_return = None
    if last_return is not None:
        for a, b in _bytes((entry_sp - 4) & 0xFFFFFF, last_return, 4):
            order[a] = b

    exit_registers = {'a3': exit_a3}
    if exit_a1 is not None:
        exit_registers['a1'] = exit_a1
    if exit_a0 is not None:
        exit_registers['a0'] = exit_a0
    if exit_d0 is not None:
        exit_registers['d0'] = exit_d0
    if exit_d3 is not None:
        exit_registers['d3'] = (registers['d3'] & 0xFFFF0000) | exit_d3
    if exit_d4 is not None:
        exit_registers['d4'] = (registers['d4'] & 0xFFFF0000) | exit_d4
    if exit_d5 is not None:
        # moveq #$18,d5 (part of every found slot's own head) clears the WHOLE register first;
        # nothing after it ever restores a nonzero upper half (word ops only), unlike d0/d3/d4/d6.
        exit_registers['d5'] = exit_d5
    if exit_d6 is not None:
        exit_registers['d6'] = (registers['d6'] & 0xFFFF0000) | exit_d6
    if exit_a5 is not None:
        exit_registers['a5'] = exit_a5
    return cycles, instructions, order, exit_registers, last_slot


def _contact_consume_plan(machine, registers, routine, entry_pc):
    from .game import pickups
    if registers['pc'] != entry_pc:
        raise UnsupportedCandidate('contact consume planner needs the machine parked at its own entry')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    cycles, instructions, order, exit_registers, last_slot = _cc_resolve(machine, read, registers, routine, sp32)
    exit_registers['a7'] = (sp32 + 4) & 0xFFFFFFFF
    exit_registers['pc'] = _return(machine, sp32 & 0xFFFFFF)

    # The last flag-setting instruction is a MOVE-class one on every path (SUBQ only when a body
    # stops before its own third, unrolled group -- MOVE/CLR set N/Z from the value, V=C=0; SUBQ's
    # own N/Z come from the decremented result, itself always exactly 0 when it is the reason the
    # body stopped there): the 'all empty' path's last tst.l; a body that wrote all three groups
    # (no decrement follows its own third one at all) ends on that group's own last store -- the
    # pool sentinel 0xFFFA for a pooled body, the third group's own constant otherwise; any body
    # that stopped at one or two groups ends on the SUBQ that found d6 exactly 0.  X is untouched
    # by MOVE/CLR/SUBQ alike here (SUBQ's own X does update, but nothing after it reads X on any
    # witnessed path), so X simply survives from entry.
    if last_slot['arm'] == 'empty':
        empty_addr = pickups.CONTACT_SLOTS[2]   # contact_consume always processes all three slots
        last_value = read(empty_addr, 4) & 0xFFFFFFFF
        width = 4
    elif routine == 0 and last_slot['type'] == 9:
        last_value, width = 0x2F, 2
    else:
        num_groups = len(last_slot['groups'])
        if num_groups < 3:
            last_value = 0
        elif last_slot['pooled']:
            last_value = 0xFFFA
        else:
            last_value = _CC_GROUP2_CONST[routine]
        width = 2
    exit_sr = (_logic_sr(sr, last_value, width) & ~0x10) | (sr & 0x10)
    exit_registers['sr'] = exit_sr

    if last_slot['arm'] == 'empty':
        last_pc = 0x012E58 if routine == 0 else 0x012F0C
    else:
        last_pc = _CC_TYPE_LAST_PC[(routine, last_slot['type'])]
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=last_pc)


# The handler's own rts, per (routine, witnessed type) -- the activation's own last instruction on
# every non-empty tail (0131D2/012F0E share 013210/012F6C's own rts respectively; 013222/012F6E
# likewise 013262/012FD2; type 9 is the only one with its own, 0131C0).
_CC_TYPE_LAST_PC = {(0, 1): 0x013210, (0, 7): 0x013210, (0, 3): 0x012F6C, (0, 9): 0x0131C0,
                    (1, 0): 0x013262, (1, 2): 0x012FD2, (1, 6): 0x013262}


def contact_consume_primary_plan(machine, registers):
    """012DA0: the movement-cluster contact consumer over ITEM_TYPE_PRIMARY (types 1, 3, 7, 9)."""
    return _contact_consume_plan(machine, registers, 0, CONTACT_CONSUME_PRIMARY_ENTRY)


def contact_consume_secondary_plan(machine, registers):
    """012E5A: the movement-cluster contact consumer over ITEM_TYPE_SECONDARY (types 0, 2)."""
    return _contact_consume_plan(machine, registers, 1, CONTACT_CONSUME_SECONDARY_ENTRY)


# --- 006AD8 (state 24) / 006B14 (state 25): game.player.movement_hit_state -----------------------
#
# A leaf composing an internal JSR into the already-recovered contact-consume family (`_cc_resolve`,
# the shape `0049DA` calling `001164` already proved) plus its own small 3-tick head/tail; cost from
# the tracer (artifacts/gods/evidence/census-006AD8-entry), one instruction-block at a time exactly
# like its own callee.
STATE24_ENTRY, STATE24_CMPI_PC = 0x006AD8, 0x006AEC
STATE25_ENTRY, STATE25_CMPI_PC = 0x006B14, 0x006B28
_MH_HEAD = (16 + 4 + 8, 3)              # move.w #imm,CONTACT_DIRECTION; addq.w #1,d7; cmpi.w #1,d7
_MH_BNE_NOTTAKEN = (8, 1)               # counter == 1: falls into the jsr
_MH_BNE_TAKEN = (10, 1)                 # counter != 1: skips the call
_MH_JSR = (20, 1)                       # jsr 12da0.l / 12e5a.l (counter == 1 only)
_MH_CMPI3 = (8, 1)                      # cmpi.w #3,d7
_MH_BLT_TAKEN = (10, 1)                 # counter < 3: 'call'/'wait'
_MH_BLT_NOTTAKEN = (12, 1)              # counter >= 3: 'transition'
_MH_TRANSITION_HEAD = {0: (20 + 4, 2), 1: (16 + 4, 2)}   # move.w #$e,STATE_INDEX (ABS.L for 24, ABS.W for 25); moveq
_MH_BTST = (16, 1)
_MH_BTST_NOTTAKEN = (8, 1)              # bit clear: the override read follows
_MH_BTST_TAKEN = (10, 1)                # bit set: no override read
_MH_OVERRIDE_READ = (12, 1)             # move.w CONTACT_OVERRIDE_COUNTER,d7
_MH_TAIL = (20 + 10, 2)                 # move.w CONTACT_OVERRIDE_Y,grid.GRID_Y; bra.w 0075D6
_MH_TRANSITION_LAST_PC = {0: 0x006B10, 1: 0x006B4A}   # the transition arm's own bra.w, per routine


def _movement_hit_plan(machine, registers, routine, entry_pc, cmpi_pc):
    from .game import player
    if registers['pc'] != entry_pc:
        raise UnsupportedCandidate('movement hit state planner needs the machine parked at its own entry')
    sr = registers['sr']
    read = _reader(machine)
    state_counter = registers['d7'] & 0xFFFF
    result = player.movement_hit_state(read, routine, state_counter)
    order = {}
    for address, (value, size) in result['stores'].items():
        for a, b in _bytes(address, value, size):
            order[a] = b

    cycles, instructions = _add(_MH_HEAD, _MH_BNE_NOTTAKEN if result['calls_consumer'] else _MH_BNE_TAKEN)
    exit_registers = {}
    if result['calls_consumer']:
        c, i = _MH_JSR
        cycles += c
        instructions += i
        sp32 = registers['a7']
        # The jsr itself pushes ITS OWN return address (cmpi_pc, the instruction right after it) at
        # (entry a7 - 4) -- one level up from 012DA0/012E5A's own internal bsr residue, which
        # _cc_resolve already places relative to ITS OWN entry a7 (sp32 - 4 here).
        for a, b in _bytes((sp32 - 4) & 0xFFFFFF, cmpi_pc, 4):
            order[a] = b
        cc_cycles, cc_instructions, cc_order, cc_registers, _ = _cc_resolve(machine, read, registers, routine, sp32 - 4)
        cycles += cc_cycles
        instructions += cc_instructions
        order.update(cc_order)
        exit_registers.update(cc_registers)
    c, i = _MH_CMPI3
    cycles += c
    instructions += i

    if result['arm'] != 'transition':
        c, i = _MH_BLT_TAKEN
        cycles += c
        instructions += i
        # cmpi.w #3,d7 is the last flag-setter: a plain CMP of the counter (post-increment, pre-any
        # call -- the call's own internal flags are overwritten here regardless).
        exit_sr = (_cmp_sr(sr, result['counter'], 3, 2) & ~0x10) | (sr & 0x10)
        last_pc = cmpi_pc + 4   # the blt.w itself
    else:
        c, i = _add(_MH_BLT_NOTTAKEN, _MH_TRANSITION_HEAD[routine], _MH_BTST)
        cycles += c
        instructions += i
        c, i = _MH_BTST_NOTTAKEN if not result['override_flag'] else _MH_BTST_TAKEN
        cycles += c
        instructions += i
        if not result['override_flag']:
            c, i = _MH_OVERRIDE_READ
            cycles += c
            instructions += i
        c, i = _MH_TAIL
        cycles += c
        instructions += i
        # The routine's own last instruction, "move.w CONTACT_OVERRIDE_Y,GRID_Y", is the last
        # flag-setter on both transition sub-arms (a plain MOVE; X untouched, as by every
        # instruction after the head's own addq.w #1,d7 -- confirmed empirically, below).
        from .game import player as _player
        y_value = read(_player.CONTACT_OVERRIDE_Y, 2)
        exit_sr = (_logic_sr(sr, y_value, 2) & ~0x10) | (sr & 0x10)
        last_pc = _MH_TRANSITION_LAST_PC[routine]   # the bra.w itself

    exit_registers['d7'] = result['counter'] if result['arm'] == 'transition' else \
        (registers['d7'] & 0xFFFF0000) | result['counter']
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = exit_sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=last_pc)


def movement_hit_primary_plan(machine, registers):
    """006AD8 (state 24): the contact-consume-primary family's own caller."""
    return _movement_hit_plan(machine, registers, 0, STATE24_ENTRY, STATE24_CMPI_PC)


def movement_hit_secondary_plan(machine, registers):
    """006B14 (state 25): the contact-consume-secondary family's own caller."""
    return _movement_hit_plan(machine, registers, 1, STATE25_ENTRY, STATE25_CMPI_PC)


# --- 00722C: the 200-entry box-overlap scan (game.movement.box_overlap_scan) ---------------------
#
# Costed one instruction-block at a time exactly like every other census-driven leaf here; every
# instruction's own cost confirmed data-independent against the tracer
# (artifacts/gods/evidence/census-00722C-entry).  The result is discarded at both witnessed call
# sites, so this candidate has no mutant the game can see yet (game.movement's own module
# docstring) -- not armed in `camera-sprites` for that reason, recovered on its own merits.
BOX_SCAN_ENTRY, BOX_SCAN_FOUND_LAST_PC, BOX_SCAN_EXHAUSTED_LAST_PC = 0x00722C, 0x007280, 0x00727A
_BS_HEAD_FIXED = (12 + 4 + 4 + 12 + 12 + 8, 6)      # lea; moveq #$10,d0; moveq #$28,d1; add.w x2; move.w #$c7,d6
_BS_TEST_A = (12, 1)                                 # tst.w $4(a0)
_BS_SKIP_NEGATIVE_TAIL = (10, 1)                     # bmi.b taken
_BS_TEST_A_CONTINUE = (8, 1)                         # bmi.b not taken
_BS_TEST_B = (12, 1)                                 # tst.w $6(a0)
_BS_SKIP_ZERO_TAIL = (10, 1)                         # beq.b taken
_BS_TEST_B_CONTINUE = (8, 1)                         # beq.b not taken
_BS_BOX_HEAD = (8 + 12 + 4 + 4 + 4 + 4 + 4 + 8, 8)   # move.w (a0),d2 .. subi.w #$c,d3
_BS_CMP = (4, 1)
_BS_COND_FAIL = (10, 1)                              # blt/bgt taken (the box test's own failing branch)
_BS_COND_PASS = (8, 1)                                # not taken (continue the chain)
_BS_FOUND_TAKEN = (10, 1)                             # ble.b taken (the fourth comparison's own match)
_BS_FOUND_NOTTAKEN = (8, 1)                           # ble.b not taken (the fourth comparison's own fail)
_BS_ADVANCE_CONTINUE = (4 + 10, 2)                   # addq.w #8,a0; dbra taken
_BS_ADVANCE_EXHAUSTED = (4 + 14, 2)                  # addq.w #8,a0; dbra not taken (the 200th entry)
_BS_FOUND_EXIT = (12 + 20, 2)                        # move.w #imm,-(a7); rtr
_BS_NOTFOUND_EXIT = (14 + 20, 2)                     # clr.w -(a7); rtr


def _bs_entry_cost(step, is_last):
    """One entry's own cost, from its own tst.w $4(a0) through whichever tail (skip / box-test
    fail / found, with the advance-and-loop suffix only when the scan continues) it reaches."""
    cycles, instructions = _BS_TEST_A
    if step['arm'] == 'skip-negative':
        c, i = _BS_SKIP_NEGATIVE_TAIL
        cycles += c
        instructions += i
        c, i = _BS_ADVANCE_EXHAUSTED if is_last else _BS_ADVANCE_CONTINUE
        return cycles + c, instructions + i
    c, i = _BS_TEST_A_CONTINUE
    cycles += c
    instructions += i
    c, i = _BS_TEST_B
    cycles += c
    instructions += i
    if step['arm'] == 'skip-zero':
        c, i = _BS_SKIP_ZERO_TAIL
        cycles += c
        instructions += i
        c, i = _BS_ADVANCE_EXHAUSTED if is_last else _BS_ADVANCE_CONTINUE
        return cycles + c, instructions + i
    c, i = _BS_TEST_B_CONTINUE
    cycles += c
    instructions += i
    c, i = _BS_BOX_HEAD
    cycles += c
    instructions += i
    # The four chained comparisons: each PASS costs CMP+COND_PASS and continues to the next; the
    # first FAIL costs CMP+COND_FAIL and ends this entry; the fourth (pass_y_far) is 'ble', whose
    # own TAKEN outcome is the match (ends the whole scan, no advance/loop suffix at all).
    for passed, is_fourth in ((step['pass_x_near'], False), (step['pass_x_far'], False),
                              (step['pass_y_near'], False), (step['arm'] == 'found', True)):
        c, i = _BS_CMP
        cycles += c
        instructions += i
        if is_fourth:
            c, i = _BS_FOUND_TAKEN if passed else _BS_FOUND_NOTTAKEN
            cycles += c
            instructions += i
            if passed:
                return cycles, instructions   # found: no advance/loop suffix
            break
        if not passed:
            c, i = _BS_COND_FAIL
            cycles += c
            instructions += i
            break
        c, i = _BS_COND_PASS
        cycles += c
        instructions += i
    c, i = _BS_ADVANCE_EXHAUSTED if is_last else _BS_ADVANCE_CONTINUE
    return cycles + c, instructions + i


def box_overlap_scan_plan(machine, registers):
    """00722C: the box-overlap scan, admitted for every entry pattern (no arm declines -- every
    instruction the routine can execute is modelled; nothing here is unwitnessed by name)."""
    from .game import movement
    if registers['pc'] != BOX_SCAN_ENTRY:
        raise UnsupportedCandidate('box overlap scan planner needs the machine parked at 00722C')
    sr = registers['sr']
    read = _reader(machine)
    result = movement.box_overlap_scan(read)
    entries = result['entries']

    cycles, instructions = _BS_HEAD_FIXED
    for index, step in enumerate(entries):
        c, i = _bs_entry_cost(step, index == movement.BOX_SCAN_COUNT - 1)
        cycles += c
        instructions += i
    c, i = _BS_FOUND_EXIT if result['arm'] == 'found' else _BS_NOTFOUND_EXIT
    cycles += c
    instructions += i

    sp32 = registers['a7']
    # moveq #$10,d0 / moveq #$28,d1 (the fixed head, always run) clear the WHOLE register; moveq
    # #$14,d4 / moveq #$10,d5 (only when some entry reaches the box test) do too -- unlike d2/d3
    # (plain .w moves throughout) and d6 (a MOVE.W of the loop count, then DBcc, neither of which
    # ever touches its own upper half: preserved from entry the whole time).
    exit_registers = {'d0': result['player_x'], 'd1': result['player_y'],
                      'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp32 & 0xFFFFFF)}
    last_tested = next((e for e in reversed(entries) if e['arm'] in ('tested', 'found')), None)
    if last_tested is not None:
        exit_registers['d2'] = (registers['d2'] & 0xFFFF0000) | ((last_tested['x'] - 4) & 0xFFFF)
        exit_registers['d3'] = (registers['d3'] & 0xFFFF0000) | ((last_tested['y'] - 0xC) & 0xFFFF)
        exit_registers['d4'] = last_tested['far_x']
        exit_registers['d5'] = last_tested['far_y']
    dbra_count = len(entries) - (1 if result['arm'] == 'found' else 0)
    exit_registers['d6'] = (registers['d6'] & 0xFFFF0000) | ((0xC7 - dbra_count) & 0xFFFF)
    if result['arm'] == 'found':
        found = result['found']
        exit_registers['a0'] = found['entry'] & 0xFFFFFFFF
        # move.w #imm,-(a7); rtr: RTR pops the pushed word AS the exit CCR outright (the whole
        # point of the trick), so it sets X too, not just NZVC -- 0x0008 gives X=0,N=1,Z=V=C=0.
        exit_sr = (sr & ~0x1F) | 0x08
        last_pc = BOX_SCAN_FOUND_LAST_PC
        pushed = 8
    else:
        exit_registers['a0'] = result['end_entry'] & 0xFFFFFFFF
        exit_sr = sr & ~0x1F
        last_pc = BOX_SCAN_EXHAUSTED_LAST_PC
        pushed = 0
    exit_registers['sr'] = exit_sr
    # "move.w #imm,-(a7)" / "clr.w -(a7)" pushes the word RTR immediately pops back off again --
    # transient, but a real write at (entry a7 - 2) all the same (the same "a routine that saves
    # registers writes its whole frame" rule this project already follows elsewhere).
    writes = tuple(_bytes((sp32 - 2) & 0xFFFFFF, pushed, 2))
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes,
                      registers=exit_registers, last_pc=last_pc)




# --- 005886/005834: states 19 and 18 -- see game.player's own module note above
# state1918_scan_consume / state1918_dispatch / state19_head / state18_head / achievements.
# achievement_highlight_cycle / spawns.floating_icon_spawn.  "One region, two gates": states 19 and
# 18 share the WHOLE body from 0058D2 onward physically (the scan, the post-scan dispatch at 005C14,
# the pending/idle tails, the achievement highlight cycle at 005CEE); only each state's own outer
# head (0058A2-0058D2 for 19, 005852-005878 for 18: NOT byte-identical, but the same shape) and the
# budget-reset transition target are separate ROM copies with their own cost constants.  Costed one
# instruction-block at a time from the tracer on every retained fixture across states 19
# (census-005886-*, five recordings, 190 fixtures) and 18 (census-005834-*, five recordings, 118
# fixtures).  The scan (0058D2-005954) is a second, separately-compiled copy of
# game.movement.box_overlap_scan's own algorithm (00722C) -- its own per-entry costs (_BS_*,
# _bs_entry_cost, above) are reused verbatim, confirmed instruction-for-instruction identical; only
# the head (a different opening sequence for the same margin arithmetic) and the found/not-found
# tails (continuing into this region's own dispatch instead of 00722C's own "move #imm,-(a7);rtr"
# trick) are this region's own.  Both the 005C36 consume-and-highlight call and the 005CEE-owned
# achievement highlight cycle reach 001648 (the SAME icon-upload device operation
# achievement_slot_reset_plan already seams) with D2 sometimes POSITIVE here (005C36's own call: the
# found entry's own kind, e.g. 0x12) -- 001648's own real-descriptor upload arm, never witnessed by
# achievement_slot_reset's own always-D2=-1 caller, but the seam does not need to know which arm the
# ceded operation takes.
STATE19_ENTRY, STATE18_ENTRY = 0x005886, 0x005834
STATE1918_ICON_UPLOAD = 0x001648        # the SAME seam target achievement_slot_reset_plan already uses
STATE1918_CYCLE_SOUND_VALUE = 0x4B

_S1918_SCAN_HEAD = (16 + 4 + 4 + 12 + 12 + 12 + 8, 7)     # 0058D2-0058EA: move#1,f238; moveq x2; add x2; lea; move#$c7,d6
_S1918_FOUND_TAIL_HEAD = (12 + 24 + 8, 3)                 # 00592E-005938: lea 14b42,a2; movem.w (a0),d0-d2; cmpi #$c0,d2
_S1918_FOUND_RANGE_BGE_NOT = (12, 1)                      # 00593C bge.w -- not taken (kind < 0xc0, the only witnessed case)
_S1918_FOUND_KIND_TEST = (18, 1)                          # 005940 cmpi.b #2,(a2,d2.w)
_S1918_FOUND_KIND_BNE_NOT = (8, 1)                        # 005946 bne.b -- not taken (kind == 2, the only witnessed case)
_S1918_FOUND_SAVE_A2 = (4, 1)                             # 005948 movea.l a0,a2
_S1918_FOUND_DISABLE = (16 + 16, 2)                       # 00594A-005950: move.w #$ffff,4(a0); clr.w 6(a0)
_S1918_FOUND_BRA_5C14 = (10, 1)                           # 005954 bra.w $5c14
_S1918_NOTFOUND_SET_EMPTY = (16, 1)                       # 005924 move.w #1,f23a.w
_S1918_NOTFOUND_BRA = (10, 1)                             # 00592A bra.w 75d6

_S1918_5C14_BIT1_TEST = (16, 1)                           # 005C14 btst #1,ea23.w
_S1918_5C14_BIT1_BNE = {True: (10, 1), False: (8, 1)}     # 005C1A bne.b -- taken: consume directly
_S1918_5C14_BIT2_TEST = (16, 1)                           # 005C1C btst #2,ea23.w
_S1918_5C14_BIT2_BNE = {True: (10, 1), False: (8, 1)}     # 005C22 bne.b
_S1918_REARM_CLEAR_ACTIVE = (16, 1)                       # 005C24 clr.w f238.w
_S1918_REARM_STORE_KIND = (12, 1)                         # 005C28 move.w d2,4(a2)
_S1918_REARM_STORE_ONE = (16, 1)                          # 005C2C move.w #1,6(a2)
_S1918_REARM_BRA = (10, 1)                                # 005C32 bra.w 75d6
_S1918_CONSUME_HEAD = (16 + 8 + 12 + 4 + 4 + 14, 6)       # 005C36-005C48: move#1,f2e0; lea; move f236,d5; move d5,d0; add d5,d5; move d2,(a3,d5)
_S1918_CONSUME_MOVEQ_D1 = (4, 1)                          # 005C4C moveq #1,d1
_S1918_CONSUME_JSR = (20, 1)                              # 005C4E jsr 1648 -- the prefix's own last instruction
_S1918_CONSUME_TAIL_BRA = (10, 1)                         # 005C54 bra.w 75d6 -- the suffix, after 1648 returns

_S1918_DISPATCH_MOVEQ = (4, 1)                            # moveq #1,d7 -- 0058A2 (state19) / 005852 (state18)
_S1918_5C58_SET_PENDING = (16, 1)                         # 005C58 move.w #1,f2e0.w
_S1918_5C5E_CLEAR_EMPTY = (16, 1)                         # 005C5E clr.w f23a.w
_S1918_5C62_TST_PENDING = (12, 1)                         # 005C62 tst.w f2e0.w
_S1918_5C66_BEQ_IDLE = {True: (10, 1), False: (8, 1)}     # 005C66 beq.b -- taken: PENDING clear (idle tail)
_S1918_PEND_BIT1_TEST = (16, 1)                           # 005C68 btst #1,ea23.w
_S1918_PEND_BIT1_BNE_NOT = (12, 1)                        # 005C6E bne.w -- not taken (bit 1 clear, the only witnessed case)
_S1918_PEND_BIT2_TEST = (16, 1)                           # 005C72 btst #2,ea23.w
_S1918_PEND_BIT2_BNE = {True: (10, 1), False: (12, 1)}    # 005C78 bne.w
_S1918_PEND_CLEAR = (16, 1)                               # 005C7C clr.w f2e0.w
_S1918_PEND_BRA = (10, 1)                                 # 005C80 bra.w 75d6
_S1918_IDLE_BIT1_TEST = (16, 1)                           # 005C84 btst #1,ea23.w
_S1918_IDLE_BIT1_BNE_NOT = (8, 1)                         # 005C8A bne.b -- not taken (bit 1 clear, the only witnessed case)
_S1918_IDLE_BIT2_TEST = (16, 1)                           # 005C8C btst #2,ea23.w
_S1918_IDLE_BIT2_BNE = {True: (10, 1), False: (8, 1)}     # 005C92 bne.b
_S1918_IDLE_EXIT_BRA = (10, 1)                            # 005C94 bra.w 75d6

_S1918_CYCLE_SOUND = (16, 1)                              # 005C98 move.w #$4b,fdf6.w
_S1918_CYCLE_HEAD1 = (12 + 4 + 4 + 8 + 14, 5)             # 005C9E-005CAA: move f236,d5; move d5,d0; add d5,d5; lea; move (a3,d5),d2
_S1918_CYCLE_MOVEQ_D1_0 = (4, 1)                          # 005CAE moveq #0,d1
_S1918_CYCLE_JSR1 = (20, 1)                               # 005CB0 jsr 1648 (clear the OLD highlighted icon)
_S1918_CYCLE_CLEAR_PENDING = (16, 1)                      # 005CE0 clr.w f16e.w
_S1918_CYCLE_LOAD_BUFFER = (16, 1)                        # 005CE4 movea.l f166.w,a3
_S1918_CYCLE_CLEAR_BUFFER = (12, 1)                       # 005CE8 clr.w (a3)
_S1918_CYCLE_BRA = (10, 1)                                # 005CEA bra.w 75d6

_S1918_HIGHLIGHT_PUSH = (12, 1)                           # 005CEE move.l d7,-(a7)
_S1918_HIGHLIGHT_HEAD = (8 + 12 + 4 + 14, 4)              # 005CF0-005CFA: lea; move f236,d4; add d4,d4; move (a3,d4),d2
_S1918_HIGHLIGHT_BMI_EMPTY = {True: (10, 1), False: (8, 1)}   # 005CFE bmi.b -- taken: slot already empty ('refresh')
_S1918_HIGHLIGHT_ADDI = (8, 1)                            # 005D00 addi.w #$b,d2
_S1918_HIGHLIGHT_BMI2_NOT = (8, 1)                        # 005D04 bmi.b -- not taken (the only witnessed case)
_S1918_HIGHLIGHT_SPAWN_SETUP = (12 + 12 + 4 + 8 + 18, 5)  # 005D06-005D14: move f18c,d0; move f18e,d1; addq#8,d0; addi#$20,d1; move#$ffff,(a3,d4)
_S1918_HIGHLIGHT_JSR_SPAWN = (20, 1)                      # 005D1A jsr 10d7c
# 010D7C's own body (game.spawns.floating_icon_spawn's own 'spawn' arm, the only one witnessed):
_S1918_SPAWN_CMPI = (8, 1)                                # 010D7C cmpi.w #$3d,d2
_S1918_SPAWN_BEQ_NOT = (8, 1)                             # 010D80 beq.b -- not taken (kind != 0x3d, the only witnessed case)
_S1918_SPAWN_TST_BUSY = (12, 1)                           # 010D82 tst.w f1f6.w
_S1918_SPAWN_BPL_NOT = (12, 1)                            # 010D86 bpl.w -- not taken (idle, the only witnessed case)
_S1918_SPAWN_STORE = (12 + 12 + 16 + 12, 4)               # 010D8A-010D98: move d0,f1f0; move d1,f1f2; move#$fffd,f1f4; move d2,f1f6
_S1918_SPAWN_RTS = (16, 1)                                # 010D9C rts
_S1918_HIGHLIGHT_REFRESH_HEAD = (12 + 4 + 4, 3)           # 005D20-005D26: move f236,d0; moveq#1,d1; moveq#$ff,d2
_S1918_HIGHLIGHT_REFRESH_JSR = (20, 1)                    # 005D28 jsr 1648
_S1918_HIGHLIGHT_RESTORE_D7 = (12, 1)                     # 005D2E move.l (a7)+,d7
_S1918_HIGHLIGHT_RTS = (16, 1)                            # 005D30 rts

_S19_HEAD_CMPI = (16, 1)                                  # 005886 cmpi.w #1,ea1e.w
_S19_HEAD_BEQ = {True: (10, 1), False: (8, 1)}            # 00588C beq.b $58a2
_S19_BUDGET_BSR = (18, 1)                                 # 00588E bsr.w $5cee
_S19_BUDGET_SUBQ = (4, 1)                                 # 005892 subq.w #1,d7
_S19_BUDGET_BPL = {True: (10, 1), False: (12, 1)}         # 005894 bpl.w -- taken: budget still open
_S19_BUDGET_RESET_MOVEQ = (4, 1)                          # 005898 moveq #2,d7
_S19_BUDGET_RESET_STORE = (16, 1)                         # 00589A clr.w f192.w
_S19_BUDGET_RESET_BRA = (10, 1)                           # 00589E bra.w 75d6
_S19_DISPATCH_TST_ACTIVE = (12, 1)                        # 0058A4 tst.w f238.w
_S19_DISPATCH_BEQ_SCAN = {True: (10, 1), False: (8, 1)}   # 0058A8 beq.b $58d2
_S19_DISPATCH_TST_EMPTY = (12, 1)                         # 0058AA tst.w f23a.w
_S19_DISPATCH_BEQ_DIRECT = {True: (10, 1), False: (12, 1)}  # 0058AE beq.w $5c5e -- word branch
_S19_DISPATCH_BIT1_TEST = (16, 1)                         # 0058B2 btst #1,ea23.w
_S19_DISPATCH_BIT1_BNE_NOT = (12, 1)                      # 0058B8 bne.w -- not taken (the only witnessed case)
_S19_DISPATCH_BIT2_TEST = (16, 1)                         # 0058BC btst #2,ea23.w
_S19_DISPATCH_BIT2_BNE = {True: (10, 1), False: (12, 1)}  # 0058C2 bne.w
_S19_DISPATCH_BSR_HIGHLIGHT = (18, 1)                     # 0058C6 bsr.w $5cee
_S19_DISPATCH_TST_ACTIVE2 = (12, 1)                       # 0058CA tst.w f238.w
_S19_DISPATCH_BNE_EXIT = (10, 1)                          # 0058CE bne.w 75d6 -- always taken (f238 already nonzero here)

_S18_HEAD_CMPI = (16, 1)                                  # 005834 cmpi.w #1,ea1e.w
_S18_HEAD_BEQ = {True: (10, 1), False: (8, 1)}            # 00583A beq.b $5852
_S18_BUDGET_BSR = (18, 1)                                 # 00583C bsr.w $5cee
_S18_BUDGET_SUBQ = (4, 1)                                 # 005840 subq.w #1,d7
_S18_BUDGET_BPL = {True: (10, 1), False: (12, 1)}         # 005842 bpl.w -- taken: budget still open
_S18_BUDGET_RESET_MOVEQ = (4, 1)                          # 005846 moveq #2,d7
_S18_BUDGET_RESET_STORE = (16, 1)                         # 005848 move.w #1,f192.w
_S18_BUDGET_RESET_BRA = (10, 1)                           # 00584E bra.w 75d6
_S18_DISPATCH_TST_ACTIVE = (12, 1)                        # 005854 tst.w f238.w
_S18_DISPATCH_BEQ_SCAN = {True: (10, 1), False: (12, 1)}  # 005858 beq.w $58d2
_S18_DISPATCH_TST_EMPTY = (12, 1)                         # 00585C tst.w f23a.w
_S18_DISPATCH_BEQ_DIRECT = {True: (10, 1), False: (12, 1)}  # 005860 beq.w $5c5e
_S18_DISPATCH_BIT1_TEST = (16, 1)                         # 005864 btst #1,ea23.w
_S18_DISPATCH_BIT1_BNE_NOT = (12, 1)                      # 00586A bne.w -- not taken (the only witnessed case)
_S18_DISPATCH_BIT2_TEST = (16, 1)                         # 00586E btst #2,ea23.w
_S18_DISPATCH_BIT2_BNE = {True: (10, 1), False: (12, 1)}  # 005874 bne.w
_S18_DISPATCH_BSR_HIGHLIGHT = (18, 1)                     # 005878 bsr.w $5cee
_S18_DISPATCH_TST_ACTIVE2 = (12, 1)                       # 00587C tst.w f238.w
_S18_DISPATCH_BEQ_RESCAN_NOT = (8, 1)                     # 005880 beq.b $58d2 -- always not taken (f238 unchanged since entry)
_S18_DISPATCH_BRA_EXIT = (10, 1)                          # 005882 bra.w 75d6

import collections as _collections

_S1918Costs = _collections.namedtuple('_S1918Costs', [
    'active_test', 'beq_scan', 'empty_test', 'beq_direct',
    'bit1_test', 'bit1_bne_not', 'bit2_test', 'bit2_bne', 'bsr_highlight'])

_S19_DISPATCH_COSTS = _S1918Costs(
    active_test=_S19_DISPATCH_TST_ACTIVE, beq_scan=_S19_DISPATCH_BEQ_SCAN,
    empty_test=_S19_DISPATCH_TST_EMPTY, beq_direct=_S19_DISPATCH_BEQ_DIRECT,
    bit1_test=_S19_DISPATCH_BIT1_TEST, bit1_bne_not=_S19_DISPATCH_BIT1_BNE_NOT,
    bit2_test=_S19_DISPATCH_BIT2_TEST, bit2_bne=_S19_DISPATCH_BIT2_BNE,
    bsr_highlight=_S19_DISPATCH_BSR_HIGHLIGHT)
_S18_DISPATCH_COSTS = _S1918Costs(
    active_test=_S18_DISPATCH_TST_ACTIVE, beq_scan=_S18_DISPATCH_BEQ_SCAN,
    empty_test=_S18_DISPATCH_TST_EMPTY, beq_direct=_S18_DISPATCH_BEQ_DIRECT,
    bit1_test=_S18_DISPATCH_BIT1_TEST, bit1_bne_not=_S18_DISPATCH_BIT1_BNE_NOT,
    bit2_test=_S18_DISPATCH_BIT2_TEST, bit2_bne=_S18_DISPATCH_BIT2_BNE,
    bsr_highlight=_S18_DISPATCH_BSR_HIGHLIGHT)


def _s1918_scan_plan(machine, registers, read, cycles, instructions, sr):
    """0058D2-005954: the scan itself (game.movement.box_overlap_scan's own algorithm), consumed by
    player.state1918_scan_consume.  Returns a plain AtomicPlan ('not-found' / 'rearmed') or a Seam
    ('consumed', ceded over 001648)."""
    from .game import player, movement
    result = player.state1918_scan_consume(read)
    scan = result['scan']
    entries = scan['entries']
    c, i = _S1918_SCAN_HEAD
    cycles += c
    instructions += i
    for index, step in enumerate(entries):
        c, i = _bs_entry_cost(step, index == movement.BOX_SCAN_COUNT - 1)
        cycles += c
        instructions += i
    exit_registers = {'d0': scan['player_x'], 'd1': scan['player_y'], 'd7': 1}
    last_tested = next((e for e in reversed(entries) if e['arm'] in ('tested', 'found')), None)
    if last_tested is not None:
        exit_registers['d2'] = (registers['d2'] & 0xFFFF0000) | ((last_tested['x'] - 4) & 0xFFFF)
        exit_registers['d3'] = (registers['d3'] & 0xFFFF0000) | ((last_tested['y'] - 0xC) & 0xFFFF)
        exit_registers['d4'] = last_tested['far_x']
        exit_registers['d5'] = last_tested['far_y']
    dbra_count = len(entries) - (1 if scan['arm'] == 'found' else 0)
    exit_registers['d6'] = (registers['d6'] & 0xFFFF0000) | ((0xC7 - dbra_count) & 0xFFFF)
    sp32 = registers['a7']
    sp = sp32 & 0xFFFFFF
    # 0058D2 move.w #1,f238.w runs unconditionally at scan entry, before any of found/not-found is
    # decided; the 'rearmed' tail's own clr.w f238.w (005C24) later overrides it back to 0.
    order = dict(_bytes(0xFFFFF238 & 0xFFFFFF, 1, 2))

    if result['arm'] == 'not-found':
        c, i = _S1918_NOTFOUND_SET_EMPTY
        cycles += c
        instructions += i
        for a, (v, s) in result['stores'].items():
            order.update(dict(_bytes(a, v, s)))
        sr = _logic_sr(sr, 1, 2)   # 005924 move.w #1,f23a.w is the last flag-setter
        c, i = _S1918_NOTFOUND_BRA
        cycles += c
        instructions += i
        exit_registers['a0'] = scan['end_entry'] & 0xFFFFFFFF
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00592A)

    if result['arm'] in ('kind-other', 'kind-out-of-range'):
        raise UnsupportedCandidate(f"state 19/18 scan found-kind arm not witnessed: {result['arm']}")

    entry = result['entry']
    exit_registers['a0'] = entry & 0xFFFFFFFF
    # 005934 movem.w (a0),d0-d2 overwrites d0/d1/d2 with the found entry's own raw x/y/kind fields
    # (each sign-extended to 32 bits, MOVEM's own word-transfer convention) -- unlike 00722C's own
    # tail, which never reaches this instruction.  d3/d4/d5/d6 are untouched by it (only three
    # registers, d0-d2) and keep the box-test chain's own residue computed above.
    def _sign_extend(word):
        word &= 0xFFFF
        return (word - 0x10000) & 0xFFFFFFFF if word & 0x8000 else word
    ex = read(entry & 0xFFFFFF, 2)
    ey = read((entry + 2) & 0xFFFFFF, 2)
    kind = result['kind']
    exit_registers['d0'] = _sign_extend(ex)
    exit_registers['d1'] = _sign_extend(ey)
    exit_registers['d2'] = _sign_extend(kind)
    c, i = _S1918_FOUND_TAIL_HEAD
    cycles += c
    instructions += i
    c, i = _S1918_FOUND_RANGE_BGE_NOT
    cycles += c
    instructions += i
    c, i = _S1918_FOUND_KIND_TEST
    cycles += c
    instructions += i
    c, i = _S1918_FOUND_KIND_BNE_NOT
    cycles += c
    instructions += i
    c, i = _S1918_FOUND_SAVE_A2
    cycles += c
    instructions += i
    c, i = _S1918_FOUND_DISABLE
    cycles += c
    instructions += i
    c, i = _S1918_FOUND_BRA_5C14
    cycles += c
    instructions += i
    c, i = _S1918_5C14_BIT1_TEST
    cycles += c
    instructions += i
    ea23 = read(0xFFFFEA23, 1)
    bit1, bit2 = bool(ea23 & 0x2), bool(ea23 & 0x4)
    c, i = _S1918_5C14_BIT1_BNE[bit1]
    cycles += c
    instructions += i
    if not bit1:
        c, i = _S1918_5C14_BIT2_TEST
        cycles += c
        instructions += i
        c, i = _S1918_5C14_BIT2_BNE[bit2]
        cycles += c
        instructions += i

    if result['arm'] == 'rearmed':
        if bit1 or bit2:
            raise UnsupportedCandidate('state 19/18 scan rearm arm disagrees with EA23')
        c, i = _S1918_REARM_CLEAR_ACTIVE
        cycles += c
        instructions += i
        c, i = _S1918_REARM_STORE_KIND
        cycles += c
        instructions += i
        for a, (v, s) in result['stores'].items():
            order.update(dict(_bytes(a, v, s)))
        sr = _logic_sr(sr, 1, 2)   # 005C2C move.w #1,6(a2) is the last flag-setter
        c, i = _S1918_REARM_STORE_ONE
        cycles += c
        instructions += i
        c, i = _S1918_REARM_BRA
        cycles += c
        instructions += i
        exit_registers['a2'] = entry & 0xFFFFFFFF
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x005C32)

    if not (bit1 or bit2):
        raise UnsupportedCandidate('state 19/18 scan consume arm disagrees with EA23')
    # jsr $1648 (005C4E) pushes its own return address (005C54) as part of running; the machine
    # hands off to 001648 with a7 = entry a7 - 4, not entry a7 (no bsr/frame precedes it here).  This
    # structural write goes into `order` FIRST and the semantic stores LAST (achievement_slot_reset's
    # own convention), so a generic "flip the last write" mutant (_mutate_result) corrupts an
    # observable game byte, never the return address 001648's own rts reads.
    order.update(dict(_bytes((sp - 4) & 0xFFFFFF, 0x005C54, 4)))
    for a, (v, s) in result['stores'].items():
        order.update(dict(_bytes(a, v, s)))
    c, i = _S1918_CONSUME_HEAD
    cycles += c
    instructions += i
    from .game import achievements
    # 005C36 move.w #1,f2e0.w (PENDING_HIGHLIGHT); 005C40-005C44: move.w f236.w,d5 (HIGHLIGHT_ID into
    # d5's own lower half, upper already 0 from the scan's own far_y residue); move.w d5,d0 (D0's own
    # upper half stays whatever movem.w left it at -- sign_extend(ex) above -- only the lower word
    # becomes HIGHLIGHT_ID); 005C48 move.w d2,(a3,d5.w) stores the found entry's own kind into
    # ACHIEVEMENT_SLOTS[HIGHLIGHT_ID].
    highlight_id = read(achievements.HIGHLIGHT_ID, 2) & 0xFFFF
    order.update(dict(_bytes(0xFFFFF2E0 & 0xFFFFFF, 1, 2)))
    order.update(dict(_bytes((achievements.ACHIEVEMENT_SLOTS + 2 * highlight_id) & 0xFFFFFF, kind & 0xFFFF, 2)))
    c, i = _S1918_CONSUME_MOVEQ_D1
    cycles += c
    instructions += i
    c, i = _S1918_CONSUME_JSR
    cycles += c
    instructions += i
    exit_registers['a2'] = entry & 0xFFFFFFFF
    prefix_regs = dict(exit_registers)
    prefix_regs.update({'d0': (exit_registers['d0'] & 0xFFFF0000) | highlight_id,
                        'd1': 1, 'd2': exit_registers['d2'], 'a3': 0xFFFFF22E,
                        'd5': (exit_registers['d5'] & 0xFFFF0000) | ((2 * highlight_id) & 0xFFFF),
                        'a7': (sp32 - 4) & 0xFFFFFFFF, 'pc': STATE1918_ICON_UPLOAD,
                        'sr': _logic_sr(sr, 1, 4)})   # 005C4C moveq #1,d1 is the last flag-setter
    prefix = AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                        registers=prefix_regs, last_pc=0x005C4E)

    def consume_suffix(machine2, registers2, _sp32=sp32):
        if registers2['pc'] != 0x005C54:
            raise UnsupportedCandidate('state 19/18 consume suffix needs the machine parked at 005C54')
        c2, i2 = _S1918_CONSUME_TAIL_BRA
        return AtomicPlan(cycles=c2, instructions=i2, writes=(),
                          registers={'a7': _sp32, 'pc': 0x0075D6}, last_pc=0x005C54)

    return Seam(prefix=prefix, resume_pc=0x005C54, stack_basis=sp32, guards=(((sp - 4) & 0xFFFFFF, 4),), suffix=consume_suffix)


def _s1918_pending_idle_plan(machine, registers, head, cycles, instructions, sr, order):
    """005C58-005C94: the SAME shared tail regardless of state or how it was reached (directly, or
    via 005C58's own PENDING_HIGHLIGHT store)."""
    sp32 = registers['a7']
    for a, (v, s) in head.get('stores', {}).items():
        order.update(dict(_bytes(a, v, s)))
    c, i = _S1918_5C62_TST_PENDING
    cycles += c
    instructions += i
    pending = head['arm'] in ('pending-hold', 'pending-cleared')
    c, i = _S1918_5C66_BEQ_IDLE[not pending]
    cycles += c
    instructions += i
    if pending:
        c, i = _S1918_PEND_BIT1_TEST
        cycles += c
        instructions += i
        c, i = _S1918_PEND_BIT1_BNE_NOT
        cycles += c
        instructions += i
        c, i = _S1918_PEND_BIT2_TEST
        cycles += c
        instructions += i
        if head['arm'] == 'pending-hold':
            c, i = _S1918_PEND_BIT2_BNE[True]
            cycles += c
            instructions += i
            sr = (sr & ~0x04)   # 005C72 btst #2,ea23.w: bit set -> Z=0; N/V/C/X retained
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers={'d7': 1, 'a7': sp32, 'pc': 0x0075D6, 'sr': sr}, last_pc=0x005C78)
        c, i = _S1918_PEND_BIT2_BNE[False]
        cycles += c
        instructions += i
        c, i = _S1918_PEND_CLEAR
        cycles += c
        instructions += i
        sr = _logic_sr(sr, 0, 2)   # 005C7C clr.w f2e0.w is the last flag-setter
        c, i = _S1918_PEND_BRA
        cycles += c
        instructions += i
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'d7': 1, 'a7': sp32, 'pc': 0x0075D6, 'sr': sr}, last_pc=0x005C80)
    c, i = _S1918_IDLE_BIT1_TEST
    cycles += c
    instructions += i
    c, i = _S1918_IDLE_BIT1_BNE_NOT
    cycles += c
    instructions += i
    c, i = _S1918_IDLE_BIT2_TEST
    cycles += c
    instructions += i
    if head['arm'] == 'idle-exit':
        c, i = _S1918_IDLE_BIT2_BNE[False]
        cycles += c
        instructions += i
        sr = (sr & ~0x04) | 0x04   # 005C8C btst #2,ea23.w: bit clear -> Z=1; N/V/C/X retained
        c, i = _S1918_IDLE_EXIT_BRA
        cycles += c
        instructions += i
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'d7': 1, 'a7': sp32, 'pc': 0x0075D6, 'sr': sr}, last_pc=0x005C94)
    c, i = _S1918_IDLE_BIT2_BNE[True]
    cycles += c
    instructions += i
    return _s1918_idle_cycle_plan(machine, registers, cycles, instructions, order)


def _s1918_idle_cycle_plan(machine, registers, cycles, instructions, order):
    """005C98-005CEA: the sound-cued highlight-advance-and-clear-message arm, shared by states 19
    and 18.  Two chained platform calls (a run of them, Aladdin's own platform-tail shape): per the
    "never chain seams" rule, the prefix ends at the FIRST jsr and resume_pc is set past BOTH calls
    (005CE0) -- the machine runs the whole span (jsr 1648 #1, the RAM work 005CB6-005CD8, jsr 1648
    #2) uninterrupted, never re-gated in between, and the single suffix from 005CE0 is the region's
    own final RAM-only tail, read live rather than predicted (HIGHLIGHT_ID's own new value included)."""
    from .game import achievements
    sp32 = registers['a7']
    sp = sp32 & 0xFFFFFF
    read = _reader(machine)
    # jsr $1648 (005CB0) pushes its own return address (005CB6) as part of running.  This structural
    # write goes into `order` FIRST and the semantic sound-cue write LAST (achievement_slot_reset's
    # own convention), so a generic "flip the last write" mutant (_mutate_result) corrupts an
    # observable game byte, never the return address 001648's own rts reads.
    order.update(dict(_bytes((sp - 4) & 0xFFFFFF, 0x005CB6, 4)))
    c, i = _S1918_CYCLE_SOUND
    cycles += c
    instructions += i
    from .game.pickups import MOVEMENT_SOUND_CUE
    for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, STATE1918_CYCLE_SOUND_VALUE, 2):
        order[a] = b
    old_highlight = read(achievements.HIGHLIGHT_ID, 2) & 0xFFFF
    c, i = _S1918_CYCLE_HEAD1
    cycles += c
    instructions += i
    # 005CAA move.w (a3,d5.w),d2 is a WORD move: D2's own upper half survives from before it.
    d2_old = (registers['d2'] & 0xFFFF0000) | (read((achievements.ACHIEVEMENT_SLOTS + 2 * old_highlight) & 0xFFFFFF, 2) & 0xFFFF)
    c, i = _S1918_CYCLE_MOVEQ_D1_0
    cycles += c
    instructions += i
    c, i = _S1918_CYCLE_JSR1
    cycles += c
    instructions += i
    # 005CA6 lea.l f22e.w,a3 sets A3 for the rest of this activation (never reset); 005CAE moveq #0,d1
    # is the last flag-setter before the jsr (N=0,Z=1,V=C=0 from the immediate zero).
    sr_here = _logic_sr(registers['sr'], 0, 2)
    prefix = AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                        registers={'d0': (registers['d0'] & 0xFFFF0000) | old_highlight, 'd1': 0, 'd2': d2_old,
                                   'd5': (registers['d5'] & 0xFFFF0000) | ((2 * old_highlight) & 0xFFFF),
                                   'a3': 0xFFFFF22E, 'd7': 1,
                                   'a7': (sp32 - 4) & 0xFFFFFFFF, 'pc': STATE1918_ICON_UPLOAD, 'sr': sr_here},
                        last_pc=0x005CB0)

    def suffix(machine2, registers2, _sp32=sp32):
        if registers2['pc'] != 0x005CE0:
            raise UnsupportedCandidate('state 19/18 highlight-cycle suffix needs the machine parked at 005CE0')
        read2 = _reader(machine2)
        sr2 = registers2['sr']
        order2 = {}
        for a, b in _bytes(0xFFFFF16E & 0xFFFFFF, 0, 2):
            order2[a] = b
        sr2 = _logic_sr(sr2, 0, 2)   # 005CE0 clr.w f16e.w
        buffer_full = read2(0xFFFFF166, 4) & 0xFFFFFFFF   # 005CE4 movea.l f166.w,a3 -- the full pointer
        for a, b in _bytes(buffer_full & 0xFFFFFF, 0, 2):
            order2[a] = b
        sr2 = _logic_sr(sr2, 0, 2)   # 005CE8 clr.w (a3) is the last flag-setter
        c5, i5 = _S1918_CYCLE_CLEAR_PENDING
        c6, i6 = _S1918_CYCLE_LOAD_BUFFER
        c7, i7 = _S1918_CYCLE_CLEAR_BUFFER
        c8, i8 = _S1918_CYCLE_BRA
        return AtomicPlan(cycles=c5 + c6 + c7 + c8, instructions=i5 + i6 + i7 + i8, writes=tuple(order2.items()),
                          registers={'a3': buffer_full, 'a7': _sp32, 'pc': 0x0075D6, 'sr': sr2}, last_pc=0x005CEA)

    # No guard: the ceded span's own second jsr (005CDA) legitimately reuses the SAME stack slot the
    # first jsr's own return address (005CB6) occupied -- by design (a7 returns to entry a7 between
    # the two real calls), not a violation.  There is no frame of this activation's own beneath that
    # slot left to protect; stack_basis (checked unconditionally by run_seam) is the real identity
    # check here.
    return Seam(prefix=prefix, resume_pc=0x005CE0, stack_basis=sp32, guards=(), suffix=suffix)


def _s1918_highlight_cycle_prefix(read, sr, cycles, instructions, frame_a7, entry_d4):
    """005CEE-005D28: the achievement highlight cycle's own body, common to every caller (0058C6,
    00588E, 005878).  ``frame_a7`` is the a7 value already in effect when 005CEE's own code starts
    (after the caller's own bsr and its own d7 push).  Returns (cycles, instructions, writes,
    icon_d0, exit_a7) up to and including the jsr 1648 instruction: the caller adds its own register
    file (icon_d0 needs achievements.HIGHLIGHT_REFRESH_ICON_D2 et al -- kept out of this helper since
    d7's own presence in the register file differs by caller).  Both the 'spawn' arm's own internal
    jsr 10d7c and the final jsr 1648 push their own return address onto the stack as part of running
    -- transient for 10d7c (its own rts pops it before 005D20), permanent for 1648 (the machine takes
    over from exactly this pushed state) -- both real writes over the span this prefix claims."""
    from .game import achievements, spawns
    from .game.grid import GRID_X, GRID_Y
    result = achievements.achievement_highlight_cycle(read)
    hc, hi = _S1918_HIGHLIGHT_PUSH
    hc2, hi2 = _S1918_HIGHLIGHT_HEAD
    cycles += hc + hc2
    instructions += hi + hi2
    # jsr $1648 (005D28) pushes its own return address (005D2E) as part of running -- inserted FIRST,
    # ahead of every semantic store, so a generic "flip the last write" mutant (_mutate_result)
    # corrupts an observable game byte, never the return address 001648's own rts reads (the 'spawn'
    # arm's own jsr 10d7c also pushes to this SAME slot transiently, but only the FINAL byte content
    # at each address matters to the strict witness, and 005D2E is what is there once this prefix's
    # own span ends, regardless of arm).
    horder = dict(_bytes((frame_a7 - 4) & 0xFFFFFF, 0x005D2E, 4))
    for a, (v, s) in result['stores'].items():
        horder.update(dict(_bytes(a, v, s)))
    if result['arm'] == 'refresh':
        c, i = _S1918_HIGHLIGHT_BMI_EMPTY[True]
        cycles += c
        instructions += i
    else:
        c, i = _S1918_HIGHLIGHT_BMI_EMPTY[False]
        cycles += c
        instructions += i
        c, i = _S1918_HIGHLIGHT_ADDI
        cycles += c
        instructions += i
        c, i = _S1918_HIGHLIGHT_BMI2_NOT
        cycles += c
        instructions += i
        c, i = _S1918_HIGHLIGHT_SPAWN_SETUP
        cycles += c
        instructions += i
        x = (read(GRID_X, 2) + 8) & 0xFFFF
        y = (read(GRID_Y, 2) + 0x20) & 0xFFFF
        spawn = spawns.floating_icon_spawn(read, x, y, result['kind'])
        if spawn['arm'] != 'spawn':
            raise UnsupportedCandidate(f"floating icon spawn arm not witnessed: {spawn['arm']}")
        for a, (v, s) in spawn['stores'].items():
            horder.update(dict(_bytes(a, v, s)))
        c, i = _S1918_HIGHLIGHT_JSR_SPAWN
        cycles += c
        instructions += i
        # 010D7C's own body: the cmpi/beq special-kind test, the busy test, then the four-field store.
        for cost in (_S1918_SPAWN_CMPI, _S1918_SPAWN_BEQ_NOT, _S1918_SPAWN_TST_BUSY, _S1918_SPAWN_BPL_NOT,
                    _S1918_SPAWN_STORE, _S1918_SPAWN_RTS):
            c, i = cost
            cycles += c
            instructions += i
    c, i = _S1918_HIGHLIGHT_REFRESH_HEAD
    cycles += c
    instructions += i
    c, i = _S1918_HIGHLIGHT_REFRESH_JSR   # 005D28 jsr 1648 -- the prefix's own last instruction
    cycles += c
    instructions += i
    # Regardless of arm, the code converges at 005D20-005D28 (move f236,d0; moveq #1,d1; moveq #$ff,
    # d2; jsr 1648): 005D26's own moveq #$ff,d2 is always the last flag-setter before the jsr
    # (N=1,Z=V=C=0, the immediate -1's own sign).  005CF4/005CF8 (move f236,d4; add d4,d4) leave D4
    # at icon_d0*2, never touched again before the jsr; 005CF0's own lea sets A3 to ACHIEVEMENT_SLOTS
    # for the rest of the activation.
    sr_final = _logic_sr(sr, 0xFFFFFFFF, 4)
    # 005CF4 move.w f236.w,d4 / 005CF8 add.w d4,d4 are both WORD ops: D4's own upper half survives
    # from whatever it held when 005CEE's own body started (the caller's own D4, untouched before it).
    extra_registers = {'d4': (entry_d4 & 0xFFFF0000) | ((2 * result['icon_d0']) & 0xFFFF), 'a3': 0xFFFFF22E}
    return cycles, instructions, tuple(horder.items()), result['icon_d0'], (frame_a7 - 4) & 0xFFFFFFFF, sr_final, extra_registers


def _s1918_highlight_via_dispatch_plan(machine, registers, read, sr, cycles, instructions, resume_pc, tail_active_test, tail_bne_exit, tail_last_pc):
    """0058C6 (state 19) / 005878 (state 18): the EA1E==1 arm's own bit-tests-both-clear case --
    calls the achievement highlight cycle, then unconditionally exits (tst f238.w always finds it
    still nonzero, since nothing between the outer test and here touches it)."""
    from .game import achievements
    sp32 = registers['a7']
    sp = sp32 & 0xFFFFFF
    # bsr.w $5cee pushes its own return address (resume_pc) at (entry a7 - 4); 005CEE's own first
    # instruction, move.l d7,-(a7), then pushes d7 (already 1, this arm's own moveq having already
    # run) at (entry a7 - 8): both real writes the prefix must include, and the machine hands off to
    # 001648 with a7 = entry a7 - 8, not entry a7.
    frame_a7 = (sp32 - 8) & 0xFFFFFFFF
    frame_order = dict(_bytes((sp - 4) & 0xFFFFFF, resume_pc, 4))
    frame_order.update(_bytes((sp - 8) & 0xFFFFFF, 1, 4))
    cycles, instructions, writes, icon_d0, exit_a7, sr_final, extra_registers = _s1918_highlight_cycle_prefix(
        read, sr, cycles, instructions, frame_a7, registers['d4'])
    order = dict(frame_order)
    order.update(writes)
    prefix_registers = {'d0': (registers['d0'] & 0xFFFF0000) | icon_d0, 'd1': 1,
                        'd2': achievements.HIGHLIGHT_REFRESH_ICON_D2 & 0xFFFFFFFF,
                        'd7': 1, 'a7': exit_a7, 'pc': STATE1918_ICON_UPLOAD, 'sr': sr_final}
    prefix_registers.update(extra_registers)
    prefix = AtomicPlan(
        cycles=cycles, instructions=instructions, writes=tuple(order.items()),
        registers=prefix_registers, last_pc=0x005D28)

    def suffix(machine2, registers2, _sp32=sp32):
        if registers2['pc'] != resume_pc:
            raise UnsupportedCandidate('state 19/18 highlight suffix needs the machine parked at the resume PC')
        f238 = _reader(machine2)(0xFFFFF238, 2) & 0xFFFF
        c5, i5 = tail_active_test
        c6, i6 = tail_bne_exit
        sr2 = _logic_sr(registers2['sr'], f238, 2)   # the caller's own tst.w f238.w is the last flag-setter
        return AtomicPlan(cycles=c5 + c6, instructions=i5 + i6, writes=(),
                          registers={'d7': 1, 'a7': _sp32, 'pc': 0x0075D6, 'sr': sr2}, last_pc=tail_last_pc)

    return Seam(prefix=prefix, resume_pc=resume_pc, stack_basis=sp32,
               guards=(((sp - 8) & 0xFFFFFF, 8),), suffix=suffix)


def _s1918_highlight_via_budget_plan(machine, registers, sr, cycles, instructions, *, resume_pc,
                                     tail_arm_cost, tail_last_pc, tail_d7, tail_sr_fn, tail_writes=()):
    """00588E (state 19) / 00583C (state 18): the "!=1" arm's own unconditional call, whose own tail
    (a budget countdown, not a plain exit) runs AFTER the highlight cycle's own rts."""
    from .game import achievements
    sp32 = registers['a7']
    sp = sp32 & 0xFFFFFF
    read = _reader(machine)
    # bsr.w $5cee pushes its own return address (resume_pc) at (entry a7 - 4); 005CEE's own first
    # instruction, move.l d7,-(a7), then pushes the caller's own (untouched) D7 at (entry a7 - 8):
    # both real writes the prefix must include, and the machine hands off to 001648 with
    # a7 = entry a7 - 8, not entry a7.
    d7_entry = registers['d7'] & 0xFFFFFFFF
    frame_a7 = (sp32 - 8) & 0xFFFFFFFF
    frame_order = dict(_bytes((sp - 4) & 0xFFFFFF, resume_pc, 4))
    frame_order.update(_bytes((sp - 8) & 0xFFFFFF, d7_entry, 4))
    cycles, instructions, writes, icon_d0, exit_a7, sr_final, extra_registers = _s1918_highlight_cycle_prefix(
        read, sr, cycles, instructions, frame_a7, registers['d4'])
    order = dict(frame_order)
    order.update(writes)
    prefix_registers = {'d0': (registers['d0'] & 0xFFFF0000) | icon_d0, 'd1': 1,
                        'd2': achievements.HIGHLIGHT_REFRESH_ICON_D2 & 0xFFFFFFFF,
                        'a7': exit_a7, 'pc': STATE1918_ICON_UPLOAD, 'sr': sr_final}
    prefix_registers.update(extra_registers)
    prefix = AtomicPlan(
        cycles=cycles, instructions=instructions, writes=tuple(order.items()),
        registers=prefix_registers, last_pc=0x005D28)

    def suffix(machine2, registers2, _sp32=sp32):
        if registers2['pc'] != resume_pc:
            raise UnsupportedCandidate('state 19/18 highlight suffix needs the machine parked at the resume PC')
        c5, i5 = tail_arm_cost
        sr2 = tail_sr_fn(registers2['sr'])
        regs = {'d7': tail_d7, 'a7': _sp32, 'pc': 0x0075D6}
        if sr2 is not None:
            regs['sr'] = sr2
        return AtomicPlan(cycles=c5, instructions=i5, writes=tail_writes,
                          registers=regs, last_pc=tail_last_pc)

    return Seam(prefix=prefix, resume_pc=resume_pc, stack_basis=sp32,
               guards=(((sp - 8) & 0xFFFFFF, 8),), suffix=suffix)


def _state1918_body_plan(machine, registers, read, head, costs, dispatch_bsr_resume, dispatch_tail):
    """0058A2-0058D2 (state 19) / 005852-005878 (state 18): the EA1E==1 arm's own outer dispatch,
    then the shared body from 0058D2/005C14/005CEE onward."""
    sr = registers['sr']
    cycles, instructions = _S1918_DISPATCH_MOVEQ
    c, i = costs.active_test
    cycles += c
    instructions += i
    if head['arm'] == 'scan':
        c, i = costs.beq_scan[True]
        cycles += c
        instructions += i
        return _s1918_scan_plan(machine, registers, read, cycles, instructions, sr)
    c, i = costs.beq_scan[False]
    cycles += c
    instructions += i
    c, i = costs.empty_test
    cycles += c
    instructions += i
    if head['arm'] == 'highlight':
        c, i = costs.beq_direct[False]
        cycles += c
        instructions += i
        c, i = costs.bit1_test
        cycles += c
        instructions += i
        c, i = costs.bit1_bne_not
        cycles += c
        instructions += i
        c, i = costs.bit2_test
        cycles += c
        instructions += i
        c, i = costs.bit2_bne[False]
        cycles += c
        instructions += i
        c, i = costs.bsr_highlight
        cycles += c
        instructions += i
        return _s1918_highlight_via_dispatch_plan(machine, registers, read, sr, cycles, instructions,
                                                  dispatch_bsr_resume, *dispatch_tail)
    if head['arm'] not in ('pending-hold', 'pending-cleared', 'idle-cycle', 'idle-exit'):
        raise UnsupportedCandidate(f"state 19/18 dispatch arm not witnessed: {head['arm']}")
    set_pending = head['set_pending']
    c, i = costs.beq_direct[not set_pending]
    cycles += c
    instructions += i
    order = {}
    if set_pending:
        c, i = costs.bit1_test
        cycles += c
        instructions += i
        c, i = costs.bit1_bne_not
        cycles += c
        instructions += i
        c, i = costs.bit2_test
        cycles += c
        instructions += i
        c, i = costs.bit2_bne[True]
        cycles += c
        instructions += i
        c, i = _S1918_5C58_SET_PENDING
        cycles += c
        instructions += i
    c, i = _S1918_5C5E_CLEAR_EMPTY
    cycles += c
    instructions += i
    return _s1918_pending_idle_plan(machine, registers, head, cycles, instructions, sr, order)


def state19_plan(machine, registers):
    """005886: state 19's own outer head.  See game.player's own module note above state19_head."""
    from .game import player
    if registers['pc'] != STATE19_ENTRY:
        raise UnsupportedCandidate('state 19 planner needs the machine parked at 005886')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    if registers['a6'] != 0xC00000:
        raise UnsupportedCandidate('state 19 planner needs a6 = C00000 (the VDP data port)')
    read = _reader(machine)
    head = player.state19_head(read)

    if head['head'] == 'dispatch':
        cycles, instructions = _S19_HEAD_CMPI
        c, i = _S19_HEAD_BEQ[True]
        cycles += c
        instructions += i
        body = _state1918_body_plan(machine, registers, read, head, _S19_DISPATCH_COSTS, 0x0058CA,
                                    (_S19_DISPATCH_TST_ACTIVE2, _S19_DISPATCH_BNE_EXIT, 0x0058CE))
        return _prefix_atomic_or_seam(body, cycles, instructions)

    # head['head'] == 'budget': EA1E != 1 -- calls the highlight cycle unconditionally, then a
    # per-activation budget (D7) decides whether this activation just exits or resets STATE_INDEX.
    cycles, instructions = _S19_HEAD_CMPI
    c, i = _S19_HEAD_BEQ[False]
    cycles += c
    instructions += i
    c, i = _S19_BUDGET_BSR
    cycles += c
    instructions += i
    d7 = registers['d7'] & 0xFFFF
    tail = player.state19_budget_tail(read, d7)
    tail_order = {}
    for a, (v, s) in tail.get('stores', {}).items():
        tail_order.update(dict(_bytes(a, v, s)))

    if tail['arm'] == 'budget-hold':
        c2, i2 = _S19_BUDGET_SUBQ
        c3, i3 = _S19_BUDGET_BPL[True]
        tail_arm_cost = (c2 + c3, i2 + i3)

        def tail_sr_fn(live_sr, _d7=d7):
            return _sub_sr(live_sr, d7, 1, 2)   # 005892 subq.w #1,d7 is the last flag-setter

        return _s1918_highlight_via_budget_plan(machine, registers, sr, cycles, instructions,
                                                resume_pc=0x005892, tail_arm_cost=tail_arm_cost,
                                                tail_last_pc=0x005894, tail_d7=(registers['d7'] & 0xFFFF0000) | tail['d7'], tail_sr_fn=tail_sr_fn,
                                                tail_writes=tuple(tail_order.items()))

    c2, i2 = _S19_BUDGET_SUBQ
    c3, i3 = _S19_BUDGET_BPL[False]
    c4, i4 = _S19_BUDGET_RESET_MOVEQ
    c5, i5 = _S19_BUDGET_RESET_STORE
    c6, i6 = _S19_BUDGET_RESET_BRA
    tail_arm_cost = (c2 + c3 + c4 + c5 + c6, i2 + i3 + i4 + i5 + i6)

    def tail_sr_fn(live_sr, _d7=d7):
        # 005892 subq.w #1,d7 (the tail's own first instruction, X=C from the borrow) runs before
        # 00589A clr.w f192.w (which retains X, touching only N/Z/V/C).
        after_subq = _sub_sr(live_sr, _d7, 1, 2)
        return _logic_sr(after_subq, player.STATE19_RESET_STATE_INDEX, 2)

    return _s1918_highlight_via_budget_plan(machine, registers, sr, cycles, instructions,
                                            resume_pc=0x005892, tail_arm_cost=tail_arm_cost,
                                            tail_last_pc=0x00589E, tail_d7=2, tail_sr_fn=tail_sr_fn,
                                            tail_writes=tuple(tail_order.items()))


def _prefix_atomic_or_seam(result, extra_cycles, extra_instructions):
    """Fold an outer head's own fixed cost into whichever plan/seam the shared body returned."""
    if isinstance(result, Seam):
        p = result.prefix
        new_prefix = AtomicPlan(cycles=p.cycles + extra_cycles, instructions=p.instructions + extra_instructions,
                                writes=p.writes, registers=p.registers, last_pc=p.last_pc)
        return Seam(prefix=new_prefix, resume_pc=result.resume_pc, stack_basis=result.stack_basis,
                   guards=result.guards, suffix=result.suffix)
    return AtomicPlan(cycles=result.cycles + extra_cycles, instructions=result.instructions + extra_instructions,
                      writes=result.writes, registers=result.registers, last_pc=result.last_pc)


def state18_plan(machine, registers):
    """005834: state 18's own outer head.  See game.player's own module note above state18_head."""
    from .game import player
    if registers['pc'] != STATE18_ENTRY:
        raise UnsupportedCandidate('state 18 planner needs the machine parked at 005834')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    if registers['a6'] != 0xC00000:
        raise UnsupportedCandidate('state 18 planner needs a6 = C00000 (the VDP data port)')
    read = _reader(machine)
    head = player.state18_head(read)

    if head['head'] == 'dispatch':
        cycles, instructions = _S18_HEAD_CMPI
        c, i = _S18_HEAD_BEQ[True]
        cycles += c
        instructions += i
        # state 18's own dispatch-triggered highlight call (005878) has an extra tail (00587C-005882)
        # that re-tests SCAN_ACTIVE before exiting -- structurally always not-taken (SCAN_ACTIVE is
        # untouched by the highlight cycle, so whatever made this activation reach 'highlight' -- i.e.
        # SCAN_ACTIVE != 0 -- still holds), so it costs one extra byte-branch beyond state 19's own
        # equivalent tail (which only re-tests, no further branch).
        body = _state1918_body_plan(machine, registers, read, head, _S18_DISPATCH_COSTS, 0x00587C,
                                    (_S18_DISPATCH_TST_ACTIVE2, _add(_S18_DISPATCH_BEQ_RESCAN_NOT, _S18_DISPATCH_BRA_EXIT),
                                     0x005882))
        return _prefix_atomic_or_seam(body, cycles, instructions)

    # head['head'] == 'budget': EA1E != 1, the SAME shape as state 19's own, targeting state 1.
    cycles, instructions = _S18_HEAD_CMPI
    c, i = _S18_HEAD_BEQ[False]
    cycles += c
    instructions += i
    c, i = _S18_BUDGET_BSR
    cycles += c
    instructions += i
    d7 = registers['d7'] & 0xFFFF
    tail = player.state18_budget_tail(read, d7)
    tail_order = {}
    for a, (v, s) in tail.get('stores', {}).items():
        tail_order.update(dict(_bytes(a, v, s)))

    if tail['arm'] == 'budget-hold':
        c2, i2 = _S18_BUDGET_SUBQ
        c3, i3 = _S18_BUDGET_BPL[True]
        tail_arm_cost = (c2 + c3, i2 + i3)

        def tail_sr_fn(live_sr, _d7=d7):
            return _sub_sr(live_sr, d7, 1, 2)

        return _s1918_highlight_via_budget_plan(machine, registers, sr, cycles, instructions,
                                                resume_pc=0x005840, tail_arm_cost=tail_arm_cost,
                                                tail_last_pc=0x005842, tail_d7=(registers['d7'] & 0xFFFF0000) | tail['d7'], tail_sr_fn=tail_sr_fn,
                                                tail_writes=tuple(tail_order.items()))

    c2, i2 = _S18_BUDGET_SUBQ
    c3, i3 = _S18_BUDGET_BPL[False]
    c4, i4 = _S18_BUDGET_RESET_MOVEQ
    c5, i5 = _S18_BUDGET_RESET_STORE
    c6, i6 = _S18_BUDGET_RESET_BRA
    tail_arm_cost = (c2 + c3 + c4 + c5 + c6, i2 + i3 + i4 + i5 + i6)

    def tail_sr_fn(live_sr, _d7=d7):
        after_subq = _sub_sr(live_sr, _d7, 1, 2)
        return _logic_sr(after_subq, player.STATE18_RESET_STATE_INDEX, 2)

    return _s1918_highlight_via_budget_plan(machine, registers, sr, cycles, instructions,
                                            resume_pc=0x005840, tail_arm_cost=tail_arm_cost,
                                            tail_last_pc=0x00584E, tail_d7=2, tail_sr_fn=tail_sr_fn,
                                            tail_writes=tuple(tail_order.items()))

# --- 0066A8: state 9 (game.player.state9_step / state9_fall_tail / _state9_head / _row_gate_open) --
#
# Costed one instruction-block at a time from the tracer on nine real fixtures over
# `census-0066A8-*` covering every witnessed arm (18 September); every branch pair's own taken/
# not-taken cost matches the short-branch convention already established for states 0/1/14 (10/8).
# `006442`/`006468` (`_row_gate_cost` below) are byte-identical in cost regardless of the row bias
# baked into their own immediate operands (confirmed against real traces of both).
STATE9_ENTRY = 0x0066A8

_S9_HEAD_CMPI_C = (8, 1)                    # 0066A8 cmpi.w #$c,d7
_S9_HEAD_BNE_C = {True: (10, 1), False: (8, 1)}     # 0066AC bne.b -- taken: d7 != 0xC
_S9_HEAD_CMPI_F19C = (16, 1)                # cmpi.w #4,f19c.w (both the 0xC and 0 branches)
_S9_HEAD_BLT = {True: (10, 1), False: (8, 1)}       # blt.b -- taken: stays put; not taken: jumps
_S9_HEAD_MOVEQ5 = (4, 1)                    # moveq #5,d7 (0066B6, 0066D0)
_S9_HEAD_BRA = (10, 1)                      # bra.b $66d2 (0066B8, 0066CE)
_S9_HEAD_CMPI_5 = (8, 1)                    # 0066BA cmpi.w #5,d7
_S9_HEAD_BEQ_5 = {True: (10, 1), False: (8, 1)}
_S9_HEAD_TST = (4, 1)                       # 0066C0 tst.w d7
_S9_HEAD_BNE_0 = {True: (10, 1), False: (8, 1)}     # 0066C2 bne.b -- taken: d7 not in {0,5,0xc}
_S9_HEAD_ADDQ4 = (4, 1)                     # 0066CC addq.w #4,d7

_S9_BSR_GRID = (18, 1)                      # bsr.w $63fa (both call sites, 0066D2/00670C)
_S9_P1_HEAD = (12 + 8 + 8, 3)               # move.w f18c,d0; andi.w #1f,d0; cmpi.w #8,d0
_S9_P1_BGE = {True: (10, 1), False: (8, 1)}         # bge.b -- taken: low5 >= 8, skip the grid tests
_S9_P1_GRIDTEST = (16, 1)                   # cmpi.b #1,offset(a0), each of the three positions
_S9_P1_GRIDBEQ = {True: (10, 1), False: (8, 1)}     # beq.b -- taken: blocked, straight to 00670C
_S9_P1_CMPI_F19C = (16, 1)                  # 0066FC cmpi.w #4,f19c.w
_S9_P1_BLT = {True: (10, 1), False: (8, 1)}         # blt.b -- taken: not yet time to advance
_S9_P1_ADVANCE = (12 + 16, 2)               # move.w f196,d0; add.w d0,f18c.w

_S9_L_TST_EA1E = (12, 1)                    # 006710 tst.w ea1e.w
_S9_L_BPL = {True: (10, 1), False: (8, 1)}          # bpl.b -- taken: ea1e >= 0 (arm B); not taken: arm A

_S9_A_MOVE_D0 = (12, 1)                     # 006716 move.w f18c,d0
_S9_A_TST_F196 = (12, 1)                    # 00671A tst.w f196.w
_S9_A_BEQ_F196 = {True: (10, 1), False: (8, 1)}     # beq.b -- taken: decline (f196 == 0)
_S9_A_CMP_F19A = (12, 1)                    # 006720 cmp.w f19a.w,d0
_S9_A_BEQ_F19A = {True: (10, 1), False: (8, 1)}     # beq.b -- taken: decline (x == tracked)
_S9_A_ANDI_1F = (8, 1)                      # 006726 andi.w #1f,d0
_S9_A_BNE_LOW = {True: (10, 1), False: (8, 1)}      # bne.b -- taken: decline (low5 != 0)
_S9_A_CMPI_CELL = (12, 1)                   # 00672C cmpi.b #2,(a0)
_S9_A_BNE_CELL = {True: (10, 1), False: (8, 1)}     # bne.b -- taken: decline; not taken: LANDING
_S9_A_LANDING_TAIL = _add((20, 1), (20, 1), (16, 1), (16, 1), (4, 1), (16, 1), (16, 1), (16, 1), (10, 1))
# 006732 andi f18c,#$ffe0; 006738 andi f18e,#$fff8; 00673E clr f1a8; 006742 move #$e,f192;
# 006748 moveq #2,d7; 00674A clr f1ae; 00674E clr f1a4; 006752 clr f1a6; 006756 bra.w $75d6

_S9_B_CMPI_EA1E = (16, 1)                   # 00675A cmpi.w #1,ea1e.w
_S9_B_BNE_EA1E = {True: (10, 1), False: (8, 1)}     # bne.b -- taken: decline outright (ea1e != 1)
_S9_B_MOVE_D0 = (12, 1)                     # 006762 move.w f18c,d0
_S9_B_CMP_F19A = (12, 1)                    # 006766 cmp.w f19a.w,d0
_S9_B_BEQ_F19A = {True: (10, 1), False: (8, 1)}     # beq.b -- taken: decline
_S9_B_ANDI_1F = (8, 1)                      # 00676C andi.w #1f,d0
_S9_B_BNE_LOW = {True: (10, 1), False: (8, 1)}      # bne.b -- taken: decline (low5 != 0)

_S9_G_CMPI_F19C = (16, 1)                   # cmpi.w #$16,f19c.w (both the before and after checks)
_S9_G_BLT = {True: (10, 1), False: (8, 1)}          # blt.b -- taken: player.F19C short of the trigger gate
_S9_BSR_ROWGATE = (18, 1)                   # bsr.w $6442/$6468 -- the OUTER call, either probe
_S9_G_TST_D1 = (4, 1)                       # tst.w d1 (both probe return sites)
_S9_G_BEQ_D1 = {True: (10, 1), False: (8, 1)}       # beq.b -- taken: not found
_S9_GROUND_TAIL = _add((16, 1), (20, 1), (4, 1), (16, 1), (16, 1), (10, 1))   # ...the final bra.w $75d6
# 0067B8 move #$10,f192; 0067BE andi f18e,#$fff0; 0067C4 moveq #0,d7; 0067C6 clr f1b8;
# 0067CA move #$39,fdf6

_S9_D_LEA = (8, 1)                          # 0067D4 lea.l $6414(pc),a1
_S9_D_MOVE_F19C = (12, 1)                   # 0067D8 move.w f19c.w,d0
_S9_D_TABLE_READ = (14, 1)                  # 0067DC move.w (a1,d0.w),d0
_S9_D_SUB = (16, 1)                         # 0067E0 sub.w d0,f18e.w
_S9_D_TST_F19E = (12, 1)                    # 0067E4 tst.w f19e.w
_S9_D_BEQ_F19E = {True: (10, 1), False: (8, 1)}     # beq.b -- taken: no double (F19E == 0, always true)
_S9_D_BNE_D1 = {True: (10, 1), False: (8, 1)}       # beq.b at 0067F4 -- taken(==0): not found
_S9_LANDED_TAIL = _add((20, 1), (20, 1), (16, 1), (16, 1), (16, 1), (16, 1))
# 0067F6 andi f18e,#$fff0; 0067FC addi f18e,#$10; 006802 move #$c,f192; 006808 clr f194;
# 00680C clr f1a0; 006810 clr f198 -- six instructions; 006814's own moveq #0,d7 is separate, below
_S9_LANDED_MOVEQ = (4, 1)
_S9_LANDED_BRA = (10, 1)                     # 006816 bra.w $75d6

_S9_G2_BNE_D1 = {True: (10, 1), False: (8, 1)}      # bne.b at 006828 -- taken: found, jump back to the ground tail

_S9_T_CMPI_F19C_4 = (16, 1)                 # 00682A cmpi.w #4,f19c.w
_S9_T_BLT = {True: (10, 1), False: (8, 1)}          # blt.b -- taken: skip the trigger gate entirely
_S9_T_BTST = (16, 1)                        # 006832 btst.b #2,ea23.w
_S9_T_BEQ_BIT2 = {True: (10, 1), False: (8, 1)}     # beq.b -- taken: bit clear, skip the search
_S9_BSR_SEARCH = (18, 1)                    # 00683A bsr.w $8222
_S9_T_TST_D0 = (4, 1)                       # 00683E tst.w d0
_S9_T_BNE_D0 = {True: (10, 1), False: (8, 1)}       # bne.b -- taken: not found
_S9_T_CMPI_2C = (16, 1)                     # 006842 cmpi.w #$2c,f19c.w
_S9_T_BGE_2C = {True: (10, 1), False: (8, 1)}       # bge.b -- taken: too late, decline
_S9_TRIGGER_TAIL = _add((16, 1), (4, 1), (16, 1), (16, 1), (10, 1))   # ...the final bra.w $75d6
# 00684A move #$14,f192; 006850 moveq #1,d7; 006852 move #1,f1ba; 006858 addq #2,f19c
_S9_COUNTDOWN_ADDQ = (16, 1)                # 006860 addq.w #2,f19c.w
_S9_COUNTDOWN_CMPI = (16, 1)                # 006864 cmpi.w #$2e,f19c.w
_S9_COUNTDOWN_BLT = {True: (10, 1), False: (12, 1)}  # blt.w -- taken: exit unchanged (still state 9); not
                                                       # taken (word displacement) costs 12, not the byte-branch 8
_S9_TERMINAL_TAIL = _add((16, 1), (16, 1), (16, 1), (16, 1), (4, 1), (10, 1))   # ...the final bra.w $75d6
# 00686E move #$c,f192; 006874 clr f194; 006878 clr f1a0; 00687C clr f198; 006880 moveq #0,d7


_S9_ROW_INNER_BSR = (18, 1)                  # bsr.b $63fa -- 006442's/006468's own inner call
_S9_ROW_MOVEQ0 = (4, 1)                      # moveq #0,d1 (006444/00646A)
_S9_ROW_TEST0 = {0x180: (16, 1), 0: (12, 1)}  # cmpi.b #1,bias(a0) -- displacement (0x180) vs direct (a0), bias=0
_S9_ROW_BEQ0 = {True: (10, 1), False: (8, 1)}       # beq.b -- taken: found directly
_S9_ROW_LOWHEAD = (12 + 8 + 8, 3)            # move.w f18c,d0; andi.w #1f,d0; cmpi.w #8,d0
_S9_ROW_BLT = {True: (10, 1), False: (8, 1)}        # blt.b -- taken: low5 < 8, not found
_S9_ROW_TEST1 = (16, 1)                      # cmpi.b #1,bias+1(a0)
_S9_ROW_BNE1 = {True: (10, 1), False: (8, 1)}       # bne.b -- taken: not found; not taken: found
_S9_ROW_MOVEQ1 = (4, 1)                      # moveq #1,d1 (found only)
_S9_ROW_RTS = (16, 1)


_S9_ROW_INNER_RETURN = {0x180: 0x006444, 0: 0x00646A}   # 006442's/006468's own bsr.b $63fa return site


def _row_gate_cost(read, address, position_x, bias, entry_sp, cell_d0):
    """006442 (bias=0x180, "ahead")/006468 (bias=0, "here"): cost, outcome (True = found/open),
    exit D0/D1 and stack residue of the SAME shape `game.player._row_gate_open` computes.
    `entry_sp` is A7 as this routine's own `rts` will see it (i.e. AFTER the caller's own OUTER
    bsr.w $6442/$6468 push, `_S9_BSR_ROWGATE` -- the caller's own concern); this only writes the
    residue of the INNER bsr.b $63fa (`entry_sp - 4`).  `cell_d0` is the INNER grid_cell call's own
    D0 (the column) -- the direct-match arm never overwrites it again; the low-bits arm does
    (`move.w f18c,d0; andi.w #1f,d0`, `position_x & 0x1F`).  D1 is 0 unless found (1)."""
    cycles, instructions = _add(_S9_ROW_INNER_BSR, GRID_CELL_COST, _S9_ROW_MOVEQ0, _S9_ROW_TEST0[bias])
    order = dict(_bytes((entry_sp - 4) & 0xFFFFFF, _S9_ROW_INNER_RETURN[bias], 4))
    if read((address + bias) & 0xFFFFFF, 1) == 1:
        c, i = _add(_S9_ROW_BEQ0[True], _S9_ROW_MOVEQ1, _S9_ROW_RTS)
        return cycles + c, instructions + i, True, order, cell_d0
    c, i = _add(_S9_ROW_BEQ0[False], _S9_ROW_LOWHEAD)
    cycles += c
    instructions += i
    low_d0 = position_x & 0x1F
    if (position_x & 0x1E) < 8:
        c, i = _add(_S9_ROW_BLT[True], _S9_ROW_RTS)
        return cycles + c, instructions + i, False, order, low_d0
    c, i = _add(_S9_ROW_BLT[False], _S9_ROW_TEST1)
    cycles += c
    instructions += i
    found = read((address + bias + 1) & 0xFFFFFF, 1) == 1
    if found:
        c, i = _add(_S9_ROW_BNE1[False], _S9_ROW_MOVEQ1, _S9_ROW_RTS)
    else:
        c, i = _add(_S9_ROW_BNE1[True], _S9_ROW_RTS)
    return cycles + c, instructions + i, found, order, low_d0


def _state9_head_cost(read, d7):
    """0066A8-0066D2: `_state9_head`'s own cost, exit d7 (plain, not yet merged with any upper
    half -- the caller does that) and how (see `game.player._state9_head`'s own docstring)."""
    from .game import player
    new_d7, source = player._state9_head(read, d7)
    if d7 == 0xC:
        f19c_taken = new_d7 != d7
        c, i = _add(_S9_HEAD_CMPI_C, _S9_HEAD_BNE_C[False], _S9_HEAD_CMPI_F19C, _S9_HEAD_BLT[not f19c_taken])
        if f19c_taken:
            c, i = _add((c, i), _S9_HEAD_MOVEQ5, _S9_HEAD_BRA)
        return c, i, new_d7, source
    if d7 == 5:
        c, i = _add(_S9_HEAD_CMPI_C, _S9_HEAD_BNE_C[True], _S9_HEAD_CMPI_5, _S9_HEAD_BEQ_5[True])
        return c, i, new_d7, source
    if d7 == 0:
        f19c_taken = new_d7 != d7
        c, i = _add(_S9_HEAD_CMPI_C, _S9_HEAD_BNE_C[True], _S9_HEAD_CMPI_5, _S9_HEAD_BEQ_5[False],
                    _S9_HEAD_TST, _S9_HEAD_BNE_0[False], _S9_HEAD_CMPI_F19C, _S9_HEAD_BLT[not f19c_taken])
        if f19c_taken:
            c, i = _add((c, i), _S9_HEAD_ADDQ4, _S9_HEAD_BRA)
        return c, i, new_d7, source
    c, i = _add(_S9_HEAD_CMPI_C, _S9_HEAD_BNE_C[True], _S9_HEAD_CMPI_5, _S9_HEAD_BEQ_5[False],
                _S9_HEAD_TST, _S9_HEAD_BNE_0[True], _S9_HEAD_MOVEQ5)
    return c, i, new_d7, source


def state9_plan(machine, registers):
    """0066A8 (state 9): the player state machine's own dispatch table entry 9, a falling/jump-arc
    physics dispatcher.  See `game.player`'s own module note above the state 9 section for the shape.
    Every terminal arm ends at `pc = 0x0075D6` (the shared tail's own gate)."""
    from .game import player
    if registers['pc'] != STATE9_ENTRY:
        raise UnsupportedCandidate('state 9 planner needs the machine parked at 0066A8')
    read = _reader(machine)
    sr = registers['sr']
    entry_d7 = registers['d7'] & 0xFFFF
    sp32 = registers['a7']
    order = {}

    hc, hi, d7, source = _state9_head_cost(read, entry_d7)
    cycles, instructions = hc, hi
    if source == 'addq':
        sr = _add_sr(sr, entry_d7, 4, 2)   # 0066CC addq.w #4,d7

    from .game.grid import grid_cell
    c, i = _S9_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0066D6, 4))   # 0066D2 bsr.w $63fa's own return site
    cell1 = grid_cell(read)
    address = cell1['address']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)
    position_x = read(player.POSITION_X, 2)
    low5 = position_x & 0x1F
    exit_registers = {'a0': cell1['address'] & 0xFFFFFFFF,
                       'd0': (registers['d0'] & 0xFFFF0000) | cell1['d0'],
                       'd1': (registers['d1'] & 0xFFFF0000) | cell1['d1']}

    c, i = _S9_P1_HEAD
    cycles += c
    instructions += i
    blocked = False
    if low5 < 8:
        c, i = _S9_P1_BGE[False]
        cycles += c
        instructions += i
        for offset in (1, 0x81, 0x101):
            c, i = _S9_P1_GRIDTEST
            cycles += c
            instructions += i
            hit = read((address + offset) & 0xFFFFFF, 1) == 1
            c, i = _S9_P1_GRIDBEQ[hit]
            cycles += c
            instructions += i
            if hit:
                blocked = True
                break
    else:
        c, i = _S9_P1_BGE[True]
        cycles += c
        instructions += i

    advanced = False
    if not blocked:
        f19c = read(player.F19C, 2)
        c, i = _S9_P1_CMPI_F19C
        cycles += c
        instructions += i
        advanced = f19c >= player.STATE9_ADVANCE_GATE
        c, i = _S9_P1_BLT[not advanced]
        cycles += c
        instructions += i
        if advanced:
            c, i = _S9_P1_ADVANCE
            cycles += c
            instructions += i
            step = read(player.F196, 2)
            sr = _add_sr(sr, position_x, step, 2)   # 006708 add.w d0,f18c.w
            position_x = (position_x + step) & 0xFFFF
            order.update({a: b for a, b in _bytes(player.POSITION_X, position_x, 2)})

    c, i = _S9_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006710, 4))   # 00670C bsr.w $63fa's own return site
    if advanced:
        def _read_after_advance(a, s, _position_x=position_x):
            return _position_x if (a & 0xFFFFFF) == (player.POSITION_X & 0xFFFFFF) else read(a, s)
        cell2 = grid_cell(_read_after_advance)
    else:
        cell2 = grid_cell(read)
    address2 = cell2['address']
    sr = _asl_sr(sr, cell2['row_source'], 3, 2)
    exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell2['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell2['d1']

    c, i = _S9_L_TST_EA1E
    cycles += c
    instructions += i
    ea1e = player._signed_word(read(player.EA1E_WORD, 2))
    tracked_x = read(player.F19A, 2)
    c, i = _S9_L_BPL[ea1e >= 0]
    cycles += c
    instructions += i

    if ea1e < 0:
        c, i = _S9_A_MOVE_D0
        cycles += c
        instructions += i
        f196 = read(player.F196, 2)
        c, i = _S9_A_TST_F196
        cycles += c
        instructions += i
        # 00671E beq.b $6726: F196 == 0 SKIPS the tracked-X test below (falling straight into the
        # low-bits/cell test) -- it does NOT decline by itself (a real trace outside the original
        # survey caught a real landing with F196 == 0, 18 September).
        c, i = _S9_A_BEQ_F196[f196 == 0]
        cycles += c
        instructions += i
        landing = False
        blocked = False
        if f196 != 0:
            c, i = _S9_A_CMP_F19A
            cycles += c
            instructions += i
            blocked = position_x == tracked_x
            c, i = _S9_A_BEQ_F19A[blocked]
            cycles += c
            instructions += i
        if not blocked:
            c, i = _S9_A_ANDI_1F
            cycles += c
            instructions += i
            c, i = _S9_A_BNE_LOW[(position_x & 0x1F) != 0]
            cycles += c
            instructions += i
            if (position_x & 0x1F) == 0:
                c, i = _S9_A_CMPI_CELL
                cycles += c
                instructions += i
                cell_byte = read(address2 & 0xFFFFFF, 1)
                c, i = _S9_A_BNE_CELL[cell_byte != 2]
                cycles += c
                instructions += i
                landing = cell_byte == 2
        if landing:
            c, i = _S9_A_LANDING_TAIL
            cycles += c
            instructions += i
            new_x = position_x & 0xFFE0
            new_y = read(player.POSITION_Y, 2) & 0xFFF8
            for a, b in _bytes(player.POSITION_X, new_x, 2):
                order[a] = b
            for a, b in _bytes(player.POSITION_Y, new_y, 2):
                order[a] = b
            for a, b in _bytes(player.F1A8 & 0xFFFFFF, 0, 2):
                order[a] = b
            for a, b in _bytes(player.STATE_INDEX, 0xE, 2):
                order[a] = b
            for a, b in _bytes(player.F1AE & 0xFFFFFF, 0, 2):
                order[a] = b
            for a, b in _bytes(player.F1A4 & 0xFFFFFF, 0, 2):
                order[a] = b
            for a, b in _bytes(player.F1A6 & 0xFFFFFF, 0, 2):
                order[a] = b
            # 006726 andi.w #1f,d0 is D0's own last write on this arm (position_x & 0x1F, which the
            # landing gate above already proved is 0) -- overwrites cell2's own d0 (the column).
            exit_registers['d0'] = registers['d0'] & 0xFFFF0000
            exit_registers['d7'] = 2   # moveq #2,d7: a full 32-bit clear
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 006752 clr.w f1a6.w is the last flag-setter
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x006756)
        # Arm A's own decline (any sub-reason) falls straight into arm B's own head (0x675A), which
        # re-tests the SAME already-negative EA1E ("cmpi.w #1,ea1e.w; bne.b") -- always declines
        # again immediately, since EA1E < 0 can never equal 1 -- before reaching 0x67A8.  Caught by a
        # real trace whose own cycle/instruction total was short by exactly this pair.
        c, i = _add(_S9_B_CMPI_EA1E, _S9_B_BNE_EA1E[True])
        cycles += c
        instructions += i
    else:
        c, i = _S9_B_CMPI_EA1E
        cycles += c
        instructions += i
        c, i = _S9_B_BNE_EA1E[ea1e != 1]
        cycles += c
        instructions += i
        if ea1e == 1:
            c, i = _S9_B_MOVE_D0
            cycles += c
            instructions += i
            c, i = _S9_B_CMP_F19A
            cycles += c
            instructions += i
            c, i = _S9_B_BEQ_F19A[position_x == tracked_x]
            cycles += c
            instructions += i
            if position_x != tracked_x:
                c, i = _S9_B_ANDI_1F
                cycles += c
                instructions += i
                low_zero = (position_x & 0x1F) == 0
                c, i = _S9_B_BNE_LOW[not low_zero]
                cycles += c
                instructions += i
                if low_zero:
                    raise UnsupportedCandidate('state 9 landing-13 (transition to state 13) not witnessed by a recording')

    # Neither landing check fired: the ground-ahead probe, before the fall step.
    f19c = read(player.F19C, 2)
    c, i = _S9_G_CMPI_F19C
    cycles += c
    instructions += i
    trigger_gate_before = f19c >= player.STATE9_TRIGGER_GATE
    c, i = _S9_G_BLT[not trigger_gate_before]
    cycles += c
    instructions += i
    found_before = False
    if trigger_gate_before:
        c, i = _S9_BSR_ROWGATE
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0067B4, 4))   # 0067B0 bsr.w $6442's own return site
        rc, ri, found_before, rowgate_order, rowgate_d0 = _row_gate_cost(
            read, address2, position_x, 0x180, sp32 - 4, cell2['d0'])
        cycles += rc
        instructions += ri
        order.update(rowgate_order)
        exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
        exit_registers['d1'] = 1 if found_before else 0   # moveq #0/#1,d1: a full 32-bit clear
        sr = _asl_sr(sr, cell2['row_source'], 3, 2)
        c, i = _S9_G_TST_D1
        cycles += c
        instructions += i
        c, i = _S9_G_BEQ_D1[not found_before]
        cycles += c
        instructions += i

    if found_before:
        c, i = _S9_GROUND_TAIL
        cycles += c
        instructions += i
        original_y = read(player.POSITION_Y, 2)
        stores = player._state9_ground_stores(original_y)
        for a, b in _bytes(player.STATE_INDEX, stores[player.STATE_INDEX][0], 2):
            order[a] = b
        for a, b in _bytes(player.POSITION_Y, stores[player.POSITION_Y][0], 2):
            order[a] = b
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x39, 2)   # 0067CA move.w #$39,fdf6.w is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0067D0)

    # The fall step.
    c, i = _add(_S9_D_LEA, _S9_D_MOVE_F19C, _S9_D_TABLE_READ)
    cycles += c
    instructions += i
    exit_registers['a1'] = player.STATE9_FALL_TABLE & 0xFFFFFFFF   # 0067D4 lea.l $6414(pc),a1: never touched again
    if f19c > player.STATE9_FALL_TABLE_LIMIT:
        raise UnsupportedCandidate('state 9 fall table index past its own last entry (F19E path) not witnessed')
    step = player._signed_word(read((player.STATE9_FALL_TABLE + f19c) & 0xFFFFFF, 2))
    original_y = read(player.POSITION_Y, 2)
    c, i = _S9_D_SUB
    cycles += c
    instructions += i
    sr = _sub_sr(sr, original_y, step & 0xFFFF, 2)
    new_y = (original_y - step) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    c, i = _S9_D_TST_F19E
    cycles += c
    instructions += i
    if read(player.F19E, 2) != 0:
        raise UnsupportedCandidate('state 9 doubled fall step (FFFFF19E != 0) not witnessed by a recording')
    c, i = _S9_D_BEQ_F19E[True]
    cycles += c
    instructions += i

    c, i = _S9_BSR_ROWGATE
    cycles += c
    instructions += i
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0067F2, 4))   # 0067EE bsr.w $6468's own return site

    def _read_after_fall(a, s, _new_y=new_y, _position_x=position_x):
        masked = a & 0xFFFFFF
        if masked == (player.POSITION_Y & 0xFFFFFF):
            return _new_y
        if masked == (player.POSITION_X & 0xFFFFFF):
            return _position_x
        return read(a, s)
    cell3 = grid_cell(_read_after_fall)
    address3 = cell3['address']
    rc, ri, found_landed, rowgate_order, rowgate_d0 = _row_gate_cost(
        read, address3, position_x, 0, sp32 - 4, cell3['d0'])
    cycles += rc
    instructions += ri
    order.update(rowgate_order)
    exit_registers['a0'] = cell3['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
    exit_registers['d1'] = 1 if found_landed else 0   # moveq #0/#1,d1: a full 32-bit clear
    sr = _asl_sr(sr, cell3['row_source'], 3, 2)
    c, i = _S9_G_TST_D1
    cycles += c
    instructions += i
    c, i = _S9_D_BNE_D1[not found_landed]
    cycles += c
    instructions += i

    if found_landed:
        c, i = _S9_LANDED_TAIL
        cycles += c
        instructions += i
        masked_y = new_y & 0xFFF0
        sr = _add_sr(sr, masked_y, 0x10, 2)   # 0067FC addi.w #$10,f18e.w
        new_y_aligned = (masked_y + 0x10) & 0xFFFF
        for a, b in _bytes(player.POSITION_Y, new_y_aligned, 2):
            order[a] = b
        for a, b in _bytes(player.STATE_INDEX, 0xC, 2):
            order[a] = b
        for a, b in _bytes(player.F194 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(player.F1A0 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(player.F198 & 0xFFFFFF, 0, 2):
            order[a] = b
        c, i = _add(_S9_LANDED_MOVEQ, _S9_LANDED_BRA)
        cycles += c
        instructions += i
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 006814 moveq #0,d7 is the last flag-setter (Z=1)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006816)

    # The re-check ground-ahead probe, at the new position.
    c, i = _S9_G_CMPI_F19C
    cycles += c
    instructions += i
    trigger_gate_after = f19c >= player.STATE9_TRIGGER_GATE
    c, i = _S9_G_BLT[not trigger_gate_after]
    cycles += c
    instructions += i
    found_after = False
    if trigger_gate_after:
        c, i = _S9_BSR_ROWGATE
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006826, 4))   # 006822 bsr.w $6442's own return site
        rc, ri, found_after, rowgate_order, rowgate_d0 = _row_gate_cost(
            read, address3, position_x, 0x180, sp32 - 4, cell3['d0'])
        cycles += rc
        instructions += ri
        order.update(rowgate_order)
        exit_registers['a0'] = cell3['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
        exit_registers['d1'] = 1 if found_after else 0   # moveq #0/#1,d1: a full 32-bit clear
        sr = _asl_sr(sr, cell3['row_source'], 3, 2)
        c, i = _S9_G_TST_D1
        cycles += c
        instructions += i
        c, i = _S9_G2_BNE_D1[found_after]
        cycles += c
        instructions += i

    if found_after:
        c, i = _S9_GROUND_TAIL
        cycles += c
        instructions += i
        stores = player._state9_ground_stores(new_y)
        for a, b in _bytes(player.STATE_INDEX, stores[player.STATE_INDEX][0], 2):
            order[a] = b
        for a, b in _bytes(player.POSITION_Y, stores[player.POSITION_Y][0], 2):
            order[a] = b
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x39, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0067D0)

    # The trigger gate / countdown tail.
    c, i = _S9_T_CMPI_F19C_4
    cycles += c
    instructions += i
    advance_gate_open = f19c >= player.STATE9_ADVANCE_GATE
    c, i = _S9_T_BLT[not advance_gate_open]
    cycles += c
    instructions += i
    found_trigger = False
    if advance_gate_open:
        c, i = _S9_T_BTST
        cycles += c
        instructions += i
        bit2 = read(player.EA23_WORD, 1) & 4
        c, i = _S9_T_BEQ_BIT2[not bit2]
        cycles += c
        instructions += i
        if bit2:
            c, i = _S9_BSR_SEARCH
            cycles += c
            instructions += i
            sp32 = registers['a7']
            for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x00683E, 4):
                order[a] = b
            cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
                machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4, 'sr': sr}, sp32 - 4)
            cycles += cs_cycles
            instructions += cs_instructions
            order.update(cs_order)
            exit_registers.update(cs_registers)
            sr = cs_registers['sr']
            c, i = _S9_T_TST_D0
            cycles += c
            instructions += i
            found_search = cs_result['d0'] == 0
            c, i = _S9_T_BNE_D0[not found_search]
            cycles += c
            instructions += i
            if found_search:
                c, i = _S9_T_CMPI_2C
                cycles += c
                instructions += i
                too_late = f19c >= player.STATE9_TRIGGER_CAP
                c, i = _S9_T_BGE_2C[too_late]
                cycles += c
                instructions += i
                found_trigger = not too_late

    if found_trigger:
        c, i = _S9_TRIGGER_TAIL
        cycles += c
        instructions += i
        new_f19c = (f19c + 2) & 0xFFFF
        sr = _add_sr(sr, f19c, 2, 2)   # 006858 addq.w #2,f19c.w is the last flag-setter
        for a, b in _bytes(player.STATE_INDEX, 0x14, 2):
            order[a] = b
        for a, b in _bytes(player.F1BA & 0xFFFFFF, 1, 2):
            order[a] = b
        for a, b in _bytes(player.F19C & 0xFFFFFF, new_f19c, 2):
            order[a] = b
        exit_registers['d7'] = 1   # moveq #1,d7: a full 32-bit clear
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, new_f19c, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00685C)

    c, i = _S9_COUNTDOWN_ADDQ
    cycles += c
    instructions += i
    new_f19c = (f19c + 2) & 0xFFFF
    sr = _add_sr(sr, f19c, 2, 2)   # 006860 addq.w #2,f19c.w
    for a, b in _bytes(player.F19C & 0xFFFFFF, new_f19c, 2):
        order[a] = b
    c, i = _S9_COUNTDOWN_CMPI
    cycles += c
    instructions += i
    terminal = new_f19c >= player.STATE9_COUNTDOWN_CAP
    c, i = _S9_COUNTDOWN_BLT[not terminal]
    cycles += c
    instructions += i

    if not terminal:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _cmp_sr(sr, new_f19c, player.STATE9_COUNTDOWN_CAP, 2)   # the cmpi.w itself
        if source == 'untouched':
            pass   # D7 genuinely untouched by this whole activation: leave the caller's own register
        elif source == 'moveq':
            exit_registers['d7'] = d7   # a full 32-bit clear (5)
        else:   # 'addq': a word op, the entry's own upper half survives
            exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | d7
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00686A)

    c, i = _S9_TERMINAL_TAIL
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, 0xC, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, 0, 2):
        order[a] = b
    for a, b in _bytes(player.F1A0 & 0xFFFFFF, 0, 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, 0, 2):
        order[a] = b
    exit_registers['d7'] = 0   # moveq #0,d7: a full 32-bit clear
    exit_registers['pc'] = 0x0075D6
    # 006880's own moveq #0,d7 is the LAST flag-setter on this arm (Z=1), not the earlier move.w
    # #$c,f192.w -- caught by a real trace whose own exit CCR still had Z set.
    exit_registers['sr'] = _logic_sr(sr, 0, 2)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x006882)


# --- 0069AC: state 26 (game.player.state26_step / state26_tail) -- a near-twin of state 9's own
# shape, reusing its own row-gate cost helper (`_row_gate_cost`) and jump-arc table constants
# verbatim; only the head, the always-on X-advance and the tail differ (see the module note in
# game/player.py above `state26_step`).  Costed from the tracer on real fixtures over
# `census-0069AC-*` covering every witnessed arm, 18 September; every shared block's own cost
# already matched state 9's own constants exactly (confirmed, not assumed).
STATE26_ENTRY = 0x0069AC

_S26_TST_F1BA = (12, 1)                     # 0069AC tst.w f1ba.w
_S26_BEQ_F1BA = {True: (10, 1), False: (8, 1)}      # beq.b -- taken: F1BA == 0 (the addq.w branch)
_S26_SUBQ1 = (4, 1)                         # 0069B2 subq.w #1,d7
_S26_CLR_F1BA = (16, 1)                     # 0069B4 clr.w f1ba.w
_S26_HEAD_BRA = (10, 1)                     # 0069B8 bra.b $69bc
_S26_ADDQ1 = (4, 1)                         # 0069BA addq.w #1,d7

_S26_TAIL_CMPI3 = (8, 1)                    # 006A72 cmpi.w #3,d7
_S26_TAIL_BLT3 = {True: (10, 1), False: (8, 1)}     # blt.b -- taken: D7 < 3 (the consume/wait tail)
_S26_TO9_MOVEQ5 = (4, 1)                    # 006A78 moveq #5,d7
_S26_TO9_MOVE_STATE = (16, 1)               # 006A7A move.w #9,f192.w
_S26_CONSUME_CMPI1 = (8, 1)                 # 006AA6 cmpi.w #1,d7
_S26_CONSUME_BNE1 = {True: (10, 1), False: (8, 1)}  # bne.b -- taken: D7 != 1, skip the jsr
_S26_BEQ_LANDED_WORD = {True: (10, 1), False: (12, 1)}  # 006A3A beq.w -- a word branch, unlike state 9's own $6468 landed check


def state26_plan(machine, registers):
    """0069AC (state 26): the player state machine's own dispatch table entry 26.  See game/player.py's
    own module note above `state26_step` for the shape and its three real differences from state 9's
    own.  Every terminal arm ends at `pc = 0x0075D6`."""
    from .game import player
    if registers['pc'] != STATE26_ENTRY:
        raise UnsupportedCandidate('state 26 planner needs the machine parked at 0069AC')
    read = _reader(machine)
    sr = registers['sr']
    entry_d7 = registers['d7'] & 0xFFFF
    sp32 = registers['a7']
    order = {}

    f1ba_set = read(player.F1BA, 2) != 0
    c, i = _S26_TST_F1BA
    cycles, instructions = c, i
    c, i = _S26_BEQ_F1BA[not f1ba_set]
    cycles += c
    instructions += i
    if f1ba_set:
        c, i = _add(_S26_SUBQ1, _S26_CLR_F1BA, _S26_HEAD_BRA)
        cycles += c
        instructions += i
        sr = _sub_sr(sr, entry_d7, 1, 2)   # 0069B2 subq.w #1,d7
        d7 = (entry_d7 - 1) & 0xFFFF
        for a, b in _bytes(player.F1BA & 0xFFFFFF, 0, 2):
            order[a] = b
    else:
        c, i = _S26_ADDQ1
        cycles += c
        instructions += i
        sr = _add_sr(sr, entry_d7, 1, 2)   # 0069BA addq.w #1,d7
        d7 = (entry_d7 + 1) & 0xFFFF

    from .game.grid import grid_cell
    c, i = _S9_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0069C0, 4))   # 0069BC bsr.w $63fa's own return site
    cell1 = grid_cell(read)
    address = cell1['address']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)
    position_x = read(player.POSITION_X, 2)
    low5 = position_x & 0x1F
    exit_registers = {'a0': cell1['address'] & 0xFFFFFFFF,
                       'd0': (registers['d0'] & 0xFFFF0000) | cell1['d0'],
                       'd1': (registers['d1'] & 0xFFFF0000) | cell1['d1']}

    c, i = _S9_P1_HEAD
    cycles += c
    instructions += i
    blocked = False
    if low5 < 8:
        c, i = _S9_P1_BGE[False]
        cycles += c
        instructions += i
        for offset in (1, 0x81, 0x101):
            c, i = _S9_P1_GRIDTEST
            cycles += c
            instructions += i
            hit = read((address + offset) & 0xFFFFFF, 1) == 1
            c, i = _S9_P1_GRIDBEQ[hit]
            cycles += c
            instructions += i
            if hit:
                blocked = True
                break
    else:
        c, i = _S9_P1_BGE[True]
        cycles += c
        instructions += i

    if not blocked:
        c, i = _S9_P1_ADVANCE
        cycles += c
        instructions += i
        step = read(player.F196, 2)
        sr = _add_sr(sr, position_x, step, 2)   # 0069EA add.w d0,f18c.w
        position_x = (position_x + step) & 0xFFFF
        order.update(_bytes(player.POSITION_X, position_x, 2))
    # Unlike state 9, state 26 does NOT re-read the grid cell after the X-advance: 0069EE's own
    # cmpi.w #$16,f19c.w follows the add.w directly, with no second bsr.w $63fa in between (a real
    # defect an earlier draft introduced by assuming state 9's own two-call shape here; the FAST
    # tier's own cost mismatch caught it before any of this reached the tree).  The ground-ahead
    # probe below runs on the SAME cell (`cell1`/`address`) the head's own single grid_cell call
    # already computed, even though POSITION_X may have just moved.
    address2, cell2 = address, cell1

    f19c = read(player.F19C, 2)
    c, i = _S9_G_CMPI_F19C
    cycles += c
    instructions += i
    trigger_gate_before = f19c >= player.STATE9_TRIGGER_GATE
    c, i = _S9_G_BLT[not trigger_gate_before]
    cycles += c
    instructions += i
    found_before = False
    if trigger_gate_before:
        c, i = _S9_BSR_ROWGATE
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0069FA, 4))   # 0069F6 bsr.w $6442's own return site
        rc, ri, found_before, rowgate_order, rowgate_d0 = _row_gate_cost(
            read, address2, position_x, 0x180, sp32 - 4, cell2['d0'])
        cycles += rc
        instructions += ri
        order.update(rowgate_order)
        exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
        exit_registers['d1'] = 1 if found_before else 0   # moveq #0/#1,d1: a full 32-bit clear
        sr = _asl_sr(sr, cell2['row_source'], 3, 2)
        c, i = _S9_G_TST_D1
        cycles += c
        instructions += i
        c, i = _S9_G_BEQ_D1[not found_before]
        cycles += c
        instructions += i

    if found_before:
        c, i = _S9_GROUND_TAIL
        cycles += c
        instructions += i
        original_y = read(player.POSITION_Y, 2)
        stores = player._state9_ground_stores(original_y)
        for a, b in _bytes(player.STATE_INDEX, stores[player.STATE_INDEX][0], 2):
            order[a] = b
        for a, b in _bytes(player.POSITION_Y, stores[player.POSITION_Y][0], 2):
            order[a] = b
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x39, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006A16)

    c, i = _add(_S9_D_LEA, _S9_D_MOVE_F19C, _S9_D_TABLE_READ)
    cycles += c
    instructions += i
    exit_registers['a1'] = player.STATE9_FALL_TABLE & 0xFFFFFFFF
    if f19c > player.STATE9_FALL_TABLE_LIMIT:
        raise UnsupportedCandidate('state 26 fall table index past its own last entry (F19E path) not witnessed')
    step = player._signed_word(read((player.STATE9_FALL_TABLE + f19c) & 0xFFFFFF, 2))
    original_y = read(player.POSITION_Y, 2)
    c, i = _S9_D_SUB
    cycles += c
    instructions += i
    sr = _sub_sr(sr, original_y, step & 0xFFFF, 2)
    new_y = (original_y - step) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    c, i = _S9_D_TST_F19E
    cycles += c
    instructions += i
    if read(player.F19E, 2) != 0:
        raise UnsupportedCandidate('state 26 doubled fall step (FFFFF19E != 0) not witnessed by a recording')
    c, i = _S9_D_BEQ_F19E[True]
    cycles += c
    instructions += i

    c, i = _S9_BSR_ROWGATE
    cycles += c
    instructions += i
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006A38, 4))   # 006A34 bsr.w $6468's own return site

    def _read_after_fall(a, s, _new_y=new_y, _position_x=position_x):
        masked = a & 0xFFFFFF
        if masked == (player.POSITION_Y & 0xFFFFFF):
            return _new_y
        if masked == (player.POSITION_X & 0xFFFFFF):
            return _position_x
        return read(a, s)
    cell3 = grid_cell(_read_after_fall)
    address3 = cell3['address']
    rc, ri, found_landed, rowgate_order, rowgate_d0 = _row_gate_cost(
        read, address3, position_x, 0, sp32 - 4, cell3['d0'])
    cycles += rc
    instructions += ri
    order.update(rowgate_order)
    exit_registers['a0'] = cell3['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
    exit_registers['d1'] = 1 if found_landed else 0
    sr = _asl_sr(sr, cell3['row_source'], 3, 2)
    c, i = _S9_G_TST_D1
    cycles += c
    instructions += i
    # 006A3A beq.w $6a62 -- a WORD-displacement branch here (unlike state 9's own byte-displacement
    # 0067F4), so its own not-taken cost is 12, not 8.
    c, i = _S26_BEQ_LANDED_WORD[not found_landed]
    cycles += c
    instructions += i

    if found_landed:
        c, i = _S9_LANDED_TAIL
        cycles += c
        instructions += i
        masked_y = new_y & 0xFFF0
        sr = _add_sr(sr, masked_y, 0x10, 2)   # addi.w #$10,f18e.w
        new_y_aligned = (masked_y + 0x10) & 0xFFFF
        for a, b in _bytes(player.POSITION_Y, new_y_aligned, 2):
            order[a] = b
        for a, b in _bytes(player.STATE_INDEX, 0xC, 2):
            order[a] = b
        for a, b in _bytes(player.F194 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(player.F1A0 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(player.F198 & 0xFFFFFF, 0, 2):
            order[a] = b
        c, i = _add(_S9_LANDED_MOVEQ, _S9_LANDED_BRA)
        cycles += c
        instructions += i
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006A5E)

    c, i = _S9_G_CMPI_F19C
    cycles += c
    instructions += i
    recheck_gate_open = f19c >= player.STATE26_RECHECK_GATE
    c, i = _S9_G_BLT[not recheck_gate_open]
    cycles += c
    instructions += i
    found_after = False
    if recheck_gate_open:
        c, i = _S9_BSR_ROWGATE
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006A6E, 4))   # 006A6A bsr.w $6442's own return site
        rc, ri, found_after, rowgate_order, rowgate_d0 = _row_gate_cost(
            read, address3, position_x, 0x180, sp32 - 4, cell3['d0'])
        cycles += rc
        instructions += ri
        order.update(rowgate_order)
        exit_registers['a0'] = cell3['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
        exit_registers['d1'] = 1 if found_after else 0
        sr = _asl_sr(sr, cell3['row_source'], 3, 2)
        c, i = _S9_G_TST_D1
        cycles += c
        instructions += i
        c, i = _S9_G2_BNE_D1[found_after]
        cycles += c
        instructions += i

    if found_after:
        c, i = _S9_GROUND_TAIL
        cycles += c
        instructions += i
        stores = player._state9_ground_stores(new_y)
        for a, b in _bytes(player.STATE_INDEX, stores[player.STATE_INDEX][0], 2):
            order[a] = b
        for a, b in _bytes(player.POSITION_Y, stores[player.POSITION_Y][0], 2):
            order[a] = b
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x39, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006A16)

    # The D7-based tail: at/past 3 hands straight off into state 9; short of 3, D7 == 1 also calls
    # the already-recovered contact-consume primary first.
    c, i = _S26_TAIL_CMPI3
    cycles += c
    instructions += i
    to_state9 = d7 >= player.STATE26_TO_STATE9_COUNTER
    c, i = _S26_TAIL_BLT3[not to_state9]
    cycles += c
    instructions += i

    if to_state9:
        c, i = _add(_S26_TO9_MOVEQ5, _S26_TO9_MOVE_STATE)
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, player.STATE26_TO_STATE9_STATE_INDEX, 2):
            order[a] = b
        d7 = player.STATE26_TO_STATE9_D7
        sr = _logic_sr(sr, player.STATE26_TO_STATE9_STATE_INDEX, 2)   # 006A7A move.w #9,f192.w
    else:
        c, i = _S26_CONSUME_CMPI1
        cycles += c
        instructions += i
        calls_consumer = d7 == player.STATE26_CONSUME_COUNTER
        c, i = _S26_CONSUME_BNE1[not calls_consumer]
        cycles += c
        instructions += i
        if calls_consumer:
            c, i = _S5_JSR_CONSUME
            cycles += c
            instructions += i
            for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x006AB2, 4):
                order[a] = b
            # POSITION_X/POSITION_Y already carry this activation's own X-advance and fall step
            # (above); 012DA0's own _consume_position reads GRID_X/GRID_Y live, so it must see those
            # values too, not the machine's own (pre-advance / pre-fall) ones.
            def _read_for_consume(a, s, _position_x=position_x, _new_y=new_y):
                masked = a & 0xFFFFFF
                if masked == (player.POSITION_X & 0xFFFFFF):
                    return _position_x
                if masked == (player.POSITION_Y & 0xFFFFFF):
                    return _new_y
                return read(a, s)
            cc_cycles, cc_instructions, cc_order, cc_registers, _ = _cc_resolve(
                machine, _read_for_consume, registers, 0, sp32 - 4)
            cycles += cc_cycles
            instructions += cc_instructions
            order.update(cc_order)
            exit_registers.update(cc_registers)

    c, i = _S9_COUNTDOWN_ADDQ
    cycles += c
    instructions += i
    new_f19c = (f19c + 2) & 0xFFFF
    sr = _add_sr(sr, f19c, 2, 2)   # ...'s own addq.w #2,f19c.w
    for a, b in _bytes(player.F19C & 0xFFFFFF, new_f19c, 2):
        order[a] = b
    c, i = _S9_COUNTDOWN_CMPI
    cycles += c
    instructions += i
    terminal = new_f19c >= player.STATE9_COUNTDOWN_CAP
    c, i = _S9_COUNTDOWN_BLT[not terminal]
    cycles += c
    instructions += i

    if not terminal:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _cmp_sr(sr, new_f19c, player.STATE9_COUNTDOWN_CAP, 2)
        if to_state9:
            exit_registers['d7'] = d7   # moveq #5,d7: a full 32-bit clear
        else:
            exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | d7   # a word op: the entry's own upper half survives
        last_pc = 0x006ABC if not to_state9 else 0x006A8A
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    c, i = _S9_TERMINAL_TAIL
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, 0xC, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, 0, 2):
        order[a] = b
    for a, b in _bytes(player.F1A0 & 0xFFFFFF, 0, 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, 0, 2):
        order[a] = b
    exit_registers['d7'] = 0
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = _logic_sr(sr, 0, 2)
    last_pc = 0x006AD4 if not to_state9 else 0x006AA2   # the terminal tail's own final bra.w $75d6
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=last_pc)


# --- 005724: the REAL STATE_TABLE index 26 (game.player.state_26_step and friends) -- not
# `STATE26_ENTRY`/`state26_plan` above, which target `0069AC` (real index 20; the misnomer, kept
# as-is: every gate and fixture is keyed by PC, not by name, `docs/gods/STATUS.md`'s own 18 September
# entries).  The tree's largest single decline (1,975 of 8,857 fallbacks) before this session; see
# game/player.py's own module note above `state_26_step` for the full arm breakdown and counts.
STATE_26_ENTRY = 0x005724

_S26_MOVEQ0_D7 = (4, 1)                        # 005724 moveq #0,d7
_S26_MOVEQ_D0 = (4, 1)                         # 005726 moveq #$1c,d0
_S26_TST_EA20 = (12, 1)                        # 005728 tst.w ea20.w
_S26_BEQ_EA20 = {True: (10, 1), False: (8, 1)}     # 00572C beq.b 573a (byte)
_S26_BPL_EA20 = {True: (10, 1), False: (8, 1)}     # 00572E bpl.b 5732 (byte, EA20 != 0 branch only)
_S26_MOVEQ_NEG = (4, 1)                        # 005730 moveq #$1b,d0 (EA20 < 0 only)
_S26_MOVE_STATE = (12, 1)                      # 005732 move.w d0,f192.w
_S26_BRA_TAIL = (10, 1)                        # bra.w 75d6 (every use: 005736/005746/0057BE/0057AC)

_S26_BTST_EA23 = (16, 1)                       # 00573A btst.b #2,ea23.w
_S26_BEQ_EA23 = {True: (10, 1), False: (8, 1)}     # 005740 beq.b 574a (byte)
_S26_BSR_8148 = (18, 1)                        # 005742 bsr.w 8148

_S26_CLR_F24A = (16, 1)                        # 00574A clr.w f24a.w
_S26_TST_EA1E = (12, 1)                        # 00574E tst.w ea1e.w
_S26_BPL_EA1E = {True: (10, 1), False: (12, 1)}    # 005752 bpl.w 6d68 (word)
_S26_BSR_57C2 = (18, 1)                        # 005756 bsr.w 57c2

_S26_TST_EF54 = (12, 1)                        # 00575A tst.w ef54.w
_S26_BNE_EF54 = {True: (10, 1), False: (12, 1)}    # 00575E bne.w 75d6 (word)
_S26_BSR_63FA = (18, 1)                        # 005762 bsr.w 63fa
_S26_LOAD_POSX = (12, 1)                       # 005766 move.w f18c.w,d0
_S26_ANDI_1F = (8, 1)                          # 00576A andi.w #$1f,d0
_S26_CMP_10 = (8, 1)                           # 00576E cmpi.w #$10,d0
_S26_BLT_10 = {True: (10, 1), False: (8, 1)}       # 005772 blt.b 57b0 (byte)

_S26_CMP_A0 = (12, 1)                          # 0057B0 cmpi.b #2,(a0)
_S26_BEQ_A0 = {True: (10, 1), False: (8, 1)}       # 0057B4 beq.b 578e (byte)
_S26_CMP_A0_80 = (16, 1)                       # 0057B6 cmpi.b #2,$80(a0)
_S26_BEQ_A0_80 = {True: (10, 1), False: (8, 1)}    # 0057BC beq.b 578e (byte)

_S26_CMP_A0_1 = (16, 1)                        # 005774 cmpi.b #2,$1(a0)
_S26_BNE_A0_1 = {True: (10, 1), False: (12, 1)}    # 00577A bne.w 75d6 (word)
_S26_CMP_A0_81 = (16, 1)                       # 00577E cmpi.b #2,$81(a0)
_S26_BNE_A0_81 = {True: (10, 1), False: (12, 1)}   # 005784 bne.w 75d6 (word)
_S26_ADDI_20 = (20, 1)                         # 005788 addi.w #$20,f18c.w (high-arm advance only)
_S26_ANDI_MASK = (20, 1)                       # 00578E andi.w #$ffe0,f18c.w
_S26_MOVE_STATE14 = (16, 1)                    # 005794 move.w #$e,f192.w
_S26_MOVEQ_1A = (4, 1)                         # 00579A moveq #$1a,d7
_S26_CLR_FIELD = (16, 1)                       # 00579C/A0/A4/A8 clr.w f1ae/f1a4/f1a6/f1a8.w (each)

_S26B_HEAD = (64, 10)                          # 0057C2-0057DC: the box scan's own fixed setup
_S26B_TEST_STATUS = (12, 1)                    # 0057DE tst.w $4(a0)
_S26B_BMI = {True: (10, 1), False: (8, 1)}         # 0057E2 bmi.b 5816 (byte)
_S26B_BEQ = {True: (10, 1), False: (8, 1)}         # 0057E4 beq.b 5816 (byte, only when bmi not taken)
_S26B_LOAD_X = (8, 1)                          # 0057E6 move.w (a0),d4
_S26B_LOAD_Y = (12, 1)                         # 0057E8 move.w $2(a0),d5
_S26B_CMP = (4, 1)
_S26B_COND_TAKEN = (10, 1)                     # blt/bgt taken -- the chain's own failing branch
_S26B_COND_PASS = (8, 1)                       # not taken -- continue the chain
_S26B_FOUND_STORE = (16 + 20 + 20 + 16, 4)     # move#1,ef54; move 4(a0),ef56; move 6(a0),ef58; move#$69,fdf6
_S26B_RTS = (16, 1)
_S26B_ADVANCE = (4, 1)                         # 005816 addq.w #8,a0
_S26B_DBRA_TAKEN = (10, 1)
_S26B_DBRA_LAST = (14, 1)

_S26A_TST_ACTIVE = (12, 1)                     # 008148 tst.w f24a.w
_S26A_BNE_ACTIVE = {True: (10, 1), False: (12, 1)}     # 00814C bne.w 81e8 (word)
_S26A_BTST_BUSY = (16, 1)                      # 008150 btst.b #2,f17c.w
_S26A_BNE_BUSY = {True: (10, 1), False: (12, 1)}       # 008156 bne.w 81e8 (word, never witnessed taken)
_S26A_TST_PENDING = (12, 1)                    # 00815A tst.w f248.w
_S26A_BPL_PENDING = {True: (10, 1), False: (12, 1)}    # 00815E bpl.w 81e8 (word, never witnessed taken)
_S26A_RTS_EARLY = (16, 1)                      # 0081E8 rts (already-active / busy / pending declines)
_S26A_SET_ACTIVE = (16, 1)                     # 008162 move.w #1,f24a.w
_S26A_LEA_TABLE = (12, 1)                      # 008168 lea.l $ffff4342.l,a0
_S26A_LOAD_COUNT = (8, 1)                      # 00816E move.w #$c7,d6

_S26A_TST_B = (12, 1)                          # 008172 tst.w $6(a0)
_S26A_BEQ_B = {True: (10, 1), False: (12, 1)}      # 008176 beq.w 81e2 (word)
_S26A_TST_A = (12, 1)                          # 00817A tst.w $4(a0)
_S26A_BMI_A = {True: (10, 1), False: (8, 1)}       # 00817E bmi.b 81e2 (byte, never witnessed taken)
_S26A_MOVEM = (24, 1)                          # 008180 movem.w (a0),d0-d2
_S26A_MOVE_D3 = (4, 1)                         # 008184 move.w d2,d3
_S26A_LEA_RECORD = (8, 1)                      # 008186 lea.l $f8c2.w,a1
_S26A_ADD_D3 = (4, 1)                          # 00818A/8E/90 add.w d3,d3 (x3)
_S26A_ADDA_D3 = (8, 1)                         # 00818C/92 adda.w d3,a1 (x2)
_S26A_CMP_KIND = (16, 1)                       # 008194 cmpi.w #3,$4(a1)
_S26A_BNE_KIND = {True: (10, 1), False: (8, 1)}    # 00819A bne.b 81e2 (byte)
_S26A_MOVEA_A3 = (4, 1)                        # 00819C movea.l a0,a3
_S26A_BSR_2E0A = (18, 1)                       # 00819E bsr.w 2e0a
_S26A_EXG = (6, 1)                             # 0081A2 exg.l a0,a3
_S26A_TST_D1 = (4, 1)                          # 0081A4 tst.w d1
_S26A_BMI_D1 = {True: (10, 1), False: (8, 1)}      # 0081A6 bmi.b 81e2 (byte, never witnessed taken)
_S26A_BSR_81EA = (18, 1)                       # 0081A8 bsr.b 81ea
_S26A_BMI_BOX = {True: (10, 1), False: (8, 1)}     # 0081AA bmi.b 81e2 (byte)
_S26A_ID_CMP = (12, 1)                         # 0081AC/B2/B8/BE cmpi.w #imm,(a1) (each)
_S26A_ID_BEQ = {True: (10, 1), False: (8, 1)}      # 0081B0/B6/BC beq.b 81c4 (byte)
_S26A_BNE_FINAL = {True: (10, 1), False: (8, 1)}   # 0081C2 bne.b 81ce (byte)
_S26A_MOVE_FOUND = (16, 1)                     # 0081C4 move.l a3,f24c.w
_S26A_CLR_PENDING = (16, 1)                    # 0081C8 clr.w f248.w
_S26A_BRA_SOUND = (10, 1)                      # 0081CC bra.b 81da
_S26A_EORI = (20, 1)                           # 0081CE/D4 eori.w #1,$4(a0)/$4(a3) (each)
_S26A_SOUND = (16, 1)                          # 0081DA move.w #$60,fdf4.w
_S26A_RTS = (16, 1)                            # 0081E0 rts
_S26A_ADVANCE = (4, 1)                         # 0081E2 addq.w #8,a0
_S26A_DBRA_TAKEN = (10, 1)
_S26A_DBRA_LAST = (14, 1)

_S26_ID_KEY_COST = (4 + 4 + 12 + 4, 4)         # 002E0A swap; move.w d1,d0; lea $ffff62f6.l,a0; moveq #$3f,d1
_S26_ID_CMP = (14, 1)                          # 002E16 cmp.l (a0),d0
_S26_ID_BEQ = {True: (10, 1), False: (8, 1)}       # 002E18 beq.b 2e24 (byte)
_S26_ID_ADVANCE = (4, 1)                       # 002E1A addq.w #6,a0
_S26_ID_DBRA_TAKEN = (10, 1)
_S26_ID_RTS = (16, 1)                          # 002E24 rts

_S26_BOX_LOAD_XY = (8 + 12, 2)                 # 0081EA move.w (a0),d0; 0081EC move.w $2(a0),d1
_S26_BOX_MOVEQ = (4 + 4, 2)                    # 0081F0/F2 moveq #$10,d2/d3
_S26_BOX_ADD = (4 + 4, 2)                      # 0081F4/F6 add.w d0,d2 / d1,d3
_S26_BOX_MOVEQ_C = (4, 1)                      # 0081F8 moveq #$c,d4
_S26_BOX_ADD_POSX = (12, 1)                    # 0081FA add.w f18c.w,d4
_S26_BOX_LOAD_POSY = (12, 1)                   # 0081FE move.w f18e.w,d5
_S26_BOX_CMP1 = (4, 1)                         # 008202 cmp.w d2,d4
_S26_BOX_BGT1 = {True: (10, 1), False: (8, 1)}     # 008204 bgt.b 821c (byte)
_S26_BOX_CMP2 = (4, 1)                         # 008206 cmp.w d3,d5
_S26_BOX_BGT2 = {True: (10, 1), False: (8, 1)}     # 008208 bgt.b 821c (byte)
_S26_BOX_ADDQ = (4, 1)                         # 00820A addq.w #8,d4
_S26_BOX_ADDI = (8, 1)                         # 00820C addi.w #$30,d5
_S26_BOX_CMP3 = (4, 1)                         # 008210 cmp.w d0,d4
_S26_BOX_BLT1 = {True: (10, 1), False: (8, 1)}     # 008212 blt.b 821c (byte)
_S26_BOX_CMP4 = (4, 1)                         # 008214 cmp.w d1,d5
_S26_BOX_BLT2 = {True: (10, 1), False: (8, 1)}     # 008216 blt.b 821c (byte)
_S26_BOX_PASS_EXIT = (14 + 20, 2)              # 008218 clr.w -(a7); 00821A rtr
_S26_BOX_FAIL_EXIT = (12 + 20, 2)              # 00821C move.w #8,-(a7); 008220 rtr


def _s26_box_entry_cost(step, is_last):
    """One entry's own cost through `game.player.state_26_box_scan`'s own 20-entry table, from its
    own tst.w $4(a0) through whichever tail (skip / found) it reaches."""
    cycles, instructions = _S26B_TEST_STATUS
    if step['arm'] in ('skip-negative', 'skip-zero'):
        neg = step['arm'] == 'skip-negative'
        c, i = _S26B_BMI[neg]
        cycles += c
        instructions += i
        if not neg:
            c, i = _S26B_BEQ[True]
            cycles += c
            instructions += i
        c, i = _S26B_DBRA_LAST if is_last else _S26B_DBRA_TAKEN
        return cycles + _S26B_ADVANCE[0] + c, instructions + _S26B_ADVANCE[1] + i
    c, i = _S26B_BMI[False]
    cycles += c
    instructions += i
    c, i = _S26B_BEQ[False]
    cycles += c
    instructions += i
    c, i = _S26B_LOAD_X
    cycles += c
    instructions += i
    c, i = _S26B_LOAD_Y
    cycles += c
    instructions += i
    for passed, is_last_test in ((step['pass_x_near'], False), (step['pass_x_far'], False),
                                 (step['pass_y_near'], False), (step['arm'] == 'found', True)):
        c, i = _S26B_CMP
        cycles += c
        instructions += i
        if not passed:
            c, i = _S26B_COND_TAKEN
            cycles += c
            instructions += i
            break
        if is_last_test:
            c, i = _S26B_COND_PASS   # the fourth test's own PASS falls straight into the store block
            cycles += c
            instructions += i
            c, i = _S26B_FOUND_STORE
            cycles += c
            instructions += i
            c, i = _S26B_RTS
            return cycles + c, instructions + i
        c, i = _S26B_COND_PASS
        cycles += c
        instructions += i
    c, i = _S26B_DBRA_LAST if is_last else _S26B_DBRA_TAKEN
    return cycles + _S26B_ADVANCE[0] + c, instructions + _S26B_ADVANCE[1] + i


def _s26_box_scan_cost(entries):
    from .game import player
    cycles, instructions = _S26B_HEAD
    for index, step in enumerate(entries):
        c, i = _s26_box_entry_cost(step, index == player.STATE_26_BOX_SCAN_COUNT - 1)
        cycles += c
        instructions += i
    if entries[-1]['arm'] != 'found':
        # 00581C's own rts: the found arm's own rts is already inside _s26_box_entry_cost's own
        # _S26B_FOUND_STORE/_S26B_RTS tail; the exhausted arm's own final rts is a standalone
        # instruction reached only once, after the last entry's own dbra falls through.
        c, i = _S26B_RTS
        cycles += c
        instructions += i
    return cycles, instructions


def _s26_id_search_cost(found_id):
    """002E0A: the 64-entry `conditions.FLAGGED` search's own cost, walking the SAME entries
    `game.player._state_26_id_search` reads to find `found_id` (or confirm it as the first match)."""
    from .game import conditions
    cycles, instructions = _S26_ID_KEY_COST
    entry_addr = conditions.FLAGGED
    while True:
        c, i = _S26_ID_CMP
        cycles += c
        instructions += i
        matched = entry_addr == found_id
        c, i = _S26_ID_BEQ[matched]
        cycles += c
        instructions += i
        if matched:
            c, i = _S26_ID_RTS
            return cycles + c, instructions + i
        c, i = _S26_ID_ADVANCE
        cycles += c
        instructions += i
        c, i = _S26_ID_DBRA_TAKEN
        cycles += c
        instructions += i
        entry_addr = (entry_addr + conditions.FLAGGED_STRIDE) & 0xFFFFFFFF


def _s26_box_test_cost(passed_first_pair, passed):
    """0081EA-008220.  Every return path (early-fail or the fourth test) falls into the SAME
    `move.w #8,-(a7); rtr` (fail, `_S26_BOX_FAIL_EXIT`) or `clr.w -(a7); rtr` (pass,
    `_S26_BOX_PASS_EXIT`) tail -- easy to lose track of since each early-exit branch reaches a
    DIFFERENT one of the four comparisons but the SAME two-instruction exit."""
    cycles, instructions = _add(_S26_BOX_LOAD_XY, _S26_BOX_MOVEQ, _S26_BOX_ADD, _S26_BOX_MOVEQ_C,
                                _S26_BOX_ADD_POSX, _S26_BOX_LOAD_POSY, _S26_BOX_CMP1)
    if not passed_first_pair[0]:
        c, i = _add(_S26_BOX_BGT1[True], _S26_BOX_FAIL_EXIT)
        return cycles + c, instructions + i
    c, i = _S26_BOX_BGT1[False]
    cycles += c
    instructions += i
    c, i = _S26_BOX_CMP2
    cycles += c
    instructions += i
    if not passed_first_pair[1]:
        c, i = _add(_S26_BOX_BGT2[True], _S26_BOX_FAIL_EXIT)
        return cycles + c, instructions + i
    c, i = _add(_S26_BOX_BGT2[False], _S26_BOX_ADDQ, _S26_BOX_ADDI, _S26_BOX_CMP3)
    cycles += c
    instructions += i
    if not passed_first_pair[2]:
        c, i = _add(_S26_BOX_BLT1[True], _S26_BOX_FAIL_EXIT)
        return cycles + c, instructions + i
    c, i = _add(_S26_BOX_BLT1[False], _S26_BOX_CMP4)
    cycles += c
    instructions += i
    c, i = _add(_S26_BOX_BLT2[not passed], _S26_BOX_PASS_EXIT if passed else _S26_BOX_FAIL_EXIT)
    return cycles + c, instructions + i


def _s26_actor_entry_cost(read, entry, is_last):
    """One `game.movement.BOX_SCAN_TABLE` entry's own cost through `game.player.state_26_actor_scan`,
    from its own `tst.w $6(a0)` through whichever tail it reaches.  Returns (cycles, instructions,
    continues) -- `continues` is False for 'matched'/'unmatched' (the scan ends there, no advance/loop
    suffix) and True for every skip arm (the caller adds the loop's own advance+dbra)."""
    from .game import player
    cycles, instructions = _S26A_TST_B
    if entry['arm'] == 'skip-inactive':
        c, i = _S26A_BEQ_B[True]
        return cycles + c, instructions + i, True
    c, i = _S26A_BEQ_B[False]
    cycles += c
    instructions += i
    c, i = _S26A_TST_A
    cycles += c
    instructions += i
    c, i = _S26A_BMI_A[False]
    cycles += c
    instructions += i
    c, i = _add(_S26A_MOVEM, _S26A_MOVE_D3, _S26A_LEA_RECORD, _S26A_ADD_D3, _S26A_ADDA_D3, _S26A_ADD_D3,
               _S26A_ADD_D3, _S26A_ADDA_D3, _S26A_CMP_KIND)
    cycles += c
    instructions += i
    if entry['arm'] == 'skip-kind':
        c, i = _S26A_BNE_KIND[True]
        return cycles + c, instructions + i, True
    c, i = _S26A_BNE_KIND[False]
    cycles += c
    instructions += i
    c, i = _add(_S26A_MOVEA_A3, _S26A_BSR_2E0A)
    cycles += c
    instructions += i
    c, i = _s26_id_search_cost(entry['found_id'])
    cycles += c
    instructions += i
    c, i = _add(_S26A_EXG, _S26A_TST_D1, _S26A_BMI_D1[False], _S26A_BSR_81EA)
    cycles += c
    instructions += i
    box_passed = entry['arm'] != 'box-failed'
    ex = read(entry['entry'] & 0xFFFFFF, 2)
    ey = read((entry['entry'] + 2) & 0xFFFFFF, 2)
    px = (read(player.POSITION_X, 2) + 0xC) & 0xFFFF
    py = read(player.POSITION_Y, 2)
    far_x = (ex + 0x10) & 0xFFFF
    far_y = (ey + 0x10) & 0xFFFF
    px2 = (px + 8) & 0xFFFF
    py2 = (py + 0x30) & 0xFFFF
    pairs = (player._signed_word(px) <= player._signed_word(far_x),
             player._signed_word(py) <= player._signed_word(far_y),
             player._signed_word(px2) >= player._signed_word(ex))
    c, i = _s26_box_test_cost(pairs, box_passed)
    cycles += c
    instructions += i
    c, i = _S26A_BMI_BOX[not box_passed]
    cycles += c
    instructions += i
    if not box_passed:
        return cycles, instructions, True
    # 0081AC-0081BE: up to four chained ID comparisons (0x76/0x78/0x7A/0x3E); the first match short-
    # circuits straight to 0081C4, so only the matching id's own position (or all four, unmatched)
    # costs a comparison.
    payload = read(entry['record'] & 0xFFFFFF, 2)   # (a1): the F8C2 record's own word, not the id table's
    matched_at = next((i for i, value in enumerate(player.PROXIMITY_MATCH_IDS) if value == payload), None)
    last_index = matched_at if matched_at is not None else 3
    for test_index in range(last_index + 1):
        c, i = _S26A_ID_CMP
        cycles += c
        instructions += i
        if test_index < 3:
            c, i = _S26A_ID_BEQ[test_index == matched_at]
        else:
            # the fourth id (0x3E) is tested with 'bne': taken means NOT matched (falls to eori).
            c, i = _S26A_BNE_FINAL[matched_at is None]
        cycles += c
        instructions += i
    matched = matched_at is not None
    if matched:
        c, i = _add(_S26A_MOVE_FOUND, _S26A_CLR_PENDING, _S26A_BRA_SOUND)
    else:
        c, i = _add(_S26A_EORI, _S26A_EORI)
    cycles += c
    instructions += i
    c, i = _add(_S26A_SOUND, _S26A_RTS)
    return cycles + c, instructions + i, False


def _s26_actor_scan_cost(read, result):
    """`game.player.state_26_actor_scan`'s own cost: the three head gates (only `PROXIMITY_ACTIVE`
    ever witnessed as the deciding one; the other two decline before reaching here) then, once armed,
    the 200-entry loop over `game.movement.BOX_SCAN_TABLE`."""
    from .game import movement
    if result['arm'] == 'already-active':
        cycles, instructions = _add(_S26A_TST_ACTIVE, _S26A_BNE_ACTIVE[True], _S26A_RTS_EARLY)
        return cycles, instructions
    cycles, instructions = _add(_S26A_TST_ACTIVE, _S26A_BNE_ACTIVE[False], _S26A_BTST_BUSY, _S26A_BNE_BUSY[False],
                                _S26A_TST_PENDING, _S26A_BPL_PENDING[False], _S26A_SET_ACTIVE, _S26A_LEA_TABLE,
                                _S26A_LOAD_COUNT)
    entries = result['entries']
    for index, entry in enumerate(entries):
        is_last = index == movement.BOX_SCAN_COUNT - 1
        c, i, continues = _s26_actor_entry_cost(read, entry, is_last)
        cycles += c
        instructions += i
        if continues:
            c, i = _S26A_DBRA_LAST if is_last else _S26A_DBRA_TAKEN
            cycles += c + _S26A_ADVANCE[0]
            instructions += i + _S26A_ADVANCE[1]
    if result['arm'] == 'exhausted':
        c, i = _S26A_RTS_EARLY
        cycles += c
        instructions += i
    return cycles, instructions


def _s26_actor_scan_exit_sr(read, sr, result):
    """`game.player.state_26_actor_scan`'s own exit CCR.  'matched'/'unmatched' both end at
    `0081DA move.w #$60,fdf4.w` -- a constant, so the flags are fixed regardless of how the scan
    got there.  'already-active' exits on its own `tst.w f24a.w` (F24A's own live, nonzero value).
    'exhausted' exits on whichever the LAST processed entry's own last flag-setter was; `game.
    movement.BOX_SCAN_TABLE`'s own address-register `addq.w`/`dbra` never touch CCR, so the loop's
    own advance-and-continue steps are transparent."""
    from .game import player
    if result['arm'] == 'already-active':
        return _logic_sr(sr, read(player.PROXIMITY_ACTIVE, 2), 2)
    if result['arm'] in ('matched', 'unmatched'):
        return _logic_sr(sr, 0x60, 2)
    last = result['entries'][-1]
    if last['arm'] == 'skip-inactive':
        return _logic_sr(sr, 0, 2)   # tst.w $6(a0): status-B, == 0
    if last['arm'] == 'skip-kind':
        value = read((last['record'] + 4) & 0xFFFFFF, 2)
        return _cmp_sr(sr, value, 3, 2)   # cmpi.w #3,$4(a1)
    if last['arm'] == 'box-failed':
        return (sr & ~0x1F) | 0x08   # 0081EA's own move.w #8,-(a7); rtr (fail) leaves N set, X cleared
    raise UnsupportedCandidate(f"state 26 actor scan exit CCR not modelled for entry arm: {last['arm']}")


_S26_ACTOR_DECLINED = ('busy-declined', 'pending-declined', 'skip-negative', 'id-exhausted')


def _s26_apply_stores(order, stores):
    """Expand a semantics-layer `{address: (value, width)}` stores dict into `order`'s own per-byte
    writes, the same shape `state0_plan` and friends already apply for `game.player`'s own helpers."""
    for address, (value, width) in stores.items():
        for a, b in _bytes(address & 0xFFFFFF, value, width):
            order[a] = b


def state_26_plan(machine, registers):
    """005724: the real STATE_TABLE index 26.  See game/player.py's own module note above
    `state_26_step` for the full arm breakdown and counts.  Every witnessed arm ends at
    `pc = 0x0075D6`; the boundary declines the arms `state_26_step`/`state_26_actor_scan` name but
    do not compute (real ROM, unwitnessed by any recording)."""
    from .game import player
    if registers['pc'] != STATE_26_ENTRY:
        raise UnsupportedCandidate('state 26 (real index 26) planner needs the machine parked at 005724')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    order = {}
    exit_registers = {'d7': 0, 'd0': 0x1C}   # 005726's own moveq #$1c,d0 runs unconditionally, first

    result = player.state_26_step(read)
    arm = result['arm']
    cycles, instructions = _add(_S26_MOVEQ0_D7, _S26_MOVEQ_D0, _S26_TST_EA20)

    if arm in ('transition-27', 'transition-28'):
        c, i = _S26_BEQ_EA20[False]
        cycles += c
        instructions += i
        negative = arm == 'transition-27'
        c, i = _S26_BPL_EA20[not negative]
        cycles += c
        instructions += i
        target = player.STATE_26_TO_27 if negative else player.STATE_26_TO_28
        if negative:
            c, i = _S26_MOVEQ_NEG
            cycles += c
            instructions += i
        c, i = _S26_MOVE_STATE
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, target, 2):
            order[a] = b
        sr = _logic_sr(sr, target, 2)   # 005732's own move.w d0,f192.w is the last flag-setter
        c, i = _S26_BRA_TAIL
        cycles += c
        instructions += i
        exit_registers['d0'] = target   # moveq #imm,d0: a full 32-bit sign-extending load, not a merge
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x005736)

    c, i = _S26_BEQ_EA20[True]
    cycles += c
    instructions += i
    c, i = _S26_BTST_EA23
    cycles += c
    instructions += i
    ea23_bit2 = read(player.EA23_WORD, 1) & 4

    if arm == 'actor-scan':
        c, i = _S26_BEQ_EA23[False]
        cycles += c
        instructions += i
        c, i = _S26_BSR_8148
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x005746, 4))
        scan = player.state_26_actor_scan(read)
        if scan['arm'] in _S26_ACTOR_DECLINED:
            raise UnsupportedCandidate(f'state 26 actor scan arm not witnessed by a recording: {scan["arm"]}')
        c, i = _s26_actor_scan_cost(read, scan)
        cycles += c
        instructions += i
        if scan['arm'] != 'already-active':
            order.update(_bytes(player.PROXIMITY_ACTIVE & 0xFFFFFF, 1, 2))   # 008162 move.w #1,f24a.w
            reached_id = next((e for e in reversed(scan['entries']) if 'found_id' in e), None)
            # 008180's own movem.w (a0),d0-d2 SIGN-EXTENDS each word into the full register, for
            # every entry reaching skip-kind or deeper; 008184's own move.w d2,d3 then copies d2's
            # LOW word into d3, preserving d3's own upper half.  The LAST such entry (which may be
            # LATER than the last one to reach 2E0A/81EA, if it never gets past skip-kind itself)
            # decides d0/d1/d2 outright; d3's own upper half is 0 once ANY entry in the whole scan
            # ever reaches 81EA (its own moveq #$10,d2 clears d3 too, transitively, and nothing
            # later un-clears a word op's own untouched upper half), else the entry's own original.
            last_movem = next((e for e in reversed(scan['entries'])
                               if e['arm'] in ('skip-kind', 'box-failed', 'matched', 'unmatched')), None)
            any_reached_81ea = any('found_id' in e for e in scan['entries'])
            if last_movem is not None:
                mx = player._signed_word(read(last_movem['entry'] & 0xFFFFFF, 2))
                my = player._signed_word(read((last_movem['entry'] + 2) & 0xFFFFFF, 2))
                mk = player._signed_word(read((last_movem['entry'] + 4) & 0xFFFFFF, 2))
                exit_registers['d0'] = mx & 0xFFFFFFFF
                exit_registers['d1'] = my & 0xFFFFFFFF
                exit_registers['d2'] = mk & 0xFFFFFFFF
                # 008184-008192's own record-address arithmetic doubles d3 three times (*2, *4, *8)
                # in place while building a1 (achievements._record_address's own shape) -- this runs
                # for EVERY entry reaching skip-kind or deeper, not only ones that reach 2E0A/81EA.
                d3_upper = 0 if any_reached_81ea else (registers['d3'] & 0xFFFF0000)
                exit_registers['d3'] = d3_upper | ((mk & 0xFFFF) * 8 & 0xFFFF)
            if reached_id is not None:
                # bsr.w 2e0a then bsr.b 81ea both push a 4-byte return address at the SAME slot
                # (sp32-8): 81EA's own 0081AA overwrites 2E0A's own 0081A2 there, then its own
                # rtr-pushed CCR word leaves a 2-byte residue at sp32-10.
                order.update(_bytes((sp32 - 8) & 0xFFFFFF, 0x0081AA, 4))
                box_passed = reached_id['arm'] != 'box-failed'
                order.update(_bytes((sp32 - 10) & 0xFFFFFF, 0 if box_passed else 8, 2))
                # 0081EA's own body runs for reached_id's own entry regardless of whether a LATER
                # entry then reaches skip-kind (which touches d0-d3 again but never d4/d5) -- so d4/
                # d5 always come from reached_id, but d0-d3 only survive to the exit if reached_id IS
                # the last entry to reach skip-kind or deeper (last_movem); otherwise a later entry's
                # own fresh movem/record-address arithmetic (already applied above) wins instead.
                ex = read(reached_id['entry'] & 0xFFFFFF, 2)
                ey = read((reached_id['entry'] + 2) & 0xFFFFFF, 2)
                far_x = (ex + 0x10) & 0xFFFF
                far_y = (ey + 0x10) & 0xFFFF
                if last_movem is reached_id:
                    # 002E0A's own cmp.l (a0),d0 leaves d0 = the (x<<16|y) key it built (never
                    # restored); 0081EA's own move.w (a0),d0 then overwrites d0's LOW word with the
                    # SAME entry's own x again (a0 restored to the FFFF4342 slot by 0081A2's own
                    # exg.l) -- both halves end up holding the entry's own x.  d1-d3's own upper
                    # halves are 0 (each cleared by its own moveq before the word op that follows).
                    exit_registers['d0'] = ((ex & 0xFFFF) << 16) | (ex & 0xFFFF)
                    exit_registers['d1'] = ey
                    exit_registers['d2'] = far_x
                    exit_registers['d3'] = far_y
                px = (read(player.POSITION_X, 2) + 0xC) & 0xFFFF
                py = read(player.POSITION_Y, 2)
                first_pair_passed = (player._signed_word(px) <= player._signed_word(far_x)
                                     and player._signed_word(py) <= player._signed_word(far_y))
                if first_pair_passed:
                    px = (px + 8) & 0xFFFF
                    py = (py + 0x30) & 0xFFFF
                exit_registers['d4'] = px   # 0081F8-FA's own moveq #$c,d4 clears the upper half
                exit_registers['d5'] = (registers['d5'] & 0xFFFF0000) | py   # never touched before ENTRY
                exit_registers['a3'] = reached_id['found_id'] & 0xFFFFFFFF   # 0081A2's own exg.l a0,a3
            reached_record = next((e for e in reversed(scan['entries']) if 'record' in e), None)
            if reached_record is not None:
                exit_registers['a1'] = reached_record['record'] & 0xFFFFFFFF   # 008186's own lea + adda chain
            last_entry = scan['entries'][-1]
            if last_entry['arm'] in ('matched', 'unmatched'):
                # the terminal entry's own iteration never reaches its own dbra or addq.w #8,a0.
                dbra_count = last_entry['index']
                exit_registers['a0'] = last_entry['entry'] & 0xFFFFFFFF
            else:
                dbra_count = len(scan['entries'])
                from .game import movement
                exit_registers['a0'] = (movement.BOX_SCAN_TABLE + movement.BOX_SCAN_STRIDE * dbra_count) & 0xFFFFFFFF
            exit_registers['d6'] = (registers['d6'] & 0xFFFF0000) | ((0xC7 - dbra_count) & 0xFFFF)   # move.w #$c7,d6 is a word op: the entry's own upper half survives
        if scan['arm'] in ('matched', 'unmatched'):
            for a, b in scan['stores'].items():
                order.update(_bytes(a, b[0], b[1]))
        sr = _s26_actor_scan_exit_sr(read, sr, scan)
        last_pc = 0x005746
        c, i = _S26_BRA_TAIL
        cycles += c
        instructions += i
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    c, i = _S26_BEQ_EA23[True]
    cycles += c
    instructions += i
    c, i = _S26_CLR_F24A
    cycles += c
    instructions += i
    for a, b in _bytes(player.PROXIMITY_ACTIVE & 0xFFFFFF, 0, 2):
        order[a] = b
    c, i = _S26_TST_EA1E
    cycles += c
    instructions += i
    ea1e = player._signed_word(read(player.EA1E_WORD, 2))

    if arm == 'state15-body':
        c, i = _S26_BPL_EA1E[True]
        cycles += c
        instructions += i
        # 005726's own moveq #$1c,d0 already cleared d0's upper half before this shared body reads
        # it; state4's own call site has no such head, so the merge base must be per-caller.
        probe_regs = dict(registers, d0=0x1C)
        c, i, probe_writes, overlay, sr, last_pc = _state15_ground_probe(read, sp32, sr, probe_regs)
        cycles += c
        instructions += i
        order.update(probe_writes)
        exit_registers.update(overlay)
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    c, i = _S26_BPL_EA1E[False]
    cycles += c
    instructions += i
    c, i = _S26_BSR_57C2
    cycles += c
    instructions += i
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x00575A, 4))
    scan = player.state_26_box_scan(read)
    c, i = _s26_box_scan_cost(scan['entries'])
    cycles += c
    instructions += i
    # d0-d3 (near_x/near_y/far_x/far_y) are set once at the head and never touched again.  d4/d5
    # hold the LAST examined entry's own (x, y) (the fourth chained comparison's own operands, or a
    # 'found' entry's own) -- unchanged from ENTRY if every entry skipped via the status test alone,
    # never reaching that read.  d6 is the loop counter at the point the scan stopped (a 'found'
    # entry's own iteration never reaches its own dbra; full exhaustion runs it 20 times, ending at
    # -1).  a0 is the last examined entry's own address (never advanced past a 'found' one).
    x, y = read(player.POSITION_X, 2), read(player.POSITION_Y, 2)
    near_x = (x - player.STATE_26_BOX_X_MARGIN) & 0xFFFF
    far_x = (x + player.STATE_26_BOX_X_MARGIN) & 0xFFFF
    near_y = (y - player.STATE_26_BOX_Y_MARGIN) & 0xFFFF
    far_y = (y + player.STATE_26_BOX_Y_MARGIN) & 0xFFFF
    # d0/d1: move.w then subi.w/subq.w, both word ops -- the entry's own upper half survives.
    # d2/d3: moveq (a full 32-bit clear) then add.w -- the upper half is 0, not the entry's own.
    exit_registers['d0'] = near_x   # d0's upper half has been 0 since 005726's own moveq #$1c,d0
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | near_y
    exit_registers['d2'] = far_x
    exit_registers['d3'] = far_y
    last_tested = next((e for e in reversed(scan['entries']) if e['arm'] in ('tested', 'found')), None)
    if last_tested is not None:
        exit_registers['d4'] = (registers['d4'] & 0xFFFF0000) | last_tested['x']
        exit_registers['d5'] = (registers['d5'] & 0xFFFF0000) | last_tested['y']
    last_entry = scan['entries'][-1]
    if last_entry['arm'] == 'found':
        # the found entry's own iteration never reaches its own dbra or its own addq.w #8,a0.
        dbra_count = last_entry['index']
        exit_registers['a0'] = last_entry['entry'] & 0xFFFFFFFF
    else:
        # every entry through the scan's own end (found or not) runs its own advance+dbra.
        dbra_count = len(scan['entries'])
        exit_registers['a0'] = (player.STATE_26_BOX_SCAN_TABLE + player.STATE_26_BOX_SCAN_STRIDE * dbra_count) & 0xFFFFFFFF
    exit_registers['d6'] = (0x13 - dbra_count) & 0xFFFF   # moveq #$13,d6 clears the upper half

    c, i = _S26_TST_EF54
    cycles += c
    instructions += i
    found = arm == 'box-found'
    # 00575A's own tst.w ef54.w is a fresh flag-setter that overrides whatever the box scan (a plain
    # rts, not a Seam) internally left -- the store block's own last write (a MOVE too) never
    # survives to be observed here.
    sr = _logic_sr(sr, 1 if found else 0, 2)

    if found:
        c, i = _S26_BNE_EF54[True]
        cycles += c
        instructions += i
        for a, b in scan['stores'].items():
            order.update(_bytes(a, b[0], b[1]))
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00575E)

    c, i = _S26_BNE_EF54[False]
    cycles += c
    instructions += i
    c, i = _S26_BSR_63FA
    cycles += c
    instructions += i
    c, i = GRID_CELL_COST
    cycles += c
    instructions += i
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x005766, 4))
    from .game.grid import grid_cell
    cell = grid_cell(read)
    exit_registers['a0'] = cell['address'] & 0xFFFFFFFF
    # d0's upper half has been 0 since 005726's own moveq #$1c,d0; d1's own upper half is whatever
    # the box scan's own subq.w #8,d1 left (the entry's own, since that too is a word op).
    exit_registers['d0'] = cell['d0']
    exit_registers['d1'] = (exit_registers['d1'] & 0xFFFF0000) | cell['d1']
    sr = _asl_sr(sr, cell['row_source'], 3, 2)
    c, i = _S26_LOAD_POSX
    cycles += c
    instructions += i
    c, i = _S26_ANDI_1F
    cycles += c
    instructions += i
    position_x = read(player.POSITION_X, 2)
    low5 = position_x & 0x1F
    exit_registers['d0'] = low5   # 005766's own move.w f18c.w,d0 is a word op, but d0's upper half
                                    # has been 0 since 005726's own moveq #$1c,d0 either way
    sr = _logic_sr(sr, low5, 2)
    c, i = _S26_CMP_10
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, low5, 0x10, 2)
    low = low5 < player.STATE_26_HIGH_LOW5_GATE
    c, i = _S26_BLT_10[low]
    cycles += c
    instructions += i

    if low:
        c, i = _S26_CMP_A0
        cycles += c
        instructions += i
        first_byte = read(cell['address'] & 0xFFFFFF, 1)
        sr = _cmp_sr(sr, first_byte, 2, 1)
        if arm == 'transition-14-low':
            c, i = _S26_BEQ_A0[True]
            cycles += c
            instructions += i
            # 0057B4's own beq.b jumps straight into 578E (the SAME merge point the high-low5 arm's
            # own double-pass falls into from 005788), so the SAME tail (andi/move/moveq/4x clr/bra)
            # runs here too -- just without the +0x20 advance beforehand.
            masked_x = position_x & 0xFFE0
            c, i = _S26_ANDI_MASK
            cycles += c
            instructions += i
            order.update(_bytes(player.POSITION_X, masked_x, 2))
            sr = _logic_sr(sr, masked_x, 2)
            c, i = _S26_MOVE_STATE14
            cycles += c
            instructions += i
            order.update(_bytes(player.STATE_INDEX, 0xE, 2))
            c, i = _S26_MOVEQ_1A
            cycles += c
            instructions += i
            _s26_apply_stores(order, player._state0_state14_stores())
            for _ in range(4):
                c, i = _S26_CLR_FIELD
                cycles += c
                instructions += i
            exit_registers['d7'] = 0x1A
            sr = _logic_sr(sr, 0, 2)   # 00579C-0057A8's own last clr.w is the last flag-setter
            c, i = _S26_BRA_TAIL
            cycles += c
            instructions += i
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x0057AC)
        c, i = _S26_BEQ_A0[False]
        cycles += c
        instructions += i
        if arm == 'box-not-found-low-second-found':
            raise UnsupportedCandidate('state 26 low5<0x10 second-test transition-14 arm not witnessed by a recording')
        c, i = _S26_CMP_A0_80
        cycles += c
        instructions += i
        second_byte = read((cell['address'] + 0x80) & 0xFFFFFF, 1)
        sr = _cmp_sr(sr, second_byte, 2, 1)
        c, i = _S26_BEQ_A0_80[False]
        cycles += c
        instructions += i
        c, i = _S26_BRA_TAIL
        cycles += c
        instructions += i
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0057BE)

    c, i = _S26_CMP_A0_1
    cycles += c
    instructions += i
    first_byte = read((cell['address'] + 1) & 0xFFFFFF, 1)
    sr = _cmp_sr(sr, first_byte, 2, 1)
    first_hit = first_byte == 2
    c, i = _S26_BNE_A0_1[not first_hit]
    cycles += c
    instructions += i
    if not first_hit:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00577A)
    c, i = _S26_CMP_A0_81
    cycles += c
    instructions += i
    second_byte = read((cell['address'] + 0x81) & 0xFFFFFF, 1)
    sr = _cmp_sr(sr, second_byte, 2, 1)
    second_hit = second_byte == 2
    c, i = _S26_BNE_A0_81[not second_hit]
    cycles += c
    instructions += i
    if not second_hit:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x005784)
    c, i = _S26_ADDI_20
    cycles += c
    instructions += i
    new_x = (position_x + 0x20) & 0xFFFF
    for a, b in _bytes(player.POSITION_X, new_x, 2):
        order[a] = b
    sr = _logic_sr(sr, new_x, 2)
    c, i = _S26_ANDI_MASK
    cycles += c
    instructions += i
    masked_x = new_x & 0xFFE0
    for a, b in _bytes(player.POSITION_X, masked_x, 2):
        order[a] = b
    sr = _logic_sr(sr, masked_x, 2)
    c, i = _S26_MOVE_STATE14
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, 0xE, 2):
        order[a] = b
    c, i = _S26_MOVEQ_1A
    cycles += c
    instructions += i
    _s26_apply_stores(order, player._state0_state14_stores())
    for _ in range(4):
        c, i = _S26_CLR_FIELD
        cycles += c
        instructions += i
    exit_registers['d7'] = 0x1A
    sr = _logic_sr(sr, 0, 2)   # 0057A8's own final clr.w f1a8.w is the last flag-setter
    c, i = _S26_BRA_TAIL
    cycles += c
    instructions += i
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x0057AC)


# --- 00648C: state 8 (game.player.state8_step / state8_fall_tail / _state8_head) -- state 9's own
# sibling, sharing state 9's own row-gate cost helper (`_row_gate_cost`) and jump-arc table constants
# verbatim, the same shape state 26 already established for reuse.  Costed one instruction-block at a
# time from the tracer on real fixtures over `census-00648C-*` covering every witnessed arm (18
# September); every shared block's own cost matches state 9's own constants exactly wherever the ROM
# bytes are identical or the same instruction/addressing shape (confirmed against the ROM, not
# assumed) -- only the head's own resting-value branch and the block test's own gate (one fewer
# instruction, no `cmpi.w #$8,d0`) need their own constants.
STATE8_ENTRY = 0x00648C

_S8_P1_HEAD = (12 + 8, 2)                    # 0064BA move.w f18c,d0; 0064BE andi.w #$1f,d0 -- no cmpi #$8
_S8_P1_BNE_LOW = {True: (10, 1), False: (8, 1)}      # 0064C2 bne.b -- taken: low5 != 0, skip the block test entirely

_S8_B_CMPI_CELL80 = (16, 1)                  # 006558 cmpi.b #$2,$80(a0) -- the landing-13 arm's own second test
_S8_B_BNE_CELL80 = {True: (10, 1), False: (8, 1)}    # bne.b -- taken: neither test found (not witnessed)


def _state8_head_cost(read, d7):
    """00648C-0064B6: `_state8_head`'s own cost -- the SAME instruction/addressing shape as
    `_state9_head_cost` (only the immediate operands differ, which cost nothing extra), so its own
    cost constants (`_S9_HEAD_*`) are reused verbatim."""
    from .game import player
    new_d7, source = player._state8_head(read, d7)
    if d7 == 0xD:
        f19c_taken = new_d7 != d7
        c, i = _add(_S9_HEAD_CMPI_C, _S9_HEAD_BNE_C[False], _S9_HEAD_CMPI_F19C, _S9_HEAD_BLT[not f19c_taken])
        if f19c_taken:
            c, i = _add((c, i), _S9_HEAD_MOVEQ5, _S9_HEAD_BRA)
        return c, i, new_d7, source
    if d7 == 6:
        c, i = _add(_S9_HEAD_CMPI_C, _S9_HEAD_BNE_C[True], _S9_HEAD_CMPI_5, _S9_HEAD_BEQ_5[True])
        return c, i, new_d7, source
    if d7 == 0:
        f19c_taken = new_d7 != d7
        c, i = _add(_S9_HEAD_CMPI_C, _S9_HEAD_BNE_C[True], _S9_HEAD_CMPI_5, _S9_HEAD_BEQ_5[False],
                    _S9_HEAD_TST, _S9_HEAD_BNE_0[False], _S9_HEAD_CMPI_F19C, _S9_HEAD_BLT[not f19c_taken])
        if f19c_taken:
            c, i = _add((c, i), _S9_HEAD_ADDQ4, _S9_HEAD_BRA)
        return c, i, new_d7, source
    c, i = _add(_S9_HEAD_CMPI_C, _S9_HEAD_BNE_C[True], _S9_HEAD_CMPI_5, _S9_HEAD_BEQ_5[False],
                _S9_HEAD_TST, _S9_HEAD_BNE_0[True], _S9_HEAD_MOVEQ5)
    return c, i, new_d7, source


def state8_plan(machine, registers):
    """00648C (state 8): the player state machine's own dispatch table entry 8, state 9's own
    sibling.  See `game.player`'s own module note above the state 8 section for the shape.  Every
    terminal arm ends at `pc = 0x0075D6` (the shared tail's own gate)."""
    from .game import player
    if registers['pc'] != STATE8_ENTRY:
        raise UnsupportedCandidate('state 8 planner needs the machine parked at 00648C')
    read = _reader(machine)
    sr = registers['sr']
    entry_d7 = registers['d7'] & 0xFFFF
    sp32 = registers['a7']
    order = {}

    hc, hi, d7, source = _state8_head_cost(read, entry_d7)
    cycles, instructions = hc, hi
    if source == 'addq':
        sr = _add_sr(sr, entry_d7, 5, 2)   # 0064B0 addq.w #5,d7

    from .game.grid import grid_cell
    c, i = _S9_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0064BA, 4))   # 0064B6 bsr.w $63fa's own return site
    cell1 = grid_cell(read)
    address = cell1['address']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)
    position_x = read(player.POSITION_X, 2)
    low5 = position_x & 0x1F
    exit_registers = {'a0': cell1['address'] & 0xFFFFFFFF,
                       'd0': (registers['d0'] & 0xFFFF0000) | cell1['d0'],
                       'd1': (registers['d1'] & 0xFFFF0000) | cell1['d1']}

    c, i = _S8_P1_HEAD
    cycles += c
    instructions += i
    blocked = False
    if low5 == 0:
        c, i = _S8_P1_BNE_LOW[False]
        cycles += c
        instructions += i
        for offset in (-1, 0x7F, 0xFF):
            c, i = _S9_P1_GRIDTEST
            cycles += c
            instructions += i
            hit = read((address + offset) & 0xFFFFFF, 1) == 1
            c, i = _S9_P1_GRIDBEQ[hit]
            cycles += c
            instructions += i
            if hit:
                blocked = True
                break
    else:
        c, i = _S8_P1_BNE_LOW[True]
        cycles += c
        instructions += i

    advanced = False
    if not blocked:
        f19c = read(player.F19C, 2)
        c, i = _S9_P1_CMPI_F19C
        cycles += c
        instructions += i
        advanced = f19c >= player.STATE9_ADVANCE_GATE
        c, i = _S9_P1_BLT[not advanced]
        cycles += c
        instructions += i
        if advanced:
            c, i = _S9_P1_ADVANCE
            cycles += c
            instructions += i
            step = read(player.F196, 2)
            sr = _add_sr(sr, position_x, step, 2)   # 0064E8 add.w d0,f18c.w
            position_x = (position_x + step) & 0xFFFF
            order.update({a: b for a, b in _bytes(player.POSITION_X, position_x, 2)})

    c, i = _S9_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0064F0, 4))   # 0064EC bsr.w $63fa's own return site
    if advanced:
        def _read_after_advance(a, s, _position_x=position_x):
            return _position_x if (a & 0xFFFFFF) == (player.POSITION_X & 0xFFFFFF) else read(a, s)
        cell2 = grid_cell(_read_after_advance)
    else:
        cell2 = grid_cell(read)
    address2 = cell2['address']
    sr = _asl_sr(sr, cell2['row_source'], 3, 2)
    exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell2['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell2['d1']

    c, i = _S9_L_TST_EA1E
    cycles += c
    instructions += i
    ea1e = player._signed_word(read(player.EA1E_WORD, 2))
    tracked_x = read(player.F19A, 2)
    c, i = _S9_L_BPL[ea1e >= 0]
    cycles += c
    instructions += i

    if ea1e < 0:
        # Byte-identical to state 9's own arm A: its own cost constants apply verbatim.
        c, i = _S9_A_MOVE_D0
        cycles += c
        instructions += i
        f196 = read(player.F196, 2)
        c, i = _S9_A_TST_F196
        cycles += c
        instructions += i
        c, i = _S9_A_BEQ_F196[f196 == 0]
        cycles += c
        instructions += i
        landing = False
        blocked = False
        if f196 != 0:
            c, i = _S9_A_CMP_F19A
            cycles += c
            instructions += i
            blocked = position_x == tracked_x
            c, i = _S9_A_BEQ_F19A[blocked]
            cycles += c
            instructions += i
        if not blocked:
            c, i = _S9_A_ANDI_1F
            cycles += c
            instructions += i
            c, i = _S9_A_BNE_LOW[(position_x & 0x1F) != 0]
            cycles += c
            instructions += i
            if (position_x & 0x1F) == 0:
                c, i = _S9_A_CMPI_CELL
                cycles += c
                instructions += i
                cell_byte = read(address2 & 0xFFFFFF, 1)
                c, i = _S9_A_BNE_CELL[cell_byte != 2]
                cycles += c
                instructions += i
                landing = cell_byte == 2
        if landing:
            c, i = _S9_A_LANDING_TAIL
            cycles += c
            instructions += i
            new_x = position_x & 0xFFE0
            new_y = read(player.POSITION_Y, 2) & 0xFFF8
            for a, b in _bytes(player.POSITION_X, new_x, 2):
                order[a] = b
            for a, b in _bytes(player.POSITION_Y, new_y, 2):
                order[a] = b
            for a, b in _bytes(player.F1A8 & 0xFFFFFF, 0, 2):
                order[a] = b
            for a, b in _bytes(player.STATE_INDEX, 0xE, 2):
                order[a] = b
            for a, b in _bytes(player.F1AE & 0xFFFFFF, 0, 2):
                order[a] = b
            for a, b in _bytes(player.F1A4 & 0xFFFFFF, 0, 2):
                order[a] = b
            for a, b in _bytes(player.F1A6 & 0xFFFFFF, 0, 2):
                order[a] = b
            exit_registers['d0'] = registers['d0'] & 0xFFFF0000
            exit_registers['d7'] = 2   # moveq #2,d7: a full 32-bit clear
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = _logic_sr(sr, 0, 2)   # the last clr.w is the last flag-setter
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x006536)
        # Arm A's own decline falls straight into arm B's own head, exactly as state 9's own does.
        c, i = _add(_S9_B_CMPI_EA1E, _S9_B_BNE_EA1E[True])
        cycles += c
        instructions += i
    else:
        c, i = _S9_B_CMPI_EA1E
        cycles += c
        instructions += i
        c, i = _S9_B_BNE_EA1E[ea1e != 1]
        cycles += c
        instructions += i
        if ea1e == 1:
            c, i = _S9_B_MOVE_D0
            cycles += c
            instructions += i
            c, i = _S9_B_CMP_F19A
            cycles += c
            instructions += i
            c, i = _S9_B_BEQ_F19A[position_x == tracked_x]
            cycles += c
            instructions += i
            if position_x != tracked_x:
                c, i = _S9_B_ANDI_1F
                cycles += c
                instructions += i
                low_zero = (position_x & 0x1F) == 0
                c, i = _S9_B_BNE_LOW[not low_zero]
                cycles += c
                instructions += i
                if low_zero:
                    # WITNESSED here (unlike state 9's own): the SAME OR test state9_step's own
                    # (declined) arm B names, now costed for real.
                    c, i = _S9_A_CMPI_CELL
                    cycles += c
                    instructions += i
                    cell_byte = read(address2 & 0xFFFFFF, 1)
                    # 006556 beq.b $6560 -- unlike arm A's own bne (taken = decline), this is a BEQ:
                    # taken means FOUND directly, only falling to the second test when not taken.
                    c, i = _S9_A_BNE_CELL[cell_byte == 2]
                    cycles += c
                    instructions += i
                    found13 = cell_byte == 2
                    if not found13:
                        c, i = _S8_B_CMPI_CELL80
                        cycles += c
                        instructions += i
                        cell_byte80 = read((address2 + 0x80) & 0xFFFFFF, 1)
                        c, i = _S8_B_BNE_CELL80[cell_byte80 != 2]
                        cycles += c
                        instructions += i
                        found13 = cell_byte80 == 2
                    if not found13:
                        raise UnsupportedCandidate('state 8 landing-13 not found by either cell test (not witnessed)')
                    c, i = _S9_A_LANDING_TAIL
                    cycles += c
                    instructions += i
                    new_x = position_x & 0xFFE0
                    new_y = read(player.POSITION_Y, 2) & 0xFFF8
                    for a, b in _bytes(player.POSITION_X, new_x, 2):
                        order[a] = b
                    for a, b in _bytes(player.POSITION_Y, new_y, 2):
                        order[a] = b
                    for a, b in _bytes(player.F1A8 & 0xFFFFFF, 0, 2):
                        order[a] = b
                    for a, b in _bytes(player.STATE_INDEX, 0xD, 2):
                        order[a] = b
                    for a, b in _bytes(player.F1AE & 0xFFFFFF, 0, 2):
                        order[a] = b
                    for a, b in _bytes(player.F1A4 & 0xFFFFFF, 0, 2):
                        order[a] = b
                    for a, b in _bytes(player.F1A6 & 0xFFFFFF, 0, 2):
                        order[a] = b
                    # 00654C andi.w #$1f,d0 (position_x & 0x1F, already proved 0 by the low_zero gate
                    # above) is D0's own LAST write on this arm too -- neither cell test touches D0.
                    exit_registers['d0'] = registers['d0'] & 0xFFFF0000
                    exit_registers['d7'] = 2   # moveq #2,d7: a full 32-bit clear
                    exit_registers['pc'] = 0x0075D6
                    exit_registers['sr'] = _logic_sr(sr, 0, 2)
                    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                                      registers=exit_registers, last_pc=0x006584)

    # Neither landing check fired: the ground-ahead probe, before the fall step.
    f19c = read(player.F19C, 2)
    c, i = _S9_G_CMPI_F19C
    cycles += c
    instructions += i
    trigger_gate_before = f19c >= player.STATE9_TRIGGER_GATE
    c, i = _S9_G_BLT[not trigger_gate_before]
    cycles += c
    instructions += i
    found_before = False
    if trigger_gate_before:
        c, i = _S9_BSR_ROWGATE
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006594, 4))   # 006590 bsr.w $6442's own return site
        rc, ri, found_before, rowgate_order, rowgate_d0 = _row_gate_cost(
            read, address2, position_x, 0x180, sp32 - 4, cell2['d0'])
        cycles += rc
        instructions += ri
        order.update(rowgate_order)
        exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
        exit_registers['d1'] = 1 if found_before else 0
        sr = _asl_sr(sr, cell2['row_source'], 3, 2)
        c, i = _S9_G_TST_D1
        cycles += c
        instructions += i
        c, i = _S9_G_BEQ_D1[not found_before]
        cycles += c
        instructions += i

    if found_before:
        c, i = _S9_GROUND_TAIL
        cycles += c
        instructions += i
        original_y = read(player.POSITION_Y, 2)
        stores = player._state8_ground_stores(original_y)
        for a, b in _bytes(player.STATE_INDEX, stores[player.STATE_INDEX][0], 2):
            order[a] = b
        for a, b in _bytes(player.POSITION_Y, stores[player.POSITION_Y][0], 2):
            order[a] = b
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x39, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0065B0)

    # The fall step.
    c, i = _add(_S9_D_LEA, _S9_D_MOVE_F19C, _S9_D_TABLE_READ)
    cycles += c
    instructions += i
    exit_registers['a1'] = player.STATE9_FALL_TABLE & 0xFFFFFFFF
    if f19c > player.STATE9_FALL_TABLE_LIMIT:
        raise UnsupportedCandidate('state 8 fall table index past its own last entry (F19E path) not witnessed')
    step = player._signed_word(read((player.STATE9_FALL_TABLE + f19c) & 0xFFFFFF, 2))
    original_y = read(player.POSITION_Y, 2)
    c, i = _S9_D_SUB
    cycles += c
    instructions += i
    sr = _sub_sr(sr, original_y, step & 0xFFFF, 2)
    new_y = (original_y - step) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    c, i = _S9_D_TST_F19E
    cycles += c
    instructions += i
    if read(player.F19E, 2) != 0:
        raise UnsupportedCandidate('state 8 doubled fall step (FFFFF19E != 0) not witnessed by a recording')
    c, i = _S9_D_BEQ_F19E[True]
    cycles += c
    instructions += i

    c, i = _S9_BSR_ROWGATE
    cycles += c
    instructions += i
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0065D2, 4))   # 0065CE bsr.w $6468's own return site

    def _read_after_fall(a, s, _new_y=new_y, _position_x=position_x):
        masked = a & 0xFFFFFF
        if masked == (player.POSITION_Y & 0xFFFFFF):
            return _new_y
        if masked == (player.POSITION_X & 0xFFFFFF):
            return _position_x
        return read(a, s)
    cell3 = grid_cell(_read_after_fall)
    address3 = cell3['address']
    rc, ri, found_landed, rowgate_order, rowgate_d0 = _row_gate_cost(
        read, address3, position_x, 0, sp32 - 4, cell3['d0'])
    cycles += rc
    instructions += ri
    order.update(rowgate_order)
    exit_registers['a0'] = cell3['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
    exit_registers['d1'] = 1 if found_landed else 0
    sr = _asl_sr(sr, cell3['row_source'], 3, 2)
    c, i = _S9_G_TST_D1
    cycles += c
    instructions += i
    c, i = _S9_D_BNE_D1[not found_landed]
    cycles += c
    instructions += i

    if found_landed:
        c, i = _S9_LANDED_TAIL
        cycles += c
        instructions += i
        masked_y = new_y & 0xFFF0
        sr = _add_sr(sr, masked_y, 0x10, 2)   # 0065DC addi.w #$10,f18e.w
        new_y_aligned = (masked_y + 0x10) & 0xFFFF
        for a, b in _bytes(player.POSITION_Y, new_y_aligned, 2):
            order[a] = b
        for a, b in _bytes(player.STATE_INDEX, player.STATE8_LANDED_INDEX, 2):
            order[a] = b
        for a, b in _bytes(player.F198 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(player.F1A0 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(player.F194 & 0xFFFFFF, 0, 2):
            order[a] = b
        c, i = _add(_S9_LANDED_MOVEQ, _S9_LANDED_BRA)
        cycles += c
        instructions += i
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0065F6)

    # The re-check ground-ahead probe, at the new position: STATE8_RECHECK_GATE (0x12), not state 9's
    # own STATE9_TRIGGER_GATE (0x16).
    c, i = _S9_G_CMPI_F19C
    cycles += c
    instructions += i
    trigger_gate_after = f19c >= player.STATE8_RECHECK_GATE
    c, i = _S9_G_BLT[not trigger_gate_after]
    cycles += c
    instructions += i
    found_after = False
    if trigger_gate_after:
        c, i = _S9_BSR_ROWGATE
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006606, 4))   # 006602 bsr.w $6442's own return site
        rc, ri, found_after, rowgate_order, rowgate_d0 = _row_gate_cost(
            read, address3, position_x, 0x180, sp32 - 4, cell3['d0'])
        cycles += rc
        instructions += ri
        order.update(rowgate_order)
        exit_registers['a0'] = cell3['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
        exit_registers['d1'] = 1 if found_after else 0
        sr = _asl_sr(sr, cell3['row_source'], 3, 2)
        c, i = _S9_G_TST_D1
        cycles += c
        instructions += i
        c, i = _S9_G2_BNE_D1[found_after]
        cycles += c
        instructions += i

    if found_after:
        c, i = _S9_GROUND_TAIL
        cycles += c
        instructions += i
        stores = player._state8_ground_stores(new_y)
        for a, b in _bytes(player.STATE_INDEX, stores[player.STATE_INDEX][0], 2):
            order[a] = b
        for a, b in _bytes(player.POSITION_Y, stores[player.POSITION_Y][0], 2):
            order[a] = b
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x39, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0065B0)

    # The trigger gate / countdown tail.
    c, i = _S9_T_CMPI_F19C_4
    cycles += c
    instructions += i
    advance_gate_open = f19c >= player.STATE9_ADVANCE_GATE
    c, i = _S9_T_BLT[not advance_gate_open]
    cycles += c
    instructions += i
    found_trigger = False
    if advance_gate_open:
        c, i = _S9_T_BTST
        cycles += c
        instructions += i
        bit2 = read(player.EA23_WORD, 1) & 4
        c, i = _S9_T_BEQ_BIT2[not bit2]
        cycles += c
        instructions += i
        if bit2:
            c, i = _S9_BSR_SEARCH
            cycles += c
            instructions += i
            sp32 = registers['a7']
            for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x00661E, 4):
                order[a] = b
            cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
                machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4, 'sr': sr}, sp32 - 4)
            cycles += cs_cycles
            instructions += cs_instructions
            order.update(cs_order)
            exit_registers.update(cs_registers)
            sr = cs_registers['sr']
            c, i = _S9_T_TST_D0
            cycles += c
            instructions += i
            found_search = cs_result['d0'] == 0
            c, i = _S9_T_BNE_D0[not found_search]
            cycles += c
            instructions += i
            if found_search:
                c, i = _S9_T_CMPI_2C
                cycles += c
                instructions += i
                too_late = f19c >= player.STATE9_TRIGGER_CAP
                c, i = _S9_T_BGE_2C[too_late]
                cycles += c
                instructions += i
                found_trigger = not too_late

    if found_trigger:
        c, i = _S9_TRIGGER_TAIL
        cycles += c
        instructions += i
        new_f19c = (f19c + 2) & 0xFFFF
        sr = _add_sr(sr, f19c, 2, 2)   # 006638 addq.w #2,f19c.w is the last flag-setter
        for a, b in _bytes(player.STATE_INDEX, player.STATE8_TRIGGER_INDEX, 2):
            order[a] = b
        for a, b in _bytes(player.F1BA & 0xFFFFFF, 1, 2):
            order[a] = b
        for a, b in _bytes(player.F19C & 0xFFFFFF, new_f19c, 2):
            order[a] = b
        exit_registers['d7'] = 1   # moveq #1,d7: a full 32-bit clear
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, new_f19c, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00663C)

    c, i = _S9_COUNTDOWN_ADDQ
    cycles += c
    instructions += i
    new_f19c = (f19c + 2) & 0xFFFF
    sr = _add_sr(sr, f19c, 2, 2)   # 006640 addq.w #2,f19c.w
    for a, b in _bytes(player.F19C & 0xFFFFFF, new_f19c, 2):
        order[a] = b
    c, i = _S9_COUNTDOWN_CMPI
    cycles += c
    instructions += i
    terminal = new_f19c >= player.STATE9_COUNTDOWN_CAP
    c, i = _S9_COUNTDOWN_BLT[not terminal]
    cycles += c
    instructions += i

    if not terminal:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _cmp_sr(sr, new_f19c, player.STATE9_COUNTDOWN_CAP, 2)
        if source == 'untouched':
            pass
        elif source == 'moveq':
            exit_registers['d7'] = d7
        else:   # 'addq': a word op, the entry's own upper half survives
            exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | d7
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00664A)

    c, i = _S9_TERMINAL_TAIL
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, player.STATE8_LANDED_INDEX, 2):
        order[a] = b
    for a, b in _bytes(player.F1A0 & 0xFFFFFF, 0, 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, 0, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, 0, 2):
        order[a] = b
    exit_registers['d7'] = 0   # moveq #0,d7: a full 32-bit clear
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = _logic_sr(sr, 0, 2)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x006662)


# --- 006B4E: state 13 (game.player.state13_step / state13_arm_a / state13_arm_b / state13_arm_d /
# state13_settle / state13_settle_probe) -- state 14's own counterpart.  The contact-search gate
# (006C62-006CC5) is byte-identical to state 14's own (006EC4-006F27), confirmed against the ROM
# save for relocated branch displacements, and reuses the shared _state14_contact_cost helper (which
# itself calls player.state14_contact/player.state14_contact_found, state-agnostic semantics); the
# two jump-start tails (0x6FB8 into state 8, 0x6FDA into state 9) are the SAME physical ROM addresses
# state 14's own arm A/B jump into, not copies.  Costed one instruction-block at a time from the
# tracer on real fixtures over census-006B4E-star covering every witnessed arm.  The arm A/B retry-
# budget/grid/nibble/transition bodies are the same shape as state 14's own; the head, the arm gates
# and the settle probe are real, different code (see the module note in game/player.py above
# state13_step) and get their own cost constants.
STATE13_ENTRY = 0x006B4E

_S13_FROZEN_TEST = (12, 1)                   # 006B4E tst.w ef4a
_S13_FROZEN_BEQ = {True: (10, 1), False: (12, 1)}       # 006B52 beq.w -- taken: exit unchanged
_S13_WRAP_TEST = (8, 1)                      # 006B56 cmpi.w #0x14,d7
_S13_WRAP_BLT = {True: (10, 1), False: (8, 1)}          # 006B5A blt.b -- taken(d7<20): main path
_S13_WRAP_RESET = (4 + 10, 2)                # 006B5C moveq #0,d7; 006B5E bra.w 6ce4
_S13_EA20_TEST0 = (12, 1)                    # 006B62 tst.w ea20
_S13_EA20_BNE0 = {True: (10, 1), False: (8, 1)}         # 006B66 bne.b -- taken(!=0): skip to 6b7a
_S13_SETTLE_GATE_TEST = (16, 1)              # 006B68 cmpi.w #1,ea1e (settle-carrying gate)
_S13_SETTLE_GATE_BEQ = {True: (10, 1), False: (12, 1)}  # 006B6E beq.w -- taken(==1): settle, carrying
_S13_CLEAR = (16 + 16, 2)                    # 006B72 clr f1a4; 006B76 clr f1a6
_S13_ARMSEL_TEST = (16, 1)                   # 006B7A cmpi.w #1,ea20
_S13_ARMSEL_BNE = {True: (10, 1), False: (12, 1)}       # 006B80 bne.w -- taken(!=1): arm B

_S13A_BIT2 = (16, 1)                         # 006B84 btst #2,ea23
_S13A_BIT2_BEQ = {True: (10, 1), False: (8, 1)}         # 006B8A beq.b -- taken(clear): 6B96
_S13A_SET_F1A8 = (16, 1)                     # 006B8C move.w #1,f1a8
_S13A_BRA_C = (10, 1)                        # 006B92 bra.w 6c62
_S13A_EA1E_TEST = (12, 1)                    # 006B96 tst.w ea1e (arm A's own sign-based jump gate)
_S13A_EA1E_BMI = {True: (10, 1), False: (12, 1)}        # 006B9A bmi.w -- taken(<0): transition-9 (unwitnessed)
_S13_TRANS_9_OR_8 = (16 + 16 + 4 + 20 + 16 + 16 + 10, 7)   # move state; f196; d7; f19a; f19c; fdf6; bra
_S13A_HEAD2 = (16 + 16 + 16, 3)              # 006B9E clr f1a4; 006BA2 addq.w #1,f1a6 (mem); 006BA6 cmpi.w #5,f1a6 (mem)
_S13A_F1A6_BLE = {True: (10, 1), False: (8, 1)}         # 006BAC ble.b -- taken(<=5): contact-gate-f1a6
_S13A_DETOUR = (12 + 10, 2)                  # 006BF0 tst ea20; 006BF4 bpl.w (always taken here: ea20==1)
_S13A_GRIDSETUP = (18, 1)                    # 006BAE bsr 63fa
_S13_GRID_TEST = (16, 1)                     # cmpi.b #1,offset(a0)
_S13_GRID_BEQ = {True: (10, 1), False: (8, 1)}          # beq.b -- taken: matched (decline to contact-gate)
_S13_NIBBLE_HEAD = (12 + 8, 2)                # move f18e,d0; andi #0xf,d0
_S13A_NIBBLE_BEQ = {True: (10, 1), False: (8, 1)}       # 006BD2 beq.b -- taken(==0): transition-1 directly
_S13A_NIBBLE_TEST = (16, 1)                  # 006BD4 cmpi.b #1,0x181(a0)
_S13A_NIBBLE_BEQ2 = {True: (10, 1), False: (8, 1)}      # 006BDA beq.b -- taken: decline to contact-gate
_S13_TRANS_1_OR_0 = (16 + 4 + 16 + 16 + 10, 5)   # move state; d7; position step x/y; bra

_S13B_EA20_TEST = (12, 1)                    # 006BF0 tst.w ea20 (arm B's own entry)
_S13B_EA20_BPL = {True: (10, 1), False: (12, 1)}        # 006BF4 bpl.w -- taken(>=0): contact-gate-immediate
_S13B_BIT2 = (16, 1)                         # 006BF8 btst #2,ea23
_S13B_BIT2_BEQ = {True: (10, 1), False: (8, 1)}         # 006BFE beq.b -- taken(clear): 6C0A
_S13B_SET_F1A8 = (16, 1)                     # 006C00 move.w #0xffff,f1a8
_S13B_BRA_C = (10, 1)                        # 006C06 bra.w 6c62
_S13B_EA1E_TEST = (12, 1)                    # 006C0A tst.w ea1e
_S13B_EA1E_BMI = {True: (10, 1), False: (12, 1)}        # 006C0E bmi.w -- taken(<0): transition-8
_S13B_HEAD2 = (16 + 16 + 16, 3)              # 006C12 clr f1a6; 006C16 addq.w #1,f1a4 (mem); 006C1A cmpi.w #5,f1a4 (mem)
_S13B_F1A4_BLE = {True: (10, 1), False: (8, 1)}         # 006C20 ble.b -- taken(<=5): contact-gate-f1a4
_S13B_GRIDSETUP = (18, 1)                    # 006C22 bsr 63fa
_S13B_NIBBLE_BEQ = {True: (10, 1), False: (8, 1)}       # 006C46 beq.b -- taken(==0): transition-0 directly
_S13B_NIBBLE_TEST = (16, 1)                  # 006C48 cmpi.b #1,0x17f(a0)
_S13B_NIBBLE_BEQ2 = {True: (10, 1), False: (8, 1)}      # 006C4E beq.b -- taken: decline to contact-gate

_S13D_EA1E_TEST = (12, 1)                    # 006CC6 tst.w ea1e (arm D's own SIGN test, not state 14's cmpi #1)
_S13D_EA1E_BPL = {True: (10, 1), False: (12, 1)}        # 006CCA bpl.w -- taken(>=0): exit unchanged

_S13S_RETRY_BEQ = {True: (10, 1), False: (8, 1)}        # 006D2A beq.b -- taken(d7==0 after decrement): loopback
_S13S_RETRY_BRA = (10, 1)                    # 006D2C bra.b 6cfa -- the retry (d7 != 0)
_S13S_SHARED_SUBQ = (4, 1)                   # 006D28 subq.w #1,d7 (register; the F1AE-fork's own shared entry)

_S13P_ADVANCE = (16, 1)                      # 006CFA addq.w #6,f18e (memory, Y += 6)
_S13P_BSR = (18, 1)                          # 006CFE bsr 63fa
_S13P_BLOCK_TEST = (16, 1)                   # 006D02 cmpi.b #1,0x180(a0)
_S13P_BLOCK_BNE = {True: (10, 1), False: (8, 1)}        # 006D08 bne.b -- taken(!=1): not blocked, continue
_S13P_BLOCKED_TAIL = (16 + 4 + 20 + 10, 4)   # 006D0A move state; 006D10 moveq #0,d7; 006D12 andi f18e #0xfff0; bra
_S13P_GROUND_TEST = (16, 1)                  # cmpi.b #2,0x100(a0) / 0x180(a0)
_S13P_GROUND_BEQ = {True: (10, 1), False: (12, 1)}      # beq.w -- taken: solid ground, exit unchanged
_S13P_CLEAR_TAIL = (16 + 4 + 16 + 16 + 16 + 10, 6)   # move state; moveq #0,d7; clr f194; clr f1a0; clr f198; bra


def _state13_settle_probe_cost(read, sr, settle_d7, sp32, d7_register):
    """006CFA-006D64: state 13's own settle probe -- unlike state 14's own (always exits unchanged
    or loops), this one produces two real transitions (state 26 or state 10) alongside the plain
    exit-unchanged result, and has no FFFFF1B0-based restore at all.  Returns (cycles, instructions,
    order, exit_d7_or_None, exit_sr, last_pc, cell)."""
    from .game import player

    def high_d7(low):
        return (d7_register & 0xFFFF0000) | (low & 0xFFFF)

    order = {}
    result = player.state13_settle_probe(read, settle_d7)
    cycles, instructions = _add(_S13P_ADVANCE, _S13P_BSR)
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x006D02, 4):
        order[a] = b
    c, i = GRID_CELL_COST
    cycles += c
    instructions += i
    c, i = _S13P_BLOCK_TEST
    cycles += c
    instructions += i
    cell = result['cell']
    address = cell['address']
    if result['arm'] == 'blocked':
        c, i = _add(_S13P_BLOCK_BNE[False], _S13P_BLOCKED_TAIL)
        cycles += c
        instructions += i
        for a, b in result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        # 006D12's own andi.w #$fff0,f18e.w (NOT 006D10's own moveq #0,d7) is the last flag-setter:
        # it runs AFTER the moveq, masking the just-advanced POSITION_Y down to a tile boundary.
        exit_sr = _logic_sr(sr, result['stores'][player.POSITION_Y][0], 2)
        return cycles, instructions, order, 0, exit_sr, 0x006D18, cell
    c, i = _add(_S13P_BLOCK_BNE[True], _S13P_GROUND_TEST)
    cycles += c
    instructions += i
    first = read((address + 0x100) & 0xFFFFFF, 1) == 2
    c, i = _S13P_GROUND_BEQ[first]
    cycles += c
    instructions += i
    if first:
        for a, b in result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_sr = _cmp_sr(sr, 2, 2, 1)
        return cycles, instructions, order, high_d7(settle_d7), exit_sr, 0x006D42, cell
    second = read((address + 0x180) & 0xFFFFFF, 1) == 2
    c, i = _add(_S13P_GROUND_TEST, _S13P_GROUND_BEQ[second])
    cycles += c
    instructions += i
    if second:
        for a, b in result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_sr = _cmp_sr(sr, 2, 2, 1)
        return cycles, instructions, order, high_d7(settle_d7), exit_sr, 0x006D4C, cell
    c, i = _S13P_CLEAR_TAIL
    cycles += c
    instructions += i
    for a, b in result['stores'].items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb
    exit_sr = _logic_sr(sr, 0, 2)   # 006D56's own moveq #0,d7 is the last flag-setter
    return cycles, instructions, order, 0, exit_sr, 0x006D64, cell


def _state13_settle_cost(read, sr, settle_d7, sp32, d7_register):
    """006CE4-006D64: state 13's own "settle" tail as a whole, reached from `state13_plan`'s own
    head with `settle_d7` either freshly reset to 0 or carrying the caller's own STATE_COUNTER.
    Almost always one pass through `player.state13_settle`; the `'loopback'` arm takes a second pass
    with `FFFFF1AE` now clear -- the SAME single-extra-pass shape `state14_settle` already proves
    bounded, so the loop below is capped at three passes purely as a defensive check."""
    from .game import player

    order = {}
    cycles, instructions = (0, 0)
    current_d7 = settle_d7
    f1ae_override = None
    for _ in range(3):
        result = player.state13_settle(read, current_d7, f1ae_override)
        for a, b in result.get('stores', {}).items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        c, i = _S13_CLEAR
        cycles += c
        instructions += i
        f1ae_nonzero = result['arm'] in ('probe-f1ae', 'loopback')
        c, i = _add(_S14S_F1AE_TEST, _S14S_F1AE_BNE[f1ae_nonzero])
        cycles += c
        instructions += i
        if result['arm'] == 'loopback':
            c, i = _add(_S13S_SHARED_SUBQ, _S13S_RETRY_BEQ[True], _S14S_LOOPBACK_TAIL)
            cycles += c
            instructions += i
            current_d7 = result['next_d7']
            f1ae_override = result['next_f1ae']
            continue
        if result['arm'] == 'probe-f1ae':
            c, i = _add(_S13S_SHARED_SUBQ, _S13S_RETRY_BEQ[False], _S13S_RETRY_BRA)
            cycles += c
            instructions += i
            break
        c, i = _S14S_BUMP
        cycles += c
        instructions += i
        sound = result['sound']
        c, i = _S14S_BUMP_BGT[sound]
        cycles += c
        instructions += i
        if sound:
            c, i = _add(_S14S_SOUND, _S13S_RETRY_BEQ[False], _S13S_RETRY_BRA)
            cycles += c
            instructions += i
        break
    else:
        raise UnsupportedCandidate('state 13 settle: more than two passes through 006CE4 not witnessed by a recording')

    settle_d7_final = result['settle_d7']
    pc, pi, porder, exit_d7, exit_sr, last_pc, cell = _state13_settle_probe_cost(
        read, sr, settle_d7_final, sp32, d7_register)
    cycles += pc
    instructions += pi
    order.update(porder)
    return cycles, instructions, order, exit_d7, exit_sr, last_pc, cell


def _state13_arm_d_cost(read, sr):
    """006CC6-006CE4: state 13's own arm D (the contact-search gate's own fall-through) --
    `FFFFEA1E`'s own SIGN (`tst`+`bpl`, not state 14's own exact `cmpi #1`+`bne`) toggles
    `FFFFF1AE` and transitions to state 14; any non-negative value exits unchanged."""
    from .game import player
    result = player.state13_arm_d(read)
    if result['arm'] == 'unchanged':
        c, i = _add(_S13D_EA1E_TEST, _S13D_EA1E_BPL[True])
        value = read(player.EA1E_WORD, 2) & 0xFFFF
        exit_sr = _logic_sr(sr, value, 2)   # 006CC6 tst.w ea1e is the last (and only) flag-setter
        return c, i, result, 0x006CCA, exit_sr
    c, i = _add(_S13D_EA1E_TEST, _S13D_EA1E_BPL[False], _S14D_TRANS13)
    # 006CDC's own clr.w f1a6.w (the LAST of the two CLRs) is the true last flag-setter (Z=1).
    exit_sr = _logic_sr(sr, 0, 2)
    return c, i, result, 0x006CE0, exit_sr


def _state13_main_dispatch(machine, read, registers, sr, order, exit_registers, cycles, instructions,
                            ea20_one, d7_register):
    """006B84 onward: state 13's own EA20-based arm dispatch (arm A/B, the shared contact-search
    gate, arm D, and the contact-search 'found' continuation) -- the SAME shape
    `_state14_main_dispatch` already establishes, with state 13's own jump-start gate (`FFFFEA1E`'s
    SIGN, not state 14's own `FFFFEA23` bit 0) and arm D's own toggle (into state 14, its own sign
    test too).  `d7_register` is the FULL 32-bit register this dispatch starts with (nothing before
    it touches D7 at all on state 13's own top-level 'main' path)."""
    from .game import player
    exit_registers['d7'] = d7_register
    if ea20_one:
        arm_result = player.state13_arm_a(read)
    else:
        arm_result = player.state13_arm_b(read)

    if 'cell' in arm_result:
        exit_registers['a0'] = arm_result['cell']['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | arm_result['cell']['d0']
        exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | arm_result['cell']['d1']
    if 'd0' in arm_result:
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | arm_result['d0']

    arm_name = arm_result['arm']

    if arm_name in ('transition-9', 'transition-8'):
        # UNWITNESSED for arm A ('transition-9') by any of the four recordings that reach state 13 at
        # all; arm B's own ('transition-8') is witnessed.
        if ea20_one:
            raise UnsupportedCandidate('state 13 arm A transition-9 (FFFFEA1E < 0) not witnessed by a recording')
        c, i = _add(_S13B_EA20_TEST, _S13B_EA20_BPL[False], _S13B_BIT2, _S13B_BIT2_BEQ[True], _S13B_EA1E_TEST,
                    _S13B_EA1E_BMI[True], _S13_TRANS_9_OR_8)
        cycles += c
        instructions += i
        for a, b in arm_result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = arm_result['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x30, 2)   # move.w #$30,fdf6 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006FD6)

    if arm_name in ('transition-1', 'transition-0'):
        if ea20_one:
            for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x006BB2, 4):
                order[a] = b
            c, i = _add(_S13A_BIT2, _S13A_BIT2_BEQ[True], _S13A_EA1E_TEST, _S13A_EA1E_BMI[False], _S13A_HEAD2,
                        _S13A_F1A6_BLE[False], _S13A_GRIDSETUP, GRID_CELL_COST)
            for offset in (1, 0x81, 0x101):
                c, i = _add((c, i), _S13_GRID_TEST, _S13_GRID_BEQ[False])
            c, i = _add((c, i), _S13_NIBBLE_HEAD, _S13A_NIBBLE_BEQ[not arm_result['nibble_tested']])
            if arm_result['nibble_tested']:
                c, i = _add((c, i), _S13A_NIBBLE_TEST, _S13A_NIBBLE_BEQ2[False])
            c, i = _add((c, i), _S13_TRANS_1_OR_0)
        else:
            for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x006C26, 4):
                order[a] = b
            c, i = _add(_S13B_EA20_TEST, _S13B_EA20_BPL[False], _S13B_BIT2, _S13B_BIT2_BEQ[True], _S13B_EA1E_TEST,
                        _S13B_EA1E_BMI[False], _S13B_HEAD2, _S13B_F1A4_BLE[False], _S13B_GRIDSETUP, GRID_CELL_COST)
            for offset in (-1, 0x7F, 0xFF):
                c, i = _add((c, i), _S13_GRID_TEST, _S13_GRID_BEQ[False])
            c, i = _add((c, i), _S13_NIBBLE_HEAD, _S13B_NIBBLE_BEQ[not arm_result['nibble_tested']])
            if arm_result['nibble_tested']:
                c, i = _add((c, i), _S13B_NIBBLE_TEST, _S13B_NIBBLE_BEQ2[False])
            c, i = _add((c, i), _S13_TRANS_1_OR_0)
        cycles += c
        instructions += i
        for a, b in arm_result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['d7'] = arm_result['d7']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _sub_sr(sr, read(player.POSITION_Y, 2), 4, 2)   # the final subq.w #4,POSITION_Y
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006BEC if ea20_one else 0x006C5E)

    # Every remaining arm reaches the shared contact-search gate (006C62), byte-identical to state
    # 14's own (006EC4).
    if ea20_one:
        if arm_name == 'contact-gate':
            c, i = _add(_S13A_BIT2, _S13A_BIT2_BEQ[False], _S13A_SET_F1A8, _S13A_BRA_C)
        elif arm_name == 'contact-gate-f1a6':
            # 006BAC's own ble.b lands on arm B's OWN entry (006BF0), not a dedicated detour block:
            # its own tst.w ea20/bpl.w always takes the positive branch here (EA20 == 1 in arm A).
            c, i = _add(_S13A_BIT2, _S13A_BIT2_BEQ[True], _S13A_EA1E_TEST, _S13A_EA1E_BMI[False], _S13A_HEAD2,
                        _S13A_F1A6_BLE[True], _S13A_DETOUR)
        else:
            for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x006BB2, 4):
                order[a] = b
            c, i = _add(_S13A_BIT2, _S13A_BIT2_BEQ[True], _S13A_EA1E_TEST, _S13A_EA1E_BMI[False], _S13A_HEAD2,
                        _S13A_F1A6_BLE[False], _S13A_GRIDSETUP, GRID_CELL_COST)
            if arm_name == 'contact-gate-grid':
                address = arm_result['cell']['address']
                matched_offset = next(o for o in (1, 0x81, 0x101) if read((address + o) & 0xFFFFFF, 1) == 1)
                for offset in (1, 0x81, 0x101):
                    c, i = _add((c, i), _S13_GRID_TEST, _S13_GRID_BEQ[offset == matched_offset])
                    if offset == matched_offset:
                        break
            else:
                for offset in (1, 0x81, 0x101):
                    c, i = _add((c, i), _S13_GRID_TEST, _S13_GRID_BEQ[False])
                c, i = _add((c, i), _S13_NIBBLE_HEAD, _S13A_NIBBLE_BEQ[False], _S13A_NIBBLE_TEST,
                            _S13A_NIBBLE_BEQ2[True])
            # Every one of arm A's own decline targets (the f1a6 budget, a grid match, a nibble
            # match) lands at 006BF0 (arm B's own entry), the SAME detour the f1a6-budget case takes.
            c, i = _add((c, i), _S13A_DETOUR)
    else:
        if arm_name == 'contact-gate-immediate':
            c, i = _add(_S13B_EA20_TEST, _S13B_EA20_BPL[True])
        elif arm_name == 'contact-gate':
            c, i = _add(_S13B_EA20_TEST, _S13B_EA20_BPL[False], _S13B_BIT2, _S13B_BIT2_BEQ[False], _S13B_SET_F1A8,
                        _S13B_BRA_C)
        elif arm_name == 'contact-gate-f1a4':
            c, i = _add(_S13B_EA20_TEST, _S13B_EA20_BPL[False], _S13B_BIT2, _S13B_BIT2_BEQ[True], _S13B_EA1E_TEST,
                        _S13B_EA1E_BMI[False], _S13B_HEAD2, _S13B_F1A4_BLE[True])
        else:
            for a, b in _bytes((registers['a7'] - 4) & 0xFFFFFF, 0x006C26, 4):
                order[a] = b
            c, i = _add(_S13B_EA20_TEST, _S13B_EA20_BPL[False], _S13B_BIT2, _S13B_BIT2_BEQ[True], _S13B_EA1E_TEST,
                        _S13B_EA1E_BMI[False], _S13B_HEAD2, _S13B_F1A4_BLE[False], _S13B_GRIDSETUP, GRID_CELL_COST)
            if arm_name == 'contact-gate-grid':
                address = arm_result['cell']['address']
                matched_offset = next(o for o in (-1, 0x7F, 0xFF) if read((address + o) & 0xFFFFFF, 1) == 1)
                for offset in (-1, 0x7F, 0xFF):
                    c, i = _add((c, i), _S13_GRID_TEST, _S13_GRID_BEQ[offset == matched_offset])
                    if offset == matched_offset:
                        break
            else:
                for offset in (-1, 0x7F, 0xFF):
                    c, i = _add((c, i), _S13_GRID_TEST, _S13_GRID_BEQ[False])
                c, i = _add((c, i), _S13_NIBBLE_HEAD, _S13B_NIBBLE_BEQ[False], _S13B_NIBBLE_TEST,
                            _S13B_NIBBLE_BEQ2[True])
    cycles += c
    instructions += i
    for a, b in arm_result.get('stores', {}).items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb

    gc, gi, contact, has_contact = _state14_contact_cost(read, sr, arm_result)
    cycles += gc
    instructions += gi

    if not has_contact:
        sp32 = registers['a7']
        arm_d_c, arm_d_i, arm_d_result, arm_d_last_pc, arm_d_sr = _state13_arm_d_cost(read, sr)
        cycles += arm_d_c
        instructions += arm_d_i
        for a, b in arm_d_result.get('stores', {}).items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = arm_d_sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=arm_d_last_pc)

    sp32 = registers['a7']
    return_pc = 0x006CA0 if contact['negative'] else 0x006C76
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, return_pc, 4):
        order[a] = b
    cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
        machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4}, sp32 - 4)
    cycles += cs_cycles
    instructions += cs_instructions
    order.update(cs_order)
    exit_registers.update(cs_registers)
    exit_registers['d0'] = cs_registers['d0']
    c, i = _S14C_TST_D0
    cycles += c
    instructions += i
    found = cs_result['d0'] == 0
    c, i = _S14C_BNE_D0[not found]
    cycles += c
    instructions += i

    if not found:
        arm_d_c, arm_d_i, arm_d_result, arm_d_last_pc, arm_d_sr = _state13_arm_d_cost(read, cs_registers['sr'])
        cycles += arm_d_c
        instructions += arm_d_i
        for a, b in arm_d_result.get('stores', {}).items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = arm_d_sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=arm_d_last_pc)

    found_result = player.state14_contact_found(read, d7_register & 0xFFFF, contact['negative'])
    c, i = _add(_S14C_FOUND_HEAD, _S14C_FOUND_BTST)
    cycles += c
    instructions += i
    even = (d7_register & 1) == 0
    c, i = _S14C_FOUND_BNE[not even]
    cycles += c
    instructions += i
    if even:
        c, i = _S14C_FOUND_SUBQ
        cycles += c
        instructions += i
    c, i = _S14C_FOUND_TAIL
    cycles += c
    instructions += i
    for a, b in found_result['stores'].items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb
    exit_registers['d7'] = found_result['d7']
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = _logic_sr(cs_registers['sr'], 0, 2)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x006C98 if not contact['negative'] else 0x006CC2)


def state13_plan(machine, registers):
    """006B4E (state 13): the player state machine's own dispatch table entry 13, state 14's own
    counterpart.  See `game.player`'s own module note above `state13_step` for the shape."""
    from .game import player
    if registers['pc'] != STATE13_ENTRY:
        raise UnsupportedCandidate('state 13 planner needs the machine parked at 006B4E')
    sr = registers['sr']
    read = _reader(machine)
    d7 = registers['d7'] & 0xFFFF
    head = player.state13_step(read, d7)
    order = {}
    exit_registers = {}

    if head['arm'] == 'frozen':
        cycles, instructions = _add(_S13_FROZEN_TEST, _S13_FROZEN_BEQ[True])
        exit_sr = _logic_sr(sr, 0, 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=(),
                          registers={'pc': 0x0075D6, 'sr': exit_sr}, last_pc=0x006B52)

    cycles, instructions = _add(_S13_FROZEN_TEST, _S13_FROZEN_BEQ[False], _S13_WRAP_TEST)

    if head['arm'] == 'settle':
        c, i = _S13_WRAP_BLT[not head['reset']]
        cycles += c
        instructions += i
        if head['reset']:
            c, i = _S13_WRAP_RESET
            cycles += c
            instructions += i
            settle_d7_register = 0
        else:
            c, i = _add(_S13_EA20_TEST0, _S13_EA20_BNE0[False], _S13_SETTLE_GATE_TEST, _S13_SETTLE_GATE_BEQ[True])
            cycles += c
            instructions += i
            settle_d7_register = registers['d7']
        sc, si, sorder, exit_d7, exit_sr, last_pc, cell = _state13_settle_cost(
            read, sr, head['settle_d7'], registers['a7'], settle_d7_register)
        cycles += sc
        instructions += si
        order.update(sorder)
        if cell is not None:
            exit_registers['a0'] = cell['address'] & 0xFFFFFFFF
            exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell['d0']
            exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell['d1']
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = exit_sr
        if exit_d7 is not None:
            exit_registers['d7'] = exit_d7
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    # head['arm'] == 'main': reached either with FFFFEA20 != 0 (skips straight past the clears,
    # head['stores'] empty) or FFFFEA20 == 0 and FFFFEA1E != 1 (the clears ran, head['stores'] holds
    # them) -- game.player.state13_step's own return already tells which.
    ea20_cleared = bool(head.get('stores'))
    c, i = _S13_WRAP_BLT[True]
    cycles += c
    instructions += i
    if ea20_cleared:
        c, i = _add(_S13_EA20_TEST0, _S13_EA20_BNE0[False], _S13_SETTLE_GATE_TEST, _S13_SETTLE_GATE_BEQ[False],
                    _S13_CLEAR)
    else:
        c, i = _add(_S13_EA20_TEST0, _S13_EA20_BNE0[True])
    cycles += c
    instructions += i
    for a, b in head.get('stores', {}).items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb
    c, i = _add(_S13_ARMSEL_TEST, _S13_ARMSEL_BNE[not head['ea20_one']])
    cycles += c
    instructions += i

    return _state13_main_dispatch(machine, read, registers, sr, order, exit_registers, cycles,
                                   instructions, head['ea20_one'], registers['d7'])


# --- 005FF4: state 12 (game.player.state12_step / state12_oscillate / state12_block_test_left /
# state12_block_test_right / state12_ground_tail) -- an oscillating swing/pendulum dispatcher, a
# genuinely NEW shape (not a horizontal/vertical/falling twin), sharing the already-recovered grid
# cell and contact search and the zone check's own COOLDOWN/SUPPRESS_COOLDOWN fields.  Costed one
# instruction-block at a time from the tracer on real fixtures over census-005FF4-* covering every
# real terminal shape (609 real path classes over all five recordings collapse to six: exit
# unchanged via a closed trigger gate or a 'not found' search, a state-22 trigger, and the ground
# tail's own three real exits).  No d7 (STATE_COUNTER) is ever read as an input.
STATE12_ENTRY = 0x005FF4

_S12_ADVANCE_Y = (16, 1)                     # 005FF4 addq.w #4,f18e.w
_S12_READ_F194 = (12, 1)                     # 005FF8 move.w f194,d0
_S12_ASR2 = (10, 1)                          # 005FFC asr.w #2,d0
_S12_ADD_F198 = (16, 1)                      # 005FFE add.w d0,f198.w
_S12_HOLD_TEST = (12, 1)                     # 006002 tst.w ef4c.w
_S12_HOLD_BNE = {True: (10, 1), False: (8, 1)}          # 006006 bne.b -- taken(!=0): skip the bump
_S12_BUMP = (16 + 16, 2)                     # 006008 addq.w #1,f194 (mem); 00600C cmpi.w #$a,f194 (mem)
_S12_BUMP_BLE = {True: (10, 1), False: (8, 1)}          # 006012 ble.b -- taken(<=10): no cap needed
_S12_CAP = (16, 1)                           # 006014 move.w #$a,f194.w
_S12_STEP_Y2 = (12 + 16, 2)                  # 00601A move.w f194,d0; 00601E add.w d0,f18e.w (mem)
_S12_TICK = (16 + 16, 2)                     # 006022 addq.w #1,f198 (mem); 006026 cmpi.w #8,f198 (mem)
_S12_TICK_BNE = {True: (10, 1), False: (8, 1)}          # 00602C bne.b -- taken(!=8): no sound
_S12_SOUND = (16, 1)                         # 00602E move.w #$50,fdf4.w
_S12_BSR_GRID = (18, 1)                      # bsr.w $63fa (both call sites, 006034/0060E6)

_S12_LEFT_GATE_TEST = (16, 1)                # 006038 cmpi.w #$ffff,ea20.w
_S12_LEFT_GATE_BNE = {True: (10, 1), False: (8, 1)}     # 00603E bne.b -- taken(!=-1): skip the left arm
_S12_RETRY_TEST = (16, 1)                    # cmpi.w #6,f1a0.w (both arms)
_S12_RETRY_BGE = {True: (10, 1), False: (8, 1)}         # bge.b -- taken(>=6): budget exhausted, skip
_S12_LEFT_SET_STATE = (16, 1)                # 006048 move.w #$b,f192.w
_S12_LR_HEAD = (12 + 8, 2)                   # move f18c,d0; andi.w #imm,d0
_S12_LEFT_BNE_LOW = {True: (10, 1), False: (8, 1)}      # 006056 bne.b -- taken(low!=0): skip the block test
_S12_GRID_TEST = (16, 1)                     # cmpi.b #1,offset(a0)
_S12_GRID_BEQ = {True: (10, 1), False: (8, 1)}          # beq.b -- taken: blocked, decline
_S12_NIBBLE_HEAD = (12 + 8, 2)               # move f18e,d0; andi #$f,d0
_S12_NIBBLE_BEQ = {True: (10, 1), False: (8, 1)}        # beq.b -- taken(==0): skip the nibble test
_S12_NIBBLE_TEST = (16, 1)                   # cmpi.b #1,offset(a0)
_S12_NIBBLE_BEQ2 = {True: (10, 1), False: (8, 1)}       # beq.b -- taken: blocked, decline
_S12_LEFT_ADVANCE = (16 + 16, 2)             # 006082 subq.w #4,f18c (mem); 006086 addq.w #1,f1a0 (mem)

_S12_RIGHT_GATE_TEST = (16, 1)               # 00608A cmpi.w #1,ea20.w
_S12_RIGHT_GATE_BNE = {True: (10, 1), False: (8, 1)}    # 006090 bne.b -- taken(!=1): skip the right arm
_S12_RIGHT_SET_STATE = (16, 1)               # 00609A move.w #$c,f192.w
_S12_RIGHT_MASK_TEST = (8, 1)                # 0060A8 cmpi.w #$1c,d0
_S12_RIGHT_MASK_BEQ = {True: (10, 1), False: (8, 1)}    # 0060AC beq.b -- taken(==0x1c): straight to the grid test
_S12_RIGHT_LOW_TEST = (8, 1)                 # 0060AE cmpi.w #8,d0
_S12_RIGHT_LOW_BGE = {True: (10, 1), False: (8, 1)}     # 0060B2 bge.b -- taken(>=8): skip the block test outright
_S12_RIGHT_ADVANCE = (16 + 16, 2)            # 0060DE addq.w #4,f18c (mem); 0060E2 addq.w #1,f1a0 (mem)

_S12_TAIL_MOVEQ = (4, 1)                     # 0060EA moveq #0,d7
_S12_GROUND_TEST = (16, 1)                   # 0060EC cmpi.b #1,$180(a0)
_S12_GROUND_BEQ = {True: (10, 1), False: (8, 1)}        # 0060F2 beq.b -- taken: ground found
_S12_ALT_HEAD = (12 + 8, 2)                  # 0060F4 move f18c,d0; 0060F8 andi.w #$1c,d0
_S12_ALT_TEST = (8, 1)                       # 0060FC cmpi.w #8,d0
_S12_ALT_BLT = {True: (10, 1), False: (8, 1)}           # 006100 blt.b -- taken(<8): skip the alt test
_S12_ALT_GROUND_TEST = (16, 1)               # 006102 cmpi.b #1,$181(a0)
_S12_ALT_GROUND_BEQ = {True: (10, 1), False: (8, 1)}    # 006108 beq.b -- taken: ground found (alt)
_S12_TRIGGER_BIT2 = (16, 1)                  # 00610A btst.b #2,ea23.w
_S12_TRIGGER_BIT2_BEQ = {True: (10, 1), False: (12, 1)} # 006110 beq.w -- taken(clear): exit unchanged
_S12_BSR_SEARCH = (18, 1)                    # 006114 bsr.w $8222
_S12_TRIGGER_TST_D0 = (4, 1)                 # 006118 tst.w d0
_S12_TRIGGER_BNE_D0 = {True: (10, 1), False: (12, 1)}   # 00611A bne.w -- taken(!=0, not found): exit unchanged
_S12_TRIGGER_TAIL = (16 + 4 + 12 + 10, 4)    # 00611E move.w #$16,f192; moveq #1,d7; move.w d7,f1ba; bra.w

_S12G_HEAD = (16 + 20 + 16 + 4 + 16, 5)      # move state; andi f18e #$fff0; clr f1b8; moveq #0,d7; move #$39,fdf6
_S12G_TICK_TEST = (12 + 8, 2)                # move f198,d0; subi.w #$14,d0
_S12G_TICK_BLE = {True: (10, 1), False: (12, 1)}        # ble.w -- taken(<=0): exit unchanged
_S12G_SUPPRESS_TEST = (12, 1)                # tst.w f1b6.w
_S12G_SUPPRESS_BNE = {True: (10, 1), False: (12, 1)}    # bne.w -- taken(!=0): exit unchanged
_S12G_APPLY = (8 + 16 + 10, 3)               # asr.w #1,d0; sub.w d0,ef3e.w; bra.w


def _state12_head_cost(read):
    """005FF4-006033: state 12's own oscillation head."""
    from .game import player
    osc = player.state12_oscillate(read)
    c, i = _add(_S12_ADVANCE_Y, _S12_READ_F194, _S12_ASR2, _S12_ADD_F198, _S12_HOLD_TEST)
    hold = read(player.F194_HOLD, 2) & 0xFFFF != 0
    c, i = _add((c, i), _S12_HOLD_BNE[hold])
    if not hold:
        f194_raw = read(player.F194, 2)
        bumped = (f194_raw + 1) & 0xFFFF
        capped = bumped > player.STATE12_OSCILLATION_CAP
        c, i = _add((c, i), _S12_BUMP, _S12_BUMP_BLE[not capped])
        if capped:
            c, i = _add((c, i), _S12_CAP)
    c, i = _add((c, i), _S12_STEP_Y2, _S12_TICK)
    sound = osc['f198'] == player.STATE12_TICK_CAP
    c, i = _add((c, i), _S12_TICK_BNE[not sound])
    if sound:
        c, i = _add((c, i), _S12_SOUND)
    return c, i, osc


def state12_plan(machine, registers):
    """005FF4 (state 12): the player state machine's own dispatch table entry 12, an oscillating
    swing/pendulum dispatcher.  See `game.player`'s own module note above `state12_step`."""
    from .game import player
    from .game.grid import grid_cell
    if registers['pc'] != STATE12_ENTRY:
        raise UnsupportedCandidate('state 12 planner needs the machine parked at 005FF4')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    order = {}
    exit_registers = {'d7': registers['d7']}

    hc, hi, osc = _state12_head_cost(read)
    cycles, instructions = hc, hi
    new_y = (read(player.POSITION_Y, 2) + osc['position_y_delta']) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, osc['f194'], 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, osc['f198'], 2):
        order[a] = b
    if osc['sound']:
        from .game.hazard import SOUND_COMMAND
        for a, b in _bytes(SOUND_COMMAND & 0xFFFFFF, 0x50, 2):
            order[a] = b
    sr = _cmp_sr(sr, osc['f198'], player.STATE12_TICK_CAP, 2)   # 006026's own cmpi.w is the last flag-setter so far

    # 005FF4's own addq.w #4,f18e.w and 00601E's own add.w d0,f18e.w are REAL, IMMEDIATE memory
    # writes -- POSITION_Y is already at `new_y` in real RAM by the time the grid_cell calls, the
    # block tests and the ground tests below run; the machine snapshot itself is not yet updated
    # (this is a plan computation, not a real execution), so every read from here on must see the
    # advanced value, not the parked one.
    read_orig = read

    def read(a, s, _y=new_y):
        return _y if (a & 0xFFFFFF) == (player.POSITION_Y & 0xFFFFFF) else read_orig(a, s)

    ea20 = player._signed_word(read(player.EA20_WORD, 2))
    position_x = read(player.POSITION_X, 2)
    f1a0 = read(player.F1A0, 2)

    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006038, 4))
    cell1 = grid_cell(read)
    exit_registers['a0'] = cell1['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell1['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell1['d1']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)

    c, i = _S12_LEFT_GATE_TEST
    cycles += c
    instructions += i
    retry_open = f1a0 < player.STATE12_RETRY_CAP
    provisional_state = None
    position_x_after = position_x
    if ea20 == -1:
        c, i = _S12_LEFT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if not retry_open:
            raise UnsupportedCandidate('state 12 left arm retry budget exhausted (FFFFF1A0 >= 6) not witnessed by a recording')
        provisional_state = 0xB
        c, i = _S12_LEFT_SET_STATE
        cycles += c
        instructions += i
        address = cell1['address']
        low = position_x & 0x1F
        c, i = _S12_LR_HEAD
        cycles += c
        instructions += i
        c, i = _S12_LEFT_BNE_LOW[low != 0]
        cycles += c
        instructions += i
        blocked = False
        if low == 0:
            for offset in (-1, 0x7F, 0xFF):
                c, i = _S12_GRID_TEST
                cycles += c
                instructions += i
                hit = read((address + offset) & 0xFFFFFF, 1) == 1
                c, i = _S12_GRID_BEQ[hit]
                cycles += c
                instructions += i
                if hit:
                    blocked = True
                    break
            if not blocked:
                nibble = read(player.POSITION_Y, 2) & 0xF
                c, i = _S12_NIBBLE_HEAD
                cycles += c
                instructions += i
                c, i = _S12_NIBBLE_BEQ[nibble == 0]
                cycles += c
                instructions += i
                if nibble != 0:
                    c, i = _S12_NIBBLE_TEST
                    cycles += c
                    instructions += i
                    blocked = read((address + 0x17F) & 0xFFFFFF, 1) == 1
                    c, i = _S12_NIBBLE_BEQ2[blocked]
                    cycles += c
                    instructions += i
        if not blocked:
            c, i = _S12_LEFT_ADVANCE
            cycles += c
            instructions += i
            position_x_after = (position_x - 4) & 0xFFFF
            for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                order[a] = b
            for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                order[a] = b
    else:
        c, i = _S12_LEFT_GATE_BNE[True]
        cycles += c
        instructions += i

    c, i = _S12_RIGHT_GATE_TEST
    cycles += c
    instructions += i
    if ea20 == 1:
        c, i = _S12_RIGHT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if retry_open:
            provisional_state = 0xC
            c, i = _S12_RIGHT_SET_STATE
            cycles += c
            instructions += i
            address = cell1['address']
            low = position_x & 0x1C
            c, i = _add(_S12_LR_HEAD, _S12_RIGHT_MASK_TEST)
            cycles += c
            instructions += i
            mask_match = low == 0x1C
            c, i = _S12_RIGHT_MASK_BEQ[mask_match]
            cycles += c
            instructions += i
            run_test = mask_match
            if not mask_match:
                c, i = _S12_RIGHT_LOW_TEST
                cycles += c
                instructions += i
                skip_test = low >= 8
                c, i = _S12_RIGHT_LOW_BGE[skip_test]
                cycles += c
                instructions += i
                run_test = not skip_test
            blocked = False
            if run_test:
                for offset in (1, 0x81, 0x101):
                    c, i = _S12_GRID_TEST
                    cycles += c
                    instructions += i
                    hit = read((address + offset) & 0xFFFFFF, 1) == 1
                    c, i = _S12_GRID_BEQ[hit]
                    cycles += c
                    instructions += i
                    if hit:
                        blocked = True
                        break
                if not blocked:
                    nibble = read(player.POSITION_Y, 2) & 0xF
                    c, i = _S12_NIBBLE_HEAD
                    cycles += c
                    instructions += i
                    c, i = _S12_NIBBLE_BEQ[nibble == 0]
                    cycles += c
                    instructions += i
                    if nibble != 0:
                        c, i = _S12_NIBBLE_TEST
                        cycles += c
                        instructions += i
                        blocked = read((address + 0x181) & 0xFFFFFF, 1) == 1
                        c, i = _S12_NIBBLE_BEQ2[blocked]
                        cycles += c
                        instructions += i
            if not blocked:
                c, i = _S12_RIGHT_ADVANCE
                cycles += c
                instructions += i
                position_x_after = (position_x + 4) & 0xFFFF
                for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                    order[a] = b
                for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                    order[a] = b
    else:
        c, i = _S12_RIGHT_GATE_BNE[True]
        cycles += c
        instructions += i

    if provisional_state is not None:
        for a, b in _bytes(player.STATE_INDEX, provisional_state, 2):
            order[a] = b

    def _read_after_move(a, s, _x=position_x_after):
        return _x if (a & 0xFFFFFF) == (player.POSITION_X & 0xFFFFFF) else read(a, s)
    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0060EA, 4))
    cell2 = grid_cell(_read_after_move)
    address2 = cell2['address']
    exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell2['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell2['d1']
    sr = _asl_sr(sr, cell2['row_source'], 3, 2)

    c, i = _S12_TAIL_MOVEQ
    cycles += c
    instructions += i
    exit_registers['d7'] = 0
    c, i = _S12_GROUND_TEST
    cycles += c
    instructions += i
    ground = read((address2 + 0x180) & 0xFFFFFF, 1) == 1
    c, i = _S12_GROUND_BEQ[ground]
    cycles += c
    instructions += i
    alt_low = None
    if not ground:
        # 0060F4/0060F8 run UNCONDITIONALLY once the first ground test fails, overwriting D0 with
        # POSITION_X's own low bits (& 0x1c) -- not grid_cell's own column -- and 0060FC's own
        # cmpi.w #8,d0 is the last flag-setter until btst below touches Z alone.
        low = _read_after_move(player.POSITION_X, 2) & 0x1C
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | low
        c, i = _add(_S12_ALT_HEAD, _S12_ALT_TEST)
        cycles += c
        instructions += i
        sr = _cmp_sr(sr, low, 8, 2)
        alt_low = low < 8
        c, i = _S12_ALT_BLT[alt_low]
        cycles += c
        instructions += i
        if not alt_low:
            c, i = _S12_ALT_GROUND_TEST
            cycles += c
            instructions += i
            alt_byte = read((address2 + 0x181) & 0xFFFFFF, 1)
            ground = alt_byte == 1
            sr = _cmp_sr(sr, alt_byte, 1, 1)
            c, i = _S12_ALT_GROUND_BEQ[ground]
            cycles += c
            instructions += i

    if ground:
        for a, b in _bytes(player.STATE_INDEX, player.STATE12_GROUND_INDEX, 2):
            order[a] = b
        masked_y = new_y & 0xFFF0
        for a, b in _bytes(player.POSITION_Y, masked_y, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        from .game.zones import COOLDOWN, SUPPRESS_COOLDOWN
        c, i = _S12G_HEAD
        cycles += c
        instructions += i
        c, i = _S12G_TICK_TEST
        cycles += c
        instructions += i
        d0 = player._signed_word((osc['f198'] - 0x14) & 0xFFFF)
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | ((osc['f198'] - 0x14) & 0xFFFF)
        c, i = _S12G_TICK_BLE[d0 <= 0]
        cycles += c
        instructions += i
        if d0 <= 0:
            sr = _sub_sr(sr, osc['f198'], 0x14, 2)   # 00614A subi.w #$14,d0: a real subtract, X follows C
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x00614E)
        suppress = read(SUPPRESS_COOLDOWN, 2) & 0xFFFF != 0
        c, i = _S12G_SUPPRESS_TEST
        cycles += c
        instructions += i
        c, i = _S12G_SUPPRESS_BNE[suppress]
        cycles += c
        instructions += i
        if suppress:
            sr = _logic_sr(sr, read(SUPPRESS_COOLDOWN, 2), 2)
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x006156)
        half = d0 >> 1
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | (half & 0xFFFF)   # 00615A asr.w #1,d0
        cooldown = (read(COOLDOWN, 2) - half) & 0xFFFF
        for a, b in _bytes(COOLDOWN & 0xFFFFFF, cooldown, 2):
            order[a] = b
        c, i = _S12G_APPLY
        cycles += c
        instructions += i
        sr = _sub_sr(sr, read(COOLDOWN, 2), half, 2)
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006160)

    c, i = _S12_TRIGGER_BIT2
    cycles += c
    instructions += i
    bit2 = read(player.EA23_WORD, 1) & 4
    c, i = _S12_TRIGGER_BIT2_BEQ[not bit2]
    cycles += c
    instructions += i
    if not bit2:
        # btst only ever touches Z; N/V/C/X are retained from whatever the last flag-setter left
        # (the ground/alt-ground path's own cmpi.w #8,d0 when the alt test ran, sr already carries it).
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = (sr & ~0x04) | (0x00 if bit2 else 0x04)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006110)

    c, i = _S12_BSR_SEARCH
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x006118, 4):
        order[a] = b
    cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
        machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4, 'sr': sr}, sp32 - 4)
    cycles += cs_cycles
    instructions += cs_instructions
    order.update(cs_order)
    exit_registers.update(cs_registers)
    sr = cs_registers['sr']
    c, i = _S12_TRIGGER_TST_D0
    cycles += c
    instructions += i
    found = cs_result['d0'] == 0
    c, i = _S12_TRIGGER_BNE_D0[not found]
    cycles += c
    instructions += i
    if not found:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, cs_result['d0'], 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00611A)

    c, i = _S12_TRIGGER_TAIL
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, player.STATE12_TRIGGER_INDEX, 2):
        order[a] = b
    for a, b in _bytes(player.F1BA & 0xFFFFFF, 1, 2):
        order[a] = b
    exit_registers['d7'] = 1
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = _logic_sr(sr, 1, 2)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x00612A)


# --- 005D32: state 11 (game.player.state11_step / state11_ground_tail) -- BYTE-IDENTICAL to
# state 12's own oscillation head and EA20-gated block test (confirmed via a raw ROM diff,
# rom[0x005D32:0x005E28] == rom[0x005FF4:0x0060EA], differing only in relocated branch
# displacement bytes); the ground tail's real instructions are the same four stores, just
# reordered in the ROM (clr f1b8/moveq d7/move fdf6 BEFORE andi f18e, unlike state 12's
# andi-second order) -- functionally identical, so every _S12_*/_S12G_* cost constant is reused
# directly.  Costed against census-005D32-* (five recordings, 693 occurrences collapsing to the
# same six real terminal shapes as state 12) plus one targeted segment_verify capture for the
# LEFT arm (FFFFEA20 == -1), which no whole-history census fixture reached as its own
# path-signature class.  No d7 is ever read as an input.
STATE11_ENTRY = 0x005D32


def state11_plan(machine, registers):
    """005D32 (state 11): the player state machine's own dispatch table entry 11, BYTE-IDENTICAL to
    state 12's own oscillation head and EA20-gated block test (see `game.player`'s own module note
    above `state11_step`); only the ground tail's target constants differ."""
    from .game import player
    from .game.grid import grid_cell
    if registers['pc'] != STATE11_ENTRY:
        raise UnsupportedCandidate('state 11 planner needs the machine parked at 005D32')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    order = {}
    exit_registers = {'d7': registers['d7']}

    hc, hi, osc = _state12_head_cost(read)
    cycles, instructions = hc, hi
    new_y = (read(player.POSITION_Y, 2) + osc['position_y_delta']) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, osc['f194'], 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, osc['f198'], 2):
        order[a] = b
    if osc['sound']:
        from .game.hazard import SOUND_COMMAND
        for a, b in _bytes(SOUND_COMMAND & 0xFFFFFF, 0x50, 2):
            order[a] = b
    sr = _cmp_sr(sr, osc['f198'], player.STATE12_TICK_CAP, 2)   # 006026's own cmpi.w is the last flag-setter so far

    # 005FF4's own addq.w #4,f18e.w and 00601E's own add.w d0,f18e.w are REAL, IMMEDIATE memory
    # writes -- POSITION_Y is already at `new_y` in real RAM by the time the grid_cell calls, the
    # block tests and the ground tests below run; the machine snapshot itself is not yet updated
    # (this is a plan computation, not a real execution), so every read from here on must see the
    # advanced value, not the parked one.
    read_orig = read

    def read(a, s, _y=new_y):
        return _y if (a & 0xFFFFFF) == (player.POSITION_Y & 0xFFFFFF) else read_orig(a, s)

    ea20 = player._signed_word(read(player.EA20_WORD, 2))
    position_x = read(player.POSITION_X, 2)
    f1a0 = read(player.F1A0, 2)

    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x005D76, 4))
    cell1 = grid_cell(read)
    exit_registers['a0'] = cell1['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell1['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell1['d1']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)

    c, i = _S12_LEFT_GATE_TEST
    cycles += c
    instructions += i
    retry_open = f1a0 < player.STATE12_RETRY_CAP
    provisional_state = None
    position_x_after = position_x
    if ea20 == -1:
        c, i = _S12_LEFT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if not retry_open:
            raise UnsupportedCandidate('state 11 left arm retry budget exhausted (FFFFF1A0 >= 6) not witnessed by a recording')
        provisional_state = 0xB
        c, i = _S12_LEFT_SET_STATE
        cycles += c
        instructions += i
        address = cell1['address']
        low = position_x & 0x1F
        c, i = _S12_LR_HEAD
        cycles += c
        instructions += i
        c, i = _S12_LEFT_BNE_LOW[low != 0]
        cycles += c
        instructions += i
        blocked = False
        if low == 0:
            for offset in (-1, 0x7F, 0xFF):
                c, i = _S12_GRID_TEST
                cycles += c
                instructions += i
                hit = read((address + offset) & 0xFFFFFF, 1) == 1
                c, i = _S12_GRID_BEQ[hit]
                cycles += c
                instructions += i
                if hit:
                    blocked = True
                    break
            if not blocked:
                nibble = read(player.POSITION_Y, 2) & 0xF
                c, i = _S12_NIBBLE_HEAD
                cycles += c
                instructions += i
                c, i = _S12_NIBBLE_BEQ[nibble == 0]
                cycles += c
                instructions += i
                if nibble != 0:
                    c, i = _S12_NIBBLE_TEST
                    cycles += c
                    instructions += i
                    blocked = read((address + 0x17F) & 0xFFFFFF, 1) == 1
                    c, i = _S12_NIBBLE_BEQ2[blocked]
                    cycles += c
                    instructions += i
        if not blocked:
            c, i = _S12_LEFT_ADVANCE
            cycles += c
            instructions += i
            position_x_after = (position_x - 4) & 0xFFFF
            for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                order[a] = b
            for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                order[a] = b
    else:
        c, i = _S12_LEFT_GATE_BNE[True]
        cycles += c
        instructions += i

    c, i = _S12_RIGHT_GATE_TEST
    cycles += c
    instructions += i
    if ea20 == 1:
        c, i = _S12_RIGHT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if retry_open:
            provisional_state = 0xC
            c, i = _S12_RIGHT_SET_STATE
            cycles += c
            instructions += i
            address = cell1['address']
            low = position_x & 0x1C
            c, i = _add(_S12_LR_HEAD, _S12_RIGHT_MASK_TEST)
            cycles += c
            instructions += i
            mask_match = low == 0x1C
            c, i = _S12_RIGHT_MASK_BEQ[mask_match]
            cycles += c
            instructions += i
            run_test = mask_match
            if not mask_match:
                c, i = _S12_RIGHT_LOW_TEST
                cycles += c
                instructions += i
                skip_test = low >= 8
                c, i = _S12_RIGHT_LOW_BGE[skip_test]
                cycles += c
                instructions += i
                run_test = not skip_test
            blocked = False
            if run_test:
                for offset in (1, 0x81, 0x101):
                    c, i = _S12_GRID_TEST
                    cycles += c
                    instructions += i
                    hit = read((address + offset) & 0xFFFFFF, 1) == 1
                    c, i = _S12_GRID_BEQ[hit]
                    cycles += c
                    instructions += i
                    if hit:
                        blocked = True
                        break
                if not blocked:
                    nibble = read(player.POSITION_Y, 2) & 0xF
                    c, i = _S12_NIBBLE_HEAD
                    cycles += c
                    instructions += i
                    c, i = _S12_NIBBLE_BEQ[nibble == 0]
                    cycles += c
                    instructions += i
                    if nibble != 0:
                        c, i = _S12_NIBBLE_TEST
                        cycles += c
                        instructions += i
                        blocked = read((address + 0x181) & 0xFFFFFF, 1) == 1
                        c, i = _S12_NIBBLE_BEQ2[blocked]
                        cycles += c
                        instructions += i
            if not blocked:
                c, i = _S12_RIGHT_ADVANCE
                cycles += c
                instructions += i
                position_x_after = (position_x + 4) & 0xFFFF
                for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                    order[a] = b
                for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                    order[a] = b
    else:
        c, i = _S12_RIGHT_GATE_BNE[True]
        cycles += c
        instructions += i

    if provisional_state is not None:
        for a, b in _bytes(player.STATE_INDEX, provisional_state, 2):
            order[a] = b

    def _read_after_move(a, s, _x=position_x_after):
        return _x if (a & 0xFFFFFF) == (player.POSITION_X & 0xFFFFFF) else read(a, s)
    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x005E28, 4))
    cell2 = grid_cell(_read_after_move)
    address2 = cell2['address']
    exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell2['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell2['d1']
    sr = _asl_sr(sr, cell2['row_source'], 3, 2)

    c, i = _S12_TAIL_MOVEQ
    cycles += c
    instructions += i
    exit_registers['d7'] = 0
    c, i = _S12_GROUND_TEST
    cycles += c
    instructions += i
    ground = read((address2 + 0x180) & 0xFFFFFF, 1) == 1
    c, i = _S12_GROUND_BEQ[ground]
    cycles += c
    instructions += i
    alt_low = None
    if not ground:
        # 0060F4/0060F8 run UNCONDITIONALLY once the first ground test fails, overwriting D0 with
        # POSITION_X's own low bits (& 0x1c) -- not grid_cell's own column -- and 0060FC's own
        # cmpi.w #8,d0 is the last flag-setter until btst below touches Z alone.
        low = _read_after_move(player.POSITION_X, 2) & 0x1C
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | low
        c, i = _add(_S12_ALT_HEAD, _S12_ALT_TEST)
        cycles += c
        instructions += i
        sr = _cmp_sr(sr, low, 8, 2)
        alt_low = low < 8
        c, i = _S12_ALT_BLT[alt_low]
        cycles += c
        instructions += i
        if not alt_low:
            c, i = _S12_ALT_GROUND_TEST
            cycles += c
            instructions += i
            alt_byte = read((address2 + 0x181) & 0xFFFFFF, 1)
            ground = alt_byte == 1
            sr = _cmp_sr(sr, alt_byte, 1, 1)
            c, i = _S12_ALT_GROUND_BEQ[ground]
            cycles += c
            instructions += i

    if ground:
        for a, b in _bytes(player.STATE_INDEX, player.STATE11_GROUND_INDEX, 2):
            order[a] = b
        masked_y = new_y & 0xFFF0
        for a, b in _bytes(player.POSITION_Y, masked_y, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        from .game.zones import COOLDOWN, SUPPRESS_COOLDOWN
        c, i = _S12G_HEAD
        cycles += c
        instructions += i
        c, i = _S12G_TICK_TEST
        cycles += c
        instructions += i
        d0 = player._signed_word((osc['f198'] - 0x14) & 0xFFFF)
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | ((osc['f198'] - 0x14) & 0xFFFF)
        c, i = _S12G_TICK_BLE[d0 <= 0]
        cycles += c
        instructions += i
        if d0 <= 0:
            sr = _sub_sr(sr, osc['f198'], 0x14, 2)   # 00614A subi.w #$14,d0: a real subtract, X follows C
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x005E8C)
        suppress = read(SUPPRESS_COOLDOWN, 2) & 0xFFFF != 0
        c, i = _S12G_SUPPRESS_TEST
        cycles += c
        instructions += i
        c, i = _S12G_SUPPRESS_BNE[suppress]
        cycles += c
        instructions += i
        if suppress:
            sr = _logic_sr(sr, read(SUPPRESS_COOLDOWN, 2), 2)
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x005E94)
        half = d0 >> 1
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | (half & 0xFFFF)   # 00615A asr.w #1,d0
        cooldown = (read(COOLDOWN, 2) - half) & 0xFFFF
        for a, b in _bytes(COOLDOWN & 0xFFFFFF, cooldown, 2):
            order[a] = b
        c, i = _S12G_APPLY
        cycles += c
        instructions += i
        sr = _sub_sr(sr, read(COOLDOWN, 2), half, 2)
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x005E9E)

    c, i = _S12_TRIGGER_BIT2
    cycles += c
    instructions += i
    bit2 = read(player.EA23_WORD, 1) & 4
    c, i = _S12_TRIGGER_BIT2_BEQ[not bit2]
    cycles += c
    instructions += i
    if not bit2:
        # btst only ever touches Z; N/V/C/X are retained from whatever the last flag-setter left
        # (the ground/alt-ground path's own cmpi.w #8,d0 when the alt test ran, sr already carries it).
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = (sr & ~0x04) | (0x00 if bit2 else 0x04)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x005E4E)

    c, i = _S12_BSR_SEARCH
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x005E56, 4):
        order[a] = b
    cs_cycles, cs_instructions, cs_order, cs_registers, cs_result = _contact_search_resolve(
        machine, read, {**registers, 'pc': CONTACT_SEARCH_ENTRY, 'a7': sp32 - 4, 'sr': sr}, sp32 - 4)
    cycles += cs_cycles
    instructions += cs_instructions
    order.update(cs_order)
    exit_registers.update(cs_registers)
    sr = cs_registers['sr']
    c, i = _S12_TRIGGER_TST_D0
    cycles += c
    instructions += i
    found = cs_result['d0'] == 0
    c, i = _S12_TRIGGER_BNE_D0[not found]
    cycles += c
    instructions += i
    if not found:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, cs_result['d0'], 2)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x005E58)

    c, i = _S12_TRIGGER_TAIL
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, player.STATE11_TRIGGER_INDEX, 2):
        order[a] = b
    for a, b in _bytes(player.F1BA & 0xFFFFFF, 1, 2):
        order[a] = b
    exit_registers['d7'] = 1
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = _logic_sr(sr, 1, 2)
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x005E68)


# --- 006686: state 16 (game.player.state16_step) -- a tiny two-step "settle then countdown" leaf,
# the target both state 9's own "ground-before"/"ground-after" arms and state 26's own mirror
# transition into.  Costed one instruction-block at a time from the tracer on real fixtures over
# census-006686-* (all five recordings; 391 real path classes collapsing to exactly three real
# terminal shapes).  No d7 is ever read as an input.
STATE16_ENTRY = 0x006686

_S16_TEST = (12, 1)                          # 006686 tst.w f1b8.w
_S16_BNE = {True: (10, 1), False: (8, 1)}    # 00668A bne.b -- taken(!=0): countdown/transition
_S16_SETTLE_TAIL = (16 + 10, 2)              # 00668C addq.w #1,f1b8 (mem); 006690 bra.w
_S16_COUNTDOWN = (16, 1)                     # 006694 subq.w #4,f198 (mem)
_S16_BPL = {True: (10, 1), False: (12, 1)}   # 006698 bpl.w -- taken(>=0): countdown continues (word branch)
_S16_TRANS_TAIL = (4 + 16 + 10, 3)           # 00669C moveq #2,d7; 00669E move.w #1,f192; bra.w


def state16_plan(machine, registers):
    """006686 (state 16): the player state machine's own dispatch table entry 16.  See
    game.player's own module note above state16_step."""
    from .game import player
    if registers['pc'] != STATE16_ENTRY:
        raise UnsupportedCandidate('state 16 planner needs the machine parked at 006686')
    sr = registers['sr']
    read = _reader(machine)
    order = {}
    exit_registers = {}

    result = player.state16_step(read)
    c, i = _add(_S16_TEST, _S16_BNE[result['arm'] != 'settle'])
    cycles, instructions = c, i

    if result['arm'] == 'settle':
        c, i = _S16_SETTLE_TAIL
        cycles += c
        instructions += i
        for a, b in result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        f1b8 = read(player.F1B8, 2)
        sr = _add_sr(sr, f1b8, 1, 2)
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006690)

    c, i = _S16_COUNTDOWN
    cycles += c
    instructions += i
    old_f198 = read(player.F198, 2)
    sr = _sub_sr(sr, old_f198, 4, 2)
    negative = result['arm'] == 'transition-1'
    c, i = _S16_BPL[not negative]
    cycles += c
    instructions += i
    for a, b in result['stores'].items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb

    if not negative:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006698)

    c, i = _S16_TRANS_TAIL
    cycles += c
    instructions += i
    exit_registers['d7'] = result['d7']
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = _logic_sr(sr, 1, 2)   # 00669E move.w #1,f192.w is the last flag-setter
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x0066A4)


# --- 0074F0: state 2 -- a tiny three-arm leaf, the SAME shape as state 16's own "settle then
# countdown" leaf.  Costed one instruction-block at a time from the tracer on real fixtures over
# census-0074F0-* (all five recordings; 269 real path classes collapsing to exactly three real
# terminal shapes).
STATE2_ENTRY = 0x0074F0

_S2_TEST = (12, 1)                           # 0074F0 tst.w ea20.w
_S2_BPL = {True: (10, 1), False: (8, 1)}     # 0074F4 bpl.b -- taken(>=0): the counter arm (byte branch)
_S2_TO3_TAIL = (16 + 10, 2)                  # 0074F6 move.w #3,f192.w; 0074FC bra.w
_S2_COUNT = (4 + 8, 2)                       # 007500 addq.w #1,d7; 007502 cmpi.w #3,d7
_S2_BLT = {True: (10, 1), False: (12, 1)}    # 007506 blt.w -- taken(<3): still counting (word branch)
_S2_TO1_TAIL = (4 + 16 + 10, 3)              # 00750A moveq #6,d7; 00750C move.w #1,f192.w; 007512 bra.w


def state2_plan(machine, registers):
    """0074F0 (state 2): the player state machine's own dispatch table entry 2.  See
    game.player's own module note above state2_step."""
    from .game import player
    if registers['pc'] != STATE2_ENTRY:
        raise UnsupportedCandidate('state 2 planner needs the machine parked at 0074F0')
    sr = registers['sr']
    read = _reader(machine)
    order = {}
    exit_registers = {}

    ea20 = read(player.EA20_WORD, 2)
    result = player.state2_step(read, registers['d7'])
    c, i = _S2_TEST
    cycles, instructions = c, i
    sr = _logic_sr(sr, ea20, 2)
    negative = result['arm'] == 'transition-3'
    c, i = _S2_BPL[not negative]
    cycles += c
    instructions += i

    if negative:
        c, i = _S2_TO3_TAIL
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, player.STATE2_TO_STATE3, 2):
            order[a] = b
        sr = _logic_sr(sr, player.STATE2_TO_STATE3, 2)   # 0074F6's own move.w is the last flag-setter
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0074FC)

    c, i = _S2_COUNT
    cycles += c
    instructions += i
    counted = (registers['d7'] + 1) & 0xFFFF
    sr = _add_sr(sr, registers['d7'], 1, 2)
    sr = _cmp_sr(sr, counted, player.STATE2_COUNT_CAP, 2)   # 007502's own cmpi.w is the last flag-setter so far
    still_counting = result['arm'] == 'counting'
    c, i = _S2_BLT[still_counting]
    cycles += c
    instructions += i

    if still_counting:
        exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | result['d7']   # addq.w: a word op, upper half survives
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x007506)

    c, i = _S2_TO1_TAIL
    cycles += c
    instructions += i
    exit_registers['d7'] = result['d7']   # moveq #6,d7: a full 32-bit long move, clears the upper half
    for a, b in _bytes(player.STATE_INDEX, player.STATE2_TO_STATE1, 2):
        order[a] = b
    sr = _logic_sr(sr, player.STATE2_TO_STATE1, 2)   # 00750C's own move.w is the last flag-setter
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x007512)


# --- 007516: state 3 -- a mirror of state 2's own countdown/gate shape.  Costed one instruction-
# block at a time from the tracer on real fixtures over census-007516-* (all five recordings; 270
# real path classes collapsing to exactly two real terminal shapes -- the transition-2 arm is real
# ROM, unwitnessed by any recording, and declines by name).
STATE3_ENTRY = 0x007516

_S3_TEST = (16, 1)                           # 007516 cmpi.w #1,ea20.w
_S3_BNE = {True: (10, 1), False: (8, 1)}     # 00751C bne.b -- taken(!=1): the counter arm (byte branch)
_S3_COUNT = (4, 1)                           # 007528 subq.w #1,d7
_S3_BPL = {True: (10, 1), False: (12, 1)}    # 00752A bpl.w -- taken(>=0): still counting (word branch)
_S3_TO0_TAIL = (16 + 4 + 10, 3)              # 00752E clr.w f192.w; 007532 moveq #6,d7; 007534 bra.w


def state3_plan(machine, registers):
    """007516 (state 3): the player state machine's own dispatch table entry 3.  See
    game.player's own module note above state3_step."""
    from .game import player
    if registers['pc'] != STATE3_ENTRY:
        raise UnsupportedCandidate('state 3 planner needs the machine parked at 007516')
    sr = registers['sr']
    read = _reader(machine)
    order = {}
    exit_registers = {}

    ea20 = read(player.EA20_WORD, 2) & 0xFFFF
    if ea20 == 1:
        raise UnsupportedCandidate('state 3 transition-2 arm (FFFFEA20 == 1) not witnessed by a recording')

    result = player.state3_step(read, registers['d7'])
    c, i = _S3_TEST
    cycles, instructions = c, i
    sr = _cmp_sr(sr, ea20, 1, 2)
    c, i = _S3_BNE[True]
    cycles += c
    instructions += i

    c, i = _S3_COUNT
    cycles += c
    instructions += i
    counted = (registers['d7'] - 1) & 0xFFFF
    sr = _sub_sr(sr, registers['d7'], 1, 2)
    still_counting = result['arm'] == 'counting'
    c, i = _S3_BPL[still_counting]
    cycles += c
    instructions += i

    if still_counting:
        exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | result['d7']   # subq.w: a word op, upper half survives
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x00752A)

    c, i = _S3_TO0_TAIL
    cycles += c
    instructions += i
    exit_registers['d7'] = result['d7']   # moveq #6,d7: a full 32-bit long move, clears the upper half
    for a, b in _bytes(player.STATE_INDEX, player.STATE3_TO_STATE0, 2):
        order[a] = b
    sr = _logic_sr(sr, player.STATE3_RESET_COUNTER, 2)   # 007532's own moveq #6,d7 is the last flag-setter, after the clr
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x007534)


# --- 007538: state 4 -- FFFFEA20 == 0 jumps directly into state 15's own entry (006D68), the SAME
# "one region, two gates" shared-fallthrough shape as states 5/6 into 1/0.  Costed one instruction-
# block at a time from the tracer on real fixtures over census-007538-* (all five recordings; 81
# real path classes collapsing to exactly three real terminal shapes -- the composed "ground not
# found" continuation into state 15's own further, untraced body is real ROM, unwitnessed by any
# recording, and declines by name).
STATE4_ENTRY = 0x007538

_S4_TEST = (12, 1)                            # 007538 tst.w ea20.w
_S4_BEQ = {True: (10, 1), False: (12, 1)}     # 00753C beq.w -- taken(==0): the state-15 composition (word branch)
_STATE15_BSR_GRID = (18, 1)                   # 006D68 bsr.w $63fa
_STATE15_GROUND_TEST = (16, 1)                # 006D6C cmpi.b #1,$180(a0)
_STATE15_GROUND_BEQ = {True: (10, 1), False: (12, 1)}   # 006D72 beq.w -- taken: ground found (word branch)
_S4_BMI = {True: (10, 1), False: (8, 1)}      # 007540 bmi.b -- taken(<0): transition-3 (byte branch)
_S4_TO2_TAIL = (16 + 4 + 10, 3)               # 007542 move.w #2,f192.w; 007548 moveq #2,d7; 00754A bra.w
_S4_TO3_TAIL = (16 + 4 + 10, 3)               # 00754E move.w #3,f192.w; 007554 moveq #0,d7; 007556 bra.w


def _state15_ground_probe(read, sp32, sr, registers):
    """006D68-006D72: state 15's own body as reached by a shared fallthrough -- state 4's own
    `FFFFEA20 == 0` arm (below) and the real STATE_TABLE index 26's own `FFFFEA1E >= 0` arm
    (`game.player.state_26_step`'s own `'state15-body'` arm) both land here directly, no call
    pushed on top of their own.  Re-runs the already-recovered grid cell lookup and tests its own
    ground byte; 'not-found' past `006D72` is real ROM, unwitnessed by any recording from either
    caller, and stays declined here for both.  Returns (cycles, instructions, stack write, exit
    register overlay, exit sr, last_pc) for the caller to fold onto its own head cost."""
    from .game.grid import grid_cell
    c, i = _STATE15_BSR_GRID
    cycles, instructions = c, i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order = dict(_bytes((sp32 - 4) & 0xFFFFFF, 0x006D6C, 4))
    cell = grid_cell(read)
    overlay = {'a0': cell['address'] & 0xFFFFFFFF,
               'd0': (registers['d0'] & 0xFFFF0000) | cell['d0'],
               'd1': (registers['d1'] & 0xFFFF0000) | cell['d1']}
    sr = _asl_sr(sr, cell['row_source'], 3, 2)

    c, i = _STATE15_GROUND_TEST
    cycles += c
    instructions += i
    ground_byte = read((cell['address'] + 0x180) & 0xFFFFFF, 1)
    sr = _cmp_sr(sr, ground_byte, 1, 1)
    if ground_byte != 1:
        raise UnsupportedCandidate('state 15 composition: ground not found at 006D72 not witnessed by a recording')
    c, i = _STATE15_GROUND_BEQ[True]
    cycles += c
    instructions += i
    return cycles, instructions, order, overlay, sr, 0x006D72


def state4_plan(machine, registers):
    """007538 (state 4): the player state machine's own dispatch table entry 4.  See
    game.player's own module note above state4_step."""
    from .game import player
    if registers['pc'] != STATE4_ENTRY:
        raise UnsupportedCandidate('state 4 planner needs the machine parked at 007538')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    order = {}
    exit_registers = {}

    ea20 = player._signed_word(read(player.EA20_WORD, 2))
    c, i = _S4_TEST
    cycles, instructions = c, i
    sr = _logic_sr(sr, ea20, 2)
    zero = ea20 == 0
    c, i = _S4_BEQ[zero]
    cycles += c
    instructions += i

    if zero:
        c, i, probe_writes, overlay, sr, last_pc = _state15_ground_probe(read, sp32, sr, registers)
        cycles += c
        instructions += i
        order.update(probe_writes)
        exit_registers.update(overlay)
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    negative = ea20 < 0
    c, i = _S4_BMI[negative]
    cycles += c
    instructions += i

    if negative:
        c, i = _S4_TO3_TAIL
        cycles += c
        instructions += i
        exit_registers['d7'] = 0   # moveq #0,d7: a full 32-bit long move, clears the upper half
        for a, b in _bytes(player.STATE_INDEX, player.STATE4_TO_STATE3, 2):
            order[a] = b
        sr = _logic_sr(sr, 0, 2)   # 007554's own moveq #0,d7 is the last flag-setter, after the move.w
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x007556)

    c, i = _S4_TO2_TAIL
    cycles += c
    instructions += i
    exit_registers['d7'] = 2   # moveq #2,d7: a full 32-bit long move, clears the upper half
    for a, b in _bytes(player.STATE_INDEX, player.STATE4_TO_STATE2, 2):
        order[a] = b
    sr = _logic_sr(sr, 2, 2)   # 007548's own moveq #2,d7 is the last flag-setter, after the move.w
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x00754A)


# --- 006666: state 17 -- the SAME "settle then countdown" shape as state 16's own.  Costed one
# instruction-block at a time from the tracer on real fixtures over census-006666-* (all five
# recordings; 298 real path classes collapsing to exactly three real terminal shapes).
STATE17_ENTRY = 0x006666

_S17_TEST = (12, 1)                          # 006666 tst.w f1b8.w
_S17_BNE = {True: (10, 1), False: (8, 1)}    # 00666A bne.b -- taken(!=0): countdown/transition
_S17_SETTLE_TAIL = (16 + 10, 2)              # 00666C addq.w #1,f1b8 (mem); 006670 bra.w
_S17_COUNTDOWN = (16, 1)                     # 006674 subq.w #4,f198 (mem)
_S17_BPL = {True: (10, 1), False: (12, 1)}   # 006678 bpl.w -- taken(>=0): countdown continues (word branch)
_S17_TRANS_TAIL = (4 + 16 + 10, 3)           # 00667C moveq #2,d7; 00667E clr.w f192; bra.w


def state17_plan(machine, registers):
    """006666 (state 17): the player state machine's own dispatch table entry 17.  See
    game.player's own module note above state17_step."""
    from .game import player
    if registers['pc'] != STATE17_ENTRY:
        raise UnsupportedCandidate('state 17 planner needs the machine parked at 006666')
    sr = registers['sr']
    read = _reader(machine)
    order = {}
    exit_registers = {}

    result = player.state17_step(read)
    c, i = _add(_S17_TEST, _S17_BNE[result['arm'] != 'settle'])
    cycles, instructions = c, i

    if result['arm'] == 'settle':
        c, i = _S17_SETTLE_TAIL
        cycles += c
        instructions += i
        for a, b in result['stores'].items():
            for aa, bb in _bytes(a, b[0], b[1]):
                order[aa] = bb
        f1b8 = read(player.F1B8, 2)
        sr = _add_sr(sr, f1b8, 1, 2)
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006670)

    c, i = _S17_COUNTDOWN
    cycles += c
    instructions += i
    old_f198 = read(player.F198, 2)
    sr = _sub_sr(sr, old_f198, 4, 2)
    negative = result['arm'] == 'transition-0'
    c, i = _S17_BPL[not negative]
    cycles += c
    instructions += i
    for a, b in result['stores'].items():
        for aa, bb in _bytes(a, b[0], b[1]):
            order[aa] = bb

    if not negative:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006678)

    c, i = _S17_TRANS_TAIL
    cycles += c
    instructions += i
    exit_registers['d7'] = result['d7']
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 00667E clr.w f192.w is the last flag-setter
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x006682)


# --- 006886: state 21 -- a hybrid of state 9/26's own jump-arc fall step and state 12's own LEFT
# block-test gate, plus a THIRD real composition into the already-recovered movement-cluster
# consumer 012E5A.  See game.player's own module note above state21_step/state21_tail.  Costed one
# instruction-block at a time from the tracer on real fixtures over census-006886-* (all five
# recordings; 448 real path classes collapsing to five real terminal shapes; the "<3, !=1" tail's
# own cap-override, at 0x006994, is real ROM this session did not witness and declines by name).
STATE21_ENTRY = 0x006886

_S21_TST_F1BA = (12, 1)                          # 006886 tst.w f1ba.w
_S21_BEQ_F1BA = {True: (10, 1), False: (8, 1)}   # beq.b -- taken: F1BA == 0 (the addq.w branch)
_S21_SUBQ1 = (4, 1)                              # 00688C subq.w #1,d7
_S21_CLR_F1BA = (16, 1)                          # 00688E clr.w f1ba.w
_S21_HEAD_BRA = (10, 1)                          # 006892 bra.b $6896
_S21_ADDQ1 = (4, 1)                              # 006894 addq.w #1,d7

_S21_BSR_GRID = (18, 1)                          # 006896 bsr.w $63fa

_S21_LOW_HEAD = (12 + 8, 2)                      # 00689A move.w f18c,d0; 00689E andi.w #1f,d0
_S21_BNE_LOW = {True: (10, 1), False: (8, 1)}    # 0068A2 bne.b -- taken(low5!=0): skip the block test
_S21_BLOCK_TEST = (16, 1)                        # cmpi.b #1,offset(a0)
_S21_BLOCK_BEQ = {True: (10, 1), False: (8, 1)}  # beq.b -- taken: blocked

_S21_ADVANCE = (12 + 16, 2)                      # 0068BC move.w f196.w,d0; 0068C0 add.w d0,f18c.w

_S21_CMPI_GROUND_GATE = (16, 1)                  # 0068C4 cmpi.w #$16,f19c.w
_S21_BLT_GROUND_GATE = {True: (10, 1), False: (8, 1)}   # 0068CA blt.b -- taken: skip the before-probe

_S21_BSR_ROWGATE = (18, 1)                       # 0068CC/00693E bsr.w $6442 -- both ground-ahead call sites
_S21_TST_D1 = (4, 1)                             # tst.w d1 (both probe return sites)
_S21_BEQ_D1 = {True: (10, 1), False: (8, 1)}     # 0068D2 beq.b -- taken: not found (skip to the fall step)
_S21_BNE_D1_RECHECK = {True: (10, 1), False: (8, 1)}    # 006944 bne.b -- taken: found (jump back to the ground tail)

_S21_GROUND_TAIL = _add((16, 1), (20, 1), (4, 1), (16, 1), (16, 1), (10, 1))
# 0068D4 move #$11,f192; 0068DA andi f18e,#$fff0; 0068E0 moveq #0,d7; 0068E2 clr f1b8;
# 0068E6 move #$39,fdf6; 0068EC bra.w $75d6

_S21_LEA = (8, 1)                                # 0068F0 lea.l $6414(pc),a1
_S21_MOVE_F19C = (12, 1)                         # 0068F4 move.w f19c.w,d0
_S21_TABLE_READ = (14, 1)                        # 0068F8 move.w (a1,d0.w),d0
_S21_SUB = (16, 1)                               # 0068FC sub.w d0,f18e.w
_S21_TST_F19E = (12, 1)                          # 006900 tst.w f19e.w
_S21_BEQ_F19E = {True: (10, 1), False: (8, 1)}   # 006904 beq.b -- taken: no double
_S21_SUB_DOUBLE = (16, 1)                        # 006906 sub.w d0,f18e.w -- the F19E-doubled path

_S21_BEQ_LANDED = {True: (10, 1), False: (8, 1)}  # 006910 beq.b -- taken: not landed
_S21_LANDED_TAIL = _add((20, 1), (20, 1), (16, 1), (16, 1), (16, 1), (16, 1))
# 006912 andi f18e,#$fff0; 006918 addi f18e,#$10; 00691E move #$b,f192; 006924 clr f194;
# 006928 clr f1a0; 00692C clr f198 -- moveq #0,d7 and the bra.w are separate, below
_S21_LANDED_MOVEQ = (4, 1)
_S21_LANDED_BRA = (10, 1)                        # 006932 bra.w $75d6

_S21_CMPI_RECHECK_GATE = (16, 1)                 # 006936 cmpi.w #$12,f19c.w
_S21_BLT_RECHECK_GATE = {True: (10, 1), False: (8, 1)}  # 00693C blt.b -- taken: skip the after-probe

_S21_CMPI_TAIL_GATE = (8, 1)                     # 006946 cmpi.w #3,d7
_S21_BLT_TAIL_GATE = {True: (10, 1), False: (8, 1)}     # 00694A blt.b -- taken(<3): the consume/countdown tail
_S21_TRIGGER_HEAD = (4 + 16, 2)                  # 00694C moveq #6,d7; 00694E move.w #8,f192.w
_S21_TAIL_ADDQ = (16, 1)                         # 006954/006986 addq.w #2,f19c.w -- both copies
_S21_TAIL_CMPI = (16, 1)                         # 006958/00698A cmpi.w #$2e,f19c.w -- both copies
_S21_TAIL_BLT = {True: (10, 1), False: (12, 1)}  # 00695E/006990 blt.w -- word branch, both copies
_S21_CAP_TAIL = _add((16, 1), (4, 1), (16, 1), (16, 1), (16, 1), (10, 1))
# 006962 move #$b,f192; 006968 moveq #0,d7; 00696A clr f1a0; 00696E clr f198; 006972 clr f194;
# 006976 bra.w $75d6 -- the TRIGGER tail's own cap override

_S21_CONSUME_CMPI1 = (8, 1)                      # 00697A cmpi.w #1,d7
_S21_CONSUME_BNE1 = {True: (10, 1), False: (8, 1)}      # 00697E bne.b -- taken: D7 != 1, skip the jsr


def state21_plan(machine, registers):
    """006886 (state 21): the player state machine's own dispatch table entry 21.  See
    game.player's own module note above state21_step/state21_tail."""
    from .game import player
    from .game.grid import grid_cell
    if registers['pc'] != STATE21_ENTRY:
        raise UnsupportedCandidate('state 21 planner needs the machine parked at 006886')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    order = {}
    exit_registers = {}

    f1ba = read(player.F1BA, 2)
    c, i = _S21_TST_F1BA
    cycles, instructions = c, i
    sr = _logic_sr(sr, f1ba, 2)
    f1ba_set = f1ba != 0
    c, i = _S21_BEQ_F1BA[not f1ba_set]
    cycles += c
    instructions += i
    d7 = registers['d7'] & 0xFFFF
    if f1ba_set:
        c, i = _add(_S21_SUBQ1, _S21_CLR_F1BA, _S21_HEAD_BRA)
        cycles += c
        instructions += i
        sr = _sub_sr(sr, d7, 1, 2)
        new_d7 = (d7 - 1) & 0xFFFF
        for a, b in _bytes(player.F1BA & 0xFFFFFF, 0, 2):
            order[a] = b
    else:
        c, i = _S21_ADDQ1
        cycles += c
        instructions += i
        sr = _add_sr(sr, d7, 1, 2)
        new_d7 = (d7 + 1) & 0xFFFF

    c, i = _S21_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x00689A, 4))
    cell1 = grid_cell(read)
    exit_registers['a0'] = cell1['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell1['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell1['d1']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)

    position_x = read(player.POSITION_X, 2)
    low5 = position_x & 0x1F
    c, i = _S21_LOW_HEAD
    cycles += c
    instructions += i
    sr = _logic_sr(sr, low5, 2)   # andi.w: logic flags of the RESULT
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | low5
    c, i = _S21_BNE_LOW[low5 != 0]
    cycles += c
    instructions += i
    blocked = False
    if low5 == 0:
        for offset in (-1, 0x7F, 0xFF):
            c, i = _S21_BLOCK_TEST
            cycles += c
            instructions += i
            byte_val = read((cell1['address'] + offset) & 0xFFFFFF, 1)
            sr = _cmp_sr(sr, byte_val, 1, 1)
            hit = byte_val == 1
            c, i = _S21_BLOCK_BEQ[hit]
            cycles += c
            instructions += i
            if hit:
                blocked = True
                break

    position_x_after = position_x
    if not blocked:
        c, i = _S21_ADVANCE
        cycles += c
        instructions += i
        step_x = read(player.F196, 2)
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | step_x
        position_x_after = (position_x + step_x) & 0xFFFF
        for a, b in _bytes(player.POSITION_X, position_x_after, 2):
            order[a] = b
        sr = _add_sr(sr, position_x, step_x, 2)

    def _read_after_advance(a, s, _x=position_x_after):
        return _x if (a & 0xFFFFFF) == (player.POSITION_X & 0xFFFFFF) else read(a, s)

    # A pure-Python precompute of what 006442's/006468's OWN internal bsr.b $63fa will see (real RAM
    # already carries the advanced POSITION_X by this point) -- not a separate boundary-plan cost;
    # _row_gate_cost below already charges that inner call in full, the same way state9_plan's own
    # 'address2'/'address3' are precomputed without their own top-level grid_cell cost.
    cell2 = grid_cell(_read_after_advance)

    f19c = read(player.F19C, 2)
    c, i = _S21_CMPI_GROUND_GATE
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, f19c, player.STATE21_GROUND_GATE, 2)
    ground_gate_open = f19c >= player.STATE21_GROUND_GATE
    c, i = _S21_BLT_GROUND_GATE[not ground_gate_open]
    cycles += c
    instructions += i

    found_before = False
    if ground_gate_open:
        c, i = _S21_BSR_ROWGATE
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0068D0, 4))
        rc, ri, found_before, rowgate_order, rowgate_d0 = _row_gate_cost(
            read, cell2['address'], position_x_after, 0x180, sp32 - 4, cell2['d0'])
        cycles += rc
        instructions += ri
        order.update(rowgate_order)
        exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
        exit_registers['d1'] = 1 if found_before else 0   # moveq #0/#1,d1: a full 32-bit clear
        sr = _asl_sr(sr, cell2['row_source'], 3, 2)
        c, i = _S21_TST_D1
        cycles += c
        instructions += i
        c, i = _S21_BEQ_D1[not found_before]
        cycles += c
        instructions += i

    if found_before:
        c, i = _S21_GROUND_TAIL
        cycles += c
        instructions += i
        original_y = read(player.POSITION_Y, 2)
        for a, b in _bytes(player.STATE_INDEX, player.STATE21_GROUND_INDEX, 2):
            order[a] = b
        for a, b in _bytes(player.POSITION_Y, original_y & 0xFFF0, 2):
            order[a] = b
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x39, 2)   # 0068E6 move.w #$39,fdf6.w is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0068EC)

    # The fall step.
    c, i = _add(_S21_LEA, _S21_MOVE_F19C, _S21_TABLE_READ)
    cycles += c
    instructions += i
    exit_registers['a1'] = player.STATE9_FALL_TABLE & 0xFFFFFFFF
    if f19c > player.STATE9_FALL_TABLE_LIMIT:
        raise UnsupportedCandidate('state 21 fall table index past its own last entry not witnessed')
    step_y = player._signed_word(read((player.STATE9_FALL_TABLE + f19c) & 0xFFFFFF, 2))
    original_y = read(player.POSITION_Y, 2)
    c, i = _S21_SUB
    cycles += c
    instructions += i
    sr = _sub_sr(sr, original_y, step_y & 0xFFFF, 2)
    new_y = (original_y - step_y) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    c, i = _S21_TST_F19E
    cycles += c
    instructions += i
    doubled = read(player.F19E, 2) != 0
    c, i = _S21_BEQ_F19E[not doubled]
    cycles += c
    instructions += i
    if doubled:
        c, i = _S21_SUB_DOUBLE
        cycles += c
        instructions += i
        sr = _sub_sr(sr, new_y, step_y & 0xFFFF, 2)
        new_y = (new_y - step_y) & 0xFFFF
        for a, b in _bytes(player.POSITION_Y, new_y, 2):
            order[a] = b

    c, i = _S21_BSR_ROWGATE
    cycles += c
    instructions += i
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x00690E, 4))

    def _read_after_fall(a, s, _y=new_y, _x=position_x_after):
        masked = a & 0xFFFFFF
        if masked == (player.POSITION_Y & 0xFFFFFF):
            return _y
        if masked == (player.POSITION_X & 0xFFFFFF):
            return _x
        return read(a, s)
    cell3 = grid_cell(_read_after_fall)
    rc, ri, found_landed, rowgate_order, rowgate_d0 = _row_gate_cost(
        read, cell3['address'], position_x_after, 0, sp32 - 4, cell3['d0'])
    cycles += rc
    instructions += ri
    order.update(rowgate_order)
    exit_registers['a0'] = cell3['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
    exit_registers['d1'] = 1 if found_landed else 0   # moveq #0/#1,d1: a full 32-bit clear
    sr = _asl_sr(sr, cell3['row_source'], 3, 2)
    c, i = _S21_TST_D1
    cycles += c
    instructions += i
    c, i = _S21_BEQ_LANDED[not found_landed]
    cycles += c
    instructions += i

    if found_landed:
        c, i = _S21_LANDED_TAIL
        cycles += c
        instructions += i
        masked_y = new_y & 0xFFF0
        sr = _add_sr(sr, masked_y, 0x10, 2)   # addi.w #$10,f18e.w
        new_y_aligned = (masked_y + 0x10) & 0xFFFF
        for a, b in _bytes(player.POSITION_Y, new_y_aligned, 2):
            order[a] = b
        for a, b in _bytes(player.STATE_INDEX, player.STATE21_LANDED_INDEX, 2):
            order[a] = b
        for a, b in _bytes(player.F194 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(player.F1A0 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(player.F198 & 0xFFFFFF, 0, 2):
            order[a] = b
        c, i = _add(_S21_LANDED_MOVEQ, _S21_LANDED_BRA)
        cycles += c
        instructions += i
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)   # moveq #0,d7 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006932)

    # The re-check ground-ahead probe, at the new position.
    c, i = _S21_CMPI_RECHECK_GATE
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, f19c, player.STATE21_RECHECK_GATE, 2)
    recheck_gate_open = f19c >= player.STATE21_RECHECK_GATE
    c, i = _S21_BLT_RECHECK_GATE[not recheck_gate_open]
    cycles += c
    instructions += i
    found_after = False
    if recheck_gate_open:
        c, i = _S21_BSR_ROWGATE
        cycles += c
        instructions += i
        order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006942, 4))
        rc, ri, found_after, rowgate_order, rowgate_d0 = _row_gate_cost(
            read, cell3['address'], position_x_after, 0x180, sp32 - 4, cell3['d0'])
        cycles += rc
        instructions += ri
        order.update(rowgate_order)
        exit_registers['a0'] = cell3['address'] & 0xFFFFFFFF
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | rowgate_d0
        exit_registers['d1'] = 1 if found_after else 0   # moveq #0/#1,d1: a full 32-bit clear
        sr = _asl_sr(sr, cell3['row_source'], 3, 2)
        c, i = _S21_TST_D1
        cycles += c
        instructions += i
        c, i = _S21_BNE_D1_RECHECK[found_after]
        cycles += c
        instructions += i

    if found_after:
        c, i = _S21_GROUND_TAIL
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, player.STATE21_GROUND_INDEX, 2):
            order[a] = b
        for a, b in _bytes(player.POSITION_Y, new_y & 0xFFF0, 2):
            order[a] = b
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        exit_registers['d7'] = 0
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0x39, 2)   # 0068E6 move.w #$39,fdf6.w is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0068EC)

    # Neither probe fired: the D7-based tail.
    c, i = _S21_CMPI_TAIL_GATE
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, new_d7, player.STATE21_TAIL_GATE, 2)
    to_trigger = new_d7 >= player.STATE21_TAIL_GATE
    c, i = _S21_BLT_TAIL_GATE[not to_trigger]
    cycles += c
    instructions += i

    if to_trigger:
        c, i = _S21_TRIGGER_HEAD
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, player.STATE21_TRIGGER_INDEX, 2):
            order[a] = b
        d7_out = player.STATE21_TRIGGER_D7
        sr = _logic_sr(sr, player.STATE21_TRIGGER_INDEX, 2)   # 00694E move.w #8,f192.w
    else:
        c, i = _S21_CONSUME_CMPI1
        cycles += c
        instructions += i
        calls_consumer = new_d7 == player.STATE21_CONSUME_COUNTER
        c, i = _S21_CONSUME_BNE1[not calls_consumer]
        cycles += c
        instructions += i
        d7_out = new_d7
        if calls_consumer:
            c, i = _S5_JSR_CONSUME
            cycles += c
            instructions += i
            for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x006986, 4):
                order[a] = b

            def _read_for_consume(a, s, _x=position_x_after, _y=new_y):
                masked = a & 0xFFFFFF
                if masked == (player.POSITION_X & 0xFFFFFF):
                    return _x
                if masked == (player.POSITION_Y & 0xFFFFFF):
                    return _y
                return read(a, s)
            cc_cycles, cc_instructions, cc_order, cc_registers, _ = _cc_resolve(
                machine, _read_for_consume, registers, 1, sp32 - 4)
            cycles += cc_cycles
            instructions += cc_instructions
            order.update(cc_order)
            exit_registers.update(cc_registers)

    c, i = _S21_TAIL_ADDQ
    cycles += c
    instructions += i
    new_f19c = (f19c + 2) & 0xFFFF
    sr = _add_sr(sr, f19c, 2, 2)
    for a, b in _bytes(player.F19C & 0xFFFFFF, new_f19c, 2):
        order[a] = b
    c, i = _S21_TAIL_CMPI
    cycles += c
    instructions += i
    capped = new_f19c >= player.STATE21_CAP
    c, i = _S21_TAIL_BLT[not capped]
    cycles += c
    instructions += i

    if not capped:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _cmp_sr(sr, new_f19c, player.STATE21_CAP, 2)
        if to_trigger:
            exit_registers['d7'] = d7_out   # moveq #6,d7: a full 32-bit clear
        else:
            exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | d7_out   # ADDQ/SUBQ (the head) or MOVEQ #1
        last_pc = 0x00695E if to_trigger else 0x006990
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=last_pc)

    if not to_trigger:
        raise UnsupportedCandidate('state 21 tail cap-override at 006994 (the <3, !=1 tail) not witnessed by a recording')

    c, i = _S21_CAP_TAIL
    cycles += c
    instructions += i
    for a, b in _bytes(player.STATE_INDEX, player.STATE21_LANDED_INDEX, 2):
        order[a] = b
    for a, b in _bytes(player.F1A0 & 0xFFFFFF, 0, 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, 0, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, 0, 2):
        order[a] = b
    exit_registers['d7'] = 0
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 006972 clr.w f194.w is the last flag-setter
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x006976)


# --- 005828: state 28 -- the smallest leaf yet: an unconditional transition to state 1.  Costed
# from the tracer on real fixtures over census-005828-* (all five recordings; 71 real path classes,
# all one shape).
STATE28_ENTRY = 0x005828

_S28_TAIL = (4 + 16 + 10, 3)   # 005828 moveq #2,d7; 00582A move.w #1,f192.w; 005830 bra.w


def state28_plan(machine, registers):
    """005828 (state 28): the player state machine's own dispatch table entry 28.  See
    game.player's own module note above state28_step."""
    from .game import player
    if registers['pc'] != STATE28_ENTRY:
        raise UnsupportedCandidate('state 28 planner needs the machine parked at 005828')
    sr = registers['sr']
    order = {}
    c, i = _S28_TAIL
    cycles, instructions = c, i
    for a, b in _bytes(player.STATE_INDEX, player.STATE28_TO_STATE1, 2):
        order[a] = b
    exit_registers = {'d7': player.STATE28_D7, 'pc': 0x0075D6,
                       'sr': _logic_sr(sr, player.STATE28_TO_STATE1, 2)}   # 00582A move.w #1,f192.w is the last flag-setter
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x005830)


# --- 0062B0: state 22 -- state 21's own FFFFF1BA-gated head in front of state 12's own ENTIRE
# oscillation body and BOTH block tests, reused verbatim (byte-for-byte the same masks, offsets and
# immediates, confirmed via a direct disassembly of 0062B0-006412), with a genuine ground-found jump
# into the SAME PHYSICAL ground-tail code state 12's own uses (006134-006160, not a relocated copy).
# See game.player's own module note above state22_step.  Costed one instruction-block at a time from
# the tracer on real fixtures over census-0062B0-* (all five recordings; 91 real path classes
# collapsing to six real terminal shapes) -- unlike state 12's own planner, the retry-budget-
# exhausted sub-case is REAL AND WITNESSED here (a clean skip to the next test, not a decline).
STATE22_ENTRY = 0x0062B0

_S22_TST_F1BA = (12, 1)                          # 0062B0 tst.w f1ba.w
_S22_BEQ_F1BA = {True: (10, 1), False: (8, 1)}   # beq.b -- taken: F1BA == 0 (the addq.w branch)
_S22_SUBQ1 = (4, 1)                              # 0062B6 subq.w #1,d7
_S22_CLR_F1BA = (16, 1)                          # 0062B8 clr.w f1ba.w
_S22_HEAD_BRA = (10, 1)                          # 0062BC bra.b $62c0
_S22_ADDQ1 = (4, 1)                              # 0062BE addq.w #1,d7

_S22_ALT_HEAD = (12 + 8, 2)                      # 0063BE move f18c,d0; 0063C2 andi.w #$1f,d0 (NOT 0x1c)
_S22_ALT_TEST = (8, 1)                           # 0063C6 cmpi.w #8,d0
_S22_ALT_BLT = {True: (10, 1), False: (8, 1)}    # 0063CA blt.b -- taken(<8): skip the alt test
_S22_ALT_GROUND_TEST = (16, 1)                   # 0063CC cmpi.b #1,$181(a0)
_S22_ALT_GROUND_BEQ = {True: (10, 1), False: (12, 1)}   # 0063D2 beq.w -- taken: ground found (alt, word branch)
_S22_GROUND_BEQ = {True: (10, 1), False: (12, 1)}       # 0063BA beq.w -- taken: ground found (word branch)

_S22_TAIL_CMPI3 = (8, 1)                         # 0063D6 cmpi.w #3,d7
_S22_TAIL_BEQ3 = {True: (10, 1), False: (8, 1)}  # 0063DA beq.b -- taken: the trigger tail
_S22_TRIGGER_TAIL = _add((16, 1), (4, 1), (10, 1))   # 0063EE move #$c,f192; 0063F4 moveq #0,d7; 0063F6 bra.w
_S22_TAIL_CMPI1 = (8, 1)                         # 0063DC cmpi.w #1,d7
_S22_TAIL_BNE1 = {True: (10, 1), False: (12, 1)}  # 0063E0 bne.w -- taken(!=1): exit unchanged (word branch)
_S22_CONSUME_BRA = (10, 1)                       # 0063EA bra.w $75d6, after the jsr returns


def state22_plan(machine, registers):
    """0062B0 (state 22): the player state machine's own dispatch table entry 22.  See
    game.player's own module note above state22_step."""
    from .game import player
    from .game.grid import grid_cell
    if registers['pc'] != STATE22_ENTRY:
        raise UnsupportedCandidate('state 22 planner needs the machine parked at 0062B0')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    order = {}
    exit_registers = {}

    d7 = registers['d7'] & 0xFFFF
    f1ba = read(player.F1BA, 2)
    c, i = _S22_TST_F1BA
    cycles, instructions = c, i
    sr = _logic_sr(sr, f1ba, 2)
    f1ba_set = f1ba != 0
    c, i = _S22_BEQ_F1BA[not f1ba_set]
    cycles += c
    instructions += i
    if f1ba_set:
        c, i = _add(_S22_SUBQ1, _S22_CLR_F1BA, _S22_HEAD_BRA)
        cycles += c
        instructions += i
        sr = _sub_sr(sr, d7, 1, 2)
        new_d7 = (d7 - 1) & 0xFFFF
        for a, b in _bytes(player.F1BA & 0xFFFFFF, 0, 2):
            order[a] = b
    else:
        c, i = _S22_ADDQ1
        cycles += c
        instructions += i
        sr = _add_sr(sr, d7, 1, 2)
        new_d7 = (d7 + 1) & 0xFFFF
    exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | new_d7   # ADDQ/SUBQ: a word op, the upper half survives

    hc, hi, osc = _state12_head_cost(read)
    cycles += hc
    instructions += hi
    new_y = (read(player.POSITION_Y, 2) + osc['position_y_delta']) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, osc['f194'], 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, osc['f198'], 2):
        order[a] = b
    if osc['sound']:
        from .game.hazard import SOUND_COMMAND
        for a, b in _bytes(SOUND_COMMAND & 0xFFFFFF, 0x50, 2):
            order[a] = b
    sr = _cmp_sr(sr, osc['f198'], player.STATE12_TICK_CAP, 2)

    read_orig = read

    def read(a, s, _y=new_y):
        return _y if (a & 0xFFFFFF) == (player.POSITION_Y & 0xFFFFFF) else read_orig(a, s)

    ea20 = player._signed_word(read(player.EA20_WORD, 2))
    position_x = read(player.POSITION_X, 2)
    f1a0 = read(player.F1A0, 2)

    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x006304, 4))
    cell1 = grid_cell(read)
    exit_registers['a0'] = cell1['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell1['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell1['d1']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)

    c, i = _S12_LEFT_GATE_TEST
    cycles += c
    instructions += i
    retry_open = f1a0 < player.STATE12_RETRY_CAP
    provisional_state = None
    position_x_after = position_x
    if ea20 == -1:
        c, i = _S12_LEFT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if retry_open:
            provisional_state = 0xB
            c, i = _S12_LEFT_SET_STATE
            cycles += c
            instructions += i
            address = cell1['address']
            low = position_x & 0x1F
            c, i = _S12_LR_HEAD
            cycles += c
            instructions += i
            c, i = _S12_LEFT_BNE_LOW[low != 0]
            cycles += c
            instructions += i
            blocked = False
            if low == 0:
                for offset in (-1, 0x7F, 0xFF):
                    c, i = _S12_GRID_TEST
                    cycles += c
                    instructions += i
                    hit = read((address + offset) & 0xFFFFFF, 1) == 1
                    c, i = _S12_GRID_BEQ[hit]
                    cycles += c
                    instructions += i
                    if hit:
                        blocked = True
                        break
                if not blocked:
                    nibble = read(player.POSITION_Y, 2) & 0xF
                    c, i = _S12_NIBBLE_HEAD
                    cycles += c
                    instructions += i
                    c, i = _S12_NIBBLE_BEQ[nibble == 0]
                    cycles += c
                    instructions += i
                    if nibble != 0:
                        c, i = _S12_NIBBLE_TEST
                        cycles += c
                        instructions += i
                        blocked = read((address + 0x17F) & 0xFFFFFF, 1) == 1
                        c, i = _S12_NIBBLE_BEQ2[blocked]
                        cycles += c
                        instructions += i
            if not blocked:
                c, i = _S12_LEFT_ADVANCE
                cycles += c
                instructions += i
                position_x_after = (position_x - 4) & 0xFFFF
                for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                    order[a] = b
                for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                    order[a] = b
    else:
        c, i = _S12_LEFT_GATE_BNE[True]
        cycles += c
        instructions += i

    c, i = _S12_RIGHT_GATE_TEST
    cycles += c
    instructions += i
    if ea20 == 1:
        c, i = _S12_RIGHT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if retry_open:
            provisional_state = 0xC
            c, i = _S12_RIGHT_SET_STATE
            cycles += c
            instructions += i
            address = cell1['address']
            low = position_x & 0x1C
            c, i = _add(_S12_LR_HEAD, _S12_RIGHT_MASK_TEST)
            cycles += c
            instructions += i
            mask_match = low == 0x1C
            c, i = _S12_RIGHT_MASK_BEQ[mask_match]
            cycles += c
            instructions += i
            run_test = mask_match
            if not mask_match:
                c, i = _S12_RIGHT_LOW_TEST
                cycles += c
                instructions += i
                skip_test = low >= 8
                c, i = _S12_RIGHT_LOW_BGE[skip_test]
                cycles += c
                instructions += i
                run_test = not skip_test
            blocked = False
            if run_test:
                for offset in (1, 0x81, 0x101):
                    c, i = _S12_GRID_TEST
                    cycles += c
                    instructions += i
                    hit = read((address + offset) & 0xFFFFFF, 1) == 1
                    c, i = _S12_GRID_BEQ[hit]
                    cycles += c
                    instructions += i
                    if hit:
                        blocked = True
                        break
                if not blocked:
                    nibble = read(player.POSITION_Y, 2) & 0xF
                    c, i = _S12_NIBBLE_HEAD
                    cycles += c
                    instructions += i
                    c, i = _S12_NIBBLE_BEQ[nibble == 0]
                    cycles += c
                    instructions += i
                    if nibble != 0:
                        c, i = _S12_NIBBLE_TEST
                        cycles += c
                        instructions += i
                        blocked = read((address + 0x181) & 0xFFFFFF, 1) == 1
                        c, i = _S12_NIBBLE_BEQ2[blocked]
                        cycles += c
                        instructions += i
            if not blocked:
                c, i = _S12_RIGHT_ADVANCE
                cycles += c
                instructions += i
                position_x_after = (position_x + 4) & 0xFFFF
                for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                    order[a] = b
                for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                    order[a] = b
    else:
        c, i = _S12_RIGHT_GATE_BNE[True]
        cycles += c
        instructions += i

    if provisional_state is not None:
        for a, b in _bytes(player.STATE_INDEX, provisional_state, 2):
            order[a] = b

    def _read_after_move(a, s, _x=position_x_after):
        return _x if (a & 0xFFFFFF) == (player.POSITION_X & 0xFFFFFF) else read(a, s)
    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0063B4, 4))
    cell2 = grid_cell(_read_after_move)
    address2 = cell2['address']
    exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell2['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell2['d1']
    sr = _asl_sr(sr, cell2['row_source'], 3, 2)

    c, i = _S12_GROUND_TEST
    cycles += c
    instructions += i
    ground = read((address2 + 0x180) & 0xFFFFFF, 1) == 1
    c, i = _S22_GROUND_BEQ[ground]
    cycles += c
    instructions += i
    alt_low = None
    if not ground:
        # Confirmed a real difference from state 12's own inline ALT test: the mask here is 0x1F.
        low = _read_after_move(player.POSITION_X, 2) & 0x1F
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | low
        c, i = _add(_S22_ALT_HEAD, _S22_ALT_TEST)
        cycles += c
        instructions += i
        sr = _cmp_sr(sr, low, 8, 2)
        alt_low = low < 8
        c, i = _S22_ALT_BLT[alt_low]
        cycles += c
        instructions += i
        if not alt_low:
            c, i = _S22_ALT_GROUND_TEST
            cycles += c
            instructions += i
            alt_byte = read((address2 + 0x181) & 0xFFFFFF, 1)
            ground = alt_byte == 1
            sr = _cmp_sr(sr, alt_byte, 1, 1)
            c, i = _S22_ALT_GROUND_BEQ[ground]
            cycles += c
            instructions += i

    if ground:
        for a, b in _bytes(player.STATE_INDEX, player.STATE12_GROUND_INDEX, 2):
            order[a] = b
        masked_y = new_y & 0xFFF0
        for a, b in _bytes(player.POSITION_Y, masked_y, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        from .game.zones import COOLDOWN, SUPPRESS_COOLDOWN
        c, i = _S12G_HEAD
        cycles += c
        instructions += i
        c, i = _S12G_TICK_TEST
        cycles += c
        instructions += i
        d0 = player._signed_word((osc['f198'] - 0x14) & 0xFFFF)
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | ((osc['f198'] - 0x14) & 0xFFFF)
        c, i = _S12G_TICK_BLE[d0 <= 0]
        cycles += c
        instructions += i
        if d0 <= 0:
            sr = _sub_sr(sr, osc['f198'], 0x14, 2)
            exit_registers['d7'] = 0   # 00613E's own moveq #0,d7 (state 12's own shared ground tail) already ran
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x00614E)
        suppress = read(SUPPRESS_COOLDOWN, 2) & 0xFFFF != 0
        c, i = _S12G_SUPPRESS_TEST
        cycles += c
        instructions += i
        c, i = _S12G_SUPPRESS_BNE[suppress]
        cycles += c
        instructions += i
        if suppress:
            sr = _logic_sr(sr, read(SUPPRESS_COOLDOWN, 2), 2)
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            exit_registers['d7'] = 0
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x006156)
        half = d0 >> 1
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | (half & 0xFFFF)
        cooldown = (read(COOLDOWN, 2) - half) & 0xFFFF
        for a, b in _bytes(COOLDOWN & 0xFFFFFF, cooldown, 2):
            order[a] = b
        c, i = _S12G_APPLY
        cycles += c
        instructions += i
        sr = _sub_sr(sr, read(COOLDOWN, 2), half, 2)
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        exit_registers['d7'] = 0
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006160)

    # Neither ground test fired: the D7-based tail.
    c, i = _S22_TAIL_CMPI3
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, new_d7, player.STATE22_TRIGGER_D7_GATE, 2)
    to_trigger = new_d7 == player.STATE22_TRIGGER_D7_GATE
    c, i = _S22_TAIL_BEQ3[to_trigger]
    cycles += c
    instructions += i

    if to_trigger:
        c, i = _S22_TRIGGER_TAIL
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, 0xC, 2):
            order[a] = b
        exit_registers['d7'] = 0   # moveq #0,d7: a full 32-bit clear
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)   # 0063F4 moveq #0,d7 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0063F6)

    c, i = _S22_TAIL_CMPI1
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, new_d7, player.STATE22_CONSUME_D7_GATE, 2)
    to_consume = new_d7 == player.STATE22_CONSUME_D7_GATE
    c, i = _S22_TAIL_BNE1[not to_consume]
    cycles += c
    instructions += i

    if not to_consume:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0063E0)

    c, i = _S5_JSR_CONSUME
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x0063EA, 4):
        order[a] = b

    def _read_for_consume(a, s, _x=position_x_after, _y=new_y):
        masked = a & 0xFFFFFF
        if masked == (player.POSITION_X & 0xFFFFFF):
            return _x
        if masked == (player.POSITION_Y & 0xFFFFFF):
            return _y
        return read(a, s)
    cc_cycles, cc_instructions, cc_order, cc_registers, last_slot = _cc_resolve(
        machine, _read_for_consume, registers, 0, sp32 - 4)
    cycles += cc_cycles
    instructions += cc_instructions
    order.update(cc_order)
    exit_registers.update(cc_registers)

    # 012DA0's own rts is state 22's own last flag-setting instruction on this path too (0063EA's
    # own bra.w never touches flags) -- the SAME per-type/arm formula `_contact_consume_plan`'s own
    # standalone gate computes for its own exit, X preserved from entry.
    from .game import pickups
    if last_slot['arm'] == 'empty':
        last_value = read(pickups.CONTACT_SLOTS[2], 4) & 0xFFFFFFFF
        width = 4
    elif last_slot['type'] == 9:
        last_value, width = 0x2F, 2
    else:
        num_groups = len(last_slot['groups'])
        if num_groups < 3:
            last_value = 0
        elif last_slot['pooled']:
            last_value = 0xFFFA
        else:
            last_value = _CC_GROUP2_CONST[0]
        width = 2
    sr = (_logic_sr(sr, last_value, width) & ~0x10) | (sr & 0x10)

    c, i = _S22_CONSUME_BRA
    cycles += c
    instructions += i
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x0063EA)


# --- 00581E: state 27 -- another unconditional leaf, the SAME shape as state 28's own.  Costed
# from the tracer on real fixtures over census-00581E-* (all five recordings; 55 real path classes,
# all one shape).
STATE27_ENTRY = 0x00581E

_S27_TAIL = (4 + 16 + 10, 3)   # 00581E moveq #2,d7; 005820 clr.w f192.w; 005824 bra.w


def state27_plan(machine, registers):
    """00581E (state 27): the player state machine's own dispatch table entry 27.  See
    game.player's own module note above state27_step."""
    from .game import player
    if registers['pc'] != STATE27_ENTRY:
        raise UnsupportedCandidate('state 27 planner needs the machine parked at 00581E')
    sr = registers['sr']
    order = {}
    c, i = _S27_TAIL
    cycles, instructions = c, i
    for a, b in _bytes(player.STATE_INDEX, player.STATE27_TO_STATE0, 2):
        order[a] = b
    exit_registers = {'d7': player.STATE27_D7, 'pc': 0x0075D6,
                       'sr': _logic_sr(sr, player.STATE27_TO_STATE0, 2)}   # 005820 clr.w f192.w is the last flag-setter
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x005824)


# --- 006164: state 23 -- state 21/22's own FFFFF1BA-gated head and D7-based tail shape, structurally
# identical to state 22's own body (confirmed via a direct disassembly of 006164-0062AC, which sits
# immediately before state 22's own 0062B0), reusing every _S22_*/_S12_*/_S12G_* cost constant
# directly.  See game.player's own module note above state23_step.  Costed against census-006164-*
# (all five recordings; 34 real path classes collapsing to five real terminal shapes).
STATE23_ENTRY = 0x006164


def state23_plan(machine, registers):
    """006164 (state 23): the player state machine's own dispatch table entry 23.  See
    game.player's own module note above state23_step."""
    from .game import player
    from .game.grid import grid_cell
    if registers['pc'] != STATE23_ENTRY:
        raise UnsupportedCandidate('state 23 planner needs the machine parked at 006164')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    order = {}
    exit_registers = {}

    d7 = registers['d7'] & 0xFFFF
    f1ba = read(player.F1BA, 2)
    c, i = _S22_TST_F1BA
    cycles, instructions = c, i
    sr = _logic_sr(sr, f1ba, 2)
    f1ba_set = f1ba != 0
    c, i = _S22_BEQ_F1BA[not f1ba_set]
    cycles += c
    instructions += i
    if f1ba_set:
        c, i = _add(_S22_SUBQ1, _S22_CLR_F1BA, _S22_HEAD_BRA)
        cycles += c
        instructions += i
        sr = _sub_sr(sr, d7, 1, 2)
        new_d7 = (d7 - 1) & 0xFFFF
        for a, b in _bytes(player.F1BA & 0xFFFFFF, 0, 2):
            order[a] = b
    else:
        c, i = _S22_ADDQ1
        cycles += c
        instructions += i
        sr = _add_sr(sr, d7, 1, 2)
        new_d7 = (d7 + 1) & 0xFFFF
    exit_registers['d7'] = (registers['d7'] & 0xFFFF0000) | new_d7   # ADDQ/SUBQ: a word op, the upper half survives

    hc, hi, osc = _state12_head_cost(read)
    cycles += hc
    instructions += hi
    new_y = (read(player.POSITION_Y, 2) + osc['position_y_delta']) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, osc['f194'], 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, osc['f198'], 2):
        order[a] = b
    if osc['sound']:
        from .game.hazard import SOUND_COMMAND
        for a, b in _bytes(SOUND_COMMAND & 0xFFFFFF, 0x50, 2):
            order[a] = b
    sr = _cmp_sr(sr, osc['f198'], player.STATE12_TICK_CAP, 2)

    read_orig = read

    def read(a, s, _y=new_y):
        return _y if (a & 0xFFFFFF) == (player.POSITION_Y & 0xFFFFFF) else read_orig(a, s)

    ea20 = player._signed_word(read(player.EA20_WORD, 2))
    position_x = read(player.POSITION_X, 2)
    f1a0 = read(player.F1A0, 2)

    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x0061B8, 4))
    cell1 = grid_cell(read)
    exit_registers['a0'] = cell1['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell1['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell1['d1']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)

    c, i = _S12_LEFT_GATE_TEST
    cycles += c
    instructions += i
    retry_open = f1a0 < player.STATE12_RETRY_CAP
    provisional_state = None
    position_x_after = position_x
    if ea20 == -1:
        c, i = _S12_LEFT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if retry_open:
            provisional_state = 0xB
            c, i = _S12_LEFT_SET_STATE
            cycles += c
            instructions += i
            address = cell1['address']
            low = position_x & 0x1F
            c, i = _S12_LR_HEAD
            cycles += c
            instructions += i
            c, i = _S12_LEFT_BNE_LOW[low != 0]
            cycles += c
            instructions += i
            blocked = False
            if low == 0:
                for offset in (-1, 0x7F, 0xFF):
                    c, i = _S12_GRID_TEST
                    cycles += c
                    instructions += i
                    hit = read((address + offset) & 0xFFFFFF, 1) == 1
                    c, i = _S12_GRID_BEQ[hit]
                    cycles += c
                    instructions += i
                    if hit:
                        blocked = True
                        break
                if not blocked:
                    nibble = read(player.POSITION_Y, 2) & 0xF
                    c, i = _S12_NIBBLE_HEAD
                    cycles += c
                    instructions += i
                    c, i = _S12_NIBBLE_BEQ[nibble == 0]
                    cycles += c
                    instructions += i
                    if nibble != 0:
                        c, i = _S12_NIBBLE_TEST
                        cycles += c
                        instructions += i
                        blocked = read((address + 0x17F) & 0xFFFFFF, 1) == 1
                        c, i = _S12_NIBBLE_BEQ2[blocked]
                        cycles += c
                        instructions += i
            if not blocked:
                c, i = _S12_LEFT_ADVANCE
                cycles += c
                instructions += i
                position_x_after = (position_x - 4) & 0xFFFF
                for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                    order[a] = b
                for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                    order[a] = b
    else:
        c, i = _S12_LEFT_GATE_BNE[True]
        cycles += c
        instructions += i

    c, i = _S12_RIGHT_GATE_TEST
    cycles += c
    instructions += i
    if ea20 == 1:
        c, i = _S12_RIGHT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if retry_open:
            provisional_state = 0xC
            c, i = _S12_RIGHT_SET_STATE
            cycles += c
            instructions += i
            address = cell1['address']
            low = position_x & 0x1C
            c, i = _add(_S12_LR_HEAD, _S12_RIGHT_MASK_TEST)
            cycles += c
            instructions += i
            mask_match = low == 0x1C
            c, i = _S12_RIGHT_MASK_BEQ[mask_match]
            cycles += c
            instructions += i
            run_test = mask_match
            if not mask_match:
                c, i = _S12_RIGHT_LOW_TEST
                cycles += c
                instructions += i
                skip_test = low >= 8
                c, i = _S12_RIGHT_LOW_BGE[skip_test]
                cycles += c
                instructions += i
                run_test = not skip_test
            blocked = False
            if run_test:
                for offset in (1, 0x81, 0x101):
                    c, i = _S12_GRID_TEST
                    cycles += c
                    instructions += i
                    hit = read((address + offset) & 0xFFFFFF, 1) == 1
                    c, i = _S12_GRID_BEQ[hit]
                    cycles += c
                    instructions += i
                    if hit:
                        blocked = True
                        break
                if not blocked:
                    nibble = read(player.POSITION_Y, 2) & 0xF
                    c, i = _S12_NIBBLE_HEAD
                    cycles += c
                    instructions += i
                    c, i = _S12_NIBBLE_BEQ[nibble == 0]
                    cycles += c
                    instructions += i
                    if nibble != 0:
                        c, i = _S12_NIBBLE_TEST
                        cycles += c
                        instructions += i
                        blocked = read((address + 0x181) & 0xFFFFFF, 1) == 1
                        c, i = _S12_NIBBLE_BEQ2[blocked]
                        cycles += c
                        instructions += i
            if not blocked:
                c, i = _S12_RIGHT_ADVANCE
                cycles += c
                instructions += i
                position_x_after = (position_x + 4) & 0xFFFF
                for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                    order[a] = b
                for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                    order[a] = b
    else:
        c, i = _S12_RIGHT_GATE_BNE[True]
        cycles += c
        instructions += i

    if provisional_state is not None:
        for a, b in _bytes(player.STATE_INDEX, provisional_state, 2):
            order[a] = b

    def _read_after_move(a, s, _x=position_x_after):
        return _x if (a & 0xFFFFFF) == (player.POSITION_X & 0xFFFFFF) else read(a, s)
    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x00626A, 4))
    cell2 = grid_cell(_read_after_move)
    address2 = cell2['address']
    exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell2['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell2['d1']
    sr = _asl_sr(sr, cell2['row_source'], 3, 2)

    c, i = _S12_GROUND_TEST
    cycles += c
    instructions += i
    ground = read((address2 + 0x180) & 0xFFFFFF, 1) == 1
    c, i = _S22_GROUND_BEQ[ground]
    cycles += c
    instructions += i
    alt_low = None
    if not ground:
        low = _read_after_move(player.POSITION_X, 2) & 0x1F
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | low
        c, i = _add(_S22_ALT_HEAD, _S22_ALT_TEST)
        cycles += c
        instructions += i
        sr = _cmp_sr(sr, low, 8, 2)
        alt_low = low < 8
        c, i = _S22_ALT_BLT[alt_low]
        cycles += c
        instructions += i
        if not alt_low:
            c, i = _S22_ALT_GROUND_TEST
            cycles += c
            instructions += i
            alt_byte = read((address2 + 0x181) & 0xFFFFFF, 1)
            ground = alt_byte == 1
            sr = _cmp_sr(sr, alt_byte, 1, 1)
            c, i = _S22_ALT_GROUND_BEQ[ground]
            cycles += c
            instructions += i

    if ground:
        for a, b in _bytes(player.STATE_INDEX, player.STATE11_GROUND_INDEX, 2):
            order[a] = b
        masked_y = new_y & 0xFFF0
        for a, b in _bytes(player.POSITION_Y, masked_y, 2):
            order[a] = b
        from .game.pickups import MOVEMENT_SOUND_CUE
        for a, b in _bytes(player.F1B8 & 0xFFFFFF, 0, 2):
            order[a] = b
        for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
            order[a] = b
        from .game.zones import COOLDOWN, SUPPRESS_COOLDOWN
        c, i = _S12G_HEAD
        cycles += c
        instructions += i
        c, i = _S12G_TICK_TEST
        cycles += c
        instructions += i
        d0 = player._signed_word((osc['f198'] - 0x14) & 0xFFFF)
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | ((osc['f198'] - 0x14) & 0xFFFF)
        c, i = _S12G_TICK_BLE[d0 <= 0]
        cycles += c
        instructions += i
        if d0 <= 0:
            sr = _sub_sr(sr, osc['f198'], 0x14, 2)
            exit_registers['d7'] = 0
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x005E8C)
        suppress = read(SUPPRESS_COOLDOWN, 2) & 0xFFFF != 0
        c, i = _S12G_SUPPRESS_TEST
        cycles += c
        instructions += i
        c, i = _S12G_SUPPRESS_BNE[suppress]
        cycles += c
        instructions += i
        if suppress:
            sr = _logic_sr(sr, read(SUPPRESS_COOLDOWN, 2), 2)
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            exit_registers['d7'] = 0
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x005E94)
        half = d0 >> 1
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | (half & 0xFFFF)
        cooldown = (read(COOLDOWN, 2) - half) & 0xFFFF
        for a, b in _bytes(COOLDOWN & 0xFFFFFF, cooldown, 2):
            order[a] = b
        c, i = _S12G_APPLY
        cycles += c
        instructions += i
        sr = _sub_sr(sr, read(COOLDOWN, 2), half, 2)
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        exit_registers['d7'] = 0
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x005E9E)

    # Neither ground test fired: the D7-based tail.
    c, i = _S22_TAIL_CMPI3
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, new_d7, player.STATE23_TRIGGER_D7_GATE, 2)
    to_trigger = new_d7 == player.STATE23_TRIGGER_D7_GATE
    c, i = _S22_TAIL_BEQ3[to_trigger]
    cycles += c
    instructions += i

    if to_trigger:
        c, i = _S22_TRIGGER_TAIL
        cycles += c
        instructions += i
        for a, b in _bytes(player.STATE_INDEX, player.STATE23_TRIGGER_INDEX, 2):
            order[a] = b
        exit_registers['d7'] = 0   # moveq #0,d7: a full 32-bit clear
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = _logic_sr(sr, 0, 2)   # moveq #0,d7 is the last flag-setter
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x0062AC)

    c, i = _S22_TAIL_CMPI1
    cycles += c
    instructions += i
    sr = _cmp_sr(sr, new_d7, player.STATE23_CONSUME_D7_GATE, 2)
    to_consume = new_d7 == player.STATE23_CONSUME_D7_GATE
    c, i = _S22_TAIL_BNE1[not to_consume]
    cycles += c
    instructions += i

    if not to_consume:
        exit_registers['pc'] = 0x0075D6
        exit_registers['sr'] = sr
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers=exit_registers, last_pc=0x006296)

    c, i = _S5_JSR_CONSUME
    cycles += c
    instructions += i
    for a, b in _bytes((sp32 - 4) & 0xFFFFFF, 0x0062A0, 4):
        order[a] = b

    def _read_for_consume(a, s, _x=position_x_after, _y=new_y):
        masked = a & 0xFFFFFF
        if masked == (player.POSITION_X & 0xFFFFFF):
            return _x
        if masked == (player.POSITION_Y & 0xFFFFFF):
            return _y
        return read(a, s)
    cc_cycles, cc_instructions, cc_order, cc_registers, last_slot = _cc_resolve(
        machine, _read_for_consume, registers, 1, sp32 - 4)
    cycles += cc_cycles
    instructions += cc_instructions
    order.update(cc_order)
    exit_registers.update(cc_registers)

    from .game import pickups
    if last_slot['arm'] == 'empty':
        last_value = read(pickups.CONTACT_SLOTS[2], 4) & 0xFFFFFFFF
        width = 4
    elif last_slot['type'] == 9:
        last_value, width = 0x2F, 2
    else:
        num_groups = len(last_slot['groups'])
        if num_groups < 3:
            last_value = 0
        elif last_slot['pooled']:
            last_value = 0xFFFA
        else:
            last_value = _CC_GROUP2_CONST[1]
        width = 2
    sr = (_logic_sr(sr, last_value, width) & ~0x10) | (sr & 0x10)

    c, i = _S22_CONSUME_BRA
    cycles += c
    instructions += i
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x0062A0)


# --- 005EA2: state 10 -- state 12's own oscillation head and BOTH block tests, reused verbatim, in
# front of a genuinely NEW ground tail.  See game.player's own module note above state10_step/
# state10_ground_tail.  Costed one instruction-block at a time from the tracer on real fixtures over
# census-005EA2-* (all five recordings; 22 real path classes collapsing to two real terminal
# shapes -- a small census, but every branch this session's own recipe requires was witnessed).
STATE10_ENTRY = 0x005EA2

_S10_GROUND_BEQ = {True: (10, 1), False: (8, 1)}       # 005F9E beq.b -- taken: ground found directly
_S10_ALT_BLT_WORD = {True: (10, 1), False: (12, 1)}    # 005FAC blt.w -- taken(<8): exit unchanged (word branch)
_S10_ALT_GROUND_BEQ = {True: (10, 1), False: (8, 1)}   # 005FB6 beq.b -- taken: ground found (alt)
_S10_UNCHANGED_BRA = (10, 1)                           # 005FB8 bra.w $75d6

_S10_GROUND_SET_STATE = (16, 1)                        # 005FBC move.w #$11,f192.w
_S10_GROUND_TST_F1A8 = (12, 1)                         # 005FC2 tst.w f1a8.w
_S10_GROUND_BMI_F1A8 = {True: (10, 1), False: (8, 1)}  # 005FC6 bmi.b -- taken(<0): skip the decrement
_S10_GROUND_DECREMENT = (16, 1)                        # 005FC8 subq.w #1,f192.w (mem)
_S10_G_MASK_Y = (20, 1)                                # 005FCC andi.w #$fff0,f18e.w
_S10_G_TICK_TEST = (12 + 8, 2)                         # 005FD2 move f198,d0; 005FD6 subi.w #$14,d0
_S10_G_TICK_BLE = {True: (10, 1), False: (8, 1)}       # 005FDA ble.b -- taken(<=0): skip the cooldown apply (byte branch)
_S10_G_SUPPRESS_TEST = (12, 1)                         # 005FDC tst.w f1b6.w
_S10_G_SUPPRESS_BNE = {True: (10, 1), False: (8, 1)}   # 005FE0 bne.b -- taken(!=0): skip the apply (byte branch)
_S10_G_APPLY = (8 + 16, 2)                             # 005FE2 asr.w #1,d0; 005FE4 sub.w d0,ef3e.w
_S10_G_TAIL = (4 + 16, 2)                              # 005FE8 moveq #0,d7; 005FEA move.w #$39,fdf6.w -- shared
_S10_G_BRA = (10, 1)                                   # 005FF0 bra.w $75d6 -- shared


def state10_plan(machine, registers):
    """005EA2 (state 10): the player state machine's own dispatch table entry 10.  See
    game.player's own module note above state10_step/state10_ground_tail."""
    from .game import player
    from .game.grid import grid_cell
    if registers['pc'] != STATE10_ENTRY:
        raise UnsupportedCandidate('state 10 planner needs the machine parked at 005EA2')
    sr = registers['sr']
    read = _reader(machine)
    sp32 = registers['a7']
    order = {}
    exit_registers = {}

    hc, hi, osc = _state12_head_cost(read)
    cycles, instructions = hc, hi
    new_y = (read(player.POSITION_Y, 2) + osc['position_y_delta']) & 0xFFFF
    for a, b in _bytes(player.POSITION_Y, new_y, 2):
        order[a] = b
    for a, b in _bytes(player.F194 & 0xFFFFFF, osc['f194'], 2):
        order[a] = b
    for a, b in _bytes(player.F198 & 0xFFFFFF, osc['f198'], 2):
        order[a] = b
    if osc['sound']:
        from .game.hazard import SOUND_COMMAND
        for a, b in _bytes(SOUND_COMMAND & 0xFFFFFF, 0x50, 2):
            order[a] = b
    sr = _cmp_sr(sr, osc['f198'], player.STATE12_TICK_CAP, 2)

    read_orig = read

    def read(a, s, _y=new_y):
        return _y if (a & 0xFFFFFF) == (player.POSITION_Y & 0xFFFFFF) else read_orig(a, s)

    ea20 = player._signed_word(read(player.EA20_WORD, 2))
    position_x = read(player.POSITION_X, 2)
    f1a0 = read(player.F1A0, 2)

    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x005EE6, 4))
    cell1 = grid_cell(read)
    exit_registers['a0'] = cell1['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell1['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell1['d1']
    sr = _asl_sr(sr, cell1['row_source'], 3, 2)

    c, i = _S12_LEFT_GATE_TEST
    cycles += c
    instructions += i
    retry_open = f1a0 < player.STATE12_RETRY_CAP
    provisional_state = None
    position_x_after = position_x
    if ea20 == -1:
        c, i = _S12_LEFT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if retry_open:
            provisional_state = 0xB
            c, i = _S12_LEFT_SET_STATE
            cycles += c
            instructions += i
            address = cell1['address']
            low = position_x & 0x1F
            c, i = _S12_LR_HEAD
            cycles += c
            instructions += i
            c, i = _S12_LEFT_BNE_LOW[low != 0]
            cycles += c
            instructions += i
            blocked = False
            if low == 0:
                for offset in (-1, 0x7F, 0xFF):
                    c, i = _S12_GRID_TEST
                    cycles += c
                    instructions += i
                    hit = read((address + offset) & 0xFFFFFF, 1) == 1
                    c, i = _S12_GRID_BEQ[hit]
                    cycles += c
                    instructions += i
                    if hit:
                        blocked = True
                        break
                if not blocked:
                    nibble = read(player.POSITION_Y, 2) & 0xF
                    c, i = _S12_NIBBLE_HEAD
                    cycles += c
                    instructions += i
                    c, i = _S12_NIBBLE_BEQ[nibble == 0]
                    cycles += c
                    instructions += i
                    if nibble != 0:
                        c, i = _S12_NIBBLE_TEST
                        cycles += c
                        instructions += i
                        blocked = read((address + 0x17F) & 0xFFFFFF, 1) == 1
                        c, i = _S12_NIBBLE_BEQ2[blocked]
                        cycles += c
                        instructions += i
            if not blocked:
                c, i = _S12_LEFT_ADVANCE
                cycles += c
                instructions += i
                position_x_after = (position_x - 4) & 0xFFFF
                for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                    order[a] = b
                for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                    order[a] = b
    else:
        c, i = _S12_LEFT_GATE_BNE[True]
        cycles += c
        instructions += i

    c, i = _S12_RIGHT_GATE_TEST
    cycles += c
    instructions += i
    if ea20 == 1:
        c, i = _S12_RIGHT_GATE_BNE[False]
        cycles += c
        instructions += i
        c, i = _S12_RETRY_TEST
        cycles += c
        instructions += i
        c, i = _S12_RETRY_BGE[not retry_open]
        cycles += c
        instructions += i
        if retry_open:
            provisional_state = 0xC
            c, i = _S12_RIGHT_SET_STATE
            cycles += c
            instructions += i
            address = cell1['address']
            low = position_x & 0x1C
            c, i = _add(_S12_LR_HEAD, _S12_RIGHT_MASK_TEST)
            cycles += c
            instructions += i
            mask_match = low == 0x1C
            c, i = _S12_RIGHT_MASK_BEQ[mask_match]
            cycles += c
            instructions += i
            run_test = mask_match
            if not mask_match:
                c, i = _S12_RIGHT_LOW_TEST
                cycles += c
                instructions += i
                skip_test = low >= 8
                c, i = _S12_RIGHT_LOW_BGE[skip_test]
                cycles += c
                instructions += i
                run_test = not skip_test
            blocked = False
            if run_test:
                for offset in (1, 0x81, 0x101):
                    c, i = _S12_GRID_TEST
                    cycles += c
                    instructions += i
                    hit = read((address + offset) & 0xFFFFFF, 1) == 1
                    c, i = _S12_GRID_BEQ[hit]
                    cycles += c
                    instructions += i
                    if hit:
                        blocked = True
                        break
                if not blocked:
                    nibble = read(player.POSITION_Y, 2) & 0xF
                    c, i = _S12_NIBBLE_HEAD
                    cycles += c
                    instructions += i
                    c, i = _S12_NIBBLE_BEQ[nibble == 0]
                    cycles += c
                    instructions += i
                    if nibble != 0:
                        c, i = _S12_NIBBLE_TEST
                        cycles += c
                        instructions += i
                        blocked = read((address + 0x181) & 0xFFFFFF, 1) == 1
                        c, i = _S12_NIBBLE_BEQ2[blocked]
                        cycles += c
                        instructions += i
            if not blocked:
                c, i = _S12_RIGHT_ADVANCE
                cycles += c
                instructions += i
                position_x_after = (position_x + 4) & 0xFFFF
                for a, b in _bytes(player.POSITION_X, position_x_after, 2):
                    order[a] = b
                for a, b in _bytes(player.F1A0 & 0xFFFFFF, (f1a0 + 1) & 0xFFFF, 2):
                    order[a] = b
    else:
        c, i = _S12_RIGHT_GATE_BNE[True]
        cycles += c
        instructions += i

    if provisional_state is not None:
        for a, b in _bytes(player.STATE_INDEX, provisional_state, 2):
            order[a] = b

    def _read_after_move(a, s, _x=position_x_after):
        return _x if (a & 0xFFFFFF) == (player.POSITION_X & 0xFFFFFF) else read(a, s)
    c, i = _S12_BSR_GRID
    cycles += c
    instructions += i
    cycles += GRID_CELL_COST[0]
    instructions += GRID_CELL_COST[1]
    order.update(_bytes((sp32 - 4) & 0xFFFFFF, 0x005F98, 4))
    cell2 = grid_cell(_read_after_move)
    address2 = cell2['address']
    exit_registers['a0'] = cell2['address'] & 0xFFFFFFFF
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | cell2['d0']
    exit_registers['d1'] = (registers['d1'] & 0xFFFF0000) | cell2['d1']
    sr = _asl_sr(sr, cell2['row_source'], 3, 2)

    c, i = _S12_GROUND_TEST
    cycles += c
    instructions += i
    ground = read((address2 + 0x180) & 0xFFFFFF, 1) == 1
    c, i = _S10_GROUND_BEQ[ground]
    cycles += c
    instructions += i

    if not ground:
        low = _read_after_move(player.POSITION_X, 2) & 0x1F
        exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | low
        c, i = _add(_S12_ALT_HEAD, _S12_ALT_TEST)
        cycles += c
        instructions += i
        sr = _cmp_sr(sr, low, 8, 2)
        alt_low = low < 8
        c, i = _S10_ALT_BLT_WORD[alt_low]
        cycles += c
        instructions += i
        if alt_low:
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x005FAC)
        c, i = _S12_ALT_GROUND_TEST
        cycles += c
        instructions += i
        alt_byte = read((address2 + 0x181) & 0xFFFFFF, 1)
        ground = alt_byte == 1
        sr = _cmp_sr(sr, alt_byte, 1, 1)
        c, i = _S10_ALT_GROUND_BEQ[ground]
        cycles += c
        instructions += i
        if not ground:
            c, i = _S10_UNCHANGED_BRA
            cycles += c
            instructions += i
            exit_registers['pc'] = 0x0075D6
            exit_registers['sr'] = sr
            return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                              registers=exit_registers, last_pc=0x005FB8)

    # Ground found (directly, or via the ALT test).
    f1a8 = player._signed_word(read(player.F1A8, 2))
    c, i = _S10_GROUND_SET_STATE
    cycles += c
    instructions += i
    state_index = player.STATE10_GROUND_INDEX
    c, i = _S10_GROUND_TST_F1A8
    cycles += c
    instructions += i
    sr = _logic_sr(sr, f1a8, 2)
    negative = f1a8 < 0
    c, i = _S10_GROUND_BMI_F1A8[negative]
    cycles += c
    instructions += i
    if not negative:
        c, i = _S10_GROUND_DECREMENT
        cycles += c
        instructions += i
        state_index = player.STATE10_GROUND_INDEX_ADJUSTED
        sr = _sub_sr(sr, player.STATE10_GROUND_INDEX, 1, 2)
    for a, b in _bytes(player.STATE_INDEX, state_index, 2):
        order[a] = b

    c, i = _S10_G_MASK_Y
    cycles += c
    instructions += i
    masked_y = new_y & 0xFFF0
    for a, b in _bytes(player.POSITION_Y, masked_y, 2):
        order[a] = b
    sr = _logic_sr(sr, masked_y, 2)

    c, i = _S10_G_TICK_TEST
    cycles += c
    instructions += i
    d0 = player._signed_word((osc['f198'] - 0x14) & 0xFFFF)
    exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | ((osc['f198'] - 0x14) & 0xFFFF)
    sr = _sub_sr(sr, osc['f198'], 0x14, 2)
    skip_apply = d0 <= 0
    c, i = _S10_G_TICK_BLE[skip_apply]
    cycles += c
    instructions += i

    if not skip_apply:
        from .game.zones import COOLDOWN, SUPPRESS_COOLDOWN
        suppress = read(SUPPRESS_COOLDOWN, 2) & 0xFFFF != 0
        c, i = _S10_G_SUPPRESS_TEST
        cycles += c
        instructions += i
        sr = _logic_sr(sr, read(SUPPRESS_COOLDOWN, 2), 2)
        c, i = _S10_G_SUPPRESS_BNE[suppress]
        cycles += c
        instructions += i
        if not suppress:
            half = d0 >> 1
            exit_registers['d0'] = (registers['d0'] & 0xFFFF0000) | (half & 0xFFFF)
            cooldown = (read(COOLDOWN, 2) - half) & 0xFFFF
            for a, b in _bytes(COOLDOWN & 0xFFFFFF, cooldown, 2):
                order[a] = b
            c, i = _S10_G_APPLY
            cycles += c
            instructions += i
            sr = _sub_sr(sr, read(COOLDOWN, 2), half, 2)

    c, i = _S10_G_TAIL
    cycles += c
    instructions += i
    exit_registers['d7'] = 0
    from .game.pickups import MOVEMENT_SOUND_CUE
    for a, b in _bytes(MOVEMENT_SOUND_CUE & 0xFFFFFF, 0x39, 2):
        order[a] = b
    sr = _logic_sr(sr, 0x39, 2)   # 005FEA move.w #$39,fdf6.w is the last flag-setter
    c, i = _S10_G_BRA
    cycles += c
    instructions += i
    exit_registers['pc'] = 0x0075D6
    exit_registers['sr'] = sr
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                      registers=exit_registers, last_pc=0x005FF0)


# --- 005700: the player state machine's own dispatch head, composed as the family over FFFFF192 --
#
# The dispatcher's own prefix (d7 <- STATE_COUNTER FFFFF190, d0 <- STATE_INDEX FFFFF192, the
# FROZEN_FLAG/ACTIVE_GATE inactive arm falling straight into the already-armed player-tail gate,
# the STATE_TABLE lookup at 005618 otherwise) owning the jump into each recovered state's own
# planner: the same "call the callee's own planner from a machine parked at its own entry, prepend
# this region's own cost" composition `achievement_slot_dispatch_plan` already draws over
# `achievement_slot_reset_plan` -- but, unlike that seam-of-seam (0047DA's own inline VDP work makes
# it a platform block the original must run opaquely), no device access sits between 005700's own
# entry and the target handler's own first instruction, so the callee's own AtomicPlan/Seam is reused
# directly (`_prefix_atomic_or_seam`, already proven by state19_plan/state18_plan's own outer heads),
# never ceded to the machine.  Costs from the tracer (artifacts/gods/evidence/census-005700-*, and
# the FROZEN_FLAG/ACTIVE_GATE branches poked directly, since no recording sets either).
PLAYER_STATE_ENTRY = 0x005700
PLAYER_STATE_TABLE = 0x005618

_PS_LOAD_D7 = (12, 1)                                # 005700 move.w f190.w,d7
_PS_LEA_TABLE = (8, 1)                               # 005704 lea.l 5618(pc),a0
_PS_LOAD_D0 = (12, 1)                                # 005708 move.w f192.w,d0
_PS_TST_FROZEN = (12, 1)                             # 00570C tst.b eecd.w
_PS_BNE_FROZEN = {True: (10, 1), False: (12, 1)}     # 005710 bne.w 75d6 (word branch)
_PS_TST_GATE = (12, 1)                               # 005714 tst.w f210.w
_PS_BPL_INACTIVE = {True: (10, 1), False: (12, 1)}   # 005718 bpl.w 75d6 (word branch)
_PS_ASL = (12, 1)                                    # 00571C asl.w #3,d0
_PS_MOVEA = (18, 1)                                  # 00571E movea.l 4(a0,d0.w),a0
_PS_JMP = (8, 1)                                     # 005722 jmp (a0)

# Real STATE_TABLE indices with a recovered handler of their own: every witnessed state (17 September's
# own full-history tally) except 7 and 15 (game.player.UNWITNESSED_STATES: a bare rts and a body only
# ever reached via state 4's own shared-fallthrough jump, never as FFFFF192's own value).  Real index
# 26 (player.STATE_HANDLERS[26], ROM 005724 -- the tree's largest single decline before this session,
# 1,975 of 8,857 fallbacks) is recovered as `state_26_plan` (18 Sep, real-index-26 session); the
# candidate PREVIOUSLY named 'state-26' targeted STATE26_ENTRY (0069AC), which the STATE_TABLE
# reconstruction showed is player.STATE_HANDLERS[20], not [26] -- that candidate is renamed
# 'state-20' in recovery.py (the gate PC and this dict entry are unchanged: this composition is
# keyed by the PC the STATE_TABLE actually holds at each index, not by any candidate's own name).
_PLAYER_STATE_PLANNERS = {
    STATE0_ENTRY: state0_plan, STATE1_ENTRY: state1_plan, STATE2_ENTRY: state2_plan,
    STATE3_ENTRY: state3_plan, STATE4_ENTRY: state4_plan, STATE5_ENTRY: state5_plan,
    STATE6_ENTRY: state6_plan, STATE8_ENTRY: state8_plan, STATE9_ENTRY: state9_plan,
    STATE10_ENTRY: state10_plan, STATE11_ENTRY: state11_plan, STATE12_ENTRY: state12_plan,
    STATE13_ENTRY: state13_plan, STATE14_ENTRY: state14_plan, STATE16_ENTRY: state16_plan,
    STATE17_ENTRY: state17_plan, STATE18_ENTRY: state18_plan, STATE19_ENTRY: state19_plan,
    STATE21_ENTRY: state21_plan, STATE22_ENTRY: state22_plan, STATE23_ENTRY: state23_plan,
    STATE24_ENTRY: movement_hit_primary_plan, STATE25_ENTRY: movement_hit_secondary_plan,
    STATE26_ENTRY: state26_plan, STATE27_ENTRY: state27_plan, STATE28_ENTRY: state28_plan,
    STATE_26_ENTRY: state_26_plan,   # real STATE_TABLE index 26 (005724) -- STATE26_ENTRY above is index 20
}


def _merge_head(result, head_overlay, extra_cycles, extra_instructions):
    """Fold this region's own head cost AND its own register overlay into the callee's own plan/seam.

    `_prefix_atomic_or_seam` alone (state19_plan/state18_plan's own shape) is right when the outer
    head never itself changes a register: it just bumps the cost and passes the callee's own
    ``registers`` dict through unchanged.  Here the head DOES set d0/a0 (the STATE_TABLE scratch) --
    a value dead on every witnessed arm, but still the real ROM's own residue -- and a callee that
    never revisits them (most of the plain state-transition arms) would silently lose them if only
    its own delta reached the adapter: ``AtomicPlan.registers`` is a delta against the CALLEE's own
    entry, not against the real machine's entry at 005700, so an unset register reverts to whatever
    it was BEFORE this whole activation began.  ``head_overlay`` restates the head's own effect first;
    the callee's own returned registers are applied on top, so anything it DOES set (a taken grid-cell
    branch's own a0/d0) still wins.
    """
    if isinstance(result, Seam):
        p = result.prefix
        merged = dict(head_overlay)
        merged.update(p.registers)
        new_prefix = AtomicPlan(cycles=p.cycles + extra_cycles, instructions=p.instructions + extra_instructions,
                                writes=p.writes, registers=merged, last_pc=p.last_pc)
        return Seam(prefix=new_prefix, resume_pc=result.resume_pc, stack_basis=result.stack_basis,
                   guards=result.guards, suffix=result.suffix, expect=result.expect)
    merged = dict(head_overlay)
    merged.update(result.registers)
    return AtomicPlan(cycles=result.cycles + extra_cycles, instructions=result.instructions + extra_instructions,
                      writes=result.writes, registers=merged, last_pc=result.last_pc)


def player_state_plan(machine, registers):
    """005700: the player state machine's own dispatch, composed as the family over FFFFF192 -- the
    dispatcher's own prefix owning the jump into each recovered state's own planner (or into the
    already-armed player-tail gate directly, on the FROZEN_FLAG/ACTIVE_GATE inactive arm)."""
    from .game import player
    if registers['pc'] != PLAYER_STATE_ENTRY:
        raise UnsupportedCandidate('player state planner needs the machine parked at 005700')
    sp = registers['a7'] & 0xFFFFFF
    if sp & 1:
        raise UnsupportedCandidate('unaligned stack')
    read = _reader(machine)

    d7_word = read(player.STATE_COUNTER, 2)
    state_index = read(player.STATE_INDEX, 2)
    frozen_byte = read(player.FROZEN_FLAG, 1)

    cycles, instructions = _add(_PS_LOAD_D7, _PS_LEA_TABLE, _PS_LOAD_D0, _PS_TST_FROZEN)
    sr = _logic_sr(registers['sr'], frozen_byte, 1)
    frozen = bool(frozen_byte)
    c, i = _PS_BNE_FROZEN[frozen]
    cycles, instructions = cycles + c, instructions + i

    handoff_registers = dict(registers)
    handoff_registers['d7'] = (registers['d7'] & 0xFFFF0000) | d7_word
    handoff_registers['d0'] = (registers['d0'] & 0xFFFF0000) | state_index
    handoff_registers['a0'] = PLAYER_STATE_TABLE
    head_overlay = {'d7': handoff_registers['d7'], 'd0': handoff_registers['d0'], 'a0': handoff_registers['a0']}

    if frozen:
        handoff_registers['pc'] = PLAYER_TAIL_ENTRY
        handoff_registers['sr'] = sr
        result = player_tail_plan(machine, handoff_registers)
        return _merge_head(result, head_overlay, cycles, instructions)

    gate = player._signed_word(read(player.ACTIVE_GATE, 2))
    c, i = _PS_TST_GATE
    cycles, instructions = cycles + c, instructions + i
    sr = _logic_sr(sr, gate, 2)
    inactive = gate >= 0
    c, i = _PS_BPL_INACTIVE[inactive]
    cycles, instructions = cycles + c, instructions + i

    if inactive:
        handoff_registers['pc'] = PLAYER_TAIL_ENTRY
        handoff_registers['sr'] = sr
        result = player_tail_plan(machine, handoff_registers)
        return _merge_head(result, head_overlay, cycles, instructions)

    if not (0 <= state_index < len(player.STATE_HANDLERS)):
        raise UnsupportedCandidate(f'player state {state_index} outside the 29-entry STATE_TABLE')
    handler_entry = player.STATE_HANDLERS[state_index]
    planner = _PLAYER_STATE_PLANNERS.get(handler_entry)
    if planner is None:
        raise UnsupportedCandidate(
            f'player state {state_index} (ROM {handler_entry:06X}) not witnessed by a recording')

    c, i = _PS_ASL
    cycles, instructions = cycles + c, instructions + i
    sr = _asl_sr(sr, state_index, 3, 2)
    c, i = _PS_MOVEA
    cycles, instructions = cycles + c, instructions + i
    c, i = _PS_JMP
    cycles, instructions = cycles + c, instructions + i

    handoff_registers['d0'] = (registers['d0'] & 0xFFFF0000) | ((state_index << 3) & 0xFFFF)
    handoff_registers['a0'] = handler_entry & 0xFFFFFFFF
    handoff_registers['pc'] = handler_entry
    handoff_registers['sr'] = sr
    head_overlay = {'d7': handoff_registers['d7'], 'd0': handoff_registers['d0'], 'a0': handoff_registers['a0']}
    result = planner(machine, handoff_registers)
    return _merge_head(result, head_overlay, cycles, instructions)
