# pr-context

JSON bundle of files relevant to the changes on a branch. Lists changed
files, related in-repo files reached via Python imports (one hop by default),
and any tests that import the changed modules.

## Usage

```bash
./pr-context.py                                       # main..HEAD
./pr-context.py --base origin/main --head feature
./pr-context.py --depth 2 --pretty
```

## Output schema

```json
{
  "base": "main",
  "head": "HEAD",
  "depth": 1,
  "changed_files": ["src/foo.py", "src/bar.py"],
  "related_files": ["src/util.py"],
  "related_tests": ["tests/test_foo.py"],
  "stats": {"changed": 2, "related": 1, "tests": 1}
}
```

## Arguments

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `--base`       | Base ref (default `main`)                           |
| `--head`       | Head ref (default `HEAD`)                           |
| `--path`       | Repo root (default `.`)                             |
| `--depth N`    | Import hops from each changed file (default 1)      |
| `--exclude N`  | Extra dir to exclude (repeatable)                   |
| `--pretty`     | Indent JSON                                         |

## Failure cases

- Not a git repo → exit 2.
- Refs missing → `git diff` fails; exit 1 with stderr message.

## Caveats

- Only Python imports are followed; non-Python touched files appear in
  `changed_files` but don't contribute to `related_files`.
- "Related tests" use pytest naming + import match; tests that exercise a
  module only via a runtime registration are not detected.
