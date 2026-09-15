"""Compare the VDP port writes of a native transition with the original's, word for word and in order.

  verify_ports.py FRAME DIE_FRAME DIE_PC

The RAM checkpoints of verify_sequence.py prove the game state; this proves
the video output of a transition: every word the native sequence writes to
the VDP control and data ports (the VDP model's log) against every word
the original writes between the transition's entry and the main loop's
resumed boundary (aladdin_sega.native.oracle.trace_port_writes, which
single-steps the original and records a port write only when its
instruction completes).  Equal streams into equal VRAM / CRAM / VSRAM
images mean equal video memories, so this is the observable-output
contract for fades, screen draws and the outer-game screens.  The native
side runs under the aligned replay clock.

The original's stream is a few million instructions for a level change;
expect minutes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from aladdin_sega.machine import Machine
from aladdin_sega.native import NativeGap, run_frame
from aladdin_sega.native.oracle import trace_port_writes


def main(start, die_frame, die_pc):
    rom = nr.read_rom(); pads = nr.masks()
    m = Machine(rom); m.audio_policy('discard'); m.restore(nr.load(start))
    state, frame = nr.seed_at_boundary(m, start, pads, rom)
    driver = nr.OracleDriver(m, pads, frame=frame)
    while state.frame < die_frame - 2:
        driver.begin_frame(state.replay); run_frame(state); driver.run_frame(state.replay)
        state.advance_frames(max(0, driver.frame - state.frame))
    # the native transition, its port log kept apart from the transition's start; the clock still aligns it
    clock = state.replay
    original_begin = clock.begin

    def begin(kind):
        original_begin(kind)
        state.vdp.log = []
    clock.begin = begin
    started = None
    for _ in range(5):
        f = state.frame
        state.vdp.log = []
        driver.begin_frame(clock)
        try:
            run_frame(state)
        except NativeGap as gap:
            print(f'native: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
            return 4
        if clock.consumed:
            started = f
            break
        driver.run_frame(clock)
    if started is None:
        print(f'no transition started in frames {die_frame - 2}..{die_frame + 2}')
        return 2
    native_log = list(state.vdp.log)
    clock.consumed = False
    print(f'the native transition started in frame {started} and wrote {len(native_log)} port words')
    # the original: from the transition's entry to the main loop's resumed boundary, single-stepped
    m2 = Machine(rom); m2.audio_policy('discard'); m2.restore(nr.load(start))
    m.close()
    nr.seed_at_boundary(m2, start, pads, rom)
    nr.arm(m2, [nr.FRAME_BOUNDARY, die_pc])
    boundary = None
    while True:
        assert nr.run_with_pads(m2, pads, m2.info['tick'] + 3 * nr.FRAME_TICKS) == 'gate'
        pc, f = m2.info['pc'], m2.info['tick'] // nr.FRAME_TICKS
        if pc == die_pc and boundary is not None and abs(boundary - started) <= 2:
            break
        m2.gate(pc, bypass_once=True)
        if pc == nr.FRAME_BOUNDARY and nr.at_main_loop_boundary(m2):
            boundary = f
            if boundary > started + 3:
                print(f'the original did not enter {die_pc:06X} near frame {started}'); return 2
    print(f'the original entered {die_pc:06X} in tick frame {f}; tracing its port writes ...')
    last = [m2.info['tick'] // nr.FRAME_TICKS]

    def on_step(machine):
        frame = machine.info['tick'] // nr.FRAME_TICKS
        if frame != last[0]:
            last[0] = frame; machine.pad(pads.get(frame, 0))
    oracle_log = []
    m2.gate(die_pc, bypass_once=True)
    m2.gates([])
    while True:
        oracle_log.extend(trace_port_writes(m2, (nr.FRAME_BOUNDARY,), limit=50_000_000, on_step=on_step))
        if nr.at_main_loop_boundary(m2):
            break
        m2.run(instructions=1)          # past the mini frame's own call of the boundary step
    # the resumed frame's own steps up to the next boundary belong to the native frame too
    m2.close()
    print(f'the original wrote {len(oracle_log)} port words up to its resumed boundary')
    return compare(native_log, oracle_log)


def compare(native_log, oracle_log):
    n = min(len(native_log), len(oracle_log))
    for i in range(n):
        if native_log[i] != oracle_log[i]:
            print(f'first difference at word {i}:')
            for j in range(max(0, i - 4), min(n, i + 6)):
                mark = '  <--' if j == i else ''
                print(f'  {j:6}: native {native_log[j][0]:7} {native_log[j][1]:04X}   oracle {oracle_log[j][0]:7} {oracle_log[j][1]:04X}{mark}')
            return 3
    if len(native_log) != len(oracle_log):
        print(f'the streams agree for {n} words, then one goes on: native {len(native_log)}, oracle {len(oracle_log)}')
        longer = native_log if len(native_log) > len(oracle_log) else oracle_log
        print('  next words of the longer stream:', longer[n:n + 6])
        return 3
    print(f'the port streams are identical: {n} words')
    return 0


if __name__ == '__main__':
    sys.exit(main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3], 16)))
