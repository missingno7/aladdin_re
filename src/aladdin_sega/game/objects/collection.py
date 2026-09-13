"""Pure collection-counter and collection-state effects."""


def increment_counter(digits):
    """Advance two ASCII digits within the uncapped 00..98 domain."""
    tens, ones = digits >> 8, digits & 255
    if not (0x30 <= tens <= 0x39 and 0x30 <= ones <= 0x39) or digits == 0x3939:
        raise ValueError("decimal counter outside 00..98; capped branch remains original")
    return [(0xFFEFE0, tens + 1), (0xFFEFE1, 0x30)] if ones == 0x39 else [(0xFFEFE1, ones + 1)]


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
