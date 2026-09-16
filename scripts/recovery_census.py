"""Original-only entry census using the canonical input-history runner.

    python scripts/recovery_census.py OUTPUT_DIR --game GAME --entry PC [--entry PC ...]
                                      [--parent PC] [--node main] [--history history/GAME]
                                      [--max-classes 32] [--plain] [--retain 3]

Replays one cold input history on the ORIGINAL machine and, at every
occurrence of an entry PC, single-steps the region to its caller return and
reduces it to a path signature (the executed path outside native sound
calls and its depth-zero calls).  The first occurrence of every
signature per (entry, record kind) class retains its entry state; one more
state is retained per distinct exit CCR inside a signature; with ``--parent``
the most recent parent entry state (for example the contact tick 1ABB40) is
retained next to each of them.  Occurrences that reach the frame deadline
while being stepped are classified after the replay from their entry state.
Counts are kept per signature, so frequency stays visible without members.

The output directory gets ``report.json`` (counts and retained rows per
class), ``index.json`` (one evidence row per class and signature, the record
the frontier ledger and the grinder read) and the ``*.state`` fixtures.

``--plain`` restores the older behavior: group by (entry, kind) only and
retain the first ``--retain`` occurrences per class.  Classifiers supply
game-specific facts; this helper owns replay, bounded retention and
provenance.  It introduces no candidate or recovery state format and never
writes into the history.  Stepping the original changes nothing about its
trajectory: the terminal observation is recorded so a cold run can confirm.
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
sys.path.insert(0, str(_Path(__file__).resolve().parent))

from genesis_re.artifacts import digest
from genesis_re.games import game as select_game
from genesis_re.history import HistoryStore
from genesis_re.history_runtime import GenesisRun

STEP_CAP = 12000        # instructions stepped inside one occurrence before it is classified offline
CUT_STATES = 512        # deadline-cut entry states kept in memory for offline classification
CCR_VARIANTS = 4        # extra fixtures per signature, one per distinct exit CCR


def kind_classifier(machine, pc):
    """Classification by the record kind byte the dispatcher read at A1.

    This is Aladdin's object-table convention (a record pointer in A1 whose
    first byte is the kind); another game passes its own classifier, or
    ``entry_classifier`` until it has one.
    """
    kind = machine.peek_ram(machine.registers()['a1'] & 0xFFFF, 1)[0]
    return {'branch': 'kind%02X' % kind, 'kind': kind}


def entry_classifier(machine, pc):
    """No game knowledge: every occurrence of an entry is one class."""
    return {'branch': 'entry'}


def register_classifier(spec):
    """``reg:d5.w``: one class per value of a register at the entry (a dispatcher's kind in a data register).

    No game knowledge either: the register and width name the convention
    the caller saw in the facts (Gods' condition kinds arrive in ``d5``).
    """
    name, _, width = spec.partition('.')
    if name not in [f'd{i}' for i in range(8)] + [f'a{i}' for i in range(8)] or width not in ('', 'b', 'w', 'l'):
        raise ValueError('register classifier: reg:<d0-d7|a0-a7>[.b|.w|.l]')
    mask = {'b': 0xFF, 'w': 0xFFFF, '': 0xFFFF, 'l': 0xFFFFFFFF}[width]
    digits = {0xFF: 2, 0xFFFF: 4, 0xFFFFFFFF: 8}[mask]

    def classify(machine, pc):
        value = machine.registers()[name] & mask
        return {'branch': '%s-%0*X' % (name, digits, value), 'kind': value}
    return classify


CLASSIFIERS = {'kind': kind_classifier, 'entry': entry_classifier}


def classifier(spec):
    return register_classifier(spec[4:]) if spec.startswith('reg:') else CLASSIFIERS[spec]


def _safe_branch(branch):
    if not isinstance(branch, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', branch):
        raise ValueError('Branch names must be safe descriptive filename components')
    return branch


class _Evidence:
    """Bounded retention of entry and parent states per class and signature."""

    def __init__(self, output, path, parent, max_classes):
        self.output, self.path, self.parent, self.max_classes = output, path, parent, max_classes
        self.classes = defaultdict(lambda: {'count': 0, 'cut': 0, 'unclassified': 0, 'signatures': {}})
        self.first, self.parents = defaultdict(list), defaultdict(list)
        self.mismatches = 0

    def _write(self, name, state, facts):
        (self.output / (name + '.state')).write_bytes(state)
        (self.output / (name + '.json')).write_text(json.dumps(facts, indent=2) + '\n', encoding='utf-8')

    def _retain_parent(self, name, parent_state, parent_frame, key, pc, branch, frame):
        if self.parent is None or parent_state is None or len(self.parents[key]) >= self.max_classes * (1 + CCR_VARIANTS):
            return None
        record = {'parent': self.parent, 'child': pc, 'branch': branch, 'child_frame': frame,
                  'parent_frame': parent_frame, 'history_id': self.path['history_id'],
                  'history_end_frame': self.path['end_frame'], 'child_fixture': name + '.state',
                  'parent_state_sha256': digest(parent_state), 'fixture': 'parent-' + name + '.state'}
        self._write('parent-' + name, parent_state, record)
        self.parents[key].append(record)
        return record['fixture']

    def occurrence(self, pc, branch, facts, signature, key_text, *, frame, entry_state, registers, info,
                   parent_state, parent_frame, cut=None):
        key = f'{pc:06X}:{branch}'
        cls = self.classes[key]
        cls['count'] += 1
        if cut:
            cls['cut'] += 1
        if signature is None:
            cls['unclassified'] += 1
            return
        rows = cls['signatures']
        row = rows.get(key_text)
        new_row = row is None
        if new_row:
            if len(rows) >= self.max_classes:
                cls.setdefault('overflow', 0)
                cls['overflow'] += 1
                return
            row = rows[key_text] = {'index': len(rows), 'count': 0, 'first_frame': frame, 'last_frame': frame,
                                    'frames': [], 'signature': signature, 'signature_key': key_text, 'ccr_variants': {},
                                    'fixture': None, 'parent_fixture': None, 'state_sha256': None}
        row['count'] += 1
        row['last_frame'] = frame
        if len(row['frames']) < 5:
            row['frames'].append(frame)
        ccr = '%02X' % signature['ccr']
        retain_name = None
        if new_row:
            retain_name = f'{pc:06X}-{branch}-p{row["index"]}'
        elif ccr not in row['ccr_variants'] and len(row['ccr_variants']) < CCR_VARIANTS:
            retain_name = f'{pc:06X}-{branch}-p{row["index"]}-ccr{ccr}'
        if retain_name is None:
            row['ccr_variants'].setdefault(ccr, None)
            return
        facts = dict(facts)
        facts.update(entry=pc, branch=branch, frame=frame, history_id=self.path['history_id'],
                     history_end_frame=self.path['end_frame'], registers=registers, info=info,
                     state_sha256=digest(entry_state), fixture=retain_name + '.state',
                     signature=signature, signature_key=key_text, path_class=row['index'], cut=cut)
        self._write(retain_name, entry_state, facts)
        parent_fixture = self._retain_parent(retain_name, parent_state, parent_frame, key, pc, branch, frame)
        facts['parent_fixture'] = parent_fixture
        self.first[key].append(facts)
        if new_row:
            row['fixture'], row['state_sha256'], row['parent_fixture'] = facts['fixture'], facts['state_sha256'], parent_fixture
            row['ccr_variants'][ccr] = facts['fixture']
        else:
            row['ccr_variants'][ccr] = facts['fixture']


def capture_entries(entries, classify, output, *, game, history=None, node='main', retain=2,
                    parent=None, signatures=False, max_classes=32):
    import pathfacts
    game = select_game(game) if isinstance(game, str) else game
    entries = tuple(dict.fromkeys(entries))
    if not entries or not 1 <= retain <= 10:
        raise ValueError('Provide entry PCs and retain between one and ten fixtures per class')
    if parent is not None and parent in entries:
        raise ValueError('The parent entry must not also be a census entry')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'report.json').exists() or any(output.glob('*.state')):
        raise ValueError('Use an empty output directory to avoid mixing census evidence')
    store = HistoryStore(game.history_path() if history is None else history, game.history_root)
    selected = store.resolve(node)
    path = store.flatten(selected)
    rom = game.read_rom()
    counts, first, parents = Counter(), defaultdict(list), defaultdict(list)
    evidence = _Evidence(output, path, parent, max_classes)
    pending = []  # deadline-cut occurrences classified after the replay

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
            branch = _safe_branch(facts['branch'])
            if not signatures:
                key = f'{pc:06X}:{branch}'
                counts[key] += 1
                if len(first[key]) < retain:
                    name = f'{pc:06X}-{branch}-{len(first[key])}'
                    raw = machine.snapshot()
                    facts.update(entry=pc, branch=branch, frame=run.frame,
                                 history_id=path['history_id'], history_end_frame=path['end_frame'],
                                 registers=machine.registers(), info=dict(machine.info),
                                 state_sha256=digest(raw), fixture=name + '.state')
                    evidence._write(name, raw, facts)
                    first[key].append(facts)
                if parent is not None and self.parent_state is not None and len(parents[key]) < retain:
                    name = f'parent-{pc:06X}-{branch}-{len(parents[key])}'
                    record = {'parent': parent, 'child': pc, 'branch': branch,
                              'child_frame': run.frame, 'parent_frame': self.parent_frame,
                              'history_id': path['history_id'], 'history_end_frame': path['end_frame'],
                              'parent_state_sha256': digest(self.parent_state), 'fixture': name + '.state'}
                    evidence._write(name, self.parent_state, record)
                    parents[key].append(record)
                machine.gate(pc, bypass_once=True)
                machine.run(instructions=1)
                return
            entry_state, registers, info, frame = machine.snapshot(), machine.registers(), dict(machine.info), run.frame
            tracer = pathfacts.Tracer(machine, rom, natives=game.tracer_native_entries, track_ram=False, detail=True)
            cut = None
            while not tracer.at_exit():
                if tracer.n > 0 and machine.info['tick'] >= target:
                    cut = 'deadline'
                    break
                if tracer.n >= STEP_CAP:
                    cut = 'cap'
                    break
                tracer.step()
            if cut is None:
                signature = pathfacts.path_signature(tracer.facts())
                evidence.occurrence(pc, branch, facts, signature, pathfacts.signature_key(signature), frame=frame,
                                    entry_state=entry_state, registers=registers, info=info,
                                    parent_state=self.parent_state, parent_frame=self.parent_frame)
            elif len(pending) < CUT_STATES:
                pending.append((pc, branch, facts, frame, entry_state, registers, info, self.parent_state,
                                self.parent_frame, cut))
            else:
                evidence.occurrence(pc, branch, facts, None, None, frame=frame, entry_state=entry_state,
                                    registers=registers, info=info, parent_state=None, parent_frame=None, cut=cut)

    started = time.monotonic()
    with GenesisRun(game, rom) as run:
        run.candidate = Probe()
        run.machine.gates(list(entries) + ([parent] if parent is not None else []))
        run.advance(path['end_frame'], path['events'])
        terminal = run.observable()
        implementation = run.implementation
    replay_seconds = time.monotonic() - started
    # Deadline-cut occurrences: the region continues past the frame end, so
    # classify them from their entry state now that the replay machine is closed.
    for pc, branch, facts, frame, entry_state, registers, info, parent_state, parent_frame, cut in pending:
        try:
            traced = pathfacts.trace(entry_state, game=game, max_instructions=STEP_CAP * 4, track_ram=False)
            signature = pathfacts.path_signature(traced)
            key_text = pathfacts.signature_key(signature)
        except (RuntimeError, ValueError):
            signature = key_text = None
        evidence.occurrence(pc, branch, facts, signature, key_text, frame=frame, entry_state=entry_state,
                            registers=registers, info=info, parent_state=parent_state,
                            parent_frame=parent_frame, cut=cut)
    if signatures:
        counts = Counter({key: cls['count'] for key, cls in evidence.classes.items()})
        first, parents = evidence.first, evidence.parents
        index = _build_index(evidence, path, parent, entries, pathfacts, game)
        (output / 'index.json').write_text(json.dumps(index, indent=1) + '\n', encoding='utf-8')
    report = {
        'status': 'CAPTURED', 'origin': 'canonical original cold input history',
        'history_id': path['history_id'], 'end_frame': path['end_frame'],
        'counts': dict(sorted(counts.items())), 'first': dict(first),
        'targets': [f'{pc:06X}' for pc in entries],
        'parent': None if parent is None else f'{parent:06X}', 'parents': dict(parents),
        'terminal': terminal, 'implementation': implementation,
        'retention_per_class': retain, 'signatures': signatures,
        'classes': {key: {k: v for k, v in cls.items() if k != 'signatures'}
                    | {'distinct': len(cls['signatures']),
                       'signatures': sorted(cls['signatures'].values(), key=lambda row: -row['count'])}
                    for key, cls in evidence.classes.items()} if signatures else {},
        'signature_mismatches': evidence.mismatches,
        'seconds': round(time.monotonic() - started, 1), 'replay_seconds': round(replay_seconds, 1),
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def _branch_kind(branch):
    """The classifier's value behind a branch name: ``kindNN`` (Aladdin) or ``dN-VVVV`` (a register)."""
    if branch.startswith('kind'):
        return int(branch[4:], 16)
    if re.fullmatch(r'[da][0-7]-[0-9A-F]+', branch):
        return int(branch.split('-')[1], 16)
    return None


def _build_index(evidence, path, parent, entries, pathfacts, game):
    """One evidence row per retained signature, with facets traced from the fixture.

    The offline trace of the retained state (RAM tracked, no deadline) supplies
    the record/global writes and confirms the online signature; a disagreement
    is counted, never hidden.
    """
    rows = []
    for key, cls in sorted(evidence.classes.items()):
        entry, branch = key.split(':')
        for row in sorted(cls['signatures'].values(), key=lambda r: r['index']):
            signature = row['signature']
            writes = None
            if row['fixture']:
                try:
                    traced = pathfacts.trace((evidence.output / row['fixture']).read_bytes(), game=game, max_instructions=STEP_CAP * 4)
                    offline = pathfacts.path_signature(traced)
                    writes = offline['writes']
                    if pathfacts.signature_key(offline) != pathfacts.signature_key(signature):
                        evidence.mismatches += 1
                except (RuntimeError, ValueError):
                    writes = None
            rows.append({
                'entry': entry, 'branch': branch, 'kind': _branch_kind(branch),
                'path_class': row['index'], 'signature_key': pathfacts.signature_key(signature),
                'count': row['count'], 'first_frame': row['first_frame'], 'last_frame': row['last_frame'],
                'instructions': signature['instructions'], 'cycles': signature['cycles'], 'exit': signature['exit'],
                'calls': signature['calls'], 'natives': signature['natives'], 'changed': signature['changed'],
                'writes': writes, 'ccr_variants': row['ccr_variants'],
                'fixture': row['fixture'], 'state_sha256': row['state_sha256'],
                'parent_fixture': row['parent_fixture'], 'parent': None if parent is None else f'{parent:06X}',
            })
    return {'history_id': path['history_id'], 'end_frame': path['end_frame'],
            'entries': [f'{pc:06X}' for pc in entries], 'parent': None if parent is None else f'{parent:06X}',
            'generated': time.strftime('%Y-%m-%dT%H:%M:%S'), 'signature_mismatches': evidence.mismatches,
            'rows': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('output')
    parser.add_argument('--entry', action='append', required=True, help='entry PC in hex, repeatable')
    parser.add_argument('--parent', default=None, help='parent entry PC in hex whose state is retained per fixture')
    parser.add_argument('--node', default='main')
    parser.add_argument('--retain', type=int, default=3, help='fixtures per class in --plain mode')
    parser.add_argument('--max-classes', type=int, default=32, help='signatures retained per (entry, kind) class')
    parser.add_argument('--plain', action='store_true', help='group by (entry, kind) only; retain the first --retain')
    parser.add_argument('--game', required=True)
    parser.add_argument('--history', default=None, help='history store; default history/<game>')
    parser.add_argument('--classifier', default='kind',
                        help="'kind': the record kind byte at (A1), Aladdin's object-table convention; "
                             "'entry': one class per entry, no game knowledge; "
                             "'reg:d5.w': one class per value of a register at the entry")
    args = parser.parse_args(argv)
    entries = [int(value, 16) for value in args.entry]
    parent = int(args.parent, 16) if args.parent else None
    report = capture_entries(entries, classifier(args.classifier), args.output, game=args.game, history=args.history,
                             node=args.node, retain=args.retain, parent=parent,
                             signatures=not args.plain, max_classes=args.max_classes)
    print('census of %s (%d frames) took %s s (replay %s s)' % (
        report['history_id'][:12], report['end_frame'], report['seconds'], report['replay_seconds']))
    for key, count in report['counts'].items():
        cls = report['classes'].get(key)
        extra = ''
        if cls:
            extra = '  paths %d  cut %d%s' % (cls['distinct'], cls['cut'],
                                            '  overflow %d' % cls['overflow'] if cls.get('overflow') else '')
        print('  %-16s %6d  fixtures %d%s%s' % (key, count, len(report['first'].get(key, [])),
              ('  parents %d' % len(report['parents'].get(key, []))) if parent is not None else '', extra))
    if not report['counts']:
        print('  no entry fired on this history')
    if report['signature_mismatches']:
        print('  WARNING: %d retained fixtures trace to a different signature offline' % report['signature_mismatches'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
