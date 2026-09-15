from aladdin_sega.game.objects.contact import contact_decay, contact_path, contact_reaction, contact_reset
from aladdin_sega.boundary import CONTACT_ENTRY, COLLECTION_DISPATCH_ENTRY, COLLECTION_DISPATCH_RETURN, CONTACT_COMPLETION_EXIT
from genesis_re.machine import Machine
from aladdin_sega.recovery import Candidate
from test_recovery import native_replace_rom, native_write
from pathlib import Path
import pytest


def reader(values):
    return lambda address, size=1: values.get(address, 0)


def test_contact_state_gate_and_decay_are_pure_live_ram_recipes():
    values = {0xFFF0F2: 3}
    assert contact_path(reader(values)) == ('early', 0xFFF0F2)
    assert contact_decay(reader({0xFFEFFA: 2})) == [(0xFFEFFA, 1), (0xFFF0F2, 0x28)]
    assert contact_decay(reader({})) == [(0xFFF0E6, 10)]


def test_contact_reset_and_reaction_compose_their_state_writes():
    reset = dict(contact_reset(reader({0xFF7E21: 2, 0xFFEFFA: 1}), pointer_reset=True))
    assert reset[0xFF7E60] == 0 and reset[0xFF7E63] == 0xCE
    assert reset[0xFFF0B0] == reset[0xFFF0B1] == reset[0xFFF0CC] == 0
    assert reset[0xFFEFFA] == 0 and reset[0xFFF0F2] == 0x28
    reaction = dict(contact_reaction(reader({0xFFF0D8: 0})))
    assert reaction[0xFFF0E7] == 0xff and reaction[0xFFF0E9] == 0x32
    assert reaction[0xFFEFFF] == 1


def contact_machine():
    original = Path('assets/Aladdin (USA).md')
    if not original.exists():
        pytest.skip('Original USA ROM required for contact qualification')
    rom = bytearray(native_replace_rom(CONTACT_ENTRY, 0x2000)); source = original.read_bytes()
    rom[0x1AE4F8:0x1AE61A] = source[0x1AE4F8:0x1AE61A]
    rom[0x1B03F2:0x1B0434] = source[0x1B03F2:0x1B0434]
    # Deterministic synchronous callees retain the original two-JSR stack
    # protocol while making the caller/suffix comparison self-contained.
    rom[0x1E58B8:0x1E58C8] = bytes.fromhex('203c12345678227c00ff43214e754e714e71')
    rom[0x1E589A:0x1E58A2] = bytes.fromhex('2c7c00ff67894e75')
    machine = Machine(bytes(rom)); machine.gates([CONTACT_ENTRY])
    assert machine.run(instructions=64) == 'gate'; return machine


def contact_dispatch_machine():
    original = Path('assets/Aladdin (USA).md')
    if not original.exists():
        pytest.skip('Original USA ROM required for contact qualification')
    rom = bytearray(native_replace_rom(COLLECTION_DISPATCH_ENTRY, 0x2000)); source = original.read_bytes()
    for start, end in ((0x1CBE, 0x20BE), (0x1ABC82, 0x1ABD76),
                       (0x1A8E0C, 0x1A8E40),
                       (0x1AE9D4, 0x1AE9DA), (0x1AE4F8, 0x1AE61A),
                       (0x1B03F2, 0x1B0434)):
        rom[start:end] = source[start:end]
    rom[0x1E58B8:0x1E58C8] = bytes.fromhex('203c12345678227c00ff43214e754e714e71')
    rom[0x1E589A:0x1E58A2] = bytes.fromhex('2c7c00ff67894e75')
    machine = Machine(bytes(rom)); machine.gates([COLLECTION_DISPATCH_ENTRY])
    assert machine.run(instructions=64) == 'gate'
    return machine


