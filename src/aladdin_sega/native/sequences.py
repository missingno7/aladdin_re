"""Transitions as sequences of nested frames: what the original runs outside its main loop.

A transition (a life lost, a level change) leaves the main loop and runs
its own small frame loops: palette fades (1B278A: 16 VBlanks stepping
all 64 CRAM entries; 1B26F0: 47 VBlanks growing the range one entry per
frame), "mini frames" (motion, animation, the sprite table, VBlank,
uploads), timed waits that a button can cut short, the screen redraw
through the strip machinery, and the level re-initialisation.  Every
primitive here is one of those ROM routines over the same game modules
the main loop uses; every VBlank the original waits for is one
``services.vblank()`` (which advances the recorded-pad clock), and the
sequences call ``services.checkpoint(pc)`` where the original reaches
``pc`` so that the verification tools can compare RAM there.

What the native runtime cannot know is how many VBlanks the original's
*work* took between waits (decompression and screen drawing run longer
than a frame); that lag is measured on the recording and applied from
:data:`TRANSITION_TIMING`, and a sequence whose own wait count differs
from the measurement stops with a NativeGap instead of guessing.
"""
from __future__ import annotations
from ..game import video, level, spawn, player, control, hud, compress, messages, pad
from ..game.objects import lifecycle
from ..game.objects.record import RECORD_TABLE, RECORD_SIZE, RECORD_COUNT, RecordView
from ..game.objects.script_engine import Engine
from ..game import sprites, scroll
from .state import NativeGap

# native frame in which a transition starts -> (kind, VBlank interrupts already taken in that frame when the
# sequence begins, the frame boundary at which the main loop resumes counted from the start frame, VBlank
# waits the sequence itself made).  Measured on the recording with the oracle: the 1A8F82 / 1A902E gate
# frame, the 1AC726 boundary after the 1A8C16 resume, the 1B249E gate count up to the resumed frame's own wait.
TRANSITION_TIMING = {
    75278: ('life_lost', 0, 160, 131),
    76174: ('life_lost', 0, 130, 101),
    77192: ('life_lost', 0, 147, 118),
    77641: ('life_lost', 0, 165, 136),
    77927: ('life_lost', 0, 134, 105),
    79034: ('life_lost', 0, 130, 101),
    79293: ('life_lost', 0, 634, 329),
    81096: ('life_lost', 0, 129, 103),
}

BLACK_PALETTE = 0x128ED2
FADE_FRAMES = 0xF + 1                # 1B278A
SLOW_FADE_FRAMES = 0x2E + 1         # 1B26F0
FADE_MINI_FRAMES = 0xFFF11B          # the fade keeps the objects moving when set
FADE_TARGET = 0xFF7DF2
FADE_STEP = 0xFFEFF6
PALETTE_SNAPSHOT = 0xFF8800          # 64 CRAM words the fade interpolates from
LIVES_DISPLAY_FRAMES = 0x103 + 1
LIVES_DISPLAY_SKIP_AFTER = 0x103 + 1 - 0xD2
CHECKPOINT = (0xFF7E0A, 0xFF7E0C, 0xFF7E0E, 0xFF7E10)   # screen X/Y and camera X/Y saved by 1B0490
HISCORE = 0xFF7E30
HISCORE_BEATEN = 0xFFF0F1
SOUND_ENABLED_SAVED = 0xFFF57E
STRIPS_BUSY = 0xFFF175
PLANE_B_CACHE = 0xFF8884
PLANE_B_ON_A = 0xFFF165
DEATH_TEMPLATES = ((1, 0x1B788C, 0x16A, 0x18A), (2, 0x1B7878, 0x120, 0x178))
PLAYER_TEMPLATE = 0x1B7864
PLAYER_STAND_SCRIPTS = {'hang': 0x122336, 'cutscene': 0x125C52, 'locked': 0x121D5A, 'stand': 0x121D88}
LEVEL_TABLE, LEVEL_ENTRY = 0x2C78, 0x42


def _w(v):
    return v & 0xFFFF


