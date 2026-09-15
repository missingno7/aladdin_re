"""Object spawning from the level map: the spawn-caller table decoded into spawn sites.

Every cell of a newly exposed map strip carries a spawn flag (FFAE87 +
``cell word >> 1``).  A non-zero flag indexes the table at ROM 0x4154, whose
256 entries point at small "spawn caller" routines in 1B65BE..1B7640.  Each
caller is the same shape: optional guards (a progress flag, the level, the
difficulty, a coordinate), one of five allocators that takes a free record
from a pool, expands the caller's 19-byte template into it and places it
at the strip anchor plus the strip offset, then a few field adjustments
(position nudges, a different kind or script, a linked partner), sometimes
a palette load or a sound.

Rather than hand-copy ~90 such routines, :func:`site` decodes a caller from
the ROM into a small program of named operations over a spawn context
(the new record, its partner, the template, the scratch word) and
:func:`run_site` executes it.  Anything the decoder does not recognise is
kept as an ``unsupported`` operation that raises when reached, so a gap is
reported at its exact ROM address instead of guessed around.  The
allocators' pool order and exhaustion behaviour (a failed allocation leaves
the record pointer at the pool's end and some callers still write through
it) are reproduced exactly.
"""
from __future__ import annotations
import re
from .objects.record import RECORD_TABLE, RECORD_SIZE
from .objects.lifecycle import initialize
from .rng import SEED_ADDRESS, advance_rng
from .level import WINDOW_X, WINDOW_Y, MAP_CURSOR, MAP_STRIDE, COLUMN_CELLS, ROW_CELLS
from . import video

SPAWN_TABLE = 0x4154             # ROM: 256 longs, flag -> spawn caller
SPAWN_FLAGS = 0xFFAE87           # byte per cell-word/2: 0 = nothing (or already spawned)
STRIP_X_OFFSET, STRIP_Y_OFFSET = 0xFFF150, 0xFFF152   # placement offset for the strip being walked
STRIP_ANCHOR_X, STRIP_ANCHOR_Y = 0xFF7DB0, 0xFF7DB2   # placement anchor (the window origin / the running cell)
TEMPLATE_SIZE = 19
RANDOM = 0x1B3032

# allocator entry -> (first record, count, direction, clear the cell's spawn flag)
POOLS = {
    0x1B524E: (RECORD_TABLE + RECORD_SIZE, 24, 1, True),          # slots 1..24 upward
    0x1B5256: (RECORD_TABLE + RECORD_SIZE * 24, 24, -1, True),    # slots 24..1 downward
    0x1B525E: (RECORD_TABLE + RECORD_SIZE * 20, 20, -1, True),    # slots 20..1 downward
    0x1B5266: (RECORD_TABLE + RECORD_SIZE * 3, 20, 1, True),      # slots 3..22 upward
    0x1B52A0: (RECORD_TABLE + RECORD_SIZE * 3, 20, 1, False),     # slots 3..22 upward, flag kept (respawns)
}
FIND_FREE = {0x1AE262: (RECORD_TABLE + RECORD_SIZE * 3, 20, 1)}
FIND_KIND_POOL = (RECORD_TABLE + RECORD_SIZE, 24)                # 1AE2F2: main pool, slots 1..24


class SpawnGap(Exception):
    """A spawn caller reached an operation the decoder does not model."""


def _h(text):
    return int(text, 16)


def _off(text):
    return int(text, 16) if text else 0


