"""zb_rule_probe: what the Z80 bank guard refuses, and what narrower rules would admit (research, read-only).

    python scripts/research/zb_rule_probe.py --fixture artifacts/gods/evidence/main/boundary-6000.state
                                             [--frames 600] [--candidate camera-sprites] [--json OUT]

Runs the candidate over a window (the same dispatch as the product; the observation instant is the
profile's own).  ``Machine.atomic`` is wrapped: before and after every call the Z80 box is decoded
out of a snapshot (research-only decode, zb_common.Z80View), so each call records

  * admitted / refused and the adapter's cause (``Machine.refusal``: deadline, z80_bank, engine);
  * the bank register and its bit count at the gate, the Z80 PC, IFF1;
  * for an ADMITTED span: whether the bank register was written inside the span (bit count delta),
    and whether the register passed through a work-RAM value inside the span (the transient writes
    of the driver's nine-bit sequence) -- while the adapter's shared-RAM observer was armed; the run
    continuing past the call is the measurement that the observer did not fire;
  * for a z80_bank REFUSAL: the residue of the bit count modulo nine (the phase of the sequence),
    the plan's span, and what each candidate rule would do with it.

Candidate rules (each evaluated on the machine facts at the gate, nothing else):
  R0  current: refuse while (bank << 15) >= E00000.
  R1  complete-sequence: refuse only if (bank << 15) >= E00000 and bank_bits % 9 == 0.
  R2  observer-only: never refuse for the bank; rely on the armed observer.

A refused span changes nothing, so the wrapper never alters the run: every call is the product's own.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zb_common as zb
from genesis_re.history_runtime import GenesisRun, EMPTY_PCM


def transient_windows(bank, bits_before, bits_after, written_bits):
    """Replay the shift register over the bits written inside the span; return the windows it passed through."""
    seen = []
    b = bank
    for bit in written_bits:
        b = ((b >> 1) | ((bit & 1) << 8)) & 0x1FF
        seen.append(b << 15)
    return seen


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fixture', required=True)
    p.add_argument('--frames', type=int, default=600)
    p.add_argument('--candidate', default='camera-sprites')
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    game = zb.GODS
    rom = game.read_rom()
    state, frame, buttons, events, meta = zb.load_fixture(game, a.fixture)
    view = zb.Z80View(rom)
    calls = []
    causes = Counter()
    with GenesisRun(game, rom, a.candidate) as run:
        run.restore((state, frame, buttons, EMPTY_PCM, 0))
        m = run.machine
        real_atomic = m.atomic

        def atomic(*, target, cycles, instructions, last_pc, writes, registers):
            info = m.info
            before = view.decode(m.snapshot())
            ok = real_atomic(target=target, cycles=cycles, instructions=instructions, last_pc=last_pc, writes=writes, registers=registers)
            cause = 'admitted' if ok else m.refusal
            causes[cause] += 1
            rec = {'frame': run.frame, 'gate': '%06X' % info['pc'], 'tick': info['tick'],
                   'line': round(zb.frame_line(info['tick']), 2), 'cycles': cycles, 'writes': len(writes),
                   'result': cause, 'bank': '%03X' % before['bank'], 'window': '%06X' % (before['bank'] << 15),
                   'bank_bits': before['bank_bits'], 'phase': before['bank_bits'] % 9,
                   'z80_pc': '%04X' % before['pc'], 'z80_iff1': before['iff1'], 'z80_running': not (before['bus_requested'] or before['reset_asserted'])}
            if ok:
                after = view.decode(m.snapshot())
                delta = after['bank_bits'] - before['bank_bits']
                rec['bank_writes_in_span'] = delta
                if delta:
                    # The bits written are recoverable from the register's value after the span only
                    # when at most nine were written; the driver writes exactly nine per sequence.
                    rec['bank_after'] = '%03X' % after['bank']
                    rec['window_after'] = '%06X' % (after['bank'] << 15)
                    # which intermediate windows the register passed through inside the span
                    if delta <= 9:
                        bits = [(after['bank'] >> (9 - delta + i)) & 1 for i in range(delta)]
                        passed = transient_windows(before['bank'], before['bank_bits'], after['bank_bits'], bits)
                    else:
                        passed = None
                    rec['ram_window_inside_span'] = None if passed is None else any(w >= 0xE00000 for w in passed)
                    rec['windows_passed'] = None if passed is None else ['%06X' % w for w in passed]
            else:
                rec['R0'] = 'refuse' if cause == 'z80_bank' else cause
                if cause == 'z80_bank':
                    rec['R1'] = 'refuse' if before['bank_bits'] % 9 == 0 else 'admit'
                    rec['R2'] = 'admit'
            calls.append(rec)
            return ok
        m.atomic = atomic
        run.advance(frame + a.frames, events)
        stats = dict(run.candidate.stats)
    refusals = [c for c in calls if c['result'] == 'z80_bank']
    admitted = [c for c in calls if c['result'] == 'admitted']
    spans_with_writes = [c for c in admitted if c.get('bank_writes_in_span')]
    spans_with_ram_transient = [c for c in spans_with_writes if c.get('ram_window_inside_span')]
    print('candidate %s from frame %d for %d frames (observation offset %d): %s' % (a.candidate, frame, a.frames, run.observation_offset_ticks, dict(causes)))
    print('candidate stats: hits %s fallbacks %s reasons %s' % (stats['candidate_hits'], stats['fallbacks'], dict(stats['fallback_reasons'])))
    print('z80_bank refusals: %d' % len(refusals))
    print('  by window at the gate: %s' % dict(Counter(c['window'] for c in refusals)))
    print('  by phase (bank_bits mod 9): %s' % dict(sorted(Counter(c['phase'] for c in refusals).items())))
    print('  by Z80 PC at the gate: %s' % dict(sorted(Counter(c['z80_pc'] for c in refusals).items())))
    print('  by gate: %s' % dict(Counter(c['gate'] for c in refusals).most_common()))
    print('  by raster line (10-line bins): %s' % dict(sorted(Counter(int(c['line']) // 10 * 10 for c in refusals).items())))
    print('  plan cycles: min %s median %s max %s' % ((min(c['cycles'] for c in refusals), sorted(c['cycles'] for c in refusals)[len(refusals) // 2], max(c['cycles'] for c in refusals)) if refusals else ('-', '-', '-')))
    print('  R1 (complete-sequence rule) would admit %d, refuse %d' % (sum(c.get('R1') == 'admit' for c in refusals), sum(c.get('R1') == 'refuse' for c in refusals)))
    print('  R2 (observer only) would admit %d' % len(refusals))
    print('admitted spans: %d; containing bank-register writes: %d; whose register passed through a work-RAM window inside the span (observer armed, did not fire): %d'
          % (len(admitted), len(spans_with_writes), len(spans_with_ram_transient)))
    print('  writes-in-span distribution: %s' % dict(sorted(Counter(c['bank_writes_in_span'] for c in spans_with_writes).items())))
    print('  windows passed inside admitted spans: %s' % dict(Counter(w for c in spans_with_ram_transient for w in c['windows_passed'] if int(w, 16) >= 0xE00000)))
    print('  banks at the gate of admitted spans: %s' % dict(Counter(c['window'] for c in admitted)))
    if a.json:
        Path(a.json).write_text(json.dumps({'provenance': zb.provenance(), 'fixture': str(a.fixture), 'frame': frame, 'frames': a.frames,
                                            'candidate': a.candidate, 'observation_offset_ticks': run.observation_offset_ticks,
                                            'causes': dict(causes), 'stats': stats, 'calls': calls}, indent=1))


if __name__ == '__main__':
    main()
