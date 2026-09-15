"""Original-ROM qualification of the Type-2C/2D/2E/31/6D own-buffer release
and nested CONTACT_ENTRY BSR.

1AEE40 gates on FFF0D8: clear, it self-retypes (clears the record's own
kind byte), releases the record's own attached buffer through the
already-proven ``_clear_objects(pair=False)`` adapter (also proven for
Type-0C), then BSRs the shared 1AE4F8 contact root -- composed exactly as
``begin_contact_dispatch``/``begin_contact_dispatch_sound`` and Type-78's
own nested BSR compose that same call, through the already-proven
``begin_contact``/``begin_contact_sound``.  Active (FFF0D8 set) instead
continues into a pool-scan-and-spawn arm behind a new subroutine 1AE2DA
that is not recovered here.  Five collection-dispatch kinds (0x2C, 0x2D,
0x2E, 0x31, 0x6D) all share this one entry.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega import boundary
from test_contact_family import family_fixture, RECORD, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture, RECORD as SCAN_RECORD
from aladdin_sega.boundary import COLLECTION_DISPATCH_ENTRY


def type2c_fixture(*, gate=0, own_buffer=0, own_length=6, **kwargs):
    """Construct a valid Type-2C collection record over the original ROM.

    ``family_fixture`` seeds the record's own FFF0D8 gate (``gate`` --
    clear, not set, is this entry's own recovered arm); this optionally
    adds an attached buffer (record+42/record+41) for the single
    ``_clear_objects(pair=False)`` release to find, matching Type-0C's
    own fixture.
    """
    state = family_fixture(0x1AEE40, active_d8=gate, **kwargs)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        writes = [(RECORD + 41, own_length), *oracle.write_long(RECORD + 42, own_buffer)]
        if own_buffer:
            writes += [(own_buffer + i, 0xA5) for i in range(own_length + 1)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=writes, registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


def _assert_matches_oracle(state):
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('kind', (0x2C, 0x2D, 0x2E, 0x31, 0x6D))
def test_type2c_gate_clear_calls_contact_root(monkeypatch, kind):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEE40, kind)
    state = type2c_fixture(gate=0, kind=kind)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('own_buffer', (0, 0xFFD000))
def test_type2c_gate_clear_owns_buffer_release(monkeypatch, own_buffer):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEE40, 0x2D)
    state = type2c_fixture(gate=0, own_buffer=own_buffer)
    _assert_matches_oracle(state)


def test_type2c_gate_clear_sound_arm_matches_original(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEE40, 0x2D)
    state = type2c_fixture(gate=0, sound=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type2c_gate_set_pool_scan_is_owned(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEE40, 0x2D)
    state = type2c_fixture(gate=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_type2c_sound_seam_declines_when_gate_set(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEE40, 0x2D)
    state = type2c_fixture(gate=1, sound=1)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        with pytest.raises(boundary.UnsupportedCandidate, match='pool-scan-and-spawn arm is not recovered'):
            boundary.begin_contact_family_type2c_sound(machine, registers)


@pytest.mark.parametrize('arm', ('clear', 'clear_buffer'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type2c_every_ram_only_arm_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEE40, 0x2D)
    if arm == 'clear':
        state = type2c_fixture(gate=0)
    else:
        state = type2c_fixture(gate=0, own_buffer=0xFFD000)
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        original = boundary.begin_contact_family_type2c
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == RECORD for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type2c', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type2c_declines_unaligned_stack(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AEE40, 0x2D)
    state = type2c_fixture(gate=0)
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned type2c'):
            boundary.begin_contact_family_type2c(machine, registers)


# --- parent ownership ---------------------------------------------------------


def test_type2c_is_owned_inside_the_complete_contact_scan(monkeypatch):
    original = boundary.begin_contact_family_type2c_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type2c_dispatch', observed)
    state = scan_fixture(kind=0x2D)
    # scan_fixture's own template leaves record+42 (the buffer pointer
    # _clear_objects reads) as unrelated filler; FFF0D8 defaults clear,
    # which is this entry's own recovered (not declined) arm, unlike the
    # sibling families whose "active" gate is FFF0D8 *set* -- zero the
    # pointer so the real, owned buffer-release path runs safely.
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        machine.gates([SCAN_ENTRY]); assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1, last_pc=SCAN_ENTRY,
                              writes=[*oracle.write_long(SCAN_RECORD + 42, 0)],
                              registers=registers)
        state = machine.snapshot()
    expected = oracle.execute_region(state, entry=SCAN_ENTRY, candidate=None,
                                     expected_return=SCAN_EXIT, include_raw=True)
    actual = oracle.execute_region(state, entry=SCAN_ENTRY, candidate='lifecycle',
                                   expected_return=SCAN_EXIT, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['contact_scan_hits'] == 1
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] == 0
    assert calls == 1


# ---------------------------------------------------------------------------
# FFF0D8 set: stash the record in the extra pool, optional command 21, then a
# main-pool spawn from template 1B7E40.
# ---------------------------------------------------------------------------

EXTRA_POOL, MAIN_POOL = 0xFF84B2, 0xFF7E82


def _active_fixture(*, sound, extra_free, main_free, **kwargs):
    """``extra_free``/``main_free``: index of the first free slot, or None for exhausted."""
    state = type2c_fixture(gate=1, sound=sound, **kwargs)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        writes = [(EXTRA_POOL + i * 66, 0 if extra_free == i else 0x11) for i in range(6)]
        writes += [(MAIN_POOL + i * 66, 0 if main_free == i else 0x22) for i in range(24)]
        writes += [(RECORD + 2, 0x03), (RECORD + 3, 0x21), (RECORD + 4, 0x01), (RECORD + 5, 0xF8)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY, writes=writes,
                              registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


@pytest.mark.parametrize('extra_free', (0, 3, 5, None), ids=('extra-first', 'extra-mid', 'extra-last', 'extra-full'))
@pytest.mark.parametrize('main_free', (0, 7, 23, None), ids=('main-first', 'main-mid', 'main-last', 'main-full'))
@pytest.mark.parametrize('sound', (0, 1), ids=('sound-off', 'sound-on'))
def test_type2c_active_arm_matches_original(extra_free, main_free, sound):
    state = _active_fixture(sound=sound, extra_free=extra_free, main_free=main_free)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == sound
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
@pytest.mark.parametrize('sound', (0, 1), ids=('sound-off', 'sound-on'))
def test_type2c_active_arm_mutants_diverge_at_outer_boundary(mutant, sound, monkeypatch):
    state = _active_fixture(sound=sound, extra_free=0, main_free=0)
    expected = qualify(state, None)
    if mutant == 'continuation' and sound:
        original_mutate = oracle.Candidate._mutate

        def suffix_only(candidate, plan):
            if candidate.name.endswith('continuation') and plan.registers.get('pc') == 0x1E58B8:
                return plan
            return original_mutate(candidate, plan)

        monkeypatch.setattr(oracle.Candidate, '_mutate', suffix_only)
    actual = qualify(state, 'lifecycle-mutant-' + mutant, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer
