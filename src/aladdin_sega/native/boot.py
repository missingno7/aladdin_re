"""Power-on to the first main-loop frame: the game's initialisation as recovered source.

The console's reset code (ROM 21A: TMSS, the VDP's and the Z80's setup,
the region check) is platform work; what it leaves for the game is the
*power-on contract* below (zeroed work RAM, the VDP as the reset code set
it).  From there the game runs its own code:

* 1AA344 (``game_init``): the sound driver's data tables handed to the
  driver (a platform service), the mode and level defaults, the region's
  frame rate, the high-score table and the button routines on first boot
  (the magic at FF728C says the table already exists).
* 1A8A4A / 1A8A58 (``new_game``): the VDP registers, the font and HUD
  tiles, the planes, the scroll table and the objects cleared; 1A8B24:
  the title screen and its menu (1B3B96), the score, lives, apples and
  gems reset, then the level prologue (1A8B50) and the main loop from
  its frame-counter step (1A8C16).  1A8B24 is also where the attract
  demo's exit (1B3182) and a declined continue (1A8A58) come back to.
"""
from __future__ import annotations
from ..game import video, player, hud
from ..game.objects.record import RECORD_TABLE
from .state import GameState, NativeGap
from . import sequences

GAME_INIT, NEW_GAME, TITLE_ENTRY, MAIN_LOOP = 0x1AA344, 0x1A8A58, 0x1A8B24, 0x1A8C16
SOUND_DRIVER_TABLES = (0x1B9D06, 0x1BAF46, 0x1BAF6F, 0x1C73CB)     # 1AA344: the four pointers pushed for 1E584A
HISCORE_MAGIC, HISCORE_MAGIC_VALUE = 0xFF728C, 0x294C
BUTTON_ROUTINES_DEFAULT = 0x4036                                     # ROM: three routine pointers (B, C, A)
FRAME_RATE = 0xFF7E27                                                # 0x32 (PAL) / 0x3C (NTSC) per the VDP's status
VDP_REGISTERS_1A8A58 = (0x8004, 0x8164, 0x8230, 0x8407, 0x857A, 0x8600, 0x8700, 0x8800, 0x8900, 0x8A00, 0x8B00,
                        0x8C00, 0x8D3C, 0x8E00, 0x8F02, 0x9001, 0x9100, 0x929C)
RESET_REGISTERS = (0x8164, 0x8230, 0x8C81, 0x8F02, 0x9001)          # ROM 356..366: what the reset code sets


def power_on(rom: bytes) -> GameState:
    """The power-on contract: work RAM zeroed (the reset code's fill loop), the VDP as the reset code leaves it."""
    state = GameState(bytearray(65536), rom, 0)
    for word in RESET_REGISTERS:
        state.vdp.control(word)
    state.vdp.control_long(0xC0020000)      # ROM 36A: colour 1 white, for the region message
    state.vdp.data(0x0EEE)
    return state


def game_init(state: GameState, services) -> None:
    """1AA344."""
    write, read = state.write, state.read
    services.sound_driver_init(SOUND_DRIVER_TABLES)
    services.sound_command(0x16)
    write(sequences.FADE_MINI_FRAMES, 0, 1)
    write(0xFF7274, 0, 1)
    write(0xFF7DA8, 0x29A6, 4)
    write(0xFFF57C, 0, 1)                   # not the attract demo
    write(0xFFF57A, 0, 2)
    write(player.LEVEL_INDEX, 1, 1)
    write(0xFF7E20, 0, 1)
    write(0xFF7E25, 0, 1)
    write(FRAME_RATE, 0x32 if services.pal() else 0x3C, 1)
    write(0xFFF158, 0, 1)
    write(0xFFF168, 0, 1)
    if read(HISCORE_MAGIC, 4) != HISCORE_MAGIC_VALUE:               # the first boot (RAM zeroed): the table
        write(sequences.HISCORE, 0x31, 1)                           # 1AFFE4: "100000"
        for i in range(1, 6):
            write(sequences.HISCORE + i, 0x30, 1)
        write(sequences.HISCORE + 6, 0, 1)
        write(0xFF7DDE, BUTTON_ROUTINES_DEFAULT, 4)
        for i in range(3):                                          # 1B32E2: the button routines
            write(0xFF7DD2 + 4 * i, int.from_bytes(state.rom[BUTTON_ROUTINES_DEFAULT + 4 * i:BUTTON_ROUTINES_DEFAULT + 4 * i + 4], 'big'), 4)
        write(player.SOUND_ENABLED, 1, 1)
        write(0xFFF57F, 1, 1)
        write(player.DIFFICULTY, 1, 1)
        write(HISCORE_MAGIC, HISCORE_MAGIC_VALUE, 4)


def new_game_setup(state: GameState, services) -> None:
    """1AA41C: the session defaults (the stream, level 1, the counters, the continues by difficulty)."""
    write, read = state.write, state.read
    services.sound_command(0x16)
    sequences.clear_bytes(state, 0xFFEFDC, 0x2B)                    # 1AA6EE
    write(0xFF7DE2, 0x12675E, 4)
    write(0xFFEFFB, 8, 1)
    write(sequences.SEQUENCE_STREAM, 0x4082, 4)
    write(player.LEVEL_INDEX, 1, 1)
    sequences.reset_apples(state)
    write(0xFFEFE2, 0x3030, 2)                                      # 1AA664
    difficulty = read(player.DIFFICULTY, 1)
    write(sequences.CONTINUES, 3 if difficulty == 0 else 1 if difficulty == 1 else 0, 1)


def new_game(state: GameState, services) -> str:
    """1A8A58: the console side of a new game, the title, the counters, the prologue; resumes at 1A8C16."""
    vdp = state.vdp
    new_game_setup(state, services)
    for word in VDP_REGISTERS_1A8A58:
        vdp.control(word)
    sequences.clear_cram(vdp)
    sequences.copy_words(vdp, state.rom, sequences.FONT_TILES, 0xF800, 0x400)     # 1B2E44
    sequences.copy_words(vdp, state.rom, 0x11E0A0, 0xD000, 0x800)                # 1B2E70
    sequences.clear_plane(vdp, 0xC000)
    sequences.clear_plane(vdp, 0xE000)
    sequences.hscroll_from_list(state)
    sequences.clear_scroll(vdp)
    sequences.clear_records(state)
    sequences.sprite_terminator(state)
    return title_entry(state, services)


def title_entry(state: GameState, services) -> str:
    """1A8B24: the title and its menu, the session counters, then the level prologue."""
    write = state.write
    write(0xFFF57C, 0, 1)
    services.checkpoint(0x1A8B2C)
    raise NativeGap('title', 0x1B3B96, 'the title screen and its menu are not recovered', state.frame)
    # 1B3B96 here, then:
    # sequences.plane_size_64(state); (1B02EA, 1B0022 are RTS)
    # sequences.reset_score(state); sequences.lives_by_difficulty(state); sequences.reset_apples(state)
    # write(0xFFEFE2, 0x3030, 2)
    # services.checkpoint(0x1A8B50); sequences.level_prologue(state, services); return 'frame_counter'


def start(state: GameState, services) -> str:
    """Power-on to the first main-loop frame; the step the frame loop resumes at."""
    services.checkpoint(GAME_INIT)
    game_init(state, services)
    services.checkpoint(NEW_GAME)
    return new_game(state, services)
