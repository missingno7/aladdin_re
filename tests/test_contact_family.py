"""Qualification of the adjacent collection contact callback family.

The current cold history supplies recorded entry states for the 66 and motion
callbacks.  The sibling and sound arms are also qualified here with explicit
ROM-table fixtures; those cases are synthetic until a current recording hits
their callback entries.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega.boundary import (COLLECTION_DISPATCH_ENTRY,
                                   COLLECTION_DISPATCH_RETURN,
                                   CONTACT_COMPLETION_EXIT)


RECORD = 0xFF6000
SAFE_RETURN = 0x1B65BE
TARGET_KINDS = {
    0x1AFBF4: 0x65,  # recorded type-66 transition
    0x1AFC4E: 0x4F,  # synthetic on current main history
    0x1AF978: 0x6A,  # recorded contact motion transition
    0x1AF9F6: 0x76,  # synthetic on current main history
}


def family_fixture(target, *, kind=None, vertical=0x0800, blocked=0,
                   be=0, c0=0xFF, sound=0, flags=0x10,
                   previous=100, object_x=100, object_y=108,
                   origin_x=0, player_x=100, motion=0, object_delta=0,
                   publication=0, publication_index=0,
                   initial_d0=0xABCD1234, initial_d1=0x13572468,
                   initial_a3=0x0012A3B4, stack=0xFFEC00,
                   scratch_seed=0x5A,
                   incoming_x=False):
    """Park a real ROM collection dispatch at one selected callback."""
    if target not in TARGET_KINDS:
        raise ValueError(f"unknown contact-family target {target:06X}")
    rom = oracle.read_rom()
    table = 0x1CBE
    kind = TARGET_KINDS[target] if kind is None else kind
    assert int.from_bytes(rom[table + kind * 4:table + kind * 4 + 4], 'big') & 0xFFFFFF == target
    machine = oracle.cold_fixture(0x1B5266, pc_entry=COLLECTION_DISPATCH_ENTRY,
                                  incoming_x=incoming_x)
    try:
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        registers.update(a1=RECORD, d1=initial_d1, a3=initial_a3, d0=initial_d0,
                         d2=0x98764321, d7=0x76543210, a7=stack)
        writes = [(RECORD + i, 0xA5) for i in range(66)]
        # Keep a valid return runway for the 150-instruction continuation;
        # vary only the scratch words before the callback's outer slot.
        writes += [item for i in range(-16, 152)
                   for item in oracle.write_long(stack + 4 * i, SAFE_RETURN)]
        writes += [item for i in range(-16, 0)
                   for item in oracle.write_long(stack + 4 * i,
                                                (scratch_seed << 24) | (scratch_seed << 16)
                                                | (scratch_seed << 8) | scratch_seed)]
        # The ROM consumes byte +1C as a signed displacement.  Accepting a
        # caller spelling such as 0xFF80 is convenient in the matrix, but the
        # fixture must still materialize the single guest byte (0x80).
        writes += [(RECORD, kind), (RECORD + 6, flags),
                   (RECORD + 0x1C, object_delta & 0xFF),
                   (0xFFF0BE, be), (0xFFF0C0, c0), (0xFFF0E7, blocked),
                   (0xFFF0F5, 0x35), (0xFFF57D, sound)]
        for address, value in ((RECORD + 2, object_x), (RECORD + 4, object_y),
                               (0xFF7E5A, vertical), (0xFF7DFC, previous),
                               (0xFF7DFA, motion),
                               (0xFF7DF8, origin_x), (0xFF7E02, player_x),
                               (RECORD + 0x32, publication_index)):
            writes.extend(oracle.write_word(address, value))
        writes.append((RECORD + 0x34, publication & 0xFF))
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=writes, registers=registers)
        return machine.snapshot()
    finally:
        machine.close()


def qualify(state, candidate, *, future=150, stop_after_first=False):
    return oracle.execute_region(
        state, entry=COLLECTION_DISPATCH_ENTRY, candidate=candidate,
        expected_return=CONTACT_COMPLETION_EXIT, future_instructions=future,
        include_raw=True, stop_after_first=stop_after_first)


@pytest.mark.parametrize('target,values', [
    (0x1AFBF4, {'vertical': 0x0800, 'blocked': 0}),
    (0x1AFBF4, {'vertical': 0x0800, 'blocked': 1}),
    (0x1AF978, {'kind': 0x6A, 'be': 0, 'previous': 100, 'object_y': 108}),
    (0x1AF978, {'kind': 0x69, 'be': 0, 'previous': 100, 'object_y': 108}),
    (0x1AF9F6, {'kind': 0x76, 'be': 0, 'previous': 100, 'object_y': 111,
                'player_x': 100, 'object_delta': 0x0080}),
    (0x1AF9F6, {'kind': 0x76, 'be': 0, 'previous': 100, 'object_y': 111,
                'player_x': 0x0100}),
    (0x1AFC4E, {'vertical': 0x0800, 'player_x': 100, 'object_x': 100,
                'sound': 0}),
    (0x1AFC4E, {'vertical': 0x0800, 'player_x': 100, 'object_x': 100,
                'sound': 1}),
])
@pytest.mark.parametrize('incoming_x', [False, True])
def test_contact_family_dispatch_matches_original_outer_future_and_fresh(
        target, values, incoming_x):
    state = family_fixture(target, incoming_x=incoming_x, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    if values.get('sound', 0):
        assert actual.stats['legacy_entries'] == 1
        assert actual.stats['legacy_returns'] == 1


@pytest.mark.parametrize('target,values', [
    (0x1AFBF4, {'vertical': 0x0800}),
    (0x1AF978, {'kind': 0x6A, 'be': 0, 'previous': 100, 'object_y': 108}),
    (0x1AF9F6, {'kind': 0x76, 'be': 0, 'previous': 100, 'object_y': 111}),
    (0x1AFC4E, {'vertical': 0x0800, 'player_x': 100, 'object_x': 100,
                'sound': 0}),
    (0x1AFC4E, {'vertical': 0x0800, 'player_x': 100, 'object_x': 100,
                'sound': 1}),
])
@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_contact_family_mutants_diverge_at_outer_boundary(target, values, mutant,
                                                          monkeypatch):
    state = family_fixture(target, **values)
    expected = qualify(state, None)
    if target == 0x1AFC4E and values.get('sound') and mutant == 'continuation':
        # A sound request has two machine plans: its prefix enters the real
        # sound routine, while its suffix resumes at the object return.  A
        # generic PC+2 mutation of the prefix would execute arbitrary ROM and
        # turn the negative control into a native fault before observation.
        # Keep the legacy prefix intact and apply the same mutation to the
        # resumed outer plan, where divergence is directly observable.
        original_mutate = oracle.Candidate._mutate

        def suffix_only(candidate, plan):
            if (candidate.name.endswith('continuation') and
                    plan.registers.get('pc') == 0x1E58B8):
                return plan
            return original_mutate(candidate, plan)

        monkeypatch.setattr(oracle.Candidate, '_mutate', suffix_only)
    actual = qualify(state, 'lifecycle-mutant-' + mutant,
                     stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    if values.get('sound'):
        assert actual.stats['legacy_entries'] == 1
        assert actual.stats['legacy_returns'] == 1
    assert actual.outer != expected.outer


def test_contact_family_alias_and_signed_proximity_are_strictly_qualified():
    # This is an actual alias refusal: signed index B179 maps 1AE6DE's
    # publication byte onto the callback record itself.  The candidate must
    # leave the whole callback to the original machine rather than claiming a
    # plan whose writes overlap.
    state = family_fixture(0x1AF978, kind=0x6A, be=0, previous=100,
                           object_y=108, publication=1, publication_index=0xB179)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['fallbacks'] == 1


@pytest.mark.parametrize('target,values', [
    (0x1AF978, {'kind': 0x6A, 'be': 0, 'previous': 111, 'object_y': 108}),
    (0x1AF978, {'kind': 0x6A, 'be': 0, 'previous': 112, 'object_y': 108}),
    (0x1AF978, {'kind': 0x6A, 'be': 0, 'previous': 99, 'object_y': 108}),
    (0x1AF978, {'kind': 0x6A, 'be': 0, 'previous': 88, 'object_y': 108}),
    (0x1AF9F6, {'kind': 0x76, 'be': 0, 'previous': 105, 'object_y': 111,
                'object_delta': 0x0080}),
    (0x1AF9F6, {'kind': 0x76, 'be': 0, 'previous': 106, 'object_y': 111,
                'object_delta': 0x0080}),
    (0x1AF9F6, {'kind': 0x76, 'be': 0, 'previous': 99, 'object_y': 111,
                'object_delta': 0xFF80}),
    (0x1AF9F6, {'kind': 0x76, 'be': 0, 'previous': 94, 'object_y': 111,
                'object_delta': 0xFF80}),
])
def test_contact_family_proximity_boundaries_match_original(target, values):
    expected = qualify(family_fixture(target, **values), None)
    actual = qualify(family_fixture(target, **values), 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('motion', [0x0000, 0xFFFF, 0x7FFF])
@pytest.mark.parametrize('object_delta', [0x7F, 0x80, 0xFF])
def test_secondary_motion_signed_byte_accumulation_and_carry(motion, object_delta):
    # +1C is a sign-extended byte added to the pre-existing secondary motion
    # word.  Exercise both sign boundaries and carry/borrow around varied
    # 16-bit starting values rather than treating it as a wide integer.
    values = {'kind': 0x76, 'be': 0, 'previous': 100, 'object_y': 111,
              'player_x': 100, 'motion': motion, 'object_delta': object_delta}
    expected = qualify(family_fixture(0x1AF9F6, **values), None)
    actual = qualify(family_fixture(0x1AF9F6, **values), 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('target,values', [
    (0x1AFBF4, {'vertical': 0x0800, 'initial_d0': 0xDEAD1234,
                'initial_d1': 0xCAFEBABE, 'initial_a3': 0x00ABCDEF,
                'stack': 0xFFED00, 'scratch_seed': 0x3C}),
    (0x1AF978, {'kind': 0x6A, 'be': 0, 'previous': 100, 'object_y': 108,
                'publication': 1, 'publication_index': 2,
                'initial_d0': 0xDEAD1234, 'initial_d1': 0xCAFEBABE,
                'initial_a3': 0x00ABCDEF, 'stack': 0xFFED00,
                'scratch_seed': 0x3C}),
])
def test_contact_family_preserves_register_and_stack_variants(target, values):
    state = family_fixture(target, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_contact_family_synthetic_guard_paths_remain_original_when_unowned():
    # These are explicitly constructed guards.  They document the supported
    # domain without claiming current replay coverage for every sibling arm.
    for target, values in (
            (0x1AF978, {'be': 1, 'c0': 0}),
            (0x1AF978, {'be': 0, 'flags': 0}),
            (0x1AF9F6, {'be': 1, 'c0': 0}),
            (0x1AFC4E, {'vertical': 0x8000}),
            (0x1AFC4E, {'blocked': 1}),
            (0x1AFC4E, {'player_x': 50}),
            (0x1AFC4E, {'player_x': 130}),
    ):
        state = family_fixture(target, **values)
        expected = qualify(state, None)
        actual = qualify(state, 'lifecycle')
        assert actual.outer == expected.outer
        assert actual.future == expected.future
        assert actual.stats['collection_dispatch_hits'] == 1
        assert actual.stats['fallbacks'] == 0


def test_contact_family_scheduler_deadline_refuses_without_partial_plan():
    state = family_fixture(0x1AFBF4, vertical=0x0800)
    original = oracle.Machine(oracle.read_rom())
    try:
        original.restore(state)
        original.gates([COLLECTION_DISPATCH_ENTRY])
        assert original.run(instructions=1) == 'gate'
        original.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
        assert original.run(instructions=1) == 'limit'
        expected = oracle.observable(original)
    finally:
        original.close()

    candidate_machine = oracle.Machine(oracle.read_rom())
    try:
        candidate_machine.restore(state)
        candidate_machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert candidate_machine.run(instructions=1) == 'gate'
        candidate = oracle.Candidate('lifecycle')
        candidate.arm(candidate_machine)
        assert candidate_machine.run(instructions=1) == 'gate'
        assert not candidate.on_gate(candidate_machine, candidate_machine.info['tick'] + 1)
        assert candidate.stats['fallback_reasons'] == {'scheduler admission': 1}
        assert oracle.observable(candidate_machine) == expected
    finally:
        candidate_machine.close()
