# secret-scan

Regex scan for likely secrets — cloud creds, private keys, common provider
tokens, and high-entropy assignment patterns. Findings are redacted (first 4
+ `…` + last 4) so the JSON is safe to share with an LLM.

## Usage

```bash
./secret-scan.py                          # scan current dir
./secret-scan.py src/ --include .py .yml
./secret-scan.py --min-entropy 4.0 --pretty
```

## Built-in rules

`aws-access-key`, `aws-secret`, `google-api-key`, `github-pat` / `oauth` /
`server` / `user`, `slack-token`, `stripe-secret` / `restricted`,
`openai-key`, `anthropic-key`, `jwt`, `private-key-pem`,
`generic-secret-assign` (entropy-gated).

## Output schema

```json
{
  "root": "/abs/root",
  "count": 2,
  "truncated": false,
  "by_rule": {"aws-access-key": 1, "github-pat": 1},
  "findings": [
    {"path": "config/dev.env", "line": 12, "rule": "aws-access-key",
     "redacted": "AKIA…IJ8K"}
  ]
}
```

## Arguments

| Flag             | Effect                                              |
| ---------------- | --------------------------------------------------- |
| `path`           | Directory or single file (default `.`)              |
| `--include EXT`  | Only scan files with these extensions (repeatable)  |
| `--exclude DIR`  | Extra dir to exclude (repeatable)                   |
| `--max-line N`   | Skip lines longer than N chars (default 2000)       |
| `--min-entropy N`| Min Shannon entropy for `generic-secret-assign`     |
| `--limit N`      | Cap findings (default 500)                          |
| `--pretty`       | Indent JSON                                         |

## Exit codes

- `0` no findings
- `1` secrets found (still valid JSON)
- `2` path missing

## Caveats

- Designed to be conservative — expect false positives in test fixtures and
  example configs. Triage before rotating keys.
- Binary files (by extension) are skipped automatically.
