"""The title screen: its logo intro, palette-cycled backdrop, attract-mode entry and Start/options menu.

ROM 1B3B96..1B4800 (called once, from 1A8B24 / :mod:`boot`.title_entry).  The routine:

* loads the title's own tiles and objects (1B477C, two 128x32 title-piece
  templates via 1AE30A), fades them in over two palette-cycled ``mini
  frame`` loops of 180 frames each (1B3C60..1B3CAA; the palette cycle
  itself is :func:`sequences.cycle_palette`, 1B3B4A), any of B/C/A/Start
  cutting the intro short at any of three points (1B3548, decoded here
  as :func:`sequences.any_button` -- the four port bits it tests are
  exactly the mask ``any_button`` already reads);
* redraws the menu backdrop (1B3DB8..1B3E9E): the two remaining title
  pieces (1B47D0 / 1B47AC), "PRESS START", and the cursor placed by
  :func:`_place_title_cursor` (1B43C4, ROM 1B43C4..1B43DE);
* runs the menu loop (1B3EAA..1B4054): a 1500-frame idle timeout
  (FFF13E) that hands off to the attract demo (the table at ROM 4B04,
  indexed by FFF57A, 6 bytes per entry: a long pad-stream pointer and a
  level byte) when it expires; Up/Down moves the cursor (FFF13C, 0 = new
  game, 1 = options) with the repeat latch FFEFFD, wrapping at the two
  entries; any of B/C/A/Start (the CBAS repeat latch FFEFFE) with the
  cursor at 0 ends the routine (the game starts); with the cursor at 1 it
  enters the options screen (1B4056, :func:`_options_screen`): six rows
  (difficulty, music, sound, the button-remap entry, the control-scheme
  cycle, exit) cycled by Up/Down and confirmed by any of B/C/A, with
  Start exiting from any row.  The button-remap sub-screen it can enter
  (1B4436..) and the hidden button-sequence completion its per-frame pad
  reader can reach (1B0C82) are not recovered (see ``OPTIONS_GAP``).

The routine's own return value models FFF57C: it returns ``('game', None)``
when 1A8B2C should continue as a new game, or ``('attract', level)`` when
the attract demo should run (FFF57C left at 1, the level from the demo
table).  ``boot.title_entry`` composes what follows exactly as the
original does after 1B3B96 returns (both paths converge there).
"""
from __future__ import annotations
from ..game import video, player, pad, messages, sprites
from ..game.objects.record import RECORD_TABLE, RECORD_SIZE
from ..game.objects.script_engine import Engine
from .state import NativeGap
from . import sequences

# ---- ROM data ------------------------------------------------------------------------------------
TITLE_PIECE_2 = 0x1B7D28          # 1B3BFE: slot 2's template, position (0x192, 0x170)
TITLE_PIECE_3 = 0x1B846C          # 1B3C1A: slot 3's template, position (0x1BA, 0x170)
TITLE_PIECE_2B = 0x1B7D64         # 1B3D06: slot 2's template after the intro, position (0x58, 0x164)
LOGO_FADE_IN = 0x1296B2           # 1B3C56
LOGO_PALETTE_A = 0x128F52         # 1B3CB4: the mini-framed fade after the first two 180-frame loops
LOGO_PALETTE_B = 0x129732         # 1B3D46: the mini-framed fade before the objects are spawned
BACKDROP_PALETTE = 0x1297D2       # 1B3D8A: palette line 0 once an object list has run once
TITLE_TEXT_LOGO = 0x128E51        # 1B3C80: printed at column 0xF, row 0x13 during the logo loops
BLANK_ROW = 0x128E5B              # printed at column 0, row 0x19: clears the previous menu text line
PRESS_START_TEXT = 0x126679       # printed at column 0xE, row 0x10
STOP_MUSIC_CODE = 0x1A             # 1B3CD2 / 1B3DBC: sound_if_enabled(..., flag=0xFFF57F)
CURSOR_MOVE_SOUND = 0x04           # 1B327A: sound_if_enabled(..., flag=0xFFF57D)
TITLE_TILES = ((0x12CCD8, 0xC000), (0x12CD74, 0xE000), (0x136912, 0))    # 1B477C
BACKDROP_C = (0x12F4EC, 0xC000)   # 1B47D0 / 1B47F0 (same source, two call sites)
BACKDROP_E = (0x12D0FA, 0xE000)   # 1B47AC
BACKDROP_OBJECT = 0x12CE06        # 1B47BE, into VRAM E000
DEMO_TABLE = 0x4B04                # ROM: 6 bytes/entry (long pad-stream pointer, level byte)
DEMO_TABLE_ENTRIES = 5
SPAWN_LIST_TEMPLATE = 0x1B797C     # 1B4802
SPAWN_LIST_SOURCE = 0xFF7282       # "spawns from a list at FF7282"
SPAWN_LIST_ENABLED = 0xFFF0FF
CURSOR = 0xFFF13C
CURSOR_TIMEOUT = 0xFFF13E
CURSOR_TIMEOUT_FRAMES = 0x5DC      # 1500
DIR_LATCH = 0xFFEFFD                # the Up/Down repeat latch
SELECT_LATCH = 0xFFEFFE             # the B/C/A/Start repeat latch
DIFFICULTY_DEBUG = 0xFF7274         # 1B3FBA: unreachable with a two-item menu (cursor is only ever 0 or 1)


