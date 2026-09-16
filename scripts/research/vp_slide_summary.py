"""vp_slide_summary: classify every vp_slide run of a batch directory by what (if anything) differed.

    python scripts/research/vp_slide_summary.py artifacts/gods/research/slide-vp-all

Classes per accepted burn:
  EQUIVALENT        exit RAM/registers equal, every tick-start observation (masked live RAM, frame, VBlank counter) equal
  DROP              tick starts equal in RAM but the VBlank counter is +2 from the first tick start: the stall pushed the
                    tick's end past the even VBlank (a dropped tick; a property of the stall, not of the region)
  PAD               the moved odd VBlank sampled a changed pad inside the tick (tick-end pads differ) and the tick-start RAM
                    differs (the tick consumed the new sample one tick early: the pad-latch channel)
  OTHER             anything else -- to be examined by hand
"""
import json
import sys
from collections import Counter
from pathlib import Path


def classify(r):
    if r['verdict'] == 'EQUIVALENT':
        return 'EQUIVALENT'
    ts_counter = [c for c in r['counter_diffs'] if c[1] == 'tick_start']
    ts_diff = r.get('first_tick_start_diff')
    if ts_counter and not ts_diff and not r['exit_live_diff'] and not r['exit_regs_diff'] and all(c[3] - c[2] == 2 for c in ts_counter):
        return 'DROP'
    te = [t for t in r['timer_diffs'] if t[1] == 'tick_end']
    pads_changed = any(t[2][2] != t[3][2] for t in te)
    if pads_changed and not r['exit_live_diff'] and not r['exit_regs_diff'] and not ts_counter:
        return 'PAD'
    return 'OTHER'


def main(d):
    d = Path(d)
    per_region = {}
    rows = []
    for f in sorted(d.glob('census-*.json')):
        rep = json.loads(f.read_text())
        runs = [r for r in rep['runs'] if r.get('accepted')]
        classes = Counter(classify(r) for r in runs)
        inside = sorted({r['landing_step'] for r in runs if r['landing_step'] is not None}, reverse=True)
        region = rep['region']
        per_region.setdefault(region, Counter()).update(classes)
        per_region[region]['fixtures'] += 1
        per_region[region]['landings_inside'] += len(inside)
        rows.append((region, f.stem, rep['A']['region_steps'], round(rep['entry_offset'], 3), inside, dict(classes),
                     [r['first_tick_start_diff']['live_addresses'][:4] for r in runs if classify(r) == 'OTHER' and r['first_tick_start_diff']]))
    for r in rows:
        print('%s %-52s steps %4d entry@%.3f landings %-28s %s %s' % (r[0], r[1], r[2], r[3], r[4], r[5], r[6] if r[6] else ''))
    print()
    print('%-8s %8s %9s %10s %6s %5s %6s' % ('region', 'fixtures', 'landings', 'EQUIVALENT', 'DROP', 'PAD', 'OTHER'))
    for region, c in sorted(per_region.items()):
        print('%-8s %8d %9d %10d %6d %5d %6d' % (region, c['fixtures'], c['landings_inside'], c['EQUIVALENT'], c['DROP'], c['PAD'], c['OTHER']))
    total = Counter()
    for c in per_region.values():
        total.update(c)
    print('total fixtures %d, landings inside a region %d, burns: EQUIVALENT %d, DROP %d, PAD %d, OTHER %d' % (
        total['fixtures'], total['landings_inside'], total['EQUIVALENT'], total['DROP'], total['PAD'], total['OTHER']))
    (d / 'classified.json').write_text(json.dumps({'rows': rows, 'per_region': {k: dict(v) for k, v in per_region.items()}}, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
