"""Pure live-RAM effects for the bounded 1AE4F8 contact reaction block."""


_EARLY = (0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2)
_RESET_GATES = (0xFFF0BE, 0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4)
_RESET_NAMES = ('be', 'd0', 'd7', 'cd', 'd4')


def contact_route(read):
    """Name the ordered original branch through 1AE4F8 without state."""
    for address in _EARLY:
        if read(address, 1):
            return 'early', address
    if read(0xFFF0BE, 1):
        return ('reaction' if read(0xFFF173, 1) else 'reset'), 'be'
    if not read(0xFFF0C1, 1):
        return ('reaction' if read(0xFFF173, 1) else 'reset'), 'c1zero'
    for name, address in zip(_RESET_NAMES[1:], _RESET_GATES[1:]):
        if read(address, 1):
            return ('reaction' if read(0xFFF173, 1) else 'reset'), name
    if read(0xFFF173, 1):
        return 'reaction', 'direct'
    if read(0xFFF0CC, 1) or read(0xFFEFFF, 1) or read(0xFFF11F, 1):
        return 'reset', 'cc' if read(0xFFF0CC, 1) else 'efff' if read(0xFFEFFF, 1) else 'f11f'
    return 'pointer_reset', 'pointer'


def contact_path(read):
    """Classify the concrete 1AE4F8 state gate without retaining state."""
    path, route = contact_route(read)
    return (path, route if path == 'early' else None)


def contact_sibling_route(read, record):
    """Classify 1AEC00 through its bounded counter-retirement arm."""
    if not read(0xFFF0D8, 1):
        return 'contact', None
    distance = read(0xFF7E02, 2)
    limit = read(record + 2, 2)
    if (read(0xFF7E49, 1) and distance < limit) or (not read(0xFF7E49, 1) and distance >= limit):
        return 'early', None
    if read(record + 1, 1):
        return 'decrement', None
    kind = read(record, 1)
    if kind == 0x13:
        return 'type13', kind
    if kind == 0x18:
        return 'retire18', kind
    if kind == 0x10:
        return 'retire10', kind
    if kind == 0x11:
        return 'retire11', kind
    return 'retire', kind


def contact_script_selector(read):
    """Classify 1AD150's flag-priority script-pointer selection.

    The selector itself has no external device calls.  It returns the selected
    immutable pointer when that pointer is fixed by the branch, or the table
    index for the one ROM-table arm.  The boundary owns the cartridge read and
    exact machine residue.
    """
    if read(0xFFF0D7, 1):
        return 'd7', 0x121964, None, False
    if read(0xFFF173, 1):
        if not read(0xFFF0C1, 1):
            return 'f173-c1zero', 0x121C28, None, False
        value = read(0xFFF0B0, 2)
        if value == 1:
            return 'f173-b0-1', 0x121FD4, None, False
        if value == 2:
            return 'f173-b0-2', 0x121FD4, None, False
        return 'f173-default', 0x121D5A, None, True
    if read(0xFFF115, 1):
        return 'f115', 0x125E72, None, False
    if read(0xFFF0CD, 1):
        d3 = read(0xFFF0D3, 1)
        if 0x50 <= d3 < 0x52:
            return 'cd-50-51', 0x121964, None, False
        if d3 == 0x60:
            return 'cd-60', 0x122336, None, False
    # 1AD1CE is reached after the optional CD arm, but is not part of it.
    if read(0xFFF0D3, 1) == 0x5E:
        return 'cd-5e', 0x122336, None, False
    if read(0xFFF0DB, 1):
        return 'db', 0x12181A, None, False
    if read(0xFFF0D0, 1):
        return 'd0-table', None, (read(0xFF7E04, 2) >> 2) & 0xF, False
    if read(0xFFF0D2, 1):
        return 'd2', 0x121C62, None, False
    if not read(0xFFF0C1, 1):
        return 'normal', 0x121AD8, None, False
    if read(0xFFF0DE, 1):
        return 'de', 0x12231E, None, False
    if read(0xFFF0DF, 1):
        return 'df', 0x122298, None, False
    if read(0xFFF0ED, 1):
        return 'ed', 0x121FA6, None, False
    value = read(0xFFF0B0, 2)
    if value in (1, 2):
        return f'b0-{value}', 0x122006, None, False
    return 'c1-default', 0x121D9A, None, False


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
        writes.extend(contact_repeated_decay(read, writes))
    return writes


def contact_repeated_decay(read, prior=()):
    """The one, two, or three 1B03F2 calls after a contact reset."""
    writes = list(prior)
    start = len(writes)
    for _ in range(1 + min(read(0xFF7E21, 1), 2)):
        writes.extend(contact_decay(lambda address, size: _overlay(read, writes, address, size)))
    return writes[start:]


def contact_reaction(read):
    """The FFF173 arm of 1AE5EA, including its FFF0D8-dependent final flag."""
    writes = [(0xFF7E60, 0x00), (0xFF7E61, 0x12), (0xFF7E62, 0x26), (0xFF7E63, 0xB2),
              (0xFF7E77, 0), (0xFFF0E7, 0xff), (0xFFF0E9, 0x32)]
    if not read(0xFFF0D8, 1):
        writes.append((0xFFEFFF, 1))
    return writes


def activate_contact(record, motion_delta, horizontal_impulse):
    """Publish the accepted contact activation's object and player-side state.

    Guard predicates and machine timing remain at the ROM boundary.  This body
    only names the durable player motion, script, object transition, and
    horizontal-impulse effects after that boundary accepts proximity.
    """
    return [
        (0xFF7DFC, (motion_delta >> 8) & 0xFF), (0xFF7DFD, motion_delta & 0xFF),
        (0xFF7E5A, 0xF8), (0xFF7E5B, 0),
        (0xFF7DFE, 0), (0xFF7DFF, 0xB0),
        (0xFF7E60, 0), (0xFF7E61, 0x12), (0xFF7E62, 0x1C), (0xFF7E63, 0x62),
        (0xFF7E77, 0), (0xFFF0BE, 0xFF), (0xFFF0C0, 0),
        (record, 0x84),
        (record + 0x20, 0), (record + 0x21, 0x12),
        (record + 0x22, 0x2D), (record + 0x23, 0xB2),
        (record + 0x37, 0), (0xFF7E58, horizontal_impulse & 0xFF),
    ]


def _overlay(read, writes, address, size):
    values = {at: value for at, value in writes}
    if size == 1:
        return values.get(address, read(address, size))
    return int.from_bytes(bytes(values.get(address + i, (read(address + i, 1))) for i in range(size)), 'big')
