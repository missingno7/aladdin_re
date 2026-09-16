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


def hazard_tick_plan(machine, registers):
    """014084: the grid-gated pool spawn, or the tile-array paint; the 'trigger' arm (calls 00F828) is declined."""
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
        raise UnsupportedCandidate('hazard tick trigger arm calls unrecovered 00F828')
    high = lambda name: registers[name] & 0xFFFF0000
    if arm == 'spawn':
        _spans_disjoint([('hazard pool entry', hazard.POOL_BASE & 0xFFFFFF, hazard.POOL_STRIDE * hazard.POOL_COUNT),
                         ('hazard pending flag', a3, 2)])
        cycles = (_HZ_HEAD_ACTIVE[0] + _HZ_GRID_SETUP[0] + _HZ_GRID_MATCH[0] + _HZ_SOUND_WRITE[0]
                  + _HZ_TYPE_MISMATCH[0] + _HZ_POOL_SETUP[0])
        instructions = (_HZ_HEAD_ACTIVE[1] + _HZ_GRID_SETUP[1] + _HZ_GRID_MATCH[1] + _HZ_SOUND_WRITE[1]
                        + _HZ_TYPE_MISMATCH[1] + _HZ_POOL_SETUP[1])
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
        # counter) clears it, and nothing after ever restores the caller's own upper half.
        exit_registers = {'d4': result['d4'], 'd5': high('d5') | result['d5'],
                          'a1': result['a1'], 'a2': registers['a1'],
                          'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr}
        writes = tuple(pair for address, (value, size) in result['stores'].items() for pair in _bytes(address, value, size))
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


def evaluator_plan(machine, registers):
    """00462C: the trigger evaluator's non-firing arm, three composed calls into 00470C."""
    from .game import triggers
    if registers['pc'] != EVALUATOR_ENTRY:
        raise UnsupportedCandidate('trigger evaluator planner needs the machine parked at 00462C')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    a0 = registers['a0'] & 0xFFFFFFFF
    read = _reader(machine)
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
    _spans_disjoint([('trigger frame', sp, 4), ('trigger record', entry & 0xFFFFFF, triggers.TRIGGER_STRIDE)])
    cycles, instructions = _TE_HEAD
    # muls.w #$18,d0 (the head's own index-to-entry-offset multiply) leaves the full 32-bit signed
    # product in d0 before the first internal call -- the caller's own entering d0 is gone by then.
    index_signed = index - 0x10000 if index & 0x8000 else index
    regs = {'d0': (index_signed * triggers.TRIGGER_STRIDE) & 0xFFFFFFFF, 'd1': registers['d1'],
           'd5': registers['d5'], 'd6': registers['d6'], 'a4': registers['a4'], 'a5': registers['a5']}
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
                      'd1': regs.get('d1', registers['d1']), 'd5': regs['d5'], 'd6': regs['d6'],
                      'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr}
    writes = list(_bytes(triggers.SLOT_BASE & 0xFFFFFF, 0xFFFFFFFF, 4))
    writes.extend(_bytes((triggers.SLOT_BASE + 4) & 0xFFFFFF, 0xFFFF, 2))
    for call in result['calls']:
        writes.extend(pair for address, (value, size) in call['result']['stores'].items()
                      for pair in _bytes(address, value, size))
    writes.extend(_bytes((sp - 4) & 0xFFFFFF, _TE_RETURN_PC[len(result['calls']) - 1], 4))
    return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(writes), registers=exit_registers,
                      last_pc=EVALUATOR_LAST_PC)


# --- 00F828: the proximity table search-and-add (game/hazard.py: proximity_search/proximity_add) ---
#
# Owns its own internal call into 00F86A the way 0049DA owns its calls into
# 001164: no separate gate for 00F86A, the whole activation planned as one.
# Cost from the tracer (artifacts/gods/evidence/census-00F828*): the head
# (both the search's own hash and the outer routine's), the search's four
# per-position shapes (miss/close/stale/trigger), the free-slot scan's two
# (free/occupied), and the add body (a redundant recompute of the same key).
PROXIMITY_ENTRY, PROXIMITY_ADD_LAST_PC = 0x00F828, 0x00F868
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


