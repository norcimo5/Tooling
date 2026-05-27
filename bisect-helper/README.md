# bisect-helper

Drive `git bisect run` with a test command and return the first bad commit as
JSON. Wraps the entire start/run/reset cycle and ensures the repo is reset
even on failure.

## Usage

```bash
./bisect-helper.py --good v1.0 --cmd 'pytest tests/test_api.py'
./bisect-helper.py --good abc123 --bad def456 --cmd 'make test' --pretty
```

The `--cmd` is run via `sh -c`. It must exit `0` for good commits and non-zero
for bad ones.

## Output schema

```json
{
  "good": "v1.0",
  "bad": "HEAD",
  "cmd": "pytest tests/test_api.py",
  "first_bad": "9f2c1ab",
  "commit_info": "9f2c1ab Alice\nRefactor handler\n\n...",
  "bisect_log": "Bisecting: 24 revisions left ... 9f2c1ab is the first bad commit ..."
}
```

If bisect can't determine a single bad commit, `first_bad` is absent and
`error` is set; `bisect_log` and `raw_stderr` are included for diagnosis.

## Arguments

| Flag       | Effect                                                  |
| ---------- | ------------------------------------------------------- |
| `--good`   | Known-good ref (older commit) — **required**            |
| `--bad`    | Known-bad ref (default `HEAD`)                          |
| `--cmd`    | Shell command; non-zero exit = bad — **required**       |
| `--path`   | Repo root (default `.`)                                 |
| `--pretty` | Indent JSON                                             |

## Failure cases

- Not a git repo → exit 2.
- Working tree not clean → exit 2 (refuses to risk losing changes).
- `git bisect start` fails → exit 1.
- Bisect inconclusive (skipped commits, command always passes, etc.) → exit 1.

## Cleanup

`git bisect reset` always runs at the end, even on failure, so HEAD is restored.
