"""Project-owned gate dispatch and qualification policy for recovered Aladdin."""
from __future__ import annotations
from dataclasses import dataclass, field

from .recovered import (AtomicPlan, UnsupportedCandidate, LEAF_ENTRY, PAIR_ENTRY, CALLER_ENTRY,
                        INIT_ENTRY, FINISH_ENTRY, ROM_SHA256, clear_auxiliary_buffer,
                        COUNTED_REPLACE_ENTRY, REPLACE_ENTRY, clear_object_pair, detach_object,
                        initialize_object, finish_object, replace_object)


@dataclass
class Candidate:
    """Dispatch either the semantic leaf or its directly composed caller.

    ``Machine.atomic`` is the admission point.  It must return ``False`` with
    the machine unchanged when the scheduler cannot admit the whole plan.
    """

    name: str = "leaf"
    stats: dict[str, int | dict[str, int]] = field(default_factory=lambda: {
        "gates": 0, "candidate_hits": 0, "fallbacks": 0,
        "leaf_hits": 0, "pair_hits": 0, "caller_hits": 0, "direct_python_calls": 0,
        "initializer_hits": 0, "finish_hits": 0,
        "replace_hits": 0, "counted_replace_hits": 0,
        "replaced_m68k_instructions": 0, "charged_m68k_cycles": 0, "fallback_reasons": {},
    })

    _names = {
        "leaf", "pair", "init", "finish", "replace", "composed",
        "mutant-result", "mutant-continuation", "mutant-timing",
    }

    def __post_init__(self):
        if self.name not in self._names:
            raise ValueError(f"Unknown recovery candidate: {self.name}")

    @property
    def is_composed(self) -> bool:
        return self.name == "composed"

    @property
    def mutation(self) -> str | None:
        return {"mutant-result": "store", "mutant-continuation": "continuation",
                "mutant-timing": "timing"}.get(self.name)

    @property
    def gate_pcs(self) -> tuple[int, ...]:
        # The composed form reaches the leaf directly inside the caller.  A
        # separate leaf gate stays armed for other callers in the same replay.
        if self.is_composed:
            return (COUNTED_REPLACE_ENTRY, REPLACE_ENTRY, FINISH_ENTRY, CALLER_ENTRY, PAIR_ENTRY, INIT_ENTRY, LEAF_ENTRY)
        if self.name == "replace":
            return (COUNTED_REPLACE_ENTRY, REPLACE_ENTRY)
        if self.name == "init":
            return (INIT_ENTRY,)
        if self.name == "finish":
            return (FINISH_ENTRY,)
        return (PAIR_ENTRY,) if self.name == "pair" else (LEAF_ENTRY,)

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
        fallback_reason = "scheduler admission"
        try:
            registers = machine.registers()
            if entry == CALLER_ENTRY and self.is_composed:
                plan = detach_object(machine, registers)
            elif entry in (COUNTED_REPLACE_ENTRY, REPLACE_ENTRY):
                plan = replace_object(machine, registers, increment_total=entry == COUNTED_REPLACE_ENTRY)
            elif entry == INIT_ENTRY:
                plan = initialize_object(machine, registers)
            elif entry == FINISH_ENTRY:
                plan = finish_object(machine, registers)
            elif entry == PAIR_ENTRY:
                plan = clear_object_pair(machine, registers)
            elif entry == LEAF_ENTRY:
                plan = clear_auxiliary_buffer(machine, registers)
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
        except UnsupportedCandidate as error:
            fallback_reason = f"unsupported domain: {error}"
            accepted = False
        if accepted:
            self.stats["candidate_hits"] += 1
            self.stats["replaced_m68k_instructions"] += plan.instructions
            self.stats["charged_m68k_cycles"] += plan.cycles
            if entry == LEAF_ENTRY:
                self.stats["leaf_hits"] += 1
            elif entry == PAIR_ENTRY:
                self.stats["pair_hits"] += 1
            elif entry == INIT_ENTRY:
                self.stats["initializer_hits"] += 1
            elif entry == FINISH_ENTRY:
                self.stats["finish_hits"] += 1
            elif entry in (COUNTED_REPLACE_ENTRY, REPLACE_ENTRY):
                self.stats["replace_hits"] += 1
                self.stats["counted_replace_hits"] += int(entry == COUNTED_REPLACE_ENTRY)
            else:
                self.stats["caller_hits"] += 1
            self.stats["direct_python_calls"] += plan.direct_calls
            return True
        # Atomic admission is specified to leave state unchanged on refusal.
        # Bypass exactly the stopped opcode; the remaining original body is
        # then responsible for its own timing, stack, and return behavior.
        self.stats["fallbacks"] += 1
        reasons = self.stats["fallback_reasons"]
        reasons[fallback_reason] = reasons.get(fallback_reason, 0) + 1
        machine.gate(entry, bypass_once=True)
        machine.run(instructions=1)
        return False

    def _mutate(self, plan: AtomicPlan) -> AtomicPlan:
        mutation = self.mutation
        if mutation is None:
            return plan
        if mutation == "store":
            writes = list(plan.writes)
            if len(writes) > 6:
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
