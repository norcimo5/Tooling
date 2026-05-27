# patch-apply

Apply a unified diff strictly (no fuzz) and report success/failure as JSON.
Uses `git apply` when in a git repo, otherwise falls back to `patch -p1`.
Always runs a dry-run check first.

## Usage

```bash
./patch-apply.py changes.patch                       # apply
./patch-apply.py - < changes.patch                   # via stdin
./patch-apply.py changes.patch --check               # dry-run only
./patch-apply.py changes.patch --3way                # allow trivial merges
```

## Output schema

```json
{
  "engine": "git apply",
  "check_only": false,
  "files": ["src/foo.py", "src/bar.py"],
  "check_ok": true,
  "applied": true
}
```

If something fails:

```json
{
  "engine": "git apply",
  "check_ok": false,
  "check_stderr": "error: patch failed: src/foo.py:42",
  "applied": false
}
```

## Arguments

| Flag       | Effect                                                  |
| ---------- | ------------------------------------------------------- |
| `patch`    | Patch file path, or `-` for stdin                       |
| `--path`   | Project root (default `.`)                              |
| `--check`  | Dry-run only — never modify the working tree            |
| `--3way`   | `git apply --3way` (allow merge of trivial conflicts)   |
| `--pretty` | Indent JSON                                             |

## Exit codes

- `0` patch applied (or `--check` succeeded)
- `1` patch did not apply (or `--check` failed)
- `2` invalid `--path`

## Failure cases

- Conflict / context mismatch → `check_ok: false` with `check_stderr` containing
  the engine's diagnostic.
- Not in a git repo and `patch` not installed → exit 1.
