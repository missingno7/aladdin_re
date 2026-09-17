"""The movement-cluster contact search (008222, with its helper 00837E): a reentrancy-guarded,
three-sub-pass hit-list search over the same collectible lists ``pickups.GROUP_TABLES`` names,
read here as up to three consecutive 0x18-byte "hit records" per list (docs/gods/blockers/
2026-09-17-008222.md, Decision).  Structurally parallel to ``hazard.proximity_search`` (a bounded
list scan with retries) but with three independent sub-passes, a retry budget read from the item
record itself, and a latch that lets sub-pass 1 suppress a duplicate special match in sub-passes
2/3.  Three tiers as for the other leaves; the evidence tiers skip when the local census or
reference artifacts are absent.
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
FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-008222-entry*/008222-entry-p*.state'))
REFERENCE_FIXTURES = sorted(Path('artifacts/gods/evidence/census-008222-entry').glob('008222-entry-p*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 008222')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not REFERENCE_FIXTURES
                                     or not GODS.history_path().is_dir(), reason='no local Gods reference evidence')


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def _world(overrides=None):
    # Every list's own count word negative (both other lists skip outright) is the baseline; a test
    # overrides just the one list (and its item record) it wants to exercise.
    values = {(pickups.REENTRANCY_GUARD & 0xFFFFFF, 2): 0}
    for table in pickups.GROUP_TABLES:
        values[(table & 0xFFFFFF, 2)] = 0xFFFF   # -1: skip
    values.update(overrides or {})
    return values


def _entry(list_table, index):
    return (list_table + pickups.CONTACT_ENTRY_BASE_OFFSET + pickups.CONTACT_ENTRY_STRIDE * index) & 0xFFFFFFFF


def _free_entry(address, values):
    for offset in pickups.CONTACT_STATUS_OFFSETS:
        values[((address + offset) & 0xFFFFFF, 2)] = 0


def _occupied_entry(address, values, offset=0):
    for stop in pickups.CONTACT_STATUS_OFFSETS:
        values[((address + stop) & 0xFFFFFF, 2)] = 1 if stop == offset else 0


def test_the_guard_declines_a_reentrant_call_and_touches_nothing():
    result = pickups.contact_search(_reader({(pickups.REENTRANCY_GUARD & 0xFFFFFF, 2): 1}))
    assert result == {'arm': 'busy', 'd0': 1, 'stores': {}, 'subpasses': None}


def test_every_list_skipped_finds_nothing_and_still_clears_every_slot():
    result = pickups.contact_search(_reader(_world()))
    assert result['arm'] == 'ran' and result['d0'] == 1 and not result['found']
    assert [sp['arm'] for sp in result['subpasses']] == ['skip', 'skip', 'skip']
    for slot in pickups.CONTACT_SLOTS:
        assert result['stores'][slot & 0xFFFFFF] == (0, 4)
    assert result['stores'][pickups.REENTRANCY_GUARD & 0xFFFFFF] == (1, 2)
    assert result['stores'][pickups.CONTACT_LATCH & 0xFFFFFF] == (0, 2)


def test_sub_pass_one_finds_its_first_entry_directly_off_the_flat_item_table():
    count = 2
    record = (pickups.CONTACT_ITEM_RECORDS_BASE + count * pickups.CONTACT_ITEM_RECORD_STRIDE) & 0xFFFFFFFF
    values = _world()
    values[(pickups.GROUP_TABLES[0] & 0xFFFFFF, 2)] = count
    values[((record + pickups.CONTACT_WORD_OFFSET) & 0xFFFFFF, 2)] = 5   # != 1: no latch
    entry = _entry(pickups.GROUP_TABLES[0], 0)
    _free_entry(entry, values)
    result = pickups.contact_search(_reader(values))
    sp0 = result['subpasses'][0]
    assert sp0['arm'] == 'found' and not sp0['sets_latch']
    assert result['d0'] == 0 and result['found']
    assert result['stores'][pickups.CONTACT_SLOTS[0] & 0xFFFFFF] == (entry, 4)
    assert result['stores'][pickups.CONTACT_INDEX_WORDS[0] & 0xFFFFFF] == (1, 2)
    assert (pickups.CONTACT_LATCH & 0xFFFFFF) not in {a for a, (v, s) in sp0['stores'].items()}


def test_sub_pass_one_retries_up_to_three_entries_before_giving_up():
    count = 0
    values = _world()
    values[(pickups.GROUP_TABLES[0] & 0xFFFFFF, 2)] = count
    record = pickups.CONTACT_ITEM_RECORDS_BASE
    values[((record + pickups.CONTACT_WORD_OFFSET) & 0xFFFFFF, 2)] = 5   # budget of 5: never hits zero in 3 tries
    for index in range(3):
        _occupied_entry(_entry(pickups.GROUP_TABLES[0], index), values, offset=0)
    result = pickups.contact_search(_reader(values))
    sp0 = result['subpasses'][0]
    assert sp0['arm'] == 'not-found' and len(sp0['attempts']) == 3
    assert [step['index'] for step in sp0['attempts']] == [1, 4, 7]
    assert result['stores'][pickups.CONTACT_SLOTS[0] & 0xFFFFFF] == (0, 4)


def test_sub_pass_one_abandons_early_once_the_contact_word_budget_reaches_zero():
    values = _world()
    values[(pickups.GROUP_TABLES[0] & 0xFFFFFF, 2)] = 0
    values[((pickups.CONTACT_ITEM_RECORDS_BASE + pickups.CONTACT_WORD_OFFSET) & 0xFFFFFF, 2)] = 1
    _occupied_entry(_entry(pickups.GROUP_TABLES[0], 0), values, offset=0)
    result = pickups.contact_search(_reader(values))
    sp0 = result['subpasses'][0]
    assert sp0['arm'] == 'not-found' and len(sp0['attempts']) == 1
    assert sp0['attempts'][0]['budget_after'] == 0


def test_sub_pass_one_sets_the_latch_when_the_contact_word_is_exactly_one():
    values = _world()
    values[(pickups.GROUP_TABLES[0] & 0xFFFFFF, 2)] = 0
    values[((pickups.CONTACT_ITEM_RECORDS_BASE + pickups.CONTACT_WORD_OFFSET) & 0xFFFFFF, 2)] = 1
    _free_entry(_entry(pickups.GROUP_TABLES[0], 0), values)
    result = pickups.contact_search(_reader(values))
    sp0 = result['subpasses'][0]
    assert sp0['arm'] == 'found' and sp0['sets_latch']
    assert result['stores'][pickups.CONTACT_LATCH & 0xFFFFFF] == (1, 2)


def test_sub_pass_two_goes_through_the_pointer_table_and_declines_a_negative_contact_word():
    count = 3
    pointer = 0xFFFFF700
    values = _world()
    values[(pickups.GROUP_TABLES[1] & 0xFFFFFF, 2)] = count
    values[((pickups.ITEM_RECORDS + count * 4) & 0xFFFFFF, 4)] = pointer
    values[((pointer + pickups.CONTACT_WORD_OFFSET) & 0xFFFFFF, 2)] = 0xFFFF   # negative: skip-negative
    result = pickups.contact_search(_reader(values))
    sp1 = result['subpasses'][1]
    assert sp1['arm'] == 'skip-negative' and sp1['attempts'] == []
    assert sp1['a2_exit'] == pointer


def test_a_sub_pass_two_or_three_match_is_discarded_when_the_latch_is_already_set_and_its_own_contact_word_is_one():
    # Sub-pass 1 sets the latch (contact word 1, found on the first try); sub-pass 3's own match,
    # also contact word 1, must then be GATED -- no store, and its own contribution to D0 is as if
    # it had found nothing, even though 00837E's own probe returned 'free'.
    values = _world()
    values[(pickups.GROUP_TABLES[0] & 0xFFFFFF, 2)] = 0
    values[((pickups.CONTACT_ITEM_RECORDS_BASE + pickups.CONTACT_WORD_OFFSET) & 0xFFFFFF, 2)] = 1
    _free_entry(_entry(pickups.GROUP_TABLES[0], 0), values)

    count = 4
    pointer = 0xFFFFF700
    values[(pickups.GROUP_TABLES[2] & 0xFFFFFF, 2)] = count
    values[((pickups.ITEM_RECORDS + count * 4) & 0xFFFFFF, 4)] = pointer
    values[((pointer + pickups.CONTACT_WORD_OFFSET) & 0xFFFFFF, 2)] = 1
    _free_entry(_entry(pickups.GROUP_TABLES[2], 0), values)

    result = pickups.contact_search(_reader(values))
    sp0, sp2 = result['subpasses'][0], result['subpasses'][2]
    assert sp0['arm'] == 'found' and sp0['sets_latch']
    assert sp2['arm'] == 'gated' and not sp2['stored']
    assert result['stores'][pickups.CONTACT_SLOTS[2] & 0xFFFFFF] == (0, 4)
    # D0 is still 0 (found) thanks to sub-pass 1 alone.
    assert result['d0'] == 0


@needs_census
def test_contact_search_plan_declines_a_poked_item_contact_word_of_one():
    candidates = [f for f in Path('artifacts/gods/evidence/census-008222-entry').glob('008222-entry-p2.state')]
    if not candidates:
        pytest.skip('no local census-008222-entry/008222-entry-p2.state fixture')
    state = candidates[0].read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        pc = machine.info['pc']
        machine.gates([pc])
        assert machine.run(instructions=1) == 'gate'
        # Sub-pass 1's own record here (count 0) has ITEM_CONTACT_WORD 3 (FFFFF552+0xA); poke it to
        # 1, the one value this whole ladder has never witnessed on any recording.
        assert machine.atomic(target=machine.info['tick'] + 1_000_000, cycles=1, instructions=1, last_pc=pc,
                              writes=[(0xFFF55C, 0x00), (0xFFF55D, 0x01)], registers=machine.registers())
        with pytest.raises(boundary.UnsupportedCandidate, match='latch'):
            boundary.contact_search_plan(machine, machine.registers())


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_contact_search_plan_reproduces_every_fact_of_the_original_or_declines_an_unwitnessed_arm(fixture):
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        try:
            plan = boundary.contact_search_plan(machine, registers)
        except boundary.UnsupportedCandidate:
            # Every one of the 271 retained fixtures across all eight recordings has
            # ITEM_CONTACT_WORD != 1 and no sub-pass 2/3 with a negative one (see the module
            # docstring); a decline here would mean a NEW arm slipped into the census.
            pytest.fail('unexpected decline: no retained fixture is known to exercise the latch '
                       'or a negative ITEM_CONTACT_WORD')
            return
    facts = pathfacts.region_only(pathfacts.trace(state, game=GODS))
    problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
    assert problems == [], problems
    assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


def test_candidate_names_are_explicit():
    assert recovery.Candidate('contact-search').gate_pcs == (boundary.CONTACT_SEARCH_ENTRY,)
    assert boundary.CONTACT_SEARCH_ENTRY in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate('contact-search-mutant-result').mutation is recovery._mutate_contact_outcome


@needs_reference
def test_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges():
    for fixture in REFERENCE_FIXTURES:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate='contact-search', reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip('no retained fixture reaches a witnessed arm within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate='contact-search-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
