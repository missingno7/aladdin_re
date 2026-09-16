"""vp_recording_census: whole-recording census of Gods' VBlank/tick timing on the ORIGINAL, from power-on.

    python scripts/research/vp_recording_census.py --node fb408bc75597 --out artifacts/gods/research/census-T-fb408bc7.json
    python scripts/research/vp_recording_census.py --node fb408bc75597 --sound-sites 1 --out ...   (pass S1)
    python scripts/research/vp_recording_census.py --node fb408bc75597 --sound-sites 2 --out ...   (pass S2)

Replays the recorded inputs of one history leaf from power-on exactly as ``history_runtime.step``
does (the mask set at the frame wrap, the machine run to the observation instant and then to the
next wrap; gates only observe and are bypassed once, so the trajectory IS the original's).

Pass T gates: 0003DC (VBlank handler entry: counter, pre-empted PC, latches, FFEECC, sound block,
pause/mode words), 0004E8 (handler exit: latches after the sample), 001EC2 (tick start: counters,
tick words, mode words), 001EB4 (wait entry), 000492 (the palette upload executes: pre-empted PC),
0F4478 (the sound block transfer executes: block bytes), and the nine gameplay read sites of the 60
Hz counters (004BA0 004BB8 0065C4 0067E4 006900 006A2A 00F456 00F4AA 00F4BE).  When an odd VBlank
lands inside a tick's body and the handler's sample CHANGED a pad latch, the remainder of that tick
is single-stepped to 001EB4 and every read of FFEA1E/FFEA20/FFEA22/FFEA23/FFF3DA (and of the 60 Hz
counters) after the VBlank is recorded: the exact "torn input consumed" witness.

Pass S1/S2 gates the direct write sites of the sound command block FFFDEA..FFFE0B (three thirds of the
static sites) and records, per write, the slot's value before the write, the new value, and where
in the tick it happened relative to the VBlanks.  Research tooling; nothing is written to the
product; one Machine per process.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_common
vp_common.guard_paths()
import pathfacts
from genesis_re.history import HistoryStore
from genesis_re.machine import Machine

FT = vp_common.FT
VBLANK, HANDLER_EXIT, TICK_START, TICK_END, PALETTE_UP, SOUND_XFER = 0x0003DC, 0x0004E8, 0x001EC2, 0x001EB4, 0x000492, 0x0F4478
PALETTE_SET_TAIL, EXIT_PATH = 0x00211C, 0x002142      # the tick tail that sets FFEECC; the bit-6 exit path that writes the VDP after it
COUNTER_READS = [0x004BA0, 0x004BB8, 0x0065C4, 0x0067E4, 0x006900, 0x006A2A, 0x00F456, 0x00F4AA, 0x00F4BE]
WAIT_LOOP = range(0x00052E, 0x00053E)
LATCH_RE = re.compile(r'\$(ea1e|ea20|ea22|ea23|f3da)\.w')
COUNTER_RE = re.compile(r'\$(eec6|eec8|f2aa|f19e)\.w')
UPLOAD_LOOPS = {'0018C8-tiles': range(0x001974, 0x00198C), '00126A-tiles': range(0x0012F4, 0x00130C),
                '00FC8E-tiles': range(0x00FD86, 0x00FD9E), '001098-sprites': range(0x0010C8, 0x0010D6),
                '001098-scroll': range(0x001104, 0x00112E), '00112E-map': range(0x00112E, 0x001164)}


def latches(m):
    return m.peek_ram(0xEA1E, 6).hex() + '/' + m.peek_ram(0xF3DA, 2).hex()


def block(m):
    return m.peek_ram(0xFDEA, 0x22).hex()


def mode_words(m):
    return {'f210': int.from_bytes(m.peek_ram(0xF210, 2), 'big', signed=True), 'ef14': int.from_bytes(m.peek_ram(0xEF14, 2), 'big'),
            'ef3c': int.from_bytes(m.peek_ram(0xEF3C, 2), 'big', signed=True), 'eef8': int.from_bytes(m.peek_ram(0xEEF8, 2), 'big'),
            'f3d8': int.from_bytes(m.peek_ram(0xF3D8, 2), 'big'), 'eedf': m.peek_ram(0xEEDF, 1)[0], 'eecc': m.peek_ram(0xEECC, 1)[0]}


def sound_sites(rom):
    sites = []
    for start, end in ((0x200, 0x16000), (0xF4400, 0xF4600)):
        pc = start
        while pc < end:
            text, size = pathfacts.disasm(rom, None, pc)
            mm = re.search(r'\$(fde[a-f]|fdf[0-9a-f]|fe0[0-9a-b])\.w$', text)
            if mm and not text.startswith(('tst', 'cmp', 'btst')) and not (0x0F4472 <= pc < 0x0F44D0):
                sites.append(pc)
            pc += size
    return sites


def is_read(text, address_re):
    mm = address_re.search(text)
    if not mm:
        return None
    mnemonic = text.split()[0]
    operands = text[len(mnemonic):].strip()
    last = operands.split(',')[-1].strip() if operands else ''
    if mnemonic.startswith(('move', 'clr', 'st', 'sf')) and address_re.search(last):
        return False
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--node', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--sound-sites', type=int, default=0, help='0: pass T; 1, 2 or 3: a third of the sound write sites')
    p.add_argument('--frames', type=int, default=None)
    p.add_argument('--no-step', action='store_true', help='skip the single-step witness of torn reads')
    p.add_argument('--offset', type=int, default=None, help='observation instant override (replay machinery only; the game cannot see it)')
    p.add_argument('--start-fixture', default=None, help='start from a retained state instead of power-on (its metadata gives the frame)')
    a = p.parse_args(argv)
    game = vp_common.gods_profile(a.offset)
    rom = game.read_rom()
    store = HistoryStore(game.history_path(), game.history_root)
    node = store.resolve(a.node)
    path = store.flatten(node)
    changes = {e['frame']: e['buttons'] for e in path['events']}
    end_frame = path['end_frame'] if a.frames is None else min(path['end_frame'], a.frames)
    OBS = game.observation_offset_ticks
    frame_start, start_state = 0, None
    if a.start_fixture:
        fmeta = json.loads(Path(a.start_fixture).with_suffix('.json').read_text())
        assert fmeta['history_id'] == node, 'fixture belongs to another history'
        frame_start, start_state = fmeta['frame'], Path(a.start_fixture).read_bytes()
    out = {'head': vp_common.HEAD, 'node': node, 'frames': end_frame, 'frame_start': frame_start, 'observation_offset_ticks': OBS,
           'pass': 'T' if not a.sound_sites else 'S%d' % a.sound_sites,
           'vblanks': [], 'ticks': [], 'palette_uploads': [], 'sound_transfers': [], 'counter_reads': [], 'sound_writes': [],
           'torn_witness': [], 'palette_set_tail': [], 'exit_path': []}
    if a.sound_sites:
        sites = sound_sites(rom)
        third = len(sites) // 3 + 1
        sites = sites[(a.sound_sites - 1) * third:a.sound_sites * third]
        out['sound_sites'] = ['%06X' % s for s in sites]
        gates = [VBLANK, HANDLER_EXIT, TICK_START, TICK_END] + sites
    else:
        gates = [VBLANK, HANDLER_EXIT, TICK_START, TICK_END, PALETTE_UP, SOUND_XFER, PALETTE_SET_TAIL, EXIT_PATH] + COUNTER_READS
    assert len(gates) <= 64, len(gates)
    site_set = set(gates)
    started = time.perf_counter()
    with Machine(rom, game) as m:
        if start_state is not None:
            m.restore(start_state)
        m.audio_policy('discard')
        m.gates(gates)
        tick = {}          # the tick in progress (after 001EC2, before 001EB4)
        vb = {}            # the VBlank in progress (between 0003DC and 0004E8)
        n_ticks = [0]
        buttons = [0]
        frame_now = [0]
        wait_visits = [0]
        stepping = [False]

        def on_gate(pc):
            info = m.info
            if pc == VBLANK:
                regs = m.registers()
                pre = int.from_bytes(m.peek_ram((regs['a7'] + 2) & 0xFFFF, 4), 'big') & 0xFFFFFF
                counter = int.from_bytes(m.peek_ram(0xEEC6, 4), 'big')
                vb.clear()
                vb.update({'frame': frame_now[0], 'tick': info['tick'], 'offset': round(info['tick'] % FT / FT, 4), 'vblanks': info['vblanks'],
                           'counter_before': counter, 'preempted_pc': pre, 'idle': pre in WAIT_LOOP, 'in_tick': bool(tick),
                           'tick_index': n_ticks[0] - 1 if tick else None, 'latches_before': latches(m), 'block_before': block(m),
                           'eecc': m.peek_ram(0xEECC, 1)[0], 'eedf': m.peek_ram(0xEEDF, 1)[0], 'fe10': int.from_bytes(m.peek_ram(0xFE10, 2), 'big'),
                           'buttons': buttons[0]})
                for name, r in UPLOAD_LOOPS.items():
                    if pre in r:
                        vb['in_upload_loop'] = name
                if tick:
                    tick['vblanks_inside'] += 1
                    tick['preempted'].append(pre)
                    tick['vblank_parity_inside'].append(counter & 1)
            elif pc == HANDLER_EXIT and vb:
                after = latches(m)
                vb['latches_after'] = after
                vb['latch_changed'] = after != vb['latches_before']
                vb['block_after'] = block(m)
                out['vblanks'].append(dict(vb))
                record = dict(vb)
                vb.clear()
                if tick and record['latch_changed']:
                    tick['latch_changed_inside'] = True
                    if not a.no_step and not a.sound_sites and not stepping[0]:
                        step_remainder(m, record, tick)
            elif pc == TICK_START:
                tick.clear()
                tick.update({'index': n_ticks[0], 'frame': frame_now[0], 'start_tick': info['tick'], 'start_offset': round(info['tick'] % FT / FT, 4),
                             'start_vblanks': info['vblanks'], 'counter': int.from_bytes(m.peek_ram(0xEEC6, 4), 'big'),
                             'ef4a': int.from_bytes(m.peek_ram(0xEF4A, 2), 'big'), 'ef4c': int.from_bytes(m.peek_ram(0xEF4C, 2), 'big'),
                             'f2aa': int.from_bytes(m.peek_ram(0xF2AA, 4), 'big'), 'f19e': int.from_bytes(m.peek_ram(0xF19E, 2), 'big'),
                             'latches': latches(m), 'mode': mode_words(m), 'vblanks_inside': 0, 'preempted': [], 'vblank_parity_inside': [],
                             'latch_changed_inside': False, 'wait_visits_before': wait_visits[0], 'block_at_start': block(m)})
                wait_visits[0] = 0
                n_ticks[0] += 1
            elif pc == TICK_END:
                wait_visits[0] += 1
                if tick and 'end_tick' not in tick:
                    tick.update({'end_tick': info['tick'], 'end_frame': frame_now[0], 'work_frames': round((info['tick'] - tick['start_tick']) / FT, 4),
                                 'end_vblanks': info['vblanks'], 'block_at_end': block(m), 'eecc_at_end': m.peek_ram(0xEECC, 1)[0]})
                    out['ticks'].append(dict(tick))
                    tick.clear()
            elif pc == PALETTE_UP:
                regs = m.registers()
                pre = int.from_bytes(m.peek_ram((regs['a7'] + 22) & 0xFFFF, 4), 'big') & 0xFFFFFF
                rec = {'frame': frame_now[0], 'vblanks': info['vblanks'], 'preempted_pc': pre, 'idle': pre in WAIT_LOOP, 'in_tick': bool(tick),
                       'tick_index': n_ticks[0] - 1 if tick else None}
                for name, r in UPLOAD_LOOPS.items():
                    if pre in r:
                        rec['in_upload_loop'] = name
                out['palette_uploads'].append(rec)
            elif pc == SOUND_XFER:
                out['sound_transfers'].append({'frame': frame_now[0], 'vblanks': info['vblanks'], 'block': block(m), 'in_tick': bool(tick),
                                               'tick_index': n_ticks[0] - 1 if tick else None,
                                               'preempted_pc': vb.get('preempted_pc'), 'idle': vb.get('idle')})
            elif pc in (PALETTE_SET_TAIL, EXIT_PATH) and not a.sound_sites:
                out['palette_set_tail' if pc == PALETTE_SET_TAIL else 'exit_path'].append(
                    {'frame': frame_now[0], 'tick_index': n_ticks[0] - 1 if tick else None, 'vblanks': info['vblanks'], 'offset': round(info['tick'] % FT / FT, 4),
                     'vblanks_inside': tick['vblanks_inside'] if tick else None, 'eecc': m.peek_ram(0xEECC, 1)[0]})
            elif pc in COUNTER_READS and not a.sound_sites:
                out['counter_reads'].append({'pc': '%06X' % pc, 'frame': frame_now[0], 'tick_index': n_ticks[0] - 1 if tick else None, 'in_tick': bool(tick),
                                             'after_odd_vblank_inside': bool(tick) and tick['vblanks_inside'] > 0})
            elif a.sound_sites and pc in site_set:
                text, _ = pathfacts.disasm(rom, None, pc)
                mm = re.search(r'\$(fd[ef][0-9a-f]|fe0[0-9a-f])\.w$', text)
                slot = int(mm.group(1), 16)
                mnemonic = text.split()[0]
                size = 4 if mnemonic.endswith('.l') else 2 if mnemonic.endswith('.w') else 1
                old = m.peek_ram(slot, size).hex()
                regs = m.registers()
                src = text.split()[1].split(',')[0] if ' ' in text else ''
                new = None
                if src.startswith('#$'):
                    new = int(src[2:], 16) & ((1 << (8 * size)) - 1)
                elif src in regs:
                    new = regs[src] & ((1 << (8 * size)) - 1)
                out['sound_writes'].append({'pc': '%06X' % pc, 'frame': frame_now[0], 'tick_index': n_ticks[0] - 1 if tick else None, 'in_tick': bool(tick),
                                            'slot': '%04X' % slot, 'size': size, 'old': old, 'new': None if new is None else '%0*x' % (size * 2, new),
                                            'vblanks_inside_before': tick['vblanks_inside'] if tick else None, 'text': text})

        def step_remainder(m, vb, tick):
            """Single-step from the handler's exit to 001EB4, recording reads of the latches and the 60 Hz counters."""
            reads, steps = [], 0
            vbl0 = m.info['vblanks']
            stepping[0] = True
            m.gate(m.info['pc'], bypass_once=True)       # parked at the handler-exit gate: execute it first
            while True:
                info = m.info
                pc = info['pc']
                if pc == TICK_END or steps > 60000 or info['vblanks'] != vbl0:
                    break
                text, _ = pathfacts.disasm(rom, None, pc)
                r = is_read(text, LATCH_RE)
                if r is not None:
                    reads.append({'pc': '%06X' % pc, 'text': text, 'kind': 'latch', 'read': r})
                r = is_read(text, COUNTER_RE)
                if r is not None and pc != 0x001EB8:
                    reads.append({'pc': '%06X' % pc, 'text': text, 'kind': 'counter', 'read': r})
                if m.run(instructions=1) == 'gate':
                    gated = m.info['pc']     # parked at a gate (this pc, or the handler entry after an IRQ): observe, then execute
                    on_gate(gated)
                    if m.info['pc'] == gated:
                        m.gate(gated, bypass_once=True)
                        m.run(instructions=1)
                steps += 1
            stepping[0] = False
            out['torn_witness'].append({'tick_index': tick['index'], 'frame': vb['frame'], 'latches_before': vb['latches_before'],
                                        'latches_after': vb['latches_after'], 'preempted_pc': vb['preempted_pc'], 'steps_after': steps,
                                        'ended_at_tick_end': m.info['pc'] == TICK_END, 'another_vblank': m.info['vblanks'] != vbl0,
                                        'reads': reads[:200], 'latch_reads': sum(1 for r in reads if r['kind'] == 'latch' and r['read']),
                                        'counter_reads': sum(1 for r in reads if r['kind'] == 'counter' and r['read'])})

        def run_to(target):
            while m.info['tick'] < target:
                if m.run(target=target) == 'gate':
                    pc = m.info['pc']
                    on_gate(pc)
                    if m.info['pc'] == pc:
                        m.gate(pc, bypass_once=True)

        for e in path['events']:
            if e['frame'] < frame_start:
                buttons[0] = e['buttons']
        for frame in range(frame_start, end_frame):
            frame_now[0] = frame
            wrap = frame * FT
            run_to(wrap)
            b = changes.get(frame, buttons[0])
            if b != buttons[0]:
                m.pad(b)
                buttons[0] = b
            run_to(wrap + OBS)
            run_to(wrap + FT)
            if frame % 5000 == 0 and frame:
                print('  frame %d (%.0f s): %d VBlanks, %d ticks, %d torn witnesses' % (frame, time.perf_counter() - started, len(out['vblanks']), len(out['ticks']), len(out['torn_witness'])), flush=True)
    out['seconds'] = round(time.perf_counter() - started, 1)
    out['events'] = path['events']
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out))
    print('node %s: %d frames, %d VBlanks, %d ticks, %d palette uploads, %d sound transfers, %d counter reads, %d sound writes, %d torn witnesses; %.0f s -> %s' % (
        node[:12], end_frame, len(out['vblanks']), len(out['ticks']), len(out['palette_uploads']), len(out['sound_transfers']),
        len(out['counter_reads']), len(out['sound_writes']), len(out['torn_witness']), out['seconds'], a.out))


if __name__ == '__main__':
    main()
