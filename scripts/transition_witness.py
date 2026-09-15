"""Find the recording's transitions and time them coarsely (the per-checkpoint witness is verify_sequence.py --measure).

  transition_witness.py FRAME DIE_FRAME
  transition_witness.py FRAME --all [LAST_FRAME]

The oracle runs from artifacts/evidence/frames/fFRAME.state with the
recorded pads applied per VBlank until a transition entry (1A8F82: the
dying countdown ran out, 1A902E: fell below the level) is reached in
the main-loop frame DIE_FRAME.  It then counts the VBlank interrupts
already taken in that frame, the 1B249E waits the sequence makes (not
the main loop's own wait once it resumes), and the main-loop boundary
at which the loop resumes.  With --all every transition up to
LAST_FRAME (default: the end of the recording) is listed in turn; a
transition whose loop does not resume within 3,000 frames (a level
change, the game over) ends the scan.  The listing says which
transitions need a witness in native/witnesses.py.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from aladdin_sega.machine import Machine

ENTRIES = {0x1A8F82: 'life_lost', 0x1A902E: 'fell'}
WAIT = 0x1B249E
MAIN_LOOP_WAIT_RETURN = 0x1A8CD8


def main(start, die_frame=None, last_frame=None):
    rom = nr.read_rom(); pads = nr.masks()
    last_frame = last_frame or max(pads)
    m = Machine(rom); m.audio_policy('discard'); m.restore(nr.load(start))
    nr.seed_at_boundary(m, start, pads, rom)
    while True:
        entry = _run_to_entry(m, pads, die_frame, last_frame)
        if entry is None:
            break
        pc, boundary, f, interrupts = entry
        kind = ENTRIES[pc]
        print(f'{kind} at {pc:06X} in main-loop frame {boundary} (VBlank frame {f}), {interrupts} interrupts taken')
        entry = pc
        resumed = _measure(m, pc, pads, boundary)
        if resumed is None:
            print(f'    the main loop did not resume within 3,000 frames (a level change or the game over)')
            break
        f, waits = resumed
        print(f'the main loop resumes at boundary frame {f}: {waits} waits by the sequence, '
              f'{f - boundary - waits} frames of work; measure it with verify_sequence.py {start} {boundary} {entry:06X} --measure')
        if die_frame is not None:
            break
    m.close()


def _run_to_entry(m, pads, die_frame, last_frame):
    """The oracle to the next transition entry (in main-loop frame ``die_frame`` when given): (pc, boundary, f, interrupts)."""
    nr.arm(m, [nr.VBLANK_HANDLER, nr.FRAME_BOUNDARY, *ENTRIES])
    boundary, interrupts = None, 0
    while True:
        assert nr.run_with_pads(m, pads, m.info['tick'] + 3 * nr.FRAME_TICKS) == 'gate', 'the oracle stalled'
        pc, f = m.info['pc'], m.info['tick'] // nr.FRAME_TICKS
        if pc in ENTRIES and (die_frame is None or boundary == die_frame):
            return pc, boundary, f, interrupts
        m.gate(pc, bypass_once=True)
        if pc == nr.VBLANK_HANDLER:
            interrupts += 1
        elif pc == nr.FRAME_BOUNDARY and nr.at_main_loop_boundary(m):
            boundary, interrupts = f, 0
        if boundary is not None and (die_frame is not None and boundary > die_frame or boundary > last_frame):
            if die_frame is not None:
                sys.exit(f'no transition entry in frame {die_frame}')
            print(f'no further transition up to frame {last_frame}')
            return None


def _measure(m, pc, pads, boundary):
    """From the entry ``pc``: the sequence's own 1B249E waits and the boundary at which the main loop resumes."""
    m.gate(pc, bypass_once=True); nr.arm(m, [nr.VBLANK_HANDLER, nr.FRAME_BOUNDARY, WAIT])
    waits = 0
    while True:
        assert nr.run_with_pads(m, pads, m.info['tick'] + 3 * nr.FRAME_TICKS) == 'gate', 'the oracle stalled'
        pc, f = m.info['pc'], m.info['tick'] // nr.FRAME_TICKS
        if f - boundary > 3000:
            return None
        m.gate(pc, bypass_once=True)
        if pc == nr.VBLANK_HANDLER:
            pass
        elif pc == WAIT:
            sp = m.registers()['a7']
            if int.from_bytes(m.peek_ram(sp & 0xFFFF, 4), 'big') != MAIN_LOOP_WAIT_RETURN:
                waits += 1
        elif nr.at_main_loop_boundary(m):
            return f, waits


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--all' in sys.argv:
        main(int(args[0]), None, int(args[1]) if len(args) > 1 else None)
    else:
        main(int(args[0]), int(args[1]))
