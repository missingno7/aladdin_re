"""tick_timing_census: where Gods' VBlanks land relative to its 30 Hz game tick, on the ORIGINAL.

    python scripts/research/tick_timing_census.py --fixture artifacts/gods/evidence/main/boundary-6000.state
                                                  --frames 600 [--json OUT]

Restores a retained frame-boundary state of the main history, replays the
recorded inputs exactly as ``history_runtime.step`` does (mask at the wrap),
and gates three PCs of the original:

  0003DC  the VBlank handler's first instruction (the exception frame is
          already pushed: the pre-empted PC is at 2(a7))
  001EC2  the first instruction of a game tick's work (the parity gate at
          001EB8 has just passed)
  001EB4  the tick loop head: the tick's work is over, the game waits

For every VBlank it records the VBlank count, the pre-empted PC and whether
that PC is inside the wait loop 00052E..00053C (idle) or in game code
(busy); for every tick its start/end master ticks, the number of VBlanks it
spanned and its work length.  Research tooling: reads the machine, changes
nothing, one Machine per process.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from genesis_re.games import game as select_game
from genesis_re.history import HistoryStore
from genesis_re.machine import Machine

VBLANK, TICK_START, TICK_END = 0x0003DC, 0x001EC2, 0x001EB4
WAIT_LOOP = range(0x00052E, 0x00053E)


def run_gated(machine, target, on_gate):
    """Run to a master tick, calling on_gate at every armed PC and bypassing it once."""
    while machine.info['tick'] < target:
        if machine.run(target=target) == 'gate':
            pc = machine.info['pc']
            on_gate(pc)
            machine.gate(pc, bypass_once=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fixture', required=True)
    p.add_argument('--frames', type=int, default=600)
    p.add_argument('--game', default='gods')
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    game = select_game(a.game)
    fixture = Path(a.fixture)
    meta = json.loads(fixture.with_suffix('.json').read_text())
    frame0 = meta['frame']
    store = HistoryStore(game.history_path(), game.history_root)
    path = store.flatten(store.resolve(meta['history_id']))
    changes = {e['frame']: e['buttons'] for e in path['events']}
    buttons = 0
    for e in path['events']:
        if e['frame'] < frame0:
            buttons = e['buttons']
    FT = game.board.frame_ticks
    OBS = game.observation_offset_ticks
    vblanks, ticks = [], []
    current = {}

    with Machine(game.read_rom(), game) as m:
        m.restore(fixture.read_bytes())
        m.audio_policy('discard')   # research: PCM is not compared here
        # the loop body's top-level callees (static: every bsr/jsr target between 001EC2 and 002130)
        import pathfacts
        rom = game.read_rom()
        callees, pc = [], TICK_START
        while pc < 0x002130:
            text, size = pathfacts.disasm(rom, None, pc)
            if text.startswith(('bsr', 'jsr')) and '$' in text and '(a' not in text:
                target = int(text.split('$')[1].split('.')[0].split(',')[0].strip(), 16)
                if target not in callees:
                    callees.append(target)
            pc += size
        callee_set = set(callees)
        m.gates([VBLANK, TICK_START, TICK_END] + callees[:61])

        def on_gate(pc):
            info = m.info
            if pc == VBLANK:
                regs = m.registers()
                preempted = int.from_bytes(m.peek_ram((regs['a7'] + 2) & 0xFFFF, 4), 'big') & 0xFFFFFF
                counter = int.from_bytes(m.peek_ram(0xEEC6, 4), 'big')
                # the tick step the VBlank landed in: the last top-level callee of the loop body entered
                step = current.get('step') if current else None
                vblanks.append({'tick_step': step, 'tick': info['tick'], 'frame_offset': info['tick'] % FT / FT, 'vblanks': info['vblanks'],
                                'counter_before': counter, 'preempted_pc': preempted,
                                'idle': preempted in WAIT_LOOP, 'in_tick': bool(current)})
                if current:
                    current['vblanks_inside'] += 1
                    current['preempted'].append(preempted)
            elif pc == TICK_START:
                current.clear()
                current.update({'start_tick': info['tick'], 'start_cycles': info['m68k_cycles'],
                                'start_offset': info['tick'] % FT / FT, 'start_vblanks': info['vblanks'],
                                'counter': int.from_bytes(m.peek_ram(0xEEC6, 4), 'big'),
                                'vblanks_inside': 0, 'preempted': []})
            elif pc in callee_set:
                if current:
                    current['step'] = pc
            elif pc == TICK_END and current:
                current.update({'end_tick': info['tick'], 'end_offset': info['tick'] % FT / FT,
                                'work_cycles': info['m68k_cycles'] - current['start_cycles'],
                                'work_frames': (info['tick'] - current['start_tick']) / FT})
                ticks.append(dict(current))
                current.clear()

        for frame in range(frame0, frame0 + a.frames):
            wrap = frame * FT
            run_gated(m, wrap, on_gate)
            b = changes.get(frame, buttons)
            if b != buttons:
                m.pad(b)
                buttons = b
            run_gated(m, wrap + OBS, on_gate)
            run_gated(m, wrap + FT, on_gate)

    idle = sum(1 for v in vblanks if v['idle'])
    busy = [v for v in vblanks if not v['idle']]
    parity = Counter(v['counter_before'] & 1 for v in busy)
    print('frames %d: %d VBlanks, %d ticks' % (a.frames, len(vblanks), len(ticks)))
    print('VBlank frame offset: min %.4f max %.4f' % (min(v['frame_offset'] for v in vblanks), max(v['frame_offset'] for v in vblanks)))
    print('VBlanks pre-empting the wait loop (idle): %d; pre-empting game code (busy): %d' % (idle, len(busy)))
    print('busy VBlanks by counter parity before increment (0 = the VBlank that ends an odd count... see report): %s' % dict(parity))
    hot = Counter(v['preempted_pc'] for v in busy).most_common(25)
    print('most pre-empted busy PCs: ' + ', '.join('%06X x%d' % (pc, n) for pc, n in hot))
    steps = Counter(v['tick_step'] for v in busy)
    print('tick step (the loop body callee last entered) the busy VBlanks landed in: ' + ', '.join(
        '%s x%d' % ('%06X' % s if s else '?', n) for s, n in steps.most_common(30)))
    if ticks:
        wf = sorted(t['work_frames'] for t in ticks)
        print('tick work length in frames: min %.3f median %.3f p90 %.3f max %.3f' % (wf[0], wf[len(wf) // 2], wf[int(len(wf) * .9)], wf[-1]))
        inside = Counter(t['vblanks_inside'] for t in ticks)
        print('VBlanks landing inside a tick\'s work: %s' % dict(sorted(inside.items())))
        so = sorted(t['start_offset'] for t in ticks)
        eo = sorted(t['end_offset'] for t in ticks)
        print('tick start frame offset: min %.4f median %.4f max %.4f' % (so[0], so[len(so) // 2], so[-1]))
        print('tick end frame offset:   min %.4f median %.4f max %.4f' % (eo[0], eo[len(eo) // 2], eo[-1]))
        # is the observation instant (OBS) inside the busy window?  A tick that starts at offset s in frame f
        # and ends at offset e in frame f+1 is busy at OBS of frame f+1 when e > OBS/FT (and e < 1 wrap).
        obs = OBS / FT
        busy_at_obs = sum(1 for t in ticks if (t['end_tick'] - t['start_tick']) > 0 and
                          any(((k * FT + OBS) > t['start_tick'] and (k * FT + OBS) < t['end_tick'])
                              for k in range(t['start_tick'] // FT, t['end_tick'] // FT + 1)))
        print('ticks still working at the replay observation instant (offset %.3f): %d of %d' % (obs, busy_at_obs, len(ticks)))
        counters = Counter((t['counter'] & 1) for t in ticks)
        print('VBlank counter parity at tick start: %s' % dict(counters))
        gaps = Counter(ticks[i + 1]['start_vblanks'] - ticks[i]['start_vblanks'] for i in range(len(ticks) - 1))
        print('VBlanks between consecutive tick starts: %s' % dict(sorted(gaps.items())))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps({'fixture': str(fixture), 'frames': a.frames, 'vblanks': vblanks, 'ticks': ticks}, indent=0))
        print('wrote', a.json)


if __name__ == '__main__':
    main()
