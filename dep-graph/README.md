# dep-graph

Inter-file import graph for a Python project as JSON — `modules` are nodes
and `edges` are `importer -> importee` relations. Relative imports are
resolved to in-repo files when possible. External (3rd-party / stdlib)
imports are only included with `--external`.

## Usage

```bash
./dep-graph.py src/                           # internal edges only
./dep-graph.py src/ --external                # include external leaves
./dep-graph.py src/ --pretty
```

## Output schema

```json
{
  "root": "/abs/root",
  "modules": [
    {"id": "pkg.mod", "file": "pkg/mod.py"},
    {"id": "requests", "external": true}
  ],
  "edges": [
    {"from": "pkg.mod", "to": "pkg.other", "kind": "absolute", "external": false},
    {"from": "pkg.mod", "to": "requests", "kind": "absolute", "external": true}
  ],
  "stats": {"modules": 42, "edges": 91}
}
```

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `path`         | Python package or repo directory                    |
| `--external`   | Include external modules as leaf nodes              |
| `--exclude N`  | Extra dir to exclude (repeatable)                   |
| `--pretty`     | Indent JSON                                         |

## Failure cases

- Path is not a directory → exit 2.
- A file that fails to parse is reported in `parse_errors`; other files still emit.

## Caveats

- Dynamic imports (`importlib.import_module(...)`, `__import__`) are invisible
  to static analysis.
- Conditional imports inside functions are still recorded — they aren't
  scoped.

## Performance

Pure AST. O(file size). Use `--exclude` to skip vendored dirs in a monorepo.
