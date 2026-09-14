"""pathfacts: derive compact machine facts by single-stepping the ORIGINAL machine.

Python-side, zero native changes.  Facts: executed PCs and disassembly,
per-instruction cycles, RAM writes (final residue and write counts), register
deltas, CCR/X history, stack delta, return PC, calls/returns, branch decisions.

``Tracer`` steps a live machine the caller owns (the census uses it during a
replay); ``trace`` opens its own machine on a snapshot.  ``path_signature``
reduces a fact report to the behavior identity used to group occurrences:
the executed path outside native sound calls and the depth-zero call
targets.  Cycles are implied by the path; the exit PC, the exit CCR, the
changed registers and the writes are facets kept beside it.
"""
import ctypes
import hashlib
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
# Native routines a seam may call: bounded, self-contained, return to their
# caller, and touch devices the plan itself may not.  A JSR to one of these is
# collapsed to a NATIVE segment; the caller's code around it stays PYTHON.
NATIVE_ENTRIES = {0x1E58B8: 'sound-request', 0x1E58F4: 'sound-fixed-helper', 0x1E589A: 'sound-flush',
                  0x1B2650: 'vdp-tile-upload'}
SOUND_ENTRIES = NATIVE_ENTRIES  # historical name
STACK_WINDOW = (128, 8)  # bytes below and above the entry A7 that belong to the activation's stack


def ram_bytes(machine):
    return ctypes.string_at(machine.ram_address, 65536)


def _disasm_code(code, pc):
    for insn in _MD.disasm(code, pc):
        return (insn.mnemonic + ' ' + insn.op_str).strip(), insn.size
    if len(code) < 2:
        return '??', 2
    return 'dc.w $%04X' % int.from_bytes(code[:2], 'big'), 2


def disasm(rom, ram, pc):
    if pc < len(rom):
        return _disasm_code(rom[pc:pc + 10], pc)
    if 0xFF0000 <= pc <= 0xFFFFFF and ram:
        return _disasm_code(ram[pc & 0xFFFF:(pc & 0xFFFF) + 10], pc)
    return '??', 2


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


class Tracer:
    """Single-step a live ORIGINAL machine from its current PC and record facts.

    The caller owns the machine and decides when to stop (``at_exit`` for the
    caller return or a stop PC, a deadline, a cap).  With ``track_ram`` off no
    RAM is copied per step: writes are not recorded, which is enough for a
    path signature and about twice as fast.  A gate stop that executed nothing
    is bypassed once and retried, so gates armed inside the region are
    harmless to the trace.
    """

    def __init__(self, machine, rom, *, track_ram=True, detail=True):
        self.machine, self.rom, self.track_ram, self.detail = machine, rom, track_ram, detail
        self.regs, self.info = machine.registers(), dict(machine.info)
        self.ram = ram_bytes(machine) if track_ram else None
        self.entry_regs, self.entry_info, self.entry_ram = dict(self.regs), dict(self.info), self.ram
        self.entry = self.regs['pc']
        self.entry_a7 = self.regs['a7']
        self.caller_return = int.from_bytes(machine.peek_ram(self.entry_a7 & 0xFFFF, 4), 'big') & 0xFFFFFF
        self.steps, self.writes, self.write_counts, self.calls, self.stack = [], OrderedDict(), {}, [], []
        self.ccr_last = {name: None for name, _ in CCR}
        self.interrupts, self.last_pc, self.n = 0, None, 0

    def at_exit(self, stop_pc=None):
        if self.n == 0:
            return False
        pc = self.regs['pc']
        if stop_pc is not None:
            return pc == stop_pc
        return pc == self.caller_return and self.regs['a7'] == self.entry_a7 + 4

    def _code_at(self, pc):
        if pc < len(self.rom):
            return self.rom[pc:pc + 10]
        if 0xFF0000 <= pc <= 0xFFFFFF:
            if self.ram is not None:
                return self.ram[pc & 0xFFFF:(pc & 0xFFFF) + 10]
            offset = pc & 0xFFFF
            return self.machine.peek_ram(offset, min(10, 0x10000 - offset))
        return b''

    def step(self):
        m, regs, info, ram = self.machine, self.regs, self.info, self.ram
        pc = regs['pc']
        text, size = _disasm_code(self._code_at(pc), pc)
        before = info['m68k_instructions']
        m.run(instructions=1)
        new_info = dict(m.info)
        if new_info['m68k_instructions'] == before:
            # A gate armed on this PC stopped the machine before executing it.
            m.gate(pc, bypass_once=True)
            m.run(instructions=1)
            new_info = dict(m.info)
        new_regs = m.registers()
        new_ram = ram_bytes(m) if self.track_ram else None
        cycles = new_info['m68k_cycles'] - info['m68k_cycles']
        if new_info['vblanks'] != info['vblanks']:
            self.interrupts += 1
        changed = {k: (regs[k], new_regs[k]) for k in REGS if regs[k] != new_regs[k] and k != 'pc'}
        step_writes = []
        if self.track_ram and new_ram != ram:
            for base in range(0, 65536, 256):
                if new_ram[base:base + 256] != ram[base:base + 256]:
                    for i in range(base, base + 256):
                        if new_ram[i] != ram[i]:
                            addr = 0xFF0000 + i
                            step_writes.append((addr, new_ram[i]))
                            self.writes[addr] = new_ram[i]
                            self.write_counts[addr] = self.write_counts.get(addr, 0) + 1
        mnemonic = text.split(' ')[0].split('.')[0]
        taken = None
        if mnemonic in _BRANCHES or mnemonic.startswith('db'):
            taken = new_regs['pc'] != pc + size
        if mnemonic in ('bsr', 'jsr'):
            self.calls.append({'site': pc, 'callee': new_regs['pc'], 'return_slot': new_regs['a7'],
                               'return_pc': pc + size, 'depth': len(self.stack), 'step': self.n})
            self.stack.append(pc + size)
        elif mnemonic == 'rts':
            self.calls.append({'site': pc, 'return_to': new_regs['pc'], 'depth': len(self.stack) - 1, 'step': self.n})
            if self.stack:
                self.stack.pop()
        if 'sr' in changed:
            for name, bit in CCR:
                if (changed['sr'][0] ^ changed['sr'][1]) & bit:
                    self.ccr_last[name] = self.n
        record = {'n': self.n, 'pc': pc, 'text': text, 'cycles': cycles, 'taken': taken,
                  'changed': {k: v[1] for k, v in changed.items()},
                  'writes': step_writes, 'sr': new_regs['sr'] & 0x1F}
        if self.detail:
            self.steps.append(record)
        self.last_pc = pc
        self.n += 1
        self.regs, self.info, self.ram = new_regs, new_info, new_ram
        return record

    def facts(self):
        exit_regs, exit_info = dict(self.regs), dict(self.info)
        changed_regs = {k: (self.entry_regs[k], exit_regs[k]) for k in REGS if self.entry_regs[k] != exit_regs[k]}
        return {
            'entry': self.entry, 'exit_pc': exit_regs['pc'], 'last_pc': self.last_pc,
            'instructions': exit_info['m68k_instructions'] - self.entry_info['m68k_instructions'],
            'cycles': exit_info['m68k_cycles'] - self.entry_info['m68k_cycles'],
            'master_ticks': exit_info['tick'] - self.entry_info['tick'],
            'interrupts_during_trace': self.interrupts,
            'stack_delta': exit_regs['a7'] - self.entry_regs['a7'],
            'caller_return_slot_at_entry': self.caller_return,
            'entry_registers': self.entry_regs,
            'entry_ram': self.entry_ram,
            'changed_registers': changed_regs,
            'ccr_exit': {name: bool(exit_regs['sr'] & bit) for name, bit in CCR},
            'ccr_last_changed_step': self.ccr_last,
            'ram_writes_final': self.writes, 'ram_write_counts': self.write_counts,
            'calls': self.calls, 'steps': self.steps,
        }


