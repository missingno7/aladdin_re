"""vp_compare_runs: compare two vp_tree_run outputs (or one against a history-verify reference.json) frame by frame.

    python scripts/research/vp_compare_runs.py A_DIR B_DIR_or_reference.json
"""
import json
import sys
from pathlib import Path

FIELDS = ('frame', 'buttons', 'state_sha256', 'frame_sha256', 'pcm_sha256', 'pcm_bytes', 'tick', 'pc', 'sr', 'm68k_cycles', 'm68k_instructions', 'z80_instructions', 'vblanks')


def load(path):
    path = Path(path)
    if path.is_dir():
        obs = json.loads((path / 'observations.json').read_text())
        run = json.loads((path / 'run.json').read_text())
        return obs, run.get('endpoints'), run
    data = json.loads(path.read_text())
    return data['observations'], data.get('endpoints'), data


def main(a, b):
    oa, ea, ra = load(a)
    ob, eb, rb = load(b)
    print('A: %s  offset %s candidate %s' % (a, ra.get('observation_offset_ticks', 'product default'), ra.get('candidate', ra.get('implementation', {}).get('candidate'))))
    print('B: %s  offset %s candidate %s' % (b, rb.get('observation_offset_ticks', 'product default'), rb.get('candidate', rb.get('implementation', {}).get('candidate'))))
    nodes = sorted(set(oa) | set(ob))
    total = equal = 0
    first = None
    per_field = {}
    for node in nodes:
        xa, xb = oa.get(node, []), ob.get(node, [])
        if len(xa) != len(xb):
            print('node %s: %d vs %d frames' % (node[:12], len(xa), len(xb)))
        for i in range(min(len(xa), len(xb))):
            total += 1
            diff = [f for f in FIELDS if xa[i].get(f) != xb[i].get(f)]
            if not diff:
                equal += 1
            else:
                for f in diff:
                    per_field[f] = per_field.get(f, 0) + 1
                if first is None:
                    first = (node, i, xa[i], xb[i], diff)
    print('frames compared %d, equal %d, differing %d; differing fields: %s' % (total, equal, total - equal, per_field))
    if first:
        node, i, x, y, diff = first
        print('first difference: node %s frame %s fields %s' % (node[:12], x.get('frame'), diff))
        for f in diff:
            print('   %s: %s | %s' % (f, x.get(f), y.get(f)))
    if ea and eb:
        print('endpoints equal: %s' % (ea == eb))
    return 0 if total == equal else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
