"""vp_sweep_disasm: linear-sweep disassembly of the Gods code region into a text file, for reference greps."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_common
import pathfacts
from gods_sega.profile import GODS
rom = GODS.read_rom()
out = Path('artifacts/gods/research/vp-sweep-disasm.txt')
lines = []
for start, end in ((0x200, 0x16000), (0xF4400, 0xF4600)):
    pc = start
    while pc < end:
        text, size = pathfacts.disasm(rom, None, pc)
        lines.append('%06X  %s' % (pc, text))
        pc += size
out.write_text('\n'.join(lines))
print(len(lines), 'lines ->', out)
