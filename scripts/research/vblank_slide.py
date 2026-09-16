"""vblank_slide: does the VBlank commute with a witnessed region?  Measured on the ORIGINAL machine.

    python scripts/research/vblank_slide.py FIXTURE.state [--ticks 40] [--positions 6] [--json OUT]

The fixture stands at a region's entry.  Run A is the untouched original:
single-stepped to the region's exit (the caller's return with the entry A7
restored), recording every step's PC and master tick and where the VBlank
handler ran; then run on, gate by gate, through the tick loop head (001EB4)
and ``--ticks`` further tick starts (001EC2), hashing work RAM, the rendered
frame and the VBlank counter at each.

Run B(b) is the same original after one time-only operation at the entry:
``Machine.atomic`` with no writes and no register change, charged ``b`` CPU
cycles (the CPU stalls for b cycles; devices run; nothing else changes).
The 60 Hz VBlank therefore lands b cycles earlier in the region -- at a
chosen step, or (for a fixture whose VBlank fell after the exit) inside the
region at all.  The engine refuses a stall that reaches the VBlank instant,
so the earliest landing that can be constructed is after the region's first
instruction.  Interrupts cannot be masked from Python; sliding the machine's
own clock is the only way to move the handler, and it is a legitimate
original execution (the machine stalls on real hardware too).

For each B the report compares with A: work RAM at the region's exit (live
bytes, i.e. at or above A7, and dead stack residue below A7 separately), the
register file at the exit, the sound command block FFFDEA..FFFE0B, and then
the tick-start observations (RAM hash above the main loop's A7, frame hash,
VBlank counter) for the whole window.  Equality of the future window under
every landing position is the evidence that the handler and the region
commute; the first differing tick start is where they do not.

Research tooling: one Machine per process, opened and closed per run;
retained fixtures are only read.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import pathfacts
from genesis_re.machine import Machine
from gods_sega.profile import GODS

TICK_START, TICK_END, VBLANK = 0x001EC2, 0x001EB4, 0x0003DC
SOUND_BLOCK = (0xFDEA, 0xFE0C)
FT = GODS.board.frame_ticks
# Bytes the VBlank handler itself owns (its counters, its pad latches, the palette-dirty flag and the sound
# command block it consumes).  They legitimately differ between two observations taken on different sides of
# a VBlank; they are compared separately from the game's own state.
HANDLER_OWNED = set(range(0xEEC6, 0xEECA)) | set(range(0xF2AA, 0xF2AE)) | set(range(0xF19E, 0xF1A0)) |     set(range(0xEA1E, 0xEA24)) | set(range(0xF3DA, 0xF3DC)) | {0xEECC} | set(range(*SOUND_BLOCK))
_MASK = bytes(0 if i in HANDLER_OWNED else 0xFF for i in range(65536))


def masked(ram):
    return bytes(a & b for a, b in zip(ram, _MASK))


def _sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def step_region(m, rom):
    """Single-step the original from the region's entry to its exit; return the step list and exit facts."""
    regs = m.registers()
    entry_a7 = regs['a7']
    caller_return = int.from_bytes(m.peek_ram(entry_a7 & 0xFFFF, 4), 'big') & 0xFFFFFF
    info = m.info
    steps, handler_depth, n = [], 0, 0
    while True:
        pc = info['pc']
        if n and pc == caller_return and regs['a7'] == entry_a7 + 4:
            break
        text, _ = pathfacts.disasm(rom, None, pc)
        m.run(instructions=1)
        new_info = m.info
        if new_info['m68k_instructions'] == info['m68k_instructions']:
            m.gate(pc, bypass_once=True)
            m.run(instructions=1)
            new_info = m.info
        if new_info['vblanks'] != info['vblanks']:
            handler_depth += 1
        steps.append({'n': n, 'pc': pc, 'tick': info['tick'], 'cycles': new_info['m68k_cycles'] - info['m68k_cycles'],
                      'handler': handler_depth > 0})
        if text.startswith('rte') and handler_depth:
            handler_depth -= 1
        info, regs, n = new_info, m.registers(), n + 1
        if n > 20000:
            raise RuntimeError('region did not return')
    return steps, regs, info


