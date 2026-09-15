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

Natively they become events; the original's only work-RAM side effects
are the last DMA destination word (FF8880) and the stream offset.
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


def flush_upload_queue(read, write, emit) -> None:
    """1AC726: every queued sprite-piece upload goes to the VDP."""
    count = read(UPLOAD_COUNT, 2)
    for i in range(count):
        entry = bytes(read(UPLOAD_QUEUE + UPLOAD_ENTRY * i + j, 1) for j in range(UPLOAD_ENTRY))
        emit('vram_upload', entry)
        write(LAST_DMA_DESTINATION, int.from_bytes(entry[12:14], 'big'), 2)


def upload_sprite_table(read, emit) -> None:
    """1AB776: the sprite attribute table built this frame goes to VRAM."""
    count = read(SPRITE_TABLE_COUNT, 2)
    if count and count < 0x80:
        emit('sprite_table', bytes(read(SPRITE_TABLE + i, 1) for i in range(8 * count)))


def stream_tiles(read, write, rom, emit) -> None:
    """1AE0F6: advance the per-frame tile stream by one 14-byte DMA command."""
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
    write(LAST_DMA_DESTINATION, int.from_bytes(entry[0:4], 'big') >> 16, 2)
    write(LAST_DMA_DESTINATION + 2, int.from_bytes(entry[0:4], 'big') & 0xFFFF, 2)
    emit('vram_stream', bytes(entry))
