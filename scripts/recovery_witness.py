"""Qualify one stopped recovery activation against original 68000 execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from aladdin_sega import artifacts
from aladdin_sega.recovered import (CALLER_ENTRY, PAIR_ENTRY, LEAF_ENTRY,
                                    clear_auxiliary_buffer, clear_object_pair, detach_object)
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.receipt import execution_receipt


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDING = ROOT / "recordings" / "current" / "20260912T210640.729016Z.alreplay"


def reach_gate(machine, events):
    """Replay input only until the already-armed candidate gate is reached."""
    for event in events:
        while machine.info["tick"] < event["tick"]:
            current = machine.info["tick"]
            deadline = min(event["tick"], (current // FRAME_TICKS + 1) * FRAME_TICKS)
            reason = machine.run(target=deadline)
            machine.audio()
            if reason == "gate":
                return
        if machine.info["tick"] != event["tick"]:
            raise RuntimeError("candidate gate did not leave the next input boundary reachable")
        machine.pad(event["buttons"])
    raise RuntimeError("candidate gate was not reached before the final replay input")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fresh_short_replay(short_path, rom_path, expected):
    command = [sys.executable, "-m", "aladdin_sega", "replay", str(short_path), "--rom", str(rom_path)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError("fresh witness replay failed: " + completed.stderr.strip())
    payload = next((json.loads(line) for line in reversed(completed.stdout.splitlines()) if line.startswith("{")), None)
    if payload is None:
        raise RuntimeError("fresh witness replay emitted no receipt")
    actual = (payload.get("state_sha256"), payload.get("frame_sha256"), payload.get("pcm_sha256"))
    return actual == tuple(digest(value) for value in expected), payload


def follow_original_boundaries(machine, instructions=100):
    """Continue a bounded amount, bypassing any repeated witness gate once."""
    end = machine.info["m68k_instructions"] + instructions
    pcm = []
    while machine.info["m68k_instructions"] < end:
        reason = machine.run(instructions=end - machine.info["m68k_instructions"])
        pcm.append(machine.audio())
        if reason == "limit":
            break
        if reason != "gate":
            raise RuntimeError("continuation ended outside a normal instruction boundary")
        machine.gate(machine.info["pc"], bypass_once=True)
    if machine.info["m68k_instructions"] != end:
        raise RuntimeError("continuation did not consume its bounded instruction budget")
    return machine.snapshot(), machine.frame()[2], b"".join(pcm)


def run_witness(*, candidate_name, recording, rom_path, output):
    entry_pc = {"leaf": LEAF_ENTRY, "pair": PAIR_ENTRY, "composed": CALLER_ENTRY}[candidate_name]
    recover = {"leaf": clear_auxiliary_buffer, "pair": clear_object_pair, "composed": detach_object}[candidate_name]
    output.mkdir(parents=True, exist_ok=True)
    rom, replay_bytes = read_rom(rom_path), artifacts.read_bounded(recording)
    replay_digest = digest(replay_bytes)

    with Machine(rom) as original:
        meta, initial, events = artifacts.load_replay(replay_bytes, rom_sha256=original.rom_sha256,
                                                      state_version=original.state_version)
        artifacts.restore_snapshot(original, initial)
        original.gates([entry_pc])
        reach_gate(original, events)
        if original.info["pc"] != entry_pc:
            raise RuntimeError("stopped PC does not match the selected candidate")
        entry_info, entry_registers = dict(original.info), original.registers()
        stopped_state = original.snapshot()
        gate_archive = artifacts.snapshot_bytes(original)
        (output / "gate.alsnap").write_bytes(gate_archive)
        short = artifacts.Recorder(original, origin="synthetic", reset_provenance="recovery-gate-witness")
        plan = recover(original, entry_registers)
        original.gates([entry_pc, plan.registers["pc"]])
        original.gate(entry_pc, bypass_once=True)
        if original.run(instructions=1000) != "gate":
            raise RuntimeError("original region did not stop at its verified continuation")
        original_state, original_frame, original_pcm = original.snapshot(), original.frame()[2], original.audio()
        continuation_tick = original.info["tick"]

        # A small original continuation checks that the return is a safe normal
        # instruction boundary, and gives the replacement an equal follow-on.
        original_follow_state, original_follow_frame, original_follow_pcm = follow_original_boundaries(original)
        witness_bytes = short.finish(original, terminal_tick=original.info["tick"])
        short_expected = (original_follow_state, original_follow_frame, original_pcm + original_follow_pcm)

    short_path = output / "witness.alreplay"
    short_path.write_bytes(witness_bytes)
    short_equal, short_receipt = fresh_short_replay(short_path, rom_path, short_expected)

    with Machine(rom) as replacement:
        replacement.restore(stopped_state)
        replacement.gates([entry_pc])
        if replacement.run(instructions=1) != "gate":
            raise RuntimeError("restored stopped state did not re-arm its candidate gate")
        replacement_plan = recover(replacement, replacement.registers())
        if replacement_plan != plan:
            raise RuntimeError("restored stopped state produced a different recovery plan")
        if not replacement.atomic(target=replacement.info["tick"] + 1_000_000,
                                  cycles=plan.cycles, instructions=plan.instructions,
                                  writes=list(plan.writes), registers=plan.registers,
                                  last_pc=plan.last_pc):
            raise RuntimeError("native scheduler declined the bounded replacement")
        immediate = (replacement.snapshot(), replacement.frame()[2], replacement.audio())
        continuation_archive = artifacts.snapshot_bytes(replacement)
        (output / "continuation.alsnap").write_bytes(continuation_archive)

    # Resume the staged state from its portable artifact in a fresh machine,
    # rather than merely continuing the in-memory replacement instance.
    with Machine(rom) as resumed:
        artifacts.restore_snapshot(resumed, continuation_archive)
        follow = follow_original_boundaries(resumed)

    immediate_equal = immediate == (original_state, original_frame, original_pcm)
    continuation_equal = follow == (original_follow_state, original_follow_frame, original_follow_pcm)
    receipt = execution_receipt(artifact_sha256=replay_digest, capture_source=meta["source_id"],
                                candidate=candidate_name)
    report = {
        "status": "PASS" if immediate_equal and continuation_equal and short_equal else "DIVERGENCE",
        "scope": "one user-recording activation; original region, staged replacement, and 100-instruction continuation",
        "candidate": candidate_name, "recording": str(recording),
        "entry": {**entry_info, "registers": entry_registers},
        "plan": {"cycles": plan.cycles, "instructions": plan.instructions, "writes": len(plan.writes),
                 "last_pc": plan.last_pc, "continuation_pc": plan.registers["pc"],
                 "continuation_tick": continuation_tick},
        "comparison": {"region": immediate_equal, "continuation": continuation_equal,
                       "fresh_short_replay": short_equal},
        "artifacts": {"gate_snapshot": "gate.alsnap", "gate_snapshot_sha256": digest(gate_archive),
                      "short_replay": "witness.alreplay", "short_replay_sha256": digest((output / "witness.alreplay").read_bytes()),
                      "continuation_snapshot": "continuation.alsnap", "continuation_snapshot_sha256": digest(continuation_archive)},
        "state_sha256": digest(immediate[0]), "frame_sha256": digest(immediate[1]), "pcm_sha256": digest(immediate[2]),
        "continuation_state_sha256": digest(follow[0]), "continuation_frame_sha256": digest(follow[1]),
        "continuation_pcm_sha256": digest(follow[2]), "receipt": receipt,
        "fresh_short_replay_receipt": short_receipt,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=("leaf", "pair", "composed"), default="leaf")
    parser.add_argument("--recording", type=Path, default=DEFAULT_RECORDING)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "recovery-witness")
    args = parser.parse_args(argv)
    report = run_witness(candidate_name=args.candidate, recording=args.recording.resolve(), rom_path=args.rom.resolve(),
                         output=args.output.resolve())
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
