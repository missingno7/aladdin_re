"""Isolate each on-screen object's sprite by deactivating it in a scratch copy and diffing two frames."""
import json, os, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[3] / 'src'))
os.environ.setdefault('GENESIS_NATIVE_LIBRARY', 'D:/Prog/aladdin_re/build/libgenesis_native.dll')
import numpy as np
from genesis_re.history import HistoryStore
from aladdin_sega.profile import read_rom, FRAME_TICKS
from genesis_re.history_runtime import GenesisRun
from aladdin_sega.profile import ALADDIN
from PIL import Image

out = 'D:/Prog/aladdin_re/artifacts/cartography/masks'
os.makedirs(out, exist_ok=True)
frames = list(range(*[int(x) for x in sys.argv[1].split(':')])) if ':' in sys.argv[1] else [int(x) for x in sys.argv[1].split(',')]
store = HistoryStore('D:/Prog/aladdin_re/history/aladdin', ALADDIN.history_root)
rom = read_rom()
path = store.flatten(store.resolve('main'))
events = path['events']
index = []


def render_after(m, saved, frames_ahead, poke=None):
    m.restore(saved)
    if poke is not None:
        regs = m.registers()
        m.gates([regs['pc']])
        if m.run(instructions=1) != 'gate':
            m.gates([]); return None
        ok = m.atomic(target=m.info['tick'] + 10_000_000, cycles=1, instructions=1, last_pc=regs['pc'],
                      writes=[poke], registers=regs)
        m.gates([])
        if not ok:
            return None
    m.run(target=m.info['tick'] + frames_ahead * FRAME_TICKS)
    w, h, px = m.frame()
    return np.frombuffer(px, dtype=np.uint8).reshape(h, w, 3)


with GenesisRun(ALADDIN, rom, 'original') as run:
    for f in frames:
        run.advance(f, [e for e in events if e['frame'] >= run.frame], lambda r: None)
        m = run.machine
        saved = m.snapshot()
        ram = m.peek_ram(0, 65536)
        w2 = lambda a: int.from_bytes(ram[a & 0xFFFF:(a & 0xFFFF) + 2], 'big')
        l4 = lambda a: int.from_bytes(ram[a & 0xFFFF:(a & 0xFFFF) + 4], 'big')
        cam = (w2(0xFF7DF6), w2(0xFF7DF8) + 192)
        base = render_after(m, saved, 2)
        for slot in range(1, 31):
            rec = 0xFF7E40 + slot * 66
            kind = ram[rec & 0xFFFF]
            if kind == 0:
                continue
            sx, sy = w2(rec + 2) - cam[0], w2(rec + 4) - cam[1]
            if not (-48 <= sx <= 368 and -48 <= sy <= 272):
                continue
            alt = render_after(m, saved, 2, poke=(rec, 0))
            if alt is None:
                continue
            diff = np.any(base != alt, axis=2)
            if diff.sum() < 12:
                continue
            ys, xs = np.where(diff)
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            if (x1 - x0) * (y1 - y0) > 160 * 160:
                continue   # the deactivation changed the scene more broadly (camera, HUD); not a clean mask
            crop = base[y0:y1, x0:x1].copy()
            crop[~diff[y0:y1, x0:x1]] = (255, 0, 255)   # magenta = not this object
            name = f'k{kind:02X}_{l4(rec + 0x20):06X}_f{f}_s{slot}'
            Image.fromarray(crop).resize(((x1 - x0) * 3, (y1 - y0) * 3), Image.NEAREST).save(os.path.join(out, name + '.png'))
            index.append({'frame': f, 'slot': slot, 'kind': kind, 'script': f'{l4(rec + 0x20):06X}', 'hp': ram[(rec + 1) & 0xFFFF],
                          'x': w2(rec + 2), 'y': w2(rec + 4), 'screen': (int(sx), int(sy)), 'bbox': [int(x0), int(y0), int(x1), int(y1)]})
        m.restore(saved)
        print(f, 'objects masked so far', len(index), flush=True)
json.dump(index, open(os.path.join(out, 'index.json'), 'w'), indent=1)
print('done', len(index))
