#!/usr/bin/env python3
"""secret-scan — regex scan for likely secrets in a repo.

Looks for cloud creds, private keys, common provider tokens, and high-entropy
assignment-like patterns. Emits JSON with file:line, the pattern name, and a
*redacted* preview (middle of the match replaced with `…`). Designed to be
cheap, deterministic, and conservative — false positives are accepted to
keep false negatives low.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

DEFAULT_EXCLUDES = {".git", "__pycache__", ".venv", "venv", "node_modules",
                    "dist", "build", ".mypy_cache", ".pytest_cache",
                    ".cache", "vendor"}

BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip",
               ".tar", ".gz", ".bz2", ".xz", ".so", ".o", ".a", ".bin",
               ".exe", ".dll", ".class", ".jar", ".whl", ".pyc", ".woff",
               ".woff2", ".ttf", ".eot", ".ico", ".mp3", ".mp4", ".mov"}

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws-access-key", re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ("aws-secret",
     re.compile(r'(?i)aws[_\-]?(?:secret|sk)[^=:\n]{0,30}[:=]\s*["\']?'
                r'(?P<v>[A-Za-z0-9/+=]{40})')),
    ("google-api-key", re.compile(r'\bAIza[0-9A-Za-z\-_]{35}\b')),
    ("github-pat", re.compile(r'\bghp_[A-Za-z0-9]{36,}\b')),
    ("github-oauth", re.compile(r'\bgho_[A-Za-z0-9]{36,}\b')),
    ("github-server", re.compile(r'\bghs_[A-Za-z0-9]{36,}\b')),
    ("github-user", re.compile(r'\bghu_[A-Za-z0-9]{36,}\b')),
    ("slack-token", re.compile(r'\bxox[baprs]-[A-Za-z0-9\-]{10,}\b')),
    ("stripe-secret", re.compile(r'\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b')),
    ("stripe-restricted", re.compile(r'\brk_(?:live|test)_[A-Za-z0-9]{20,}\b')),
    ("openai-key", re.compile(r'\bsk-[A-Za-z0-9]{20,}\b')),
    ("anthropic-key", re.compile(r'\bsk-ant-[A-Za-z0-9_\-]{20,}\b')),
    ("jwt", re.compile(r'\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}'
                       r'\.[A-Za-z0-9_\-]{10,}\b')),
    ("private-key-pem",
     re.compile(r'-----BEGIN (?:RSA|EC|OPENSSH|DSA|PGP|ENCRYPTED) '
                r'PRIVATE KEY-----')),
    ("generic-secret-assign",
     re.compile(r'(?i)\b(?:api[_-]?key|secret|token|passwd|password|'
                r'auth[_-]?token)\b\s*[:=]\s*["\']'
                r'(?P<v>[A-Za-z0-9_\-/+=.]{16,})["\']')),
]


def shannon(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    return -sum((c / len(s)) * math.log2(c / len(s)) for c in freq.values())


def redact(s: str) -> str:
    if len(s) <= 8:
        return s[0] + "…" + s[-1] if len(s) > 2 else "…"
    return s[:4] + "…" + s[-4:]


def scan_line(line: str, min_entropy: float):
    found = []
    for name, pat in PATTERNS:
        for m in pat.finditer(line):
            val = m.group("v") if "v" in pat.groupindex else m.group(0)
            if name == "generic-secret-assign" and shannon(val) < min_entropy:
                continue
            found.append({"rule": name, "redacted": redact(val)})
    return found


def walk(root: Path, excludes: set[str], include_ext: set[str] | None):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if p.suffix.lower() in BINARY_EXTS:
                continue
            if include_ext and p.suffix.lower() not in include_ext:
                continue
            yield p


def main() -> int:
    ap = argparse.ArgumentParser(prog="secret-scan",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", nargs="?", default=".",
                    help="repo or file (default: .)")
    ap.add_argument("--include", action="append", default=[],
                    help="only scan files with these extensions (e.g. .py .yml)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="extra dir to exclude")
    ap.add_argument("--max-line", type=int, default=2000,
                    help="skip lines longer than N chars (default 2000)")
    ap.add_argument("--min-entropy", type=float, default=3.5,
                    help="min entropy for generic-secret-assign hits "
                         "(default 3.5)")
    ap.add_argument("--limit", type=int, default=500,
                    help="cap findings (default 500)")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    p = Path(args.path).resolve()
    if not p.exists():
        print(json.dumps({"error": f"not found: {args.path}"}), file=sys.stderr)
        return 2
    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    include_ext = {e if e.startswith(".") else "." + e
                   for e in args.include} or None

    findings: list[dict] = []
    files = walk(p, excludes, include_ext) if p.is_dir() else [p]
    by_rule: dict[str, int] = {}
    truncated = False
    for fp in files:
        try:
            with fp.open("r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    if len(line) > args.max_line:
                        continue
                    for hit in scan_line(line, args.min_entropy):
                        findings.append({
                            "path": str(fp.relative_to(p) if p.is_dir() else fp),
                            "line": lineno,
                            **hit,
                        })
                        by_rule[hit["rule"]] = by_rule.get(hit["rule"], 0) + 1
                        if len(findings) >= args.limit:
                            truncated = True
                            break
                    if truncated:
                        break
        except OSError:
            continue
        if truncated:
            break

    out = {"root": str(p), "count": len(findings), "truncated": truncated,
           "by_rule": dict(sorted(by_rule.items(), key=lambda kv: -kv[1])),
           "findings": findings}
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
