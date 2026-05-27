#!/usr/bin/env python3
"""repo-map — compact JSON map of a repository.

Emits a deterministic listing of files (relative paths, sizes, line counts,
inferred language) with optional top-level Python symbols, plus aggregate
stats. Designed to give an LLM agent a single token-cheap overview of an
unfamiliar repo without listing huge directories.
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
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "dist", "build", ".next", "target", ".gradle", ".idea",
    ".vscode", ".cache", ".eggs",
}
EXCLUDE_GLOBS = ("*.egg-info",)

EXT_LANG = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".rs": "rust",
    ".java": "java", ".kt": "kotlin", ".rb": "ruby", ".php": "php",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".swift": "swift", ".scala": "scala",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".lua": "lua", ".r": "r", ".jl": "julia", ".dart": "dart",
    ".ex": "elixir", ".exs": "elixir", ".erl": "erlang",
    ".hs": "haskell", ".ml": "ocaml", ".clj": "clojure",
    ".md": "markdown", ".rst": "rst", ".html": "html",
    ".css": "css", ".scss": "scss",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".xml": "xml", ".sql": "sql", ".proto": "proto",
}


def excluded(name: str, names: set[str]) -> bool:
    if name in names:
        return True
    for g in EXCLUDE_GLOBS:
        if g.startswith("*") and name.endswith(g[1:]):
            return True
    return False


def py_symbols(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text("utf-8", errors="replace"))
    except (SyntaxError, OSError, ValueError):
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append(node.name)
    return out


def walk(root: Path, excludes: set[str], max_depth: int | None):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_parts = Path(dirpath).relative_to(root).parts
        if max_depth is not None and len(rel_parts) >= max_depth:
            dirnames[:] = []
        dirnames[:] = sorted(d for d in dirnames if not excluded(d, excludes))
        for fn in sorted(filenames):
            if excluded(fn, excludes):
                continue
            yield Path(dirpath) / fn


def main() -> int:
    ap = argparse.ArgumentParser(prog="repo-map",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--symbols", action="store_true",
                    help="include top-level Python symbols per .py file")
    ap.add_argument("--exclude", action="append", default=[],
                    help="extra name to exclude (repeatable)")
    ap.add_argument("--max-depth", type=int, default=None,
                    help="limit traversal depth")
    ap.add_argument("--max-files", type=int, default=10000,
                    help="hard cap on files returned (default 10000)")
    ap.add_argument("--pretty", action="store_true", help="indent JSON")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {args.path}"}),
              file=sys.stderr)
        return 2

    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    files: list[dict] = []
    by_lang: dict[str, dict] = {}
    total_bytes = 0
    truncated = False

    for fp in walk(root, excludes, args.max_depth):
        if len(files) >= args.max_files:
            truncated = True
            break
        try:
            st = fp.stat()
        except OSError:
            continue
        rel = str(fp.relative_to(root))
        lang = EXT_LANG.get(fp.suffix.lower(), "")
        lines = None
        if lang and st.st_size < 5_000_000:
            try:
                with fp.open("rb") as f:
                    lines = sum(1 for _ in f)
            except OSError:
                pass
        entry: dict = {"path": rel, "bytes": st.st_size}
        if lang:
            entry["lang"] = lang
        if lines is not None:
            entry["lines"] = lines
        if args.symbols and lang == "python":
            syms = py_symbols(fp)
            if syms:
                entry["symbols"] = syms
        files.append(entry)
        total_bytes += st.st_size
        if lang:
            agg = by_lang.setdefault(lang, {"files": 0, "bytes": 0, "lines": 0})
            agg["files"] += 1
            agg["bytes"] += st.st_size
            if lines is not None:
                agg["lines"] += lines

    out = {
        "root": str(root),
        "stats": {
            "files": len(files),
            "bytes": total_bytes,
            "by_lang": dict(sorted(by_lang.items(), key=lambda kv: -kv[1]["files"])),
            "truncated": truncated,
        },
        "files": files,
    }
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
