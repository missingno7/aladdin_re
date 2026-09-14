"""Pure live-RAM effects for the bounded 1AE4F8 contact reaction block."""


def contact_scan_collision(read_ram, read_source, *, record, player, player_shape):
    """Classify one 1ABBE0 object against the player contact rectangle.

    This is deliberately just the game predicate.  The boundary owns operand
    provenance, the exact 68000 register/CCR residue, and branch costs.
    """
    kind = read_ram(record, 1)
    if kind == 0:
        return {'branch': 'inactive'}
    if kind >= 0x7f:
        return {'branch': 'non-contact-kind'}
    shape = read_ram(record + 20, 4)
    if shape == 0:
        return {'branch': 'no-shape'}
    x, y, mirrored = read_ram(record + 2, 2), read_ram(record + 4, 2), read_ram(record + 9, 1)
    left_byte = read_source(shape + (4 if mirrored else 2), 1)
    left = ((-left_byte) & 0xff) if mirrored else left_byte
    object_horizontal = (x + left) & 0xffff
    player_horizontal = read_ram(0xfff08e, 2)
    if player_horizontal < object_horizontal:
        return {'branch': 'left', 'player_horizontal_edge': player_horizontal, 'object_horizontal_edge': object_horizontal,
                'shape': shape, 'mirrored': mirrored}
    player_vertical = (read_ram(player + 4, 2) + read_source(player_shape + 5, 1)) & 0xffff
    object_vertical = (y + read_source(shape + 3, 1)) & 0xffff
    if player_vertical < object_vertical:
        return {'branch': 'above', 'player_horizontal_edge': player_horizontal, 'player_vertical_edge': player_vertical,
                'object_horizontal_edge': object_horizontal, 'object_vertical_edge': object_vertical, 'shape': shape, 'mirrored': mirrored}
    right_byte = read_source(shape + (2 if mirrored else 4), 1)
    right = ((-right_byte) & 0xff) if mirrored else right_byte
    object_horizontal = (x + right) & 0xffff
    player_horizontal = read_ram(0xfff08c, 2)
    if player_horizontal >= object_horizontal:
        return {'branch': 'right', 'player_horizontal_edge': player_horizontal, 'player_vertical_edge': player_vertical,
                'object_horizontal_edge': object_horizontal, 'object_vertical_edge': object_vertical, 'shape': shape, 'mirrored': mirrored}
    player_vertical = (read_ram(player + 4, 2) + read_source(player_shape + 3, 1)) & 0xffff
    object_vertical = (y + read_source(shape + 5, 1)) & 0xffff
    return {'branch': 'below' if player_vertical >= object_vertical else 'contact', 'player_horizontal_edge': player_horizontal,
            'player_vertical_edge': player_vertical, 'object_horizontal_edge': object_horizontal,
            'object_vertical_edge': object_vertical, 'shape': shape, 'mirrored': mirrored}


_EARLY = (0xFFF0E7, 0xFFF0E6, 0xFFF0E9, 0xFFF0F2)
_RESET_GATES = (0xFFF0BE, 0xFFF0D0, 0xFFF0D7, 0xFFF0CD, 0xFFF0D4)
_RESET_NAMES = ('be', 'd0', 'd7', 'cd', 'd4')


def contact_tick_reset(previous_contact, countdown_ee, countdown_f2):
    """Durable timer/latch writes at the beginning of one contact tick."""
    writes = [(0xFFF0F0, 0), (0xFFF0EF, 0)]
    if countdown_ee:
        writes.append((0xFFF0EE, (countdown_ee - 1) & 0xff))
    if countdown_f2:
        writes.append((0xFFF0F2, (countdown_f2 - 1) & 0xff))
    writes.extend(((0xFFF0D4, previous_contact), (0xFFF0D3, 0),
                   (0xFFF0F6, 0), (0xFFF0CD, 0)))
    return writes


def contact_tick_bounds(player_x, left_extent, right_extent, mirrored):
    """Return the wrapped horizontal bounds published before the object scan."""
    if mirrored:
        left_extent, right_extent = (-right_extent) & 0xff, (-left_extent) & 0xff
    return ((player_x + left_extent) & 0xffff, (player_x + right_extent) & 0xffff)


