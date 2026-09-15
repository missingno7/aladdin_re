"""Gods: the one supported cartridge revision and its history roots.

Inspected from the cartridge in assets/ (header at 0x100): "SEGA GENESIS",
"(C)SEGA 1992.JUN", domestic/overseas name "GODS", serial "GM T87016  -00",
region "U", ROM 000000-0FFFFF, work RAM FF0000-FFFFFF, header checksum
E80A (matches the computed sum), entry 000200.  Recovered code lives in
``game`` (semantics), ``boundary`` (exact effects) and ``recovery`` (gate
dispatch); ``candidate`` names it for the replay runner.
"""
from genesis_re.history import digest, encoded
from genesis_re.profile import GameProfile

ROM_SHA256 = "f7e577a66ed4d9901cb44ed0620e61439527cfbd854bc4626173b17e30fa6be0"
HISTORY_ROOT = {"format": "input-history-1", "root": "gods-usa-new",
                "clock": "simulation-frame", "input": "three-button-pad-1", "initial_buttons": 0}
ROOT_ID = digest(encoded(HISTORY_ROOT))


def candidate(name):
    from .recovery import Candidate
    return Candidate(name)


GODS = GameProfile(
    id="gods", title="Gods", package="gods_sega",
    profile_id="gods-usa-ntsc-v1", rom_sha256=ROM_SHA256, rom_size=1_048_576,
    rom_filename="Gods (USA).md", history_root=HISTORY_ROOT, candidate=candidate)
DEFAULT_ROM = GODS.rom_path


def read_rom(path=DEFAULT_ROM):
    return GODS.read_rom(path)