@pytest.mark.parametrize('writes', [
    [(0xfff0e7, 1)],
    [(0xfff0f2, 1)],
    [(0xfff0e6, 1)],
    [(0xfff0e9, 1)],
    [(0xfff0be, 1), (0xfff173, 1), (0xfff0d8, 0)],
])
def test_contact_direct_branches_match_original_outer_return(writes):
    with contact_machine() as machine:
        for address, value in writes:
            native_write(machine, address, bytes((value,)))
        initial = machine.snapshot(); machine.gates([0]); machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        machine.gates([])
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([CONTACT_ENTRY]); assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats['contact_hits'] == 1


@pytest.mark.parametrize('writes', [
    [(0xFFF0E7, 1)], [(0xFFF0E6, 1)], [(0xFFF0E9, 1)], [(0xFFF0F2, 1)],
    [(0xFFF0BE, 1), (0xFFF173, 1), (0xFFF0D8, 0)],
    [(0xFFF0BE, 1), (0xFFF57D, 0), (0xFFEFFA, 2), (0xFF7E21, 2)],
])
def test_type7b_dispatcher_composes_its_bsr_rts_and_direct_contact(writes):
    with contact_dispatch_machine() as machine:
        native_write(machine, 0xFF1000, b'\x7b')
        for address, value in writes:
            native_write(machine, address, bytes((value,)))
        initial = machine.snapshot(); machine.gates([CONTACT_COMPLETION_EXIT])
        machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats['collection_dispatch_hits'] == candidate.stats['contact_hits'] == 1


def test_type7b_dispatcher_composes_contact_sound31_and_local_return():
    with contact_dispatch_machine() as machine:
        for address, value in ((0xFF1000, 0x7B), (0xFFF0C1, 1), (0xFFF57D, 1),
                               (0xFFF0BE, 1), (0xFFEFFA, 2), (0xFF7E21, 2)):
            native_write(machine, address, bytes((value,)))
        initial = machine.snapshot(); machine.gates([CONTACT_COMPLETION_EXIT])
        machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats['gates'] == 2
        assert candidate.stats['collection_dispatch_hits'] == candidate.stats['contact_hits'] == 1
        assert candidate.stats['legacy_returns'] == 1


_RESET_ROUTES = {
    'be': [(0xfff0be, 1)], 'd0': [(0xfff0d0, 1)],
    'd7': [(0xfff0d7, 1)], 'cd': [(0xfff0cd, 1)],
    'd4': [(0xfff0d4, 1)], 'c1zero': [(0xfff0c1, 0)],
    'cc': [(0xfff0cc, 1)], 'efff': [(0xffefff, 1)],
    'f11f': [(0xfff11f, 1)], 'pointer': [],
}


