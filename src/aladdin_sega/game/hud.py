"""Score, lives and the HUD counters as the game keeps them.

All counters are ASCII digits in work RAM (docs/semantic-map.md section 3):
score FF7E2A..FF7E2E, lives FF7E3C, apples FFEFE0..E1, gems FFEFE2..E3.
Points are accumulated in FFF14E as *tally units* of ten points and moved
into the digits by ``score_tally`` (1B00CA), which also counts progress
toward the next extra life in FFEFEA.
"""
SCORE_DIGITS = 0xFF7E2A         # five ASCII digits, most significant first
SCORE_LAST_DIGIT = 0xFF7E2E
LIVES = 0xFF7E3C                # one ASCII digit
APPLES = 0xFFEFE0               # two ASCII digits
GEMS = 0xFFEFE2                 # two ASCII digits
PENDING_POINTS = 0xFFF14E       # tally units (10 points each) not yet shown
EXTRA_LIFE_PROGRESS = 0xFFEFEA  # tally units since the last extra life
DIFFICULTY = 0xFF7E21           # 0 easy, 1 normal, else hard
FRAME_COUNTER = 0xFF7E28
SOUND_ENABLED = 0xFFF57D
EXTRA_LIFE_SOUND = 0x66

EXTRA_LIFE_THRESHOLDS = {0: 0x1388, 1: 0x1D4C}   # 5,000 and 7,500 points; harder: 10,000
POINT_ADDERS = {0x1B0138: 1, 0x1B0142: 5, 0x1B014C: 10, 0x1B0156: 15, 0x1B0160: 20, 0x1B016A: 25,
                0x1B0174: 50, 0x1B017E: 75, 0x1B0188: 100, 0x1B0192: 1000}   # ROM helpers -> tally units


def score_value(read) -> int:
    return int(''.join(chr(read(SCORE_DIGITS + i, 1)) for i in range(5)))


def add_points(read, write, tally_units: int) -> None:
    """The ``addi.w #n,FFF14E`` helpers (1B0138..1B0192): queue points for the tally."""
    write(PENDING_POINTS, (read(PENDING_POINTS, 2) + tally_units) & 0xFFFF, 2)


def extra_life(read, write, sound) -> None:
    """1AEF70: one more life, capped at nine, with its jingle."""
    lives = read(LIVES, 1) + 1
    if lives < 0x3A:
        write(LIVES, lives, 1)
    if read(SOUND_ENABLED, 1):
        sound(EXTRA_LIFE_SOUND)


def score_tally(read, write, sound) -> None:
    """1B00CA: on even frames move one tally unit into the score and the extra-life progress."""
    if read(FRAME_COUNTER, 1) & 1:
        return
    pending = read(PENDING_POINTS, 2)
    if not pending:
        return
    write(PENDING_POINTS, pending - 1, 2)
    progress = (read(EXTRA_LIFE_PROGRESS, 2) + 1) & 0xFFFF
    write(EXTRA_LIFE_PROGRESS, progress, 2)
    threshold = EXTRA_LIFE_THRESHOLDS.get(read(DIFFICULTY, 1), 0x2710)
    if progress >= threshold:
        extra_life(read, write, sound)
        write(EXTRA_LIFE_PROGRESS, 0, 2)
    digit = SCORE_LAST_DIGIT - 1                      # the tens digit
    while read(digit, 1) == 0x39:
        write(digit, 0x30, 1)
        digit -= 1
    write(digit, read(digit, 1) + 1, 1)