def trace(state, *, entry=None, stop_pc=None, max_instructions=20000, rom=None, detail=True, track_ram=True):
    rom = rom or read_rom()
    with Machine(rom) as m:
        m.restore(state)
        m.gates([])
        tracer = Tracer(m, rom, track_ram=track_ram, detail=detail)
        entry = tracer.entry if entry is None else entry
        if tracer.entry != entry:
            raise ValueError('state stands at %06X, not %06X' % (tracer.entry, entry))
        for _ in range(max_instructions):
            if tracer.at_exit(stop_pc):
                break
            tracer.step()
        else:
            raise RuntimeError('trace exceeded instruction cap before reaching its stop')
        return tracer.facts()


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


def path_signature(facts):
    """Reduce a fact report to the behavior identity and its facets.

    Identity: sha1 of the executed PCs in the python segments and the
    depth-zero call targets (native callees marked with ``*``).  Facets beside
    it: exit PC (the caller's return site), instructions, cycles, exit CCR,
    the native-call shape, the set of registers whose value differs at exit,
    and the record/global writes
    outside the activation's stack window and outside native segments (empty
    when RAM was not tracked).  Changed registers and writes are value-blind,
    so they are labels rather than identity.
    """
    segments = split_at_native(facts)
    digest = hashlib.sha1()
    writes = set()
    record = facts['entry_registers']['a1'] & 0xFFFFFF
    sp = facts['entry_registers']['a7']
    for segment in segments:
        if segment['kind'] != 'python':
            continue
        for step in facts['steps'][segment['first_step']:segment['last_step'] + 1]:
            digest.update(step['pc'].to_bytes(4, 'big'))
            for address, _ in step['writes']:
                if sp - STACK_WINDOW[0] <= address <= sp + STACK_WINDOW[1]:
                    continue
                writes.add('rec+%02X' % (address - record) if record <= address < record + 66 else '%06X' % address)
    calls = ['%06X%s' % (c['callee'], '*' if c['callee'] in SOUND_ENTRIES else '')
             for c in facts['calls'] if 'callee' in c and c['depth'] == 0]
    natives = ['%06X' % c['callee'] for c in facts['calls'] if 'callee' in c and c['callee'] in SOUND_ENTRIES]
    ccr = sum(bit for name, bit in CCR if facts['ccr_exit'][name])
    return {'exit': '%06X' % facts['exit_pc'], 'path': digest.hexdigest()[:16], 'calls': calls,
            'changed': sorted(k for k in facts['changed_registers'] if k not in ('pc', 'sr')),
            'instructions': facts['instructions'], 'cycles': facts['cycles'], 'ccr': ccr,
            'natives': natives, 'writes': sorted(writes)}


def signature_key(signature):
    """The identity string of a path signature: the path and its depth-zero calls.

    The exit PC is the caller's return site, a context facet: one leaf called
    from five sites is one behavior.  The changed-register set is a facet
    too: like a RAM diff it is value-blind (a register rewritten with its old
    value is not "changed"), so one path can show different sets.
    """
    return '%s:%s' % (signature['path'], ','.join(signature['calls']))


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
    if facts['steps']:
        signature = path_signature(facts)
        lines.append('signature: exit %s path %s calls %s changed %s ccr %02X' % (
            signature['exit'], signature['path'], ' '.join(signature['calls']) or '-',
            ' '.join(signature['changed']) or '-', signature['ccr']))
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