def proximity_plan(machine, registers):
    """00F828: the proximity table search-and-add; 'trigger' (00F8A2 onward) and 'pool-full' decline."""
    from .game import hazard
    if registers['pc'] != PROXIMITY_ENTRY:
        raise UnsupportedCandidate('proximity planner needs the machine parked at 00F828')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    a1 = registers['a1'] & 0xFFFFFFFF
    read = _reader(machine)
    search = hazard.proximity_search(read, a1)
    if search['arm'] == 'trigger':
        raise UnsupportedCandidate('proximity trigger arm (00F8A2) is not recovered (left for the supervisor)')
    cycles, instructions = _PX_BSR
    c, i = _PX_HASH_HEAD
    cycles += c
    instructions += i
    positions = search['positions']
    costs = {'miss': (_PX_MISS_MID, _PX_MISS_LAST), 'close': (_PX_CLOSE_MID, _PX_CLOSE_LAST),
            'stale': (_PX_STALE_MID, _PX_STALE_LAST)}
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
    slot_base = (hazard.PROXIMITY_TABLE + hazard.PROXIMITY_STRIDE * added['index']) & 0xFFFFFFFF
    counter_before = added['counter_before']
    exit_sr = _add_sr(sr, counter_before, 1, 2)
    # d4's word ops (andi.w/lsl.w) preserve whatever upper half the long subtract left; d5 is all
    # long ops (andi.l/lsr.l), so its exit value is the full 32-bit result, no upper half to keep.
    exit_registers = {'d4': (search['offset'] & 0xFFFF0000) | search['d4'], 'd5': search['d5'] & 0xFFFFFFFF,
                      'd6': (registers['d6'] & 0xFFFF0000) | 0xFFFF,
                      'a0': (slot_base + 4) & 0xFFFFFFFF, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                      'pc': _return(machine, sp), 'sr': exit_sr}
    # The internal bsr.w $f86a's own return address, pushed once and never popped by anything else:
    # it's dead stack scratch (a7 is back above it by the time this routine returns) but a real write.
    writes = list(_bytes((sp - 4) & 0xFFFFFF, 0x00F82C, 4))
    writes.extend(pair for address, (value, size) in added['stores'].items() for pair in _bytes(address, value, size))
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
PICKUP_CHECK_ZONE_CUE_LAST_PC = 0x00BAE2      # the sound-off arm's own rts
PICKUP_CHECK_ZONE_CUE_SOUND_ON_LAST_PC = 0x00BADA   # the sound-on arm has its OWN separate rts
PICKUP_CHECK_CLEAN_LAST_PC = 0x00BBCA
PICKUP_CHECK_SOUND_LAST_PC = 0x00BC42
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
_PK_BEQ_D4_TAKEN = (10, 1)              # beq.b (d4==0, the only witnessed continuation)
_PK_TST_EF46 = (12, 1)                  # tst.w MESSAGE_FLAG
_PK_BEQ_EF46_TAKEN = (10, 1)            # beq.b (ef46==0, the only witnessed continuation)
_PK_SUB_D3_D2 = (4, 1)                  # sub.w d3,d2
_PK_BMI_RESULT_TAKEN, _PK_BMI_RESULT_NOTTAKEN = (10, 1), (8, 1)     # bmi.b $bc24
_PK_BNE_RESULT_TAKEN, _PK_BNE_RESULT_NOTTAKEN = (10, 1), (8, 1)     # bne.b $bc4e
_PK_STORE_F3D4 = (12, 1)                # move.w d2,RESULT_WORD
_PK_TST_D3 = (4, 1)                     # tst.w d3
_PK_BEQ_D3_NOTTAKEN = (8, 1)            # beq.b not taken (d3!=0, the effect chain)

