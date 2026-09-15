"""Run the native runtime and the oracle side by side and report the first frame where they diverge.

  native_diff.py FRAME COUNT [--every N]

Both start from artifacts/evidence/frames/fFRAME.state.  After every frame
(at the VBlank wait) the whole work RAM is compared, ignoring only the
bookkeeping regions; the first divergence is reported with the fields
that differ, or a NativeGap when the native side stops.  This is the
whole-frame boundary of verification: nothing is copied from the oracle
after the seed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from aladdin_sega.machine import Machine
from aladdin_sega.native import GameState, NativeGap, STEPS, run_frame


def main(frame, count, every=1):
    rom = nr.read_rom(); pads = nr.masks()
    first = frame
    m = Machine(rom); m.audio_policy('discard'); m.restore(nr.load(frame))
    boundary = next(s for s in STEPS if s.name == 'wait_vblank').exits[0]
    m.gates([boundary])
    m.pad(pads.get(frame, 0))
    if m.run(target=m.info['tick'] + 3 * nr.FRAME_TICKS) != 'gate':
        print('the snapshot did not reach a frame boundary'); return 2
    frame = m.info['tick'] // nr.FRAME_TICKS
    state = GameState.from_machine(m, frame, rom)      # seeded at the frame boundary, both sides aligned
    m.gate(boundary, bypass_once=True)
    for i in range(count):
        f = frame + i
        try:
            run_frame(state, pads.get(f, 0))
        except NativeGap as gap:
            print(f'frame {f}: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
            return 1
        m.pad(pads.get(f, 0))
        if m.run(target=m.info['tick'] + 3 * nr.FRAME_TICKS) != 'gate':
            print(f'frame {f}: the oracle did not reach the frame boundary'); return 2
        m.gate(boundary, bypass_once=True)
        if (i + 1) % every:
            continue
        oracle = m.peek_ram(0, 65536)
        diff = [a for a in range(65536) if oracle[a] != state.ram[a]
                and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in nr.BOOKKEEPING)]
        if diff:
            _report(f, diff, state.ram, oracle)
            m.close()
            step_diff(rom, first, f, pads)
            return 3
    print(f'native matches the oracle for {count} frames to {frame + count} (events {len(state.events)})')
    m.close()
    return 0


def _report(f, diff, native_ram, oracle, label=''):
    names = {}
    for a in diff:
        names.setdefault(nr.field_name(0xFF0000 | a), []).append(a)
    print(f'frame {f}{label}: native diverges in {len(diff)} bytes:')
    for name, addresses in list(names.items())[:20]:
        a = addresses[0]
        print(f'  {name}: native {native_ram[a]:02X} oracle {oracle[a]:02X}')


def step_diff(rom, first, target, pads):
    """Replay to the frame before ``target`` on both sides, then diff after every step of that frame."""
    from aladdin_sega.native.frame import NativeServices
    from aladdin_sega.native.oracle import run_to_exits, trace_port_writes
    m = Machine(rom); m.audio_policy('discard'); m.restore(nr.load(first))
    boundary = next(s for s in STEPS if s.name == 'wait_vblank').exits[0]
    m.gates([boundary]); m.pad(pads.get(first, 0))
    assert m.run(target=m.info['tick'] + 3 * nr.FRAME_TICKS) == 'gate'
    frame = m.info['tick'] // nr.FRAME_TICKS
    state = GameState.from_machine(m, frame, rom); m.gate(boundary, bypass_once=True)
    for f in range(frame, target):
        run_frame(state, pads.get(f, 0)); m.pad(pads.get(f, 0))
        assert m.run(target=m.info['tick'] + 3 * nr.FRAME_TICKS) == 'gate'; m.gate(boundary, bypass_once=True)
    m.gates(sorted({s.entry for s in STEPS} | {e for s in STEPS for e in s.exits}))
    m.pad(pads.get(target, 0)); state.buttons = pads.get(target, 0)
    services = NativeServices(state)
    for step in STEPS:
        if m.info['pc'] != step.entry:
            run_to_exits(m, (step.entry,), m.info['tick'] + 3 * nr.FRAME_TICKS)
        m.gate(step.entry, bypass_once=True)
        step.run(state, services)
        if step.ports:
            trace_port_writes(m, step.exits)
        else:
            run_to_exits(m, step.exits, m.info['tick'] + 3 * nr.FRAME_TICKS)
        oracle = m.peek_ram(0, 65536)
        diff = [a for a in range(65536) if oracle[a] != state.ram[a]
                and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in nr.BOOKKEEPING)]
        if diff:
            _report(target, diff, state.ram, oracle, label=f' after step {step.name} ({step.entry:06X})')
            m.close(); return
    print(f'frame {target}: every step matches when carried forward; the frame boundary differs only in timing')
    m.close()


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    every = int(sys.argv[sys.argv.index('--every') + 1]) if '--every' in sys.argv else 1
    sys.exit(main(int(args[0]), int(args[1]), every))
