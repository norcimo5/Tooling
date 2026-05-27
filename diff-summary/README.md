# diff-summary

Summarize a unified diff as JSON — per-file change type, line counts, hunk
count, and a heuristic list of changed Python `def`/`class` symbols.

## Usage

```bash
git diff main..HEAD | ./diff-summary.py -
./diff-summary.py changes.patch
./diff-summary.py main..HEAD                 # treats arg as a git range
./diff-summary.py main..HEAD --pretty
```

## Output schema

```json
{
  "totals": {
    "files": 4,
    "added": 87,
    "removed": 23,
    "by_change": {"modified": 3, "added": 1}
  },
  "files": [
    {"path": "src/foo.py", "old_path": "src/foo.py",
     "change": "modified", "added": 30, "removed": 12,
     "hunks": 4, "symbols": ["def handle", "class Foo"]}
  ]
}
```

`change` is one of `added`, `modified`, `deleted`, `renamed`.
`symbols` is omitted when empty.

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `input`        | Diff file, `-` for stdin, or git range (default `-`)|
| `--pretty`     | Indent JSON                                         |

## Failure cases

- Argument neither a file nor `-` nor a valid git range → exit 1 with stderr message.
- Symbol heuristic only looks at `+` lines for `def`/`class` — moved code may not appear in `symbols`.

## Performance

Single linear pass over the diff text.
