"""zb_bank_trace: the sound driver's bank-register transitions, sampled at every 68000 instruction boundary.

    python scripts/research/zb_bank_trace.py --fixture artifacts/gods/evidence/main/boundary-6000.state
                                             [--frames 3] [--from-line 220] [--to-line 60] [--json OUT]

Runs the ORIGINAL (no candidate) from the fixture, and for each of ``--frames`` frames steps the 68000
one instruction at a time from raster line ``--from-line`` to line ``--to-line`` of the next frame,
decoding the Z80 box out of a snapshot at every boundary.  A 68000 instruction is at least 4 CPU
cycles = 28 master ticks = 1.87 Z80 T-states, so every Z80 instruction boundary (>= 4 T) is sampled
at least once.  Reports each change of ``bank_bits`` (a write to 6000): the tick, raster line, the
Z80 PC at the sample, the register's value and window, and whether the window points at work RAM
(>= E00000, the adapter's pre-check); plus, for every sample with a transient RAM window, whether
the Z80 PC lies inside the bank routine that is executing (nothing else can run: IFF1 is 0 there).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zb_common as zb
from genesis_re.history_runtime import GenesisRun, EMPTY_PCM


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fixture', required=True)
    p.add_argument('--frames', type=int, default=3)
    p.add_argument('--from-line', type=float, default=220)
    p.add_argument('--to-line', type=float, default=60)
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    game = zb.GODS
    rom = game.read_rom()
    state, frame, buttons, events, meta = zb.load_fixture(game, a.fixture)
    view = zb.Z80View(rom)
    transitions, violations, samples_total = [], [], 0
    windows = []
    changes = {e['frame']: e['buttons'] for e in events}
    with GenesisRun(game, rom, 'original') as run:
        run.restore((state, frame, buttons, EMPTY_PCM, 0))
        m = run.machine
        pad = buttons
        for k in range(a.frames):
            f = frame + k
            start = f * zb.FT + int(a.from_line * zb.LINE)
            wrap = (f + 1) * zb.FT
            end = wrap + int(a.to_line * zb.LINE)
            assert m.run(target=start) == 'limit'
            last = view.decode(m.snapshot())
            window = {'frame': f, 'samples': 0, 'transitions': []}
            padded = False
            while m.info['tick'] < end:
                m.run(instructions=1)
                info = m.info
                if not padded and info['tick'] >= wrap:
                    pad = changes.get(f + 1, pad)
                    m.pad(pad)
                    padded = True
                z = view.decode(m.snapshot())
                samples_total += 1
                window['samples'] += 1
                if z['bank_bits'] != last['bank_bits']:
                    rec = {'tick': info['tick'], 'line': round(zb.frame_line(info['tick']), 2),
                           'z80_pc': '%04X' % z['pc'], 'bank': '%03X' % z['bank'], 'window': '%06X' % (z['bank'] << 15),
                           'bank_bits': z['bank_bits'], 'bits_delta': z['bank_bits'] - last['bank_bits'],
                           'ram_window': (z['bank'] << 15) >= 0xE00000, 'z80_instructions': z['instructions'],
                           'iff1': z['iff1'], 'in_routine': zb.BANK_A[0] <= z['pc'] < zb.BANK_B[1]}
                    window['transitions'].append(rec)
                    transitions.append(rec)
                if (z['bank'] << 15) >= 0xE00000:
                    routine = 'A' if zb.BANK_A[0] <= z['pc'] < zb.BANK_A[1] else 'B' if zb.BANK_B[0] <= z['pc'] < zb.BANK_B[1] else None
                    if routine is None or z['iff1']:
                        violations.append({'frame': f, 'tick': info['tick'], 'z80_pc': '%04X' % z['pc'], 'bank': '%03X' % z['bank'],
                                           'bank_bits': z['bank_bits'], 'iff1': z['iff1']})
                last = z
            windows.append(window)
            m.audio()          # drain the PCM the machine produced; the original's output is not compared here
    seqs = []
    cur = None
    for t in transitions:
        if cur is None or t['bank_bits'] - cur['last_bits'] > 1 or t['tick'] - cur['end_tick'] > 2000 * zb.DIV:
            cur = {'start_tick': t['tick'], 'start_line': t['line'], 'writes': 0, 'ram_transients': [], 'last_bits': t['bank_bits'] - 1,
                   'end_tick': t['tick']}
            seqs.append(cur)
        cur['writes'] += t['bits_delta']
        cur['last_bits'] = t['bank_bits']
        cur['end_tick'] = t['tick']
        cur['end_line'] = t['line']
        cur['final_bank'] = t['bank']
        cur['final_window'] = t['window']
        if t['ram_window']:
            cur['ram_transients'].append(t['window'])
    for s in seqs:
        s['duration_ticks'] = s['end_tick'] - s['start_tick']
        s['duration_68k_cycles'] = s['duration_ticks'] // zb.DIV
        del s['last_bits']
    print('fixture %s frame %d, %d frames traced, %d samples' % (a.fixture, frame, a.frames, samples_total))
    print('bank-register writes seen: %d; nine-bit sequences: %d' % (len(transitions), len(seqs)))
    for s in seqs:
        print('  sequence at line %.2f-%.2f (%d master ticks, %d 68k cycles): %d writes -> bank %s window %s; RAM-window transients %s'
              % (s['start_line'], s['end_line'], s['duration_ticks'], s['duration_68k_cycles'], s['writes'], s['final_bank'], s['final_window'], s['ram_transients']))
    print('samples with a RAM window where the Z80 PC is outside the executing bank routine or IFF1 is set: %d' % len(violations))
    for v in violations[:10]:
        print('  ', v)
    if a.json:
        Path(a.json).write_text(json.dumps({'provenance': zb.provenance(), 'fixture': str(a.fixture), 'frame': frame,
                                            'frames': a.frames, 'from_line': a.from_line, 'to_line': a.to_line,
                                            'samples': samples_total, 'transitions': transitions, 'sequences': seqs,
                                            'violations': violations}, indent=1))


if __name__ == '__main__':
    main()
