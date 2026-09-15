"""The player: fields and the per-frame steps recovered so far.

The player is object slot 0 (``FF7E40``); its world position is the
camera position plus its screen offset, published every frame to the
globals the collision callbacks read (1A8E0C).  Control, physics and the
state machine (1A9D98, 1A9B90, 1A986E, 1A99F0, 1A9716, 1A9304, 1A9502,
1AA8FA) are the next steps to recover here; their fields are named in
docs/semantic-map.md section 2.
"""
CAMERA_X, CAMERA_Y = 0xFF7DF6, 0xFF7DF8
SCREEN_X, SCREEN_Y = 0xFF7DFA, 0xFF7DFC      # player offset from the camera (Y carries the 192 plane bias)
WORLD_X, WORLD_Y = 0xFF7E02, 0xFF7E04        # published copies
RECORD_X, RECORD_Y = 0xFF7E42, 0xFF7E44      # the player record's own +02 / +04
FRAME_COUNTER = 0xFF7E28


def publish_position(read, write) -> None:
    """1A8E0C: world = camera + screen offset, into the globals and the player record."""
    x = (read(CAMERA_X, 2) + read(SCREEN_X, 2)) & 0xFFFF
    y = (read(CAMERA_Y, 2) + read(SCREEN_Y, 2)) & 0xFFFF
    write(WORLD_X, x, 2); write(RECORD_X, x, 2)
    write(WORLD_Y, y, 2); write(RECORD_Y, y, 2)


def advance_frame_counter(read, write) -> None:
    """1A8C16: the loop's own frame counter (bit 0 gates the animation and score passes)."""
    write(FRAME_COUNTER, (read(FRAME_COUNTER, 1) + 1) & 0xFF, 1)
