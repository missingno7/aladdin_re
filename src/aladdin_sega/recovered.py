"""Editable Aladdin object semantics; RAM stays authoritative and effects are staged.

No CPU context, timing, guest call frames, admission or replay policy. The caller
validates the non-aliasing RAM domain before these effects can be committed.
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


def increment_counter(digits):
    """Advance two ASCII digits within the uncapped 00..98 domain."""
    tens, ones = digits >> 8, digits & 255
    if not (0x30 <= tens <= 0x39 and 0x30 <= ones <= 0x39) or digits == 0x3939:
        raise ValueError("decimal counter outside 00..98; capped branch remains original")
    return [(0xFFEFE0, tens + 1), (0xFFEFE1, 0x30)] if ones == 0x39 else [(0xFFEFE1, ones + 1)]


def unlink(read, linked):
    """Detach the linked object's back pointer and linked-state flag."""
    if not linked:
        return []
    return [(linked + offset, 0) for offset in range(62, 66)] + [
        (linked + 60, read(linked + 60, 1) & ~0x04)]


def collection_state(read, record, kind):
    """State changes made when a collection handler accepts an object.

    Names describe established effects, not guessed identities of collectibles.
    Sound and retirement are separate stages because original sound can observe
    the committed prefix. Values here are bytes in the one authoritative RAM.
    """
    if kind == 'flag25':
        return [(0xFFF176, 255)]
    if kind in ('flag128', 'flag129', 'flag116', 'flag12a'):
        return [({'flag128': 0xFFF128, 'flag129': 0xFFF129,
                  'flag116': 0xFFF116, 'flag12a': 0xFFF12A}[kind], 255)]
    if kind == 'count25':
        return [(0xFFF003, (read(0xFFF003, 1) + 1) & 255)]
    if kind == 'reset15':
        return [(0xFFF0A4, 0), (0xFFF0A5, 0)]
    if kind in ('flag177', 'flag178'):
        flag = 0xFFF177 if kind == 'flag177' else 0xFFF178
        return [(flag, 255), (record, 0x84),
                *[(record + 10 + i, b) for i, b in enumerate(bytes.fromhex('00121618'))],
                (record + 55, 0), (0xFF7DFE, 0), (0xFF7DFF, 0x70),
                (0xFF7E00, 1), (0xFF7E01, 0x90)]
    if kind == 'timer100':
        return [(0xFFF0E9, 0x20)]
    if kind == 'spawn':
        return [(0xFFF11C, 255)]
    if kind in ('primary', 'secondary'):
        shift = 2 if kind == 'secondary' else 0
        digits = read(0xFFEFE0 + shift, 2)
        if digits == 0x3939:
            flag = read(record + 52, 1)
            index = read(record + 50, 2)
            index = index - 65536 if index & 0x8000 else index
            return [(0xFFAE87 + index, flag)] if flag else []
        return [(address + shift, value) for address, value in increment_counter(digits)]
    if kind == 'quarter':
        count = (read(0xFFF10A, 1) + 1) & 255
        return [(0xFFF10A, count if count < 4 else 0),
                *(increment_counter(read(0xFFEFE0, 2)) if count >= 4 else [])]
    return []


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
            *[(record+32+i, b) for i,b in enumerate(bytes.fromhex('00121c30'))],
            *[(record+10+i, b) for i,b in enumerate(bytes.fromhex('001215e0'))]]


def spawn_collection(read, record, destination, template):
    """Initialize a companion at the collected object's current position."""
    return [*initialize(destination, template),
            *[(destination+offset, read(record+offset, 1)) for offset in range(2, 6)]]
