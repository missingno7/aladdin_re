"""Score, lives and the HUD counters as the game keeps them.

All counters are ASCII digits in work RAM (docs/aladdin/semantic-map.md section 3):
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
    if not read(PENDING_POINTS, 2):
        return
    score_tally_unit(read, write, sound)


def score_tally_unit(read, write, sound=lambda sound_id: None) -> None:
    """1B00D6: one pending unit into the score digits and the extra-life progress."""
    write(PENDING_POINTS, read(PENDING_POINTS, 2) - 1, 2)
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


def _add_two_digits(read, write, address) -> None:
    """1B0336 / 1B0394: a two-digit ASCII counter goes up, capped at 99."""
    if read(address, 2) == 0x3939:
        return
    ones = read(address + 1, 1) + 1
    write(address + 1, ones, 1)
    if ones >= 0x3A:
        write(address, read(address, 1) + 1, 1)
        write(address + 1, 0x30, 1)


def _remove_two_digits(read, write, address) -> None:
    """1B0360 / 1B03BE: a two-digit ASCII counter goes down, floored at 00."""
    if read(address, 2) == 0x3030:
        return
    ones = (read(address + 1, 1) - 1) & 0xFF
    write(address + 1, ones, 1)
    if ones >= 0x30:
        return
    write(address + 1, 0x39, 1)
    if read(address, 1) != 0x30:
        write(address, read(address, 1) - 1, 1)


def add_apple(read, write): _add_two_digits(read, write, APPLES)
def remove_apple(read, write): _remove_two_digits(read, write, APPLES)
def add_gem(read, write): _add_two_digits(read, write, GEMS)
def remove_gem(read, write): _remove_two_digits(read, write, GEMS)


HEALTH, SHOWN_HEALTH = 0xFFEFFA, 0xFFF0EC
TOKEN_DIGITS = 0xFF7E38            # three ASCII digits (TENTATIVE: the level's collected tokens)
TOKENS_PENDING = 0xFFF159          # units still to be counted into the digits
TOKEN_GOAL_A, TOKEN_GOAL_B = 0xFF7E16, 0xFF7E12   # longs: the digit strings that trigger a reward (per difficulty)
TOKEN_REWARD_FLAG = 0xFFF0F9
LEVEL_INDEX = 0xFF7E26
BONUS_STAGE_FLAG = 0xFFF0F7
TRANSITION_COUNTDOWN = 0xFFF0E9
MESSAGE = 0xFFF15A
PAUSED = 0xFFF158
TOKEN_SOUND = 0x02
LEVEL_INDEX_BONUS = 0x14


def health_display(read, write) -> None:
    """1B02EC: on even frames the shown health eases one step toward the real one."""
    if read(FRAME_COUNTER, 1) & 1:
        return
    shown, health = read(SHOWN_HEALTH, 1), read(HEALTH, 1)
    if shown == health:
        return
    write(SHOWN_HEALTH, shown - 1 if shown > health else shown + 1, 1)


def token_counter(read, write, sound, message) -> None:
    """1B01AC: on even frames count one pending token into the digits; goals trigger a message and points."""
    if read(FRAME_COUNTER, 1) & 1 or not read(TOKENS_PENDING, 1):
        return
    write(TOKENS_PENDING, read(TOKENS_PENDING, 1) - 1, 1)
    digit = TOKEN_DIGITS + 2
    while read(digit, 1) == 0x39:
        write(digit, 0x30, 1)
        digit -= 1
    write(digit, read(digit, 1) + 1, 1)
    if read(LEVEL_INDEX, 1) < LEVEL_INDEX_BONUS:
        digits = read(TOKEN_DIGITS, 4)
        for goal, code in ((TOKEN_GOAL_A, 0x1C), (TOKEN_GOAL_B, 0x1B)):
            if digits == read(goal, 4):
                write(PAUSED, 0xFF, 1)
                write(MESSAGE, code, 1)
                message(code)
                write(PAUSED, 0, 1)
                if read(SOUND_ENABLED, 1):
                    sound(TOKEN_SOUND)
                return
    if read(TOKEN_DIGITS, 4) != 0x30313000:
        return
    write(TOKEN_REWARD_FLAG, 0xFF, 1)
    add_points(read, write, POINT_ADDERS[0x1B0192])
    if read(LEVEL_INDEX, 1) >= LEVEL_INDEX_BONUS and read(BONUS_STAGE_FLAG, 1):
        write(TRANSITION_COUNTDOWN, 0xB4, 1)
