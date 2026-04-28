#!/usr/bin/env python3
"""Apply an agent's JSON-encoded multi-page output.

Expects a file containing JSON of the form:
{
  "fever_main": "<main>...</main>",
  "fever_pages": {"slug-a": "<main>...</main>", "slug-b": "<main>...</main>"}
}

Writes one file per entry (fever-main → fever.html, fever_pages.<slug> →
<slug>.html), wrapping each main block in the standard wiki page template.
Calls inject_nav.py at the end.
"""
from __future__ import annotations
import argparse
import html as html_lib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — RO Zero Guide</title>
<link rel="stylesheet" href="style.css">
</head>
<body>

<header class="topbar">
  <div class="topbar-inner">
    <a href="index.html" class="brand">
      <span class="brand-title">Ragnarok Zero</span>
      <span class="brand-subtitle">Global Guide · Deutsch</span>
    </a>
  </div>
</header>

<input type="checkbox" id="nav-toggle" class="nav-toggle">
<div class="layout">
  <label for="nav-toggle" class="nav-toggle-label">Navigation</label>
  <aside class="sidebar"></aside>

  {main_block}

</div>

<footer class="footer">
  Quellen: <a href="https://www.midgardhub.com/" target="_blank" rel="noopener">Midgard Hub</a> · <a href="https://old.criatura-academy.com/" target="_blank" rel="noopener">Criatura Academy</a> · <a href="https://wiki.playragnarokzero.com/" target="_blank" rel="noopener">Project Zero Wiki</a>
</footer>

</body>
</html>
"""


def extract_main(text: str) -> str:
    """Pull <main>…</main> from text. Handles HTML-encoded variant too."""
    m = re.search(r"<main\b.*?</main>", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(0)
    m = re.search(r"&lt;main\b.*?&lt;/main&gt;", text, re.DOTALL | re.IGNORECASE)
    if m:
        return html_lib.unescape(m.group(0))
    return text  # assume already a bare <main> block


def title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_json_file")
    ap.add_argument("--main-key", required=True, help='JSON key for the overview page (e.g. "fever_main")')
    ap.add_argument("--main-target", required=True, help='Target HTML for the overview (e.g. "fever.html")')
    ap.add_argument("--pages-key", required=True, help='JSON key for the per-detail pages (e.g. "fever_pages")')
    ap.add_argument("--main-title", default="")
    args = ap.parse_args()

    raw = Path(args.agent_json_file).read_text(encoding="utf-8")

    # Extract the JSON block (may be wrapped in code fences or commentary)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise SystemExit("no JSON block found")
    data = json.loads(m.group(0))

    # Overview page
    main_target = ROOT / args.main_target
    main_block = extract_main(data[args.main_key])
    title = args.main_title or main_target.stem.replace("-", " ").title()
    main_target.write_text(PAGE_TEMPLATE.format(title=title, main_block=main_block), encoding="utf-8")
    print(f"wrote {main_target.name}: {main_target.stat().st_size}b")

    # Per-page outputs
    for slug, body in data[args.pages_key].items():
        target = ROOT / f"{slug}.html"
        page_main = extract_main(body)
        page_title = title_from_slug(slug)
        target.write_text(PAGE_TEMPLATE.format(title=page_title, main_block=page_main), encoding="utf-8")
        print(f"wrote {target.name}: {target.stat().st_size}b")

    subprocess.run([sys.executable, str(ROOT / "_dev" / "_tools" / "inject_nav.py")], check=True)


if __name__ == "__main__":
    main()
