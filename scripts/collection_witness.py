"""Recorded collection entries: strict exits, native future, portable fresh replay."""
from pathlib import Path
import json
import argparse
import time

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import Candidate
from aladdin_sega.verification import compare_replay
from carrier_witness import original_exit
from recovery_witness import fresh_short_replay, digest


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for pc in (0x1AF3C2, 0x1AF4D8, 0x1AF516):
        folder = output / f'{pc:06X}'; folder.mkdir(exist_ok=True)
        entry = Path(f'artifacts/lifecycle/census/{pc:06X}.alsnap').read_bytes()
        rom = read_rom(DEFAULT_ROM)
        with Machine(rom) as m:
            artifacts.restore_snapshot(m, entry)
            regs = m.registers(); sp = regs['a7']
            return_pc = int.from_bytes(m.peek_ram(sp & 65535, 4), 'big') & 0xffffff
            initial = m.snapshot()
            recorder = artifacts.Recorder(m, origin='synthetic', reset_provenance='collection-witness')
            pcm = original_exit(m, return_pc, sp+4)
            expected = m.snapshot(), m.frame()[2], pcm
            exit_tick = m.info['tick']
            m.gates([]); m.run(instructions=150)
            future = m.snapshot(), m.frame()[2], m.audio()
            replay = folder / 'witness.alreplay'
            replay.write_bytes(recorder.finish(m))
        with Machine(rom) as m:
            m.restore(initial)
            candidate = Candidate('lifecycle'); candidate.arm(m)
            assert m.run(instructions=1) == 'gate'
            start = time.perf_counter()
            assert candidate.on_gate(m, m.info['tick'] + FRAME_TICKS)
            actual = m.snapshot(), m.frame()[2], m.audio()
            assert actual == expected, (hex(pc), m.info, exit_tick, candidate.stats)
            safe = artifacts.snapshot_bytes(m)
            (folder/'exit.alsnap').write_bytes(safe)
        with Machine(rom) as m:
            artifacts.restore_snapshot(m, safe)
            suffix_recorder = artifacts.Recorder(m, origin='synthetic', reset_provenance='collection-safe-exit')
            m.gates([]); m.run(instructions=150)
            assert (m.snapshot(), m.frame()[2], m.audio()) == future
            suffix_replay = folder/'after.alreplay'
            suffix_replay.write_bytes(suffix_recorder.finish(m))
        fresh_exit, _ = fresh_short_replay(suffix_replay, DEFAULT_ROM, future)
        assert fresh_exit
        fresh, receipt = fresh_short_replay(replay, DEFAULT_ROM, (future[0], future[1], pcm+future[2]))
        assert fresh
        compare = compare_replay(DEFAULT_ROM, replay, candidate='lifecycle',
                                 output=folder/'comparison')
        assert compare['status'] == 'PASS'
        results[f'{pc:06X}'] = {'status': 'PASS', 'exit_tick': exit_tick,
            'strict_exit': True, 'native_future_instructions': 150,
            'safe_restore': True, 'fresh_process': fresh, 'fresh_exit_restore': fresh_exit, 'stats': candidate.stats,
            'replay_sha256': digest(replay.read_bytes()), 'seconds': time.perf_counter()-start}
    controls = {}
    focused = output/'1AF3C2'/'witness.alreplay'
    for mutation in ('result', 'continuation', 'timing'):
        name = 'lifecycle-mutant-'+mutation
        result = compare_replay(DEFAULT_ROM, focused, candidate=name,
            timeout_seconds=30, output=output/name)
        assert result['status'] in ('DIVERGENCE', 'CANDIDATE_ERROR'), result
        controls[mutation] = result['status']
    entry = Path('artifacts/lifecycle/census/1AF3C2.alsnap').read_bytes()
    with Machine(rom) as m:
        artifacts.restore_snapshot(m, entry)
        m.gates([0x1E57AC]); assert m.run(instructions=10000) == 'gate'
        deadline = m.info['tick']
    with Machine(rom) as m:
        artifacts.restore_snapshot(m, entry)
        inputs = artifacts.Recorder(m, origin='synthetic', reset_provenance='collection-sound-input')
        m.run(target=deadline); m.audio()
        inputs.apply_pad(m, m.info['buttons'] ^ 1)
        m.run(instructions=300); m.audio()
        input_replay = output/'input-deadline.alreplay'
        input_replay.write_bytes(inputs.finish(m))
    result = compare_replay(DEFAULT_ROM, input_replay, candidate='lifecycle',
        output=output/'input-deadline', diagnostics=True)
    assert result['status'] == 'PASS', result
    assert result['candidate_receipt']['candidate_stats']['legacy_deadline_fallbacks'] == 1
    controls['input_deadline'] = 'PASS'
    with Machine(rom) as m:
        artifacts.restore_snapshot(m, entry)
        candidate = Candidate('lifecycle'); candidate.arm(m); m.run(instructions=1)
        run_original = m.run
        def checked_run(**limits):
            if m.in_sound_call:
                try: artifacts.snapshot_bytes(m)
                except ValueError as error:
                    assert 'synchronous sound' in str(error)
                    controls['in_call_snapshot_rejected'] = True
                else: raise AssertionError('active sound snapshot was accepted')
            return run_original(**limits)
        m.run = checked_run
        candidate.on_gate(m, m.info['tick']+FRAME_TICKS)
    assert controls.get('in_call_snapshot_rejected')
    results['controls'] = controls
    (output/'report.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('artifacts/lifecycle/witnesses'))
    run(parser.parse_args().output)