# ---- primitives ---------------------------------------------------------------------------------
def sound_if_enabled(state, services, sound_id, flag=0xFFF57D, flush=True):
    if state.read(flag, 1):
        services.sound(0, sound_id, flush=flush)


def clear_plane(vdp, base, words=0x800, fill=0):
    """1B2534: ``words`` words of ``fill`` from VRAM ``base``."""
    vdp.control_long(video.vram_write_command(base))
    for _ in range(words):
        vdp.data(fill)


def copy_words(vdp, rom, source, vram, count):
    """1B255C."""
    vdp.control_long(video.vram_write_command(vram))
    for i in range(count):
        vdp.data(int.from_bytes(rom[source + 2 * i:source + 2 * i + 2], 'big'))


def copy_ram_words(state, source, vram, count):
    vdp = state.vdp
    vdp.control_long(video.vram_write_command(vram))
    for i in range(count):
        vdp.data(state.read(source + 2 * i, 2))


def decompress_to_vram(state, source, vram):
    """1B3416: the VRAM decompressor through the 16 KB window at FF0000 (which it overwrites)."""
    state.vdp.control_long(video.vram_write_command(vram))
    window = bytearray(state.ram[0:0x4000])
    ring = compress.decompress_to_vdp(state.rom, source, state.vdp.data, window=window)
    state.ram[0:0x4000] = ring


def decompress_to_ram(state, source, destination):
    """1B3818."""
    out = compress.decompress(state.rom, source)
    size = int.from_bytes(state.rom[source + 4:source + 8], 'big')
    base = destination & 0xFFFF
    state.ram[base:base + size] = out[:size]


def clear_cram(vdp):
    """1B26B0."""
    vdp.control_long(video.PALETTE_COMMANDS[0])
    for _ in range(64):
        vdp.data(0)


def sprite_terminator(state):
    """1B269C: the four words at ROM 2A40 into the sprite table's VRAM (an empty table)."""
    copy_words(state.vdp, state.rom, 0x2A40, 0xF400, 4)


def clear_scroll(vdp):
    """1B211C: both vertical scroll words to zero."""
    vdp.control_long(scroll.VSCROLL_A); vdp.data(0)
    vdp.control_long(scroll.VSCROLL_B); vdp.data(0)


def set_palette_targets(state, source, lines=4):
    """1B278A's bookkeeping: the palette the fade heads for, line by line."""
    state.write(FADE_TARGET, source, 4)
    for i, address in enumerate(video.PALETTE_SOURCES[:lines]):
        state.write(address, source + 0x20 * i, 4)


def snapshot_cram(state):
    """The CRAM read-back (C00004 <- 00000020) into the 64 words at FF8800."""
    for i in range(64):
        state.write(PALETTE_SNAPSHOT + 2 * i, int.from_bytes(state.vdp.cram[2 * i:2 * i + 2], 'big'), 2)


def fade_to(state, services, source):
    """1B278A: 16 VBlank frames (mini frames when FFF11B) stepping all 64 CRAM entries toward ``source``."""
    set_palette_targets(state, source)
    snapshot_cram(state)
    for _ in range(FADE_FRAMES):
        if state.read(FADE_MINI_FRAMES, 1):
            mini_frame(state, services)
        else:
            services.vblank()
        fade_step(state, source, 64)


def slow_fade_to(state, services, source):
    """1B26F0: 47 VBlank frames; frame n steps the first n+1 entries (FFEFF6) toward the palette at ``source``."""
    vdp = state.vdp
    set_palette_targets(state, source)
    snapshot_cram(state)
    state.write(FADE_STEP, 0, 2)
    for _ in range(SLOW_FADE_FRAMES):
        services.vblank()
        vdp.control_long(scroll.HSCROLL_A)
        vdp.data(state.read(player.FRAME_COUNTER, 1) & 1)
        fade_step(state, source, state.read(FADE_STEP, 2) + 1)
        state.write(FADE_STEP, state.read(FADE_STEP, 2) + 1, 2)
        state.write(player.FRAME_COUNTER, (state.read(player.FRAME_COUNTER, 1) + 1) & 0xFF, 1)