def contact_route(read):
    """Name the ordered original branch through 1AE4F8 without state."""
    for address in _EARLY:
        if read(address, 1):
            return 'early', address
    if read(0xFFF0BE, 1):
        return ('reaction' if read(0xFFF173, 1) else 'reset'), 'be'
    if not read(0xFFF0C1, 1):
        return ('reaction' if read(0xFFF173, 1) else 'reset'), 'c1zero'
    for name, address in zip(_RESET_NAMES[1:], _RESET_GATES[1:]):
        if read(address, 1):
            return ('reaction' if read(0xFFF173, 1) else 'reset'), name
    if read(0xFFF173, 1):
        return 'reaction', 'direct'
    if read(0xFFF0CC, 1) or read(0xFFEFFF, 1) or read(0xFFF11F, 1):
        return 'reset', 'cc' if read(0xFFF0CC, 1) else 'efff' if read(0xFFEFFF, 1) else 'f11f'
    return 'pointer_reset', 'pointer'


def contact_path(read):
    """Classify the concrete 1AE4F8 state gate without retaining state."""
    path, route = contact_route(read)
    return (path, route if path == 'early' else None)


def contact_sibling_route(read, record):
    """Classify 1AEC00 through its bounded counter-retirement arm."""
    if not read(0xFFF0D8, 1):
        return 'contact', None
    distance = read(0xFF7E02, 2)
    limit = read(record + 2, 2)
    if (read(0xFF7E49, 1) and distance < limit) or (not read(0xFF7E49, 1) and distance >= limit):
        return 'early', None
    if read(record + 1, 1):
        return 'decrement', None
    kind = read(record, 1)
    if kind == 0x13:
        return 'type13', kind
    if kind == 0x18:
        return 'retire18', kind
    if kind == 0x10:
        return 'retire10', kind
    if kind == 0x11:
        return 'retire11', kind
    return 'retire', kind


def contact_script_selector(read):
    """Classify 1AD150's flag-priority script-pointer selection.

    The selector itself has no external device calls.  It returns the selected
    immutable pointer when that pointer is fixed by the branch, or the table
    index for the one ROM-table arm.  The boundary owns the cartridge read and
    exact machine residue.
    """
    if read(0xFFF0D7, 1):
        return 'd7', 0x121964, None, False
    if read(0xFFF173, 1):
        if not read(0xFFF0C1, 1):
            return 'f173-c1zero', 0x121C28, None, False
        value = read(0xFFF0B0, 2)
        if value == 1:
            return 'f173-b0-1', 0x121FD4, None, False
        if value == 2:
            return 'f173-b0-2', 0x121FD4, None, False
        return 'f173-default', 0x121D5A, None, True
    if read(0xFFF115, 1):
        return 'f115', 0x125E72, None, False
    if read(0xFFF0CD, 1):
        d3 = read(0xFFF0D3, 1)
        if 0x50 <= d3 < 0x52:
            return 'cd-50-51', 0x121964, None, False
        if d3 == 0x60:
            return 'cd-60', 0x122336, None, False
    # 1AD1CE is reached after the optional CD arm, but is not part of it.
    if read(0xFFF0D3, 1) == 0x5E:
        return 'cd-5e', 0x122336, None, False
    if read(0xFFF0DB, 1):
        return 'db', 0x12181A, None, False
    if read(0xFFF0D0, 1):
        return 'd0-table', None, (read(0xFF7E04, 2) >> 2) & 0xF, False
    if read(0xFFF0D2, 1):
        return 'd2', 0x121C62, None, False
    if not read(0xFFF0C1, 1):
        return 'normal', 0x121AD8, None, False
    if read(0xFFF0DE, 1):
        return 'de', 0x12231E, None, False
    if read(0xFFF0DF, 1):
        return 'df', 0x122298, None, False
    if read(0xFFF0ED, 1):
        return 'ed', 0x121FA6, None, False
    value = read(0xFFF0B0, 2)
    if value in (1, 2):
        return f'b0-{value}', 0x122006, None, False
    return 'c1-default', 0x121D9A, None, False


def contact_decay(read):
    """One exact 1B03F2 pass; repeat callers may invoke it up to three times."""
    if read(0xFFF0E9, 1) or read(0xFFF0E6, 1) or read(0xFF7E20, 1):
        return []
    if read(0xFFEFFA, 1):
        if read(0xFFF0F2, 1):
            return []
        return [(0xFFEFFA, (read(0xFFEFFA, 1) - 1) & 0xff), (0xFFF0F2, 0x28)]
    return [(0xFFF0E6, 10)]


