# type-probe

Extract static type info for a single Python symbol as JSON — signature,
parameter annotations, return type, decorators, docstring. AST-only, no
imports executed (safe for code with side effects).

## Usage

```bash
./type-probe.py src/foo.py::handle
./type-probe.py src/foo.py::Foo.run
./type-probe.py src/foo.py::Foo --pretty
```

## Output schema (function/method)

```json
{
  "path": "src/foo.py",
  "kind": "method",
  "name": "run",
  "parent": "Foo",
  "line": 24,
  "params": [
    {"name": "self", "kind": "positional", "annotation": null, "default": null},
    {"name": "n", "kind": "positional", "annotation": "int", "default": "1"}
  ],
  "returns": "str",
  "decorators": ["staticmethod"],
  "docstring": "Do the thing.",
  "signature": "run(self, n: int=1) -> str"
}
```

For a class, `params` and `returns` are absent; `bases` and `signature` (e.g.
`Foo(Base)`) are present.

## Arguments

| Flag       | Effect                                                  |
| ---------- | ------------------------------------------------------- |
| `target`   | `path/to/file.py::Symbol` or `...::Class.method`        |
| `--pretty` | Indent JSON                                             |

## Exit codes

- `0` symbol found
- `1` symbol not found or syntax error
- `2` malformed target / missing file

## Caveats

- Only static annotations — no inference. If a parameter has no `:T`, `annotation` is `null`.
- Nested classes (`Class.Inner.method`) are supported.
