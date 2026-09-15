"""Gate dispatch for recovered Gods regions: one planner per gate, admission through ``Machine.atomic``."""
from __future__ import annotations

from dataclasses import dataclass, field

from .boundary import AtomicPlan, UnsupportedCandidate, CAMERA_FOLLOW_ENTRY, camera_follow_plan


def _mutate_result(plan: AtomicPlan) -> AtomicPlan:
    """Negative control: one stored byte off by one.  A PASS with this candidate would mean nothing is compared."""
    address, value = plan.writes[-1]
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes[:-1] + ((address, (value + 1) & 0xFF),),
                      plan.registers, plan.last_pc, plan.direct_calls)


PLANNERS = {
    'camera': {CAMERA_FOLLOW_ENTRY: camera_follow_plan},
}
MUTATIONS = {'camera-mutant-result': ('camera', _mutate_result)}


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
        'replaced_m68k_instructions': 0, 'charged_m68k_cycles': 0, 'direct_python_calls': 0})

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
        if self.mutation is not None:
            plan = self.mutation(plan)
        if not machine.atomic(target=deadline, cycles=plan.cycles, instructions=plan.instructions,
                              writes=list(plan.writes), registers=plan.registers, last_pc=plan.last_pc):
            return self._fallback(machine, pc, 'scheduler admission')
        self.stats['candidate_hits'] += 1
        self.stats['replaced_m68k_instructions'] += plan.instructions
        self.stats['charged_m68k_cycles'] += plan.cycles
        self.stats['direct_python_calls'] += plan.direct_calls
        return True

    def _fallback(self, machine, pc, reason):
        self.stats['fallbacks'] += 1
        reasons = self.stats['fallback_reasons']
        reasons[reason] = reasons.get(reason, 0) + 1
        gate = f'{pc:06X}'
        self.stats['fallbacks_by_gate'][gate] = self.stats['fallbacks_by_gate'].get(gate, 0) + 1
        machine.gate(pc, bypass_once=True)
        machine.run(instructions=1)
        return False
