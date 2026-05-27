# repo-map

Compact JSON map of a repository — for giving an LLM agent a single
token-cheap overview of an unfamiliar codebase.

## Usage

```bash
./repo-map.py                   # map current directory
./repo-map.py /path/to/repo
./repo-map.py --symbols         # include top-level Python symbols
./repo-map.py --max-depth 2     # don't recurse deeper than 2 levels
./repo-map.py --pretty | jq .   # human-readable
```

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `path`         | Repo root (default `.`)                             |
| `--symbols`    | Add top-level Python symbols per `.py` file         |
| `--exclude N`  | Extra dir/file name to exclude (repeatable)         |
| `--max-depth`  | Limit traversal depth                               |
| `--max-files`  | Hard cap on files returned (default 10,000)         |
| `--pretty`     | Indent JSON output                                  |

Default excludes: `.git`, `__pycache__`, `node_modules`, `.venv`, `venv`,
`.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `dist`, `build`, `.next`,
`target`, `.idea`, `.vscode`, `.cache`, `*.egg-info`.

## Output schema

```json
{
  "root": "/abs/path",
  "stats": {
    "files": 123,
    "bytes": 456789,
    "by_lang": {"python": {"files": 50, "bytes": 200000, "lines": 5000}},
    "truncated": false
  },
  "files": [
    {"path": "src/foo.py", "bytes": 1234, "lang": "python", "lines": 100,
     "symbols": ["foo", "Bar"]}
  ]
}
```

## Failure cases

- Path is not a directory → exit 2, JSON error on stderr.
- Unreadable files are skipped silently.
- Hit `--max-files` cap → `stats.truncated = true`.

## Performance

Single pass `os.walk`, sorted output (deterministic), reads each file's bytes
only to count lines (and only for files under 5 MB). For huge monorepos
combine `--max-depth` and `--exclude` to scope the scan.
