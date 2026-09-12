"""Synthetic boot/menu/early-gameplay engineering scenario, never human evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, MASTER_HZ, read_rom


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--output", type=Path, default=Path("artifacts/synthetic-gameplay-new.alreplay"))
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output already exists; choose a new --output path")
    with Machine(read_rom(args.rom)) as machine:
        recorder = artifacts.Recorder(machine, origin="synthetic", reset_provenance="cold-boot")
        start = time.perf_counter()
        pcm = hashlib.sha256()
        for frame in range(1, 4201):
            if frame in (700, 1000, 1300, 2300, 3000):
                recorder.apply_pad(machine, 128)
            if frame in (710, 1010, 1310, 2310, 3010, 3880):
                recorder.apply_pad(machine, 0)
            if frame == 3800:
                recorder.apply_pad(machine, 8)
            machine.run(target=frame * FRAME_TICKS)
            pcm.update(machine.audio())
        data = recorder.finish(machine)
        artifacts.write_new(args.output, data)
        result = {"origin": "synthetic", "scope": "boot/menu/Start inputs and brief right movement",
                  "recording": str(args.output), "recording_sha256": artifacts.digest(data),
                  "source_id": machine.source_id, "wall_seconds": time.perf_counter() - start,
                  "emulated_seconds": machine.info["tick"] / MASTER_HZ, **machine.info,
                  "state_sha256": artifacts.digest(machine.snapshot()),
                  "frame_sha256": artifacts.digest(machine.frame()[2]), "pcm_sha256": pcm.hexdigest()}
        artifacts.write_new(args.output.with_suffix(".json"), json.dumps(result, indent=2).encode())
        print(json.dumps(result))


if __name__ == "__main__":
    main()
