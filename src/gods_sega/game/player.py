"""The player state machine (ROM 005700-0075D6) and its shared tail.

Once (every logical tick, order 22 of ``../../../docs/gods/tick-map.md``) the
main loop calls ``005700``.  It reads the state index ``STATE_INDEX``
(``FFF192``) and a per-state working word ``STATE_COUNTER`` (``FFF190``,
loaded into D7) and, unless ``FROZEN_FLAG`` (``FFFFEECD``) is set or
``ACTIVE_GATE`` (``FFFFF210``) is non-negative -- either sends control
straight to the shared tail below -- jumps through ``STATE_TABLE`` (the ROM
table at ``005618``, eight bytes per entry: a word then the handler
address) to one of ``STATE_HANDLERS``' 29 bodies.  Every path a handler can
take -- including state 7's own bare ``rts`` below -- either returns
directly or, far more often, falls into the shared tail at ``0075D6``.

The tail is not a small helper: ``0075D6`` writes ``STATE_COUNTER`` back
unconditionally, calls the tile trigger scan (``tile_trigger_scan``,
``00773A``) once, then runs a camera-relative window computation over
``POSITION_X``/``POSITION_Y`` against a *second* pair of tracked words
(``FFF3EE``/``FFF3F0``, clamped toward the position in steps of 4 within
bands of 0x50-0xD0 in x and, depending on ``FFFFEF4E``, a different
comparison in y) and, on the read so far, ends by re-indexing
``STATE_TABLE`` at ``STATE_INDEX + STATE_COUNTER`` and tail-jumping
(``0076AA jmp $1312``) into a *second*, distinct inline VDP tile-upload
routine (ROM 001312-0013CE: its own ``movem`` frame, its own
camera-subtracted descriptor lookup through the SAME ROM table
``066794`` ``game/sprites.py`` already names, and a register-counted
``move.l (a0)+,(a6)`` loop copying up to 0xC0 longwords into the VDP data
port) whose own ``rts`` pops the ORIGINAL caller's return address directly
-- the same "platform tail" shape ``0048B4``'s tail jump into ``0047DA``
proved (no intermediate resume layer), but for a *second*, not yet
recovered, sprite-emitter-shaped routine.  A witnessed tile-trigger-scan
'trigger' arm (below) cascades further still, through the event table at
``004494``, into deeply unrecovered creature/spawn code (``00FB2C`` and
below) before rejoining the same tail.  Recovering any state's own
composition therefore needs this whole tail recovered first --
``docs/gods/blockers/2026-09-17-005700.md``.

Record fields verified this session (a state whose meaning could not be
read this session stays "state N" -- see ``STATE_HANDLERS``):

- ``POSITION_X``/``POSITION_Y`` (``FFF18C``/``FFF18E``): the player's own
  position, the same words ``game/grid.py``'s ``GRID_X``/``GRID_Y`` name.
- ``STATE_INDEX`` (``FFF192``): the state table selector.
- ``STATE_COUNTER`` (``FFF190``): D7 at entry, read back from RAM and
  written back to RAM unconditionally by the tail regardless of which
  state ran; several handlers reload it fresh (``moveq #n,d7``) as their
  own per-state working counter (a sub-phase, a retry count, or an index
  into ``STATE_TABLE`` a second time at the tail's own icon draw) rather
  than a single fixed meaning across states.
- ``FROZEN_FLAG`` (``FFFFEECD``, byte): dispatch is skipped for the whole
  tick when this is nonzero (state or the tail: the tick's mass, both, are
  bypassed).
- ``ACTIVE_GATE`` (``FFFFF210``, word): dispatch only runs while this is
  negative; a value that is zero or positive also sends control straight
  to the shared tail without running a state handler at all.

Fields the tail itself touches, named for what the arithmetic supports:
``FFFFF3EE``/``FFFFF3F0`` (a tracked camera-relative window, clamped
toward ``POSITION_X``/``POSITION_Y`` in steps of four), ``FFFFEF4E`` (a
flag selecting between two window computations, unread this session
beyond that it is a flag).  Fields read inside individual state handlers
but not yet traced past a handler's own head this session -- ``F194``,
``F196``, ``F198``, ``F19A``, ``F19C``, ``F1A0``, ``F1A4``, ``F1A6``,
``F1A8``, ``F1AE``, ``F1B0``, ``F1B8`` (jump/climb physics, seen in states
8-14, 16-17), ``EA20``/``EA1E``/``EA23`` (input-derived words/bitmask
tested throughout, presumably the pad-latch intents ``004150`` -- order 4
of the tick -- derives) -- are not documented further here; the task's
own ``F206``/``F252`` were not reached by any handler head this session
and are not claimed.

``STATE_HANDLERS[i]`` is the ROM address ``STATE_TABLE``'s i-th entry
jumps to.  Handler bodies are NOT modelled here beyond state 7's rts and,
in ``tile_trigger_scan`` below, the shared tail's own first call.
"""
from __future__ import annotations

STATE_INDEX = 0xFFF192            # word: the state table selector (jmp table[005618][F192])
STATE_COUNTER = 0xFFF190          # word: D7 at entry; the tail writes it back unconditionally
FROZEN_FLAG = 0xFFFFEECD          # byte: dispatch skipped for the whole tick when nonzero
ACTIVE_GATE = 0xFFFFF210          # word: dispatch only runs while this is negative
POSITION_X, POSITION_Y = 0xFFF18C, 0xFFF18E   # words: the player's own position (game.grid.GRID_X/GRID_Y)

STATE_TABLE = 0x005618
STATE_HANDLERS = (
    0x006FFE, 0x007282, 0x0074F0, 0x007516, 0x007538, 0x00746A, 0x0074C2, 0x006FFC,
    0x00648C, 0x0066A8, 0x005EA2, 0x005D32, 0x005FF4, 0x006B4E, 0x006DA6, 0x006D68,
    0x006686, 0x006666, 0x005834, 0x005886, 0x0069AC, 0x006886, 0x0062B0, 0x006164,
    0x006AD8, 0x006B14, 0x005724, 0x00581E, 0x005828)
# States never entered by any of the eight recordings' 13,488-34,904 activations of 005700 each
# (a full-history tally, not the shared census tool: recovery_census.py's own path-signature
# classifier explodes past --max-classes 400 on this dispatcher, since two states rarely execute
# the identical internal branch pattern -- see the blocker).  Real ROM code, not claimed here.
UNWITNESSED_STATES = (7, 15)
TAIL_ENTRY = 0x0075D6              # every witnessed state handler's own exit; also the "inactive" arm's target
SHARED_TAIL_ALT_GATE = 0xFFFFEF4E  # word: nonzero selects the cutscene-style tracker (ROM 00755A) instead of
                                    # the follow-point step (game.camera.follow_point_step); zero on every
                                    # occurrence of every recording (55,326 activations, all eight histories)


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


# --- the shared tail's own first call: the tile trigger scan (00773A/0077A8) ---
#
# Reached unconditionally from every activation of 005700 that is not state
# 7's bare rts (below).  Up to two columns (the player's own grid column,
# and, when the low five bits of x are >= 0x10, the one to its left) of
# three rows each (the cell at the player's own row, +0x80, +0x100 -- the
# same work-RAM grid game.grid.GRID_TABLE/0063FA/00FDB8/010CBC all index,
# 128 bytes per row) are tested in program order against TILE_THRESHOLD.
# Every check but the scan's own LAST one reaches 0077A8 by ``bsr`` (returns
# to try the next cell if this one declines), while the last one tail-
# branches there instead (``bra.b``, since no further cell follows).
#
# 0077A8 itself is now characterised in full (18 Sep, disassembly of
# 0077A8-007878): it reads the cell's OWN byte as a record kind, looks up
# ``EVENT_STATUS_WORDS`` (the SAME table game.conditions.py's own kinds 5/6
# index, ``STATUS_WORDS``) at ``kind - 3``, and, when that status word is
# zero or negative, does nothing durable at all and returns -- the checked
# cell raised nothing, and the scan (called by ``bsr``) tries the next cell
# exactly as if this one had never exceeded the threshold.  Only a
# STRICTLY POSITIVE status word clears ten hard-coded flag words (real
# code, not modelled: no recording has ever been seen with any of them set)
# and dispatches through the event table at ``004494``, indexed by
# ``status - 1`` (``EVENT_HANDLERS``, 1-11) -- kind 3 is the trigger
# evaluator ``00462C``, already recovered (``game.triggers``); the rest
# (``0045D0``, ``00457A``, ``0044C0``, ``0094D0``, ``009514``, ``00D2BA``,
# ``00FB28``-``00FB34``) are separate routines of their own.  This is the
# actual "found an event" arm (``docs/gods/blockers/2026-09-17-005700.md``);
# a cell merely exceeding ``TILE_THRESHOLD`` is not by itself unmodelled --
# most such cells decline at the status check and the activation composes
# exactly as if the scan had found nothing (43% of 13,519 occurrences on
# fb408bc75597 never even call 0077A8; a further, larger fraction call it
# one or more times but every call declines -- see the ledger).  Every
# register 0077A8 touches on a decline (d0, a0) is dead by the tail's own
# next durable effect, same as for a scan that finds nothing at all.
TILE_TABLE = 0xFFFF885E            # the same work-RAM grid 0063FA/00FDB8/010CBC index
TILE_ROW_BYTES = 0x80
TILE_X_BIAS = 0x10
TILE_Y_MASK = 0xFFF0
TILE_THRESHOLD = 2                 # a cell's byte > 2 calls 0077A8

EVENT_STATUS_WORDS = 0xFFFF502A    # == game.conditions.STATUS_WORDS; entry at base + 4 * (kind - 3)
EVENT_STATUS_INDEX_BIAS = 3
EVENT_TABLE = 0x004494             # one long per event, indexed by (status - 1)
EVENT_HANDLERS = (0x0045D0, 0x00457A, 0x00462C, 0x0094D0, 0x009514, 0x0044C0,
                  0x00FB28, 0x00FB2C, 0x00FB30, 0x00FB34, 0x00D2BA)
EVENT_RECORD_INDEX_OFFSET = 2      # the SAME EVENT_STATUS_WORDS entry's own +2 word: kind 3's (00462C's)
                                    # own trigger.TRIGGER_TABLE record index (00462C: move.w 2(a0),d0),
                                    # read from the STATUS_WORDS entry a0 already points at (0077B0-0077BA)
                                    # when the status word itself (+0) was read; unread by any other kind.


