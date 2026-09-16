"""vblank_slide: does a witnessed Gods region commute with the vertical interrupt?  A strict-original check.

    python scripts/gods/vblank_slide.py FIXTURE.state [--ticks 20] [--positions 4] [--json OUT]

The review question for any region whose census shows VBlank-pre-empted occurrences (the tracer sets
the handler aside, `pathfacts.region_only`, and the plan is checked against the region's own facts; this
tool checks the assumption behind that): run A restores the retained fixture and runs the unmodified
original through the region and on for ``--ticks`` game ticks; run B(b) first stalls the CPU b cycles
at the region's entry with a time-only ``Machine.atomic`` (no writes, no register change -- a bus
stall the machine also performs on its own during DMA and FIFO waits), so the next VBlank lands b
cycles earlier, inside the region.  ``Machine.atomic`` caps one stall at 100,000 cycles; a longer
stall is a chain of stalls re-parked at the entry gate.  Then A and B are compared at the region's
exit (every live work-RAM byte at or above the user SP except the handler-owned bytes, which are
compared separately; the dead stack residue is counted; the register file; the sound block) and at
the tick-loop head and every following tick start (the masked live RAM, the rendered frame, the
VBlank counter).  Any live difference is listed byte by byte so it can be attributed to a channel
(pad latch, 60 Hz counter, sound, palette, VDP address) or to something new.

EQUIVALENT means the handler commutes with the region on this fixture at these landings; DIFFERS names
the first difference.  It is a fixture-based experiment on the strict original: retained fixtures are
only read, nothing is written into the product.  Gods facts: the tick start ``001EC2``, the wait loop
``001EB4``, the handler ``0003DC`` and its bytes (docs/gods/research/timing-and-verification-2026-09-16.md,
timing-verification-pass-2026-09-16.md).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path as _Path

# Judge the checkout, never an installed wheel: the checkout's src wins.
sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / 'src'))
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from pathlib import Path

import pathfacts
from genesis_re.machine import Machine
from gods_sega.profile import GODS

# The tick is observed at gate-able PCs: the entry of the sprite-list flush the tick starts with (the
# first instruction of every tick, bsr'd from 001EC2) and the entry of the VBlank wait (bsr'd from
# 001EB4 at the tick's end).  The engine recognises a gate where a region starts; 001EC2 itself, the
# fall-through of the parity test, is not such a place.
TICK_START, TICK_END, VBLANK = 0x001098, 0x00052E, 0x0003DC
SOUND_BLOCK = (0xFDEA, 0xFE0C)
FT = GODS.board.frame_ticks
VBLANK_IRQ = GODS.board.vblank_offset_ticks
HANDLER_OWNED = set(range(0xEEC6, 0xEECA)) | set(range(0xF2AA, 0xF2AE)) | set(range(0xF19E, 0xF1A0)) | \
    set(range(0xEA1E, 0xEA24)) | set(range(0xF3DA, 0xF3DC)) | {0xEECC} | set(range(*SOUND_BLOCK))
_MASK = bytes(0 if i in HANDLER_OWNED else 0xFF for i in range(65536))
MAX_STALL = 100_000


def masked(ram):
    return bytes(a & b for a, b in zip(ram, _MASK))


def _sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def step_region(m, rom):
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
        steps.append({'n': n, 'pc': pc, 'tick': info['tick'], 'handler': handler_depth > 0})
        if text.startswith('rte') and handler_depth:
            handler_depth -= 1
        info, regs, n = new_info, m.registers(), n + 1
        if n > 40000:
            raise RuntimeError('region did not return')
    return steps, regs, info


def observe(m):
    regs = m.registers()
    ram = pathfacts.ram_bytes(m)
    a7 = regs['a7'] & 0xFFFF
    return {'tick': m.info['tick'], 'vblanks': m.info['vblanks'], 'counter': int.from_bytes(ram[0xEEC6:0xEECA], 'big'),
            'ram_live': _sha(masked(ram)[a7:]), 'frame': _sha(m.frame()[2]), 'a7': regs['a7'], 'ram': ram, 'regs': regs,
            'pads': ram[0xEA1E:0xEA24].hex(), 'elapsed': int.from_bytes(ram[0xF2AA:0xF2AE], 'big'), 'f19e': int.from_bytes(ram[0xF19E:0xF1A0], 'big')}


def run_gates(m, pcs, until_pc, limit_ticks):
    """Run until ``until_pc`` is reached AGAIN: a machine already parked at a gated PC is bypassed once first.

    (scripts/research/vblank_slide.py did not do this, so every 'tick_start' observation after the
    first was the same parked instant re-observed: its 20-tick future was one tick start.)
    """
    m.gates(list(pcs))
    if m.info['pc'] in pcs:
        m.gate(m.info['pc'], bypass_once=True)
    while True:
        reason = m.run(target=m.info['tick'] + limit_ticks)
        if reason != 'gate':
            raise RuntimeError('ran %d ticks without reaching %06X' % (limit_ticks, until_pc))
        pc = m.info['pc']
        if pc == until_pc:
            return
        m.gate(pc, bypass_once=True)


def stall(m, entry_pc, total):
    """Chain time-only atomics at the parked entry gate until ``total`` cycles are charged; return the accepted amount."""
    done = 0
    while done < total:
        piece = min(MAX_STALL, total - done)
        m.gates([entry_pc])
        if m.run(instructions=1) != 'gate':
            raise RuntimeError('lost the entry gate')
        ok = m.atomic(target=m.info['tick'] + 10 * FT, cycles=piece, instructions=1, last_pc=entry_pc, writes=[], registers={})
        if not ok:
            return done, False
        done += piece
    return done, True


def one_run(state, rom, burn, ticks):
    with Machine(rom, GODS) as m:
        m.restore(state)
        m.audio_policy('discard')
        entry_pc = m.info['pc']
        result = {'burn': burn, 'burn_accepted': None}
        if burn:
            done, ok = stall(m, entry_pc, burn)
            result['burn_accepted'] = ok
            result['burn_done'] = done
            if not ok:
                return result
        m.gates([])
        steps, exit_regs, exit_info = step_region(m, rom)
        ram = pathfacts.ram_bytes(m)
        a7 = exit_regs['a7'] & 0xFFFF
        vb = [s for s in steps if s['handler']]
        result.update({'steps': len(steps), 'region_steps': sum(1 for s in steps if not s['handler']), 'handler_steps': len(vb),
                       'handler_first_step': vb[0]['n'] if vb else None, 'entry_tick': steps[0]['tick'], 'exit_tick': exit_info['tick'],
                       'exit_regs': exit_regs, 'exit_ram': ram, 'exit_a7': a7, 'exit_sound_block': ram[SOUND_BLOCK[0]:SOUND_BLOCK[1]].hex(),
                       'step_ticks': [(s['pc'], s['tick']) for s in steps if not s['handler']]})
        obs = []
        try:
            run_gates(m, [TICK_END], TICK_END, 4 * FT)
            obs.append(('tick_end', observe(m)))
            for _ in range(ticks):
                run_gates(m, [TICK_START], TICK_START, 4 * FT)
                obs.append(('tick_start', observe(m)))
        except RuntimeError as error:
            # The tick loop stopped (a transition, a screen): the future is as long as gameplay lasted.
            result['future_cut'] = str(error)
        result['observations'] = obs
        return result


def diff_ram(a, b, a7):
    live = [i for i in range(a7, 65536) if a[i] != b[i] and i not in HANDLER_OWNED]
    dead = [i for i in range(0, a7) if a[i] != b[i]]
    return live, dead


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('fixture')
    p.add_argument('--ticks', type=int, default=20)
    p.add_argument('--positions', type=int, default=4)
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    rom = GODS.read_rom()
    state = Path(a.fixture).read_bytes()
    A = one_run(state, rom, 0, a.ticks)
    entry_pc = A['step_ticks'][0][0]
    entry_tick = A['entry_tick']
    vblank_at = (entry_tick // FT) * FT + VBLANK_IRQ
    while vblank_at <= entry_tick:
        vblank_at += FT
    cycles_to_vblank = (vblank_at - entry_tick) // 7
    print('fixture %s: region %06X, %d region steps (+%d handler steps%s), entry at frame offset %.4f; VBlank IRQ ~%d CPU cycles after the entry (%s)' % (
        Path(a.fixture).name, entry_pc, A['region_steps'], A['handler_steps'],
        ', handler entered at step %d' % A['handler_first_step'] if A['handler_steps'] else '', entry_tick % FT / FT, cycles_to_vblank,
        'inside the region in run A' if A['handler_steps'] else 'after the exit in run A'))
    region_ticks = [t - entry_tick for _, t in A['step_ticks']]
    span = region_ticks[-1]
    targets = sorted({cycles_to_vblank - (span * k // (a.positions + 1)) // 7 for k in range(1, a.positions + 1)} | {cycles_to_vblank - d for d in (12, 40, 160)})
    targets = [t for t in targets if 0 < t < cycles_to_vblank]
    report = {'fixture': a.fixture, 'region': '%06X' % entry_pc, 'entry_offset': entry_tick % FT / FT, 'cycles_to_vblank': cycles_to_vblank,
              'A': {k: v for k, v in A.items() if k not in ('exit_ram', 'observations', 'exit_regs', 'step_ticks')}, 'runs': []}
    for burn in targets:
        B = one_run(state, rom, burn, a.ticks)
        if not B['burn_accepted']:
            print('  burn %6d cycles: refused by the engine after %d (the stall would reach the VBlank)' % (burn, B.get('burn_done', 0)))
            report['runs'].append({'burn': burn, 'accepted': False, 'done': B.get('burn_done', 0)})
            continue
        landing = B['handler_first_step']
        live, dead = diff_ram(A['exit_ram'], B['exit_ram'], min(A['exit_a7'], B['exit_a7']))
        regs_diff = {k: (A['exit_regs'][k], B['exit_regs'][k]) for k in A['exit_regs'] if A['exit_regs'][k] != B['exit_regs'][k]}
        sound_same = A['exit_sound_block'] == B['exit_sound_block']
        future_diffs, counter_diffs, timer_diffs = [], [], []
        for i, ((ka, oa), (kb, ob)) in enumerate(zip(A['observations'], B['observations'])):
            if oa['counter'] != ob['counter']:
                counter_diffs.append((i, ka, oa['counter'], ob['counter']))
            if (oa['elapsed'], oa['f19e'], oa['pads']) != (ob['elapsed'], ob['f19e'], ob['pads']):
                timer_diffs.append((i, ka, (oa['elapsed'], oa['f19e'], oa['pads']), (ob['elapsed'], ob['f19e'], ob['pads'])))
            if oa['ram_live'] != ob['ram_live'] or oa['frame'] != ob['frame']:
                l2, _ = diff_ram(oa['ram'], ob['ram'], min(oa['a7'], ob['a7']) & 0xFFFF)
                future_diffs.append({'index': i, 'kind': ka, 'ram_live_differs': oa['ram_live'] != ob['ram_live'], 'frame_differs': oa['frame'] != ob['frame'],
                                     'live_addresses': ['%06X %02X/%02X' % (0xFF0000 + x, oa['ram'][x], ob['ram'][x]) for x in l2[:24]], 'live_count': len(l2)})
        first = future_diffs[0] if future_diffs else None
        if A.get('future_cut') or B.get('future_cut'):
            print('      note: the tick loop stopped inside the window (%s); %d observations compared' % (
                A.get('future_cut') or B.get('future_cut'), min(len(A['observations']), len(B['observations']))))
        where = ('handler at region step %d of %d' % (landing, B['region_steps'])) if landing is not None else 'handler after the exit'
        tick_start_counters = [c for c in counter_diffs if c[1] == 'tick_start']
        tick_start_diffs = [fd for fd in future_diffs if fd['kind'] == 'tick_start']
        tick_end_only = bool(future_diffs) and not tick_start_diffs
        # the verdict is taken at tick starts: the tick-end observation legitimately differs in the handler's own
        # bytes (and in whatever the tick consumed from them) when the odd VBlank was moved to the tick's inside
        verdict = 'EQUIVALENT' if not live and not regs_diff and not tick_start_diffs and not tick_start_counters else 'DIFFERS'
        print('  burn %6d cycles: %-36s exit: %d live RAM bytes differ, %d dead-stack bytes, regs %s, sound block %s; future %d obs %s -> %s' % (
            burn, where, len(live), len(dead), 'equal' if not regs_diff else sorted(regs_diff), 'same' if sound_same else 'DIFFERENT',
            len(B['observations']), 'all equal' if first is None else '%d differ, first at %s #%d (%s)' % (
                len(future_diffs), first['kind'], first['index'], ', '.join(first['live_addresses'][:6])), verdict))
        if counter_diffs:
            print('      VBlank counter differs at %d observation(s): %s' % (len(counter_diffs), ', '.join('%s#%d %d/%d' % (k, i, x, y) for i, k, x, y in counter_diffs[:4])))
        if timer_diffs:
            print('      60 Hz state (elapsed, countdown, pads) differs at %d observation(s): first %s' % (len(timer_diffs), timer_diffs[0]))
        if live:
            print('      live exit differences: ' + ', '.join('%06X %02X/%02X' % (0xFF0000 + x, A['exit_ram'][x], B['exit_ram'][x]) for x in live[:16]))
        report['runs'].append({'burn': burn, 'accepted': True, 'landing_step': landing, 'region_steps': B['region_steps'],
                               'exit_live_diff': ['%06X' % (0xFF0000 + x) for x in live], 'exit_dead_diff_count': len(dead), 'exit_regs_diff': regs_diff,
                               'sound_block_same': sound_same, 'first_future_diff': first, 'future_diff_count': len(future_diffs),
                               'first_tick_start_diff': tick_start_diffs[0] if tick_start_diffs else None, 'tick_end_only': tick_end_only,
                               'counter_diffs': counter_diffs, 'timer_diffs': timer_diffs[:4], 'verdict': verdict})
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(report, indent=1, default=str))
        print('wrote', a.json)


if __name__ == '__main__':
    main()
