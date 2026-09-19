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
                       SPAWN_PUFF_BOX_ENTRY, spawn_puff_box_plan,
                       SPAWN_EFFECT_SLOT_ENTRY, spawn_effect_slot_plan,
                       AIM_CUE_ENTRY, aim_cue_update_plan, AIM_POOL_RESET_ENTRY, aim_pool_reset_plan, AIM_POOL_ADD_ENTRY, aim_pool_add_plan,
                       AIM_WINDOW_ADDRESS_ENTRY, aim_window_address_plan,
                       AIM_PROBE_MARK_ENTRY, aim_probe_mark_plan,
                       AIM_PROBE_MARK_STORE_ENTRY, aim_probe_mark_store_plan,
                       AIM_RAY_MARCH_FORWARD_ENTRY, aim_ray_march_forward_plan,
                       AIM_RAY_MARCH_BACKWARD_ENTRY, aim_ray_march_backward_plan,
                       AIM_POOL_SCAN_ENTRY, aim_pool_scan_plan,
                       AIM_TARGET_SCAN_ENTRY, aim_target_scan_plan,
                       AIM_TARGET_SCAN_BACKWARD_ENTRY, aim_target_scan_backward_plan,
                       AIM_TARGET_RESOLVE_ENTRY, aim_target_resolve_plan,
                       AIM_SEARCH_SCAN_ENTRY, aim_search_scan_plan,
                       AIM_SEARCH_DISPATCH_ENTRY, aim_search_dispatch_plan,
                       AIM_SEARCH_FLAG_DISPATCH_ENTRY, aim_search_flag_dispatch_plan,
                       AIM_KIND_HANDLER_76_ENTRY, aim_kind_handler_76_plan,
                       AIM_KIND_HANDLER_50_ENTRY, aim_kind_handler_50_plan,
                       EFFECT_SLOT_FIND_ENTRY, effect_slot_find_free_plan,
                       EFFECT_SLOT_ADD_ENTRY, effect_slot_add_plan,
                       BCD_COUNTER_ADD_ENTRY, bcd_counter_add_plan,
                       CREATURE_DEATH_BCD_ENTRY, creature_death_bcd_plan,
                       CREATURE_FAMILY_ENTRY, creature_family_plan,
                       CREATURE_WALK_ENTRY, creature_walk_plan,
                       FLOATING_ICON_SPAWN_ENTRY, floating_icon_spawn_plan,
                       SPAWN_FIND_FREE_ENTRY, spawn_table_find_free_plan, SPAWN_TABLE_ADD_ENTRY, spawn_table_add_plan,
                       SPAWN_SCAN_ENTRY, spawn_scan_plan,
                       ANIMATION_STEP_ENTRY, ATTACK_UPDATE_ENTRY, CAMERA_FOLLOW_ENTRY, CREATURE_GRID_CELL_ENTRY, CREATURE_PICKUP_CHECK_ENTRY, EVENT_CONSUME_ENTRY,
                       COLLISION_GATE_ENTRY, CONDITION_ENTRY, CONTACT_CONSUME_PRIMARY_ENTRY, CONTACT_CONSUME_SECONDARY_ENTRY,
                       CONTACT_SEARCH_ENTRY, COUNTDOWN_CHECK_ENTRY,
                       AF3C_ENTRY, EFFECT_POOL_ADD_ENTRY, EVALUATOR_ENTRY, FALL_KIND_UPDATE_ENTRY, FALL_KIND_UPDATE_MIRROR_ENTRY, FOOTPRINT_STAMP_ENTRY, GRID_CELL_ENTRY, GROUND_CONTACT_UPDATE_ENTRY, GROUND_CONTACT_UPDATE_MIRROR_ENTRY, GROUND_EDGE_TEST_ENTRY, HAZARD_TICK_ENTRY,
                       OBJECT_TILE_ENTRY, object_tile_plan,
                       OBJECT_KIND_DISPATCH_ENTRY, object_kind_dispatch_plan,
                       PICKUP_AWARD_GROUP_ENTRY, pickup_award_group_plan,
                       QUEUE_APPEND_ENTRY, queue_append_plan,
                       ACCUMULATOR_0_ENTRY, accumulator_0_plan, ACCUMULATOR_3_ENTRY, accumulator_3_plan,
                       ACCUMULATOR_19_ENTRY, accumulator_19_plan, ACCUMULATOR_21_ENTRY, accumulator_21_plan,
                       SOUND_CUE_PAIR_ENTRY, sound_cue_pair_plan,
                       COPY_TABLE_14_ENTRY, copy_table_14_plan, COPY_TABLE_15_ENTRY, copy_table_15_plan,
                       COPY_TABLE_16_ENTRY, copy_table_16_plan,
                       BUMP_TALLY_1_ENTRY, bump_tally_1_plan, BUMP_TALLY_2_ENTRY, bump_tally_2_plan,
                       HALF_FRAME_COUNTER_ENTRY, half_frame_counter_plan,
                       OBJECT_ACTIVITY_GATE_ENTRY, object_activity_gate_plan,
                       KIND_FRAME_OFFSET_ENTRY, LAUNCH_ENTRY, MESSAGE_GATE_ENTRY, NEXT_RANDOM_ENTRY, PARTICLE_EMIT_ENTRY, PICKUP_AWARD_ENTRY, PICKUP_CHECK_ENTRY,
                       PICKUP_PROBE_ENTRY, PLAYER_STATE_ENTRY, PLAYER_TAIL_ENTRY, PROJECTILE_RESUME_ENTRY, PROXIMITY_ENTRY, RECORD_ID_SCAN_ENTRY, SCORE_CONVERT_ENTRY, SLOT_SCAN_ENTRY, SOLID_DRAW_ENTRY,
                       SPAWN_QUEUE_ENTRY, SPRITE_EMIT_ENTRY, STATE0_ENTRY, STATE1_ENTRY, STATE2_ENTRY, STATE10_ENTRY, STATE3_ENTRY, STATE4_ENTRY, STATE5_ENTRY, STATE6_ENTRY, STATE8_ENTRY, STATE9_ENTRY, STATE11_ENTRY, STATE12_ENTRY, STATE13_ENTRY, STATE14_ENTRY, STATE16_ENTRY, STATE17_ENTRY, STATE18_ENTRY, STATE19_ENTRY, STATE21_ENTRY, STATE22_ENTRY, STATE23_ENTRY, STATE26_ENTRY, STATE_26_ENTRY, STATE27_ENTRY, STATE28_ENTRY, STATE24_ENTRY, STATE25_ENTRY, STATIC_EMIT_ENTRY, STRING_COPY_ENTRY, TABLE_RESET_ENTRY,
                       TRAIL_CHECK_ENTRY, WALKER_RESUME_ENTRY, ZONE_CHECK_ENTRY, achievement_slot_dispatch_plan, achievement_slot_reset_plan,
                       action_clear_group_plan, action_reset_elapsed_plan,
                       animation_step_plan, attack_update_plan, camera_follow_plan, creature_grid_cell_plan, creature_grid_cell_d0d1_plan, creature_pickup_check_plan, event_consume_plan,
                       collision_gate_plan, contact_consume_primary_plan, contact_consume_secondary_plan, contact_search_plan,
                       countdown_check_plan, draw_solid_plan, effect_pool_add_plan, evaluator_plan, fall_kind_update_plan, fall_kind_update_mirror_plan,
                       footprint_stamp_plan, condition_plan, grid_cell_plan, ground_contact_update_plan, ground_contact_update_mirror_plan, ground_edge_test_plan, hazard_tick_plan, kind_frame_offset_plan, launch_plan, message_gate_plan,
                       movement_hit_primary_plan, movement_hit_secondary_plan,
                       next_random_plan, particle_emit_plan, pickup_award_plan, pickup_check_plan, pickup_probe_plan, player_state_plan, player_tail_plan, proximity_plan,
                       record_id_scan_plan, score_convert_plan, slot_scan_plan, spawn_queue_plan, sprite_emit_plan, state0_plan, state1_plan, state2_plan, state10_plan, state3_plan, state4_plan, state5_plan, state6_plan, state8_plan, state9_plan, state11_plan, state12_plan, state13_plan, state14_plan, state16_plan, state17_plan, state18_plan, state19_plan, state21_plan, state22_plan, state23_plan, state26_plan, state_26_plan, state27_plan, state28_plan, static_emit_plan, string_copy_plan, table_reset_plan,
                       trail_check_plan, walker_resume_plan, walker_resume_projectile_plan, zone_check_plan)


