"""Summarize frame samples: routines by attributed instructions, call skeleton, memory hot spots."""
import json, glob, os, sys, collections, bisect
d = 'D:/Prog/aladdin_re/artifacts/cartography/samples'
files = sorted(glob.glob(os.path.join(d, 'f*.json')), key=lambda f: int(os.path.basename(f)[1:-5]))
want = sys.argv[1:] if len(sys.argv) > 1 else None
total_routine = collections.Counter()
total_calls = collections.Counter()
for f in files:
    tag = os.path.basename(f)[:-5]
    if want and tag not in want:
        continue
    s = json.load(open(f))
    starts = sorted({int(c['callee'], 16) for c in s['calls']})
    hist = {int(k, 16): v for k, v in s['pc_hist'].items()}

    def routine(pc):
        i = bisect.bisect_right(starts, pc) - 1
        return starts[i] if i >= 0 and pc - starts[i] < 0x2000 else None
    per = collections.Counter()
    for pc, n in hist.items():
        r = routine(pc)
        per[f'{r:06X}' if r is not None else f'~{pc & 0xFFFF00:06X}'] += n
    print(f"\n=== {tag}: frames {s['frames']} steps {s['steps']}")
    print('  top routines by instructions:')
    for r, n in per.most_common(28):
        total_routine[r] += n
        print(f'    {r:>8} {n:7d}  {100.0 * n / s["steps"]:5.1f}%')
    print('  hottest call edges:')
    for c in s['calls'][:25]:
        total_calls[(c['caller'], c['callee'])] += c['count']
        print(f"    {c['caller']:>8} -> {c['callee']} x{c['count']}")
print('\n=== aggregate routines across samples')
for r, n in total_routine.most_common(40):
    print(f'    {r:>8} {n:8d}')