def tile_row(y):
    """00773C-00774A: (y & TILE_Y_MASK) << 3, left in D1 by the scan's own head and NEVER touched
    again before any raise this module composes (0077A8's own status check and the raiser's own
    dispatch preamble both leave D1 alone) -- so this is also the low word every raise's own entry D1
    carries, for as long as no condition predicate (kind 9/10) overwrites it."""
    return ((y & TILE_Y_MASK) << 3) & 0xFFFF


def _tile_cell(x, y):
    column = (_signed_word((x + TILE_X_BIAS) & 0xFFFF) >> 5) & 0xFFFF
    row = tile_row(y)
    return (TILE_TABLE + _signed_word(column) + _signed_word(row)) & 0xFFFFFFFF


def event_status(read, tile_value):
    """0077A8's own status check for a cell whose byte exceeded ``TILE_THRESHOLD``.

    ``tile_value`` is read again from ``EVENT_STATUS_WORDS`` at ``tile_value
    - EVENT_STATUS_INDEX_BIAS`` (a word, the SAME table's 4-byte stride
    ``game.conditions.STATUS_WORDS`` uses).  The ROM takes one of THREE
    branches on this word (``0077BE bmi`` then ``0077C2 beq``), not two: a
    NEGATIVE status declines by the ``bmi`` taken arm (``'declined'``,
    witnessed 517 times over the 654 retained fixtures, none of the other
    two); a ZERO status declines too, but by the OTHER instruction
    (``bmi`` not taken, ``beq`` taken) -- the SAME outcome (the scan tries
    the next cell) at a DIFFERENT cost, unwitnessed by any of the eight
    recordings, so it stays its own named arm (``'declined-zero'``) rather
    than being folded into ``'declined'`` on an untraced cost; a strictly
    POSITIVE value is the 1-11 index into ``EVENT_TABLE``
    (``EVENT_HANDLERS[value - 1]``) after the ten unmodelled flag clears --
    ``'event'`` -- and the raiser also reads the SAME table entry's own
    ``EVENT_RECORD_INDEX_OFFSET`` (+2) word (``record_index``): kind 3's own
    handler (00462C) reads it back as its trigger-record index (``move.w
    2(a0),d0``, ``a0`` still the STATUS_WORDS entry address this function
    read the status word from); the other ten kinds never read it, but it
    costs nothing to carry for every kind alike.
    """
    index = (tile_value - EVENT_STATUS_INDEX_BIAS) & 0xFFFF
    address = (EVENT_STATUS_WORDS + 4 * index) & 0xFFFFFFFF
    status = read(address, 2)
    signed = _signed_word(status)
    if signed < 0:
        return {'arm': 'declined', 'status': status}
    if signed == 0:
        return {'arm': 'declined-zero', 'status': status}
    handler = EVENT_HANDLERS[signed - 1] if signed <= len(EVENT_HANDLERS) else None
    record_index = read((address + EVENT_RECORD_INDEX_OFFSET) & 0xFFFFFFFF, 2)
    return {'arm': 'event', 'status': status, 'kind': signed, 'handler': handler,
            'status_address': address, 'record_index': record_index}


def tile_trigger_scan(read, x, y):
    """What 00773A/0077A8 does at the player's own position (x, y): see the module docstring above.

    Returns the checked cell addresses and byte values, whether the scan
    widened to a second column, ``checks`` (one entry per cell whose byte
    exceeded ``TILE_THRESHOLD``, in scan order, each carrying its own
    ``event_status`` result), ``fires`` (the sub-list of ``checks`` whose
    arm is not the witnessed ``'declined'`` -- an ``'event'`` (real code
    this module does not model further) or the unwitnessed
    ``'declined-zero'``, either of which the boundary must decline the
    whole activation for), and, for backward compatibility with callers
    that only care whether 0077A8 was ever reached, ``arm`` (``'clean'``:
    no cell exceeded the threshold; ``'trigger'``: at least one did,
    whether or not any of them actually fired an event) and
    ``trigger_index`` (the first such cell).
    """
    base = _tile_cell(x, y)
    cells = [base, (base + TILE_ROW_BYTES) & 0xFFFFFFFF, (base + 2 * TILE_ROW_BYTES) & 0xFFFFFFFF]
    widen = (x & 0x1F) >= 0x10
    if widen:
        left = (base - 1) & 0xFFFFFFFF
        cells += [left, (left + TILE_ROW_BYTES) & 0xFFFFFFFF, (left + 2 * TILE_ROW_BYTES) & 0xFFFFFFFF]
    values = [read(cell & 0xFFFFFF, 1) for cell in cells]
    checks = []
    for index, value in enumerate(values):
        if value <= TILE_THRESHOLD:
            continue
        checks.append({'index': index, 'value': value, **event_status(read, value)})
    trigger = checks[0]['index'] if checks else None
    fires = [check for check in checks if check['arm'] != 'declined']
    return {'cells': cells, 'values': values, 'widen': widen,
            'arm': 'clean' if trigger is None else 'trigger', 'trigger_index': trigger,
            'checks': checks, 'fires': fires}


# --- The shared tail's own state-table re-index (ROM 007670-0076AA) --------------------------------
#
# Reached unconditionally after the follow-point step (``game.camera.follow_point_step``) or its
# unmodelled EF4E-nonzero sibling (ROM 00755A): re-indexes ``STATE_TABLE`` at ``STATE_INDEX``, adds
# back the ORIGINAL entry D7 (``STATE_COUNTER``, still held live in D7 -- not the value already
# written back to RAM at the tail's own first instruction), and uses the sum as an index into a
# second ROM table (0076B8, unbounded like ``game.sprites``' own descriptor tables -- read live, never
# hard-coded) to select a tile/sprite descriptor for the second inline upload (ROM 001312, the
# ceded operation ``boundary.player_tail_plan`` hands the machine).  A bit test against one of two
# 32-bit ROM masks (0076B0 for a sum under 0x20, 0076B4 otherwise), indexed by the sum's own low five
# bits, decides whether the descriptor's own flip bit (0x8000) is set.  Pure arithmetic and ROM/RAM
# reads; no store of its own.
STATE_TABLE_REINDEX_LOW_MASK, STATE_TABLE_REINDEX_HIGH_MASK = 0x0076B0, 0x0076B4
STATE_TABLE_REINDEX_TABLE = 0x0076B8
STATE_TABLE_REINDEX_SPLIT = 0x20


def state_table_reindex(read, state_index, state_counter):
    """007670-0076AA: the descriptor index (and its own flip bit) for the second inline upload.

    ``state_counter`` is D7 as the tail's caller left it (the state
    handler's own working counter), read fresh here exactly as the ROM's
    own ``add.w d7,d2`` does -- not re-derived from the ``STATE_COUNTER``
    RAM word the tail already wrote back.  Returns the entry longword's own
    upper half (``high``, preserved into D2 by every later ``.w`` op), the
    sum (``index``, D2's own low word after the add), which mask table was
    used, and the final descriptor value with its own flip bit applied.
    """
    entry = read(STATE_TABLE + 8 * (state_index & 0xFFFF), 4)
    high, low = (entry >> 16) & 0xFFFF, entry & 0xFFFF
    index = (low + state_counter) & 0xFFFF
    if index < STATE_TABLE_REINDEX_SPLIT:
        mask_table, mask = 'low', read(STATE_TABLE_REINDEX_LOW_MASK, 4)
    else:
        mask_table, mask = 'high', read(STATE_TABLE_REINDEX_HIGH_MASK, 4)
    bit = index & 0x1F
    descriptor = read((STATE_TABLE_REINDEX_TABLE + ((index * 2) & 0xFFFF)) & 0xFFFFFFFF, 2)
    flip = bool((mask >> bit) & 1)
    if flip:
        descriptor |= 0x8000
    return {'high': high, 'index': index, 'mask_table': mask_table, 'mask': mask, 'flip': flip,
            'descriptor': descriptor}


# --- 006AD8 (state 24) / 006B14 (state 25): the contact-consume family's own callers ------------
#
# Two near-identical handlers -- 24 calls the already-recovered 012DA0 (game.pickups.contact_consume,
# routine 0), 25 calls 012E5A (routine 1) -- differing only in which consumer they call and
# CONTACT_DIRECTION's own sign (+1/-1, unconditional on entry; what reads it back is not traced
# here).  A 3-tick sequence over STATE_COUNTER (D7, incremented unconditionally on entry): tick 1
# (the counter becomes 1) calls the consumer once and falls into the shared tail; tick 2 (becomes 2)
# just falls into the tail; tick 3 (reaches 3) transitions to state 14 (STATE_INDEX = 0xE) --
# CONTACT_OVERRIDE_FLAG's own bit 0 clear reloads the counter from CONTACT_OVERRIDE_COUNTER instead
# of leaving it at 3 -- and copies CONTACT_OVERRIDE_Y into grid.GRID_Y unconditionally, before
# falling into the tail the same way.  STATE_COUNTER itself is not written here: the shared tail's
# own prefix (0075D6, already recovered as 'player-tail') writes it back from D7 unconditionally,
# exactly as every other state handler's own counter update does.
CONTACT_DIRECTION = 0xFFFFF1A8
CONTACT_OVERRIDE_FLAG = 0xFFFFF1AD      # byte: bit 0 set keeps the counter at 3 on transition
CONTACT_OVERRIDE_COUNTER = 0xFFFFF1AC   # word: the counter's own alternate value when bit 0 is clear
CONTACT_OVERRIDE_Y = 0xFFFFF1AA         # word: copied into grid.GRID_Y unconditionally on transition
CONTACT_HIT_TRANSITION_STATE = 0xE      # state 14
CONTACT_HIT_DIRECTION = {0: 1, 1: 0xFFFF}   # routine 0 (state 24) / 1 (state 25) -- CONTACT_DIRECTION's own value
CONTACT_HIT_RESET_COUNTER = {0: 3, 1: 1}    # the counter's own reset value on transition, when the override flag is set


