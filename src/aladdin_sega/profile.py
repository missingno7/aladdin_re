"""The one selected cartridge and board configuration."""
import hashlib
import json
from pathlib import Path

ROM_SHA256 = "a3779fc77994780e80d05bb557f800110d0398d34b951baa8c0a14910014ded3"
MASTER_HZ = 53_693_175
FRAME_TICKS = 896_040
PROFILE = {
    "id": "aladdin-usa-ntsc-v1", "rom_sha256": ROM_SHA256,
    "master_hz": MASTER_HZ, "m68k_divider": 7, "z80_divider": 15,
    "frame_ticks": FRAME_TICKS, "controller": "port1-three-button",
    "power_on": "zero-ram", "scheduling": "instruction-boundaries-v1",
    "audio": "nuked-opn2-ym2612+nuked-psg;pcm-s16-clamped",
}
PROFILE_SHA256 = hashlib.sha256(json.dumps(PROFILE, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
DEFAULT_ROM = Path("assets/Aladdin (USA).md")


def read_rom(path=DEFAULT_ROM):
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != 2_097_152 or actual != ROM_SHA256:
        raise ValueError(f"Wrong ROM revision: expected {ROM_SHA256}; got {actual}")
    return data
