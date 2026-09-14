"""pathfacts: derive compact machine facts by single-stepping the ORIGINAL machine.

Prototype (Python-side, zero native changes). Facts: executed PCs + disassembly,
per-instruction cycles, RAM writes (final residue and write counts), register
deltas, CCR/X history, stack delta, return PC, calls/returns, branch decisions.
"""
import ctypes
import json
import sys
from collections import OrderedDict
from pathlib import Path as _Path

# Judge the checkout, never an installed wheel: the checkout's src wins.
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'src'))

import capstone

from aladdin_sega.machine import Machine
from aladdin_sega.profile import read_rom

REGS = [f'd{i}' for i in range(8)] + [f'a{i}' for i in range(8)] + ['pc', 'sr']
CCR = (('X', 0x10), ('N', 0x08), ('Z', 0x04), ('V', 0x02), ('C', 0x01))
_MD = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000)
_BRANCHES = {'bra', 'bsr', 'bhi', 'bls', 'bcc', 'bcs', 'bne', 'beq', 'bvc', 'bvs',
             'bpl', 'bmi', 'bge', 'blt', 'bgt', 'ble'}


def ram_bytes(machine):
    return ctypes.string_at(machine.ram_address, 65536)


def disasm(rom, ram, pc):
    if pc < len(rom):
        code = rom[pc:pc + 10]
    elif 0xFF0000 <= pc <= 0xFFFFFF:
        code = ram[pc & 0xFFFF:(pc & 0xFFFF) + 10]
    else:
        return '??', 2
    for insn in _MD.disasm(code, pc):
        return (insn.mnemonic + ' ' + insn.op_str).strip(), insn.size
    word = int.from_bytes(code[:2], 'big')
    return 'dc.w $%04X' % word, 2


def park(state, at_pc, *, rom=None, max_instructions=200000):
    """Run the original from a parked state until it stands on at_pc; return snapshot."""
    rom = rom or read_rom()
    with Machine(rom) as m:
        m.restore(state)
        if m.info['pc'] == at_pc:
            return m.snapshot()
        m.gates([at_pc])
        if m.run(instructions=max_instructions) != 'gate':
            raise RuntimeError('original never reached %06X' % at_pc)
        return m.snapshot()


def trace(state, *, entry=None, stop_pc=None, max_instructions=20000, rom=None, detail=True):
    rom = rom or read_rom()
    with Machine(rom) as m:
        m.restore(state)
        m.gates([])
        regs = m.registers()
        info = m.info
        ram = ram_bytes(m)
        entry = regs['pc'] if entry is None else entry
        if regs['pc'] != entry:
            raise ValueError('state stands at %06X, not %06X' % (regs['pc'], entry))
        entry_regs, entry_info = dict(regs), dict(info)
        entry_ram = ram
        entry_a7 = regs['a7']
        caller_return = int.from_bytes(ram[entry_a7 & 0xFFFF:(entry_a7 & 0xFFFF) + 4], 'big') & 0xFFFFFF
        steps, writes, write_counts, calls, stack = [], OrderedDict(), {}, [], []
        ccr_last = {name: None for name, _ in CCR}
        interrupts = 0
        last_pc = None
        for n in range(max_instructions):
            pc = regs['pc']
            if n > 0:
                if stop_pc is not None and pc == stop_pc:
                    break
                if stop_pc is None and pc == caller_return and regs['a7'] == entry_a7 + 4:
                    break
            text, size = disasm(rom, ram, pc)
            m.run(instructions=1)
            new_regs, new_info, new_ram = m.registers(), m.info, ram_bytes(m)
            cycles = new_info['m68k_cycles'] - info['m68k_cycles']
            if new_info['vblanks'] != info['vblanks']:
                interrupts += 1
            changed = {k: (regs[k], new_regs[k]) for k in REGS if regs[k] != new_regs[k] and k != 'pc'}
            step_writes = []
            if new_ram != ram:
                # Chunked diff: compare 256-byte slices first, scan only the changed ones.
                for base in range(0, 65536, 256):
                    if new_ram[base:base + 256] != ram[base:base + 256]:
                        for i in range(base, base + 256):
                            if new_ram[i] != ram[i]:
                                addr = 0xFF0000 + i
                                step_writes.append((addr, new_ram[i]))
                                writes[addr] = new_ram[i]
                                write_counts[addr] = write_counts.get(addr, 0) + 1
            mnemonic = text.split(' ')[0].split('.')[0]
            taken = None
            if mnemonic in _BRANCHES or mnemonic.startswith('db'):
                taken = new_regs['pc'] != pc + size
            if mnemonic in ('bsr', 'jsr'):
                calls.append({'site': pc, 'callee': new_regs['pc'], 'return_slot': new_regs['a7'],
                              'return_pc': pc + size, 'depth': len(stack), 'step': n})
                stack.append(pc + size)
            elif mnemonic == 'rts':
                calls.append({'site': pc, 'return_to': new_regs['pc'], 'depth': len(stack) - 1, 'step': n})
                if stack:
                    stack.pop()
            if 'sr' in changed:
                for name, bit in CCR:
                    if (changed['sr'][0] ^ changed['sr'][1]) & bit:
                        ccr_last[name] = n
            if detail:
                steps.append({'n': n, 'pc': pc, 'text': text, 'cycles': cycles, 'taken': taken,
                              'changed': {k: v[1] for k, v in changed.items()},
                              'writes': step_writes, 'sr': new_regs['sr'] & 0x1F})
            last_pc = pc
            regs, info, ram = new_regs, new_info, new_ram
        else:
            raise RuntimeError('trace exceeded instruction cap before reaching its stop')
        exit_regs, exit_info = dict(regs), dict(info)
    changed_regs = {k: (entry_regs[k], exit_regs[k]) for k in REGS if entry_regs[k] != exit_regs[k]}
    return {
        'entry': entry, 'exit_pc': exit_regs['pc'], 'last_pc': last_pc,
        'instructions': exit_info['m68k_instructions'] - entry_info['m68k_instructions'],
        'cycles': exit_info['m68k_cycles'] - entry_info['m68k_cycles'],
        'master_ticks': exit_info['tick'] - entry_info['tick'],
        'interrupts_during_trace': interrupts,
        'stack_delta': exit_regs['a7'] - entry_regs['a7'],
        'caller_return_slot_at_entry': caller_return,
        'entry_registers': entry_regs,
        'entry_ram': entry_ram,
        'changed_registers': changed_regs,
        'ccr_exit': {name: bool(exit_regs['sr'] & bit) for name, bit in CCR},
        'ccr_last_changed_step': ccr_last,
        'ram_writes_final': writes, 'ram_write_counts': write_counts,
        'calls': calls, 'steps': steps,
    }