class OPTIONS_GAP:
    """The options screen's button-remap sub-screen (ROM 1B4436..1B4664) and the hidden button-sequence
    completion (1B0C82) are not recovered; the rest of the options screen is (see ``_options_screen``)."""
    REMAP_PC = 0x1B4436
    SECRET_PC = 0x1B0C82


OPTIONS_HEADER_TEXT = 0x1266A0      # 1B407C: printed at (0xA, 0x10)
DIFFICULTY_LABEL = 0x126692         # 1B4372: printed at (0xA, 0xE) before the difficulty name
DIFFICULTY = 0xFF7E21               # 1B4128: the options screen's own difficulty digit (0..2)
DIFFICULTY_TABLE = 0x3FD2           # ROM: 3 long pointers, indexed by DIFFICULTY (0..2)
ONOFF_TEXT_A = 0x126512             # 1B430C: printed when the tested flag is set
ONOFF_TEXT_B = 0x126516             # 1B430C: printed when the tested flag is clear
MUSIC_ENABLED = 0xFFF57F
SOUND_ENABLED = 0xFFF57D
OPTIONS_SELECT_LATCH = 0xFFEFFD     # 1B410C..: one shared edge latch for Start/A/B/C *and* Up/Down here
OPTIONS_DIR_LATCH = 0xFFF0BF        # 1B42A6..: the Up/Down repeat latch (options screen only)
CONTROL_PROFILE_PTR = 0xFF7DDE      # the active control-scheme record: 12 bytes of routine pointers + text
CONTROL_PROFILE_COPY = 0xFF7DD2     # 1B32E2: the 12 bytes copied out for the active scheme
CONTROL_PROFILE_DEFAULT = 0x4012    # ROM: the wraparound entry
CONTROL_PROFILE_NEXT = 0x12         # each profile record is 0x12 bytes; the next one follows directly,
                                     # a leading zero long marking the end of the list (1B4224..1B4254)
PAD_SEQ_PTR, PAD_SEQ_RESET, PAD_SEQ_MATCHED = 0xFF7276, 0xFF727A, 0xFF727E    # 1B0BA6 / 1B0BBE
PAD_SEQ_TABLE = 0x413A              # ROM: the hidden button-sequence table, 2 bytes/entry, FF terminated

_TEXT_ARG_LEN = {0x00: 0, 0x01: 1, 0x02: 1, 0x03: 2, 0x04: 2, 0x05: 3, 0x06: 1,
                 0x07: 0, 0x08: 0, 0x09: 0, 0x0A: 0, 0x0B: 0, 0x0C: 3, 0x0F: 8}


