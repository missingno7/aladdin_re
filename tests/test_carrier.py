"""Concrete sound-frame continuation, original-ROM branches, and save integrity."""
import copy

import pytest

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine
from aladdin_sega.recovered import TRANSITION_ENTRY, SOUND_RETURN, begin_object_transition
from aladdin_sega.recovery import Candidate, transition_frame, validate_transition
from test_recovery import leaf_machine, native_replace_rom, native_write, put


TRANSITION_BYTES = bytes.fromhex(
    "0c79393900ffefe0660000066100f26861000ebc4a3900fff57d671a48e7c0c24"
    "878000b4eb9001e58b84eb9001e589a588f4cdf43036026")
COUNTER_BYTES = bytes.fromhex(
    "0c79393900ffefe0671e523900ffefe10c39003a00ffefe1650e523900ffefe0"
    "13fc003000ffefe14e75")


def continuation_machine():
    machine = leaf_machine()
    machine.info["pc"] = SOUND_RETURN
    machine._registers.update(pc=SOUND_RETURN, a7=0xff7fe8)
    put(machine, 0xff7fe4, SOUND_RETURN, 4)
    for i, name in enumerate(("a6", "a1", "a0", "d1", "d0"), 1):
        put(machine, 0xff8000 - i * 4, machine._registers[name], 4)
    machine.pending_transition = {"contract": "object-sound-v1", "entry_tick": 1,
                                  "outer_sp": 0xff8000, "frame_sha256": transition_frame(machine, 0xff8000)}
    return machine


def test_same_pc_at_another_stack_depth_does_not_resume_python():
    machine = continuation_machine()
    machine._registers["a7"] -= 32
    pending = copy.deepcopy(machine.pending_transition)
    candidate = Candidate("carrier")
    assert not candidate.on_gate(machine, 10000)
    assert machine.atomic_call is None
    assert machine.pending_transition == pending
    assert machine.gate_call == (SOUND_RETURN, True)
    assert candidate.stats["foreign_returns"] == 1


@pytest.mark.parametrize("address,reason", [(0xff8000, "frame"), (0xff7ffc, "frame"), (0xff7fe4, "return slot")])
def test_same_pc_and_sp_with_wrong_activation_is_rejected(address, reason):
    machine = continuation_machine()
    put(machine, address, 0x12345678, 4)
    with pytest.raises(ValueError, match=reason):
        Candidate("carrier").on_gate(machine, 10000)
    assert machine.atomic_call is None


def test_suffix_refusal_keeps_prefix_and_delegates_only_suffix():
    machine = continuation_machine()
    machine.atomic_result = False
    before = bytes(machine.ram)
    candidate = Candidate("carrier")
    assert not candidate.on_gate(machine, 10000)
    assert machine.pending_transition is None
    assert machine.gate_call == (SOUND_RETURN, True)
    assert machine.run_call == 1
    assert bytes(machine.ram) == before
    assert candidate.stats["local_fallbacks"] == 1
    assert candidate.stats["legacy_returns"] == 1


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


@pytest.mark.parametrize("digits", [0x3030, 0x3039, 0x3938])
@pytest.mark.parametrize("sound", [0, 1, 0x80])
def test_native_connected_region_branches_match_original(monkeypatch, digits, sound):
    # Prefix/counter/pair/initializer are verbatim ROM bytes. The two sound
    # callees below are synthetic clobbering stubs; real sound is qualified by
    # carrier_witness.py and the full corpus, not claimed by this fixture.
    rom = bytearray(native_replace_rom(TRANSITION_ENTRY, 0x201f))
    rom[TRANSITION_ENTRY:TRANSITION_ENTRY + len(TRANSITION_BYTES)] = TRANSITION_BYTES
    rom[0x1b0336:0x1b0336 + len(COUNTER_BYTES)] = COUNTER_BYTES
    request = bytes.fromhex("4eb9001e57ac203c12345678227c00ff43212c7c00ff67894e75")
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
        prefix_pcm = b""
        if sound:
            assert candidate.run(instructions=1) == "limit"
            assert candidate.info["pc"] == 0x1e57ac
            prefix_pcm = candidate.audio()
            saved = artifacts.snapshot_bytes(candidate)
            check_snapshot_envelope(candidate, saved)
            artifacts.restore_snapshot(candidate, saved)
            policy.arm(candidate)
            assert candidate.run(instructions=10000) == "gate"
            assert policy.on_gate(candidate, candidate.info["tick"] + 1_000_000)
            assert policy.stats["legacy_returns"] == 1
        assert candidate.pending_transition is None
        assert (candidate.snapshot(), prefix_pcm + candidate.audio()) == expected


def check_snapshot_envelope(machine, saved):
    members = {"manifest.json", "machine.bin", "object-transition.json"}
    parts = artifacts.unpack(saved, members, members)
    meta, _ = artifacts.load_snapshot(saved, rom_sha256=machine.rom_sha256, state_version=machine.state_version)
    assert meta["version"] == 3
    injected = artifacts.decode_json(parts["manifest.json"])
    injected["version"] = 2
    injected["sections"].pop("object-transition.json")
    injected["object_transition"] = meta["object_transition"]
    with pytest.raises(ValueError, match="snapshot member"):
        artifacts.restore_snapshot(machine, artifacts.pack({"manifest.json": artifacts.json_bytes(injected),
                                                           "machine.bin": parts["machine.bin"]}))
    broken = dict(parts)
    broken["object-transition.json"] += b" "
    with pytest.raises(ValueError, match="integrity"):
        artifacts.restore_snapshot(machine, artifacts.pack(broken))
    saved_context = artifacts.decode_json(parts["object-transition.json"])
    saved_context["machine_sha256"] = "0" * 64
    broken["object-transition.json"] = artifacts.json_bytes(saved_context)
    manifest = artifacts.decode_json(parts["manifest.json"])
    manifest["sections"]["object-transition.json"] = {
        "size": len(broken["object-transition.json"]), "sha256": artifacts.digest(broken["object-transition.json"])}
    broken["manifest.json"] = artifacts.json_bytes(manifest)
    with pytest.raises(ValueError, match="binding"):
        artifacts.restore_snapshot(machine, artifacts.pack(broken))


def test_metadata_cannot_select_an_arbitrary_resume_case():
    pending = continuation_machine().pending_transition
    pending["return_pc"] = 0x123456
    with pytest.raises(ValueError, match="metadata"):
        validate_transition(pending)
