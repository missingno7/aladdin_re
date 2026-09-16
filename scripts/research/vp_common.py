"""vp_common: shared setup for the verification pass (2026-09-16).  Read-only research tooling.

Every script of the pass imports this first: it puts the COMMITTED source tree exported to
artifacts/gods/research/src-at-HEAD (src, scripts) first on sys.path so the grinder's working
tree is never imported, and offers ``gods_profile(offset)`` -- the Gods profile with only the
observation instant replaced (dataclasses.replace), registered for this process only so
``Machine``/``GenesisRun`` accept it as the game.  Nothing under the product is changed.
"""
import dataclasses
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISO = ROOT / 'artifacts' / 'gods' / 'research' / 'src-at-HEAD'
if not (ISO / 'src').is_dir():
    raise SystemExit('export the committed tree first: %s' % ISO)
sys.path.insert(0, str(ISO / 'scripts'))
sys.path.insert(0, str(ISO / 'src'))
os.environ.setdefault('GENESIS_NATIVE_LIBRARY', str(ROOT / 'build' / 'libgenesis_native.dll'))
HEAD = (ISO / 'HEAD.txt').read_text().strip()

from genesis_re import games as _games            # noqa: E402
from gods_sega.profile import GODS as _GODS      # noqa: E402

FT = _GODS.board.frame_ticks
DIVIDER = _GODS.board.m68k_divider
DEFAULT_OFFSET = _GODS.observation_offset_ticks
MOVED_OFFSET = 757_154            # the report's proposed instant, 0.845 x FRAME_TICKS (raster line ~221)


def gods_profile(offset=None):
    """The Gods profile, with the observation instant replaced for THIS PROCESS only (never persisted)."""
    profile = _GODS if offset is None or offset == _GODS.observation_offset_ticks else \
        dataclasses.replace(_GODS, observation_offset_ticks=int(offset))
    _games.GAMES[profile.id] = profile      # so Machine.registered()/GenesisRun see the same object
    return profile


def guard_paths():
    """Assert the isolated tree is what got imported."""
    import genesis_re, gods_sega, pathfacts
    for module in (genesis_re, gods_sega, pathfacts):
        path = Path(module.__file__).resolve()
        if ISO not in path.parents:
            raise SystemExit('imported %s from the checkout, not the isolated tree: %s' % (module.__name__, path))