def observe(m):
    regs = m.registers()
    ram = pathfacts.ram_bytes(m)
    a7 = regs['a7'] & 0xFFFF
    return {'tick': m.info['tick'], 'vblanks': m.info['vblanks'], 'counter': int.from_bytes(ram[0xEEC6:0xEECA], 'big'),
            'ram_live': _sha(masked(ram)[a7:]), 'ram_all': _sha(ram), 'frame': _sha(m.frame()[2]), 'a7': regs['a7'],
            'ram': ram, 'regs': regs}


def run_gates(m, pcs, until_pc, limit_ticks):
    """Run with gates armed until until_pc is reached (bypassing other gates); return the gate hits."""
    m.gates(list(pcs))
    hits = []
    while True:
        reason = m.run(target=m.info['tick'] + limit_ticks)
        if reason != 'gate':
            raise RuntimeError('ran %d ticks without reaching %06X' % (limit_ticks, until_pc))
        pc = m.info['pc']
        hits.append(pc)
        if pc == until_pc:
            return hits
        m.gate(pc, bypass_once=True)


def one_run(state, rom, burn, ticks):
    """Run A (burn 0) or B(burn): return the exit observation and the tick-start observations."""
    with Machine(rom, GODS) as m:
        m.restore(state)
        m.audio_policy('discard')
        entry_pc = m.info['pc']
        result = {'burn': burn, 'burn_accepted': None}
        if burn:
            m.gates([entry_pc])
            assert m.run(instructions=1) == 'gate'
            accepted = m.atomic(target=m.info['tick'] + 10 * FT, cycles=burn, instructions=1, last_pc=entry_pc,
                                writes=[], registers={})
            result['burn_accepted'] = accepted
            if not accepted:
                return result
        m.gates([])
        steps, exit_regs, exit_info = step_region(m, rom)
        ram = pathfacts.ram_bytes(m)
        a7 = exit_regs['a7'] & 0xFFFF
        vb = [s for s in steps if s['handler']]
        result.update({
            'steps': len(steps), 'region_steps': sum(1 for s in steps if not s['handler']),
            'handler_steps': len(vb), 'handler_first_step': vb[0]['n'] if vb else None,
            'entry_tick': steps[0]['tick'], 'exit_tick': exit_info['tick'],
            'exit_regs': exit_regs, 'exit_ram': ram, 'exit_a7': a7,
            'exit_sound_block': ram[SOUND_BLOCK[0]:SOUND_BLOCK[1]].hex(),
            'exit_live_hash': _sha(ram[a7:]),
            'step_ticks': [(s['pc'], s['tick']) for s in steps if not s['handler']],
        })
        # to the tick loop head, then the tick starts
        m.gates([])
        obs = []
        run_gates(m, [TICK_END], TICK_END, 4 * FT)
        obs.append(('tick_end', observe(m)))
        for _ in range(ticks):
            run_gates(m, [TICK_START], TICK_START, 400 * FT)
            obs.append(('tick_start', observe(m)))
        result['observations'] = obs
        return result


