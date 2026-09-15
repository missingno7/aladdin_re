"""Run the lifecycle candidate over main and log every fallback with its frame and context."""
import json, os, sys, time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'src'))
os.environ.setdefault('ALADDIN_NATIVE_LIBRARY', 'D:/Prog/aladdin_re/build/libaladdin_native.dll')
from aladdin_sega.history import HistoryStore
from aladdin_sega.profile import read_rom
from aladdin_sega.history_runtime import GenesisRun
from aladdin_sega import recovery

out = sys.argv[1] if len(sys.argv) > 1 else 'D:/Prog/aladdin_re/artifacts/grinder/scratch/fallback_log.json'
limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
store = HistoryStore('D:/Prog/aladdin_re/history')
rom = read_rom()
log = []
orig = recovery.Candidate._fallback
current = {'run': None}


def hooked(self, machine, pc, reason):
    regs = machine.registers()
    run = current['run']
    a1 = regs['a1'] & 0xFFFFFF
    kind = machine.peek_ram(a1 & 0xFFFF, 1)[0] if 0xFF0000 <= a1 <= 0xFFFFFF else None
    log.append({'frame': run.frame, 'tick': machine.info['tick'],
                'gate': f"{(machine.info['pc'] if pc is None else pc):06X}",
                'live_pc': f"{regs['pc']:06X}", 'reason': reason,
                'a1': f'{a1:06X}', 'kind': kind, 'a7': f"{regs['a7'] & 0xFFFFFF:06X}",
                'a6': f"{regs['a6'] & 0xFFFFFF:06X}"})
    return orig(self, machine, pc, reason)


recovery.Candidate._fallback = hooked
path = store.flatten(store.resolve('main'))
end = path['end_frame'] if limit is None else min(limit, path['end_frame'])
started = time.time()
with GenesisRun(rom, 'lifecycle') as run:
    current['run'] = run
    events = [event for event in path['events'] if event['frame'] >= run.frame]
    run.advance(end, events, lambda r: None)
    stats = dict(run.candidate.stats)
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump({'frames': end, 'seconds': time.time() - started, 'fallbacks': stats['fallbacks'],
           'reasons': stats['fallback_reasons'], 'log': log}, open(out, 'w'), indent=1)
print('frames', end, 'fallbacks', stats['fallbacks'], 'logged', len(log), 'seconds', round(time.time() - started))
