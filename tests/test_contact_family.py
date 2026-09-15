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
    0x1AED86: 0x03,  # recorded D8-zero contact sound wrapper
    0x1AEF5C: 0x46,  # recorded command-66 counted replacement
    0x1AFBF4: 0x65,  # recorded type-66 transition
    0x1AFC4E: 0x4F,  # synthetic on current main history
    0x1AF978: 0x6A,  # recorded contact motion transition
    0x1AF9F6: 0x76,  # synthetic on current main history
    0x1AE978: 0x15,  # recorded type-15 sibling wrapper
    0x1AEF12: 0x44,  # type-44 counter/replacement callback
    0x1AEB7C: 0x79,  # type-79 guard return
    0x1AE796: 0x1F,  # recorded inactive position tail
    0x1AE64C: 0x43,  # recorded collection-dispatcher motion/type update
    0x1AF5F0: 0x58,  # recorded bounded-distance guard, both arms owned
    0x1AFA84: 0x74,  # recorded bounded-distance guard, window/kind/state gate and child spawn
    0x1AFB36: 0x6E,  # recorded gate cascade, dual-axis distance guard and FFF103 state tail (kinds 6E-73)
    0x1AE9E0: 0x1A,  # recorded FFF0D8 gate, self pair-release and 1B7940 re-template
    0x1AEECA: 0x23,  # recorded FFF0D8 gate, self-retype and double pool-slot spawn
    0x1AEB7A: 0x0D,  # recorded unconditional RTS stub
    0x1AEBFE: 0x14,  # recorded unconditional RTS stub (also reached by kind 0x2B)
    0x1AE9A8: 0x0C,  # recorded FFF0D8 gate, own-buffer release and 1B7CC4 re-template
    0x1AEBDC: 0x78,  # recorded FFF0D8 gate, +/-8 window guard, BSR into shared 1AE4F8 (also kind 0x7A)
    0x1AF81C: 0x63,  # recorded bounded-distance guard (limit 0xA) + self-kind check (also kind 0x62)
    0x1AEE40: 0x2D,  # recorded FFF0D8 gate, own-buffer release (1AE372) + BSR into shared 1AE4F8 (also 2C/2E/31/6D)
    0x1AE9C6: 0x13,  # recorded C6 sibling wrapper: the type-13 decrement bridges command 8 to 1AECBE
}


def family_fixture(target, *, kind=None, vertical=0x0800, blocked=0,
                   be=0, c0=0xFF, sound=0, flags=0x10,
                   previous=100, object_x=100, object_y=108,
                   origin_x=0, player_x=100, motion=0, object_delta=0,
                   publication=0, publication_index=0,
                   initial_d0=0xABCD1234, initial_d1=0x13572468,
                   initial_a3=0x0012A3B4, stack=0xFFEC00,
                   scratch_seed=0x5A,
                   incoming_x=False, active_d8=0, gate_e7=None, gate_f2=0,
                   contact_bit5=0, direction=0, finish_gate=None,
                   record_counter=None, decimal_current=None, decimal_limit=None,
                   type46_counter=None):
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
                   (0xFFF0D8, active_d8), (0xFFF0E7, blocked if gate_e7 is None else gate_e7),
                   (0xFFF0F2, gate_f2),
                   (RECORD + 0x3C, contact_bit5),
                   (0xFF7E49, direction),
                   (0xFFF0F5, 0x35), (0xFFF57D, sound)]
        if finish_gate is not None:
            writes.append((0xFF7E21, finish_gate))
        if record_counter is not None:
            writes.append((RECORD + 1, record_counter))
        if decimal_current is not None:
            writes.append((0xFFEFFA, decimal_current))
        if decimal_limit is not None:
            writes.append((0xFFEFFB, decimal_limit))
        if type46_counter is not None:
            writes.append((0xFF7E3C, type46_counter))
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


def type44_fixture(*, sound, finish_gate, decimal_current, decimal_limit):
    """Construct a valid byte-backed replacement record over the original ROM."""
    state = family_fixture(0x1AEF12, flags=0)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=[(0xFFF57D, sound), (0xFF7E21, finish_gate),
                                      (0xFFEFFA, decimal_current),
                                      (0xFFEFFB, decimal_limit),
                                      *oracle.write_long(RECORD + 42, 0),
                                      *oracle.write_long(RECORD + 62, 0)],
                              registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