def contact_reset(read, *, pointer_reset=False, decay=True):
    """Return the reset-side RAM writes before optional synchronous sound."""
    writes = []
    if pointer_reset:
        writes.extend(((0xFF7E60, 0x00), (0xFF7E61, 0x12),
                       (0xFF7E62, 0x26), (0xFF7E63, 0xCE), (0xFF7E77, 0)))
    writes.extend(((0xFFF0B0, 0), (0xFFF0B1, 0), (0xFFF0CC, 0)))
    if decay:
        writes.extend(contact_repeated_decay(read, writes))
    return writes


def contact_repeated_decay(read, prior=()):
    """The one, two, or three 1B03F2 calls after a contact reset."""
    writes = list(prior)
    start = len(writes)
    for _ in range(1 + min(read(0xFF7E21, 1), 2)):
        writes.extend(contact_decay(lambda address, size: _overlay(read, writes, address, size)))
    return writes[start:]


def contact_reaction(read):
    """The FFF173 arm of 1AE5EA, including its FFF0D8-dependent final flag."""
    writes = [(0xFF7E60, 0x00), (0xFF7E61, 0x12), (0xFF7E62, 0x26), (0xFF7E63, 0xB2),
              (0xFF7E77, 0), (0xFFF0E7, 0xff), (0xFFF0E9, 0x32)]
    if not read(0xFFF0D8, 1):
        writes.append((0xFFEFFF, 1))
    return writes


def activate_contact(record, motion_delta, horizontal_impulse):
    """Publish the accepted contact activation's object and player-side state.

    Guard predicates and machine timing remain at the ROM boundary.  This body
    only names the durable player motion, script, object transition, and
    horizontal-impulse effects after that boundary accepts proximity.
    """
    return [
        (0xFF7DFC, (motion_delta >> 8) & 0xFF), (0xFF7DFD, motion_delta & 0xFF),
        (0xFF7E5A, 0xF8), (0xFF7E5B, 0),
        (0xFF7DFE, 0), (0xFF7DFF, 0xB0),
        (0xFF7E60, 0), (0xFF7E61, 0x12), (0xFF7E62, 0x1C), (0xFF7E63, 0x62),
        (0xFF7E77, 0), (0xFFF0BE, 0xFF), (0xFFF0C0, 0),
        (record, 0x84),
        (record + 0x20, 0), (record + 0x21, 0x12),
        (record + 0x22, 0x2D), (record + 0x23, 0xB2),
        (record + 0x37, 0), (0xFF7E58, horizontal_impulse & 0xFF),
    ]


def transition_contact_66(record, *, publish):
    """Accepted `1AFBF4` object transition and its optional player publish."""
    writes = [(record, 0x66),
              (record + 0x20, 0), (record + 0x21, 0x12),
              (record + 0x22, 0x44), (record + 0x23, 0xB0),
              (record + 0x37, 0)]
    if publish:
        writes.extend(((0xFF7E5A, 0xFB), (0xFF7E5B, 0),
                       (0xFF7E60, 0), (0xFF7E61, 0x12),
                       (0xFF7E62, 0x21), (0xFF7E63, 0xB8),
                       (0xFF7E77, 0), (0xFFF0BE, 0xFF),
                       (0xFFF0C0, 0), (0xFFF0CC, 0)))
    return writes


def transition_contact_6b(record, motion, script):
    """Accepted `1AF978` object motion and the selected type-6B script."""
    return [(0xFF7DFC, (motion >> 8) & 0xFF), (0xFF7DFD, motion & 0xFF),
            (record, 0x6B),
            (record + 0x20, 0), (record + 0x21, 0x12),
            (record + 0x22, (script >> 8) & 0xFF), (record + 0x23, script & 0xFF),
            (record + 0x37, 0)]


def publish_contact_record(record, index, value):
    """The `1AE6DE` publication byte after its caller has accepted it."""
    return [(0xFFAE87 + index, value)] if value else []


def transition_contact_77(record, motion, secondary_motion, script):
    """Accepted `1AF9F6` motion publication and optional type-77 script."""
    writes = [(0xFF7DFC, (motion >> 8) & 0xFF), (0xFF7DFD, motion & 0xFF),
              (0xFF7DFA, (secondary_motion >> 8) & 0xFF),
              (0xFF7DFB, secondary_motion & 0xFF)]
    if script is not None:
        writes.extend(((record + 0x20, 0), (record + 0x21, 0x12),
                       (record + 0x22, (script >> 8) & 0xFF), (record + 0x23, script & 0xFF),
                       (record, 0x77)))
    return writes


