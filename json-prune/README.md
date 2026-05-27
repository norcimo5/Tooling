# json-prune

Shrink a JSON document for LLM consumption — drop noisy keys, truncate long
strings and arrays, optionally keep only the top-level keys that matter.

## Usage

```bash
curl -s api/users/123 | ./json-prune.py - --drop '*_at' --max-string 200
./json-prune.py response.json --drop 'meta' --drop '/^_/'
./json-prune.py response.json --keep 'data' --max-array 50 --pretty
```

## Patterns

`--drop` and `--keep` accept:
- **fnmatch glob** — e.g. `*_at`, `user_*`, `meta`
- **/regex/** — e.g. `/^_/` to drop underscore-prefixed keys

`--drop` operates on *any* key in the tree. `--keep` operates on top-level
keys only (so the structure beneath survives).

## Arguments

| Flag             | Effect                                              |
| ---------------- | --------------------------------------------------- |
| `input`          | JSON file, `-` for stdin (default `-`)              |
| `--drop PATTERN` | Key pattern to drop (repeatable)                    |
| `--keep PATTERN` | Top-level key pattern to keep (repeatable)          |
| `--max-string N` | Truncate strings longer than N chars                |
| `--max-array N`  | Truncate arrays longer than N items                 |
| `--pretty`       | Indent JSON                                         |

## Truncation markers

- Strings: `"first N chars…<+K chars>"`
- Arrays: a trailing `{"__truncated__": K}` marker noting how many items dropped.

## Exit codes

- `0` valid JSON pruned
- `1` invalid JSON in input

## Performance

Single recursive pass. Holds the whole document in memory; for huge JSON
streams pre-split with `jq` first.