SOUND_ENTRIES = {0x1E58B8: 'sound-request', 0x1E58F4: 'sound-fixed-helper', 0x1E589A: 'sound-flush'}


def registers_at(facts, step_index):
    """Reconstruct the register file after step_index (or at entry for -1)."""
    regs = dict(facts['entry_registers'])
    for s in facts['steps'][:step_index + 1]:
        regs.update(s['changed'])
        regs['pc'] = None  # unknown here; filled by the next step's pc
    if step_index + 1 < len(facts['steps']):
        regs['pc'] = facts['steps'][step_index + 1]['pc']
    else:
        regs['pc'] = facts['exit_pc']
    return regs


def split_at_native(facts, callees=None):
    """Split a traced region around calls into native sound/device routines.

    Returns a list of segments: ('python', start, end) spans the recovered
    candidate may own; ('native', start, end, callee) spans that must run on
    the original machine.  Each segment carries its own cycles/instructions,
    RAM writes and register file at its boundaries, which is exactly the
    prefix/seam/suffix contract a SoundSeam needs.
    """
    callees = SOUND_ENTRIES if callees is None else callees
    steps = facts['steps']
    segments, start, index = [], 0, 0
    calls = {c['step']: c for c in facts['calls'] if 'callee' in c and c['callee'] in callees}
    while index < len(steps):
        if index in calls:
            depth = calls[index]['depth']
            segments.append(('python', start, index))  # includes the JSR itself
            end = index + 1
            while end < len(steps):
                c = next((c for c in facts['calls'] if c['step'] == end and 'return_to' in c and c['depth'] == depth), None)
                if c is not None:
                    break
                end += 1
            segments.append(('native', index + 1, end, calls[index]['callee']))
            start = end + 1
            index = end + 1
        else:
            index += 1
    segments.append(('python', start, len(steps) - 1))
    result = []
    for seg in segments:
        kind, a, b = seg[0], seg[1], seg[2]
        if a > b:
            continue
        chunk = steps[a:b + 1]
        writes = {}
        for s in chunk:
            for addr, value in s['writes']:
                writes[addr] = value
        result.append({
            'kind': kind, 'first_step': a, 'last_step': b,
            'callee': seg[3] if kind == 'native' else None,
            'entry_pc': chunk[0]['pc'], 'last_pc': chunk[-1]['pc'],
            'instructions': len(chunk), 'cycles': sum(s['cycles'] for s in chunk),
            'writes': writes,
            'registers_before': registers_at(facts, a - 1),
            'registers_after': registers_at(facts, b),
        })
    return result


def report_segments(segments):
    lines = []
    for i, seg in enumerate(segments):
        head = '%s segment %d: %06X..%06X  %d instructions / %d cycles' % (
            seg['kind'].upper(), i, seg['entry_pc'], seg['last_pc'], seg['instructions'], seg['cycles'])
        if seg['kind'] == 'native':
            head += '  (callee %06X %s)' % (seg['callee'], SOUND_ENTRIES.get(seg['callee'], ''))
        lines.append(head)
        ra, rb = seg['registers_before'], seg['registers_after']
        changed = ', '.join('%s %08X->%08X' % (k, ra[k], rb[k]) for k in REGS if k != 'pc' and ra.get(k) != rb.get(k))
        lines.append('   registers changed: ' + (changed or 'none'))
        lines.append('   after: pc %s a7 %08X sr %04X' % ('%06X' % rb['pc'] if rb['pc'] is not None else '??', rb['a7'], rb['sr']))
        lines.append('   writes: ' + (', '.join('%06X=%02X' % (a, v) for a, v in seg['writes'].items()) or 'none'))
    return '\n'.join(lines)


