"""Differential check of the semantic script engine against the original at its own boundaries.

For each requested frame: replay the original to that frame, run to the
interpreter's entry (1AC784), copy RAM, run to its RTS (1AC84E), and compare
the original's RAM changes with the engine's ``animation_pass`` run over
the copied RAM; likewise 1ADE36 -> 1AE0AE for ``motion_pass``.  Records
whose processing handed off to a native effect are reported separately.
"""
import os, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
os.environ.setdefault('GENESIS_NATIVE_LIBRARY', str(Path(__file__).resolve().parents[2] / 'build' / 'libgenesis_native.dll'))
from genesis_re.history import HistoryStore
from aladdin_sega.profile import read_rom
from genesis_re.history_runtime import GenesisRun
from aladdin_sega.game.objects.record import RECORD_TABLE, RECORD_SIZE, FIELDS
from aladdin_sega.game.objects.script_engine import Engine, Memory, Services, Trace
from aladdin_sega.profile import ALADDIN

ANIM = (0x1AC784, (0x1AC84E, 0x1B0334))   # 1B0334 is the even-frame RTS
MOTION = (0x1ADE36, (0x1AE0AE,))
root = Path(__file__).resolve().parents[2]


def field_name(address):
    if RECORD_TABLE <= address < RECORD_TABLE + 32 * RECORD_SIZE:
        slot, off = divmod(address - RECORD_TABLE, RECORD_SIZE)
        for name, (o, size, _) in FIELDS.items():
            if o <= off < o + size:
                return f'slot{slot}.{name}'
        return f'slot{slot}+{off:02X}'
    return f'{address:06X}'


BOOKKEEPING = [(0xFF769A, 0xFF7800, 'DMA upload queue (1AC6D0)'), (0xFFEF80, 0xFFEFE0, 'stack'),
               (0xFF7D9A, 0xFF7DA3, 'continuation pointers / channel flag'), (0xFFEFEE, 0xFFEFF0, 'queue counters')]


def bookkeeping(address):
    return any(lo <= address < hi for lo, hi, _ in BOOKKEEPING)


def run_boundary(m, entry, exits):
    m.gates([entry, *exits])
    for _ in range(4):
        if m.run(target=m.info['tick'] + 10 * 896040) != 'gate':
            return None
        if m.info['pc'] == entry:
            break
        m.gate(m.info['pc'], bypass_once=True)
    else:
        return None
    before = bytearray(m.peek_ram(0, 65536))
    m.gate(entry, bypass_once=True)
    if m.run(target=m.info['tick'] + 10 * 896040) != 'gate' or m.info['pc'] not in exits:
        return None
    after = bytearray(m.peek_ram(0, 65536))
    return before, after


def engine_over(rom, before, which):
    ram = bytearray(before)
    def read(a, n): return int.from_bytes(ram[a & 0xFFFF:(a & 0xFFFF) + n], 'big')
    def write(a, v, n): ram[a & 0xFFFF:(a & 0xFFFF) + n] = v.to_bytes(n, 'big')
    trace = Trace()
    engine = Engine(Memory(read, write, rom), Services(trace))
    (engine.animation_pass if which == 'anim' else engine.motion_pass)()
    return ram, trace


def compare(before, after, mine, trace):
    changed = {a for a in range(65536) if before[a] != after[a]} | {a for a in range(65536) if before[a] != mine[a]}
    handoff_slots = {h.slot for h in trace.handoffs if h.kind != 'frame_upload'}
    bad = collections.OrderedDict()
    for a in sorted(changed):
        if after[a] != mine[a]:
            if bookkeeping(0xFF0000 | a):
                continue
            name = field_name(0xFF0000 | a)
            slot = int(name[4:name.index('.')]) if name.startswith('slot') and '.' in name else None
            if slot in handoff_slots:
                continue
            bad[name] = (before[a], after[a], mine[a])
    return bad, handoff_slots


def main():
    frames = [int(x) for x in sys.argv[1].split(',')] if len(sys.argv) > 1 else [1000, 8500, 16266, 22200, 44827, 57289, 69586, 82000]
    which = sys.argv[2] if len(sys.argv) > 2 else 'anim'
    store = HistoryStore(str(root / 'history' / 'aladdin'), ALADDIN.history_root); rom = read_rom()
    path = store.flatten(store.resolve('main')); events = path['events']
    totals = collections.Counter()
    with GenesisRun(ALADDIN, rom, 'original') as run:
        for f in frames:
            run.advance(f, [e for e in events if e['frame'] >= run.frame], lambda r: None)
            m = run.machine
            saved = m.snapshot()
            for repeat in range(3):
                result = run_boundary(m, *(ANIM if which == 'anim' else MOTION))
                if result is None:
                    print(f, 'boundary not reached'); break
                before, after = result
                mine, trace = engine_over(rom, before, which)
                bad, handoffs = compare(before, after, mine, trace)
                totals['passes'] += 1; totals['mismatch_passes'] += bool(bad); totals['bad_fields'] += len(bad)
                print(f'frame {f}+{repeat}: {len([a for a in range(65536) if before[a] != after[a]])} bytes changed by the original, '
                      f'{len(bad)} mismatching fields, handoffs {sorted(handoffs)} {[h.kind for h in trace.handoffs if h.kind != "frame_upload"][:6]}')
                for name, (b, a, mv) in list(bad.items())[:12]:
                    print(f'    {name}: before {b:02X} original {a:02X} engine {mv:02X}')
            m.restore(saved); m.gates([])
    print('totals', dict(totals))


if __name__ == '__main__':
    main()