def _text_end(rom, addr):
    """Where ``messages.print_text`` (1B21F6) stops walking the string at ``addr``: the same command-byte
    argument lengths it uses, so a caller that prints one string per call (1B4410) can chain the next."""
    p = addr
    while True:
        c = rom[p]
        p += 1
        if c == 0x00:
            return p
        if c < 0x20:
            p += _TEXT_ARG_LEN.get(c, 0)


def _title_tiles(state, services):
    """1B477C: the title's own three background layers."""
    for source, vram in TITLE_TILES:
        sequences.decompress_to_vram(state, source, vram, services)


def _place_title_cursor(state):
    """1B43C4: the cursor object (slot 2) next to the selected menu row."""
    record = RECORD_TABLE + RECORD_SIZE * 2
    cursor = state.read(CURSOR, 2)
    state.write(record + 4, (cursor << 4) + 0x184 & 0xFFFF, 2)
    state.write(record + 2, 0xD4, 2)


def _spawn_from_list(state, services):
    """1B4802: one entry from the word list at FF7282 spawns into a free slot 3..22, guarded by FFF0FF."""
    if not state.read(SPAWN_LIST_ENABLED, 1):
        return
    p = state.read(SPAWN_LIST_SOURCE, 4)
    x = int.from_bytes(state.rom[p:p + 2], 'big')
    if x == 0:
        return
    y = int.from_bytes(state.rom[p + 2:p + 4], 'big')
    p += 4
    record = None
    scan = RECORD_TABLE + RECORD_SIZE * 3
    for _ in range(20):
        if not state.read(scan, 1):
            record = scan
            break
        scan += RECORD_SIZE
    if record is None:
        return
    sequences.init_template(state, record, SPAWN_LIST_TEMPLATE, x, y)
    state.write(SPAWN_LIST_SOURCE, p, 4)


def _print(state, services, text, column, row):
    """1B21F6 as the title calls it: no control byte in these strings waits, but the walker is general."""
    messages.print_text(state.read, state.write, state.rom, state.vdp, text, column, row,
                         sequences.text_wait(state, services), lambda: sequences.latched(state))


def _menu_frame(state, services):
    """1B3F36 / 1B40A8 / 1B471E: the menu's own per-frame update -- animation *before* motion (mini_frame
    runs them the other way for the main loop's own order), no VBlank-wait alone (folded into services.vblank())."""
    engine = Engine(state.memory(), services)
    engine.animation_pass()
    engine.motion_pass()
    sprites.build_sprite_table(state.read, state.write, state.rom, state.bus_read, objects_only=True)
    services.vblank()
    video.flush_upload_queue(state.read, state.write, state.vdp)
    video.upload_sprite_table(state.read, state.rom, state.vdp)


def _arm_menu(state, services):
    """1B3E66..1B3EA2: ready the title's menu for input -- the title's own entry, and where the options
    screen's exit (1B4280 ``bra.w $1b3e66``) rejoins the title (both reach this same ROM code)."""
    write = state.write
    write(0xFFF157, 0, 1)
    write(SELECT_LATCH, 0xFF, 1)
    write(CURSOR, 0, 2)
    _print(state, services, BLANK_ROW, 0, 0x19)
    _print(state, services, PRESS_START_TEXT, 0xE, 0x10)
    _place_title_cursor(state)
    services.checkpoint(0x1B3EA2)                  # once per pass, at the instruction that arms the timeout
    write(CURSOR_TIMEOUT, CURSOR_TIMEOUT_FRAMES, 2)


def _reset_pad_sequence(state):
    """1B0BA6: (re)arm the hidden button-sequence reader at the table's start."""
    state.write(PAD_SEQ_PTR, PAD_SEQ_TABLE, 4)
    state.write(PAD_SEQ_RESET, PAD_SEQ_TABLE, 4)
    state.write(PAD_SEQ_MATCHED, 0, 1)


