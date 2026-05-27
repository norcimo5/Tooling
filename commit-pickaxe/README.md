# commit-pickaxe

Find commits that introduced or removed a string (or regex). Wraps
`git log -S` / `-G` and emits JSON instead of paged log output.

## Usage

```bash
./commit-pickaxe.py 'DEPRECATED_FLAG'                    # literal
./commit-pickaxe.py 'TODO\(.*\):' --regex                # regex
./commit-pickaxe.py 'old_handler' --diff                 # include hunks
./commit-pickaxe.py foo --paths src/ tests/              # scoped
```

## Output schema

```json
{
  "pattern": "DEPRECATED_FLAG",
  "regex": false,
  "count": 3,
  "commits": [
    {"sha": "9f2c1ab...", "author": "Alice", "date": "2026-04-12T11:03:08-07:00",
     "subject": "Remove DEPRECATED_FLAG", "diff": "..."}
  ]
}
```

`diff` is included only with `--diff`.

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `pattern`      | Literal string, or regex with `--regex`             |
| `--regex`      | Use `git log -G` instead of `-S`                    |
| `--path`       | Repo root (default `.`)                             |
| `--limit N`    | Max commits (default 50)                            |
| `--diff`       | Include touching diff hunks                         |
| `--paths ...`  | Restrict to these paths                             |
| `--pretty`     | Indent JSON                                         |

## Exit codes

- `0` commits found
- `1` no commits matched (or `git log` failed)
- `2` not a git repo

## Performance

For huge histories use `--paths` and a tight `--limit`. `git log -S` is far
cheaper than scanning checkouts by hand.
