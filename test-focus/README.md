# test-focus

For a pytest test (selector or bare name), find the test function and the
in-repo files it touches via imports, up to `--depth` hops. Lets an LLM agent
load exactly the relevant slice of a large repo when chasing a test failure.

## Usage

```bash
./test-focus.py tests/test_api.py::test_login
./test-focus.py test_login                   # search across test files
./test-focus.py test_login --depth 2 --pretty
```

## Output schema

```json
{
  "query": "tests/test_api.py::test_login",
  "test": {
    "file": "tests/test_api.py", "func": "test_login", "line": 42,
    "signature": "test_login(client, db)"
  },
  "depth": 1,
  "imports": ["app.auth", "app.db", "..."],
  "touched_files": ["app/auth.py", "app/db.py"]
}
```

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `selector`     | `path::func` or a bare function name                |
| `--path`       | Repo root (default `.`)                             |
| `--depth N`    | Import hops to follow (default 1)                   |
| `--exclude N`  | Extra dir to exclude (repeatable)                   |
| `--pretty`     | Indent JSON                                         |

## Exit codes

- `0` test found
- `1` test not found
- `2` `--path` is not a directory

## Caveats

- Static import analysis — fixtures resolved by name (e.g. `client`) are not
  followed unless they appear in the test's imports.
- Bare-name search uses pytest naming conventions (`test_*.py`, `*_test.py`).
