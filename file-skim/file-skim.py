#!/usr/bin/env python3
"""file-skim — emit the structural skeleton of a Python file as JSON.

Returns imports, top-level constants, classes (with method names and line
ranges), and free functions (with signatures and docstring first-line). Lets
an LLM grasp a file's shape without reading the bodies.
"""
from __future__ import annotations
import argparse
import ast
import json
import sys
from pathlib import Path


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = ast.unparse(node.args) if node.args else ""
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({args}){ret}"


def doc_first(node: ast.AST) -> str | None:
    doc = ast.get_docstring(node)
    if not doc:
        return None
    line = doc.strip().split("\n", 1)[0].strip()
    return line or None


def imports_of(tree: ast.Module) -> list[str]:
    out = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name + (f" as {a.asname}" if a.asname else ""))
        elif isinstance(node, ast.ImportFrom):
            mod = ("." * (node.level or 0)) + (node.module or "")
            names = ", ".join(
                n.name + (f" as {n.asname}" if n.asname else "")
                for n in node.names
            )
            out.append(f"from {mod} import {names}")
    return out


def constants_of(tree: ast.Module) -> list[dict]:
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    out.append({"name": target.id, "line": node.lineno,
                                "value_kind": type(node.value).__name__})
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper():
                out.append({"name": node.target.id, "line": node.lineno,
                            "annotation": ast.unparse(node.annotation)
                            if node.annotation else None})
    return out


def class_entry(node: ast.ClassDef) -> dict:
    methods = []
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m: dict = {"name": child.name, "line": child.lineno,
                       "signature": signature(child)}
            doc = doc_first(child)
            if doc:
                m["doc"] = doc
            methods.append(m)
    bases = [ast.unparse(b) for b in node.bases]
    entry: dict = {"name": node.name, "line": node.lineno,
                   "end_line": getattr(node, "end_lineno", None),
                   "bases": bases, "methods": methods}
    doc = doc_first(node)
    if doc:
        entry["doc"] = doc
    return entry


def function_entry(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    entry: dict = {"name": node.name, "line": node.lineno,
                   "end_line": getattr(node, "end_lineno", None),
                   "signature": signature(node)}
    doc = doc_first(node)
    if doc:
        entry["doc"] = doc
    return entry


def skim(path: Path) -> dict:
    src = path.read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return {"path": str(path), "error": f"SyntaxError: {e.msg} (line {e.lineno})"}
    out = {
        "path": str(path),
        "lines": src.count("\n") + (0 if src.endswith("\n") else 1),
        "module_doc": doc_first(tree),
        "imports": imports_of(tree),
        "constants": constants_of(tree),
        "classes": [class_entry(n) for n in tree.body if isinstance(n, ast.ClassDef)],
        "functions": [function_entry(n) for n in tree.body
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
    }
    if out["module_doc"] is None:
        out.pop("module_doc")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="file-skim",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("file", help="path to a Python file")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(json.dumps({"error": f"not a file: {args.file}"}), file=sys.stderr)
        return 2

    out = skim(path)
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0 if "error" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
