"""Keep donor framework names and native snapshot layouts out of project Python,
and keep the shared layer free of game knowledge.

This is a small lexical/import guard, not a type-system or a full dependency
analyzer. Backend binding and execution receipts are explicit boundary owners.
The registry (``genesis_re/games.py``) is the one shared module allowed to
import a game package.
"""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SHARED = "genesis_re"
GAME_PACKAGES = ("aladdin_sega", "gods_sega")
BOUNDARY_OWNERS = {"machine.py", "receipt.py"}
FORBIDDEN = re.compile(
    r"pf::|GenesisRegionBoundary|genesis_session|port_forge|portforge|"
    r"PFGENS\d+|ALNAT\d+|authority_codec|admission_observer|"
    r"carrier_manifest|island_registry|verdict_record", re.IGNORECASE)
POLICY_MODULES = {"ctypes", "machine", "boundary", "recovery", "verification", "diagnostics", "artifacts", "frontend"}


def violations(source, *, filename, package=None):
    """``filename`` is relative to its package; ``package`` names it (a game package by default)."""
    if filename in BOUNDARY_OWNERS and package in (None, SHARED):
        return []
    shared_file = package == SHARED
    semantic_file = not shared_file and (filename == "recovered.py" or filename.startswith("game/"))
    tree = ast.parse(source, filename=filename)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            values = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom):
                values.append(node.module or "")
            if semantic_file and any(
                    value.split(".")[0] in POLICY_MODULES or value.split(".")[:2] == [SHARED, "machine"]
                    for value in values):
                findings.append(f"{filename}:{node.lineno}: recovered behavior imports policy/backend machinery")
            if shared_file and filename != "games.py" and any(
                    value.split(".")[0] in GAME_PACKAGES for value in values):
                findings.append(f"{filename}:{node.lineno}: shared infrastructure imports a game package")
        elif isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            values = [node.value.decode(errors="replace") if isinstance(node.value, bytes) else node.value]
        elif isinstance(node, ast.Name):
            values = [node.id]
            if semantic_file and node.id in {"AtomicPlan", "_logic_sr"}:
                findings.append(f"{filename}:{node.lineno}: semantic behavior constructs machine effects")
        elif isinstance(node, ast.Attribute):
            values = [node.attr]
        else:
            continue
        if any(FORBIDDEN.search(value) for value in values):
            findings.append(f"{filename}:{node.lineno}: donor framework or native codec leakage")
    return findings


def check(root=ROOT / "src"):
    findings = []
    for package in (SHARED, *GAME_PACKAGES):
        base = root / package
        for path in sorted(base.rglob("*.py")):
            findings += [f"{package}/{finding}" for finding in violations(
                path.read_text(encoding="utf-8"), filename=path.relative_to(base).as_posix(), package=package)]
    return findings


if __name__ == "__main__":
    errors = check()
    print("\n".join(errors) if errors else "Architecture boundary check passed")
    raise SystemExit(bool(errors))
