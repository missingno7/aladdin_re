"""Original-byte qualification of the connected collection/retirement family."""
from pathlib import Path
import hashlib
import pytest

from aladdin_sega.machine import Machine
from test_recovery import native_replace_rom, native_write
from aladdin_sega.recovery import Candidate
from aladdin_sega.boundary import begin_collection, finish_collection, relocate_collection, ROM_SHA256, UnsupportedCandidate

ROUTES = {0x1AF008: 0x1AF02A, 0x1AF034: 0x1AF056, 0x1AF060: 0x1AF082, 0x1AF08C: 0x1AF0AE,
          0x1AF468: 0x1AF498, 0x1AF21E: 0x1AF258, 0x1AF264: 0x1AF2A6,
          0x1AF2B0: 0x1AF2F2, 0x1AF2FA: 0x1AF33C,
          0x1AF344: 0x1AF378, 0x1AF384: 0x1AF3B0,
          0x1AF3C2: 0x1AF3E4, 0x1AF400: 0x1AF422, 0x1AF4A0: 0x1AF4BC,
          0x1AF4D8: 0x1AF4FA, 0x1AF53E: 0x1AF4BC}


def prepared(entry, *, sound=1, digits=0x3039, count=3, linked=False,
             length=1, sr=0x201f, total=0xfff0, slots=0, primary=0, record=0xff1000):
    rom = bytearray(native_replace_rom(entry, sr))
    rom[0x200:0x240] = rom[0x200:0x240].replace(bytes.fromhex('2e7c00ff8000'), bytes.fromhex('2e7c00ff9000'))
    rom[0x200:0x240] = rom[0x200:0x240].replace(bytes.fromhex('227c00ff1000'), bytes.fromhex('227c') + record.to_bytes(4, 'big'))
    path = Path('assets/Aladdin (USA).md')
    if not path.exists(): pytest.skip('Original USA ROM required for collection qualification')
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == ROM_SHA256
    for start, end in [(0x1CBE, 0x20BE), (0x1ABC82, 0x1ABD7E), (0x1AF008, 0x1AF54A),
                       (0x1AE27A, 0x1AE30A),
                       (0x1B0156, 0x1B0192), (0x1B0336, 0x1B03BE),
                       (0x1B7ABC, 0x1B7CF0), (0x1A91C4, 0x1A91C6), (0x1AE6DE, 0x1AE700)]:
        rom[start:end] = original[start:end]
    # Clobbering sound fixture; actual original sound is tested with recordings.
    rom[0x1E58B8:0x1E58C8] = bytes.fromhex('203c12345678227c00ff43214e754e714e71')
    rom[0x1E589A:0x1E58A2] = bytes.fromhex('2c7c00ff67894e75')
    m = Machine(bytes(rom))
    def put(at, value, width=1): native_write(m, at, value.to_bytes(width, 'big'))
    for at, ptr in [(record, 0xff2000), (0xff5000, 0xff6000)]:
        native_write(m, at, b'\xa5'*66)
        put(at+41, max(0, length-1)); put(at+42, ptr if length else 0, 4)
        native_write(m, ptr, b'\x5a'*256)
    put(record+62, 0xff5000 if linked else 0, 4)
    put(0xffefe0, digits, 2); put(0xffefe2, digits, 2)
    put(0xfff10a, count); put(0xfff003, count); put(0xfff57d, sound)
    put(0xfff14e, total, 2); put(0xff9000, 0x300, 4)
    native_write(m, 0xff8fc0, b'\x5a'*64)
    for index in range(slots): put(0xff84b2+66*index, 1)
    for index in range(primary): put(0xff7e82+66*index, 1)
    m.gates([entry]); assert m.run(instructions=64) == 'gate'; m.audio()
    return m


