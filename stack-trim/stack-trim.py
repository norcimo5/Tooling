#!/usr/bin/env python3
"""stack-trim — drop irrelevant frames from a Python traceback.

Parses a Python traceback from a file or stdin, classifies each frame as
`user` / `stdlib` / `thirdparty`, and keeps only the user frames by default.
Useful before pasting a 200-line stack into an LLM — emit a tight JSON of the
~3 frames that actually matter.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import sysconfig
from pathlib import Path

FRAME_RE = re.compile(
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>.+?)$'
)
ERROR_RE = re.compile(
    r'^(?P<cls>[A-Za-z_][\w.]*Error|[A-Za-z_][\w.]*Exception|'
    r'[A-Za-z_][\w.]*Warning|SystemExit|KeyboardInterrupt|StopIteration|'
    r'GeneratorExit|BaseException)(?:: (?P<msg>.*))?$'
)


def classify(file_path: str, project_root: Path) -> str:
    p = Path(file_path).resolve() if file_path else Path()
    try:
        stdlib = Path(sysconfig.get_paths()["stdlib"]).resolve()
    except KeyError:
        stdlib = None
    s = str(p)
    if "site-packages" in s or "dist-packages" in s:
        return "thirdparty"
    if stdlib and s.startswith(str(stdlib)):
        return "stdlib"
    try:
        p.relative_to(project_root)
        return "user"
    except ValueError:
        return "stdlib" if s.startswith(sys.prefix) else "thirdparty"


def parse_traceback(text: str, project_root: Path):
    lines = text.splitlines()
    frames = []
    error = None
    i = 0
    while i < len(lines):
        m = FRAME_RE.match(lines[i])
        if m:
            frame = {"file": m.group("file"), "line": int(m.group("line")),
                     "func": m.group("func").strip()}
            if i + 1 < len(lines) and lines[i + 1].startswith("    "):
                frame["code"] = lines[i + 1].strip()
                i += 1
            frame["class"] = classify(frame["file"], project_root)
            frames.append(frame)
        else:
            m2 = ERROR_RE.match(lines[i].strip())
            if m2 and lines[i].strip() and not lines[i].startswith(" "):
                error = {"type": m2.group("cls"), "message": m2.group("msg") or ""}
        i += 1
    return frames, error


def main() -> int:
    ap = argparse.ArgumentParser(prog="stack-trim",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("input", nargs="?", default="-",
                    help="traceback file or '-' for stdin")
    ap.add_argument("--project", default=".",
                    help="project root for 'user' classification (default: .)")
    ap.add_argument("--keep", action="append", default=[],
                    choices=["stdlib", "thirdparty"],
                    help="also keep frames from these layers (repeatable)")
    ap.add_argument("--context", type=int, default=0,
                    help="N lines of source around each kept frame's line")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    text = (sys.stdin.read() if args.input == "-"
            else Path(args.input).read_text("utf-8", errors="replace"))
    project_root = Path(args.project).resolve()

    frames, error = parse_traceback(text, project_root)
    keep = {"user"} | set(args.keep)
    kept = [f for f in frames if f["class"] in keep]

    if args.context > 0:
        for f in kept:
            try:
                src = Path(f["file"]).read_text("utf-8", errors="replace").splitlines()
                lo = max(0, f["line"] - 1 - args.context)
                hi = min(len(src), f["line"] + args.context)
                f["source"] = [{"line": lo + i + 1, "code": src[lo + i]}
                               for i in range(hi - lo)]
            except (OSError, ValueError):
                pass

    out = {"error": error, "frames_total": len(frames),
           "frames_kept": len(kept), "frames": kept}
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
