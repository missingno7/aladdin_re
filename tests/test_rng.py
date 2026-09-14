"""The game's random number generator, recovered as a composable helper."""
import pytest
import factcheck
import pathfacts
from aladdin_sega.game.rng import advance_rng, rng_writes
from aladdin_sega import boundary
from aladdin_sega.machine import Machine
from aladdin_sega.profile import read_rom
from pathlib import Path

FIXTURE = Path('artifacts/evidence/spawn/1B67C2-kind00-p1.state')
pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason='optional local spawn evidence is absent')


def test_advance_rng_matches_the_traced_step():
    # Traced on the original: seed AFB72295 -> EC4CC198, output 2DD4.
    assert advance_rng(0xAFB72295) == (0xEC4CC198, 0x2DD4)
    assert advance_rng(0) == (7, 7)
    assert rng_writes(0xEC4CC198) == [(0xFF7DEA, 0xEC), (0xFF7DEB, 0x4C), (0xFF7DEC, 0xC1), (0xFF7DED, 0x98)]


def test_rng_step_matches_the_original_for_carry_and_no_carry_seeds(capsys):
    code = factcheck.main(['check', str(FIXTURE), 'aladdin_sega.boundary:rng_step', '--park', '1B3032',
                           '--vary', 'FF7DEA.l=0,1,0x7FFFFFFF,0xFFFFFFFF,0xAFB72295,0x13B13B13'])
    out = capsys.readouterr().out
    assert code == 0 and out.count(chr(10) + 'MATCH') == 6 and 'MISMATCH' not in out


def test_rng_step_leaves_the_machine_unchanged_on_an_odd_stack():
    state = pathfacts.park(FIXTURE.read_bytes(), 0x1B3032)
    with Machine(read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        before = machine.snapshot()
        with pytest.raises(boundary.UnsupportedCandidate, match='rng stack'):
            boundary.rng_step(machine, registers)
        assert machine.snapshot() == before
