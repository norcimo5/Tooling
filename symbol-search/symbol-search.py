#!/usr/bin/env python3
"""symbol-search — locate Python symbol definitions in a repo.

Walks .py files, parses with the AST, and returns JSON locations for any
function/class/method definitions whose name matches a literal substring or
regex. Useful as a deterministic, low-token alternative to grep for "where is
X defined?" — emits only the definition line, kind, and signature.
"""
from __future__ import annotations
import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "dist", "build", ".next", "target", ".idea", ".vscode", ".cache",
}


def signature(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = ast.unparse(node.args) if node.args else ""
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{prefix}{node.name}({args}){ret}"
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        return f"{node.name}({bases})" if bases else node.name
    return getattr(node, "name", "")


def walk_python(root: Path, excludes: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            if fn.endswith((".py", ".pyi")):
                yield Path(dirpath) / fn


def matcher(pattern: str, use_regex: bool, case: bool):
    if use_regex:
        flags = 0 if case else re.IGNORECASE
        rx = re.compile(pattern, flags)
        return lambda name: bool(rx.search(name))
    if case:
        return lambda name: pattern in name
    p = pattern.lower()
    return lambda name: p in name.lower()


def search_file(path: Path, root: Path, match, kinds: set[str]):
    try:
        tree = ast.parse(path.read_text("utf-8", errors="replace"))
    except (SyntaxError, OSError, ValueError) as e:
        return [{"path": str(path.relative_to(root)),
                 "error": f"parse: {type(e).__name__}"}]
    rel = str(path.relative_to(root))
    found = []
    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack: list[str] = []
        def _emit(self, node, kind):
            if kinds and kind not in kinds:
                return
            if not match(node.name):
                return
            found.append({
                "path": rel,
                "line": node.lineno,
                "kind": kind,
                "name": node.name,
                "signature": signature(node),
                "parent": self.stack[-1] if self.stack else None,
            })
        def visit_FunctionDef(self, node):
            self._emit(node, "method" if self.stack else "function")
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_ClassDef(self, node):
            self._emit(node, "class")
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()
    V().visit(tree)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(prog="symbol-search",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("name", help="substring (or regex with --regex) to match")
    ap.add_argument("--path", default=".", help="repo root (default: .)")
    ap.add_argument("--kind", action="append", default=[],
                    choices=["function", "method", "class"],
                    help="restrict to a kind (repeatable)")
    ap.add_argument("--regex", action="store_true", help="treat name as regex")
    ap.add_argument("--case", action="store_true", help="case-sensitive match")
    ap.add_argument("--exclude", action="append", default=[],
                    help="extra dir name to exclude (repeatable)")
    ap.add_argument("--limit", type=int, default=500,
                    help="hard cap on matches (default 500)")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {args.path}"}),
              file=sys.stderr)
        return 2

    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    match = matcher(args.name, args.regex, args.case)
    kinds = set(args.kind)

    matches = []
    errors = []
    truncated = False
    for fp in walk_python(root, excludes):
        for entry in search_file(fp, root, match, kinds):
            if "error" in entry:
                errors.append(entry)
                continue
            matches.append(entry)
            if len(matches) >= args.limit:
                truncated = True
                break
        if truncated:
            break

    out = {"query": args.name, "count": len(matches),
           "truncated": truncated, "matches": matches}
    if errors:
        out["parse_errors"] = errors
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
