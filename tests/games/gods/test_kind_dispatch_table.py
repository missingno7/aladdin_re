"""The 005958 table's own seven admitted handlers (`docs/gods/blockers/2026-09-19-003480.md`), jsr'd
from 00352C inside 003480's own still-unrecovered body.  The table is a real 23 entries, not the 16
the prior reconnaissance read (entries 16-22 are real, witnessed handlers too, confirmed by this
session's own full-tree trace of every "jsr (a0)" occurrence and by reading the ROM past entry 15
directly).  Fifteen of the twenty-three are witnessed; seven are recovered here: the "phase
accumulator" family (indices 0, 3, 21), the fixed sound-cue pair (index 10) and the ROM-to-RAM copy
family (indices 14, 15, 16).  Standalone candidates only -- kept out of camera-sprites for native
gate capacity until 003480 itself is composed.  Three tiers as for the other leaves; the evidence
tiers skip when the local census or reference artifacts are absent.
"""
from pathlib import Path

import pytest
import pathfacts
import segment_verify

from genesis_re.machine import Machine
from gods_sega import boundary, recovery
from gods_sega.game import world
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
CENSUS_DIR = Path('artifacts/gods/evidence/census-0X5ABE-fb408bc75597')
needs_census = pytest.mark.skipif(not CENSUS_DIR.is_dir() or not GODS.rom_path.is_file(),
                                  reason='no local census of the 005958 table handlers')
needs_reference = pytest.mark.skipif(not (EVIDENCE / 'reference.json').exists() or not GODS.history_path().is_dir(),
                                     reason='no local Gods reference evidence')

# (stem prefix, entry constant, planner, candidate name)
HANDLERS = [
    ('005ABE', 'ACCUMULATOR_0_ENTRY', boundary.accumulator_0_plan, 'kind-accumulator-0'),
    ('005AE8', 'ACCUMULATOR_3_ENTRY', boundary.accumulator_3_plan, 'kind-accumulator-3'),
    ('005B3E', 'ACCUMULATOR_21_ENTRY', boundary.accumulator_21_plan, 'kind-accumulator-21'),
    ('005A48', 'SOUND_CUE_PAIR_ENTRY', boundary.sound_cue_pair_plan, 'kind-sound-cue-pair'),
    ('0142A6', 'COPY_TABLE_14_ENTRY', boundary.copy_table_14_plan, 'kind-copy-table-14'),
    ('014292', 'COPY_TABLE_15_ENTRY', boundary.copy_table_15_plan, 'kind-copy-table-15'),
    ('01429C', 'COPY_TABLE_16_ENTRY', boundary.copy_table_16_plan, 'kind-copy-table-16'),
]


def _reader(values):
    def read(address, size):
        return values.get((address & 0xFFFFFF, size), 0)
    return read


def test_kind_table_count_is_the_signed_zero_byte_scan():
    values = {(world.SOUND_SCAN_TABLE + i, 1): (0 if i in (0, 2, 4) else 1) for i in range(10)}
    assert world.kind_table_count(_reader(values), 5) == 3   # bytes 0-4: zeros at 0, 2, 4
    assert world.kind_table_count(_reader(values), 0) == 0
    assert world.kind_table_count(_reader({}), -5) == 0      # status <= 0: the subq/bmi test skips the loop


def test_accumulator_bypass_below_cap_and_accumulate_arms():
    base = {(world.EF3E_COUNTER & 0xFFFFFF, 2): 0, (world.SPECIAL_TIMER & 0xFFFFFF, 2): 0}
    bypass = {**base, (world.EF3C_BYPASS & 0xFFFFFF, 2): 0xFFFF}
    assert world.accumulator_step(_reader(bypass), 0)['arm'] == 'bypass'
    below = {**base, (world.EF3C_BYPASS & 0xFFFFFF, 2): 0}
    result = world.accumulator_step(_reader(below), 21)   # increment 3, cap 0x18: stays below
    assert result['arm'] == 'below-cap' and result['stores'][world.EF3E_COUNTER & 0xFFFFFF] == (3, 2)
    over = {**base, (world.EF3C_BYPASS & 0xFFFFFF, 2): 0, (world.EF3E_COUNTER & 0xFFFFFF, 2): 0x20}
    accumulate = world.accumulator_step(_reader(over), 0)   # increment 0xC: 0x2c > 0x18
    assert accumulate['arm'] == 'accumulate'
    assert accumulate['stores'][world.EF3E_COUNTER & 0xFFFFFF] == (world.EF3E_CAP, 2)
    assert accumulate['stores'][world.ACCUM_CUE_ADDRESS & 0xFFFFFF] == (world.ACCUM_CUE, 2)
    assert world.SPECIAL_TIMER & 0xFFFFFF in accumulate['stores']


