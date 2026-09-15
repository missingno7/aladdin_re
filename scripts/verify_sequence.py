"""Compare a native transition sequence with the original at every one of its checkpoints.

  verify_sequence.py FRAME DIE_FRAME DIE_PC [--pad FROM-TO MASK ...]

Both sides start from artifacts/evidence/frames/fFRAME.state and run to
the main-loop frame DIE_FRAME in which the transition starts (DIE_PC:
1A8F82 the dying countdown ran out, 1A902E fell below the level).  The
oracle is the replay clock of the native run (scripts/native_replay
.OracleClock): at every ``services.checkpoint(pc)`` the sequence makes,
the oracle is driven to ``pc``, the native frame counter takes its
VBlank count, and the whole work RAM of both is compared there
(bookkeeping regions excluded).  The first checkpoint that differs is
reported with the fields involved; a checkpoint the original does not
reach next is a ReplayMismatch.

--pad FROM-TO MASK replaces the recorded pad with MASK (hex; bits up 1,
down 2, left 4, right 8, B 10, C 20, A 40, Start 80) on the frames FROM
up to TO on both sides: an input the recording never made, so a
sequence is proved on routes and timings the recording did not take.

  verify_sequence.py 69586 75278 1A8F82                        # the life lost in level 5
  verify_sequence.py 69586 75278 1A8F82 --pad 75346-75350 40   # A pressed at the earliest skip
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from aladdin_sega.machine import Machine
from aladdin_sega.native import NativeGap, run_frame
from aladdin_sega.native.frame import NativeServices


class ComparingClock(nr.OracleClock):
    """The oracle clock that also compares RAM at every checkpoint."""

    def __init__(self, state, m, pads):
        super().__init__(state, m, pads)
        self.differences = None

    def checkpoint(self, pc):
        super().checkpoint(pc)
        oracle = self.m.peek_ram(0, 65536)
        native = self.state.ram
        diff = [a for a in range(65536) if oracle[a] != native[a]
                and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in nr.BOOKKEEPING)]
        print(f'{pc:06X}: frame {self.state.frame}: {len(diff)} bytes differ')
        if diff and self.differences is None:
            self.differences = (pc, diff, bytes(native), oracle)
            _report(diff, native, oracle)


def main(start, die_frame, die_pc, overrides=()):
    rom = nr.read_rom(); pads = dict(nr.masks())
    for lo, hi, mask in overrides:
        for f in range(lo, hi):
            pads[f] = mask
    m = Machine(rom); m.audio_policy('discard'); m.restore(nr.load(start))
    state, frame = nr.seed_at_boundary(m, start, pads, rom)
    while state.frame < die_frame:
        run_frame(state)
        nr.run_oracle_frame(m, pads, state.replay)
    clock = ComparingClock(state, m, pads)
    state.replay = clock
    status = 0
    try:
        run_frame(state)
    except NativeGap as gap:
        print(f'native: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
        status = 4
    if not clock.consumed and status == 0:
        print(f'no transition started in frame {die_frame}')
        status = 2
    elif clock.differences:
        status = 3
    elif status == 0:
        print(f'the sequence matches the original at every checkpoint; the main loop resumes at frame {state.frame}')
    m.close(); return status


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
    argv = sys.argv[1:]
    overrides = []
    while '--pad' in argv:
        i = argv.index('--pad')
        lo, hi = argv[i + 1].split('-')
        overrides.append((int(lo), int(hi), int(argv[i + 2], 16)))
        del argv[i:i + 3]
    args = [a for a in argv if not a.startswith('--')]
    sys.exit(main(int(args[0]), int(args[1]), int(args[2], 16), overrides=overrides))
