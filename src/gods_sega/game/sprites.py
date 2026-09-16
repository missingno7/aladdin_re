"""The dynamic sprite emitter ``0018C8``: one sprite record into the frame's list, its tiles through a per-frame cache.

Called with a world position (``d0``/``d1``) and a sprite id (``d2``, bit 15
= horizontal flip) by the object drawers (``003324``, ``013F46``,
``010DE8``).  The routine subtracts the camera, rejects a sprite outside the
screen with a 32-pixel margin, looks the id up in the frame's tile cache
(nine word slots, the first eight scanned, an empty slot is negative), and
appends a four-word hardware sprite record to the sprite list.  A cache miss
also claims the next tiles of the dynamic VRAM area and uploads the tile
data from ROM: that upload is the platform operation the boundary hands to
the machine (``boundary.sprite_emit_plan``); everything here is RAM and ROM.

Pure functions of ``read(address, size)`` (work RAM and ROM); no cycles,
CCR, stack or registers.
"""
from __future__ import annotations

CAMERA_X, CAMERA_Y = 0xFFEA38, 0xFFEA3A            # the camera's world position (also game.camera)
DESCRIPTORS = 0x066794                              # ROM: sprite descriptors, one per id
DESCRIPTOR_OFFSETS = 0x0019D2                       # ROM: word offset of each id's descriptor
CACHE_IDS = 0xFFEE98                                # nine words: the doubled ids uploaded this frame, -1 when empty
CACHE_TILES = 0xFFEEAA                              # nine words: the VRAM tile index each cached id received
CACHE_SCANNED = 8                                   # the scan tests eight slots; the ninth is taken unchecked
LIST_HEAD = 0xFFEBF8                                # long: the next free sprite record
LIST_LAST = 0xFFEBFC                                # long: the record written last
LIST_COUNT = 0xFFEBF6                               # word: records so far, the link of the next record
TILE_CURSOR = 0xFFEE84                              # word: VRAM byte address of the next free dynamic tile
SCREEN_MARGIN, SCREEN_X_LIMIT, SCREEN_Y_LIMIT = 0x20, 0x160, 0xE0
FLIP_ID_BIT, FLIP_ATTRIBUTE, PRIORITY_ATTRIBUTE = 0x8000, 0x0800, 0x2000
RECORD_SIZE = 8
VDP_VRAM_WRITE = 0x40000000                         # the control-port command the upload starts with

# Descriptor fields (relative to the id's descriptor).
TILES_POINTER, TILE_BYTES, X_OFFSET, X_OFFSET_FLIPPED, Y_OFFSET, SIZE_ATTRIBUTE = 0, 4, 6, 8, 0xA, 0xC


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def emit_sprite(read, x, y, sprite):
    """What ``0018C8`` does for world position ``(x, y)`` and sprite id ``sprite``.

    Returns the arm (``'offscreen-x'``, ``'offscreen-y'``, ``'hit'``,
    ``'miss'``), the number of cache slots the scan tested, the slot a miss
    inserted into (``None`` for a hit or an off-screen sprite), the durable
    stores as ``{address: (value, size)}``, the record's address, whether
    the sprite is flipped, and for a miss the upload the machine performs:
    the VDP control command, the ROM source, the number of longwords and
    the byte count added to the tile cursor.
    """
    screen_x = (x - read(CAMERA_X, 2)) & 0xFFFF
    screen_y = (y - read(CAMERA_Y, 2)) & 0xFFFF
    result = {'scan': 0, 'inserted': None, 'stores': {}, 'record': None, 'flip': bool(sprite & FLIP_ID_BIT),
              'upload': None, 'screen': (screen_x, screen_y)}
    if ((screen_x + SCREEN_MARGIN) & 0xFFFF) > SCREEN_X_LIMIT:
        return {**result, 'arm': 'offscreen-x'}
    if ((screen_y + SCREEN_MARGIN) & 0xFFFF) > SCREEN_Y_LIMIT:
        return {**result, 'arm': 'offscreen-y'}
    key = (sprite * 2) & 0xFFFF                     # the doubled id; the flip bit falls off the word
    descriptor = (DESCRIPTORS + _signed_word(read(DESCRIPTOR_OFFSETS + _signed_word(key), 2))) & 0xFFFFFF
    arm, slot = 'miss', CACHE_SCANNED
    for index in range(CACHE_SCANNED):
        cached = read(CACHE_IDS + 2 * index, 2)
        result['scan'] = index + 1
        if cached & 0x8000:                          # an empty slot ends the scan: insert here
            slot = index
            break
        if cached == key:
            arm, slot = 'hit', index
            break
    stores = result['stores']
    if arm == 'miss':
        result['inserted'] = slot
        stores[CACHE_IDS + 2 * slot] = (key, 2)
    x_offset = read(descriptor + (X_OFFSET_FLIPPED if result['flip'] else X_OFFSET), 2)
    attribute = FLIP_ATTRIBUTE if result['flip'] else 0
    record_x = (screen_x + x_offset) & 0xFFFF
    record_y = (screen_y + read(descriptor + Y_OFFSET, 2)) & 0xFFFF
    head = read(LIST_HEAD, 4)                       # a full long: the game keeps its pointers sign-extended
    record = head & 0xFFFFFF
    count = read(LIST_COUNT, 2)
    if arm == 'hit':
        tile = read(CACHE_TILES + 2 * slot, 2)
    else:
        cursor = read(TILE_CURSOR, 2)
        tile = cursor >> 5
        stores[CACHE_TILES + 2 * slot] = (tile, 2)
        tile_bytes = read(descriptor + TILE_BYTES, 2)
        # The VRAM write command for the cursor: bits 13..0 in the high word, 15..14 in the low word.
        command = (VDP_VRAM_WRITE | ((cursor & 0x3FFF) << 16) | (cursor >> 14)) & 0xFFFFFFFF
        result['upload'] = {'command': command, 'source': read(descriptor + TILES_POINTER, 4) & 0xFFFFFF,
                            'longs': tile_bytes >> 2, 'bytes': tile_bytes, 'cursor': cursor}
    stores[LIST_LAST] = (head, 4)
    stores[record] = (record_y, 2)
    stores[record + 2] = (count | read(descriptor + SIZE_ATTRIBUTE, 2), 2)
    stores[record + 4] = (tile | attribute | PRIORITY_ATTRIBUTE, 2)
    stores[record + 6] = (record_x, 2)
    stores[LIST_HEAD] = ((head + RECORD_SIZE) & 0xFFFFFFFF, 4)
    stores[LIST_COUNT] = ((count + 1) & 0xFFFF, 2)
    return {**result, 'arm': arm, 'record': record, 'descriptor': descriptor, 'count': count}


