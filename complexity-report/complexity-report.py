#!/usr/bin/env python3
"""complexity-report — per-function cyclomatic complexity + LOC for Python.

McCabe-style branch counting (1 + each if/for/while/elif/except/with-as/
boolean-op/comprehension/assert/match-case). Emits a list sorted by
complexity desc with the top hotspots an LLM agent should look at first.
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
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def complexity(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While,
                              ast.ExceptHandler, ast.Assert)):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1
        elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp,
                                ast.GeneratorExp)):
            score += 1
            for gen in child.generators:
                score += len(gen.ifs)
        elif isinstance(child, ast.comprehension):
            pass  # handled above
        elif hasattr(ast, "Match") and isinstance(child, ast.Match):
            score += len(child.cases)
        elif isinstance(child, ast.IfExp):
            score += 1
    return score


def analyze_file(path: Path, root: Path) -> tuple[list[dict], dict | None]:
    try:
        tree = ast.parse(path.read_text("utf-8", errors="replace"),
                         filename=str(path))
    except SyntaxError as e:
        return [], {"path": str(path.relative_to(root)),
                    "error": f"SyntaxError: {e.msg} (line {e.lineno})"}
    rel = str(path.relative_to(root))
    out: list[dict] = []

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack: list[str] = []
        def _emit(self, n, kind):
            cc = complexity(n)
            loc = (getattr(n, "end_lineno", n.lineno) or n.lineno) - n.lineno + 1
            qn = ".".join(self.stack + [n.name])
            out.append({"path": rel, "qualname": qn, "name": n.name,
                        "kind": kind, "line": n.lineno,
                        "loc": loc, "complexity": cc})
        def visit_FunctionDef(self, n):
            self._emit(n, "method" if self.stack else "function")
            self.stack.append(n.name)
            self.generic_visit(n)
            self.stack.pop()
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_ClassDef(self, n):
            self.stack.append(n.name)
            self.generic_visit(n)
            self.stack.pop()

    V().visit(tree)
    return out, None


def main() -> int:
    ap = argparse.ArgumentParser(prog="complexity-report",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", nargs="?", default=".",
                    help="file or directory (default: .)")
    ap.add_argument("--min", type=int, default=1,
                    help="only report complexity >= N (default 1)")
    ap.add_argument("--top", type=int, default=None,
                    help="keep only the N worst (default: all)")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    p = Path(args.path).resolve()
    if not p.exists():
        print(json.dumps({"error": f"not found: {args.path}"}), file=sys.stderr)
        return 2
    root = p if p.is_dir() else p.parent
    excludes = DEFAULT_EXCLUDES | set(args.exclude)

    functions: list[dict] = []
    errors: list[dict] = []
    for fp in walk_python(p, excludes):
        funcs, err = analyze_file(fp, root)
        if err:
            errors.append(err)
        functions.extend(funcs)

    functions = [f for f in functions if f["complexity"] >= args.min]
    functions.sort(key=lambda f: (-f["complexity"], -f["loc"], f["path"]))
    if args.top is not None:
        functions = functions[:args.top]

    totals = {"functions": len(functions),
              "max_complexity": max((f["complexity"] for f in functions),
                                    default=0),
              "avg_complexity": (sum(f["complexity"] for f in functions)
                                 / len(functions)) if functions else 0}
    out = {"root": str(root), "stats": totals, "functions": functions}
    if errors:
        out["parse_errors"] = errors
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