def begin_contact_launch():
    """Publish the motion/script state before the optional contact sound."""
    return [(0xFF7E5A, 0xF8), (0xFF7E5B, 0),
            (0xFF7E60, 0), (0xFF7E61, 0x12), (0xFF7E62, 0x1C), (0xFF7E63, 0x62),
            (0xFF7E77, 0), (0xFFF0BE, 0xFF), (0xFFF0C0, 0)]


def finish_contact_launch(record):
    """Advance the contact object after its optional sound request."""
    return [(record, 0x84), (record + 0x20, 0), (record + 0x21, 0x12),
            (record + 0x22, 0x4B), (record + 0x23, 0x3E), (record + 0x37, 0)]


def finish_contact_type7e(*, clear_armed):
    """The finite `1AFE1C` exits before its progress/stream handoff."""
    writes = []
    if clear_armed:
        writes.append((0xFFF114, 0))
    writes.extend(((0xFF7DFE, 0), (0xFF7DFF, 0xB0),
                   (0xFF7E00, 1), (0xFF7E01, 0x80)))
    return writes


def contact_landing_script(read, kind):
    """Select the landing script after a contact stops vertical movement."""
    if 0x50 <= kind < 0x52:
        return 0x121964
    if read(0xFFF173, 1):
        return 0x121F74
    if read(0xFFF0B0, 2):
        return 0x1220AA
    return 0x121F84 if read(0xFFF0EB, 1) < 0x28 else 0x121BB6


def contact_position(read):
    """Apply the current motion offsets to the paired player coordinates."""
    return ((read(0xFF7DF6, 2) + read(0xFF7DFA, 2)) & 0xFFFF,
            (read(0xFF7DF8, 2) + read(0xFF7DFC, 2)) & 0xFFFF)


def complete_contact_landing(kind, script=None):
    """Durable 1ABCA0 landing publication after its boundary guards admit it."""
    writes = [(0xFFF0C1, 0xFF), (0xFFF0CD, 0xFF), (0xFFF0D3, kind), (0xFFF0EB, 0)]
    if script is not None:
        writes.extend(((0xFF7E5A, 0), (0xFF7E5B, 0),
                       (0xFF7E60, (script >> 24) & 0xFF), (0xFF7E61, (script >> 16) & 0xFF),
                       (0xFF7E62, (script >> 8) & 0xFF), (0xFF7E63, script & 0xFF),
                       (0xFF7E77, 0), (0xFFF0CC, 0), (0xFFF101, 0)))
    return writes


def publish_contact_position(x, y):
    """Publish the paired player position copies used by 1A8E0C."""
    return [(0xFF7E02, (x >> 8) & 0xFF), (0xFF7E03, x & 0xFF),
            (0xFF7E42, (x >> 8) & 0xFF), (0xFF7E43, x & 0xFF),
            (0xFF7E04, (y >> 8) & 0xFF), (0xFF7E05, y & 0xFF),
            (0xFF7E44, (y >> 8) & 0xFF), (0xFF7E45, y & 0xFF)]


def _word(address, value):
    return [(address, (value >> 8) & 0xFF), (address + 1, value & 0xFF)]


def _long(address, value):
    return [(address + index, (value >> (8 * (3 - index))) & 0xFF) for index in range(4)]


def contact_type55_guard(read, record):
    """Select 1AF590's arm from live RAM and name its distance facts.

    ``FFF0BE`` chooses the family: clear falls straight into the bit-4
    distance guard; set first tests ``FFF0C0``, and a clear ``FFF0C0`` is a
    direct flag return that never reads the record.  The guard subtracts the
    object's horizontal delta from the previous motion word and negates a
    borrowed result; a distance under six transitions the object, which is
    not recovered.  Returns ``(arm, facts)`` with ``arm`` one of ``direct``,
    ``inactive``, ``transition`` or ``guard``.
    """
    selector = read(0xFFF0BE, 1)
    facts = {'selector': selector}
    if selector and not read(0xFFF0C0, 1):
        return 'direct', facts
    facts['flags'] = read(record + 6, 1)
    if not facts['flags'] & 0x10:
        return 'inactive', facts
    delta = (read(record + 4, 2) - read(0xFF7DF8, 2) - 18) & 0xFFFF
    previous = read(0xFF7DFC, 2)
    difference = (previous - delta) & 0xFFFF
    borrowed = previous < delta
    facts.update(delta=delta, previous=previous, difference=difference, borrowed=borrowed,
                 distance=(-difference) & 0xFFFF if borrowed else difference)
    return ('transition' if facts['distance'] < 6 else 'guard'), facts


