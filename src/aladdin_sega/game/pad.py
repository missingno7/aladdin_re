"""Controller input as the game sees it.

The main loop (1A8CEE..1A8E08) reads the three-button pad twice per
frame through port A10003 with TH high and TH low and stores the raw,
active-low bytes at FFF156 and FFF155.  Four decoders at 1B3212..1B3230
turn the direction bits into the flags FFF07C..FFF07F the player code
reads; the buttons themselves (B, C, A, Start) are tested straight from
the raw bytes by 1B3244 / 1B324E / 1B323A / 1B3208.
"""
RAW_TH_HIGH = 0xFFF156      # bit0 up, bit1 down, bit2 left, bit3 right, bit4 B, bit5 C (0 = pressed)
RAW_TH_LOW = 0xFFF155       # bit0 up, bit1 down, bit4 A, bit5 Start (0 = pressed); bits 2,3 read as 0
HELD_RIGHT, HELD_LEFT, HELD_UP, HELD_DOWN = 0xFFF07C, 0xFFF07D, 0xFFF07E, 0xFFF07F

# the recording's mask: bit0 up, 1 down, 2 left, 3 right, 4 B, 5 C, 6 A, 7 Start
def raw_bytes(mask: int) -> tuple[int, int]:
    """(FFF156, FFF155) for a recorded pad mask, exactly as the port reads deliver them."""
    th_high = 0x7F & ~(mask & 0x3F)
    th_low = 0x33 & ~((mask & 0x03) | ((mask >> 2) & 0x30))
    return th_high & 0xFF, th_low & 0xFF


GAME_MODE = 0xFFF57C            # 1 = attract demo (input comes from the ROM stream below)
DEMO_STREAM = 0xFFF576          # long: next byte of the attract demo's recorded pad bytes


def read_pad(read, write, mask: int) -> bool:
    """The main loop's two port reads (1A8CEE).  In attract mode the pad only starts the game.

    Returns True when the attract demo should end because a button was
    pressed (B and C, or A and Start, on the recorded mask).
    """
    if read(GAME_MODE, 1) == 1:
        return bool(mask & 0x30) or bool(mask & 0xC0)
    th_high, th_low = raw_bytes(mask)
    write(RAW_TH_HIGH, th_high, 1)
    write(RAW_TH_LOW, th_low, 1)
    return False


def attract_input(read, write, rom) -> bool:
    """1B315C: in attract mode feed the next recorded byte into FFF156; False when the stream ends."""
    if read(GAME_MODE, 1) != 1:
        return True
    pointer = read(DEMO_STREAM, 4)
    value = rom[pointer]
    if value == 0:
        return False
    write(RAW_TH_HIGH, value, 1)
    write(DEMO_STREAM, pointer + 1, 4)
    return True


def decode_directions(read, write) -> None:
    """1A8C44..1A8C86: ``seq.b`` of each direction decoder into its flag byte (FF = held)."""
    raw = read(RAW_TH_HIGH, 1)
    write(HELD_DOWN, 0xFF if not raw & 0x02 else 0, 1)
    write(HELD_UP, 0xFF if not raw & 0x01 else 0, 1)
    write(HELD_LEFT, 0xFF if not raw & 0x04 else 0, 1)
    write(HELD_RIGHT, 0xFF if not raw & 0x08 else 0, 1)


def button_b(read): return not read(RAW_TH_HIGH, 1) & 0x10       # 1B3244
def button_c(read): return not read(RAW_TH_HIGH, 1) & 0x20       # 1B324E
def button_a(read): return not read(RAW_TH_LOW, 1) & 0x10        # 1B323A
def button_start(read): return not read(RAW_TH_LOW, 1) & 0x20    # 1B3208
