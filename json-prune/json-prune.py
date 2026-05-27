#!/usr/bin/env python3
"""json-prune — shrink a JSON document for LLM consumption.

Drops keys matching `--drop` patterns, truncates long strings and arrays,
optionally keeps only paths matching `--keep`. Deterministic, single-pass,
streaming-friendly for documents that still fit in memory.
"""
from __future__ import annotations
import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path


def matches_any(name: str, patterns: list[str]) -> bool:
    for p in patterns:
        if p.startswith("/") and p.endswith("/"):
            if re.search(p[1:-1], name):
                return True
        elif fnmatch.fnmatchcase(name, p):
            return True
    return False


def prune(obj, drop, keep, max_str, max_arr, path="$"):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if drop and matches_any(k, drop):
                continue
            if keep and not (matches_any(k, keep)
                             or any(matches_any(path, [k]) for _ in [1])):
                # If keep is set, retain only keys matching keep OR with
                # descendants that match (we do a conservative include).
                # Simpler: keep everything not dropped, then optionally filter
                # at the top level. The default keep=[] means keep all.
                pass
            out[k] = prune(v, drop, keep, max_str, max_arr, f"{path}.{k}")
        return out
    if isinstance(obj, list):
        truncated = max_arr is not None and len(obj) > max_arr
        items = obj[:max_arr] if truncated else obj
        out = [prune(it, drop, keep, max_str, max_arr, f"{path}[{i}]")
               for i, it in enumerate(items)]
        if truncated:
            out.append({"__truncated__": len(obj) - max_arr})
        return out
    if isinstance(obj, str):
        if max_str is not None and len(obj) > max_str:
            return obj[:max_str] + f"…<+{len(obj) - max_str} chars>"
        return obj
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(prog="json-prune",
                                 description=__doc__.split("\n", 1)[0])
    ap.add_argument("input", nargs="?", default="-",
                    help="JSON file, or '-' for stdin (default '-')")
    ap.add_argument("--drop", action="append", default=[],
                    help="key pattern to drop (fnmatch or /regex/), repeatable")
    ap.add_argument("--keep", action="append", default=[],
                    help="top-level key pattern to keep (others dropped), "
                         "repeatable")
    ap.add_argument("--max-string", type=int, default=None,
                    help="truncate strings longer than N chars")
    ap.add_argument("--max-array", type=int, default=None,
                    help="truncate arrays longer than N items")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    text = (sys.stdin.read() if args.input == "-"
            else Path(args.input).read_text("utf-8", errors="replace"))
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON: {e}"}), file=sys.stderr)
        return 1

    pruned = prune(obj, args.drop, args.keep, args.max_string, args.max_array)

    if args.keep and isinstance(pruned, dict):
        pruned = {k: v for k, v in pruned.items()
                  if matches_any(k, args.keep)}

    if args.pretty:
        print(json.dumps(pruned, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(pruned, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
