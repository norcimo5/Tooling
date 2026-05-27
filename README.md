# Tooling

Linux Python3 command-line tools for autonomous coding agents — designed to
**reduce LLM token consumption** while **increasing coding/debugging
velocity** on real enterprise codebases.

Every tool is a standalone CLI utility that emits **compact JSON by default**
(`--pretty` to indent). Outputs are deterministic, sorted, and reproducible so
they cache well in LLM context.

## Tools

### Context reduction

| Tool | Purpose |
| ---- | ------- |
| [html2llm](html2llm) | Convert HTML to LLM-friendly Markdown; strips chrome, dedupes link metadata, drops base64/tracking junk. |
| [file-skim](file-skim) | Structural skeleton of a Python file (imports, classes, functions, constants) — no bodies. |
| [doc-snippets](doc-snippets) | Extract all docstrings (and optional comments) from a project as JSON. |
| [json-prune](json-prune) | Shrink a JSON document — drop noisy keys, truncate long strings/arrays. |

### Code understanding

| Tool | Purpose |
| ---- | ------- |
| [repo-map](repo-map) | Compact JSON map of an entire repo (paths, sizes, langs, lines, top symbols). |
| [symbol-search](symbol-search) | Locate Python defs across a repo by name or regex; emits file:line + signature. |
| [api-surface](api-surface) | Public API of a file/package — classes, methods, functions with signatures & docstring. |

### Semantic analysis

| Tool | Purpose |
| ---- | ------- |
| [call-graph](call-graph) | Static function-call graph for Python file(s). |
| [dep-graph](dep-graph) | Inter-file import graph for a Python project. |
| [type-probe](type-probe) | Extract static type info for one symbol (params, return, decorators, docstring). |
| [dead-code](dead-code) | Find unused top-level defs and unused imports. |
| [complexity-report](complexity-report) | McCabe cyclomatic complexity + LOC per function. |
| [secret-scan](secret-scan) | Regex scan for likely secrets; findings are redacted. |

### Debugging

| Tool | Purpose |
| ---- | ------- |
| [stack-trim](stack-trim) | Trim a Python traceback to user frames; optional source context. |
| [test-focus](test-focus) | For a pytest test, list the in-repo files it touches via imports. |
| [bisect-helper](bisect-helper) | Drive `git bisect run`; returns the first bad commit + diff stats. |
| [lint-collate](lint-collate) | Run ruff/pyflakes; emit normalized JSON findings. |

### Change management

| Tool | Purpose |
| ---- | ------- |
| [diff-summary](diff-summary) | Summarize a unified diff (per-file change type, hunks, touched symbols). |
| [patch-apply](patch-apply) | Apply a unified diff strictly via `git apply` / `patch`; JSON status. |
| [pr-context](pr-context) | For a branch's changes: changed files + related files (one import hop) + related tests. |
| [commit-pickaxe](commit-pickaxe) | `git log -S/-G` wrapper; JSON commits with subject and optional diffs. |

## Conventions

- **JSON-by-default, compact.** Use `--pretty` for indented output.
- **Deterministic.** Files and findings are sorted.
- **Standalone.** Each tool is a single `.py` in its own directory; no shared
  package import.
- **Token-cheap exits.** Errors are `{"error": "..."}` on stderr, non-zero exit;
  partial results (parse errors, truncation) are flagged in the JSON.
- **Excludes by default.** All repo walkers skip `.git`, `__pycache__`, `.venv`,
  `venv`, `node_modules`, `dist`, `build`, `.mypy_cache`, `.pytest_cache`,
  `.ruff_cache`, `target`, `.idea`, `.vscode`.

## Install / use

The tools are designed to be run in place — clone and execute:

```bash
git clone https://github.com/norcimo5/Tooling.git
cd Tooling
./repo-map/repo-map.py ~/code/some-repo --symbols --pretty
```

Most tools use only the Python standard library. The exceptions:

| Tool        | Extra dependency               |
| ----------- | ------------------------------ |
| html2llm    | `beautifulsoup4`, `html2text`, `lxml` |
| lint-collate| `ruff` (preferred) or `pyflakes` |

Install with `pip install -r requirements.txt`.

## Composing the tools

These are designed to compose. A few starting points:

```bash
# Quick "what is this repo?" briefing for an LLM
./repo-map/repo-map.py ~/code/repo --symbols > map.json
./api-surface/api-surface.py ~/code/repo/src > api.json
./doc-snippets/doc-snippets.py ~/code/repo/src > docs.json

# Triage a failing test
./stack-trim/stack-trim.py pytest.log --project ~/code/repo --context 2
./test-focus/test-focus.py tests/test_api.py::test_login --path ~/code/repo

# Review a PR
./pr-context/pr-context.py --base main --head feature --path ~/code/repo
./diff-summary/diff-summary.py main..HEAD
./lint-collate/lint-collate.py src/
```

## Project guidance

See [`CLAUDE.md`](CLAUDE.md) for the design goals and constraints applied to
every tool in this suite.
