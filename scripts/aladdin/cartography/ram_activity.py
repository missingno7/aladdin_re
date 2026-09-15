"""Replay the original over main; record per-frame RAM change activity, instruction counts, and periodic RAM snapshots."""
import json, os, sys, time
import numpy as np
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[3] / 'src'))
os.environ.setdefault('GENESIS_NATIVE_LIBRARY', 'D:/Prog/aladdin_re/build/libgenesis_native.dll')
from genesis_re.history import HistoryStore
from aladdin_sega.profile import read_rom
from genesis_re.history_runtime import GenesisRun
from aladdin_sega.profile import ALADDIN

out = 'D:/Prog/aladdin_re/artifacts/cartography'
os.makedirs(out, exist_ok=True)
store = HistoryStore('D:/Prog/aladdin_re/history/aladdin', ALADDIN.history_root)
rom = read_rom()
path = store.flatten(store.resolve('main'))
end = path['end_frame']
events = {e['frame']: e['buttons'] for e in path['events']}

change_counts = np.zeros(65536, dtype=np.uint32)      # how many frames each byte changed
page_changes = np.zeros((end + 1, 256), dtype=np.uint16)  # changed bytes per 256-byte page per frame
per_frame = np.zeros((end + 1, 4), dtype=np.uint64)   # instructions, cycles, changed bytes, buttons
snap_every = 32
snapshots = []
snap_frames = []
prev = None
last_info = None
started = time.time()


def observe(run):
    global prev, last_info
    m = run.machine
    ram = np.frombuffer(m.peek_ram(0, 65536), dtype=np.uint8)
    info = m.info
    f = run.frame
    if prev is not None:
        diff = ram != prev
        change_counts[diff] += 1
        page_changes[f] = diff.reshape(256, 256).sum(axis=1)
        per_frame[f, 2] = int(diff.sum())
    if last_info is not None:
        per_frame[f, 0] = info['m68k_instructions'] - last_info['m68k_instructions']
        per_frame[f, 1] = info['m68k_cycles'] - last_info['m68k_cycles']
    per_frame[f, 3] = info['buttons']
    if f % snap_every == 0:
        snapshots.append(ram.copy()); snap_frames.append(f)
    prev = ram.copy(); last_info = info
    if f % 5000 == 0:
        print('frame', f, round(time.time() - started), 's', flush=True)


with GenesisRun(ALADDIN, rom, 'original') as run:
    run.advance(end, [e for e in path['events'] if e['frame'] >= run.frame], observe)

np.savez_compressed(os.path.join(out, 'ram_activity.npz'), change_counts=change_counts,
                    page_changes=page_changes, per_frame=per_frame,
                    snapshots=np.stack(snapshots), snap_frames=np.array(snap_frames))
print('done frames', end, 'seconds', round(time.time() - started))
