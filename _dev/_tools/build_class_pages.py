#!/usr/bin/env python3
"""Build the 13 class-guide pages from midgardhub builds + ratemyserver skill data.

Inputs:
  _dev/_working/midgardhub/all_builds.json          (3 builds per class)
  _dev/_working/skills_complete/klasse-<slug>.json  (full skill list)
  klasse-<slug>.html                           (existing page; preserved sections)
  klasse-bard-dancer.html                      (existing combined page; reused for new bard + dancer)

Outputs: 13 klasse-<slug>.html files (rewritten in place / created).
Also: archive klasse-bard-dancer.html to _dev/_archive/.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path("/home/trusch/rozero")
BUILDS_PATH = ROOT / "_dev/_working/midgardhub/all_builds.json"
SKILLS_DIR = ROOT / "_dev/_working/skills_complete"
SPRITES_DIR = ROOT / "images/jobs"

# slug → (German-display name, City, builds-key in all_builds.json)
CLASSES = [
    ("knight",     "Knight",     "Prontera",   "knight"),
    ("crusader",   "Crusader",   "Prontera",   "crusader"),
    ("wizard",     "Wizard",     "Geffen",     "wizard"),
    ("sage",       "Sage",       "Juno",       "sage"),
    ("hunter",     "Hunter",     "Hugel",      "hunter"),
    ("bard",       "Bard",       "Comodo",     "bard"),
    ("dancer",     "Dancer",     "Comodo",     "bard"),  # same builds as Bard
    ("priest",     "Priest",     "Prontera",   "priest"),
    ("monk",       "Monk",       "Prontera",   "monk"),
    ("assassin",   "Assassin",   "Morroc",     "assassin"),
    ("rogue",      "Rogue",      "Comodo",     "rogue"),
    ("blacksmith", "Blacksmith", "Geffen",     "blacksmith"),
    ("alchemist",  "Alchemist",  "Al de Baran","alchemist"),
]

# Subtitles for hero — mostly come from existing pages (page lead). Falls back to a 1-sentence summary.
DEFAULT_LEADS = {
    "knight":     "2nd Job aus dem Swordsman-Pfad. Klassischer DPS-Krieger mit Spear- oder Two-Handed-Sword-Spezialisierung und PecoPeco-Mount für Move-Speed.",
    "crusader":   "2nd Job aus dem Swordsman-Pfad. Heiliger Tank mit Shield-Boomerang, Grand-Cross und holy-elementaren Buffs für Party und Solo.",
    "wizard":     "2nd Job aus dem Mage-Pfad. Premium-AoE-Caster mit Storm Gust, Meteor Storm und Lord of Vermilion. Die Klasse für MD-Clear.",
    "sage":       "2nd Job aus dem Mage-Pfad. Hybrid-Magier mit Auto-Spell, elementarer Endow-Unterstützung und PvP-tauglichen Anti-Magic-Tools.",
    "hunter":     "2nd Job aus dem Archer-Pfad. Long-Range-DPS mit Falcon-Auto-Hits, Trap-Setups und stärkster Single-Target-Burst-Skill (Double Strafe / Sharpshoot).",
    "bard":       "2nd Job aus dem Archer-Pfad (männlich). Solo-Songs und Ensembles mit der Dancer definieren die Klasse — Bragi, Apple of Idun und Tarot Card.",
    "dancer":     "2nd Job aus dem Archer-Pfad (weiblich). Pendant zum Bard mit Whip-Skills, eigenen Solo-Songs (Service for You, Humming) und Ensemble-Hälfte.",
    "priest":     "2nd Job aus dem Acolyte-Pfad. Klassische Heal/Buff-Klasse mit zusätzlichen Anti-Undead-DPS-Optionen (Magnus Exorcismus, Turn Undead).",
    "monk":       "2nd Job aus dem Acolyte-Pfad. Combo-Klasse mit Asura Strike (höchster Single-Hit-Damage im Spiel) und Triple Attack / Combo-Finish-Ketten.",
    "assassin":   "2nd Job aus dem Thief-Pfad. Dual-Wield-DPS mit Sonic Blow, Grimtooth, Cloaking und höchstem reinen ATK-Output.",
    "rogue":      "2nd Job aus dem Thief-Pfad. Plagiarism-kopierter Skill, Gangster Paradise zum AFK-Sitzen, Stealing-Profi mit Strip-Skills.",
    "blacksmith": "2nd Job aus dem Merchant-Pfad. Forger-Profi und Hybrid-DPS mit Cart Revolution, Mammonite und elementarer Weapon-Endow.",
    "alchemist":  "2nd Job aus dem Merchant-Pfad. Homunculus-AI-Farmer, Acid-Terror-Burster oder reiner Brewer — drei stark unterschiedliche Spielweisen.",
}

# Map skill type string → CSS class
def skill_css_class(skill_type: str | None) -> str:
    if not skill_type:
        return "active"
    t = skill_type.lower()
    if "passive" in t:
        return "passive"
    if any(k in t for k in ("support", "buff", "ensemble", "instrumental")):
        return "buff"
    return "active"

def skill_short_type(skill_type: str | None) -> str:
    if not skill_type:
        return "Active"
    # Take first word before comma
    return skill_type.split(",")[0].strip()


def load_existing_page(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


# Generic <section>…</section> matcher that extracts a section whose first <h2> contains a needle.
SECTION_RE = re.compile(r"<section[^>]*>.*?</section>", re.DOTALL)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)


def find_section(html_text: str, needle: str) -> str | None:
    for m in SECTION_RE.finditer(html_text):
        body = m.group(0)
        h2 = H2_RE.search(body)
        if h2 and needle.lower() in h2.group(1).lower():
            return body
    return None


# Extract existing lead text from page-hero
LEAD_RE = re.compile(r'<p class="lead">(.*?)</p>', re.DOTALL)


def find_lead(html_text: str) -> str | None:
    m = LEAD_RE.search(html_text)
    return m.group(1).strip() if m else None


def render_stat_pills(stats: list[dict]) -> str:
    pills = []
    for s in stats:
        attr = s.get("attr", "STR")
        val = s.get("val", "")
        desc = s.get("desc", "")
        pills.append(
            f'<span class="stat-pill stat-pill--{attr.lower()}" data-attr="{html.escape(attr)}">'
            f'<strong class="pill-attr">{html.escape(attr)}</strong>'
            f'<strong class="pill-val">{html.escape(val)}</strong>'
            f'<span class="pill-note">{html.escape(desc)}</span>'
            f'</span>'
        )
    return '<div class="stat-pills">\n  ' + "\n  ".join(pills) + "\n</div>"


def render_priority_skills(skills: list[dict]) -> str:
    items = []
    for s in skills:
        name = html.escape(s.get("name", ""))
        desc = html.escape(s.get("desc", ""))
        items.append(f"  <li><strong>{name}</strong> — {desc}</li>")
    return '<ul class="priority-skills">\n' + "\n".join(items) + "\n</ul>"


def render_build_section(build: dict) -> str:
    title = html.escape(build.get("title", ""))
    subtitle = html.escape(build.get("subtitle", ""))
    overview = html.escape(build.get("overview", ""))
    tip = html.escape(build.get("tip", ""))

    pills = render_stat_pills(build.get("stats", []))
    skills = render_priority_skills(build.get("skills", []))

    return f"""  <section class="build-section">
    <header style="border-left:4px solid var(--accent);padding-left:16px;margin-bottom:12px">
      <h2>{title}</h2>
      <p style="text-transform:uppercase;letter-spacing:0.05em;font-size:13px;color:var(--accent);font-weight:700;margin:4px 0">{subtitle}</p>
      <p>{overview}</p>
    </header>

    <h3>Optimaler Stat-Spread</h3>
    {pills}

    <h3>Priority-Skills für diesen Build</h3>
    {skills}

    <div class="info-box tip">
      <strong>💡 Pro-Tipp:</strong> {tip}
    </div>
  </section>"""


def render_skill_block(skill: dict) -> str:
    name = html.escape(skill.get("name", ""))
    type_ = skill_short_type(skill.get("type"))
    max_lv = skill.get("max_level")
    lv_str = f"Lv {max_lv}" if max_lv else "Lv —"
    css = skill_css_class(skill.get("type"))
    prereq = skill.get("prereq")
    prereq_text = html.escape(prereq) if prereq else "keine"
    desc = html.escape(skill.get("description", ""))
    return f"""    <div class="skill-block {css}">
      <h5>{name} <span class="skill-tag">{html.escape(type_)} · {lv_str}</span></h5>
      <p class="skill-prereq">Voraussetzung: {prereq_text}</p>
      <p class="skill-desc">{desc}</p>
    </div>"""


def render_skill_tree(skill_data: dict) -> str:
    skills = skill_data.get("skills", [])
    first = [s for s in skills if s.get("tier") == "first"]
    second = [s for s in skills if s.get("tier") == "second"]
    total = len(skills)
    first_job = html.escape(skill_data.get("first_job", ""))
    second_job = html.escape(skill_data.get("second_job", ""))

    first_blocks = "\n".join(render_skill_block(s) for s in first)
    second_blocks = "\n".join(render_skill_block(s) for s in second)

    return f"""  <section>
    <h2>Komplette Skill-Liste</h2>
    <p>Alle {total} Skills der {first_job} → {second_job} Klasse. Quelle: ratemyserver.net.</p>

    <h3>1. Job — {first_job} ({len(first)} Skills)</h3>
    <div class="skill-tree">
{first_blocks}
    </div>

    <h3>2. Job — {second_job} ({len(second)} Skills)</h3>
    <div class="skill-tree">
{second_blocks}
    </div>
  </section>"""


def render_hero(slug: str, klass: str, city: str, lead: str, sprite_exists: bool) -> str:
    eyebrow = f'<span class="eyebrow">Klassen · {html.escape(city)}</span>'
    sprite_img = ""
    if sprite_exists:
        sprite_img = (
            f'<img src="images/jobs/{slug}.png" alt="{html.escape(klass)} sprite" '
            f'style="width:64px;height:64px;image-rendering:pixelated">'
        )
    return f"""  <div class="page-hero">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      {sprite_img}
      <div>
        {eyebrow}
        <h1>{html.escape(klass)}</h1>
        <p class="lead">{lead}</p>
      </div>
    </div>
  </div>"""


CROSSLINKS = (
    '  <p>Cross-Links: <a href="klassen.html">Klassen-Übersicht</a> · '
    '<a href="leveling.html">Level-Routen</a> · '
    '<a href="ausruestung.html">Ausrüstung</a> · '
    '<a href="md-equipment.html">MD-Equipment</a></p>'
)


SHELL_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Klasse {klass} — RO Zero Guide</title>
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
{NAV_PLACEHOLDER}

  <main>
{MAIN_BODY}
  </main>

</div>

<footer class="footer">
  Quellen: <a href="https://www.midgardhub.com/" target="_blank" rel="noopener">Midgard Hub</a> · <a href="https://old.criatura-academy.com/" target="_blank" rel="noopener">Criatura Academy</a> · <a href="https://wiki.playragnarokzero.com/" target="_blank" rel="noopener">Project Zero Wiki</a> · <a href="https://ratemyserver.net/" target="_blank" rel="noopener">RateMyServer</a>
</footer>

</body>
</html>
"""


