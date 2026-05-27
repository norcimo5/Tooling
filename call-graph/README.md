# call-graph

Static function-call graph for Python file(s) as JSON. Each function or method
is a node; each call site is an edge to the *name* of the callee. Best-effort
name resolution (`resolved: true` when the callee name matches a known
node in the scanned set).

## Usage

```bash
./call-graph.py src/foo.py
./call-graph.py src/pkg/ --pretty
```

## Output schema

```json
{
  "root": "/abs/root",
  "nodes": [
    {"id": "pkg.mod.Foo.run", "name": "run", "kind": "method",
     "file": "pkg/mod.py", "line": 14}
  ],
  "edges": [
    {"from": "pkg.mod.Foo.run", "to": "_helper", "line": 17, "resolved": true}
  ],
  "stats": {"functions": 12, "calls": 34, "resolved": 28},
  "parse_errors": [{"path": "broken.py", "error": "SyntaxError: ... (line 3)"}]
}
```

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `path`         | Python file or directory                            |
| `--exclude N`  | Extra dir to exclude (repeatable)                   |
| `--pretty`     | Indent JSON                                         |

## Caveats

- Python is dynamic: `getattr`, decorators, dispatch tables, and methods called
  on `self` whose type isn't known statically can't be resolved. Edges have
  `resolved: false` in those cases.
- The `to` field is the bare callee name, not a qualified id.
- Only walks defined functions — calls at module top level are not nodes.

## Performance

Pure AST walk, no execution. O(file size). Combine with `--exclude` for big
trees.
