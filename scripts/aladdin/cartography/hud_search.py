"""Find RAM fields matching the HUD values visible in the checkpoint screenshots."""
import numpy as np
z = np.load('D:/Prog/aladdin_re/artifacts/cartography/ram_activity.npz')
snaps, frames = z['snapshots'], z['snap_frames']
# frame -> (score, lives, gems, apples) read off the checkpoint screenshots (None = not shown)
truth = {
    1096: (None, 3, None, 10), 8536: (2050, 3, 5, 66), 16266: (2900, 6, 3, 77), 22200: (4450, 8, 2, 94),
    24935: (6100, 8, 3, 95), 26378: (6100, 8, 3, 99), 44827: (10900, 6, 10, 22), 47202: (12650, 6, 10, 31),
    49504: (12650, 6, 10, 19), 57289: (13100, 6, None, 10), 68338: (15500, 6, 10, 16), 69586: (15500, 6, 13, 20),
    82161: (20900, 4, 24, 9),
}
names = ('score', 'lives', 'gems', 'apples')


def encodings(value, width_hint):
    """Candidate byte patterns for a decimal value."""
    out = []
    s = str(value)
    out.append(('ascii', s.encode()))
    out.append(('ascii-padded', s.rjust(width_hint, '0').encode()))
    out.append(('ascii-space', s.rjust(width_hint, ' ').encode()))
    bcd = int(s, 16)
    out.append(('bcd-be', bcd.to_bytes(max(1, (len(s) + 1) // 2), 'big')))
    out.append(('bin8', bytes([value & 0xFF])) if value < 256 else ('bin16', value.to_bytes(2, 'big')))
    if value < 65536:
        out.append(('bin16', value.to_bytes(2, 'big')))
    return out


def find_all(ram, pattern):
    hits, start = [], 0
    b = ram.tobytes()
    while True:
        i = b.find(pattern, start)
        if i < 0:
            return hits
        hits.append(i); start = i + 1


for field, width in zip(names, (5, 1, 2, 2)):
    candidates = None
    for frame, values in truth.items():
        value = values[names.index(field)]
        if value is None:
            continue
        idx = int(np.argmin(np.abs(frames - frame)))
        if abs(int(frames[idx]) - frame) > 40:
            continue
        ram = snaps[idx]
        found = set()
        for enc, pattern in encodings(value, width):
            for addr in find_all(ram, pattern):
                if addr >= 0xE000 or True:
                    found.add((enc, addr))
        candidates = found if candidates is None else candidates & found
        if not candidates:
            break
    print(field, 'consistent candidates:', sorted((e, f'FF{a:04X}') for e, a in candidates)[:20] if candidates else 'none')
