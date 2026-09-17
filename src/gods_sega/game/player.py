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
# The first cell whose byte exceeds it calls 0077A8 (a caller-record status
# lookup through the SAME STATUS_WORDS table game.conditions.py's own kinds
# 5/6 index, then -- unless that status is negative or zero -- ten
# hard-coded flag clears and a jsr through the event table at 004494,
# reaching further unrecovered code, e.g. creature/solid spawn logic
# through 00FB2C); every check but the scan's own LAST one reaches 0077A8
# by ``bsr`` (returns to try the next cell), while the last one tail-
# branches there instead (``bra.b``, since no further cell follows) --
# 0077A8 is not recovered, so a scan that finds a cell over the threshold
# declines the WHOLE activation, not just this call.  A
# scan that finds nothing (43% of 13,519 occurrences on fb408bc75597, per
# the 00773A-only census) is a leaf: no store, no branch outside the
# routine, and every register it touches (d0, d1, a0) is dead -- overwritten
# by the tail's own very next instructions -- before the tail's first
# durable effect.  Verified against the tracer (docs/gods/blockers/
# 2026-09-17-005700.md); not registered as its own recovery candidate,
# since a leaf with no durable effect at all has no mutant the game can
# see (recovery-process.md's own gate) -- it is meant to be composed into
# a parent (the tail itself, or eventually a full state) whose own writes
# give a real one, the way game.grid.grid_cell_at is 0063FA's own
# arithmetic without a gate of its own.
TILE_TABLE = 0xFFFF885E            # the same work-RAM grid 0063FA/00FDB8/010CBC index
TILE_ROW_BYTES = 0x80
TILE_X_BIAS = 0x10
TILE_Y_MASK = 0xFFF0
TILE_THRESHOLD = 2                 # a cell's byte > 2 raises an event through 0077A8


def _tile_cell(x, y):
    column = (_signed_word((x + TILE_X_BIAS) & 0xFFFF) >> 5) & 0xFFFF
    row = ((y & TILE_Y_MASK) << 3) & 0xFFFF
    return (TILE_TABLE + _signed_word(column) + _signed_word(row)) & 0xFFFFFFFF


def tile_trigger_scan(read, x, y):
    """What 00773A does at the player's own position (x, y): see the module docstring above.

    Returns the checked cell addresses and byte values, whether the scan
    widened to a second column, and the arm (``'clean'``: every checked
    byte is at or below ``TILE_THRESHOLD``; ``'trigger'``: the index of the
    first cell that exceeds it, real code this module does not model).
    """
    base = _tile_cell(x, y)
    cells = [base, (base + TILE_ROW_BYTES) & 0xFFFFFFFF, (base + 2 * TILE_ROW_BYTES) & 0xFFFFFFFF]
    widen = (x & 0x1F) >= 0x10
    if widen:
        left = (base - 1) & 0xFFFFFFFF
        cells += [left, (left + TILE_ROW_BYTES) & 0xFFFFFFFF, (left + 2 * TILE_ROW_BYTES) & 0xFFFFFFFF]
    values = [read(cell & 0xFFFFFF, 1) for cell in cells]
    trigger = next((index for index, value in enumerate(values) if value > TILE_THRESHOLD), None)
    return {'cells': cells, 'values': values, 'widen': widen,
            'arm': 'clean' if trigger is None else 'trigger', 'trigger_index': trigger}
