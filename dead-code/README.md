# dead-code

Find Python top-level defs (functions, classes, CONSTANTS) and imports that
look unused across a project. Best-effort static analysis — verify before
deleting, since dynamic dispatch (`getattr`, plugin registry, entry points)
can produce false positives.

## Usage

```bash
./dead-code.py                          # scan current dir
./dead-code.py src/
./dead-code.py src/ --pretty
```

## Output schema

```json
{
  "root": "/abs/root",
  "stats": {"unused_defs": 5, "unused_imports": 12},
  "unused_defs": [
    {"name": "old_helper", "path": "src/util.py", "line": 80, "kind": "function"}
  ],
  "unused_imports": [
    {"path": "src/foo.py", "line": 3, "name": "os", "module": "os"}
  ]
}
```

## Arguments

| Flag                  | Effect                                              |
| --------------------- | --------------------------------------------------- |
| `path`                | Repo or package root (default `.`)                  |
| `--exclude N`         | Extra dir to exclude (repeatable)                   |
| `--keep-test-funcs`   | Include `test_*` defs as candidates                 |
| `--pretty`            | Indent JSON                                         |

## What is checked

- **Defs:** top-level `def`, `class`, and UPPER_SNAKE constants.
- **Refs:** any `Name`/`Attribute` load anywhere in the project, plus strings
  in `__all__`, decorators, type-hint constants, and f-strings.
- **Imports:** an import is unused if its bound name never appears as a
  reference in the same file.

## Skipped by default

- Dunder methods (`__init__`, `__repr__`, …)
- `main`
- `test_*` (override with `--keep-test-funcs`)
- Names listed in any file's `__all__`

## Caveats

- Plugins registered via decorators that store callables in a registry: the
  name may look unused. Mark them in `__all__` or rename `_internal_*`.
- Strings used in `getattr(obj, "name")` are detected when the literal is a
  valid identifier; computed names are invisible.
