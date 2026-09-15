"""Aladdin: the one supported cartridge revision, its history roots and its recovery entry point."""
from genesis_re.history import digest, encoded
from genesis_re.profile import FRAME_TICKS, MASTER_HZ, GameProfile

ROM_SHA256 = "a3779fc77994780e80d05bb557f800110d0398d34b951baa8c0a14910014ded3"
# Where inside a logical frame the replay observes the machine and deadlines
# recovered operations: raster line 131, the middle of the game's idle window
# (the 68000 waits for the next VBlank from line 60 to line 224; it is busy
# from the VBlank at line 225 through the frame wrap to line 37).  The input
# instant stays at the frame wrap.  Measured in docs/execution-model-research.md.
OBSERVATION_OFFSET_TICKS = FRAME_TICKS // 2
HISTORY_ROOT = {"format": "input-history-1", "root": "aladdin-usa-new",
                "clock": "simulation-frame", "input": "three-button-pad-1", "initial_buttons": 0}
# The native runtime's histories: the same immutable model, but a frame is one of the game's own VBlank waits
# (the mask for game frame W applies when the game returns from its W-th wait), never elapsed console time.
NATIVE_HISTORY_ROOT = {"format": "input-history-1", "root": "aladdin-usa-native",
                       "clock": "game-frame", "input": "three-button-pad-1", "initial_buttons": 0}
ROOT_ID = digest(encoded(HISTORY_ROOT))
NATIVE_ROOT_ID = digest(encoded(NATIVE_HISTORY_ROOT))
# Native routines the tracer collapses to one segment: the sound driver's entry points and the tile upload.
TRACER_NATIVE_ENTRIES = {0x1E58B8: 'sound-request', 0x1E58F4: 'sound-fixed-helper', 0x1E589A: 'sound-flush',
                         0x1B2650: 'vdp-tile-upload'}


def candidate(name):
    from .recovery import Candidate
    return Candidate(name)


ALADDIN = GameProfile(
    id="aladdin", title="Aladdin", package="aladdin_sega",
    profile_id="aladdin-usa-ntsc-v1", rom_sha256=ROM_SHA256, rom_size=2_097_152,
    rom_filename="Aladdin (USA).md",
    history_root=HISTORY_ROOT, native_history_root=NATIVE_HISTORY_ROOT,
    observation_offset_ticks=OBSERVATION_OFFSET_TICKS,
    candidate=candidate, tracer_native_entries=TRACER_NATIVE_ENTRIES)
PROFILE = ALADDIN.profile
PROFILE_SHA256 = ALADDIN.profile_sha256
DEFAULT_ROM = ALADDIN.rom_path


def read_rom(path=DEFAULT_ROM):
    return ALADDIN.read_rom(path)
