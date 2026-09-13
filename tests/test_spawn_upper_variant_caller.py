"""Strict original-ROM qualification for dispatcher callback 1B7262."""
from __future__ import annotations
from ctypes import memmove
from pathlib import Path

import pytest

from aladdin_sega import artifacts
from aladdin_sega.boundary import SPAWN_UPPER_VARIANT_CALLER_ENTRY, UnsupportedCandidate, spawn_upper_variant_caller
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from aladdin_sega.recovery import Candidate

ROOT = Path('artifacts/grinding/luna/dispatcher-1ae3fc')
FIXTURES = tuple(sorted(ROOT.glob('*/*/1B7262.alsnap')))
assert FIXTURES, 'recorded 1B7262 fixtures are required'


def observable(machine):
    return (artifacts.snapshot_bytes(machine), machine.info, machine.registers(),
            machine.peek_ram(0, 65536), machine.frame()[2], machine.audio())


def write(machine, address, value, size):
    memmove(machine.ram_address + (address & 0xffff), value.to_bytes(size, 'big'), size)


def run(path, *, candidate, cap=None, exhaust=False, y=None, incoming_x=None, target=None):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        if cap is not None:
            write(machine, 0xFFEFE2, cap, 2)
        if exhaust:
            for index in range(20):
                write(machine, 0xFF7F06 + index * 0x42, 1, 1)
        if y:
            write(machine, 0xFFF152, y[0], 2); write(machine, 0xFF7DB2, y[1], 2)
        registers = machine.registers()
        outer = int.from_bytes(machine.peek_ram(registers['a7'] & 0xffff, 4), 'big') & 0xffffff
        if incoming_x is not None:
            registers.update(pc=SPAWN_UPPER_VARIANT_CALLER_ENTRY,
                             sr=(registers['sr'] & ~0x1f) | (0x10 if incoming_x else 0))
            machine.gates([SPAWN_UPPER_VARIANT_CALLER_ENTRY])
            assert machine.run(instructions=1) == 'gate'
            assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1,
                                  instructions=1, writes=[], registers=registers,
                                  last_pc=SPAWN_UPPER_VARIANT_CALLER_ENTRY)
        stats = None
        if candidate:
            recovery = Candidate('lifecycle'); recovery.arm(machine)
            assert machine.run(instructions=1) == 'gate'
            assert recovery.on_gate(machine, machine.info['tick'] + 1_000_000 if target is None else target)
            stats = recovery.stats
        machine.gates([outer]); assert machine.run(instructions=20_000) == 'gate'
        exit_state = observable(machine)
        machine.gates([]); assert machine.run(instructions=150) == 'limit'
        return exit_state, observable(machine), stats


@pytest.mark.parametrize('path', FIXTURES, ids=lambda path: path.parent.parent.name)
@pytest.mark.parametrize('cap,exhaust', ((None, False), (0x3939, False), (None, True)),
                         ids=('recorded-success', 'synthetic-cap', 'synthetic-exhaustion'))
@pytest.mark.parametrize('incoming_x', (False, True))
def test_variant_caller_matches_outer_and_future(path, cap, exhaust, incoming_x):
    expected, expected_future, _ = run(path, candidate=False, cap=cap, exhaust=exhaust, incoming_x=incoming_x)
    actual, actual_future, stats = run(path, candidate=True, cap=cap, exhaust=exhaust, incoming_x=incoming_x)
    assert actual == expected
    assert actual_future == expected_future
    assert stats['spawn_caller_hits'] == 1
    assert stats['spawn_region_hits'] == 0


@pytest.mark.parametrize('y', ((1, 1), (0xffff, 1)), ids=('y-no-carry', 'y-carry'))
@pytest.mark.parametrize('incoming_x', (False, True))
def test_variant_caller_tracks_final_coordinate_x(y, incoming_x):
    expected, expected_future, _ = run(FIXTURES[0], candidate=False, y=y, incoming_x=incoming_x)
    actual, actual_future, _ = run(FIXTURES[0], candidate=True, y=y, incoming_x=incoming_x)
    assert actual == expected
    assert actual_future == expected_future


def test_variant_caller_deadline_falls_back_before_writes():
    expected, expected_future, _ = run(FIXTURES[0], candidate=False)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, FIXTURES[0].read_bytes())
        registers = machine.registers()
        outer = int.from_bytes(machine.peek_ram(registers['a7'] & 0xffff, 4), 'big') & 0xffffff
        plan = spawn_upper_variant_caller(machine, registers)
        recovery = Candidate('lifecycle'); recovery.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        assert not recovery.on_gate(machine, machine.info['tick'] + plan.cycles - 1)
        machine.gates([outer]); assert machine.run(instructions=20_000) == 'gate'
        assert observable(machine) == expected
        machine.gates([]); assert machine.run(instructions=150) == 'limit'
        assert observable(machine) == expected_future
        assert recovery.stats['candidate_hits'] == 0


@pytest.mark.parametrize('which', ('unaligned', 'pool', 'globals', 'cap'))
def test_variant_caller_aliases_refuse_before_writes(which):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, FIXTURES[0].read_bytes())
        registers = machine.registers()
        if which == 'unaligned': registers['a7'] |= 1
        elif which == 'pool': registers['a7'] = 0xFF7E8A
        elif which == 'globals': registers['a7'] = 0xFFF152 + 2
        else: registers['a7'] = 0xFFEFE2 + 2
        before = observable(machine)
        with pytest.raises(UnsupportedCandidate):
            spawn_upper_variant_caller(machine, registers)
        assert observable(machine) == before
