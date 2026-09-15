"""Original-ROM qualification of the Type-63 bounded distance guard, self-
kind check and command-0x45 mismatch seam.

1AF81C is structurally the same dispatch as Type-55/58 (the same FFF0BE
selector, the same record-plus-6 bit-4 activity test, the same shared
1AE6B4 tail), but its own guard adds nothing to the delta and its limit is
0xA rather than 0xC or 6.  A guard pass publishes the delta through
FF7DFC exactly as Type-58's own pass does, then reads the record's own
kind byte: a match against the fixed 0x63 constant returns locally at
once; a mismatch retypes the record to 0x63 and either returns locally
(FFF57D clear) or continues into its own command-0x45 sound seam (FFF57D
set) -- a private MOVEM/PEA/JSR frame with the same 24-byte-saved-frame,
28-byte-return-delta ABI shape as Type-46's own seam.  Both kind 0x62 and
kind 0x63 collection-dispatch slots share this one entry.
"""
import pytest
import oracle_witness as oracle
from aladdin_sega import boundary
from aladdin_sega import recovery as recovery_mod
from test_contact_family import family_fixture, TARGET_KINDS, qualify
from test_contact_scan import ENTRY as SCAN_ENTRY, EXIT as SCAN_EXIT, scan_fixture


# object_y=100, origin_x=0 puts delta at 100 - 0 = 100.
PASS_PREVIOUS = (91, 95, 100, 105, 109)      # distance 9,5,0,5,9 (mixed borrow)
FAIL_PREVIOUS = (0, 50, 89, 110, 200, 65535)  # distance 100,50,11,10,100,65435


def type63_fixture(*, kind=0x63, be=0, c0=0xFF, sound=0,
                   object_y=100, origin_x=0, previous=100, **kwargs):
    """Construct a valid Type-63 collection record over the original ROM.

    ``family_fixture`` seeds the record's own kind byte (``kind``, also
    the ROM dispatch-table selector -- both 0x62 and 0x63 route to this
    entry) and the guard's own fields: record+4 (``object_y``), FF7DF8
    (``origin_x``, subtracted from record+4) and FF7DFC (``previous``,
    compared against that delta).  ``be``/``c0`` select the FFF0BE/FFF0C0
    family selector (default: selector clear, straight into the bit-4/
    guard path); ``sound`` gates the kind-mismatch arm's own command-0x45
    seam.
    """
    return family_fixture(0x1AF81C, kind=kind, be=be, c0=c0, sound=sound,
                          object_y=object_y, origin_x=origin_x, previous=previous, **kwargs)


def _assert_matches_oracle(state):
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('kind', (0x62, 0x63))
def test_type63_direct_arm(monkeypatch, kind):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, kind)
    state = type63_fixture(kind=kind, be=1, c0=0)
    _assert_matches_oracle(state)


def test_type63_inactive_declines(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    state = type63_fixture(flags=0)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] >= 1


@pytest.mark.parametrize('previous', PASS_PREVIOUS)
@pytest.mark.parametrize('selector', (False, True))
def test_type63_guard_pass_kind_match(monkeypatch, previous, selector):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    state = type63_fixture(kind=0x63, previous=previous,
                           be=1 if selector else 0, c0=1 if selector else 0xFF)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('previous', FAIL_PREVIOUS)
@pytest.mark.parametrize('selector', (False, True))
def test_type63_guard_fail(monkeypatch, previous, selector):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    state = type63_fixture(kind=0x63, previous=previous,
                           be=1 if selector else 0, c0=1 if selector else 0xFF)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('previous', PASS_PREVIOUS)
@pytest.mark.parametrize('selector', (False, True))
def test_type63_guard_pass_kind_mismatch_no_sound(monkeypatch, previous, selector):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    state = type63_fixture(kind=0x62, previous=previous, sound=0,
                           be=1 if selector else 0, c0=1 if selector else 0xFF)
    _assert_matches_oracle(state)


@pytest.mark.parametrize('previous', PASS_PREVIOUS)
@pytest.mark.parametrize('selector', (False, True))
def test_type63_guard_pass_kind_mismatch_sound(monkeypatch, previous, selector):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    state = type63_fixture(kind=0x62, previous=previous, sound=1,
                           be=1 if selector else 0, c0=1 if selector else 0xFF)
    expected = qualify(state, None)
    actual = qualify(state, 'lifecycle')
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.stats['legacy_entries'] == 1
    assert actual.stats['legacy_returns'] == 1
    assert actual.stats['fallbacks'] == 0


@pytest.mark.parametrize('arm', ('direct', 'guard_fail', 'kind_match', 'kind_mismatch_no_sound'))
@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type63_every_ram_only_arm_mutants_diverge(monkeypatch, arm, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    if arm == 'direct':
        state = type63_fixture(be=1, c0=0)
        written_address = 0xFFF0F5
    elif arm == 'guard_fail':
        state = type63_fixture(previous=0)
        written_address = 0xFFF0F5
    elif arm == 'kind_match':
        state = type63_fixture(kind=0x63, previous=100)
        written_address = 0xFF7DFC
    else:
        state = type63_fixture(kind=0x62, previous=100, sound=0)
        written_address = 0xFF7DFC
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        from dataclasses import replace
        original = boundary.begin_contact_family_type63
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == written_address for at, _ in plan.writes)
            return replace(plan, writes=tuple((at, value ^ 1) for at, value in plan.writes))
        monkeypatch.setattr(boundary, 'begin_contact_family_type63', wrong)
        candidate = 'lifecycle'
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


@pytest.mark.parametrize('mutant', ('result', 'continuation', 'timing'))
def test_type63_sound_arm_mutants_diverge(monkeypatch, mutant):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    state = type63_fixture(kind=0x62, previous=100, sound=1)
    expected = qualify(state, None)
    candidate = 'lifecycle-mutant-' + mutant
    if mutant == 'result':
        # Flipping every prefix write (the generic mutant path's fallback
        # for a single-write plan does not apply here, since this plan has
        # several) would also corrupt the pushed native-call return address
        # and the command word, diverting into the native routine and
        # faulting instead of diverging observably. Flip only the safe,
        # purely-local delta publish.
        from dataclasses import replace
        original = boundary.begin_contact_family_type63_sound_seam
        def wrong(*args, **kwargs):
            plan = original(*args, **kwargs)
            assert any(at == 0xFF7DFC for at, _ in plan.writes)
            writes = tuple((at, value ^ 1 if at == 0xFF7DFC else value) for at, value in plan.writes)
            return replace(plan, writes=writes)
        monkeypatch.setattr(boundary, 'begin_contact_family_type63_sound_seam', wrong)
        candidate = 'lifecycle'
    if mutant == 'continuation':
        # As with the type43/type79 seams, a PC+2 mutation of the prefix
        # would divert into the native sound routine and fault instead of
        # diverging observably; perturb only the resumed suffix plan.
        original_mutate = recovery_mod.Candidate._mutate

        def suffix_only(candidate_obj, plan):
            if candidate_obj.name.endswith('continuation') and plan.registers.get('pc') == 0x1E58B8:
                return plan
            return original_mutate(candidate_obj, plan)

        monkeypatch.setattr(recovery_mod.Candidate, '_mutate', suffix_only)
    actual = qualify(state, candidate, stop_after_first=True)
    assert actual.stats['collection_dispatch_hits'] == 1
    assert actual.outer != expected.outer


def test_type63_declines_unaligned_stack(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    state = type63_fixture()
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        registers = machine.registers()
        registers['a7'] |= 1
        with pytest.raises(boundary.UnsupportedCandidate, match='unaligned type63'):
            boundary.begin_contact_family_type63(machine, registers)


def test_type63_sound_seam_declines_outside_mismatch_sound(monkeypatch):
    monkeypatch.setitem(TARGET_KINDS, 0x1AF81C, 0x63)
    state = type63_fixture(kind=0x63)  # kind match, not a mismatch at all
    with oracle.Machine(oracle.read_rom()) as machine:
        machine.restore(state)
        machine.gates([boundary.COLLECTION_DISPATCH_ENTRY])
        assert machine.run(instructions=1) == 'gate'
        registers = machine.registers()
        with pytest.raises(boundary.UnsupportedCandidate, match='outside the kind-mismatch sound arm'):
            boundary.begin_contact_family_type63_sound_seam(machine, registers)


# --- parent ownership ---------------------------------------------------------


def test_type63_is_owned_inside_the_complete_contact_scan(monkeypatch):
    original = boundary.begin_contact_family_type63_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type63_dispatch', observed)
    state = scan_fixture(kind=0x63)
    expected = oracle.execute_region(state, entry=SCAN_ENTRY, candidate=None,
                                     expected_return=SCAN_EXIT, include_raw=True)
    actual = oracle.execute_region(state, entry=SCAN_ENTRY, candidate='lifecycle',
                                   expected_return=SCAN_EXIT, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['contact_scan_hits'] == 1
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] == 0
    assert calls == 1


def test_type63_is_owned_inside_the_complete_contact_scan_kind_62(monkeypatch):
    original = boundary.begin_contact_family_type63_dispatch
    calls = 0
    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(boundary, 'begin_contact_family_type63_dispatch', observed)
    state = scan_fixture(kind=0x62)
    expected = oracle.execute_region(state, entry=SCAN_ENTRY, candidate=None,
                                     expected_return=SCAN_EXIT, include_raw=True)
    actual = oracle.execute_region(state, entry=SCAN_ENTRY, candidate='lifecycle',
                                   expected_return=SCAN_EXIT, include_raw=True)
    assert actual.outer == expected.outer
    assert actual.future == expected.future
    assert oracle.fresh_process_future(actual.outer_state) == actual.future
    assert actual.stats['contact_scan_hits'] == 1
    assert actual.stats['collection_dispatch_hits'] == 0
    assert actual.stats['fallbacks'] == 0
    assert calls == 1
