"""zb_z80dis: a small table-driven Z80 disassembler for the sound-driver study (research, read-only).

    python scripts/research/zb_z80dis.py [--rom assets/...] [--base 0F4570] [--size 1074] [START-END ...]

Decodes the un-prefixed, CB, ED, DD/FD (IX/IY) and DD CB/FD CB groups by the x/y/z/p/q scheme.
Addresses printed are Z80 addresses (the 68000 copies ROM ``base`` to Z80 RAM 0000).  Output is
text only; nothing is written unless ``--out`` names a file under artifacts/gods/research/.
"""
import argparse
import sys
from pathlib import Path

R = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
RP = ['bc', 'de', 'hl', 'sp']
RP2 = ['bc', 'de', 'hl', 'af']
CC = ['nz', 'z', 'nc', 'c', 'po', 'pe', 'p', 'm']
ALU = ['add a,', 'adc a,', 'sub ', 'sbc a,', 'and ', 'xor ', 'or ', 'cp ']
ROT = ['rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', 'sll', 'srl']
BLI = {4: ['ldi', 'cpi', 'ini', 'outi'], 5: ['ldd', 'cpd', 'ind', 'outd'],
       6: ['ldir', 'cpir', 'inir', 'otir'], 7: ['lddr', 'cpdr', 'indr', 'otdr']}
IM = ['0', '0/1', '1', '2', '0', '0/1', '1', '2']


def _s8(v):
    return v - 256 if v & 0x80 else v


