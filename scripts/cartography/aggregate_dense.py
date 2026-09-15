"""Aggregate dense frame samples: routine totals, provenance per RAM address / object field, frame modes."""
import json, glob, os, sys, collections, bisect
d = sys.argv[1] if len(sys.argv) > 1 else 'D:/Prog/aladdin_re/artifacts/cartography/dense'
files = sorted(glob.glob(os.path.join(d, 'f*.json')), key=lambda f: int(os.path.basename(f)[1:-5]))
PLAYER, POOL, EXTRA = 0xFF7E40, 0xFF7E82, 0xFF84B2


def field(addr):
    """Map a work-RAM address to ('player'|'pool'|'extra', offset) when it lies in a record."""
    if PLAYER <= addr < POOL:
        return 'player', addr - PLAYER
    if POOL <= addr < EXTRA:
        return 'pool', (addr - POOL) % 66
    if EXTRA <= addr < EXTRA + 6 * 66:
        return 'extra', (addr - EXTRA) % 66
    return None


routine_total = collections.Counter()
routine_frames = collections.Counter()
readers = collections.defaultdict(collections.Counter)   # addr/field -> routine -> count
writers = collections.defaultdict(collections.Counter)
routine_fields = collections.defaultdict(collections.Counter)  # routine -> (field, op) -> count
modes = collections.Counter()
mode_frames = collections.defaultdict(list)
callers = collections.defaultdict(collections.Counter)
for f in files:
    s = json.load(open(f))
    frame = s['frame']
    starts = sorted({int(c['callee'], 16) for c in s['calls']})
    hist = {int(k, 16): v for k, v in s['pc_hist'].items()}
    per = collections.Counter()
    for pc, n in hist.items():
        i = bisect.bisect_right(starts, pc) - 1
        r = starts[i] if i >= 0 and pc - starts[i] < 0x2000 else None
        per[f'{r:06X}' if r is not None else 'main-loop'] += n
    for r, n in per.items():
        routine_total[r] += n; routine_frames[r] += 1
    for c in s['calls']:
        callers[c['callee']][c['caller']] += c['count']
    for r, ops in s['mem'].items():
        for o in ops:
            addr = int(o['addr'], 16)
            key = field(addr)
            target = (readers if o['op'] == 'r' else writers)
            target[f'{addr:06X}'][r] += o['count']
            if key:
                target[f'{key[0]}+{key[1]:02X}'][r] += o['count']
                routine_fields[r][(f'{key[0]}+{key[1]:02X}', o['op'])] += o['count']
    seq = tuple(s.get('root_sequence', [])[:60])
    sig = tuple(sorted(set(seq)))
    modes[sig] += 1; mode_frames[sig].append(frame)

print('samples', len(files))
print('\n== routines by total instructions (frames present)')
for r, n in routine_total.most_common(45):
    print(f'  {r:>9} {n:9d} in {routine_frames[r]:3d} samples; callers: ' + ', '.join(f'{c}x{k}' for c, k in (callers[r].most_common(3) if r in callers else [])))
print('\n== frame modes (set of main-loop callees) and where they occur')
for sig, n in modes.most_common(12):
    fr = mode_frames[sig]
    print(f'  {n:3d} samples, frames {fr[0]}..{fr[-1]} (e.g. {fr[:6]}): ' + ' '.join(sig))
if len(sys.argv) > 2:
    what = sys.argv[2:]
    for key in what:
        print(f'\n== {key}: writers', dict(writers[key].most_common(8)), ' readers', dict(readers[key].most_common(8)))
json.dump({'routine_total': routine_total, 'readers': {k: dict(v) for k, v in readers.items()},
           'writers': {k: dict(v) for k, v in writers.items()},
           'routine_fields': {r: [[f, o, n] for (f, o), n in c.most_common(60)] for r, c in routine_fields.items()},
           'modes': [{'count': n, 'frames': mode_frames[sig], 'callees': list(sig)} for sig, n in modes.most_common()]},
          open(os.path.join(d, 'aggregate.json'), 'w'))
