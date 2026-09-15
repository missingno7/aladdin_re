"""The replay clock interface: how recorded input lines up with a native run that spends no time on work.

This is harness-side, not game logic.  The native runtime computes a
transition's work (decompression, the screen draw) in zero frames while
the original spent VBlanks on it, during which the recording's player
kept pressing buttons.  To feed the game the input the original saw at
each point, a replay clock advances the frame counter at the sequence's
checkpoints (``services.checkpoint(pc)``) to the frame at which the
original reached ``pc``, and at the end of the transition to the
boundary at which the original's loop resumed.  The harness's clock
asks the oracle running alongside (scripts/aladdin/native_replay.OracleClock);
nothing about a recording is stored.  Without a replay clock (a
standalone game with live input) checkpoints do nothing and the game
simply runs its transitions faster.

A clock is also the harness's proof: a sequence that reaches a
checkpoint the original does not reach next, or reaches one later than
the original did, is a :class:`ReplayMismatch`.
"""
from .state import NativeGap


class ReplayMismatch(NativeGap):
    """The native sequence and the original disagree on the route or the timing of a transition."""


class ReplayClock:
    """What ``state.replay`` provides: ``begin(kind)`` at a transition's start, ``checkpoint(pc)``, ``end()``."""

    def begin(self, kind):
        raise NotImplementedError

    def checkpoint(self, pc):
        raise NotImplementedError

    def end(self):
        raise NotImplementedError

    def sample_input(self):
        """The masks the game's two controller port reads see this frame (the tick wrap may fall between them);
        None means the frame's own recorded mask for both."""
        return None