def decode(mem, pc):
    """Return (text, size) for the instruction at ``pc`` in the 64 KB byte view ``mem``."""
    start = pc

    def b():
        nonlocal pc
        v = mem[pc & 0xFFFF]
        pc += 1
        return v

    def w():
        lo = b(); hi = b()
        return lo | (hi << 8)

    op = b()
    prefix = None
    if op in (0xDD, 0xFD):
        prefix = 'ix' if op == 0xDD else 'iy'
        op = b()
        if op in (0xDD, 0xFD):        # a prefix followed by a prefix is a NOP-prefix; re-decode
            return ('nop (prefix %s)' % prefix, 1)
    disp = None

    def reg(i):
        if prefix is None:
            return R[i]
        if i == 6:
            nonlocal disp
            if disp is None:
                disp = _s8(b())
            return '(%s%+d)' % (prefix, disp)
        if i == 4:
            return prefix + 'h'
        if i == 5:
            return prefix + 'l'
        return R[i]

    def hl():
        return prefix or 'hl'

    def rp(i):
        return hl() if i == 2 else RP[i]

    def rp2(i):
        return hl() if i == 2 else RP2[i]

    x, y, z = op >> 6, (op >> 3) & 7, op & 7
    p, q = y >> 1, y & 1
    if op == 0xCB:
        if prefix:
            disp = _s8(b())
            op2 = b()
            x2, y2, z2 = op2 >> 6, (op2 >> 3) & 7, op2 & 7
            m = '(%s%+d)' % (prefix, disp)
            extra = '' if z2 == 6 else ',' + R[z2]
            if x2 == 0: t = '%s %s%s' % (ROT[y2], m, extra)
            elif x2 == 1: t = 'bit %d,%s' % (y2, m)
            elif x2 == 2: t = 'res %d,%s%s' % (y2, m, extra)
            else: t = 'set %d,%s%s' % (y2, m, extra)
            return t, pc - start
        op2 = b()
        x2, y2, z2 = op2 >> 6, (op2 >> 3) & 7, op2 & 7
        if x2 == 0: t = '%s %s' % (ROT[y2], R[z2])
        elif x2 == 1: t = 'bit %d,%s' % (y2, R[z2])
        elif x2 == 2: t = 'res %d,%s' % (y2, R[z2])
        else: t = 'set %d,%s' % (y2, R[z2])
        return t, pc - start
    if op == 0xED and prefix is None:
        op2 = b()
        x2, y2, z2 = op2 >> 6, (op2 >> 3) & 7, op2 & 7
        p2, q2 = y2 >> 1, y2 & 1
        if x2 == 1:
            if z2 == 0: t = 'in %s,(c)' % ('f' if y2 == 6 else R[y2])
            elif z2 == 1: t = 'out (c),%s' % ('0' if y2 == 6 else R[y2])
            elif z2 == 2: t = ('sbc' if q2 == 0 else 'adc') + ' hl,' + RP[p2]
            elif z2 == 3:
                a = w()
                t = ('ld ($%04X),%s' % (a, RP[p2])) if q2 == 0 else ('ld %s,($%04X)' % (RP[p2], a))
            elif z2 == 4: t = 'neg'
            elif z2 == 5: t = 'reti' if y2 == 1 else 'retn'
            elif z2 == 6: t = 'im ' + IM[y2]
            else: t = ['ld i,a', 'ld r,a', 'ld a,i', 'ld a,r', 'rrd', 'rld', 'nop', 'nop'][y2]
        elif x2 == 2 and z2 <= 3 and y2 >= 4:
            t = BLI[y2][z2]
        else:
            t = 'db $ED,$%02X' % op2
        return t, pc - start
    if x == 0:
        if z == 0:
            if y == 0: t = 'nop'
            elif y == 1: t = "ex af,af'"
            elif y == 2: d = _s8(b()); t = 'djnz $%04X' % ((pc + d) & 0xFFFF)
            elif y == 3: d = _s8(b()); t = 'jr $%04X' % ((pc + d) & 0xFFFF)
            else: d = _s8(b()); t = 'jr %s,$%04X' % (CC[y - 4], (pc + d) & 0xFFFF)
        elif z == 1:
            if q == 0: t = 'ld %s,$%04X' % (rp(p), w())
            else: t = 'add %s,%s' % (hl(), rp(p))
        elif z == 2:
            if q == 0:
                t = ['ld (bc),a', 'ld (de),a', 'ld ($%04X),' + hl(), 'ld ($%04X),a'][p]
                if p >= 2: t = t % w()
            else:
                t = ['ld a,(bc)', 'ld a,(de)', 'ld ' + hl() + ',($%04X)', 'ld a,($%04X)'][p]
                if p >= 2: t = t % w()
        elif z == 3:
            t = ('inc ' if q == 0 else 'dec ') + rp(p)
        elif z == 4: t = 'inc ' + reg(y)
        elif z == 5: t = 'dec ' + reg(y)
        elif z == 6:
            r = reg(y); n = b()
            t = 'ld %s,$%02X' % (r, n)
        else:
            t = ['rlca', 'rrca', 'rla', 'rra', 'daa', 'cpl', 'scf', 'ccf'][y]
    elif x == 1:
        if op == 0x76: t = 'halt'
        else:
            if prefix and (y == 6 or z == 6):
                # (ix+d) with a plain register on the other side
                if y == 6: t = 'ld %s,%s' % (reg(6), R[z])
                else: t = 'ld %s,%s' % (R[y], reg(6))
            else:
                t = 'ld %s,%s' % (reg(y), reg(z))
    elif x == 2:
        t = ALU[y] + reg(z)
    else:
        if z == 0: t = 'ret ' + CC[y]
        elif z == 1:
            if q == 0: t = 'pop ' + rp2(p)
            else: t = ['ret', 'exx', 'jp (%s)' % hl(), 'ld sp,%s' % hl()][p]
        elif z == 2: t = 'jp %s,$%04X' % (CC[y], w())
        elif z == 3:
            if y == 0: t = 'jp $%04X' % w()
            elif y == 2: t = 'out ($%02X),a' % b()
            elif y == 3: t = 'in a,($%02X)' % b()
            elif y == 4: t = 'ex (sp),' + hl()
            elif y == 5: t = 'ex de,hl'
            elif y == 6: t = 'di'
            else: t = 'ei'
        elif z == 4: t = 'call %s,$%04X' % (CC[y], w())
        elif z == 5:
            if q == 0: t = 'push ' + rp2(p)
            else: t = 'call $%04X' % w()
        elif z == 6: t = ALU[y] + '$%02X' % b()
        else: t = 'rst $%02X' % (y * 8)
    return t, pc - start


def listing(mem, start, end):
    pc = start
    while pc < end:
        text, size = decode(mem, pc)
        raw = ' '.join('%02X' % mem[pc + i] for i in range(size))
        yield '%04X  %-14s %s' % (pc, raw, text)
        pc += size


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rom', default='assets/Gods (USA).md')
    ap.add_argument('--base', default='0F4570')
    ap.add_argument('--size', default='1074')
    ap.add_argument('--out', default=None)
    ap.add_argument('ranges', nargs='*')
    a = ap.parse_args(argv)
    rom = Path(a.rom).read_bytes()
    base, size = int(a.base, 16), int(a.size, 16)
    mem = bytearray(0x10000)
    mem[:size] = rom[base:base + size]
    ranges = a.ranges or ['0000-%04X' % size]
    lines = []
    for r in ranges:
        s, e = r.split('-')
        lines.append('; --- %s' % r)
        lines.extend(listing(mem, int(s, 16), int(e, 16)))
    text = '\n'.join(lines) + '\n'
    if a.out:
        Path(a.out).write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
