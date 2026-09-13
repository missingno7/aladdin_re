"""Original-only census and entry fixtures for the adjacent collection family."""
from pathlib import Path
import json
import argparse
from collections import Counter

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import read_rom, DEFAULT_ROM, FRAME_TICKS

ENTRIES = (0x1AF21E, 0x1AF264, 0x1AF2B0, 0x1AF2FA, 0x1AF344,
           0x1AF384, 0x1AF3C2, 0x1AF400, 0x1AF468, 0x1AF4A0,
           0x1AF4D8, 0x1AF516, 0x1AF53E)


def run(out=Path('artifacts/lifecycle/census'), entries=ENTRIES,
        recording=Path('recordings/current/20260912T210640.729016Z.alreplay')):
    out.mkdir(parents=True, exist_ok=True)
    counts, first = Counter(), {}
    with Machine(read_rom(DEFAULT_ROM)) as m:
        meta, initial, events = artifacts.load_replay(recording.read_bytes(),
            rom_sha256=m.rom_sha256, state_version=m.state_version)
        artifacts.restore_snapshot(m, initial)
        m.gates(list(entries))
        def advance(target):
            while m.info['tick'] < target:
                reason = m.run(target=min(target, m.info['tick'] + FRAME_TICKS))
                m.audio()
                if reason == 'gate':
                    regs = m.registers(); pc = regs['pc']; key = f'{pc:06X}'
                    counts[key] += 1
                    if key not in first:
                        first[key] = {'registers': regs, 'info': m.info,
                            'record': m.peek_ram(regs['a1'] & 65535, 66).hex()}
                        (out / f'{key}.alsnap').write_bytes(artifacts.snapshot_bytes(m))
                    m.gate(pc, bypass_once=True)
        for event in events:
            advance(event['tick']); m.pad(event['buttons'])
        advance(meta['terminal_tick'])
        result = {'counts': dict(counts), 'first': first, 'terminal': m.info}
        (out / 'report.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'counts': dict(counts), 'terminal': m.info}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('artifacts/lifecycle/census'))
    parser.add_argument('--entry', type=lambda value: int(value, 16), action='append',
                        help='Hexadecimal original entry to census; repeat for multiple entries')
    parser.add_argument('--replay', type=Path,
                        default=Path('recordings/current/20260912T210640.729016Z.alreplay'))
    args = parser.parse_args()
    run(args.output, args.entry or ENTRIES, args.replay)
