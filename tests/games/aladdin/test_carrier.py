"""Concrete sound-frame continuation, original-ROM branches, and save integrity."""
import pytest

from genesis_re.history_runtime import safe_state
from genesis_re.machine import Machine
from aladdin_sega.recovery import TRANSITION_ENTRY, SOUND_RETURN, begin_object_transition
from aladdin_sega.recovery import Candidate
from test_recovery import leaf_machine, native_replace_rom, native_write, put


TRANSITION_BYTES = bytes.fromhex(
    "0c79393900ffefe0660000066100f26861000ebc4a3900fff57d671a48e7c0c24"
    "878000b4eb9001e58b84eb9001e589a588f4cdf43036026")
COUNTER_BYTES = bytes.fromhex(
    "0c79393900ffefe0671e523900ffefe10c39003a00ffefe1650e523900ffefe0"
    "13fc003000ffefe14e75")


def sound_machine(monkeypatch, *, foreign=False, corrupt=None, deadline=False, suffix_refusal=False):
    machine = leaf_machine()
    machine._registers["pc"] = machine.info["pc"] = TRANSITION_ENTRY
    put(machine, 0xffefe0, 0x3030, 2)
    put(machine, 0xfff57d, 1, 1)
    machine.in_seam = False
    machine.atomic_calls = 0
    def atomic(**plan):
        machine.atomic_calls += 1
        if suffix_refusal and machine.atomic_calls == 2:
            return False
        for address, value in plan["writes"]:
            put(machine, address, value, 1)
        machine._registers.update(plan["registers"])
        machine.info.update(pc=machine._registers["pc"], tick=machine.info["tick"] + 7 * plan["cycles"])
        return True
    def run(*, target=0, instructions=0):
        nonlocal foreign
        if instructions:
            machine.run_call = instructions
            return "limit"
        assert machine.in_seam
        with pytest.raises(ValueError, match="inside a seam"):
            safe_state(machine)
        if deadline:
            machine.info.update(pc=0x1e57ac, tick=target)
            machine._registers["pc"] = 0x1e57ac
            return "limit"
        machine._registers.update(pc=SOUND_RETURN, a7=0xff7fc8 if foreign else 0xff7fe8)
        machine.info["pc"] = SOUND_RETURN
        put(machine, 0xff7fe4, SOUND_RETURN, 4)
        if corrupt is not None:
            put(machine, corrupt, 0x12345678, 4)
        foreign = False
        return "gate"
    monkeypatch.setattr(machine, "atomic", atomic)
    monkeypatch.setattr(machine, "run", run)
    return machine


def test_foreign_return_does_not_resume_and_snapshot_is_forbidden_in_call(monkeypatch):
    machine = sound_machine(monkeypatch, foreign=True)
    candidate = Candidate("carrier")
    assert candidate.on_gate(machine, 100000)
    assert candidate.stats["foreign_returns"] == 1
    assert candidate.stats["legacy_returns"] == candidate.stats["carrier_completed"] == 1
    assert not machine.in_seam
    assert machine.armed == candidate.gate_pcs


@pytest.mark.parametrize("address", [0xff8000, 0xff7ffc, 0xff7fe4])
def test_wrong_outer_return_saved_frame_or_return_slot_is_rejected(monkeypatch, address):
    machine = sound_machine(monkeypatch, corrupt=address)
    with pytest.raises(ValueError, match="return/frame"):
        Candidate("carrier").on_gate(machine, 100000)
    assert machine.atomic_calls == 1
    assert not machine.in_seam


def test_deadline_relinquishes_original_suffix_without_advancing_again(monkeypatch):
    machine = sound_machine(monkeypatch, deadline=True)
    candidate = Candidate("carrier")
    assert candidate.on_gate(machine, 100000)
    assert machine.info["tick"] == 100000 and machine.run_call is None
    assert machine.peek_ram(0xefe0, 2) == b"01"
    assert candidate.stats["legacy_deadline_fallbacks"] == 1
    assert candidate.stats["legacy_returns"] == 0
    assert not machine.in_seam


def test_suffix_refusal_keeps_prefix_and_delegates_only_suffix(monkeypatch):
    machine = sound_machine(monkeypatch, suffix_refusal=True)
    candidate = Candidate("carrier")
    assert candidate.on_gate(machine, 100000)
    assert machine.peek_ram(0xefe0, 2) == b"01"
    assert machine.gate_call == (SOUND_RETURN, True)
    assert machine.run_call == 1 and not machine.in_seam
    assert candidate.stats["local_fallbacks"] == candidate.stats["legacy_returns"] == 1


