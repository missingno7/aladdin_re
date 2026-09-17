"""Gate dispatch for recovered Gods regions: one planner per gate, admission through ``Machine.atomic``.

A planner returns an ``AtomicPlan`` (the whole region as one admitted
operation) or a ``Seam`` (a recovered prefix, a platform operation the
original machine runs, a recovered suffix); ``genesis_re.seam.run_seam``
is the shared mechanism that pauses and resumes, this dispatcher admits
the plans and counts what happened.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from genesis_re.seam import AtomicPlan, Seam, UnsupportedCandidate, run_seam

from .boundary import (ANIMATION_STEP_ENTRY, CAMERA_FOLLOW_ENTRY, COLLISION_GATE_ENTRY, CONDITION_ENTRY, COUNTDOWN_CHECK_ENTRY,
                       EFFECT_POOL_ADD_ENTRY, EVALUATOR_ENTRY, FOOTPRINT_STAMP_ENTRY, GRID_CELL_ENTRY, HAZARD_TICK_ENTRY,
                       LAUNCH_ENTRY, MESSAGE_GATE_ENTRY, NEXT_RANDOM_ENTRY, PARTICLE_EMIT_ENTRY, PICKUP_AWARD_ENTRY, PICKUP_CHECK_ENTRY,
                       PICKUP_PROBE_ENTRY, PROJECTILE_RESUME_ENTRY, PROXIMITY_ENTRY, SCORE_CONVERT_ENTRY, SOLID_DRAW_ENTRY,
                       SPAWN_QUEUE_ENTRY, SPRITE_EMIT_ENTRY, STATIC_EMIT_ENTRY, STRING_COPY_ENTRY, TABLE_RESET_ENTRY,
                       WALKER_RESUME_ENTRY, ZONE_CHECK_ENTRY, animation_step_plan, camera_follow_plan,
                       collision_gate_plan, countdown_check_plan, draw_solid_plan, effect_pool_add_plan, evaluator_plan,
                       footprint_stamp_plan, condition_plan, grid_cell_plan, hazard_tick_plan, launch_plan, message_gate_plan,
                       next_random_plan, particle_emit_plan, pickup_award_plan, pickup_check_plan, pickup_probe_plan, proximity_plan,
                       score_convert_plan, spawn_queue_plan, sprite_emit_plan, static_emit_plan, string_copy_plan, table_reset_plan,
                       walker_resume_plan, walker_resume_projectile_plan, zone_check_plan)


def _mutate_result(plan: AtomicPlan) -> AtomicPlan:
    """Negative control: one stored byte off by one.  A PASS with this candidate would mean nothing is compared."""
    if not plan.writes:
        return plan
    address, value = plan.writes[-1]
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes[:-1] + ((address, (value + 1) & 0xFF),),
                      plan.registers, plan.last_pc, plan.direct_calls)


def _mutate_outcome(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for a predicate: a false outcome (the slot cleared) is reported as true (nothing stored).

    A register mutant is blind here: the dispatcher's residue is dead once
    the evaluator reloads its registers, and a cleared slot rewritten to
    another non-negative value still reads as false.  Dropping the clear
    makes a failing condition pass, and a record whose other conditions
    hold then fires its action.
    """
    return AtomicPlan(plan.cycles, plan.instructions, (), plan.registers, plan.last_pc, plan.direct_calls)


