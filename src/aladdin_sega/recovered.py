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
