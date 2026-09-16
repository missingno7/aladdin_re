"""vp_sound_report: the sound command block hazards, from the S1..S3 passes of vp_recording_census.

    python scripts/research/vp_sound_report.py artifacts/gods/research/census-S1-<node>.json census-S2-... census-S3-...  [more nodes]

Per recording (the three passes are merged by tick index): every gated write to a block slot with the
slot's value before it.  Classes:
  fresh              the slot was empty (FFFF) -- an ordinary request
  overwrite-same     the slot already held the same value -- the same sound requested twice before one
                     delivery: the original delivers it once; a VBlank between the two writes would have
                     delivered it twice (the hazard vp_l2_contract's 'sound' mutation demonstrates)
  overwrite-other    the slot held a different pending request -- the earlier one is lost in the original;
                     a VBlank between the two writes would have delivered both
  after-odd-vblank   the write happened after the odd VBlank had already run inside this tick (its
                     delivery moves to the even VBlank: a one-frame delivery shift only)
and, per tick, how many ticks carry more than one write to the same slot, and whether any recording
shows a VBlank between two same-slot writes (both delivered).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main(files):
    by_node = defaultdict(list)
    ticks_by_node = {}
    for f in files:
        d = json.loads(Path(f).read_text())
        by_node[d['node'][:12]].extend(d['sound_writes'])
        ticks_by_node.setdefault(d['node'][:12], {t['index']: t for t in d['ticks']})
    grand = Counter()
    for node, writes in by_node.items():
        c = Counter()
        per_tick_slot = defaultdict(list)
        for w in writes:
            empty = 'ff' * w['size']
            if not w['in_tick']:
                c['outside-tick'] += 1
                continue
            if w['old'] == empty:
                c['fresh'] += 1
            elif w['old'] == w['new']:
                c['overwrite-same'] += 1
            else:
                c['overwrite-other'] += 1
            if w['vblanks_inside_before']:
                c['after-odd-vblank'] += 1
            per_tick_slot[(w['tick_index'], w['slot'])].append(w)
        multi = {k: v for k, v in per_tick_slot.items() if len(v) > 1}
        split = sum(1 for v in multi.values() if len({w['vblanks_inside_before'] for w in v}) > 1)
        values = Counter()
        for v in multi.values():
            values[tuple(sorted({w['new'] for w in v if w['new']}))] += 1
        sites = Counter(w['pc'] for w in writes if w['in_tick'] and w['old'] != 'ff' * w['size'])
        ticks = ticks_by_node[node]
        gameplay_ticks = sum(1 for t in ticks.values() if t['mode']['f3d8'] == 0 and t['mode']['f210'] < 0 and not t['mode']['eedf'])
        print('%s: %d gated writes (%d in a tick over %d ticks, %d gameplay); classes %s' % (node, len(writes), sum(1 for w in writes if w['in_tick']), len(ticks), gameplay_ticks, dict(c)))
        print('   ticks with >1 write to the same slot: %d (a VBlank between the writes in %d of them); values: %s' % (
            len(multi), split, dict(values.most_common(8))))
        print('   overwrite sites: %s' % dict(sites.most_common(10)))
        grand.update(c)
        grand['multi'] += len(multi)
        grand['multi-split'] += split
    print('TOTAL: %s' % dict(grand))


if __name__ == '__main__':
    main(sys.argv[1:])