def fade_step(state, source, count):
    """1B2940 / 1B29B0: the first ``count`` snapshot entries move one step per channel toward the target, to CRAM.

    1B2916 (64 entries, sources FF7262..FF726E set), 1B28CE / 1B28DC / 1B28F4 (16 / 32 / 48 entries)
    and 1B29B0 (FFEFF6 + 1 entries) all end in this loop.
    """
    vdp = state.vdp
    vdp.control_long(video.PALETTE_COMMANDS[0])
    for i in range(count):
        target = int.from_bytes(state.rom[source + 2 * i:source + 2 * i + 2], 'big')
        current = state.read(PALETTE_SNAPSHOT + 2 * i, 2)
        for mask, step in ((0xE, 2), (0xE0, 0x20), (0xE00, 0x200)):
            want, have = target & mask, current & mask
            if have != want:
                current = _w(current - step) if have > want else _w(current + step)
        state.write(PALETTE_SNAPSHOT + 2 * i, current, 2)
        vdp.data(current)


def fade_lines_step(state, source, lines):
    """1B28CE / 1B28DC / 1B28F4 / 1B2916: one fade step over ``lines`` palette lines, their sources remembered."""
    for i in range(lines):
        state.write(video.PALETTE_SOURCES[i], source + 0x20 * i, 4)
    fade_step(state, source, 16 * lines)


def mini_frame(state, services, count=True):
    """1B28AE (1B28A6 sets the counter to FF instead): motion, animation, the objects' sprite table, VBlank, uploads."""
    if count:
        state.write(player.FRAME_COUNTER, (state.read(player.FRAME_COUNTER, 1) + 1) & 0xFF, 1)
    else:
        state.write(player.FRAME_COUNTER, 0xFF, 1)
    engine = Engine(state.memory(), services)
    engine.motion_pass()
    engine.animation_pass()
    sprites.build_sprite_table(state.read, state.write, state.rom, state.bus_read, objects_only=True)
    services.vblank()
    video.flush_upload_queue(state.read, state.write, state.vdp)
    video.upload_sprite_table(state.read, state.rom, state.vdp)


def wait_frames_or_button(state, services, count):
    """1B2EAC: up to ``count`` + 1 VBlanks, cut short once the any-button latch (FF7E22) is set."""
    for _ in range(count + 1):
        if state.read(0xFF7E22, 1):
            return
        state.write(0xFFF155, pad.raw_bytes(state.buttons)[1], 1)      # 1B319C
        services.vblank()


def any_of(state, *bits):
    return bool(state.buttons & sum(bits))


def lives_display(state, services):
    """1B2802: the empty screen with the death objects for up to 260 mini frames; A, B or C skips after 50."""
    clear_plane(state.vdp, 0xC000)
    for i in range(LIVES_DISPLAY_FRAMES):
        mini_frame(state, services)
        remaining = LIVES_DISPLAY_FRAMES - 1 - i
        if remaining < 0xD2 and any_of(state, 0x40, 0x10, 0x20):
            return


def clear_records(state):
    """1AE206."""
    for i in range(RECORD_COUNT * RECORD_SIZE):
        state.write(RECORD_TABLE + i, 0, 1)


def retire_pool(state, services, first, count):
    """1AE218 (all 32) / 1AE224 (slots 1..24): every active record is freed; spawn flags go back to the map."""
    engine = Engine(state.memory(), services)
    for slot in range(first, first + count):
        record = RECORD_TABLE + RECORD_SIZE * slot
        if not state.read(record, 1):
            continue
        state.write(record, 0, 1)
        view = RecordView(record, state.read, state.write)
        engine.release(view)
        if state.read(record + 6, 1) & 0x20 and state.read(record + 0x34, 1):
            state.write(spawn.SPAWN_FLAGS + state.read(record + 0x32, 2), state.read(record + 0x34, 1), 1)


