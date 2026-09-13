"""Original-byte qualification for the narrow collection callback dispatcher."""
import pytest

from aladdin_sega.recovery import Candidate
from aladdin_sega.boundary import (COLLECTION_DISPATCH_ENTRY, COLLECTION_DISPATCH_RETURN,
                                  COLLECTION_ROUTES, begin_collection, begin_collection_dispatch,
                                  dispatch_plan_view)
from test_collection import native_write, prepared


# One representative table index for every currently admitted callback.  The
# duplicate 0x1AF4A0/0x1AF468/etc. table slots have identical prefix behavior.
ROUTES = ((41, 0x1AF400), (51, 0x1AF4A0), (52, 0x1AF4D8), (53, 0x1AF468),
          (55, 0x1AF344), (59, 0x1AF21E), (61, 0x1AF384), (62, 0x1AF2B0),
          (63, 0x1AF2FA), (64, 0x1AF468), (65, 0x1AF3C2), (66, 0x1AF264),
          (73, 0x1AF008), (74, 0x1AF034), (75, 0x1AF060), (76, 0x1AF08C),
          (90, 0x1AF53E))
assert {callback for _kind, callback in ROUTES} == set(COLLECTION_ROUTES)


def original_to_return(machine):
    machine.gates([COLLECTION_DISPATCH_RETURN])
    machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
    assert machine.run(instructions=10_000) == 'gate'
    return machine.snapshot(), machine.info, machine.registers(), machine.audio()


@pytest.mark.parametrize('kind,callback', ROUTES)
@pytest.mark.parametrize('sound,linked,total', [(0, False, 0), (1, True, 0xfff0)])
def test_dispatcher_composes_known_callback_at_its_original_outer_return(kind, callback, sound, linked, total):
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=sound, linked=linked, total=total) as machine:
        native_write(machine, 0xff1000, bytes([kind]))
        initial = machine.snapshot()
        expected = original_to_return(machine)
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        assert (machine.snapshot(), machine.info, machine.registers(), machine.audio()) == expected
        assert candidate.stats['collection_dispatch_hits'] == 1
        assert candidate.stats['collection_entries'] == {f'{callback:06X}': 1}
        # The callback has no native stop: sound contributes the only second gate.
        assert candidate.stats['gates'] == 1 + sound


@pytest.mark.parametrize('kind,setup,branch_effect', [
    # quarter's counter avoids the sound path before it reaches four.
    (66, lambda machine: native_write(machine, 0xfff10a, b'\x02'), None),
    # primary's capped-state table path retains its direct callback semantics.
    (64, lambda machine: (native_write(machine, 0xffefe0, (0x3939).to_bytes(2, 'big')),
                          native_write(machine, 0xff1034, b'\x80'),
                          native_write(machine, 0xff1032, (0x8000).to_bytes(2, 'big'))),
     (0x2e87, 0x80)),
    # secondary's accepted short return has no sound seam or retirement.
    (59, lambda machine: (native_write(machine, 0xffefe0, (0x3939).to_bytes(2, 'big')),
                          native_write(machine, 0xfff0d8, b'\x80')), None),
])
def test_dispatcher_representative_conditional_callback_paths(kind, setup, branch_effect):
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=1) as machine:
        native_write(machine, 0xff1000, bytes([kind])); setup(machine)
        initial = machine.snapshot(); expected = original_to_return(machine)
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        assert (machine.snapshot(), machine.info, machine.registers(), machine.audio()) == expected
        assert candidate.stats['collection_dispatch_hits'] == 1
        if branch_effect is not None:
            address, value = branch_effect
            assert machine.peek_ram(address, 1) == bytes((value,))


def test_dispatcher_planning_view_supplies_prefix_writes_to_callback_reads():
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=0) as machine:
        native_write(machine, 0xff1000, bytes([73]))
        registers = machine.registers(); frame = registers['a7'] - 4
        # These bytes must not leak into the direct callback's frame/global reads.
        native_write(machine, frame, bytes.fromhex('deadbeef'))
        native_write(machine, 0xfff0f5, bytes.fromhex('aabb'))
        entry, prefix = begin_collection_dispatch(machine, registers)
        planned = dispatch_plan_view(machine, prefix)
        dispatched = dict(registers); dispatched.update(prefix.registers)
        assert planned.peek_ram(frame & 0xffff, 4) == COLLECTION_DISPATCH_RETURN.to_bytes(4, 'big')
        assert planned.peek_ram(0xf0f5, 2) == bytes((0, 73))
        assert planned.peek_ram(0x1000, 1) == bytes((73,))
        callback, legacy = begin_collection(planned, dispatched, entry)
        assert not legacy
        # Retirement consumes the planned JSR return, rather than deadbeef.
        assert callback.registers['pc'] == COLLECTION_DISPATCH_RETURN


@pytest.mark.parametrize('kind,_callback', ROUTES)
def test_dispatcher_post_callback_observer_matches_original(kind, _callback):
    with prepared(COLLECTION_DISPATCH_ENTRY, sound=0) as machine:
        native_write(machine, 0xff1000, bytes([kind]))
        initial = machine.snapshot()
        machine.gates([0x1ABD74]); machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True)
        assert machine.run(instructions=10_000) == 'gate'
        expected = machine.snapshot(), machine.info, machine.registers(), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY]); machine.run(instructions=1)
        candidate = Candidate('lifecycle')
        assert candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        machine.gates([0x1ABD74]); assert machine.run(instructions=100) == 'gate'
        assert (machine.snapshot(), machine.info, machine.registers(), machine.audio()) == expected


@pytest.mark.parametrize('record,kind', [(0xff1000, 0), (0xfff0f4, 73)])
def test_unsupported_dispatcher_domain_falls_back_before_prefix(record, kind):
    with prepared(COLLECTION_DISPATCH_ENTRY, record=record) as machine:
        native_write(machine, record, bytes([kind]))
        initial = machine.snapshot()
        machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True); machine.run(instructions=1)
        expected = machine.snapshot(), machine.info, machine.registers(), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY]); machine.run(instructions=1)
        candidate = Candidate('lifecycle')
        assert not candidate.on_gate(machine, machine.info['tick'] + 1_000_000)
        assert (machine.snapshot(), machine.info, machine.registers(), machine.audio()) == expected
        assert candidate.stats['collection_dispatch_hits'] == 0


def test_dispatcher_deadline_refuses_before_prefix():
    with prepared(COLLECTION_DISPATCH_ENTRY) as machine:
        native_write(machine, 0xff1000, bytes([73]))
        initial = machine.snapshot()
        machine.gate(COLLECTION_DISPATCH_ENTRY, bypass_once=True); machine.run(instructions=1)
        expected = machine.snapshot(), machine.info, machine.registers(), machine.audio()
        machine.restore(initial); machine.audio(); machine.gates([COLLECTION_DISPATCH_ENTRY]); machine.run(instructions=1)
        candidate = Candidate('lifecycle')
        # The prefix alone needs 98 M68K cycles, or 686 master ticks.
        assert not candidate.on_gate(machine, machine.info['tick'] + 685)
        assert (machine.snapshot(), machine.info, machine.registers(), machine.audio()) == expected
        assert candidate.stats['collection_dispatch_hits'] == 0