def movement_hit_state(read, routine, state_counter):
    """006AD8 (routine 0, state 24) / 006B14 (routine 1, state 25): the shared 3-tick shape.

    Returns the arm ('call' -- ticks 1, also calls the consumer; 'wait' -- tick 2; 'transition' --
    tick 3), the new STATE_COUNTER (for the caller to compose into its own D7, not stored here),
    whether the consumer is called this tick, and the transition's own stores.
    """
    from .grid import GRID_Y
    counter = (state_counter + 1) & 0xFFFF
    calls_consumer = counter == 1
    stores = {CONTACT_DIRECTION & 0xFFFFFF: (CONTACT_HIT_DIRECTION[routine], 2)}
    if counter < 3:
        return {'arm': 'call' if calls_consumer else 'wait', 'counter': counter,
                'calls_consumer': calls_consumer, 'stores': stores}
    override_flag = read(CONTACT_OVERRIDE_FLAG, 1) & 1
    new_counter = CONTACT_HIT_RESET_COUNTER[routine] if override_flag else read(CONTACT_OVERRIDE_COUNTER, 2)
    stores[STATE_INDEX] = (CONTACT_HIT_TRANSITION_STATE, 2)
    stores[GRID_Y] = (read(CONTACT_OVERRIDE_Y, 2), 2)
    return {'arm': 'transition', 'counter': new_counter, 'calls_consumer': False, 'stores': stores,
            'override_flag': bool(override_flag)}


# --- 007282: state 1's own decision tree, up to the shared tail (0075D6) or the contact-search-
# found hand-off into state 5's own dispatch read (0074A8-0074B4) -- `docs/gods/blockers/
# 2026-09-17-008222.md`'s "18 September (continued)" addendum, where the whole tree is transcribed
# from a recursive-descent disassembly and cross-checked against the tracer. -----------------------
#
# Reads the grid cell 0063FA already names (game.grid.grid_cell) at the player's own position, three
# pad-intent words (FFFFEA1E/EA20/EA23, `game/player.py`'s own docstring already flags these as
# unread pad-latch intents) and a movement flag (FFFFF182).  Ends with `pc = 0x0075D6` on every arm
# but the contact-search-found hand-off, which ends at `pc = 0x0075DA` (skipping the tail's own first
# instruction, already done by the hand-off's own `move.w d7,$f190.w`) -- the same "one gate hands off
# to a separately-armed gate" shape `movement_hit_state`'s own states 24/25 already use for the SAME
# tail.  One arm is real ROM code this session declines by name: `0072D8`'s own box-overlap scan
# (`FFFFEA1E == 1`, 7 of 3,181 occurrences on the main history -- game.movement.box_overlap_scan is
# already recovered but not yet composed here).  A STATE_COUNTER already above 7 reaching the main
# cascade's own reset (`007448`) IS witnessed (8 of 3,181, always 0x2D -- the shared sub-body's own
# `'shared-reset'` arm below is the only place that stores a counter this large) and is modelled: the
# reset undoes the `POSITION_X` step already taken and masks the counter back to 0-7, net-neutral.
STATE1_ENTRY = 0x007282
STATE1_SHARED_SUB = 0x007208           # 0073F2's own target: a five-instruction sub-body only state 1 reaches
STATE1_HANDOFF = 0x00749A              # the contact-search-found hand-off into state 5's own dispatch read
STATE1_HANDOFF_TABLE = 0x0074B8        # 0074B0's own PC-relative table, always read at index 0 from here
EA1E_WORD, EA20_WORD, EA23_WORD = 0xFFFFEA1E, 0xFFFFEA20, 0xFFFFEA23   # pad-intent words, game/player.py's own docstring
F194, F196, F198, F19A, F19C, F1A0 = 0xFFFFF194, 0xFFFFF196, 0xFFFFF198, 0xFFFFF19A, 0xFFFFF19C, 0xFFFFF1A0
F24A = 0xFFFFF24A
MOVEMENT_FLAG = 0xFFFFF182              # word: gates the cascade's own f182-set arm (007458)
STATE1_GRID_OFFSETS = ((1, 0x00740A), (0x81, 0x007414), (0x101, 0x00741E))   # +1/+0x81/+0x101, TILE_ROW_BYTES apart


def _wall_stores():
    return {STATE_INDEX: (0xC, 2), F194 & 0xFFFFFF: (0, 2), F1A0 & 0xFFFFFF: (0, 2), F198 & 0xFFFFFF: (0, 2)}


def state1_step(read, d7):
    """007282: state 1's own head, up to the shared tail, a contact-search call, or a named decline.

    ``d7`` is ``STATE_COUNTER`` as the dispatcher's own entry left it (the tail writes it back later;
    nothing before this routine's own tail-reaching branches touches it).  Every arm carries the grid
    cell's own ``d0``/``d1``/``address`` (0063FA's own exit registers, `game.grid.grid_cell`) so the
    boundary need not call it twice.  The ``'gate'`` arm is where the cascade begins: ``needs_search``
    true means the boundary must call the already-recovered `game.pickups.contact_search` first (a
    found result hands off via ``state1_handoff`` below; a not-found result, and the ``False`` case
    directly, both continue into ``state1_cascade``).
    """
    from .grid import grid_cell
    from .pickups import MOVEMENT_SOUND_CUE
    cell = grid_cell(read)
    address = cell['address']
    position_x = read(POSITION_X, 2)
    base = {'d0': cell['d0'], 'd1': cell['d1'], 'address': address, 'row_source': cell['row_source'],
            'position_x': position_x}
    gate_direct = read((address + 0x180) & 0xFFFFFF, 1) == 1
    if gate_direct:
        wall, low_lt_8 = False, None
    else:
        low_lt_8 = (position_x & 0x1E) < 8
        wall = low_lt_8 or read((address + 0x181) & 0xFFFFFF, 1) != 1
    base['gate_direct'] = gate_direct
    base['low_lt_8'] = low_lt_8
    if wall:
        return {'arm': 'wall', 'd7': 0, 'stores': _wall_stores(), **base}
    ea20 = _signed_word(read(EA20_WORD, 2))
    if ea20 < 0:
        return {'arm': 'negative', 'd7': 2, 'stores': {STATE_INDEX: (3, 2)}, **base}
    if read(EA1E_WORD, 2) == 1:
        return {'arm': 'box-overlap', **base}
    bit0 = read(EA23_WORD, 1) & 1
    if bit0:
        ea20_word = read(EA20_WORD, 2) & 0xFFFF
        f196 = 0 if ea20_word == 0 else 4
        stores = {STATE_INDEX: (9, 2), F196 & 0xFFFFFF: (f196, 2), F19A & 0xFFFFFF: (position_x, 2),
                  F19C & 0xFFFFFF: (0, 2), MOVEMENT_SOUND_CUE & 0xFFFFFF: (0x30, 2)}
        return {'arm': 'jump-start', 'd7': 0, 'f196': f196, 'stores': stores, **base}
    bit2 = read(EA23_WORD, 1) & 4
    return {'arm': 'gate', 'needs_search': bool(bit2), 'position_x': position_x, **base}


def state1_cascade(read, d7, position_x, address):
    """0073E4-0075D6: the cascade `state1_step`'s own `'gate'` arm reaches directly (`EA23` bit 2
    clear) or a contact-search 'not found' result continues into.  `FFFFF182` first; when clear,
    `FFFFEA20 == 1`'s own three grid tests (the SAME row-stride pattern `tile_trigger_scan` already
    names, offsets `+1`/`+0x81`/`+0x101` from the grid pointer 0063FA leaves in `address`) or, when
    not 1, the shared sub-body's own two arms.  A `d7` (STATE_COUNTER) already above 7 reaching the
    grid-clear tail takes `007448`'s own reset (folded into the `'position-advance'` arm below, marked
    `'overflow'`): the +4 just applied to `POSITION_X` is undone again and the counter is forced to 7
    before the same +1/&7 tail every other sub-arm here uses, landing back at 0.
    """
    from .pickups import MOVEMENT_SOUND_CUE
    if read(MOVEMENT_FLAG, 2) & 0xFFFF:
        new_x = (position_x + 4) & 0xFFFF
        return {'arm': 'f182-set', 'd7': (d7 + 1) & 7,
                'stores': {MOVEMENT_FLAG & 0xFFFFFF: (0, 2), POSITION_X: (new_x, 2)}}
    if (read(EA20_WORD, 2) & 0xFFFF) == 1:
        low5 = position_x & 0x1F
        d0 = low5   # 0073F6 move.w f18c,d0; 0073FA andi.w #$1f,d0 -- the low bits, left in D0 either way
        checked = 0
        if low5 < 8:
            for offset, last_pc in STATE1_GRID_OFFSETS:
                checked += 1
                if read((address + offset) & 0xFFFFFF, 1) == 1:
                    return {'arm': 'grid-block', 'last_pc': last_pc, 'low5': low5, 'checked': checked, 'd0': d0}
            checked = 3
        else:
            checked = 0
        if d7 > 7:
            # 007448 moveq #7,d7; 00744A subq.w #4,f18c -- the +4 just below is undone again (net:
            # POSITION_X unchanged), and d7 is forced to 7 before the SAME +1/&7 tail every other
            # sub-arm here uses, landing back at 0.  d7 > 7 only reaches this state from the shared
            # sub-body's own reset arm (0x2D, `'shared-reset'` below), the only place that stores a
            # STATE_COUNTER this large -- witnessed 8 times on the main history.
            return {'arm': 'position-advance', 'd7': 0, 'sound': False, 'low5': low5, 'checked': checked,
                    'd0': d0, 'overflow': True,
                    'stores': {MOVEMENT_FLAG & 0xFFFFFF: (0, 2), POSITION_X: (position_x, 2)}}
        new_x = (position_x + 4) & 0xFFFF
        stores = {MOVEMENT_FLAG & 0xFFFFFF: (0, 2), POSITION_X: (new_x, 2)}
        if d7 == 2:
            stores[MOVEMENT_SOUND_CUE & 0xFFFFFF] = (0x48, 2)
        if d7 == 6:
            stores[MOVEMENT_SOUND_CUE & 0xFFFFFF] = (0x49, 2)
        return {'arm': 'position-advance', 'd7': (d7 + 1) & 7, 'sound': d7 in (2, 6), 'stores': stores,
                'low5': low5, 'checked': checked, 'd0': d0}
    ea1e = _signed_word(read(EA1E_WORD, 2))
    if ea1e < 0:
        return {'arm': 'ea1e-negative', 'd7': 1,
                'stores': {STATE_INDEX: (0x1A, 2), F24A & 0xFFFFFF: (0, 2)}}
    if d7 == 0:
        return {'arm': 'shared-unchanged', 'd7': 0, 'stores': {}}
    return {'arm': 'shared-reset', 'd7': 0x2D, 'stores': {}}