def hiscore_check(state):
    """1B0078: the pending points are flushed into the score, then the score is compared to the high score."""
    state.write(HISCORE_BEATEN, 0, 1)
    while state.read(hud.PENDING_POINTS, 2):
        hud.score_tally_unit(state.read, state.write)
    for i in range(6):
        score, best = state.read(hud.SCORE_DIGITS - 1 + i, 1), state.read(HISCORE + i, 1)
        if score != best:
            if score < best:
                return
            break
    else:
        return
    for i in range(6):
        state.write(HISCORE + i, state.read(hud.SCORE_DIGITS - 1 + i, 1), 1)
    state.write(HISCORE_BEATEN, 0xFF, 1)


def init_player(state, services):
    """1AA696: health 8, the player's template, the standing script, the pad bytes released."""
    state.write(hud.HEALTH, 8, 1)
    for address, value in lifecycle.initialize(RECORD_TABLE, state.rom[PLAYER_TEMPLATE:PLAYER_TEMPLATE + 19]):
        state.write(address, value, 1)
    control.stand_script(state.read, state.write)
    state.write(player.WALKING, 0, 1)
    state.write(0xFFF156, 0xFF, 1)
    state.write(0xFFF155, 0xFF, 1)


def player_start_script(state):
    """1B1F28: the player's script at a (re)start by FFF154, the camera lock and the carpet level."""
    if state.read(0xFFF154, 1):
        if state.read(player.LEVEL_INDEX, 1) == 8:
            script = PLAYER_STAND_SCRIPTS['hang']
        elif state.read(player.CAMERA_LOCK, 1):
            script = PLAYER_STAND_SCRIPTS['locked']
        else:
            script = PLAYER_STAND_SCRIPTS['cutscene']
    elif state.read(player.CAMERA_LOCK, 1):
        script = PLAYER_STAND_SCRIPTS['locked']
    elif state.read(player.LEVEL_INDEX, 1) == 8:
        script = PLAYER_STAND_SCRIPTS['hang']
    else:
        script = PLAYER_STAND_SCRIPTS['stand']
    player.set_script(state.write, script)
    state.write(player.ON_GROUND, 0xFF, 1)
    state.write(player.WALKING, 0, 1)
    state.write(player.FALL_TIMER, 0, 1)
    state.write(player.VELOCITY_Y, 0, 2)


def level_entry(state, offset, size=4):
    entry = LEVEL_TABLE + LEVEL_ENTRY * state.read(player.LEVEL_INDEX, 1)
    return int.from_bytes(state.rom[entry + offset:entry + offset + size], 'big')


def plane_size_64(state):
    """1B2E9A: plane size 64x32 and the name-table row commands (1B2142 with a 128-byte stride)."""
    state.vdp.control(0x9001)
    name_rows(state, 0x80)


def name_rows(state, stride):
    """1B2142: the row command tables FF8680 / FF8700 (plane A) and FF8780 (plane B), swapped by FFF165."""
    a, b = (0xE000, 0xC000) if state.read(PLANE_B_ON_A, 1) else (0xC000, 0xE000)
    for row in range(32):
        for base, address in ((a, 0xFF8680), (a, 0xFF8700), (b, 0xFF8780)):
            vram = (base + stride * row) & 0xFFFF
            state.write(address + 4 * row, ((vram & 0x3FFF) | 0x4000) | ((vram >> 14) << 16), 4)   # swapped command


def level_init(state, services):
    """1AE1C2: the level's own initialisation routine (level table +0x28)."""
    routine = level_entry(state, 0x28)
    try:
        LEVEL_INITS[routine](state, services)
    except KeyError:
        raise NativeGap('level_init', routine, f'level init routine {routine:06X} is not recovered', state.frame) from None


def _init_message(code):
    def init(state, services):
        plane_size_64(state)
        state.write(hud.MESSAGE, code, 1)
        services.show_message(code)
    return init


def _init_plain(state, services):
    plane_size_64(state)


def _init_reg_8b02_then_plane(state, services):
    state.vdp.control(0x8B02)
    plane_size_64(state)


def _init_level_0(state, services):
    state.write(hud.MESSAGE, 0x17, 1)
    services.show_message(0x17)
    state.vdp.control(0x8B02)
    plane_size_64(state)