def test_sound_cue_pair_and_copy_table():
    pair = world.sound_cue_pair(_reader({(world.SOUND_CUE_PAIR_COUNTER & 0xFFFFFF, 2): 5}))
    assert pair['stores'][world.SOUND_CUE_PAIR_COUNTER & 0xFFFFFF] == (6, 2)
    values = {(world.COPY_SOURCE[14] + 4 * i, 4): i for i in range(6)}
    copied = world.copy_table(_reader(values), 14)
    assert copied['stores'][(world.COPY_TABLE_DEST + 4 * 3) & 0xFFFFFF] == (3, 4)


@needs_census
@pytest.mark.parametrize('stem,entry_name,planner,_candidate', HANDLERS, ids=lambda v: v if isinstance(v, str) else '')
def test_plan_reproduces_every_witnessed_arm(stem, entry_name, planner, _candidate):
    fixtures = sorted(Path('artifacts/gods/evidence').glob(f'census-0X5ABE-*/{stem}-entry-p*.state'))
    if not fixtures:
        pytest.skip(f'no retained fixture for {stem}')
    entry = getattr(boundary, entry_name)
    for fixture in fixtures:
        state = fixture.read_bytes()
        with Machine(GODS.read_rom()) as machine:
            machine.restore(state)
            registers = machine.registers()
            assert registers['pc'] == entry
            plan = planner(machine, registers)
        facts = pathfacts.trace(state, game=GODS)
        problems = [p for p in pathfacts.check_plan(plan, facts, facts['entry_registers']) if not p.startswith('note:')]
        assert problems == [], (fixture, problems)
        assert facts['exit_pc'] == plan.registers['pc'] and facts['last_pc'] == plan.last_pc


@pytest.mark.parametrize('stem,entry_name,planner,candidate', HANDLERS, ids=lambda v: v if isinstance(v, str) else '')
def test_candidate_name_is_explicit_and_standalone(stem, entry_name, planner, candidate):
    entry = getattr(boundary, entry_name)
    assert recovery.Candidate(candidate).gate_pcs == (entry,)
    # kept OUT of camera-sprites for native gate capacity (state-18/creature-attack's own precedent)
    assert entry not in recovery.Candidate('camera-sprites').gate_pcs
    assert recovery.Candidate(candidate + '-mutant-result').mutation is recovery._mutate_result


@needs_reference
@pytest.mark.parametrize('stem,entry_name,planner,candidate', HANDLERS, ids=lambda v: v if isinstance(v, str) else '')
def test_candidate_matches_the_reference_from_a_retained_fixture_and_its_mutant_diverges(stem, entry_name, planner, candidate):
    fixtures = sorted(Path('artifacts/gods/evidence').glob(f'census-0X5ABE-*/{stem}-entry-p*.state'))
    if not fixtures:
        pytest.skip(f'no retained fixture for {stem}')
    for fixture in fixtures:
        report = segment_verify.check(fixture, game=GODS, frames=120, candidate=candidate, reference=EVIDENCE)
        if report['candidate_hits'] >= 1:
            break
    else:
        pytest.skip(f'no retained fixture reaches {stem} within 120 frames')
    assert report['status'] == 'PASS', report
    assert set(report['fallback_reasons']) <= recovery.ADAPTER_REFUSALS
    mutant = segment_verify.check(fixture, game=GODS, frames=120, candidate=candidate + '-mutant-result',
                                  reference=EVIDENCE)
    assert mutant['status'] == 'DIVERGENCE'