def _pad_sequence_step(state, services):
    """1B0BBE: one step of the hidden button-sequence reader.  A(0x10)/Start(0x20) come from what a TH-low
    port read would show; B(0x10)/C(0x20) from a TH-high read, repacked into the table's own byte pattern.
    The sequence's own completion (1B0C82, which unwinds two call frames) is not recovered."""
    a0 = state.read(PAD_SEQ_PTR, 4)
    d0 = (0x10 if state.buttons & 0x40 else 0) | (0x20 if state.buttons & 0x80 else 0)    # A, Start
    d1 = (0x10 if state.buttons & 0x10 else 0) | (0x20 if state.buttons & 0x20 else 0)    # B, C
    if d0 == 0 and d1 == 0:
        if state.read(PAD_SEQ_MATCHED, 1):
            state.write(PAD_SEQ_MATCHED, 0, 1)
            a0 += 2
            state.write(PAD_SEQ_PTR, a0, 4)
            if state.rom[a0] == 0xFF:
                raise NativeGap('title', OPTIONS_GAP.SECRET_PC,
                                 'the hidden button-sequence completion is not recovered', state.frame)
        return
    if state.rom[a0] == d0 and state.rom[a0 + 1] == d1:
        state.write(PAD_SEQ_MATCHED, 0xFF, 1)
    else:
        _reset_pad_sequence(state)


def _draw_difficulty(state, services):
    """1B434E: the fixed label, then the difficulty name from the table at DIFFICULTY_TABLE (both printed
    at the same position -- the label's own text blanks the line the name is drawn over)."""
    digit = state.read(DIFFICULTY, 1)
    name = int.from_bytes(state.rom[DIFFICULTY_TABLE + 4 * digit:DIFFICULTY_TABLE + 4 * digit + 4], 'big')
    _print(state, services, DIFFICULTY_LABEL, 0xA, 0xE)
    _print(state, services, name, 0xA, 0xE)


def _draw_sound_music(state, services):
    """1B430C: the music and sound on/off labels."""
    _print(state, services, ONOFF_TEXT_A if state.read(MUSIC_ENABLED, 1) else ONOFF_TEXT_B, 0x15, 0x10)
    _print(state, services, ONOFF_TEXT_A if state.read(SOUND_ENABLED, 1) else ONOFF_TEXT_B, 0x19, 0x12)


def _draw_control_labels(state, services, text):
    """1B4410: the active control scheme's own three-line text, chained from its own terminators."""
    _print(state, services, text, 0x21, 0x16)
    text = _text_end(state.rom, text)
    _print(state, services, text, 0x21, 0x17)
    text = _text_end(state.rom, text)
    _print(state, services, text, 0x21, 0x18)


def _load_control_profile(state, services):
    """1B32E2 (the 12-byte routine table copy) + 1B4410 (its trailing text), from CONTROL_PROFILE_PTR."""
    source = state.read(CONTROL_PROFILE_PTR, 4)
    for i in range(3):
        state.write(CONTROL_PROFILE_COPY + 4 * i,
                    int.from_bytes(state.rom[source + 4 * i:source + 4 * i + 4], 'big'), 4)
    _draw_control_labels(state, services, source + 12)


def _place_options_cursor(state):
    """1B43E0: the shared cursor object (slot 2), next to the selected options row."""
    record = RECORD_TABLE + RECORD_SIZE * 2
    cursor = state.read(CURSOR, 2)
    state.write(record + 4, ((cursor << 4) + 0x174) & 0xFFFF, 2)
    state.write(record + 2, 0xB4, 2)


def _place_remap_cursor(state):
    """1B43FC: the cursor object placed for the button-remap screen (a fixed position)."""
    record = RECORD_TABLE + RECORD_SIZE * 2
    state.write(record + 4, 0x194, 2)
    state.write(record + 2, 0xCC, 2)