def _mutate_walk(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for the line walker: the re-armed x position one off (the eighth stored byte, after the
    budget word, the continuation and x's high byte).  The counter is not the control: a counter one off
    drove the original's own waypoint code into a write to the cartridge -- a fault, not a divergence."""
    address, value = plan.writes[7]
    return AtomicPlan(plan.cycles, plan.instructions,
                      plan.writes[:7] + ((address, (value + 1) & 0xFF),) + plan.writes[8:],
                      plan.registers, plan.last_pc, plan.direct_calls)


def _mutate_launch(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for the projectile launch: the new slot's own re-armed x position one off (the
    twelfth stored byte, after the internal call's own return address, the budget word and the
    continuation) -- the same field `_mutate_walk` flips for the resume, offset by the call return."""
    address, value = plan.writes[11]
    return AtomicPlan(plan.cycles, plan.instructions,
                      plan.writes[:11] + ((address, (value + 1) & 0xFF),) + plan.writes[12:],
                      plan.registers, plan.last_pc, plan.direct_calls)


def _mutate_register(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for a seam's register contract: d0 off by one in every admitted plan."""
    registers = dict(plan.registers)
    registers['d0'] = (registers.get('d0', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_address(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for a routine whose result is an address in a0 the caller dereferences: one cell
    off.  (A residue register such as d0 is not a control the game can see: with the observation instant
    in the idle window the caller has long overwritten it, and the mutant passed.)"""
    registers = dict(plan.registers)
    registers['a0'] = (registers.get('a0', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


# The fallback reasons that are the adapter's refusal of an exact span (the original runs it; nothing
# is declined): the caller's observation instant precedes the span's end, the sound driver's Z80
# bank register points at work RAM, a vertical interrupt falls inside the span, or another condition
# of the engine's.  Everything else a fallback reason names is a declined arm or a seam outcome.
ADAPTER_REFUSALS = frozenset({'observation deadline', 'z80 bank guard', 'vblank in span', 'machine admission'})

PLANNERS = {
    'camera': {CAMERA_FOLLOW_ENTRY: camera_follow_plan},
    'sprites': {SPRITE_EMIT_ENTRY: sprite_emit_plan},
    'sprites-static': {STATIC_EMIT_ENTRY: static_emit_plan},
    'table-reset': {TABLE_RESET_ENTRY: table_reset_plan},
    'spawn-queue': {SPAWN_QUEUE_ENTRY: spawn_queue_plan},
    'grid-cell': {GRID_CELL_ENTRY: grid_cell_plan},
    'footprint': {FOOTPRINT_STAMP_ENTRY: footprint_stamp_plan},
    'solid-draw': {SOLID_DRAW_ENTRY: draw_solid_plan},
    'animation-step': {ANIMATION_STEP_ENTRY: animation_step_plan},
    'countdown-check': {COUNTDOWN_CHECK_ENTRY: countdown_check_plan},
    'collision-gate': {COLLISION_GATE_ENTRY: collision_gate_plan},
    'zone-check': {ZONE_CHECK_ENTRY: zone_check_plan},
    'particle-emit': {PARTICLE_EMIT_ENTRY: particle_emit_plan},
    'hazard-tick': {HAZARD_TICK_ENTRY: hazard_tick_plan},
    'conditions': {CONDITION_ENTRY: condition_plan},
    'pickups': {PICKUP_AWARD_ENTRY: pickup_award_plan},
    'walker': {WALKER_RESUME_ENTRY: walker_resume_plan},
    'projectile-launch': {LAUNCH_ENTRY: launch_plan},
    'projectile-resume': {PROJECTILE_RESUME_ENTRY: walker_resume_projectile_plan},
    'score-convert': {SCORE_CONVERT_ENTRY: score_convert_plan},
    'evaluator': {EVALUATOR_ENTRY: evaluator_plan},
    'proximity': {PROXIMITY_ENTRY: proximity_plan},
    'message-gate': {MESSAGE_GATE_ENTRY: message_gate_plan},
    'string-copy': {STRING_COPY_ENTRY: string_copy_plan},
    'next-random': {NEXT_RANDOM_ENTRY: next_random_plan},
    'effect-pool-add': {EFFECT_POOL_ADD_ENTRY: effect_pool_add_plan},
    'pickup-check': {PICKUP_CHECK_ENTRY: pickup_check_plan},
    'pickup-probe': {PICKUP_PROBE_ENTRY: pickup_probe_plan},
    'camera-sprites': {CAMERA_FOLLOW_ENTRY: camera_follow_plan, SPRITE_EMIT_ENTRY: sprite_emit_plan,
                       STATIC_EMIT_ENTRY: static_emit_plan, TABLE_RESET_ENTRY: table_reset_plan,
                       SPAWN_QUEUE_ENTRY: spawn_queue_plan, GRID_CELL_ENTRY: grid_cell_plan,
                       FOOTPRINT_STAMP_ENTRY: footprint_stamp_plan, SOLID_DRAW_ENTRY: draw_solid_plan,
                       ANIMATION_STEP_ENTRY: animation_step_plan, COUNTDOWN_CHECK_ENTRY: countdown_check_plan,
                       COLLISION_GATE_ENTRY: collision_gate_plan, ZONE_CHECK_ENTRY: zone_check_plan,
                       PARTICLE_EMIT_ENTRY: particle_emit_plan, HAZARD_TICK_ENTRY: hazard_tick_plan,
                       CONDITION_ENTRY: condition_plan, SCORE_CONVERT_ENTRY: score_convert_plan,
                       EVALUATOR_ENTRY: evaluator_plan, PROXIMITY_ENTRY: proximity_plan, PICKUP_AWARD_ENTRY: pickup_award_plan,
                       NEXT_RANDOM_ENTRY: next_random_plan, EFFECT_POOL_ADD_ENTRY: effect_pool_add_plan,
                       PICKUP_CHECK_ENTRY: pickup_check_plan, PICKUP_PROBE_ENTRY: pickup_probe_plan, WALKER_RESUME_ENTRY: walker_resume_plan,
                       LAUNCH_ENTRY: launch_plan, PROJECTILE_RESUME_ENTRY: walker_resume_projectile_plan,
                       MESSAGE_GATE_ENTRY: message_gate_plan, STRING_COPY_ENTRY: string_copy_plan},
}
MUTATIONS = {'camera-mutant-result': ('camera', _mutate_result),
             'conditions-mutant-outcome': ('conditions', _mutate_outcome),
             'pickups-mutant-result': ('pickups', _mutate_result),
             'walker-mutant-result': ('walker', _mutate_walk),
             'sprites-mutant-result': ('sprites', _mutate_result),
             'sprites-mutant-register': ('sprites', _mutate_register),
             'sprites-static-mutant-result': ('sprites-static', _mutate_result),
             'table-reset-mutant-result': ('table-reset', _mutate_result),
             'spawn-queue-mutant-result': ('spawn-queue', _mutate_result),
             'grid-cell-mutant-result': ('grid-cell', _mutate_address),
             'footprint-mutant-result': ('footprint', _mutate_result),
             # a register, not the stored list: the routine's own last write is the unconditional
             # LIST_HEAD pointer, and corrupting it can cascade into an address error in the
             # (unrelated, unrecovered) sprite-list flush that reads it later in the same frame.
             'solid-draw-mutant-result': ('solid-draw', _mutate_register),
             'animation-step-mutant-result': ('animation-step', _mutate_result),
             'countdown-check-mutant-result': ('countdown-check', _mutate_register),
             'collision-gate-mutant-result': ('collision-gate', _mutate_result),
             # a register: the 'held' and 'outside' arms (the great majority) store nothing durable
             # at all -- the whole box test is scratch a save/restore frame discards -- so the
             # generic "flip the last write" mutation would only corrupt already-dead stack space.
             'zone-check-mutant-result': ('zone-check', _mutate_register),
             'particle-emit-mutant-result': ('particle-emit', _mutate_result),
             'hazard-tick-mutant-result': ('hazard-tick', _mutate_result),
             'score-convert-mutant-result': ('score-convert', _mutate_result),
             'evaluator-mutant-outcome': ('evaluator', _mutate_outcome),
             'proximity-mutant-result': ('proximity', _mutate_result),
             'message-gate-mutant-result': ('message-gate', _mutate_result),
             'string-copy-mutant-result': ('string-copy', _mutate_result),
             # a register (the drawn word), not the stored cursor: the generic "flip the last write"
             # mutation corrupts the cursor itself, which can wrap onto an odd address and fault the
             # 68000 on its own next read -- a real crash, not the clean divergence a control needs.
             'next-random-mutant-result': ('next-random', _mutate_register),
             'effect-pool-add-mutant-result': ('effect-pool-add', _mutate_result),
             'pickup-check-mutant-result': ('pickup-check', _mutate_result),
             # the outcome, not a register (both d0 and d2 are scratch here, restored from the
             # caller-supplied record's own frame, so a register mutant is blind) and not the generic
             # "flip the last write" (the record's own D2 field is read by the still-unrecovered
             # 010CF8 coroutine system this same table feeds, which can fault the 68000 outright on a
             # corrupted value rather than diverge cleanly): dropping the writes entirely still leaves
             # the caller with the wrong (unset) record field, a clean and safe divergence.
             'pickup-probe-mutant-result': ('pickup-probe', _mutate_outcome),
             'projectile-launch-mutant-result': ('projectile-launch', _mutate_launch),
             'projectile-resume-mutant-result': ('projectile-resume', _mutate_walk)}


@dataclass
class Candidate:
    """``arm`` gates the recovered entries; ``on_gate`` plans from live RAM and lets the adapter admit or refuse.

    ``Machine.atomic`` is the admission point: it returns ``False`` with the
    machine unchanged when the scheduler cannot admit the whole plan before
    the deadline, and the original then runs the region (a fallback).
    """
    name: str = 'camera'
    last_refusal: str = 'machine admission'   # why the adapter refused the last span (_refusal_cause)
    stats: dict = field(default_factory=lambda: {
        'gates': 0, 'candidate_hits': 0, 'fallbacks': 0, 'fallback_reasons': {}, 'fallbacks_by_gate': {},
        'replaced_m68k_instructions': 0, 'charged_m68k_cycles': 0, 'direct_python_calls': 0,
        'seam_entries': 0, 'seam_completions': 0, 'seam_foreign_returns': 0, 'seam_deadline_fallbacks': 0})

    def __post_init__(self):
        if self.name not in PLANNERS and self.name not in MUTATIONS:
            raise ValueError(f'Unknown Gods recovery candidate: {self.name}')
        base, self.mutation = MUTATIONS.get(self.name, (self.name, None))
        self.planners = PLANNERS[base]

    @property
    def gate_pcs(self):
        return tuple(self.planners)

    def arm(self, machine):
        from .profile import GODS
        if machine.rom_sha256 != GODS.rom_sha256:
            raise UnsupportedCandidate('Gods recovery needs the supported Gods (USA) cartridge')
        machine.gates(list(self.gate_pcs))
        machine.candidate_identity = self.name

    def on_gate(self, machine, deadline):
        self.stats['gates'] += 1
        registers = machine.registers()
        pc = registers['pc']
        planner = self.planners.get(pc)
        if planner is None:
            return self._fallback(machine, pc, 'gate without a planner')
        try:
            plan = planner(machine, registers)
        except UnsupportedCandidate as error:
            return self._fallback(machine, pc, f'unsupported domain: {error}')
        if isinstance(plan, Seam):
            return self._run_seam(machine, deadline, plan, pc)
        if not self._admit(machine, deadline, plan):
            return self._fallback(machine, pc, self.last_refusal)
        return True

    def _refusal_cause(self, machine, plan):
        """Why the adapter refused a span, as the fallback reason: the observation deadline (the caller's
        instant precedes the span's end), the Z80 bank guard (the sound driver's bank register points
        at work RAM), a vertical interrupt inside the span, or another condition of the engine's."""
        if machine.refusal == 'deadline':
            return 'observation deadline'
        if machine.refusal == 'z80_bank':
            return 'z80 bank guard'
        board, tick = machine.board, machine.info['tick']
        next_vblank = (tick // board.frame_ticks) * board.frame_ticks + board.vblank_offset_ticks
        if next_vblank < tick:
            next_vblank += board.frame_ticks
        if (next_vblank - tick) // board.m68k_divider <= plan.cycles + 8:
            return 'vblank in span'
        return 'machine admission'

    def _admit(self, machine, deadline, plan):
        if self.mutation is not None:
            plan = self.mutation(plan)
        if not machine.atomic(target=deadline, cycles=plan.cycles, instructions=plan.instructions,
                              writes=list(plan.writes), registers=plan.registers, last_pc=plan.last_pc):
            self.last_refusal = self._refusal_cause(machine, plan)
            return False
        self.stats['candidate_hits'] += 1
        self.stats['replaced_m68k_instructions'] += plan.instructions
        self.stats['charged_m68k_cycles'] += plan.cycles
        self.stats['direct_python_calls'] += plan.direct_calls
        return True

    def _run_seam(self, machine, deadline, seam, pc):
        """Commit the prefix, let the original run the platform operation, admit the suffix at the resume."""
        if not self._admit(machine, deadline, seam.prefix):
            return self._fallback(machine, pc, self.last_refusal)
        self.stats['seam_entries'] += 1
        outcome = run_seam(machine, deadline, seam, admit=lambda plan: self._admit(machine, deadline, plan),
                           gates=self.gate_pcs)
        self.stats['gates'] += outcome.stops
        self.stats['seam_foreign_returns'] += outcome.foreign_returns
        if outcome.status == 'completed':
            self.stats['seam_completions'] += 1
            return True
        if outcome.status == 'deadline':
            # The frame's observation instant fell inside the platform operation:
            # the committed prefix stands and the original owns the rest of the activation.
            self.stats['seam_deadline_fallbacks'] += 1
            return self._fallback(machine, None, outcome.reason)
        # A declined or refused suffix: the original runs it from the resume.
        return self._fallback(machine, seam.resume_pc,
                              self.last_refusal if outcome.status == 'refused' else outcome.reason)

    def _fallback(self, machine, pc, reason):
        self.stats['fallbacks'] += 1
        reasons = self.stats['fallback_reasons']
        reasons[reason] = reasons.get(reason, 0) + 1
        gate = f'{(machine.info["pc"] if pc is None else pc):06X}'
        self.stats['fallbacks_by_gate'][gate] = self.stats['fallbacks_by_gate'].get(gate, 0) + 1
        if pc is not None:
            machine.gate(pc, bypass_once=True)
            machine.run(instructions=1)
        return False
