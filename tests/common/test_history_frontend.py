"""The frontend chooses immutable history nodes before opening a live session."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from genesis_re import frontend
from genesis_re import history
from genesis_re import history_runtime
from genesis_re.profile import GameProfile

GAME = GameProfile(id="test", title="Test Game", package="genesis_re", profile_id="test-v1",
                   rom_sha256="0" * 64, rom_size=1, rom_filename="test.md",
                   history_root={"format": "input-history-1", "root": "test-new", "clock": "simulation-frame",
                                 "input": "three-button-pad-1", "initial_buttons": 0})
OTHER = GameProfile(id="other", title="Other Game", package="genesis_re", profile_id="other-v1",
                    rom_sha256="1" * 64, rom_size=1, rom_filename="other.md",
                    history_root={"format": "input-history-1", "root": "other-new", "clock": "simulation-frame",
                                  "input": "three-button-pad-1", "initial_buttons": 0})


class _Window:
    def fill(self, *_):
        pass

    def blit(self, *_):
        pass


class _Font:
    def render(self, *_):
        return object()


def _pygame(monkeypatch):
    pygame = SimpleNamespace(
        QUIT=1, WINDOWFOCUSLOST=2, KEYDOWN=3, KEYUP=4,
        K_UP=10, K_DOWN=11, K_LEFT=12, K_RIGHT=13,
        K_x=14, K_c=15, K_z=16, K_RETURN=17,
        K_F5=18, K_F6=19, K_F7=20, K_F8=21,
        display=SimpleNamespace(init=lambda: None, set_mode=lambda _: _Window(), set_caption=lambda _: None, flip=lambda: None),
        font=SimpleNamespace(init=lambda: None, Font=lambda *_: _Font()),
        event=SimpleNamespace(get=lambda: []),
        image=SimpleNamespace(frombuffer=lambda *_: object()),
        transform=SimpleNamespace(scale=lambda picture, _: picture),
        quit=lambda: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "pygame", pygame)
    return pygame


class _Session:
    instances = []

    def __init__(self, game, store, rom, node=None):
        self.game, self.store, self.rom, self.node = game, store, rom, node
        self.machine = SimpleNamespace(frame=lambda: (1, 1, b"\0\0\0"))
        self.steps, self.checkpoints = [], []
        self.frame = 0
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, error_type, *_):
        if error_type is None:
            self.checkpoint("session_exit")

    def step(self, buttons):
        self.steps.append(buttons)
        self.frame += 1
        return b""

    def checkpoint(self, reason="manual", label=None):
        self.checkpoints.append((reason, label))
        return "a" * 64


class _Store:
    root_id = "root"
    instances = []

    def __init__(self, path, root=None):
        self.path, self.root = path, root
        self.__class__.instances.append(self)

    def resolve(self, ref="main"):
        return "main-node" if ref == "main" else ref

    def nodes(self):
        return {"root": {"parent": None, "end_frame": 0},
                "main-node": {"parent": "root", "end_frame": 3}}

    def metadata(self, _):
        return {}


def _install_runtime(monkeypatch):
    _Session.instances = []
    _Store.instances = []
    monkeypatch.setattr(history, "HistoryStore", _Store)
    monkeypatch.setattr(history_runtime, "Session", _Session)
    monkeypatch.setattr(frontend, "AudioOutput", lambda: None)
    monkeypatch.setattr(frontend.time, "sleep", lambda _: None)


def test_frame_automation_bypasses_timeline_and_chooses_cold_root(monkeypatch, tmp_path):
    _pygame(monkeypatch)
    _install_runtime(monkeypatch)

    frontend.play(GAME, b"rom", frames=1, history_path=tmp_path / "history", mute=True)

    session = _Session.instances[0]
    assert session.node is None
    assert session.game is GAME
    assert session.steps == [0]
    assert session.checkpoints == [("session_exit", None)]


def test_history_store_defaults_to_the_games_own_directory_and_root(monkeypatch, tmp_path):
    _pygame(monkeypatch)
    _install_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)

    frontend.play(GAME, b"rom", frames=1, mute=True)

    store = _Store.instances[0]
    assert store.path == Path("history") / "test"
    assert store.root == GAME.history_root
    assert store.root != OTHER.history_root


def test_automation_without_a_game_is_refused(monkeypatch, tmp_path):
    _pygame(monkeypatch)
    _install_runtime(monkeypatch)
    with pytest.raises(ValueError, match="explicit game"):
        frontend.play(None, frames=1, mute=True)
    assert _Session.instances == []


def test_game_chooser_returns_the_clicked_game(monkeypatch):
    pygame = _pygame(monkeypatch)
    pygame.MOUSEBUTTONDOWN = 9
    games = {GAME.id: GAME, OTHER.id: OTHER}
    layout = frontend._game_layout(games, width=960)
    left, top, width, height = layout[OTHER.id]
    pygame.event.get = lambda: [SimpleNamespace(type=9, button=1, pos=(left + width // 2, top + height // 2))]
    monkeypatch.setattr(frontend.time, "sleep", lambda _: None)

    assert frontend._choose_game(pygame, _Window(), _Font(), games) is OTHER

    pygame.event.get = lambda: [SimpleNamespace(type=pygame.QUIT)]
    assert frontend._choose_game(pygame, _Window(), _Font(), games) is None


def test_closing_the_game_chooser_opens_no_session(monkeypatch, tmp_path):
    pygame = _pygame(monkeypatch)
    _install_runtime(monkeypatch)
    pygame.event.get = lambda: [SimpleNamespace(type=pygame.QUIT)]

    frontend.play(None)

    assert _Session.instances == []
    assert _Store.instances == []


def test_resumed_history_releases_held_input_on_its_next_step(monkeypatch, tmp_path):
    _pygame(monkeypatch)
    _install_runtime(monkeypatch)

    frontend.play(GAME, b"rom", frames=1, history_path=tmp_path / "history", node="prior", mute=True)

    session = _Session.instances[0]
    assert session.node == "prior"
    assert session.steps == [0]


def test_history_layout_scales_time_and_splits_only_at_branch_nodes():
    nodes = {
        "root": {"parent": None, "end_frame": 0},
        "shared": {"parent": "root", "end_frame": 4},
        "left": {"parent": "shared", "end_frame": 8},
        "right": {"parent": "shared", "end_frame": 12},
    }

    layout = frontend._history_layout(nodes, "root", width=960, height=736)

    assert layout["root"][0] < layout["shared"][0] < layout["left"][0] < layout["right"][0]
    assert layout["root"][1] == layout["shared"][1] == layout["left"][1]
    assert layout["right"][1] > layout["shared"][1]


def test_timeline_new_button_selects_a_cold_start(monkeypatch):
    pygame = _pygame(monkeypatch)
    pygame.MOUSEBUTTONDOWN = 9
    pygame.event.get = lambda: [SimpleNamespace(type=9, button=1, pos=(20, 20))]
    monkeypatch.setattr(frontend.time, "sleep", lambda _: None)

    selected, cold = frontend._choose_history(pygame, _Window(), _Font(), _Store("unused"), GAME)

    assert selected is None
    assert cold is True


def test_timeline_checkpoint_marker_starts_that_checkpoint(monkeypatch):
    pygame = _pygame(monkeypatch)
    pygame.MOUSEBUTTONDOWN = 9
    store = _Store("unused")
    point = frontend._history_layout(store.nodes(), store.root_id, width=960, height=736)["main-node"]
    pygame.event.get = lambda: [SimpleNamespace(type=9, button=1, pos=point)]
    monkeypatch.setattr(frontend.time, "sleep", lambda _: None)

    selected, cold = frontend._choose_history(pygame, _Window(), _Font(), store, GAME)

    assert selected == "main-node"
    assert cold is False


def test_session_failure_still_closes_audio_and_pygame(monkeypatch, tmp_path):
    class StepFailure(RuntimeError):
        pass

    class CleanupFailure(RuntimeError):
        pass

    pygame = _pygame(monkeypatch)
    calls = []
    def quit():
        calls.append("pygame")
        raise CleanupFailure("pygame")
    pygame.quit = quit

    class FailingSession(_Session):
        def step(self, buttons):
            raise StepFailure("step")

    class Audio:
        def __init__(self):
            self.closed = False

        def push(self, _):
            pass

        def close(self):
            self.closed = True
            raise CleanupFailure("audio")

    _install_runtime(monkeypatch)
    monkeypatch.setattr(history_runtime, "Session", FailingSession)
    created = []
    monkeypatch.setattr(frontend, "AudioOutput", lambda: created.append(Audio()) or created[-1])
    with pytest.raises(StepFailure, match="step") as raised:
        frontend.play(GAME, b"rom", frames=1, history_path=tmp_path / "history")

    assert created[0].closed
    assert calls == ["pygame"]
    if hasattr(raised.value, "add_note"):
        notes = "\n".join(raised.value.__notes__)
        assert "audio output" in notes
        assert "pygame" in notes


def test_pause_before_first_frame_does_not_read_unconfigured_vdp(monkeypatch, tmp_path):
    pygame = _pygame(monkeypatch)
    _install_runtime(monkeypatch)
    events = iter([[SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_F7)],
                   [SimpleNamespace(type=pygame.QUIT)]])
    pygame.event.get = lambda: next(events)

    class ColdSession(_Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.machine.frame = lambda: pytest.fail('VDP not initialized at cold root')

    monkeypatch.setattr(history_runtime, 'Session', ColdSession)
    frontend.play(GAME, b'rom', new=True, mute=True, history_path=tmp_path)
    assert _Session.instances[0].steps == []
    assert _Session.instances[0].checkpoints == [('session_exit', None)]
