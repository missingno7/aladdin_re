"""The object script engine: decoded data and the oracle contract at its own boundaries.

The differential tests replay nothing: they use the original-machine
snapshots under ``artifacts/evidence/frames`` (regenerable with
``scripts/cartography/frame_states.py``) and skip when absent.
"""
import glob, os
from pathlib import Path
import pytest
from aladdin_sega.profile import read_rom
from aladdin_sega.game import assets, scripts
from aladdin_sega.game.objects import record
from aladdin_sega.game.objects.script_engine import Engine, Memory, Services, Trace

ROOT = Path(__file__).resolve().parents[3]
FRAMES = sorted(glob.glob(str(ROOT / 'artifacts' / 'evidence' / 'frames' / 'f*.state')),
                key=lambda p: int(os.path.basename(p)[1:-6]))
rom = read_rom()


def test_opcode_table_names_every_handler():
    assert len(scripts.OPCODES) == 21
    assert [o[0] for o in scripts.OPCODES][:3] == ['jump', 'flip', 'end']
    assert scripts.OPCODES[0x14][0] == 'near_y'


def test_templates_decode_from_their_spawn_sites():
    ts = assets.templates(rom)
    assert len(ts) == 85
    guard = next(t for t in ts if t.address == 0x1B7B84)
    assert (guard.kind, guard.hit_points, guard.script, guard.vram_slots) == (0x10, 9, 0x1239CA, 0x0C)


def test_large_guard_script_decodes_to_frames_and_named_opcodes():
    sc = scripts.decode_animation(rom, 0x1239CA)
    names = [op.name for op in sc.ops()]
    assert names[:3] == ['face_player', 'wait', 'branch_compare']
    assert names[-1] == 'loop'
    attack = sc.blocks[0x123A26]
    assert [op.name for op in attack.ops()] == ['face_player', 'spawn', 'jump']
    spawn = attack.ops()[1]
    assert spawn.operands[:4] == (0, 0x1B7CB0, 56, -30) and spawn.size == 16
    assert attack.ops()[2].target == 0x1239CA and attack.ops()[2].size == 6


def test_frame_descriptor_and_pieces_decode():
    frame = assets.SpriteFrame.from_word(rom, 0x1912)
    assert len(frame.pieces) == 7
    first = frame.pieces[0]
    assert (first.dx, first.dy, first.tile_record.size_tiles, first.tile_record.tiles) == (-13, -25, (4, 4), 16)
    image, origin = assets.render_frame(rom, frame)
    assert image.size == (72, 56) and origin == (-29, -33)


def test_record_view_names_the_fields():
    buffer = bytearray(66 * 32)
    read, write = record.bytes_view(buffer)
    obj = record.RecordView(record.RECORD_TABLE + 66, read, write)
    obj.kind = 0x10; obj.x = 0x1234; obj.vel_x = -0x28; obj.script = 0x1239CA
    assert buffer[66] == 0x10 and buffer[66 + 2:66 + 4] == b'\x12\x34'
    assert obj.vel_x == -0x28 and obj.slot == 1 and obj.script == 0x1239CA


def _machine_at(path):
    from genesis_re.machine import Machine
    m = Machine(rom); m.restore(Path(path).read_bytes()); return m


def _boundary(m, entry, exits):
    m.gates([entry, *exits])
    for _ in range(4):
        assert m.run(target=m.info['tick'] + 10 * 896040) == 'gate'
        if m.info['pc'] == entry:
            break
        m.gate(m.info['pc'], bypass_once=True)
    else:
        pytest.skip('boundary not reached')
    before = bytearray(m.peek_ram(0, 65536))
    m.gate(entry, bypass_once=True)
    assert m.run(target=m.info['tick'] + 10 * 896040) == 'gate' and m.info['pc'] in exits
    return before, bytearray(m.peek_ram(0, 65536))


BOOKKEEPING = ((0xFF769A, 0xFF7800), (0xFFEF80, 0xFFEFE0), (0xFF7D9A, 0xFF7DA3), (0xFFEFEE, 0xFFEFF0))


def _engine_over(before, which):
    ram = bytearray(before)
    def read(a, n): return int.from_bytes(ram[a & 0xFFFF:(a & 0xFFFF) + n], 'big')
    def write(a, v, n): ram[a & 0xFFFF:(a & 0xFFFF) + n] = v.to_bytes(n, 'big')
    trace = Trace()
    engine = Engine(Memory(read, write, rom), Services(trace))
    (engine.animation_pass if which == 'anim' else engine.motion_pass)()
    return ram, trace


def _mismatches(before, after, mine, trace):
    handoff_slots = {h.slot for h in trace.handoffs if h.kind != 'frame_upload'}
    bad = []
    for a in range(65536):
        if after[a] == mine[a] or any(lo <= 0xFF0000 | a < hi for lo, hi in BOOKKEEPING):
            continue
        address = 0xFF0000 | a
        if record.RECORD_TABLE <= address < record.RECORD_TABLE + 32 * 66:
            if (address - record.RECORD_TABLE) // 66 in handoff_slots:
                continue
        bad.append((f'{address:06X}', before[a], after[a], mine[a]))
    return bad


@pytest.mark.skipif(not FRAMES, reason='no recorded frame states under artifacts/evidence/frames')
@pytest.mark.parametrize('path', FRAMES, ids=[os.path.basename(p)[:-6] for p in FRAMES])
@pytest.mark.parametrize('which', ['anim', 'motion'])
def test_engine_pass_matches_the_original_at_its_boundary(path, which):
    """Every record field the engine owns ends the pass exactly as the original leaves it."""
    entry, exits = ((0x1AC784, (0x1AC84E, 0x1B0334)) if which == 'anim' else (0x1ADE36, (0x1AE0AE,)))
    m = _machine_at(path)
    try:
        for _ in range(3):
            before, after = _boundary(m, entry, exits)
            mine, trace = _engine_over(before, which)
            assert _mismatches(before, after, mine, trace) == []
    finally:
        m.close()
