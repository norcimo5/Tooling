# stack-trim

Trim a Python traceback to the frames that actually matter (your code), so an
LLM doesn't waste tokens reading layers of stdlib/framework noise.

## Usage

```bash
python failing.py 2>&1 | ./stack-trim.py -          # from stdin
./stack-trim.py crash.log --context 2               # 2 lines of source around each frame
./stack-trim.py crash.log --keep thirdparty         # also keep site-packages frames
./stack-trim.py crash.log --project /repo --pretty
```

## Output schema

```json
{
  "error": {"type": "KeyError", "message": "'foo'"},
  "frames_total": 17,
  "frames_kept": 3,
  "frames": [
    {"file": "/repo/svc/handlers.py", "line": 88, "func": "handle",
     "code": "result = config['foo']", "class": "user",
     "source": [
       {"line": 86, "code": "    ..."},
       {"line": 87, "code": "    # comment"},
       {"line": 88, "code": "    result = config['foo']"}
     ]}
  ]
}
```

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `input`        | Traceback file, or `-` for stdin (default `-`)      |
| `--project`    | Project root for `user` classification (default `.`)|
| `--keep K`     | Also keep `stdlib`/`thirdparty` frames (repeatable) |
| `--context N`  | N lines of source around each kept frame            |
| `--pretty`     | Indent JSON                                         |

## Classification

A frame is `user` if its file is inside `--project`, `thirdparty` if the path
contains `site-packages`/`dist-packages`, and `stdlib` if under Python's
stdlib path (or `sys.prefix`).

## Failure cases

- No traceback in the input → `frames_total: 0`, `error: null`, exit 0 (still valid JSON).
- `--context` with an unreadable file silently omits the `source` field.