@pytest.mark.parametrize('entry', list(ROUTES))
@pytest.mark.parametrize('sound,digits,count,linked,length,sr,total', [
    (0, 0x3030, 0, False, 0, 0x2000, 0),
    (1, 0x3039, 3, False, 1, 0x201f, 0xfff0),
    (0, 0x3938, 2, True, 8, 0x201f, 0x7ff0),
    (0x80, 0x3030, 255, True, 4, 0x2000, 0xffff),
])
def test_collection_exact_outer_and_future(entry, sound, digits, count, linked, length, sr, total):
    with prepared(entry, sound=sound, digits=digits, count=count, linked=linked,
                  length=length, sr=sr, total=total) as m:
        initial = m.snapshot()
        m.gates([0x300]); assert m.run(instructions=10000) == 'gate'
        expected = m.snapshot(), m.audio()
        expected_regs, expected_info = m.registers(), m.info
        expected_ram = m.peek_ram(0, 65536)
        m.gates([]); m.run(instructions=150)
        future = m.snapshot(), m.audio()
        m.restore(initial); m.audio(); m.gates([entry]); assert m.run(instructions=1) == 'gate'
        recovery = Candidate('lifecycle')
        assert recovery.on_gate(m, m.info['tick'] + 1_000_000)
        assert m.info == expected_info, (hex(entry), m.info, expected_info, recovery.stats)
        assert m.registers() == expected_regs, (hex(entry), m.registers(), expected_regs)
        assert m.peek_ram(0, 65536) == expected_ram, [hex(0xff0000+i) for i,(a,b) in enumerate(zip(m.peek_ram(0,65536), expected_ram)) if a!=b]
        assert (m.snapshot(), m.audio()) == expected
        m.gates([]); m.run(instructions=150)
        assert (m.snapshot(), m.audio()) == future


@pytest.mark.parametrize('slots', range(7))
@pytest.mark.parametrize('sr', [0x2000, 0x201f])
def test_relocation_exact_outer_and_future(slots, sr):
    with prepared(0x1AF516, slots=slots, sr=sr) as m:
        initial = m.snapshot()
        m.gates([0x300]); assert m.run(instructions=3000) == 'gate'
        expected = m.snapshot(), m.audio()
        regs, info, ram = m.registers(), m.info, m.peek_ram(0, 65536)
        m.gates([]); m.run(instructions=150); future = m.snapshot(), m.audio()
        m.restore(initial); m.audio(); m.gates([0x1AF516]); m.run(instructions=1)
        recovery = Candidate('lifecycle'); assert recovery.on_gate(m, m.info['tick']+1_000_000)
        assert m.info == info, (m.info, info)
        assert m.registers() == regs
        assert m.peek_ram(0,65536) == ram
        assert (m.snapshot(), m.audio()) == expected
        m.gates([]); m.run(instructions=150); assert (m.snapshot(), m.audio()) == future


def check_prepared(m, entry):
    initial = m.snapshot()
    m.gates([0x300]); assert m.run(instructions=10000) == 'gate'
    expected = m.snapshot(), m.audio()
    m.gates([]); m.run(instructions=150); future = m.snapshot(), m.audio()
    m.restore(initial); m.audio(); m.gates([entry]); m.run(instructions=1)
    candidate = Candidate('lifecycle')
    assert candidate.on_gate(m, m.info['tick']+1_000_000), candidate.stats
    assert candidate.stats['fallbacks'] == 0, candidate.stats
    assert (m.snapshot(), m.audio()) == expected
    m.gates([]); m.run(instructions=150); assert (m.snapshot(), m.audio()) == future


@pytest.mark.parametrize('primary', [0, 1, 7, 23, 24])
@pytest.mark.parametrize('record,y', [(0xff1000, 0), (0xff7e82, 0x8000), (0xff8470, 0x7fff)])
def test_spawn_search_exhaustion_and_read_after_activation(primary, record, y):
    with prepared(0x1AF400, primary=primary, record=record) as m:
        native_write(m, record, b'\0')  # activation must occupy this slot before the search
        native_write(m, record+4, y.to_bytes(2, 'big'))
        check_prepared(m, 0x1AF400)


