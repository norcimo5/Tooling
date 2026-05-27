# file-skim

Emit the structural skeleton of a Python file as JSON — imports, classes (with
method names + line ranges), free functions (with signatures and docstring
first-line), and top-level CONSTANT assignments. No bodies, no comments.

## Usage

```bash
./file-skim.py src/foo.py
./file-skim.py src/foo.py --pretty
```

## Output schema

```json
{
  "path": "src/foo.py",
  "lines": 240,
  "module_doc": "Module description (first line of docstring).",
  "imports": ["import os", "from .x import Y as Z"],
  "constants": [{"name": "VERSION", "line": 3, "value_kind": "Constant"}],
  "classes": [
    {"name": "Foo", "line": 12, "end_line": 80, "bases": ["Base"],
     "doc": "Foo summary.",
     "methods": [
       {"name": "__init__", "line": 14, "signature": "__init__(self, x: int)"}
     ]}
  ],
  "functions": [
    {"name": "main", "line": 90, "end_line": 110,
     "signature": "main() -> int", "doc": "Entry point."}
  ]
}
```

Optional fields (`module_doc`, `doc`, `constants[].annotation`) are omitted when
absent to keep the JSON tight.

## Exit codes

- `0` parsed and emitted
- `1` syntax error in file (error reported in JSON)
- `2` argument is not a file

## Failure cases

- SyntaxError → `{"path": "...", "error": "SyntaxError: ... (line N)"}` and exit 1.
- Non-UTF-8 bytes are replaced with `�` (lossy but parseable).

## Performance

Single AST parse, no execution. Stable < 50 ms even on multi-thousand-line files.
