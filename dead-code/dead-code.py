#!/usr/bin/env python3
"""dead-code — find Python definitions and imports that look unused.

Builds two sets across a project:
  • defined names: function, class, and top-level constant defs (with file:line)
  • referenced names: ast.Name reads + attribute names + string forms used in
    __all__, decorators, type-hint strings, and f-strings.

Reports definitions that are never referenced. Also reports per-file unused
imports. By design, this is a best-effort static check; dynamic access
(`getattr`, plugin registration, entry points) can produce false positives.
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
KEEP_NAMES = {"__init__", "__call__", "__enter__", "__exit__", "__repr__",
              "__str__", "__hash__", "__eq__", "__iter__", "__next__",
              "__len__", "__getitem__", "__setitem__", "__delitem__",
              "__contains__", "__new__", "main"}


def walk_python(root: Path, excludes: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def collect(path: Path, root: Path):
    src = path.read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return {}, set(), [], {"path": str(path.relative_to(root)),
                               "error": f"SyntaxError: {e.msg} (line {e.lineno})"}
    rel = str(path.relative_to(root))

    defined: dict[str, dict] = {}     # name -> {path, line, kind}
    references: set[str] = set()
    imports: list[dict] = []          # {name, line, module}

    # Top-level defs only — nested defs are usually local helpers
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.setdefault(node.name, {"path": rel, "line": node.lineno,
                                           "kind": "function"})
        elif isinstance(node, ast.ClassDef):
            defined.setdefault(node.name, {"path": rel, "line": node.lineno,
                                           "kind": "class"})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    defined.setdefault(t.id, {"path": rel, "line": node.lineno,
                                              "kind": "constant"})
        elif isinstance(node, ast.Import):
            for a in node.names:
                imports.append({"name": a.asname or a.name.split(".")[0],
                                "line": node.lineno, "module": a.name})
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    continue
                imports.append({"name": a.asname or a.name,
                                "line": node.lineno,
                                "module": (node.module or "")})

    # Collect references everywhere
    class V(ast.NodeVisitor):
        def visit_Name(self, n):
            if isinstance(n.ctx, ast.Load):
                references.add(n.id)
        def visit_Attribute(self, n):
            references.add(n.attr)
            self.generic_visit(n)
        def visit_Constant(self, n):
            if isinstance(n.value, str) and n.value.isidentifier():
                references.add(n.value)
    V().visit(tree)

    # __all__ keeps names
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "__all__":
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            references.add(elt.value)
    return defined, references, imports, None


def main() -> int:
    ap = argparse.ArgumentParser(prog="dead-code",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", nargs="?", default=".",
                    help="repo or package root (default: .)")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--keep-test-funcs", action="store_true",
                    help="skip names matching test_* (default: skip them)")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {args.path}"}),
              file=sys.stderr)
        return 2

    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    all_defs: dict[str, list[dict]] = {}
    all_refs: set[str] = set()
    unused_imports: list[dict] = []
    errors: list[dict] = []

    for fp in walk_python(root, excludes):
        defined, references, imports, err = collect(fp, root)
        if err:
            errors.append(err)
            continue
        for name, meta in defined.items():
            all_defs.setdefault(name, []).append(meta)
        all_refs |= references
        for imp in imports:
            if imp["name"] not in references:
                unused_imports.append({"path": str(fp.relative_to(root)),
                                       "line": imp["line"],
                                       "name": imp["name"],
                                       "module": imp["module"]})

    unused: list[dict] = []
    for name, metas in sorted(all_defs.items()):
        if name in all_refs or name in KEEP_NAMES:
            continue
        if name.startswith("__") and name.endswith("__"):
            continue
        if name.startswith("test_") and not args.keep_test_funcs:
            continue
        for m in metas:
            unused.append({"name": name, **m})

    out = {"root": str(root),
           "stats": {"unused_defs": len(unused),
                     "unused_imports": len(unused_imports)},
           "unused_defs": unused,
           "unused_imports": unused_imports}
    if errors:
        out["parse_errors"] = errors
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
