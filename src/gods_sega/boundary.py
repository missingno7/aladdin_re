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
# Cost from the tracer (artifacts/gods/evidence/census-00FE08*): the
# 'idle' arm only -- a plain leaf, constant cost.  The 'moving' arm (common,
# not merely unwitnessed) calls the unrecovered coroutine/dispatch at
# 00FFF0 and is declined: the boundary cannot reproduce a call into code
# that has not itself been recovered.
ANIMATION_STEP_ENTRY, ANIMATION_STEP_LAST_PC = 0x00FE08, 0x00FE5A
ANIMATION_STEP_FRAME = 24                              # movem.l d0-d3/a1-a2,-(a7)
_AS_FRAME_REGISTERS = ('d0', 'd1', 'd2', 'd3', 'a1', 'a2')
ANIMATION_STEP_IDLE_COST = (194, 10)


def _animation_frame_writes(sp, registers):
    return tuple(pair for index, name in enumerate(_AS_FRAME_REGISTERS)
                 for pair in _bytes(sp - ANIMATION_STEP_FRAME + 4 * index, registers[name], 4))


def animation_step_plan(machine, registers):
    """00FE08: the frame-budget refresh and the immediate return; the 'moving' arm is declined."""
    from .game import animation
    if registers['pc'] != ANIMATION_STEP_ENTRY:
        raise UnsupportedCandidate('animation step planner needs the machine parked at 00FE08')
    sp32, sr = registers['a7'], registers['sr']
    sp = sp32 & 0xFFFFFF
    record, definition = registers['a1'] & 0xFFFFFF, registers['a2'] & 0xFFFFFF
    if (sp | record | definition) & 1:
        raise UnsupportedCandidate('unaligned stack, record or definition')
    result = animation.animation_step(_reader(machine), record, definition)
    if result['arm'] != 'idle':
        raise UnsupportedCandidate('animation step arm calls unrecovered 00FFF0: ' + result['arm'])
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
                      last_pc=ANIMATION_STEP_LAST_PC)


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
    if arm == 'trigger-deep':
        raise UnsupportedCandidate('countdown check trigger arm calls unrecovered 0091BC')
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
        return AtomicPlan(cycles=_ZC_HELD_COST[0], instructions=_ZC_HELD_COST[1], writes=(),
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=ZONE_CHECK_HELD_LAST_PC)
    frame = ('zone check frame', sp - ZONE_CHECK_FRAME, ZONE_CHECK_FRAME)
    _spans_disjoint([frame, ('zone check cooldown', zones.COOLDOWN & 0xFFFFFF, 2)])
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
    x_left, x_right = result['x_operands']
    x_bit = _add_sr(sr, x_left, x_right, 2) & 0x10
    if arm == 'outside':
        cycles, instructions = cycles + _ZC_TAIL_OUTSIDE[0], instructions + _ZC_TAIL_OUTSIDE[1]
        left, right = result['test_operands']
        exit_sr = (_cmp_sr(sr, left, right, 2) & ~0x10) | x_bit
        writes = _zone_frame_writes(sp, registers)
        return AtomicPlan(cycles=cycles, instructions=instructions, writes=writes,
                          registers={'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp), 'sr': exit_sr},
                          last_pc=ZONE_CHECK_HELD_LAST_PC)
    # 'inside'
    cycles, instructions = cycles + _ZC_INSIDE_HEAD[0], instructions + _ZC_INSIDE_HEAD[1]
    if result['suppressed']:
        cycles, instructions = cycles + _ZC_SUPPRESS_TAKEN[0], instructions + _ZC_SUPPRESS_TAKEN[1]
        x_bit = _add_sr(sr, result['shifted'], 5, 2) & 0x10
    else:
        cycles, instructions = cycles + _ZC_SUPPRESS_NOT_TAKEN[0], instructions + _ZC_SUPPRESS_NOT_TAKEN[1]
        x_bit = _sub_sr(sr, result['cooldown_before'], result['scale'], 2) & 0x10
    cycles, instructions = cycles + _ZC_INSIDE_POP[0] + _ZC_RESULT_TST[0], instructions + _ZC_INSIDE_POP[1] + _ZC_RESULT_TST[1]
    result_flag = machine.peek_ram(zones.RESULT_FLAG & 0xFFFF, 2)
    result_flag = int.from_bytes(result_flag, 'big')
    exit_registers = {'a7': (sp32 + 4) & 0xFFFFFFFF, 'pc': _return(machine, sp)}
    if result_flag != 0:
        cycles, instructions = cycles + _ZC_RESULT_TAKEN[0], instructions + _ZC_RESULT_TAKEN[1]
        exit_sr = (_logic_sr(sr, result_flag, 2) & ~0x10) | x_bit
    else:
        cycles, instructions = cycles + _ZC_RESULT_NOT_TAKEN[0], instructions + _ZC_RESULT_NOT_TAKEN[1]
        exit_registers['d2'] = 0xFFFFFFFF
        exit_sr = (0x08 & ~0x10) | x_bit          # moveq #$ff,d2: N=1, Z=V=C=0
    cycles, instructions = cycles + _ZC_RTS[0], instructions + _ZC_RTS[1]
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
