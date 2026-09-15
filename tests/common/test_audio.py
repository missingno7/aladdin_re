import array

import pytest

from genesis_re.audio import FramePacer, PcmBuffer


def pcm(values):
    return array.array("h", [v for value in values for v in (value, -value)]).tobytes()


def test_continuous_pcm_crosses_chunk_and_callback_boundaries():
    buffer = PcmBuffer(prime_frames=1, capacity_frames=32)
    source = pcm(range(1, 16))
    for start, end in ((0, 3), (3, 8), (8, 15)):
        buffer.push(source[4*start:4*end])
    outputs = []
    for count in (4, 6, 5):
        out = bytearray(count * 4)
        buffer.fill(out)
        outputs.append(bytes(out))
    assert b"".join(outputs) == source
    assert buffer.stats["played_frames"] == 15
    assert buffer.stats["buffered_frames"] == buffer.stats["underruns"] == 0


def test_priming_underflow_and_flush_never_repeat_old_samples():
    buffer = PcmBuffer(prime_frames=3, capacity_frames=8)
    buffer.push(pcm([1, 2]))
    out = bytearray(16)
    buffer.fill(out)
    assert out == bytes(16)
    assert buffer.stats["buffered_frames"] == 2
    buffer.push(pcm([3]))
    buffer.fill(out)
    assert out == pcm([1, 2, 3, 0])
    assert buffer.stats["underruns"] == 1
    buffer.push(pcm([4, 5, 6]))
    buffer.clear()
    buffer.fill(out)
    assert out == bytes(16)
    buffer.push(pcm([7, 8, 9]))
    buffer.fill(out)
    assert out == pcm([7, 8, 9, 0])


def test_full_queue_is_reported_without_silently_dropping_data():
    buffer = PcmBuffer(prime_frames=1, capacity_frames=3)
    buffer.push(pcm([1, 2, 3]))
    with pytest.raises(RuntimeError, match="overflow"):
        buffer.push(pcm([4]))
    out = bytearray(12)
    buffer.fill(out)
    assert out == pcm([1, 2, 3])


def test_pacer_compensates_sleep_overshoot_without_changing_simulation():
    pacer = FramePacer(0, 0.02)
    assert pacer.delay(0.003) == pytest.approx(0.017)
    # Previous sleep overshot by 5ms, and the next frame took 3ms.
    assert pacer.delay(0.028) == pytest.approx(0.012)
    assert pacer.delay(0.3) == 0  # bounded catch-up after a long host stall
    pacer.reset(1)
    assert pacer.delay(1.003) == pytest.approx(0.017)
