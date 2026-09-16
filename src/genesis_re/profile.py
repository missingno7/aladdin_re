"""What varies per cartridge (a GameProfile) and what is the console's (the Board)."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


def _sha256_of(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Board:
    """The NTSC Genesis as the native adapter models it.  Both supported games run on it."""
    id: str = "genesis-ntsc-v1"
    region: str = "ntsc"
    master_hz: int = 53_693_175
    m68k_divider: int = 7
    z80_divider: int = 15
    frame_ticks: int = 896_040
    controller: str = "port1-three-button"
    power_on: str = "zero-ram"
    scheduling: str = "instruction-boundaries-v1"
    audio: str = "nuked-opn2-ym2612+nuked-psg;pcm-s16-clamped"
    # Where inside a frame the adapter delivers the vertical interrupt (raster
    # line 224 of 262): measured on the machine, a fact about the board rather
    # than a term of its identity (docs/gods/research/timing-verification-pass-2026-09-16.md).
    vblank_offset_ticks: int = 766_522

    @property
    def record(self) -> dict[str, Any]:
        return {"master_hz": self.master_hz, "m68k_divider": self.m68k_divider, "z80_divider": self.z80_divider,
                "frame_ticks": self.frame_ticks, "controller": self.controller, "power_on": self.power_on,
                "scheduling": self.scheduling, "audio": self.audio}

    @property
    def sha256(self) -> str:
        return _sha256_of({"id": self.id, "region": self.region, **self.record})


NTSC = Board()
MASTER_HZ = NTSC.master_hz
FRAME_TICKS = NTSC.frame_ticks


@dataclass(frozen=True)
class GameProfile:
    """One supported cartridge revision and the project that recovers it.

    ``candidate`` turns a candidate name into an armed dispatcher for recovered
    code (``arm(machine)``, ``on_gate(machine, deadline)``, ``stats``); a game
    without recovered code leaves it ``None`` and runs only as the original.
    """
    id: str                                   # stable game id: the CLI's --game, the history directory
    title: str
    package: str                              # the Python package holding the game's recovered code
    profile_id: str                           # e.g. aladdin-usa-ntsc-v1: the exact supported revision
    rom_sha256: str
    rom_size: int
    rom_filename: str                         # below assets/
    history_root: dict[str, Any]              # the immutable root record of original-machine histories
    board: Board = NTSC
    # Where inside a logical frame the replay observes the machine and deadlines
    # recovered operations.  Measured per game (docs/execution-model-research.md
    # for Aladdin); the default is the middle of the frame.
    observation_offset_ticks: int = FRAME_TICKS // 2
    native_history_root: dict[str, Any] | None = None
    candidate: Callable[[str], Any] | None = None
    tracer_native_entries: dict[int, str] = field(default_factory=dict)

    def __post_init__(self):
        if len(self.rom_sha256) != 64 or self.rom_size <= 0 or not self.id or not self.profile_id:
            raise ValueError("Incomplete game profile")
        if self.board.region != "ntsc":
            raise ValueError("The native adapter models the NTSC board only")

    @property
    def profile(self) -> dict[str, Any]:
        return {"id": self.profile_id, "rom_sha256": self.rom_sha256, **self.board.record}

    @property
    def profile_sha256(self) -> str:
        return _sha256_of(self.profile)

    @property
    def rom_path(self) -> Path:
        return Path("assets") / self.rom_filename

    def read_rom(self, path=None) -> bytes:
        data = Path(self.rom_path if path is None else path).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if len(data) != self.rom_size or actual != self.rom_sha256:
            raise ValueError(f"Wrong {self.title} ROM revision: expected {self.rom_sha256} "
                             f"({self.rom_size} bytes); got {actual} ({len(data)} bytes)")
        return data

    def history_path(self, root: Path | str = "history") -> Path:
        return Path(root) / self.id

    def native_history_path(self, root: Path | str = "history_native") -> Path:
        return Path(root) / self.id
