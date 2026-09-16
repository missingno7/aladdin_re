"""vp_tree_run: the COMPLETE Gods history tree, original or candidate, at a chosen observation instant.

    python scripts/research/vp_tree_run.py --candidate original --offset 757154 --out artifacts/gods/research/tree-orig-moved-A
    python scripts/research/vp_tree_run.py --candidate camera-sprites --offset 757154 --classify --out ...

Walks every recorded branch of history/gods exactly as ``genesis_re.verification.execute_history``
does for ``--tree`` (a DFS over the node DAG, restoring in-memory saved states at each branch
point, never a persistent cache), observing every canonical frame with ``GenesisRun.observable``
(state/video/PCM digests, tick, pc, sr, cycle and instruction counters, VBlank count).  The only
change from the product is the observation instant, applied by ``vp_common.gods_profile(offset)``
(``dataclasses.replace`` of the Gods profile, registered for this process only); the input instant
(the frame wrap) is untouched.

``--classify`` wraps ``Machine.atomic`` in the candidate run and classifies every refusal BEFORE the
native call: ``deadline`` (the plan reaches the caller's deadline -- the observation instant --
``al_atomic``'s first test), ``vblank-in-span`` (the next VBlank IRQ instant, measured at
FRAME_TICKS-relative tick 766,080 by vp_vblank_instant.py, lies inside the plan's cycles + 64),
``engine-other`` (the engine's own remaining guards: VDP FIFO stall, bus access, trace bit, Z80
bank).  Fallbacks for an unsupported semantic domain and the seam's own deadline come from the
candidate's counters.  Every refusal is kept with node, frame, gate, tick offset, cycles and margin.
Research tooling; the product caches are never written.
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_common
vp_common.guard_paths()
from genesis_re.history import HistoryStore
from genesis_re.history_runtime import GenesisRun

FT, DIV = vp_common.FT, vp_common.DIVIDER
VBLANK_IRQ = 766_080          # master tick of the VBlank IRQ inside a frame (vp_vblank_instant.py: handler entry min 766,522 - 63 cycles)
IRQ_SLACK_CYCLES = 64


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--candidate', default='original')
    p.add_argument('--offset', type=int, default=None)
    p.add_argument('--out', required=True)
    p.add_argument('--classify', action='store_true')
    p.add_argument('--limit-frames', type=int, default=None, help='smoke test: stop each edge after N frames')
    a = p.parse_args(argv)
    game = vp_common.gods_profile(a.offset)
    rom = game.read_rom()
    store = HistoryStore(game.history_path(), game.history_root)
    nodes = store.nodes()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    observations, endpoints = {}, {}
    refusals, causes, by_gate = [], Counter(), {}
    executed = 0
    started = time.perf_counter()
    with GenesisRun(game, rom, a.candidate) as run:
        assert run.observation_offset_ticks == (a.offset if a.offset is not None else vp_common.DEFAULT_OFFSET)
        m = run.machine
        current = {'node': None}
        if a.classify and run.candidate is not None:
            real_atomic = m.atomic

            def atomic(*, target, cycles, instructions, last_pc, writes, registers):
                tick = m.info['tick']
                pc = m.info['pc']
                deadline = cycles >= (target - tick) // DIV
                ok = real_atomic(target=target, cycles=cycles, instructions=instructions, last_pc=last_pc,
                                 writes=writes, registers=registers)
                if ok:
                    causes['admitted'] += 1
                    return ok
                vblank_at = (tick // FT) * FT + VBLANK_IRQ
                if vblank_at <= tick:
                    vblank_at += FT
                margin = (vblank_at - tick) // DIV - cycles      # CPU cycles between the plan's end and the IRQ
                if deadline:
                    cause = 'deadline'
                elif margin <= IRQ_SLACK_CYCLES:
                    cause = 'vblank-in-span'
                else:
                    cause = 'engine-other'
                causes[cause] += 1
                gate = '%06X' % pc
                by_gate.setdefault(gate, Counter())[cause] += 1
                refusals.append({'node': current['node'][:12], 'frame': run.frame, 'gate': gate, 'cause': cause,
                                 'offset': round(tick % FT / FT, 4), 'cycles': cycles, 'margin_cycles': margin,
                                 'deadline_cycles': (target - tick) // DIV, 'in_seam': bool(getattr(m, 'in_seam', False))})
                return ok
            m.atomic = atomic
        children = {key: [] for key in nodes}
        for key, value in nodes.items():
            if value['parent'] is not None:
                children[value['parent']].append(key)
        stack = [(store.root_id, run.save())]
        while stack:
            key, saved = stack.pop()
            run.restore(saved)
            current['node'] = key
            if key != store.root_id:
                branch = nodes[key]
                edge = []
                before = run.frame
                end = branch['end_frame'] if a.limit_frames is None else min(branch['end_frame'], before + a.limit_frames)
                run.advance(end, branch['events'], lambda r: edge.append(r.observable()))
                executed += run.frame - before
                observations[key] = edge
                print('  node %s frames %d-%d done (%.0f s, %d frames total)' % (key[:12], before, run.frame, time.perf_counter() - started, executed), flush=True)
            endpoints[key] = run.observable()
            checkpoint = run.save()
            for child in sorted(children[key], reverse=True):
                stack.append((child, checkpoint))
        stats = dict(run.candidate.stats) if run.candidate else {}
        implementation = run.implementation
    report = {'head': vp_common.HEAD, 'candidate': a.candidate, 'observation_offset_ticks': run.observation_offset_ticks,
              'executed_frames': executed, 'seconds': round(time.perf_counter() - started, 1),
              'candidate_stats': stats, 'implementation': implementation,
              'refusal_causes': dict(causes), 'refusals_by_gate': {g: dict(c) for g, c in by_gate.items()},
              'endpoints': endpoints}
    (out / 'run.json').write_text(json.dumps(report, indent=1))
    (out / 'observations.json').write_text(json.dumps(observations))
    if a.classify:
        (out / 'refusals.json').write_text(json.dumps(refusals))
    print(json.dumps({k: v for k, v in report.items() if k not in ('endpoints', 'implementation')}, indent=1))


if __name__ == '__main__':
    main()