def type46_fixture():
    """Construct a valid command-66 replacement record over the original ROM."""
    state = family_fixture(0x1AEF5C, sound=1, type46_counter=0x35)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=[*oracle.write_long(RECORD + 42, 0),
                                      *oracle.write_long(RECORD + 62, 0)],
                              registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


def type43_fixture(*, fff0c1=0xFF, sound=1, motion_x=0x0140, **kwargs):
    """Construct a valid Type-43 collection record over the original ROM.

    ``family_fixture`` seeds the record's link field (object_x at record+2),
    FF7DF8/FF7DFA/FF7DFC and FFF57D; this adds the FFF0C1 activity gate and
    the FF7DF6 horizontal-motion word the branch also reads.
    """
    state = family_fixture(0x1AE64C, sound=sound, **kwargs)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        writes = [(0xFFF0C1, fff0c1), *oracle.write_word(0xFF7DF6, motion_x)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=writes, registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


def type6e_fixture(*, origin_x2=0, fff103=1, **kwargs):
    """Construct a valid Type-6E collection record over the original ROM.

    ``family_fixture`` seeds the record's own link field (object_x at
    record+2), FF7DF8/FF7DFA(``motion``)/FF7DFC and FFF0E7(``blocked``)/
    FFF0BE(``be``)/FFF0C0(``c0``); this adds the FF7DF6 horizontal target
    the X-axis guard reads and the FFF103 state-machine key its tail
    branches on.
    """
    state = family_fixture(0x1AFB36, **kwargs)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        writes = [*oracle.write_word(0xFF7DF6, origin_x2), (0xFFF103, fff103)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=writes, registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


def type1a_fixture(*, active=1, own_buffer=0, own_length=6, linked=0, linked_buffer=0,
                   linked_length=3, **kwargs):
    """Construct a valid Type-1A collection record over the original ROM.

    ``family_fixture`` seeds the record's own FFF0D8 gate (``active_d8``);
    this adds the record's own attached-buffer pointer/length (record+42/
    record+41), its record+62 link to a second synthetic record, and that
    linked record's own attached-buffer pointer/length.
    """
    state = family_fixture(0x1AE9E0, active_d8=active, **kwargs)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        writes = [(RECORD + 41, own_length), *oracle.write_long(RECORD + 42, own_buffer)]
        if own_buffer:
            writes += [(own_buffer + i, 0xA5) for i in range(own_length + 1)]
        if linked:
            writes += [*oracle.write_long(RECORD + 62, linked)]
            writes += [(linked + i, 0xA5) for i in range(66)]
            writes += [(linked + 41, linked_length), *oracle.write_long(linked + 42, linked_buffer)]
            if linked_buffer:
                writes += [(linked_buffer + i, 0xA5) for i in range(linked_length + 1)]
        else:
            writes += [*oracle.write_long(RECORD + 62, 0)]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=writes, registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


def type23_fixture(*, active=1, occupy_primary=(), occupy_secondary=(), **kwargs):
    """Construct a valid Type-23 collection record over the original ROM.

    ``family_fixture`` seeds the record's own FFF0D8 gate (``active_d8``);
    this optionally occupies chosen 0-based slot indices of the primary
    (FF7F06, 20 slots) and secondary (FF7E82, 24 slots) pools the two
    spawn attempts search, to exercise a specific found index or
    exhaustion of either.
    """
    state = family_fixture(0x1AEECA, active_d8=active, **kwargs)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        writes = [(0xFF7F06 + i * 66, 0x99) for i in occupy_primary]
        writes += [(0xFF7E82 + i * 66, 0x99) for i in occupy_secondary]
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=writes, registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


def type0c_fixture(*, active=1, own_buffer=0, own_length=6, **kwargs):
    """Construct a valid Type-0C collection record over the original ROM.

    ``family_fixture`` seeds the record's own FFF0D8 gate (``active_d8``);
    this optionally adds an attached buffer (record+42/record+41) for the
    single ``_clear_objects(pair=False)`` release to find.
    """
    state = family_fixture(0x1AE9A8, active_d8=active, **kwargs)
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


def test_type79_guard_return_matches_original_outer_future_and_fresh():
    state = family_fixture(0x1AEB7C, active_d8=1, gate_e7=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type79_sound_guard_return_matches_original_outer_future_and_fresh():
    state = family_fixture(0x1AEB7C, active_d8=0, gate_f2=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('values', [
    {'direction': 0, 'player_x': 99, 'object_x': 100, 'active_d8': 0},
    {'direction': 0, 'player_x': 100, 'object_x': 100, 'active_d8': 1},
    {'direction': 1, 'player_x': 99, 'object_x': 100, 'active_d8': 1},
    {'direction': 1, 'player_x': 100, 'object_x': 100, 'active_d8': 0},
])
def test_type1f_rts_tails_match_original_outer_future_and_fresh(values):
    state = family_fixture(0x1AE796, contact_bit5=0, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type1f_inactive_contact_early_return_matches_original_future_and_fresh():
    state = family_fixture(0x1AE796, active_d8=0, object_x=100, player_x=99,
                           contact_bit5=0x20, gate_f2=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type1f_inactive_contact_sound_matches_original_future_and_fresh():
    state = family_fixture(0x1AE796, active_d8=0, object_x=100, player_x=99,
                           contact_bit5=0x20, gate_f2=0, sound=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type1f_direct_finish_transition_matches_original_future_and_fresh():
    state = family_fixture(0x1AE796, active_d8=1, object_x=100, player_x=99,
                           contact_bit5=0, finish_gate=1, record_counter=0)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=(*oracle.write_long(RECORD + 42, 0),
                                      *oracle.write_long(RECORD + 62, 0)), registers={})
        state = machine.snapshot()
    finally:
        machine.close()
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('kind', (0x1E, 0x1F, 0x21, 0x22))
def test_type1f_zero_finish_gate_transition_matches_original_future_and_fresh(kind):
    state = family_fixture(0x1AE796, kind=kind, active_d8=1,
                           object_x=100, player_x=99, contact_bit5=0,
                           finish_gate=0, record_counter=1)
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=(*oracle.write_long(RECORD + 42, 0),
                                      *oracle.write_long(RECORD + 62, 0)), registers={})
        state = machine.snapshot()
    finally:
        machine.close()
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type1f_direct_command41_transition_matches_original_future_and_fresh():
    state = family_fixture(0x1AE796, active_d8=1, object_x=100, player_x=99,
                           contact_bit5=0, finish_gate=1, record_counter=1, sound=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('kind', (0x1E, 0x1F, 0x21, 0x22))
def test_type1f_direct_soundoff_transition_matches_original_future_and_fresh(kind):
    state = family_fixture(0x1AE796, kind=kind, active_d8=1, object_x=100, player_x=99,
                           contact_bit5=0, finish_gate=1, record_counter=1, sound=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 0
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type1e_direct_command41_transition_matches_original_future_and_fresh():
    state = family_fixture(0x1AE796, kind=0x1E, active_d8=1,
                           object_x=100, player_x=99, contact_bit5=0,
                           finish_gate=1, record_counter=1, sound=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('kind', (0x21, 0x22))
def test_type1f_sibling_direct_command41_transition_matches_original_future_and_fresh(kind):
    state = family_fixture(0x1AE796, kind=kind, active_d8=1,
                           object_x=100, player_x=99, contact_bit5=0,
                           finish_gate=1, record_counter=1, sound=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('values', [
    {'direction': 0, 'player_x': 100, 'object_x': 100},                 # position failed
    {'direction': 1, 'player_x': 99, 'object_x': 100},                  # position failed, reversed
    {'direction': 1, 'player_x': 100, 'object_x': 100, 'active_d8': 0}, # position ok, D8 clear, reversed
    {'direction': 0, 'player_x': 99, 'object_x': 100, 'active_d8': 0},  # the originally recorded arm
], ids=['pos-fail', 'pos-fail-reversed', 'd8-zero-reversed', 'd8-zero'])
@pytest.mark.parametrize('root', [{'gate_f2': 1}, {'gate_f2': 0, 'sound': 1}],
                         ids=['early-root', 'sound-reset-root'])
def test_type1f_contact_join_arms_match_original(values, root):
    """Every route into 1AE862 with bit 5 set calls the shared contact root."""
    state = family_fixture(0x1AE796, contact_bit5=0x20, **values, **root)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == (1 if root.get('sound') else 0)
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('kind', (0x1E, 0x1F, 0x21, 0x22))
@pytest.mark.parametrize('direction,player_x', [(0, 99), (1, 100)], ids=['forward', 'reversed'])
def test_type1f_finish_gate_counter_zero_transition_matches_original(kind, direction, player_x):
    """FF7E21 set with a zero counter takes the same direct finish as the gate-clear arm."""
    state = _poke(family_fixture(0x1AE796, kind=kind, active_d8=1, object_x=100, player_x=player_x,
                                 direction=direction, contact_bit5=0, finish_gate=1, record_counter=0),
                  (*oracle.write_long(RECORD + 42, 0), *oracle.write_long(RECORD + 62, 0)))
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('kind', (0x1E, 0x21))
@pytest.mark.parametrize('sound', (0, 1), ids=['soundoff', 'command41'])
def test_type1f_reversed_counter_transition_matches_original(kind, sound):
    """The reversed direction only changes the compare's branch timing."""
    state = family_fixture(0x1AE796, kind=kind, active_d8=1, object_x=100, player_x=100,
                           direction=1, contact_bit5=0, finish_gate=1, record_counter=2, sound=sound)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == sound
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('values', ({'contact_bit5': 0x20, 'active_d8': 1, 'player_x': 99, 'object_x': 100},))
def test_type1f_non_rts_arms_decline_to_original(values):
    """Bit 5 set with the record active is the device/stream arm and stays original."""
    state = family_fixture(0x1AE796, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] >= 1


def test_type79_sound_arm_matches_original_outer_future_and_fresh():
    state = family_fixture(0x1AEB7C, active_d8=0, sound=1)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('values', ({'active_d8': 0, 'sound': 0}, {'gate_e7': 1}))
def test_type79_nonreturn_arms_decline_to_original(values):
    state = family_fixture(0x1AEB7C, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] >= 1


@pytest.mark.parametrize('values', [
    {'direction': 0, 'player_x': 100, 'object_x': 100},
    {'direction': 1, 'player_x': 99, 'object_x': 100},
    {'direction': 0, 'player_x': 99, 'object_x': 100, 'record_counter': 1},
    {'direction': 1, 'player_x': 100, 'object_x': 100, 'record_counter': 1},
])
def test_type15_sibling_wrapper_early_and_decrement_paths_match_original(values):
    expected = qualify(family_fixture(0x1AE978, active_d8=1, sound=0, **values), None)
    actual = qualify(family_fixture(0x1AE978, active_d8=1, sound=0, **values),
                     'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('values', [
    {'direction': 0, 'player_x': 99, 'object_x': 100, 'record_counter': 2},
    {'direction': 1, 'player_x': 100, 'object_x': 100, 'record_counter': 1},
    {'direction': 0, 'player_x': 99, 'object_x': 100, 'record_counter': 3},
])
def test_type15_sibling_wrapper_decrement_sound_seams_match_original(values):
    """Sound on: the sibling's command-8 decrement seam, then 1AE97C's D8 tail."""
    state = family_fixture(0x1AE978, active_d8=1, sound=1, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('direction,player_x', [(0, 99), (1, 100)], ids=['forward', 'reversed'])
def test_type13_sibling_decrement_bridges_to_its_rts(direction, player_x):
    """Kind 13 requests command 6A after the selector: the machine bridges to 1AECBE."""
    state = family_fixture(0x1AE9C6, active_d8=1, sound=1, direction=direction,
                           player_x=player_x, object_x=100, record_counter=4)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type13_sibling_bridge_mutants_diverge_at_outer_boundary(mutant, monkeypatch):
    state = family_fixture(0x1AE9C6, active_d8=1, sound=1, direction=0,
                           player_x=99, object_x=100, record_counter=4)
    expected = qualify(state, None)
    if mutant == 'continuation':
        original_mutate = oracle.Candidate._mutate

        def suffix_only(candidate, plan):
            if candidate.name.endswith('continuation') and plan.registers.get('pc') == 0x1E58B8:
                return plan
            return original_mutate(candidate, plan)

        monkeypatch.setattr(oracle.Candidate, '_mutate', suffix_only)
    actual = qualify(state, 'lifecycle-mutant-' + mutant, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def _poke(state, writes):
    """Return ``state`` with extra work-RAM bytes written at the dispatch gate."""
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(state)
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1,
                              last_pc=COLLECTION_DISPATCH_ENTRY, writes=list(writes),
                              registers=machine.registers())
        return machine.snapshot()
    finally:
        machine.close()


@pytest.mark.parametrize('digits', [(0x33, 0x35), (0x33, 0x30), (0x30, 0x30), (0x31, 0x30),
                                    (0x30, 0x32), (0x00, 0x00)],
                         ids=['plain', 'borrow', 'zero', 'borrow-to-zero-tens', 'floor-then-zero',
                              'non-digit'])
def test_type15_sibling_wrapper_inactive_tail_matches_original(digits):
    """FFF0D8 clear: the sibling returns at once and 1AE97C runs three 1B0360 decrements."""
    state = _poke(family_fixture(0x1AE978, active_d8=0, sound=0),
                  [(0xFFEFE0, digits[0]), (0xFFEFE1, digits[1])])
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type15_inactive_tail_mutants_diverge_at_outer_boundary(mutant):
    state = _poke(family_fixture(0x1AE978, active_d8=0, sound=0),
                  [(0xFFEFE0, 0x33), (0xFFEFE1, 0x30)])
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle-mutant-' + mutant, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type03_d8_set_retype_matches_original_outer_future_and_fresh():
    state = family_fixture(0x1AED86, active_d8=1, sound=1)
    overrides = {'a2': 0xFF7E40}
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY, candidate=None,
                                     register_overrides=overrides,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150, include_raw=True)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY, candidate='lifecycle',
                                   register_overrides=overrides,
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   future_instructions=150, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('values', [
    {'sound': 1, 'gate_f2': 0x28},   # the recorded arm: sound on, contact root exits early
    {'sound': 0, 'gate_f2': 0x28},
    {'sound': 0, 'blocked': 1},
])
def test_type03_d8_zero_plain_contact_route_matches_original(values):
    """FFF0D8 clear and the contact root on a RAM-only route: no seam is needed."""
    state = family_fixture(0x1AED86, active_d8=0, **values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 0
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type03_d8_set_retype_mutants_diverge_at_outer_boundary(mutant):
    state = family_fixture(0x1AED86, active_d8=1, sound=1)
    overrides = {'a2': 0xFF7E40}
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY, candidate=None,
                                     register_overrides=overrides,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150, include_raw=True)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle-mutant-' + mutant,
                                   register_overrides=overrides,
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   future_instructions=150, include_raw=True,
                                   stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type03_d8_zero_contact_sound_matches_original_outer_future_and_fresh():
    state = family_fixture(0x1AED86, active_d8=0, sound=1)
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150, include_raw=True)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle',
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   future_instructions=150, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['contact_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


def test_type46_command66_counted_replacement_matches_original_outer_future_and_fresh():
    state = type46_fixture()
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150, include_raw=True)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle',
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   future_instructions=150, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type03_d8_zero_contact_sound_mutants_diverge_at_outer_boundary(mutant, monkeypatch):
    state = family_fixture(0x1AED86, active_d8=0, sound=1)
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150)
    if mutant == 'continuation':
        # The prefix deliberately enters the native sound request.  Moving
        # that PC would execute unrelated ROM, so perturb the resumed suffix
        # instead; this is the observable continuation contract under test.
        original_mutate = oracle.Candidate._mutate

        def suffix_only(candidate, plan):
            if candidate.name.endswith('continuation') and plan.registers.get('pc') == 0x1E58B8:
                return plan
            return original_mutate(candidate, plan)

        monkeypatch.setattr(oracle.Candidate, '_mutate', suffix_only)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle-mutant-' + mutant,
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type15_sibling_wrapper_matches_original_outer_future_and_fresh():
    state = family_fixture(0x1AE978, active_d8=1, sound=0,
                           player_x=99, object_x=100, record_counter=2)
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150, include_raw=True)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle',
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   future_instructions=150, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type15_sibling_wrapper_mutants_diverge_at_outer_boundary(mutant):
    state = family_fixture(0x1AE978, active_d8=1, sound=0,
                           player_x=99, object_x=100, record_counter=2)
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle-mutant-' + mutant,
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


@pytest.mark.parametrize('finish_gate,current,limit', [
    (0, 1, 9), (2, 7, 9), (0, 8, 9), (3, 0, 0),
])
def test_type44_counter_clamp_and_counted_replace_match_original(
        finish_gate, current, limit):
    values = {'sound': 0, 'finish_gate': finish_gate,
              'decimal_current': current, 'decimal_limit': limit}
    state = type44_fixture(**values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('finish_gate,current,limit', [
    (0, 1, 9), (2, 7, 9), (0, 8, 9), (3, 0, 0),
])
def test_type44_sound_arm_seams_into_the_shared_body(finish_gate, current, limit):
    state = type44_fixture(sound=1, finish_gate=finish_gate, decimal_current=current,
                           decimal_limit=limit)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type44_sound_arm_mutants_diverge_at_outer_boundary(mutant, monkeypatch):
    state = type44_fixture(sound=1, finish_gate=0, decimal_current=1, decimal_limit=9)
    expected = qualify(state, None)
    if mutant == 'continuation':
        original_mutate = oracle.Candidate._mutate

        def suffix_only(candidate, plan):
            if candidate.name.endswith('continuation') and plan.registers.get('pc') == 0x1E58B8:
                return plan
            return original_mutate(candidate, plan)

        monkeypatch.setattr(oracle.Candidate, '_mutate', suffix_only)
    actual = qualify(state, 'lifecycle-mutant-' + mutant, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type44_counter_replace_mutants_diverge_at_outer_boundary(mutant):
    state = type44_fixture(sound=0, finish_gate=0, decimal_current=1,
                           decimal_limit=9)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle-mutant-' + mutant, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer




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


@pytest.mark.parametrize('motion_x', (0x0140, 0x0007, 0xFFF3))
def test_type43_collection_dispatch_sound_matches_original_outer_future_and_fresh(motion_x):
    state = type43_fixture(motion_x=motion_x)
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150, include_raw=True)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle',
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   future_instructions=150, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('values', [{'sound': 0}])
def test_type43_unsupported_arms_decline_to_original(values):
    state = type43_fixture(**values)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] >= 1


def test_type43_inactive_matches_original_outer_future_and_fresh():
    """FFF0C1 clear is a direct RTS: TST.B FFF0C1/BEQ, no writes at all."""
    state = type43_fixture(fff0c1=0)
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150, include_raw=True)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle',
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   future_instructions=150, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type43_inactive_mutants_diverge_at_outer_boundary(mutant):
    state = type43_fixture(fff0c1=0)
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle-mutant-' + mutant,
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_type43_collection_dispatch_sound_mutants_diverge_at_outer_boundary(mutant, monkeypatch):
    state = type43_fixture()
    expected = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                     candidate=None,
                                     expected_return=CONTACT_COMPLETION_EXIT,
                                     future_instructions=150)
    if mutant == 'continuation':
        # As with the type03/type79 seams, a PC+2 mutation of the prefix
        # would divert into the native sound routine and fault instead of
        # diverging observably; perturb only the resumed suffix plan.
        original_mutate = oracle.Candidate._mutate

        def suffix_only(candidate, plan):
            if candidate.name.endswith('continuation') and plan.registers.get('pc') == 0x1E58B8:
                return plan
            return original_mutate(candidate, plan)

        monkeypatch.setattr(oracle.Candidate, '_mutate', suffix_only)
    actual = oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                   candidate='lifecycle-mutant-' + mutant,
                                   expected_return=CONTACT_COMPLETION_EXIT,
                                   stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type43_semantics_publish_span_and_template_from_a_reader():
    from aladdin_sega.game.objects import contact as game
    record = 0xFF6000
    values = {0xFFF0C1: 0xFF, 0xFFF57D: 1, 0xFF7DFA: 0x1234, 0xFF7DF6: 0x0143, 0xFF7DF8: 0x0125,
              0xFF7DFC: 0x0010, record + 2: 0x0200}
    read = lambda address, size: values.get(address, 0)
    writes, facts = game.contact_type43_update(read, record)
    assert facts['old_secondary'] == 0x1234 and facts['new_secondary'] == 0x00BD
    assert facts['vertical_span'] == 0x0120 and facts['command'] == 0x63
    assert dict(writes)[record] == 0x8A and dict(writes)[0xFFF154] == 0xFF
    assert (dict(writes)[0xFF7E0A], dict(writes)[0xFF7E0B]) == (0x00, 0xC0)
    assert (dict(writes)[0xFF7E0C], dict(writes)[0xFF7E0D]) == (0x00, 0x15)
    assert (dict(writes)[0xFF7E0E], dict(writes)[0xFF7E0F]) == (0x01, 0x40)
    values[0xFFF0C1] = 0
    assert game.contact_type43_update(read, record) == ([], {'active': 0, 'sound': 1, 'command': 0x63})
    assert game.contact_type46_request(lambda a, s: {0xFF7E3C: 0x39, 0xFFF57D: 1}.get(a, 0)) == (
        [(0xFF7E3C, 0x39)], {'old': 0x39, 'value': 0x39, 'capped': True, 'sound': 1, 'command': 0x66})
