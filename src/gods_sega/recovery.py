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

from .boundary import (ACHIEVEMENT_DISPATCH_ENTRY, ACHIEVEMENT_SLOT_RESET_ENTRY, ACTION_CLEAR_GROUP_ENTRY, ACTION_RESET_ELAPSED_ENTRY,
                       ANIMATION_STEP_ENTRY, CAMERA_FOLLOW_ENTRY,
                       COLLISION_GATE_ENTRY, CONDITION_ENTRY, CONTACT_CONSUME_PRIMARY_ENTRY, CONTACT_CONSUME_SECONDARY_ENTRY,
                       CONTACT_SEARCH_ENTRY, COUNTDOWN_CHECK_ENTRY,
                       EFFECT_POOL_ADD_ENTRY, EVALUATOR_ENTRY, FOOTPRINT_STAMP_ENTRY, GRID_CELL_ENTRY, HAZARD_TICK_ENTRY,
                       LAUNCH_ENTRY, MESSAGE_GATE_ENTRY, NEXT_RANDOM_ENTRY, PARTICLE_EMIT_ENTRY, PICKUP_AWARD_ENTRY, PICKUP_CHECK_ENTRY,
                       PICKUP_PROBE_ENTRY, PLAYER_TAIL_ENTRY, PROJECTILE_RESUME_ENTRY, PROXIMITY_ENTRY, RECORD_ID_SCAN_ENTRY, SCORE_CONVERT_ENTRY, SLOT_SCAN_ENTRY, SOLID_DRAW_ENTRY,
                       SPAWN_QUEUE_ENTRY, SPRITE_EMIT_ENTRY, STATE0_ENTRY, STATE1_ENTRY, STATE5_ENTRY, STATE6_ENTRY, STATE9_ENTRY, STATE14_ENTRY, STATE26_ENTRY, STATE24_ENTRY, STATE25_ENTRY, STATIC_EMIT_ENTRY, STRING_COPY_ENTRY, TABLE_RESET_ENTRY,
                       TRAIL_CHECK_ENTRY, WALKER_RESUME_ENTRY, ZONE_CHECK_ENTRY, achievement_slot_dispatch_plan, achievement_slot_reset_plan,
                       action_clear_group_plan, action_reset_elapsed_plan,
                       animation_step_plan, camera_follow_plan,
                       collision_gate_plan, contact_consume_primary_plan, contact_consume_secondary_plan, contact_search_plan,
                       countdown_check_plan, draw_solid_plan, effect_pool_add_plan, evaluator_plan,
                       footprint_stamp_plan, condition_plan, grid_cell_plan, hazard_tick_plan, launch_plan, message_gate_plan,
                       movement_hit_primary_plan, movement_hit_secondary_plan,
                       next_random_plan, particle_emit_plan, pickup_award_plan, pickup_check_plan, pickup_probe_plan, player_tail_plan, proximity_plan,
                       record_id_scan_plan, score_convert_plan, slot_scan_plan, spawn_queue_plan, sprite_emit_plan, state0_plan, state1_plan, state5_plan, state6_plan, state9_plan, state14_plan, state26_plan, static_emit_plan, string_copy_plan, table_reset_plan,
                       trail_check_plan, walker_resume_plan, walker_resume_projectile_plan, zone_check_plan)


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


