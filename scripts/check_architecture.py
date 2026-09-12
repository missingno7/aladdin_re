"""Keep donor framework names and native snapshot layouts out of project Python.

This is a small lexical/import guard, not a type-system or a full dependency
analyzer. Backend binding and execution receipts are explicit boundary owners.
"""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_OWNERS = {"machine.py", "receipt.py"}
FORBIDDEN = re.compile(
    r"pf::|GenesisRegionBoundary|genesis_session|port_forge|portforge|"
    r"PFGENS\d+|ALNAT\d+|authority_codec|admission_observer|"
    r"carrier_manifest|island_registry|verdict_record", re.IGNORECASE)


def violations(source, *, filename):
    if filename in BOUNDARY_OWNERS:
        return []
    tree = ast.parse(source, filename=filename)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            values = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom):
                values.append(node.module or "")
            if filename == "recovered.py" and any(
                    value.split(".")[0] in {"ctypes", "machine", "recovery", "verification", "artifacts", "frontend"}
                    for value in values):
                findings.append(f"{filename}:{node.lineno}: recovered behavior imports policy/backend machinery")
        elif isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            values = [node.value.decode(errors="replace") if isinstance(node.value, bytes) else node.value]
        elif isinstance(node, ast.Name):
            values = [node.id]
        elif isinstance(node, ast.Attribute):
            values = [node.attr]
        else:
            continue
        if any(FORBIDDEN.search(value) for value in values):
            findings.append(f"{filename}:{node.lineno}: donor framework or native codec leakage")
    return findings


def check(root=ROOT / "src/aladdin_sega"):
    return [finding for path in sorted(root.glob("*.py"))
            for finding in violations(path.read_text(encoding="utf-8"), filename=path.name)]


if __name__ == "__main__":
    errors = check()
    print("\n".join(errors) if errors else "Architecture boundary check passed")
    raise SystemExit(bool(errors))
