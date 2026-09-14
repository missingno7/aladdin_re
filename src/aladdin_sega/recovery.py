"""Project-owned gate dispatch and qualification policy for recovered Aladdin."""
from __future__ import annotations
from dataclasses import dataclass, field

from .boundary import (AtomicPlan, SoundSeam, UnsupportedCandidate, LEAF_ENTRY, PAIR_ENTRY, CALLER_ENTRY,
                        INIT_ENTRY, FINISH_ENTRY, ROM_SHA256, clear_auxiliary_buffer,
                        COUNTED_REPLACE_ENTRY, REPLACE_ENTRY, clear_object_pair, detach_object,
                        initialize_object, finish_object, replace_object, TRANSITION_ENTRY,
                        SOUND_RETURN, begin_object_transition, finish_object_transition,
                        COLLECTION_ROUTES, COLLECTION_DISPATCH_ENTRY, begin_collection_dispatch,
                        dispatch_plan_view, CONTACT_ENTRY, CONTACT_DISPATCH_ENTRY, begin_contact_dispatch,
                        COLLECTION_DISPATCH_RETURN, extend_contact_completion,
                        CONTACT_SCAN_ENTRY, contact_scan_plan, CONTACT_STEP_ENTRY, contact_step_plan,
                        begin_contact_step_sound,
                        begin_contact_dispatch_sound, finish_contact_dispatch_sound, begin_contact,
                        begin_contact_sound, finish_contact_sound, begin_collection,
                        CONTACT_ACTIVATION_ENTRY, begin_contact_activation_dispatch,
                        CONTACT_FAMILY_66_ENTRY, begin_contact_family_66_dispatch,
                        CONTACT_FAMILY_MOTION_ENTRY, begin_contact_family_motion_dispatch,
                        CONTACT_FAMILY_SOUND_ENTRY, begin_contact_family_sound_dispatch,
                        CONTACT_FAMILY_SECONDARY_MOTION_ENTRY, begin_contact_family_secondary_dispatch,
                        CONTACT_FAMILY_TYPE79_ENTRY, begin_contact_family_type79_dispatch,
                        begin_contact_family_type79_dispatch_sound,
                        finish_contact_family_type79_sound,
                        CONTACT_FAMILY_TYPE1F_ENTRY, begin_contact_family_type1f_inactive_dispatch,
                        CONTACT_FAMILY_TYPE15_ENTRY, begin_contact_family_type15_dispatch,
                        CONTACT_FAMILY_TYPE44_ENTRY, begin_contact_family_type44_dispatch,
                        CONTACT_FAMILY_TYPE03_ENTRY, begin_contact_family_type03_sound_seam,
                        begin_contact_family_type03_dispatch_sound_seam,
                        CONTACT_FAMILY_TYPE46_ENTRY, begin_contact_family_type46_dispatch_sound_seam,
                        CONTACT_FAMILY_TYPE55_ENTRY, begin_contact_family_type55_dispatch,
                        CONTACT_COLLECTION_RELOCATION_ENTRY,
                        begin_contact_collection_relocation_dispatch,
                        begin_contact_family_type1f_contact_dispatch,
                        begin_contact_family_type1f_contact_dispatch_sound,
                        finish_contact_family_type1f_contact_sound,
                        begin_contact_family_type1f_transition_dispatch,
                        begin_contact_family_type1f_transition_dispatch_sound,
                        finish_contact_family_type1f_transition_sound,
                        begin_contact_family_type1f_transition_soundoff_dispatch,
                        CONTACT_TYPE7E_ENTRY, begin_contact_type7e_dispatch,
                        finish_collection, relocate_collection, CONTACT_SIBLING_ENTRY,
                        CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT,
                        begin_contact_sibling, begin_contact_sibling_wrapper,
                        begin_contact_sibling_dispatch, begin_contact_sibling_wrapper_sound_seam,
                        finish_contact_sibling_wrapper_sound, begin_contact_sibling_dispatch_sound_seam,
                        begin_contact_sibling_sound_seam, finish_contact_sibling_sound,
                        SPAWN_REGION_ENTRIES, SPAWN_REVERSE_CALLER_ENTRY, SPAWN_REVERSE_PLAIN_CALLER_ENTRY, SPAWN_UPPER_PLAIN_CALLER_ENTRY, SPAWN_UPPER_STANDARD_CALLER_ENTRY, SPAWN_UPPER_SECONDARY_CALLER_ENTRY, SPAWN_UPPER_TERTIARY_CALLER_ENTRY, SPAWN_UPPER_TYPED_CALLER_ENTRY, SPAWN_UPPER_CALLER_ENTRY, SPAWN_UPPER_GUARD_ENTRY, SPAWN_PRIMARY_DISPATCH_ENTRY, SPAWN_PRIMARY_GUARD_ENTRY, SPAWN_LOWER_DISPATCH_ENTRY, SPAWN_PRIMARY_DOUBLE_GUARD_ENTRY, SPAWN_PRIMARY_INVERSE_GUARD_ENTRY, SPAWN_PRIMARY_MIXED_GUARD_ENTRY, SPAWN_UPPER_VARIANT_CALLER_ENTRY, SPAWN_UPPER_SCRIPTED_CALLER_ENTRY, SPAWN_UPPER_DISPATCH_ENTRY, SPAWN_UPPER_DISPATCH_GUARD_ENTRY, SPAWN_DISPATCH_ITERATION_ENTRY, SPAWN_DISPATCH_WALKER_ENTRY, SPAWN_ROW_DISPATCH_WALKER_ENTRY, SPAWN_SETUP_LEFT_ENTRY, SPAWN_SETUP_RIGHT_ENTRY, SPAWN_SETUP_ROW_LOW_ENTRY, SPAWN_SETUP_ROW_HIGH_ENTRY,
                        spawn_region, spawn_reverse_caller, spawn_reverse_plain_caller, spawn_upper_plain_caller, spawn_upper_standard_caller, spawn_upper_secondary_caller, spawn_upper_tertiary_caller, spawn_upper_typed_caller, spawn_upper_caller, spawn_upper_guard_caller, spawn_primary_dispatch_caller, spawn_primary_guard_caller, spawn_lower_dispatch_caller, spawn_primary_double_guard_caller, spawn_primary_inverse_guard_caller, spawn_primary_mixed_guard_caller, spawn_upper_variant_caller, spawn_upper_scripted_caller, spawn_upper_dispatch_caller, spawn_upper_dispatch_guard_caller, spawn_dispatch_iteration, spawn_dispatch_walker, spawn_row_dispatch_walker, spawn_setup_dispatch)
