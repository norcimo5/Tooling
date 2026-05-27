# html2llm

Convert an HTML page into clean Markdown that an LLM can read with minimal
tokens. Strips scripts, styles, navs, footers, cookie banners, SVGs, hidden
elements; drops base64 `data:` images, tracking pixels, and tracking query
params; fences code blocks; trims redundant whitespace.

## Usage

```bash
./html2llm.py page.html                         # Markdown to stdout
./html2llm.py page.html -o page.md               # write to a file
./html2llm.py https://example.com --main         # fetch + main content only
cat page.html | ./html2llm.py -                  # read from stdin
```

Input can be a local `.html` file, an `http(s)` URL, or `-` for stdin.

## Options

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `-o, --output` | Write Markdown to a file (default: stdout)          |
| `--main`       | Keep only the main content, dropping boilerplate    |
| `--no-links`   | Strip hyperlinks (keep anchor text)                 |
| `--no-images`  | Strip images                                        |
| `--no-header`  | Omit the title/source metadata header               |
| `--stats`      | Print size/token reduction to stderr                |

## Measured savings (148 KB Slashdot homepage)

| Mode                       | Size  | ~Tokens | Smaller than raw |
| -------------------------- | ----- | ------- | ---------------- |
| raw HTML                   | 148K  | ~37,000 | —                |
| default                    | 42K   | ~10,500 | 72%              |
| `--no-links`               | 32K   | ~7,900  | 79%              |
| `--no-links --no-images`   | 30K   | ~7,500  | 80%              |

For maximum savings when URLs don't matter, use `--no-links` — anchor text
and source domains in headings are preserved.

## Requires

Python 3, `beautifulsoup4`, `html2text`, `lxml` (see top-level `requirements.txt`).
