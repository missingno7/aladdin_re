"""phase_shift_sweep: shift the VBlank phase against Gods' game tick over real recorded play and see what changes.

    python scripts/research/phase_shift_sweep.py --fixture artifacts/gods/evidence/main/boundary-6000.state
                                                 --frames 600 --burns 2000,20000,60000,100000 [--json OUT]

Run A replays the recorded inputs from the fixture on the untouched original
(the mask set at each frame wrap, as ``history_runtime.step`` does).  Run
B(b) is identical except that in every game tick, at ``--burn-gate`` (default
004150, early in the tick's work), the CPU is stalled for b cycles by a time-only ``Machine.atomic`` (no writes, no
register change).  From then on every 60 Hz VBlank lands b cycles earlier in
every tick's work than it did in A: the whole 30 Hz game runs at a shifted
phase against the machine's frame clock while the recorded input still
changes at the same wall-clock instants.

At every tick start both runs are observed: the game's RAM (above the user
stack pointer, with the handler-owned bytes masked: its counters, the pad
latches, the palette flag, the sound block), the rendered frame, the VBlank
counter and the pad latches themselves.  A run of Gods whose gameplay does
not depend on where inside a tick the odd VBlank falls shows identical game
RAM at every tick start; a dropped tick shows as a VBlank-counter offset
with equal RAM; a torn input sample or a 60 Hz-counter read shows as the
first RAM difference, attributed here to the tick and the bytes.  Research
tooling on the original only; retained fixtures are read, never written.
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
from genesis_re.games import game as select_game
from genesis_re.history import HistoryStore
from genesis_re.machine import Machine

TICK_START, TICK_END, VBLANK = 0x001EC2, 0x001EB4, 0x0003DC
SOUND_BLOCK = (0xFDEA, 0xFE0C)
HANDLER_OWNED = set(range(0xEEC6, 0xEECA)) | set(range(0xF2AA, 0xF2AE)) | set(range(0xF19E, 0xF1A0)) | \
    set(range(0xEA1E, 0xEA24)) | set(range(0xF3DA, 0xF3DC)) | {0xEECC} | set(range(*SOUND_BLOCK)) | set(range(0x0000, 0x0040))
_MASK = bytes(0 if i in HANDLER_OWNED else 0xFF for i in range(65536))


def _sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def run(game, fixture, frames, burn, keep_ram=False, burn_gate=0x004150):
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
    observations, burned, stalls = [], None, [0, 0]
    with Machine(game.read_rom(), game) as m:
        m.restore(fixture.read_bytes())
        m.audio_policy('discard')
        m.gates([TICK_START, burn_gate])
        state = {'buttons': buttons}

        def at_gate():
            nonlocal burned
            pc = m.info['pc']
            if pc == burn_gate:
                if burn and observations:
                    # every tick: the game's work is b cycles longer from here on (a persistently shifted VBlank phase)
                    ok = m.atomic(target=m.info['tick'] + 10 * FT, cycles=burn, instructions=1, last_pc=burn_gate,
                                  writes=[], registers={})
                    stalls[0 if ok else 1] += 1
                return
            regs = m.registers()
            ram = pathfacts.ram_bytes(m)
            a7 = regs['a7'] & 0xFFFF
            info = m.info
            observations.append({'tick': info['tick'], 'frame': info['tick'] // FT, 'counter': int.from_bytes(ram[0xEEC6:0xEECA], 'big'),
                                 'game_ram': _sha(bytes(x & y for x, y in zip(ram, _MASK))[a7:]), 'frame_hash': _sha(m.frame()[2]),
                                 'pads': ram[0xEA1E:0xEA24].hex(), 'timer': int.from_bytes(ram[0xF19E:0xF1A0], 'big'),
                                 'elapsed': int.from_bytes(ram[0xF2AA:0xF2AE], 'big'), 'a7': a7,
                                 'ram': bytes(ram) if keep_ram else None, 'buttons': state['buttons']})

        def run_to(target):
            while m.info['tick'] < target:
                if m.run(target=target) == 'gate':
                    pc = m.info['pc']
                    at_gate()
                    m.gate(pc, bypass_once=True)

        for frame in range(frame0, frame0 + frames):
            wrap = frame * FT
            run_to(wrap)
            b = changes.get(frame, state['buttons'])
            if b != state['buttons']:
                m.pad(b)
                state['buttons'] = b
            run_to(wrap + FT)
    return observations, changes, stalls


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fixture', required=True)
    p.add_argument('--frames', type=int, default=600)
    p.add_argument('--burns', default='2000,20000,60000,100000')
    p.add_argument('--game', default='gods')
    p.add_argument('--json', default=None)
    p.add_argument('--burn-gate', default='004150', help='PC inside the tick at which the stall is applied (first occurrence after the first tick start)')
    a = p.parse_args(argv)
    game = select_game(a.game)
    fixture = Path(a.fixture)
    gate = int(a.burn_gate, 16)
    A, changes, _ = run(game, fixture, a.frames, 0, keep_ram=True, burn_gate=gate)
    print('run A: %d ticks over %d frames; %d input events in the window' % (
        len(A), a.frames, sum(1 for f in changes if A[0]['frame'] <= f < A[0]['frame'] + a.frames)))
    report = {'fixture': str(fixture), 'frames': a.frames, 'ticks': len(A), 'runs': []}
    for burn in [int(x) for x in a.burns.split(',') if x]:
        try:
            B, _, stalls = run(game, fixture, a.frames, burn, keep_ram=True, burn_gate=gate)
        except RuntimeError as error:
            print('burn %7d: %s' % (burn, error))
            report['runs'].append({'burn': burn, 'error': str(error)})
            continue
        n = min(len(A), len(B))
        ram_diff = [i for i in range(n) if A[i]['game_ram'] != B[i]['game_ram']]
        frame_diff = [i for i in range(n) if A[i]['frame_hash'] != B[i]['frame_hash']]
        counter_off = [(i, B[i]['counter'] - A[i]['counter']) for i in range(n) if A[i]['counter'] != B[i]['counter']]
        pad_diff = [i for i in range(n) if A[i]['pads'] != B[i]['pads']]
        timer_diff = [i for i in range(n) if A[i]['timer'] != B[i]['timer']]
        first = None
        if ram_diff:
            i = ram_diff[0]
            a7 = min(A[i]['a7'], B[i]['a7'])
            addresses = [k for k in range(a7, 65536) if A[i]['ram'][k] != B[i]['ram'][k] and k not in HANDLER_OWNED]
            first = {'tick_index': i, 'frame': B[i]['frame'], 'addresses': ['%06X %02X/%02X' % (0xFF0000 + k, A[i]['ram'][k], B[i]['ram'][k]) for k in addresses[:16]],
                     'count': len(addresses), 'counter_offset_there': B[i]['counter'] - A[i]['counter'],
                     'input_events_within_3_frames': [f for f in changes if B[i]['frame'] - 3 <= f <= B[i]['frame']]}
        summary = {'burn': burn, 'ticks_compared': n, 'ticks_A': len(A), 'ticks_B': len(B), 'stalls_applied': stalls[0], 'stalls_refused': stalls[1],
                   'game_ram_differs_at': len(ram_diff), 'first_game_ram_difference': first,
                   'frame_differs_at': len(frame_diff), 'first_frame_difference': frame_diff[0] if frame_diff else None,
                   'counter_offsets': sorted({o for _, o in counter_off}), 'first_counter_offset': counter_off[0] if counter_off else None,
                   'pad_latch_differs_at': len(pad_diff), 'timer_differs_at': len(timer_diff)}
        report['runs'].append(summary)
        print('burn %7d cycles (%.3f frame) per tick, %d applied / %d refused: A %d B %d ticks; game RAM differs at %d tick starts%s; frame differs at %d%s; '
              'VBlank counter offsets %s%s; pad latches differ at %d; 60Hz timer differs at %d' % (
                  burn, burn * 7 / game.board.frame_ticks, stalls[0], stalls[1], len(A), len(B), len(ram_diff),
                  '' if first is None else ' (first at tick %d, frame %d: %s%s)' % (
                      first['tick_index'], first['frame'], ', '.join(first['addresses'][:6]),
                      ' with input events at frames %s' % first['input_events_within_3_frames'] if first['input_events_within_3_frames'] else ''),
                  len(frame_diff), '' if not frame_diff else ' (first at tick %d)' % frame_diff[0],
                  summary['counter_offsets'], '' if not counter_off else ' (first at tick %d)' % counter_off[0][0],
                  len(pad_diff), len(timer_diff)))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(report, indent=1))
        print('wrote', a.json)


if __name__ == '__main__':
    main()
