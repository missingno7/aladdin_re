"""Pad, HUD and player steps proven against the original at their own boundaries."""
import glob, os
from pathlib import Path
import pytest
from aladdin_sega.profile import read_rom
from aladdin_sega.game import pad, hud
from aladdin_sega.native import GameState, STEPS, NativeGap
from aladdin_sega.native.frame import NativeServices
from aladdin_sega.native.oracle import trace_port_writes, run_to_exits

ROOT = Path(__file__).resolve().parents[1]
FRAMES = sorted(glob.glob(str(ROOT / 'artifacts' / 'evidence' / 'frames' / 'f*.state')),
                key=lambda p: int(os.path.basename(p)[1:-6]))
rom = read_rom()
RECOVERED = [s for s in STEPS if s.run is not None and s.name not in ('object_animation', 'object_motion')]


def test_pad_bytes_follow_the_active_low_port_reads():
    assert pad.raw_bytes(0) == (0x7F, 0x33)
    assert pad.raw_bytes(0x08) == (0x77, 0x33)          # right
    assert pad.raw_bytes(0x01) == (0x7E, 0x32)          # up mirrors into the TH-low byte
    assert pad.raw_bytes(0x40) == (0x7F, 0x23)          # A
    assert pad.raw_bytes(0x30) == (0x4F, 0x33)          # B + C


def _ram():
    ram = bytearray(65536)
    read = lambda a, n: int.from_bytes(ram[a & 0xFFFF:(a & 0xFFFF) + n], 'big')

    def write(a, v, n):
        ram[a & 0xFFFF:(a & 0xFFFF) + n] = v.to_bytes(n, 'big')
    return ram, read, write


def test_score_tally_moves_one_unit_with_carry_and_awards_the_extra_life():
    ram, read, write = _ram()
    for i, c in enumerate(b'00990'):
        write(hud.SCORE_DIGITS + i, c, 1)
    write(hud.PENDING_POINTS, 2, 2); write(hud.DIFFICULTY, 1, 1); write(hud.LIVES, 0x33, 1)
    hud.score_tally(read, write, lambda s: None)
    assert bytes(ram[0x7E2A:0x7E2F]) == b'01000' and read(hud.PENDING_POINTS, 2) == 1
    write(hud.FRAME_COUNTER, 1, 1); hud.score_tally(read, write, lambda s: None)
    assert bytes(ram[0x7E2A:0x7E2F]) == b'01000'         # odd frames do not tally
    write(hud.EXTRA_LIFE_PROGRESS, 0x1D4B, 2); write(hud.FRAME_COUNTER, 0, 1); write(hud.SOUND_ENABLED, 1, 1)
    sounds = []; hud.score_tally(read, write, sounds.append)
    assert read(hud.LIVES, 1) == 0x34 and sounds == [0x66] and read(hud.EXTRA_LIFE_PROGRESS, 2) == 0


@pytest.mark.skipif(not FRAMES, reason='no recorded frame states under artifacts/evidence/frames')
@pytest.mark.parametrize('path', FRAMES[:6], ids=[os.path.basename(p)[:-6] for p in FRAMES[:6]])
def test_recovered_frame_steps_match_the_original(path):
    """Each RAM-only step reproduces the original's writes at its exit during two frames of play."""
    from aladdin_sega.machine import Machine
    m = Machine(rom); m.restore(Path(path).read_bytes())
    try:
        entries = {s.entry: s for s in RECOVERED}
        m.gates(sorted({s.entry for s in RECOVERED} | {e for s in RECOVERED for e in s.exits}))
        checked = set(); gaps = []; tick_end = m.info['tick'] + 2 * 896040
        while m.info['tick'] < tick_end:
            if m.run(target=tick_end) != 'gate':
                break
            step = entries.get(m.info['pc'])
            if step is None:
                m.gate(m.info['pc'], bypass_once=True); continue
            before = bytearray(m.peek_ram(0, 65536)); m.gate(step.entry, bypass_once=True)
            try:
                traced = trace_port_writes(m, step.exits) if step.ports else None
                if not step.ports:
                    run_to_exits(m, step.exits, tick_end + 896040)
            except RuntimeError:
                break                       # entered from outside the main loop (a loading loop): not bracketed
            after = m.peek_ram(0, 65536)
            state = GameState(bytearray(before), rom, 0); state.buttons = m.info['buttons']
            try:
                step.run(state, NativeServices(state))
            except NativeGap as gap:
                gaps.append(str(gap)); m.gate(m.info['pc'], bypass_once=True); continue
            diff = [f'{0xFF0000 | a:06X}' for a in range(65536)
                    if after[a] != state.ram[a] and not 0xFFEF40 <= 0xFF0000 | a < 0xFFEFE0]
            assert diff == [], (step.name, diff)
            if step.ports:
                assert state.vdp.log == traced, (step.name, 'VDP port words differ')
            checked.add(step.name); m.gate(m.info['pc'], bypass_once=True)
        if not checked:
            pytest.skip('no recovered step is reached in these two frames (a loading or card loop)'
                        + (f'; declared gaps: {gaps}' if gaps else ''))
    finally:
        m.close()
