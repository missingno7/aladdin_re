"""vp_engine_probe: what is the 'engine-other' refusal?  Probe each one with a 1-cycle time-only atomic.

    python scripts/research/vp_engine_probe.py --fixture artifacts/gods/evidence/main/boundary-6000.state --frames 600
                                               [--candidate camera-sprites] [--offset 757154]

Runs the candidate over a window (as refusal_classifier does) and, at every refusal that is neither
the caller's deadline nor a VBlank inside the span, immediately asks ``Machine.atomic`` for a 1-cycle,
1-instruction, write-free operation at the same parked gate.  If that is refused too, the engine's
condition is independent of the plan's span (a Z80 bank over work RAM, a bus access in progress, the
trace bit, or a VDP stall/IRQ latch that any native operation trips); if it is accepted, the refusal
was about the span (the original plan's cycles reached a device event).  An accepted probe charges the
machine one cycle (the window's trajectory then differs from the reference by that cycle; this is a
diagnostic run, not a verification).  Also records the Z80 instruction rate around the refusal.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_common
vp_common.guard_paths()
from genesis_re.history import HistoryStore
from genesis_re.history_runtime import GenesisRun, EMPTY_PCM

FT, DIV = vp_common.FT, vp_common.DIVIDER
VBLANK_IRQ = 766_080


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fixture', required=True)
    p.add_argument('--frames', type=int, default=600)
    p.add_argument('--candidate', default='camera-sprites')
    p.add_argument('--offset', type=int, default=None)
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    game = vp_common.gods_profile(a.offset)
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
    probes, causes = [], Counter()
    rom = game.read_rom()
    z80_code = rom[0xF4570:0xF4570 + 64]      # the driver the 68000 copies to Z80 RAM 0000: locates the Z80 RAM in a snapshot

    def z80_bank(snapshot):
        i = snapshot.find(z80_code)
        if i < 0:
            return None
        z = i + 8192 + 4                          # Z80 RAM, then four booleans, then the bank register (u16 LE) and its bit count (u32)
        return int.from_bytes(snapshot[z:z + 2], 'little'), int.from_bytes(snapshot[z + 2:z + 6], 'little')
    with GenesisRun(game, rom, a.candidate) as run:
        run.restore((fixture.read_bytes(), frame, buttons, EMPTY_PCM, 0))
        m = run.machine
        real_atomic = m.atomic
        last = {'z80': m.info['z80_instructions'], 'tick': m.info['tick']}

        def atomic(*, target, cycles, instructions, last_pc, writes, registers):
            info = m.info
            tick = info['tick']
            deadline = cycles >= (target - tick) // DIV
            ok = real_atomic(target=target, cycles=cycles, instructions=instructions, last_pc=last_pc, writes=writes, registers=registers)
            if ok:
                causes['admitted'] += 1
                return ok
            vblank_at = (tick // FT) * FT + VBLANK_IRQ
            if vblank_at <= tick:
                vblank_at += FT
            margin = (vblank_at - tick) // DIV - cycles
            cause = 'deadline' if deadline else 'vblank-in-span' if margin <= 64 else 'engine-other'
            causes[cause] += 1
            if cause == 'engine-other':
                z80_rate = (info['z80_instructions'] - last['z80']) / max(1, (tick - last['tick']) / FT)
                bank = z80_bank(m.snapshot())
                probe = real_atomic(target=target, cycles=1, instructions=1, last_pc=info['pc'], writes=[], registers={})
                probes.append({'frame': run.frame, 'gate': '%06X' % info['pc'], 'offset': round(tick % FT / FT, 4), 'line': int(tick % FT / FT * 262),
                               'cycles': cycles, 'probe_1_cycle_accepted': probe, 'z80_instr_per_frame_since_last': round(z80_rate),
                               'sr': info['sr'], 'z80_bank': None if bank is None else '%03X' % bank[0], 'z80_window': None if bank is None else '%06X' % (bank[0] << 15),
                               'z80_bank_bits': None if bank is None else bank[1]})
                if probe:
                    # the probe consumed the parked gate: the original must now run the region from here
                    pass
            last['z80'], last['tick'] = info['z80_instructions'], tick
            return ok
        m.atomic = atomic
        run.advance(frame + a.frames, events)
        stats = dict(run.candidate.stats)
    print('candidate %s from frame %d for %d frames (offset %s): causes %s' % (a.candidate, frame, a.frames, run.observation_offset_ticks, dict(causes)))
    print('candidate stats: hits %s fallbacks %s reasons %s' % (stats['candidate_hits'], stats['fallbacks'], dict(stats['fallback_reasons'])))
    acc = Counter(p['probe_1_cycle_accepted'] for p in probes)
    print('engine-other probes: %d; 1-cycle probe accepted: %s' % (len(probes), dict(acc)))
    print('by line (probe refused): %s' % dict(sorted(Counter(p['line'] for p in probes if not p['probe_1_cycle_accepted']).items())))
    print('by line (probe accepted): %s' % dict(sorted(Counter(p['line'] for p in probes if p['probe_1_cycle_accepted']).items())))
    print('z80 instructions per frame around refused probes: %s' % sorted(Counter(p['z80_instr_per_frame_since_last'] // 500 * 500 for p in probes if not p['probe_1_cycle_accepted']).items()))
    print('Z80 bank window at refused probes: %s' % dict(Counter(p['z80_window'] for p in probes if not p['probe_1_cycle_accepted'])))
    print('Z80 bank window at accepted probes: %s' % dict(Counter(p['z80_window'] for p in probes if p['probe_1_cycle_accepted'])))
    print('examples: %s' % probes[:3])
    if a.json:
        Path(a.json).write_text(json.dumps({'causes': dict(causes), 'probes': probes, 'stats': stats}, indent=1))


if __name__ == '__main__':
    main()