@pytest.mark.parametrize('route', _RESET_ROUTES)
@pytest.mark.parametrize('counter,count', [(0, 0), (1, 0), (2, 1), (1, 2), (255, 255)])
def test_contact_soundoff_reset_routes_and_repeated_decay_match_original(route, counter, count):
    with contact_machine() as machine:
        for address, value in ((0xfff0c1, 1), (0xfff57d, 0), (0xffeffa, counter),
                               (0xff7e21, count)):
            native_write(machine, address, bytes((value,)))
        for address, value in _RESET_ROUTES[route]:
            native_write(machine, address, bytes((value,)))
        initial = machine.snapshot(); machine.gates([0]); machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        machine.gates([])
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([CONTACT_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats['contact_hits'] == 1


@pytest.mark.parametrize('counter,count,blocker', [(0, 0, 1), (1, 0, 1),
                                                    (2, 1, 1), (255, 255, 0x80)])
def test_contact_soundoff_blocked_decay_repeats_match_original(counter, count, blocker):
    with contact_machine() as machine:
        for address, value in ((0xfff0c1, 0), (0xfff57d, 0), (0xffeffa, counter),
                               (0xff7e21, count), (0xff7e20, blocker)):
            native_write(machine, address, bytes((value,)))
        initial = machine.snapshot(); machine.gates([0]); machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        machine.gates([])
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([CONTACT_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats['contact_hits'] == 1


@pytest.mark.parametrize('route,writes', [
    ('be', [(0xfff0be, 1)]), ('d0', [(0xfff0d0, 1)]),
    ('d7', [(0xfff0d7, 1)]), ('cd', [(0xfff0cd, 1)]),
    ('d4', [(0xfff0d4, 1)]), ('c1zero', [(0xfff0c1, 0)]),
    ('direct', []),
])
@pytest.mark.parametrize('d8', [0, 1])
def test_contact_reaction_routes_and_final_flag_match_original(route, writes, d8):
    with contact_machine() as machine:
        native_write(machine, 0xfff0c1, b'\x01'); native_write(machine, 0xfff173, b'\x01'); native_write(machine, 0xfff0d8, bytes((d8,)))
        for address, value in writes:
            native_write(machine, address, bytes((value,)))
        initial = machine.snapshot(); machine.gates([0]); machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        machine.gates([])
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([CONTACT_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats['contact_hits'] == 1


@pytest.mark.parametrize('c1', [0, 1])
def test_contact_sound31_reuses_the_guarded_synchronous_seam(c1):
    with contact_machine() as machine:
        for address, value in ((0xFFF0C1, c1), (0xFFF57D, 1), (0xFFF11F, 1),
                               (0xFFEFFA, 1)):
            native_write(machine, address, bytes((value,)))
        native_write(machine, 0xFF8000, (0x300).to_bytes(4, 'big'))
        initial = machine.snapshot()
        machine.gates([0x300]); machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        machine.gates([])
        expected = machine.snapshot(), machine.audio()
        expected_info, expected_registers = machine.info, machine.registers()
        expected_ram = machine.peek_ram(0, 65536)
        machine.run(instructions=150)
        future = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([CONTACT_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([])
        assert machine.info == expected_info
        assert machine.registers() == expected_registers
        assert machine.peek_ram(0, 65536) == expected_ram
        assert machine.audio() == expected[1]
        assert candidate.stats['contact_hits'] == candidate.stats['legacy_returns'] == 1
        machine.run(instructions=150)
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == future


@pytest.mark.parametrize('route', _RESET_ROUTES)
@pytest.mark.parametrize('counter,count', [(0, 0), (1, 0), (2, 1), (1, 2), (255, 255)])
def test_contact_sound31_routes_and_repeated_decay_match_original(route, counter, count):
    with contact_machine() as machine:
        for address, value in ((0xfff0c1, 1), (0xfff57d, 1), (0xffeffa, counter),
                               (0xff7e21, count)):
            native_write(machine, address, bytes((value,)))
        for address, value in _RESET_ROUTES[route]:
            native_write(machine, address, bytes((value,)))
        native_write(machine, 0xFF8000, (0x300).to_bytes(4, 'big'))
        initial = machine.snapshot()
        machine.gates([0x300]); machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        machine.gates([])
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([CONTACT_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats['contact_hits'] == candidate.stats['legacy_returns'] == 1


@pytest.mark.parametrize('counter,count,blocker', [(0, 0, 1), (1, 0, 1),
                                                    (2, 1, 1), (255, 255, 0x80)])
def test_contact_sound31_blocked_decay_repeats_match_original(counter, count, blocker):
    with contact_machine() as machine:
        for address, value in ((0xfff0c1, 0), (0xfff57d, 1), (0xffeffa, counter),
                               (0xff7e21, count), (0xff7e20, blocker)):
            native_write(machine, address, bytes((value,)))
        native_write(machine, 0xFF8000, (0x300).to_bytes(4, 'big'))
        initial = machine.snapshot(); machine.gates([0x300]); machine.gate(CONTACT_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        machine.gates([])
        expected = machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([CONTACT_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([])
        assert (machine.info, machine.registers(), machine.peek_ram(0, 65536), machine.audio()) == expected
        assert candidate.stats['contact_hits'] == candidate.stats['legacy_returns'] == 1
