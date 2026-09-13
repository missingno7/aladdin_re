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
