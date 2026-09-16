"""vp_l2_contract: a prototype of the report's L2 tick contract, and the mutations it must reject.

    python scripts/research/vp_l2_contract.py --fixture artifacts/gods/evidence/main/boundary-6000.state --frames 400
           --mutation none|drop|phase|sound|palette|hidden [--param N] [--json OUT]

At every tick start (001EC2) the ORIGINAL is observed as the report's L2 proposes:
  (a) the game's RAM at or above the main loop's user SP (FF0400 at the cut), hashed -- i.e. all 64 KiB
      except the supervisor stack FF0000-FF003F and the dead user-stack area FF0040-FF03FF, which is
      hashed separately (the wait loop 00052E pushes the VBlank counter there: it is timing residue);
  (b) video time (FFEEC6), the 30 Hz tick counters (FFEF4A/FFEF4C), the 60 Hz elapsed/countdown
      words (FFF2AA/FFF19E), the pad latches (FFEA1E/20/22, FFF3DA);
  (c) the ordered platform event stream of the tick just finished, each entry stamped with the VBlank
      counter value at which it happened: the sprite-table/scroll commit at 001098 (record count and
      a hash of the committed words), every tile upload block entered (site, source, count words),
      the palette upload (at which VBlank), the sound block transferred (at which VBlank, the bytes),
      and every input sample (at which VBlank, the latch values, whether the tick was running).
Run A is the untouched original with the recorded inputs.  A mutation run is the same original with
one time-only or one-byte intervention through ``Machine.atomic`` (the workbench's own admission
path; no register change outside the plan, no oracle change):
  drop     in tick --at (default 20): a chained stall at 004150 up to the odd VBlank (the engine refuses a
           stall that reaches it), then, after that VBlank has run, a second chained stall at the first
           tile-upload site up to the even VBlank; the tick's remaining work crosses it and a game tick is
           dropped (--param caps each chain, default 150,000)
  phase    a stall of --param cycles (default 5,000) at 004150 in EVERY tick: the odd VBlank lands
           earlier in every tick's logic (torn input where the tick runs long)
  sound    one stall (default 60,000) at 014084's entry in the first tick that enters it: the odd
           VBlank crosses the hazard tick's sound request
  palette  one stall (default 60,000) at 004150 in the tick whose tail will set FFEECC at 00211C (FFF210 == 0
           at the tick's start): the tail runs after the odd VBlank and the palette is committed one
           VBlank later
  hidden   one atomic write at 004150 in tick --at: FFEEF1 (the random cursor's low byte) += 2
The comparator reports, per component, the first tick at which A and the mutation differ.  Research
tooling: the product is untouched; the fixture is only read.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_common
vp_common.guard_paths()
import pathfacts
from genesis_re.history import HistoryStore
from genesis_re.machine import Machine

FT = vp_common.FT
TICK_START, TICK_END, VBLANK, HANDLER_EXIT, PALETTE_UP, SOUND_XFER = 0x001EC2, 0x001EB4, 0x0003DC, 0x0004E8, 0x000492, 0x0F4478
SPRITE_COMMIT = 0x0010C8
UPLOADS = {0x001974: '0018C8', 0x0012F4: '00126A', 0x00FD86: '00FC8E', 0x00112E: '00112E'}
STALL_GATE, HAZARD_ENTRY, PALETTE_SET = 0x004150, 0x014084, 0x00211C
MAX_STALL = 100_000


def _sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def observe(m, events):
    ram = pathfacts.ram_bytes(m)
    return {'tick': m.info['tick'], 'frame': m.info['tick'] // FT,
            'ram': _sha(ram[0x400:]), 'stack_area': _sha(ram[0x40:0x400]),
            'counter': int.from_bytes(ram[0xEEC6:0xEECA], 'big'), 'ef4a': int.from_bytes(ram[0xEF4A:0xEF4C], 'big'),
            'ef4c': int.from_bytes(ram[0xEF4C:0xEF4E], 'big'), 'f2aa': int.from_bytes(ram[0xF2AA:0xF2AE], 'big'),
            'f19e': int.from_bytes(ram[0xF19E:0xF1A0], 'big'), 'latches': ram[0xEA1E:0xEA24].hex() + ram[0xF3DA:0xF3DC].hex(),
            'frame_hash': _sha(m.frame()[2]), 'events': list(events), 'ram_bytes': ram}


def run(game, rom, fixture, frames, mutation, param, at):
    meta = json.loads(fixture.with_suffix('.json').read_text())
    frame0 = meta['frame']
    store = HistoryStore(game.history_path(), game.history_root)
    path = store.flatten(store.resolve(meta['history_id']))
    changes = {e['frame']: e['buttons'] for e in path['events']}
    buttons = 0
    for e in path['events']:
        if e['frame'] < frame0:
            buttons = e['buttons']
    gates = [TICK_START, TICK_END, VBLANK, HANDLER_EXIT, PALETTE_UP, SOUND_XFER, SPRITE_COMMIT] + list(UPLOADS)
    if mutation in ('drop', 'phase', 'hidden'):
        gates.append(STALL_GATE)
    if mutation == 'sound':
        gates.append(HAZARD_ENTRY)
    if mutation == 'palette':
        gates += [PALETTE_SET, STALL_GATE]
    ticks, events, log = [], [], {'stalls': 0, 'stall_cycles': 0, 'mutations': []}
    with Machine(rom, game) as m:
        m.restore(fixture.read_bytes())
        m.audio_policy('discard')
        m.gates(gates)
        state = {'in_tick': False, 'index': -1, 'vb_pre': None, 'done': False}

        def counter():
            return int.from_bytes(m.peek_ram(0xEEC6, 4), 'big')

        def stall(total, pc):
            done = 0
            while done < total:
                piece = min(MAX_STALL, total - done)
                if done:
                    m.gates(gates)
                    assert m.run(instructions=1) == 'gate' and m.info['pc'] == pc
                ok = m.atomic(target=m.info['tick'] + 10 * FT, cycles=piece, instructions=1, last_pc=pc, writes=[], registers={})
                if not ok:
                    break
                done += piece
            log['stalls'] += 1
            log['stall_cycles'] += done
            return done

        def on_gate(pc):
            info = m.info
            if pc == TICK_START:
                state['index'] += 1
                ticks.append(observe(m, events))
                events.clear()
                state['in_tick'] = True
            elif pc == TICK_END:
                state['in_tick'] = False
            elif pc == VBLANK:
                state['vb_pre'] = {'counter': counter(), 'in_tick': state['in_tick'], 'latches': m.peek_ram(0xEA1E, 6).hex()}
            elif pc == HANDLER_EXIT and state['vb_pre']:
                pre = state['vb_pre']
                after = m.peek_ram(0xEA1E, 6).hex()
                events.append(('input-sample', counter(), after, 'in-tick' if pre['in_tick'] else 'idle', 'changed' if after != pre['latches'] else 'same'))
                events.append(('video-after-vblank', counter(), _sha(m.frame()[2])))
                state['vb_pre'] = None
            elif pc == PALETTE_UP:
                events.append(('palette-commit', counter(), _sha(m.peek_ram(0xEA6A, 128)), 'in-tick' if state['in_tick'] else 'idle'))
            elif pc == SOUND_XFER:
                blk = m.peek_ram(0xFDEA, 0x22)
                if blk != bytes([0xFF] * 18) + blk[18:22] + bytes([0xFF] * 12):
                    events.append(('sound-transfer', counter(), blk.hex(), 'in-tick' if state['in_tick'] else 'idle'))
            elif pc == SPRITE_COMMIT:
                count = int.from_bytes(m.peek_ram(0xEBF6, 2), 'big')
                regs = m.registers()
                words = ((regs['d0'] & 0xFFFF) + 1) * 4
                events.append(('sprite-scroll-commit', counter(), count, words, _sha(m.peek_ram(0xEC00, min(words, 640)) + m.peek_ram(0xEA38, 8))))
            elif pc in UPLOADS:
                if mutation == 'drop' and state.get('drop_phase') == 1 and state['index'] == at and events and events[-1][0] == 'input-sample':
                    done = stall(param, pc)          # after the odd VBlank: up to the even one; the rest of the tick then crosses it
                    state['drop_phase'] = 2
                    state['done'] = True
                    log['mutations'].append({'tick': state['index'], 'phase': 2, 'at': '%06X' % pc, 'stall_cycles': done})
                    return 'stalled'
                regs = m.registers()
                a0 = regs['a0'] & 0xFFFFFF
                src = m.peek_ram(a0 & 0xFFFF, 64) if a0 >= 0xFF0000 else rom[a0:a0 + 64]
                events.append(('tile-upload', counter(), UPLOADS[pc], '%06X' % a0, regs['d0'] & 0xFFFF, regs['d1'] & 0xFFFF, _sha(src)))
            elif pc == STALL_GATE and state['in_tick']:
                if mutation == 'hidden' and state['index'] == at and not state['done']:
                    low = m.peek_ram(0xEEF1, 1)[0]
                    ok = m.atomic(target=info['tick'] + FT, cycles=1, instructions=1, last_pc=pc, writes=[(0xFFEEF1, (low + 2) & 0xFF)], registers={})
                    log['mutations'].append({'tick': state['index'], 'at': '%06X' % pc, 'write': 'FFEEF1 %02X->%02X' % (low, (low + 2) & 0xFF), 'accepted': ok})
                    state['done'] = True
                    return 'stalled' if ok else None
                if mutation == 'palette' and not state['done'] and int.from_bytes(m.peek_ram(0xF210, 2), 'big', signed=True) == 0:
                    done = stall(param, pc)          # this tick's tail will set FFEECC: push the tail past the odd VBlank
                    state['done'] = True
                    log['mutations'].append({'tick': state['index'], 'stall_cycles': done, 'at': '004150 (FFF210 == 0)'})
                    return 'stalled'
                if mutation == 'phase' and state['index'] >= 1:
                    stall(param, pc)
                    return 'stalled'
                if mutation == 'drop' and state['index'] == at and not state['done']:
                    done = stall(param, pc)          # up to the odd VBlank (the engine refuses a stall that reaches it)
                    state['drop_phase'] = 1
                    log['mutations'].append({'tick': state['index'], 'phase': 1, 'at': '%06X' % pc, 'stall_cycles': done})
                    return 'stalled'
            elif pc == HAZARD_ENTRY and mutation == 'sound' and not state['done']:
                done = stall(param, pc)
                state['done'] = True
                log['mutations'].append({'tick': state['index'], 'stall_cycles': done, 'at': '014084'})
                return 'stalled'
            elif pc == PALETTE_SET and mutation == 'palette':
                log['mutations'].append({'tick': state['index'], 'at': '00211C reached', 'counter': counter(), 'offset': round(info['tick'] % FT / FT, 4)})
            return None

        def run_to(target):
            while m.info['tick'] < target:
                if m.run(target=target) == 'gate':
                    pc = m.info['pc']
                    what = on_gate(pc)
                    if what is None or what == 'mutated':
                        m.gate(pc, bypass_once=True)
                    else:
                        m.gates(gates)
                        if m.run(instructions=1) == 'gate' and m.info['pc'] == pc:
                            m.gate(pc, bypass_once=True)

        for frame in range(frame0, frame0 + frames):
            wrap = frame * FT
            run_to(wrap)
            b = changes.get(frame, buttons)
            if b != buttons:
                m.pad(b)
                buttons = b
            run_to(wrap + game.observation_offset_ticks)
            run_to(wrap + FT)
    return ticks, log


def compare(A, B):
    n = min(len(A), len(B))
    first = {}
    for i in range(n):
        a, b = A[i], B[i]
        for comp in ('ram', 'stack_area', 'counter', 'ef4a', 'ef4c', 'f2aa', 'f19e', 'latches', 'frame_hash'):
            if comp not in first and a[comp] != b[comp]:
                first[comp] = {'tick': i, 'frame': b['frame'], 'A': a[comp], 'B': b[comp]}
                if comp == 'ram':
                    diff = [k for k in range(0x400, 65536) if a["ram_bytes"][k] != b["ram_bytes"][k]]
                    first[comp]['bytes'] = ['%06X %02X/%02X' % (0xFF0000 + k, a['ram_bytes'][k], b['ram_bytes'][k]) for k in diff[:16]]
                    first[comp]['count'] = len(diff)
        if 'events' not in first and a['events'] != b['events']:
            for j, (ea, eb) in enumerate(zip(a['events'], b['events'])):
                if ea != eb:
                    first['events'] = {'tick': i, 'frame': b['frame'], 'index': j, 'A': ea, 'B': eb}
                    break
            else:
                first['events'] = {'tick': i, 'frame': b['frame'], 'index': min(len(a['events']), len(b['events'])), 'A': 'len %d' % len(a['events']), 'B': 'len %d' % len(b['events'])}
    counts = {comp: sum(1 for i in range(n) if A[i][comp] != B[i][comp]) for comp in ('ram', 'counter', 'frame_hash', 'latches', 'f2aa')}
    counts['events'] = sum(1 for i in range(n) if A[i]['events'] != B[i]['events'])
    return {'ticks_compared': n, 'ticks_A': len(A), 'ticks_B': len(B), 'first_difference': first, 'differing_ticks': counts}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fixture', required=True)
    p.add_argument('--frames', type=int, default=400)
    p.add_argument('--mutation', default='none')
    p.add_argument('--param', type=int, default=None)
    p.add_argument('--at', type=int, default=20)
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    game = vp_common.gods_profile()
    rom = game.read_rom()
    fixture = Path(a.fixture)
    defaults = {'drop': 150_000, 'phase': 5_000, 'sound': 60_000, 'palette': 60_000, 'hidden': 0}
    param = a.param if a.param is not None else defaults.get(a.mutation, 0)
    A, _ = run(game, rom, fixture, a.frames, 'none', 0, a.at)
    print('run A: %d ticks over %d frames from frame %d; events per tick %.1f' % (len(A), a.frames, json.loads(fixture.with_suffix('.json').read_text())['frame'],
                                                                              sum(len(t['events']) for t in A) / max(1, len(A))))
    report = {'fixture': str(fixture), 'frames': a.frames, 'mutation': a.mutation, 'param': param, 'at': a.at, 'ticks_A': len(A)}
    if a.mutation != 'none':
        B, log = run(game, rom, fixture, a.frames, a.mutation, param, a.at)
        cmp = compare(A, B)
        report.update({'log': log, 'comparison': {k: v for k, v in cmp.items()}})
        print('mutation %s (param %d): %s' % (a.mutation, param, json.dumps(log)))
        print('  ticks compared %d (A %d, B %d); differing ticks per component: %s' % (cmp['ticks_compared'], cmp['ticks_A'], cmp['ticks_B'], cmp['differing_ticks']))
        for comp, f in sorted(cmp['first_difference'].items(), key=lambda kv: (kv[1]['tick'], kv[0])):
            print('  first %-11s difference at tick %d (frame %d): %s' % (comp, f['tick'], f['frame'], json.dumps({k: v for k, v in f.items() if k not in ('tick', 'frame')})[:300]))
    else:
        sample = A[min(30, len(A) - 1)]
        print('sample observation (tick 30): ' + json.dumps({k: v for k, v in sample.items() if k != 'ram_bytes'})[:1200])
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        for t in A:
            t.pop('ram_bytes', None)
        report['A'] = A if a.mutation == 'none' else None
        Path(a.json).write_text(json.dumps(report, indent=1, default=str))
        print('wrote', a.json)


if __name__ == '__main__':
    main()
