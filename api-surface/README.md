# api-surface

Extract the public API of a Python file or package as JSON — classes (with
public methods), functions, signatures, and first-line docstrings. Honors
`__all__`; otherwise filters by leading-underscore convention.

## Usage

```bash
./api-surface.py path/to/file.py
./api-surface.py path/to/package/    # walks all .py files
./api-surface.py path/to/package/ --pretty
```

## Output schema

```json
{
  "root": "/abs/root",
  "count": 3,
  "modules": [
    {
      "path": "pkg/core.py",
      "module_doc": "Core abstractions.",
      "__all__": ["Foo", "make_foo"],
      "classes": [
        {"name": "Foo", "line": 10, "bases": ["Base"], "doc": "Foo summary.",
         "methods": [
           {"name": "run", "line": 14, "signature": "run(self, x: int) -> str",
            "doc": "Run once."}
         ]}
      ],
      "functions": [
        {"name": "make_foo", "line": 40,
         "signature": "make_foo(cfg: Cfg) -> Foo", "doc": "Factory."}
      ]
    }
  ]
}
```

Optional fields are omitted when missing.

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `path`         | Python file or package directory                    |
| `--exclude N`  | Extra dir to exclude (repeatable)                   |
| `--pretty`     | Indent JSON                                         |

## Failure cases

- Path missing → exit 2, JSON error on stderr.
- A module that fails to parse is reported with `error` and skipped (other modules still emit).

## Performance

Pure AST. No imports executed, so side-effects in modules are safe.
