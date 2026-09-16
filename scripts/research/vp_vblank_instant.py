"""vp_vblank_instant: measure the master tick (mod FRAME_TICKS) at which the VBlank handler is entered."""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_common
vp_common.guard_paths()
from genesis_re.machine import Machine
game = vp_common.gods_profile()
FT = vp_common.FT
fixture = Path('artifacts/gods/evidence/main/boundary-6000.state')
offsets = []
with Machine(game.read_rom(), game) as m:
    m.restore(fixture.read_bytes()); m.audio_policy('discard')
    m.gates([0x0003DC])
    start = m.info['tick']
    while m.info['tick'] < start + 600 * FT:
        if m.run(target=start + 600 * FT) == 'gate':
            info = m.info
            regs = m.registers()
            pre = int.from_bytes(m.peek_ram((regs['a7'] + 2) & 0xFFFF, 4), 'big') & 0xFFFFFF
            offsets.append((info['tick'] % FT, pre))
            m.gate(0x0003DC, bypass_once=True)
ticks = sorted(o for o, _ in offsets)
print('VBlanks', len(offsets), 'handler entry tick mod FT: min %d (%.5f) median %d max %d (%.5f)' % (ticks[0], ticks[0]/FT, ticks[len(ticks)//2], ticks[-1], ticks[-1]/FT))
print('exception entry is 44 cycles = 308 ticks; irq instant <= %d (%.5f), line %.2f of 262' % (ticks[0]-308, (ticks[0]-308)/FT, (ticks[0]-308)/(FT/262)))
print('preempted PCs', Counter(p for _, p in offsets).most_common(8))
json.dump({'entries_mod_ft': ticks, 'min': ticks[0], 'irq_upper_bound': ticks[0]-308}, open('artifacts/gods/research/vp-vblank-instant.json','w'))
