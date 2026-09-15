"""Which game routines does the original run in a window of a recording, and which of them has the native runtime?

  route_census.py FROM_FRAME TO_FRAME [--recording ID] [--seed FRAME]

The oracle replays the recording (the evidence recording by default, or
the history node ID / prefix) from power-on, or from the evidence
snapshot fFRAME.state with --seed, and counts how often each call
target of the game's code region (every bsr / jsr / jmp target in the
listing artifacts/cartography/dis_game.txt, 1A8000..1B8000, plus the
sound driver entries) is entered between the VBlank frames FROM_FRAME
and TO_FRAME.  Targets are gated in batches of 63 (the machine's limit),
so the window is replayed once per batch.

The report lists every routine entered, hottest first, and marks the
ones no native module cites by address: that is the recovery frontier
of the window, whatever the old fallback frontier said.
"""
import glob
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_replay as nr
from aladdin_sega.machine import Machine

ROOT = Path(__file__).resolve().parents[1]
BATCH = 63


def call_targets():
    targets = set()
    for line in (ROOT / 'artifacts' / 'cartography' / 'dis_game.txt').read_text().splitlines():
        m = re.search(r'\b(?:bsr|jsr|jmp)\S*\s+\$([0-9a-f]{6})', line)
        if m:
            targets.add(int(m.group(1), 16))
    return sorted(t for t in targets if 0x1A8000 <= t < 0x1B8000 or 0x1E5000 <= t < 0x1E6000)


def cited_natively():
    cited = set()
    for f in glob.glob(str(ROOT / 'src' / 'aladdin_sega' / 'game' / '**' / '*.py'), recursive=True) + \
            glob.glob(str(ROOT / 'src' / 'aladdin_sega' / 'native' / '*.py')):
        for m in re.finditer(r'(?<![0-9A-Fa-fx])(?:0x)?(1[A-F][0-9A-F]{4})\b', Path(f).read_text(encoding='utf-8')):
            cited.add(int(m.group(1), 16))
    return cited


def run_window(m, pads, snapshot, start_frame, from_frame, to_frame, targets):
    """Replay from the snapshot (or the start) to TO_FRAME with the targets gated; hits per target inside the window."""
    if snapshot is not None:
        m.restore(snapshot)
    hits = {t: 0 for t in targets}
    nr.arm(m, list(targets))
    m.pad(pads.get(m.info['tick'] // nr.FRAME_TICKS, 0))
    while True:
        if nr.run_with_pads(m, pads, to_frame * nr.FRAME_TICKS) != 'gate':
            break
        pc, f = m.info['pc'], m.info['tick'] // nr.FRAME_TICKS
        m.gate(pc, bypass_once=True)
        if f >= from_frame:
            hits[pc] += 1
    return hits


def main(from_frame, to_frame, recording=None, seed=None):
    rom = nr.read_rom(); pads = nr.masks(recording)
    targets = call_targets(); cited = cited_natively()
    m = Machine(rom); m.audio_policy('discard')
    if seed is not None:
        m.restore(nr.load(seed)); snapshot = m.snapshot(); start_frame = seed
    else:
        snapshot = m.snapshot(); start_frame = 0
    totals = {}
    for i in range(0, len(targets), BATCH):
        batch = targets[i:i + BATCH]
        totals.update(run_window(m, pads, snapshot, start_frame, from_frame, to_frame, batch))
        print(f'  batch {i // BATCH + 1}/{(len(targets) + BATCH - 1) // BATCH}', file=sys.stderr)
    m.close()
    entered = sorted(((n, t) for t, n in totals.items() if n), reverse=True)
    print(f'{len(entered)} of {len(targets)} call targets entered in frames {from_frame}..{to_frame}'
          + (f' of recording {recording}' if recording else ''))
    print('  entries  routine  native?')
    for n, t in entered:
        print(f'  {n:>7}  {t:06X}  {"cited" if t in cited else "-- not cited by any native module"}')


if __name__ == '__main__':
    argv = sys.argv[1:]
    recording = seed = None
    if '--recording' in argv:
        i = argv.index('--recording'); recording = argv[i + 1]; del argv[i:i + 2]
    if '--seed' in argv:
        i = argv.index('--seed'); seed = int(argv[i + 1]); del argv[i:i + 2]
    main(int(argv[0]), int(argv[1]), recording, seed)
