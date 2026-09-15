import json

import pytest

from genesis_re import diagnostics as d, verification as v
from genesis_re.machine import Machine
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
    assert meta["capture_errors"]["oracle-state.bin"] == "Execution invalidated"
    assert "oracle-state.bin" not in meta
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


