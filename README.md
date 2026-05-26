# Tooling

Small command-line tools to make everyday tasks easier.

## html2llm

Convert an HTML page into clean Markdown that an LLM can read easily. It strips
the noise that bloats raw HTML — scripts, styles, nav bars, footers, cookie
banners, SVGs, comments, and hidden elements — and emits tidy Markdown with an
optional title/source header.

### Usage

```bash
./html2llm.py page.html                 # Markdown to stdout
./html2llm.py page.html -o page.md       # write to a file
./html2llm.py https://example.com --main # fetch a URL, keep main content only
cat page.html | ./html2llm.py -          # read HTML from stdin
```

Input can be a local `.html` file, an `http(s)` URL, or `-` for stdin.

### Options

| Flag           | Effect                                              |
| -------------- | --------------------------------------------------- |
| `-o, --output` | Write Markdown to a file (default: stdout)          |
| `--main`       | Keep only the main content, dropping boilerplate    |
| `--no-links`   | Strip hyperlinks (keeps the anchor text)            |
| `--no-images`  | Strip images                                        |
| `--no-header`  | Omit the title/source metadata header               |
| `--stats`      | Print size/token reduction to stderr                |

### Token efficiency

The point of this tool is to spend fewer tokens on a page while keeping its
information. It strips markup, scripts, chrome, and duplicated link metadata;
drops base64 `data:` images (token bombs) and tracking query params; fences code
blocks; and trims redundant whitespace. On a saved Slashdot homepage:

| Mode                       | Size       | Approx. tokens | Smaller than raw HTML |
| -------------------------- | ---------- | -------------- | --------------------- |
| raw HTML                   | 148 KB     | ~37,000        | —                     |
| default                    | 42 KB      | ~10,500        | 72%                   |
| `--no-links`               | 32 KB      | ~7,900         | 79%                   |
| `--no-links --no-images`   | 30 KB      | ~7,500         | 80%                   |

For maximum savings when the URLs don't matter, use `--no-links` — anchor text
(and source domains in headings) is preserved, only the URLs are dropped. Pass
`--stats` to see the reduction for your own page.

### Requirements

Python 3 with `beautifulsoup4`, `html2text`, and `lxml`:

```bash
pip install beautifulsoup4 html2text lxml
```
