"""Strict qualification for an admitted, ordinary guest-return region.

This helper supports the three existing spawn witnesses only: saved return at
entry A7, final A7+4, one candidate admission, and no intervening input event.
It does not define gameplay domains or replace region-specific branch tests.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import Candidate
from aladdin_sega.verification import compare_replay
from aladdin_sega.receipt import execution_receipt
from aladdin_sega.machine import library_path
from carrier_witness import original_exit
from recovery_witness import digest, fresh_short_replay


def qualify_return_region(fixture: Path, output: Path, *, entries: tuple[int, ...],
                          provenance: str, entry: int | None = None) -> dict:
    native = Path(__file__).resolve().parents[1] / "build/libaladdin_native.dll"
    os.environ["ALADDIN_NATIVE_LIBRARY"] = str(native)
    if library_path().resolve() != native.resolve():
        raise RuntimeError("witness requires the build native library")
    receipt = execution_receipt(candidate="lifecycle")
    if receipt["native_binary_sha256"] != digest(native.read_bytes()):
        raise RuntimeError("native witness identity mismatch")
    output.mkdir(parents=True, exist_ok=True)
    rom = read_rom(DEFAULT_ROM)
    with Machine(rom) as original:
        artifacts.restore_snapshot(original, fixture.read_bytes())
        registers = original.registers()
        entry = registers['pc'] if entry is None else entry
        if entry not in entries or registers['pc'] != entry:
            raise ValueError('fixture PC must match an explicitly supported region entry')
        sp = registers['a7']
        return_pc = int.from_bytes(original.peek_ram(sp & 0xffff, 4), 'big') & 0xffffff
        initial = artifacts.snapshot_bytes(original)
        recorder = artifacts.Recorder(original, origin='synthetic', reset_provenance=provenance + '-witness')
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
        recorder = artifacts.Recorder(suffix, origin='synthetic', reset_provenance=provenance + '-safe-exit')
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
        'status': 'PASS', 'receipt': receipt, 'fixture': str(fixture), 'entry': f'{entry:06X}',
        'outer_return': f'{return_pc:06X}', 'strict_exit': True,
        'native_future_instructions': 150, 'safe_restore': True,
        'fresh_process': fresh, 'fresh_exit_restore': fresh_exit,
        'candidate_stats': candidate.stats, 'controls': controls,
        'witness_sha256': digest(witness.read_bytes()), 'seconds': elapsed,
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return report


def witness_cli(run, description):
    """Preserve the existing human/CI command shape for each concrete region."""
    import argparse
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--entry', type=lambda value: int(value, 16))
    args = parser.parse_args()
    run(args.fixture, args.output, entry=args.entry)
