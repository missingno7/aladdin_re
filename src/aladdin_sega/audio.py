"""Continuous host PCM output. The callback only consumes already-emulated audio."""
from collections import deque
import threading

from .profile import MASTER_HZ

SAMPLE_RATE = round(MASTER_HZ / 1008)
FRAME_BYTES = 4  # little-endian signed 16-bit stereo


class PcmBuffer:
    def __init__(self, *, prime_frames=4096, capacity_frames=SAMPLE_RATE):
        if not 0 < prime_frames <= capacity_frames:
            raise ValueError("Invalid audio buffer limits")
        self.prime_bytes = prime_frames * FRAME_BYTES
        self.capacity_bytes = capacity_frames * FRAME_BYTES
        self._lock = threading.Lock()
        self._chunks = deque()
        self._offset = 0
        self._buffered = 0
        self._playing = False
        self._stats = {"submitted_frames": 0, "played_frames": 0, "underruns": 0,
                       "underrun_frames": 0, "priming_frames": 0, "high_water_frames": 0,
                       "flushes": 0}

    def push(self, pcm):
        if len(pcm) % FRAME_BYTES:
            raise ValueError("PCM must contain complete stereo frames")
        if not pcm:
            return
        with self._lock:
            if self._buffered + len(pcm) > self.capacity_bytes:
                raise RuntimeError("Host audio buffer overflow; output device is not consuming PCM")
            self._chunks.append(bytes(pcm))
            self._buffered += len(pcm)
            self._stats["submitted_frames"] += len(pcm) // FRAME_BYTES
            self._stats["high_water_frames"] = max(self._stats["high_water_frames"], self._buffered // FRAME_BYTES)

    def fill(self, output):
        output = memoryview(output).cast("B")
        if len(output) % FRAME_BYTES:
            raise ValueError("Output must contain complete stereo frames")
        with self._lock:
            output[:] = bytes(len(output))
            if not self._playing:
                if self._buffered < self.prime_bytes:
                    self._stats["priming_frames"] += len(output) // FRAME_BYTES
                    return
                self._playing = True
            used = 0
            while self._chunks and used < len(output):
                chunk = self._chunks[0]
                take = min(len(chunk) - self._offset, len(output) - used)
                output[used:used+take] = chunk[self._offset:self._offset+take]
                used += take
                self._offset += take
                self._buffered -= take
                if self._offset == len(chunk):
                    self._chunks.popleft()
                    self._offset = 0
            self._stats["played_frames"] += used // FRAME_BYTES
            if used < len(output):
                self._stats["underruns"] += 1
                self._stats["underrun_frames"] += (len(output) - used) // FRAME_BYTES
                self._playing = False

    def clear(self):
        with self._lock:
            self._chunks.clear()
            self._offset = self._buffered = 0
            self._playing = False
            self._stats["flushes"] += 1

    @property
    def stats(self):
        with self._lock:
            return {**self._stats, "buffered_frames": self._buffered // FRAME_BYTES}


class AudioOutput:
    def __init__(self):
        import pygame
        from pygame._sdl2.mixer import set_post_mix
        self._pygame = pygame
        self._set_post_mix = set_post_mix
        self.buffer = PcmBuffer()
        self.error = None
        # Keep the requested application format; SDL handles physical device conversion.
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=1024, allowedchanges=0)
        if pygame.mixer.get_init() != (SAMPLE_RATE, -16, 2):
            pygame.mixer.quit()
            raise RuntimeError("Audio device did not provide the required PCM format")
        self._callback = self._mix  # Keep the callback alive until mixer shutdown.
        set_post_mix(self._callback)

    def _mix(self, _, output):
        try:
            self.buffer.fill(output)
        except Exception as error:
            # Callback failures are reported on the UI thread, never swallowed.
            self.error = str(error)
            raw = memoryview(output).cast("B")
            raw[:] = bytes(len(raw))

    def push(self, pcm):
        if self.error:
            raise RuntimeError(f"Audio callback failed: {self.error}")
        self.buffer.push(pcm)

    def clear(self):
        self.buffer.clear()

    def close(self):
        self._set_post_mix(None)
        self._pygame.mixer.quit()


class FramePacer:
    """Absolute host deadlines avoid adding sleep overshoot to every frame."""
    def __init__(self, now, period):
        self.period = period
        self.reset(now)

    def reset(self, now):
        self.deadline = now

    def delay(self, now):
        self.deadline += self.period
        # A long host stall should not cause an unbounded catch-up burst.
        if now - self.deadline > 4 * self.period:
            self.deadline = now
        return max(0.0, self.deadline - now)
