"""The registry: every supported game, by its stable id.  Adding a game is one line here."""
from __future__ import annotations

import hashlib

from aladdin_sega.profile import ALADDIN
from gods_sega.profile import GODS
from .profile import GameProfile

GAMES: dict[str, GameProfile] = {ALADDIN.id: ALADDIN, GODS.id: GODS}


def game(game_id: str) -> GameProfile:
    try:
        return GAMES[game_id]
    except KeyError:
        raise ValueError(f"Unknown game {game_id!r}; supported: {', '.join(GAMES)}") from None


def registered(data: bytes) -> GameProfile | None:
    """The registered game whose exact revision these bytes are, or ``None`` for any other cartridge."""
    actual = hashlib.sha256(data).hexdigest()
    for profile in GAMES.values():
        if profile.rom_sha256 == actual and profile.rom_size == len(data):
            return profile
    return None


def for_rom(data: bytes) -> GameProfile:
    """The registered game these bytes are; an unknown cartridge is refused."""
    profile = registered(data)
    if profile is None:
        raise ValueError(f"No supported game has ROM SHA-256 {hashlib.sha256(data).hexdigest()}")
    return profile