def build_page(slug: str, klass: str, city: str, builds_key: str,
               builds: dict, skills_data: dict, equipment_section: str,
               milestones_section: str, lead: str, sprite_exists: bool) -> str:
    builds_for_class = builds[builds_key]
    build_keys = list(builds_for_class.keys())  # 3 keys

    parts = [render_hero(slug, klass, city, lead, sprite_exists)]
    for bk in build_keys:
        parts.append(render_build_section(builds_for_class[bk]))
    parts.append(render_skill_tree(skills_data))
    if equipment_section:
        parts.append("  " + equipment_section)
    if milestones_section:
        parts.append("  " + milestones_section)
    parts.append(CROSSLINKS)

    main_body = "\n\n".join(parts)
    # NAV_PLACEHOLDER: leave a stub aside; inject_nav.py will overwrite.
    nav_stub = '  <aside class="sidebar"><nav><ul></ul></nav></aside>'
    return SHELL_TEMPLATE.format(
        klass=klass, NAV_PLACEHOLDER=nav_stub, MAIN_BODY=main_body
    )


def main():
    builds = json.loads(BUILDS_PATH.read_text(encoding="utf-8"))

    # Read existing combined bard-dancer page once (used for both new pages).
    bd_path = ROOT / "klasse-bard-dancer.html"
    bd_html = load_existing_page(bd_path)
    bd_equipment = find_section(bd_html, "Empfohlene Ausrüstung") or ""
    bd_milestones = find_section(bd_html, "Level-Milestones") or ""

    report_lines = []
    total_bytes = 0

    for slug, klass, city, builds_key in CLASSES:
        skill_path = SKILLS_DIR / f"klasse-{slug}.json"
        skills_data = json.loads(skill_path.read_text(encoding="utf-8"))

        existing_path = ROOT / f"klasse-{slug}.html"
        existing_html = load_existing_page(existing_path)

        if slug in ("bard", "dancer"):
            equipment = bd_equipment
            milestones = bd_milestones
            lead = DEFAULT_LEADS[slug]
        else:
            equipment = find_section(existing_html, "Empfohlene Ausrüstung") or ""
            milestones = find_section(existing_html, "Level-Milestones") or ""
            lead = find_lead(existing_html) or DEFAULT_LEADS.get(slug, "")

        sprite_path = SPRITES_DIR / f"{slug}.png"
        sprite_exists = sprite_path.exists()

        page_html = build_page(
            slug, klass, city, builds_key, builds, skills_data,
            equipment, milestones, lead, sprite_exists,
        )
        existing_path.write_text(page_html, encoding="utf-8")
        sz = existing_path.stat().st_size
        total_bytes += sz

        n_first = sum(1 for s in skills_data["skills"] if s["tier"] == "first")
        n_second = sum(1 for s in skills_data["skills"] if s["tier"] == "second")
        report_lines.append(
            f"  {slug:11s}: 1st={n_first:2d} 2nd={n_second:2d} builds=3 "
            f"sprite={'y' if sprite_exists else 'n'} bytes={sz}"
        )

    # Archive bard-dancer
    archive_path = ROOT / "_dev/_archive/klasse-bard-dancer.html"
    if bd_path.exists():
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(bd_path), str(archive_path))
        report_lines.append(f"  archived: {bd_path.name} -> {archive_path}")

    print("\n".join(report_lines))
    print(f"  total bytes written: {total_bytes}")


if __name__ == "__main__":
    main()
