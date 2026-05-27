#!/usr/bin/env python3
"""diff-summary — summarize a unified diff as JSON.

Reads a unified diff from a file, stdin, or `git diff <range>` output and
emits per-file stats: change type (added/modified/deleted/renamed),
added/removed line counts, hunk count, and a best-effort list of changed
Python symbols (functions/classes touched by added lines).
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FILE_HEADER = re.compile(r'^diff --git a/(.+?) b/(.+?)$')
HUNK_HEADER = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
DEF_RE = re.compile(r'^\+\s*(?:async\s+)?(def|class)\s+([A-Za-z_]\w*)')


def parse(diff_text: str):
    files: list[dict] = []
    curr: dict | None = None
    for line in diff_text.splitlines():
        m = FILE_HEADER.match(line)
        if m:
            if curr is not None:
                files.append(curr)
            curr = {"path": m.group(2), "old_path": m.group(1),
                    "change": "modified", "added": 0, "removed": 0,
                    "hunks": 0, "symbols": []}
            if m.group(1) != m.group(2):
                curr["change"] = "renamed"
            continue
        if curr is None:
            continue
        if line.startswith("new file"):
            curr["change"] = "added"
        elif line.startswith("deleted file"):
            curr["change"] = "deleted"
        elif line.startswith("rename from") or line.startswith("rename to"):
            curr["change"] = "renamed"
        elif HUNK_HEADER.match(line):
            curr["hunks"] += 1
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+"):
            curr["added"] += 1
            ms = DEF_RE.match(line)
            if ms and curr["path"].endswith(".py"):
                sym = f"{ms.group(1)} {ms.group(2)}"
                if sym not in curr["symbols"]:
                    curr["symbols"].append(sym)
        elif line.startswith("-"):
            curr["removed"] += 1
    if curr is not None:
        files.append(curr)
    return files


def read_input(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    p = Path(src)
    if p.is_file():
        return p.read_text("utf-8", errors="replace")
    # treat as a git range like "main..HEAD"
    out = subprocess.run(["git", "diff", src],
                         capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise SystemExit(f"diff-summary: cannot read input: {src}")
    return out.stdout


def main() -> int:
    ap = argparse.ArgumentParser(prog="diff-summary",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("input", nargs="?", default="-",
                    help="diff file, '-' for stdin, or a git range (default '-')")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    diff_text = read_input(args.input)
    files = parse(diff_text)
    totals = {"files": len(files),
              "added": sum(f["added"] for f in files),
              "removed": sum(f["removed"] for f in files),
              "by_change": {}}
    for f in files:
        totals["by_change"][f["change"]] = totals["by_change"].get(f["change"], 0) + 1
        if not f["symbols"]:
            f.pop("symbols")

    out = {"totals": totals, "files": files}
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
