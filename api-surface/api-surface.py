#!/usr/bin/env python3
"""api-surface — extract the public API of a Python file or package.

For each module: public (non-`_`-prefixed) classes (with public methods) and
functions, with signatures and docstring first-line. If `__all__` is present
it overrides the public/private convention. Use this to give an LLM a
package's *interface* without dumping thousands of lines of implementation.
"""
from __future__ import annotations
import argparse
import ast
import json
import os
import sys
from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", "dist", "build",
}


def signature(node) -> str:
    args = ast.unparse(node.args) if node.args else ""
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({args}){ret}"


def doc_first(node) -> str | None:
    doc = ast.get_docstring(node)
    return doc.strip().split("\n", 1)[0].strip() if doc else None


def extract_all(tree: ast.Module) -> set[str] | None:
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "__all__":
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    names = set()
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            names.add(elt.value)
                    return names
    return None


def is_public(name: str, allow: set[str] | None) -> bool:
    if allow is not None:
        return name in allow
    return not name.startswith("_") or name in ("__init__", "__call__")


def class_api(node: ast.ClassDef) -> dict:
    methods = []
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if is_public(child.name, None):
                m = {"name": child.name, "signature": signature(child),
                     "line": child.lineno}
                d = doc_first(child)
                if d:
                    m["doc"] = d
                methods.append(m)
    entry: dict = {"name": node.name, "line": node.lineno,
                   "bases": [ast.unparse(b) for b in node.bases],
                   "methods": methods}
    d = doc_first(node)
    if d:
        entry["doc"] = d
    return entry


def module_api(path: Path, root: Path) -> dict:
    src = path.read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return {"path": str(path.relative_to(root)),
                "error": f"SyntaxError: {e.msg} (line {e.lineno})"}
    allow = extract_all(tree)
    classes = [class_api(n) for n in tree.body
               if isinstance(n, ast.ClassDef) and is_public(n.name, allow)]
    functions = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and is_public(n.name, allow):
            f = {"name": n.name, "signature": signature(n), "line": n.lineno}
            d = doc_first(n)
            if d:
                f["doc"] = d
            functions.append(f)
    out: dict = {"path": str(path.relative_to(root)),
                 "module_doc": doc_first(tree),
                 "classes": classes, "functions": functions}
    if allow is not None:
        out["__all__"] = sorted(allow)
    if out["module_doc"] is None:
        out.pop("module_doc")
    return out


def walk_python(root: Path, excludes: set[str]):
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def main() -> int:
    ap = argparse.ArgumentParser(prog="api-surface",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", help="Python file or package directory")
    ap.add_argument("--exclude", action="append", default=[],
                    help="extra dir name to exclude (repeatable)")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    p = Path(args.path).resolve()
    if not p.exists():
        print(json.dumps({"error": f"not found: {args.path}"}), file=sys.stderr)
        return 2

    root = p if p.is_dir() else p.parent
    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    modules = [module_api(fp, root) for fp in walk_python(p, excludes)]
    out = {"root": str(root), "modules": modules,
           "count": len(modules)}
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
