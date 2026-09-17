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
