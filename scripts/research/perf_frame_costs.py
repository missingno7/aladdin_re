"""perf_frame_costs: where a replay frame's wall time goes (read-only research tooling).

    python scripts/research/perf_frame_costs.py --game gods --node fb408bc75597 --frames 600 [--candidate camera-sprites]
                                                [--skip 0] [--json artifacts/gods/research/perf/frame-costs.json]

Replays the first ``--frames`` frames of one history node exactly as the
verification worker does (``GenesisRun.advance`` with the recorded events),
three ways in one process, and reports the per-frame cost of each layer:

  bare       ``advance`` without an observer (what recovery_census pays per frame)
  observed   ``advance`` with ``observable()`` per frame (what history-run / history-verify pay)
  parts      the observation decomposed: native ``export`` (snapshot encode + two
             native SHA-256 passes), the Python SHA-256 of the snapshot, the frame
             render + copy, its SHA-256, the PCM drain + chained digest, and the
             ``info`` reads

Also reports the snapshot size, the bytes hashed per frame, and the
Python->native crossings per frame (``Machine.calls``).  One native machine per
process; the measurement restores a saved state between passes so all three
cover the same frames.  Timings are wall-clock ``perf_counter`` and are
disturbed by concurrent load on the machine: the report records the load.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("GENESIS_NATIVE_LIBRARY", str(ROOT / "build" / "libgenesis_native.dll"))

from genesis_re.games import game as select_game          # noqa: E402
from genesis_re.history import HistoryStore, digest         # noqa: E402
from genesis_re.history_runtime import GenesisRun          # noqa: E402


def _calls_delta(before, after):
    return {k: after.get(k, 0) - before.get(k, 0) for k in set(before) | set(after) if after.get(k, 0) != before.get(k, 0)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", default="gods")
    parser.add_argument("--node", default="main")
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--skip", type=int, default=0, help="frames to replay (bare) before measuring")
    parser.add_argument("--candidate", default="original")
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    game = select_game(args.game)
    rom = game.read_rom()
    store = HistoryStore(game.history_path(), game.history_root)
    path = store.flatten(store.resolve(args.node))
    events = path["events"]
    report = {"game": game.id, "node": path["history_id"], "frames": args.frames, "skip": args.skip,
              "candidate": args.candidate, "cpu_count": os.cpu_count()}

    t0 = time.perf_counter()
    run = GenesisRun(game, rom, args.candidate)
    report["startup_seconds"] = round(time.perf_counter() - t0, 3)
    with run:
        m = run.machine
        if args.skip:
            run.advance(args.skip, events)
        saved = run.save()
        report["snapshot_bytes"] = len(saved[0])
        end = args.skip + args.frames

        # pass 1: bare replay
        before = dict(m.calls)
        t = time.perf_counter()
        run.advance(end, events)
        bare = time.perf_counter() - t
        report["bare"] = {"seconds": round(bare, 3), "ms_per_frame": round(1000 * bare / args.frames, 3),
                          "fps": round(args.frames / bare, 1), "calls_per_frame": {k: round(v / args.frames, 2) for k, v in _calls_delta(before, m.calls).items()}}
        stats_bare = dict(run.candidate.stats) if run.candidate else None

        # pass 2: observed replay (what a verification worker does)
        run.restore(saved)
        before = dict(m.calls)
        observations = []
        t = time.perf_counter()
        run.advance(end, events, lambda r: observations.append(r.observable()))
        observed = time.perf_counter() - t
        report["observed"] = {"seconds": round(observed, 3), "ms_per_frame": round(1000 * observed / args.frames, 3),
                              "fps": round(args.frames / observed, 1), "calls_per_frame": {k: round(v / args.frames, 2) for k, v in _calls_delta(before, m.calls).items()}}
        report["observation_overhead_ms_per_frame"] = round(1000 * (observed - bare) / args.frames, 3)
        report["observation_share_of_observed"] = round((observed - bare) / observed, 3)
        if run.candidate:
            report["candidate_stats"] = {k: v for k, v in run.candidate.stats.items() if not isinstance(v, dict)}

        # pass 3: the observation decomposed, on the same frames, timing each part separately
        run.restore(saved)
        parts = {"export": 0.0, "sha_snapshot": 0.0, "frame_render": 0.0, "sha_frame": 0.0, "audio": 0.0, "sha_pcm": 0.0, "info": 0.0}
        hashed = {"snapshot": 0, "frame": 0, "pcm": 0}
        frame_bytes = [0]

        def decompose(r):
            t = time.perf_counter(); snap = r.machine.snapshot(); parts["export"] += time.perf_counter() - t
            t = time.perf_counter(); hashlib.sha256(snap).hexdigest(); parts["sha_snapshot"] += time.perf_counter() - t
            hashed["snapshot"] += len(snap)
            t = time.perf_counter(); _, _, rgb = r.machine.frame(); parts["frame_render"] += time.perf_counter() - t
            t = time.perf_counter(); hashlib.sha256(rgb).hexdigest(); parts["sha_frame"] += time.perf_counter() - t
            hashed["frame"] += len(rgb); frame_bytes[0] = len(rgb)
            t = time.perf_counter(); r.machine.info; parts["info"] += time.perf_counter() - t

        # the PCM drain and its chained digest happen inside step(); time them by wrapping
        original_audio = m.audio
        pcm_total = [0]

        def timed_audio():
            t = time.perf_counter(); pcm = original_audio(); parts["audio"] += time.perf_counter() - t
            pcm_total[0] += len(pcm)
            return pcm
        m.audio = timed_audio
        original_digest = digest

        t = time.perf_counter()
        run.advance(end, events, decompose)
        decomposed = time.perf_counter() - t
        m.audio = original_audio
        # the chained PCM digest: bytes.fromhex(prev) + pcm hashed per frame (~pcm bytes + 32)
        t = time.perf_counter()
        prev = digest(b"")
        for _ in range(args.frames):
            prev = digest(bytes.fromhex(prev) + b"\0" * (pcm_total[0] // args.frames))
        parts["sha_pcm"] = time.perf_counter() - t
        report["parts_ms_per_frame"] = {k: round(1000 * v / args.frames, 3) for k, v in parts.items()}
        report["parts_total_ms_per_frame"] = round(1000 * sum(parts.values()) / args.frames, 3)
        report["decomposed_pass_ms_per_frame"] = round(1000 * decomposed / args.frames, 3)
        report["bytes_hashed_per_frame"] = {"snapshot_python": hashed["snapshot"] // args.frames,
                                            "snapshot_native_two_passes": 2 * hashed["snapshot"] // args.frames,
                                            "frame": hashed["frame"] // args.frames, "pcm": pcm_total[0] // args.frames}
        report["bytes_hashed_per_frame"]["total"] = sum(report["bytes_hashed_per_frame"].values())
        report["hash_mb_per_second_at_observed_fps"] = round(report["bytes_hashed_per_frame"]["total"] * report["observed"]["fps"] / 1e6, 1)
        report["observations_equal_between_passes"] = all(
            o["state_sha256"] == observations[i]["state_sha256"] for i, o in enumerate(observations))
    print(json.dumps(report, indent=1))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
