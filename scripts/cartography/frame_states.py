"""Save original-machine snapshots at chosen frames of main into artifacts/evidence/frames.

usage: frame_states.py 1000,8500,... [RECORDING]   (regenerable evidence; never committed)

Every snapshot in the directory must come from the one recording named in
its history_id: regenerate the whole set together, never a subset.
"""
import os, sys
from pathlib import Path
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'src'))
os.environ.setdefault('GENESIS_NATIVE_LIBRARY', str(root / 'build' / 'libgenesis_native.dll'))
from genesis_re.history import HistoryStore
from aladdin_sega.profile import read_rom
from genesis_re.history_runtime import GenesisRun
from aladdin_sega.profile import ALADDIN

out = root / 'artifacts' / 'evidence' / 'frames'
out.mkdir(parents=True, exist_ok=True)
frames = sorted(int(x) for x in sys.argv[1].split(','))
store = HistoryStore(str(root / 'history' / 'aladdin'), ALADDIN.history_root); rom = read_rom()
recording = store.resolve(sys.argv[2] if len(sys.argv) > 2 else 'main')     # resolved once; written below
path = store.flatten(recording); events = path['events']
print('recording', recording)
with GenesisRun(ALADDIN, rom, 'original') as run:
    for f in frames:
        run.advance(f, [e for e in events if e['frame'] >= run.frame], lambda r: None)
        (out / f'f{f}.state').write_bytes(run.machine.snapshot())
        print('saved', f, flush=True)
(out / 'history_id').write_text(recording)
