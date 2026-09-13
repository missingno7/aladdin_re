"""Extract unmodified 1ABC82 checkpoints for known callbacks from user replays."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom


DISPATCH_PC = 0x1ABC82
TABLE = 0x1CBE
TARGETS = {0x1AF468, 0x1AF3C2, 0x1AF4D8}
DEFAULT_RECORDING = Path("recordings/current/20260912T210640.729016Z.alreplay")


def capture(recording: Path, output: Path, targets=TARGETS) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    rom = read_rom(DEFAULT_ROM)
    replay_data = recording.read_bytes()
    found = {}
    with Machine(rom) as machine:
        meta, initial, events = artifacts.load_replay(
            replay_data, rom_sha256=machine.rom_sha256, state_version=machine.state_version)
        artifacts.restore_snapshot(machine, initial)
        machine.gates([DISPATCH_PC])

        def advance(target):
            while machine.info["tick"] < target:
                reason = machine.run(target=min(target, machine.info["tick"] + FRAME_TICKS))
                machine.audio()
                if reason == "gate":
                    registers = machine.registers()
                    if registers["pc"] != DISPATCH_PC:
                        machine.gate(registers["pc"], bypass_once=True)
                        continue
                    record = registers["a1"]
                    kind = machine.peek_ram(record & 0xFFFF, 1)[0]
                    target_pc = int.from_bytes(machine.peek_rom(TABLE + 4 * kind, 4), "big") & 0xFFFFFF
                    key = f"{target_pc:06X}"
                    if target_pc in targets and key not in found:
                        snapshot = artifacts.snapshot_bytes(machine)
                        path = output / f"{key}.dispatcher.alsnap"
                        path.write_bytes(snapshot)
                        details = {
                            "origin": "user",
                            "scope": "unmodified dispatcher gate derived from user recording",
                            "recording": str(recording),
                            "recording_sha256": artifacts.digest(replay_data),
                            "target": key,
                            "object_type": kind,
                            "table_address": f"{TABLE + 4 * kind:06X}",
                            "dispatcher_pc": f"{DISPATCH_PC:06X}",
                            "info": machine.info,
                            "registers": registers,
                            "record_prefix": machine.peek_ram(record & 0xFFFF, 66).hex(),
                            "return_stack": machine.peek_ram(registers["a7"] & 0xFFFF, 8).hex(),
                            "fixture": str(path),
                        }
                        (output / f"{key}.json").write_text(json.dumps(details, indent=2) + "\n")
                        found[key] = details
                    machine.gate(DISPATCH_PC, bypass_once=True)
        for event in events:
            advance(event["tick"])
            machine.pad(event["buttons"])
        advance(meta["terminal_tick"])
        terminal = machine.info
    report = {
        "origin": "user",
        "scope": "unmodified dispatcher census extraction",
        "recording": str(recording),
        "recording_sha256": artifacts.digest(replay_data),
        "terminal": terminal,
        "target_hits": sorted(found),
        "missing_targets": sorted(f"{target:06X}" for target in targets if f"{target:06X}" not in found),
        "entries": found,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--recording", type=Path, default=DEFAULT_RECORDING)
    parser.add_argument("--output", type=Path, default=Path("artifacts/dispatcher/recorded"))
    parser.add_argument("--entry", action="append", type=lambda value: int(value, 16),
                        help="Callback target to capture (hexadecimal, repeatable)")
    args = parser.parse_args()
    capture(args.recording, args.output, set(args.entry) if args.entry else TARGETS)