def diff_ram(a, b, a7):
    live = [i for i in range(a7, 65536) if a[i] != b[i] and i not in HANDLER_OWNED]
    dead = [i for i in range(0, a7) if a[i] != b[i]]
    return live, dead


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('fixture')
    p.add_argument('--ticks', type=int, default=40)
    p.add_argument('--positions', type=int, default=6, help='how many landing positions inside the region to try')
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    rom = GODS.read_rom()
    state = Path(a.fixture).read_bytes()
    A = one_run(state, rom, 0, a.ticks)
    entry_pc = A['step_ticks'][0][0]
    print('fixture %s: region %06X, %d region steps (+%d handler steps%s), exit at tick %d' % (
        Path(a.fixture).name, entry_pc, A['region_steps'], A['handler_steps'],
        ', handler entered at step %d' % A['handler_first_step'] if A['handler_steps'] else '', A['exit_tick']))
    # where is the VBlank instant relative to the entry?  From A: either the handler's first step, or the
    # next VBlank after the exit (frame arithmetic, then confirmed by run B's own handler position).
    entry_tick = A['entry_tick']
    vblank_at = (entry_tick // FT) * FT + int(0.85555 * FT)
    while vblank_at <= entry_tick:
        vblank_at += FT
    cycles_to_vblank = (vblank_at - entry_tick) // 7
    print('VBlank instant about %d CPU cycles after the entry (%s)' % (
        cycles_to_vblank, 'inside the region in run A' if A['handler_steps'] else 'after the exit in run A'))
    # landing targets: the region's own steps at evenly spaced master-tick offsets, plus 'as early as possible'
    region_ticks = [t - entry_tick for _, t in A['step_ticks']]
    span = region_ticks[-1]
    targets = sorted({cycles_to_vblank - (span * k // (a.positions + 1)) // 7 for k in range(1, a.positions + 1)}
                     | {cycles_to_vblank - d for d in (12, 40, 80, 160, 320)})
    targets = [t for t in targets if 0 < t < cycles_to_vblank]
    report = {'fixture': a.fixture, 'region': '%06X' % entry_pc, 'A': {k: v for k, v in A.items() if k not in ('exit_ram', 'observations', 'exit_regs', 'step_ticks')},
              'A_observations': [(kind, {k: v for k, v in o.items() if k not in ('ram', 'regs')}) for kind, o in A['observations']],
              'runs': []}
    for burn in targets:
        B = one_run(state, rom, burn, a.ticks)
        if not B['burn_accepted']:
            print('  burn %6d cycles: refused by the engine (the stall would reach the VBlank)' % burn)
            report['runs'].append({'burn': burn, 'accepted': False})
            continue
        landing = B['handler_first_step']
        live, dead = diff_ram(A['exit_ram'], B['exit_ram'], min(A['exit_a7'], B['exit_a7']))
        regs_diff = {k: (A['exit_regs'][k], B['exit_regs'][k]) for k in A['exit_regs'] if A['exit_regs'][k] != B['exit_regs'][k]}
        sound_same = A['exit_sound_block'] == B['exit_sound_block']
        first_future_diff = None
        future_diffs, counter_diffs = [], []
        for i, ((ka, oa), (kb, ob)) in enumerate(zip(A['observations'], B['observations'])):
            if oa['counter'] != ob['counter']:
                counter_diffs.append((i, ka, oa['counter'], ob['counter']))
            if oa['ram_live'] != ob['ram_live'] or oa['frame'] != ob['frame']:
                l2, d2 = diff_ram(oa['ram'], ob['ram'], min(oa['a7'], ob['a7']) & 0xFFFF)
                future_diffs.append({'index': i, 'kind': ka, 'ram_live_differs': oa['ram_live'] != ob['ram_live'],
                                     'frame_differs': oa['frame'] != ob['frame'],
                                     'live_addresses': ['%06X' % (0xFF0000 + x) for x in l2[:24]], 'live_count': len(l2)})
        first_future_diff = future_diffs[0] if future_diffs else None
        where = ('handler at region step %d of %d' % (landing, B['region_steps'])) if landing is not None else 'handler after the exit'
        tick_start_counters = [c for c in counter_diffs if c[1] == 'tick_start']
        verdict = 'EQUIVALENT' if not live and not regs_diff and first_future_diff is None and not tick_start_counters else 'DIFFERS'
        print('  burn %6d cycles: %-38s exit: %d live RAM bytes differ, %d dead-stack bytes, regs %s, sound block %s; '
              'future %d observations %s -> %s' % (
                  burn, where, len(live), len(dead), 'equal' if not regs_diff else sorted(regs_diff),
                  'same' if sound_same else 'DIFFERENT', len(B['observations']),
                  'all equal' if first_future_diff is None else '%d differ, first at %s #%d (%s)' % (
                      len(future_diffs), first_future_diff['kind'], first_future_diff['index'], ', '.join(first_future_diff['live_addresses'][:8])),
                  verdict))
        if counter_diffs:
            print('      VBlank counter differs at %d observation(s): %s' % (len(counter_diffs), ', '.join(
                '%s#%d %d/%d' % (k, i, x, y) for i, k, x, y in counter_diffs[:6])))
        if live:
            print('      live exit differences: ' + ', '.join('%06X %02X/%02X' % (0xFF0000 + x, A['exit_ram'][x], B['exit_ram'][x]) for x in live[:16]))
        report['runs'].append({'burn': burn, 'accepted': True, 'landing_step': landing, 'region_steps': B['region_steps'],
                               'exit_live_diff': ['%06X' % (0xFF0000 + x) for x in live], 'exit_dead_diff_count': len(dead),
                               'exit_regs_diff': regs_diff, 'sound_block_same': sound_same,
                               'first_future_diff': first_future_diff, 'future_diff_count': len(future_diffs),
                               'counter_diffs': counter_diffs, 'verdict': verdict})
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(report, indent=1, default=str))
        print('wrote', a.json)


if __name__ == '__main__':
    main()
