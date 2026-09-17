"""perf_tracer: profile pathfacts.trace and factcheck check on retained fixtures (read-only research tooling).

    python scripts/research/perf_tracer.py --game gods --fixtures "artifacts/gods/evidence/census-006DA6/006DA6-entry-p*.state"
                                           [--planner gods_sega.boundary:state14_plan] [--limit 20] [--profile]

For each fixture: the wall time of ``pathfacts.trace`` (open a machine, restore,
single-step to the caller return with RAM tracked), the instruction count, the
per-instruction cost, the Python->native crossings per instruction
(``Machine.calls``), and -- with ``--planner`` -- the planner's own time and
crossings on the same fixture (what ``factcheck check`` and the fixture tests
pay per fixture).  ``--profile`` runs cProfile over one trace and prints the
top functions, so the per-step costs (the 64 KiB RAM copy and compare, the
disassembly, ``registers()``/``info`` calls, dict building) are attributed.
"""
from __future__ import annotations

import argparse
import cProfile
import glob
import importlib
import io
import json
import os
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("GENESIS_NATIVE_LIBRARY", str(ROOT / "build" / "libgenesis_native.dll"))

import pathfacts                                     # noqa: E402
from genesis_re.games import game as select_game    # noqa: E402
from genesis_re.machine import Machine               # noqa: E402


def _trace_with_calls(state, game, rom, stop_pc=None):
    """pathfacts.trace, but returning the machine's crossing counts too."""
    counts = {}
    with Machine(rom, game) as m:
        m.restore(state)
        m.gates([])
        tracer = pathfacts.Tracer(m, rom, natives=game.tracer_native_entries)
        for _ in range(20000):
            if tracer.at_exit(stop_pc):
                break
            tracer.step()
        else:
            raise RuntimeError("trace exceeded cap")
        facts = tracer.facts()
        counts = dict(m.calls)
    return facts, counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", default="gods")
    parser.add_argument("--fixtures", required=True, help="glob of .state fixtures")
    parser.add_argument("--planner", default=None, help="module:function; the plan's own time and crossings")
    parser.add_argument("--stop-from-plan", action="store_true", help="trace to the plan's continuation PC (a handoff region)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)
    game = select_game(args.game)
    rom = game.read_rom()
    fixtures = sorted(glob.glob(args.fixtures))[: args.limit]
    planner = None
    if args.planner:
        module, function = args.planner.split(":")
        planner = getattr(importlib.import_module(module), function)
    rows = []
    for fixture in fixtures:
        state = Path(fixture).read_bytes()
        stop = None
        plan_seconds = plan_calls = None
        if planner is not None:
            t = time.perf_counter()
            with Machine(rom, game) as m:
                m.restore(state)
                regs = m.registers()
                peeks = {"peek_ram": 0, "peek_ram_bytes": 0}
                original_peek = m.peek_ram

                def counted_peek(offset, size=1):
                    peeks["peek_ram"] += 1
                    peeks["peek_ram_bytes"] += size
                    return original_peek(offset, size)
                m.peek_ram = counted_peek
                t_plan = time.perf_counter()
                try:
                    plan = planner(m, regs)
                except Exception as error:      # UnsupportedCandidate or a planner refusal: still a cost
                    plan = None
                    declined = str(error)
                peeks["planner_only_seconds"] = round(time.perf_counter() - t_plan, 5)
                plan_calls = dict(m.calls)
                plan_calls.update(peeks)
            plan_seconds = time.perf_counter() - t
            if args.stop_from_plan and plan is not None:
                stop = getattr(plan, "registers", {}).get("pc") if not hasattr(plan, "prefix") else plan.prefix.registers.get("pc")
        t = time.perf_counter()
        facts, calls = _trace_with_calls(state, game, rom, stop)
        seconds = time.perf_counter() - t
        n = facts["instructions"] or 1
        rows.append({"fixture": Path(fixture).name, "instructions": facts["instructions"], "trace_seconds": round(seconds, 4),
                     "us_per_instruction": round(1e6 * seconds / n, 1),
                     "crossings_per_instruction": round(sum(v for k, v in calls.items() if k not in ("import", "destroy", "ram", "gates")) / n, 2),
                     "trace_calls": calls, "plan_seconds": None if plan_seconds is None else round(plan_seconds, 4),
                     "plan_calls": plan_calls})
    summary = {"fixtures": len(rows), "instructions_total": sum(r["instructions"] for r in rows),
               "trace_seconds_total": round(sum(r["trace_seconds"] for r in rows), 3),
               "us_per_instruction_mean": round(sum(r["us_per_instruction"] for r in rows) / max(1, len(rows)), 1),
               "plan_seconds_total": None if planner is None else round(sum(r["plan_seconds"] for r in rows), 3),
               "plan_calls_mean": None if planner is None else {
                   k: round(sum(r["plan_calls"].get(k, 0) for r in rows) / len(rows), 1)
                   for k in sorted({k for r in rows for k in r["plan_calls"]})}}
    report = {"game": game.id, "glob": args.fixtures, "planner": args.planner, "summary": summary, "rows": rows}
    if args.profile and fixtures:
        state = Path(fixtures[0]).read_bytes()
        profiler = cProfile.Profile()
        profiler.enable()
        pathfacts.trace(state, game=game)
        profiler.disable()
        out = io.StringIO()
        pstats.Stats(profiler, stream=out).sort_stats("cumulative").print_stats(28)
        report["profile_top"] = out.getvalue()
        out = io.StringIO()
        pstats.Stats(profiler, stream=out).sort_stats("tottime").print_stats(18)
        report["profile_tottime"] = out.getvalue()
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
