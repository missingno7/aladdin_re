"""Strict qualification for the recorded reverse-pool creation caller at 1B6802."""
from __future__ import annotations
from ctypes import memmove
from pathlib import Path

import pytest

from aladdin_sega import artifacts
from aladdin_sega.boundary import SPAWN_REVERSE_CALLER_ENTRY, UnsupportedCandidate, spawn_reverse_caller
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from aladdin_sega.recovery import Candidate

ROOT = Path('artifacts/grinding/terra/spawn-callers')
FIXTURES = tuple(sorted(ROOT.glob('*/1B6802.alsnap')))
assert FIXTURES, 'captured 1B6802 fixtures are required for strict qualification'


def _observable(machine):
    return (artifacts.snapshot_bytes(machine), machine.info, machine.registers(),
            machine.peek_ram(0, 65536), machine.frame()[2], machine.audio())


def _outer(machine):
    registers = machine.registers()
    return int.from_bytes(machine.peek_ram(registers['a7'] & 0xffff, 4), 'big') & 0xffffff


def _occupy(machine, free):
    for index in range(24):
        memmove(machine.ram_address + ((0xFF8470 - index * 0x42) & 0xffff),
                b'\0' if index == free else b'\1', 1)


def _run(path, *, candidate=None, free='recorded', target=None):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        if free != 'recorded':
            _occupy(machine, free)
        outer = _outer(machine)
        recovery = None
        if candidate:
            recovery = Candidate(candidate)
            recovery.arm(machine)
            assert machine.run(instructions=1) == 'gate'
            assert machine.info['pc'] == SPAWN_REVERSE_CALLER_ENTRY
            assert recovery.on_gate(machine, machine.info['tick'] + 1_000_000 if target is None else target)
        machine.gates([outer])
        assert machine.run(instructions=20_000) == 'gate'
        result = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == 'limit'
        return result, _observable(machine), recovery.stats if recovery else None


@pytest.mark.parametrize('path', FIXTURES, ids=lambda path: path.parent.name)
@pytest.mark.parametrize('free', ('recorded', 0, 7, 23, None))
def test_reverse_spawn_caller_keeps_recorded_outer_and_future(path, free):
    expected, expected_future, _ = _run(path, free=free)
    actual, actual_future, stats = _run(path, candidate='lifecycle', free=free)
    assert actual == expected
    assert actual_future == expected_future
    assert stats['spawn_caller_hits'] == 1
    assert stats['spawn_region_hits'] == 0


def test_reverse_spawn_caller_alias_refuses_before_planning_writes():
    path = FIXTURES[0]
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        machine.gates([SPAWN_REVERSE_CALLER_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        # An aligned outer frame overlapping the shared primary pool is unsafe.
        registers['a7'] = 0xFF7E8A
        before = artifacts.snapshot_bytes(machine)
        with pytest.raises(UnsupportedCandidate):
            spawn_reverse_caller(machine, registers)
        assert artifacts.snapshot_bytes(machine) == before


def test_reverse_spawn_caller_deadline_leaves_whole_original_path():
    path = FIXTURES[0]
    expected, expected_future, _ = _run(path)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        machine.gates([SPAWN_REVERSE_CALLER_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        plan = spawn_reverse_caller(machine, machine.registers())
        recovery = Candidate('lifecycle'); recovery.arm(machine)
        assert not recovery.on_gate(machine, machine.info['tick'] + plan.cycles - 1)
        assert recovery.stats['candidate_hits'] == 0
        outer = _outer(machine)
        machine.gates([outer])
        assert machine.run(instructions=20_000) == 'gate'
        assert _observable(machine) == expected
        machine.gates([])
        assert machine.run(instructions=150) == 'limit'
        assert _observable(machine) == expected_future


@pytest.mark.parametrize('mutant', ('lifecycle-mutant-result',
                                    'lifecycle-mutant-continuation',
                                    'lifecycle-mutant-timing'))
def test_reverse_spawn_caller_mutants_do_not_match_recorded_outer(mutant):
    path = FIXTURES[0]
    expected, _, _ = _run(path)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        outer = _outer(machine)
        candidate = Candidate(mutant); candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        try:
            accepted = candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
            machine.gates([outer])
            reached = machine.run(instructions=20_000) == 'gate'
            actual = _observable(machine) if reached else None
        except Exception:
            accepted, actual = False, None
    assert not accepted or actual != expected