def _options_frame(state, services):
    """1B409A..1B40BA: the options screen's own per-frame update (animation *after* the VBlank wait here,
    unlike the title's own ``_menu_frame``; the pad-sequence reader runs every frame)."""
    state.write(player.FRAME_COUNTER, (state.read(player.FRAME_COUNTER, 1) + 1) & 0xFF, 1)
    _pad_sequence_step(state, services)
    services.vblank()
    engine = Engine(state.memory(), services)
    engine.animation_pass()
    engine.motion_pass()
    video.flush_upload_queue(state.read, state.write, state.vdp)
    sprites.build_sprite_table(state.read, state.write, state.rom, state.bus_read, objects_only=True)
    video.upload_sprite_table(state.read, state.rom, state.vdp)


def _options_screen(state, services):
    """1B4056..1B430A: the options screen's own menu loop (difficulty, music, sound, control scheme, the
    button-remap entry, and exit).  Returns when the original reaches 1B3E66 (``bra.w`` back to the title)."""
    read, write = state.read, state.write
    services.checkpoint(0x1B4056)
    _reset_pad_sequence(state)
    write(CURSOR, 0, 2)
    write(OPTIONS_SELECT_LATCH, 0xFF, 1)

    def redraw():
        write(0xFFF157, 1, 1)
        _print(state, services, OPTIONS_HEADER_TEXT, 0xA, 0x10)
        _draw_difficulty(state, services)
        _draw_sound_music(state, services)
        _load_control_profile(state, services)
        _place_options_cursor(state)

    redraw()
    services.checkpoint(0x1B409A)                  # once per pass, right before the per-frame loop

    while True:
        _options_frame(state, services)

        start = bool(state.buttons & 0x80)
        a = bool(state.buttons & 0x40)
        b = bool(state.buttons & 0x10)
        c = bool(state.buttons & 0x20)

        if start or a or b or c:
            if read(OPTIONS_SELECT_LATCH, 1):
                pass                                        # already held: fall through to Up/Down
            elif start:
                sequences.decompress_to_vram(state, 0x12F4EC, 0xC000, services)     # 1B47F0
                return
            else:
                services.sound(0, 6)                         # 1B329E, unconditional
                cursor = read(CURSOR, 2)
                if cursor == 0:
                    write(OPTIONS_SELECT_LATCH, 0xFF, 1)
                    digit = (read(DIFFICULTY, 1) + 1) % 3
                    write(DIFFICULTY, digit, 1)
                    _draw_difficulty(state, services)
                    continue
                elif cursor == 1:
                    write(OPTIONS_SELECT_LATCH, 0xFF, 1)
                    was_on = bool(read(MUSIC_ENABLED, 1))
                    write(MUSIC_ENABLED, 0 if was_on else 1, 1)
                    services.sound_command(0x16)
                    if not was_on:
                        services.sound(0, 0x1A)
                    sequences.sound_if_enabled(state, services, CURSOR_MOVE_SOUND, flag=SOUND_ENABLED)
                    continue
                elif cursor == 2:
                    write(OPTIONS_SELECT_LATCH, 0xFF, 1)
                    write(SOUND_ENABLED, 0 if read(SOUND_ENABLED, 1) else 1, 1)
                    _draw_sound_music(state, services)
                    continue
                elif cursor == 4:
                    write(OPTIONS_SELECT_LATCH, 0xFF, 1)
                    source = read(CONTROL_PROFILE_PTR, 4) + CONTROL_PROFILE_NEXT
                    if int.from_bytes(state.rom[source:source + 4], 'big') == 0:
                        source = CONTROL_PROFILE_DEFAULT
                    write(CONTROL_PROFILE_PTR, source, 4)
                    _load_control_profile(state, services)
                    continue
                elif cursor == 3:
                    _place_remap_cursor(state)
                    raise NativeGap('title', OPTIONS_GAP.REMAP_PC,
                                     'the button-remap screen is not recovered', state.frame)
                else:
                    sequences.decompress_to_vram(state, 0x12F4EC, 0xC000, services)
                    return
        else:
            write(OPTIONS_SELECT_LATCH, 0, 1)

        up = bool(state.buttons & 0x01)
        down = bool(state.buttons & 0x02)
        if up:
            if read(OPTIONS_DIR_LATCH, 1):
                continue
            write(OPTIONS_DIR_LATCH, 0xFF, 1)
            cursor = (read(CURSOR, 2) - 1) % 6
        elif down:
            if read(OPTIONS_DIR_LATCH, 1):
                continue
            write(OPTIONS_DIR_LATCH, 0xFF, 1)
            cursor = (read(CURSOR, 2) + 1) % 6
        else:
            write(OPTIONS_DIR_LATCH, 0, 1)
            continue
        write(CURSOR, cursor, 2)
        sequences.sound_if_enabled(state, services, CURSOR_MOVE_SOUND, flag=SOUND_ENABLED)
        _place_options_cursor(state)


