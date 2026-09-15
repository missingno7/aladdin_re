"""Render frames with boxes at each active object's screen position; also crop object sprites.

usage: object_boxes.py FRAME[,FRAME...] [crop]
Camera hypothesis: screen_x = X - w(FFF080), screen_y = Y - w(FFF082).
"""
import json, os, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'src'))
os.environ.setdefault('GENESIS_NATIVE_LIBRARY', 'D:/Prog/aladdin_re/build/libgenesis_native.dll')
from genesis_re.history import HistoryStore
from aladdin_sega.profile import read_rom
from genesis_re.history_runtime import GenesisRun
from aladdin_sega.profile import ALADDIN
from PIL import Image, ImageDraw

out = 'D:/Prog/aladdin_re/artifacts/cartography/frames'
os.makedirs(out, exist_ok=True)
frames = [int(x) for x in sys.argv[1].split(',')]
crop = len(sys.argv) > 2 and sys.argv[2] == 'crop'
YOFF = int(sys.argv[3]) if len(sys.argv) > 3 else 192
store = HistoryStore('D:/Prog/aladdin_re/history/aladdin', ALADDIN.history_root)
rom = read_rom()
path = store.flatten(store.resolve('main'))
events = path['events']
records = []


def objects(m):
    ram = m.peek_ram(0, 65536)
    w = lambda a: int.from_bytes(ram[a & 0xFFFF:(a & 0xFFFF) + 2], 'big')
    l = lambda a: int.from_bytes(ram[a & 0xFFFF:(a & 0xFFFF) + 4], 'big')
    cam = (w(0xFF7DF6), w(0xFF7DF8) + YOFF)
    out = []
    for slot in range(32):
        base = 0xFF7E40 + slot * 66
        kind = ram[base & 0xFFFF]
        if kind == 0:
            continue
        out.append({'slot': slot, 'kind': kind, 'x': w(base + 2), 'y': w(base + 4), 'script': l(base + 0x20),
                    'frame_ptr': l(base + 0x14), 'hp': ram[(base + 1) & 0xFFFF], 'flags3c': ram[(base + 0x3C) & 0xFFFF]})
    return cam, out


with GenesisRun(ALADDIN, rom, 'original') as run:
    for f in sorted(frames):
        run.advance(f, [e for e in events if e['frame'] >= run.frame], lambda r: None)
        m = run.machine
        wdt, hgt, pixels = m.frame()
        im = Image.frombytes('RGB', (wdt, hgt), pixels)
        cam, objs = objects(m)
        d = ImageDraw.Draw(im)
        for o in objs:
            sx, sy = o['x'] - cam[0], o['y'] - cam[1]
            if -64 <= sx <= wdt + 64 and -64 <= sy <= hgt + 64:
                color = 'yellow' if o['slot'] == 0 else 'red'
                d.rectangle([sx - 2, sy - 2, sx + 2, sy + 2], outline=color)
                d.text((sx + 4, sy - 10), f"{o['kind']:02X}", fill=color)
                if crop and o['slot'] != 0:
                    box = (max(0, sx - 32), max(0, sy - 56), min(wdt, sx + 32), min(hgt, sy + 8))
                    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
                        continue
                    Image.frombytes('RGB', (wdt, hgt), pixels).crop(box).resize(((box[2]-box[0]) * 3, (box[3]-box[1]) * 3), Image.NEAREST).save(
                        os.path.join(out, f"crop_f{f}_s{o['slot']}_k{o['kind']:02X}_{o['script']:06X}.png"))
        im.save(os.path.join(out, f'boxes_f{f}.png'))
        records.append({'frame': f, 'camera': cam, 'objects': objs})
        print(f, 'camera', cam, 'objects', [(o['slot'], f"{o['kind']:02X}", o['x'], o['y']) for o in objs][:12], flush=True)
json.dump(records, open(os.path.join(out, 'records.json'), 'a'))