def _handoff(read, state_index):
    """0074A8-0074B4 (reached at 0x00749A for state 1's own STATE_INDEX=5, at 0x0074A2 for state 0's
    own STATE_INDEX=6): the contact-search-found hand-off, fully deterministic, no branch:
    STATE_COUNTER forced to 0, and a PC-relative table read always at index 0 (the ROM's own
    `moveq #0,d7` immediately before it), landing one instruction into the shared tail (`pc =
    0x0075DA`, skipping the tail's own first `move.w d7,$f190.w` -- already done here)."""
    d7 = read(STATE1_HANDOFF_TABLE, 2)
    return {'stores': {STATE_INDEX: (state_index, 2), STATE_COUNTER: (0, 2)}, 'd7': d7}


def state1_handoff(read):
    """00749A-0074B4: state 1's own contact-search-found hand-off (STATE_INDEX forced to 5)."""
    return _handoff(read, 5)


def state0_handoff(read):
    """0074A2-0074B4: state 0's own contact-search-found hand-off (STATE_INDEX forced to 6) -- the
    SAME deterministic tail-let `state1_handoff` reaches, entered one instruction earlier."""
    return _handoff(read, 6)


# --- 00746A: state 5's own table-dispatch entry -- "one region, two gates, one planner"
# (`docs/gods/blockers/2026-09-17-005700.md`'s Decision; confirmed by a full disassembly and cross-
# checked against eleven `factcheck.py facts --path` traces, 18 September).  Reached both by
# STATE_TABLE's own slot 5 (a fresh dispatch with STATE_INDEX already 5) and by a `bra.w` fallthrough
# from inside state 1's own body (`0073E0`, the contact-search-found hand-off's OTHER destination --
# `state1_handoff` reaches `00749A` instead, one instruction further in, so the two never collide).
# Its own counter increment (unconditional) feeds three outcomes: a counter that lands under 5 always
# takes the SAME deterministic table hand-off `state1_handoff`/`state0_handoff` reach at `0074A8`, but
# through the LIVE counter as the table's own index (not forced to 0) and without touching
# STATE_INDEX at all -- this activation is already state 5's own, nothing to re-select; a counter that
# becomes exactly 3 additionally calls the already-recovered contact-consume primary routine (`012DA0`,
# `game.pickups.contact_consume` routine 0 -- the SAME consumer state 24's own `006AD8` calls) first,
# its own result read by nothing here; a counter of 5 or more gates on `FFFFEA23` bit 2 exactly like
# state 1's own 'gate' arm -- clear, or a contact-search (`008222`) 'not found' result, falls all the
# way OUT of state 5's own body into state 1's own gate (`STATE_INDEX` forced to 1, `d7` reset to 2,
# `pc = 0x007282` -- the boundary hands off to state 1's own SEPARATELY ARMED candidate exactly the
# way every other state hands off to the shared tail's own gate); a contact-search 'found' result
# takes the counter-under-5 arm's own hand-off instead, but through the table's own index-0 entry
# (its own `moveq #0,d7` first, `00748A`-`0074A8`, byte-identical to `state1_handoff`'s own shape).
STATE5_ENTRY = 0x00746A
STATE5_CONSUME_COUNTER = 3        # the post-increment counter that calls 012DA0 (contact_consume routine 0)
STATE5_HANDOFF_LIMIT = 5          # post-increment counter under this: the deterministic table hand-off, no gate
STATE5_FALLBACK_STATE_INDEX = 1   # forced onto FFFFF192 before handing off to state 1's own gate
STATE5_FALLBACK_COUNTER = 2       # the caller's own D7 on the fallback hand-off (not stored to RAM here)
STATE5_FALLBACK_PC = 0x007282     # state 1's own entry -- the second of "one region, two gates, one planner"


def state5_step(read, d7):
    """00746A-007496: state 5's own head, up to the deterministic table hand-off, the contact-search
    gate, or the fallback into state 1's own gate.  `d7` is STATE_COUNTER as the dispatcher's own
    entry (or state 1's own `bra.w`) left it.  Returns `'handoff'` (counter under 5: the boundary
    reads `state5_handoff(read, counter)`), `'gate'` (counter >= 5, `FFFFEA23` bit 2 set: the boundary
    must call the already-recovered `game.pickups.contact_search` -- a 'found' result takes
    `state5_handoff(read, 0)`, 'not found' takes the fallback), or `'fallback'` (counter >= 5, bit 2
    clear: straight to state 1's own gate, `state5_fallback_stores()`).  Every arm's own
    `calls_consumer` says whether the boundary must also compose the internal `jsr 012DA0` first
    (`counter == STATE5_CONSUME_COUNTER`, independent of which of the three arms follows it -- the ROM
    tests the counter against 5 the SAME way whether or not it just called the consumer)."""
    counter = (d7 + 1) & 0xFFFF
    calls_consumer = counter == STATE5_CONSUME_COUNTER
    if counter < STATE5_HANDOFF_LIMIT:
        return {'arm': 'handoff', 'counter': counter, 'calls_consumer': calls_consumer}
    bit2 = read(EA23_WORD, 1) & 4
    if not bit2:
        return {'arm': 'fallback', 'counter': counter, 'calls_consumer': calls_consumer}
    return {'arm': 'gate', 'counter': counter, 'calls_consumer': calls_consumer}


def state5_handoff(read, index):
    """0074AA-0074B4 (`'handoff'`, `index` the live counter) or 0074A8-0074B4 (`'gate'`'s own 'found'
    continuation, `index` forced to 0 by its own `moveq` first): the SAME deterministic table read
    `state1_handoff`/`state0_handoff` use (`STATE1_HANDOFF_TABLE`), storing the SAME index it reads by
    into STATE_COUNTER and landing one instruction into the shared tail (`pc = 0x0075DA`) -- but,
    unlike `state1_handoff`/`state0_handoff`, never touching STATE_INDEX (this activation is already
    state 5's own; nothing here re-selects it)."""
    return {'stores': {STATE_COUNTER: (index, 2)}, 'd7': read(STATE1_HANDOFF_TABLE + 2 * index, 2)}


def state5_fallback_stores():
    """00748E-007490: STATE_INDEX forced to 1 (`FFFFF192`) before the `bra.w $7282` that ends the
    activation at state 1's own gate; the caller's own D7 (`STATE5_FALLBACK_COUNTER`, 2) is not stored
    to RAM here -- state 1's own eventual hand-off to the shared tail (`0075D6`) writes STATE_COUNTER
    from D7 unconditionally, exactly as it does for a fresh state-1 dispatch."""
    return {STATE_INDEX: (STATE5_FALLBACK_STATE_INDEX, 2)}


# --- 0074C2: state 6's own table-dispatch entry -- a byte-for-byte MIRROR of state 5's own shape,
# with three constants swapped: it calls the SECONDARY contact-consume routine (`012E5A`, not
# `012DA0`), and its own fallback lands on state 0's own gate (`STATE_INDEX` CLEARED to 0 by a
# `clr.w`, not forced to 1 by a `move.w #imm`; `pc = 0x006FFE`, not `0x007282`) -- reached both by
# STATE_TABLE's own slot 6 and by state 0's own contact-search-found hand-off (`state0_handoff`,
# `0074A2`, which forces STATE_INDEX to 6 before falling in one instruction ahead of state 5's own
# entry).  The counter-under-5 arm and the contact-search gate are the SAME shared code state 5's own
# entry reaches (`0074AA`-`0074B4`'s own table hand-off, `STATE1_HANDOFF_TABLE`) -- `state5_handoff`
# is reused verbatim, not copied, since neither arm has anything state-6-specific in it (confirmed by
# a fresh disassembly, 0074C2-0074FC, 18 September).
STATE6_ENTRY = 0x0074C2
STATE6_CONSUME_COUNTER = 3
STATE6_HANDOFF_LIMIT = 5
STATE6_FALLBACK_STATE_INDEX = 0    # cleared onto FFFFF192 before handing off to state 0's own gate
STATE6_FALLBACK_COUNTER = 2        # the caller's own D7 on the fallback hand-off (not stored to RAM here)
STATE6_FALLBACK_PC = 0x006FFE      # state 0's own entry -- state 6's own half of "two gates, one planner"


def state6_step(read, d7):
    """0074C2-0074EC: state 6's own head -- `state5_step`'s own mirror; see its docstring for the
    shape.  Returns the SAME arm names (`'handoff'`, `'gate'`, `'fallback'`); the boundary reads
    `state5_handoff` for the first two (shared code) and `state6_fallback_stores` for the third."""
    counter = (d7 + 1) & 0xFFFF
    calls_consumer = counter == STATE6_CONSUME_COUNTER
    if counter < STATE6_HANDOFF_LIMIT:
        return {'arm': 'handoff', 'counter': counter, 'calls_consumer': calls_consumer}
    bit2 = read(EA23_WORD, 1) & 4
    if not bit2:
        return {'arm': 'fallback', 'counter': counter, 'calls_consumer': calls_consumer}
    return {'arm': 'gate', 'counter': counter, 'calls_consumer': calls_consumer}


def state6_fallback_stores():
    """0074E6-0074E8: STATE_INDEX CLEARED to 0 (`clr.w $f192.w`, not a `move.w #imm` like state 5's own
    fallback) before the `bra.w $6ffe` that ends the activation at state 0's own gate; the caller's
    own D7 (`STATE6_FALLBACK_COUNTER`, 2) is not stored to RAM here, for the same reason as state 5's
    own fallback."""
    return {STATE_INDEX: (STATE6_FALLBACK_STATE_INDEX, 2)}


# --- 006FFE: state 0's own decision tree -- the "move left" mirror of state 1, NOT a byte-identical
# copy: real differences confirmed by the tracer, not assumed by symmetry (docs/gods/blockers/
# 2026-09-17-008222.md's "18 September (continued)" addendum, extended when state 0 was recovered).
# The wall shape and the shared sub-body (state 0's own inline copy at 0071E6, not shared code the
# way state 1 jumps into 007208) follow the same shape as state 1's with different constants; three
# real differences: (1) state 0's own arm-A test compares FFFFEA20 to the LITERAL 1
# (`cmpi.w #1,ea20; bne`), not its sign, so a negative EA20 can still reach every later branch, unlike
# state 1 where arm A already proves EA20 >= 0; (2) where state 1's own bit-0 sub-arm only ever needed
# EA20's zero/positive split (both converge into the SAME state-9 tail), state 0's needs all three:
# EA20 negative and EA20 zero both reach the SAME state-8 tail, but EA20 positive reaches its own
# three-way grid-byte dispatch (0x0710A-0x007150) state 1 has no analogue of at all, landing on state
# 14 or falling into the shared cascade; (3) the cascade's own low-bits gate compares POSITION_X's low
# 5 bits to 0 (not 8), the grid tests read offsets -1/+0x7F/+0xFF (not +1/+0x81/+0x101) and decrement
# POSITION_X (not increment) -- state 0 is the "moving left" counterpart of state 1's "moving right".
STATE0_ENTRY = 0x006FFE
STATE0_SHARED_SUB = 0x0071E6
F1A4, F1A6, F1A8, F1AE = 0xFFFFF1A4, 0xFFFFF1A6, 0xFFFFF1A8, 0xFFFFF1AE


