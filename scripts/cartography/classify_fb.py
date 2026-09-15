"""Classify saved fallback snapshots by the record/global facts the planners branch on."""
import collections, json, os, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'src'))
sys.path.insert(0, 'D:/Prog/aladdin_re/scripts')
os.environ.setdefault('ALADDIN_NATIVE_LIBRARY', 'D:/Prog/aladdin_re/build/libaladdin_native.dll')
from aladdin_sega.machine import Machine
from aladdin_sega.profile import read_rom
from aladdin_sega.game.objects.contact import contact_route, contact_sibling_route

fb = 'D:/Prog/aladdin_re/artifacts/grinder/scratch/fb'
index = json.load(open(os.path.join(fb, 'index.json')))
want = sys.argv[1] if len(sys.argv) > 1 else ''
rom = read_rom()
rows = []
with Machine(rom) as m:
    for item in index:
        if want and want not in item['name']:
            continue
        m.restore(open(os.path.join(fb, item['name'] + '.state'), 'rb').read())
        regs = m.registers()
        read = lambda a, n: int.from_bytes(m.peek_ram(a & 0xFFFF, n), 'big')
        rec = regs['a1'] & 0xFFFFFF
        facts = {
            'name': item['name'], 'frame': item['frame'], 'gate': item['gate'],
            'pc': f"{regs['pc']:06X}", 'rec': f'{rec:06X}',
            'kind': read(rec, 1), 'counter': read(rec + 1, 1), 'threshold': read(rec + 2, 2),
            'bit5': (read(rec + 0x3C, 1) >> 5) & 1, 'flags3c': read(rec + 0x3C, 1),
            'dir': read(0xFF7E49, 1), 'player': read(0xFF7E02, 2),
            'd8': read(0xFFF0D8, 1), 'sound': read(0xFFF57D, 1), 'finish': read(0xFF7E21, 1),
            'f173': read(0xFFF173, 1), 'c1': read(0xFFF0C1, 1), 'be': read(0xFFF0BE, 1),
            'cc': read(0xFFF0CC, 1), 'route': contact_route(read),
            'sib': contact_sibling_route(read, rec) if rec >= 0xFF0000 else None,
        }
        rows.append(facts)
keys = ('kind', 'dir', 'bit5', 'd8', 'sound', 'finish', 'counter', 'route', 'sib')
groups = collections.Counter()
for r in rows:
    r['pos_fail'] = (r['player'] >= r['threshold']) if not r['dir'] else (r['player'] < r['threshold'])
    groups[tuple((k, str(r[k])) for k in keys) + (('pos_fail', r['pos_fail']),)] += 1
for g, n in groups.most_common():
    print(n, dict(g))
json.dump(rows, open(os.path.join(fb, 'classified.json'), 'w'), indent=1)
