"""The spawn allocator fact recognizer protects the four boundary arm recipes."""
import importlib.util
from dataclasses import replace
from pathlib import Path
import sys

import pytest

from aladdin_sega import boundary
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from test_spawn_region import ENTRY_FIXTURES, _occupy, _prepare


spec = importlib.util.spec_from_file_location('spawn_allocator_facts',
    Path(__file__).resolve().parents[1] / 'scripts' / 'spawn_allocator_facts.py')
facts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = facts
spec.loader.exec_module(facts)


@pytest.fixture
def rom():
    path = Path('assets/Aladdin (USA).md')
    if not path.exists():
        pytest.skip('Original USA ROM required')
    return path.read_bytes()


def test_four_verified_allocator_sequences_match_boundary_arm_facts(rom):
    result = facts.allocator_arms(rom)
    facts.check_boundary_arms(result)
    assert {entry: (arm.start, arm.count, arm.direction, arm.stride,
                    arm.return_target, arm.exhausted_a5)
            for entry, arm in result.items()} == {
        0x1B524E: (0xFF7E82, 24, 1, 0x42, 0x1B5252, 0xFF84B2),
        0x1B5256: (0xFF8470, 24, -1, 0x42, 0x1B525A, 0xFF7E40),
        0x1B525E: (0xFF8368, 20, -1, 0x42, 0x1B5262, 0xFF7E40),
        0x1B5266: (0xFF7F06, 20, 1, 0x42, 0x1B526A, 0xFF842E),
    }
    upper = result[0x1B5266]
    assert (upper.free_cycles_base, upper.free_cycles_per_occupied,
            upper.free_instructions_base, upper.free_instructions_per_occupied,
            upper.exhausted_cycles, upper.exhausted_instructions) == (54, 40, 5, 4, 840, 83)


@pytest.mark.parametrize('entry,offset', ((0x1AE262, 0), (0x1AE27A, 10),
                                            (0x1AE292, 14), (0x1AE2AA, 22)))
def test_changed_allocator_instruction_is_rejected(rom, entry, offset):
    broken = bytearray(rom)
    broken[entry + offset] ^= 1
    with pytest.raises(ValueError, match='Unsupported allocator'):
        facts.decode_allocator_arms(bytes(broken))


def test_wrong_callee_or_mid_instruction_target_is_rejected(rom):
    broken = bytearray(rom)
    entry, target = 0x1B5266, 0x1AFD12  # historical invalid interior address
    broken[entry + 2:entry + 4] = ((target - (entry + 2)) & 0xffff).to_bytes(2, 'big')
    with pytest.raises(ValueError, match='callee'):
        facts.decode_allocator_arms(bytes(broken))


def test_changed_selector_operand_derives_an_endpoint_boundary_reject(rom):
    broken = bytearray(rom)
    broken[0x1AE262 + 5] ^= 8
    with pytest.raises(ValueError, match='Boundary arm facts'):
        facts.check_boundary_arms(facts.decode_allocator_arms(bytes(broken)))


def test_wrong_boundary_cost_is_rejected(rom, monkeypatch):
    arms = facts.allocator_arms(rom)
    original = boundary._SPAWN_REGION_ARMS[0x1B5266]
    monkeypatch.setitem(boundary._SPAWN_REGION_ARMS, 0x1B5266,
                        (*original[:4], original[4] + 2, *original[5:]))
    with pytest.raises(ValueError, match='Boundary arm facts'):
        facts.check_boundary_arms(arms)


PLAN_FIXTURES = (*ENTRY_FIXTURES,
                 ('lower', boundary.SPAWN_REGION_LOWER_ENTRY,
                  Path('artifacts/grinding/luna/allocator-arms-1b524e/old-225/1AE2AA-1B5262.alsnap'),
                  0xFF8368, 20, -1))


def _assert_plan_matches_rom_facts(rom, fixture, free, planner=boundary.spawn_region):
    _, entry, path, base, count, direction = fixture
    arm = facts.allocator_arms(rom)[entry]
    with Machine(read_rom(DEFAULT_ROM)) as machine:
        _prepare(machine, path, entry)
        _occupy(machine, base, count, direction, free)
        plan = planner(machine, machine.registers(), entry)
    if free is None:
        assert (plan.cycles, plan.instructions) == (
            arm.exhausted_cycles + arm.exhausted_fixed_cycles,
            arm.exhausted_instructions + arm.exhausted_fixed_instructions)
        assert plan.registers['a5'] == arm.exhausted_a5
        assert plan.registers['d0'] & 0xffff == 0xffff
        return
    assert (plan.cycles, plan.instructions) == (
        arm.free_cycles_base + arm.free_cycles_per_occupied * free + arm.free_fixed_cycles,
        arm.free_instructions_base + arm.free_instructions_per_occupied * free
        + arm.free_fixed_instructions)
    assert plan.registers['a5'] == arm.start + arm.direction * arm.stride * free


@pytest.mark.parametrize('fixture', PLAN_FIXTURES, ids=lambda item: item[0])
@pytest.mark.parametrize('free', (0, 1, 'last', None))
def test_runtime_spawn_plans_match_derived_scan_formula(rom, fixture, free):
    last = fixture[4] - 1
    _assert_plan_matches_rom_facts(rom, fixture, last if free == 'last' else free)


def test_runtime_scan_accounting_mutation_is_rejected(rom, monkeypatch):
    """Changing the produced scan accounting cannot hide behind arm constants."""
    original = boundary.spawn_region

    def mutated(machine, registers, entry):
        plan = original(machine, registers, entry)
        return replace(plan, cycles=plan.cycles + 2)

    monkeypatch.setattr(boundary, 'spawn_region', mutated)
    with pytest.raises(AssertionError):
        _assert_plan_matches_rom_facts(rom, PLAN_FIXTURES[0], 1, planner=boundary.spawn_region)