def _state0_wall_stores():
    return {STATE_INDEX: (0xB, 2), F194 & 0xFFFFFF: (0, 2), F1A0 & 0xFFFFFF: (0, 2), F198 & 0xFFFFFF: (0, 2)}


def _state0_state14_stores():
    return {F1A8 & 0xFFFFFF: (0, 2), STATE_INDEX: (0xE, 2), F1AE & 0xFFFFFF: (0, 2),
            F1A4 & 0xFFFFFF: (0, 2), F1A6 & 0xFFFFFF: (0, 2)}


def state0_step(read, d7):
    """006FFE: state 0's own head, up to the shared tail, a contact-search call, or a named decline.

    Mirrors `state1_step`'s own contract (same base fields: `d0`/`d1`/`address`/`row_source`/
    `position_x`/`gate_direct`/`low_lt_8`), but every test past the initial grid gate is state 0's
    own, not state 1's copied with new constants -- see the module note above.
    """
    from .grid import grid_cell
    from .pickups import MOVEMENT_SOUND_CUE
    cell = grid_cell(read)
    address = cell['address']
    position_x = read(POSITION_X, 2)
    base = {'d0': cell['d0'], 'd1': cell['d1'], 'address': address, 'row_source': cell['row_source'],
            'position_x': position_x}
    gate_direct = read((address + 0x180) & 0xFFFFFF, 1) == 1
    if gate_direct:
        wall, low_lt_8 = False, None
    else:
        low_lt_8 = (position_x & 0x1E) < 8
        wall = low_lt_8 or read((address + 0x181) & 0xFFFFFF, 1) != 1
    base['gate_direct'] = gate_direct
    base['low_lt_8'] = low_lt_8
    if wall:
        return {'arm': 'wall', 'd7': 0, 'stores': _state0_wall_stores(), **base}
    # Arm A: FFFFEA20 == 1 literally (not a sign test) transitions to state 2; EA20's own sign is
    # untested here, unlike state 1's arm A.
    if (read(EA20_WORD, 2) & 0xFFFF) == 1:
        return {'arm': 'transition-2', 'd7': 0, 'stores': {STATE_INDEX: (2, 2)}, **base}
    if read(EA1E_WORD, 2) == 1:
        return {'arm': 'box-overlap', **base}
    bit0 = read(EA23_WORD, 1) & 1
    if bit0:
        ea20_signed = _signed_word(read(EA20_WORD, 2))
        if ea20_signed <= 0:
            f196 = 0xFFFC if ea20_signed < 0 else 0   # -4 (negative) or 0 (zero): the SAME state-8 tail
            stores = {STATE_INDEX: (8, 2), F196 & 0xFFFFFF: (f196, 2), F19A & 0xFFFFFF: (position_x, 2),
                      F19C & 0xFFFFFF: (0, 2), MOVEMENT_SOUND_CUE & 0xFFFFFF: (0x30, 2)}
            return {'arm': 'jump-start', 'd7': 0, 'f196': f196, 'stores': stores, **base}
        # EA20 positive: a three-way grid-byte dispatch state 1 has no analogue of, landing on state
        # 14 (two different ROM entry points, `007132`/`00712C`, only the second also advancing
        # POSITION_X by 0x20 first) or falling into the shared cascade (ARM_A4) untransitioned.
        low5 = position_x & 0x1F
        if low5 <= 0x14 and read(address & 0xFFFFFF, 1) == 2:
            return {'arm': 'transition-14', 'd7': 0x1A, 'advance': False, 'low5': low5,
                    'stores': {POSITION_X: (position_x & 0xFFE0, 2), **_state0_state14_stores()}, **base}
        if low5 > 0x14 or low5 >= 0xC:
            if read((address + 1) & 0xFFFFFF, 1) == 2:
                new_x = (position_x + 0x20) & 0xFFE0
                return {'arm': 'transition-14', 'd7': 0x1A, 'advance': True, 'low5': low5,
                        'stores': {POSITION_X: (new_x, 2), **_state0_state14_stores()}, **base}
        base['low5'] = low5
        base['position_positive'] = True
    bit2 = read(EA23_WORD, 1) & 4
    return {'arm': 'gate', 'needs_search': bool(bit2), **base}


def state0_cascade(read, d7, position_x, address):
    """0071DA(ARM_A4)-0075D6: the cascade `state0_step`'s own `'gate'` arm reaches directly (`EA23`
    bit 2 clear) or a contact-search 'not found' result continues into.  `FFFFF182` first; when
    clear, `FFFFEA20`'s own SIGN (not `== 1`, unlike arm A's own test) selects the shared sub-body
    (`>= 0`) or the three row-stride grid tests at `-1`/`+0x7F`/`+0xFF` (`< 0`, gated by POSITION_X's
    own low 5 bits being exactly 0, not `< 8`); POSITION_X decrements by 4, the mirror of state 1's
    own increment.  A STATE_COUNTER already above 7 here (witnessed, the shared sub-body's own reset
    arm is the only place that stores one this large) undoes the decrement and masks back to 0-7,
    the mirror of state 1's own `007448`.
    """
    from .pickups import MOVEMENT_SOUND_CUE
    if read(MOVEMENT_FLAG, 2) & 0xFFFF:
        new_d7 = (d7 + 1) & 7
        new_x = (position_x - 4) & 0xFFFF
        return {'arm': 'f182-set', 'd7': new_d7,
                'stores': {MOVEMENT_FLAG & 0xFFFFFF: (0, 2), POSITION_X: (new_x, 2)}}
    if _signed_word(read(EA20_WORD, 2)) >= 0:
        return {'arm': 'shared-sub-gate'}   # the boundary composes state0_shared_sub from here
    # 007176 move.w f18c,d0; 00717A andi.w #$1f,d0 -- read regardless of low5's own value, the SAME
    # low-bits value the caller already has; left in D0 either way, mirroring state 1's own 0073F6.
    low5 = position_x & 0x1F
    d0 = low5
    checked = 0
    if low5 == 0:
        for offset, last_pc in ((-1, 0x007186), (0x7F, 0x007190), (0xFF, 0x00719A)):
            checked += 1
            if read((address + offset) & 0xFFFFFF, 1) == 1:
                return {'arm': 'grid-block', 'last_pc': last_pc, 'low5': low5, 'checked': checked, 'd0': d0}
    if d7 > 7:
        new_x = position_x   # the -4 just below is undone again by the overflow's own +4
        return {'arm': 'position-advance', 'd7': 0, 'low5': low5, 'checked': checked, 'overflow': True, 'd0': d0,
                'stores': {MOVEMENT_FLAG & 0xFFFFFF: (0, 2), POSITION_X: (new_x, 2)}}
    new_x = (position_x - 4) & 0xFFFF
    stores = {MOVEMENT_FLAG & 0xFFFFFF: (0, 2), POSITION_X: (new_x, 2)}
    if d7 == 2:
        stores[MOVEMENT_SOUND_CUE & 0xFFFFFF] = (0x48, 2)
    if d7 == 6:
        stores[MOVEMENT_SOUND_CUE & 0xFFFFFF] = (0x49, 2)
    return {'arm': 'position-advance', 'd7': (d7 + 1) & 7, 'low5': low5, 'checked': checked, 'd0': d0,
            'stores': stores}


def state0_shared_sub(read, d7):
    """0071E6-007204: state 0's own inline copy of the shared five-instruction sub-body state 1
    reaches by jumping into 007208 -- the SAME three arms, state 0's own physical copy."""
    ea1e = _signed_word(read(EA1E_WORD, 2))
    if ea1e < 0:
        # 0071EC's own "moveq #$ff,d7" (state 1's copy at 007210 uses "moveq #$1,d7" instead) sign-
        # extends to the FULL 32-bit register, not just the low word like every other arm here --
        # 'd7_full' signals the boundary to skip the usual upper-half-preserving merge.
        return {'arm': 'ea1e-negative', 'd7': 0xFFFF, 'd7_full': 0xFFFFFFFF,
                'stores': {STATE_INDEX: (0x1A, 2), F24A & 0xFFFFFF: (0, 2)}}
    if d7 == 0:
        return {'arm': 'shared-unchanged', 'd7': 0, 'stores': {}}
    return {'arm': 'shared-reset', 'd7': 0x39, 'stores': {}}


# --- 006DA6: state 14's own decision tree -- a vertical-movement dispatcher (states 0/1 are
# horizontal), reached from the tick's own movement cascade the same way, but its own shape:
# a `FFFFEF4A` gate (a flag this module has not otherwise named -- "inactive"/"grounded", read but
# not written here), a STATE_COUNTER wraparound at 0x14 that hands off to the SAME "settle" tail
# either fresh (counter reset to 0) or carried, a `FFFFEA20 == 1` fork into two near-mirror arms (A:
# EA20 == 1, B: EA20's own sign, the SAME asymmetry state 0's own arm A already showed against state
# 1's), and a contact-search gate (`006EC4`) shared by both arms whose own direction depends on
# `FFFFF1A8`'s LIVE value -- set by whichever arm's own bit-2 test fired THIS activation, or else
# whatever a PREVIOUS activation last left there (docs/gods/blockers/2026-09-17-008222.md's "18
# September (continued)" addendum transcribes the whole tree; census `census-006DA6`,
# `--classifier entry`, `--max-classes 4000`, 183 real path classes over 1,155 occurrences).
STATE14_ENTRY = 0x006DA6
FROZEN_LIKE_FLAG = 0xFFFFEF4A          # word: gates the whole routine; unnamed beyond what this reads
F1A8, F1AA, F1AC, F1AE, F1B0, F1B2 = (0xFFFFF1A8, 0xFFFFF1AA, 0xFFFFF1AC, 0xFFFFF1AE, 0xFFFFF1B0, 0xFFFFF1B2)
STATE14_WRAP = 0x14


