"""The achievement/collectible-slot tracker's own reset call (``0047DA``).

Reached from ``004790`` (the slot dispatch, one call per matching tracked id)
and from ``0048B4`` inside ``004800``/``00475E``'s own bounded record scans
(the trigger firing subsystem blocker's second structure,
``docs/gods/blockers/2026-09-16-00462C-firing.md``): four consecutive
tracked-id slots at ``FFFFF22E`` are marked empty (``-1``) by index, and the
routine always calls into the collected-item icon upload (``001648``) to
clear the matching VRAM icon slot -- with ``D2`` fixed at ``-1`` on every
witnessed call, the icon upload's own "clear" arm, never its real
tile-descriptor upload (a positive ``D2``, unreached from this caller: the
routine's own code sets ``D2`` unconditionally before the call, so no
recording needs to witness the other value for this fact to hold).

Pure function of ``read(address, size)``; no cycles, CCR, stack or
registers -- the whole routine is scratch (its own ``d1``/``d2``/``a0``
frame restores their entry values unchanged at the RTS).
"""
from __future__ import annotations

ACHIEVEMENT_SLOTS = 0xFFFFF22E    # four consecutive words, one per tracked id (FFEF8C/F01E/F0B0's own ids); -1 = empty
HIGHLIGHT_ID = 0xFFFFF236         # word: D0 matching this selects 001648's own DDDDDDDD fill instead of FFFFFFFF
WITNESSED_ICON_SLOTS = (0, 1, 3)  # D0: which of 001648's four VRAM icon slots (its own table at 0016C2); 2 unwitnessed


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


def achievement_slot_dispatch(read, a2):
    """004790: the slot dispatch over a caller-supplied record pointer."""
    tracked = read(a2 & 0xFFFFFF, 2) & 0xFFFF
    record = _record_address(tracked)
    status = read((record + 4) & 0xFFFFFF, 2) & 0xFFFF
    if status not in WITNESSED_STATUS:
        return {'arm': 'blocked', 'tracked': tracked, 'record': record, 'status': status, 'match': None}
    match = next((slot for slot, address in enumerate(TRACKED_IDS) if tracked == (read(address, 2) & 0xFFFF)), None)
    return {'arm': 'match' if match is not None else 'no-match', 'tracked': tracked, 'record': record,
            'status': status, 'match': match}
