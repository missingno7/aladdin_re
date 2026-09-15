"""Gods (USA) on the shared Genesis machine: the exact revision, cold power-on, video, input, determinism.

Phase 1 evidence for the oracle/replay environment.  Nothing here is
recovered code; the game runs as the original.  The frame numbers below were
taken from a headless cold run of this revision (Mindscape logo by frame
240, the intro by 900, "GET READY" after Start at 900, level 1 by 1500).
"""
import hashlib

import pytest

from genesis_re.history import HistoryStore
from genesis_re.history_runtime import GenesisRun, Session
from gods_sega.profile import GODS, ROM_SHA256

pytestmark = pytest.mark.skipif(not GODS.rom_path.is_file(), reason="Gods (USA) cartridge is not under assets/")


def test_the_supported_revision_is_the_inspected_cartridge():
    data = GODS.read_rom()
    assert hashlib.sha256(data).hexdigest() == ROM_SHA256 == GODS.rom_sha256
    assert len(data) == GODS.rom_size == 1_048_576
    assert data[0x100:0x110] == b"SEGA GENESIS    "
    assert data[0x120:0x124] == b"GODS" and data[0x180:0x18E] == b"GM T87016  -00"
    assert data[0x1F0:0x1F1] == b"U" and int.from_bytes(data[4:8], "big") == 0x200
    assert GODS.profile_id == "gods-usa-ntsc-v1" and GODS.candidate is not None
    assert GODS.history_root["root"] == "gods-usa-new"


def test_cold_power_on_reaches_video_and_runs_the_sound_cpu():
    with GenesisRun(GODS, GODS.read_rom()) as run:
        run.advance(60, [])
        early = run.observable()
        assert early["vblanks"] >= 50 and early["z80_instructions"] > 0 and early["pcm_bytes"] > 0
        width, height, rgb = run.machine.frame()
        assert (width, height) == (320, 224)
        run.advance(240, [])
        _, _, logo = run.machine.frame()
        assert any(logo[i] | logo[i + 1] | logo[i + 2] for i in range(0, len(logo), 3))   # the Mindscape logo
        assert logo != rgb


def test_start_button_is_read_and_changes_the_trajectory():
    with GenesisRun(GODS, GODS.read_rom()) as idle:
        idle.advance(1500, [])
        untouched = idle.observable()
    with GenesisRun(GODS, GODS.read_rom()) as started:
        started.advance(1500, [{"frame": 900, "buttons": 128}, {"frame": 905, "buttons": 0}])
        pressed = started.observable()
    assert pressed["frame_sha256"] != untouched["frame_sha256"]
    assert pressed["state_sha256"] != untouched["state_sha256"]


def test_rerun_from_reset_reproduces_state_video_and_pcm():
    events = [{"frame": 900, "buttons": 128}, {"frame": 905, "buttons": 0}, {"frame": 1300, "buttons": 8}]
    results = []
    for _ in range(2):
        with GenesisRun(GODS, GODS.read_rom()) as run:
            per_frame = []
            run.advance(1400, events, lambda r: per_frame.append(r.observable()))
            results.append((per_frame, run.observable()))
    assert results[0] == results[1]
    assert results[0][1]["frame"] == 1400 and results[0][1]["buttons"] == 8


def test_snapshot_restore_does_not_change_the_continuation():
    events = [{"frame": 900, "buttons": 128}, {"frame": 905, "buttons": 0}]
    with GenesisRun(GODS, GODS.read_rom()) as run:
        run.advance(1000, events)
        saved = run.save()
        run.advance(1100, events)
        straight = run.observable()
        run.restore(saved)
        assert run.frame == 1000
        run.advance(1100, events)
        assert run.observable() == straight


def test_a_session_journals_gods_input_into_its_own_store_and_resumes(tmp_path):
    store = HistoryStore(tmp_path / "gods", GODS.history_root)
    with Session(GODS, store, GODS.read_rom()) as session:
        for frame in range(40):
            session.step(128 if 10 <= frame < 14 else 0)
        node = session.checkpoint(reason="manual", label="test")
        live = session.run.observable()
    assert store.flatten(node)["events"] == [{"frame": 10, "buttons": 128}, {"frame": 14, "buttons": 0}]
    with GenesisRun(GODS, GODS.read_rom()) as cold:          # one native machine per process: after the session
        cold.advance(40, store.flatten(node)["events"])
        assert cold.observable() == live
    with Session(GODS, store, GODS.read_rom(), node=node) as resumed:
        assert resumed.used_cache and resumed.frame == 40
        resumed.step(0)
    assert store.resolve("main") != node and store.node(store.resolve("main"))["parent"] == node


def test_a_deliberately_altered_input_diverges_detectably():
    """Replay confidence: the observation stream tells two histories apart from their first differing frame."""
    from genesis_re.verification import compare_observations
    streams = []
    for start in (900, 901):
        events = [{"frame": start, "buttons": 128}, {"frame": start + 5, "buttons": 0}]
        with GenesisRun(GODS, GODS.read_rom()) as run:
            per_frame = []
            run.advance(1000, events, lambda r: per_frame.append(r.observable()))
            streams.append(per_frame)
    first = next(i for i, (a, b) in enumerate(zip(*streams)) if a != b)
    assert first == 900                     # frame 901 is the first interval whose mask differs
    assert streams[0][-1]["state_sha256"] != streams[1][-1]["state_sha256"]
    observed = [[{"id": str(o["frame"]), "requested_tick": o["frame"], "actual_tick": o["tick"],
                  "state_sha256": o["state_sha256"], "frame_sha256": o["frame_sha256"],
                  "pcm_sha256": o["pcm_sha256"], "pcm_bytes": o["pcm_bytes"]} for o in stream] for stream in streams]
    verdict = compare_observations(*observed)
    assert not verdict["equal"] and verdict["last_matching_checkpoint"]["id"] == "900"
    assert verdict["first_failing_interval"]["to"]["reference"]["id"] == "901"


def test_fresh_processes_reconstruct_a_constructed_gods_history(tmp_path):
    """Two separate cold workers agree frame by frame on a constructed (not player-recorded) history."""
    from genesis_re.verification import compare_history
    store = HistoryStore(tmp_path / "gods", GODS.history_root)
    node = store.append(store.root_id, [{"frame": 900, "buttons": 128}, {"frame": 905, "buttons": 0}], 960)
    store.set_main(node)
    report = compare_history(GODS, store.path, GODS.rom_path, node=node, candidate="original",
                             output=tmp_path / "verify", timeout_seconds=300)
    assert report["status"] == "PASS", report.get("error")
    assert report["game"] == "gods" and report["comparison"]["equal"]
    assert report["reference"]["executed_frames"] == 960 and report["reference"]["implementation"]["game"] == "gods"
