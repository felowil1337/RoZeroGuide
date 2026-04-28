#!/usr/bin/env python3
"""Replace the <aside class="sidebar">…</aside> block in every root-level HTML
page with the canonical version from _dev/_includes/nav.html.

Idempotent: re-running produces no diff. The current page's link gets
class="active" automatically, based on its filename.

Usage:
    python3 _dev/_tools/inject_nav.py            # all pages in repo root
    python3 _dev/_tools/inject_nav.py page.html  # just one
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "_dev" / "_includes" / "nav.html"

ASIDE_RE = re.compile(r'<aside class="sidebar">.*?</aside>', re.DOTALL)


def inject(page: Path, canonical_nav: str) -> bool:
    html = page.read_text(encoding="utf-8")
    if not ASIDE_RE.search(html):
        return False
    # Mark the current page's link active
    fname = page.name
    nav = re.sub(
        rf'<a href="{re.escape(fname)}">',
        f'<a href="{fname}" class="active">',
        canonical_nav,
        count=1,
    )
    new_html = ASIDE_RE.sub(lambda _: nav, html, count=1)
    if new_html == html:
        return False
    page.write_text(new_html, encoding="utf-8")
    return True


def main() -> None:
    canonical = SRC.read_text(encoding="utf-8").strip()
    if sys.argv[1:]:
        targets = [ROOT / p for p in sys.argv[1:]]
    else:
        targets = sorted(ROOT.glob("*.html"))
    changed = 0
    for p in targets:
        if inject(p, canonical):
            changed += 1
    print(f"injected nav into {changed}/{len(targets)} files")


if __name__ == "__main__":
    main()
