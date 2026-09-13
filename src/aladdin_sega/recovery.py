"""Project-owned gate dispatch and qualification policy for recovered Aladdin."""
from __future__ import annotations
from dataclasses import dataclass, field

from .boundary import (AtomicPlan, UnsupportedCandidate, LEAF_ENTRY, PAIR_ENTRY, CALLER_ENTRY,
                        INIT_ENTRY, FINISH_ENTRY, ROM_SHA256, clear_auxiliary_buffer,
                        COUNTED_REPLACE_ENTRY, REPLACE_ENTRY, clear_object_pair, detach_object,
                        initialize_object, finish_object, replace_object, TRANSITION_ENTRY,
                        SOUND_RETURN, begin_object_transition, finish_object_transition,
                        COLLECTION_ROUTES, COLLECTION_DISPATCH_ENTRY, begin_collection_dispatch,
                        dispatch_plan_view, CONTACT_ENTRY, CONTACT_DISPATCH_ENTRY, begin_contact_dispatch,
                        begin_contact_dispatch_sound, finish_contact_dispatch_sound, begin_contact,
                        begin_contact_sound, finish_contact_sound, begin_collection,
                        finish_collection, relocate_collection)


@dataclass
class Candidate:
    """Dispatch recovered regions and one synchronous original sound call.

    ``Machine.atomic`` is the admission point.  It must return ``False`` with
    the machine unchanged when the scheduler cannot admit the whole plan.
    """

    name: str = "leaf"
    stats: dict[str, int | dict[str, int]] = field(default_factory=lambda: {
        "gates": 0, "candidate_hits": 0, "fallbacks": 0,
        "leaf_hits": 0, "pair_hits": 0, "caller_hits": 0, "direct_python_calls": 0,
        "initializer_hits": 0, "finish_hits": 0,
        "collection_hits": 0, "collection_entries": {}, "relocation_hits": 0,
        "collection_dispatch_hits": 0,
        "contact_hits": 0,
        "replace_hits": 0, "counted_replace_hits": 0,
        "carrier_entries": 0, "carrier_completed": 0, "legacy_entries": 0, "legacy_returns": 0,
        "local_fallbacks": 0, "foreign_returns": 0, "legacy_deadline_fallbacks": 0,
        "replaced_m68k_instructions": 0, "charged_m68k_cycles": 0, "fallback_reasons": {},
    })

    _names = {
        "leaf", "pair", "init", "finish", "replace", "composed", "carrier", "lifecycle",
        "carrier-mutant-result", "carrier-mutant-continuation", "carrier-mutant-timing",
        "lifecycle-mutant-result", "lifecycle-mutant-continuation", "lifecycle-mutant-timing",
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
        return self.name == "carrier" or self.is_lifecycle or self.name.startswith("carrier-mutant-")

    @property
    def is_lifecycle(self) -> bool:
        return self.name == 'lifecycle' or self.name.startswith('lifecycle-mutant-')

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
            base = (TRANSITION_ENTRY, COUNTED_REPLACE_ENTRY, FINISH_ENTRY, CALLER_ENTRY, PAIR_ENTRY, INIT_ENTRY, LEAF_ENTRY)
            return tuple(dict.fromkeys((COLLECTION_DISPATCH_ENTRY, CONTACT_ENTRY, *COLLECTION_ROUTES, 0x1AF516, *base))) if self.is_lifecycle else base
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

    def _apply(self, machine, plan, target):
        if not machine.atomic(target=target, cycles=plan.cycles, instructions=plan.instructions,
                              writes=list(plan.writes), registers=plan.registers, last_pc=plan.last_pc):
            return False
        self.stats["candidate_hits"] += 1
        self.stats["replaced_m68k_instructions"] += plan.instructions
        self.stats["charged_m68k_cycles"] += plan.cycles
        self.stats["direct_python_calls"] += plan.direct_calls
        return True

    def _fallback(self, machine, pc, reason):
        self.stats["fallbacks"] += 1
        reasons = self.stats["fallback_reasons"]
        reasons[reason] = reasons.get(reason, 0) + 1
        if pc is not None:
            machine.gate(pc, bypass_once=True)
            machine.run(instructions=1)
        return False

    def _run_sound_seam(self, machine, target, *, sp, resume, return_slot, suffix,
                        suffix_transform=lambda plan: plan, on_complete=lambda: None):
        """Run one admitted synchronous sound call and prove its local return.

        Collection and contact both save a 28-byte frame below the caller's
        stack pointer.  The native sound routine may run arbitrary original
        code, so the resumed local suffix is admitted only when its PC, stack
        pointer, saved frame, and preceding JSR return slot still identify the
        activation that constructed it.
        """
        frame_base = (sp - 24) & 0xFFFF
        frame = machine.peek_ram(frame_base, 28)
        self.stats['legacy_entries'] += 1
        machine.in_sound_call = True
        try:
            machine.gates([resume])
            while machine.run(target=target) == 'gate':
                self.stats['gates'] += 1
                returned = machine.registers()
                if returned['a7'] != sp - 24:
                    self.stats['foreign_returns'] += 1
                    machine.gate(resume, bypass_once=True)
                    continue
                if (returned['pc'] != resume or machine.peek_ram(frame_base, 28) != frame
                        or int.from_bytes(machine.peek_ram((sp - 28) & 0xFFFF, 4), 'big') != return_slot):
                    raise ValueError('Object sound return/frame mismatch')
                self.stats['legacy_returns'] += 1
                reason = 'scheduler admission'
                try:
                    plan = suffix(returned)
                    if self._apply(machine, suffix_transform(plan), target):
                        on_complete()
                        return True
                except UnsupportedCandidate as error:
                    reason = f'unsupported domain: {error}'
                self.stats['local_fallbacks'] += 1
                self._fallback(machine, resume, reason)
                return True
            # The prefix remains committed.  Let original code own the rest
            # once the caller's scheduling deadline is reached.
            self.stats['local_fallbacks'] += 1
            self.stats['legacy_deadline_fallbacks'] += 1
            self._fallback(machine, None, 'legacy deadline')
            return True
        finally:
            machine.in_sound_call = False
            machine.gates(list(self.gate_pcs))

    def _transition(self, machine, target, entry=TRANSITION_ENTRY, *, count_gate=True,
                    registers=None, planner=None, prefix=None, fallback_entry=None):
        if count_gate:
            self.stats["gates"] += 1
        regs = machine.registers() if registers is None else registers
        planner = machine if planner is None else planner
        collection = self.is_lifecycle and entry in COLLECTION_ROUTES
        resume = COLLECTION_ROUTES[entry][1] if collection else SOUND_RETURN
        try:
            plan, legacy = begin_collection(planner, regs, entry) if collection else begin_object_transition(planner, regs)
            if prefix is not None:
                # Callback recipes only name registers their own path writes.
                # Keep dispatcher outputs (notably D1/A4) unless the callback
                # explicitly replaces them.
                final_registers = dict(prefix.registers)
                final_registers.update(plan.registers)
                plan = AtomicPlan(prefix.cycles + plan.cycles, prefix.instructions + plan.instructions,
                                  tuple(dict((*prefix.writes, *plan.writes)).items()), final_registers,
                                  plan.last_pc, prefix.direct_calls + plan.direct_calls)
            if not self._apply(machine, self._mutate(plan), target):
                return self._fallback(machine, fallback_entry or entry, "scheduler admission")
        except UnsupportedCandidate as error:
            return self._fallback(machine, fallback_entry or entry, f"unsupported domain: {error}")
        self.stats["carrier_entries"] += 1
        if collection:
            self.stats['collection_hits'] += 1
            entries = self.stats['collection_entries']
            key = f'{entry:06X}'
            entries[key] = entries.get(key, 0) + 1
        if not legacy:
            self.stats["carrier_completed"] += 1
            return True
        return self._run_sound_seam(
            machine, target, sp=regs['a7'], resume=resume, return_slot=resume,
            suffix=(lambda returned: finish_collection(machine, returned, entry)) if collection
            else (lambda returned: finish_object_transition(machine, returned)),
            on_complete=lambda: self.stats.__setitem__('carrier_completed', self.stats['carrier_completed'] + 1),
        )

    def _collection_dispatch(self, machine, target):
        """Admit 1ABC82 and its known callback in one native atomic region."""
        self.stats['gates'] += 1
        try:
            dispatch_registers = machine.registers()
            entry, prefix = begin_collection_dispatch(machine, dispatch_registers)
        except UnsupportedCandidate as error:
            return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, f'unsupported domain: {error}')
        if entry == CONTACT_DISPATCH_ENTRY:
            try:
                plan = begin_contact_dispatch(machine, dispatch_registers, prefix)
                if not self._apply(machine, self._mutate(plan), target):
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
            except UnsupportedCandidate as error:
                try:
                    sound = begin_contact_dispatch_sound(machine, dispatch_registers, prefix)
                    if not self._apply(machine, self._mutate(sound), target):
                        return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
                except UnsupportedCandidate:
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, f'unsupported domain: {error}')
                return self._run_sound_seam(
                    machine, target, sp=dispatch_registers['a7'] - 8,
                    resume=0x1AE5B6, return_slot=0x1AE5B6,
                    suffix=lambda returned: finish_contact_dispatch_sound(machine, returned),
                    suffix_transform=self._mutate,
                    on_complete=lambda: (self.stats.__setitem__('collection_dispatch_hits', self.stats['collection_dispatch_hits'] + 1),
                                         self.stats.__setitem__('contact_hits', self.stats['contact_hits'] + 1)),
                )
            self.stats['collection_dispatch_hits'] += 1
            self.stats['contact_hits'] += 1
            return True
        dispatch_registers.update(prefix.registers)
        # The callback is at the original JSR boundary, but it did not cause a
        # native stop. Its stack return exists in this read-only planning view,
        # then prefix and callback commit together at the real dispatch gate.
        accepted = self._transition(machine, target, entry, count_gate=False,
                                    registers=dispatch_registers,
                                    planner=dispatch_plan_view(machine, prefix), prefix=prefix,
                                    fallback_entry=COLLECTION_DISPATCH_ENTRY)
        if accepted:
            self.stats['collection_dispatch_hits'] += 1
        return accepted

    def _contact(self, machine, target):
        self.stats['gates'] += 1
        try:
            plan = begin_contact(machine, machine.registers())
            if not self._apply(machine, self._mutate(plan), target):
                return self._fallback(machine, CONTACT_ENTRY, 'scheduler admission')
        except UnsupportedCandidate as error:
            try:
                registers = machine.registers(); prefix = begin_contact_sound(machine, registers)
                if not self._apply(machine, self._mutate(prefix), target):
                    return self._fallback(machine, CONTACT_ENTRY, 'scheduler admission')
            except UnsupportedCandidate:
                return self._fallback(machine, CONTACT_ENTRY, f'unsupported domain: {error}')
            return self._run_sound_seam(
                machine, target, sp=registers['a7'], resume=0x1AE5B6,
                return_slot=0x1AE5B6,
                suffix=lambda returned: finish_contact_sound(machine, returned),
                suffix_transform=self._mutate,
                on_complete=lambda: self.stats.__setitem__('contact_hits', self.stats['contact_hits'] + 1),
            )
        self.stats['contact_hits'] += 1
        return True

    def on_gate(self, machine, target: int) -> bool:
        """Try a candidate at the current gate; otherwise retire one original instruction.

        ``True`` means recovered work was committed; a sound deadline may have
        handed the remaining suffix to original execution. ``False`` means
        the entry declined and retired its original instruction.
        """
        entry = machine.info["pc"]
        if type(target) is not int or target < machine.info["tick"]:
            raise ValueError("Recovery dispatch needs the scheduler master-tick deadline")
        if self.is_carrier and entry == TRANSITION_ENTRY:
            return self._transition(machine, target)
        if self.is_lifecycle and entry == COLLECTION_DISPATCH_ENTRY:
            return self._collection_dispatch(machine, target)
        if self.is_lifecycle and entry == CONTACT_ENTRY:
            return self._contact(machine, target)
        if self.is_lifecycle and entry in COLLECTION_ROUTES:
            return self._transition(machine, target, entry)
        if entry not in self.gate_pcs:
            raise ValueError("Recovery dispatch does not match the stopped PC")
        self.stats["gates"] += 1
        fallback_reason = "scheduler admission"
        try:
            registers = machine.registers()
            if entry == 0x1AF516 and self.is_lifecycle:
                plan = relocate_collection(machine, registers)
            elif entry == CALLER_ENTRY and self.is_composed:
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
            accepted = self._apply(machine, plan, target)
        except UnsupportedCandidate as error:
            fallback_reason = f"unsupported domain: {error}"
            accepted = False
        if accepted:
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
            elif entry == 0x1AF516:
                self.stats['relocation_hits'] += 1
            else:
                self.stats["caller_hits"] += 1
            return True
        return self._fallback(machine, entry, fallback_reason)

    def _mutate(self, plan: AtomicPlan) -> AtomicPlan:
        if self.name.startswith(("carrier-mutant-", "lifecycle-mutant-")):
            if self.name.endswith("timing"):
                return AtomicPlan(plan.cycles + 2, plan.instructions, plan.writes, plan.registers, plan.last_pc, plan.direct_calls)
            writes = list(plan.writes)
            index = 0 if self.name.endswith("result") else -1
            writes[index] = (writes[index][0], writes[index][1] ^ 1 if index == 0 else writes[index][1] + 2)
            return AtomicPlan(plan.cycles, plan.instructions, tuple(writes), plan.registers, plan.last_pc, plan.direct_calls)
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
