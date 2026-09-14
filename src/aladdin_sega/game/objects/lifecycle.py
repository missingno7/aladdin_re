"""Pure object lifecycle effects over a caller-supplied RAM reader.

The functions return staged byte writes. They do not import machine state,
timing, admission, snapshots, sound or replay policy.
"""


def release_buffer(read, record):
    pointer = read(record + 42, 4)
    if not pointer:
        return []
    length = read(record + 41, 1) + 1
    return [(record + offset, 0) for offset in range(42, 50)] + [(record + 41, 0)] + [
        (pointer + offset, 0) for offset in range(length)]


def clear_pair(read, record):
    writes = [(record, 0), *release_buffer(read, record)]
    linked = read(record + 62, 4)
    if linked:
        writes.extend(((linked, 0), *release_buffer(read, linked)))
    return writes


def initialize(record, template):
    """Expand the same 19-byte object template into the same selected fields."""
    fields = (0, 1, 6, 7, 8, 9, 10, 11, 12, 13,
              30, 31, 32, 33, 34, 35, 41, 53, 60)
    cleared = (19, *range(20, 30), *range(42, 53), 54, 55, 61, *range(62, 66))
    return [(record + offset, value) for offset, value in zip(fields, template)] + [
        (record + offset, 0) for offset in cleared]


def unlink(read, linked):
    """Detach the linked object's back pointer and linked-state flag."""
    if not linked:
        return []
    return [(linked + offset, 0) for offset in range(62, 66)] + [
        (linked + 60, read(linked + 60, 1) & ~0x04)]


def retire_collected_object(read, record, template, amount=0):
    """Accumulate the collection value, release its pair and install the retirement template."""
    total = (read(0xFFF14E, 2) + amount) & 0xFFFF if amount else None
    return [*([(0xFFF14E, total >> 8), (0xFFF14F, total & 255)] if amount else []),
            *clear_pair(read, record), *initialize(record, template)]


def free_object(read, start, count, stride=66, *, occupied=None):
    """Find the first inactive record in the specified original object pool."""
    for index in range(count):
        if start + index * stride != occupied and read(start + index * stride, 1) == 0:
            return start + index * stride, index
    return None, count


def free_object_reverse(read, start, count, stride=66, *, occupied=None):
    """Find the first inactive record while walking an original pool downwards.

    ``1AE292`` starts at the high address and tests exactly ``count`` record
    type bytes before its DBRA exhaustion result.  ``occupied`` is retained
    for callers whose source record lives in the same pool after they have
    made that source active.
    """
    for index in range(count):
        address = start - index * stride
        if address != occupied and read(address, 1) == 0:
            return address, index
    return None, count


def relocate_object(read, record, destination):
    """Move a 66-byte object to the secondary pool, installing its new script."""
    data = [read(record + offset, 1) for offset in range(66)]
    data[0], data[55] = 0x82, 0
    data[32:36] = bytes.fromhex('00125710')
    return [(record, 0), *[(record + 32 + i, b) for i, b in enumerate(data[32:36])],
            (record + 55, 0), *[(destination + i, b) for i, b in enumerate(data)]]


def activate_collection(record):
    """Install the collected object's active script and reset its script cursors."""
    return [(record, 0x84), (record + 6, 1), (record + 55, 0), (record + 54, 0),
            *[(record + 32 + i, b) for i, b in enumerate(bytes.fromhex('00121c30'))],
            *[(record + 10 + i, b) for i, b in enumerate(bytes.fromhex('001215e0'))]]


def spawn_collection(read, record, destination, template):
    """Initialize a companion at the collected object's current position."""
    return [*initialize(destination, template),
            *[(destination + offset, read(record + offset, 1)) for offset in range(2, 6)]]


def spawn_region(destination, template, d2, d3, x, y, clear_address):
    """Install one allocator-selected object and its caller-supplied placement.

    This is the pure residue of the common ``1B526C`` tail.  Selection,
    template source ownership, and the indexed clear's alias domain remain at
    the machine boundary.
    """
    return [*initialize(destination, template),
            *((destination + 0x32 + offset, (d2 >> (8 * (1 - offset))) & 0xff)
              for offset in range(2)),
            (destination + 0x34, d3 & 0xff),
            *((destination + 2 + offset, (x >> (8 * (1 - offset))) & 0xff)
              for offset in range(2)),
            *((destination + 4 + offset, (y >> (8 * (1 - offset))) & 0xff)
              for offset in range(2)),
            (clear_address, 0)]

def finish_reverse_spawn(read, record):
    """Apply 1B680C's successful reverse-pool position correction."""
    x = (read(record + 2, 2) + 8) & 0xFFFF
    y = (read(record + 4, 2) - 1) & 0xFFFF
    return [*((record + 2 + offset, (x >> (8 * (1 - offset))) & 0xff)
              for offset in range(2)),
            *((record + 4 + offset, (y >> (8 * (1 - offset))) & 0xff)
              for offset in range(2))]


def finish_upper_spawn(record):
    """Apply 1B7376's type, script, and mode residue to an upper-pool slot."""
    return [(record, 0x40), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('00122c12'))),
            (record + 0x29, 0)]


def finish_upper_variant_spawn(record):
    """Apply 1B727A's type, script, and enabled-flag residue to an upper slot."""
    return [(record, 0x3A), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('00122bd8'))),
            (record + 0x29, 1)]


