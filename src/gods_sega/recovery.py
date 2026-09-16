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

from .boundary import (CAMERA_FOLLOW_ENTRY, FOOTPRINT_STAMP_ENTRY, GRID_CELL_ENTRY, SPAWN_QUEUE_ENTRY,
                       SPRITE_EMIT_ENTRY, STATIC_EMIT_ENTRY, TABLE_RESET_ENTRY, camera_follow_plan,
                       footprint_stamp_plan, grid_cell_plan, spawn_queue_plan, sprite_emit_plan,
                       static_emit_plan, table_reset_plan)


def _mutate_result(plan: AtomicPlan) -> AtomicPlan:
    """Negative control: one stored byte off by one.  A PASS with this candidate would mean nothing is compared."""
    if not plan.writes:
        return plan
    address, value = plan.writes[-1]
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes[:-1] + ((address, (value + 1) & 0xFF),),
                      plan.registers, plan.last_pc, plan.direct_calls)


def _mutate_register(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for a seam's register contract: d0 off by one in every admitted plan."""
    registers = dict(plan.registers)
    registers['d0'] = (registers.get('d0', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


PLANNERS = {
    'camera': {CAMERA_FOLLOW_ENTRY: camera_follow_plan},
    'sprites': {SPRITE_EMIT_ENTRY: sprite_emit_plan},
    'sprites-static': {STATIC_EMIT_ENTRY: static_emit_plan},
    'table-reset': {TABLE_RESET_ENTRY: table_reset_plan},
    'spawn-queue': {SPAWN_QUEUE_ENTRY: spawn_queue_plan},
    'grid-cell': {GRID_CELL_ENTRY: grid_cell_plan},
    'footprint': {FOOTPRINT_STAMP_ENTRY: footprint_stamp_plan},
    'camera-sprites': {CAMERA_FOLLOW_ENTRY: camera_follow_plan, SPRITE_EMIT_ENTRY: sprite_emit_plan,
                       STATIC_EMIT_ENTRY: static_emit_plan, TABLE_RESET_ENTRY: table_reset_plan,
                       SPAWN_QUEUE_ENTRY: spawn_queue_plan, GRID_CELL_ENTRY: grid_cell_plan,
                       FOOTPRINT_STAMP_ENTRY: footprint_stamp_plan},
}
MUTATIONS = {'camera-mutant-result': ('camera', _mutate_result),
             'sprites-mutant-result': ('sprites', _mutate_result),
             'sprites-mutant-register': ('sprites', _mutate_register),
             'sprites-static-mutant-result': ('sprites-static', _mutate_result),
             'table-reset-mutant-result': ('table-reset', _mutate_result),
             'spawn-queue-mutant-result': ('spawn-queue', _mutate_result),
             'grid-cell-mutant-result': ('grid-cell', _mutate_register),
             'footprint-mutant-result': ('footprint', _mutate_result)}


@dataclass
class Candidate:
    """``arm`` gates the recovered entries; ``on_gate`` plans from live RAM and lets the adapter admit or refuse.

    ``Machine.atomic`` is the admission point: it returns ``False`` with the
    machine unchanged when the scheduler cannot admit the whole plan before
    the deadline, and the original then runs the region (a fallback).
    """
    name: str = 'camera'
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
            return self._fallback(machine, pc, 'scheduler admission')
        return True

    def _admit(self, machine, deadline, plan):
        if self.mutation is not None:
            plan = self.mutation(plan)
        if not machine.atomic(target=deadline, cycles=plan.cycles, instructions=plan.instructions,
                              writes=list(plan.writes), registers=plan.registers, last_pc=plan.last_pc):
            return False
        self.stats['candidate_hits'] += 1
        self.stats['replaced_m68k_instructions'] += plan.instructions
        self.stats['charged_m68k_cycles'] += plan.cycles
        self.stats['direct_python_calls'] += plan.direct_calls
        return True

    def _run_seam(self, machine, deadline, seam, pc):
        """Commit the prefix, let the original run the platform operation, admit the suffix at the resume."""
        if not self._admit(machine, deadline, seam.prefix):
            return self._fallback(machine, pc, 'scheduler admission')
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
        return self._fallback(machine, seam.resume_pc, outcome.reason)

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
