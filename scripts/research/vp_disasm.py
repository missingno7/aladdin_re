"""vp_disasm: disassemble Gods ROM ranges from the committed source tree (verification pass, read-only)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ISO = ROOT / 'artifacts/gods/research/src-at-HEAD'
sys.path.insert(0, str(ISO / 'src')); sys.path.insert(0, str(ISO / 'scripts'))
import pathfacts
from gods_sega.profile import GODS
rom = GODS.read_rom()
for arg in sys.argv[1:]:
    s, e = arg.split('-')
    pc, end = int(s, 16), int(e, 16)
    print('; --- %06X-%06X' % (pc, end))
    while pc < end:
        text, size = pathfacts.disasm(rom, None, pc)
        words = ' '.join('%04X' % int.from_bytes(rom[pc + i:pc + i + 2], 'big') for i in range(0, size, 2))
        print('%06X  %-24s %s' % (pc, words, text))
        pc += size
