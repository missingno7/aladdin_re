"""Compare a native transition sequence with the original at every one of its checkpoints.

  verify_sequence.py FRAME DIE_FRAME DIE_PC [--pad FROM-TO MASK ...] [--poke ADDR=BYTE ...]

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

--poke ADDR=BYTE writes one work-RAM byte on both sides at the seed
boundary (hex): a state the recording never reached, so a screen no
recording enters (the game over) is proved against the original from a
recorded route.  The perturbation is the witness's construction, never
the game's logic.

  verify_sequence.py 69586 75050 1A8F82                        # the life lost in level 5
  verify_sequence.py 69586 75050 1A8F82 --poke FF7E3F=00 --poke FF7E3C=30   # no continues, last life: game over
  verify_sequence.py 69586 75050 1A8F82 --pad 75346-75350 40   # A pressed at the earliest skip
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from genesis_re.machine import Machine
from aladdin_sega.native import NativeGap, run_frame


def known_checkpoints():
    """Every checkpoint pc the sequences can make (their source literals): the order contract's alphabet."""
    source = (Path(__file__).resolve().parents[1] / 'src' / 'aladdin_sega' / 'native' / 'sequences.py').read_text(encoding='utf-8')
    from aladdin_sega.native.sequences import PRINT_CHECKPOINTS
    return sorted({int(h, 16) for h in re.findall(r'checkpoint\(0x([0-9A-F]{6})\)', source)} | set(PRINT_CHECKPOINTS))


class ComparingClock(nr.OracleClock):
    """The oracle clock that also compares RAM at every checkpoint and requires the checkpoints in order.

    Where the plain clock drives the oracle to the requested pc alone, this one gates every checkpoint the
    sequences can make: the original reaching another one first is a route mismatch, not a rejoin.
    """

    def __init__(self, state, m, pads):
        super().__init__(state, m, pads)
        self.differences = None
        self.entry = None
        self.parked_at = None
        self.alphabet = known_checkpoints()

    def begin(self, kind):
        super().begin(kind)
        self.entry = nr.TRANSITION_ENTRIES[kind]

    def checkpoint(self, pc):
        # the native gate set is capped at 64 (native/machine.cpp); the alphabet has outgrown that, so the
        # route-mismatch net is the closest 59 other checkpoints rather than all of them (pc itself, plus the
        # platform sound/VBlank gates _run_to always adds, still make the checkpoint itself exact)
        room = 64 - 1 - 3 - len(nr.SOUND_COMMAND_GATES)         # pc, the VBlank handler, request, flush, the commands
        others = sorted((c for c in self.alphabet if c != pc), key=lambda c: abs(c - pc))[:room]
        if self.m.info['pc'] == pc and self.parked_at != pc:        # the clock's entry already parked the oracle here
            reached = pc
        else:
            reached = self._run_to((pc, *others), self.m.info['tick'] + nr.TRANSITION_LIMIT)
        self.parked_at = pc
        if reached != pc:
            where = f'{reached:06X}' if reached is not None else 'no checkpoint within the limit'
            raise nr.ReplayMismatch('checkpoint', pc, f'the original reached {where} where the sequence reached {pc:06X}',
                                    self.state.frame)
        self._align(pc)
        oracle = self.m.peek_ram(0, 65536)
        native = self.state.ram
        diff = [a for a in range(65536) if oracle[a] != native[a]
                and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in nr.BOOKKEEPING)]
        print(f'{pc:06X}: frame {self.state.frame}: {len(diff)} bytes differ')
        if diff and self.differences is None:
            self.differences = (pc, diff, bytes(native), oracle)
            _report(diff, native, oracle)


