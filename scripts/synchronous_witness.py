"""Compare the synchronous seam on the frozen 0.6 entry, including deadline handback."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import Candidate
from aladdin_sega.verification import compare_replay
from carrier_witness import original_exit, state

ROOT = Path(__file__).resolve().parents[1]


def run(output, evidence, rom_path):
    output.mkdir(parents=True, exist_ok=True)
    old = json.loads((evidence / "report.json").read_text())
    entry = (evidence / "entry.alsnap").read_bytes()
    rom = read_rom(rom_path)
    with Machine(rom) as m:
        artifacts.restore_snapshot(m, entry)
        regs = m.registers()
        exit_pc = int.from_bytes(m.peek_ram(regs["a7"] & 65535, 4), "big") & 0xffffff
        original_pcm = original_exit(m, exit_pc, regs["a7"] + 4)
        immediate, exit_tick = state(m), m.info["tick"]
        m.gates([])
        m.run(instructions=150)
        final, tail_pcm, final_tick = state(m), m.audio(), m.info["tick"]
    with Machine(rom) as m:
        artifacts.restore_snapshot(m, entry)
        candidate = Candidate("carrier")
        candidate.arm(m)
        assert m.run(instructions=1) == "gate"
        native_run = m.run
        inspected = False
        def inspect_call(**limits):
            nonlocal inspected
            if m.in_sound_call and not inspected:
                inspected = True
                assert native_run(instructions=1) == "limit"
                assert m.info["pc"] == 0x1e57ac
                # Native debug inspection is still possible; a portable recovery
                # save must not claim that this live Python call can be restored.
                assert m.snapshot()
                try:
                    artifacts.snapshot_bytes(m)
                except ValueError as error:
                    assert "synchronous sound" in str(error)
                else:
                    raise AssertionError("In-call portable snapshot was accepted")
            return native_run(**limits)
        m.run = inspect_call
        assert candidate.on_gate(m, m.info["tick"] + FRAME_TICKS)
        assert inspected and not m.in_sound_call
        assert state(m) == immediate and m.info["tick"] == exit_tick
        assert m.audio() == original_pcm
        exit_save = artifacts.snapshot_bytes(m)
        (output / "exit.alsnap").write_bytes(exit_save)
        m.run = native_run
        m.gates([])
        m.run(instructions=150)
        assert state(m) == final and m.audio() == tail_pcm
        stats = dict(candidate.stats)
    # Safe exit save: a fresh process continues original execution, with no
    # pending carrier registration or Python continuation at all.
    command = [sys.executable, "-m", "aladdin_sega", "resume-check", str(output / "exit.alsnap"),
               "--rom", str(rom_path), "--target", str(final_tick)]
    restored = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    resumed = json.loads(restored.stdout)
    assert resumed["state_sha256"] == artifacts.digest(final[0])
    assert resumed["frame_sha256"] == artifacts.digest(final[1])
    assert resumed["pcm_sha256"] == artifacts.digest(tail_pcm)
    (output / "fresh-exit.json").write_text(json.dumps(resumed, indent=2) + "\n")
    # Use the identical interior tick where 0.6 saved its persistent return.
    # The synchronous caller must hand execution back at that tick, without
    # delaying an input or serializing a continuation.
    deadline = old["inside"]["tick"]
    with Machine(rom) as m:
        artifacts.restore_snapshot(m, entry)
        m.run(target=deadline)
        inside, prefix_pcm = state(m), m.audio()
    with Machine(rom) as m:
        artifacts.restore_snapshot(m, entry)
        candidate = Candidate("carrier")
        candidate.arm(m)
        assert m.run(instructions=1) == "gate"
        assert candidate.on_gate(m, deadline)
        assert m.info["tick"] == deadline and state(m) == inside
        assert m.audio() == prefix_pcm and not m.in_sound_call
        assert candidate.stats["legacy_deadline_fallbacks"] == 1
        assert candidate.stats["legacy_returns"] == 0
        handback = artifacts.Recorder(m, origin="synthetic", reset_provenance="deadline-original-handback")
        (output / "handback.alsnap").write_bytes(handback.initial)
        m.gates([])
        m.run(target=final_tick)
        assert state(m) == final
        (output / "handback.alreplay").write_bytes(handback.finish(m))
    with Machine(rom) as m:
        artifacts.restore_snapshot(m, entry)
        inputs = artifacts.Recorder(m, origin="synthetic", reset_provenance="inside-sound-input-deadline")
        m.run(target=deadline)
        m.audio()
        inputs.apply_pad(m, m.info["buttons"] ^ 1)
        m.run(target=final_tick)
        (output / "input-deadline.alreplay").write_bytes(inputs.finish(m))
    comparisons = {}
    cases = [("entry", evidence / "witness.alreplay", "carrier"),
             ("handback", output / "handback.alreplay", "carrier"),
             ("input-deadline", output / "input-deadline.alreplay", "carrier")]
    cases += [(name, evidence / "witness.alreplay", name) for name in
              ("carrier-mutant-result", "carrier-mutant-continuation", "carrier-mutant-timing")]
    for label, path, name in cases:
        result = compare_replay(rom_path, path, candidate=name, timeout_seconds=30,
                                output=output / label, diagnostics=True)
        assert result["status"] == "PASS" if name == "carrier" else result["status"] in ("DIVERGENCE", "CANDIDATE_ERROR"), result
        if label == "input-deadline":
            assert result["candidate_receipt"]["candidate_stats"]["legacy_deadline_fallbacks"] == 1
        comparisons[label] = result["status"]
    report = {"status": "PASS", "baseline_replay_sha256": artifacts.digest((evidence / "witness.alreplay").read_bytes()),
              "scope": "same 0.6 entry and callees; strict exit, native tail, fresh safe restore, exact input deadline",
              "entry_tick": old["entry_tick"], "exit_tick": exit_tick, "final_tick": final_tick,
              "tail_instructions": 150, "deadline": deadline, "candidate_stats": stats,
              "in_call_snapshot_rejected": inspected, "comparisons": comparisons}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=ROOT / "artifacts/carrier/witness-v060")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/synchronous/witness")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    args = parser.parse_args()
    print(json.dumps(run(args.output.resolve(), args.evidence.resolve(), args.rom.resolve())))
