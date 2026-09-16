"""vp_timing_probe: how long does the original take per frame; where exactly is the VBlank instant."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_common
vp_common.guard_paths()
from genesis_re.history_runtime import GenesisRun
from genesis_re.history import HistoryStore
from genesis_re.machine import Machine
game = vp_common.gods_profile()
rom = game.read_rom()
store = HistoryStore(game.history_path(), game.history_root)
path = store.flatten(store.resolve('f0ac19738f19'))
n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
t0 = time.perf_counter()
with GenesisRun(game, rom, 'original') as run:
    run.advance(n, path['events'], lambda r: r.observable())
dt = time.perf_counter() - t0
print('original %d frames in %.1f s (%.1f frames/s) -> full tree 107,519 frames ~ %.0f s' % (n, dt, n / dt, 107519 / (n / dt)))