def verify_boot(recording=None, overrides=()):
    """The native power-on against the original from reset, at every checkpoint of the boot sequence."""
    from aladdin_sega.native import boot
    from aladdin_sega.native.frame import NativeServices
    rom = nr.read_rom(); pads = dict(nr.masks(recording))
    for lo, hi, mask in overrides:
        for f in range(lo, hi):
            pads[f] = mask
    m = Machine(rom); m.audio_policy('discard')
    state = boot.power_on(rom)
    state.pads = lambda f: pads.get(f, 0)
    clock = ComparingClock(state, m, pads)
    state.replay = clock
    clock.begin_at(boot.GAME_INIT)
    status = 0
    try:
        step = boot.start(state, NativeServices(state))
        if clock.differences:
            print(f'the boot reached the main loop at frame {state.frame} ({step}) with differences (above)')
        else:
            print(f'the boot matches the original at every checkpoint; the main loop starts at frame {state.frame} ({step})')
    except NativeGap as gap:
        print(f'native: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
        status = 4
    if clock.differences:
        status = 3
    m.close(); return status


def poke(m, state, pokes):
    """Equal work-RAM bytes on both sides, at the seed boundary (the original's through an atomic write)."""
    if not pokes:
        return
    pc = m.info['pc']
    m.gates([pc])
    assert m.run(instructions=1) == 'gate'
    assert m.atomic(target=m.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=pc,
                    writes=list(pokes), registers=m.registers())
    for address, value in pokes:
        state.write(address, value, 1)
    print('poked on both sides: ' + ', '.join(f'{a:06X}={v:02X}' for a, v in pokes))


def main(start, die_frame, die_pc, overrides=(), pokes=()):
    rom = nr.read_rom(); pads = dict(nr.masks())
    for lo, hi, mask in overrides:
        for f in range(lo, hi):
            pads[f] = mask
    m = Machine(rom); m.audio_policy('discard'); m.restore(nr.load(start))
    state, frame = nr.seed_at_boundary(m, start, pads, rom)
    poke(m, state, pokes)
    while state.frame < die_frame - 2:
        run_frame(state)
        nr.run_oracle_frame(m, pads, state.replay)
    clock = ComparingClock(state, m, pads)
    state.replay = clock
    status = 0
    started = False
    try:
        while state.frame <= die_frame + 2 and not started:       # the native frame count may sit a frame off
            frame = state.frame                                    # the tick count after an earlier transition
            run_frame(state)
            started = clock.consumed
            if not started:
                nr.run_oracle_frame(m, pads, state.replay)
    except NativeGap as gap:
        print(f'native: NativeGap at {gap.step} ({gap.pc:06X}): {gap.detail}')
        status = 4
        started = clock.entry is not None
    if started:
        print(f'the transition started in native frame {frame}')
    if not started and status == 0:
        print(f'no transition started in frames {die_frame - 2}..{die_frame + 2}')
        status = 2
    elif clock.entry != die_pc and status == 0:
        print(f'the transition entered at {clock.entry:06X}, not {die_pc:06X}')
        status = 2
    elif clock.differences:
        status = 3
    elif status == 0:
        nr.run_oracle_frame(m, pads, clock)          # both at the resumed frame's boundary
        oracle = m.peek_ram(0, 65536)
        diff = [a for a in range(65536) if oracle[a] != state.ram[a]
                and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in nr.BOOKKEEPING)]
        print(f'resumed main-loop frame {state.frame}: {len(diff)} bytes differ')
        if diff:
            _report(diff, state.ram, oracle); status = 3
        else:
            print('the sequence matches the original at every checkpoint and at the resumed frame boundary')
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
    overrides = []; pokes = []
    while '--poke' in argv:
        i = argv.index('--poke')
        address, value = argv[i + 1].split('=')
        pokes.append((int(address, 16), int(value, 16)))
        del argv[i:i + 2]
    while '--pad' in argv:
        i = argv.index('--pad')
        lo, hi = argv[i + 1].split('-')
        overrides.append((int(lo), int(hi), int(argv[i + 2], 16)))
        del argv[i:i + 3]
    if '--boot' in argv:
        i = argv.index('--boot')
        recording = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith('--') else None
        sys.exit(verify_boot(recording, overrides))
    args = [a for a in argv if not a.startswith('--')]
    sys.exit(main(int(args[0]), int(args[1]), int(args[2], 16), overrides=overrides, pokes=pokes))
