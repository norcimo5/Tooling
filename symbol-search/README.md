# symbol-search

Locate Python symbol definitions (functions, classes, methods) across a repo.
Deterministic JSON output with file:line, kind, and signature — a low-token
alternative to grep for "where is X defined?".

## Usage

```bash
./symbol-search.py MyClass                   # all defs containing "MyClass"
./symbol-search.py '^handle_.*' --regex      # regex match on names
./symbol-search.py user --kind method        # only methods
./symbol-search.py --path ../svc --case foo
```

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `name`         | Substring (or regex with `--regex`) to match        |
| `--path`       | Repo root (default `.`)                             |
| `--kind K`     | Restrict to `function`/`method`/`class` (repeatable)|
| `--regex`      | Treat `name` as a Python regex                      |
| `--case`       | Case-sensitive match                                |
| `--exclude N`  | Extra dir to exclude (repeatable)                   |
| `--limit N`    | Cap on matches (default 500)                        |
| `--pretty`     | Indent JSON                                         |

## Output schema

```json
{
  "query": "MyClass",
  "count": 2,
  "truncated": false,
  "matches": [
    {"path": "src/m.py", "line": 12, "kind": "class",
     "name": "MyClass", "signature": "MyClass(Base)", "parent": null}
  ],
  "parse_errors": [{"path": "broken.py", "error": "parse: SyntaxError"}]
}
```

`parent` is the enclosing class name for methods, `null` otherwise.

## Exit codes

- `0` matches found
- `1` no matches (still valid JSON)
- `2` path is not a directory

## Failure cases

- Files that fail to parse are reported in `parse_errors`, not raised.
- Only Python (`.py`, `.pyi`) is scanned — use language-specific tools for others.

## Performance

Single AST parse per file (no execution). For huge repos, narrow with `--path`,
`--exclude`, and `--kind`.
