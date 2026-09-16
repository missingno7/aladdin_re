"""Pickups: the award for a collected item (``013264``).

The level keeps a byte grid at ``FFBBDE`` (8x8-pixel cells, 48 bytes per
row) whose non-zero bytes are pickup codes; the player's box is scanned
against it every tick by the pickup check ``00BA8E``, and a hit calls
``013264`` with A0 just past the found byte.  A positive code names one of
27 item slots in three groups of nine (the groups' tables at ``FFEF8C``,
``FFF01E``, ``FFF0B0``: an active-id word, then nine 8-byte slots); the
active id selects the group's item record through the ROM table at
``012D04`` (eleven work-RAM records of 0x50 bytes at ``FFF552``), whose
word at ``+8`` is the item's value.  The value goes to ``FFF35A`` (plus a
time bonus, an eighth of ``FFF362 - FFF36C`` when positive), a cue is
requested when sound is on (``FFEF14``), and the slot is consumed when the
record's byte at ``+0x49`` says so.  Negative codes are the special
pickups: -1 takes the value from ``FFF158`` and reports 1 in D4, -2 is
worth 10,000 (nothing when sound is on), -3 is worth nothing; -4 and below
continue into the routine that follows and are not recovered.

Pure functions of ``read(address, size)``; no cycles, CCR, stack or
registers.  The names are what the arithmetic supports, not more.
"""
from __future__ import annotations

PICKUP_GRID = 0xFFFFBBDE                              # bytes, 8x8-pixel cells, 48 per row (00BA8E's scan, 013316's inverse)
GROUP_TABLES = (0xFFFFEF8C, 0xFFFFF01E, 0xFFFFF0B0)   # per group: the active id word, then nine 8-byte slots
GROUP_SIZE, SLOT_SIZE, SLOT_BASE = 9, 8, 2
ITEM_RECORDS = 0x012D04                               # ROM: eleven longs, the work-RAM record of each item id
ITEM_RECORD_COUNT = 11
ITEM_VALUE, ITEM_CONSUMES_SLOT = 0x8, 0x49            # record fields: the value word, the consume flag byte
AWARD = 0xFFF35A                                      # word: the value awarded by the last pickup
TIME_NOW, TIME_MARK = 0xFFF362, 0xFFF36C              # words: the bonus is an eighth of their difference when positive
SOUND_ON, SOUND_CUE = 0xFFEF14, 0xFFFDF4              # the cue word of the sound command block
PICKUP_CUE = 0x38
SPECIAL_VALUE = 0xFFF158                              # the -1 pickup's value
BIG_VALUE = 0x2710


def _signed_byte(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def _signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def collect(read, after_code):
    """What ``013264`` does with A0 just past the pickup code byte.

    Returns the arm (``'item'``, ``'special-1'``, ``'special-2'``,
    ``'special-3'``, ``'unrecovered'`` for codes of -4 and below), the
    code, the stores as ``{address: (value, size)}``, D4's result, and for
    an item: the group table, the slot index (0-based), the active id, the
    record, the time difference and whether the bonus arm ran, whether the
    cue was requested and whether the slot was consumed.
    """
    code = _signed_byte(read((after_code - 1) & 0xFFFFFF, 1))
    result = {'code': code, 'stores': {}, 'd4': 0, 'group': None, 'slot': None, 'record': None,
              'time_difference': None, 'bonus': False, 'cue': False, 'consumed': False}
    stores = result['stores']
    if code >= 0:
        group = 0 if code <= GROUP_SIZE else (1 if code - GROUP_SIZE <= GROUP_SIZE else 2)
        in_group = code - GROUP_SIZE * group
        table = GROUP_TABLES[group]
        slot = in_group - 1                              # code 0 gives slot -1: the word before the slots
        active = read(table & 0xFFFFFF, 2)
        record = read(ITEM_RECORDS + _signed_word(4 * active), 4) & 0xFFFFFFFF   # (a1,d4.w): a signed index
        value = read((record + ITEM_VALUE) & 0xFFFFFF, 2)
        difference = _signed_word(read(TIME_NOW, 2) - read(TIME_MARK, 2))
        if difference > 0:
            value = (value + (difference >> 3)) & 0xFFFF
        stores[AWARD] = (value, 2)
        if read(SOUND_ON, 2):
            stores[SOUND_CUE] = (PICKUP_CUE, 2)
            result['cue'] = True
        if read((record + ITEM_CONSUMES_SLOT) & 0xFFFFFF, 1):
            stores[(table + SLOT_BASE + SLOT_SIZE * slot) & 0xFFFFFF] = (0, 2)
            result['consumed'] = True
        result.update(arm='item', group=group, slot=slot, active=active, record=record,
                      time_difference=difference, bonus=difference > 0, table=table)
        return result
    if code == -1:
        stores[AWARD] = (read(SPECIAL_VALUE, 2), 2)
        return {**result, 'arm': 'special-1', 'd4': 1}
    if code == -2:
        stores[AWARD] = (0, 2) if read(SOUND_ON, 2) else (BIG_VALUE, 2)
        return {**result, 'arm': 'special-2'}
    if code == -3:
        stores[AWARD] = (0, 2)
        return {**result, 'arm': 'special-3'}
    return {**result, 'arm': 'unrecovered'}