# --- 001164: the same emitter without a tile cache -------------------------
#
# Called by six sites (the particle drawer's siblings) with a world position
# and a sprite id, the same screen test and descriptor layout as
# ``emit_sprite`` (the flip bit, ``X_OFFSET``/``X_OFFSET_FLIPPED``,
# ``Y_OFFSET``, ``SIZE_ATTRIBUTE``), but the tile is a fixed word already
# resident in VRAM (descriptor + ``TILE_INDEX``): no per-frame cache, no
# upload, hence no platform operation -- and a guard the dynamic emitter does
# not have, the sprite list's capacity (``LIST_FULL``).  The id-to-descriptor
# offset table is this routine's own (``STATIC_DESCRIPTOR_OFFSETS``), not the
# dynamic emitter's (``DESCRIPTOR_OFFSETS``).

STATIC_DESCRIPTOR_OFFSETS = 0x0011E6                # ROM: word offset of each id's descriptor, this routine's own table
TILE_INDEX = 0x000E                                 # descriptor field: the fixed VRAM tile index (no cache, no upload)
LIST_FULL = 0xFFFFEE30                              # LIST_HEAD (sign-extended) at or beyond this: the list is full


def emit_static_sprite(read, x, y, sprite):
    """What ``001164`` does for world position ``(x, y)`` and sprite id ``sprite``.

    Returns the arm (``'offscreen-x'``, ``'offscreen-y'``, ``'full'``,
    ``'placed'``), whether the sprite is flipped, and for ``'placed'`` the
    durable stores, the record's address, the descriptor used and the
    sprite count before the append.
    """
    screen_x = (x - read(CAMERA_X, 2)) & 0xFFFF
    screen_y = (y - read(CAMERA_Y, 2)) & 0xFFFF
    flip = bool(sprite & FLIP_ID_BIT)
    result = {'flip': flip, 'stores': {}, 'record': None, 'descriptor': None, 'screen': (screen_x, screen_y)}
    if ((screen_x + SCREEN_MARGIN) & 0xFFFF) > SCREEN_X_LIMIT:
        return {**result, 'arm': 'offscreen-x'}
    if ((screen_y + SCREEN_MARGIN) & 0xFFFF) > SCREEN_Y_LIMIT:
        return {**result, 'arm': 'offscreen-y'}
    key = (sprite * 2) & 0xFFFF
    descriptor = (DESCRIPTORS + _signed_word(read(STATIC_DESCRIPTOR_OFFSETS + _signed_word(key), 2))) & 0xFFFFFF
    result['descriptor'] = descriptor
    head = read(LIST_HEAD, 4)
    if head >= LIST_FULL:
        return {**result, 'arm': 'full'}
    x_offset = read(descriptor + (X_OFFSET_FLIPPED if flip else X_OFFSET), 2)
    attribute = FLIP_ATTRIBUTE if flip else 0
    record_x = (screen_x + x_offset) & 0xFFFF
    record_y = (screen_y + read(descriptor + Y_OFFSET, 2)) & 0xFFFF
    record = head & 0xFFFFFF
    count = read(LIST_COUNT, 2)
    tile = read(descriptor + TILE_INDEX, 2)
    stores = result['stores']
    stores[LIST_LAST] = (head, 4)
    stores[record] = (record_y, 2)
    stores[record + 2] = (count | read(descriptor + SIZE_ATTRIBUTE, 2), 2)
    stores[record + 4] = (tile | attribute | PRIORITY_ATTRIBUTE, 2)
    stores[record + 6] = (record_x, 2)
    stores[LIST_HEAD] = ((head + RECORD_SIZE) & 0xFFFFFFFF, 4)
    stores[LIST_COUNT] = ((count + 1) & 0xFFFF, 2)
    return {**result, 'arm': 'placed', 'record': record, 'count': count}


