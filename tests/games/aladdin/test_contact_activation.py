"""Literal-ROM qualification of the motion-gated contact activation parent."""
import pytest
import oracle_witness as oracle
from aladdin_sega.boundary import (COLLECTION_DISPATCH_ENTRY,
                                   COLLECTION_DISPATCH_RETURN,
                                   CONTACT_COMPLETION_EXIT)

RECORD = 0xFF6000


def activation_fixture(*, vertical=0, blocked=0, previous=100, object_y=100,
                       origin_y=0, player_x=120, object_x=100, incoming_x=False,
                       record=RECORD):
    rom = oracle.read_rom()
    kinds = [kind for kind in range(256)
             if int.from_bytes(rom[0x1CBE + kind * 4:0x1CC2 + kind * 4], 'big') == 0x1AFD84]
    assert kinds
    machine = oracle.cold_fixture(0x1B5266, pc_entry=COLLECTION_DISPATCH_ENTRY,
                                  incoming_x=incoming_x)
    try:
        machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        registers.update(a1=record, d0=0xABCD1234, d2=0x98764321, d7=0x76543210)
        writes = [(record + i, 0xA5) for i in range(66)]
        writes += [(record, kinds[0]), (0xFFF0E7, blocked), (0xFFF0F5, 0x35)]
        for address, value in ((record + 2, object_x), (record + 4, object_y),
                               (0xFF7E5A, vertical), (0xFF7DFC, previous),
                               (0xFF7DF8, origin_y), (0xFF7E02, player_x)):
            writes.extend(oracle.write_word(address, value))
        assert machine.atomic(target=machine.info['tick'] + 1_000_000,
                              cycles=1, instructions=1, last_pc=COLLECTION_DISPATCH_ENTRY,
                              writes=writes, registers=registers)
        return machine.snapshot()
    finally:
        machine.close()


def qualify(state, candidate):
    return oracle.execute_region(state, entry=COLLECTION_DISPATCH_ENTRY,
                                 candidate=candidate,
                                 expected_return=CONTACT_COMPLETION_EXIT,
                                 include_raw=True)


@pytest.mark.parametrize('values', [
    {'vertical': 0x8000}, {'vertical': 0xFFFF, 'blocked': 1}, {'blocked': 0x80},
    {'previous': 106}, {'previous': 94}, {'previous': 105}, {'previous': 95},
    {'player_x': 80}, {'player_x': 100}, {'player_x': 107}, {'player_x': 108},
    {'player_x': 0x8100, 'object_x': 0x0100},
    {'previous': 0, 'object_y': 0xFFFF},
    {'previous': 0xFFFF, 'object_y': 0},
    {'object_y': 2, 'origin_y': 0xFFFE, 'previous': 4},
])
@pytest.mark.parametrize('incoming_x', [False, True])
def test_activation_dispatch_matches_original_outer_and_native_future(values, incoming_x):
    state = activation_fixture(**values, incoming_x=incoming_x)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


def test_activation_outer_restores_in_fresh_process():
    actual = qualify(activation_fixture(player_x=80), 'lifecycle')
    assert actual.stats['collection_dispatch_hits'] == 1
    assert oracle.fresh_process_future(actual.outer_state) == actual.future


@pytest.mark.parametrize('player_x,impulse', [(80, 0xFE), (100, 0), (107, 0), (108, 1), (120, 2)])
def test_activation_publishes_motion_and_object_transition(player_x, impulse):
    actual = qualify(activation_fixture(player_x=player_x), 'lifecycle')
    machine = oracle.Machine(oracle.read_rom())
    try:
        machine.restore(actual.outer_state)
        assert machine.peek_ram(0x7E58, 1) == bytes([impulse])
        assert machine.peek_ram(0x7E5A, 2) == bytes.fromhex('f800')
        assert machine.peek_ram(0x7DFE, 2) == bytes.fromhex('00b0')
        assert machine.peek_ram(0x7E60, 4) == bytes.fromhex('00121c62')
        assert machine.peek_ram(RECORD & 65535, 1) == b'\x84'
        assert machine.peek_ram((RECORD + 32) & 65535, 4) == bytes.fromhex('00122db2')
        assert machine.peek_ram((RECORD + 55) & 65535, 1) == b'\0'
    finally:
        machine.close()


@pytest.mark.parametrize('record', [0xFF7DF6, 0xFF7E58])
def test_activation_record_global_alias_is_exact_or_locally_refused(record):
    state = activation_fixture(record=record)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] + actual.stats['fallbacks'] >= 1


@pytest.mark.parametrize('mutant', ['result', 'continuation', 'timing'])
def test_activation_mutants_diverge_at_outer_boundary(mutant):
    state = activation_fixture(player_x=80)
    expected = qualify(state, None)
    actual = oracle.execute_region(
        state, entry=COLLECTION_DISPATCH_ENTRY,
        candidate='lifecycle-mutant-' + mutant,
        expected_return=COLLECTION_DISPATCH_RETURN, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_activation_deadline_refusal_leaves_only_original_first_instruction():
    state = activation_fixture()
    observations = []
    for recovered in (False, True):
        machine = oracle.Machine(oracle.read_rom())
        try:
            machine.restore(state)
            machine.gates([COLLECTION_DISPATCH_ENTRY])
            assert machine.run(instructions=1) == 'gate'
            if recovered:
                candidate = oracle.Candidate('lifecycle')
                candidate.arm(machine)
                assert machine.run(instructions=1) == 'gate'
                assert not candidate.on_gate(machine, machine.info['tick'] + 1)
                assert candidate.stats['fallback_reasons'] == {'scheduler admission': 1}
            else:
                machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
                assert machine.run(instructions=1) == 'limit'
            observations.append(oracle.observable(machine))
        finally:
            machine.close()
    assert observations[0] == observations[1]
