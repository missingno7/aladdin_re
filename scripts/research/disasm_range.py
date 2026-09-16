"""Disassemble a ROM range of the Gods cartridge with the tracer's disassembler.

  python scripts/research/disasm_range.py START END [--game gods]

Research-only helper (docs/gods/research/); reads the ROM, touches no machine.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import pathfacts
from genesis_re.games import game as select_game


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('start')
    p.add_argument('end')
    p.add_argument('--game', type=select_game, default=select_game('gods'))
    a = p.parse_args(argv)
    rom = a.game.read_rom()
    pc, end = int(a.start, 16), int(a.end, 16)
    while pc < end:
        text, size = pathfacts.disasm(rom, None, pc)
        words = ' '.join('%04X' % int.from_bytes(rom[pc + i:pc + i + 2], 'big') for i in range(0, size, 2))
        print('%06X  %-24s %s' % (pc, words, text))
        pc += size


if __name__ == '__main__':
    main()
