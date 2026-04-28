#!/usr/bin/env python3
"""Embed item / monster / skill cards inline into existing guide pages.

The DB pages (items.html, monster.html, skills.html, crafting.html) are the
reference. The guide pages (instanzen.html, ausruestung.html, enchant-*.html,
klassen.html) tell players what to do — but should *show* the relevant items,
mobs, and skills inline so readers don't have to flip back and forth.

This script applies a declarative manifest. Each entry says: in PAGE, find the
H2 whose text contains ANCHOR, walk to the end of that <section>, and embed a
card grid. Idempotent via marker comments.
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

# ── data loaders ─────────────────────────────────────────────────────────
def all_items() -> list[dict]:
    out = []
    for f in (EXTRACT / "items").glob("*.json"):
        if f.name.startswith("_"): continue
        out.append(json.loads(f.read_text()))
    return out


def all_skills() -> list[dict]:
    out = []
    for f in (EXTRACT / "skills").glob("*.json"):
        if f.name.startswith("_"): continue
        out.append(json.loads(f.read_text()))
    return out


# ── card renderer for skills (inline variant) ───────────────────────────
def render_skill_card(sk: dict) -> str:
    title = sk.get("title") or sk.get("slug")
    f_ = sk.get("fields", {})
    meta_lines = []
    for label, key in [("Max Level", "max_level"), ("Type", "skill_kind"),
                       ("Target", "target"), ("Prerequisite", "prerequisite")]:
        v = f_.get(key)
        if v: meta_lines.append(f'<li><strong>{label}:</strong> {v}</li>')
    lvls = sk.get("level_effects") or {}
    per = sk.get("per_level_lists") or {}
    table = ""
    if lvls or per:
        max_lv = max([int(k) for k in lvls.keys()] + [len(v) for v in per.values()] + [0])
        ord_keys = ["sp_cost", "fixed_casting", "variable_casting", "skill_cooldown"]
        if max_lv:
            head = "<tr><th>Lv</th><th>Effekt</th>"
            for k in ord_keys:
                if k in per:
                    head += f'<th>{k.replace("_", " ").title()}</th>'
            head += "</tr>"
            rows = ""
            for i in range(1, max_lv + 1):
                row = f"<tr><td>{i}</td><td>{lvls.get(str(i), '')}</td>"
                for k in ord_keys:
                    if k in per:
                        a = per[k]
                        row += f"<td>{a[i-1] if i-1 < len(a) else ''}</td>"
                row += "</tr>"
                rows += row
            table = f'<div class="table-wrap" style="margin:8px 12px 12px"><table><thead>{head}</thead><tbody>{rows}</tbody></table></div>'
    foot = f'<div class="entry-card-foot"><a href="skills.html#skill-{sk["slug"]}">In Skill-DB ↗</a></div>'
    meta_html = f'<ul class="entry-meta">{"".join(meta_lines)}</ul>' if meta_lines else ""
    return f"""<div class="entry-card is-skill">
  <div class="entry-card-head">
    <span class="entry-name">{title}</span>
    <span class="entry-type">Skill</span>
  </div>
  {meta_html}
  {table}
  {foot}
