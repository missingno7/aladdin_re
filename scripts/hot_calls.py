"""hot_calls: which subroutines a window of a recorded history enters, by single-stepping the ORIGINAL.

    python scripts/hot_calls.py --game GAME [--node main] --from FRAME --to FRAME [--top 40] [--json FILE]

For every JSR/BSR executed in the window the callee is recorded; its return
(RTS at the same depth) closes the activation, giving per-callee counts,
minimum/maximum/mean instruction lengths and whether any activation left the
window without returning.  Entries whose activations touch only work RAM and
ROM are the bounded candidates a recovery loop starts with; that finer fact
comes from the tracer (``factcheck.py facts``) on a state parked at the entry.

This is discovery, not evidence: it reads the machine, changes nothing, and
its counts are a property of this window of this history.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from genesis_re.games import game as select_game
from genesis_re.history import HistoryStore
from genesis_re.history_runtime import GenesisRun


def _opcode(rom, pc):
    return int.from_bytes(rom[pc:pc + 2], 'big') if pc + 2 <= len(rom) else 0


def census(game, node='main', *, start, end, history=None):
    store = HistoryStore(game.history_path() if history is None else history, game.history_root)
    path = store.flatten(store.resolve(node))
    if not 0 <= start < end <= path['end_frame']:
        raise ValueError('window must lie inside the history')
    rom = game.read_rom()
    calls = defaultdict(lambda: {'count': 0, 'min': None, 'max': 0, 'total': 0, 'unreturned': 0, 'callers': defaultdict(int)})
    stack = []
    steps = 0
    with GenesisRun(game, rom) as run:
        run.advance(start, path['events'])
        events = [e for e in path['events'] if e['frame'] >= start]
        changes = {e['frame']: e['buttons'] for e in events}
        m = run.machine
        m.gates([])
        started = time.perf_counter()
        for frame in range(start, end):
            buttons = changes.get(frame, run.buttons)
            if buttons != run.buttons:
                m.pad(buttons); run.buttons = buttons
            target = (frame + 1) * game.board.frame_ticks
            info = m.info
            while info['tick'] < target:
                pc, count = info['pc'], info['m68k_instructions']
                op = _opcode(rom, pc)
                is_call = (op & 0xFFC0) == 0x4E80 or (op & 0xFF00) == 0x6100
                is_rts = op == 0x4E75
                m.run(instructions=1)
                info = m.info
                steps += 1
                if info['m68k_instructions'] != count + 1:
                    continue        # an exception entry, not this instruction
                if is_call:
                    stack.append((info['pc'], info['m68k_instructions'], pc))
                elif is_rts and stack:
                    callee, entered, caller = stack.pop()
                    entry = calls[callee]
                    length = info['m68k_instructions'] - entered
                    entry['count'] += 1; entry['total'] += length
                    entry['min'] = length if entry['min'] is None else min(entry['min'], length)
                    entry['max'] = max(entry['max'], length)
                    entry['callers'][f'{caller:06X}'] += 1
            run.frame = frame + 1
            m.audio()               # drain the frame's PCM; the census keeps no audio
        elapsed = time.perf_counter() - started
    for callee, _, _ in stack:
        calls[callee]['unreturned'] += 1
    rows = []
    for callee, entry in calls.items():
        rows.append({'entry': f'{callee:06X}', 'count': entry['count'], 'unreturned': entry['unreturned'],
                     'min': entry['min'], 'max': entry['max'],
                     'mean': round(entry['total'] / entry['count'], 1) if entry['count'] else None,
                     'callers': dict(sorted(entry['callers'].items(), key=lambda kv: -kv[1])[:6])})
    rows.sort(key=lambda r: -r['count'])
    return {'game': game.id, 'history_id': path['history_id'], 'window': [start, end], 'instructions': steps,
            'seconds': round(elapsed, 1), 'entries': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--game', required=True)
    parser.add_argument('--node', default='main')
    parser.add_argument('--history', default=None)
    parser.add_argument('--from', dest='start', type=int, required=True)
    parser.add_argument('--to', dest='end', type=int, required=True)
    parser.add_argument('--top', type=int, default=40)
    parser.add_argument('--json', default=None)
    args = parser.parse_args(argv)
    report = census(select_game(args.game), args.node, start=args.start, end=args.end, history=args.history)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=1), encoding='utf-8')
    print('%s frames %d..%d: %d instructions in %.1f s, %d callees' % (
        report['history_id'][:12], args.start, args.end, report['instructions'], report['seconds'], len(report['entries'])))
    print('%-8s %7s %5s %5s %7s %s' % ('entry', 'calls', 'min', 'max', 'mean', 'callers'))
    for row in report['entries'][:args.top]:
        print('%-8s %7d %5s %5d %7s %s%s' % (row['entry'], row['count'], row['min'], row['max'], row['mean'],
                                            ' '.join(row['callers']), '  (unreturned %d)' % row['unreturned'] if row['unreturned'] else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
