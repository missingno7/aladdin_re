"""Qualify recorded 1B6802 reverse-pool creation without a rebuild."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from aladdin_sega import artifacts
from aladdin_sega.boundary import SPAWN_REVERSE_CALLER_ENTRY
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import Candidate
from aladdin_sega.verification import compare_replay
from carrier_witness import original_exit
from recovery_witness import digest, fresh_short_replay


def run(fixture: Path, output: Path, *, entry: int | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    rom = read_rom(DEFAULT_ROM)
    with Machine(rom) as original:
        artifacts.restore_snapshot(original, fixture.read_bytes())
        registers = original.registers()
        entry = registers['pc'] if entry is None else entry
        if entry != SPAWN_REVERSE_CALLER_ENTRY or registers['pc'] != entry:
            raise ValueError('fixture must be parked at the recovered reverse spawn caller')
        sp = registers['a7']
        return_pc = int.from_bytes(original.peek_ram(sp & 0xffff, 4), 'big') & 0xffffff
        initial = artifacts.snapshot_bytes(original)
        recorder = artifacts.Recorder(original, origin='synthetic', reset_provenance='spawn-caller-witness')
        pcm = original_exit(original, return_pc, sp + 4)
        expected = original.snapshot(), original.frame()[2], pcm
        original.gates([])
        assert original.run(instructions=150) == 'limit'
        future = original.snapshot(), original.frame()[2], original.audio()
        witness = output / 'witness.alreplay'
        witness.write_bytes(recorder.finish(original))

    with Machine(rom) as candidate_machine:
        artifacts.restore_snapshot(candidate_machine, initial)
        candidate = Candidate('lifecycle')
        candidate.arm(candidate_machine)
        assert candidate_machine.run(instructions=1) == 'gate'
        started = time.perf_counter()
        assert candidate.on_gate(candidate_machine, candidate_machine.info['tick'] + FRAME_TICKS)
        actual = candidate_machine.snapshot(), candidate_machine.frame()[2], candidate_machine.audio()
        assert actual == expected
        safe = artifacts.snapshot_bytes(candidate_machine)
        (output / 'exit.alsnap').write_bytes(safe)
        elapsed = time.perf_counter() - started

    with Machine(rom) as suffix:
        artifacts.restore_snapshot(suffix, safe)
        recorder = artifacts.Recorder(suffix, origin='synthetic', reset_provenance='spawn-caller-safe-exit')
        suffix.gates([])
        assert suffix.run(instructions=150) == 'limit'
        assert (suffix.snapshot(), suffix.frame()[2], suffix.audio()) == future
        after = output / 'after.alreplay'
        after.write_bytes(recorder.finish(suffix))
    fresh_exit, _ = fresh_short_replay(after, DEFAULT_ROM, future)
    fresh, _ = fresh_short_replay(witness, DEFAULT_ROM, (future[0], future[1], pcm + future[2]))
    assert fresh_exit and fresh
    comparison = compare_replay(DEFAULT_ROM, witness, candidate='lifecycle', diagnostics=True,
                                output=output / 'comparison')
    assert comparison['status'] == 'PASS', comparison
    controls = {}
    for mutation in ('result', 'continuation', 'timing'):
        result = compare_replay(DEFAULT_ROM, witness, candidate='lifecycle-mutant-' + mutation,
                                diagnostics=True, output=output / ('mutant-' + mutation))
        assert result['status'] in ('DIVERGENCE', 'CANDIDATE_ERROR'), result
        controls[mutation] = result['status']
    report = {
        'status': 'PASS', 'fixture': str(fixture), 'entry': f'{entry:06X}',
        'outer_return': f'{return_pc:06X}', 'strict_exit': True,
        'native_future_instructions': 150, 'safe_restore': True,
        'fresh_process': fresh, 'fresh_exit_restore': fresh_exit,
        'candidate_stats': candidate.stats, 'controls': controls,
        'witness_sha256': digest(witness.read_bytes()), 'seconds': elapsed,
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--entry', type=lambda value: int(value, 16))
    args = parser.parse_args()
    run(args.fixture, args.output, entry=args.entry)
