# complexity-report

Per-function cyclomatic complexity and LOC for Python code, sorted worst-first.
Use it to point an LLM agent at the actual hotspots in a large codebase
instead of letting it skim every file.

## Usage

```bash
./complexity-report.py
./complexity-report.py src/ --min 10 --top 20
./complexity-report.py src/foo.py --pretty
```

## Scoring

Starts at 1 and adds one for each branching construct:
`if` / `elif` / `for` / `while` / `except` / `assert` / `match` case /
conditional expr / each extra operand of `and`/`or` /
each comprehension and its `if` clauses.

## Output schema

```json
{
  "root": "/abs/root",
  "stats": {"functions": 8, "max_complexity": 22, "avg_complexity": 6.4},
  "functions": [
    {"path": "src/router.py", "qualname": "Router.dispatch", "name": "dispatch",
     "kind": "method", "line": 80, "loc": 95, "complexity": 22}
  ]
}
```

Sorted by complexity desc, then LOC desc, then path.

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `path`         | File or directory (default `.`)                     |
| `--min N`      | Only report complexity ≥ N (default 1)              |
| `--top N`      | Keep only the N worst                               |
| `--exclude N`  | Extra dir to exclude (repeatable)                   |
| `--pretty`     | Indent JSON                                         |

## Failure cases

- Files that fail to parse → `parse_errors`; other files still emit.
- Empty input → `functions: []`, `stats.max_complexity: 0`.

## Performance

Pure AST walk; O(N) in source size.