_ALLOCATORS = '|'.join(f'{a:06x}' for a in POOLS)
_DECODERS = (
    (r'^lea\.l \$([0-9a-f]+)\.l, a6$', lambda m: ('template', _h(m[1]))),
    (r'^lea\.l \$([0-9a-f]+)\.l, a0$', lambda m: ('palette_source', _h(m[1]))),
    (rf'^(?:bsr\.w|jsr) \$({_ALLOCATORS})(?:\.l)?$', lambda m: ('allocate', _h(m[1]))),
    (r'^jsr \$1ae262\.l$', lambda m: ('find_free', 0x1AE262)),
    (r'^jsr \$1ae2f2\.l$', lambda m: ('find_kind',)),
    (r'^jsr \$1ae30a\.l$', lambda m: ('copy_template',)),
    (r'^move\.b #\$([0-9a-f]+), d0$', lambda m: ('kind_arg', _h(m[1]))),
    (r'^(bne|beq|bra|bcc|bcs)\.[bw] \$([0-9a-f]+)$', lambda m: ('branch', m[1], _h(m[2]))),
    (r'^rts$', lambda m: ('return',)),
    (r'^tst\.b \$([0-9a-f]+)\.l$', lambda m: ('test_byte', _h(m[1]))),
    (r'^cmpi\.([bw]) #\$([0-9a-f]+), \$([0-9a-f]+)\.l$', lambda m: ('compare', 1 if m[1] == 'b' else 2, _h(m[3]), _h(m[2]))),
    (r'^cmpi\.b #\$([0-9a-f]+), d7$', lambda m: ('compare_scratch', _h(m[1]))),
    (r'^btst\.b #\$([0-9a-f]+), d7$', lambda m: ('test_scratch_bit', _h(m[1]))),
    (r'^move\.([bwl]) #\$([0-9a-f]+), (?:\$([0-9a-f]+))?\(a5\)$',
     lambda m: ('set', _off(m[3]), {'b': 1, 'w': 2, 'l': 4}[m[1]], _h(m[2]))),
    (r'^(addi|addq)\.w #\$([0-9a-f]+), \$([0-9a-f]+)\(a5\)$', lambda m: ('add', _h(m[3]), _h(m[2]))),
    (r'^subi\.w #\$([0-9a-f]+), \$([0-9a-f]+)\(a5\)$', lambda m: ('add', _h(m[2]), -_h(m[1]))),
    (r'^clr\.([bwl]) \$([0-9a-f]+)\(a5\)$', lambda m: ('set', _h(m[2]), {'b': 1, 'w': 2, 'l': 4}[m[1]], 0)),
    (r'^st\.b \$([0-9a-f]+)\(a5\)$', lambda m: ('set', _h(m[1]), 1, 0xFF)),
    (r'^eori\.b #\$([0-9a-f]+), \$([0-9a-f]+)\(a5\)$', lambda m: ('xor', _h(m[2]), _h(m[1]))),
    (r'^clr\.b \$([0-9a-f]+)\.l$', lambda m: ('write', _h(m[1]), 1, 0)),
    (r'^st\.b \$([0-9a-f]+)\.l$', lambda m: ('write', _h(m[1]), 1, 0xFF)),
    (r'^movea\.l a5, a3$', lambda m: ('remember_partner',)),
    (r'^move\.l a3, \$([0-9a-f]+)\(a5\)$', lambda m: ('link_partner', _h(m[1]))),
    (r'^move\.l a5, \$([0-9a-f]+)\(a3\)$', lambda m: ('link_back', _h(m[1]))),
    (r'^move\.w \$([0-9a-f]+)\(a5\), d7$', lambda m: ('scratch_from_field', _h(m[1]))),
    (r'^addi\.w #\$([0-9a-f]+), d7$', lambda m: ('scratch_add', _h(m[1]))),
    (r'^subi\.w #\$([0-9a-f]+), d7$', lambda m: ('scratch_add', -_h(m[1]))),
    (r'^andi\.w #\$([0-9a-f]+), d7$', lambda m: ('scratch_and', _h(m[1]))),
    (r'^move\.w d7, \$([0-9a-f]+)\.l$', lambda m: ('write_scratch', _h(m[1]))),
    (r'^add\.w d7, \$([0-9a-f]+)\(a5\)$', lambda m: ('add_scratch_to_field', _h(m[1]))),
    (rf'^bsr\.w \${RANDOM:x}$', lambda m: ('random',)),
    (r'^(?:bsr\.w|jsr) \$1b2650(?:\.l)?$', lambda m: ('palette', 2)),
    (r'^movem\.l .*$', lambda m: ('nop',)),
    (r'^jsr \$1e58f4\.l$', lambda m: ('sound_command', 0x16)),
    (r'^pea\.l \$([0-9a-f]+)\.w$', lambda m: ('push', _h(m[1]))),
    (r'^jsr \$1e58b8\.l$', lambda m: ('sound_request',)),
    (r'^jsr \$1e589a\.l$', lambda m: ('sound_flush',)),
    (r'^addq\.l #\$4, a7$', lambda m: ('nop',)),
    (r'^move\.l a0, -\(a7\)$', lambda m: ('nop',)),
    (r'^movea\.l \(a7\)\+, a0$', lambda m: ('nop',)),
    (r'^bsr\.[bw] \$([0-9a-f]+)$', lambda m: ('call', _h(m[1]))),
)
_COMPILED = [(re.compile(p), f) for p, f in _DECODERS]
_FLAG_SETTERS = {'test_byte', 'compare', 'compare_scratch', 'test_scratch_bit', 'allocate',
                 'find_free', 'find_kind', 'call', 'scratch_and', 'scratch_add'}
_MD = None
_SITES = {}


