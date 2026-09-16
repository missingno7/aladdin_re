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
