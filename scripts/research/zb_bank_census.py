"""zb_bank_census: which banks a game's sound driver selects, over a recording from power-on (research, read-only).

    python scripts/research/zb_bank_census.py --game gods|aladdin [--frames 3000] [--samples 8] [--json OUT]

Runs the ORIGINAL over the game's ``main`` history from power-on and decodes the Z80 box out of a
snapshot at ``--samples`` evenly spaced instants of every frame (plus the frame's own observation
instant).  Reports every distinct bank-register value seen with its phase (bit count modulo nine),
split into completed values (phase 0) and transients, the number of nine-bit sequences per frame
(from the bit count), and whether any COMPLETED value points at work RAM (>= E00000).  A completed
RAM bank persists between sequences, so sampling catches it; transients (< 400 T-states) are caught
only by chance, which is why the phase is reported with every value.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zb_common as zb
from genesis_re.history import HistoryStore
from genesis_re.history_runtime import GenesisRun


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--game', default='gods')
    p.add_argument('--frames', type=int, default=3000)
    p.add_argument('--samples', type=int, default=8)
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    if a.game == 'gods':
        game = zb.GODS
    else:
        from aladdin_sega.profile import ALADDIN as game
    rom = game.read_rom()
    store = HistoryStore(game.history_path(), game.history_root)
    path = store.flatten(store.resolve('main'))
    events = path['events']
    changes = {e['frame']: e['buttons'] for e in events}
    FT = game.board.frame_ticks

    # the driver image differs per game; the locator is code the driver never overwrites
    if a.game == 'gods':
        view = zb.Z80View(rom, offset=0x13C, length=64)        # the bank routines
    else:
        view = zb.Z80View(rom, base=0x1B8480, offset=0x23D, length=48)   # Aladdin: ROM 1B8480.. -> Z80 0000 (1E573A); its bank routine
    values, completed_ram, per_frame_seqs = Counter(), [], Counter()
    last_bits = None
    with GenesisRun(game, rom, 'original') as run:
        m = run.machine
        pad = 0
        for f in range(a.frames):
            pad = changes.get(f, pad)
            m.pad(pad)
            base = f * FT
            for s in range(1, a.samples + 1):
                t = base + (FT * s) // (a.samples + 1)
                m.run(target=t)
                z = view.decode(m.snapshot())
                if z is None:
                    continue
                key = ('%03X' % z['bank'], z['bank_bits'] % 9)
                values[key] += 1
                if z['bank_bits'] % 9 == 0 and (z['bank'] << 15) >= 0xE00000 and not (z['reset_asserted']):
                    completed_ram.append({'frame': f, 'tick': t, 'bank': '%03X' % z['bank'], 'z80_pc': '%04X' % z['pc']})
            m.run(target=base + FT)
            z = view.decode(m.snapshot())
            if z is not None:
                if last_bits is not None:
                    per_frame_seqs[(z['bank_bits'] - last_bits)] += 1
                last_bits = z['bank_bits']
            m.audio()
    done = sorted(((k, v) for k, v in values.items() if k[1] == 0), key=lambda kv: -kv[1])
    trans = sorted(((k, v) for k, v in values.items() if k[1] != 0), key=lambda kv: -kv[1])
    print('%s: %d frames from power-on, %d samples per frame' % (game.title, a.frames, a.samples))
    print('completed bank values (phase 0): %s' % [('%s->%06X' % (k[0], int(k[0], 16) << 15), v) for k, v in done])
    print('transient values seen (bank, phase): %s' % [(k, v) for k, v in trans[:20]])
    print('bank writes per frame (from the bit count): %s' % dict(sorted(per_frame_seqs.items())))
    print('completed values pointing at work RAM: %d %s' % (len(completed_ram), completed_ram[:5]))
    if a.json:
        Path(a.json).write_text(json.dumps({'provenance': zb.provenance(), 'game': game.id, 'frames': a.frames, 'samples': a.samples,
                                            'values': [[k[0], k[1], v] for k, v in values.items()],
                                            'writes_per_frame': {str(k): v for k, v in per_frame_seqs.items()},
                                            'completed_ram': completed_ram}, indent=1))


if __name__ == '__main__':
    main()
