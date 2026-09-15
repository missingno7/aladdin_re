"""Verification-side observation of the original: its VDP port writes, instruction by instruction.

The native machine exposes no VRAM, so a recovered step's video output is
proven by single-stepping the oracle over the same step and recording every
word the original moves into C00000 / C00004.  Only ``move`` instructions
reach the ports in this game; their source operands are evaluated from the
registers and memory just before the instruction executes.
"""
from __future__ import annotations
import re

_SIZES = {'b': 1, 'w': 2, 'l': 4}
_MD = None


def _disassembler():
    global _MD
    if _MD is None:
        import capstone
        _MD = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000)
    return _MD


def _split(op_str: str) -> list:
    parts, depth, current = [], 0, ''
    for ch in op_str:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(current.strip())
            current = ''
        else:
            current += ch
    parts.append(current.strip())
    return parts


def _hex(text: str) -> int:
    sign = -1 if text.startswith('-') else 1
    return sign * int(text.lstrip('-').lstrip('$'), 16)


_ABS = re.compile(r'^\$([0-9a-f]+)\.([wl])$')
_IND = re.compile(r'^(-?)\((a\d)\)(\+?)$')
_DISP = re.compile(r'^(-?\$[0-9a-f]+)?\((a\d)\)$')
_INDEX = re.compile(r'^(-?\$[0-9a-f]+)?\((a\d), ([ad]\d)\.([wl])\)$')


def _signed(value: int, size: int) -> int:
    bits = 8 * size
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def effective_address(regs: dict, operand: str, size: int):
    """The memory address an operand names, or None for a register or immediate."""
    m = _ABS.match(operand)
    if m:
        value = int(m[1], 16)
        return (value | 0xFF0000) if m[2] == 'w' and value >= 0x8000 else value
    m = _IND.match(operand)
    if m:
        base = regs[m[2]]
        return (base - size if m[1] else base) & 0xFFFFFF
    m = _DISP.match(operand)
    if m:
        return (regs[m[2]] + (_hex(m[1]) if m[1] else 0)) & 0xFFFFFF
    m = _INDEX.match(operand)
    if m:
        index = _signed(regs[m[3]], 2 if m[4] == 'w' else 4)
        return (regs[m[2]] + (_hex(m[1]) if m[1] else 0) + index) & 0xFFFFFF
    return None


def read_bus(machine, address: int, size: int) -> int:
    if address < 0x400000:
        return int.from_bytes(machine.peek_rom(address, size), 'big')
    if address >= 0xFF0000:
        return int.from_bytes(machine.peek_ram(address & 0xFFFF, size), 'big')
    raise ValueError(f'source operand outside ROM and work RAM: {address:06X}')


def operand_value(machine, regs: dict, operand: str, size: int) -> int:
    mask = (1 << (8 * size)) - 1
    if re.fullmatch(r'[ad]\d', operand):
        return regs[operand] & mask
    if operand.startswith('#'):
        return _hex(operand[1:]) & mask
    address = effective_address(regs, operand, size)
    if address is None:
        raise ValueError(f'unsupported source operand {operand!r}')
    return read_bus(machine, address, size)


def run_to_exits(machine, exits, target: int) -> None:
    """Run the oracle until its PC is one of ``exits``, passing through any other gate it meets."""
    while True:
        if machine.run(target=target) != 'gate':
            raise RuntimeError('the oracle reached the tick limit before ' + ', '.join(f'{e:06X}' for e in exits))
        pc = machine.info['pc']
        if pc in exits:
            return
        machine.gate(pc, bypass_once=True)


def trace_port_writes(machine, exits, *, limit: int = 2_000_000) -> list:
    """Single-step the oracle until its PC is one of ``exits``; return the VDP port words written.

    A write is recorded only when its instruction completes: an interrupt
    taken in front of it (the machine parks on the handler's gate without
    executing) or a full-FIFO stall (no progress at the same PC) does not
    count it, and the instruction is evaluated again when the PC returns.
    """
    md = _disassembler()
    writes = []
    while True:
        info = machine.info
        pc = info['pc']
        if pc in exits:
            return writes
        code = machine.peek_rom(pc, 10) if pc < 0x400000 else machine.peek_ram(pc & 0xFFFF, 10)
        insn = next(iter(md.disasm(code, pc)), None)
        pending = None
        if insn is not None and insn.mnemonic in ('move.b', 'move.w', 'move.l'):
            size = _SIZES[insn.mnemonic[-1]]
            source, destination = _split(insn.op_str)
            regs = machine.registers()
            address = effective_address(regs, destination, size)
            if address is not None and 0xC00000 <= address <= 0xC00007:
                value = operand_value(machine, regs, source, size)
                port = 'data' if address & 4 == 0 else 'control'
                pending = [(port, value >> 16), (port, value & 0xFFFF)] if size == 4 else [(port, value & 0xFFFF)]
        machine.run(instructions=1)
        stalls = 0
        while machine.info['m68k_instructions'] == info['m68k_instructions']:
            if machine.info['pc'] != pc:
                pending = None          # an interrupt was taken first: the instruction has not executed
                break
            try:
                machine.gate(pc, bypass_once=True)     # parked on its own gate: pass it once
            except Exception:
                stalls += 1                            # a full-FIFO stall: wait for the write to go through
                if stalls > 100000:
                    raise RuntimeError(f'the oracle makes no progress at {pc:06X}')
            machine.run(instructions=1)
        if pending and machine.info['m68k_instructions'] != info['m68k_instructions']:
            writes.extend(pending)
        limit -= 1
        if not limit:
            raise RuntimeError('port trace did not reach ' + ', '.join(f'{e:06X}' for e in exits))
