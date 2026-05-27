#!/usr/bin/env python3
"""commit-pickaxe — find commits that introduced or removed a string.

Wraps `git log -S<string>` (or `-G<regex>` with --regex) and emits JSON
listings: commit sha, author, date, subject, and the diff hunks that touched
the term. Token-cheap alternative to scrolling `git log -p -S 'foo'`.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

SEP = "<<<COMMIT-PICKAXE-SEP>>>"


def main() -> int:
    ap = argparse.ArgumentParser(prog="commit-pickaxe",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("pattern", help="literal string (or regex with --regex)")
    ap.add_argument("--regex", action="store_true",
                    help="use git log -G (regex) instead of -S (literal)")
    ap.add_argument("--path", default=".", help="repo root (default: .)")
    ap.add_argument("--limit", type=int, default=50,
                    help="max commits returned (default 50)")
    ap.add_argument("--diff", action="store_true",
                    help="include the touching diff hunks")
    ap.add_argument("--paths", nargs="*", default=[],
                    help="restrict to these paths")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    cwd = Path(args.path).resolve()
    if not (cwd / ".git").exists():
        print(json.dumps({"error": f"not a git repo: {cwd}"}), file=sys.stderr)
        return 2

    pickaxe = f"-G{args.pattern}" if args.regex else f"-S{args.pattern}"
    cmd = ["git", "log", pickaxe, f"-{args.limit}",
           f"--pretty=format:%H%x09%an%x09%aI%x09%s{SEP}"]
    if args.diff:
        cmd.append("-p")
    if args.paths:
        cmd.append("--")
        cmd.extend(args.paths)

    res = subprocess.run(cmd, cwd=cwd, capture_output=True,
                         text=True, check=False)
    if res.returncode != 0:
        print(json.dumps({"error": "git log failed",
                          "stderr": res.stderr.strip()}), file=sys.stderr)
        return 1

    commits: list[dict] = []
    for chunk in res.stdout.split(SEP):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        header, _, diff_body = chunk.partition("\n")
        parts = header.split("\t", 3)
        if len(parts) < 4:
            continue
        sha, author, when, subject = parts
        entry = {"sha": sha, "author": author, "date": when,
                 "subject": subject}
        if args.diff and diff_body.strip():
            entry["diff"] = diff_body.strip()
        commits.append(entry)

    out = {"pattern": args.pattern, "regex": args.regex,
           "count": len(commits), "commits": commits}
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0 if commits else 1


if __name__ == "__main__":
    raise SystemExit(main())
