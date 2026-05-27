# lint-collate

Run a Python linter (`ruff` if available, `pyflakes` otherwise) and emit
normalized JSON findings — so an LLM agent sees the same shape regardless of
which linter is installed.

## Usage

```bash
./lint-collate.py                          # lint current dir
./lint-collate.py src/ tests/
./lint-collate.py src/ --tool pyflakes
./lint-collate.py src/ --pretty
```

## Output schema

```json
{
  "tool": "ruff",
  "count": 12,
  "truncated": false,
  "by_code": {"F401": 5, "E501": 4, "uncoded": 3},
  "findings": [
    {"file": "src/foo.py", "line": 10, "col": 1, "code": "F401",
     "severity": "error", "message": "`os` imported but unused"}
  ]
}
```

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `paths`        | Files/dirs to lint (default `.`)                    |
| `--tool`       | `auto` / `ruff` / `pyflakes` (default `auto`)       |
| `--limit N`    | Cap on findings (default 500)                       |
| `--pretty`     | Indent JSON                                         |

## Exit codes

- `0` no findings
- `1` findings present (still valid JSON)
- `2` no linter installed

## Requires

`ruff` (preferred) or `pyflakes` on `PATH`. Install with `pip install ruff` or
`pip install pyflakes`.
