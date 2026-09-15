"""Compare a native transition sequence with the original at every checkpoint.

  verify_sequence.py FRAME DIE_FRAME DIE_PC

Both sides start from artifacts/evidence/frames/fFRAME.state.  The native
runtime runs to the frame DIE_FRAME in which the transition starts and
records its whole work RAM at every ``services.checkpoint(pc)`` the
sequence makes; the oracle is then run from the transition's entry
DIE_PC (with the recorded pads applied per VBlank) to each of those pcs
in turn and its RAM is compared, bookkeeping regions excluded.  The
first checkpoint that differs is reported with the fields involved.

  verify_sequence.py 69586 75278 1A8F82      # the life lost in level 5
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from aladdin_sega.machine import Machine
from aladdin_sega.native import NativeGap, run_frame
from aladdin_sega.native.frame import NativeServices


def main(start, die_frame, die_pc):
    rom = nr.read_rom(); pads = nr.masks()
    m = Machine(rom); m.audio_policy('discard'); m.restore(nr.load(start))
    state, frame = nr.seed_at_boundary(m, start, pads, rom)
    while state.frame < die_frame:
        run_frame(state)
    snapshots = []
    NativeServices.checkpoint = lambda self, pc: snapshots.append((pc, bytes(state.ram), state.frame))
    try:
        run_frame(state)
    except NativeGap as gap:
        print(f'native: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
    print('native checkpoints:', ' '.join(f'{pc:06X}' for pc, _, _ in snapshots))
    _run_to_entry(m, die_pc, die_frame, pads)
    m.gate(die_pc, bypass_once=True)
    for pc, native, native_frame in snapshots:
        f = _run_to(m, pc, pads)
        oracle = m.peek_ram(0, 65536)
        diff = [a for a in range(65536) if oracle[a] != native[a]
                and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in nr.BOOKKEEPING)]
        print(f'{pc:06X}: oracle VBlank frame {f}, native frame {native_frame}: {len(diff)} bytes differ')
        if diff:
            _report(diff, native, oracle)
            m.close(); return 3
    print('the sequence matches the original at every checkpoint')
    m.close(); return 0


def _run_to_entry(m, pc, die_frame, pads):
    """The oracle to the transition entry ``pc`` reached from the main-loop frame ``die_frame`` (not an earlier one)."""
    m.gates([nr.VBLANK_HANDLER, nr.FRAME_BOUNDARY, pc])
    boundary = None
    while True:
        if m.run(target=m.info['tick'] + 3 * nr.FRAME_TICKS) != 'gate':
            sys.exit(f'the oracle did not reach {pc:06X}')
        here, f = m.info['pc'], m.info['tick'] // nr.FRAME_TICKS
        if here == pc and boundary == die_frame:
            return
        m.gate(here, bypass_once=True)
        if here == nr.VBLANK_HANDLER:
            m.pad(pads.get(f, 0))
        elif here == nr.FRAME_BOUNDARY and nr.at_main_loop_boundary(m):
            boundary = f
            if boundary > die_frame:
                sys.exit(f'no {pc:06X} entry in main-loop frame {die_frame}')


def _run_to(m, pc, pads):
    m.gates([nr.VBLANK_HANDLER, pc])
    while True:
        if m.run(target=m.info['tick'] + 3 * nr.FRAME_TICKS) != 'gate':
            sys.exit(f'the oracle did not reach {pc:06X}')
        here, f = m.info['pc'], m.info['tick'] // nr.FRAME_TICKS
        m.gate(here, bypass_once=True)
        if here == nr.VBLANK_HANDLER:
            m.pad(pads.get(f, 0)); continue
        return f


def _report(diff, native, oracle, limit=16):
    ranges = []
    for a in diff:
        if ranges and a - ranges[-1][1] <= 4:
            ranges[-1][1] = a
        else:
            ranges.append([a, a])
    for lo, hi in ranges[:limit]:
        print(f'   {0xFF0000 | lo:06X}-{0xFF0000 | hi:06X} ({hi - lo + 1}) {nr.field_name(0xFF0000 | lo)}: '
              f'native {native[lo:lo + 10].hex()} oracle {oracle[lo:lo + 10].hex()}')


if __name__ == '__main__':
    sys.exit(main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3], 16)))