def _disasm(rom, pc):
    global _MD
    if _MD is None:
        import capstone
        _MD = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000)
    insn = next(iter(_MD.disasm(rom[pc:pc + 10], pc)), None)
    if insn is None:
        return 'dc.w', 2
    return (insn.mnemonic + ' ' + insn.op_str).strip(), insn.size


def site(rom, entry):
    """Decode one spawn caller: {pc: (op, next_pc)}; branch targets are decoded too."""
    if entry in _SITES:
        return _SITES[entry]
    program, work = {}, [entry]
    while work:
        pc = work.pop()
        previous = None
        while pc not in program:
            text, size = _disasm(rom, pc)
            op = None
            for pattern, decode in _COMPILED:
                m = pattern.match(text)
                if m:
                    op = decode(m)
                    break
            if op is None:
                op = ('unsupported', pc, text)
            if op[0] == 'branch' and previous not in _FLAG_SETTERS:
                op = ('unsupported', pc, f'{text} after {previous}')
            program[pc] = (op, pc + size)
            if op[0] in ('return', 'unsupported'):
                break
            if op[0] == 'branch':
                work.append(op[2])
                if op[1] == 'bra':
                    break
            previous = op[0]
            pc += size
    _SITES[entry] = program
    return program


class SpawnContext:
    """The locals of one spawn caller while it runs."""
    def __init__(self, cell, flag):
        self.cell, self.flag = cell, flag
        self.record = None          # the record being spawned into (a5)
        self.partner = None         # a linked partner spawned just before (a3)
        self.template = None
        self.palette_source = None
        self.scratch = 0            # d7
        self.kind_arg = 0
        self.pushed = None
        self.pending_sound = None
        self.zero = self.carry = False


def _find(read, start, count, direction, *, kind=None):
    for i in range(count):
        address = start + direction * RECORD_SIZE * i
        value = read(address, 1)
        if value == (0 if kind is None else kind):
            return address, True
    return start + direction * RECORD_SIZE * count, False


def _place(read, write, ctx, clear):
    """1B526C: expand the template and place the record at anchor + offset (the shared allocator tail)."""
    record = ctx.record
    for address, value in initialize(record, bytes(ctx.template)):
        write(address, value, 1)
    write(record + 0x32, ctx.cell, 2)
    write(record + 0x34, ctx.flag, 1)
    write(record + 2, (read(STRIP_X_OFFSET, 2) + read(STRIP_ANCHOR_X, 2)) & 0xFFFF, 2)
    write(record + 4, (read(STRIP_Y_OFFSET, 2) + read(STRIP_ANCHOR_Y, 2)) & 0xFFFF, 2)
    if clear:
        write(SPAWN_FLAGS + ctx.cell, 0, 1)


