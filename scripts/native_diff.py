"""Run the native runtime and the oracle side by side and report the first frame where they diverge.

  native_diff.py FRAME COUNT [--every N]
  native_diff.py --cold RECORDING COUNT [--every N]

Both start from artifacts/evidence/frames/fFRAME.state, or (--cold) from
power-on with the recording RECORDING (a history node id or prefix): the
oracle boots, runs the title and attract screens (not yet native) and
seeds the native runtime at the first main-loop boundary.  After every
frame (at the VBlank wait) the whole work RAM is compared, ignoring
only the bookkeeping regions; the first divergence is reported with the
fields that differ, or a NativeGap when the native side stops.  The
oracle is also the replay clock: at a transition's checkpoints the
native frame counter takes the original's VBlank count, so recorded
input lines up without anything stored per recording.  This is the
whole-frame boundary of verification: nothing is copied from the
oracle after the seed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from aladdin_sega.machine import Machine
from aladdin_sega.native import GameState, NativeGap, STEPS, run_frame


def main(frame, count, every=1, recording=None):
    rom = nr.read_rom(); pads = nr.masks(recording)
    first = frame
    m = Machine(rom); m.audio_policy('discard')
    if recording is None:
        m.restore(nr.load(frame))
        state, frame = nr.seed_at_boundary(m, frame, pads, rom)
    else:
        state, frame = nr.seed_cold(m, pads, rom)
    print(f'seeded at main-loop frame {frame}' + (f' of recording {recording}' if recording else ''))
    for i in range(count):
        f = state.frame
        try:
            run_frame(state)
        except NativeGap as gap:
            print(f'frame {f}: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
            return 1
        nr.run_oracle_frame(m, pads, state.replay)
        if (i + 1) % every:
            continue
        oracle = m.peek_ram(0, 65536)
        diff = [a for a in range(65536) if oracle[a] != state.ram[a]
                and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in nr.BOOKKEEPING)]
        if diff:
            _report(f, diff, state.ram, oracle)
            m.close()
            step_diff(rom, first, f, pads, recording)
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


def step_diff(rom, first, target, pads, recording=None):
    """Replay to the frame before ``target`` on both sides, then diff after every step of that frame."""
    from aladdin_sega.native.frame import NativeServices
    from aladdin_sega.native.oracle import run_to_exits, trace_port_writes
    m = Machine(rom); m.audio_policy('discard')
    if recording is None:
        m.restore(nr.load(first))
        state, frame = nr.seed_at_boundary(m, first, pads, rom)
    else:
        state, frame = nr.seed_cold(m, pads, rom)
    while state.frame < target:
        run_frame(state)
        nr.run_oracle_frame(m, pads, state.replay)
    m.gates(sorted({s.entry for s in STEPS} | {e for s in STEPS for e in s.exits} | {nr.VBLANK_HANDLER}))
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
    argv = sys.argv[1:]
    every = 1
    if '--every' in argv:
        i = argv.index('--every'); every = int(argv[i + 1]); del argv[i:i + 2]
    if '--cold' in argv:
        i = argv.index('--cold'); recording = argv[i + 1]; del argv[i:i + 2]
        sys.exit(main(0, int(argv[0]), every, recording=recording))
    sys.exit(main(int(argv[0]), int(argv[1]), every))
