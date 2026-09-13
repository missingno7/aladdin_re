"""Independent portable-resume review for the qualified spawn-region seam."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from aladdin_sega import artifacts
from aladdin_sega.boundary import SPAWN_REGION_UPPER_ENTRY
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from aladdin_sega.recovery import Candidate
from test_spawn_region import (ENTRY_FIXTURES, _occupy, _outer_return, _prepare,
                               _observable, _run)


UPPER_SELECTOR_STOPS = tuple(sorted(
    Path('artifacts/grinding/luna/allocator-arms-1b524e').glob('*/1AE262-1B526A.alsnap')))


def _prepare_upper_from_selector_stop(machine, path):
    """Turn a recorded selector stop into the enclosing B5266 entry state.

    The selector snapshot is after B5266's BSR, so its current stack word is
    already the exact B526A return and the next longword is the outer return.
    The one-instruction atomic setup is common to original and candidate runs;
    it lets the same full-ROM oracle exercise distinct recorded device phases.
    """
    artifacts.restore_snapshot(machine, path.read_bytes())
    machine.gates([0x1AE262])
    assert machine.run(instructions=1) == 'gate'
    registers = machine.registers()
    assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                          cycles=1, instructions=1, writes=[],
                          registers={'a7': registers['a7'] + 4,
                                     'pc': SPAWN_REGION_UPPER_ENTRY},
                          last_pc=0x1AE262)


def _run_derived_upper(path, *, candidate):
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        _prepare_upper_from_selector_stop(machine, path)
        _occupy(machine, 0xFF7F06, 20, 1, None)
        outer = _outer_return(machine)
        recovery = None
        if candidate:
            recovery = Candidate('lifecycle')
            recovery.arm(machine)
            assert machine.run(instructions=1) == 'gate'
            assert recovery.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([outer])
        assert machine.run(instructions=20_000) == 'gate'
        result = _observable(machine)
        machine.gates([])
        assert machine.run(instructions=150) == 'limit'
        return result, _observable(machine), recovery.stats if recovery else None


@pytest.mark.parametrize('entry,path,base,count,direction', (
    (ENTRY_FIXTURES[0][1], ENTRY_FIXTURES[0][2], ENTRY_FIXTURES[0][3],
     ENTRY_FIXTURES[0][4], ENTRY_FIXTURES[0][5]),
    (SPAWN_REGION_UPPER_ENTRY,
     Path('artifacts/grinding/luna/allocator-arms-1b524e/state-transition-witness/1B5266.alsnap'),
     0xFF7F06, 20, 1),
))
def test_recorded_spawn_exit_survives_fresh_process_resume(tmp_path: Path,
                                                            entry, path, base, count, direction):
    """The candidate's safe outer exit must resume through native code freshly."""
    with Machine(read_rom(DEFAULT_ROM)) as original:
        _prepare(original, path, entry)
        _occupy(original, base, count, direction, 0)
        outer = _outer_return(original)
        original.gates([outer])
        assert original.run(instructions=20_000) == 'gate'
        original_exit = _observable(original)
        original_exit_archive = artifacts.snapshot_bytes(original)
        original.gates([])
        assert original.run(instructions=150) == 'limit'
        original_final = _observable(original)
        final_tick = original.info['tick']

    original_exit_path = tmp_path / 'original-exit.alsnap'
    original_exit_path.write_bytes(original_exit_archive)
    exit_path = tmp_path / 'spawn-exit.alsnap'
    with Machine(read_rom(DEFAULT_ROM)) as candidate_machine:
        _prepare(candidate_machine, path, entry)
        _occupy(candidate_machine, base, count, direction, 0)
        recovery = Candidate('lifecycle')
        recovery.arm(candidate_machine)
        assert candidate_machine.run(instructions=1) == 'gate'
        assert recovery.on_gate(candidate_machine,
                                candidate_machine.info['tick'] + 1_000_000)
        candidate_machine.gates([outer])
        assert candidate_machine.run(instructions=20_000) == 'gate'
        assert _observable(candidate_machine) == original_exit
        exit_path.write_bytes(artifacts.snapshot_bytes(candidate_machine))

    def fresh_resume(path):
        command = [sys.executable, '-m', 'aladdin_sega', 'resume-check', str(path),
                   '--rom', str(DEFAULT_ROM), '--target', str(final_tick)]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        return next(json.loads(line) for line in reversed(completed.stdout.splitlines())
                    if line.startswith('{'))

    expected = fresh_resume(original_exit_path)
    actual = fresh_resume(exit_path)
    assert {key: actual[key] for key in ('state_sha256', 'frame_sha256', 'pcm_sha256')} == {
        key: expected[key] for key in ('state_sha256', 'frame_sha256', 'pcm_sha256')}


@pytest.mark.parametrize('free', (0, 1, 19, None))
def test_recorded_upper_arm_matches_original_outer_and_future(free):
    """1B5266 is a recorded enclosing arm, not the invalid 1AFD12 label."""
    path = Path('artifacts/grinding/luna/allocator-arms-1b524e/state-transition-witness/1B5266.alsnap')
    expected, expected_future, _ = _run(path, SPAWN_REGION_UPPER_ENTRY,
                                        0xFF7F06, 20, 1, free=free, candidate=None)
    actual, actual_future, stats = _run(path, SPAWN_REGION_UPPER_ENTRY,
                                        0xFF7F06, 20, 1, free=free, candidate='lifecycle')
    assert actual == expected
    assert actual_future == expected_future
    assert stats['spawn_region_hits'] == 1


@pytest.mark.parametrize('path', UPPER_SELECTOR_STOPS,
                         ids=lambda path: path.parent.name)
def test_upper_exhaustion_is_exact_across_recorded_selector_device_phases(path):
    """The whole 884/86 enclosing plan remains exact outside its base fixture."""
    expected, expected_future, _ = _run_derived_upper(path, candidate=False)
    actual, actual_future, stats = _run_derived_upper(path, candidate=True)
    assert actual == expected
    assert actual_future == expected_future
    assert stats['spawn_region_hits'] == 1