def _init_level_3(state, services):
    plane_size_64(state)
    state.vdp.control(0x8B02)
    state.write(hud.MESSAGE, 0x10, 1)
    services.show_message(0x10)


def _init_level_5(state, services):
    plane_size_64(state)
    state.write(0xFFF111, 1, 1)
    state.write(hud.MESSAGE, 0x18, 1)
    services.show_message(0x18)


def _init_level_7(state, services):
    plane_size_64(state)
    state.vdp.control(0x8B02)


def _init_level_9(state, services):
    state.vdp.control(0x8B02)
    state.write(player.ATTRIBUTE_LAYER, 1, 2)
    plane_size_64(state)


LEVEL_INITS = {
    0x1B63EA: _init_level_0, 0x1B6406: _init_reg_8b02_then_plane, 0x1B6414: _init_level_3, 0x1B642E: _init_plain,
    0x1B6434: _init_level_5, 0x1B64C2: _init_level_7, 0x1B653E: _init_level_9, 0x1B6554: _init_reg_8b02_then_plane,
    0x1B655C: _init_plain,
}


def restore_checkpoint(state):
    """1B04DE: the player's screen offsets and the camera from the checkpoint; the window anchored there."""
    state.write(player.SCREEN_X, state.read(CHECKPOINT[0], 2), 2)
    state.write(player.SCREEN_Y, state.read(CHECKPOINT[1], 2), 2)
    state.write(player.CAMERA_X, state.read(CHECKPOINT[2], 2), 2)
    state.write(player.CAMERA_Y, state.read(CHECKPOINT[3], 2), 2)
    player.publish_position(state.read, state.write)
    state.write(level.COLUMN_DEBT, 0, 2)
    state.write(level.ROW_DEBT, 0, 2)
    state.write(level.WINDOW_X, state.read(player.CAMERA_X, 2), 2)
    state.write(level.WINDOW_Y, state.read(player.CAMERA_Y, 2), 2)


def reset_apples(state):
    """1AA66E: apples by difficulty: 15 / 10 / 05."""
    difficulty = state.read(hud.DIFFICULTY, 1)
    state.write(hud.APPLES, 0x3135 if difficulty == 0 else 0x3130 if difficulty == 1 else 0x3035, 2)


def reload_attributes(state):
    """1B3434: the level's cell attributes (level table +8) decompressed to FFAE84."""
    decompress_to_ram(state, level_entry(state, 8), player.CELL_ATTRIBUTES)


def _walk(state, services):
    def walk(row, far):
        try:
            spawn.walk_strip(state.read, state.write, state.rom, state.vdp, services, row=row, far=far)
        except spawn.SpawnGap as error:
            raise NativeGap('screen_draw', 0x1AE44A, str(error), state.frame) from None
    return walk


def _strip_pass(state, services):
    engine = Engine(state.memory(), services)
    engine.motion_pass()
    engine.animation_pass()
    sprites.build_sprite_table(state.read, state.write, state.rom, state.bus_read)
    scroll.run(state.read, state.write, state.rom, state.vdp, services)
    level.draw_pending_strips(state.read, state.write, state.rom, state.vdp, _walk(state, services))
    video.flush_upload_queue(state.read, state.write, state.vdp)
    video.upload_sprite_table(state.read, state.rom, state.vdp)


