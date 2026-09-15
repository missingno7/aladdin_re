"""The object script language: animation scripts and motion scripts as decoded data.

Recovered from the interpreter at 1AC784 (animation channel), the motion
runner at 1ADE36 (secondary channel) and the 21 handlers reached through
the opcode table at ROM 4954.  Both channels share the handlers; the
animation channel encodes an opcode as a byte 0xEA..0xFE, the motion
channel as 0x80..0x94 (same table index).  Words below 0xE000 in an
animation script are sprite frames; a motion script is a sequence of
signed (dx, dy) byte pairs each optionally followed by opcodes.
"""
from __future__ import annotations
from dataclasses import dataclass, field

FRAME_TABLE_LIMIT = 0xE000       # animation words below this are frame-table addresses
ANIMATION_OPCODE_BASE = 0xEA
MOTION_OPCODE_BASE = 0x80
OPCODE_COUNT = 21

# Named opcodes, by table index.  ``operands`` is a format string decoded by
# ``decode_operands``: b byte, w word, l long, a address-word (FF0000-relative
# or record-relative depending on a mode bit), m mode byte, v value sized by
# the preceding mode, t branch target (long).
OPCODES = (
    ('jump', 'l'),                     # EA: a2 = long
    ('flip', 'b'),                     # EB: 0 flips facing (+09), else the vertical flip (+35)
    ('end', 'b'),                      # EC: 0 ends the motion channel (+0A), else the animation (+20)
    ('set', 'mav'),                    # ED: write a byte/word/long to memory
    ('wait', 'b'),                     # EE: bit7 -> wait N frames; else loop counter = N, loop start = here
    ('loop', ''),                      # EF: decrement the loop counter and jump to the loop start
    ('random_jump', 'bt'),             # F0: jump if RNG byte < threshold
    ('move', 'bw'),                    # F1: 0 -> X += word in the facing direction, else Y += word (flip)
    ('branch_bit', 'mat'),             # F2: jump if bit (mode & 7) of the byte is set (mode bit6 inverts)
    ('sound', 'b'),                    # F3: play sound id (bit7: request without flush) when FFF57D is set
    ('branch_compare', 'mavt'),        # F4: jump if imm <op> memory; op in mode bits 4-5
    ('spawn', 'bl bb ll'),             # F5: mode, template, dx, dy, animation script, motion script
    ('destroy', 'b'),                  # F6: release this record (mode)
    ('face_player', ''),               # F7: facing = player X >= my X
    ('player_select', ''),             # F8: choose the player's animation from the state flags
    ('home', 'bbb'),                   # F9: speed, y-window, x-window: steer velocity toward the player
    ('add', 'mav'),                    # FA: add (bit7: subtract) a value to memory
    ('call_native', 'l'),              # FB: continue in 68000 code at the address
    ('resume', 'b'),                   # FC: bit7 -> jump to the saved script (+38)
    ('near_x', 'bt'),                  # FD: jump if |player X - my X| <= N (FF = 0x140)
    ('near_y', 'bt'),                  # FE: jump if |player Y - my Y| <= N
)


@dataclass(frozen=True)
class Frame:
    address: int          # where the word sits in the script
    word: int             # frame-table address (ROM)
    descriptor: int       # sprite frame descriptor address (ROM)


@dataclass(frozen=True)
class Op:
    address: int
    code: int             # table index 0..20
    name: str
    operands: tuple
    size: int             # bytes consumed including the opcode byte
    target: int | None = None   # branch/jump target when the opcode has one


@dataclass(frozen=True)
class MotionStep:
    address: int
    dx: int
    dy: int


@dataclass
class Script:
    address: int
    kind: str                                 # 'animation' or 'motion'
    items: list = field(default_factory=list)
    blocks: dict = field(default_factory=dict)  # target address -> Script (decoded branch targets)

    def frames(self):
        return [i for i in self.items if isinstance(i, Frame)]

    def ops(self):
        return [i for i in self.items if isinstance(i, Op)]


def _u16(rom, a):
    return int.from_bytes(rom[a:a + 2], 'big')


def _u32(rom, a):
    return int.from_bytes(rom[a:a + 4], 'big')


def _address_operand(rom, pc, mode, relative_bit):
    """The address operand of set/add/branch: record-relative word or FF0000+word."""
    word = _u16(rom, pc)
    if mode & (1 << relative_bit):
        return ('record', word if word < 0x8000 else word - 0x10000)
    return ('ram', 0xFF0000 | word)


def _value_size(mode):
    return {1: 1, 2: 2}.get(mode & 3, 4)


