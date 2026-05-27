#!/usr/bin/env python3
"""lint-collate — run a Python linter and emit normalized JSON.

Tries `ruff` first (fast, JSON-native); falls back to `pyflakes` and parses
its line-based output. Emits a uniform shape: {file, line, col, code,
severity, message}. Use this so an LLM agent sees the same JSON regardless
of which linter is available in the environment.
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PYFLAKES_RE = re.compile(r'^(?P<file>[^:]+):(?P<line>\d+):(?:(?P<col>\d+):)? '
                         r'(?P<msg>.+)$')


def run_ruff(paths: list[str], cwd: Path) -> tuple[list[dict], str]:
    cmd = ["ruff", "check", "--output-format=json", *paths]
    res = subprocess.run(cmd, cwd=cwd, capture_output=True,
                         text=True, check=False)
    try:
        items = json.loads(res.stdout) if res.stdout.strip() else []
    except json.JSONDecodeError:
        return [], res.stderr.strip() or res.stdout.strip()
    out = []
    for it in items:
        out.append({
            "file": it.get("filename") or it.get("file") or "",
            "line": (it.get("location") or {}).get("row")
                    or it.get("row") or it.get("line") or 0,
            "col": (it.get("location") or {}).get("column")
                    or it.get("col") or 0,
            "code": it.get("code") or "",
            "severity": "error",
            "message": it.get("message") or "",
        })
    return out, ""


def run_pyflakes(paths: list[str], cwd: Path) -> tuple[list[dict], str]:
    cmd = ["pyflakes", *paths]
    res = subprocess.run(cmd, cwd=cwd, capture_output=True,
                         text=True, check=False)
    out = []
    for line in res.stdout.splitlines():
        m = PYFLAKES_RE.match(line)
        if m:
            out.append({"file": m.group("file"),
                        "line": int(m.group("line")),
                        "col": int(m.group("col") or 0),
                        "code": "",
                        "severity": "error",
                        "message": m.group("msg")})
    return out, res.stderr.strip()


def main() -> int:
    ap = argparse.ArgumentParser(prog="lint-collate",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("paths", nargs="*", default=["."],
                    help="files or directories to lint (default: .)")
    ap.add_argument("--tool", choices=["auto", "ruff", "pyflakes"],
                    default="auto", help="force a specific linter")
    ap.add_argument("--limit", type=int, default=500,
                    help="cap on findings returned (default 500)")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    cwd = Path.cwd()
    chosen = None
    if args.tool == "ruff" or (args.tool == "auto" and shutil.which("ruff")):
        chosen = "ruff"
        findings, err = run_ruff(args.paths, cwd)
    elif args.tool == "pyflakes" or shutil.which("pyflakes"):
        chosen = "pyflakes"
        findings, err = run_pyflakes(args.paths, cwd)
    else:
        print(json.dumps({"error": "no linter available "
                                   "(install ruff or pyflakes)"}),
              file=sys.stderr)
        return 2

    truncated = False
    if len(findings) > args.limit:
        findings = findings[:args.limit]
        truncated = True

    by_code: dict[str, int] = {}
    for f in findings:
        by_code[f["code"] or "uncoded"] = by_code.get(f["code"] or "uncoded", 0) + 1

    out = {"tool": chosen, "count": len(findings),
           "truncated": truncated,
           "by_code": dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
           "findings": findings}
    if err:
        out["stderr"] = err
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
