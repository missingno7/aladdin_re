"""Whole contact tick through the original collection sound service."""
import pytest
import oracle_witness as oracle
from test_contact_step import step_fixture, ENTRY, RETURN, RECORD


def sound_fixture(*, kind=0x35, two=False):
    state = step_fixture(kind=kind, two=two)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        machine.gates([ENTRY]); assert machine.run(instructions=1) == 'gate'
        writes = [(0xFFF57D, 1), (0xFFF0D8, 0),
                  *oracle.write_word(0xFFEFE0, 0x3030),
                  *oracle.write_word(0xFFEFE2, 0x3030)]
        for record in (RECORD, RECORD + 23 * 66) if two else (RECORD,):
            writes += [(record + 6, 0), (record + 41, 0),
                       *oracle.write_long(record + 42, 0),
                       *oracle.write_long(record + 62, 0),
                       (record + 52, 0)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1, last_pc=ENTRY,
                              writes=writes, registers=machine.registers())
        return machine.snapshot()


@pytest.mark.parametrize('kind', (0x35, 0x34))
def test_parent_owns_prefix_and_suffix_across_original_sound(kind):
    """The record's own contact_step_plan composition now truncates its
    scan at the seam slot (0x1ABBE0) instead of declining the whole tick,
    so the seam itself is owned by COLLECTION_DISPATCH_ENTRY -- the same
    per-slot dispatcher gate a direct (non-scan) callback already uses --
    rather than by contact_step's own begin_contact_step_sound fallback.
    The outer/future result is unaffected; only which gate legitimately
    owns the sound call changes."""
    state = sound_fixture(kind=kind)
    expected = oracle.execute_region(state, entry=ENTRY, candidate=None,
                                     expected_return=RETURN, include_raw=True)
    actual = oracle.execute_region(state, entry=ENTRY, candidate='lifecycle',
                                   expected_return=RETURN, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['contact_step_hits'] == 1
    assert actual.stats['legacy_entries'] == actual.stats['legacy_returns'] == 1
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == actual.stats['local_fallbacks'] == 0


def test_second_sound_in_the_same_scan_no_longer_needs_a_local_fallback():
    """Both records' sound calls are now recovered independently through
    COLLECTION_DISPATCH_ENTRY (the truncated scan hands each seam slot to
    that already-existing per-slot gate rather than composing them as one
    batch), so neither needs the local-fallback degradation the previous
    single-pass recipe required for a second sound call."""
    state = sound_fixture(two=True)
    expected = oracle.execute_region(state, entry=ENTRY, candidate=None,
                                     expected_return=RETURN, include_raw=True)
    actual = oracle.execute_region(state, entry=ENTRY, candidate='lifecycle',
                                   expected_return=RETURN, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['contact_step_hits'] == 1
    assert actual.stats['collection_dispatch_hits'] == 2
    assert actual.stats['legacy_entries'] == actual.stats['legacy_returns'] == 2
    assert actual.stats['fallbacks'] == actual.stats['local_fallbacks'] == 0


@pytest.mark.parametrize('kind', (0x05, 0x06))
def test_parent_composes_sibling_command8_sound(kind):
    state = sound_fixture(kind=kind)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        machine.gates([ENTRY]); assert machine.run(instructions=1) == 'gate'
        writes = [(0xFFF0D8, 1), (0xFFF57D, 1),
                  *oracle.write_word(0xFF7E02, 99),
                  (RECORD + 1, 2), (RECORD + 6, 0)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1, last_pc=ENTRY,
                              writes=writes, registers=machine.registers())
        state = machine.snapshot()
    expected = oracle.execute_region(state, entry=ENTRY, candidate=None,
                                     expected_return=RETURN, include_raw=True)
    actual = oracle.execute_region(state, entry=ENTRY, candidate='lifecycle',
                                   expected_return=RETURN, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['contact_step_hits'] == 1
    assert actual.stats['legacy_entries'] == actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == actual.stats['local_fallbacks'] == 0


@pytest.mark.parametrize('remaining,record', ((24, RECORD), (65535, RECORD),
                                            (23, RECORD + 66), (0, RECORD)))
def test_sound_resume_rejects_invalid_live_scan_cursor(remaining, record):
    import aladdin_sega.boundary as boundary
    state = sound_fixture()
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        before = machine.snapshot()
        registers = {**machine.registers(), 'pc': boundary.CONTACT_COMPLETION_EXIT,
                     'd4': remaining, 'a1': record}
        with pytest.raises(boundary.UnsupportedCandidate, match='resume cursor'):
            boundary._contact_scan_resume(machine, registers)
        assert machine.snapshot() == before


@pytest.mark.parametrize('mutation', ('a1', 'd4', 'pc', 'timing'))
def test_parent_sound_suffix_mutations_are_observable(monkeypatch, mutation):
    """finish_contact_step_sound (the begin_contact_step_sound suffix) is no
    longer reached for a fresh first-slot seam -- contact_step_plan now
    truncates its own scan there and COLLECTION_DISPATCH_ENTRY owns it
    directly (see test_parent_owns_prefix_and_suffix_across_original_sound).
    finish_contact_step_sound's own mutation-safety still matters for the
    narrower set of failures that still reach it (contact_step_plan's other
    guards, e.g. an unaligned outer return), so this test forces that path
    by making contact_scan_plan itself decline, exactly as it would for one
    of those other reasons, and checks the suffix mutation is still caught."""
    from dataclasses import replace
    import aladdin_sega.boundary as boundary
    from aladdin_sega.recovery import Candidate
    state = sound_fixture()
    expected = oracle.execute_region(state, entry=ENTRY, candidate=None,
                                     expected_return=RETURN, include_raw=True)
    monkeypatch.setattr(boundary, 'contact_scan_plan',
                        lambda machine, registers: (_ for _ in ()).throw(
                            boundary.UnsupportedCandidate('forced for mutation test')))
    original = boundary.finish_contact_step_sound
    def wrong(*args, **kwargs):
        plan = original(*args, **kwargs)
        if mutation == 'timing':
            return replace(plan, cycles=plan.cycles + 4)
        registers = dict(plan.registers)
        registers[mutation] ^= 2
        return replace(plan, registers=registers)
    monkeypatch.setattr(boundary, 'finish_contact_step_sound', wrong)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        candidate = Candidate('lifecycle'); candidate.arm(machine)
        assert machine.run(instructions=1) == 'gate'
        assert candidate.on_gate(machine, machine.info['tick'] + 10_000_000)
        assert candidate.stats['legacy_entries'] == candidate.stats['legacy_returns'] == 1
        assert candidate.stats['local_fallbacks'] == 0
        assert oracle.observable(machine) != expected.outer


@pytest.mark.parametrize('kind', (0x79, 0x1F, 0x15, 0x44))
def test_qualified_family_ram_paths_are_internal_to_parent(kind):
    state = sound_fixture(kind=kind)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state); machine.gates([ENTRY])
        assert machine.run(instructions=1) == 'gate'
        writes = [(0xFFF57D, 0), (0xFFF0D8, 0 if kind == 0x1F else 1),
                  (RECORD + 0x3C, 0), (RECORD + 1, 2),
                  *oracle.write_word(0xFF7E02, 100), (0xFF7E21, 0),
                  (0xFFEFFA, 1), (0xFFEFFB, 9)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1, last_pc=ENTRY,
                              writes=writes, registers=machine.registers())
        state = machine.snapshot()
    expected = oracle.execute_region(state, entry=ENTRY, candidate=None,
                                     expected_return=RETURN, include_raw=True)
    actual = oracle.execute_region(state, entry=ENTRY, candidate='lifecycle',
                                   expected_return=RETURN, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['contact_step_hits'] == 1
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] == 0