def contact_type55_return():
    """The tail flag every recovered Type-55 return publishes through 1AE6B4."""
    return [(0xFFF0F5, 0xFF)]


def contact_type58_guard(read, record):
    """Select 1AF5F0's arm from live RAM and name its distance facts.

    Same dispatch shape as ``contact_type55_guard`` (the same ``FFF0BE``
    family selector, the same record-plus-6 bit-4 activity test, the same
    shared 1AE6B4 tail), but this entry's own guard adds 2 to the delta
    rather than subtracting 18, and its limit is 0xC rather than 6.  Unlike
    Type-55, both sides of the guard are observed on the recorded history and
    recovered here: a distance under the limit is the object's ordinary
    return, not a transition.  Returns ``(arm, facts)`` with ``arm`` one of
    ``direct``, ``inactive``, ``guard_fail`` or ``guard_pass``.
    """
    selector = read(0xFFF0BE, 1)
    facts = {'selector': selector}
    if selector and not read(0xFFF0C0, 1):
        return 'direct', facts
    facts['flags'] = read(record + 6, 1)
    if not facts['flags'] & 0x10:
        return 'inactive', facts
    delta = (read(record + 4, 2) - read(0xFF7DF8, 2) + 2) & 0xFFFF
    previous = read(0xFF7DFC, 2)
    difference = (previous - delta) & 0xFFFF
    borrowed = previous < delta
    facts.update(delta=delta, previous=previous, difference=difference, borrowed=borrowed,
                 distance=(-difference) & 0xFFFF if borrowed else difference)
    return ('guard_pass' if facts['distance'] < 0xC else 'guard_fail'), facts


def contact_type58_fail():
    """The tail flag every recovered Type-58 direct/inactive/guard-fail return publishes through 1AE6B4."""
    return [(0xFFF0F5, 0xFF)]


def contact_type58_pass(delta):
    """The motion word a Type-58 guard-pass return publishes locally through 1AF636."""
    return _word(0xFF7DFC, delta)


def contact_type74_guard(read, record):
    """Select 1AFA84's arm from live RAM and name its distance facts.

    Same FFF0BE/FFF0C0 family selector as Type-55/58, but this entry has no
    bit-4 activity test at all: a cleared selector, or a selector with
    FFF0C0 set, falls straight into the distance guard, which subtracts
    0xB from the delta and bounds it to 0xA.  Returns ``(arm, facts)`` with
    ``arm`` one of ``direct``, ``guard_fail`` or ``guard_pass``.
    """
    selector = read(0xFFF0BE, 1)
    facts = {'selector': selector}
    if selector and not read(0xFFF0C0, 1):
        return 'direct', facts
    delta = (read(record + 4, 2) - read(0xFF7DF8, 2) - 0xB) & 0xFFFF
    previous = read(0xFF7DFC, 2)
    difference = (previous - delta) & 0xFFFF
    borrowed = previous < delta
    distance = (-difference) & 0xFFFF if borrowed else difference
    facts.update(delta=delta, previous=previous, difference=difference,
                 borrowed=borrowed, distance=distance)
    return ('guard_pass' if distance < 0xA else 'guard_fail'), facts


def contact_type74_fail():
    """The tail flag every recovered Type-74/75 direct/guard-fail return publishes through 1AE6B4."""
    return [(0xFFF0F5, 0xFF)]


def contact_type74_pass(delta):
    """The motion word a Type-74/75 guard-pass return publishes locally through FF7DFC."""
    return _word(0xFF7DFC, delta)


def contact_type74_target(read, record, player_x):
    """1AFAC4..1AFAF8's horizontal-window, kind and state gate.

    Reached only after a guard pass.  The screen position ``player_x`` must
    fall inside ``[record_x - 0x10, record_x + 0x10)``, the record's own
    kind byte must still be 0x74 (a kind-0x75 self-marker never
    re-triggers, which is how the kind-0x75 collection-dispatch slot that
    shares this same entry always declines past this point), FFF0D8 must be
    clear, and FF7E5A must be a strictly positive word.  Returns
    ``(stage, facts)`` where ``stage`` names the first failing check, or
    ``spawn``.
    """
    record_x = read(record + 2, 2)
    upper = (record_x + 0x10) & 0xFFFF
    facts = {'record_x': record_x, 'upper': upper}
    if player_x >= upper:
        return 'window_upper', facts
    lower = (upper - 0x20) & 0xFFFF
    facts['lower'] = lower
    if player_x < lower:
        return 'window_lower', facts
    kind = read(record, 1)
    facts['kind'] = kind
    if kind != 0x74:
        return 'kind_mismatch', facts
    gate = read(0xFFF0D8, 1)
    facts['gate'] = gate
    if gate:
        return 'state_gate', facts
    state = read(0xFF7E5A, 2)
    facts['state'] = state
    if state & 0x8000:
        return 'negative_state', facts
    if state == 0:
        return 'zero_state', facts
    return 'spawn', facts


