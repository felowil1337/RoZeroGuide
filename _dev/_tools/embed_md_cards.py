#!/usr/bin/env python3
"""For each MD section in instanzen.html, embed monster cards and drop cards
directly inline (between MD_CARDS markers). Idempotent — re-running replaces
the marked block.

The MD section gets a new subsection at the bottom:
  <h4>👾 Mobs in dieser Instanz</h4>
  <div class="entry-grid">…monster cards…</div>
  <h4>📦 Drops · Normal Mode</h4>
  <div class="entry-grid">…item cards…</div>
  <h4>📦 Drops · Hard Mode</h4>
  <div class="entry-grid">…item cards…</div>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "_dev" / "_tools"))
from generate_pages import render_item_card, render_monster_card  # noqa: E402

EXTRACT = ROOT / "_dev" / "_working" / "criatura-extracted"

MARKER_START = "<!-- MD_CARDS:START {slug} -->"
MARKER_END = "<!-- MD_CARDS:END {slug} -->"
BLOCK_RE = re.compile(
    r"<!-- MD_CARDS:START ([a-z0-9-]+) -->.*?<!-- MD_CARDS:END \1 -->",
    re.DOTALL,
)


def load_md(slug: str) -> dict | None:
    f = EXTRACT / "memorial-dungeons" / f"{slug}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def load_item_by_id(kro_id: str) -> dict | None:
    f = EXTRACT / "items" / f"{kro_id}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def render_drop_grid(drops: list[dict]) -> str:
    cards = []
    for d in drops:
        kid = d.get("kro_id")
        if not kid:
            continue
        # Prefer the full item record (has stats); fall back to the drop entry
        item = load_item_by_id(kid) or d
        cards.append(render_item_card(item))
    if not cards:
        return ""
    return '<div class="entry-grid">\n' + "\n".join(cards) + "\n</div>"


def build_block(slug: str, md: dict) -> str:
    """Insert a small link-out card pointing to the dedicated md-<slug>.html
    detail page. Replaces earlier inline card grids — those duplicate the
    detail page's content and bloat instanzen.html."""
    n_mons = len(md.get("monsters", []))
    n_normal = len(md.get("drops_normal", []))
    n_hard = len(md.get("drops_hard", []))
    bits: list[str] = []
    if n_mons:    bits.append(f'{n_mons} Monster')
    if n_normal:  bits.append(f'{n_normal} Normal-Drops')
    if n_hard:    bits.append(f'{n_hard} Hard-Drops')
    summary = " · ".join(bits) if bits else "Detail-Daten verfügbar"

    block = f"""{MARKER_START.format(slug=slug)}
      <a href="md-{slug}.html" class="md-detail-link">
        <span class="md-detail-link-arrow">📖</span>
        <span class="md-detail-link-text">
          <strong>Komplette Detail-Seite öffnen</strong>
          <span class="md-detail-link-meta">{summary} mit Stats, Icons und Bildern aus criatura-academy</span>
        </span>
        <span class="md-detail-link-chev">→</span>
      </a>
      {MARKER_END.format(slug=slug)}"""
    return block


def embed_in_instanzen() -> None:
    page = ROOT / "instanzen.html"
    html = page.read_text()

    # First, remove all existing MD_CARDS blocks (so we can re-insert idempotently)
    html = BLOCK_RE.sub("", html)
    # Drop the per-section "Detail-Links" callouts since data is now inline
    html = re.sub(
        r'<div class="entry-jump" style="margin-top:8px">'
        r'<a href="monster\.html#dg-[a-z0-9-]+">[^<]*</a>'
        r'<a href="items\.html#sec-[a-z0-9-]+">[^<]*</a>'
        r'</div>\s*',
        "",
        html,
    )

    md_files = list((EXTRACT / "memorial-dungeons").glob("*.json"))
    inserted = 0
    for f in md_files:
        md = json.loads(f.read_text())
        slug = md["slug"]
        # Find the closing </section> for the section with id="<slug>"
        section_re = re.compile(
            r'(<section id="' + re.escape(slug) + r'">.*?)</section>',
            re.DOTALL,
        )
        m = section_re.search(html)
        if not m:
            print(f"  [miss] no <section id=\"{slug}\"> in instanzen.html")
            continue
        block = build_block(slug, md)
        replacement = m.group(1) + "\n      " + block + "\n    </section>"
        html = html[: m.start()] + replacement + html[m.end():]
        inserted += 1

    page.write_text(html)
    print(f"Embedded MD cards into {inserted} sections of instanzen.html")


if __name__ == "__main__":
    embed_in_instanzen()
