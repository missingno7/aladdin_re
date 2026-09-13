"""Project-owned gate dispatch and qualification policy for recovered Aladdin."""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib

from .recovered import (AtomicPlan, UnsupportedCandidate, LEAF_ENTRY, PAIR_ENTRY, CALLER_ENTRY,
                        INIT_ENTRY, FINISH_ENTRY, ROM_SHA256, clear_auxiliary_buffer,
                        COUNTED_REPLACE_ENTRY, REPLACE_ENTRY, clear_object_pair, detach_object,
                        initialize_object, finish_object, replace_object, TRANSITION_ENTRY,
                        SOUND_RETURN, begin_object_transition, finish_object_transition)


def validate_transition(value):
    """One Aladdin sound-frame contract; no arbitrary resume addresses or stack."""
    if not isinstance(value, dict) or set(value) != {"contract", "entry_tick", "outer_sp", "frame_sha256"}:
        raise ValueError("Invalid object-transition metadata")
    if value["contract"] != "object-sound-v1":
        raise ValueError("Unsupported object-transition contract")
    if type(value["entry_tick"]) is not int or not 0 <= value["entry_tick"] < 2**64:
        raise ValueError("Invalid transition entry tick")
    sp = value["outer_sp"]
    if type(sp) is not int or sp & 1 or not 0xFF001C <= sp <= 0xFFFFFC:
        raise ValueError("Invalid transition stack")
    digest = value["frame_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid transition frame digest")
    return dict(value)


def transition_frame(machine, sp):
    # Sound argument, five saved registers and the outer return slot. The
    # callee return slot below this is reused by the second original JSR.
    return hashlib.sha256(machine.peek_ram((sp - 24) & 0xFFFF, 28)).hexdigest()


def check_transition(machine, pending):
    validate_transition(pending)
    if machine.info["tick"] < pending["entry_tick"] or transition_frame(machine, pending["outer_sp"]) != pending["frame_sha256"]:
        raise ValueError("Object-transition activation/frame mismatch")


