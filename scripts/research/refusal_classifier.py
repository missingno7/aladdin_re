"""refusal_classifier: split a candidate's 'scheduler admission' fallbacks by cause, on a retained state.

    python scripts/research/refusal_classifier.py --fixture artifacts/gods/evidence/main/boundary-6000.state
                                                  --frames 600 [--candidate camera-sprites] [--offset TICKS]

Runs the candidate from the fixture with the recorded inputs exactly as
``segment_verify`` does, but wraps ``Machine.atomic`` so that every refusal
is classified before the native call:

  deadline   the plan's cycles reach the caller's deadline (the replay's
             observation instant): ``cycles >= (target - tick) / divider``,
             the first test in ``al_atomic``
  engine     the engine's own admission refused (an interrupt due inside the
             span, a DMA stall, a Z80 bank over work RAM)

``--offset`` overrides the profile's observation offset for this run only
(the deadline handed to the candidate and the instant the frame is observed
at), so the same window can be measured with the instant moved into the
game's idle window.  Research tooling; nothing under src changes.
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
from genesis_re.history_runtime import GenesisRun, EMPTY_PCM


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fixture', required=True)
    p.add_argument('--frames', type=int, default=600)
    p.add_argument('--candidate', default='camera-sprites')
    p.add_argument('--game', default='gods')
    p.add_argument('--offset', type=int, default=None, help='observation offset in master ticks (default: the profile\'s)')
    p.add_argument('--verbose', action='store_true')
    a = p.parse_args(argv)
    game = select_game(a.game)
    fixture = Path(a.fixture)
    meta = json.loads(fixture.with_suffix('.json').read_text())
    frame = meta['frame']
    store = HistoryStore(game.history_path(), game.history_root)
    path = store.flatten(store.resolve(meta['history_id']))
    buttons = 0
    for e in path['events']:
        if e['frame'] < frame:
            buttons = e['buttons']
    events = [e for e in path['events'] if e['frame'] >= frame]
    divider = game.board.m68k_divider
    causes = Counter()
    by_gate = {}
    with GenesisRun(game, game.read_rom(), a.candidate) as run:
        if a.offset is not None:
            run.observation_offset_ticks = a.offset
        run.restore((fixture.read_bytes(), frame, buttons, EMPTY_PCM, 0))
        m = run.machine
        real_atomic = m.atomic

        def atomic(*, target, cycles, instructions, last_pc, writes, registers):
            tick = m.info['tick']
            deadline = target < tick or cycles >= (target - tick) // divider
            ok = real_atomic(target=target, cycles=cycles, instructions=instructions, last_pc=last_pc,
                             writes=writes, registers=registers)
            if not ok:
                cause = 'deadline' if deadline else 'engine'
                if cause == 'engine':
                    ft = game.board.frame_ticks
                    vblank_at = (tick // ft) * ft + int(0.8555 * ft)
                    if vblank_at < tick:
                        vblank_at += ft
                    cause = 'engine-irq-in-span' if (vblank_at - tick) // divider <= cycles + 8 else 'engine-other'
                causes[cause] += 1
                gate = '%06X' % m.info['pc']
                by_gate.setdefault(gate, Counter())[cause] += 1
                if cause.startswith('engine') and a.verbose:
                    ft = game.board.frame_ticks
                    offset = tick % ft / ft
                    vblank_at = (tick // ft) * ft + int(0.8555 * ft)
                    if vblank_at < tick:
                        vblank_at += ft
                    print('  engine refusal at %s: frame offset %.4f, plan %d cycles (%.4f frame), next VBlank in %d cycles, '
                          'deadline in %d cycles' % (gate, offset, cycles, cycles * divider / ft, (vblank_at - tick) // divider,
                                                     (target - tick) // divider))
            else:
                causes['admitted'] += 1
            return ok

        m.atomic = atomic
        run.advance(frame + a.frames, events)
        stats = dict(run.candidate.stats)
    print('candidate %s from frame %d for %d frames (observation offset %s)' % (
        a.candidate, frame, a.frames, run.observation_offset_ticks))
    print('atomic outcomes: %s' % dict(causes))
    print('candidate stats: hits %s fallbacks %s seam entries %s completions %s seam deadlines %s' % (
        stats.get('candidate_hits'), stats.get('fallbacks'), stats.get('seam_entries'),
        stats.get('seam_completions'), stats.get('seam_deadline_fallbacks')))
    print('fallback reasons: %s' % dict(stats.get('fallback_reasons', {})))
    for gate, c in sorted(by_gate.items(), key=lambda kv: -sum(kv[1].values())):
        print('  refusals at %s: %s' % (gate, dict(c)))


if __name__ == '__main__':
    main()
