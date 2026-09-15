"""Run the native runtime and the oracle side by side and report the first frame where they diverge.

  native_diff.py FRAME COUNT [--every N] [--independent]
  native_diff.py --cold RECORDING COUNT [--every N] [--independent] [--native-boot]
  native_diff.py --cold NODE COUNT --native-history [--store DIR] --independent --native-boot

--native-history takes a node of the native player's store (history_native):
its inputs are indexed by the game's own frames, so the run must be
--independent (the oracle fed by waits) and starts from native power-on;
this reproduces a native session's point of failure in the original.

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

Two modes, named in the output.  The default is the *aligned* run: the
oracle is also the replay clock, so at a transition's checkpoints the
native frame counter takes the original's VBlank count, and each frame's
controller read takes the mask the original's read saw; this proves the
reconstructed operations under the original's timing.  --independent
detaches the clock after the seed: the native frame N reads pads(N) and
transitions spend no work time; the oracle only compares.  Divergences
in that mode are timing differences of the standalone policy or real
semantic ones, and the aligned run tells which.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from aladdin_sega.machine import Machine
from aladdin_sega.native import GameState, NativeGap, STEPS, run_frame


def main(frame, count, every=1, recording=None, independent=False, native_boot=False, native_history=False, store=None):
    rom = nr.read_rom()
    if native_history and not (independent and native_boot):
        sys.exit('--native-history needs --independent and --native-boot')
    pads = nr.masks(recording, store_path=store, native=native_history)
    first = frame
    m = Machine(rom); m.audio_policy('discard')
    start_step = None
    if native_boot:
        from aladdin_sega.native import boot
        from aladdin_sega.native.frame import NativeServices
        state = boot.power_on(rom)
        state.pads = lambda f: pads.get(f, 0)
        state.replay = None if independent else nr.OracleClock(state, m, pads)
        driver = nr.OracleDriver(m, pads, by_waits=independent, frame=0)
        driver.begin_frame(state.replay)
        if state.replay is not None:
            state.replay.begin_at(boot.GAME_INIT)
        try:
            start_step = boot.start(state, NativeServices(state))
            if state.replay is not None:
                state.replay.end()          # the original on to its first main-loop boundary; the clocks agree there
        except NativeGap as gap:
            print(f'boot: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
            return 1
        frame = state.frame
        print(f'{"independent" if independent else "aligned"} run from native power-on; the main loop starts at frame {frame}')
    elif recording is None:
        m.restore(nr.load(frame))
        state, frame = nr.seed_at_boundary(m, frame, pads, rom)
    else:
        state, frame = nr.seed_cold(m, pads, rom)
    if independent:
        state.replay = None
    if not native_boot:
        driver = nr.OracleDriver(m, pads, by_waits=independent, frame=frame)
        print(f'{"independent" if independent else "aligned"} run seeded at main-loop frame {frame}'
              + (f' of recording {recording}' if recording else ''))
    for i in range(count):
        f = state.frame
        # the independent driver's first run from reset passes the whole boot: its sound calls are the native
        # boot's events (the aligned clock compared those as it drove the boot)
        before = 0 if i == 0 and native_boot and independent else len(state.events)
        driver.begin_frame(state.replay)
        try:
            run_frame(state, start_step=start_step)
            start_step = None
        except NativeGap as gap:
            print(f'frame {f}: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
            return 1
        driver.run_frame(state.replay)
        if not independent:
            if state.frame > driver.frame:
                print(f'frame {f}: the native frame waited to {state.frame}, the original passed {driver.frame} VBlanks')
                m.close(); return 4
            state.advance_frames(driver.frame - state.frame)     # a loop iteration the original spent two VBlanks on
        native_sounds = [s for e in state.events[before:] for s in nr.native_sound_events([e], e[1])]
        if native_sounds != driver.sounds:
            print(f'frame {f}: sound events differ: native {native_sounds} oracle {driver.sounds}')
            m.close()
            return 4
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
    print(f'native matches the oracle for {count} frames to frame {state.frame} (events {len(state.events)})')
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
    from aladdin_sega.native.frame import NativeServices, ResumeFrame
    from aladdin_sega.native.oracle import run_to_exits, trace_port_writes
    m = Machine(rom); m.audio_policy('discard')
    if recording is None:
        m.restore(nr.load(first))
        state, frame = nr.seed_at_boundary(m, first, pads, rom)
    else:
        state, frame = nr.seed_cold(m, pads, rom)
    driver = nr.OracleDriver(m, pads, frame=frame)
    while state.frame < target:
        driver.begin_frame(state.replay)
        run_frame(state)
        driver.run_frame(state.replay)
        state.advance_frames(max(0, driver.frame - state.frame))
    m.gates(sorted({s.entry for s in STEPS} | {e for s in STEPS for e in s.exits} | {nr.VBLANK_HANDLER}))
    m.pad(pads.get(target, 0)); state.buttons = pads.get(target, 0)
    services = NativeServices(state)
    for step in STEPS:
        if m.info['pc'] != step.entry:
            run_to_exits(m, (step.entry,), m.info['tick'] + 3 * nr.FRAME_TICKS)
        m.gate(step.entry, bypass_once=True)
        try:
            step.run(state, services)
        except ResumeFrame:
            print(f'frame {target}: step {step.name} ran a transition that resumes the loop elsewhere; '
                  f'compare its checkpoints with verify_sequence.py')
            m.close(); return
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
    independent = '--independent' in argv
    native_boot = '--native-boot' in argv
    native_history = '--native-history' in argv
    store = None
    if '--store' in argv:
        i = argv.index('--store'); store = argv[i + 1]; del argv[i:i + 2]
    argv = [a for a in argv if a not in ('--independent', '--native-boot', '--native-history')]
    if '--every' in argv:
        i = argv.index('--every'); every = int(argv[i + 1]); del argv[i:i + 2]
    if '--cold' in argv:
        i = argv.index('--cold'); recording = argv[i + 1]; del argv[i:i + 2]
        sys.exit(main(0, int(argv[0]), every, recording=recording, independent=independent, native_boot=native_boot,
                      native_history=native_history, store=store))
    sys.exit(main(int(argv[0]), int(argv[1]), every, independent=independent))