def state14_step(read, d7):
    """006DA6-006DDA: state 14's own head, up to the EA20-based arm fork.  Returns `'frozen'` (exit
    unchanged, `FFFFEF4A == 0`), `'settle'` (hand off to `state14_settle`, either freshly reset --
    STATE_COUNTER wrapped past `0x14` -- or carrying the caller's own counter -- `FFFFEA1E < 0`), or
    `'main'` (the EA20 == 1 fork, `state14_arm_a`/`state14_arm_b`)."""
    if read(FROZEN_LIKE_FLAG, 2) & 0xFFFF == 0:
        return {'arm': 'frozen'}
    if d7 >= STATE14_WRAP:
        return {'arm': 'settle', 'settle_d7': 0, 'reset': True}
    stores = {F1B0 & 0xFFFFFF: (d7, 2)}
    if _signed_word(read(EA1E_WORD, 2)) < 0:
        return {'arm': 'settle', 'settle_d7': d7, 'reset': False, 'stores': stores}
    ea20 = read(EA20_WORD, 2) & 0xFFFF
    if ea20 == 0:
        stores[F1A4 & 0xFFFFFF] = (0, 2)
        stores[F1A6 & 0xFFFFFF] = (0, 2)
    return {'arm': 'main', 'ea20_one': ea20 == 1, 'stores': stores}


def state14_arm_a(read):
    """006DDE-006E4C: state 14's own arm A (`FFFFEA20 == 1`).  Returns `'contact-gate'` (bit 2 set:
    `FFFFF1A8` forced to 1) or `'contact-gate-plain'` (the f1a6 retry budget not yet exhausted:
    `FFFFF1A8` untouched, left at whatever it already held) to hand off to `state14_contact`;
    `'transition-9'`; or, when the grid tests run (`'cell'` then carries `game.grid.grid_cell`'s own
    result, for the boundary's a0/d0/d1), `'transition-1'` (blocked or the low nibble zero) or
    `'contact-gate'` again (a grid byte matched, `FFFFF1A8` still untouched -- the ROM's own
    `beq.b $6e50` rejoins arm B's entry, whose own `tst.w ea20;bpl.w $6ec4` always takes the positive
    branch here since EA20 is still 1).  `006DFA`'s own `clr.w f1a4.w` is UNCONDITIONAL (it runs
    before the retry-budget compare even looks at its own result), so every arm past the bit-0 test
    carries `FFFFF1A4 == 0` regardless of which branch fires next -- caught by a real trace where
    F1A4 had accumulated a nonzero value from an EARLIER activation's own retries, not guessed.
    `006E2A`'s own `move.w f18e,d0; andi.w #$f,d0` OVERWRITES D0 with the low nibble before EITHER
    the nibble test or `'transition-1'`'s own body -- `'contact-gate-nibble'` carries a `'d0'`
    override for this reason too (not grid_cell's own column), caught the same way."""
    from .grid import grid_cell
    bit2 = read(EA23_WORD, 1) & 4
    if bit2:
        return {'arm': 'contact-gate', 'stores': {F1A8 & 0xFFFFFF: (1, 2)}, 'f1a8_forced': 1}
    bit0 = read(EA23_WORD, 1) & 1
    if bit0:
        from .pickups import MOVEMENT_SOUND_CUE
        position_x = read(POSITION_X, 2)
        stores = {STATE_INDEX: (9, 2), F196 & 0xFFFFFF: (4, 2), F19A & 0xFFFFFF: (position_x, 2),
                  F19C & 0xFFFFFF: (0, 2), MOVEMENT_SOUND_CUE & 0xFFFFFF: (0x30, 2)}
        return {'arm': 'transition-9', 'stores': stores, 'd7': 0xC}
    f1a6 = (read(F1A6, 2) + 1) & 0xFFFF
    if f1a6 <= 5:
        return {'arm': 'contact-gate-f1a6', 'stores': {F1A4 & 0xFFFFFF: (0, 2), F1A6 & 0xFFFFFF: (f1a6, 2)}}
    cell = grid_cell(read)
    address = cell['address']
    for offset in (1, 0x81, 0x101):
        if read((address + offset) & 0xFFFFFF, 1) == 1:
            return {'arm': 'contact-gate-grid',
                    'stores': {F1A4 & 0xFFFFFF: (0, 2), F1A6 & 0xFFFFFF: (0, 2)}, 'cell': cell}
    low_nibble = read(POSITION_Y, 2) & 0xF
    if low_nibble != 0 and read((address + 0x181) & 0xFFFFFF, 1) == 1:
        return {'arm': 'contact-gate-nibble', 'stores': {F1A4 & 0xFFFFFF: (0, 2), F1A6 & 0xFFFFFF: (0, 2)},
                'cell': cell, 'nibble_tested': True, 'd0': low_nibble}
    position_x = read(POSITION_X, 2)
    stores = {F1A4 & 0xFFFFFF: (0, 2), F1A6 & 0xFFFFFF: (0, 2), STATE_INDEX: (1, 2),
              POSITION_X: ((position_x + 8) & 0xFFFF, 2), POSITION_Y: ((read(POSITION_Y, 2) - 4) & 0xFFFF, 2)}
    return {'arm': 'transition-1', 'stores': stores, 'd7': 6, 'cell': cell, 'nibble_tested': low_nibble != 0,
            'd0': low_nibble}


def state14_arm_b(read):
    """006E50-006EBC: state 14's own arm B (`FFFFEA20`'s own sign, the mirror of arm A's literal
    compare).  Returns the same arm names as `state14_arm_a`, `'transition-0'` instead of
    `'transition-1'` (state 0, not state 1); its own `+0x17F` nibble sub-test mirrors arm A's own
    `+0x181` exactly (a matched byte reaches `'contact-gate-nibble'`, anything else -- INCLUDING the
    low nibble already zero -- falls through to `'transition-0'` directly) -- an earlier survey
    mis-read this as an unconditional decline (`'nibble-declined'`), missed because every witnessed
    fb408bc75597 occurrence happened to take the low-nibble-zero shortcut; a tree recording outside
    that single-history census exercised the nibble!=0 fallthrough and caught it.  `006EA0`'s own
    `move.w f18e,d0; andi.w #$f,d0` OVERWRITES D0 with the low nibble before EITHER exit, exactly
    like arm A's own `006E2A` mirror -- both `'contact-gate-nibble'` and `'transition-0'` carry a
    `'d0'` override for this reason, not grid_cell's own column.  UNLIKE arm A, `006E74`'s own
    `clr.w f1a6.w` (the OTHER counter) is the only unconditional clear here -- `FFFFF1A4` itself is
    only ever INCREMENTED (`006E78 addq.w #1,f1a4.w`, real RAM, before the retry-budget compare even
    looks at it) and never re-cleared past the budget (arm A's own mirror explicitly re-clears
    `FFFFF1A6` at its own `006E0A` before the grid_cell call; arm B's `006E84 bsr.w $63fa` has no
    such clear, real ROM bytes confirm), so every arm past the retry budget carries the INCREMENTED
    `f1a4` forward, not zero -- caught by a real trace (`FFFFF1A5` held 6, not 0, at a `'transition-0'`
    exit) where an EARLIER activation's own retries had already pushed the counter past the budget."""
    from .grid import grid_cell
    if _signed_word(read(EA20_WORD, 2)) >= 0:
        return {'arm': 'contact-gate-immediate'}
    bit2 = read(EA23_WORD, 1) & 4
    if bit2:
        return {'arm': 'contact-gate', 'stores': {F1A8 & 0xFFFFFF: (0xFFFF, 2)}, 'f1a8_forced': 0xFFFF}
    bit0 = read(EA23_WORD, 1) & 1
    if bit0:
        from .pickups import MOVEMENT_SOUND_CUE
        position_x = read(POSITION_X, 2)
        stores = {STATE_INDEX: (8, 2), F196 & 0xFFFFFF: (0xFFFC, 2), F19A & 0xFFFFFF: (position_x, 2),
                  F19C & 0xFFFFFF: (0, 2), MOVEMENT_SOUND_CUE & 0xFFFFFF: (0x30, 2)}
        return {'arm': 'transition-8', 'stores': stores, 'd7': 0xD}
    f1a4 = (read(F1A4, 2) + 1) & 0xFFFF
    if f1a4 <= 5:
        return {'arm': 'contact-gate-f1a4', 'stores': {F1A6 & 0xFFFFFF: (0, 2), F1A4 & 0xFFFFFF: (f1a4, 2)}}
    cell = grid_cell(read)
    address = cell['address']
    for offset in (-1, 0x7F, 0xFF):
        if read((address + offset) & 0xFFFFFF, 1) == 1:
            return {'arm': 'contact-gate-grid',
                    'stores': {F1A6 & 0xFFFFFF: (0, 2), F1A4 & 0xFFFFFF: (f1a4, 2)}, 'cell': cell}
    low_nibble = read(POSITION_Y, 2) & 0xF
    if low_nibble != 0 and read((address + 0x17F) & 0xFFFFFF, 1) == 1:
        return {'arm': 'contact-gate-nibble', 'stores': {F1A6 & 0xFFFFFF: (0, 2), F1A4 & 0xFFFFFF: (f1a4, 2)},
                'cell': cell, 'nibble_tested': True, 'd0': low_nibble}
    position_x = read(POSITION_X, 2)
    stores = {F1A6 & 0xFFFFFF: (0, 2), F1A4 & 0xFFFFFF: (f1a4, 2), STATE_INDEX: (0, 2),
              POSITION_X: ((position_x - 8) & 0xFFFF, 2), POSITION_Y: ((read(POSITION_Y, 2) - 4) & 0xFFFF, 2)}
    return {'arm': 'transition-0', 'stores': stores, 'd7': 6, 'cell': cell, 'nibble_tested': low_nibble != 0,
            'd0': low_nibble}


def state14_contact(read, routine, d7, f1a8_override=None):
    """006EC4-006F24: the contact-search gate both arm A and arm B's own `'contact-gate'` (bit 2 set
    THIS activation, forcing `FFFFF1A8` -- `f1a8_override` carries that forced value, since the real
    ROM's own store has not reached RAM yet at this point in the SAME activation) and
    `'contact-gate-*'` results reach -- `FFFFEA23` bit 2 (already tested by whichever arm got here)
    then `FFFFF1A8`'s own sign selects which of two near-identical contact-search continuations
    (state 24 for positive, state 25 for negative); zero, or a 'not found' result, falls through to
    arm D (`state14_arm_d`).  `routine` mirrors `game.pickups.contact_consume`'s own convention (0
    for the positive/state-24 body, 1 for negative/state-25) but is only used by the caller to
    select which contact-search continuation ran; this function itself only decides WHETHER one runs.
    """
    bit2 = read(EA23_WORD, 1) & 4
    if not bit2:
        return {'arm': 'arm-d'}
    f1a8 = _signed_word(read(F1A8, 2)) if f1a8_override is None else _signed_word(f1a8_override)
    if f1a8 == 0:
        return {'arm': 'arm-d'}
    return {'arm': 'contact-search', 'negative': f1a8 < 0}