def run_site(entry, ctx, read, write, rom, vdp, services):
    program = site(rom, entry)
    pc = entry
    while True:
        op, next_pc = program[pc]
        kind = op[0]
        if kind == 'return':
            if ctx.pending_sound is not None:
                services.sound(0, ctx.pending_sound, flush=False)
                ctx.pending_sound = None
            return
        if kind == 'unsupported':
            raise SpawnGap(f'spawn caller {entry:06X}: {op[2]} at {op[1]:06X}')
        if kind == 'branch':
            cond = op[1]
            taken = {'bra': True, 'bne': not ctx.zero, 'beq': ctx.zero, 'bcc': not ctx.carry, 'bcs': ctx.carry}[cond]
            pc = op[2] if taken else next_pc
            continue
        if kind == 'template':
            ctx.template = rom[op[1]:op[1] + TEMPLATE_SIZE]
        elif kind == 'palette_source':
            ctx.palette_source = op[1]
        elif kind == 'allocate':
            start, count, direction, clear = POOLS[op[1]]
            ctx.record, ok = _find(read, start, count, direction)
            if ok:
                _place(read, write, ctx, clear)
            ctx.zero, ctx.carry = ok, False
        elif kind == 'find_free':
            start, count, direction = FIND_FREE[op[1]]
            ctx.record, ctx.zero = _find(read, start, count, direction)
            ctx.carry = False
        elif kind == 'find_kind':
            _, ctx.zero = _find(read, FIND_KIND_POOL[0], FIND_KIND_POOL[1], 1, kind=ctx.kind_arg)
            ctx.carry = False
        elif kind == 'copy_template':
            for address, value in initialize(ctx.record, bytes(ctx.template)):
                write(address, value, 1)
        elif kind == 'kind_arg':
            ctx.kind_arg = op[1]
        elif kind == 'test_byte':
            ctx.zero, ctx.carry = read(op[1], 1) == 0, False
        elif kind == 'compare':
            value = read(op[2], op[1])
            ctx.zero, ctx.carry = value == op[3], value < op[3]
        elif kind == 'compare_scratch':
            value = ctx.scratch & 0xFF
            ctx.zero, ctx.carry = value == op[1], value < op[1]
        elif kind == 'test_scratch_bit':
            ctx.zero, ctx.carry = not (ctx.scratch >> op[1]) & 1, False
        elif kind == 'set':
            write(ctx.record + op[1], op[3], op[2])
        elif kind == 'add':
            write(ctx.record + op[1], (read(ctx.record + op[1], 2) + op[2]) & 0xFFFF, 2)
        elif kind == 'xor':
            write(ctx.record + op[1], read(ctx.record + op[1], 1) ^ op[2], 1)
        elif kind == 'write':
            write(op[1], op[3], op[2])
        elif kind == 'remember_partner':
            ctx.partner = ctx.record
        elif kind == 'link_partner':
            write(ctx.record + op[1], ctx.partner, 4)
        elif kind == 'link_back':
            write(ctx.partner + op[1], ctx.record, 4)
        elif kind == 'scratch_from_field':
            ctx.scratch = read(ctx.record + op[1], 2)
        elif kind == 'scratch_add':
            ctx.scratch = (ctx.scratch + op[1]) & 0xFFFF
            ctx.zero, ctx.carry = ctx.scratch == 0, False
        elif kind == 'scratch_and':
            ctx.scratch &= op[1]
            ctx.zero, ctx.carry = ctx.scratch == 0, False
        elif kind == 'write_scratch':
            write(op[1], ctx.scratch, 2)
        elif kind == 'add_scratch_to_field':
            write(ctx.record + op[1], (read(ctx.record + op[1], 2) + ctx.scratch) & 0xFFFF, 2)
        elif kind == 'random':
            seed, ctx.scratch = advance_rng(read(SEED_ADDRESS, 4))
            write(SEED_ADDRESS, seed, 4)
        elif kind == 'palette':
            video.load_palette(write, rom, vdp, op[1], ctx.palette_source)
        elif kind == 'sound_command':
            services.sound_command(op[1])
        elif kind == 'push':
            ctx.pushed = op[1]
        elif kind == 'sound_request':
            ctx.pending_sound = ctx.pushed
        elif kind == 'sound_flush':
            services.sound(0, ctx.pending_sound, flush=True)
            ctx.pending_sound = None
        elif kind == 'call':
            run_site(op[1], ctx, read, write, rom, vdp, services)
        elif kind == 'nop':
            pass
        else:
            raise AssertionError(kind)
        pc = next_pc


def walk_strip(read, write, rom, vdp, services, *, row: bool, far: bool) -> None:
    """1AE3FC / 1AE406 (columns) and 1AE47E / 1AE488 (rows): spawn whatever the new strip's cells carry."""
    if row:
        write(STRIP_Y_OFFSET, 0x1E0 if far else 0xF0, 2)
        write(STRIP_X_OFFSET, 0xFFF0, 2)
        write(STRIP_ANCHOR_Y, read(WINDOW_Y, 2) & 0xFFF0, 2)
        running = read(WINDOW_X, 2) & 0xFFF0
        count, stride = ROW_CELLS, 2
    else:
        write(STRIP_X_OFFSET, 0x150 if far else 0xFFF0, 2)
        write(STRIP_Y_OFFSET, 0xF0, 2)
        write(STRIP_ANCHOR_X, read(WINDOW_X, 2) & 0xFFF0, 2)
        running = read(WINDOW_Y, 2) & 0xFFF0
        count, stride = COLUMN_CELLS, read(MAP_STRIDE, 2)
        stride = stride - 0x10000 if stride & 0x8000 else stride
    cursor = read(MAP_CURSOR, 4)
    for _ in range(count):
        cell = read(cursor, 2) >> 1
        flag = read(SPAWN_FLAGS + cell, 1)
        if flag:
            write(STRIP_ANCHOR_X if row else STRIP_ANCHOR_Y, running, 2)
            target = int.from_bytes(rom[SPAWN_TABLE + 4 * flag:SPAWN_TABLE + 4 * flag + 4], 'big')
            ctx = SpawnContext(cell, flag)
            run_site(target, ctx, read, write, rom, vdp, services)
            if ctx.record is not None and read(ctx.record, 1):
                services.spawned(flag, ctx.record, read(ctx.record, 1))
        cursor = (cursor + stride) & 0xFFFFFFFF
        running = (running + 16) & 0xFFFF