from .boundary import (SPAWN_UPPER_TYPED_SECONDARY_ENTRY, spawn_upper_typed_secondary_caller,
                       SPAWN_LOWER_RESET_ENTRY, SPAWN_LOWER_SCRIPTED_ENTRY,
                       spawn_lower_reset_caller, spawn_lower_scripted_caller)


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
        "contact_completion_hits": 0,
        "contact_scan_hits": 0,
        "contact_step_hits": 0,
        "contact_activation_hits": 0,
        "contact_sibling_hits": 0,
        "spawn_region_hits": 0, "spawn_caller_hits": 0, "spawn_walker_hits": 0, "spawn_row_walker_hits": 0,
        "spawn_setup_hits": 0,
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
            return tuple(dict.fromkeys((SPAWN_UPPER_TYPED_SECONDARY_ENTRY,
                                        SPAWN_LOWER_RESET_ENTRY, SPAWN_LOWER_SCRIPTED_ENTRY,
                                        COLLECTION_DISPATCH_ENTRY, CONTACT_ENTRY,
                                        CONTACT_STEP_ENTRY,
                                        CONTACT_SIBLING_ENTRY, CONTACT_SIBLING_WRAPPER,
                                        *COLLECTION_ROUTES,
                                        CONTACT_FAMILY_TYPE03_ENTRY,
                                        0x1AF516, SPAWN_REVERSE_CALLER_ENTRY, SPAWN_REVERSE_PLAIN_CALLER_ENTRY, SPAWN_UPPER_PLAIN_CALLER_ENTRY, SPAWN_UPPER_STANDARD_CALLER_ENTRY, SPAWN_UPPER_SECONDARY_CALLER_ENTRY, SPAWN_UPPER_TERTIARY_CALLER_ENTRY, SPAWN_UPPER_TYPED_CALLER_ENTRY, SPAWN_UPPER_CALLER_ENTRY, SPAWN_UPPER_GUARD_ENTRY, SPAWN_PRIMARY_DISPATCH_ENTRY, SPAWN_PRIMARY_GUARD_ENTRY, SPAWN_LOWER_DISPATCH_ENTRY, SPAWN_PRIMARY_DOUBLE_GUARD_ENTRY, SPAWN_PRIMARY_INVERSE_GUARD_ENTRY, SPAWN_PRIMARY_MIXED_GUARD_ENTRY, SPAWN_UPPER_VARIANT_CALLER_ENTRY, SPAWN_UPPER_SCRIPTED_CALLER_ENTRY, SPAWN_UPPER_DISPATCH_ENTRY, SPAWN_UPPER_DISPATCH_GUARD_ENTRY, SPAWN_DISPATCH_WALKER_ENTRY, SPAWN_DISPATCH_ITERATION_ENTRY, SPAWN_ROW_DISPATCH_WALKER_ENTRY, SPAWN_SETUP_LEFT_ENTRY, SPAWN_SETUP_RIGHT_ENTRY, SPAWN_SETUP_ROW_LOW_ENTRY, SPAWN_SETUP_ROW_HIGH_ENTRY,
                                        *SPAWN_REGION_ENTRIES, *base))) if self.is_lifecycle else base
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
        # Callback recipes retain their direct 1ABCA0 contract.  Lifecycle
        # dispatch may opportunistically join the measured completion suffix;
        # a refusal leaves the shorter callback plan admissible as before.
        if self.is_lifecycle and plan.registers.get('pc') == COLLECTION_DISPATCH_RETURN:
            try:
                extended = extend_contact_completion(machine, plan)
                if machine.atomic(target=target, cycles=extended.cycles, instructions=extended.instructions,
                                  writes=list(extended.writes), registers=extended.registers,
                                  last_pc=extended.last_pc):
                    self.stats['contact_completion_hits'] += 1
                    self.stats["candidate_hits"] += 1
                    self.stats["replaced_m68k_instructions"] += extended.instructions
                    self.stats["charged_m68k_cycles"] += extended.cycles
                    self.stats["direct_python_calls"] += extended.direct_calls
                    return True
            except UnsupportedCandidate:
                pass
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

    def _run_sound_seam(self, machine, target, seam: SoundSeam, *,
                        suffix_transform=lambda plan: plan, on_complete=lambda: None):
        """Run one admitted synchronous sound call and prove its local return.

        The native sound routine may run arbitrary original code, so the
        resumed local suffix is admitted only when its PC, stack pointer,
        saved frame, and preceding JSR return slot still identify the
        activation that constructed it.  The ordinary request/flush ABI uses
        a 24-byte saved frame plus argument; type-13's fixed helper saves the
        five registers alone in a measured 20-byte frame.
        """
        sp, resume, return_slot = seam.stack_basis, seam.resume_pc, seam.return_slot
        saved_frame, frame_size, return_delta = (seam.saved_frame, seam.frame_size,
                                                  seam.return_delta)
        frame_base = (sp - saved_frame) & 0xFFFF
        frame = machine.peek_ram(frame_base, frame_size)
        self.stats['legacy_entries'] += 1
        machine.in_sound_call = True
        try:
            machine.gates([resume])
            while machine.run(target=target) == 'gate':
                self.stats['gates'] += 1
                returned = machine.registers()
                if returned['a7'] != sp - saved_frame:
                    self.stats['foreign_returns'] += 1
                    machine.gate(resume, bypass_once=True)
                    continue
                if (returned['pc'] != resume or machine.peek_ram(frame_base, frame_size) != frame
                        or int.from_bytes(machine.peek_ram((sp - return_delta) & 0xFFFF, 4), 'big') != return_slot):
                    raise ValueError('Object sound return/frame mismatch')
                self.stats['legacy_returns'] += 1
                reason = 'scheduler admission'
                try:
                    if seam.suffix is None:
                        raise ValueError('sound seam has no concrete suffix')
                    plan = seam.suffix(machine, returned)
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
        seam = SoundSeam(
            plan, regs['a7'], resume, resume, 24, 28, 28,
            suffix=(lambda live, returned: finish_collection(live, returned, entry)) if collection
            else finish_object_transition,
        )
        return self._run_sound_seam(
            machine, target, seam,
            on_complete=lambda: self.stats.__setitem__('carrier_completed', self.stats['carrier_completed'] + 1),
        )

    def _complete_sibling_sound(self, seam: SoundSeam, *, dispatched: bool):
        """Bind the caller-owned counters to an explicit constructed seam."""
        def complete():
            if dispatched:
                self.stats['collection_dispatch_hits'] += 1
            self.stats['contact_sibling_hits'] += 1
            if seam.counts_contact:
                self.stats['contact_hits'] += 1
        return complete

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
                seam = SoundSeam(sound, dispatch_registers['a7'] - 8,
                                 0x1AE5B6, 0x1AE5B6, 24, 28, 28, True,
                                 finish_contact_dispatch_sound)
                return self._run_sound_seam(
                    machine, target, seam,
                    suffix_transform=self._mutate,
                    on_complete=lambda: (self.stats.__setitem__('collection_dispatch_hits', self.stats['collection_dispatch_hits'] + 1),
                                         self.stats.__setitem__('contact_hits', self.stats['contact_hits'] + 1)),
                )
            self.stats['collection_dispatch_hits'] += 1
            self.stats['contact_hits'] += 1
            return True
        if entry == CONTACT_ACTIVATION_ENTRY:
            try:
                plan = begin_contact_activation_dispatch(machine, dispatch_registers, prefix)
                if not self._apply(machine, self._mutate(plan), target):
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, f'unsupported domain: {error}')
            self.stats['collection_dispatch_hits'] += 1
            self.stats['contact_activation_hits'] += 1
            return True
        family_planner = {
            CONTACT_FAMILY_66_ENTRY: begin_contact_family_66_dispatch,
            CONTACT_FAMILY_MOTION_ENTRY: begin_contact_family_motion_dispatch,
            CONTACT_FAMILY_SECONDARY_MOTION_ENTRY: begin_contact_family_secondary_dispatch,
            CONTACT_FAMILY_TYPE79_ENTRY: begin_contact_family_type79_dispatch,
            CONTACT_FAMILY_TYPE1F_ENTRY: begin_contact_family_type1f_inactive_dispatch,
            CONTACT_FAMILY_TYPE15_ENTRY: begin_contact_family_type15_dispatch,
            CONTACT_FAMILY_TYPE44_ENTRY: begin_contact_family_type44_dispatch,
            CONTACT_FAMILY_TYPE55_ENTRY: begin_contact_family_type55_dispatch,
            CONTACT_COLLECTION_RELOCATION_ENTRY: begin_contact_collection_relocation_dispatch,
            CONTACT_TYPE7E_ENTRY: begin_contact_type7e_dispatch,
        }.get(entry)
        if family_planner is not None:
            try:
                plan = family_planner(machine, dispatch_registers, prefix)
                if not self._apply(machine, self._mutate(plan), target):
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
            except UnsupportedCandidate as error:
                if entry == CONTACT_FAMILY_TYPE1F_ENTRY:
                    try:
                        plan = begin_contact_family_type1f_transition_dispatch(
                            machine, dispatch_registers, prefix)
                        if not self._apply(machine, self._mutate(plan), target):
                            return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
                    except UnsupportedCandidate:
                        try:
                            plan = begin_contact_family_type1f_transition_soundoff_dispatch(
                                machine, dispatch_registers, prefix)
                            if not self._apply(machine, self._mutate(plan), target):
                                return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
                        except UnsupportedCandidate:
                            try:
                                sound = begin_contact_family_type1f_transition_dispatch_sound(
                                    machine, dispatch_registers, prefix)
                                if not self._apply(machine, self._mutate(sound), target):
                                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
                            except UnsupportedCandidate:
                                try:
                                    plan = begin_contact_family_type1f_contact_dispatch(
                                        machine, dispatch_registers, prefix)
                                    if not self._apply(machine, self._mutate(plan), target):
                                        return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
                                except UnsupportedCandidate:
                                    try:
                                        sound = begin_contact_family_type1f_contact_dispatch_sound(
                                            machine, dispatch_registers, prefix)
                                        if not self._apply(machine, self._mutate(sound), target):
                                            return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
                                    except UnsupportedCandidate:
                                        return self._fallback(machine, COLLECTION_DISPATCH_ENTRY,
                                                              f'unsupported domain: {error}')
                                    seam = SoundSeam(sound, dispatch_registers['a7'] - 8,
                                                     0x1AE5B6, 0x1AE5B6, 24, 28, 28, True,
                                                     finish_contact_family_type1f_contact_sound)
                                    return self._run_sound_seam(machine, target, seam, suffix_transform=self._mutate,
                                        on_complete=lambda: self.stats.__setitem__('collection_dispatch_hits', self.stats['collection_dispatch_hits'] + 1))
                                self.stats['collection_dispatch_hits'] += 1
                                return True
                            seam = SoundSeam(sound, dispatch_registers['a7'] - 4, 0x1AE920, 0x1AE920, 24, 28, 28, True,
                                             finish_contact_family_type1f_transition_sound)
                            return self._run_sound_seam(machine, target, seam, suffix_transform=self._mutate,
                                on_complete=lambda: self.stats.__setitem__('collection_dispatch_hits', self.stats['collection_dispatch_hits'] + 1))
                        self.stats['collection_dispatch_hits'] += 1
                        return True
                    self.stats['collection_dispatch_hits'] += 1
                    return True
                if entry == CONTACT_FAMILY_TYPE79_ENTRY:
                    try:
                        sound = begin_contact_family_type79_dispatch_sound(
                            machine, dispatch_registers, prefix)
                        if not self._apply(machine, self._mutate(sound), target):
                            return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
                    except UnsupportedCandidate:
                        return self._fallback(machine, COLLECTION_DISPATCH_ENTRY,
                                              f'unsupported domain: {error}')
                    seam = SoundSeam(sound, dispatch_registers['a7'] - 8,
                                     0x1AE5B6, 0x1AE5B6, 24, 28, 28, True,
                                     finish_contact_family_type79_sound)
                    return self._run_sound_seam(
                        machine, target, seam,
                        suffix_transform=self._mutate,
                        on_complete=lambda: self.stats.__setitem__(
                            'collection_dispatch_hits', self.stats['collection_dispatch_hits'] + 1))
                return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, f'unsupported domain: {error}')
            self.stats['collection_dispatch_hits'] += 1
            return True
        if entry == CONTACT_FAMILY_SOUND_ENTRY:
            try:
                result = begin_contact_family_sound_dispatch(machine, dispatch_registers, prefix)
                plan = result.prefix if isinstance(result, SoundSeam) else result
                if not self._apply(machine, self._mutate(plan), target):
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, f'unsupported domain: {error}')
            if isinstance(result, SoundSeam):
                return self._run_sound_seam(
                    machine, target, result, suffix_transform=self._mutate,
                    on_complete=lambda: self.stats.__setitem__(
                        'collection_dispatch_hits', self.stats['collection_dispatch_hits'] + 1))
            self.stats['collection_dispatch_hits'] += 1
            return True
        if entry == CONTACT_FAMILY_TYPE03_ENTRY:
            try:
                seam = begin_contact_family_type03_dispatch_sound_seam(
                    machine, dispatch_registers, prefix)
                if not self._apply(machine, self._mutate(seam.prefix), target):
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, f'unsupported domain: {error}')
            return self._run_sound_seam(
                machine, target, seam, suffix_transform=self._mutate,
                on_complete=self._complete_sibling_sound(seam, dispatched=True),
            )
        if entry == CONTACT_FAMILY_TYPE46_ENTRY:
            try:
                seam = begin_contact_family_type46_dispatch_sound_seam(
                    machine, dispatch_registers, prefix)
                if not self._apply(machine, self._mutate(seam.prefix), target):
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, f'unsupported domain: {error}')
            return self._run_sound_seam(
                machine, target, seam, suffix_transform=self._mutate,
                on_complete=lambda: self.stats.__setitem__(
                    'collection_dispatch_hits', self.stats['collection_dispatch_hits'] + 1),
            )
        if entry in (CONTACT_SIBLING_WRAPPER, CONTACT_SIBLING_DIRECT):
            try:
                plan = begin_contact_sibling_dispatch(machine, dispatch_registers, prefix, entry)
                if not self._apply(machine, self._mutate(plan), target):
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
            except UnsupportedCandidate as error:
                try:
                    seam = begin_contact_sibling_dispatch_sound_seam(machine, dispatch_registers, prefix, entry)
                    if not self._apply(machine, self._mutate(seam.prefix), target):
                        return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, 'scheduler admission')
                except UnsupportedCandidate:
                    return self._fallback(machine, COLLECTION_DISPATCH_ENTRY, f'unsupported domain: {error}')
                return self._run_sound_seam(
                    machine, target, seam,
                    suffix_transform=self._mutate,
                    on_complete=self._complete_sibling_sound(seam, dispatched=True),
                )
            self.stats['collection_dispatch_hits'] += 1
            self.stats['contact_sibling_hits'] += 1
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
            seam = SoundSeam(prefix, registers['a7'], 0x1AE5B6, 0x1AE5B6, 24, 28, 28, True,
                             finish_contact_sound)
            return self._run_sound_seam(
                machine, target, seam,
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
        if self.is_lifecycle and entry == CONTACT_SCAN_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(contact_scan_plan(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['contact_scan_hits'] += 1
            return True
        if self.is_lifecycle and entry == CONTACT_STEP_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(contact_step_plan(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                try:
                    seam = begin_contact_step_sound(machine, machine.registers())
                    if not self._apply(machine, self._mutate(seam.prefix), target):
                        return self._fallback(machine, entry, 'scheduler admission')
                except UnsupportedCandidate:
                    return self._fallback(machine, entry, f'unsupported domain: {error}')
                handled = self._run_sound_seam(machine, target, seam, suffix_transform=self._mutate)
                if handled:
                    # The parent prefix is committed once its one concrete
                    # sound seam starts, even if a later callback returns to
                    # original code through that seam's local fallback.
                    self.stats['contact_step_hits'] += 1
                return handled
            self.stats['contact_step_hits'] += 1
            return True
        if self.is_lifecycle and entry == CONTACT_ENTRY:
            return self._contact(machine, target)
        if self.is_lifecycle and entry == CONTACT_FAMILY_TYPE03_ENTRY:
            self.stats['gates'] += 1
            try:
                seam = begin_contact_family_type03_sound_seam(machine, machine.registers())
                if not self._apply(machine, self._mutate(seam.prefix), target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            return self._run_sound_seam(
                machine, target, seam, suffix_transform=self._mutate,
                on_complete=self._complete_sibling_sound(seam, dispatched=False),
            )
        if self.is_lifecycle and entry in (CONTACT_SIBLING_ENTRY, CONTACT_SIBLING_WRAPPER,
                                           CONTACT_SIBLING_DIRECT):
            self.stats['gates'] += 1
            try:
                registers = machine.registers()
                if entry == CONTACT_SIBLING_ENTRY:
                    plan = begin_contact_sibling(machine, registers)
                else:
                    plan = begin_contact_sibling_wrapper(machine, registers, entry)
                if not self._apply(machine, self._mutate(plan), target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                try:
                    seam = (begin_contact_sibling_sound_seam(machine, registers)
                            if entry == CONTACT_SIBLING_ENTRY else
                            begin_contact_sibling_wrapper_sound_seam(machine, registers, entry))
                    if not self._apply(machine, self._mutate(seam.prefix), target):
                        return self._fallback(machine, entry, 'scheduler admission')
                except UnsupportedCandidate:
                    return self._fallback(machine, entry, f'unsupported domain: {error}')
                return self._run_sound_seam(
                    machine, target, seam,
                    suffix_transform=self._mutate,
                    on_complete=self._complete_sibling_sound(seam, dispatched=False),
                )
            self.stats['contact_sibling_hits'] += 1
            return True
        if self.is_lifecycle and entry in COLLECTION_ROUTES:
            return self._transition(machine, target, entry)
        if self.is_lifecycle and entry in (SPAWN_SETUP_LEFT_ENTRY, SPAWN_SETUP_RIGHT_ENTRY,
                                           SPAWN_SETUP_ROW_LOW_ENTRY, SPAWN_SETUP_ROW_HIGH_ENTRY):
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_setup_dispatch(machine, machine.registers(), entry))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_setup_hits'] += 1
            self.stats['spawn_walker_hits'] += 1
            return True
        if self.is_lifecycle and entry in (SPAWN_DISPATCH_WALKER_ENTRY, SPAWN_ROW_DISPATCH_WALKER_ENTRY):
            self.stats['gates'] += 1
            row = entry == SPAWN_ROW_DISPATCH_WALKER_ENTRY
            try:
                walker = spawn_row_dispatch_walker if row else spawn_dispatch_walker
                plan = self._mutate(walker(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_walker_hits'] += 1
            if row:
                self.stats['spawn_row_walker_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_DISPATCH_ITERATION_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_dispatch_iteration(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_VARIANT_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_variant_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_GUARD_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_guard_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_PRIMARY_DISPATCH_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_primary_dispatch_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_PRIMARY_GUARD_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_primary_guard_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_LOWER_DISPATCH_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_lower_dispatch_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_DISPATCH_GUARD_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_dispatch_guard_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_PRIMARY_DOUBLE_GUARD_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_primary_double_guard_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_PRIMARY_INVERSE_GUARD_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_primary_inverse_guard_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_PRIMARY_MIXED_GUARD_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_primary_mixed_guard_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_SCRIPTED_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_scripted_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_REVERSE_PLAIN_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_reverse_plain_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_PLAIN_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_plain_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_STANDARD_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_standard_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_SECONDARY_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_secondary_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_TERTIARY_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_tertiary_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_TYPED_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_typed_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry in (SPAWN_UPPER_TYPED_SECONDARY_ENTRY,
                                          SPAWN_LOWER_RESET_ENTRY, SPAWN_LOWER_SCRIPTED_ENTRY):
            self.stats['gates'] += 1
            try:
                caller = {SPAWN_UPPER_TYPED_SECONDARY_ENTRY: spawn_upper_typed_secondary_caller,
                          SPAWN_LOWER_RESET_ENTRY: spawn_lower_reset_caller,
                          SPAWN_LOWER_SCRIPTED_ENTRY: spawn_lower_scripted_caller}[entry]
                plan = self._mutate(caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_UPPER_DISPATCH_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_upper_dispatch_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry == SPAWN_REVERSE_CALLER_ENTRY:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_reverse_caller(machine, machine.registers()))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_caller_hits'] += 1
            return True
        if self.is_lifecycle and entry in SPAWN_REGION_ENTRIES:
            self.stats['gates'] += 1
            try:
                plan = self._mutate(spawn_region(machine, machine.registers(), entry))
                if not self._apply(machine, plan, target):
                    return self._fallback(machine, entry, 'scheduler admission')
            except UnsupportedCandidate as error:
                return self._fallback(machine, entry, f'unsupported domain: {error}')
            self.stats['spawn_region_hits'] += 1
            return True
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
            registers = dict(plan.registers)
            if self.name.endswith("continuation"):
                registers["pc"] = (registers["pc"] + 2) & 0xFFFFFF
            else:
                if plan.writes:
                    writes = list(plan.writes)
                    writes[0] = (writes[0][0], writes[0][1] ^ 1)
                    return AtomicPlan(plan.cycles, plan.instructions, tuple(writes), registers,
                                      plan.last_pc, plan.direct_calls)
                # Some valid semantic paths (skipped guards and an empty
                # dispatcher pass) produce no RAM residue. A negative result
                # control still needs to alter an exposed architectural fact.
                registers["d0"] ^= 1
            return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers,
                              plan.last_pc, plan.direct_calls)
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