def state14_contact_found(read, d7, negative):
    """006EDE-006EFA (positive) / 006F08-006F24 (negative): a contact-search 'found' result's own
    continuation -- state 24 for the positive body, 25 for the negative, both the SAME shape: track
    the current position and STATE_COUNTER, halve POSITION_Y's own step when D7 is even."""
    position_y = read(POSITION_Y, 2)
    stores = {F1AA & 0xFFFFFF: (position_y, 2), F1AC & 0xFFFFFF: (d7 & 0xFFFF, 2)}
    if d7 & 1 == 0:
        position_y = (position_y - 4) & 0xFFFF
        stores[POSITION_Y] = (position_y, 2)
    stores[STATE_INDEX] = (0x19 if negative else 0x18, 2)
    return {'stores': stores, 'd7': 0}


def state14_arm_d(read):
    """006F28-006F44: state 14's own arm D (the contact-search gate's own fall-through) --
    `FFFFEA1E == 1` toggles `FFFFF1AE` and transitions to state 13; any other value exits unchanged,
    exactly like state 1's own equivalent no-op decline."""
    if read(EA1E_WORD, 2) != 1:
        return {'arm': 'unchanged'}
    f1ae = (~read(F1AE, 2)) & 0xFFFF
    return {'arm': 'transition-13', 'stores': {F1AE & 0xFFFFFF: (f1ae, 2), STATE_INDEX: (0xD, 2),
                                               F1A4 & 0xFFFFFF: (0, 2), F1A6 & 0xFFFFFF: (0, 2)}}


def state14_settle(read, d7, f1ae_override=None):
    """006F48-006F94: ONE pass through state 14's own "settle" head, reached either fresh
    (STATE_COUNTER wrapped past 0x14) or carrying the caller's own counter (`FFFFEA1E < 0`), and
    again on the rare `'loopback'` arm's own second pass (`006F94`'s own `bra.b $6f48`).
    `FFFFEA20 != 0` hands control back to the main dispatch (`state14_step`'s own `'main'` arm, from
    `006DD4` -- the boundary composes this, not this function); `FFFFEA20 == 0` clears F1A4/F1A6
    again (redundant with `state14_step`'s own clear on the first pass, harmless, but genuinely
    needed on a `'loopback'` pass) and forks on `FFFFF1AE`:

    - `FFFFF1AE == 0` (the common case): bumps the counter and, only above 3, plays a sound and
      toggles `FFFFF1AE` before handing off to `state14_settle_probe` (`'probe'`).
    - `FFFFF1AE != 0` (real, witnessed on a real fraction of activations -- an ODD number of prior
      sound triggers left it set): `006F84`'s own SINGLE `subq.w #1,d7` on the caller's own
      UNMODIFIED counter (not bumped first) either continues straight to the probe with `d7 - 1`
      (`'probe-f1ae'`, no sound) or, when the caller's own counter was exactly 1 (`d7 - 1 == 0`),
      plays the sound, sets the counter back to 1 (`006F8E`'s own `addq.w #1,d7` reads the ALREADY-
      decremented register, 0, not the caller's own original 1) and toggles `FFFFF1AE` back before
      looping to `006F48` itself (`'loopback'`, `next_d7`) -- provably a SINGLE extra pass:
      `FFFFF1AE` is now clear, so the second pass always takes the ordinary bump branch above
      (`d7 = 1` there bumps to 2, `<= 3`, straight to the probe, no further sound or toggle).
    """
    if read(EA20_WORD, 2) & 0xFFFF != 0:
        return {'arm': 'rejoin-main'}
    stores = {F1A4 & 0xFFFFFF: (0, 2), F1A6 & 0xFFFFFF: (0, 2)}
    f1ae = (read(F1AE, 2) & 0xFFFF) if f1ae_override is None else (f1ae_override & 0xFFFF)
    from .pickups import MOVEMENT_SOUND_CUE
    if f1ae != 0:
        after = (d7 - 1) & 0xFFFF
        if after != 0:
            return {'arm': 'probe-f1ae', 'stores': stores, 'settle_d7': after, 'sound': False}
        new_f1ae = (~f1ae) & 0xFFFF
        stores[MOVEMENT_SOUND_CUE & 0xFFFFFF] = (0x6A, 2)
        stores[F1AE & 0xFFFFFF] = (new_f1ae, 2)
        # 006F8E's own addq.w #1,d7 operates on `after` (always 0 here, the loopback's own trigger
        # condition), giving 1 -- not the caller's own original d7 (always 1 too, since after == 0
        # means d7 - 1 == 0, but the ADDQ reads the register's CURRENT value, already decremented).
        return {'arm': 'loopback', 'stores': stores, 'next_d7': (after + 1) & 0xFFFF, 'next_f1ae': new_f1ae}
    bumped = (d7 + 1) & 0xFFFF
    sound = bumped > 3
    if sound:
        settle_d7 = (bumped - 2) & 0xFFFF   # 006F82/006F84's own two SUBQ #1: net two decrements from `bumped`
        stores[MOVEMENT_SOUND_CUE & 0xFFFFFF] = (0x6A, 2)
        stores[F1AE & 0xFFFFFF] = ((~f1ae) & 0xFFFF, 2)
    else:
        settle_d7 = bumped
    return {'arm': 'probe', 'stores': stores, 'settle_d7': settle_d7, 'sound': sound}


def state14_settle_probe(read, settle_d7, f1b0_override=None):
    """006F66-006FB4: the settle tail's own bounded grid probe -- saves POSITION_Y, steps it by -6,
    calls the already-recovered grid cell, and tests `+0x80`/`-0x80`; either match exits immediately
    with no further stores, a double miss restores STATE_COUNTER from F1B0 and POSITION_Y (F1B2)
    before exiting.  `f1b0_override` carries F1B0's own just-stored value on the "carried counter"
    settle route (`state14_step`'s own `006DBA move.w d7,f1b0.w`, not yet in real RAM at this point
    in the SAME activation); `None` (the "freshly reset" route, F1B0 genuinely untouched this
    activation) reads F1B0 live, whatever an EARLIER activation last left there."""
    from .grid import grid_cell
    position_y = read(POSITION_Y, 2)
    new_y = (position_y - 6) & 0xFFFF
    cell = grid_cell(lambda a, s: new_y if (a & 0xFFFFFF) == (POSITION_Y & 0xFFFFFF) else read(a, s))
    address = cell['address']
    if read((address + 0x80) & 0xFFFFFF, 1) == 2:
        return {'arm': 'blocked', 'position_y': new_y, 'cell': cell,
                'stores': {POSITION_Y: (new_y, 2), F1B2 & 0xFFFFFF: (position_y, 2)}}
    if read((address - 0x80) & 0xFFFFFF, 1) == 2:
        return {'arm': 'blocked', 'position_y': new_y, 'cell': cell,
                'stores': {POSITION_Y: (new_y, 2), F1B2 & 0xFFFFFF: (position_y, 2)}}
    restored_d7 = read(F1B0, 2) if f1b0_override is None else f1b0_override
    return {'arm': 'exhausted', 'position_y': new_y, 'cell': cell, 'd7': restored_d7 & 0xFFFF,
            'stores': {POSITION_Y: (position_y, 2), F1B2 & 0xFFFFFF: (position_y, 2)}}


# --- 0066A8: state 9's own decision tree -- a falling/jump-arc physics dispatcher (states 8/9 are a
# pair the same way 5/6 and 0/1 are, sharing a jump-arc velocity table and two small grid-probe
# leaves, 006442/006468, at ROM addresses right before state 8's own entry 00648C -- confirmed by a
# fresh disassembly, 0066A8-006886 where state 21's own entry begins, cross-checked against
# factcheck.py facts --path on nine real fixtures over census-0066A8-* covering every witnessed
# arm, 18 September).  Reads: STATE_COUNTER (D7, normalized by the head below, never incremented),
# F19C (the fall timer, a byte offset directly into the jump-arc table STATE9_FALL_TABLE -- it
# steps by exactly 2 every tick that does not transition out, so it always lands on one of the
# table's own word boundaries), the grid cell (twice: once before any X move, once after -- a second
# activation can shift POSITION_X between them), F196 (an X step applied once F19C reaches
# STATE9_ADVANCE_GATE), F19A (a tracked X position, compared against the live one for the two landing
# checks below), F19E (an unwitnessed "double the fall step" flag -- 0 on every one of the 1,287
# retained fixtures across all five recordings; declined if ever seen nonzero), EA1E/EA23 (pad-latch
# words game/player.py's own docstring already flags).
#
# The head (0066A8-0066D2) normalizes D7 into one of three values used from here on: 0xC stays 0xC
# until F19C reaches STATE9_ADVANCE_GATE, then becomes 5 (a MOVEQ, full clear); 5 stays 5; 0 stays 0
# until the same F19C gate, then becomes 4 (an ADDQ, the entry's own upper half survives); anything
# else becomes 5 (a MOVEQ).  Two shared grid-probe leaves follow the SAME shape state1_step's own
# gate test uses (_row_gate_open below, parameterised on the row bias): the first
# (0066D6-00670C, inline, not a call) gates an X-advance by F196 the same way, tested at row bias
# 0x180 (three rows down: +1/+0x81/+0x101, low5 < 8 skips it) -- found, or low5 >= 8, skips
# the advance and any grid test entirely; not found and low5 < 8 with F19C past the gate applies the
# X step.  A second grid_cell call (00670C) re-reads the cell (the X step may have moved it) before
# the EA1E-gated landing checks: EA1E < 0 tests a "landing-a" shape (F196 != 0, the live X != F19A, X's
# low 5 bits == 0, the cell's own byte == 2) that transitions to state 14; EA1E == 1 (not just >= 0 --
# any other nonnegative value, or EA1E < 0 already declined above, falls straight through) tests a
# near-identical "landing-b" shape (the SAME X/F19A/low-5 gate, either the cell's own byte or the row
# above it == 2) that transitions to state 13 -- UNWITNESSED by any of the 1,287 retained fixtures,
# declined by name.  Past both landing checks: a ground-ahead probe (_row_gate_open at row bias
# 0x180, the SAME shape the X-advance step uses) once F19C reaches STATE9_TRIGGER_GATE, BEFORE the
# fall step -- found transitions to state 16 ("ground-before"); not found (or F19C not there yet)
# falls into the fall step itself: POSITION_Y -= the jump-arc table's own entry at F19C (doubled if
# F19E is set -- unwitnessed, declined), then a near-row probe (_row_gate_open at row bias 0) at
# the NEW position -- found transitions to state 12 ("landed-after-move"); not found re-tries the
# SAME ground-ahead probe at the NEW position once F19C reaches STATE9_TRIGGER_GATE (real: F19C did
# not change between the two tries, but POSITION_Y just did) -- found transitions to state 16 the
# SAME way ("ground-after", reusing "ground-before"'s own tail); not found gates a trigger event
# (F19C past STATE9_ADVANCE_GATE, EA23 bit 2 set, game.pickups.contact_search finds something,
# F19C short of STATE9_TRIGGER_CAP) that transitions to state 20 with F19C advanced by 2 regardless;
# failing THAT gate too, F19C simply advances by 2 and, short of STATE9_COUNTDOWN_CAP, the activation
# ends unchanged (still state 9) -- reaching the cap forces a landing at state 12 regardless
# ("terminal-velocity").
STATE9_ENTRY = 0x0066A8
F19E = 0xFFFFF19E
F1B8 = 0xFFFFF1B8
F1BA = 0xFFFFF1BA
STATE9_FALL_TABLE = 0x006414       # byte-offset-indexed by F19C directly (F19C already steps by 2)
STATE9_FALL_TABLE_LIMIT = 0x2C     # the table's own last valid F19C entry
STATE9_COUNTDOWN_CAP = 0x2E        # F19C's own cap: reaching it (after the +2 below) forces a landing
STATE9_TRIGGER_GATE = 0x16         # F19C at/after this: the ground-ahead probe runs
STATE9_ADVANCE_GATE = 4            # F19C at/after this: the X-advance / trigger gates open
STATE9_TRIGGER_CAP = 0x2C          # a trigger found at/after this F19C no longer fires


