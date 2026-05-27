#!/usr/bin/env python3
"""call-graph — static function-call graph for Python file(s) as JSON.

Walks Python AST(s) and emits each function/method as a node and each call
site as an edge. Resolution is best-effort and name-based (callee = the last
attribute or name in the call); Python is too dynamic for sound static
resolution, but the result is good enough to guide an LLM toward the most
relevant call sites.
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


def callee_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return callee_name(node.func)
    return None


def walk_python(root: Path, excludes: set[str]):
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def analyze(path: Path, root: Path):
    src = path.read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return [], [], {"path": str(path.relative_to(root)),
                        "error": f"SyntaxError: {e.msg} (line {e.lineno})"}
    rel = str(path.relative_to(root))
    mod = rel[:-3].replace("/", ".") if rel.endswith(".py") else rel
    nodes: list[dict] = []
    edges: list[dict] = []
    defined: set[str] = set()

    def qid(stack: list[str], name: str) -> str:
        return ".".join([mod] + stack + [name])

    def visit(node, stack):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "method" if stack else "function"
            qn = qid(stack, node.name)
            defined.add(qn)
            nodes.append({"id": qn, "name": node.name, "kind": kind,
                          "file": rel, "line": node.lineno})
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    cn = callee_name(child.func)
                    if cn:
                        edges.append({"from": qn, "to": cn,
                                      "line": child.lineno})
            # Recurse into nested functions / classes
            for ch in node.body:
                visit(ch, stack + [node.name])
        elif isinstance(node, ast.ClassDef):
            for ch in node.body:
                visit(ch, stack + [node.name])

    for n in tree.body:
        visit(n, [])
    return nodes, edges, None


def main() -> int:
    ap = argparse.ArgumentParser(prog="call-graph",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", help="Python file or directory")
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

    nodes: list[dict] = []
    edges: list[dict] = []
    errors: list[dict] = []
    for fp in walk_python(p, excludes):
        n, e, err = analyze(fp, root)
        if err:
            errors.append(err)
        nodes.extend(n)
        edges.extend(e)

    # mark which edges resolve to a known node (by suffix match on name)
    known_names = {n["name"] for n in nodes}
    resolved = 0
    for e in edges:
        if e["to"] in known_names:
            e["resolved"] = True
            resolved += 1
        else:
            e["resolved"] = False

    out = {"root": str(root), "nodes": nodes, "edges": edges,
           "stats": {"functions": len(nodes), "calls": len(edges),
                     "resolved": resolved}}
    if errors:
        out["parse_errors"] = errors
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
