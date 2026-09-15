"""factcheck: machine facts and plan checks for one recovery branch.

Every number a boundary planner needs (cycles, instructions, last PC, stack
slots, RAM residue, register and CCR results) is derived here by
single-stepping the ORIGINAL machine (``pathfacts``).  Nothing is counted by
hand.  PYTHONPATH must include src, scripts and tests.

  python scripts/factcheck.py facts FIXTURE.state [--park PC] [--stop PC] [--path]
      Trace the original from the fixture (after running it to --park PC)
      until it returns to its caller, or reaches --stop, and print the fact
      report: instructions, cycles, last_pc, stack delta, changed registers,
      CCR residue, RAM writes, calls/returns and (with --path) every
      instruction.  A JSR into 1E58B8/1E58F4/1E589A is a NATIVE sound
      segment; --path shows it and the resume point after it.

  python scripts/factcheck.py check FIXTURE.state MODULE:FUNCTION [--park PC] [--stop PC]
                                    [--vary ADDR[.b|.w|.l]=v1,v2,...]...
      Park the machine, call the boundary planner MODULE:FUNCTION(machine,
      registers), trace the original over the same span and report every
      fact the plan gets wrong.  A planner returning a SoundSeam is checked
      through its prefix up to the native sound entry.  With --vary the same
      check runs on every combination of poked RAM values (this is what
      catches fixture-specific constants).  Exit 0 MATCH, 1 MISMATCH,
      2 DECLINED (UnsupportedCandidate; the original facts are printed).

  python scripts/factcheck.py branches FIXTURE.state [--park PC] [--stop PC] --vary ADDR=V1,V2,...
      Re-trace after poking RAM bytes, grouping variations by the executed
      path, to see which branch each input takes and that (instructions,
      cycles, last_pc) is constant within a branch.

  python scripts/factcheck.py segments FIXTURE.state [--park PC] [--stop PC]
      Print the PYTHON/NATIVE segment split of the traced region: the
      prefix a seam may own, the native sound call, and the resumed suffix,
      each with its cycles, instructions, writes and register file.

Only one native machine may be live per process; every command here opens
and closes its own.
"""
import argparse
import importlib
import itertools
import sys
from pathlib import Path as _Path

# Judge the checkout, never an installed wheel: the checkout's src wins.
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))

import pathfacts
from genesis_re.games import game as select_game
from genesis_re.machine import Machine


def parse_pc(text):
    return int(text, 16) if text else None


def load_planner(spec):
    module_name, function_name = spec.split(':')
    module = importlib.import_module(module_name)
    return getattr(module, function_name)


def parse_vary(specs):
    """--vary ADDR=v1,v2 pokes one byte; ADDR.w=v1,v2 a big-endian word; ADDR.l a long."""
    variations = []
    for spec in specs or []:
        address, values = spec.split('=')
        width = 1
        if '.' in address:
            address, suffix = address.split('.')
            width = {'b': 1, 'w': 2, 'l': 4}[suffix.lower()]
        base = int(address, 16)
        options = []
        for v in values.split(','):
            value = int(v, 0)
            options.append(tuple((base + i, (value >> (8 * (width - 1 - i))) & 0xFF) for i in range(width)))
        variations.append(options)
    return variations


def poke(game, state, writes):
    """Return a snapshot with the given RAM bytes changed (machine parked as-is)."""
    if not writes:
        return state
    with Machine(game.read_rom(), game) as m:
        m.restore(state)
        pc = m.info['pc']
        m.gates([pc])
        assert m.run(instructions=1) == 'gate'
        assert m.atomic(target=m.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=pc,
                        writes=list(writes), registers=m.registers())
        return m.snapshot()


def _combinations(specs):
    combos = list(itertools.product(*parse_vary(specs))) if specs else [()]
    return [[pair for group in combo for pair in group] for combo in combos]


def _label(writes):
    return ' '.join('%06X=%02X' % (a, v) for a, v in writes) or 'unchanged'


def _load(args):
    state = open(args.fixture, 'rb').read()
    if args.park is not None:
        state = pathfacts.park(state, args.park, game=args.game)
    return state


def command_facts(args):
    facts = pathfacts.trace(_load(args), game=args.game, stop_pc=args.stop, max_instructions=args.max)
    print(pathfacts.report(facts, path=args.path))
    return 0


def command_segments(args):
    facts = pathfacts.trace(_load(args), game=args.game, stop_pc=args.stop, max_instructions=args.max)
    print(pathfacts.report_segments(pathfacts.split_at_native(facts), facts['natives']))
    return 0


