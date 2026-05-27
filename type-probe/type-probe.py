#!/usr/bin/env python3
"""type-probe — extract static type info for a Python symbol as JSON.

Given `path/to/file.py::Name` (or `path/to/file.py::Class.method`), emits the
symbol's kind, signature, parameter annotations, return type, decorators, and
docstring. AST-only: no imports executed.
"""
from __future__ import annotations
import argparse
import ast
import json
import sys
from pathlib import Path


def ann(node) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def params(args: ast.arguments) -> list[dict]:
    out = []
    posonly = list(args.posonlyargs)
    pos = list(args.args)
    kwonly = list(args.kwonlyargs)
    defaults_pos = list(args.defaults)
    defaults_kw = list(args.kw_defaults)

    # Defaults align to the end of (posonly + pos).
    all_pos = posonly + pos
    pad = [None] * (len(all_pos) - len(defaults_pos))
    pos_defaults = pad + defaults_pos
    for arg, default in zip(posonly, pos_defaults[: len(posonly)]):
        out.append({"name": arg.arg, "kind": "positional-only",
                    "annotation": ann(arg.annotation),
                    "default": ann(default) if default else None})
    for arg, default in zip(pos, pos_defaults[len(posonly):]):
        out.append({"name": arg.arg, "kind": "positional",
                    "annotation": ann(arg.annotation),
                    "default": ann(default) if default else None})
    if args.vararg:
        out.append({"name": args.vararg.arg, "kind": "var-positional",
                    "annotation": ann(args.vararg.annotation)})
    for arg, default in zip(kwonly, defaults_kw):
        out.append({"name": arg.arg, "kind": "keyword-only",
                    "annotation": ann(arg.annotation),
                    "default": ann(default) if default else None})
    if args.kwarg:
        out.append({"name": args.kwarg.arg, "kind": "var-keyword",
                    "annotation": ann(args.kwarg.annotation)})
    return out


def find_symbol(tree: ast.Module, dotted: str):
    parts = dotted.split(".")
    body = tree.body
    parent = None
    node = None
    for i, name in enumerate(parts):
        found = None
        for child in body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)) and child.name == name:
                found = child
                break
        if found is None:
            return None, None
        node = found
        parent = parts[i - 1] if i > 0 else None
        body = found.body if isinstance(found, ast.ClassDef) else []
    return node, parent


def main() -> int:
    ap = argparse.ArgumentParser(prog="type-probe",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("target",
                    help="'path/to/file.py::Name' or '...::Class.method'")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    if "::" not in args.target:
        print(json.dumps({"error": "expected path::symbol"}), file=sys.stderr)
        return 2
    file_str, dotted = args.target.split("::", 1)
    path = Path(file_str)
    if not path.is_file():
        print(json.dumps({"error": f"not a file: {file_str}"}), file=sys.stderr)
        return 2
    try:
        tree = ast.parse(path.read_text("utf-8", errors="replace"))
    except SyntaxError as e:
        print(json.dumps({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}),
              file=sys.stderr)
        return 1

    node, parent = find_symbol(tree, dotted)
    if node is None:
        print(json.dumps({"error": f"symbol not found: {dotted}"}),
              file=sys.stderr)
        return 1

    if isinstance(node, ast.ClassDef):
        kind = "class"
        signature = node.name + (
            f"({', '.join(ast.unparse(b) for b in node.bases)})"
            if node.bases else "")
        out = {"path": str(path), "kind": kind, "name": node.name,
               "line": node.lineno, "signature": signature,
               "bases": [ast.unparse(b) for b in node.bases],
               "decorators": [ast.unparse(d) for d in node.decorator_list],
               "docstring": ast.get_docstring(node)}
    else:
        kind = "method" if parent else "function"
        if isinstance(node, ast.AsyncFunctionDef):
            kind = "async-" + kind
        out = {"path": str(path), "kind": kind, "name": node.name,
               "parent": parent, "line": node.lineno,
               "params": params(node.args),
               "returns": ann(node.returns),
               "decorators": [ast.unparse(d) for d in node.decorator_list],
               "docstring": ast.get_docstring(node)}
        sig_args = ast.unparse(node.args) if node.args else ""
        sig_ret = f" -> {ann(node.returns)}" if node.returns else ""
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        out["signature"] = f"{prefix}{node.name}({sig_args}){sig_ret}"

    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
