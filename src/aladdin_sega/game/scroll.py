"""Per-level scrolling: the horizontal scroll bands and the vertical scroll the camera produces.

Every gameplay frame the main loop jumps through FF7DA4 to the current
level's scroll routine (level table entry +0x34).  All of them turn the
camera position (FF7DF6 / FF7DF8) into the VDP's horizontal scroll table
(VRAM F000: plane A at +0, plane B at +2, one entry per 8-line band with
auto-increment 0x20) and the two VSRAM words.  What differs per level is
the parallax: which bands of plane B scroll at which fraction of the
camera, a drifting phase for skies and water (FFF09E), a scripted vertical
offset stream (FF7E1A) and the rumble of the collapsing cave.

The routine table below maps each original routine address to its
recovered function; the level table decides which one a level uses.
"""
from __future__ import annotations

CAMERA_X, CAMERA_Y = 0xFF7DF6, 0xFF7DF8
SCROLL_ROUTINE = 0xFF7DA4        # long: the level's routine (level table +0x34)
PARALLAX_PHASE = 0xFFF09E        # word: drifts one unit per frame; the far bands add it
SKY_SCROLL = 0xFFF0A2            # word: the carpet escape's own sky position
VERTICAL_STREAM = 0xFF7E1A       # long: ROM stream of vertical offsets, one word per frame, 0 ends it
VERTICAL_OFFSET = 0xFFF080       # word: the stream's last value (the sprite builder shifts sprites by it)
SHAKE_OFFSET = 0xFFF082          # word: the rumble's horizontal shake (likewise applied to sprites)
FRAME_COUNTER = 0xFF7E28
SOUND_ENABLED = 0xFFF57D
RUMBLE_SOUND = 0x53

HSCROLL_A, HSCROLL_B = 0x70000003, 0x70020003   # VRAM F000 / F002
VSCROLL_A, VSCROLL_B = 0x40000010, 0x40020010   # VSRAM 0 / 2
STEP_32, STEP_2 = 0x8F20, 0x8F02                # auto-increment: one band per write / one word
BANDS = 28                                        # 224 lines in 8-line bands


def _w(v):
    return v & 0xFFFF


def _neg(v):
    return (-v) & 0xFFFF


def _bands(vdp, *runs):
    for value, count in runs:
        for _ in range(count):
            vdp.data(value & 0x1FF)


def _plane_a(vdp, read, count=BANDS):
    vdp.control_long(HSCROLL_A)
    _bands(vdp, (_neg(_w(read(CAMERA_X, 2) + 16)), count))


def _vertical(vdp, read, write, rom, *, stream=False):
    vdp.control_long(VSCROLL_B)
    vdp.data(0)
    y = _w(read(CAMERA_Y, 2))
    if stream:
        y = _stream(read, write, rom, y)
    vdp.control_long(VSCROLL_A)
    vdp.data(_w(y + 16) & 0xFF)


def _stream(read, write, rom, y):
    """Add the next word of the level's vertical offset stream (1AB148); a zero word stops it."""
    pointer = read(VERTICAL_STREAM, 4)
    value = int.from_bytes(rom[pointer:pointer + 2], 'big')
    if value:
        write(VERTICAL_OFFSET, value, 2)
        write(VERTICAL_STREAM, pointer + 2, 4)
        return _w(y + value)
    return y


def sky_bands_drifting_left(read, write, rom, vdp, services):
    """1AAA88 (levels 0-2): far sky and skyline bands drift with a decreasing phase."""
    vdp.control(STEP_32)
    x = _neg(read(CAMERA_X, 2))
    vdp.control_long(HSCROLL_B)
    phase = _w(read(PARALLAX_PHASE, 2) - 1)
    write(PARALLAX_PHASE, phase, 2)
    xp = _w(x + phase)
    _bands(vdp, (_w((xp >> 1) + phase) >> 1, 2), (xp >> 2, 1), (0, 1), (xp >> 2, 1), (xp >> 3, 2), (0, 5),
           (x >> 3, 2), (x >> 2, 1), (_w((x >> 1) + x) >> 2, 2), (x >> 1, 3), (x, 8))
    _plane_a(vdp, read, 32)
    _vertical(vdp, read, write, rom)
    vdp.control(STEP_2)


def sky_bands_drifting_right(read, write, rom, vdp, services):
    """1AAC14 (level 3): the same idea with an increasing phase and a slower middle distance."""
    vdp.control(STEP_32)
    x = _neg(read(CAMERA_X, 2))
    vdp.control_long(HSCROLL_B)
    phase = _w(read(PARALLAX_PHASE, 2) + 1)
    write(PARALLAX_PHASE, phase, 2)
    x2 = _w(x + phase + phase)
    _bands(vdp, (0, 4), (_w((x2 >> 1) + x2) >> 1, 2), (_w((x2 >> 1) + x2) >> 2, 2), (x2 >> 2, 1),
           (_w(x + phase) >> 2, 1), (_w((x >> 1) + x) >> 2, 7), (x >> 1, 11))
    _plane_a(vdp, read, 32)
    _vertical(vdp, read, write, rom)
    vdp.control(STEP_2)


def sky_bands_drifting_deep(read, write, rom, vdp, services):
    """1AAD96 (level 10): a drifting horizon over a wide three-quarter band."""
    vdp.control(STEP_32)
    x = _neg(read(CAMERA_X, 2))
    vdp.control_long(HSCROLL_B)
    phase = _w(read(PARALLAX_PHASE, 2) + 1)
    write(PARALLAX_PHASE, phase, 2)
    x2 = _w(x + phase + phase)
    _bands(vdp, (0, 3), (x2 >> 2, 2), (_w((x2 >> 1) + x2) >> 2, 2), (_w((x >> 1) + x) >> 2, 15), (x >> 1, 6))
    _plane_a(vdp, read, 32)
    _vertical(vdp, read, write, rom)
    vdp.control(STEP_2)