def finish_upper_scripted_spawn(record):
    """Apply ``1B72D4``'s upper-pool type, scripts, and mode flag."""
    return [(record, 0x34), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('00122c1e'))),
            *((record + 0x0a + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('001217b4'))),
            (record + 0x29, 6)]


def finish_upper_typed_spawn(record, script=0x0012337a, object_type=0x20):
    """Apply an upper typed caller's successful type and script fields."""
    return [*((record + 0x0a + offset, 0) for offset in range(4)),
            *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(script.to_bytes(4, 'big'))),
            (record, object_type)]


def reset_lower_spawn_flag():
    """Clear FFF104 before allocation, even when the lower pool is full.

    The flag's wider gameplay meaning is not yet established.
    """
    return [(0xFFF104, 0)]


def finish_lower_scripted_spawn(record):
    """Install the 1B6F1E callback's successful object script."""
    return [(record + 0x20 + offset, byte)
            for offset, byte in enumerate(bytes.fromhex('00125a4c'))]


def finish_type_8a_spawn(record):
    """Apply callback 1B723E's object type and script pointer."""
    return [(record, 0x8A), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('00124494')))]


def finish_type_41_spawn(record):
    """Apply callback 1B728E's object type, script pointer, and mode."""
    return [(record, 0x41), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('00125d7e'))), (record + 0x29, 2)]


def finish_type_84_spawn(record):
    """Apply callback 1B72AE's object type, auxiliary byte, script, and mode."""
    return [(record, 0x84), (record + 6, 0x21), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('00123e7a'))), (record + 0x29, 2)]


def finish_type_4c_spawn(record):
    """Apply callback 1B70D4's object type, script, cleared field, and mode."""
    return [(record, 0x4C), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('00123e36'))),
            *((record + 0x0A + offset, 0) for offset in range(4)), (record + 0x29, 1)]


def finish_guarded_lower_spawn(record):
    """Apply callback 1B71A0's successful object script pointer."""
    return [(record + 0x20 + offset, byte)
            for offset, byte in enumerate(bytes.fromhex('00124318'))]


def finish_lower_offset_spawn(record):
    """Apply callback 1B71C4's successful object script pointer (no guard prefix)."""
    return [(record + 0x20 + offset, byte)
            for offset, byte in enumerate(bytes.fromhex('00124332'))]


def finish_upper_tile_word_spawn(record):
    """Apply callback 1B6FAE's FF7E26==5 fixed word write at record+0x1E."""
    return [(record + 0x1E + offset, byte)
            for offset, byte in enumerate(bytes.fromhex('6000'))]


def finish_reverse_script_spawn(record):
    """Apply callback 1B6696's successful object script pointer (no retype)."""
    return [(record + 0x20 + offset, byte)
            for offset, byte in enumerate(bytes.fromhex('00125348'))]


def select_spawn_dispatch_slot(read, cursor, flag_base):
    """Read one dispatcher slot and its enable byte from the live tables.

    The walker keeps table layout, register effects and loop accounting at the
    machine boundary. This semantic fragment names the game-level selection
    that determines whether a slot dispatches a callback at all.
    """
    slot = read(cursor, 2)
    index = slot >> 1
    return index, read(flag_base + index, 1)


def offset_spawn_position(read, record, x_delta, y_delta):
    """Apply one allocator caller's observed signed position offsets."""
    x = (read(record + 2, 2) + x_delta) & 0xFFFF
    y = (read(record + 4, 2) + y_delta) & 0xFFFF
    return [*((record + 2 + index, (x >> (8 * (1 - index))) & 0xFF)
              for index in range(2)),
            *((record + 4 + index, (y >> (8 * (1 - index))) & 0xFF)
              for index in range(2))]


def prepare_spawn_strip(read, *, row, x_offset, y_offset):
    """Derive one observed spawn-strip setup's placement and table inputs."""
    position_source, varying_source = ((0xFF7E08, 0xFF7E06) if row else
                                       (0xFF7E06, 0xFF7E08))
    return {'x_offset': x_offset & 0xFFFF, 'y_offset': y_offset & 0xFFFF,
            'position': read(position_source, 2) & 0xFFF0,
            'varying': read(varying_source, 2) & 0xFFF0,
            'cursor': read(0xFF7DAC, 4),
            'stride': None if row else read(0xFF7DB4, 2)}


def finish_upper_dispatch_spawn(record):
    """Apply 1B745E's type, script, and enabled-flag residue."""
    return [(record, 0x44), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('00122c40'))),
            (record + 0x29, 1)]


def finish_primary_double_guard_spawn(record):
    """Apply 1B73A6's successful object type and script fields."""
    return [(record, 0x3C), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('0012437e'))),
            *((record + 0x0a + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('0012146c'))),
            (record + 0x29, 1)]


def finish_primary_inverse_guard_spawn(record):
    """Apply 1B73D6's successful object type and script fields."""
    return [(record, 0x3E), *((record + 0x20 + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('0012437e'))),
            *((record + 0x0a + offset, byte)
              for offset, byte in enumerate(bytes.fromhex('0012146c'))),
            (record + 0x29, 1)]


def finish_primary_mixed_guard_spawn(record):
    """Apply ``1B73F2``'s primary-pool success identity and scripts."""
    return [(record, 0x3f),
            *[(record + 0x20 + offset, value)
              for offset, value in enumerate(bytes.fromhex('0012437e'))],
            *[(record + 0x0a + offset, value)
              for offset, value in enumerate(bytes.fromhex('0012146c'))],
            (record + 0x29, 1)]
