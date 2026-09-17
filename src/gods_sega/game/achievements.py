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
