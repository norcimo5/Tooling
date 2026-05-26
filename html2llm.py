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
from urllib.request import Request, urlopen

import html2text
from bs4 import BeautifulSoup, Comment

# Tags that never carry readable content worth keeping.
HARD_NOISE = (
    "script", "style", "noscript", "template", "svg", "canvas",
    "iframe", "form", "button", "input", "select", "textarea", "dialog",
)

# Structural chrome — stripped only when it sits OUTSIDE an <article>, so that
# per-article <header>s (which hold story titles on listing pages) survive.
STRUCTURAL_NOISE = ("nav", "header", "footer", "aside")

# Query-string keys that are pure tracking — drop them from URLs (anything
# starting with "utm_" is also dropped).
TRACKING_PARAMS = {
    "gclid", "fbclid", "msclkid", "yclid", "mc_cid", "mc_eid", "igshid",
    "ref", "ref_src", "_hsenc", "_hsmi", "spm", "scm", "vero_id",
}


def strip_tracking(url: str) -> str:
    """Remove tracking parameters from a URL's query string."""
    if "?" not in url:
        return url
    base, _, query = url.partition("?")
    kept = [p for p in query.split("&")
            if not (p.split("=", 1)[0].startswith("utm_")
                    or p.split("=", 1)[0] in TRACKING_PARAMS)]
    return base + ("?" + "&".join(kept) if kept else "")

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

    for tag in soup(list(HARD_NOISE)):
        tag.decompose()

    # Drop site chrome but keep structural tags that live inside an article.
    for tag in soup(list(STRUCTURAL_NOISE)):
        if not tag.decomposed and not tag.find_parent("article"):
            tag.decompose()

    for tag in soup.find_all(True):
        # Decomposing a parent nulls out its descendants' attrs, so skip any
        # node already destroyed earlier in this loop.
        if tag.decomposed:
            continue
        attrs = tag.attrs or {}
        # Drop base64 data-URI images (token bombs) and 1px tracking pixels.
        if tag.name == "img":
            src = attrs.get("src", "")
            if (src.startswith("data:")
                    or attrs.get("width") in ("0", "1")
                    or attrs.get("height") in ("0", "1")):
                tag.decompose()
                continue
        # Drop explicitly hidden elements.
        if "hidden" in attrs or attrs.get("aria-hidden") == "true":
            tag.decompose()
            continue
        style = (attrs.get("style") or "").replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            tag.decompose()
            continue
        # Drop chrome/ads matched by id or class name.
        classes = attrs.get("class") or []
        ident = " ".join(filter(None, [attrs.get("id", ""), *classes]))
        if ident and NOISE_PATTERNS.search(ident):
            tag.decompose()
            continue
        # Strip title attrs — html2text echoes them after links/images as a
        # near-duplicate of the URL, wasting tokens.
        attrs.pop("title", None)
        # Drop tracking junk from link/image targets.
        for key in ("href", "src"):
            if key in attrs:
                attrs[key] = strip_tracking(attrs[key])


def extract_main(soup: BeautifulSoup):
    """Pick the node most likely to hold the article body."""
    for selector in ("main", "[role=main]"):
        node = soup.select_one(selector)
        if node and node.get_text(strip=True):
            return node

    # A single <article> is the page body; several <article>s means a listing
    # page (e.g. a news homepage), so don't collapse it to just the first one.
    articles = [a for a in soup.find_all("article") if a.get_text(strip=True)]
    if len(articles) == 1:
        return articles[0]

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
    conv.protect_links = False     # no <url> angle brackets (saves 2 chars/link)
    conv.mark_code = True          # tag <pre> blocks so we can fence them
    conv.ignore_links = ignore_links
    conv.ignore_images = ignore_images
    return normalize(conv.handle(str(node)))


def _fence_code(match: re.Match) -> str:
    """Turn an html2text [code]...[/code] block into a fenced code block."""
    inner = match.group(1)
    # html2text indents the block by 4 spaces; strip that base indent.
    lines = [ln[4:] if ln.startswith("    ") else ln for ln in inner.split("\n")]
    while lines and not lines[0].strip():    # drop blank edge lines
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "```\n" + "\n".join(lines) + "\n```"


def normalize(md: str) -> str:
    """Tighten Markdown so it carries the same information in fewer tokens."""
    md = re.sub(r"\[code\]\n?(.*?)\n?\[/code\]", _fence_code, md, flags=re.DOTALL)
    # Strip trailing whitespace, including Markdown hard-break markers.
    md = re.sub(r"[ \t]+$", "", md, flags=re.MULTILINE)
    # Exactly one space after a heading's #'s.
    md = re.sub(r"(?m)^(#{1,6})[ \t]+", r"\1 ", md)
    # Drop empty links/images (anchor text or alt was empty — just a bare URL).
    md = re.sub(r"!?\[\]\([^)]*\)", "", md)
    # Collapse runs of 3+ newlines into a single blank line.
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
    parser.add_argument("--stats", action="store_true",
                        help="print size/token reduction to stderr")
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

    if args.stats:
        report_stats(len(html), len(result))
    return 0


def report_stats(in_chars: int, out_chars: int) -> None:
    """Print a rough size/token reduction summary to stderr (~4 chars/token)."""
    cut = (in_chars - out_chars) / in_chars * 100 if in_chars else 0
    print(
        f"html2llm: {in_chars:,} -> {out_chars:,} chars  "
        f"(~{in_chars // 4:,} -> ~{out_chars // 4:,} tokens, {cut:.0f}% smaller)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
