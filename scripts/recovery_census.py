"""Original-only entry census using the canonical input-history runner.

Classifiers supply game-specific facts; this helper owns replay, bounded fixture
retention and provenance. It introduces no candidate or recovery state format.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from aladdin_sega.artifacts import digest
from aladdin_sega.history import HistoryStore
from aladdin_sega.history_runtime import GenesisRun
from aladdin_sega.profile import read_rom


def capture_entries(entries, classify, output, *, history='history', node='main', retain=2):
    entries = tuple(dict.fromkeys(entries))
    if not entries or not 1 <= retain <= 10:
        raise ValueError('Provide entry PCs and retain between one and ten fixtures per class')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'report.json').exists() or any(output.glob('*.state')):
        raise ValueError('Use an empty output directory to avoid mixing census evidence')
    store = HistoryStore(history)
    selected = store.resolve(node)
    path = store.flatten(selected)
    counts, first = Counter(), defaultdict(list)

    class Probe:
        def on_gate(self, machine, target):
            pc = machine.info['pc']
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
            machine.gate(pc, bypass_once=True)
            machine.run(instructions=1)

    with GenesisRun(read_rom()) as run:
        run.candidate = Probe()
        run.machine.gates(list(entries))
        run.advance(path['end_frame'], path['events'])
        terminal = run.observable()
        implementation = run.implementation
    report = {
        'status': 'CAPTURED', 'origin': 'canonical original cold input history',
        'history_id': path['history_id'], 'end_frame': path['end_frame'],
        'counts': dict(sorted(counts.items())), 'first': dict(first),
        'targets': [f'{pc:06X}' for pc in entries],
        'terminal': terminal, 'implementation': implementation,
        'retention_per_class': retain,
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
