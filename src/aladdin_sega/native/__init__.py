"""The standalone runtime: the same recovered components, no original CPU execution.

Three roles share the recovered code:

* the original (oracle) machine, untouched, used as the reference;
* the verification path, which runs a recovered component over a copy of
  the original's state at that component's boundary and compares;
* this native runtime, which owns execution of a frame and stops with a
  :class:`NativeGap` at the first step that is not recovered yet.  It never
  runs original code to get past a gap.
"""
from .state import GameState, NativeGap
from .frame import STEPS, run_frame, Step

__all__ = ['GameState', 'NativeGap', 'STEPS', 'Step', 'run_frame']