def _row_gate_open(read, address, position_x, bias):
    """006442 (bias = 0x180, three rows down -- "ahead") / 006468 (bias = 0, the current row --
    "here"): the SAME shape state1_step's own gate test uses (0x180/0x181 there), returning
    whether the probe's own D1 comes back 1 ("found"/open) rather than 0."""
    if read((address + bias) & 0xFFFFFF, 1) == 1:
        return True
    if (position_x & 0x1E) < 8:
        return False
    return read((address + bias + 1) & 0xFFFFFF, 1) == 1


def _state9_head(read, d7):
    """0066A8-0066D2: normalizes D7; see the module note above.  `source` says how: 'untouched'
    (nothing touches the register at all -- 0xC or 0 short of the F19C gate, or already 5), 'moveq'
    (a full 32-bit clear to 5), or 'addq' (0 to 4, a word op -- the entry's own upper half survives)."""
    f19c = read(F19C, 2)
    if d7 == 0xC:
        if f19c >= STATE9_ADVANCE_GATE:
            return 5, 'moveq'
        return d7, 'untouched'
    if d7 == 5:
        return d7, 'untouched'
    if d7 == 0:
        if f19c >= STATE9_ADVANCE_GATE:
            return 4, 'addq'
        return d7, 'untouched'
    return 5, 'moveq'


def state9_step(read, d7):
    """0066A8-006882: state 9's own whole decision tree.  `d7` is STATE_COUNTER as the dispatcher's
    own entry left it.  Returns one of: 'landing-14' (transitions to state 14, witnessed once),
    'landing-13' (declined, unwitnessed), 'ground-before' / 'ground-after' (both transition to state
    16, game.player._state9_ground_stores), 'landed' (state 12), 'fall-tail' (the caller composes a
    contact-search call and calls state9_fall_tail below), or 'countdown' is folded into 'fall-tail'
    too (the tail decides).  Carries d7/source from the head for the boundary's own upper-half
    bookkeeping."""
    from .grid import grid_cell
    d7, source = _state9_head(read, d7)
    cell = grid_cell(read)
    address = cell['address']
    position_x = read(POSITION_X, 2)
    low5 = position_x & 0x1F
    base = {'d7': d7, 'source': source, 'cell1': cell}
    blocked = False
    if low5 < 8:
        for offset in (1, 0x81, 0x101):
            if read((address + offset) & 0xFFFFFF, 1) == 1:
                blocked = True
                break
    advanced = False
    if not blocked:
        f19c = read(F19C, 2)
        if f19c >= STATE9_ADVANCE_GATE:
            step = read(F196, 2)
            position_x = (position_x + step) & 0xFFFF
            advanced = True
    base['blocked'], base['advanced'] = blocked, advanced
    if advanced:
        def _read_after_advance(a, s, _position_x=position_x):
            return _position_x if (a & 0xFFFFFF) == (POSITION_X & 0xFFFFFF) else read(a, s)
        cell2 = grid_cell(_read_after_advance)
    else:
        cell2 = grid_cell(read)
    address2 = cell2['address']
    base['cell2'] = cell2

    ea1e = _signed_word(read(EA1E_WORD, 2))
    tracked_x = read(F19A, 2)
    if ea1e < 0:
        # 00671E beq.b $6726: F196 == 0 does NOT decline -- it SKIPS the tracked-X test (below) and
        # falls straight into the low-bits/cell test, exactly as a real trace outside the original
        # survey caught (F196 == 0 still reaching a real landing, 18 September).
        f196 = read(F196, 2)
        blocked = f196 != 0 and position_x == tracked_x
        if not blocked and (position_x & 0x1F) == 0 and read(address2 & 0xFFFFFF, 1) == 2:
            return {'arm': 'landing-14', 'stores': {
                POSITION_X: (position_x & 0xFFE0, 2), POSITION_Y: (read(POSITION_Y, 2) & 0xFFF8, 2),
                F1A8 & 0xFFFFFF: (0, 2), STATE_INDEX: (0xE, 2), F1AE & 0xFFFFFF: (0, 2),
                F1A4 & 0xFFFFFF: (0, 2), F1A6 & 0xFFFFFF: (0, 2)}, **base}
    elif ea1e == 1:
        if position_x != tracked_x and (position_x & 0x1F) == 0 and \
                (read(address2 & 0xFFFFFF, 1) == 2 or read((address2 + 0x80) & 0xFFFFFF, 1) == 2):
            return {'arm': 'landing-13', **base}

    f19c = read(F19C, 2)
    if f19c >= STATE9_TRIGGER_GATE and _row_gate_open(read, address2, position_x, 0x180):
        return {'arm': 'ground-before', 'stores': _state9_ground_stores(read(POSITION_Y, 2)), **base}

    if f19c > STATE9_FALL_TABLE_LIMIT:
        raise ValueError('state 9 fall table index past its own last entry')
    step = _signed_word(read((STATE9_FALL_TABLE + f19c) & 0xFFFFFF, 2))
    new_y = (read(POSITION_Y, 2) - step) & 0xFFFF
    if read(F19E, 2) != 0:
        raise ValueError('state 9 doubled fall step (FFFFF19E != 0) not witnessed by a recording')

    def _read_after_fall(a, s, _new_y=new_y):
        return _new_y if (a & 0xFFFFFF) == (POSITION_Y & 0xFFFFFF) else read(a, s)
    address3 = grid_cell(_read_after_fall)['address']
    base['new_y'] = new_y
    if _row_gate_open(read, address3, position_x, 0):
        new_y_aligned = (new_y & 0xFFF0) + 0x10
        return {'arm': 'landed', 'stores': {
            POSITION_Y: (new_y_aligned & 0xFFFF, 2), STATE_INDEX: (0xC, 2), F194 & 0xFFFFFF: (0, 2),
            F1A0 & 0xFFFFFF: (0, 2), F198 & 0xFFFFFF: (0, 2)}, **base}

    if f19c >= STATE9_TRIGGER_GATE and _row_gate_open(read, address3, position_x, 0x180):
        return {'arm': 'ground-after', 'stores': _state9_ground_stores(new_y), **base}

    needs_search = f19c >= STATE9_ADVANCE_GATE and bool(read(EA23_WORD, 1) & 4)
    base['needs_search'] = needs_search
    return {'arm': 'fall-tail', **base}


def _state9_ground_stores(position_y):
    """0067B8-0067CA: STATE_INDEX forced to 0x10 (16), POSITION_Y rounded down to a tile boundary
    (the ORIGINAL, pre-fall-step Y for 'ground-before'; the POST-fall-step `new_y` for
    'ground-after' -- the caller passes the right one), D7 cleared (MOVEQ), F1B8 cleared and a sound
    cue (0x39) queued -- the SAME stores either way, save for which Y."""
    from .pickups import MOVEMENT_SOUND_CUE
    return {STATE_INDEX: (0x10, 2), POSITION_Y: (position_y & 0xFFF0, 2), F1B8 & 0xFFFFFF: (0, 2),
            MOVEMENT_SOUND_CUE & 0xFFFFFF: (0x39, 2)}


def state9_fall_tail(read, found, f19c, new_y):
    """00682A-006882: the fall step's own tail, reached when neither ground probe found anything.  A
    trigger (F19C past STATE9_ADVANCE_GATE, FFFFEA23 bit 2 set, a contact-search found result
    the caller composes, F19C short of STATE9_TRIGGER_CAP) transitions to state 20; otherwise F19C
    simply advances by 2, and -- short of STATE9_COUNTDOWN_CAP -- the activation ends unchanged
    (still state 9); reaching the cap forces a landing at state 12 instead.  `found` is `None` when
    the gate itself never opened (no search was needed), else the composed contact-search result."""
    if found and f19c < STATE9_TRIGGER_CAP:
        return {'arm': 'trigger', 'stores': {
            STATE_INDEX: (0x14, 2), F1BA & 0xFFFFFF: (1, 2), F19C: ((f19c + 2) & 0xFFFF, 2)}, 'd7': 1}
    new_f19c = (f19c + 2) & 0xFFFF
    if new_f19c >= STATE9_COUNTDOWN_CAP:
        return {'arm': 'terminal', 'stores': {
            STATE_INDEX: (0xC, 2), F194 & 0xFFFFFF: (0, 2), F1A0 & 0xFFFFFF: (0, 2), F198 & 0xFFFFFF: (0, 2),
            F19C: (new_f19c, 2)}, 'd7': 0}
    return {'arm': 'countdown', 'stores': {F19C: (new_f19c, 2)}}
