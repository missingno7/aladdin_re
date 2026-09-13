"""Strict recovery checks for the shared spawn allocator region.

The B524E and B5256 fixtures are recorded original stops.  Pool occupancy,
exhaustion, and lower-arm setup mutate only those entry states and are labelled
synthetic; the resulting oracle remains the original USA ROM.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aladdin_sega import artifacts
from aladdin_sega.boundary import (SPAWN_REGION_ENTRY, SPAWN_REGION_LOWER_ENTRY,
                                   SPAWN_REGION_REVERSE_ENTRY, SPAWN_REGION_UPPER_ENTRY, UnsupportedCandidate,
                                   spawn_region)
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from aladdin_sega.recovery import Candidate
from test_recovery import native_write


LUNA = Path('artifacts/grinding/luna')
ENTRY_FIXTURES = (
    ('enclosing', SPAWN_REGION_ENTRY,
     LUNA / 'allocator-arms-1b524e/old-225/1B524E-1B7448.alsnap', 0xFF7E82, 24, 1),
    ('reverse', SPAWN_REGION_REVERSE_ENTRY,
     LUNA / 'allocator-caller-1b5256/1B5256.alsnap', 0xFF8470, 24, -1),
    ('upper', SPAWN_REGION_UPPER_ENTRY,
     LUNA / 'allocator-arms-1b524e/state-transition-witness/1B5266.alsnap', 0xFF7F06, 20, 1),
)
RECORDED_ENCLOSING = tuple(sorted(
    (LUNA / 'allocator-arms-1b524e').glob('*/1B524E-*.alsnap')))


def _observable(machine):
    return (artifacts.snapshot_bytes(machine), machine.info, machine.registers(),
            machine.peek_ram(0, 65536), machine.frame()[2], machine.audio())


def _prepare(machine, path, entry):
    artifacts.restore_snapshot(machine, path.read_bytes())
    if entry != SPAWN_REGION_LOWER_ENTRY:
        return
    # This recorded direct 1AE2AA stop has B5262 as its allocator return.  A
    # synthetic direct entry replaces that internal return with the caller's
    # next return, then starts the enclosing B525E arm at its real PC.
    machine.gates([0x1AE2AA])
    assert machine.run(instructions=1) == 'gate'
    registers = machine.registers()
    outer = int.from_bytes(machine.peek_ram((registers['a7'] + 4) & 0xffff, 4), 'big') & 0xffffff
    native_write(machine, registers['a7'], outer.to_bytes(4, 'big'))
    registers = machine.registers()
    registers['pc'] = entry
    assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                          cycles=1, instructions=1, writes=[], registers=registers,
                          last_pc=entry)


def _occupy(machine, base, count, direction, free):
    if free == 'recorded':
        return
    for index in range(count):
        native_write(machine, base + direction * 0x42 * index, b'\0' if index == free else b'\1')


def _outer_return(machine):
    return int.from_bytes(machine.peek_ram(machine.registers()['a7'] & 0xffff, 4), 'big') & 0xffffff


def _run(path, entry, base, count, direction, *, free, candidate, target=None):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        _prepare(machine, path, entry)
        _occupy(machine, base, count, direction, free)
        outer = _outer_return(machine)
        recovery = None
        if candidate:
            recovery = Candidate(candidate)
            recovery.arm(machine)
            assert machine.run(instructions=1) == 'gate'
            assert machine.info['pc'] == entry
            assert recovery.on_gate(machine, machine.info['tick'] + 1_000_000 if target is None else target)
        machine.gates([outer])
        assert machine.run(instructions=20_000) == 'gate'
        result = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == 'limit'
        return result, _observable(machine), recovery.stats if recovery else None


@pytest.mark.parametrize('name,entry,path,base,count,direction', ENTRY_FIXTURES)
@pytest.mark.parametrize('free', (0, 1, None))
def test_recorded_spawn_entries_keep_full_outer_and_native_future(name, entry, path, base, count, direction, free):
    expected, expected_future, _ = _run(path, entry, base, count, direction, free=free, candidate=None)
    actual, actual_future, stats = _run(path, entry, base, count, direction, free=free, candidate='lifecycle')
    assert actual == expected
    assert actual_future == expected_future
    assert stats['spawn_region_hits'] == 1
    assert stats['legacy_entries'] == 0


@pytest.mark.parametrize('path', RECORDED_ENCLOSING, ids=lambda path: path.parent.name + '-' + path.stem)
def test_each_recorded_enclosing_template_keeps_outer_and_future(path):
    expected, expected_future, _ = _run(path, SPAWN_REGION_ENTRY, 0xFF7E82, 24, 1,
                                        free='recorded', candidate=None)
    actual, actual_future, stats = _run(path, SPAWN_REGION_ENTRY, 0xFF7E82, 24, 1,
                                        free='recorded', candidate='lifecycle')
    assert actual == expected
    assert actual_future == expected_future
    assert stats['spawn_region_hits'] == 1


@pytest.mark.parametrize('free', (0, 1, 19, None))
def test_lower_pool_entry_is_a_strict_synthetic_oracle(free):
    path = LUNA / 'allocator-arms-1b524e/old-225/1AE2AA-1B5262.alsnap'
    expected, expected_future, _ = _run(path, SPAWN_REGION_LOWER_ENTRY, 0xFF8368, 20, -1,
                                        free=free, candidate=None)
    actual, actual_future, stats = _run(path, SPAWN_REGION_LOWER_ENTRY, 0xFF8368, 20, -1,
                                        free=free, candidate='lifecycle')
    assert actual == expected
    assert actual_future == expected_future
    assert stats['spawn_region_hits'] == 1


@pytest.mark.parametrize('which', ('indexed-clear', 'template', 'frame'))
def test_spawn_region_aliases_refuse_before_planning_writes(which):
    path = LUNA / 'allocator-arms-1b524e/old-225/1B524E-1B7448.alsnap'
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        _prepare(machine, path, SPAWN_REGION_ENTRY)
        registers = machine.registers()
        if which == 'indexed-clear':
            registers['a2'] = (0xFF7E82 - (registers['d2'] & 0xffff)) & 0xffffff
        elif which == 'template':
            registers['a6'] = 0xFF7E84
        else:
            registers['a7'] = 0xFF84B2
        before = _observable(machine)
        with pytest.raises(UnsupportedCandidate, match='aliases'):
            spawn_region(machine, registers, SPAWN_REGION_ENTRY)
        assert _observable(machine) == before


def test_spawn_region_noncanonical_indexed_clear_refuses_before_planning_writes():
    path = LUNA / 'allocator-arms-1b524e/old-225/1B524E-1B7448.alsnap'
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        _prepare(machine, path, SPAWN_REGION_ENTRY)
        registers = machine.registers()
        registers['a2'] = 0x001000
        before = _observable(machine)
        with pytest.raises(UnsupportedCandidate, match='noncanonical'):
            spawn_region(machine, registers, SPAWN_REGION_ENTRY)
        assert _observable(machine) == before


def test_spawn_region_deadline_refusal_keeps_the_complete_original_outer_and_future():
    _, entry, path, base, count, direction = ENTRY_FIXTURES[1]
    expected, expected_future, _ = _run(path, entry, base, count, direction, free=1, candidate=None)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        _prepare(machine, path, entry)
        _occupy(machine, base, count, direction, 1)
        outer = _outer_return(machine)
        candidate = Candidate('lifecycle')
        candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        assert not candidate.on_gate(machine, machine.info['tick'])
        assert candidate.stats['fallback_reasons'] == {'scheduler admission': 1}
        machine.gates([outer])
        assert machine.run(instructions=20_000) == 'gate'
        assert _observable(machine) == expected
        machine.gates([])
        assert machine.run(instructions=150) == 'limit'
        assert _observable(machine) == expected_future


@pytest.mark.parametrize('mutant', ('lifecycle-mutant-result', 'lifecycle-mutant-continuation',
                                    'lifecycle-mutant-timing'))
def test_spawn_region_mutants_do_not_match_recorded_outer(mutant):
    _, entry, path, base, count, direction = ENTRY_FIXTURES[0]
    _, expected_future, _ = _run(path, entry, base, count, direction, free=0, candidate=None)
    try:
        _, actual_future, _ = _run(path, entry, base, count, direction, free=0, candidate=mutant)
    except Exception:
        return
    assert actual_future != expected_future