def contact_type74_retype(record):
    """The triggering record's own self-retype writes 1AFAFC..1AFB14 publish
    once the window/kind/state gate passes: it becomes a used kind-0x75
    marker (FFF0CC and FFF0B0 latches cleared, a fixed template long
    published at +0xA, +0x36 cleared) so it never re-triggers a second
    spawn -- the kind-0x75 recheck in ``contact_type74_target`` fails on it.
    """
    return [(0xFFF0CC, 0), (0xFFF0B0, 0), (0xFFF0B1, 0),
            *_long(record + 0xA, 0x120A42), (record + 0x36, 0),
            (record, 0x75)]


def contact_type74_position(destination, x, y):
    """The child slot's position copy 1AFB28..1AFB2E publishes once
    ``initialize`` has expanded the fixed 19-byte template into it --
    ``initialize`` deliberately leaves offsets 2..5 alone for this."""
    return [*_word(destination + 2, x), *_word(destination + 4, y)]


def contact_type46_request(read):
    """1AEF5C's capped command-66 counter and its sound request.

    The counter byte advances by one up to ``0x39``.  An already-capped
    counter returns without a request and a muted ``FFF57D`` replaces the
    object without sound; neither arm is recovered.  Returns ``(writes,
    facts)`` where ``facts`` names the old and new counter, the request
    command and both refusal conditions.
    """
    old = read(0xFF7E3C, 1)
    value = min(old + 1, 0x39)
    facts = {'old': old, 'value': value, 'capped': old == 0x39,
             'sound': read(0xFFF57D, 1), 'command': 0x66}
    return [(0xFF7E3C, value)], facts


def contact_type43_update(read, record):
    """1AE64C's motion span and type-8A template publication.

    Only an active ``FFF0C1`` publishes.  The secondary motion word becomes
    the record's link field minus the horizontal motion; the four span words
    at ``FF7E0A`` combine the low nibbles of the motion words with the new
    secondary and the previous motion, then the high bits alone; the record
    becomes type ``8A`` with template ``124454`` and the ``FFF154`` latch is
    set.  Returns ``(writes, facts)``: the old secondary motion the caller
    restores after its sound request, the new value, the vertical span left
    in D0, and the activity and sound predicates.
    """
    active = read(0xFFF0C1, 1)
    facts = {'active': active, 'sound': read(0xFFF57D, 1), 'command': 0x63}
    if not active:
        return [], facts
    old_secondary = read(0xFF7DFA, 2)
    motion_x, motion_y = read(0xFF7DF6, 2), read(0xFF7DF8, 2)
    new_secondary = (read(record + 2, 2) - motion_x) & 0xFFFF
    spans = (((motion_x & 0xF) + new_secondary) & 0xFFFF,
             ((motion_y & 0xF) + read(0xFF7DFC, 2)) & 0xFFFF,
             motion_x & 0xFFF0, motion_y & 0xFFF0)
    writes = [*_word(0xFF7DFA, new_secondary),
              (record, 0x8A), (record + 0x34, 0xFF),
              *_long(record + 0x20, 0x124454), (record + 0x37, 0),
              *_word(0xFF7E0A, spans[0]), *_word(0xFF7E0C, spans[1]),
              *_word(0xFF7E0E, spans[2]), *_word(0xFF7E10, spans[3]),
              (0xFFF154, 0xFF)]
    facts.update(old_secondary=old_secondary, new_secondary=new_secondary, vertical_span=spans[3])
    return writes, facts


def _overlay(read, writes, address, size):
    values = {at: value for at, value in writes}
    if size == 1:
        return values.get(address, read(address, size))
    return int.from_bytes(bytes(values.get(address + i, (read(address + i, 1))) for i in range(size)), 'big')
