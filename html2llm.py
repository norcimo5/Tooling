#!/usr/bin/env python3
"""
html2llm — Convert an HTML page into clean Markdown that an LLM can read easily.

It strips the noise that bloats raw HTML (scripts, styles, nav bars, footers,
cookie banners, SVGs, comments, hidden elements) and emits tidy Markdown with an
optional metadata header (title + source).

INPUT can be:
    - a path to a local .html file
    - an http(s) URL (it will be fetched)
    - "-" to read HTML from stdin

Examples:
    ./html2llm.py page.html                 # -> Markdown on stdout
    ./html2llm.py page.html -o page.md       # -> write to file
    ./html2llm.py https://example.com --main # fetch + keep main content only
    cat page.html | ./html2llm.py -          # read from stdin
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import html2text
from bs4 import BeautifulSoup, Comment

# Tags that never carry readable content worth keeping.
NOISE_TAGS = (
    "script", "style", "noscript", "template", "svg", "canvas",
    "iframe", "form", "button", "input", "select", "textarea",
    "nav", "footer", "header", "aside", "dialog",
)

# Substrings in id/class that usually mark chrome, ads, or navigation.
NOISE_PATTERNS = re.compile(
    r"(?:^|[-_ ])(?:nav|navbar|menu|sidebar|footer|header|banner|cookie|"
    r"consent|advert|advertis|sponsor|promo|popup|modal|newsletter|"
    r"subscribe|social|share|comment|related|breadcrumb|pagination|"
    r"skip-link|masthead)(?:$|[-_ ])",
    re.IGNORECASE,
)


def read_input(source: str) -> tuple[str, str | None]:
    """Return (html, base_url). base_url is set only when fetching a URL."""
    if source == "-":
        return sys.stdin.read(), None
    if source.startswith(("http://", "https://")):
        req = Request(source, headers={"User-Agent": "html2llm/1.0"})
        with urlopen(req, timeout=30) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace"), source
    path = Path(source)
    if not path.is_file():
        sys.exit(f"html2llm: no such file: {source}")
    return path.read_text(encoding="utf-8", errors="replace"), None


def strip_noise(soup: BeautifulSoup) -> None:
    """Remove tags and elements that don't help an LLM understand the page."""
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    for tag in soup(list(NOISE_TAGS)):
        tag.decompose()

    for tag in soup.find_all(True):
        # Drop explicitly hidden elements.
        if tag.has_attr("hidden") or tag.get("aria-hidden") == "true":
            tag.decompose()
            continue
        style = (tag.get("style") or "").replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            tag.decompose()
            continue
        # Drop chrome/ads matched by id or class name.
        ident = " ".join(filter(None, [tag.get("id", ""), *tag.get("class", [])]))
        if ident and NOISE_PATTERNS.search(ident):
            tag.decompose()


def extract_main(soup: BeautifulSoup):
    """Pick the node most likely to hold the article body."""
    for selector in ("main", "article", "[role=main]"):
        node = soup.select_one(selector)
        if node and node.get_text(strip=True):
            return node

    # Fallback: among block containers, choose the one with the most text.
    best, best_len = None, 0
    for node in soup.find_all(("div", "section")):
        text_len = len(node.get_text(strip=True))
        if text_len > best_len:
            best, best_len = node, text_len
    return best or soup.body or soup


def to_markdown(node, base_url: str | None, ignore_links: bool,
                ignore_images: bool) -> str:
    conv = html2text.HTML2Text(baseurl=base_url or "")
    conv.body_width = 0            # no hard wrapping — keep one line per block
    conv.unicode_snob = True       # keep real unicode, not escapes
    conv.skip_internal_links = True
    conv.protect_links = True
    conv.ignore_links = ignore_links
    conv.ignore_images = ignore_images
    md = conv.handle(str(node))
    # Collapse runs of 3+ blank lines into a single blank line.
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def build_header(soup: BeautifulSoup, source: str) -> str:
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    lines = []
    if title:
        lines.append(f"# {title}")
    origin = source if source.startswith(("http://", "https://")) else None
    if origin:
        lines.append(f"\n_Source: {origin}_")
    return ("\n".join(lines) + "\n\n") if lines else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="html2llm",
        description="Convert an HTML page into clean, LLM-friendly Markdown.",
    )
    parser.add_argument("input", help="HTML file, http(s) URL, or '-' for stdin")
    parser.add_argument("-o", "--output", help="write Markdown here (default: stdout)")
    parser.add_argument("--main", action="store_true",
                        help="keep only the main content (drop boilerplate)")
    parser.add_argument("--no-links", action="store_true", help="strip hyperlinks")
    parser.add_argument("--no-images", action="store_true", help="strip images")
    parser.add_argument("--no-header", action="store_true",
                        help="omit the title/source metadata header")
    args = parser.parse_args(argv)

    html, base_url = read_input(args.input)
    base_url = base_url or None
    soup = BeautifulSoup(html, "lxml")

    header = "" if args.no_header else build_header(soup, args.input)

    strip_noise(soup)
    root = extract_main(soup) if args.main else (soup.body or soup)
    body = to_markdown(root, base_url, args.no_links, args.no_images)

    result = header + body
    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"html2llm: wrote {len(result):,} chars to {args.output}",
              file=sys.stderr)
    else:
        sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
