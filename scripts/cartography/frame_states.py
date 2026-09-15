"""Save original-machine snapshots at chosen frames of main into artifacts/evidence/frames.

usage: frame_states.py 1000,8500,...   (regenerable evidence; never committed)
"""
import os, sys
from pathlib import Path
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'src'))
os.environ.setdefault('ALADDIN_NATIVE_LIBRARY', str(root / 'build' / 'libaladdin_native.dll'))
from aladdin_sega.history import HistoryStore
from aladdin_sega.profile import read_rom
from aladdin_sega.history_runtime import GenesisRun

out = root / 'artifacts' / 'evidence' / 'frames'
out.mkdir(parents=True, exist_ok=True)
frames = sorted(int(x) for x in sys.argv[1].split(','))
store = HistoryStore(str(root / 'history')); rom = read_rom()
path = store.flatten(store.resolve('main')); events = path['events']
with GenesisRun(rom, 'original') as run:
    for f in frames:
        run.advance(f, [e for e in events if e['frame'] >= run.frame], lambda r: None)
        (out / f'f{f}.state').write_bytes(run.machine.snapshot())
        print('saved', f, flush=True)
(out / 'history_id').write_text(store.resolve('main'))
