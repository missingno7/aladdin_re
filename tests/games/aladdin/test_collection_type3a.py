"""Original-byte qualification of 1AF228's shared counter and replace tail.

Kind 0x3A is the only collection-dispatch-table slot that targets 1AF228
directly (kind 0x3B instead targets the already-recovered 'secondary' route
at 0x1AF21E, which reaches 1AF228 only as an internal continuation of its
own already-proven flow -- not a fresh dispatch this leaf owns).

1AF228 gates on FFEFE2 reaching the 0x3939 sentinel (not recovered here:
original continues through 1AE6DE's own table-write arm, exactly the
``game.collection_state('secondary', ...)`` formula ``begin_collection``
already reuses for kind 'secondary' at 0x1AF21E, but that arm is not
observed on the recorded history for kind 0x3A). Short of the cap, 1B0394
advances the same FFEFE2/FFEFE3 ASCII counter with raw ADDQ/CMPI arithmetic
equivalent to ``game.increment_counter``. A pass optionally continues
through a fixed command-0x0D sound seam, then always joins the
already-proven ``replace_object(increment_total=True)`` tail.
"""
import pytest

from aladdin_sega.recovery import Candidate
from aladdin_sega.boundary import COLLECTION_DISPATCH_ENTRY, UnsupportedCandidate
from test_collection import native_write, prepared

KIND = 0x3A


def original_to_return(machine):
    machine.gates([0x1ABD74])
    machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
    assert machine.run(instructions=10_000) == 'gate'
    return machine.snapshot(), machine.info, machine.registers(), machine.audio()


@pytest.mark.parametrize('sound', (0, 1))
@pytest.mark.parametrize('digits', (0x3038, 0x3039), ids=('no-rollover', 'rollover'))
def test_type3a_gate_pass_matches_original_outer_and_audio(sound, digits):
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=sound, digits=digits) as machine:
        native_write(machine, 0xff1000, bytes([KIND]))
        initial = machine.snapshot()
        expected = original_to_return(machine)
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        assert (machine.snapshot(), machine.info, machine.registers(), machine.audio()) == expected
        assert candidate.stats['collection_dispatch_hits'] == 1
        assert candidate.stats['gates'] == 1 + sound


@pytest.mark.parametrize('linked,total', [(False, 0), (True, 0xfff0)])
def test_type3a_gate_pass_owns_pair_release_and_template(linked, total):
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=1, linked=linked, total=total) as machine:
        native_write(machine, 0xff1000, bytes([KIND]))
        initial = machine.snapshot()
        expected = original_to_return(machine)
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        assert (machine.snapshot(), machine.info, machine.registers(), machine.audio()) == expected
        assert candidate.stats['collection_dispatch_hits'] == 1


def test_type3a_capped_counter_declines_to_original():
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=1, digits=0x3939) as machine:
        native_write(machine, 0xff1000, bytes([KIND]))
        initial = machine.snapshot()
        machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True); machine.run(instructions=1)
        expected = machine.snapshot(), machine.info, machine.registers(), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert not candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        assert (machine.snapshot(), machine.info, machine.registers(), machine.audio()) == expected
        assert candidate.stats['collection_dispatch_hits'] == 0
        assert candidate.stats['fallbacks'] == 1


def test_type3a_declines_via_boundary_directly():
    from genesis_re.machine import Machine
    from aladdin_sega.profile import read_rom
    from aladdin_sega import boundary
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=1, digits=0x3939) as machine:
        native_write(machine, 0xff1000, bytes([KIND]))
        registers = machine.registers()
        entry, prefix = boundary.begin_collection_dispatch(machine, registers)
        assert entry == boundary.COLLECTION_TYPE3A_ENTRY
        with pytest.raises(UnsupportedCandidate, match='type3a capped counter arm is not recovered'):
            boundary.begin_collection_type3a_dispatch(machine, registers, prefix)


@pytest.mark.parametrize('mutant', ('result', 'timing'))
def test_type3a_gate_pass_no_sound_mutants_diverge(mutant):
    # 'continuation' is not exercised: this plan lands exactly at
    # COLLECTION_DISPATCH_RETURN, which _apply's own opportunistic
    # extend_contact_completion composes onward into the object's landing
    # script; a raw PC+2 shift there can land mid-instruction inside that
    # extended span and fault instead of diverging observably (the same
    # class of fragility the type43/63/79 seams document for their own
    # native-call boundary).
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=0) as machine:
        native_write(machine, 0xff1000, bytes([KIND]))
        initial = machine.snapshot()
        expected = original_to_return(machine)
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle-mutant-' + mutant)
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([0x1ABD74]); assert machine.run(instructions=10_000) == 'gate'
        actual = (machine.snapshot(), machine.info, machine.registers(), machine.audio())
        assert actual != expected
        assert candidate.stats['collection_dispatch_hits'] == 1


@pytest.mark.parametrize('mutant', ('result', 'timing'))
def test_type3a_gate_pass_sound_mutants_diverge(mutant):
    # 'continuation' is not exercised here either -- see the no-sound
    # arm's own test for why (the opportunistic landing-script extension
    # applies just as much once the sound seam's own suffix rejoins
    # COLLECTION_DISPATCH_RETURN).
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=1) as machine:
        native_write(machine, 0xff1000, bytes([KIND]))
        initial = machine.snapshot()
        expected = original_to_return(machine)
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle-mutant-' + mutant)
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([0x1ABD74]); assert machine.run(instructions=10_000) == 'gate'
        actual = (machine.snapshot(), machine.info, machine.registers(), machine.audio())
        assert actual != expected
        assert candidate.stats['collection_dispatch_hits'] == 1
