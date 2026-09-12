"""Failure paths use doubles so they do not require the local user ROM."""
from types import SimpleNamespace

import pytest

from aladdin_sega import frontend
from aladdin_sega.profile import FRAME_TICKS


class RunFailure(RuntimeError):
    pass


class SaveFailure(RuntimeError):
    pass


class CleanupFailure(RuntimeError):
    pass


def event(kind, key=None):
    return SimpleNamespace(type=kind, key=key)


def install_host(monkeypatch, *, batches, quit_error=None):
    calls = []
    constants = {
        "QUIT": 1, "WINDOWFOCUSLOST": 2, "KEYDOWN": 3, "KEYUP": 4,
        "K_UP": 10, "K_DOWN": 11, "K_LEFT": 12, "K_RIGHT": 13,
        "K_x": 14, "K_c": 15, "K_z": 16, "K_RETURN": 17,
        "K_F5": 18, "K_F6": 19, "K_F7": 20, "K_F8": 21, "K_F9": 22,
    }

    class Window:
        def fill(self, *_):
            pass

        def blit(self, *_):
            pass

    class Font:
        def render(self, *_):
            return object()

    def quit():
        calls.append("pygame.quit")
        if quit_error:
            raise quit_error

    batch_iter = iter(batches)
    pygame = SimpleNamespace(
        **constants,
        display=SimpleNamespace(
            init=lambda: calls.append("display.init"),
            set_mode=lambda _: Window(),
            set_caption=lambda _: None,
            flip=lambda: None,
        ),
        font=SimpleNamespace(init=lambda: calls.append("font.init"), Font=lambda *_: Font()),
        event=SimpleNamespace(get=lambda: next(batch_iter)),
        image=SimpleNamespace(frombuffer=lambda *_: object()),
        transform=SimpleNamespace(scale=lambda picture, _: picture),
        quit=quit,
    )
    monkeypatch.setitem(__import__("sys").modules, "pygame", pygame)
    return pygame, calls


class FakeMachine:
    def __init__(self, _, *, run_error=None):
        self.info = {"tick": 100, "buttons": 0}
        self.run_error = run_error

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def pad(self, buttons):
        self.info["buttons"] = buttons

    def run(self, *, target):
        if self.run_error:
            self.info["tick"] = target - 1  # A failed native call may have advanced partially.
            raise self.run_error
        self.info["tick"] = target

    def audio(self):
        return b""

    def frame(self):
        return 1, 1, b"\0\0\0"


class FakeRecorder:
    instances = []

    def __init__(self, machine, **_):
        self.start = machine.info["tick"]
        self.events = []
        self.bookmarks = []
        self.finish_calls = []
        self.__class__.instances.append(self)

    def apply_pad(self, machine, buttons):
        machine.pad(buttons)
        self.events.append({"tick": machine.info["tick"], "buttons": buttons})

    def finish(self, machine, **kwargs):
        self.finish_calls.append({"machine_tick": machine.info["tick"], **kwargs})
        return b"replay"


class FakeAudio:
    instances = []

    def __init__(self, *, close_error=None):
        self.close_error = close_error
        self.closed = False
        self.buffer = SimpleNamespace(stats={"submitted_frames": 0})
        self.__class__.instances.append(self)

    def push(self, _):
        pass

    def clear(self):
        pass

    def close(self):
        self.closed = True
        if self.close_error:
            raise self.close_error


def configure_play(monkeypatch, *, machine_error=None, audio_error=None, save_error=None):
    FakeRecorder.instances = []
    FakeAudio.instances = []
    writes = []
    monkeypatch.setattr(frontend, "Machine", lambda rom, **_: FakeMachine(rom, run_error=machine_error))
    monkeypatch.setattr(frontend.artifacts, "Recorder", FakeRecorder)
    monkeypatch.setattr(frontend, "AudioOutput", lambda: FakeAudio(close_error=audio_error))

    def write_new(path, data):
        writes.append((path, data))
        if save_error:
            raise save_error

    monkeypatch.setattr(frontend.artifacts, "write_new", write_new)
    monkeypatch.setattr(frontend.time, "sleep", lambda _: None)
    return writes


def test_run_failure_keeps_valid_input_prefix_and_all_cleanup(monkeypatch):
    """A failed native segment saves only the last completed replay prefix."""
    pygame, calls = install_host(monkeypatch, batches=[[
        event(3, 18),  # F5 starts a recording.
        event(3, 13),  # Right is part of the valid prefix at tick 100.
    ]], quit_error=CleanupFailure("pygame"))
    writes = configure_play(
        monkeypatch,
        machine_error=RunFailure("run"),
        audio_error=CleanupFailure("audio"),
        save_error=SaveFailure("save"),
    )

    with pytest.raises(RunFailure, match="run") as raised:
        frontend.play(b"synthetic")

    recorder = FakeRecorder.instances[0]
    assert recorder.events == [{"tick": 100, "buttons": 8}]
    assert recorder.finish_calls == [{
        "machine_tick": FRAME_TICKS - 1,
        "terminal_status": "failed",
        "failure": {"type": "RunFailure", "message": "run"},
        "terminal_tick": 100,
    }]
    assert len(writes) == 1
    assert FakeAudio.instances[0].closed
    assert calls[-1] == "pygame.quit"
    if hasattr(raised.value, "add_note"):
        notes = "\n".join(raised.value.__notes__)
        assert "recording save" in notes
        assert "audio output" in notes
        assert "pygame" in notes
    assert pygame.K_F5 == 18


def test_save_failure_still_closes_audio_and_pygame(monkeypatch):
    """An automatic save failure cannot bypass independent host cleanup."""
    _, calls = install_host(monkeypatch, batches=[[event(1)]])
    configure_play(monkeypatch, save_error=SaveFailure("save"))

    with pytest.raises(SaveFailure, match="save"):
        frontend.play(b"synthetic", record_from_start=True)

    assert FakeRecorder.instances[0].finish_calls == [{
        "machine_tick": 100,
        "terminal_status": "completed",
        "failure": None,
        "terminal_tick": None,
    }]
    assert FakeAudio.instances[0].closed
    assert calls[-1] == "pygame.quit"