</div>"""


# ── manifest ─────────────────────────────────────────────────────────────
# Each entry: where to embed, what to embed.
# - page:    target HTML file in repo root
# - anchor:  substring to find in an <h2>; we extend the section to end of </section>
# - block_id: unique id used in marker comments (idempotent re-runs)
# - title:   the H4 we add at the start of the embed
# - kind:    "items" | "monsters" | "skills"
# - filter:  callable taking the entity, returning bool
# - lead:    optional German caption shown above the grid

MANIFEST = [
    # ── ausruestung.html ───────────────────────────────────────────────
    {
        "page": "ausruestung.html",
        "anchor": "Memorial-Dungeon Gear",
        "block_id": "md-pretrans",
        "title": "📦 Memorial-Set (Subjugation IV + Expedition III) — Items im Detail",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith(("Subjugation", "Expedition")),
        "lead": "Die beiden Pre-Trans-Grades. Subjugation droppt direkt aus den 60er-MDs, Expedition wird aus Subjugation gecraftet (siehe <a href=\"crafting.html\">Crafting</a>).",
        "group_by_section": True,
    },
    # ── endgame-ausruestung.html ───────────────────────────────────────
    {
        "page": "endgame-ausruestung.html",
        "anchor": "Memorial",
        "block_id": "md-endgame",
        "title": "📦 Memorial-Set (Dispatching II + Conqueror I) — Endgame-Items",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith(("Dispatching", "Conqueror")),
        "lead": "Die Trans-Tier-Grades. Dispatching (Lv 80) und Conqueror (Lv 90) werden über mehrere Crafting-Stufen aus dem Pre-Trans-Set hochgezogen.",
        "group_by_section": True,
    },
    # ── enchant-subjugation.html ───────────────────────────────────────
    {
        "page": "enchant-subjugation.html",
        "anchor": "Zielausrüstung",
        "block_id": "subj-items",
        "title": "📦 Subjugation-Set — die enchantbare Zielausrüstung",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Subjugation"),
        "lead": "Diese vier Items sind das Ziel des 60MD-Subjugation-Enchant-Pools.",
    },
    # ── enchant-expedition.html ────────────────────────────────────────
    {
        "page": "enchant-expedition.html",
        "anchor": "Zielausrüstung",
        "block_id": "exp-items",
        "title": "📦 Expedition-Set — Zielausrüstung",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Expedition"),
        "lead": "Acht Items im Expedition-Set, gecraftet aus dem Subjugation-Set.",
    },

    # ── md-equip-overview.html — show actual items per grade ────────────
    {
        "page": "md-equip-overview.html",
        "anchor": "Die vier Grades",
        "block_id": "ov-subjugation",
        "title": "🛡️ Grade IV — Subjugation Set (4 Items, Drop)",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Subjugation"),
        "lead": "Die vier Drop-Items aus den 60er-Memorial-Dungeons. Basis der gesamten Crafting-Kette.",
    },
    {
        "page": "md-equip-overview.html",
        "anchor": "Crafting-Kette",
        "block_id": "ov-expedition",
        "title": "🛡️ Grade III — Expedition Set (8 Items, gecraftet)",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Expedition"),
        "lead": "Erste Spezialisierung in physische und magische Varianten. Aus Subjugation-Teilen + Shimmering Crystal + Jello-Stones.",
    },
    {
        "page": "md-equip-overview.html",
        "anchor": "Set-Bonus",
        "block_id": "ov-dispatching",
        "title": "🛡️ Grade II — Dispatching Set (16 Items, gecraftet)",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Dispatching"),
        "lead": "Hier verzweigen sich die Sub-Sets vollständig (melee, ranged, magisch-DD, magisch-support).",
    },
    {
        "page": "md-equip-overview.html",
        "anchor": "Enchanting",
        "block_id": "ov-conqueror",
        "title": "🛡️ Grade I — Conqueror Set (16 Items, gecraftet)",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Conqueror"),
        "lead": "Endgame der Memorial-Equipment-Kette. Items werden bei +9 enchant-fähig für Job-Essences.",
    },
    {
        "page": "md-equip-overview.html",
        "anchor": "Hard-Mode-Accessoires",
        "block_id": "ov-hardmode",
        "title": "💎 Hard-Mode-Accessoires (4 Items)",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Hard Mode"),
        "lead": "Slot-1-Accessoires aus Hard-Mode-Drops — eigenständig, nicht in der Subjugation→Conqueror-Kette.",
    },

    # ── md-equip-crafting.html — embed materials ────────────────────────
    {
        "page": "md-equip-crafting.html",
        "anchor": "Material-Strom",
        "block_id": "craft-materials",
        "title": "📦 Crafting-Materialien — die Rohstoffe im Detail",
        "kind": "items",
        "filter": lambda it: it.get("kro_id") in {
            "25424",  # Shimmering Crystal (Subj→Exp)
            "25475",  # Azure Crystal (Exp→Disp)
            "25476",  # Crimson Crystal (Disp→Conq)
            "25429",  # Mithril Ore (Hard-Mode-Acc)
            "23649",  # Jello Fragment Box
            "25457",  # Cursed Emerald
            "25458",  # Shiny Opal
            "25459",  # Sea Sapphire
            "25460",  # Blood-soaked Ruby
        },
        "lead": "Crystals (50× pro Craft-Schritt), Mithril (10× pro Hard-Mode-Acc), Hard-Mode-Edelsteine (15× pro Acc) und Jello Fragment Box (Wochentag-Drop, basis der Jello-Stones).",
    },

    # ── instanzen.html — show all MD bosses ─────────────────────────────
    {
        "page": "instanzen.html",
        "anchor": "Verfügbare Instanzen",
        "block_id": "md-bosses",
        "title": "👑 Memorial-Dungeon-Bosse — Übersicht",
        "kind": "monsters",
        "filter": lambda m: (m.get("class_type") or "").lower() == "boss"
                            and m.get("appears_in"),
        "lead": "Alle Final-Bosse der dokumentierten Memorial-Dungeons mit Level, HP und Element auf einen Blick. Klick auf den Namen öffnet Divine Pride mit den Skill-Daten.",
    },
    {
        "page": "instanzen.html",
        "anchor": "Equipment-Loop",
        "block_id": "md-loop-items",
        "title": "📦 Subjugation-Set (Grade IV) — der Drop-Einstieg",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Subjugation"),
        "lead": "Diese vier Items droppen direkt aus den 60er-MDs (Orc's Memory + Prontera Culvert) und sind die Basis des Equipment-Loops.",
    },

    # ── md-equipment.html (hub) — show grade-set quick-access cards ─────
    {
        "page": "md-equipment.html",
        "anchor": "Quick-Access",
        "block_id": "hub-subjugation",
        "title": "🛡️ Subjugation-Items (Grade IV)",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Subjugation"),
        "lead": "Die vier Drop-Items als Einstieg in die Crafting-Kette.",
    },
    {
        "page": "md-equipment.html",
        "anchor": "Empfohlener Pfad",
        "block_id": "hub-conqueror",
        "title": "🛡️ Conqueror-Items (Grade I) — das Endziel",
        "kind": "items",
        "filter": lambda it: it.get("source_section", "").startswith("Conqueror"),
        "lead": "16 Items, +9 enchantbar mit klassen-spezifischen Job-Essences.",
    },

]


# ── embedding engine ─────────────────────────────────────────────────────
SECTION_END_RE = re.compile(r"</section>")


def find_section_for_h2(html: str, anchor: str) -> tuple[int, int] | None:
    """Return (section_open_pos, section_close_pos) for the <section>
    containing an <h2> whose text includes anchor."""
    # Find all <section> open tags and their bodies
    for sec_m in re.finditer(r"<section\b[^>]*>", html):
        start = sec_m.start()
        end_m = re.search(r"</section>", html[sec_m.end():])
        if not end_m:
            continue
        end = sec_m.end() + end_m.start()
        section_html = html[sec_m.end():end]
        # Look for h2 with anchor text
        h2 = re.search(r"<h2\b[^>]*>(.*?)</h2>", section_html, re.DOTALL)
        if h2 and anchor.lower() in re.sub(r"<[^>]+>", "", h2.group(1)).lower():
            return start, sec_m.end() + end_m.start()
    return None


def render_block(entry: dict) -> str:
    block_id = entry["block_id"]
    parts: list[str] = [f'<!-- EMBED:START {block_id} -->']
    parts.append('      <div style="margin-top:32px;border-top:2px dashed var(--border);padding-top:16px">')
    parts.append(f'        <h4>{entry["title"]}</h4>')
    if entry.get("lead"):
        parts.append(f'        <p style="color:var(--text-dim);font-size:13px;margin-top:0">{entry["lead"]}</p>')

    if entry["kind"] == "items":
        items = [i for i in all_items() if entry["filter"](i)]
        if not items:
            parts.append('        <p><em>Keine Daten verfügbar.</em></p>')
        elif entry.get("group_by_section"):
            by_section: dict[str, list[dict]] = {}
            for it in items:
                by_section.setdefault(it.get("source_section", "Sonstige"), []).append(it)
            for sec, lst in by_section.items():
                parts.append(f'        <h5 style="margin-top:18px">{sec}</h5>')
                parts.append('        <div class="entry-grid">')
                parts.extend(f'          {render_item_card(it)}' for it in lst)
                parts.append('        </div>')
        else:
            parts.append('        <div class="entry-grid">')
            parts.extend(f'          {render_item_card(it)}' for it in items)
            parts.append('        </div>')

    elif entry["kind"] == "monsters":
        # not used yet but supported
        from generate_pages import load_monsters
        mons = [m for m in load_monsters() if entry["filter"](m)]
        parts.append('        <div class="entry-grid wide">')
        parts.extend(f'          {render_monster_card(m)}' for m in mons)
        parts.append('        </div>')

    elif entry["kind"] == "skills":
        skills = [s for s in all_skills() if entry["filter"](s)]
        if not skills:
            parts.append('        <p><em>Keine Daten verfügbar.</em></p>')
        else:
            parts.append('        <div class="entry-grid wide">')
            parts.extend(f'          {render_skill_card(s)}' for s in skills)
            parts.append('        </div>')

    parts.append('      </div>')
    parts.append(f'<!-- EMBED:END {block_id} -->')
    return "\n      ".join(parts)


def apply_entry(entry: dict) -> str:
    page = ROOT / entry["page"]
    if not page.exists():
        return f'  [miss] {entry["page"]} not found'
    html = page.read_text()

    # Remove any existing block with this ID (idempotency)
    bid = re.escape(entry["block_id"])
    html = re.sub(
        rf'\s*<!-- EMBED:START {bid} -->.*?<!-- EMBED:END {bid} -->\s*',
        "\n      ",
        html,
        flags=re.DOTALL,
    )

    # Find the target section
    span = find_section_for_h2(html, entry["anchor"])
    if span is None:
        page.write_text(html)
        return f'  [miss] {entry["page"]}: anchor "{entry["anchor"]}" not found'
    _, section_close = span

    block = render_block(entry)
    new_html = html[:section_close] + "\n      " + block + "\n    " + html[section_close:]
    page.write_text(new_html)

    # Quick sanity: count cards inserted
    n = block.count('class="entry-card')
    return f'  [ok]   {entry["page"]} <- {entry["block_id"]} ({n} cards)'


def main() -> None:
    for entry in MANIFEST:
        print(apply_entry(entry))


if __name__ == "__main__":
    main()
