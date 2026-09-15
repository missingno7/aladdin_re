"""The pause check (1A91C6): Start toggles a pause loop that runs inside the main loop's frame.

When Start is pressed (and was released since the last pause), the
original enters a nested loop: it sends the pause command to the sound
driver, saves the 64 CRAM words to FF8800, loads the dimmed palette
(128ED2) twice, draws the pause overlay (1B0B8E) and then waits VBlank
after VBlank (1B249E / 1B0A46) reading the pad until Start is pressed and
released again, unless the death countdown (FFF0E9) ends it; it then
restores the four palette lines it remembers at FF7262..FF726E and sends
the resume command.  The natively recovered part is the decision; the
loop itself is reported as a gap until a replay actually pauses.
"""
from .pad import button_start

PAUSE_INHIBITED = 0xFF7E25     # TENTATIVE: set while pausing is not allowed
PAUSED = 0xFFF158              # FF while the pause loop runs
START_RELEASED = 0xFFF168      # FF once Start has been released since the last toggle


def pause_requested(read, write) -> bool:
    """1A91C6..1A91DA: True when the original would enter the pause loop this frame."""
    if read(PAUSE_INHIBITED, 1):
        return False
    if not button_start(read):
        write(START_RELEASED, 0, 1)
        return False
    return not read(START_RELEASED, 1)
