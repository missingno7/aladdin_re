"""Tracked candidate qualification for the composed selector/decrement seam.

The selector itself has an original-only matrix in the retirement review.  These
cases exercise the caller merge as well, so selector register residue and the
first 150 native instructions after the outer RTS are compared against the
unmodified ROM.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, FRAME_TICKS, read_rom
from aladdin_sega.recovery import Candidate
from test_recovery import native_write


ROOT = Path("artifacts/grinding/parent")
ENTRY = 0x1AEC00
OUTER = 0x1ABCA0
SELECTOR_FLAGS = (
    0xFFF0D7, 0xFFF173, 0xFFF115, 0xFFF0CD, 0xFFF0DB,
    0xFFF0D0, 0xFFF0D2, 0xFFF0C1, 0xFFF0DE, 0xFFF0DF, 0xFFF0ED,
)


def _observable(machine):
    return (
        artifacts.snapshot_bytes(machine), machine.info, machine.registers(),
        machine.peek_ram(0, 65536), machine.frame()[2], machine.audio(),
    )


def _prepare(machine, *, kind=0x10, table=None, f115=False, counter=1,
             sound=False, blocker=False):
    record = machine.registers()["a1"]
    for address in SELECTOR_FLAGS:
        native_write(machine, address, b"\0")
    native_write(machine, 0xFFF0D8, b"\1")
    native_write(machine, 0xFF7E49, b"\0")
    native_write(machine, 0xFF7E02, (9).to_bytes(2, "big"))
    native_write(machine, record, bytes((kind, counter)))
    native_write(machine, record + 2, (10).to_bytes(2, "big"))
    native_write(machine, record + 8, b"\1")
    native_write(machine, 0xFFF57D, bytes((1 if sound else 0,)))
    if sound:
        for address, value in ((0xFFF0E7, 0), (0xFFF0E6, 0), (0xFFF0E9, 0),
                               (0xFFF0F2, 0), (0xFFF0BE, 0), (0xFFF0C1, 0),
                               (0xFFF173, 0), (0xFF7E20, int(blocker)),
                               (0xFF7E21, 0), (0xFFEFFA, 0)):
            native_write(machine, address, bytes((value,)))
    if table is not None:
        native_write(machine, 0xFFF0D0, b"\1")
        native_write(machine, 0xFF7E04, table.to_bytes(2, "big"))
    if f115:
        native_write(machine, 0xFFF115, b"\1")


def _set_incoming_x(machine, enabled):
    """Change only the incoming CCR X bit while parked at the real entry."""
    machine.gates([ENTRY])
    assert machine.run(instructions=1) == "gate"
    registers = machine.registers()
    registers["sr"] = (registers["sr"] | 0x10) if enabled else (registers["sr"] & ~0x10)
    assert machine.atomic(
        target=machine.info["tick"] + 1_000_000,
        cycles=1,
        instructions=1,
        writes=[],
        registers=registers,
        last_pc=ENTRY,
    )


def _original(path, *, table=None, f115=False, incoming_x=False, kind=0x10,
              counter=1, sound=False, blocker=False):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare(machine, table=table, f115=f115, kind=kind, counter=counter,
                 sound=sound, blocker=blocker)
        _set_incoming_x(machine, incoming_x)
        machine.gates([OUTER])
        assert machine.run(instructions=100_000) == "gate"
        outer = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        return outer, _observable(machine)


def _candidate(path, *, table=None, f115=False, incoming_x=False, kind=0x10,
               counter=1, sound=False, blocker=False):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare(machine, table=table, f115=f115, kind=kind, counter=counter,
                 sound=sound, blocker=blocker)
        _set_incoming_x(machine, incoming_x)
        recovery = Candidate("lifecycle")
        recovery.arm(machine)
        assert machine.run(instructions=1) == "gate"
        assert machine.info["pc"] == ENTRY
        accepted = recovery.on_gate(machine, machine.info["tick"] + FRAME_TICKS)
        assert accepted
        if machine.info["pc"] != OUTER:
            machine.gates([OUTER])
            assert machine.run(instructions=100_000) == "gate"
        assert machine.info["pc"] == OUTER
        outer = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == "limit"
        return outer, _observable(machine), recovery.stats


@pytest.mark.parametrize("corpus", ["sibling-census-old", "sibling-census-new"])
@pytest.mark.parametrize("table", [None, 0x00, 0x3C, 0x3F])
@pytest.mark.parametrize("incoming_x", [False, True])
def test_candidate_selector_residue_and_future_match_original(corpus, table, incoming_x):
    path = ROOT / corpus / "1AEC00.alsnap"
    expected, expected_future = _original(path, table=table, incoming_x=incoming_x)
    actual, actual_future, stats = _candidate(path, table=table, incoming_x=incoming_x)
    assert actual == expected
    assert actual_future == expected_future
    assert stats["candidate_hits"] == 1


@pytest.mark.parametrize("f115", [False, True])
def test_candidate_non_table_selector_preserves_full_outer_and_future(f115):
    path = ROOT / "sibling-census-old" / "1AEC00.alsnap"
    expected, expected_future = _original(path, f115=f115, incoming_x=True)
    actual, actual_future, stats = _candidate(path, f115=f115, incoming_x=True)
    assert actual == expected
    assert actual_future == expected_future
    assert stats["candidate_hits"] == 1


@pytest.mark.parametrize("corpus", ["sibling-census-old", "sibling-census-new"])
@pytest.mark.parametrize("kind", [0x10, 0x18, 0x42])
@pytest.mark.parametrize("counter", [1, 2, 0xFF])
def test_candidate_command8_sound_matches_original_outer_and_future(corpus, kind, counter):
    path = ROOT / corpus / "1AEC00.alsnap"
    expected, expected_future = _original(path, kind=kind, counter=counter, sound=True)
    actual, actual_future, stats = _candidate(path, kind=kind, counter=counter, sound=True)
    assert actual == expected
    assert actual_future == expected_future
    assert stats["legacy_entries"] == stats["legacy_returns"] == 1


def test_candidate_rejects_unrecovered_type13_sound_without_claiming_a_hit():
    path = ROOT / "sibling-census-old" / "1AEC00.alsnap"
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare(machine, kind=0x13, counter=1, sound=True)
        recovery = Candidate("lifecycle")
        recovery.arm(machine)
        assert machine.run(instructions=1) == "gate"
        assert not recovery.on_gate(machine, machine.info["tick"] + FRAME_TICKS)
        assert recovery.stats["fallbacks"] == 1
        assert recovery.stats["candidate_hits"] == 0