TITLE_PALETTE_CYCLE_SOURCE = 0x129DAA   # 1B3B4A: 15 words from CRAM index 1, walking forward, wrapping at 0x38


def _cycle_title_palette(state):
    """1B3B4A: on even frames (FF7E28 bit 0 clear), 15 CRAM words from index 1 through the table at 129DAA."""
    if state.read(player.FRAME_COUNTER, 1) & 1:
        return
    offset = state.read(sequences.PALETTE_CYCLE_OFFSET, 2)
    source = TITLE_PALETTE_CYCLE_SOURCE + offset
    vdp = state.vdp
    vdp.control_long(0xC0020000)
    for i in range(15):
        vdp.data(int.from_bytes(state.rom[source + 2 * i:source + 2 * i + 2], 'big'))
    offset += 2
    if offset >= 0x38:
        offset = 0
    state.write(sequences.PALETTE_CYCLE_OFFSET, offset, 2)


def _logo_loop(state, services, count=0xB3 + 1):
    """1B3C64..1B3C80 / 1B3C92..1B3CAA: ``count`` mini frames with the palette cycled; a button cuts it short.

    Returns True when a button ended the loop early (the caller must skip to the post-intro convergence).
    """
    for _ in range(count):
        sequences.mini_frame(state, services)
        _cycle_title_palette(state)
        if sequences.any_button(state):
            return True
    return False


