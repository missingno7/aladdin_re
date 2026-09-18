"""The achievement/collectible-slot tracker's own reset call (``0047DA``), and the achievement
highlight cycle (``005CEE``) states 19/18's own shared body calls.

``0047DA`` is reached from ``004790`` (the slot dispatch, one call per matching tracked id) and from
``0048B4`` inside ``004800``/``00475E``'s own bounded record scans (the trigger firing subsystem
blocker's second structure, ``docs/gods/blockers/2026-09-16-00462C-firing.md``): four consecutive
tracked-id slots at ``FFFFF22E`` are marked empty (``-1``) by index, and the routine always calls
into the collected-item icon upload (``001648``) to clear the matching VRAM icon slot -- with ``D2``
fixed at ``-1`` on every witnessed call, the icon upload's own "clear" arm, never its real
tile-descriptor upload (a positive ``D2``, unreached from this caller: the routine's own code sets
``D2`` unconditionally before the call, so no recording needs to witness the other value for this
fact to hold).

**Correction (18 Sep, states 19/18's own blocker,
``docs/gods/blockers/2026-09-18-005886.md``):** ``ACHIEVEMENT_SLOTS``/``HIGHLIGHT_ID`` are NOT
specific to this tracker -- ``005CEE`` (reached from states 19 and 18, not from the achievement slot
dispatch family at all) indexes ``ACHIEVEMENT_SLOTS`` directly by ``HIGHLIGHT_ID`` (``(a3,
d4.w)`` with ``d4 = HIGHLIGHT_ID*2``), a different addressing convention from ``achievement_slot_reset``'s
own four fixed offsets, but the SAME two fields.  Both belong to whatever subsystem owns the
proximity-scan-and-highlight mechanic below, shared with the achievement/collectible-slot tracker by
address, not by ownership.

Pure functions of ``read(address, size)``; no cycles, CCR, stack or registers -- ``0047DA``'s whole
routine is scratch (its own ``d1``/``d2``/``a0`` frame restores their entry values unchanged at the
RTS); ``achievement_highlight_cycle`` below is likewise scratch (only ``d7`` is saved/restored, by
``005CEE`` itself, entirely inside its own seam).
"""
from __future__ import annotations

ACHIEVEMENT_SLOTS = 0xFFFFF22E    # four consecutive words, one per tracked id (FFEF8C/F01E/F0B0's own ids); -1 = empty
HIGHLIGHT_ID = 0xFFFFF236         # word: D0 matching this selects 001648's own DDDDDDDD fill instead of FFFFFFFF
WITNESSED_ICON_SLOTS = (0, 1, 3)  # D0: which of 001648's four VRAM icon slots (its own table at 0016C2); 2 unwitnessed


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def achievement_slot_reset(read, d0):
    """0047DA: mark tracked-id slot ``d0`` empty and derive the icon upload's own D1/D2."""
    slot = d0 & 0xFFFF
    highlighted = slot == (read(HIGHLIGHT_ID, 2) & 0xFFFF)
    return {'slot': slot, 'stores': {(ACHIEVEMENT_SLOTS + 2 * slot) & 0xFFFFFF: (0xFFFF, 2)},
            'highlighted': highlighted, 'icon_d1': 1 if highlighted else 0, 'icon_d2': 0xFFFF}


# --- 004790: the slot dispatch (a caller-supplied tracked-id pointer) -------
#
# A2 points at the caller's own record; its first word is a tracked id,
# looked up in a shared 10-byte-stride table at FFFFF8C2 (also read by the
# unrelated 004926) for a status word at +4.  Every one of 12 retained
# fixtures across all eight recordings shows status 2; the ROM's own other
# arm (a nonzero, non-2 status skips the dispatch outright) is real code no
# recording enters.  When the gate passes, the tracked id is compared in
# turn against 0047DA's own four ids (FFFFF22E/F230/F232/F234) -- all four
# comparisons run regardless of an earlier match (0049DA's own kind of
# redundant check), so at most one of them can differ from the others
# (the ids are themselves distinct) and 0047DA is called at most once, with
# D0 the matched slot index.
RECORD_TABLE = 0xFFFFF8C2   # ten-byte-stride records, one per tracked id (shared with 004926, an unrelated routine)
RECORD_STRIDE = 10
WITNESSED_STATUS = (2,)     # 4(record): only 2 is witnessed; 0 would take the same code path but is not
TRACKED_IDS = (0xFFFFF22E, 0xFFFFF230, 0xFFFFF232, 0xFFFFF234)   # the same four words achievement_slot_reset marks


