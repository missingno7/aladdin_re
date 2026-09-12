import json

import pytest

from aladdin_sega import diagnostics as d, verification as v
from aladdin_sega.machine import Machine
from test_machine import synthetic_rom


class StoppedMachine:
    rom_sha256 = "0" * 64
    source_id = "1" * 64
    state_version = 1

    def __init__(self, *, tick=100, pc=0x1234, changed=(), snapshot_error=False):
        self.info = {"tick": tick, "pc": pc, "sr": 0x2000}
        self.ram = bytearray(65536)
        for index in changed:
            self.ram[index] = 7
        self.snapshot_error = snapshot_error

    def registers(self):
        return {"pc": self.info["pc"], "sr": 0x2000, "d0": 0}

    def peek_ram(self, offset, size):
        return bytes(self.ram[offset:offset + size])

    def snapshot(self):
        if self.snapshot_error:
            raise RuntimeError("Execution invalidated")
        return b"opaque state"


def test_inspection_has_exact_ram_addresses_bounded_output_and_stop_context(tmp_path):
    d.capture(StoppedMachine(), tmp_path / "reference")
    d.capture(StoppedMachine(tick=102, pc=0x1236, changed=range(100, 140)), tmp_path / "candidate")
    result = d.compare(tmp_path)
    assert result["same_tick"] is False
    assert result["register_differences"] == {"pc": {"reference": 0x1234, "candidate": 0x1236}}
    assert result["ram"]["changed_bytes"] == 40
    assert result["ram"]["truncated"] is True
    assert len(result["ram"]["first_changes"]) == 32
    assert result["ram"]["first_changes"][0] == {"address": "0xFF0064", "reference": 0, "candidate": 7}


def test_failed_execution_keeps_inspection_without_claiming_a_restorable_save(tmp_path):
    d.capture(StoppedMachine(snapshot_error=True), tmp_path / "candidate", execution_error="original failure")
    meta = json.loads((tmp_path / "candidate/machine.json").read_text())
    assert meta["execution_error"] == "original failure"
    assert meta["capture_errors"]["state.alsnap"] == "Execution invalidated"
    assert "state.alsnap" not in meta
    assert meta["registers"]["pc"] == 0x1234
    assert (tmp_path / "candidate/ram.bin").stat().st_size == 65536
    assert "reference" in d.compare(tmp_path)["unavailable"]


def test_capture_does_not_change_machine_or_consume_pending_pcm(tmp_path):
    rom = synthetic_rom()
    with Machine(rom) as machine:
        machine.run(target=900000)
        state = machine.snapshot()
        d.capture(machine, tmp_path / "capture")
        assert machine.snapshot() == state
        actual = machine.audio()
    with Machine(rom) as original:
        original.run(target=900000)
        assert actual == original.audio()
    with pytest.raises(FileExistsError):
        d.capture(StoppedMachine(), tmp_path / "capture")


def test_diagnostics_never_turn_worker_failure_into_equivalence(tmp_path, monkeypatch):
    replay = tmp_path / "input.alreplay"
    replay.write_bytes(b"input bytes retained exactly")
    def worker(role, command, **kwargs):
        directory = command[command.index("--diagnostics") + 1]
        d.capture(StoppedMachine(snapshot_error=role == "candidate"), directory,
                  execution_error="broken candidate" if role == "candidate" else None)
        if role == "candidate":
            raise v.WorkerFailure(role, command, "broken candidate")
        return v.WorkerResult(role, command, {}, "", "")
    monkeypatch.setattr(v, "run_worker", worker)
    report = v.compare_replay(tmp_path / "rom", replay, candidate="mutant-result",
                              output=tmp_path / "out", diagnostics=True)
    assert report["status"] == "CANDIDATE_ERROR"
    assert report["compared"] is False
    assert report["diagnostics"]["captures"]["candidate"]["execution_error"] == "broken candidate"
    from pathlib import Path
    assert Path(report["diagnostics"]["replay"]).read_bytes() == replay.read_bytes()
    # Each invocation owns a fresh directory; no prior run's capture can leak in.
    again = v.compare_replay(tmp_path / "rom", replay, candidate="mutant-result",
                             output=tmp_path / "out", diagnostics=True)
    assert report["diagnostics"]["directory"] != again["diagnostics"]["directory"]