@dataclass
class Candidate:
    """Dispatch recovered regions and the one concrete object/sound return.

    ``Machine.atomic`` is the admission point.  It must return ``False`` with
    the machine unchanged when the scheduler cannot admit the whole plan.
    """

    name: str = "leaf"
    stats: dict[str, int | dict[str, int]] = field(default_factory=lambda: {
        "gates": 0, "candidate_hits": 0, "fallbacks": 0,
        "leaf_hits": 0, "pair_hits": 0, "caller_hits": 0, "direct_python_calls": 0,
        "initializer_hits": 0, "finish_hits": 0,
        "replace_hits": 0, "counted_replace_hits": 0,
        "carrier_entries": 0, "carrier_completed": 0, "legacy_entries": 0, "legacy_returns": 0,
        "local_fallbacks": 0, "foreign_returns": 0,
        "replaced_m68k_instructions": 0, "charged_m68k_cycles": 0, "fallback_reasons": {},
    })

    _names = {
        "leaf", "pair", "init", "finish", "replace", "composed", "carrier",
        "carrier-mutant-result", "carrier-mutant-continuation", "carrier-mutant-timing",
        "mutant-result", "mutant-continuation", "mutant-timing",
    }

    def __post_init__(self):
        if self.name not in self._names:
            raise ValueError(f"Unknown recovery candidate: {self.name}")

    @property
    def is_composed(self) -> bool:
        return self.name == "composed" or self.is_carrier

    @property
    def is_carrier(self) -> bool:
        return self.name == "carrier" or self.name.startswith("carrier-mutant-")

    @property
    def mutation(self) -> str | None:
        return {"mutant-result": "store", "mutant-continuation": "continuation",
                "mutant-timing": "timing"}.get(self.name)

    @property
    def gate_pcs(self) -> tuple[int, ...]:
        # The composed form reaches the leaf directly inside the caller.  A
        # separate leaf gate stays armed for other callers in the same replay.
        if self.is_carrier:
            # The 1AF4C6 tail is owned inside this region; the other ten paths
            # still enter via the counted replacement boundary.
            return (TRANSITION_ENTRY, COUNTED_REPLACE_ENTRY, FINISH_ENTRY, CALLER_ENTRY, PAIR_ENTRY, INIT_ENTRY, LEAF_ENTRY)
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
        pending = getattr(machine, "pending_transition", None)
        if pending:
            if not self.is_carrier:
                raise ValueError("A pending object transition requires the carrier candidate")
            check_transition(machine, pending)
        machine.gates([SOUND_RETURN] if pending else list(self.gate_pcs))
        machine.candidate_identity = self.name

    def _transition(self, machine, target):
        self.stats["gates"] += 1
        pending = machine.pending_transition
        regs = machine.registers()
        if pending:
            if regs["pc"] != SOUND_RETURN:
                raise ValueError("Unexpected object-transition gate")
            if regs["a7"] != pending["outer_sp"] - 24:
                self.stats["foreign_returns"] += 1
                machine.gate(SOUND_RETURN, bypass_once=True)
                machine.run(instructions=1)
                return False
            check_transition(machine, pending)
            slot = int.from_bytes(machine.peek_ram((regs["a7"] - 4) & 0xFFFF, 4), "big")
            if slot != SOUND_RETURN:
                raise ValueError("Object-transition return slot mismatch")
        entry_tick = machine.info["tick"]
        try:
            plan, legacy = ((finish_object_transition(machine, regs), False) if pending
                            else begin_object_transition(machine, regs))
            if self.name == "carrier-mutant-result" and not pending:
                writes = list(plan.writes)
                writes[0] = (writes[0][0], writes[0][1] ^ 1)
                plan = AtomicPlan(plan.cycles, plan.instructions, tuple(writes), plan.registers, plan.last_pc, plan.direct_calls)
            if self.name == "carrier-mutant-continuation" and legacy:
                writes = list(plan.writes)
                writes[-1] = (writes[-1][0], writes[-1][1] + 2)  # Guest return 1AF492 -> 1AF494.
                plan = AtomicPlan(plan.cycles, plan.instructions, tuple(writes), plan.registers, plan.last_pc, plan.direct_calls)
            if self.name == "carrier-mutant-timing" and not pending:
                plan = AtomicPlan(plan.cycles + 2, plan.instructions, plan.writes, plan.registers, plan.last_pc, plan.direct_calls)
            accepted = machine.atomic(target=target, cycles=plan.cycles, instructions=plan.instructions,
                                      writes=list(plan.writes), registers=plan.registers, last_pc=plan.last_pc)
            reason = "scheduler admission"
        except UnsupportedCandidate as error:
            accepted, reason = False, f"unsupported domain: {error}"
        if accepted:
            self.stats["candidate_hits"] += 1
            self.stats["replaced_m68k_instructions"] += plan.instructions
            self.stats["charged_m68k_cycles"] += plan.cycles
            self.stats["direct_python_calls"] += plan.direct_calls
            if not pending:
                self.stats["carrier_entries"] += 1
            else:
                self.stats["legacy_returns"] += 1
            if legacy:
                machine.pending_transition = {"contract": "object-sound-v1", "entry_tick": entry_tick,
                                              "outer_sp": regs["a7"], "frame_sha256": transition_frame(machine, regs["a7"])}
                self.stats["legacy_entries"] += 1
            else:
                machine.pending_transition = None
                self.stats["carrier_completed"] += 1
            self.arm(machine)
            return True
        self.stats["fallbacks"] += 1
        reasons = self.stats["fallback_reasons"]
        reasons[reason] = reasons.get(reason, 0) + 1
        if pending:
            # Keep the recovered prefix. Only the original suffix resumes here.
            self.stats["local_fallbacks"] += 1
            self.stats["legacy_returns"] += 1
            machine.pending_transition = None
            self.arm(machine)
        machine.gate(regs["pc"], bypass_once=True)
        machine.run(instructions=1)
        return False

    def on_gate(self, machine, target: int) -> bool:
        """Try a candidate at the current gate; otherwise retire one original instruction.

        Returning ``True`` means the staged native operation was admitted and
        completed. ``False`` means execution uses the original instruction at
        the current entry or continuation, preserving any earlier prefix.
        """
        entry = machine.info["pc"]
        if type(target) is not int or target < machine.info["tick"]:
            raise ValueError("Recovery dispatch needs the scheduler master-tick deadline")
        if self.is_carrier and (getattr(machine, "pending_transition", None) or entry == TRANSITION_ENTRY):
            return self._transition(machine, target)
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
