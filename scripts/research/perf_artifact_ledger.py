"""perf_artifact_ledger: wall-time and evidence tables from the existing artifacts (read-only research tooling).

    python scripts/research/perf_artifact_ledger.py [--out artifacts/gods/research/perf]

No machine is opened.  Reads every ``artifacts/gods/verify-*/comparison.json``
(wall time from the directory's creation time to the report's mtime; the
reference and candidate workers' own finish times from ``reference.json`` /
``candidate.json``), every ``artifacts/gods/evidence/census-*/report.json``
(``seconds`` / ``replay_seconds``) and ``index.json`` (the first frame each
path class is seen), and writes four CSVs plus a JSON summary:

  verify-runs.csv     one row per verification directory
  census-runs.csv     one row per census directory
  tree-refusals.csv   the adapter-refusal classes of every camera-sprites tree run, in order
  mutants.csv         the first-difference frame of every mutant run

The summary carries the totals the throughput report quotes (hours of
verification, hours of reference re-execution, frames executed past a
mutant's first difference, the prefix before a region's first occurrence).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ("z80 bank guard", "observation deadline", "vblank in span", "machine admission")


def verify_rows():
    rows = []
    for d in sorted(Path(ROOT / "artifacts/gods").glob("verify-*")):
        c = d / "comparison.json"
        if not c.exists():
            continue
        r = json.loads(c.read_text(encoding="utf-8"))
        start, end = os.stat(d).st_ctime, os.stat(c).st_mtime
        ref, cand = d / "reference.json", d / "candidate.json"
        cr = r.get("candidate_receipt") or {}
        st = cr.get("candidate_stats") or {}
        first = (r.get("comparison") or {}).get("first_difference") or {}
        rows.append({"dir": d.name, "status": r.get("status"), "tree": bool(r.get("tree")), "candidate": r.get("candidate"),
                     "node": (r.get("history_id") or "")[:12], "frames": cr.get("executed_frames"),
                     "hits": st.get("candidate_hits"), "fallbacks": st.get("fallbacks"),
                     "wall_s": round(end - start, 1),
                     "reference_s": round(os.stat(ref).st_mtime - start, 1) if ref.exists() else None,
                     "candidate_s": round(os.stat(cand).st_mtime - start, 1) if cand.exists() else None,
                     "first_difference_frame": ((first.get("reference") or {}).get("frame")),
                     "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start)),
                     "fallback_reasons": json.dumps(st.get("fallback_reasons", {}), sort_keys=True)})
    return rows


def census_rows():
    rows = []
    for d in sorted(Path(ROOT / "artifacts/gods/evidence").glob("census-*")):
        r = d / "report.json"
        if not r.exists():
            continue
        j = json.loads(r.read_text(encoding="utf-8"))
        first = all_seen = None
        idx = d / "index.json"
        if idx.exists():
            rows_ = json.loads(idx.read_text(encoding="utf-8")).get("rows", [])
            if rows_:
                first = min(x["first_frame"] for x in rows_)
                all_seen = max(x["first_frame"] for x in rows_)
        rows.append({"dir": d.name, "node": j["history_id"][:12], "frames": j["end_frame"],
                     "occurrences": sum(j["counts"].values()),
                     "classes": sum(c.get("distinct", 0) for c in j.get("classes", {}).values()),
                     "fixtures": len(list(d.glob("*.state"))), "seconds": j.get("seconds"), "replay_seconds": j.get("replay_seconds"),
                     "first_frame": first, "all_classes_seen_frame": all_seen})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(ROOT / "artifacts/gods/research/perf"))
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    verify, census = verify_rows(), census_rows()
    for name, rows in (("verify-runs.csv", verify), ("census-runs.csv", census)):
        with (out / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    trees = [r for r in verify if r["tree"] and r["candidate"] == "camera-sprites" and r["hits"] is not None]
    with (out / "tree-refusals.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["dir", "hits", "fallbacks", *ADAPTER, "seam deadline", "declined arms", "wall_s", "reference_s"])
        for r in sorted(trees, key=lambda r: r["started"]):
            reasons = json.loads(r["fallback_reasons"])
            declined = sum(v for k, v in reasons.items() if k.startswith("unsupported"))
            writer.writerow([r["dir"], r["hits"], r["fallbacks"], *[reasons.get(k, 0) for k in ADAPTER], reasons.get("seam deadline", 0), declined, r["wall_s"], r["reference_s"]])
    mutants = [r for r in verify if "mutant" in (r["candidate"] or "")]
    with (out / "mutants.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dir", "status", "frames", "first_difference_frame", "wall_s"])
        writer.writeheader()
        writer.writerows([{k: r[k] for k in writer.fieldnames} for r in mutants])
    diverged = [r for r in mutants if r["first_difference_frame"]]
    prefix = [c["first_frame"] / c["frames"] for c in census if c["first_frame"]]
    summary = {
        "verify_runs": len(verify), "tree_runs": len([r for r in verify if r["tree"]]),
        "verification_wall_hours": round(sum(r["wall_s"] for r in verify) / 3600, 2),
        "tree_wall_hours": round(sum(r["wall_s"] for r in verify if r["tree"]) / 3600, 2),
        "reference_worker_hours": round(sum(r["reference_s"] or 0 for r in verify) / 3600, 2),
        "mutant_runs": len(mutants), "mutant_wall_hours": round(sum(r["wall_s"] for r in mutants) / 3600, 2),
        "mutant_frames_after_first_difference_share": round(sum(r["frames"] - r["first_difference_frame"] for r in diverged) / max(1, sum(r["frames"] for r in diverged)), 3),
        "mutant_first_difference_median_fraction": round(statistics.median(r["first_difference_frame"] / r["frames"] for r in diverged), 3),
        "census_runs": len(census), "census_hours": round(sum(c["seconds"] or 0 for c in census) / 3600, 2),
        "census_replay_share": round(sum(c["replay_seconds"] or 0 for c in census) / max(1, sum(c["seconds"] or 0 for c in census)), 3),
        "prefix_before_first_occurrence_median": round(statistics.median(prefix), 3),
        "identical_reference_runs_by_node": {},
    }
    by_node = {}
    for r in verify:
        if r["reference_s"] and not r["tree"]:
            by_node.setdefault(r["node"], []).append(r["reference_s"])
    summary["identical_reference_runs_by_node"] = {k: {"runs": len(v), "median_s": statistics.median(v)} for k, v in by_node.items()}
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
