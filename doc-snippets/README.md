# doc-snippets

Extract docstrings (and optionally non-trivial `#`-comments) from a Python
file or package as JSON — a compact knowledge-base view at a fraction of the
source size.

## Usage

```bash
./doc-snippets.py src/                       # docstrings only
./doc-snippets.py src/ --comments            # include # comments (>= 8 chars)
./doc-snippets.py src/foo.py --pretty
```

## Output schema

```json
{
  "root": "/abs/root",
  "stats": {"files": 12, "snippets": 78},
  "files": [
    {
      "path": "src/foo.py",
      "items": [
        {"kind": "module", "line": 1, "doc": "Foo module — does X."},
        {"kind": "class", "name": "Foo", "line": 10, "doc": "Public Foo class."},
        {"kind": "method", "name": "Foo.run", "line": 14, "doc": "Run once."},
        {"kind": "comment", "line": 33, "doc": "TODO: switch to background."}
      ]
    }
  ]
}
```

`kind` is one of `module`, `class`, `function`, `method`, `comment`.
`name` is omitted for `module` and `comment`. Items are sorted by line.

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `path`         | File or directory (default `.`)                     |
| `--comments`   | Also include `#` comments ≥ 8 chars (skips noqa/type)|
| `--exclude N`  | Extra dir to exclude (repeatable)                   |
| `--pretty`     | Indent JSON                                         |

## Failure cases

- Files that fail to parse → reported in `parse_errors`; other files still emit.

## Use case

Hand this JSON to an LLM as a "what does this codebase do?" briefing. Pair
with [api-surface](../api-surface) for signatures + docs together.
