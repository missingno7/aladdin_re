"""First bounded Aladdin recovery experiment.

The code in this module is deliberately narrow.  It owns one observed clear
routine and, optionally, one adjacent caller.  It never asks the original
CPU to calculate an answer: an unsupported activation is handed back before
any candidate mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, field


LEAF_ENTRY = 0x1AE372
LEAF_LAST_PC = 0x1AE39E
CALLER_ENTRY = 0x1AD0FC
CALLER_LAST_PC = 0x1AD136
ROM_SHA256 = "a3779fc77994780e80d05bb557f800110d0398d34b951baa8c0a14910014ded3"


class UnsupportedCandidate(RuntimeError):
    """The current stopped machine is outside this small candidate domain."""


@dataclass(frozen=True)
class AtomicPlan:
    cycles: int
    instructions: int
    writes: tuple[tuple[int, int], ...]
    registers: dict[str, int]
    last_pc: int


def _logic_sr(sr: int, value: int, width: int) -> int:
    """68000 MOVE/CLR logic flags, preserving X and the non-CCR bits."""
    mask = (1 << (width * 8)) - 1
    value &= mask
    out = sr & ~0x0F  # X is bit 4 and is deliberately retained.
    if value == 0:
        out |= 0x04
    if value & (1 << (width * 8 - 1)):
        out |= 0x08
    return out


@dataclass
class Candidate:
    """Dispatch either the semantic leaf or its directly composed caller.

    ``Machine.atomic`` is the admission point.  It must return ``False`` with
    the machine unchanged when the scheduler cannot admit the whole plan.
    """

    name: str = "leaf"
    stats: dict[str, int] = field(default_factory=lambda: {
        "gates": 0, "candidate_hits": 0, "fallbacks": 0,
        "leaf_hits": 0, "caller_hits": 0, "direct_python_calls": 0,
        "replaced_m68k_instructions": 0, "charged_m68k_cycles": 0,
    })

    _names = {
        "leaf", "composed",
        "leaf-wrong-store", "leaf-wrong-continuation", "leaf-wrong-timing",
        "composed-wrong-store", "composed-wrong-continuation", "composed-wrong-timing",
        "mutant-result", "mutant-continuation", "mutant-timing",
    }

    def __post_init__(self):
        if self.name not in self._names:
            raise ValueError(f"Unknown recovery candidate: {self.name}")

    @property
    def is_composed(self) -> bool:
        return self.name.startswith("composed")

    @property
    def mutation(self) -> str | None:
        if self.name.startswith("mutant-"):
            return {"mutant-result": "store", "mutant-continuation": "continuation",
                    "mutant-timing": "timing"}[self.name]
        if "-wrong-" not in self.name:
            return None
        return self.name.rsplit("-wrong-", 1)[1]

    @property
    def gate_pcs(self) -> tuple[int, ...]:
        # The composed form reaches the leaf directly inside the caller.  A
        # separate leaf gate stays armed for other callers in the same replay.
        return (CALLER_ENTRY, LEAF_ENTRY) if self.is_composed else (LEAF_ENTRY,)

    def arm(self, machine) -> None:
        if machine.rom_sha256 != ROM_SHA256:
            raise UnsupportedCandidate("recovery candidate requires the verified USA ROM SHA-256")
        machine.gates(list(self.gate_pcs))
        machine.candidate_identity = self.name

    def on_gate(self, machine, target: int) -> bool:
        """Try a candidate at the current gate; otherwise retire one original instruction.

        Returning ``True`` means the staged native operation was admitted and
        completed.  ``False`` means the original instruction was retired from
        an untouched entry state.
        """
        entry = machine.info["pc"]
        if type(target) is not int or target < machine.info["tick"]:
            raise ValueError("Recovery dispatch needs the scheduler master-tick deadline")
        if entry not in self.gate_pcs:
            raise ValueError("Recovery dispatch does not match the stopped PC")
        self.stats["gates"] += 1
        try:
            registers = machine.registers()
            if entry == CALLER_ENTRY and self.is_composed:
                plan = self._caller_plan(machine, registers)
            elif entry == LEAF_ENTRY:
                plan = self._leaf_plan(machine, registers)
            else:
                raise UnsupportedCandidate("caller is only owned by the composed candidate")
            plan = self._mutate(plan)
            accepted = machine.atomic(
                cycles=plan.cycles,
                instructions=plan.instructions,
                writes=list(plan.writes),
                registers=plan.registers,
                last_pc=plan.last_pc,
                target=target,
            )
        except UnsupportedCandidate:
            accepted = False
        if accepted:
            self.stats["candidate_hits"] += 1
            self.stats["replaced_m68k_instructions"] += plan.instructions
            self.stats["charged_m68k_cycles"] += plan.cycles
            if entry == LEAF_ENTRY:
                self.stats["leaf_hits"] += 1
            else:
                self.stats["caller_hits"] += 1
                # The caller plan evaluates the selected leaf directly rather
                # than making a second native gate round-trip.
                self.stats["direct_python_calls"] += 1
            return True
        # Atomic admission is specified to leave state unchanged on refusal.
        # Bypass exactly the stopped opcode; the remaining original body is
        # then responsible for its own timing, stack, and return behavior.
        self.stats["fallbacks"] += 1
        machine.gate(entry, bypass_once=True)
        machine.run(instructions=1)
        return False

    @staticmethod
    def _address(value: int, size: int) -> int:
        if type(value) is not int or type(size) is not int or size <= 0:
            raise UnsupportedCandidate("invalid candidate address span")
        if not 0xFF0000 <= value <= 0xFFFFFF or value + size - 1 > 0xFFFFFF:
            raise UnsupportedCandidate("candidate touches noncanonical work RAM")
        return value

    @classmethod
    def _spans_disjoint(cls, spans: list[tuple[str, int, int]]) -> None:
        checked = [(name, cls._address(start, size), size) for name, start, size in spans]
        for index, (name, start, size) in enumerate(checked):
            for other_name, other_start, other_size in checked[index + 1:]:
                if start < other_start + other_size and other_start < start + size:
                    raise UnsupportedCandidate(f"candidate aliases {name} and {other_name}")

    @staticmethod
    def _bytes(address: int, value: int, size: int) -> tuple[tuple[int, int], ...]:
        return tuple((address + index, (value >> (8 * (size - index - 1))) & 0xFF)
                     for index in range(size))

    @classmethod
    def _read(cls, machine, address: int, size: int) -> int:
        address = cls._address(address, size)
        return int.from_bytes(machine.peek_ram(address & 0xFFFF, size), "big")

    @classmethod
    def _read_source_byte(cls, machine, address: int) -> tuple[int, bool]:
        """Read caller script input from immutable ROM or guarded work RAM."""
        if type(address) is not int:
            raise UnsupportedCandidate("invalid script source address")
        if 0 <= address <= 0x3fffff:
            try:
                return machine.peek_rom(address, 1)[0], False
            except ValueError as error:
                raise UnsupportedCandidate("script source lies beyond the cartridge") from error
        if 0xff0000 <= address <= 0xffffff:
            return cls._read(machine, address, 1), True
        raise UnsupportedCandidate("script source is neither immutable ROM nor work RAM")

    @classmethod
    def _leaf_effects(cls, machine, registers: dict[str, int], *, entry_sp: int) -> tuple[int, int, tuple[tuple[int, int], ...], int]:
        """Return cycle/instruction/write/return-PC facts for 1AE372.

        ``entry_sp`` is the A7 value visible to the leaf.  It may be the
        caller's freshly pushed BSR frame rather than the outer activation's
        original A7.
        """
        a1, a6, d0 = registers["a1"], registers["a6"], registers["d0"]
        count_address, pointer_address = cls._address(a1 + 41, 1), cls._address(a1 + 42, 4)
        count = cls._read(machine, count_address, 1)
        pointer = cls._read(machine, pointer_address, 4)
        stack_base = cls._address(entry_sp - 6, 10)
        if pointer:
            length = count + 1
            cls._spans_disjoint([
                ("record", a1, 50), ("buffer", pointer, length), ("leaf stack", stack_base, 10),
            ])
        else:
            length = 0
            cls._spans_disjoint([("record", a1, 50), ("leaf stack", stack_base, 10)])
        writes = list(cls._bytes(entry_sp - 4, a6, 4))
        writes.extend(cls._bytes(entry_sp - 6, d0, 2))
        if pointer:
            writes.extend(cls._bytes(a1 + 42, 0, 4))
            writes.extend(cls._bytes(a1 + 46, 0, 4))
            writes.extend(cls._bytes(a1 + 41, 0, 1))
            writes.extend((pointer + offset, 0) for offset in range(length))
            return 178 + 22 * length, 13 + 2 * length, tuple(writes), pointer
        return 96, 8, tuple(writes), pointer

    def _leaf_plan(self, machine, registers: dict[str, int]) -> AtomicPlan:
        a7, d0, sr = registers["a7"], registers["d0"], registers["sr"]
        self._address(a7, 4)
        cycles, instructions, writes, _ = self._leaf_effects(machine, registers, entry_sp=a7)
        return_pc = self._read(machine, a7, 4)
        return AtomicPlan(
            cycles=cycles,
            instructions=instructions,
            writes=writes,
            registers={"d0": d0, "pc": return_pc, "a7": a7 + 4, "sr": _logic_sr(sr, d0, 2)},
            last_pc=LEAF_LAST_PC,
        )

    def _caller_plan(self, machine, registers: dict[str, int]) -> AtomicPlan:
        """The observed direct 1AD0FC -> 1AE372 path, with a direct Python call."""
        a0, a1, a2, a7, d0, sr = (registers[key] for key in ("a0", "a1", "a2", "a7", "d0", "sr"))
        source_address = a2 + 1
        source_byte, source_is_ram = self._read_source_byte(machine, source_address)
        if source_byte:
            raise UnsupportedCandidate("1AD0FC nonzero script path calls unresolved 1ABE6E")
        if self._read(machine, self._address(a1 + 60, 1), 1) & 0x04:
            raise UnsupportedCandidate("1AD0FC bit-two path calls unresolved 1ABE6E")
        outer_return = self._read(machine, self._address(a7, 4), 4)
        return_override = self._read(machine, 0xFF7D9E, 4)
        leaf_registers = dict(registers)
        leaf_registers["d0"] = (d0 & 0xFFFFFF00) | source_byte
        leaf_cycles, leaf_instructions, leaf_writes, buffer = self._leaf_effects(
            machine, leaf_registers, entry_sp=a7 - 4)
        count = self._read(machine, self._address(a1 + 41, 1), 1)
        link = self._read(machine, self._address(a1 + 62, 4), 4)
        spans = [
            ("caller record", a1, 66), ("leaf stack and outer return", a7 - 10, 14),
            ("return override", 0xFF7D9E, 4),
        ]
        if source_is_ram:
            spans.append(("script byte", source_address, 1))
        if link:
            spans.append(("linked record", link + 60, 6))
        if buffer:
            spans.append(("leaf buffer", buffer, count + 1))
        self._spans_disjoint(spans)
        writes = [(a1, 0)]
        writes.extend(self._bytes(a7 - 4, 0x1AD118, 4))
        writes.extend(leaf_writes)
        if link:
            linked_flag = self._read(machine, link + 60, 1)
            writes.extend(self._bytes(a7 - 4, a0, 4))
            writes.extend(self._bytes(link + 62, 0, 4))
            writes.append((link + 60, linked_flag & ~0x04))
            post_cycles, post_instructions = 152, 9
        else:
            post_cycles, post_instructions = 70, 4
        writes.extend(self._bytes(a7, return_override, 4))
        # Keep the read visible in the plan: an odd/unmapped stack pointer is
        # rejected above, but the source return is intentionally overwritten.
        del outer_return
        return AtomicPlan(
            cycles=80 + leaf_cycles + post_cycles,
            instructions=7 + leaf_instructions + post_instructions,
            writes=tuple(writes),
            registers={
                "d0": leaf_registers["d0"], "a2": a2 + 2,
                "a7": a7 + 4, "pc": return_override,
                "sr": _logic_sr(sr, return_override, 4),
            },
            last_pc=CALLER_LAST_PC,
        )

    def _mutate(self, plan: AtomicPlan) -> AtomicPlan:
        mutation = self.mutation
        if mutation is None:
            return plan
        if mutation == "store":
            writes = list(plan.writes)
            if self.is_composed:
                # The selected caller's CLR.B (A1) is permanent output.
                writes[0] = (writes[0][0], 1)
            elif len(writes) > 6:
                # Save slots occupy 0..5.  This is the high byte of the
                # cleared A1+0x2A pointer, a permanent leaf result.
                writes[6] = (writes[6][0], 1)
            else:
                # A null leaf has no buffer/record clear.  Alter a final
                # architectural result rather than a transient stack byte.
                registers = dict(plan.registers)
                registers["d0"] ^= 1
                return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc)
            return AtomicPlan(plan.cycles, plan.instructions, tuple(writes), dict(plan.registers), plan.last_pc)
        if mutation == "continuation":
            registers = dict(plan.registers)
            registers["pc"] = (registers["pc"] + 2) & 0xFFFFFF
            return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc)
        if mutation == "timing":
            return AtomicPlan(plan.cycles + 2, plan.instructions, plan.writes, dict(plan.registers), plan.last_pc)
        raise AssertionError(f"Unhandled mutation: {mutation}")
