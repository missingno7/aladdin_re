"""Lints on the boundary module that stand in for defects the expensive tiers once caught.

On 17 September a tree run found 00364C's cost model corrupted because a
new region's cost constants reused another region's `_SC_` prefix and
rebound the names; the module is one namespace, so a second top-level
assignment silently wins.  A whole tree is the wrong instrument for that:
this test fails on any top-level name bound twice in `boundary.py` or
`recovery.py`.
"""
import ast
from pathlib import Path

import gods_sega


def _double_bindings(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    seen, doubled = {}, []
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            targets = [node.name]
        for name in targets:
            if name in seen:
                doubled.append((name, seen[name], node.lineno))
            seen[name] = node.lineno
    return doubled


def test_no_top_level_name_is_bound_twice_in_the_boundary_or_recovery_modules():
    package = Path(gods_sega.__file__).parent
    for module in ('boundary.py', 'recovery.py'):
        assert _double_bindings(package / module) == [], module