def command_check(args):
    state = _load(args)
    worst = 0
    for writes in _combinations(args.vary):
        if args.vary:
            print('--- variation %s ---' % _label(writes))
        worst = max(worst, _check_state(poke(args.game, state, writes), args))
    return worst


def _check_state(state, args):
    planner = load_planner(args.planner)
    from aladdin_sega.boundary import UnsupportedCandidate, SoundSeam
    declined = plan = None
    seam = False
    with Machine(args.game.read_rom(), args.game) as m:
        m.restore(state)
        regs = m.registers()
        try:
            result = planner(m, regs)
        except UnsupportedCandidate as error:
            declined = str(error)
        else:
            seam = isinstance(result, SoundSeam)
            plan = result.prefix if seam else result
    # Only one native machine may be live per process: trace after the planner's machine is closed.
    stop = args.stop
    if stop is None and seam:
        stop = plan.registers.get('pc')
        print('seam: checking the prefix up to native entry %06X; the suffix planner %s is not checked here'
              % (stop, getattr(result.suffix, '__name__', result.suffix)))
    facts = pathfacts.trace(state, game=args.game, stop_pc=stop, max_instructions=args.max)
    if declined is not None:
        print('DECLINED: %s' % declined)
        print('original facts for the declined state:')
        print(pathfacts.report(facts, path=False))
        return 2
    if stop is None and plan.registers.get('pc') != facts['exit_pc']:
        print('NOTE: plan continues at %06X but the original returns to its caller at %06X;'
              ' pass --stop %06X to compare the plan span' % (
                  plan.registers.get('pc', 0), facts['exit_pc'], plan.registers.get('pc', 0)))
    problems = pathfacts.check_plan(plan, facts, regs)
    notes = [p for p in problems if p.startswith('note')]
    problems = [p for p in problems if not p.startswith('note')]
    print('plan: cycles %d instructions %d last_pc %06X writes %d registers %s' % (
        plan.cycles, plan.instructions, plan.last_pc, len(plan.writes), sorted(plan.registers)))
    print('original: cycles %d instructions %d last_pc %06X exit %06X' % (
        facts['cycles'], facts['instructions'], facts['last_pc'], facts['exit_pc']))
    for note in notes:
        print(note)
    if problems:
        print('MISMATCH:')
        for p in problems:
            print('  ' + p)
        return 1
    print('MATCH')
    return 0


def command_branches(args):
    state = _load(args)
    groups = {}
    for writes in _combinations(args.vary):
        facts = pathfacts.trace(poke(args.game, state, writes), game=args.game, stop_pc=args.stop, max_instructions=args.max)
        pcs = tuple(s['pc'] for s in facts['steps'])
        key = (facts['instructions'], facts['cycles'], facts['last_pc'], facts['exit_pc'])
        groups.setdefault(pcs, []).append((writes, key, facts))
    print('%d variations, %d distinct executed paths' % (sum(len(r) for r in groups.values()), len(groups)))
    for index, (pcs, rows) in enumerate(groups.items()):
        instructions, cycles, last_pc, exit_pc = rows[0][1]
        writes = rows[0][2]['ram_writes_final']
        print('path %d: %d instructions, %d cycles, last_pc %06X, exit %06X, writes %s' % (
            index, instructions, cycles, last_pc, exit_pc, ' '.join('%06X' % a for a in writes) or 'none'))
        print('  branch points: ' + ' '.join('%06X%s' % (s['pc'], '+' if s['taken'] else '-')
                                             for s in rows[0][2]['steps'] if s['taken'] is not None))
        print('  variations: ' + '; '.join(_label(w) for w, _, _ in rows))
        constant = all(row[1] == rows[0][1] for row in rows)
        if not constant:
            print('  WARNING: cost differs within this path: %s' % sorted({row[1] for row in rows}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('facts', 'check', 'branches', 'segments'):
        p = sub.add_parser(name)
        p.add_argument('fixture')
        if name == 'check':
            p.add_argument('planner', help='module:function, e.g. aladdin_sega.boundary:begin_contact_family_type55')
        p.add_argument('--game', type=select_game, required=True)
        p.add_argument('--park', type=parse_pc, default=None)
        p.add_argument('--stop', type=parse_pc, default=None)
        p.add_argument('--max', type=int, default=20000)
        if name == 'facts':
            p.add_argument('--path', action='store_true')
        if name in ('branches', 'check'):
            p.add_argument('--vary', action='append')
    args = parser.parse_args(argv)
    return {'facts': command_facts, 'check': command_check, 'branches': command_branches,
            'segments': command_segments}[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
