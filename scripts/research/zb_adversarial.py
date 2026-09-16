"""zb_adversarial: what the machine does with a Z80 that really touches work RAM through its window (research).

    python scripts/research/zb_adversarial.py [--json OUT]

Synthetic cartridges in the shape of tests/common/test_atomic_sound_guard.py: the 68000 uploads a
tiny Z80 program, releases the processor and parks in ``bra.s *`` (the gate).  Each case then asks
``Machine.atomic`` for a 2,000-cycle span that writes work RAM FF8000 and reports the adapter's
verdict (``Machine.refusal``), whether the machine survived, and the Z80 box's bank state at the gate
(decoded out of a snapshot for the report).  The cases separate the two guards:

  P1  completed RAM bank (nine one bits), the Z80 never touches the window  -> the pre-check refuses
      (graceful); an observer-only rule would have admitted an exact span.
  P2  the bank completes to RAM INSIDE the span and the Z80 then reads 8000  -> the pre-check passes
      (the register is still transient at the gate), the observer fires: invalidation.
  P3  three one bits only (a transient RAM window, bit count 3) and the Z80 reads 8000 in a loop, the
      gate parked after the writes -> the pre-check refuses (bank E00000); this is the positive case a
      narrowed rule R1 (complete sequences only) would ADMIT, and P3b shows what happens then:
  P3b the same program with the gate parked BEFORE the three writes, so the span covers the writes and
      the read -> the observer fires on the read through the transient window: invalidation.
  P4  a completed ROM bank (bank 000, nine zero bits) with the Z80 reading 8000 in a loop -> admitted.
  P5  three one bits (transient RAM window) and the Z80 never touches the window, gate parked after
      the writes -> the pre-check refuses although the span would be exact (the Gods case).

Each case runs in its own process (one native machine per process).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zb_common as zb
from genesis_re.machine import Machine, NativeError


def cartridge(program, *, gate_before_release=False, delay_words=0):
    rom = bytearray(4096)
    rom[:8] = bytes.fromhex('00ff8000 00000200')
    code = bytearray()

    def word(address, value):
        code.extend(bytes.fromhex('33fc') + value.to_bytes(2, 'big') + address.to_bytes(4, 'big'))
    word(0xa11100, 0x100)      # take the bus
    word(0xa11200, 0)          # hold the Z80 in reset
    for offset, value in enumerate(program):
        code.extend(bytes.fromhex('13fc') + value.to_bytes(2, 'big') + (0xa00000 + offset).to_bytes(4, 'big'))
    word(0xa11200, 0x100)      # release reset
    word(0xa11100, 0)          # release the bus: the Z80 runs from here
    for _ in range(delay_words):
        code.extend(bytes.fromhex('4e71'))   # nop: 4 cycles each, lets the Z80 advance before the gate
    gate = 0x200 + len(code)
    code.extend(bytes.fromhex('60fe'))       # bra.s *
    rom[0x200:0x200 + len(code)] = code
    return bytes(rom), gate


Z80_ONE = bytes.fromhex('3e01')             # ld a,1
Z80_ZERO = bytes.fromhex('3e00')            # ld a,0
Z80_BANK = bytes.fromhex('320060')          # ld (6000),a
Z80_READ_LOOP = bytes.fromhex('3a0080 18fb')  # loop: ld a,(8000); jr loop
Z80_SPIN = bytes.fromhex('18fe')            # jr *

CASES = {
    'P1': dict(program=Z80_ONE + Z80_BANK * 9 + Z80_SPIN, delay_words=400),
    'P2': dict(program=Z80_ONE + Z80_BANK * 9 + Z80_READ_LOOP, delay_words=0),
    'P3': dict(program=Z80_ONE + Z80_BANK * 3 + Z80_READ_LOOP, delay_words=400),
    'P3b': dict(program=Z80_ONE + Z80_BANK * 3 + Z80_READ_LOOP, delay_words=0),
    'P4': dict(program=Z80_ZERO + Z80_BANK * 9 + Z80_READ_LOOP, delay_words=400),
    'P5': dict(program=Z80_ONE + Z80_BANK * 3 + Z80_SPIN, delay_words=400),
}


def run_case(name):
    spec = CASES[name]
    rom, gate = cartridge(spec['program'], delay_words=spec['delay_words'])
    out = {'case': name}
    view = None
    with Machine(rom) as m:
        m.gates([gate])
        reason = m.run(instructions=2000)
        out['reached_gate'] = reason == 'gate'
        snap = m.snapshot()
        # locate the Z80 program image in the snapshot (the box's RAM) to read the bank state
        i = snap.find(spec['program'][:8])
        tail = i + 8192
        bank = int.from_bytes(snap[tail + 4:tail + 6], 'little')
        bits = int.from_bytes(snap[tail + 6:tail + 10], 'little')
        pc = int.from_bytes(snap[i - 31 + 22:i - 31 + 24], 'little')
        out['at_gate'] = {'bank': '%03X' % bank, 'window': '%06X' % (bank << 15), 'bank_bits': bits, 'phase': bits % 9, 'z80_pc': '%04X' % pc,
                          'ram_window': (bank << 15) >= 0xE00000}
        try:
            ok = m.atomic(target=m.info['tick'] + 100_000, cycles=2000, instructions=1, last_pc=gate,
                          writes=[(0xff8000, 0x12)], registers={'pc': gate})
            out['atomic'] = 'admitted' if ok else 'refused: %s' % m.refusal
            out['machine'] = 'valid'
            try:
                m.snapshot()
            except NativeError as e:
                out['machine'] = 'invalidated: %s' % e
        except NativeError as e:
            out['atomic'] = 'error: %s' % e
            try:
                m.snapshot()
                out['machine'] = 'valid'
            except NativeError as e2:
                out['machine'] = 'invalidated: %s' % e2
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--case', default=None)
    p.add_argument('--json', default=None)
    a = p.parse_args(argv)
    if a.case:
        print(json.dumps(run_case(a.case)))
        return
    results = []
    for name in CASES:
        r = subprocess.run([sys.executable, __file__, '--case', name], capture_output=True, text=True, cwd=zb.ROOT)
        if r.returncode:
            results.append({'case': name, 'error': r.stderr[-800:]})
        else:
            results.append(json.loads(r.stdout.strip().splitlines()[-1]))
    for r in results:
        print(json.dumps(r))
    if a.json:
        Path(a.json).write_text(json.dumps({'provenance': zb.provenance(), 'cases': results}, indent=1))


if __name__ == '__main__':
    main()
