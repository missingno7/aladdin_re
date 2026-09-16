"""vp_census_report: summarize vp_recording_census pass-T outputs (one line per recording, plus detail).

    python scripts/research/vp_census_report.py artifacts/gods/research/census-T-*.json [--json OUT]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

EMPTY_BLOCK = lambda b: b[:36] == 'ff' * 18 and b[44:] == 'ff' * 12


def context(t):
    m = t['mode']
    if m['f3d8']:
        return 'demo'
    if m['eedf'] or t['vblanks_inside'] > 8:
        return 'pause/transition'
    if m['f210'] >= 0:
        return 'intro-script'
    return 'gameplay'


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('files', nargs='+')
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    out = {}
    for f in a.files:
        d = json.loads(Path(f).read_text())
        ticks, vbl = d['ticks'], d['vblanks']
        by_index = {t['index']: t for t in ticks}
        ctx = Counter(context(t) for t in ticks)
        gameplay = [t for t in ticks if context(t) == 'gameplay']
        odd_inside = [t for t in gameplay if t['vblanks_inside'] >= 1]
        two_inside = [t for t in gameplay if t['vblanks_inside'] >= 2]
        # dropped ticks: the next tick start is 4 VBlanks later (gameplay context, no pause)
        drops = []
        for i in range(len(ticks) - 1):
            t, u = ticks[i], ticks[i + 1]
            gap = u['start_vblanks'] - t['start_vblanks']
            if gap == 4 and context(t) == 'gameplay' and context(u) == 'gameplay':
                drops.append({'tick': t['index'], 'frame': t['frame'], 'work_frames': t.get('work_frames'), 'vblanks_inside': t['vblanks_inside'],
                              'wait_visits_before_next': u['wait_visits_before'], 'preempted': ['%06X' % x for x in t['preempted']]})
        gaps = Counter(ticks[i + 1]['start_vblanks'] - ticks[i]['start_vblanks'] for i in range(len(ticks) - 1))
        waits = Counter(t['wait_visits_before'] for t in ticks)
        changed_inside = [t for t in odd_inside if t['latch_changed_inside']]
        witness = {w['tick_index']: w for w in d['torn_witness']}
        consumed = [t for t in changed_inside if witness.get(t['index'], {}).get('latch_reads', 0) > 0]
        counter_after = [t for t in changed_inside if witness.get(t['index'], {}).get('counter_reads', 0) > 0]
        # 60 Hz counter reads after an odd VBlank inside the tick (gated sites, every tick)
        cr = [c for c in d['counter_reads'] if c['after_odd_vblank_inside'] and c['tick_index'] in by_index and context(by_index[c['tick_index']]) == 'gameplay']
        cr_ticks = sorted({c['tick_index'] for c in cr})
        cr_sites = Counter(c['pc'] for c in cr)
        # palette
        pal = d['palette_uploads']
        pal_in_tick = [u for u in pal if u['in_tick']]
        pal_in_loop = [u for u in pal if u.get('in_upload_loop')]
        vb_in_loop = Counter(v['in_upload_loop'] for v in vbl if v.get('in_upload_loop'))
        vb_in_loop_flag = [v for v in vbl if v.get('in_upload_loop') and v['eecc']]
        eecc_set_at_vblank_in_tick = [v for v in vbl if v['in_tick'] and v['eecc']]
        # sound
        xfers = d['sound_transfers']
        nonempty = [x for x in xfers if not EMPTY_BLOCK(x['block'])]
        nonempty_in_tick = [x for x in nonempty if x['in_tick']]
        work = sorted(t['work_frames'] for t in gameplay if 'work_frames' in t)
        rec = {'node': d['node'][:12], 'frames': d['frames'], 'vblanks': len(vbl), 'ticks': len(ticks), 'context': dict(ctx),
               'gameplay_ticks': len(gameplay), 'odd_vblank_inside': len(odd_inside), 'two_vblanks_inside': len(two_inside),
               'dropped_ticks': len(drops), 'drops': drops[:40], 'vblank_gaps_between_tick_starts': dict(sorted(gaps.items())),
               'wait_visits_before_tick': dict(sorted(waits.items())),
               'busy_vblanks': sum(1 for v in vbl if not v['idle']), 'busy_in_gameplay_tick': sum(1 for v in vbl if not v['idle'] and v['in_tick'] and v['tick_index'] in by_index and context(by_index[v['tick_index']]) == 'gameplay'),
               'odd_inside_and_latch_changed': len(changed_inside), 'odd_inside_latch_changed_and_read_after': len(consumed),
               'consumed_ticks': [{'tick': t['index'], 'frame': t['frame'], 'reads': [r['pc'] for r in witness[t['index']]['reads'] if r['kind'] == 'latch' and r['read']][:6],
                                   'first_read': next((r['pc'] for r in witness[t['index']]['reads'] if r['kind'] == 'latch' and r['read']), None),
                                   'preempted': '%06X' % t['preempted'][0]} for t in consumed][:60],
               'odd_inside_latch_changed_and_counter_read_after': len(counter_after),
               'counter_reads_after_odd_inside_ticks': len(cr_ticks), 'counter_reads_after_odd_inside_sites': dict(cr_sites),
               'palette_uploads': len(pal), 'palette_uploads_in_tick': len(pal_in_tick), 'palette_uploads_preempting_upload_loop': len(pal_in_loop),
               'palette_in_tick_preempted': Counter('%06X' % u['preempted_pc'] for u in pal_in_tick).most_common(12),
               'vblanks_in_upload_loops': dict(vb_in_loop), 'vblanks_in_upload_loops_with_eecc_set': len(vb_in_loop_flag),
               'vblanks_in_tick_with_eecc_set': len(eecc_set_at_vblank_in_tick),
               'eecc_set_in_tick_preempted': Counter('%06X' % v['preempted_pc'] for v in eecc_set_at_vblank_in_tick).most_common(8),
               'sound_transfers': len(xfers), 'sound_transfers_nonempty': len(nonempty), 'sound_transfers_nonempty_in_tick': len(nonempty_in_tick),
               'input_events': len(d['events']),
               'work_frames': {'min': work[0], 'median': work[len(work) // 2], 'p90': work[int(len(work) * .9)], 'max': work[-1]} if work else None,
               'seconds': d.get('seconds')}
        out[rec['node']] = rec
        print(json.dumps({k: v for k, v in rec.items() if k not in ('drops', 'consumed_ticks')}, indent=None))
        for x in drops[:12]:
            print('   drop:', x)
        for x in rec['consumed_ticks'][:12]:
            print('   consumed:', x)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
