"""Native-backed progress and PCM-boundary contracts for replay execution."""
import pytest

from aladdin_sega import artifacts
from aladdin_sega.machine import Machine, NativeError
from aladdin_sega.profile import FRAME_TICKS


def synthetic_rom():
    rom = bytearray(1024)
    rom[0:8] = bytes.fromhex("00ff8000 00000200")
    # MOVE.W #$1234,$FF0010 ; BRA.S back to the store.
    rom[0x200:0x20a] = bytes.fromhex("33fc123400ff0010 60f6")
    return bytes(rom)


def event(tick, buttons):
    return {"tick": tick, "buttons": buttons}


def reachable_terminal(target):
    with Machine(synthetic_rom()) as reference:
        reference.run(target=target)
        return reference.info["tick"]


def test_replay_rejects_unexpected_gate():
    with Machine(synthetic_rom()) as machine:
        machine.gate(0x200)
        with pytest.raises(RuntimeError, match="Unexpected replay gate") as raised:
            artifacts.play_events(machine, [], FRAME_TICKS)
        assert '"pc": 512' in str(raised.value)
        assert machine.info["tick"] == 0


def test_recognized_gate_bypasses_once_then_replays():
    terminal = reachable_terminal(FRAME_TICKS)
    with Machine(synthetic_rom()) as machine:
        machine.gate(0x200)
        observed_deadlines = []

        def on_gate(candidate, deadline):
            observed_deadlines.append(deadline)
            # Bypass executes the gated store.  The handler itself must advance
            # the native machine before returning, then releases the gate.
            candidate.gate(0x200, bypass_once=True)
            assert candidate.run(instructions=1) == "limit"
            candidate.gate()

        artifacts.play_events(machine, [], terminal, on_gate=on_gate)
        assert observed_deadlines == [terminal]
        assert machine.peek_ram(0x10, 2) == b"\x12\x34"
        assert machine.info["tick"] == terminal


def test_carrier_budget_stops_at_observation_then_applies_input_exactly():
    input_tick = reachable_terminal(FRAME_TICKS * 61)
    terminal = reachable_terminal(FRAME_TICKS * 90)
    streams, deadlines = [], []
    for recovered in (False, True):
        with Machine(synthetic_rom()) as machine:
            # This store-loop ROM does not initialize a drawable VDP mode.
            # Compare native/device state and PCM; real-ROM witnesses cover RGB.
            pcm, observations = bytearray(), []
            def checkpoint(candidate, key, requested):
                observations.append((key, requested, candidate.info["tick"], candidate.snapshot(), bytes(pcm)))
                pcm.clear()
            def on_gate(candidate, deadline):
                deadlines.append(deadline)
                candidate.gates([])
                # This spans many host PCM batches but cannot pass checkpoint 60.
                candidate.run(target=deadline)
            if recovered:
                machine.gate(0x200)
            artifacts.play_events(machine, [event(input_tick, 8)], terminal,
                                  on_gate=on_gate if recovered else None,
                                  audio_sink=pcm.extend, on_checkpoint=checkpoint)
            checkpoint(machine, "terminal", terminal)
            streams.append(observations)
    assert deadlines == [FRAME_TICKS * 60]
    assert streams[0] == streams[1]


def test_replay_allows_same_tick_input_changes():
    terminal = reachable_terminal(FRAME_TICKS)
    with Machine(synthetic_rom()) as machine:
        artifacts.play_events(machine, [event(0, 1), event(0, 3)], terminal)
        assert machine.info["buttons"] == 3
        assert machine.info["tick"] == terminal


def test_replay_rejects_unreachable_input_timestamp_without_late_apply():
    with Machine(synthetic_rom()) as machine:
        with pytest.raises(ValueError, match="not reachable"):
            artifacts.play_events(machine, [event(1, 8)], FRAME_TICKS)
        # The attempted run overshot tick 1, but playback must not apply its input.
        assert machine.info["tick"] > 1
        assert machine.info["buttons"] == 0


class OscillatingGate:
    """A candidate that keeps moving its advertised PC without advancing time."""
    def __init__(self):
        self._pc = 0x200
        self.candidate_identity = "oscillating-test-candidate"

    @property
    def info(self):
        return {"tick": 0, "pc": self._pc, "buttons": 0}

    def run(self, *, target):
        assert target > 0
        return "gate"

    def audio(self):
        return b""

    def pad(self, _):
        raise AssertionError("No input should be applied while a gate is parked")

    def move_gate(self):
        self._pc = 0x202 if self._pc == 0x200 else 0x200


def test_replay_bounds_repeated_zero_time_candidate_gates():
    machine = OscillatingGate()
    calls = 0

    def on_gate(candidate, _):
        nonlocal calls
        calls += 1
        candidate.move_gate()

    with pytest.raises(RuntimeError, match="no progress|parked|gate"):
        artifacts.play_events(machine, [], 1, on_gate=on_gate)
    assert calls > 1


def test_long_pcm_capture_explicitly_invalidates_instead_of_dropping_samples():
    with Machine(synthetic_rom()) as machine:
        # The native capture capacity is 106,536 stereo frames.  This produces
        # more than that in one uninterrupted batch.
        with pytest.raises(NativeError, match="PCM output capacity exceeded"):
            machine.run(target=FRAME_TICKS * 121)
        with pytest.raises(NativeError, match="invalidated"):
            machine.run(instructions=1)
        with pytest.raises(NativeError, match="Execution failed"):
            machine.snapshot()


def test_chunked_pcm_capture_is_lossless_beyond_one_batch_capacity():
    target = FRAME_TICKS * 121
    with Machine(synthetic_rom()) as machine:
        chunks = []
        for frame in range(1, 122):
            machine.run(target=FRAME_TICKS * frame)
            chunks.append(machine.audio())
        assert machine.info["tick"] >= target
        assert len(b"".join(chunks)) // 4 > 106_536
        assert machine.snapshot()


def test_discarded_presentation_pcm_does_not_stop_emulated_audio_devices():
    target = FRAME_TICKS * 4
    with Machine(synthetic_rom()) as captured:
        captured.run(target=target)
        pcm = captured.audio()
        expected = captured.snapshot()
        expected_info = captured.info
    with Machine(synthetic_rom()) as discarded:
        discarded.audio_policy("discard")
        discarded.run(target=target)
        assert discarded.audio() == b""
        assert discarded.info == expected_info
        assert discarded.snapshot() == expected
    assert pcm


def test_snapshot_restoration_cuts_host_pcm_but_preserves_future_pcm():
    first, terminal = FRAME_TICKS * 3, FRAME_TICKS * 7
    with Machine(synthetic_rom()) as machine:
        anchor = machine.snapshot()
        machine.run(target=first)
        assert machine.audio()
        snapshot = machine.snapshot()
        machine.run(target=terminal)
        expected_suffix = machine.audio()

        # Queue pre-cut output again, then restore.  It must not reappear after
        # restore, while PCM generated from the restored device state must match.
        machine.restore(anchor)
        machine.run(target=first)
        machine.restore(snapshot)
        assert machine.audio() == b""
        machine.run(target=terminal)
        assert machine.audio() == expected_suffix
