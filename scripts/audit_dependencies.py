"""Report compiler-observed project/donor dependencies, not a guessed lock closure."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def audit(build, donor, ninja):
    raw = subprocess.check_output([str(ninja), "-C", str(build), "-t", "deps"], text=True)
    targets = subprocess.check_output([str(ninja), "-C", str(build), "-t", "targets", "all"], text=True)
    active = {line.split(": ", 1)[0] for line in targets.splitlines()}
    objects, current = {}, None
    for line in raw.splitlines():
        if match := re.match(r"(.+\.obj): #deps", line):
            current = match[1] if match[1] in active else None
            if current:
                objects[current] = []
        elif current and line.startswith("    "):
            path = Path(line.strip()).resolve()
            if path.is_relative_to(donor):
                objects[current].append("donor/" + path.relative_to(donor).as_posix())
            elif path.is_relative_to(ROOT):
                objects[current].append("project/" + path.relative_to(ROOT).as_posix())
    uses = {}
    for obj, paths in objects.items():
        for path in paths:
            uses.setdefault(path, set()).add("runtime" if "aladdin_native.dir/" in obj else "test")
    # Quote-include edges among the files the compiler actually reported.
    def resolve(name):
        return (donor if name.startswith("donor/") else ROOT) / name.split("/", 1)[1]
    reverse = {resolve(name).resolve(): name for name in uses}
    edges = []
    for name in sorted(uses):
        path = resolve(name)
        if not path.is_file():
            continue
        for included in re.findall(r'^\s*#\s*include\s*"([^"]+)"', path.read_text(errors="replace"), re.M):
            for base in (path.parent, donor, ROOT, build / "generated"):
                target = reverse.get((base / included).resolve())
                if target:
                    edges.append([name, target]); break
    return {"method": "Ninja compiler dependency records; quoted include edges resolved only among observed files",
            "objects": objects, "files": {name: sorted(scope) for name, scope in sorted(uses.items())},
            "include_edges": edges,
            "counts": {scope: sum(scope in uses[name] for name in uses) for scope in ("runtime", "test")}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", type=Path, default=ROOT / "build")
    p.add_argument("--donor", type=Path, required=True)
    p.add_argument("--ninja", type=Path, default=ROOT / ".venv/Scripts/ninja.exe")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = audit(args.build.resolve(), args.donor.resolve(), args.ninja.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report["counts"]))


if __name__ == "__main__":
    main()
