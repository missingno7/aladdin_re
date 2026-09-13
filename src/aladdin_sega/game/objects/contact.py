"""Pure live-RAM effects for the bounded 1AE4F8 contact reaction block."""


_EARLY = (0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2)
_RESET_GATES = (0xFFF0BE, 0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4)


def contact_path(read):
    """Classify the concrete 1AE4F8 state gate without retaining state."""
    for address in _EARLY:
        if read(address, 1):
            return 'early', address
    if any(read(address, 1) for address in _RESET_GATES) or not read(0xFFF0C1, 1):
        return ('reaction' if read(0xFFF173, 1) else 'reset'), None
    if read(0xFFF173, 1):
        return 'reaction', None
    if read(0xFFF0CC, 1) or read(0xFFEFFF, 1) or read(0xFFF11F, 1):
        return 'reset', None
    return 'pointer_reset', None


def contact_decay(read):
    """One exact 1B03F2 pass; repeat callers may invoke it up to three times."""
    if read(0xFFF0E9, 1) or read(0xFFF0E6, 1) or read(0xFF7E20, 1):
        return []
    if read(0xFFEFFA, 1):
        if read(0xFFF0F2, 1):
            return []
        return [(0xFFEFFA, (read(0xFFEFFA, 1) - 1) & 0xff), (0xFFF0F2, 0x28)]
    return [(0xFFF0E6, 10)]


def contact_reset(read, *, pointer_reset=False, decay=True):
    """Return the reset-side RAM writes before optional synchronous sound."""
    writes = []
    if pointer_reset:
        writes.extend(((0xFF7E60, 0x00), (0xFF7E61, 0x12),
                       (0xFF7E62, 0x26), (0xFF7E63, 0xCE), (0xFF7E77, 0)))
    writes.extend(((0xFFF0B0, 0), (0xFFF0B1, 0), (0xFFF0CC, 0)))
    if decay:
        for _ in range(1 + min(read(0xFF7E21, 1), 2)):
            writes.extend(contact_decay(lambda address, size: _overlay(read, writes, address, size)))
    return writes


def contact_reaction(read):
    """The FFF173 arm of 1AE5EA, including its FFF0D8-dependent final flag."""
    writes = [(0xFF7E60, 0x00), (0xFF7E61, 0x12), (0xFF7E62, 0x26), (0xFF7E63, 0xB2),
              (0xFF7E77, 0), (0xFFF0E7, 0xff), (0xFFF0E9, 0x32)]
    if not read(0xFFF0D8, 1):
        writes.append((0xFFEFFF, 1))
    return writes


def _overlay(read, writes, address, size):
    values = {at: value for at, value in writes}
    if size == 1:
        return values.get(address, read(address, size))
    return int.from_bytes(bytes(values.get(address + i, (read(address + i, 1))) for i in range(size)), 'big')
