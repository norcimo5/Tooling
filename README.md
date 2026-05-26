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
| `--no-links`   | Strip hyperlinks                                    |
| `--no-images`  | Strip images                                        |
| `--no-header`  | Omit the title/source metadata header               |

### Requirements

Python 3 with `beautifulsoup4`, `html2text`, and `lxml`:

```bash
pip install beautifulsoup4 html2text lxml
```
