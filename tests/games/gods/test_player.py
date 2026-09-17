"""The player state machine (005700): discovery this session, not yet a recovery candidate.

Every witnessed activation of 005700 falls through to the shared tail
(0075D6), which itself reaches a second, distinct, not-yet-recovered
sprite-emitter-shaped routine (001312) and, on a 'trigger' tile, deeply
unrecovered creature/spawn code -- see
``docs/gods/blockers/2026-09-17-005700.md``.  There is no boundary plan and
no recovery candidate here yet.  What is tested: ``game.player``'s own
``tile_trigger_scan`` (00773A, the tail's first call) against synthetic
reads, and, on every fixture the 00773A-only census retained, that its
'clean'/'trigger' classification agrees with what the ORIGINAL machine's
own tracer recorded (a call into 0077A8, or none) -- the strict-witness
tier of the confidence hierarchy for this one call, standing in for the
``factcheck check`` a real candidate would run.
"""
import json
from pathlib import Path

import pytest
import pathfacts

from genesis_re.machine import Machine
from gods_sega.game import player
from gods_sega.profile import GODS

EVENT_DISPATCH_ENTRY = 0x0077A8   # every trigger reaches this instruction, by bsr (a middle cell) or bra (the last)

FIXTURES = sorted(Path('artifacts/gods/evidence').glob('census-00773A-fb408bc75597/00773A-entry-*.state'))
needs_census = pytest.mark.skipif(not FIXTURES or not GODS.rom_path.is_file(), reason='no local census of 00773A')


def _reader(values):
    return lambda address, size: values[(address, size)]


def test_a_clean_scan_checks_three_cells_and_declines_nothing():
    base = player._tile_cell(0x300, 0x0000) & 0xFFFFFF
    reads = {(base, 1): 0, (base + player.TILE_ROW_BYTES, 1): 2, (base + 2 * player.TILE_ROW_BYTES, 1): 1}
    result = player.tile_trigger_scan(_reader(reads), x=0x300, y=0x0000)
    assert result['arm'] == 'clean' and result['trigger_index'] is None
    assert len(result['cells']) == 3 and result['widen'] is False


def test_low_x_bits_at_or_above_0x10_widen_to_a_second_column():
    always_clean = lambda address, size: 0
    result = player.tile_trigger_scan(always_clean, x=0x30, y=0)
    assert result['widen'] is True and len(result['cells']) == 6
    result = player.tile_trigger_scan(always_clean, x=0x00, y=0)
    assert result['widen'] is False and len(result['cells']) == 3


def test_a_byte_over_the_threshold_triggers_at_its_own_index():
    reads = {(0xFF885E, 1): 0, (0xFF885E + 0x80, 1): 3, (0xFF885E + 0x100, 1): 0}
    result = player.tile_trigger_scan(_reader(reads), x=0x00, y=0)
    assert result['arm'] == 'trigger' and result['trigger_index'] == 1


def test_the_threshold_itself_does_not_trigger():
    reads = {(0xFF885E, 1): player.TILE_THRESHOLD, (0xFF885E + 0x80, 1): 0, (0xFF885E + 0x100, 1): 0}
    result = player.tile_trigger_scan(_reader(reads), x=0x00, y=0)
    assert result['arm'] == 'clean'


@needs_census
@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: p.stem)
def test_the_semantics_agree_with_the_original_on_every_retained_occurrence(fixture):
    meta = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
    if meta.get('cut'):
        pytest.skip('deadline-cut occurrence, classified offline')
    state = fixture.read_bytes()
    with Machine(GODS.read_rom()) as machine:
        machine.restore(state)
        read = lambda address, size: int.from_bytes(machine.peek_ram(address & 0xFFFF, size), 'big')
        x = read(player.POSITION_X, 2)
        y = read(player.POSITION_Y, 2)
        result = player.tile_trigger_scan(read, x, y)
    # A failing check reaches 0077A8 by bsr at every position but the scan's own last one, which
    # instead tail-branches there (bra.b, 0077A4) since nothing follows -- a plain branch the shared
    # tracer's depth-0 'calls' summary never records, so the retained signature's own call list is not
    # a reliable witness here.  Whether 0077A8's own entry instruction was executed at all, over the
    # full per-step trace, is: every trigger reaches it, no clean scan ever does.
    facts = pathfacts.trace(state, game=GODS)
    witnessed_trigger = any(step['pc'] == EVENT_DISPATCH_ENTRY for step in facts['steps'])
    assert (result['arm'] == 'trigger') == witnessed_trigger, (fixture, result, meta['signature'])
