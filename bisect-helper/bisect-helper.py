#!/usr/bin/env python3
"""bisect-helper — drive `git bisect run` and report the first bad commit.

Wraps `git bisect start/run` around a user-supplied test command. The command
should exit 0 when the tree is good and non-zero when bad. Emits JSON with
the first bad commit, its parent diff stats, and the bisect log.

Caller is responsible for a clean working tree. The script always runs
`git bisect reset` afterward to leave the repo in HEAD.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FIRST_BAD_RE = re.compile(r'^([0-9a-f]{7,40}) is the first bad commit', re.M)


def git(*args, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                          text=True, check=False)


def main() -> int:
    ap = argparse.ArgumentParser(prog="bisect-helper",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("--good", required=True,
                    help="known-good ref (older commit)")
    ap.add_argument("--bad", default="HEAD",
                    help="known-bad ref (default HEAD)")
    ap.add_argument("--cmd", required=True,
                    help="shell command; non-zero exit = bad")
    ap.add_argument("--path", default=".", help="repo root (default: .)")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    cwd = Path(args.path).resolve()
    if not (cwd / ".git").exists():
        print(json.dumps({"error": f"not a git repo: {cwd}"}), file=sys.stderr)
        return 2

    status = git("status", "--porcelain", cwd=cwd)
    if status.stdout.strip():
        print(json.dumps({"error": "working tree not clean — commit or stash first"}),
              file=sys.stderr)
        return 2

    out = {"good": args.good, "bad": args.bad, "cmd": args.cmd}
    try:
        start = git("bisect", "start", args.bad, args.good, cwd=cwd)
        if start.returncode != 0:
            out["error"] = f"bisect start failed: {start.stderr.strip()}"
            return 1
        run = subprocess.run(["git", "bisect", "run", "sh", "-c", args.cmd],
                             cwd=cwd, capture_output=True, text=True, check=False)
        out["bisect_log"] = run.stdout
        m = FIRST_BAD_RE.search(run.stdout)
        if m:
            sha = m.group(1)
            out["first_bad"] = sha
            show = git("show", "--stat", "--format=%h %an%n%s%n%n%b", sha, cwd=cwd)
            out["commit_info"] = show.stdout.strip()
        else:
            out["error"] = "no first-bad commit identified"
            out["raw_stderr"] = run.stderr
    finally:
        git("bisect", "reset", cwd=cwd)

    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0 if "first_bad" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
