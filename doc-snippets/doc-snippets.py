#!/usr/bin/env python3
"""doc-snippets — extract docstrings (and optionally comments) as JSON.

For a Python file or package, emits the module docstring plus each class/
function/method docstring with file:line. Optional `--comments` includes
non-trivial `#`-comments. Useful as a compact knowledge-base view of a
codebase that costs a fraction of the source.
"""
from __future__ import annotations
import argparse
import ast
import io
import json
import os
import sys
import tokenize
from pathlib import Path

DEFAULT_EXCLUDES = {".git", "__pycache__", ".venv", "venv", "node_modules",
                    "dist", "build", ".mypy_cache", ".pytest_cache"}


def walk_python(root: Path, excludes: set[str]):
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def docs_of(path: Path, root: Path, include_comments: bool):
    src = path.read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return {"path": str(path.relative_to(root)),
                "error": f"SyntaxError: {e.msg} (line {e.lineno})"}
    rel = str(path.relative_to(root))
    out: dict = {"path": rel, "items": []}
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        out["items"].append({"kind": "module", "line": 1, "doc": mod_doc.strip()})

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack: list[str] = []
        def _emit(self, n, kind):
            d = ast.get_docstring(n)
            if d:
                qn = ".".join(self.stack + [n.name])
                out["items"].append({"kind": kind, "name": qn,
                                     "line": n.lineno,
                                     "doc": d.strip()})
        def visit_FunctionDef(self, n):
            self._emit(n, "method" if self.stack else "function")
            self.stack.append(n.name)
            self.generic_visit(n)
            self.stack.pop()
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_ClassDef(self, n):
            self._emit(n, "class")
            self.stack.append(n.name)
            self.generic_visit(n)
            self.stack.pop()

    V().visit(tree)

    if include_comments:
        try:
            tokens = tokenize.tokenize(io.BytesIO(src.encode("utf-8")).readline)
            for tok in tokens:
                if tok.type == tokenize.COMMENT:
                    text = tok.string.lstrip("#").strip()
                    if len(text) >= 8 and not text.startswith(("type:", "noqa")):
                        out["items"].append({"kind": "comment",
                                             "line": tok.start[0],
                                             "doc": text})
        except (tokenize.TokenizeError, SyntaxError):
            pass

    out["items"].sort(key=lambda it: it["line"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="doc-snippets",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", nargs="?", default=".",
                    help="file or directory (default: .)")
    ap.add_argument("--comments", action="store_true",
                    help="also include non-trivial # comments (>= 8 chars)")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    p = Path(args.path).resolve()
    if not p.exists():
        print(json.dumps({"error": f"not found: {args.path}"}), file=sys.stderr)
        return 2
    root = p if p.is_dir() else p.parent
    excludes = DEFAULT_EXCLUDES | set(args.exclude)

    files = []
    total = 0
    errors = []
    for fp in walk_python(p, excludes):
        info = docs_of(fp, root, args.comments)
        if "error" in info:
            errors.append(info)
            continue
        if info["items"]:
            files.append(info)
            total += len(info["items"])

    out = {"root": str(root),
           "stats": {"files": len(files), "snippets": total},
           "files": files}
    if errors:
        out["parse_errors"] = errors
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
