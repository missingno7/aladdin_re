"""Qualify the concrete object/sound carrier and a save inside its legacy callee."""
from pathlib import Path
import argparse
import json

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import TRANSITION_ENTRY
from aladdin_sega.recovery import Candidate
from aladdin_sega.verification import compare_replay
from recovery_witness import reach_gate


ROOT = Path(__file__).resolve().parents[1]


def state(machine):
    return machine.snapshot(), machine.frame()[2]


def original_exit(machine, pc, sp):
    machine.gates([pc])
    pcm = []
    for _ in range(100):
        reason = machine.run(instructions=10000)
        pcm.append(machine.audio())
        if reason == "gate":
            if machine.registers()["a7"] == sp:
                return b"".join(pcm)
            machine.gate(pc, bypass_once=True)
    raise RuntimeError("Original carrier exit not reached within the witness budget")


def run(output, recording, rom_path):
    output.mkdir(parents=True, exist_ok=True)
    rom = read_rom(rom_path)
    with Machine(rom) as original:
        meta, initial, events = artifacts.load_replay(recording.read_bytes(), rom_sha256=original.rom_sha256,
                                                    state_version=original.state_version)
        artifacts.restore_snapshot(original, initial)
        original.gates([TRANSITION_ENTRY])
        reach_gate(original, events)
        entry = original.registers()
        entry_tick = original.info["tick"]
        parked = original.snapshot()
        (output / "entry.alsnap").write_bytes(artifacts.snapshot_bytes(original))
        recorder = artifacts.Recorder(original, origin="synthetic", reset_provenance="carrier-entry-witness")
        return_pc = int.from_bytes(original.peek_ram(entry["a7"] & 65535, 4), "big") & 0xffffff
        original_pcm = original_exit(original, return_pc, entry["a7"] + 4)
        immediate = state(original)
        exit_tick = original.info["tick"]
        original.gates([])
        original.run(instructions=150)
        final = state(original)
        tail_pcm = original.audio()
        final_tick = original.info["tick"]
        witness = recorder.finish(original)
        (output / "witness.alreplay").write_bytes(witness)

    with Machine(rom) as candidate:
        candidate.restore(parked)
        recovery = Candidate("carrier")
        recovery.arm(candidate)
        assert candidate.run(instructions=1) == "gate"
        assert recovery.on_gate(candidate, candidate.info["tick"] + FRAME_TICKS)
        assert candidate.pending_transition and candidate.info["pc"] == 0x1e58b8
        # The first sound instruction is JSR 1E57AC. Save in that nested original
        # callee, with both guest return frames materialized in authoritative RAM.
        assert candidate.run(instructions=1) == "limit"
        assert candidate.info["pc"] == 0x1e57ac
        before_save_pcm = candidate.audio()
        inside_info = dict(candidate.info)
        saved = artifacts.snapshot_bytes(candidate)
        (output / "inside.alsnap").write_bytes(saved)
        suffix = artifacts.Recorder(candidate, origin="synthetic", reset_provenance="inside-original-sound-callee")
        inside_pcm = []
        for _ in range(100):
            if candidate.run(instructions=10000) == "gate":
                inside_pcm.append(candidate.audio())
                assert recovery.on_gate(candidate, candidate.info["tick"] + FRAME_TICKS)
                if not candidate.pending_transition:
                    break
            else:
                inside_pcm.append(candidate.audio())
        else:
            raise RuntimeError("Carrier did not resume after original sound")
        inside_pcm.append(candidate.audio())
        assert candidate.info["tick"] == exit_tick
        assert state(candidate) == immediate
        assert before_save_pcm + b"".join(inside_pcm) == original_pcm
        candidate.gates([])
        candidate.run(instructions=150)
        resumed_pcm = b"".join(inside_pcm) + candidate.audio()
        assert state(candidate) == final and candidate.info["tick"] == final_tick
        assert before_save_pcm + resumed_pcm == original_pcm + tail_pcm
        (output / "continuation.alsnap").write_bytes(artifacts.snapshot_bytes(candidate))
        (output / "inside.alreplay").write_bytes(suffix.finish(candidate))
        stats = dict(recovery.stats)

    comparisons = {}
    for label, artifact in (("entry", "witness.alreplay"), ("inside", "inside.alreplay")):
        result = compare_replay(rom_path, output / artifact, candidate="carrier", timeout_seconds=30,
                                output=output / label, diagnostics=True)
        assert result["status"] == "PASS", result
        receipt = result["candidate_receipt"]
        assert receipt["state_sha256"] == artifacts.digest(final[0])
        assert receipt["frame_sha256"] == artifacts.digest(final[1])
        assert receipt["tick"] == final_tick
        if label == "inside":
            assert receipt["candidate_stats"]["legacy_returns"] == 1
            assert receipt["candidate_stats"]["carrier_completed"] == 1
            assert receipt["pending_transition"] is None
            assert receipt["pcm_sha256"] == artifacts.digest(resumed_pcm)
        comparisons[label] = result["status"]
    for name in ("carrier-mutant-result", "carrier-mutant-continuation", "carrier-mutant-timing"):
        result = compare_replay(rom_path, output / "witness.alreplay", candidate=name, timeout_seconds=30,
                                output=output / name, diagnostics=True)
        assert result["status"] in ("DIVERGENCE", "CANDIDATE_ERROR"), result
        comparisons[name] = result["status"]
    report = {"status": "PASS", "scope": "one recorded entry, frozen-input derived witness; original vs carrier and fresh-process restore inside original sound callee",
              "entry_tick": entry_tick, "entry_registers": entry, "inside": inside_info,
              "inside_snapshot_version": 3, "exit_tick": exit_tick, "final_tick": final_tick,
              "tail_instructions": 150, "comparisons": comparisons, "candidate_stats": stats,
              "state_sha256": artifacts.digest(final[0]), "frame_sha256": artifacts.digest(final[1]),
              "pcm_sha256": artifacts.digest(original_pcm + tail_pcm),
              "recording_sha256": artifacts.digest(recording.read_bytes())}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    # Keep the original experiment reproducible after the production seam changes.
    import sys
    from carrier_v060 import main
    raise SystemExit(main(["witness", *sys.argv[1:]]))
