"""Synthetic host events exercise the actual pygame capture bindings."""
import json

import pytest

from aladdin_sega import artifacts as a
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom


@pytest.mark.skipif(not DEFAULT_ROM.exists(), reason="Local user ROM unavailable")
def test_capture_hotkeys_and_focus_release(tmp_path, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    from aladdin_sega.frontend import play
    rom = read_rom()
    monkeypatch.chdir(tmp_path)
    def down(key): return pygame.event.Event(pygame.KEYDOWN, key=key)
    batches = iter([
        [down(pygame.K_F5), down(pygame.K_RIGHT)],
        [down(pygame.K_F6), down(pygame.K_F7), down(pygame.K_F9)],
        [pygame.event.Event(pygame.WINDOWFOCUSLOST), down(pygame.K_F8)],
        [down(pygame.K_F5), pygame.event.Event(pygame.QUIT)],
    ])
    monkeypatch.setattr(pygame.event, "get", lambda: next(batches))
    play(rom, origin="synthetic")
    files = list((tmp_path / "recordings").glob("*.alreplay"))
    assert len(files) == 1
    assert len(list((tmp_path / "recordings").glob("*.alsnap"))) == 1
    with Machine(rom) as m:
        meta, initial, events = a.load_replay(files[0].read_bytes(), rom_sha256=m.rom_sha256, source_id=m.source_id)
        assert meta["origin"] == "synthetic"
        assert [e["buttons"] for e in events] == [8, 0]
        a.restore_snapshot(m, initial)
        a.play_events(m, events, meta["terminal_tick"])
        assert m.info["buttons"] == 0


@pytest.mark.skipif(not DEFAULT_ROM.exists(), reason="Local user ROM unavailable")
def test_resume_snapshot_records_anchor_and_releases_stale_buttons(tmp_path, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    from aladdin_sega.frontend import play
    from aladdin_sega.profile import FRAME_TICKS
    rom = read_rom()
    with Machine(rom) as m:
        m.run(target=FRAME_TICKS * 3)
        m.pad(8)
        expected_anchor = m.snapshot()
        start = m.info["tick"]
        saved = a.snapshot_bytes(m)
    path = tmp_path / "resume.alsnap"
    path.write_bytes(saved)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pygame.event, "get", lambda: [])
    play(rom, frames=1, origin="synthetic", snapshot=path, record_from_start=True)
    assert path.read_bytes() == saved
    capture = next((tmp_path / "recordings").glob("*.alreplay"))
    with Machine(rom) as m:
        meta, initial, events = a.load_replay(capture.read_bytes(), rom_sha256=m.rom_sha256, source_id=m.source_id)
        a.restore_snapshot(m, initial)
        assert m.snapshot() == expected_anchor
        assert meta["reset_provenance"] == "snapshot-resume"
        assert events == [{"tick": start, "seq": 0, "kind": "pad_state", "port": 0, "buttons": 0}]
        a.play_events(m, events, meta["terminal_tick"])
        assert m.info["tick"] > start
        assert m.info["buttons"] == 0


@pytest.mark.skipif(not DEFAULT_ROM.exists(), reason="Local user ROM unavailable")
@pytest.mark.parametrize("stop_key", [True, False], ids=["f5", "close-window"])
def test_record_from_reset_before_first_input(tmp_path, monkeypatch, stop_key):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    from aladdin_sega.frontend import play
    rom = read_rom()
    monkeypatch.chdir(tmp_path)
    ending = [pygame.event.Event(pygame.QUIT)]
    if stop_key:
        ending.insert(0, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F5))
    batches = iter([
        [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)],
        [pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT)],
        ending,
    ])
    monkeypatch.setattr(pygame.event, "get", lambda: next(batches))
    play(rom, origin="synthetic", record_from_start=True)
    files = list((tmp_path / "recordings").glob("*.alreplay"))
    assert len(files) == 1
    with Machine(rom) as m:
        reset = m.snapshot()
        meta, initial, events = a.load_replay(files[0].read_bytes(), rom_sha256=m.rom_sha256, source_id=m.source_id)
        assert meta["reset_provenance"] == "cold-boot"
        assert events[0]["tick"] == 0
        assert [e["buttons"] for e in events] == [8, 0]
        a.restore_snapshot(m, initial)
        assert m.snapshot() == reset
        assert m.info["tick"] == m.info["m68k_instructions"] == 0
        a.play_events(m, events, meta["terminal_tick"])
        assert m.info["m68k_instructions"] > 0
        assert m.info["buttons"] == 0