def title_screen(state, services):
    """1B3B96: the whole routine.  Returns ('game', None) or ('attract', level)."""
    read, write = state.read, state.write

    # ---- 1B3B96..1B3BFE: reset, backdrop, pads released, the title's own objects ----------------
    services.sound_command(0x16)                     # 1B3B9A
    write(pad.RAW_TH_HIGH, 0xFF, 1)
    write(pad.RAW_TH_LOW, 0xFF, 1)
    sequences.arm_any_button(state)
    sequences.clear_cram(state.vdp)
    state.vdp.control(0x8B00)
    state.vdp.control(0x8C81)
    sequences.clear_scroll(state.vdp)
    sequences.clear_bytes(state, 0xFFF008, 0x126)
    sequences.hscroll_first_band(state.vdp, 0, 0)
    sequences.retire_pool(state, services, 0, 32)
    sequences.sprite_terminator(state)
    write(sequences.PLANE_B_ON_A, 0, 1)
    sequences.plane_size_64(state)
    sequences.copy_words(state.vdp, state.rom, sequences.FONT_TILES, 0xF800, 0x400)
    write(player.INVULNERABLE, 0, 1)
    _title_tiles(state, services)

    record2 = RECORD_TABLE + RECORD_SIZE * 2
    sequences.init_template(state, record2, TITLE_PIECE_2, 0x192, 0x170)
    record3 = RECORD_TABLE + RECORD_SIZE * 3
    sequences.init_template(state, record3, TITLE_PIECE_3, 0x1BA, 0x170)

    # ---- 1B3C36..1B3C4A: the title objects' first (forced) frame, no VBlank -----------------------
    write(player.FRAME_COUNTER, 0xFF, 1)
    Engine(state.memory(), services).animation_pass(force=True)
    sprites.build_sprite_table(state.read, state.write, state.rom, state.bus_read, objects_only=True)   # 1AB7A4
    video.flush_upload_queue(state.read, state.write, state.vdp)
    video.upload_sprite_table(state.read, state.rom, state.vdp)

    # ---- 1B3C4E..1B3DB4: the logo intro -------------------------------------------------------
    write(sequences.PALETTE_CYCLE_OFFSET, 0, 2)
    sequences.fade_to(state, services, LOGO_FADE_IN)
    _cycle_title_palette(state)
    services.checkpoint(0x1B3C64)
    skipped = _logo_loop(state, services)
    if not skipped:
        _print(state, services, TITLE_TEXT_LOGO, 0xF, 0x13)
        skipped = _logo_loop(state, services)
    if not skipped:
        write(sequences.FADE_MINI_FRAMES, 0xFF, 1)
        sequences.fade_to(state, services, LOGO_PALETTE_A)
        write(sequences.FADE_MINI_FRAMES, 0, 1)
        services.sound_command(0x16)                     # 1B3CC8 (1E58F4 is always command 16)
        sequences.sound_if_enabled(state, services, STOP_MUSIC_CODE, flag=0xFFF57F)
        write(0xFFF119, 0xFF, 1)
        sequences.retire_pool(state, services, 0, 32)
        sequences.sprite_terminator(state)
        sequences.clear_records(state)
        sequences.init_template(state, record2, TITLE_PIECE_2B, 0x58, 0x164)
        sequences.mini_frame(state, services)
        sequences.clear_plane(state.vdp, 0xC000)
        sequences.mini_frame(state, services)
        sequences.decompress_to_vram(state, BACKDROP_OBJECT, 0xE000, services)
        sequences.mini_frame(state, services)
        if not sequences.latched(state):
            write(sequences.FADE_MINI_FRAMES, 0xFF, 1)
            sequences.fade_to(state, services, LOGO_PALETTE_B)
            write(sequences.FADE_MINI_FRAMES, 0, 1)
            write(0xFFF0FF, 1, 1)
            if not sequences.latched(state):
                services.checkpoint(0x1B3D68)          # once, at the instruction that starts the spawn list
                write(SPAWN_LIST_SOURCE, 0x6744, 4)
                for _ in range(0x117 + 1):
                    sequences.mini_frame(state, services)
                    _spawn_from_list(state, services)
                    if read(0xFFF0FF, 1) == 1:
                        sequences.palette_line(state, 0, BACKDROP_PALETTE)
                        write(0xFFF0FF, 2, 1)
                    if sequences.any_button(state):
                        break
                else:
                    # 1B3DAA: the fade to black only runs when the spawn loop's own dbra is exhausted --
                    # a button that ends the loop early (1B3DA2 ``beq.w $1b3db8``) skips straight to the
                    # convergence below, leaving FADE_TARGET at whatever the loop's last fade left it.
                    sequences.fade_to(state, services, sequences.BLACK_PALETTE)

    # ---- 1B3DB8: post-intro convergence -------------------------------------------------------
    sequences.clear_cram(state.vdp)
    if not read(0xFFF119, 1) and read(0xFFF57F, 1):
        services.sound_command(STOP_MUSIC_CODE)
    state.vdp.control(0x8B00)
    sequences.retire_pool(state, services, 0, 32)
    sequences.sprite_terminator(state)
    state.vdp.control(0x8C81)
    sequences.disarm_any_button(state)
    sequences.clear_plane(state.vdp, 0xC000)
    sequences.clear_plane(state.vdp, 0xE000)
    sequences.decompress_to_vram(state, BACKDROP_C[0], BACKDROP_C[1], services)
    sequences.decompress_to_vram(state, TITLE_TILES[2][0], TITLE_TILES[2][1], services)     # 0x136912 -> 0
    sequences.decompress_to_vram(state, BACKDROP_E[0], BACKDROP_E[1], services)
    sequences.init_template(state, record2, 0x1B7A44)
    services.vblank()
    sequences.palette_line(state, 2, 0x129012)
    sequences.palette_line(state, 1, 0x1297F2)
    sequences.palette_line(state, 0, 0x129812)
    sequences.palette_line(state, 3, 0x1290B2)
    write(DIR_LATCH, 0, 1)
    _arm_menu(state, services)

    # ---- 1B3EAA..1B4054: the menu loop --------------------------------------------------------
    while True:
        write(player.FRAME_COUNTER, (read(player.FRAME_COUNTER, 1) + 1) & 0xFF, 1)
        timeout = (read(CURSOR_TIMEOUT, 2) - 1) & 0xFFFF
        write(CURSOR_TIMEOUT, timeout, 2)
        if timeout == 0:
            level = _enter_attract(state, services)
            return ('attract', level)

        _menu_frame(state, services)
        any_cbas = sequences.any_button(state)
        if any_cbas:
            if not read(SELECT_LATCH, 1):
                cursor = read(CURSOR, 2)
                if cursor == 0:
                    if not read(SELECT_LATCH, 1):
                        sequences.fade_to(state, services, sequences.BLACK_PALETTE)
                        sequences.sprite_terminator(state)
                        return ('game', None)
                elif cursor == 1:
                    _options_screen(state, services)
                    _arm_menu(state, services)
                    continue
                else:
                    digit = (read(DIFFICULTY_DEBUG, 1) + 1) & 0xFF
                    write(DIFFICULTY_DEBUG, 0 if digit >= 5 else digit, 1)
                    sequences.sound_if_enabled(state, services, CURSOR_MOVE_SOUND, flag=0xFFF57D)
                    _place_title_cursor(state)
                    write(CURSOR_TIMEOUT, CURSOR_TIMEOUT_FRAMES, 2)
                    continue
        else:
            write(SELECT_LATCH, 0, 1)

        up = bool(state.buttons & 0x01)
        down = bool(state.buttons & 0x02)
        if up:
            if read(DIR_LATCH, 1):
                continue
            cursor = read(CURSOR, 2)
            cursor = 1 if cursor == 0 else (cursor - 1) & 0xFFFF
        elif down:
            if read(DIR_LATCH, 1):
                continue
            cursor = (read(CURSOR, 2) + 1) & 0xFFFF
            if cursor >= 2:
                cursor = 0
        else:
            write(DIR_LATCH, 0, 1)
            continue
        write(CURSOR, cursor, 2)
        sequences.sound_if_enabled(state, services, CURSOR_MOVE_SOUND, flag=0xFFF57D)
        _place_title_cursor(state)
        write(DIR_LATCH, 0xFF, 1)
        write(CURSOR_TIMEOUT, CURSOR_TIMEOUT_FRAMES, 2)


