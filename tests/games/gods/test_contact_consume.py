"""The movement-cluster contact consumers (012DA0, 012E5A): once contact_search has populated up
to three CONTACT_SLOTS, these two near-identical siblings consume them -- re-reading the SAME
list's own count word, looking up the item record it names and its own type field (0x14 for
012DA0, 0x10 for 012E5A), then dispatching through a second ROM table (012C3E) into a per-type
handler.  Every witnessed type reduces to a small header (a position delta) plus one of two
bounded-append bodies (contact_consume's own module docstring, game/pickups.py); type 9 (012DA0
only) is a standalone single write.  Three tiers as for the other leaves; the evidence tiers skip
when the local census or reference artifacts are absent.
"""
import json
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import pickups
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
PRIMARY_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-012DA0-entry*/012DA0-entry-p*.state'))
SECONDARY_FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-012E5A-entry*/012E5A-entry-p*.state'))
needs_primary_census = pytest.mark.skipif(not PRIMARY_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 012DA0')
needs_secondary_census = pytest.mark.skipif(not SECONDARY_FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 012E5A')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def _world(overrides=None):
    values = {(pickups.CONTACT_ACTIVE_SELECTOR & 0xFFFFFF, 2): 0xFFFF}   # never the witnessed slot indices (0/1/2)
    for slot in pickups.CONTACT_SLOTS:
        values[(slot & 0xFFFFFF, 4)] = 0
    values.update(overrides or {})
    return values


ENTRY_BASE = {0: 0xFFFFEF8E, 1: 0xFFFFF020, 2: 0xFFFFF0B2}   # CONTACT_SLOTS' own targets in this test world


def _populate(values, slot_index, list_table, count, record, index_value=1):
    slot_addr = pickups.CONTACT_SLOTS[slot_index]
    entry_addr = ENTRY_BASE[slot_index]
    values[(slot_addr & 0xFFFFFF, 4)] = entry_addr
    values[(pickups.CONTACT_INDEX_WORDS[slot_index] & 0xFFFFFF, 2)] = index_value
    values[(list_table & 0xFFFFFF, 2)] = count
    values[((pickups.ITEM_RECORDS + count * 4) & 0xFFFFFF, 4)] = record
    return entry_addr


def test_an_empty_slot_touches_nothing_and_the_next_slot_is_checked():
    result = pickups.contact_consume(_reader(_world()), 0)
    assert [s['arm'] for s in result['slots']] == ['empty', 'empty', 'empty']
    assert all(not s['stores'] for s in result['slots'])


def test_type_one_appends_up_to_three_groups_with_the_012da0_own_constants():
    values = _world()
    record = 0xFFFFF700
    values[(record + pickups.ITEM_TYPE_PRIMARY) & 0xFFFFFF, 4] = 1
    values[(record + pickups.ITEM_VALUE) & 0xFFFFFF, 2] = 5
    values[(record + pickups.ITEM_RANGE_LOW) & 0xFFFFFF, 2] = 3   # count = 5-3+1 = 3: all three groups
    entry = _populate(values, 0, pickups.GROUP_TABLES[0], 2, record, index_value=1)
    result = pickups.contact_consume(_reader(values), 0)
    slot0 = result['slots'][0]
    assert slot0['arm'] == 'found' and slot0['type'] == 1
    assert [g['const'] for g in slot0['groups']] == [1, 0, 2]
    assert [g['d4'] for g in slot0['groups']] == [1, 2, 3]
    assert slot0['stores'][(record + pickups.ITEM_CLAIM_FLAG) & 0xFFFFFF] == (1, 2)
    assert slot0['stores'][pickups.MOVEMENT_SOUND_CUE & 0xFFFFFF] == (pickups.CONTACT_BODY_CUE, 2)
    # entry(a3)+0 holds the first group's own d4 (the index word, 1) -- matches CONTACT_INDEX_WORDS.
    assert slot0['stores'][entry & 0xFFFFFF] == (1, 2)


def test_type_three_is_pooled_and_writes_the_sentinel_table_too():
    values = _world()
    record = 0xFFFFF700
    values[(record + pickups.ITEM_TYPE_PRIMARY) & 0xFFFFFF, 4] = 3
    values[(record + pickups.ITEM_VALUE) & 0xFFFFFF, 2] = 0
    values[(record + pickups.ITEM_RANGE_LOW) & 0xFFFFFF, 2] = 0   # count = 1: one group only
    values[(pickups.CONTACT_POOL_INDEX_BASE & 0xFFFFFF, 2)] = 0
    _populate(values, 2, pickups.GROUP_TABLES[2], 4, record, index_value=0x13)
    result = pickups.contact_consume(_reader(values), 0)
    slot2 = result['slots'][2]
    assert slot2['arm'] == 'found' and slot2['type'] == 3 and slot2['pooled']
    assert len(slot2['groups']) == 1
    pool_addr = slot2['groups'][0]['pool_addr']
    assert slot2['stores'][pool_addr] == (0xFFFA, 2)


def test_type_nine_is_a_standalone_single_write_with_its_own_state_block():
    values = _world()
    record = 0xFFFFF700
    values[(record + pickups.ITEM_TYPE_PRIMARY) & 0xFFFFFF, 4] = 9
    entry = _populate(values, 1, pickups.GROUP_TABLES[1], 1, record, index_value=4)
    result = pickups.contact_consume(_reader(values), 0)
    slot1 = result['slots'][1]
    assert slot1['arm'] == 'found' and slot1['type'] == 9
    assert slot1['stores'][pickups.TYPE9_FLAG & 0xFFFFFF] == (0, 2)
    assert slot1['stores'][pickups.TYPE9_COUNT & 0xFFFFFF] == (4, 2)
    assert slot1['stores'][pickups.TYPE9_CURSOR & 0xFFFFFF] == (0xFFFF, 2)
    assert slot1['stores'][pickups.MOVEMENT_SOUND_CUE & 0xFFFFFF] == (pickups.TYPE9_CUE, 2)
    assert slot1['stores'][(entry + 6) & 0xFFFFFF] == (0x2F, 2)


def test_an_unrecovered_type_stops_the_scan_without_claiming_a_later_slot():
    values = _world()
    record = 0xFFFFF700
    values[(record + pickups.ITEM_TYPE_PRIMARY) & 0xFFFFFF, 4] = 42   # not in TYPE_HEADERS, not 9
    _populate(values, 0, pickups.GROUP_TABLES[0], 0, record)
    # slot 2 (list3) is also populated, but must never be reached: the ROM itself never returns
    # from an unrecognised type's own (unknown) handler.
    record2 = 0xFFFFF800
    values[(record2 + pickups.ITEM_TYPE_PRIMARY) & 0xFFFFFF, 4] = 3
    values[(record2 + pickups.ITEM_VALUE) & 0xFFFFFF, 2] = 0
    values[(record2 + pickups.ITEM_RANGE_LOW) & 0xFFFFFF, 2] = 0
    _populate(values, 2, pickups.GROUP_TABLES[2], 1, record2)
    result = pickups.contact_consume(_reader(values), 0)
    assert len(result['slots']) == 1 and result['slots'][0]['arm'] == 'unrecovered'


def test_012e5a_type_six_shares_type_zeros_own_body_with_its_own_header():
    values = _world()
    record = 0xFFFFF700
    values[(record + pickups.ITEM_TYPE_SECONDARY) & 0xFFFFFF, 4] = 6
    values[(record + pickups.ITEM_VALUE) & 0xFFFFFF, 2] = 0
    values[(record + pickups.ITEM_RANGE_LOW) & 0xFFFFFF, 2] = 0
    _populate(values, 0, pickups.GROUP_TABLES[0], 0, record)
    result = pickups.contact_consume(_reader(values), 1)
    slot0 = result['slots'][0]
    assert slot0['arm'] == 'found' and slot0['type'] == 6 and not slot0['pooled']
    assert [g['const'] for g in slot0['groups']] == [4]
    assert slot0['stores'][(record + pickups.ITEM_CLAIM_FLAG) & 0xFFFFFF] == (0xFFFF, 2)


@needs_primary_census
@pytest.mark.parametrize('fixture', PRIMARY_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_contact_consume_primary_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_type(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        try:
            plan = boundary.contact_consume_primary_plan(machine, machine.registers())
        except boundary.UnsupportedCandidate:
            pytest.fail('unexpected decline: every retained 012DA0 fixture reaches a witnessed type')
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@needs_secondary_census
@pytest.mark.parametrize('fixture', SECONDARY_FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_contact_consume_secondary_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_type(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        try:
            plan = boundary.contact_consume_secondary_plan(machine, machine.registers())
        except boundary.UnsupportedCandidate:
            pytest.fail('unexpected decline: every retained 012E5A fixture reaches a witnessed type')
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_names_are_explicit():
    assert recovery.Candidate('contact-consume-primary').gate_pcs == (boundary.CONTACT_CONSUME_PRIMARY_ENTRY,)
    assert recovery.Candidate('contact-consume-secondary').gate_pcs == (boundary.CONTACT_CONSUME_SECONDARY_ENTRY,)
    for entry in (boundary.CONTACT_CONSUME_PRIMARY_ENTRY, boundary.CONTACT_CONSUME_SECONDARY_ENTRY):
        assert entry in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('contact-consume-primary-mutant-result').mutation is recovery._mutate_result
    assert recovery.Candidate('contact-consume-secondary-mutant-result').mutation is recovery._mutate_result


@needs_reference
def test_contact_consume_primary_candidate_matches_the_reference():
    # The mutant's own negative control is NOT checked at this (120-frame segment) tier: every
    # consumer of a hit record's own status groups is itself still unrecovered ROM (the per-type
    # handlers' own continuation, 012DA0/012E5A's own still-unrecovered callers), so a corrupted
    # byte here is not guaranteed to become video/PCM-observable within a short window -- confirmed
    # by the full-history run (artifacts/gods/verify-contact-consume-primary-mutant): DIVERGENCE,
    # but at frame 11,306, not the region's own first activation (2,625) -- real, not blind, just
    # delayed behind code this session does not model. See ledger.md.
    for fixture in PRIMARY_FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='contact-consume-primary', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches a witnessed arm within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS


@needs_reference
def test_contact_consume_secondary_candidate_matches_the_reference():
    # Same reasoning as the primary consumer's own test above: the mutant's own negative control
    # is checked at the full-history tier instead (artifacts/gods/verify-contact-consume-secondary-mutant).
    for fixture in SECONDARY_FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='contact-consume-secondary', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches a witnessed arm within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