def _adda_w(base, word):
    """68000 ADDA.W: the 16-bit source sign-extends before the 32-bit address add."""
    word &= 0xFFFF
    if word & 0x8000:
        word -= 0x10000
    return (base + word) & 0xFFFFFFFF


def _record_address(tracked):
    """The exact 0047792-0479E arithmetic: two separate adda.w steps (d5*2, then d5*8), each its own
    sign extension -- not simply RECORD_TABLE + 10*tracked, which only agrees while neither doubling
    overflows a 16-bit word (true of every witnessed tracked id, all under 128)."""
    step1 = (tracked * 2) & 0xFFFF
    a3 = _adda_w(RECORD_TABLE, step1)
    step2 = (tracked * 8) & 0xFFFF
    return _adda_w(a3, step2)


def match_tracked_id(read, tracked):
    """Compare a tracked id already in hand against 0047DA's own four ids; the matching slot, or None."""
    return next((slot for slot, address in enumerate(TRACKED_IDS) if tracked == (read(address, 2) & 0xFFFF)), None)


def achievement_slot_dispatch(read, a2):
    """004790: the slot dispatch over a caller-supplied record pointer."""
    tracked = read(a2 & 0xFFFFFF, 2) & 0xFFFF
    record = _record_address(tracked)
    status = read((record + 4) & 0xFFFFFF, 2) & 0xFFFF
    if status not in WITNESSED_STATUS:
        return {'arm': 'blocked', 'tracked': tracked, 'record': record, 'status': status, 'match': None}
    match = match_tracked_id(read, tracked)
    return {'arm': 'match' if match is not None else 'no-match', 'tracked': tracked, 'record': record,
            'status': status, 'match': match}


# --- 00475E: the slot scan (a caller-supplied record's own gate, up to three independent calls) ---
#
# Gates on bit 7 of the record's own $10 byte; when set, checks three independent flag words in
# program order ((a1), $4(a1), $8(a1), each tested against 1) and, for whichever is 1, calls
# achievement_slot_dispatch with a pointer two bytes past the flag (the tracked id) -- the
# 0049DA-calls-001164 shape, up to three times in one activation.  Every occurrence across all eight
# recordings has at most one flag true; the third (0x08) is real ROM code no recording ever sets, and
# only the first position's call is ever witnessed to match a tracked id (the second, when true, is
# always a plain miss).  A second independent match in the same activation has never been witnessed
# either, and genesis_re.seam cannot express two seams inside one activation's suffix -- the boundary
# declines that combination rather than guess at it.
SLOT_SCAN_CHECKS = ((0x00, 0x02), (0x04, 0x06), (0x08, 0x0A))  # (flag word offset, id-pointer offset), in program order
WITNESSED_SLOT_SCAN_CALLS = (0, 1)      # position 2 (0x08(a1)) is real code no recording ever sets to 1
WITNESSED_SLOT_SCAN_MATCHES = (0,)      # only position 0's call is ever witnessed to match a tracked id


def slot_scan_gate(read, a1):
    """00475E's own gate: bit 7 of the record's $10 byte."""
    return bool(read((a1 + 0x10) & 0xFFFFFF, 1) & 0x80)


def slot_scan_flag(read, a1, position):
    """One of the three independent flag words: True where it equals 1."""
    offset, _ = SLOT_SCAN_CHECKS[position]
    return (read((a1 + offset) & 0xFFFFFF, 2) & 0xFFFF) == 1


# --- 004800: the record id scan (the trigger firing subsystem blocker's own part 2, last caller) --
#
# A second, independent gate over the same caller-supplied record: D5 = ($10(a1)) & 0x7fff must be
# one of {2,3,4,7,8} (real ROM code for {5,6} or anything above 8 skips the whole routine).  When it
# is, checks the SAME three (flag, id) field pairs 00475E's own slot scan does ((a1)/$2(a1),
# $4(a1)/$6(a1), $8(a1)/$A(a1)) but with a different test: the flag word must be 1 AND the id word
# must fall in one of two ranges (0x12-0x17 or 0x7f-0x81, the achievement item ids the collectible
# tracker actually uses).  A witnessed pair calls 0048B4 (disassembled fresh: the SAME four-tracked-id
# compare achievement_slot_dispatch's own tail runs, with no status gate at all, reaching 0047DA
# through a tail JUMP -- bra.w, not bsr -- so 0047DA's own rts returns directly to whichever of
# 004800's own three call sites made the jump, needing no 004790-style resume-and-continue layer of
# its own).  Every witnessed call (from either the first or second position) is a match; the third
# position, and a miss from either witnessed one, are both real ROM code no recording enters.
RECORD_ID_SCAN_GATE_WITNESSED = (2, 3, 4, 7, 8)
ID_TAIL_RANGES = ((0x12, 0x17), (0x7F, 0x81))
WITNESSED_RECORD_ID_SCAN_CALLS = (0, 1)   # position 2 ($8(a1)/$A(a1)) is real code no recording ever satisfies