def _mutate_contact_outcome(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for the contact search: D0/D3 (0 found / 1 not found, this routine's own
    headline outcome) toggled, not nudged by one -- both are always exactly 0 or 1, so a blind '+1'
    (the generic register mutant) can leave a 'not found' occurrence nonzero either way and pass
    right through a caller's own tst/bne, blind on most of the routine's own activations (the very
    first one in the whole game, frame 2283 of fb408bc75597, is itself 'not found').  XOR 1 flips
    found and not-found into each other on every occurrence, not only the ones this candidate finds
    something on."""
    registers = dict(plan.registers)
    for name in ('d0', 'd3'):
        if name in registers:
            registers[name] = registers[name] ^ 1
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_register(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for a seam's register contract: d0 off by one in every admitted plan."""
    registers = dict(plan.registers)
    registers['d0'] = (registers.get('d0', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


_FOLLOW_POINT_ADDRESSES = frozenset((0xFFF3EE, 0xFFF3EF, 0xFFF3F0, 0xFFF3F1))


def _mutate_follow_point(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for the player tail: a follow-point byte off (FOLLOW_X or FOLLOW_Y, whichever
    this occurrence's own follow-point step wrote last) -- the camera consumes it next tick.  A
    'hold'/'hold' occurrence (about half of them) writes neither and passes through unmutated: the
    ONLY other write every occurrence makes is STATE_COUNTER, read back by the NEXT activation's own
    state-table re-index into a ROM descriptor table with no bounds check of its own -- corrupting it
    risks an M68000 address error (confirmed: 001312's own tile-copy loop faulted on a garbage
    descriptor pointer under an earlier version of this control), not a clean divergence."""
    follow_indices = [index for index, (address, _) in enumerate(plan.writes) if address in _FOLLOW_POINT_ADDRESSES]
    if not follow_indices:
        return plan
    index = follow_indices[-1]
    address, value = plan.writes[index]
    writes = plan.writes[:index] + ((address, (value + 1) & 0xFF),) + plan.writes[index + 1:]
    return AtomicPlan(plan.cycles, plan.instructions, writes, plan.registers, plan.last_pc, plan.direct_calls)


def _mutate_address(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for a routine whose result is an address in a0 the caller dereferences: one cell
    off.  (A residue register such as d0 is not a control the game can see: with the observation instant
    in the idle window the caller has long overwritten it, and the mutant passed.)"""
    registers = dict(plan.registers)
    registers['a0'] = (registers.get('a0', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_state0_counter(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for state 0: the same shape as `_mutate_state1_counter`, for the same reason
    (its own 'shared-unchanged'/'shared-reset' arms leave the plan's own semantic stores empty)."""
    registers = dict(plan.registers)
    registers['d7'] = registers.get('d7', 0) ^ 1
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_state1_counter(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for state 1: the generic "flip the last write" mutant crashes the machine on
    two of its arms (a stack-scratch byte from the composed grid_cell call, on 'shared-unchanged'/
    'shared-reset' -- both leave the plan's own semantic stores empty, so plan.writes[-1] is stack
    residue, and one of its bytes is later read back as an address).  d7 (STATE_COUNTER) is real on
    every arm instead: the shared tail's own first instruction (0075D6, the separately-armed gate
    this plan hands off to) stores it into FFFFF190 unconditionally, so a byte off here becomes an
    observable RAM byte one instruction later without touching anything the machine might dereference."""
    registers = dict(plan.registers)
    registers['d7'] = registers.get('d7', 0) ^ 1
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_state14_counter(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for state 14: the same d7-XOR-1 shape as states 0/1, for the same reason --
    every arm (frozen, settle, the rejoin-main handoff, and the main EA20 dispatch) exits to the
    SAME shared tail gate (0075D6), whose own first instruction stores d7 into FFFFF190 unconditionally,
    turning a flipped bit here into an observable RAM byte one instruction later."""
    registers = dict(plan.registers)
    registers['d7'] = registers.get('d7', 0) ^ 1
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
    'achievement-slot-reset': {ACHIEVEMENT_SLOT_RESET_ENTRY: achievement_slot_reset_plan},
    'achievement-slot-dispatch': {ACHIEVEMENT_DISPATCH_ENTRY: achievement_slot_dispatch_plan},
    'slot-scan': {SLOT_SCAN_ENTRY: slot_scan_plan},
    'record-id-scan': {RECORD_ID_SCAN_ENTRY: record_id_scan_plan},
    'action-reset-elapsed': {ACTION_RESET_ELAPSED_ENTRY: action_reset_elapsed_plan},
    'action-clear-group': {ACTION_CLEAR_GROUP_ENTRY: action_clear_group_plan},
    'player-tail': {PLAYER_TAIL_ENTRY: player_tail_plan},
    'contact-search': {CONTACT_SEARCH_ENTRY: contact_search_plan},
    'contact-consume-primary': {CONTACT_CONSUME_PRIMARY_ENTRY: contact_consume_primary_plan},
    'contact-consume-secondary': {CONTACT_CONSUME_SECONDARY_ENTRY: contact_consume_secondary_plan},
    'state-24': {STATE24_ENTRY: movement_hit_primary_plan},
    'state-25': {STATE25_ENTRY: movement_hit_secondary_plan},
    'trail-check': {TRAIL_CHECK_ENTRY: trail_check_plan},
    'state-1': {STATE1_ENTRY: state1_plan},
    'state-0': {STATE0_ENTRY: state0_plan},
    'state-5': {STATE5_ENTRY: state5_plan},
    'state-6': {STATE6_ENTRY: state6_plan},
    'state-9': {STATE9_ENTRY: state9_plan},
    'state-26': {STATE26_ENTRY: state26_plan},
    'state-14': {STATE14_ENTRY: state14_plan},
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
                       MESSAGE_GATE_ENTRY: message_gate_plan, STRING_COPY_ENTRY: string_copy_plan,
                       ACHIEVEMENT_SLOT_RESET_ENTRY: achievement_slot_reset_plan,
                       ACHIEVEMENT_DISPATCH_ENTRY: achievement_slot_dispatch_plan,
                       SLOT_SCAN_ENTRY: slot_scan_plan, RECORD_ID_SCAN_ENTRY: record_id_scan_plan,
                       ACTION_RESET_ELAPSED_ENTRY: action_reset_elapsed_plan, ACTION_CLEAR_GROUP_ENTRY: action_clear_group_plan,
                       PLAYER_TAIL_ENTRY: player_tail_plan, CONTACT_SEARCH_ENTRY: contact_search_plan,
                       CONTACT_CONSUME_PRIMARY_ENTRY: contact_consume_primary_plan,
                       CONTACT_CONSUME_SECONDARY_ENTRY: contact_consume_secondary_plan,
                       STATE24_ENTRY: movement_hit_primary_plan, STATE25_ENTRY: movement_hit_secondary_plan,
                       TRAIL_CHECK_ENTRY: trail_check_plan, STATE1_ENTRY: state1_plan, STATE0_ENTRY: state0_plan,
                       STATE5_ENTRY: state5_plan, STATE6_ENTRY: state6_plan, STATE9_ENTRY: state9_plan,
                       STATE26_ENTRY: state26_plan, STATE14_ENTRY: state14_plan},
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
             'projectile-resume-mutant-result': ('projectile-resume', _mutate_walk),
             'achievement-slot-reset-mutant-result': ('achievement-slot-reset', _mutate_result),
             # a register, not the generic "flip the last write": that write is the bsr's own return
             # address for the seam arm (an odd flip is an M68000 address error, achievement-slot-reset's
             # own lesson) and is empty outright for the no-match arm.  D0 is real: 0047DA marks slot D0
             # empty and 001648 indexes its own VDP table by it, and the no-match arm does not touch D0
             # at all, so wrongly claiming it changed is itself an observable divergence.
             'achievement-slot-dispatch-mutant-result': ('achievement-slot-dispatch', _mutate_register),
             # a register, the same reasoning as achievement-slot-dispatch's own mutant: D0 carries the
             # matched slot into 0047DA (and empty/nonempty otherwise) on the seam arm, and is untouched
             # on the no-match/all-false/gate-false arms, so a wrong claim that it changed is itself
             # observable; the generic "flip the last write" is blind on the (most common) arms with no
             # durable write at all.
             'slot-scan-mutant-result': ('slot-scan', _mutate_register),
             # NOT a register: D0 also selects the icon upload's own VRAM table entry inside the ceded
             # 001648 (achievement-slot-dispatch's own D0), and this routine's own witnessed matches
             # include icon slot 3 -- flipping D0 there reaches table index 4, out of 001648's own
             # four entries, which faults the platform (an M68000-adjacent VDP command fault, not a
             # clean divergence) rather than diverging.  The last write inside the seam's own prefix is
             # always achievement_slot_reset's own real semantic store (the ACHIEVEMENT_SLOTS array
             # entry, inserted last by achievement_slot_reset_plan itself); "flip the last write" is
             # blind on the far more common no-call arms (empty writes) but clean and safe on the seam.
             'record-id-scan-mutant-result': ('record-id-scan', _mutate_result),
             'action-reset-elapsed-mutant-result': ('action-reset-elapsed', _mutate_result),
             'action-clear-group-mutant-result': ('action-clear-group', _mutate_result),
             'player-tail-mutant-result': ('player-tail', _mutate_follow_point),
             # a register, not the generic "flip the last write": a found sub-pass's own last store
             # is the hit record's own ADDRESS (a long) into one of the three CONTACT_SLOTS, later
             # dereferenced by the still-unrecovered 012DA0/012E5A family -- corrupting its low byte
             # risks an odd-address fault there rather than a clean divergence (the same risk the
             # walker's and pickup-probe's own mutants already had to route around).  Not the generic
             # register mutant either (a blind '+1' on D0's own 0/1 outcome can stay nonzero either
             # way): see `_mutate_contact_outcome`.
             'contact-search-mutant-result': ('contact-search', _mutate_contact_outcome),
             # the last write is a status-group field (a position, an index or a small type tag)
             # inside the hit record itself, or the pool table's own sentinel -- none of them a
             # pointer another region dereferences, unlike contact_search's own found slots.
             'contact-consume-primary-mutant-result': ('contact-consume-primary', _mutate_result),
             'contact-consume-secondary-mutant-result': ('contact-consume-secondary', _mutate_result),
             # the last write is STATE_INDEX (a transition) or CONTACT_DIRECTION/GRID_Y otherwise --
             # STATE_INDEX drives the very next tick's own dispatch, and GRID_Y feeds the
             # already-recovered camera follow step, both quickly observable.
             'state-24-mutant-result': ('state-24', _mutate_result),
             'state-25-mutant-result': ('state-25', _mutate_result),
             'trail-check-mutant-result': ('trail-check', _mutate_result),
             'state-1-mutant-result': ('state-1', _mutate_state1_counter),
             'state-0-mutant-result': ('state-0', _mutate_state0_counter),
             # NOT the generic "flip the last write": on the 'handoff'/'gate'-found arms that last
             # write is STATE_COUNTER, but its own LIVE REGISTER (not the RAM byte) is what the
             # shared tail's own state-table re-index (0076B8, read fresh from D7, not re-derived
             # from RAM -- game.player.state_table_reindex's own docstring) uses to index an
             # unbounded-looking ROM table one instruction later -- corrupting it faulted the
             # machine outright on a real fixture (an unmapped read past the table), the same hazard
             # `_mutate_follow_point` already routes around for the shared tail's own STATE_COUNTER.
             # Dropping the writes instead leaves STATE_COUNTER/STATE_INDEX stale for the NEXT
             # activation's own dispatch -- safe (never an out-of-range table index THIS tick) and
             # still real (a stale counter or index is a different, observable state next time this
             # state re-enters).
             'state-5-mutant-result': ('state-5', _mutate_outcome),
             'state-6-mutant-result': ('state-6', _mutate_outcome),
             # the same reasoning as states 5/6's own mutant: the 'countdown' arm's own exit D7
             # (whichever of 4/5/untouched the head normalized it to) feeds the shared tail's own
             # state-table re-index the same unbounded way; every terminal arm's own transition
             # writes STATE_INDEX safely, but F19C (the fall timer) also feeds this candidate's own
             # fall-table read next activation -- dropping the writes is the one shape safe on
             # every arm at once.
             'state-9-mutant-result': ('state-9', _mutate_outcome),
             # the same reasoning: STATE_INDEX/F19C/D7 all feed the shared tail's own re-index or a
             # future activation's own dispatch the same unbounded way.
             'state-26-mutant-result': ('state-26', _mutate_outcome),
             'state-14-mutant-result': ('state-14', _mutate_state14_counter)}


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