def decode_op(rom: bytes, pc: int, code: int) -> Op:
    """Decode one opcode (table index ``code``) whose opcode byte sits at ``pc``."""
    name, fmt = OPCODES[code]
    p = pc + 1
    operands = []
    target = None
    if name in ('jump', 'call_native'):
        # ``addq.l #2,a2``: the long sits after a pad byte
        value = _u32(rom, pc + 2)
        target = value if name == 'jump' else None
        operands = [value]; p = pc + 6
    elif name in ('flip', 'end', 'wait', 'sound', 'destroy', 'resume'):
        operands = [rom[p]]; p += 1
    elif name == 'loop' or name == 'face_player' or name == 'player_select':
        p += 1  # the handlers skip the pad byte after the opcode
    elif name == 'random_jump':
        operands = [rom[p]]; target = _u32(rom, p + 1); operands.append(target); p += 5
    elif name == 'move':
        axis = rom[p]; operands = [axis, _u16(rom, p + 1)]; p += 3
    elif name == 'set':
        mode = rom[p]; where = _address_operand(rom, p + 1, mode, 4); size = _value_size(mode & ~0x10)
        raw = _u16(rom, p + 3) if size <= 2 else _u32(rom, p + 3)
        value = raw & 0xFF if size == 1 else raw
        operands = [size, where, value]; p += 3 + (2 if size <= 2 else 4)
    elif name == 'add':
        mode = rom[p]; where = _address_operand(rom, p + 1, mode, 6); sub = bool(mode & 0x80)
        size = _value_size(mode & 0x3F)
        raw = _u16(rom, p + 3) if size <= 2 else _u32(rom, p + 3)
        operands = [size, where, (-1 if sub else 1) * (raw & 0xFF if size == 1 else raw)]
        p += 3 + (2 if size <= 2 else 4)
    elif name == 'branch_bit':
        mode = rom[p]; where = _address_operand(rom, p + 1, mode, 7)
        operands = [mode & 7, where, 'set' if mode & 0x40 else 'clear']   # bit6 set: jump when the bit is set
        target = _u32(rom, p + 3); operands.append(target); p += 7
    elif name == 'branch_compare':
        mode = rom[p]; where = _address_operand(rom, p + 1, mode, 7)
        size = _value_size(mode & 0x87)
        raw = _u16(rom, p + 3) if size <= 2 else _u32(rom, p + 3)
        value = raw & 0xFF if size == 1 else raw
        op = {0x00: 'imm<mem', 0x10: 'eq', 0x20: 'ne', 0x30: 'imm>=mem'}.get(mode & 0x70, f'?{mode & 0x70:02X}')
        p += 3 + (2 if size <= 2 else 4)
        target = _u32(rom, p); operands = [size, where, op, value, target]; p += 4
    elif name == 'spawn':
        mode = rom[p]; template = _u32(rom, p + 1)
        dx = rom[p + 5]; dy = rom[p + 6]
        dx = dx - 256 if dx & 0x80 else dx; dy = dy - 256 if dy & 0x80 else dy
        operands = [mode, template, dx, dy, _u32(rom, p + 7), _u32(rom, p + 11)]; p += 15
    elif name == 'home':
        operands = [rom[p], rom[p + 1], rom[p + 2]]; p += 3
    elif name in ('near_x', 'near_y'):
        operands = [rom[p]]; target = _u32(rom, p + 1); operands.append(target); p += 5
    else:
        raise ValueError(name)
    return Op(pc, code, name, tuple(operands), p - pc, target)


def decode_animation(rom: bytes, address: int, *, max_items=400, follow=True, _seen=None) -> Script:
    """Decode the animation script at ``address`` until it ends or transfers control."""
    seen = _seen if _seen is not None else set()
    script = Script(address, 'animation')
    pc = address
    ends = {'jump', 'end', 'call_native', 'resume', 'loop', 'player_select'}
    for _ in range(max_items):
        head = rom[pc]
        if 0xEA <= head <= 0xFE:
            op = decode_op(rom, pc, head - ANIMATION_OPCODE_BASE)
            script.items.append(op)
            pc += op.size
            if op.name in ends:
                break
        elif head >= 0xE0:
            break   # not a frame word and not an opcode: end of decodable data
        else:
            word = _u16(rom, pc)
            script.items.append(Frame(pc, word, _u32(rom, word)))
            pc += 2
    if follow:
        seen.add(address)
        for op in script.ops():
            if op.target is not None and op.target not in seen and 0 < op.target < len(rom):
                seen.add(op.target)
                script.blocks[op.target] = decode_animation(rom, op.target, max_items=max_items, follow=True, _seen=seen)
    return script


def decode_motion(rom: bytes, address: int, *, max_items=400, follow=True, _seen=None) -> Script:
    """Decode the motion script at ``address``: (dx, dy) pairs, each followed by 0..n opcodes."""
    seen = _seen if _seen is not None else set()
    script = Script(address, 'motion')
    pc = address
    ends = {'jump', 'end', 'call_native', 'resume', 'loop', 'player_select'}
    stop = False
    for _ in range(max_items):
        dx, dy = rom[pc], rom[pc + 1]
        script.items.append(MotionStep(pc, dx - 256 if dx & 0x80 else dx, dy - 256 if dy & 0x80 else dy))
        pc += 2
        while 0x80 <= rom[pc] < 0x95:
            op = decode_op(rom, pc, rom[pc] - MOTION_OPCODE_BASE)
            script.items.append(op)
            pc += op.size
            if op.name in ends:
                stop = True
                break
        if stop:
            break
    if follow:
        seen.add(address)
        for op in script.ops():
            if op.target is not None and op.target not in seen and 0 < op.target < len(rom):
                seen.add(op.target)
                script.blocks[op.target] = decode_motion(rom, op.target, max_items=max_items, follow=True, _seen=seen)
    return script


def format_script(script: Script, indent='') -> str:
    lines = [f'{indent}{script.kind} script {script.address:06X}']
    for item in script.items:
        if isinstance(item, Frame):
            lines.append(f'{indent}  {item.address:06X}  frame {item.word:04X} -> {item.descriptor:06X}')
        elif isinstance(item, MotionStep):
            lines.append(f'{indent}  {item.address:06X}  step dx={item.dx:+d} dy={item.dy:+d}')
        else:
            args = ', '.join(f'{a:06X}' if isinstance(a, int) and a > 0xFFFF else str(a) for a in item.operands)
            lines.append(f'{indent}  {item.address:06X}  {item.name}({args})')
    for target, block in script.blocks.items():
        lines.append(format_script(block, indent + '    '))
    return '\n'.join(lines)