# --- 00126A: the particle drawer's own emitter ------------------------------
#
# Called from the particle drawer's jump table (010248) with a world
# position and a descriptor byte *offset* (not an id: the caller already
# knows it, so there is no id-to-offset table here, unlike the dynamic and
# static emitters).  No per-frame cache at all -- every on-screen call
# uploads its tile fresh, the same VDP command arithmetic and record
# layout as ``emit_sprite``'s own cache-miss upload, but its own fixed
# attribute word (``PARTICLE_PRIORITY_ATTRIBUTE``) instead of
# ``PRIORITY_ATTRIBUTE``.  Always a seam when on-screen (there is nothing
# else to be but a miss); ``boundary.particle_emit_plan`` hands the whole
# control-write-then-data-loop span to the machine, exactly as
# ``sprite_emit_plan`` does for ``0018C8``'s own upload.

PARTICLE_PRIORITY_ATTRIBUTE = 0x4000                # this routine's own fixed attribute bit (0018C8's own is 0x2000)


def emit_particle_sprite(read, x, y, offset):
    """What ``00126A`` does for world position ``(x, y)`` and descriptor byte offset ``offset`` (D2).

    Returns the arm (``'offscreen-x'``, ``'offscreen-y'``, ``'upload'``),
    whether the sprite is flipped, the durable stores, the record's
    address, and (for ``'upload'``) the VDP command and the ROM source the
    machine will copy from -- ``boundary`` cedes the copy itself to the
    real machine, so the byte count is not needed here.
    """
    screen_x = (x - read(CAMERA_X, 2)) & 0xFFFF
    screen_y = (y - read(CAMERA_Y, 2)) & 0xFFFF
    flip = bool(offset & FLIP_ID_BIT)
    result = {'flip': flip, 'stores': {}, 'record': None, 'screen': (screen_x, screen_y)}
    if ((screen_x + SCREEN_MARGIN) & 0xFFFF) > SCREEN_X_LIMIT:
        return {**result, 'arm': 'offscreen-x'}
    if ((screen_y + SCREEN_MARGIN) & 0xFFFF) > SCREEN_Y_LIMIT:
        return {**result, 'arm': 'offscreen-y'}
    descriptor = (DESCRIPTORS + (offset & 0x7FFF)) & 0xFFFFFF
    x_offset = read(descriptor + (X_OFFSET_FLIPPED if flip else X_OFFSET), 2)
    attribute = (FLIP_ATTRIBUTE if flip else 0) | PARTICLE_PRIORITY_ATTRIBUTE
    record_x = (screen_x + x_offset) & 0xFFFF
    record_y = (screen_y + read(descriptor + Y_OFFSET, 2)) & 0xFFFF
    head = read(LIST_HEAD, 4)
    record = head & 0xFFFFFF
    count = read(LIST_COUNT, 2)
    cursor = read(TILE_CURSOR, 2)
    tile = cursor >> 5
    stores = result['stores']
    stores[LIST_LAST] = (head, 4)
    stores[record] = (record_y, 2)
    stores[record + 2] = (count | read(descriptor + SIZE_ATTRIBUTE, 2), 2)
    stores[record + 4] = (tile | attribute, 2)
    stores[record + 6] = (record_x, 2)
    stores[LIST_HEAD] = ((head + RECORD_SIZE) & 0xFFFFFFFF, 4)
    stores[LIST_COUNT] = ((count + 1) & 0xFFFF, 2)
    command = (VDP_VRAM_WRITE | ((cursor & 0x3FFF) << 16) | (cursor >> 14)) & 0xFFFFFFFF
    return {**result, 'arm': 'upload', 'record': record, 'descriptor': descriptor, 'count': count,
            'upload': {'command': command, 'source': read(descriptor + TILES_POINTER, 4) & 0xFFFFFF}}