_PK_EFFECT_RESTORE_A0A2 = (36, 1)       # movem.l (a7)+,a0-a2
_PK_EFFECT_PEEK_D2D3 = (28, 1)          # movem.l (a7),d2-d3 (peek, not pop)
_PK_EFFECT_HALF = (12 + 8 + 4, 3)       # move.w size,d4; asr.w #1,d4; add.w d4,Dn
_PK_EFFECT_MASK = (8, 1)                # andi.w #$fff0,d4
_PK_EFFECT_MASK_BNE = (10, 1)           # bne.b taken (the only witnessed arm: the default-mask branch declines)
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
        # code -4 and below: the caller must decline before ever reaching here.
        raise UnsupportedCandidate(f"pickup award code {collected['code']} is not recovered")
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

    if arm in ('found-special', 'found-message'):
        raise UnsupportedCandidate(f'pickup check {arm} arm not witnessed by a recording')

    collect_result = result['collect']
    if collect_result['arm'] == 'unrecovered':
        # A grid code of -4 or below: 013264 itself declines this (the continuation into 013316,
        # not yet recovered), so the composition must decline it too rather than fall through.
        raise UnsupportedCandidate(f"pickup check found a code {collect_result['code']} 013264 declines")
    c, i = _add(_PK_PUSH_D2, _PK_JSR_AWARD, _pickup_award_cost(read, collect_result), _PK_POP_D2, _PK_READ_AWARD,
               _PK_TST_D4, _PK_BEQ_D4_TAKEN, _PK_TST_EF46, _PK_BEQ_EF46_TAKEN, _PK_SUB_D3_D2)
    cycles += c
    instructions += i
    # a1 at this point is the SCAN's own jump-table entry address (set at 00BB84-00BB90), not the
    # caller's original a1: the scan overwrote it, and nothing restores it before this push.
    scan_a1 = (0x00BBBC - 4 * result['cols']) & 0xFFFFFFFF
    _ram_span('pickup check award call frame', sp - 56, 12)
    _pk_push(order, sp - 44, [registers['d2']])          # move.l d2,-(a7)
    _pk_push(order, sp - 48, [0x00BBD4])                 # jsr $13264.l's own return address
    _pk_push(order, sp - 52, [scan_a1])                  # 013264's own move.l a1,-(a7)
    # collect_result['stores'] is NOT re-applied here: result['stores'] (seeded into order at the top
    # of this function) already carries it, merged by pickup_check() in the ROM's own order -- 013264's
    # own award cue (SOUND_CUE=0x38) first, then this routine's own cue store (0x3C/0x4F) overwriting
    # it on the found-sound arm.  Re-applying it here would undo that overwrite (the bug the tree
    # divergence at fb408bc75597 frame 6840 traced to: FFFDF5 left 0x38 instead of 0x3C).

    if arm == 'found-sound':
        box_result = result['box_result']
        if pickups._signed_word(box_result) < 0:
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
        # moveq #$ff,d2 sets N=1/Z=V=C=0 but never touches X: X survives from the sub.w d3,d2 that
        # produced box_result, untouched by every MOVE/TST/movem between here and there.
        x_bit = _sub_sr(sr, result['d2_before_award'], result['d3'], 2) & 0x10
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=tuple(order.items()),
                          registers={'d2': 0xFFFFFFFF, 'a7': (sp32 + 4) & 0xFFFFFFFF,
                                     'pc': _return(machine, sp), 'sr': 0x08 | x_bit, **a4_exit},
                          last_pc=PICKUP_CHECK_SOUND_LAST_PC)

    if arm == 'found-bare':
        raise UnsupportedCandidate('pickup check found-bare (award zero) arm not witnessed by a recording')
    if arm in ('found-jitter-x-default', 'found-jitter-y-default', 'found-jitter-y-negative'):
        raise UnsupportedCandidate(f'pickup check {arm} arm not witnessed by a recording')
    if arm != 'found-effect':
        raise UnsupportedCandidate(f'pickup check unknown arm {arm}')

    c, i = _add(_PK_BMI_RESULT_NOTTAKEN, _PK_BNE_RESULT_TAKEN, _PK_STORE_F3D4, _PK_TST_D3, _PK_BEQ_D3_NOTTAKEN)
    cycles += c
    instructions += i
    for a, b in _bytes(pickups.RESULT_WORD & 0xFFFFFF, result['box_result'], 2):
        order[a] = b

    c, i = _add(_PK_EFFECT_RESTORE_A0A2, _PK_EFFECT_PEEK_D2D3, _PK_EFFECT_HALF, _PK_EFFECT_MASK, _PK_EFFECT_MASK_BNE,
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

    c, i = _add(_PK_EFFECT_HALF, _PK_EFFECT_MASK, _PK_EFFECT_MASK_BNE, _PK_EFFECT_MASK_SUBQ, _PK_JSR_RANDOM)
    cycles += c
    instructions += i
    cycles, instructions = cycles + _NR_COST[0], instructions + _NR_COST[1]
    c, i = _PK_TST_DRAW
    cycles += c
    instructions += i
    # The second draw's negative branch declines above (result['arm'] would be 'found-jitter-y-negative').
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
    if added['arm'] == 'full':
        raise UnsupportedCandidate('pickup check found-effect pool-full arm not witnessed by a recording')
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
    # move.w RESULT_WORD,d2 is the last N/Z/V/C setter (MOVE never touches X); X instead survives
    # from 00932C's OWN last flag-setter, addq.w #1,POOL_COUNTER (the 'added' arm's own X/C).
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
