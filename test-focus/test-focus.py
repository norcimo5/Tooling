#!/usr/bin/env python3
"""test-focus — locate a pytest test and the in-repo files it touches.

Given a test selector (`tests/test_foo.py::test_bar` or a bare function name),
finds the test definition and walks its imports up to --depth hops, returning
JSON of the test plus the in-repo files most relevant to debugging it.
"""
from __future__ import annotations
import argparse
import ast
import json
import os
import sys
from pathlib import Path

DEFAULT_EXCLUDES = {".git", "__pycache__", ".venv", "venv", "node_modules",
                    "dist", "build", ".mypy_cache", ".pytest_cache"}


def walk_python(root: Path, excludes: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def to_module(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def find_test(selector: str, root: Path, excludes: set[str]):
    if "::" in selector:
        file_str, func = selector.split("::", 1)
        path = (root / file_str).resolve()
        candidates = [path] if path.is_file() else []
    else:
        func = selector
        candidates = [p for p in walk_python(root, excludes)
                      if p.name.startswith("test_") or p.name.endswith("_test.py")]

    for f in candidates:
        try:
            tree = ast.parse(f.read_text("utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name == func:
                return f, node
    return None, None


def imports_of(tree: ast.Module):
    out = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(("absolute", a.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                out.append(("relative", (node.level, node.module or "")))
            elif node.module:
                out.append(("absolute", node.module))
    return out


def resolve(curr_mod: str, kind: str, target, known: set[str]) -> str | None:
    if kind == "absolute":
        parts = target.split(".")
        for i in range(len(parts), 0, -1):
            cand = ".".join(parts[:i])
            if cand in known:
                return cand
        return None
    level, name = target
    base = curr_mod.split(".") if curr_mod else []
    if level > len(base):
        return None
    prefix = base[: len(base) - level]
    candidate = ".".join(prefix + ([name] if name else []))
    return candidate if candidate in known else None


def main() -> int:
    ap = argparse.ArgumentParser(prog="test-focus",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("selector",
                    help="'tests/test_x.py::test_func' or bare 'test_func'")
    ap.add_argument("--path", default=".", help="repo root (default: .)")
    ap.add_argument("--depth", type=int, default=1,
                    help="import hops to follow (default 1)")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {args.path}"}),
              file=sys.stderr)
        return 2

    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    test_file, test_node = find_test(args.selector, root, excludes)
    if test_file is None:
        out = {"error": f"test not found: {args.selector}"}
        print(json.dumps(out, separators=(",", ":")))
        return 1

    files = list(walk_python(root, excludes))
    mod_to_file = {to_module(f, root): f for f in files}
    known = set(mod_to_file)

    visited: set[str] = set()
    frontier: list[Path] = [test_file]
    test_module = to_module(test_file, root)
    visited.add(test_module)
    direct_imports: list[str] = []

    for hop in range(args.depth):
        next_frontier: list[Path] = []
        for f in frontier:
            try:
                tree = ast.parse(f.read_text("utf-8", errors="replace"))
            except SyntaxError:
                continue
            curr_mod = to_module(f, root)
            for kind, target in imports_of(tree):
                resolved = resolve(curr_mod, kind, target, known)
                if hop == 0 and f == test_file:
                    label = target if kind == "absolute" else f"<rel>"
                    direct_imports.append(resolved or str(label))
                if resolved and resolved not in visited:
                    visited.add(resolved)
                    next_frontier.append(mod_to_file[resolved])
        frontier = next_frontier
        if not frontier:
            break

    touched = sorted(str(mod_to_file[m].relative_to(root))
                     for m in visited if m != test_module)
    out = {
        "query": args.selector,
        "test": {
            "file": str(test_file.relative_to(root)),
            "func": test_node.name,
            "line": test_node.lineno,
            "signature": f"{test_node.name}({ast.unparse(test_node.args)})",
        },
        "depth": args.depth,
        "imports": sorted(set(direct_imports)),
        "touched_files": touched,
    }
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