def record_id_scan_gate(d5):
    """004800's own gate: d5 (masked to 15 bits) must be 2, 3, 4, 7 or 8."""
    return d5 in RECORD_ID_SCAN_GATE_WITNESSED


def id_in_range(value):
    """One of 0048B4's own two id ranges (0x12-0x17, 0x7f-0x81)."""
    return any(lo <= value <= hi for lo, hi in ID_TAIL_RANGES)


def record_id_scan_check(read, a1, position):
    """One of the three independent (flag, id) pairs: True and the id word where both the flag equals
    1 and the id falls in one of 0048B4's own two ranges; False, None otherwise.  Uses the same field
    layout as ``SLOT_SCAN_CHECKS`` (00475E's own routine, over the same record)."""
    flag_offset, id_offset = SLOT_SCAN_CHECKS[position]
    if (read((a1 + flag_offset) & 0xFFFFFF, 2) & 0xFFFF) != 1:
        return False, None
    value = read((a1 + id_offset) & 0xFFFFFF, 2) & 0xFFFF
    return id_in_range(value), value


# --- 005CEE: the achievement highlight cycle (states 19/18's own shared body,
# ``game.player.state1918_dispatch``'s own ``'highlight'`` arm) -----------------------------------
#
# Called by bsr from three sites across states 19 and 18 (0058C6/00588E, 005878); its own D7 is the
# only register it saves/restores, so from the caller's own composition it is one opaque ceded block
# (a seam over a seam, ``achievement_slot_dispatch``'s own shape over ``0047DA``).  Reads
# ACHIEVEMENT_SLOTS[HIGHLIGHT_ID]: negative (empty) skips straight to the "refresh" tail below;
# otherwise the floating icon spawn (``game.spawns.floating_icon_spawn``) is called with the tracked
# position (GRID_X + 8, GRID_Y + 0x20) and the stored value + HIGHLIGHT_KIND_BIAS, and the slot is
# marked consumed (-1) either way BEFORE the spawn call.  Both arms converge on the SAME refresh: the
# CURRENT HIGHLIGHT_ID's own icon slot re-uploaded highlighted (001648, d1=1) with whatever
# ACHIEVEMENT_SLOTS now holds there as D2 (-1 on every witnessed call: HIGHLIGHT_ID's own slot was
# never the one just consumed in any of the 191 witnessed activations, states 19 and 18 together).
HIGHLIGHT_KIND_BIAS = 0xB              # 005D00: addi.w #$b,d2 -- the floating-icon spawn's own kind bias
HIGHLIGHT_REFRESH_ICON_D2 = 0xFFFFFFFF  # moveq #$ff,d2 -- sign-extends to the full register (the refresh call's own fixed "clear" pattern)


def achievement_highlight_cycle(read):
    """005CEE: the slot at ACHIEVEMENT_SLOTS[HIGHLIGHT_ID], empty or not, then a fixed refresh call.
    Returns ``'refresh'`` (the slot was already empty) or ``'spawn'`` (the slot held a value: the
    caller composes ``game.spawns.floating_icon_spawn`` with ``kind`` and marks the slot consumed);
    either way the caller uploads HIGHLIGHT_ID's own icon slot with D1=1, D2=HIGHLIGHT_REFRESH_ICON_D2.
    """
    slot = read(HIGHLIGHT_ID, 2) & 0xFFFF
    doubled = (slot * 2) & 0xFFFF
    address = (ACHIEVEMENT_SLOTS + doubled) & 0xFFFFFF
    stored = read(address, 2)
    if _signed_word(stored) < 0:
        return {'arm': 'refresh', 'highlight_id': slot, 'icon_d0': slot, 'stores': {}}
    kind = (stored + HIGHLIGHT_KIND_BIAS) & 0xFFFF
    return {'arm': 'spawn', 'highlight_id': slot, 'icon_d0': slot, 'kind': kind,
            'stores': {address: (0xFFFF, 2)}}
