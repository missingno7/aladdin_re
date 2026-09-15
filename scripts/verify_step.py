"""Prove one recovered frame step against the oracle over a long window.

  verify_step.py STEP FRAME COUNT [FRAME COUNT ...]

Gates only that step's entry and exits, so a step can be checked over
thousands of frames quickly.  RAM is compared byte for byte at the step's
exit (ignoring the bookkeeping regions), the VDP port words are compared
when the step writes the ports, and the semantic events the step produced
are tallied so the run shows what it actually exercised.
"""
import sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from genesis_re.machine import Machine
from aladdin_sega.native import GameState, NativeGap, STEPS
from aladdin_sega.native.frame import NativeServices
from aladdin_sega.native.oracle import trace_port_writes, run_to_exits


def verify_step(step, frame, count, rom, pads):
    m = Machine(rom); m.audio_policy("discard"); m.restore(nr.load(frame)); m.gates([step.entry, *step.exits])
    tick_end = m.info['tick'] + count * nr.FRAME_TICKS
    results, events, fields = collections.Counter(), collections.Counter(), collections.Counter()
    padded = -1
    while m.info['tick'] < tick_end:
        f = m.info['tick'] // nr.FRAME_TICKS
        if f != padded:
            m.pad(pads.get(f, 0)); padded = f
        if m.run(target=min(tick_end, (f + 1) * nr.FRAME_TICKS)) != 'gate':
            continue
        if m.info['pc'] != step.entry:
            m.gate(m.info['pc'], bypass_once=True); continue
        before = bytearray(m.peek_ram(0, 65536)); m.gate(step.entry, bypass_once=True)
        if step.ports:
            traced = trace_port_writes(m, step.exits)
        else:
            run_to_exits(m, step.exits, tick_end + nr.FRAME_TICKS)
        after = m.peek_ram(0, 65536)
        state = GameState(before, rom, f); state.buttons = pads.get(f, 0)
        try:
            step.run(state, NativeServices(state))
        except NativeGap as gap:
            results[f'gap: {gap.detail[:100]}'] += 1; m.gate(m.info['pc'], bypass_once=True); continue
        bad = 0
        for a in range(65536):
            if after[a] != state.ram[a] and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in nr.BOOKKEEPING):
                fields[nr.field_name(0xFF0000 | a)] += 1; bad += 1
        if step.ports and state.vdp.log != traced:
            first = next((i for i, (a, b) in enumerate(zip(state.vdp.log, traced)) if a != b), min(len(state.vdp.log), len(traced)))
            fields[f'ports@{first}: {state.vdp.log[first:first + 3]} vs {traced[first:first + 3]}'] += 1; bad += 1
        results['ok' if not bad else f'mismatch at frame {f}'] += 1
        for ev in state.events:
            events[ev[0] + (f':{ev[2]}' if ev[0] in ('spawn', 'sound') else '')] += 1
        m.gate(m.info['pc'], bypass_once=True)
    m.close()
    return results, events, fields


if __name__ == '__main__':
    step = next(s for s in STEPS if s.name == sys.argv[1])
    rom = nr.read_rom(); pads = nr.masks()
    args = [int(a) for a in sys.argv[2:]]
    for frame, count in zip(args[::2], args[1::2]):
        results, events, fields = verify_step(step, frame, count, rom, pads)
        print(f'{step.name} from {frame} x{count}: {dict(results)}')
        if events:
            print('  events:', dict(sorted(events.items())))
        if fields:
            print('  mismatching:', dict(fields.most_common(8)))
