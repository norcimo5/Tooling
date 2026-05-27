#!/usr/bin/env python3
"""pr-context — JSON bundle of files relevant to the changes on a branch.

For changed files between `--base` and `--head`, walks Python imports up to
`--depth` hops to list related in-repo files, plus tests that import them or
are named after them. Lets an LLM agent open only the relevant slice of a
large repo before reviewing or fixing a PR.
"""
from __future__ import annotations
import argparse
import ast
import json
import os
import subprocess
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


def imports_of(tree: ast.Module, curr: str):
    out = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = curr.split(".")
                prefix = base[: max(0, len(base) - node.level)]
                if node.module:
                    out.append(".".join(prefix + [node.module]))
                else:
                    out.append(".".join(prefix))
            elif node.module:
                out.append(node.module)
    return out


def resolve(target: str, known: set[str]) -> str | None:
    parts = target.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in known:
            return cand
    return None


def git_changed(base: str, head: str, cwd: Path) -> list[str]:
    res = subprocess.run(["git", "diff", "--name-only", f"{base}..{head}"],
                         cwd=cwd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise SystemExit(f"pr-context: git diff failed: {res.stderr.strip()}")
    return [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(prog="pr-context",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("--base", default="main", help="base ref (default main)")
    ap.add_argument("--head", default="HEAD", help="head ref (default HEAD)")
    ap.add_argument("--path", default=".", help="repo root (default: .)")
    ap.add_argument("--depth", type=int, default=1,
                    help="import hops to follow (default 1)")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not (root / ".git").exists():
        print(json.dumps({"error": f"not a git repo: {root}"}), file=sys.stderr)
        return 2
    excludes = DEFAULT_EXCLUDES | set(args.exclude)

    changed = git_changed(args.base, args.head, root)
    changed_paths = [root / c for c in changed if c.endswith(".py")
                     and (root / c).is_file()]
    files = list(walk_python(root, excludes))
    mod_to_file = {to_module(f, root): f for f in files}
    known = set(mod_to_file)
    changed_modules = {to_module(p, root) for p in changed_paths}

    visited = set(changed_modules)
    frontier = list(changed_paths)
    for _ in range(args.depth):
        next_frontier = []
        for f in frontier:
            try:
                tree = ast.parse(f.read_text("utf-8", errors="replace"))
            except SyntaxError:
                continue
            curr = to_module(f, root)
            for imp in imports_of(tree, curr):
                resolved = resolve(imp, known)
                if resolved and resolved not in visited:
                    visited.add(resolved)
                    next_frontier.append(mod_to_file[resolved])
        frontier = next_frontier
        if not frontier:
            break

    related = sorted(str(mod_to_file[m].relative_to(root))
                     for m in visited if m not in changed_modules)

    # Tests that import a changed module
    related_tests: list[str] = []
    for f in files:
        if not (f.name.startswith("test_") or f.name.endswith("_test.py")):
            continue
        try:
            tree = ast.parse(f.read_text("utf-8", errors="replace"))
        except SyntaxError:
            continue
        curr = to_module(f, root)
        for imp in imports_of(tree, curr):
            r = resolve(imp, known)
            if r in changed_modules:
                related_tests.append(str(f.relative_to(root)))
                break

    out = {
        "base": args.base, "head": args.head, "depth": args.depth,
        "changed_files": changed,
        "related_files": related,
        "related_tests": sorted(set(related_tests)),
        "stats": {"changed": len(changed),
                  "related": len(related),
                  "tests": len(set(related_tests))},
    }
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