@pytest.mark.parametrize('entry', [0x1AF21E, 0x1AF264])
def test_unaccepted_collection_has_exact_short_return(entry):
    with prepared(entry, digits=0x3939) as m:
        if entry == 0x1AF21E: native_write(m, 0xfff0d8, b'\x80')
        check_prepared(m, entry)


@pytest.mark.parametrize('digits', [0x2930, 0x3040])
def test_unsupported_secondary_domain_refuses_without_effects(digits):
    with prepared(0x1AF21E, digits=digits) as m:
        before = m.snapshot()
        with pytest.raises(UnsupportedCandidate): begin_collection(m, m.registers(), 0x1AF21E)
        assert m.snapshot() == before


@pytest.mark.parametrize('entry', [0x1AF468, 0x1AF21E])
@pytest.mark.parametrize('sound,flag,index', [(0, 0, 0), (0, 0x80, 0), (1, 1, 0x8000), (1, 0xff, 0x7fff)])
def test_capped_collection_state_table_and_preserved_registers(entry, sound, flag, index):
    with prepared(entry, digits=0x3939, sound=sound) as m:
        native_write(m, 0xff1034, bytes([flag]))
        native_write(m, 0xff1032, index.to_bytes(2, 'big'))
        if index == 0x7fff:
            # The signed index would leave canonical work RAM. Unsupported
            # domains remain original, rather than wrapping into another bus.
            with pytest.raises(UnsupportedCandidate): begin_collection(m, m.registers(), entry)
        else:
            check_prepared(m, entry)


def test_collection_buffer_cannot_alias_a_live_input():
    with prepared(0x1AF344) as m:
        native_write(m, 0xff102a, (0xfff57d).to_bytes(4,'big'))
        before = m.snapshot()
        with pytest.raises(UnsupportedCandidate, match='aliases'):
            begin_collection(m, m.registers(), 0x1AF344)
        assert m.snapshot() == before


def test_same_retirement_source_runs_over_bytes_without_a_machine():
    """Semantic portability, separately from the unmasked machine tests above."""
    from aladdin_sega import recovered as game
    with prepared(0x1AF3C2, sound=0, linked=True, length=8) as m:
        ram = bytearray(m.peek_ram(0, 65536))
        template = m.peek_rom(0x1B7CD8, 19)
        m.gates([0x300]); assert m.run(instructions=3000) == 'gate'
        expected = m.peek_ram(0, 65536)
    # There is no live Machine here. These are the SAME production semantic
    # functions; this test introduces no mutable shadow into the runtime.
    read = lambda at, size: int.from_bytes(ram[at & 65535:(at & 65535)+size], 'big')
    for at, value in game.collection_state(read, 0xff1000, 'flag25'):
        ram[at & 65535] = value
    for at, value in game.retire_collected_object(read, 0xff1000, template, 25):
        ram[at & 65535] = value
    for at, size in ((0x1000, 66), (0x5000, 66), (0x2000, 8), (0x6000, 8),
                     (0xf176, 1), (0xf14e, 2)):
        assert ram[at:at+size] == expected[at:at+size]


if __name__ == '__main__':
    for entry, ret in ROUTES.items():
        with prepared(entry) as m:
            start = m.info
            m.gates([0x1e58b8, 0x300]); assert m.run(instructions=2000) == 'gate'
            first = m.info
            print(hex(entry), 'prefix', first['m68k_cycles']-start['m68k_cycles'],
                  first['m68k_instructions']-start['m68k_instructions'], hex(m.registers()['sr']))
            if first['pc'] == 0x1e58b8:
                m.gates([ret]); assert m.run(instructions=2000) == 'gate'
                start = m.info
                m.gates([0x300]); assert m.run(instructions=2000) == 'gate'
                last = m.info
                print(' suffix', last['m68k_cycles']-start['m68k_cycles'],
                      last['m68k_instructions']-start['m68k_instructions'], hex(m.registers()['sr']))
