"""Light instruction sampler: replay original to chosen frames, then trace whole frames.

Per sampled window it records: PC histogram, call edges (JSR/BSR site -> callee, with the
calling routine), routine attribution (nearest preceding call target), and memory operands
(absolute .l addresses and d16(An) effective addresses) read/written per routine.
"""
import json, os, re, sys, time, collections
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'src')); sys.path.insert(0, 'D:/Prog/aladdin_re/scripts')
os.environ.setdefault('ALADDIN_NATIVE_LIBRARY', 'D:/Prog/aladdin_re/build/libaladdin_native.dll')
import pathfacts
from aladdin_sega.history import HistoryStore
from aladdin_sega.profile import read_rom, FRAME_TICKS
from aladdin_sega.history_runtime import GenesisRun
from PIL import Image

out = sys.argv[3] if len(sys.argv) > 3 else 'D:/Prog/aladdin_re/artifacts/cartography/samples'
os.makedirs(out, exist_ok=True)
frames = list(range(*[int(x) for x in sys.argv[1].split(':')])) if ':' in sys.argv[1] else [int(x) for x in sys.argv[1].split(',')]
span = int(sys.argv[2]) if len(sys.argv) > 2 else 2   # frames per sample
store = HistoryStore('D:/Prog/aladdin_re/history')
rom = read_rom()
path = store.flatten(store.resolve('main'))
events = [e for e in path['events']]
ABS = re.compile(r'\$([0-9a-f]{6})\.l')
DISP = re.compile(r'(-?\$?[0-9a-f]*)\(a([0-7])\)')
WRITE_MNEMONICS = {'move', 'movea', 'clr', 'st', 'sf', 'addq', 'subq', 'add', 'sub', 'addi', 'subi', 'and', 'or', 'eor',
                   'andi', 'ori', 'eori', 'neg', 'not', 'bset', 'bclr', 'bchg', 'lsl', 'lsr', 'asl', 'asr', 'rol', 'ror',
                   'swap', 'ext', 'muls', 'mulu', 'divs', 'divu', 'movem', 'lea', 'pea', 'link', 'unlk', 'addx', 'subx', 'negx', 'cmp', 'cmpi', 'cmpa', 'tst', 'btst', 'jsr', 'bsr', 'dbra', 'dbf'}


def operand_addresses(text, regs):
    """Yield (address, size_hint, is_destination) for memory operands of one instruction."""
    parts = text.split(' ', 1)
    mnem = parts[0].split('.')[0]
    if len(parts) < 2:
        return
    ops = [o.strip() for o in parts[1].split(',')] if mnem not in ('movem',) else [parts[1]]
    for index, op in enumerate(ops):
        dest = index == len(ops) - 1 and mnem not in ('cmp', 'cmpi', 'cmpa', 'tst', 'btst', 'jsr', 'bsr', 'jmp', 'lea', 'pea', 'dbra', 'dbf')
        m = ABS.search(op)
        if m:
            yield int(m.group(1), 16), dest, mnem
            continue
        m2 = re.fullmatch(r'-?\(a([0-7])\)\+?', op)
        if m2:
            yield regs[f'a{m2.group(1)}'] & 0xFFFFFF, dest, mnem
            continue
        m = DISP.search(op)
        if m and not op.startswith('('):
            disp = m.group(1).replace('$', '')
            d = int(disp, 16) if disp not in ('', '-') else 0
            base = regs[f'a{m.group(2)}']
            yield (base + d) & 0xFFFFFF, dest, mnem


def sample(run, start_frame, count, tag):
    m = run.machine
    saved = m.snapshot()
    pc_hist = collections.Counter()
    calls = collections.Counter()        # (caller_routine, site, callee)
    routine_of_pc = {}
    mem = collections.defaultdict(collections.Counter)   # routine -> Counter[(addr, 'r'/'w')]
    stack = [None]                        # routine names by call depth
    root_sequence = []
    current = ('root', m.registers()['pc'])
    steps = 0
    regs = m.registers()
    ram = pathfacts.ram_bytes(m)
    started = time.time()
    target_tick = (start_frame + count) * FRAME_TICKS
    while m.info['tick'] < target_tick:
        pc = regs['pc']
        text, size = pathfacts.disasm(rom, ram, pc)
        mnem = text.split(' ', 1)[0].split('.')[0]
        pc_hist[pc] += 1
        routine = stack[-1] or 'root'
        for addr, dest, mn in operand_addresses(text, regs):
            if 0xFF0000 <= addr <= 0xFFFFFF:
                mem[routine][(addr, 'w' if dest else 'r')] += 1
        m.run(instructions=1)
        regs = m.registers()
        if mnem in ('jsr', 'bsr'):
            callee = regs['pc']
            calls[(routine, pc, callee)] += 1
            if len(stack) == 1 and len(root_sequence) < 600:
                root_sequence.append(f'{callee:06X}')
            stack.append(f'{callee:06X}')
        elif mnem in ('rts', 'rte', 'rtr'):
            if len(stack) > 1:
                stack.pop()
        steps += 1
        if steps % 20000 == 0:
            ram = pathfacts.ram_bytes(m)
    ram = pathfacts.ram_bytes(m)
    if len(frames) <= 40:
        w, h, pixels = m.frame()
        Image.frombytes('RGB', (w, h), pixels).save(os.path.join(out, f'{tag}.png'))
    json.dump({'frame': start_frame, 'frames': count, 'steps': steps, 'seconds': round(time.time() - started, 1),
               'root_sequence': root_sequence, 'instructions_total': m.info['m68k_instructions'],
               'pc_hist': {f'{k:06X}': v for k, v in pc_hist.most_common(4000)},
               'calls': [{'caller': c, 'site': f'{s:06X}', 'callee': f'{t:06X}', 'count': n}
                         for (c, s, t), n in calls.most_common(2000)],
               'mem': {r: [{'addr': f'{a:06X}', 'op': o, 'count': n} for (a, o), n in cnt.most_common(400)]
                       for r, cnt in mem.items()}},
              open(os.path.join(out, f'{tag}.json'), 'w'))
    m.restore(saved)
    print(tag, 'steps', steps, 'seconds', round(time.time() - started, 1), flush=True)


with GenesisRun(rom, 'original') as run:
    for f in sorted(frames):
        run.advance(f, [e for e in events if e['frame'] >= run.frame], lambda r: None)
        sample(run, f, span, f'f{f}')
print('done')
