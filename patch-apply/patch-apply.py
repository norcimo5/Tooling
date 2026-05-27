#!/usr/bin/env python3
"""patch-apply — apply a unified diff strictly and report status as JSON.

Wraps `git apply` (preferred when in a git repo) or falls back to `patch -p1`.
Always tries `--check` first; if the dry-run succeeds, applies the patch;
otherwise reports per-file conflicts. Use this for deterministic, scriptable
patch application from an LLM agent.
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def has_git(cwd: Path) -> bool:
    return (cwd / ".git").exists() and shutil.which("git") is not None


def files_in_diff(diff_text: str) -> list[str]:
    return [m.group(1)
            for m in re.finditer(r'^diff --git a/.+? b/(.+?)$',
                                 diff_text, re.M)]


def main() -> int:
    ap = argparse.ArgumentParser(prog="patch-apply",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("patch", help="path to a patch file, or '-' for stdin")
    ap.add_argument("--path", default=".", help="repo root (default: .)")
    ap.add_argument("--check", action="store_true",
                    help="dry-run only — do not modify the working tree")
    ap.add_argument("--3way", dest="threeway", action="store_true",
                    help="git apply --3way (allow trivial merges)")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    cwd = Path(args.path).resolve()
    if not cwd.is_dir():
        print(json.dumps({"error": f"not a directory: {cwd}"}), file=sys.stderr)
        return 2

    diff_text = (sys.stdin.read() if args.patch == "-"
                 else Path(args.patch).read_text("utf-8", errors="replace"))
    targets = files_in_diff(diff_text)

    use_git = has_git(cwd)
    out: dict = {"engine": "git apply" if use_git else "patch",
                 "check_only": args.check, "files": targets}

    def run(cmd, stdin):
        return subprocess.run(cmd, cwd=cwd, input=stdin,
                              capture_output=True, text=True, check=False)

    if use_git:
        check_cmd = ["git", "apply", "--check"]
        if args.threeway:
            check_cmd.append("--3way")
        chk = run(check_cmd, diff_text)
        out["check_ok"] = chk.returncode == 0
        if not out["check_ok"]:
            out["check_stderr"] = chk.stderr.strip()
        if args.check or not out["check_ok"]:
            out["applied"] = False
        else:
            apply_cmd = ["git", "apply"] + (["--3way"] if args.threeway else [])
            ap_res = run(apply_cmd, diff_text)
            out["applied"] = ap_res.returncode == 0
            if not out["applied"]:
                out["apply_stderr"] = ap_res.stderr.strip()
    else:
        chk = run(["patch", "-p1", "--dry-run"], diff_text)
        out["check_ok"] = chk.returncode == 0
        if not out["check_ok"]:
            out["check_stderr"] = chk.stderr.strip() or chk.stdout.strip()
        if args.check or not out["check_ok"]:
            out["applied"] = False
        else:
            ap_res = run(["patch", "-p1"], diff_text)
            out["applied"] = ap_res.returncode == 0
            if not out["applied"]:
                out["apply_stderr"] = (ap_res.stderr.strip()
                                       or ap_res.stdout.strip())

    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    if args.check:
        return 0 if out["check_ok"] else 1
    return 0 if out.get("applied") else 1


if __name__ == "__main__":
    raise SystemExit(main())
