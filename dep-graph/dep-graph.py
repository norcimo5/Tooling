#!/usr/bin/env python3
"""dep-graph — inter-file import graph for a Python project as JSON.

Walks .py files, parses imports, and emits nodes (modules) and edges
(importer -> importee). Resolves relative imports to in-repo files when
possible; external imports are kept as leaf nodes only when --external is set.
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


def resolve_relative(curr_mod: str, level: int, name: str | None) -> str:
    parts = curr_mod.split(".") if curr_mod else []
    if level > len(parts):
        return name or ""
    base = parts[: len(parts) - level + 1] if level <= len(parts) else []
    # When `from . import x` at package root, level uses parent of module
    base = parts[: max(0, len(parts) - level + (1 if name else 0))]
    if name:
        return ".".join(base + [name])
    return ".".join(base)


def imports_from(tree: ast.Module, curr_mod: str):
    out: list[tuple[str, str]] = []  # (kind: absolute|relative, target)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(("absolute", a.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                target = resolve_relative(curr_mod, node.level, node.module)
                out.append(("relative", target))
            elif node.module:
                out.append(("absolute", node.module))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="dep-graph",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", help="Python package or repo directory")
    ap.add_argument("--external", action="store_true",
                    help="include external modules as leaf nodes")
    ap.add_argument("--exclude", action="append", default=[],
                    help="extra dir name to exclude (repeatable)")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {args.path}"}),
              file=sys.stderr)
        return 2

    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    files = list(walk_python(root, excludes))
    mod_to_file = {to_module(f, root): f for f in files}
    known = set(mod_to_file)

    modules = [{"id": m, "file": str(mod_to_file[m].relative_to(root))}
               for m in sorted(mod_to_file)]
    edges: list[dict] = []
    errors: list[dict] = []
    seen_external: set[str] = set()

    for f in files:
        curr = to_module(f, root)
        try:
            tree = ast.parse(f.read_text("utf-8", errors="replace"),
                             filename=str(f))
        except SyntaxError as e:
            errors.append({"path": str(f.relative_to(root)),
                           "error": f"SyntaxError: {e.msg} (line {e.lineno})"})
            continue
        for kind, target in imports_from(tree, curr):
            # Match the longest known prefix (e.g. "pkg.mod" matches "pkg.mod.x")
            resolved = None
            parts = target.split(".")
            for i in range(len(parts), 0, -1):
                cand = ".".join(parts[:i])
                if cand in known:
                    resolved = cand
                    break
            if resolved:
                edges.append({"from": curr, "to": resolved, "kind": kind,
                              "external": False})
            elif args.external:
                edges.append({"from": curr, "to": target, "kind": kind,
                              "external": True})
                seen_external.add(target)

    if args.external:
        for m in sorted(seen_external):
            modules.append({"id": m, "external": True})

    out = {"root": str(root), "modules": modules, "edges": edges,
           "stats": {"modules": len(mod_to_file), "edges": len(edges)}}
    if errors:
        out["parse_errors"] = errors
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