def check_plan(plan, facts, entry_regs):
    """Compare a boundary AtomicPlan against traced original facts."""
    problems = []
    if plan.cycles != facts['cycles']:
        problems.append('cycles: plan %d vs original %d' % (plan.cycles, facts['cycles']))
    if plan.instructions != facts['instructions']:
        problems.append('instructions: plan %d vs original %d' % (plan.instructions, facts['instructions']))
    if plan.last_pc != facts['last_pc']:
        problems.append('last_pc: plan %06X vs original %06X' % (plan.last_pc, facts['last_pc']))
    planned = dict(plan.writes)
    traced = facts['ram_writes_final']
    for addr, value in traced.items():
        if addr not in planned:
            problems.append('missing write %06X=%02X' % (addr, value))
        elif planned[addr] != value:
            problems.append('wrong write %06X: plan %02X vs original %02X' % (addr, planned[addr], value))
    redundant = 0
    entry_ram = facts.get('entry_ram')
    for addr, value in planned.items():
        if addr not in traced:
            # A diff-based trace cannot see a store of the value already present.
            # Such a plan write is harmless; a store of a different value is not.
            if entry_ram is not None and 0xFF0000 <= addr <= 0xFFFFFF and entry_ram[addr & 0xFFFF] == value:
                redundant += 1
            else:
                problems.append('extra write %06X=%02X (original did not change it)' % (addr, value))
    if redundant:
        problems.append('note: %d plan writes store the value RAM already held (harmless)' % redundant)
    final = dict(entry_regs)
    final.update(plan.registers)
    for name, (before, after) in facts['changed_registers'].items():
        if final.get(name) != after:
            problems.append('register %s: plan %08X vs original %08X' % (name, final.get(name, 0), after))
    for name, value in plan.registers.items():
        if name not in facts['changed_registers'] and value != entry_regs[name]:
            problems.append('register %s: plan changes it to %08X, original left %08X' % (name, value, entry_regs[name]))
    return problems


def report(facts, *, path=True):
    lines = ['entry: %06X   exit: %06X   last_pc: %06X' % (facts['entry'], facts['exit_pc'], facts['last_pc']),
             'instructions: %d   cycles: %d   master_ticks: %d   interrupts: %d' % (
                 facts['instructions'], facts['cycles'], facts['master_ticks'], facts['interrupts_during_trace']),
             'stack_delta: %+d   caller_return_slot_at_entry: %06X' % (facts['stack_delta'], facts['caller_return_slot_at_entry']),
             'changed_registers: ' + ', '.join('%s %08X->%08X' % (k, a, b) for k, (a, b) in facts['changed_registers'].items()),
             'ccr_exit: ' + ' '.join('%s=%d' % (k, int(v)) for k, v in facts['ccr_exit'].items())
             + '   last_changed_step: ' + ' '.join('%s:%s' % (k, v) for k, v in facts['ccr_last_changed_step'].items())]
    parts = []
    for a, v in facts['ram_writes_final'].items():
        count = facts['ram_write_counts'][a]
        parts.append('%06X=%02X' % (a, v) + ('(x%d)' % count if count > 1 else ''))
    lines.append('ram_writes: ' + ', '.join(parts))
    if facts['calls']:
        items = []
        for c in facts['calls']:
            if 'callee' in c:
                items.append('%06X -> %06X (slot %06X = %06X, depth %d)' % (c['site'], c['callee'], c['return_slot'], c['return_pc'], c['depth']))
            else:
                items.append('rts %06X -> %06X (depth %d)' % (c['site'], c['return_to'], c['depth']))
        lines.append('calls: ' + '; '.join(items))
    if path:
        lines.append('path:')
        for s in facts['steps']:
            flag = '' if s['taken'] is None else (' [taken]' if s['taken'] else ' [not taken]')
            ch = ' '.join('%s=%X' % (k, v) for k, v in s['changed'].items() if k != 'sr')
            w = ' '.join('%06X=%02X' % (a, v) for a, v in s['writes'])
            lines.append(('  %3d %06X %-34s %3dcy ccr=%02X%s %s %s' % (
                s['n'], s['pc'], s['text'], s['cycles'], s['sr'], flag, ch, w)).rstrip())
    return '\n'.join(lines)


if __name__ == '__main__':
    state = open(sys.argv[1], 'rb').read()
    entry = int(sys.argv[2], 16) if len(sys.argv) > 2 else None
    stop = int(sys.argv[3], 16) if len(sys.argv) > 3 else None
    print(report(trace(state, entry=entry, stop_pc=stop)))
