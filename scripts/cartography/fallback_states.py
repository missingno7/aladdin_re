"""Rerun the lifecycle candidate and save one gate-time snapshot per (reason, frame) fallback."""
import json, os, re, sys, time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'src'))
os.environ.setdefault('GENESIS_NATIVE_LIBRARY', 'D:/Prog/aladdin_re/build/libgenesis_native.dll')
from genesis_re.history import HistoryStore
from aladdin_sega.profile import read_rom
from genesis_re.history_runtime import GenesisRun
from aladdin_sega import recovery
from aladdin_sega.profile import ALADDIN

out_dir = 'D:/Prog/aladdin_re/artifacts/grinder/scratch/fb'
os.makedirs(out_dir, exist_ok=True)
WANT = ('type1f', 'sibling', 'reset is outside', 'type44', 'type2c', '1B6D1E', '1B6C5A',
        'cannot batch', 'type03', 'type15', 'type7E')
store = HistoryStore('D:/Prog/aladdin_re/history/aladdin', ALADDIN.history_root)
rom = read_rom()
orig = recovery.Candidate._fallback
current = {'run': None}
seen = set()
index = []


def hooked(self, machine, pc, reason):
    run = current['run']
    tag = next((w for w in WANT if w in reason), None)
    key = (reason, run.frame)
    if tag and key not in seen:
        seen.add(key)
        regs = machine.registers()
        gate = machine.info['pc'] if pc is None else pc
        slug = re.sub(r'[^A-Za-z0-9]+', '-', tag).strip('-')
        name = f'{slug}-f{run.frame}-g{gate:06X}'
        with open(os.path.join(out_dir, name + '.state'), 'wb') as f:
            f.write(machine.snapshot())
        index.append({'name': name, 'reason': reason, 'frame': run.frame, 'gate': f'{gate:06X}',
                      'a1': f"{regs['a1'] & 0xFFFFFF:06X}", 'a7': f"{regs['a7'] & 0xFFFFFF:06X}"})
    return orig(self, machine, pc, reason)


recovery.Candidate._fallback = hooked
path = store.flatten(store.resolve('main'))
started = time.time()
with GenesisRun(ALADDIN, rom, 'lifecycle') as run:
    current['run'] = run
    events = [event for event in path['events'] if event['frame'] >= run.frame]
    run.advance(path['end_frame'], events, lambda r: None)
json.dump(index, open(os.path.join(out_dir, 'index.json'), 'w'), indent=1)
print('saved', len(index), 'states in', round(time.time() - started), 's')