def carpet_sky(read, write, rom, vdp, services):
    """1AAEFC (level 8, the carpet escape): plane A itself is half-speed sky, plane B carries its own sky scroll."""
    vdp.control(STEP_32)
    cam = read(CAMERA_X, 2)
    vdp.control_long(HSCROLL_A)
    near = _neg(_w(cam + 16))
    _bands(vdp, (_neg(_w((cam >> 1) + 16)), 21), (near, 7))
    vdp.control_long(HSCROLL_B)
    _bands(vdp, (near, 3), (read(SKY_SCROLL, 2), 17),
           (_neg(_w((_w((cam >> 1) + cam) >> 1) + 16)), 4), (_neg(_w(cam << 1)), 4))
    vdp.control_long(VSCROLL_A)
    for _ in range(BANDS):
        vdp.data_long(0)
    vdp.control(STEP_2)


def half_speed_background(read, write, rom, vdp, services):
    """1AAFE8 (levels 11-12): whole-plane scroll, plane B at half speed, its vertical at 1/32."""
    cam_x, cam_y = read(CAMERA_X, 2), read(CAMERA_Y, 2)
    vdp.control_long(HSCROLL_B)
    vdp.data(_neg(_w(cam_x + 16) >> 1) & 0x1FF)
    vdp.control_long(HSCROLL_A)
    vdp.data(_neg(_w(cam_x + 16)) & 0x1FF)
    vdp.control_long(VSCROLL_B)
    vdp.data((cam_y >> 5) & 0xFF)
    vdp.control_long(VSCROLL_A)
    vdp.data(_w(cam_y + 16) & 0xFF)


def rumble(read, write, rom, vdp, services):
    """1AB066 (level 7, the collapsing cave): both planes shake for 32 of every 256 frames, with a rumble sound."""
    vdp.control(STEP_32)
    cam_x = read(CAMERA_X, 2)
    counter = read(FRAME_COUNTER, 1)
    x = cam_x
    if counter < 0x20:
        x = _w(x + ((~counter) & 3))
    far = _neg(_w(x + 16) >> 1)
    vdp.control_long(HSCROLL_B)
    _bands(vdp, ((far >> 1), 21), (far, 7))
    x = cam_x
    write(SHAKE_OFFSET, 0, 2)
    if counter < 0x20:
        if counter == 0 and read(SOUND_ENABLED, 1):
            services.sound(0, RUMBLE_SOUND, flush=True)
        shake = counter & 3
        write(SHAKE_OFFSET, shake, 2)
        x = _w(x + shake)
    vdp.control_long(HSCROLL_A)
    _bands(vdp, (_neg(_w(x + 16)), BANDS))
    _vertical(vdp, read, write, rom, stream=True)
    vdp.control(STEP_2)


def quarter_and_half_background(read, write, rom, vdp, services):
    """1AB184 (level 9): plane B at a quarter of the camera above, half below."""
    vdp.control(STEP_32)
    far = _neg(_w(read(CAMERA_X, 2) + 16) >> 1)
    vdp.control_long(HSCROLL_B)
    _bands(vdp, (far >> 1, 16), (far, 12))
    _plane_a(vdp, read)
    _vertical(vdp, read, write, rom)
    vdp.control(STEP_2)


def half_speed_with_vertical_stream(read, write, rom, vdp, services):
    """1AB22E (levels 5-6): whole-plane scroll at half speed plus the scripted vertical offset stream."""
    cam_x = read(CAMERA_X, 2)
    vdp.control_long(HSCROLL_B)
    vdp.data(_neg(_w(cam_x + 16) >> 1) & 0x1FF)
    vdp.control_long(HSCROLL_A)
    vdp.data(_neg(_w(cam_x + 16)) & 0x1FF)
    vdp.control_long(VSCROLL_B)
    vdp.data(0)
    y = _stream(read, write, rom, _w(read(CAMERA_Y, 2) + 16))
    vdp.control_long(VSCROLL_A)
    vdp.data(y & 0xFF)


def foreground_faster(read, write, rom, vdp, services):
    """1AB2BC (level 4): plane A moves at 1.5x the camera in both axes, plane B with it."""
    cam_x, cam_y = read(CAMERA_X, 2), read(CAMERA_Y, 2)
    vdp.control_long(HSCROLL_A)
    vdp.data(_neg(_w((_w(cam_x + cam_x + cam_x) >> 1) + 16)) & 0x1FF)
    vdp.control_long(HSCROLL_B)
    vdp.data(_neg(_w(cam_x + 16)) & 0x1FF)
    vdp.control_long(VSCROLL_A)
    vdp.data(_w((_w(cam_y + cam_y + cam_y) >> 1) + 0x40) & 0xFF)
    vdp.control_long(VSCROLL_B)
    vdp.data(_w(cam_y + 16) & 0xFF)


ROUTINES = {
    0x1AAA88: sky_bands_drifting_left,
    0x1AAC14: sky_bands_drifting_right,
    0x1AAD96: sky_bands_drifting_deep,
    0x1AAEFC: carpet_sky,
    0x1AAFE8: half_speed_background,
    0x1AB066: rumble,
    0x1AB184: quarter_and_half_background,
    0x1AB22E: half_speed_with_vertical_stream,
    0x1AB2BC: foreground_faster,
}


def run(read, write, rom, vdp, services) -> None:
    """1AAA80: jump through FF7DA4 to the level's routine."""
    routine = read(SCROLL_ROUTINE, 4)
    try:
        ROUTINES[routine](read, write, rom, vdp, services)
    except KeyError:
        raise LookupError(f'scroll routine {routine:06X} is not recovered') from None
