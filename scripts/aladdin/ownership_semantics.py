"""Experimental object semantics; RAM stays authoritative and effects are staged.

No CPU context, timing, guest call frames, admission or replay policy. The caller
validates the non-aliasing RAM domain before these effects can be committed.
"""


def release_buffer(read, record):
    pointer = read(record + 42, 4)
    if not pointer:
        return []
    length = read(record + 41, 1) + 1
    return [(record + offset, 0) for offset in range(41, 50)] + [
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
