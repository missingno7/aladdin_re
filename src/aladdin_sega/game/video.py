"""Platform-facing video uploads as the game queues them.

Three main-loop steps move bytes to the VDP and nothing else:

* 1AC726 flushes the frame-upload queue at FF769A that the script engine's
  frame-change hook (1AC6D0) filled: one 14-byte DMA command per sprite
  piece (five VDP register words and the destination command), counted in
  FFEFEE and cleared by the animation pass;
* 1AB776 copies the sprite attribute table the sprite builder wrote at
  FF729A (FFEFEC entries of 8 bytes) into VRAM;
* 1AE0F6 streams one 14-byte DMA command per frame from the list at
  FFF140 (offset FFF14C, length FFF148) -- animated tiles, not sound.

Natively they drive the VDP model through the same port words the original
writes; the only work-RAM side effects are the last DMA destination word
(FF8880) and the stream offset.  1B2650 / 1B2664 / 1B2678 load one 16-colour
palette line from ROM and remember its source.
"""
UPLOAD_QUEUE = 0xFF769A
UPLOAD_COUNT = 0xFFEFEE          # word; the low byte FFEFEF is what 1AC6D0 increments
UPLOAD_ENTRY = 14
SPRITE_TABLE = 0xFF729A
SPRITE_TABLE_COUNT = 0xFFEFEC     # word, entries of 8 bytes
STREAM_POINTER = 0xFFF140        # long: DMA command list in ROM
STREAM_LENGTH = 0xFFF148         # word
STREAM_OFFSET = 0xFFF14C         # word
LAST_DMA_DESTINATION = 0xFF8880  # bookkeeping written by every flush
GAME_MODE = 0xFFF57C             # 1 attract demo, 2 (no streaming), otherwise play
SPRITE_TABLE_COMMAND = 0x1CB2    # ROM long: the VRAM write command for the sprite attribute table
DMA_ENABLED, DMA_DISABLED = 0x8174, 0x8164   # register 1 with and without M1
PALETTE_SOURCES = (0xFF7262, 0xFF7266, 0xFF726A, 0xFF726E)          # 1B2678 / 1B2664 / 1B2650 / 1B263C remember their source
PALETTE_COMMANDS = (0xC0000000, 0xC0200000, 0xC0400000, 0xC0600000)  # CRAM lines 0..3


def vram_write_command(address) -> int:
    """The control long for a VRAM write at ``address`` (1B2534 / 1B255C / 1B3416 compute it the same way)."""
    return (((address & 0x3FFF) | 0x4000) << 16) | ((address >> 14) & 3)


def flush_upload_queue(read, write, vdp) -> None:
    """1AC726: every queued sprite-piece upload is sent as a DMA command (6 words, then the last one via FF8880)."""
    count = read(UPLOAD_COUNT, 2)
    if not count:
        return
    vdp.control(DMA_ENABLED)
    for i in range(count):
        entry = UPLOAD_QUEUE + UPLOAD_ENTRY * i
        for j in range(0, 12, 2):
            vdp.control(read(entry + j, 2))
        last = read(entry + 12, 2)
        write(LAST_DMA_DESTINATION, last, 2)
        vdp.control(last)
    vdp.control(DMA_DISABLED)


def upload_sprite_table(read, rom, vdp) -> None:
    """1AB776: the sprite attribute table built this frame goes to VRAM (count + 1 entries of 8 bytes)."""
    vdp.control_long(int.from_bytes(rom[SPRITE_TABLE_COMMAND:SPRITE_TABLE_COMMAND + 4], 'big'))
    count = read(SPRITE_TABLE_COUNT, 2)
    if not count or (count & 0xFF) >= 0x80:
        return
    for i in range(count + 1):
        vdp.data_long(read(SPRITE_TABLE + 8 * i, 4))
        vdp.data_long(read(SPRITE_TABLE + 8 * i + 4, 4))


def stream_tiles(read, write, rom, vdp) -> None:
    """1AE0F6: advance the per-frame tile stream by one 14-byte DMA command (command long first, then 5 registers)."""
    if read(GAME_MODE, 1) == 2:
        return
    pointer = read(STREAM_POINTER, 4)
    if not pointer:
        return
    offset = read(STREAM_OFFSET, 2) + UPLOAD_ENTRY
    if offset >= read(STREAM_LENGTH, 2):
        offset = 0
    write(STREAM_OFFSET, offset, 2)
    entry = rom[pointer + offset:pointer + offset + UPLOAD_ENTRY]
    command = int.from_bytes(entry[0:4], 'big')
    vdp.control(DMA_ENABLED)
    write(LAST_DMA_DESTINATION, command, 4)
    for j in range(4, 14, 2):
        vdp.control(int.from_bytes(entry[j:j + 2], 'big'))
    vdp.control_long(command)
    vdp.control(DMA_DISABLED)


def flash_white(vdp) -> None:
    """1B26D0: every CRAM entry becomes white (the sword clash flash)."""
    vdp.control_long(PALETTE_COMMANDS[0])
    for _ in range(64):
        vdp.data(0xEEE)


def restore_palettes(read, write, rom, vdp) -> None:
    """1ACDA2: the four remembered palette lines are loaded again."""
    for index, source in enumerate(PALETTE_SOURCES):
        load_palette(write, rom, vdp, index, read(source, 4))


def load_palette(write, rom, vdp, index, source) -> None:
    """1B2678 (line 0) / 1B2664 (1) / 1B2650 (2) / 1B263C (3): one 16-colour line from ROM into CRAM."""
    write(PALETTE_SOURCES[index], source, 4)
    vdp.control_long(PALETTE_COMMANDS[index])
    for i in range(16):
        vdp.data(int.from_bytes(rom[source + 2 * i:source + 2 * i + 2], 'big'))
