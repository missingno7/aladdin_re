"""Original-only entry census using the canonical input-history runner.

    python scripts/recovery_census.py OUTPUT_DIR --entry PC [--entry PC ...]
                                      [--parent PC] [--node main] [--retain 3] [--history history]

Replays one cold input history on the ORIGINAL machine, counts how often each
entry PC fires per record kind (the byte at A1), and retains the first
``retain`` entry states per (entry, kind) as fixtures.  With ``--parent`` the
state at the most recent parent entry (for example the contact tick 1ABB40)
is retained too whenever a child fires, so a parent-ownership test can replay
the real recorded scan that reached the child.

Classifiers supply game-specific facts; this helper owns replay, bounded
fixture retention and provenance.  It introduces no candidate or recovery
state format and never writes into the history.
"""
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import re
import sys
import time
from pathlib import Path as _Path

# Judge the checkout, never an installed wheel: the checkout's src wins.
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))

from aladdin_sega.artifacts import digest
from aladdin_sega.history import HistoryStore
from aladdin_sega.history_runtime import GenesisRun
from aladdin_sega.profile import read_rom


def kind_classifier(machine, pc):
    """Default classification: the record kind byte the dispatcher read at A1."""
    kind = machine.peek_ram(machine.registers()['a1'] & 0xFFFF, 1)[0]
    return {'branch': 'kind%02X' % kind, 'kind': kind}


def capture_entries(entries, classify, output, *, history='history', node='main', retain=2,
                    parent=None):
    entries = tuple(dict.fromkeys(entries))
    if not entries or not 1 <= retain <= 10:
        raise ValueError('Provide entry PCs and retain between one and ten fixtures per class')
    if parent is not None and parent in entries:
        raise ValueError('The parent entry must not also be a census entry')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'report.json').exists() or any(output.glob('*.state')):
        raise ValueError('Use an empty output directory to avoid mixing census evidence')
    store = HistoryStore(history)
    selected = store.resolve(node)
    path = store.flatten(selected)
    counts, first, parents = Counter(), defaultdict(list), defaultdict(list)

    class Probe:
        parent_state = None
        parent_frame = None

        def on_gate(self, machine, target):
            pc = machine.info['pc']
            if pc == parent:
                self.parent_state, self.parent_frame = machine.snapshot(), run.frame
                machine.gate(pc, bypass_once=True)
                machine.run(instructions=1)
                return
            if pc not in entries:
                raise RuntimeError(f'Unexpected census gate {pc:06X}')
            facts = dict(classify(machine, pc))
            branch = facts['branch']
            if not isinstance(branch, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', branch):
                raise ValueError('Branch names must be safe descriptive filename components')
            key = f'{pc:06X}:{branch}'
            counts[key] += 1
            if len(first[key]) < retain:
                name = f'{pc:06X}-{branch}-{len(first[key])}'
                raw = machine.snapshot()
                registers = machine.registers()
                facts.update(entry=pc, branch=branch, frame=run.frame,
                             history_id=path['history_id'], history_end_frame=path['end_frame'],
                             registers=registers, info=dict(machine.info),
                             state_sha256=digest(raw), fixture=name + '.state')
                (output / (name + '.state')).write_bytes(raw)
                (output / (name + '.json')).write_text(
                    json.dumps(facts, indent=2) + '\n', encoding='utf-8')
                first[key].append(facts)
            if parent is not None and self.parent_state is not None and len(parents[key]) < retain:
                name = f'parent-{pc:06X}-{branch}-{len(parents[key])}'
                record = {'parent': parent, 'child': pc, 'branch': branch,
                          'child_frame': run.frame, 'parent_frame': self.parent_frame,
                          'history_id': path['history_id'], 'history_end_frame': path['end_frame'],
                          'parent_state_sha256': digest(self.parent_state), 'fixture': name + '.state'}
                (output / (name + '.state')).write_bytes(self.parent_state)
                (output / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
                parents[key].append(record)
            machine.gate(pc, bypass_once=True)
            machine.run(instructions=1)

    started = time.monotonic()
    with GenesisRun(read_rom()) as run:
        run.candidate = Probe()
        run.machine.gates(list(entries) + ([parent] if parent is not None else []))
        run.advance(path['end_frame'], path['events'])
        terminal = run.observable()
        implementation = run.implementation
    report = {
        'status': 'CAPTURED', 'origin': 'canonical original cold input history',
        'history_id': path['history_id'], 'end_frame': path['end_frame'],
        'counts': dict(sorted(counts.items())), 'first': dict(first),
        'targets': [f'{pc:06X}' for pc in entries],
        'parent': None if parent is None else f'{parent:06X}', 'parents': dict(parents),
        'terminal': terminal, 'implementation': implementation,
        'retention_per_class': retain, 'seconds': round(time.monotonic() - started, 1),
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('output')
    parser.add_argument('--entry', action='append', required=True, help='entry PC in hex, repeatable')
    parser.add_argument('--parent', default=None, help='parent entry PC in hex whose state is retained per child')
    parser.add_argument('--node', default='main')
    parser.add_argument('--retain', type=int, default=3)
    parser.add_argument('--history', default='history')
    args = parser.parse_args(argv)
    entries = [int(value, 16) for value in args.entry]
    parent = int(args.parent, 16) if args.parent else None
    report = capture_entries(entries, kind_classifier, args.output, history=args.history,
                             node=args.node, retain=args.retain, parent=parent)
    print('census of %s (%d frames) took %s s' % (report['history_id'][:12], report['end_frame'], report['seconds']))
    for key, count in report['counts'].items():
        print('  %-16s %6d  fixtures %d%s' % (key, count, len(report['first'].get(key, [])),
              ('  parents %d' % len(report['parents'].get(key, []))) if parent is not None else ''))
    if not report['counts']:
        print('  no entry fired on this history')
    return 0


if __name__ == '__main__':
    sys.exit(main())