def draw_screen(state, services):
    """1AA724: the visible window drawn by walking the camera 23 columns right and back, muted."""
    if state.read(player.CAMERA_LOCK, 1):
        raise NativeGap('screen_draw', 0x1AA81A, 'the locked-camera screen draw is not recovered', state.frame)
    read, write = state.read, state.write
    write(SOUND_ENABLED_SAVED, read(player.SOUND_ENABLED, 1), 1)
    write(player.SOUND_ENABLED, 0, 1)
    write(STRIPS_BUSY, 0xFF, 1)
    write(player.CAMERA_TARGET_HOLD, 0, 1)
    for _ in range(0x17):
        if _w(read(level.WINDOW_X, 2) + read(level.COLUMN_DEBT, 2) + 16) < _w(read(0xFF7DB8, 2) - 0x161):
            write(player.SCREEN_X, _w(read(player.SCREEN_X, 2) - 16), 2)
            write(player.CAMERA_X, _w(read(player.CAMERA_X, 2) + 16), 2)
            write(level.COLUMN_DEBT, _w(read(level.COLUMN_DEBT, 2) + 16), 2)
            write(level.STRIP_RIGHT, 0xFF, 1)
            _strip_pass(state, services)
    for _ in range(0x17):
        player.publish_position(read, write)
        write(player.FRAME_COUNTER, (read(player.FRAME_COUNTER, 1) + 1) & 0xFF, 1)
        if read(level.WINDOW_X, 2) >= 0x11:
            write(player.SCREEN_X, _w(read(player.SCREEN_X, 2) + 16), 2)
            write(player.CAMERA_X, _w(read(player.CAMERA_X, 2) - 16), 2)
            write(level.COLUMN_DEBT, _w(read(level.COLUMN_DEBT, 2) - 16), 2)
            write(level.STRIP_LEFT, 0xFF, 1)
            _strip_pass(state, services)
    write(player.SOUND_ENABLED, read(SOUND_ENABLED_SAVED, 1), 1)
    write(STRIPS_BUSY, 0, 1)


def edge_strips(state, services):
    """1AB44C then 1AB66C: the right column and the top row once, with their spawn walks."""
    walk = _walk(state, services)
    if level.draw_column(state.read, state.write, state.rom, state.vdp, True):
        walk(row=False, far=True)
    if level.draw_row(state.read, state.write, state.rom, state.vdp, False):
        walk(row=True, far=False)


def music(state, services):
    """1AE1DA: the level's music (level table +0x1A) through the sound driver's flush command."""
    if state.read(0xFFF57F, 1):
        services.sound_flush(level_entry(state, 0x1A, 2))


def restore_plane_b(state):
    """The cached plane B name table (FF8884) back into VRAM (E000, or C000 when the planes are swapped)."""
    copy_ram_words(state, PLANE_B_CACHE, 0xC000 if state.read(PLANE_B_ON_A, 1) else 0xE000, 0x800)


def fade_in_level_palette(state, services):
    """1AE1A0: the level's palette (level table +0x20) faded in."""
    source = level_entry(state, 0x20)
    state.write(0xFFEFE6, source, 4)
    fade_to(state, services, source)


