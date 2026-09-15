"""Drive the replay through the native runtime, or verify each recovered step against the oracle.

  native_replay.py --native  FRAME [COUNT]   seed from artifacts/evidence/frames/fFRAME.state and run natively;
                                             stops with a NativeGap report at the first unrecovered step
  native_replay.py --verify  FRAME [COUNT]   the oracle runs the frames; at every recovered step the semantic
                                             component runs over a copy of the oracle's state and is compared

The verify mode is the recovery loop: an unrecovered step is listed by
name and entry address in main-loop order; a recovered step is proven or
its mismatching fields are named.
"""
import os, sys, collections
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
os.environ.setdefault('ALADDIN_NATIVE_LIBRARY', str(root / 'build' / 'libaladdin_native.dll'))
from aladdin_sega.profile import read_rom
from aladdin_sega.machine import Machine
from aladdin_sega.native import GameState, NativeGap, STEPS, run_frame
from aladdin_sega.native.frame import NativeServices
from aladdin_sega.game.objects.record import RECORD_TABLE, FIELDS
from aladdin_sega.history import HistoryStore
FRAME_TICKS = 896040

BOOKKEEPING = ((0xFF769A, 0xFF7800, 'DMA queue'), (0xFFEF80, 0xFFEFE0, 'stack'),
               (0xFF7D9A, 0xFF7DA3, 'continuations'), (0xFFEFEE, 0xFFEFF0, 'queue counters'))


def field_name(address):
    if RECORD_TABLE <= address < RECORD_TABLE + 32 * 66:
        slot, off = divmod(address - RECORD_TABLE, 66)
        for name, (o, size, _) in FIELDS.items():
            if o <= off < o + size:
                return f'slot{slot}.{name}'
        return f'slot{slot}+{off:02X}'
    return f'{address:06X}'


def masks():
    """Recorded pad mask per frame (the history's events, held until the next event)."""
    store = HistoryStore(str(root / 'history')); path = store.flatten(store.resolve('main'))
    out = {}; current = 0; events = sorted(path['events'], key=lambda e: e['frame'])
    i = 0
    for f in range(path['end_frame'] + 1):
        while i < len(events) and events[i]['frame'] <= f:
            current = events[i]['buttons']; i += 1
        out[f] = current
    return out


def load(frame):
    path = root / 'artifacts' / 'evidence' / 'frames' / f'f{frame}.state'
    if not path.exists():
        sys.exit(f'no snapshot {path}; run scripts/cartography/frame_states.py {frame}')
    return path.read_bytes()


def native(frame, count):
    rom = read_rom()
    m = Machine(rom); m.restore(load(frame))
    state = GameState.from_machine(m, frame, rom); m.close()
    pads = masks()
    try:
        for _ in range(count):
            run_frame(state, pads.get(state.frame, 0))
    except NativeGap as gap:
        done = [s.name for s in STEPS[:[s.name for s in STEPS].index(gap.step)]] if gap.step in [s.name for s in STEPS] else []
        print(f'NativeGap: frame {gap.frame}, step "{gap.step}" at {gap.pc:06X}: {gap.detail}')
        print(f'  steps executed natively this frame: {done}')
        print(f'  events so far: {len(state.events)}')
        return 1
    print('native replay completed', count, 'frames; events', len(state.events))
    return 0


def verify(frame, count):
    rom = read_rom()
    m = Machine(rom); m.restore(load(frame))
    entries = {s.entry: s for s in STEPS}
    results = collections.Counter(); mismatches = collections.defaultdict(collections.Counter)
    m.gates([s.entry for s in STEPS if s.run is not None] + [e for s in STEPS if s.run for e in s.exits])
    frames_done = 0; recovered_entries = {s.entry for s in STEPS if s.run is not None}
    tick_end = m.info['tick'] + count * FRAME_TICKS
    pads = masks(); padded = -1
    while m.info['tick'] < tick_end:
        current_frame = m.info['tick'] // FRAME_TICKS
        if current_frame != padded:
            m.pad(pads.get(current_frame, 0)); padded = current_frame
        if m.run(target=min(tick_end, (current_frame + 1) * FRAME_TICKS)) != 'gate':
            continue
        pc = m.info['pc']
        step = entries.get(pc)
        if step is None or step.run is None:
            m.gate(pc, bypass_once=True); continue
        before = bytearray(m.peek_ram(0, 65536))
        m.gate(pc, bypass_once=True)
        assert m.run(target=tick_end + 896040) == 'gate' and m.info['pc'] in step.exits, f'{step.name} exit not reached'
        after = m.peek_ram(0, 65536)
        state = GameState(bytearray(before), rom, current_frame); state.buttons = pads.get(current_frame, 0)
        try:
            step.run(state, NativeServices(state))
        except NativeGap as gap:
            results[f'{step.name}: gap {gap.step}'] += 1
            m.gate(m.info['pc'], bypass_once=True); continue
        bad = 0
        for a in range(65536):
            if after[a] != state.ram[a] and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in BOOKKEEPING):
                mismatches[step.name][field_name(0xFF0000 | a)] += 1; bad += 1
        results[f'{step.name}: {"ok" if not bad else "mismatch"}'] += 1
        m.gate(m.info['pc'], bypass_once=True)
    m.close()
    print('verified passes:', dict(results))
    for name, fields in mismatches.items():
        print(' ', name, 'mismatching fields:', dict(fields.most_common(10)))
    print('unrecovered steps, in main-loop order:')
    for s in STEPS:
        if s.run is None:
            print(f'  {s.entry:06X} {s.name}  {s.note}')
    return 0


if __name__ == '__main__':
    mode, frame = sys.argv[1], int(sys.argv[2])
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    sys.exit(native(frame, count) if mode == '--native' else verify(frame, count))