def _enter_attract(state, services):
    """1B3EBA..1B404C / 1B4666: the 1500-frame timeout picks the next attract demo table entry.

    Returns the level byte for the chosen entry.  A fifth consecutive timeout (the demo table
    wrapping around) shows a high-score table (1B4666) this module does not recover.
    """
    read, write = state.read, state.write
    sequences.fade_to(state, services, sequences.BLACK_PALETTE)
    sequences.retire_pool(state, services, 0, 32)
    sequences.sprite_terminator(state)
    sequences.copy_words(state.vdp, state.rom, 0x11E0A0, 0xD000, 0x800)
    sequences.arm_any_button(state)
    sequences.plane_size_64(state)
    sequences.clear_bytes(state, 0xFFF008, 0x126)
    while True:
        write(player.FRAME_COUNTER, 0, 1)
        write(0xFF7DEA, 0xBC614E, 4)
        write(pad.GAME_MODE, 1, 1)
        index = read(0xFFF57A, 2)
        entry = DEMO_TABLE + 6 * index
        write(0xFFF576, int.from_bytes(state.rom[entry:entry + 4], 'big'), 4)
        level = state.rom[entry + 4]
        write(0xFF7E26, level, 1)
        index = (index + 1) & 0xFFFF
        write(0xFFF57A, index, 2)
        if index != DEMO_TABLE_ENTRIES:
            sequences.fade_to(state, services, sequences.BLACK_PALETTE)
            sequences.sprite_terminator(state)
            return level
        raise NativeGap('title', 0x1B4666, 'the attract demo table wraparound (high-score table) is not recovered',
                        state.frame)