# ---- the sequences ---------------------------------------------------------------------------------
def respawn(state, services, fell: bool):
    """1A902E (fell below the level) / 1A8F82 (the dying countdown ran out), then 1A9088: a life lost."""
    read, write = state.read, state.write
    services.sound_command(0x16)
    if fell:
        sound_if_enabled(state, services, 0x02, flag=0xFFF57D)
        fade_to(state, services, BLACK_PALETTE)
        hiscore_check(state)
        write(RECORD_TABLE, 0, 1)
        Engine(state.memory(), services).release(RecordView(RECORD_TABLE, read, write))
        retire_pool(state, services, 1, 24)
        sprite_terminator(state)
        wait_frames_or_button(state, services, 0x23)
    else:
        services.checkpoint(0x1A8F90)
        sound_if_enabled(state, services, 0x02, flag=0xFFF57F)
        fade_to(state, services, BLACK_PALETTE)
        services.checkpoint(0x1A8FB8)
        retire_pool(state, services, 0, 32)
        clear_records(state)
        services.checkpoint(0x1A8FC0)
        mini_frame(state, services, count=False)
        services.checkpoint(0x1A8FC6)
        video.load_palette(write, state.rom, state.vdp, 3, 0x1290B2)
        for slot, template, x, y in DEATH_TEMPLATES:
            record = RECORD_TABLE + RECORD_SIZE * slot
            for address, value in lifecycle.initialize(record, state.rom[template:template + 19]):
                write(address, value, 1)
            write(record + 2, x, 2)
            write(record + 4, y, 2)
        services.checkpoint(0x1A900A)
        hiscore_check(state)
        services.checkpoint(0x1A900E)
        lives_display(state, services)
        if read(player.LEVEL_INDEX, 1) >= 0x14:
            write(player.DYING, 0, 1)
            write(player.TRANSITION_COUNTDOWN, 0xFF, 1)
            return
    services.checkpoint(0x1A9088)
    if read(hud.LIVES, 1) == 0x30:
        raise NativeGap('respawn', 0x1B0CBC, 'the game-over sequence is not recovered', state.frame)
    if not read(player.INVINCIBLE, 1):
        write(hud.LIVES, read(hud.LIVES, 1) - 1, 1)
    services.checkpoint(0x1A90CA)
    fade_to(state, services, BLACK_PALETTE)
    clear_records(state)
    sprite_terminator(state)
    for i in range(0x126):
        write(0xFFF008 + i, 0, 1)
    services.checkpoint(0x1A90DE)
    init_player(state, services)
    player_start_script(state)
    services.checkpoint(0x1A90E8)
    level_init(state, services)
    write(player.FRAME_COUNTER, 0xFF, 1)
    write(0xFFEFFD, 0xFF, 1)
    write(control.JUMP_HOLD, 0xFF, 1)
    services.checkpoint(0x1A90FE)
    restore_checkpoint(state)
    reset_apples(state)
    services.checkpoint(0x1A9106)
    reload_attributes(state)
    services.checkpoint(0x1A910C)
    draw_screen(state, services)
    services.checkpoint(0x1A9110)
    player_start_script(state)
    if read(player.LEVEL_INDEX, 1) == 8:
        write(RECORD_TABLE + RECORD_SIZE + 2, read(player.WORLD_X, 2), 2)
        write(RECORD_TABLE + RECORD_SIZE + 4, read(player.WORLD_Y, 2), 2)
    write(player.ON_GROUND, 0xFF, 1)
    write(player.WALKING, 0, 1)
    write(player.FALL_TIMER, 0, 1)
    write(player.VELOCITY_Y, 0, 2)
    services.checkpoint(0x1A9152)
    edge_strips(state, services)
    write(player.FRAME_COUNTER, 0xFF, 1)
    services.checkpoint(0x1A9160)
    services.vblank()
    engine = Engine(state.memory(), services)
    services.checkpoint(0x1A9166)
    engine.animation_pass(force=True)
    sprites.build_sprite_table(read, write, state.rom, state.bus_read)
    engine.motion_pass()
    video.flush_upload_queue(read, write, state.vdp)
    video.upload_sprite_table(read, state.rom, state.vdp)
    player.publish_position(read, write)
    services.checkpoint(0x1A917E)
    scroll.run(read, write, state.rom, state.vdp, services)
    services.sound_command(0x16)
    services.checkpoint(0x1A9190)
    music(state, services)
    services.checkpoint(0x1A9194)
    restore_plane_b(state)
    services.checkpoint(0x1A91B8)
    fade_in_level_palette(state, services)
    services.checkpoint(0x1A91BC)
    write(player.INVULNERABLE, 0x28, 1)


def run_transition(state, services, kind: str):
    """Run the sequence for a transition raised inside a frame, then settle the recorded-pad clock."""
    start = state.frame
    timing = TRANSITION_TIMING.get(start)
    if timing is None:
        raise NativeGap(kind, 0, f'no timing witness for the transition starting in frame {start}', state.frame)
    witness_kind, interrupts_taken, resume, witness_waits = timing
    if witness_kind != kind:
        raise NativeGap(kind, 0, f'the timing witness for frame {start} is for {witness_kind!r}', state.frame)
    state.advance_frames(interrupts_taken)       # the recorded pad the sequence starts from
    waits_before = services.waits
    if kind in ('fell', 'life_lost'):
        respawn(state, services, fell=(kind == 'fell'))
    else:
        raise NativeGap(kind, 0, f'transition {kind!r} is not recovered', state.frame)
    waits = services.waits - waits_before
    if witness_waits != waits:
        raise NativeGap(kind, 0, f'the sequence made {waits} VBlank waits, the original {witness_waits}', state.frame)
    state.advance_frames(resume - interrupts_taken - waits - 1)   # the frame loop counts the resumed frame's own VBlank
