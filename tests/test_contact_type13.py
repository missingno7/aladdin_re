"""Strict synthetic qualification for type-13's allocation-backed retirement.

No current user replay reaches 1AF1AC.  These tests deliberately mutate the
recorded 1AEC00 entry snapshots and label the resulting proof synthetic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aladdin_sega import artifacts
from aladdin_sega.boundary import (COLLECTION_DISPATCH_ENTRY, COLLECTION_DISPATCH_RETURN,
                                   CONTACT_SIBLING_DIRECT, CONTACT_SIBLING_ENTRY,
                                   CONTACT_SIBLING_RETIREMENT, CONTACT_SIBLING_WRAPPER,
                                   begin_contact_sibling_retirement,
                                   begin_contact_sibling_type13_sound, UnsupportedCandidate)
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from aladdin_sega.recovery import Candidate
from test_recovery import native_write


ROOT = Path('artifacts/grinding/parent')


def _observable(machine):
    return (artifacts.snapshot_bytes(machine), machine.info, machine.registers(),
            machine.peek_ram(0, 65536), machine.frame()[2], machine.audio())


def _prepare(machine, *, slots, sound, direction=0):
    record = machine.registers()['a1']
    native_write(machine, record, b'\x13\0')
    native_write(machine, record + 2, b'\0\1')
    native_write(machine, record + 8, b'\x01')
    native_write(machine, 0xFFF0D8, b'\1')
    native_write(machine, 0xFF7E49, bytes((direction,)))
    native_write(machine, 0xFF7E02, b'\0\0' if not direction else b'\0\1')
    native_write(machine, 0xFFF57F, bytes((sound,)))
    if slots == 'second':
        native_write(machine, 0xFF8470, b'\1')
    elif slots == 'none':
        for index in range(24):
            slot = 0xFF8470 - index * 0x42
            if slot != record:
                native_write(machine, slot, b'\1')


def _run(path, *, candidate, slots, sound, direction=0):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare(machine, slots=slots, sound=sound, direction=direction)
        if candidate:
            recovery = Candidate('lifecycle')
            recovery.arm(machine)
            assert machine.run(instructions=1) == 'gate'
            assert machine.info['pc'] == CONTACT_SIBLING_ENTRY
            assert recovery.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == 'gate'
        outer = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == 'limit'
        return outer, _observable(machine), recovery.stats if candidate else None


@pytest.mark.parametrize('corpus', ('old', 'new'))
@pytest.mark.parametrize('slots', ('first', 'second', 'none'))
@pytest.mark.parametrize('direction', (0, 1))
def test_type13_allocator_outer_and_future_match_original_synthetically(corpus, slots, direction):
    path = ROOT / f'sibling-census-{corpus}' / '1AEC00.alsnap'
    expected, future, _ = _run(path, candidate=False, slots=slots, sound=0, direction=direction)
    actual, actual_future, stats = _run(path, candidate=True, slots=slots, sound=0, direction=direction)
    assert actual == expected
    assert actual_future == future
    assert stats['contact_sibling_hits'] == 1
    if slots == 'none':
        assert stats['legacy_entries'] == 0
    else:
        assert stats['legacy_entries'] == stats['legacy_returns'] == 1


@pytest.mark.parametrize('corpus', ('old', 'new'))
@pytest.mark.parametrize('slots', ('first', 'second', 'none'))
def test_type13_sound_flag_keeps_native_command14_suffix_synthetically(corpus, slots):
    path = ROOT / f'sibling-census-{corpus}' / '1AEC00.alsnap'
    expected, future, _ = _run(path, candidate=False, slots=slots, sound=1)
    actual, actual_future, stats = _run(path, candidate=True, slots=slots, sound=1)
    assert actual == expected
    assert actual_future == future
    if slots == 'none':
        assert stats['legacy_entries'] == 0
    else:
        assert stats['legacy_entries'] == stats['legacy_returns'] == 1
        assert stats['local_fallbacks'] == 1


def _rejected_type13_planner(path, *, record=None, stack=None):
    """Run an admission-only planner and prove it did not mutate guest state."""
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare(machine, slots='first', sound=0)
        registers = machine.registers()
        if record is not None:
            native_write(machine, record, b'\x13\0')
            native_write(machine, record + 8, b'\x01')
            registers['a1'] = record
        if stack is not None:
            registers['a7'] = stack
        before = artifacts.snapshot_bytes(machine)
        with pytest.raises(UnsupportedCandidate):
            begin_contact_sibling_type13_sound(machine, registers)
        assert artifacts.snapshot_bytes(machine) == before


def test_type13_aligned_partial_pool_alias_refuses_before_planner_writes():
    path = ROOT / 'sibling-census-old' / '1AEC00.alsnap'
    # FF7E84 is even and inside the pool, but not aligned to a 0x42-byte slot.
    _rejected_type13_planner(path, record=0xFF7E84)


def test_type13_frame_overlap_refuses_before_planner_writes():
    path = ROOT / 'sibling-census-old' / '1AEC00.alsnap'
    # The callee frame becomes FF8496..FF84B1, inside the allocator pool.
    _rejected_type13_planner(path, stack=0xFF84B2)


def test_type13_global_overlap_refuses_before_planner_writes():
    path = ROOT / 'sibling-census-old' / '1AEC00.alsnap'
    # This otherwise aligned record spans the live FFF124 transition byte.
    _rejected_type13_planner(path, record=0xFFF100)


@pytest.mark.parametrize('corpus', ('old', 'new'))
def test_type13_exhausted_direct_retirement_oracle_matches_original(corpus):
    path = ROOT / f'sibling-census-{corpus}' / '1AECD8.alsnap'
    expected = []
    for candidate in (False, True):
        with Machine(read_rom(DEFAULT_ROM)) as machine:
            artifacts.restore_snapshot(machine, path.read_bytes())
            record = machine.registers()['a1']
            native_write(machine, record, b'\x13\0')
            native_write(machine, 0xFFF57F, b'\1')
            for index in range(24):
                slot = 0xFF8470 - index * 0x42
                if slot != record:
                    native_write(machine, slot, b'\1')
            if candidate:
                machine.gates([CONTACT_SIBLING_RETIREMENT])
                assert machine.run(instructions=1) == 'gate'
                plan = begin_contact_sibling_retirement(machine, machine.registers())
                assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=plan.cycles,
                                      instructions=plan.instructions, writes=list(plan.writes),
                                      registers=plan.registers, last_pc=plan.last_pc)
            machine.gates([COLLECTION_DISPATCH_RETURN])
            assert machine.run(instructions=100_000) == 'gate'
            outer = _observable(machine)
            machine.gates([])
            assert machine.run(instructions=150) == 'limit'
            row = (outer, _observable(machine))
            if candidate:
                assert row == expected[0]
            else:
                expected.append(row)


def test_type13_fixed_helper_deadline_falls_back_after_committed_prefix():
    path = ROOT / 'sibling-census-old' / '1AEC00.alsnap'
    expected, expected_future, _ = _run(path, candidate=False, slots='first', sound=0)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare(machine, slots='first', sound=0)
        machine.gates([CONTACT_SIBLING_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        plan = begin_contact_sibling_type13_sound(machine, machine.registers())
        # This fixture's atomic prefix costs 12,222 master ticks; its next
        # native helper instruction cannot fit in the 278-tick remainder.
        target = machine.info['tick'] + 12_500
        recovery = Candidate('lifecycle'); recovery.arm(machine)
        assert recovery.on_gate(machine, target)
        assert recovery.stats['legacy_entries'] == 1
        assert recovery.stats['legacy_deadline_fallbacks'] == 1
        assert recovery.stats['legacy_returns'] == 0
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == 'gate'
        assert _observable(machine) == expected
        machine.gates([])
        assert machine.run(instructions=150) == 'limit'
        assert _observable(machine) == expected_future


@pytest.mark.parametrize('mutant', ('lifecycle-mutant-result',
                                    'lifecycle-mutant-continuation',
                                    'lifecycle-mutant-timing'))
def test_type13_result_return_and_timing_mutants_do_not_match_original(mutant):
    path = ROOT / 'sibling-census-old' / '1AEC00.alsnap'
    expected, _, _ = _run(path, candidate=False, slots='first', sound=0)
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare(machine, slots='first', sound=0)
        candidate = Candidate(mutant); candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        try:
            accepted = candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
            machine.gates([COLLECTION_DISPATCH_RETURN])
            reached_outer = machine.run(instructions=100_000) == 'gate'
            actual = _observable(machine) if reached_outer else None
        except Exception:
            accepted, actual = False, None
    assert not accepted or actual != expected


def _prepare_wrapper(machine, entry, *, sound):
    registers = machine.registers()
    machine.gates([registers['pc']])
    assert machine.run(instructions=1) == 'gate'
    registers.update(pc=entry, a7=registers['a7'] + 4)
    assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1,
                          writes=[], registers=registers, last_pc=entry)
    _prepare(machine, slots='first', sound=sound)


def _wrapper_run(path, entry, *, candidate, sound):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        artifacts.restore_snapshot(machine, path.read_bytes())
        _prepare_wrapper(machine, entry, sound=sound)
        if candidate:
            recovery = Candidate('lifecycle'); recovery.arm(machine)
            assert machine.run(instructions=1) == 'gate'
            assert machine.info['pc'] == entry
            assert recovery.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([COLLECTION_DISPATCH_RETURN])
        assert machine.run(instructions=100_000) == 'gate'
        outer = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == 'limit'
        return outer, _observable(machine), recovery.stats if candidate else None


@pytest.mark.parametrize('entry', (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT))
@pytest.mark.parametrize('sound', (0, 1))
def test_type13_wrappers_keep_full_outer_and_future_synthetically(entry, sound):
    path = ROOT / 'sibling-census-old' / '1AEC00.alsnap'
    expected, future, _ = _wrapper_run(path, entry, candidate=False, sound=sound)
    actual, actual_future, stats = _wrapper_run(path, entry, candidate=True, sound=sound)
    assert actual == expected
    assert actual_future == future
    assert stats['contact_sibling_hits'] == (1 if not sound else 0)
    assert stats['legacy_entries'] == stats['legacy_returns'] == 1
    if sound:
        assert stats['local_fallbacks'] == 1


def _prepare_dispatch(machine, *, sound):
    registers = machine.registers()
    machine.gates([registers['pc']])
    assert machine.run(instructions=1) == 'gate'
    registers.update(pc=COLLECTION_DISPATCH_ENTRY, a7=registers['a7'] + 4)
    assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1,
                          writes=[], registers=registers, last_pc=COLLECTION_DISPATCH_ENTRY)
    _prepare(machine, slots='first', sound=sound)


@pytest.mark.parametrize('entry', ('1AE9C6', '1AE9DA'))
def test_type13_dispatcher_composes_measured_wrapper_callbacks_synthetically(entry):
    path = ROOT / 'sibling-dispatch-recorded' / f'{entry}.dispatcher.alsnap'
    expected = []
    for candidate in (False, True):
        with Machine(read_rom(DEFAULT_ROM)) as machine:
            artifacts.restore_snapshot(machine, path.read_bytes())
            _prepare(machine, slots='first', sound=0)
            if candidate:
                recovery = Candidate('lifecycle'); recovery.arm(machine)
                assert machine.run(instructions=1) == 'gate'
                assert machine.info['pc'] == COLLECTION_DISPATCH_ENTRY
                assert recovery.on_gate(machine, machine.info['tick'] + 1_000_000)
            machine.gates([COLLECTION_DISPATCH_RETURN])
            assert machine.run(instructions=100_000) == 'gate'
            outer = _observable(machine)
            machine.gates([])
            assert machine.run(instructions=150) == 'limit'
            row = (outer, _observable(machine))
            if candidate:
                assert row == expected[0]
                assert recovery.stats['collection_dispatch_hits'] == 1
                assert recovery.stats['legacy_entries'] == recovery.stats['legacy_returns'] == 1
            else:
                expected.append(row)
