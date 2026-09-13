"""Measure exact exit effects and native continuation of one ownership prototype."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import Candidate
from carrier_witness import original_exit, state

ROOT = Path(__file__).resolve().parents[1]


def run():
    entry = (ROOT / "artifacts/carrier/witness-v060/entry.alsnap").read_bytes()
    rom = read_rom(DEFAULT_ROM)
    with Machine(rom) as machine:
        artifacts.restore_snapshot(machine, entry)
        regs = machine.registers()
        exit_pc = int.from_bytes(machine.peek_ram(regs["a7"] & 65535, 4), "big")
        pcm = original_exit(machine, exit_pc, regs["a7"] + 4)
        expected = state(machine), machine.registers(), machine.info, machine.peek_ram(0, 65536)
        machine.gates([])
        machine.run(instructions=150)
        future, future_pcm, future_ram = state(machine), machine.audio(), machine.peek_ram(0, 65536)
    with Machine(rom) as machine:
        artifacts.restore_snapshot(machine, entry)
        candidate = Candidate("carrier")
        candidate.arm(machine)
        assert machine.run(instructions=1) == "gate"
        calls, plans = Counter(), []
        def profile(frame, event, arg):
            module = frame.f_globals.get("__name__", "")
            if event == "call" and module in {
                    "aladdin_sega.recovered", "aladdin_sega.boundary",
                    "aladdin_sega.ownership_boundary", "aladdin_sega.ownership_semantics"}:
                calls[f"{module.rsplit('.', 1)[-1]}.{frame.f_code.co_name}"] += 1
            if event == "return" and frame.f_code.co_name == "replace_object":
                plans.append({"write_bytes": len(arg.writes), "unique_write_bytes": len(dict(arg.writes)),
                              "cycles": arg.cycles, "instructions": arg.instructions})
        sys.setprofile(profile)
        try:
            assert candidate.on_gate(machine, machine.info["tick"] + FRAME_TICKS)
        finally:
            sys.setprofile(None)
        actual = state(machine), machine.registers(), machine.info, machine.peek_ram(0, 65536)
        differences = [f"{0xff0000 + i:06x}" for i, (a, b) in enumerate(zip(expected[3], actual[3])) if a != b]
        report = {"exit_state_equal": actual[0][0] == expected[0][0],
                  "exit_frame_equal": actual[0][1] == expected[0][1],
                  "exit_registers_equal": actual[1] == expected[1], "exit_info_equal": actual[2] == expected[2],
                  "exit_pcm_equal": machine.audio() == pcm, "exit_ram_differences": differences,
                  "calls": dict(calls), "replacement_plans": plans, "candidate_stats": candidate.stats}
        machine.gates([])
        machine.run(instructions=150)
        report.update(native_tail_instructions=150, future_state_equal=state(machine) == future,
                      future_pcm_equal=machine.audio() == future_pcm,
                      future_ram_differences=[f"{0xff0000 + i:06x}" for i, (a, b) in
                          enumerate(zip(future_ram, machine.peek_ram(0, 65536))) if a != b])
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