def test_prefix_refusal_does_not_enter_sound_or_commit_counter(monkeypatch):
    machine = sound_machine(monkeypatch)
    monkeypatch.setattr(machine, "atomic", lambda **_: False)
    candidate = Candidate("carrier")
    assert not candidate.on_gate(machine, 100000)
    assert machine.peek_ram(0xefe0, 2) == b"00"
    assert machine.gate_call == (TRANSITION_ENTRY, True)
    assert not machine.in_seam and candidate.stats["legacy_entries"] == 0


@pytest.mark.parametrize("digits", [0x3939, 0x2930, 0x3040])
def test_unowned_counter_domains_fall_back_before_prefix_effects(digits):
    machine = leaf_machine()
    put(machine, 0xffefe0, digits, 2)
    before = bytes(machine.ram)
    with pytest.raises(RuntimeError, match="counter"):
        begin_object_transition(machine, machine.registers())
    assert bytes(machine.ram) == before


def test_silent_counter_alias_is_refused_before_composing_live_reads():
    machine = leaf_machine(a1=0xffefe0)
    put(machine, 0xffefe0, 0x3030, 2)
    before = bytes(machine.ram)
    with pytest.raises(RuntimeError, match="aliases"):
        begin_object_transition(machine, machine.registers())
    assert bytes(machine.ram) == before


@pytest.mark.parametrize("digits,sound,reentrant", [
    (digits, sound, False) for digits in (0x3030, 0x3039, 0x3938) for sound in (0, 1, 0x80)
] + [pytest.param(0x3030, 1, True, id="nested-original-return")])
def test_native_connected_region_branches_match_original(monkeypatch, digits, sound, reentrant):
    # Prefix/counter/pair/initializer are verbatim ROM bytes. The two sound
    # callees below are synthetic clobbering stubs; real sound is qualified by
    # synchronous_witness.py and the full corpus, not claimed by this fixture.
    rom = bytearray(native_replace_rom(TRANSITION_ENTRY, 0x201f))
    rom[TRANSITION_ENTRY:TRANSITION_ENTRY + len(TRANSITION_BYTES)] = TRANSITION_BYTES
    rom[0x1b0336:0x1b0336 + len(COUNTER_BYTES)] = COUNTER_BYTES
    request = bytes.fromhex("4eb9001e57ac203c12345678227c00ff43212c7c00ff67894e75")
    if reentrant:
        # One nested original caller reaches the same sound return at another
        # stack depth. A RAM latch prevents recursive sound requests forever.
        request = bytes.fromhex("4a3900fff580660e13fc000100fff5804eb9001af4684e75")
    rom[0x1e58b8:0x1e58b8 + len(request)] = request
    rom[0x1e57ac:0x1e57ae] = bytes.fromhex("4e75")
    rom[0x1e589a:0x1e58a0] = bytes.fromhex("003c00104e75")  # Set X in legacy code.
    rom = bytes(rom)
    with Machine(rom) as original:
        native_write(original, 0xff1000, b"\xa5" * 66)
        native_write(original, 0xff102a, (0xff2000).to_bytes(4, "big"))
        native_write(original, 0xff1029, b"\x04")
        native_write(original, 0xff103e, b"\0" * 4)
        native_write(original, 0xff8000, (0x300).to_bytes(4, "big"))
        native_write(original, 0xffefe0, digits.to_bytes(2, "big"))
        native_write(original, 0xfff57d, bytes([sound]))
        original.gates([TRANSITION_ENTRY])
        assert original.run(instructions=64) == "gate"
        original.audio()
        parked = original.snapshot()
        original.gates([0x300])
        assert original.run(instructions=10000) == "gate"
        expected = original.snapshot(), original.audio()
    with Machine(rom) as candidate:
        # Only this synthetic fixture substitutes the ROM identity gate.
        monkeypatch.setattr("aladdin_sega.recovery.ROM_SHA256", candidate.rom_sha256)
        candidate.restore(parked)
        policy = Candidate("carrier")
        policy.arm(candidate)
        assert candidate.run(instructions=1) == "gate"
        assert policy.on_gate(candidate, candidate.info["tick"] + 1_000_000)
        assert not candidate.in_seam
        assert policy.stats["legacy_returns"] == bool(sound)
        assert policy.stats["foreign_returns"] == int(reentrant)
        assert (candidate.snapshot(), candidate.audio()) == expected


@pytest.mark.parametrize("deadline", (False, True))
def test_lifecycle_spawn_gates_survive_sound_seam(monkeypatch, deadline):
    machine = sound_machine(monkeypatch, deadline=deadline)
    candidate = Candidate("lifecycle")
    assert candidate.on_gate(machine, 100000)
    assert machine.armed == candidate.gate_pcs
    assert {0x1B6ED0, 0x1B6F0C, 0x1B6F1E}.issubset(machine.armed)