def _mutate_result(plan: AtomicPlan) -> AtomicPlan:
    """Negative control: one stored byte off by one.  A PASS with this candidate would mean nothing is compared."""
    if not plan.writes:
        return plan
    address, value = plan.writes[-1]
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes[:-1] + ((address, (value + 1) & 0xFF),),
                      plan.registers, plan.last_pc, plan.direct_calls)


def _mutate_aim_target_resolve(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00B6AE: the FIRST stored byte, not the last -- the last one or four bytes
    of plan.writes are always the internal-call stack residue (00AF3C/00B32E/00B05A's own return
    address, dead: popped by this routine's own rts before any frame boundary, the same class of blind
    spot 009D6C's own kind_frame_offset mutant found), which is empty writes for the two-empty-slots
    occurrence and otherwise NEVER the mark byte or the pool/best-registry stores that are this
    region's own real, observable effect."""
    if not plan.writes:
        return plan
    address, value = plan.writes[0]
    return AtomicPlan(plan.cycles, plan.instructions, ((address, (value + 1) & 0xFF),) + plan.writes[1:],
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


def _mutate_spawn_find_free(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00B8C2: A0 one WHOLE slot off (the module's own SPAWN_TABLE_STRIDE), not
    one byte -- a plain +1 (``_mutate_address``) leaves A0 odd, and the caller's own `move.l (a5),(a0)+`
    (00B920) faults the 68000 with an address error on a long write to an odd address instead of
    diverging cleanly; a whole-slot offset stays long-aligned and lands the write in the ADJACENT slot,
    a real consequence the game consumes without faulting."""
    from .game import creatures
    registers = dict(plan.registers)
    registers['a0'] = (registers.get('a0', 0) + creatures.SPAWN_TABLE_STRIDE) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_creature_grid_cell(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00AA38: A1 (the grid-cell address, the routine's own real output) off by
    one.  D0/D1 are dead residue at both real call sites (00ACA0/00AD88's own tails immediately
    overwrite D0 from (a5) before ever reading it, and neither reads D1 at all): the same "flip the
    address a caller dereferences" shape grid-cell's own mutant (_mutate_address) already uses, on A1
    instead of A0 since that is this routine's own output register."""
    registers = dict(plan.registers)
    registers['a1'] = (registers.get('a1', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_ground_edge_outcome(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00AD68: D1 (0 or 1, the routine's only real output -- both real call sites,
    00ACA0's and 00AD88's own tails, follow the bsr immediately with tst.w d1/beq) XOR 1, the same
    "flip a boolean 0/1 outcome, not a blind +1" shape contact_search's own mutant uses (a blind +1
    could stay nonzero either way).  D0 (x_low5) is dead residue at both call sites."""
    registers = dict(plan.registers)
    if 'd1' in registers:
        registers['d1'] = registers['d1'] ^ 1
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_creature_grid_cell_d0d1(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00AF3C: A2 (the grid-cell address, the routine's own real output -- both
    real call sites, 00AA76's and 00AB50's own tails, dereference it immediately) off by one, the same
    "flip the address a caller dereferences" shape creature_grid_cell's own mutant already uses."""
    registers = dict(plan.registers)
    registers['a2'] = (registers.get('a2', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_effect_slot_find(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00004AAA: A5 (the found slot's own address, the routine's own real output
    -- its only real caller, 00010E28, writes a whole record through it immediately) off by one WHOLE
    slot (its own 8-byte stride, not a raw +1: a real caller word-writes through A5, and an odd
    address there is a genuine M68000 address error, not a control -- this leaf writes no RAM of its
    own, so _mutate_result would be a no-op)."""
    registers = dict(plan.registers)
    registers['a5'] = (registers.get('a5', 0) + 8) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_aim_probe(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00B524 and 00B62A: AIM_SEARCH_BEST_INDEX's own low byte off by one when a
    'found' occurrence wrote it (read back by every later probe's own found-tail, and by 00B588's own
    next AIM_POOL entry); else AIM_POOL_COUNT's own low byte when a 'store' occurrence wrote it
    (00B62A only -- read back by aim_pool_add's own next call and by 00B588's own outer loop bound);
    else pass through unmutated, the SAME "about half the occurrences write nothing to flip" shape
    _mutate_follow_point already uses -- every OTHER write here is dead call-return stack residue,
    popped before any frame boundary (_mutate_aim_target_resolve's own class of blind spot)."""
    from .game import creatures
    for target in (creatures.AIM_SEARCH_BEST_INDEX, creatures.AIM_POOL_COUNT):
        indices = [index for index, (address, _) in enumerate(plan.writes) if address == (target + 1) & 0xFFFFFF]
        if indices:
            index = indices[0]
            address, value = plan.writes[index]
            writes = plan.writes[:index] + ((address, (value + 1) & 0xFF),) + plan.writes[index + 1:]
            return AtomicPlan(plan.cycles, plan.instructions, writes, plan.registers, plan.last_pc, plan.direct_calls)
    return plan


def _mutate_aim_ray_march(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00B354/00B440: AIM_RAY_STEP_INDEX's own low byte (F2D4, the routine's own
    real output -- 00B62A's own D7 is derived straight from it, every witnessed occurrence) off by 4,
    not 1: 00B62A's own D7 = (F2D4 >> 2) + ..., so a plain +1 changes the shifted result on only one of
    four occurrences (the SAME "flip across the test, not by one" caution grinder-protocol.md already
    names for a value consumed through a shift/mask) -- +4 changes >>2's own result by exactly 1 on
    every occurrence.  Always present (the routine's own last write, every activation): no fallback
    needed, unlike _mutate_aim_probe's own 'about half the occurrences write nothing real' shape."""
    from .game import creatures
    target = (creatures.AIM_RAY_STEP_INDEX + 1) & 0xFFFFFF
    for index, (address, value) in enumerate(plan.writes):
        if address == target:
            writes = plan.writes[:index] + ((address, (value + 4) & 0xFF),) + plan.writes[index + 1:]
            return AtomicPlan(plan.cycles, plan.instructions, writes, plan.registers, plan.last_pc, plan.direct_calls)
    return plan


def _mutate_aim_window_address(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00B32E: A0 (the computed address, this leaf's own real output -- every
    known caller dereferences or stores through it) off by one, the SAME shape
    creature_grid_cell_d0d1's own mutant uses; the leaf stores nothing of its own to flip instead."""
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


def _mutate_kind_frame_offset(plan: AtomicPlan) -> AtomicPlan:
    """Negative control for 00AA50: D2, the routine's own real result (pushed as 00A922's own
    argument immediately after the call, and read directly by the ground/fall kind handlers), off by
    one.  Not the generic _mutate_register (D0): this leaf's own D0 is dispatch scratch it fully
    overwrites from a moveq before ever using it, dead by the time any caller could read it back.
    Confirmed empirically (18 Sep): this control faults the M68000 with an address error deep in the
    still-unrecovered chain D2 feeds (00A922 -> ... -> 00126A's own sprite emitter), the same "real
    consequence of the corruption, not a control failure" class states 22/23's own mutants hit --
    history-verify's own crash-tolerant comparison reports it as DIVERGENCE the same way."""
    registers = dict(plan.registers)
    registers['d2'] = (registers.get('d2', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_player_state_counter(plan) -> AtomicPlan:
    """Negative control for the composed player state family (005700): STATE_COUNTER (D7) off by
    one, the same shape states 0/1/14's own mutants already draw -- every witnessed activation (100%
    of the coordinator's own tally, `fb408bc75597`'s 13,488 of 13,488) takes the active dispatch arm,
    handing D7 through this plan's own register file to the separately-armed player-tail gate one
    step later, whose own first instruction stores it into FFFFF190 unconditionally.  Blind only on
    the FROZEN_FLAG/ACTIVE_GATE inactive arm, where this planner calls player_tail_plan itself and
    its own prefix already bakes STATE_COUNTER into a RAM write rather than leaving it live in a
    register -- real ROM, but unwitnessed by any of the eight recordings (docs/gods/ledger.md), so
    this blindness never reaches a `history-verify --expect divergence` run."""
    if isinstance(plan, Seam):
        registers = dict(plan.prefix.registers)
        if 'd7' not in registers:
            return plan
        registers['d7'] = registers['d7'] ^ 1
        prefix = AtomicPlan(plan.prefix.cycles, plan.prefix.instructions, plan.prefix.writes, registers,
                            plan.prefix.last_pc, plan.prefix.direct_calls)
        return Seam(prefix=prefix, resume_pc=plan.resume_pc, stack_basis=plan.stack_basis,
                   guards=plan.guards, suffix=plan.suffix, expect=plan.expect)
    registers = dict(plan.registers)
    registers['d7'] = registers.get('d7', 0) ^ 1
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_creature_family(plan) -> AtomicPlan:
    """Negative control for the composed creature family (00A772): D0 (the ceded particle_emit's own
    X argument) off by one.  particle_emit reads D0 immediately on entry to pick its own arm and to
    build its own record -- observable on every admitted occurrence, offscreen-x/y and upload alike,
    unlike a write-based mutant, which would have to pick one of this seam's own stack-residue writes
    (the entry D7 word, the D2 word, an internal call's own return address) and risk landing on
    something dead by the ceded block's own rts, the same blind spot 00B6AE's own mutant note names."""
    if isinstance(plan, Seam):
        registers = dict(plan.prefix.registers)
        registers['d0'] = (registers.get('d0', 0) + 1) & 0xFFFFFFFF
        prefix = AtomicPlan(plan.prefix.cycles, plan.prefix.instructions, plan.prefix.writes, registers,
                            plan.prefix.last_pc, plan.prefix.direct_calls)
        return Seam(prefix=prefix, resume_pc=plan.resume_pc, stack_basis=plan.stack_basis,
                   guards=plan.guards, suffix=plan.suffix, expect=plan.expect)
    registers = dict(plan.registers)
    registers['d0'] = (registers.get('d0', 0) + 1) & 0xFFFFFFFF
    return AtomicPlan(plan.cycles, plan.instructions, plan.writes, registers, plan.last_pc, plan.direct_calls)


def _mutate_creature_walk(plan) -> AtomicPlan:
    """Negative control for the composed 9(+1)-slot walk (00A578): when a family activation reaches
    the device (a Seam, the same platform tail creature_family_plan's own mutant already draws on),
    D0 (particle_emit's own X argument) off by one, for the identical reason.  When no instance in
    this whole tick reaches the device (a plain AtomicPlan -- every slot either skips, spawns new
    instances, or runs the icon-spawn sub-machine with no live 'family' arm), the last write instead:
    a real, permanent RAM field (a creature's own position/lifecycle/reload timer, or one of the
    per-slot F2C6/F2C8/F26C tallies) a LATER tick's own walk reads back, never dead stack residue."""
    if isinstance(plan, Seam):
        registers = dict(plan.prefix.registers)
        registers['d0'] = (registers.get('d0', 0) + 1) & 0xFFFFFFFF
        prefix = AtomicPlan(plan.prefix.cycles, plan.prefix.instructions, plan.prefix.writes, registers,
                            plan.prefix.last_pc, plan.prefix.direct_calls)
        return Seam(prefix=prefix, resume_pc=plan.resume_pc, stack_basis=plan.stack_basis,
                   guards=plan.guards, suffix=plan.suffix, expect=plan.expect)
    return _mutate_result(plan)


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
    'spawn-scan': {SPAWN_SCAN_ENTRY: spawn_scan_plan},
    'grid-cell': {GRID_CELL_ENTRY: grid_cell_plan},
    'footprint': {FOOTPRINT_STAMP_ENTRY: footprint_stamp_plan},
    'solid-draw': {SOLID_DRAW_ENTRY: draw_solid_plan},
    'animation-step': {ANIMATION_STEP_ENTRY: animation_step_plan},
    'countdown-check': {COUNTDOWN_CHECK_ENTRY: countdown_check_plan},
    'collision-gate': {COLLISION_GATE_ENTRY: collision_gate_plan},
    'zone-check': {ZONE_CHECK_ENTRY: zone_check_plan},
    'particle-emit': {PARTICLE_EMIT_ENTRY: particle_emit_plan},
    'object-tile': {OBJECT_TILE_ENTRY: object_tile_plan},
    'object-kind-dispatch': {OBJECT_KIND_DISPATCH_ENTRY: object_kind_dispatch_plan},
    'pickup-award-group': {PICKUP_AWARD_GROUP_ENTRY: pickup_award_group_plan},
    'queue-append': {QUEUE_APPEND_ENTRY: queue_append_plan},
    # The 005958 table's own seven admitted handlers (docs/gods/blockers/2026-09-19-003480.md):
    # standalone candidates only, kept OUT of camera-sprites for native gate capacity (the SAME
    # reason state-18/creature-attack/creature-frame-offset are standalone) until 003480 itself is
    # composed, which will retire these individual gates the way 00A772 retired the creature leaves'.
    'kind-accumulator-0': {ACCUMULATOR_0_ENTRY: accumulator_0_plan},
    'kind-accumulator-3': {ACCUMULATOR_3_ENTRY: accumulator_3_plan},
    'kind-accumulator-19': {ACCUMULATOR_19_ENTRY: accumulator_19_plan},
    'kind-accumulator-21': {ACCUMULATOR_21_ENTRY: accumulator_21_plan},
    'kind-bump-tally-1': {BUMP_TALLY_1_ENTRY: bump_tally_1_plan},
    'kind-bump-tally-2': {BUMP_TALLY_2_ENTRY: bump_tally_2_plan},
    'kind-half-frame-counter': {HALF_FRAME_COUNTER_ENTRY: half_frame_counter_plan},
    'object-activity-gate': {OBJECT_ACTIVITY_GATE_ENTRY: object_activity_gate_plan},
    'kind-sound-cue-pair': {SOUND_CUE_PAIR_ENTRY: sound_cue_pair_plan},
    'kind-copy-table-14': {COPY_TABLE_14_ENTRY: copy_table_14_plan},
    'kind-copy-table-15': {COPY_TABLE_15_ENTRY: copy_table_15_plan},
    'kind-copy-table-16': {COPY_TABLE_16_ENTRY: copy_table_16_plan},
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
    'spawn-puff-box': {SPAWN_PUFF_BOX_ENTRY: spawn_puff_box_plan},
    'spawn-effect-slot': {SPAWN_EFFECT_SLOT_ENTRY: spawn_effect_slot_plan},
    'action-clear-group': {ACTION_CLEAR_GROUP_ENTRY: action_clear_group_plan},
    'player-tail': {PLAYER_TAIL_ENTRY: player_tail_plan},
    'player-state': {PLAYER_STATE_ENTRY: player_state_plan},
    'creature-frame-offset': {KIND_FRAME_OFFSET_ENTRY: kind_frame_offset_plan},
    'creature-grid-cell': {CREATURE_GRID_CELL_ENTRY: creature_grid_cell_plan},
    'creature-grid-cell-d0d1': {AF3C_ENTRY: creature_grid_cell_d0d1_plan},
    'aim-cue-update': {AIM_CUE_ENTRY: aim_cue_update_plan},
    'aim-pool-reset': {AIM_POOL_RESET_ENTRY: aim_pool_reset_plan},
    'aim-pool-add': {AIM_POOL_ADD_ENTRY: aim_pool_add_plan},
    'aim-window-address': {AIM_WINDOW_ADDRESS_ENTRY: aim_window_address_plan},
    'aim-probe-mark': {AIM_PROBE_MARK_ENTRY: aim_probe_mark_plan},
    'aim-probe-mark-store': {AIM_PROBE_MARK_STORE_ENTRY: aim_probe_mark_store_plan},
    'aim-ray-march-forward': {AIM_RAY_MARCH_FORWARD_ENTRY: aim_ray_march_forward_plan},
    'aim-ray-march-backward': {AIM_RAY_MARCH_BACKWARD_ENTRY: aim_ray_march_backward_plan},
    'aim-pool-scan': {AIM_POOL_SCAN_ENTRY: aim_pool_scan_plan},
    'aim-target-scan': {AIM_TARGET_SCAN_ENTRY: aim_target_scan_plan},
    'aim-target-scan-backward': {AIM_TARGET_SCAN_BACKWARD_ENTRY: aim_target_scan_backward_plan},
    'aim-target-resolve': {AIM_TARGET_RESOLVE_ENTRY: aim_target_resolve_plan},
    'aim-search-scan': {AIM_SEARCH_SCAN_ENTRY: aim_search_scan_plan},
    'aim-search-dispatch': {AIM_SEARCH_DISPATCH_ENTRY: aim_search_dispatch_plan},
    'aim-search-flag-dispatch': {AIM_SEARCH_FLAG_DISPATCH_ENTRY: aim_search_flag_dispatch_plan},
    'aim-kind-handler-76': {AIM_KIND_HANDLER_76_ENTRY: aim_kind_handler_76_plan},
    'aim-kind-handler-50': {AIM_KIND_HANDLER_50_ENTRY: aim_kind_handler_50_plan},
    'effect-slot-find': {EFFECT_SLOT_FIND_ENTRY: effect_slot_find_free_plan},
    'effect-slot-add': {EFFECT_SLOT_ADD_ENTRY: effect_slot_add_plan},
    'bcd-counter-add': {BCD_COUNTER_ADD_ENTRY: bcd_counter_add_plan},
    'creature-death-bcd': {CREATURE_DEATH_BCD_ENTRY: creature_death_bcd_plan},
    'creature-family': {CREATURE_FAMILY_ENTRY: creature_family_plan},
    'creature-walk': {CREATURE_WALK_ENTRY: creature_walk_plan},
    'spawn-table-find-free': {SPAWN_FIND_FREE_ENTRY: spawn_table_find_free_plan},
    'spawn-table-add': {SPAWN_TABLE_ADD_ENTRY: spawn_table_add_plan},
    'ground-edge-test': {GROUND_EDGE_TEST_ENTRY: ground_edge_test_plan},
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
    'state-8': {STATE8_ENTRY: state8_plan},
    'state-9': {STATE9_ENTRY: state9_plan},
    'state-11': {STATE11_ENTRY: state11_plan},
    'state-12': {STATE12_ENTRY: state12_plan},
    'state-13': {STATE13_ENTRY: state13_plan},
    'state-16': {STATE16_ENTRY: state16_plan},
    'state-17': {STATE17_ENTRY: state17_plan},
    'state-21': {STATE21_ENTRY: state21_plan},
    'state-28': {STATE28_ENTRY: state28_plan},
    'state-22': {STATE22_ENTRY: state22_plan},
    'state-27': {STATE27_ENTRY: state27_plan},
    'state-23': {STATE23_ENTRY: state23_plan},
    'state-10': {STATE10_ENTRY: state10_plan},
    'state-19': {STATE19_ENTRY: state19_plan},
    'state-18': {STATE18_ENTRY: state18_plan},
    'creature-attack': {ATTACK_UPDATE_ENTRY: attack_update_plan},
    'creature-pickup-check': {CREATURE_PICKUP_CHECK_ENTRY: creature_pickup_check_plan},
    'event-consume': {EVENT_CONSUME_ENTRY: event_consume_plan},
    'creature-ground-contact': {GROUND_CONTACT_UPDATE_ENTRY: ground_contact_update_plan},
    'creature-ground-contact-mirror': {GROUND_CONTACT_UPDATE_MIRROR_ENTRY: ground_contact_update_mirror_plan},
    'creature-fall-kind': {FALL_KIND_UPDATE_ENTRY: fall_kind_update_plan},
    'creature-fall-kind-mirror': {FALL_KIND_UPDATE_MIRROR_ENTRY: fall_kind_update_mirror_plan},
    'state-2': {STATE2_ENTRY: state2_plan},
    'state-3': {STATE3_ENTRY: state3_plan},
    'state-4': {STATE4_ENTRY: state4_plan},
    # 'state-26' below targets 0069AC, real STATE_TABLE index 20, not 26 -- a misnomer left as a
    # fact for a future session (docs/gods/STATUS.md's own 18 September entries), renamed here to
    # 'state-20' (18 Sep, real-index-26 recovery session): the gate PC is unchanged, so this is
    # purely a candidate-name fix, not a re-verification.
    'state-20': {STATE26_ENTRY: state26_plan},
    'state-26': {STATE_26_ENTRY: state_26_plan},
    'state-14': {STATE14_ENTRY: state14_plan},
    'camera-sprites': {CAMERA_FOLLOW_ENTRY: camera_follow_plan, SPRITE_EMIT_ENTRY: sprite_emit_plan,
                       STATIC_EMIT_ENTRY: static_emit_plan, TABLE_RESET_ENTRY: table_reset_plan,
                       SPAWN_QUEUE_ENTRY: spawn_queue_plan,
                       # SPAWN_SCAN_ENTRY (004926): the box-scan puff spawner, 19 September -- a new
                       # leaf, not a composition (its two real callers, 0048EA and 0139D2, are both
                       # still unrecovered) -- 54 -> 55 gates.
                       SPAWN_SCAN_ENTRY: spawn_scan_plan,
                       # SPAWN_EFFECT_SLOT_ENTRY (004A0A): the coordinator's own priority (1), the
                       # firing arm's own action-table handler that reaches EFFECT_SLOT_FIND_ENTRY
                       # (004AAA, already recovered as 00A772's own tail) -- 56 -> 57 gates.
                       SPAWN_EFFECT_SLOT_ENTRY: spawn_effect_slot_plan,
                       GRID_CELL_ENTRY: grid_cell_plan,
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
                       # SPAWN_PUFF_BOX_ENTRY (0048EA): the 0030CC assignment's own second bite, 19
                       # September -- SPAWN_SCAN_ENTRY (004926) stays armed too, it has a second, real,
                       # still-unrecovered caller (0139D2) -- 55 -> 56 gates.
                       SPAWN_PUFF_BOX_ENTRY: spawn_puff_box_plan,
                       PLAYER_TAIL_ENTRY: player_tail_plan, CONTACT_SEARCH_ENTRY: contact_search_plan,
                       CONTACT_CONSUME_PRIMARY_ENTRY: contact_consume_primary_plan,
                       CONTACT_CONSUME_SECONDARY_ENTRY: contact_consume_secondary_plan,
                       TRAIL_CHECK_ENTRY: trail_check_plan,
                       # The 25 individual player-state gates (states 0-6, 8-14, 16-28's own dispatch
                       # table entries, plus the movement-cluster pair 24/25) are RETIRED from this
                       # combined candidate's own gate set, 18 September: player_state_plan (005700)
                       # now owns the jump into every one of them, so their own PCs are never reached
                       # as a live gate during real dispatch -- the dispatcher's own hits replace
                       # theirs (docs/gods/STATUS.md's own `005700` semantic-operation card).  Their
                       # own PLANNERS entries ('state-0' etc., above) and gate PCs stay, unchanged,
                       # for their own isolated tests (factcheck check, segment_verify) -- this
                       # candidate simply no longer arms them itself.  STATE18_ENTRY was never armed
                       # here in the first place (native/machine.cpp's own 64-gate cap, pinned;
                       # docs/gods/ledger.md's 18 September entry) and stays its own standalone
                       # candidate ('state-18'); with the 25 gates retired there is ample headroom to
                       # arm it too, but that is a separate decision from this composition.
                       PLAYER_STATE_ENTRY: player_state_plan,
                       # The creature update's recovered pieces are RETIRED from this combined candidate's
                       # own gate set, 19 September: every witnessed call into attack_update/event_consume/
                       # creature_pickup_check/the four kind handlers/00AF3C comes from creature_family_plan's
                       # own body (00A772, composed below) -- once IT is armed here, the native machine never
                       # independently reaches any of their own PCs as a live gate, the same "the family
                       # composition frees them, as 005700's did" retirement already noted for player_state_plan
                       # above.  KIND_FRAME_OFFSET_ENTRY (00AA50) stays: it is ALSO reachable directly from
                       # 00A772's own "moving" header arm (bsr $aa50), which creature_family_plan declines
                       # (0% witnessed) rather than composes, so a real occurrence of that arm still needs it
                       # armed on its own.  Their own PLANNERS entries and standalone tests are unchanged.
                       KIND_FRAME_OFFSET_ENTRY: kind_frame_offset_plan,
                       # CREATURE_FAMILY_ENTRY (00A772) is RETIRED here too, 19 September, the same day:
                       # its own SOLE caller is 00A578's own per-frame-update body (creature_walk_plan,
                       # below) -- once IT is armed here, the native machine never independently reaches
                       # 00A772 as a gate hit.  Its own PLANNERS entry and standalone tests are unchanged.
                       CREATURE_WALK_ENTRY: creature_walk_plan,
                       # AIM_CUE_ENTRY (00B082) and AIM_POOL_RESET_ENTRY (00B02A) are RETIRED here too,
                       # 19 September: both exit exclusively into 00AF52's own body (00AF90/00AF98,
                       # confirmed against their own census fixtures), and AIM_SEARCH_DISPATCH_ENTRY's
                       # own atomic plan (aim_search_dispatch_plan, below) composes both -- their own
                       # PLANNERS entries and standalone tests are unchanged, the same retirement shape
                       # as 00B588's and 00B002's own above.  AIM_POOL_ADD_ENTRY stays: it has a SECOND,
                       # independent caller (00B62A's own 'store' arm, already composed elsewhere).
                       AIM_POOL_ADD_ENTRY: aim_pool_add_plan,
                       AIM_WINDOW_ADDRESS_ENTRY: aim_window_address_plan,
                       AIM_PROBE_MARK_ENTRY: aim_probe_mark_plan,
                       # AIM_PROBE_MARK_STORE_ENTRY (00B62A) and the two ray marches (00B354/00B440) are
                       # RETIRED from this combined candidate's own gate set, 19 September: every
                       # witnessed call into them comes from 00B588's own body (00B62A directly, the
                       # ray marches via its own bsr), so once 00B588 itself is armed here its atomic
                       # plan already covers that whole span -- the native machine never independently
                       # reaches these three PCs as gate hits while 00B588 is armed.  The SAME "one
                       # region composes, the pieces stay for their own isolated tests" shape the 25
                       # player-state gates and 005700 already established above; their own PLANNERS
                       # entries and gate PCs are unchanged.  Frees three gates for AIM_POOL_SCAN_ENTRY's
                       # own one (64 -> 62; docs/gods/STATUS.md's 19 September entry).
                       #
                       # AIM_POOL_SCAN_ENTRY (00B588) and the aim-target-scan family (00B724/00B7DA/
                       # 00B6AE) are RETIRED here too, 19 September, the same day: every witnessed
                       # occurrence of all four returns to (or reaches) a fixed address inside 00B002's
                       # own body -- confirmed against every one of their own census fixtures' exits,
                       # one caller each -- and 00B002 itself never executes its own rts, tail-jumping
                       # straight into 00B588 once its own three calls return.  AIM_SEARCH_SCAN_ENTRY's
                       # own atomic plan (aim_search_scan_plan) composes all four, so once IT is armed
                       # here the native machine never independently reaches any of their own four PCs
                       # as a gate hit.  62 -> 59 gates; their own PLANNERS entries and standalone tests
                       # are unchanged, the same retirement shape as above.
                       AIM_SEARCH_SCAN_ENTRY: aim_search_scan_plan,
                       AIM_SEARCH_DISPATCH_ENTRY: aim_search_dispatch_plan,
                       AIM_SEARCH_FLAG_DISPATCH_ENTRY: aim_search_flag_dispatch_plan,
                       # AIM_KIND_HANDLER_76_ENTRY (00AA76): the most-witnessed kind handler, 19
                       # September -- 59 -> 60 gates.
                       AIM_KIND_HANDLER_76_ENTRY: aim_kind_handler_76_plan,
                       # AIM_KIND_HANDLER_50_ENTRY (00AB50): the other most-witnessed kind handler,
                       # 19 September -- 60 -> 61 gates.
                       AIM_KIND_HANDLER_50_ENTRY: aim_kind_handler_50_plan,
                       # EFFECT_SLOT_FIND_ENTRY (00004AAA): 00A772's own further tail (00010E28's own
                       # callee), 19 September -- 61 -> 62 gates.
                       EFFECT_SLOT_FIND_ENTRY: effect_slot_find_free_plan,
                       # EFFECT_SLOT_ADD_ENTRY (00010E28): composes 00004AAA over a full movem.l
                       # register frame, 19 September -- 62 -> 63 gates.
                       EFFECT_SLOT_ADD_ENTRY: effect_slot_add_plan,
                       # BCD_COUNTER_ADD_ENTRY (00003F0C): a shared utility with many callers beyond
                       # 00A772's own tail, 19 September -- 63 -> 64 gates (the adapter's own cap).
                       BCD_COUNTER_ADD_ENTRY: bcd_counter_add_plan,
                       # SPAWN_TABLE_ADD_ENTRY (00B920) is RETIRED here too, 19 September: its own SOLE
                       # caller is 00A578's own body (creature_walk_plan composes it directly, both from
                       # the spawn-init loop and the icon-spawn 'reload-wait' arm) -- once creature_walk
                       # is armed here the native machine never independently reaches 00B920 as a gate
                       # hit.  SPAWN_FIND_FREE_ENTRY (00B8C2) stays armed: it is spawn_table_add's own
                       # internal callee, composed transitively, but its own PLANNERS entry/tests are
                       # unchanged and this candidate does not itself claim it reaches no other caller.
                       SPAWN_FIND_FREE_ENTRY: spawn_table_find_free_plan,
                       # OBJECT_TILE_ENTRY (001810): the Decision's own bottom-up order's second bite
                       # (docs/gods/blockers/2026-09-19-003480.md), a second sprite-emitter shape --
                       # 57 -> 58 gates.
                       OBJECT_TILE_ENTRY: object_tile_plan,
                       # OBJECT_KIND_DISPATCH_ENTRY (0036E2): the Decision's own third bite, a seam
                       # opaque over its own table-matched handler (kind 0x51 -> 0037A0 the only
                       # witnessed pair) -- 58 -> 59 gates.
                       OBJECT_KIND_DISPATCH_ENTRY: object_kind_dispatch_plan,
                       # PICKUP_AWARD_GROUP_ENTRY (012C80) and QUEUE_APPEND_ENTRY (002F2E) are RETIRED
                       # from this combined candidate's own gate set, 20 September: their only real
                       # callers (docs/gods/blockers/2026-09-19-003480.md's own Progress notes) are
                       # OBJECT_ACTIVITY_GATE_ENTRY's own arms 2/3 (below), composed here -- once IT is
                       # armed, the native machine never independently reaches either PC as a gate hit,
                       # the same "the composition frees them" retirement 00A772's and 005700's own
                       # already used.  Their own PLANNERS entries and standalone tests are unchanged.
                       # The 005958 table's own ten composed handlers (accumulator 0/3/19/21, copy-
                       # table 14/15/16, bump-tally 1/2, half-frame-counter) were NEVER armed here in
                       # the first place (kept standalone-only for native gate capacity, the
                       # state-18/creature-attack precedent) and stay that way: OBJECT_ACTIVITY_GATE_
                       # ENTRY's own arm 2 already reaches every one of them internally.  SOUND_CUE_
                       # PAIR_ENTRY (index 10) is the one exception -- it has a second, real,
                       # independent caller (exit 008616) this composition does not cover, so it stays
                       # its own standalone-only candidate too, unchanged.
                       #
                       # OBJECT_ACTIVITY_GATE_ENTRY (003480): the Decision's own next bite, composing
                       # the bounds-check head, the achievements.RECORD_TABLE dispatch, and both the
                       # pickup-award (012C80) and sound-request (0x5958 table + 002F2E) arms -- the
                       # 0x354C record-status-1 sub-dispatch (a genuine second real sub-mechanism) and
                       # 005958 indices 4/6/17/18 (each its own real, unrecovered complexity) decline
                       # by name -- 61 -> 60 gates net (012C80/002F2E retired, 003480 admitted).
                       OBJECT_ACTIVITY_GATE_ENTRY: object_activity_gate_plan},
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
             # writes are ordered so the LAST pair is the puff's own queued spawn-queue position (not
             # the scratch F398 counter or the sound cue): a flip there is a real, externally visible
             # effect (the next tick's own scan_spawn_queue draws the puff at the corrupted position).
             'spawn-scan-mutant-result': ('spawn-scan', _mutate_result),
             # the composed spawn_scan_plan's own writes lead (a real puff position, ordered last by
             # spawn_scan_plan itself for the same reason); the outer d7-push/return-address bytes
             # this routine's own writes prepend are dead scratch by the time it returns.
             'spawn-puff-box-mutant-result': ('spawn-puff-box', _mutate_result),
             'spawn-effect-slot-mutant-result': ('spawn-effect-slot', _mutate_result),
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
             'object-tile-mutant-register': ('object-tile', _mutate_register),
             'object-kind-dispatch-mutant-register': ('object-kind-dispatch', _mutate_register),
             # the last write is TIME_MARK (both arms: award_group_dispatch's own tally update runs
             # last), re-read by pickups.collect() as the time-bonus baseline -- a real, externally
             # visible effect.
             'pickup-award-group-mutant-result': ('pickup-award-group', _mutate_result),
             'queue-append-mutant-result': ('queue-append', _mutate_result),
             'kind-accumulator-0-mutant-result': ('kind-accumulator-0', _mutate_result),
             'kind-accumulator-3-mutant-result': ('kind-accumulator-3', _mutate_result),
             'kind-accumulator-19-mutant-result': ('kind-accumulator-19', _mutate_result),
             'kind-accumulator-21-mutant-result': ('kind-accumulator-21', _mutate_result),
             'kind-bump-tally-1-mutant-result': ('kind-bump-tally-1', _mutate_result),
             'kind-bump-tally-2-mutant-result': ('kind-bump-tally-2', _mutate_result),
             'kind-half-frame-counter-mutant-result': ('kind-half-frame-counter', _mutate_result),
             'kind-sound-cue-pair-mutant-result': ('kind-sound-cue-pair', _mutate_result),
             'kind-copy-table-14-mutant-result': ('kind-copy-table-14', _mutate_result),
             'kind-copy-table-15-mutant-result': ('kind-copy-table-15', _mutate_result),
             'kind-copy-table-16-mutant-result': ('kind-copy-table-16', _mutate_result),
             # a register, not the last write: the box-miss and bypass arms (the great majority of
             # real occurrences -- most per-frame calls reject a far-off object) store nothing durable
             # at all, so the generic "flip the last write" mutation would only corrupt the dead
             # movem/rtr stack scratch every arm ends with (the same class of blind spot zone-check's
             # own mutant avoids); D0 is always either explicitly restored (sign-extended) or left
             # provably unchanged, so corrupting it diverges in every arm, including the no-op ones.
             'object-activity-gate-mutant-result': ('object-activity-gate', _mutate_register),
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
             # future activation's own dispatch the same unbounded way.  Renamed from 'state-26' (18
             # Sep, real-index-26 recovery session): this candidate's own gate (0069AC) is real
             # STATE_TABLE index 20, not 26 -- see PLANNERS' own comment above.
             'state-20-mutant-result': ('state-20', _mutate_outcome),
             # the real STATE_TABLE index 26 (005724): every witnessed arm writes STATE_INDEX,
             # PROXIMITY_ACTIVE (F24A) or the box-scan's own found fields, all read back either by
             # the shared tail's own re-index or by a LATER activation of this same gate (F24A's own
             # debounce, the box-scan's own EF54/56/58) -- dropping every write is the one shape
             # safe on every arm at once, the same reasoning every other player-state mutant uses.
             'state-26-mutant-result': ('state-26', _mutate_outcome),
             # the same reasoning as state 9's own mutant (its sibling, sharing the same shared-tail
             # hazard): STATE_INDEX/F19C/D7 all feed the shared tail's own re-index or a future
             # activation's own dispatch the same unbounded way.
             'state-8-mutant-result': ('state-8', _mutate_outcome),
             # the same reasoning as states 8/9/26's own: STATE_INDEX/F19x/D7 all feed the shared
             # tail's own re-index or a future activation's own dispatch the same unbounded way.
             'state-13-mutant-result': ('state-13', _mutate_outcome),
             # the same reasoning as states 8/9/13/26's own: STATE_INDEX/F19x/D7 all feed the shared
             # tail's own re-index or a future activation's own dispatch the same unbounded way.
             'state-12-mutant-result': ('state-12', _mutate_outcome),
             # the same reasoning as states 8/9/12/13/26's own: STATE_INDEX/F19x/D7 all feed the
             # shared tail's own re-index or a future activation's own dispatch the same unbounded way.
             'state-16-mutant-result': ('state-16', _mutate_outcome),
             # the same reasoning as states 8/9/12/13/16/26's own: STATE_INDEX/F19x/D7 all feed the
             # shared tail's own re-index or a future activation's own dispatch the same unbounded way.
             'state-11-mutant-result': ('state-11', _mutate_outcome),
             # the same reasoning as states 8/9/11/12/13/16/26's own: STATE_INDEX/D7 feed the
             # shared tail's own re-index or a future activation's own dispatch the same unbounded way.
             'state-2-mutant-result': ('state-2', _mutate_outcome),
             # the same reasoning as states 2/8/9/11/12/13/16/26's own: STATE_INDEX/D7 feed the
             # shared tail's own re-index or a future activation's own dispatch the same unbounded way.
             'state-3-mutant-result': ('state-3', _mutate_outcome),
             # the same reasoning as states 2/3/8/9/11/12/13/16/26's own: STATE_INDEX/D7 feed the
             # shared tail's own re-index or a future activation's own dispatch the same unbounded way.
             'state-4-mutant-result': ('state-4', _mutate_outcome),
             # the same reasoning as states 2/3/4/8/9/11/12/13/16/26's own: STATE_INDEX/D7 feed
             # the shared tail's own re-index or a future activation's own dispatch the same
             # unbounded way.
             'state-17-mutant-result': ('state-17', _mutate_outcome),
             # the same reasoning as states 2/3/4/8/9/11/12/13/16/17/26's own: STATE_INDEX/D7
             # feed the shared tail's own re-index or a future activation's own dispatch the
             # same unbounded way.
             'state-21-mutant-result': ('state-21', _mutate_outcome),
             # the same reasoning as states 2/3/4/8/9/11/12/13/16/17/21/26's own: STATE_INDEX/D7
             # feed the shared tail's own re-index or a future activation's own dispatch the
             # same unbounded way.
             'state-28-mutant-result': ('state-28', _mutate_outcome),
             # the same reasoning as states 2/3/4/8/9/11/12/13/16/17/21/26/28's own: STATE_INDEX/
             # D7 feed the shared tail's own re-index or a future activation's own dispatch the
             # same unbounded way.
             'state-22-mutant-result': ('state-22', _mutate_outcome),
             # the same reasoning as states 2/3/4/8/9/11/12/13/16/17/21/22/26/28's own:
             # STATE_INDEX/D7 feed the shared tail's own re-index or a future activation's own
             # dispatch the same unbounded way.
             'state-27-mutant-result': ('state-27', _mutate_outcome),
             # the same reasoning as states 2/3/4/8/9/11/12/13/16/17/21/22/26/27/28's own:
             # STATE_INDEX/D7 feed the shared tail's own re-index or a future activation's own
             # dispatch the same unbounded way.
             'state-23-mutant-result': ('state-23', _mutate_outcome),
             # the same reasoning as states 2/3/4/8/9/11/12/13/16/17/21/22/23/26/27/28's own:
             # STATE_INDEX/D7 feed the shared tail's own re-index or a future activation's own
             # dispatch the same unbounded way.
             'state-10-mutant-result': ('state-10', _mutate_outcome),
             # a register, not the generic STATE_INDEX/D7-feeds-an-unbounded-table _mutate_outcome
             # every other state uses: states 19/18 are seam-heavy (the achievement highlight cycle,
             # the box-scan consume) and _mutate_outcome's own "drop every write" corrupts the seam's
             # own structural return-address writes, faulting the M68000 rather than diverging cleanly
             # (confirmed: PC lands on a data address and executes garbage).  D0 carries the icon slot
             # into every ceded 001648 call (achievement-slot-dispatch's own reasoning) and is real on
             # every admitted arm, seam or plain, so a register mutant is always observable and never
             # touches the stack.
             'state-19-mutant-result': ('state-19', _mutate_register),
             'state-18-mutant-result': ('state-18', _mutate_register),
             'state-14-mutant-result': ('state-14', _mutate_state14_counter),
             # _mutate_result (not _mutate_register): every register 009D6C itself sets is dead on
             # return -- 00A772's own very next instruction (move.w $a(a5),d0) clobbers D0 unconditionally,
             # and the kind-handler jsr between there and 00A794 clobbers D1-D5 before anything reads
             # them, so a register mutant is unobservable however many times it hits (confirmed: PASS
             # over 1200 real frames, 102 hits, 18 Sep).  Every arm's last write is ordered to be a real
             # gameplay effect (the countdown reload, the projectile pool fill, LAUNCHED_FLAG, or the
             # random cursor advance) rather than the tail-jump's own dead stack residue, so
             # _mutate_result's one-byte flip is genuinely observable.
             'creature-attack-mutant-result': ('creature-attack', _mutate_result),
             'player-state-mutant-result': ('player-state', _mutate_player_state_counter),
             'creature-frame-offset-mutant-result': ('creature-frame-offset', _mutate_kind_frame_offset),
             # every register this leaf sets is restored from the stack (movem.l d0-d2 at its own
             # exit) to the ENTRY value, dead by construction; the real, observable effects are the
             # writes -- LIFECYCLE's own write-back always happens, FRAME_STEP/LIFECYCLE_RESET only on
             # a negative pickup-check result -- so _mutate_result's one-byte flip is the real control,
             # the same shape creature-attack's own mutant already uses.
             'creature-pickup-check-mutant-result': ('creature-pickup-check', _mutate_result),
             # every register this leaf sets (d0-d4,d6,d7,a0) is dead by construction (00A772's own
             # very next instructions -- 00A794's own kind-table jsr, the 00A922 caller's own d2
             # save/restore -- clobber all of them before anything reads them back); the real,
             # observable effect is the found arm's own five stores (the instance's own event fields,
             # the object table's own consumed pair), so _mutate_result's one-byte flip is the control.
             'event-consume-mutant-result': ('event-consume', _mutate_result),
             'creature-grid-cell-mutant-result': ('creature-grid-cell', _mutate_creature_grid_cell),
             'ground-edge-test-mutant-result': ('ground-edge-test', _mutate_ground_edge_outcome),
             # every register this leaf sets is dead residue by construction -- kind_frame_offset (the
             # gate it hands off to) reloads d0/d2/a0 itself from a4/a5 before ever reading them back,
             # and the caller's own kind-table jsr right after that clobbers whatever is left.  The
             # real, observable effects are the writes: GROUND_HOLD_TIMER on every arm (read back the
             # very next activation), POSITION_X/POSITION_Y/FALL_PHASE, and KIND on 'near-trigger'/
             # 'settle-reset' (00A772's own dispatch re-reads it every tick -- the SAME field
             # kind_frame_offset's own mutant already proved observable), so _mutate_result's one-byte
             # flip is the control.
             'creature-ground-contact-mutant-result': ('creature-ground-contact', _mutate_result),
             'creature-ground-contact-mirror-mutant-result': ('creature-ground-contact-mirror', _mutate_result),
             'creature-fall-kind-mutant-result': ('creature-fall-kind', _mutate_result),
             'creature-fall-kind-mirror-mutant-result': ('creature-fall-kind-mirror', _mutate_result),
             'creature-grid-cell-d0d1-mutant-result': ('creature-grid-cell-d0d1', _mutate_creature_grid_cell_d0d1),
             'aim-cue-update-mutant-result': ('aim-cue-update', _mutate_result),
             'aim-pool-reset-mutant-result': ('aim-pool-reset', _mutate_result),
             'aim-pool-add-mutant-result': ('aim-pool-add', _mutate_result),
             'aim-window-address-mutant-result': ('aim-window-address', _mutate_aim_window_address),
             'aim-probe-mark-mutant-result': ('aim-probe-mark', _mutate_aim_probe),
             'aim-probe-mark-store-mutant-result': ('aim-probe-mark-store', _mutate_aim_probe),
             'aim-ray-march-forward-mutant-result': ('aim-ray-march-forward', _mutate_aim_ray_march),
             'aim-ray-march-backward-mutant-result': ('aim-ray-march-backward', _mutate_aim_ray_march),
             'aim-pool-scan-mutant-result': ('aim-pool-scan', _mutate_aim_ray_march),
             'aim-search-scan-mutant-result': ('aim-search-scan', _mutate_aim_ray_march),
             'aim-search-dispatch-mutant-result': ('aim-search-dispatch', _mutate_aim_ray_march),
             'aim-search-flag-dispatch-mutant-result': ('aim-search-flag-dispatch', _mutate_result),
             'aim-target-scan-mutant-result': ('aim-target-scan', _mutate_result),
             'aim-target-scan-backward-mutant-result': ('aim-target-scan-backward', _mutate_result),
             'aim-kind-handler-76-mutant-result': ('aim-kind-handler-76', _mutate_result),
             'aim-kind-handler-50-mutant-result': ('aim-kind-handler-50', _mutate_result),
             'effect-slot-find-mutant-result': ('effect-slot-find', _mutate_effect_slot_find),
             'effect-slot-add-mutant-result': ('effect-slot-add', _mutate_result),
             'bcd-counter-add-mutant-result': ('bcd-counter-add', _mutate_result),
             'creature-death-bcd-mutant-result': ('creature-death-bcd', _mutate_result),
             'creature-family-mutant-result': ('creature-family', _mutate_creature_family),
             'creature-walk-mutant-result': ('creature-walk', _mutate_creature_walk),
             'aim-target-resolve-mutant-result': ('aim-target-resolve', _mutate_aim_target_resolve),
             'spawn-table-find-free-mutant-result': ('spawn-table-find-free', _mutate_spawn_find_free),
             'spawn-table-add-mutant-result': ('spawn-table-add', _mutate_result)}


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
