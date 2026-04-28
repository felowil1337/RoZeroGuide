#!/usr/bin/env python3
"""Apply an agent-generated <main> block to a target wiki page.

Usage: apply_agent_main.py <target_html> <agent_output_file> [--title "Page Title"]

The agent output file contains either raw HTML or HTML-encoded text
(&lt;main&gt;…&lt;/main&gt;). We extract the main block, unescape entities, and
write the full page using the wiki's standard template. inject_nav.py is
called at the end so the sidebar fills in.
"""
from __future__ import annotations

import argparse
import html
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
  Quellen: <a href="https://www.midgardhub.com/" target="_blank" rel="noopener">Midgard Hub</a> · <a href="https://old.criatura-academy.com/" target="_blank" rel="noopener">Criatura Academy</a> · <a href="https://wiki.playragnarokzero.com/" target="_blank" rel="noopener">Project Zero Wiki</a> · <a href="https://www.rozskill.me/" target="_blank" rel="noopener">rozskill.me</a>
</footer>

</body>
</html>
"""


def extract_main(text: str) -> str:
    """Pull the <main>...</main> block out of an agent response. Handles both
    raw HTML and HTML-encoded text (&lt;main&gt;)."""
    m = re.search(r"<main\b.*?</main>", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(0)
    m = re.search(r"&lt;main\b.*?&lt;/main&gt;", text, re.DOTALL | re.IGNORECASE)
    if m:
        return html.unescape(m.group(0))
    raise SystemExit("could not find <main>...</main> in input")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("target_html")
    ap.add_argument("agent_output_file")
    ap.add_argument("--title", default="")
    args = ap.parse_args()

    raw = Path(args.agent_output_file).read_text(encoding="utf-8")
    main_block = extract_main(raw)

    target = ROOT / args.target_html
    title = args.title or target.stem.replace("-", " ").title()
    html_out = PAGE_TEMPLATE.format(title=title, main_block=main_block)
    target.write_text(html_out, encoding="utf-8")
    print(f"wrote {target.name}: {target.stat().st_size}b")

    subprocess.run([sys.executable, str(ROOT / "_dev" / "_tools" / "inject_nav.py")], check=True)


if __name__ == "__main__":
    main()
