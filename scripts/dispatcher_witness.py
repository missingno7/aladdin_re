"""Qualify the recovered 1ABC82 dispatcher against original execution."""
from __future__ import annotations

import json
import argparse
import time
from pathlib import Path

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import Candidate
from aladdin_sega.verification import compare_replay
from carrier_witness import original_exit
from recovery_witness import fresh_short_replay, digest


ROOT = Path("artifacts/dispatcher")
FIXTURE_DIR = ROOT / "recorded"
OUTPUT = ROOT / "witnesses"
ROM = read_rom(DEFAULT_ROM)
DISPATCH_PC = 0x1ABC82
CALLBACKS = (0x1AF3C2, 0x1AF468, 0x1AF4D8)


def run(fixture_dir=FIXTURE_DIR, output=OUTPUT, callbacks=CALLBACKS,
        scope="unmodified dispatcher checkpoints from user recording",
        recorded_dispatch_activations=None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for callback in callbacks:
        key = f"{callback:06X}"
        folder = output / key
        folder.mkdir(exist_ok=True)
        prepared = (fixture_dir / f"{key}.dispatcher.alsnap").read_bytes()
        with Machine(ROM) as original:
            artifacts.restore_snapshot(original, prepared)
            if original.info["pc"] != DISPATCH_PC:
                raise RuntimeError(f"{key}: fixture PC is not dispatcher")
            recorder = artifacts.Recorder(original, origin="synthetic",
                                          reset_provenance="dispatcher-witness")
            original.gates([callback, 0x1ABCA0])
            original.gate(DISPATCH_PC, bypass_once=True)
            if original.run(instructions=10000) != "gate":
                raise RuntimeError(f"{key}: original dispatcher did not reach callback")
            callback_registers = original.registers()
            return_pc = int.from_bytes(original.peek_ram(callback_registers["a7"] & 0xFFFF, 4), "big") & 0xFFFFFF
            pcm = original_exit(original, return_pc, callback_registers["a7"] + 4)
            expected = original.snapshot(), original.frame()[2], pcm
            exit_tick = original.info["tick"]
            original.gates([])
            original.run(instructions=150)
            future = original.snapshot(), original.frame()[2], original.audio()
            replay = folder / "witness.alreplay"
            replay.write_bytes(recorder.finish(original))

        with Machine(ROM) as candidate_machine:
            artifacts.restore_snapshot(candidate_machine, prepared)
            candidate = Candidate("lifecycle")
            candidate.arm(candidate_machine)
            if candidate_machine.run(instructions=1) != "gate":
                raise RuntimeError(f"{key}: candidate did not stop at dispatcher")
            started = time.perf_counter()
            if not candidate.on_gate(candidate_machine, candidate_machine.info["tick"] + FRAME_TICKS):
                raise RuntimeError(f"{key}: dispatcher candidate declined")
            actual = candidate_machine.snapshot(), candidate_machine.frame()[2], candidate_machine.audio()
            if actual != expected:
                raise AssertionError(f"{key}: dispatcher outer state mismatch")
            safe = artifacts.snapshot_bytes(candidate_machine)
            (folder / "exit.alsnap").write_bytes(safe)

        with Machine(ROM) as suffix:
            artifacts.restore_snapshot(suffix, safe)
            suffix_recorder = artifacts.Recorder(suffix, origin="synthetic",
                                                 reset_provenance="dispatcher-safe-exit")
            suffix.gates([])
            suffix.run(instructions=150)
            if (suffix.snapshot(), suffix.frame()[2], suffix.audio()) != future:
                raise AssertionError(f"{key}: safe-exit continuation mismatch")
            after = folder / "after.alreplay"
            after.write_bytes(suffix_recorder.finish(suffix))

        fresh_exit, _ = fresh_short_replay(after, DEFAULT_ROM, future)
        fresh, _ = fresh_short_replay(replay, DEFAULT_ROM, (future[0], future[1], pcm + future[2]))
        if not fresh_exit or not fresh:
            raise AssertionError(f"{key}: fresh-process replay failed")
        comparison = compare_replay(DEFAULT_ROM, replay, candidate="lifecycle",
                                    output=folder / "comparison")
        if comparison["status"] != "PASS":
            raise AssertionError(comparison)
        results[key] = {
            "status": "PASS",
            "dispatcher_entry": f"{DISPATCH_PC:06X}",
            "callback": key,
            "outer_return": f"{return_pc:06X}",
            "strict_exit": True,
            "native_future_instructions": 150,
            "safe_restore": True,
            "fresh_process": fresh,
            "fresh_exit_restore": fresh_exit,
            "candidate_stats": candidate.stats,
            "replay_sha256": digest(replay.read_bytes()),
            "seconds": time.perf_counter() - started,
        }
    report = {"status": "PASS", "scope": scope,
              "recorded_dispatch_activations": recorded_dispatch_activations,
              "results": results}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", type=Path, default=FIXTURE_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--entry", action="append", type=lambda value: int(value, 16))
    parser.add_argument("--scope", default="unmodified dispatcher checkpoints from user recording")
    parser.add_argument("--recorded-dispatch-activations", type=int)
    args = parser.parse_args()
    run(fixture_dir=args.fixture_dir, output=args.output,
        callbacks=tuple(args.entry) if args.entry else CALLBACKS,
        scope=args.scope,
        recorded_dispatch_activations=args.recorded_dispatch_activations)

